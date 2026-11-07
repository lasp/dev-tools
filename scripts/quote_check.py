#!/usr/bin/env python3
"""Check every quote a revision report gives against the comment or note it cites.

Reads the report, `ratchet-YYYY-MM.md`, and every line in it that opens `said:` once its indent is
stripped, a drafted entry's included, or holds `said: "` anywhere (`docs/contracts.md`, "The
report's quotes"). Each must be a line of its own reading `said: "<words>" — <login>, <url>`, a
comment's, or `said: "<words>" — <name>, pasted <file>`, a note the driver pasted, so a quote
nested in a list item, a table or a blockquote is refused, and its words must be 1 to 40 and
found as `scripts/guidance_check.py` finds an item's quote: for a comment, in its own words, one
run of its `body` between the lines that open `>`, never starting or ending inside a word, a run
of whitespace read as one space and nothing else forgiven; for a note, in the file's text read the
same way, every line kept. A comment is the one with that `url` in the comment lists given with
--comments, `comment-list.json` files, and `<login>` must be its `author`; a note is `<file>` under
--notes. A URL whose pull request, the URL before its `#`, no comment in the lists shares is
unchecked, not refused: no list given holds it, as for a held candidate's quote from before the
log kept captures.

Prints `quotes: <n> · from comments: <n> · from notes: <n> · unchecked: <n>`, then `unchecked ·
line <n> · <url>: no comment list given holds its pull request` per unchecked quote, and exits 0.
Otherwise prints one `refused · line <n> · <why>` per fault, every fault found, and exits 1; an
input that cannot be read is one such line, `refused · <path> · <why>`. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guidance_check import MAX_WORDS, flat, holds  # noqa: E402

SAID = re.compile(
    r'said: "(?P<quote>.+)" — (?:(?P<login>[^\s,]+), (?P<url>https?://\S+)|(?P<name>[^,]+), pasted (?P<file>.+))'
)
# A quote's opening anywhere in a line, so one nested in a list item, a table or a blockquote is
# refused for its form rather than passed over.
OPENING = re.compile(r'(?<![\w`])said: "')


def found_in(text: str, quote: str) -> bool:
    """Whether quote is in text, every line kept, without cutting a word."""
    words = flat(quote)
    left = r"(?<!\w)" if re.match(r"\w", words) else ""
    right = r"(?!\w)" if re.search(r"\w$", words) else ""
    return bool(re.search(left + re.escape(words) + right, flat(text)))


def comments(paths: list[Path], faults: list[str]) -> dict[str, dict]:
    """Every listed comment by its url."""
    by_url: dict[str, dict] = {}
    for path in paths:
        try:
            listed = {c["url"]: c for c in json.loads(path.read_text())["comments"]}
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            faults.append(f"refused · {path} · not a comment list: {e}")
            continue
        by_url.update(listed)
    return by_url


def check(report: Path, lists: list[Path], notes: Path | None) -> tuple[list[str], list[str]]:
    faults: list[str] = []
    by_url = comments(lists, faults)
    try:
        lines = report.read_text().splitlines()
    except OSError as e:
        return [], [*faults, f"refused · {report} · cannot be read: {e}"]
    listed = {url.split("#")[0] for url in by_url}
    quoted = pasted = 0
    unchecked: list[str] = []
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not (line.startswith("said:") or OPENING.search(line)):
            continue
        m = SAID.fullmatch(line)
        if not m:
            faults.append(f'refused · line {n} · not a line of its own `said: "<words>" — <login>, <url>` or `— <name>, pasted <file>`')
            continue
        quote = m["quote"]
        if not 1 <= len(quote.split()) <= MAX_WORDS:
            faults.append(f"refused · line {n} · {len(quote.split())} words, not 1 to {MAX_WORDS}")
            continue
        if m["url"]:
            c = by_url.get(m["url"])
            if c is None and m["url"].split("#")[0] not in listed:
                unchecked.append(f"unchecked · line {n} · {m['url']}: no comment list given holds its pull request")
            elif c is None:
                faults.append(f"refused · line {n} · {m['url']} is no comment in the lists given")
            elif c["author"] != m["login"]:
                faults.append(f"refused · line {n} · {m['url']} is {c['author']}'s, not {m['login']}'s")
            elif not holds(c["body"], quote):
                faults.append(f"refused · line {n} · the quote is not in {m['url']}'s own words")
            else:
                quoted += 1
            continue
        path = notes / m["file"] if notes else None
        if path is None or not path.is_file():
            faults.append(f"refused · line {n} · pasted {m['file']} is no file under --notes")
        elif not found_in(path.read_text(), quote):
            faults.append(f"refused · line {n} · the quote is not in {m['file']}")
        else:
            pasted += 1
    if faults:
        return [], faults
    head = f"quotes: {quoted + pasted} · from comments: {quoted} · from notes: {pasted} · unchecked: {len(unchecked)}"
    return [head, *unchecked], []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", type=Path)
    ap.add_argument("--comments", type=Path, nargs="*", default=[], help="comment-list.json files")
    ap.add_argument("--notes", type=Path, help="the directory of pasted notes")
    a = ap.parse_args(argv)
    out, faults = check(a.report, a.comments, a.notes)
    print("\n".join(faults or out))
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
