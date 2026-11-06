#!/usr/bin/env python3
"""Print the summary a ticket-draft paste file leaves on one existing ticket, for a scenario's verify.

    python3 ticket_summary.py <paste file> <key> <the summary as filed>

The paste file's layout is the model's, so this reads the forms runs write. A summary line opens
with `Summary`, after any bullet, heading or bold marks, as `Summary: <value>`, `**Summary:**
<value>`, `| Summary | <value> |` or `Summary (<qualifier>): <value>`; a line with no value, such as
the heading `== Summary (field change) ==`, takes it from the next non-blank line, or from the
`After:` line of a `Now:`/`After:` pair. A value that is a change, `<now> → <after>` or `->`, its
sides quoted, backticked or bare, or `"<now>" to "<after>"`, gives its after; one that ends
`(was: …)` or `(changed from …)` gives what comes before. A summary line, or a `Field changes:`
line, that says the summary is unchanged, kept or none, or a What changed line `Kept: the summary,
…`, prints the summary as filed.

A follow-up ticket's summary is skipped. A line of at most 120 characters that opens with
`Follow-up`, `New follow-up` or `File the follow-up`, after any heading marks or number, opens its
block. The block ends at its first summary line, or at a heading with text (`# …`, `== … ==`) that
opens no other follow-up; a bare rule of `=` or `-` ends nothing. A summary line that names the
key is the ticket's own, inside a block or not.

The first summary found is printed. With none, the summary a `<key> · <summary>` heading names,
also as `Ticket: <key> · <summary>`, is printed. Otherwise, or when the file cannot be read,
nothing is printed and the exit is 1, so a verify that reads nothing fails.
"""

import re
import sys
from pathlib import Path
from typing import List, Optional

FOLLOW_UP = re.compile(r"^[\s#=>|]*(?:\*\*)?(?:\d+[.)]\s*)?(?:new\s+|file\s+the\s+)?follow-?up\b", re.I)
HEADING = re.compile(r"^\s*(?:#{1,6}|={2,})\s*[^\s=#]")
LABEL = re.compile(
    r"^[\s*#=>|-]*(?:\d+\.\s*)?(?:title \(the summary[^)]*\)|summary\b)(?P<rest>.*)$", re.I
)
KEPT = re.compile(r"^\W*(?:unchanged|kept|none|no change)\b", re.I)
QUOTED = re.compile(r'["“`](?P<now>[^"”`]+)["”`]\s*(?:→|->|\bto\b)\s*["“`](?P<after>[^"”`]+)["”`]')
ARROW = re.compile(r"\s(?:→|->)\s")
WAS = re.compile(r"\s*\((?:was:?|changed from)\b.*\)\s*$", re.I)


def clean(text: str) -> str:
    return text.strip().strip("*`|=\"“” ").strip()


def changed(text: str) -> str:
    """The after side of a change, or the text itself when it is not one."""
    quoted = QUOTED.search(text)
    if quoted:
        return clean(quoted.group("after"))
    if ARROW.search(text):
        return clean(ARROW.split(text)[-1])
    return clean(WAS.sub("", text))


def value(rest: str, following: List[str]) -> Optional[str]:
    """The summary a summary line gives, or None when it says the summary is kept."""
    qualifier = re.match(r"\s*\((?P<q>[^)]*)\)", rest)
    if qualifier:
        if KEPT.match(qualifier.group("q")):
            return None
        rest = rest[qualifier.end():]
    if QUOTED.search(rest):
        return changed(rest)
    rest = re.sub(r"^[\s*:|=]+", "", rest)
    if KEPT.match(rest):
        return None
    if clean(rest):
        return changed(rest)
    nonblank = [line for line in following if line.strip()]
    if not nonblank:
        return ""
    if re.match(r"^\W*now:", nonblank[0], re.I):
        after = next((line for line in nonblank[1:3] if re.match(r"^\W*after:", line, re.I)), "")
        return changed(after.split(":", 1)[1]) if after else ""
    if KEPT.match(nonblank[0]):
        return None
    return changed(nonblank[0])


def summary(text: str, key: str, filed: str) -> Optional[str]:
    """The summary the paste file leaves on <key>, or None when it says nothing about it."""
    lines = text.splitlines()
    follow_up = False
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        label = LABEL.match(line)
        if label:
            if follow_up and key not in line:
                follow_up = False
                continue
            found = value(label.group("rest"), lines[i + 1:])
            if found is None:
                return filed
            if found:
                return found
        elif FOLLOW_UP.match(line) and len(line.strip()) <= 120:
            follow_up = True
        elif HEADING.match(line):
            follow_up = False
        elif re.match(r"^\s*field changes?:", line, re.I) and not follow_up:
            if KEPT.match(line.split(":", 1)[1]):
                return filed
        elif re.match(r"^[\s*-]*kept:\s*(?:the\s+)?summary\b", line, re.I) and not follow_up:
            return filed
    heading = re.compile(rf"^[\s#=*]*(?:ticket:?\s*)?{re.escape(key)}\s*·\s*(?P<s>.+)$", re.I)
    for line in lines:
        m = heading.match(line)
        if m:
            named = re.split(r"\s+[—–-]\s+|\s+\(", m.group("s"))[0]
            if not re.search(r"paste|output", named, re.I):
                return clean(named)
    return None


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: ticket_summary.py <paste file> <key> <the summary as filed>")
    path, key, filed = sys.argv[1:]
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        sys.exit(f"ticket_summary.py: {e}")
    found = summary(text, key, filed)
    if found is None:
        sys.exit(f"ticket_summary.py: no summary for {key} in {path}")
    print(found)
