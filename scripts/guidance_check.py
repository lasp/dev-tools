#!/usr/bin/env python3
"""Check a revision's guidance items against the comment lists they were read from.

Each `guidance-extractor` run writes one slice, a JSON object (`docs/contracts.md`, "The guidance
items"): `prs`, the pull request numbers read; `comments_read`, how many comments their lists
hold; and `items`, each with exactly the keys that section names. Given every slice of the run and
every comment list with --comments, `comment-list.json` files `comment_list.py` wrote, each an
object with `pr` and `comments`, this script holds them to that form:

- every list's pull request in exactly one slice, and every slice's pull requests among the lists;
- a slice of more than 300 comments only when it holds one pull request;
- in each slice, every key present and no other, each value of its type and, where the section
  lists them, one of its values; `comments_read` the comments its lists hold;
- each item on a comment its `pr`'s list holds, with that comment's `url`, `author` and
  `authorship`, its `pr` one of its slice's;
- each `quote`, and each `rationale` that is not null, of 1 to 40 words and found in that
  comment's own words, one run of its `body` between the lines that open `>`, which quote someone
  else, never starting or ending inside a word, a run of whitespace read as one space and nothing
  else forgiven.

It prints `slices: <n> · comments: <n> · items: <n> · general: <n> · pr-specific: <n>`, then a line
`kind · <kind> · <general> · <pr-specific>` per kind with an item, and exits 0. Otherwise it prints
one `refused · <where> · <why>` line per fault, every fault found, and exits 1; a file that cannot
be read as JSON is one such line, and a slice that cannot be read leaves its pull requests in no
slice while the others are still checked. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GENERALITY = ("general", "pr-specific")
SIGNALS = ("asks for guidance", "addresses agents", "states a principle", "names a habit", "cites a source", "none")
KINDS = ("rule", "agent-guidance", "data-convention", "process", "decision", "tool-config", "exemplar",
         "review-calibration", "open-question")
AUTHORSHIP = ("human", "ai-drafted", "bot")
OUTCOMES = ("changed as asked", "changed differently", "declined", "discussed", "unanswered")
COVERED = re.compile(r"[RDAF]-\d+|instruction file")
ITEM = {
    "pr": int, "comment_id": int, "url": str, "author": str, "authorship": AUTHORSHIP, "quote": str,
    "generality": GENERALITY, "signal": SIGNALS, "kind": KINDS, "principle": str, "rationale": (str, None),
    "covered_by": (COVERED, None), "outcome": OUTCOMES,
}
MAX_WORDS = 40
MAX_SLICE = 300


def flat(text: str) -> str:
    return " ".join(text.split())


def own_words(body: str) -> list[str]:
    """A comment's own passages, each flattened: its runs of lines between the lines that open `>`."""
    runs, run = [], []
    for line in body.splitlines():
        if line.lstrip().startswith(">"):
            runs.append(run)
            run = []
        else:
            run.append(line)
    return [flat("\n".join(r)) for r in [*runs, run] if r]


def holds(body: str, passage: str) -> bool:
    """Whether passage is in one of body's own passages without cutting a word: a passage that
    starts or ends with a letter or digit does not start or end inside a word there."""
    text = flat(passage)
    left = r"(?<!\w)" if re.match(r"\w", text) else ""
    right = r"(?!\w)" if re.search(r"\w$", text) else ""
    return any(re.search(left + re.escape(text) + right, run) for run in own_words(body))


def load(path: Path, faults: list[str]):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        faults.append(f"refused · {path} · cannot be read as JSON: {e}")
        return None


def shape(value, want) -> bool:
    """Whether value has the type, or is one of the values, `want` names."""
    if isinstance(want, tuple) and want and isinstance(want[0], str) and want[-1] is not None:
        return value in want
    if isinstance(want, tuple):
        return any(shape(value, w) for w in want)
    if want is None:
        return value is None
    if isinstance(want, re.Pattern):
        return isinstance(value, str) and bool(want.fullmatch(value))
    return isinstance(value, want) and not isinstance(value, bool)


def check_slice(name: str, found, lists: dict[int, dict[int, dict]]) -> tuple[list[int], list[str]]:
    """The pull requests one slice read, empty when they cannot be told, and every fault in it,
    read against the comment lists by pr."""
    if not isinstance(found, dict) or set(found) != {"prs", "comments_read", "items"}:
        return [], [f"refused · {name} · not an object with exactly prs, comments_read and items"]
    prs, faults = found["prs"], []
    if not isinstance(prs, list) or not prs or not all(shape(p, int) for p in prs) or len(set(prs)) != len(prs):
        return [], [f"refused · {name} · prs {prs!r} is not a list of pull request numbers, each once"]
    gone = [p for p in prs if p not in lists]
    if gone:
        return prs, [f"refused · {name} · prs {gone} have no comment list given"]
    total = sum(len(lists[p]) for p in prs)
    if not shape(found["comments_read"], int) or found["comments_read"] != total:
        faults.append(f"refused · {name} · comments_read {found['comments_read']!r}, but its lists hold {total}")
    if total > MAX_SLICE and len(prs) > 1:
        faults.append(f"refused · {name} · {total} comments over {len(prs)} pull requests; "
                      f"past {MAX_SLICE} a slice holds one")
    if not isinstance(found["items"], list):
        return prs, faults + [f"refused · {name} · items is not a list"]
    for i, item in enumerate(found["items"]):
        where = f"{name} item {i}"
        if not isinstance(item, dict) or set(item) != set(ITEM):
            got = sorted(item) if isinstance(item, dict) else type(item).__name__
            faults.append(f"refused · {where} · keys {got}, not {sorted(ITEM)}")
            continue
        bad = [k for k, want in ITEM.items() if not shape(item[k], want)]
        if bad:
            faults.append(f"refused · {where} · {', '.join(f'{k}={item[k]!r}' for k in bad)} not of its form")
            continue
        where = f"{name} item {i} (pr {item['pr']}, comment {item['comment_id']})"
        comment = lists[item["pr"]].get(item["comment_id"]) if item["pr"] in prs else None
        if comment is None:
            faults.append(f"refused · {where} · no such comment in the slice's lists")
            continue
        for k in ("url", "author", "authorship"):
            if item[k] != comment[k]:
                faults.append(f"refused · {where} · {k} {item[k]!r}, but the comment's is {comment[k]!r}")
        for k in ("quote", "rationale"):
            if item[k] is None:
                continue
            words = len(item[k].split())
            if not 1 <= words <= MAX_WORDS:
                faults.append(f"refused · {where} · the {k} has {words} words, not 1 to {MAX_WORDS}")
            elif not holds(comment["body"], item[k]):
                faults.append(f"refused · {where} · the {k} is not in the comment's own words: {item[k][:80]!r}")
        if item["generality"] == "pr-specific" and item["signal"] != "none":
            faults.append(f"refused · {where} · a pr-specific item has signal {item['signal']!r}, not 'none'")
    return prs, faults


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("slices", type=Path, nargs="+", help="every slice of the run")
    p.add_argument("--comments", type=Path, nargs="+", required=True, help="every comment-list.json the run read")
    args = p.parse_args(argv)
    faults: list[str] = []
    lists: dict[int, dict[int, dict]] = {}
    for path in args.comments:
        data = load(path, faults)
        if data is None:
            continue
        if (not isinstance(data, dict) or set(data) != {"pr", "comments"} or not shape(data["pr"], int)
                or not isinstance(data["comments"], list)):
            faults.append(f"refused · {path} · not a comment list, an object with pr and comments")
        elif data["pr"] in lists:
            faults.append(f"refused · {path} · pull request {data['pr']} given twice")
        else:
            lists[data["pr"]] = {c["id"]: c for c in data["comments"]}
    if faults:
        print("\n".join(faults))
        return 1
    slices = {str(path): load(path, faults) for path in args.slices}
    seen: dict[int, str] = {}
    for name, found in slices.items():
        if found is None:
            continue
        prs, sliced = check_slice(name, found, lists)
        faults += sliced
        for pr in prs:
            if pr in seen:
                faults.append(f"refused · {name} · pull request {pr} is also in {seen[pr]}")
            seen.setdefault(pr, name)
    faults += [f"refused · pr {pr} · in no slice" for pr in sorted(set(lists) - set(seen))]
    if faults:
        print("\n".join(faults))
        return 1
    items = [it for found in slices.values() for it in found["items"]]
    general = [it for it in items if it["generality"] == "general"]
    print(f"slices: {len(slices)} · comments: {sum(len(c) for c in lists.values())} · items: {len(items)} · "
          f"general: {len(general)} · pr-specific: {len(items) - len(general)}")
    for kind in KINDS:
        g = sum(it["kind"] == kind for it in general)
        s = sum(it["kind"] == kind for it in items) - g
        if g or s:
            print(f"kind · {kind} · {g} · {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
