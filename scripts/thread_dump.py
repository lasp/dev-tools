#!/usr/bin/env python3
"""Write a pull request's thread dump from the GitHub MCP server's pages, as they were returned.

`pr-reader` saves each `pull_request_read` result under the dump's `pages/` as it came back: the
text the tool returned, or the file the harness saved a long result to, copied byte for byte.
Never retyped, since a hand-built copy drops fields, such as a comment's line or a bot's review
table, that nothing downstream would notice. This script joins and checks them:

The server leaves out a field that is empty rather than sending null: a review posted with a
batch of thread replies has no `body`, an open pull request's `get` no `merged_at`, an empty
description no `body`. So only the fields every item carries are required; `record.py` refuses
an absent field where it needs one.

- `get.json`, the `get` result: an object with `number`, `user.login`, `state`, `draft`, `merged`
  and `head.sha`.
- `get_reviews-<n>.json` and `get_comments-<n>.json`, n from 1 with no gap, each a list, fetched
  100 to a page: every page but the last holds 100, and the last fewer. A review carries `id`,
  `state`, `html_url` and `user.login`; a conversation comment
  `id`, `body`, `html_url`, `created_at` and `user.login`.
- `get_review_comments-<n>.json`, n from 1 with no gap, each an object with `review_threads`,
  `pageInfo.hasNextPage` (true on every page but the last) and `totalCount`, which the threads of
  all pages together must number. A thread carries `id`, `is_resolved`, `is_outdated` and a
  non-empty `comments`, each with `author`, `body`, `created_at`, `html_url` and `path`.

It writes `pr.json`, a copy of `get.json`; `reviews.json` and `issue-comments.json`, each the pages'
items in one list; `comments.json`, `{"review_threads": [...]}` over all pages; and `body.md`, the
body, empty when `get` has none. A page missing, out of sequence or not JSON, paging that stops early, or an item missing a
field above exits 1 with the reason and writes nothing, as does a dump directory not named
`pr-NNNN`, the number padded to four digits. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PER_PAGE = 100
REVIEW = ("id", "state", "html_url", "user.login")
COMMENT = ("id", "body", "html_url", "created_at", "user.login")
THREAD = ("id", "is_resolved", "is_outdated", "comments")
THREAD_COMMENT = ("author", "body", "created_at", "html_url", "path")
PR = ("number", "user.login", "state", "draft", "merged", "head.sha")


class Refused(Exception):
    """A page the dump cannot be built from."""


def has(item, field: str) -> bool:
    for part in field.split("."):
        if not isinstance(item, dict) or part not in item:
            return False
        item = item[part]
    return True


def check(item, fields: tuple[str, ...], where: str) -> None:
    gone = [f for f in fields if not has(item, f)]
    if gone:
        raise Refused(f"{where} has no {', '.join(repr(f) for f in gone)}")


def load(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise Refused(f"{path.name} cannot be read as JSON: {e}") from e


def pages(directory: Path, method: str) -> list[tuple[str, object]]:
    """A method's pages, by number from 1; refused when there is none or one is missing."""
    found = {int(m.group(1)): p for p in directory.glob(f"{method}-*.json") if (m := re.fullmatch(rf"{method}-(\d+)\.json", p.name))}
    if not found:
        raise Refused(f"no {method}-1.json")
    if sorted(found) != list(range(1, len(found) + 1)):
        raise Refused(f"the {method} pages are {sorted(found)}, not 1 to {len(found)}")
    return [(found[n].name, load(found[n])) for n in sorted(found)]


def listed(directory: Path, method: str, fields: tuple[str, ...]) -> list:
    """A list method's items over its pages, checking each page is a full one but the last."""
    got = pages(directory, method)
    items = []
    for i, (name, page) in enumerate(got):
        if not isinstance(page, list):
            raise Refused(f"{name} is not a list")
        last = i == len(got) - 1
        if (len(page) >= PER_PAGE) if last else (len(page) != PER_PAGE):
            raise Refused(f"{name} holds {len(page)} items: the pages stop {'early' if last else 'short of a full page'}")
        for j, item in enumerate(page):
            check(item, fields, f"{name} item {j}")
        items += page
    return items


def threads(directory: Path) -> list:
    got = pages(directory, "get_review_comments")
    out = []
    for i, (name, page) in enumerate(got):
        check(page, ("review_threads", "pageInfo.hasNextPage", "totalCount"), name)
        if page["pageInfo"]["hasNextPage"] != (i < len(got) - 1):
            raise Refused(f"{name} says hasNextPage {page['pageInfo']['hasNextPage']}, but it is page {i + 1} of {len(got)}")
        for j, thread in enumerate(page["review_threads"]):
            check(thread, THREAD, f"{name} thread {j}")
            if not thread["comments"]:
                raise Refused(f"{name} thread {thread['id']} has no comments")
            for k, comment in enumerate(thread["comments"]):
                check(comment, THREAD_COMMENT, f"{name} thread {thread['id']} comment {k}")
        out += page["review_threads"]
    if len(out) != got[0][1]["totalCount"]:
        raise Refused(f"the pages hold {len(out)} threads, but totalCount is {got[0][1]['totalCount']}")
    return out


def build(directory: Path) -> dict[str, str]:
    """The dump's files and their text, from the pages under directory."""
    get = directory / "get.json"
    pr = load(get)
    check(pr, PR, get.name)
    return {
        "pr.json": get.read_text(),
        "reviews.json": json.dumps(listed(directory, "get_reviews", REVIEW), ensure_ascii=False, indent=1),
        "comments.json": json.dumps({"review_threads": threads(directory)}, ensure_ascii=False, indent=1),
        "issue-comments.json": json.dumps(listed(directory, "get_comments", COMMENT), ensure_ascii=False, indent=1),
        "body.md": pr.get("body") or "",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("dump", type=Path, help="the dump directory, .review/threads/pr-NNNN/ or .review/harvest/threads/pr-NNNN/")
    args = p.parse_args(argv)
    try:
        number = re.fullmatch(r"pr-(\d+)", args.dump.name)
        if not number or args.dump.name != f"pr-{int(number[1]):04d}":
            raise Refused(f"{args.dump.name} is not pr-NNNN, the number padded to four digits")
        files = build(args.dump / "pages")
    except Refused as e:
        print(f"thread_dump.py: {e}", file=sys.stderr)
        return 1
    for name, text in files.items():
        (args.dump / name).write_text(text)
    print(f"wrote {args.dump}: {', '.join(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
