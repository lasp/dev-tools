#!/usr/bin/env python3
"""Write a pull request's comment list: every comment its dump holds, one JSON object each.

The list is what the guidance extractor reads (`docs/contracts.md`, "The comment list"). It reads
every comment as a possible source of guidance, apart from how a thread was settled, which the
record and `thread-analyst` judge per thread: a thread's opening comment, each reply in it, each
review's summary and each conversation comment, a bot's and the pull request author's included.

Reads a dump directory `thread_dump.py` wrote, `pr-NNNN/`, its number the pull request's: the
three files it needs, `comments.json`, `reviews.json` and `issue-comments.json`. Writes
`comment-list.json` beside them, an object with `pr`, the pull request's number from the
directory's name, and `comments`, a list ordered by `created` then `id`, empty for a pull request
no one commented on, each item:

- `pr`, the pull request's number;
- `id`, the comment's number: a review comment's from its `html_url`'s `#discussion_r<n>`, a
  review's and a conversation comment's from `id`;
- `url`, its `html_url`;
- `author`, the login;
- `authorship`, `human`, `ai-drafted` or `bot`, from `record.py`'s `authorship_of` on this
  comment alone, so a person's reply in a thread an agent opened is `human`;
- `kind`, `thread` for a thread's first comment, `reply` for the rest, `review` for a review's
  summary and `comment` for a conversation comment;
- `thread`, the review thread's id, null for a review or a conversation comment;
- `path` and `line`, where the comment anchors: `line` is its `original_line`, the line in the
  commit it was made on, else `line`, and null at file level; both null for a review or a
  conversation comment;
- `created`, its timestamp as GitHub gave it: `created_at`, or a review's `submitted_at`;
- `nominated`, what the comment nominates for the standard: the rest of each of its own lines
  (`record.py`'s `own_lines`, so not a quoted or fenced line) that opens `For agents:` or
  `Standard:`, case aside, as a list item too and bold or italic too, in order; empty when none does (`README.md`, "Nominating guidance");
- `body`, its text, unchanged.

A review with a blank body, such as one posted with a batch of thread replies, is no comment and
is left out. Exits 1 with the reason, writing nothing, for a dump directory not named `pr-NNNN`, a
file missing or not JSON, a review comment whose `html_url` has no `#discussion_r<n>`, a review
with a body but no `submitted_at`, an id given twice, across kinds as well as within one, since a
reader names a comment by its number alone, or a profile `record.py` refuses, since then
no comment's authorship can be told. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

DISCUSSION = re.compile(r"#discussion_r(\d+)$")


class Refused(Exception):
    """A dump the list cannot be built from."""


NOMINATION = re.compile(r"(?i)(?:[-*+] +)?(?:\*\*|__|\*|_)?(?:for agents|standard)(?::(?:\*\*|__|\*|_)?|(?:\*\*|__|\*|_)?:)\s*(\S.*)")


def load_record():
    spec = importlib.util.spec_from_file_location("record", Path(__file__).with_name("record.py"))
    record = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(record)
    return record


def read(dump: Path, name: str):
    try:
        return json.loads((dump / name).read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise Refused(f"{dump.name}/{name} cannot be read as JSON: {e}") from e


def build(dump: Path, record) -> dict:
    """The dump's comments, as the module docstring describes them."""
    number = re.fullmatch(r"pr-(\d+)", dump.name)
    if not number or dump.name != f"pr-{int(number[1]):04d}":
        raise Refused(f"{dump.name} is not pr-NNNN, the number padded to four digits")
    pr = int(number[1])
    items = []

    def add(kind: str, id_: int, url: str, author: str, created: str, body: str, thread=None, path=None, line=None) -> None:
        items.append({
            "pr": pr, "id": id_, "url": url, "author": author,
            "authorship": record.authorship_of({"author": author, "body": body}),
            "kind": kind, "thread": thread, "path": path, "line": line, "created": created,
            "nominated": [m[1] for m in map(NOMINATION.match, record.own_lines(body)) if m], "body": body,
        })

    for t in read(dump, "comments.json")["review_threads"]:
        for i, c in enumerate(t["comments"]):
            m = DISCUSSION.search(c["html_url"])
            if not m:
                raise Refused(f"{dump.name}: a comment in thread {t['id']} has no #discussion_r<n> in its url {c['html_url']}")
            line = c.get("original_line") or c.get("line")
            add("thread" if i == 0 else "reply", int(m[1]), c["html_url"], c["author"], c["created_at"], c["body"], t["id"], c["path"], line)
    for r in read(dump, "reviews.json"):
        body = r.get("body") or ""
        if not body.strip():
            continue
        if not r.get("submitted_at"):
            raise Refused(f"{dump.name}: review {r['id']} has a body but no submitted_at")
        add("review", int(r["id"]), r["html_url"], r["user"]["login"], r["submitted_at"], body)
    for c in read(dump, "issue-comments.json"):
        add("comment", int(c["id"]), c["html_url"], c["user"]["login"], c["created_at"], c["body"])

    seen = {}
    for it in items:
        if it["id"] in seen:
            raise Refused(f"{dump.name}: id {it['id']} is given twice, as a {seen[it['id']]} and a {it['kind']}")
        seen[it["id"]] = it["kind"]
    return {"pr": pr, "comments": sorted(items, key=lambda it: (it["created"], it["id"]))}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("dumps", nargs="+", type=Path, help="dump directories, .review/harvest/threads/pr-NNNN/")
    args = p.parse_args(argv)
    record = load_record()
    built = {}
    try:
        for dump in args.dumps:
            built[dump] = build(dump, record)
    except (Refused, record.Unsupported) as e:
        print(f"comment_list.py: {e}", file=sys.stderr)
        return 1
    for dump, listed in built.items():
        items = listed["comments"]
        (dump / "comment-list.json").write_text(json.dumps(listed, ensure_ascii=False, indent=1))
        tally = {a: sum(it["authorship"] == a for it in items) for a in ("human", "ai-drafted", "bot")}
        print(f"wrote {dump / 'comment-list.json'}: {len(items)} comments, " + ", ".join(f"{n} {a}" for a, n in tally.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
