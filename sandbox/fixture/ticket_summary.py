#!/usr/bin/env python3
"""Print the summary a ticket-draft paste file leaves on one existing ticket, for a scenario's verify.

    python3 ticket_summary.py <paste file> <key> <the summary as filed>

The paste file's layout is the model's, so this reads the forms runs write: a `Summary:` line, a
heading such as `== Summary (field change) ==` with the value on the next line, a field change
`"<now>" → "<after>"` or `from "<now>" to "<after>"`, a line saying the summary is unchanged, and
the `<key> · <summary>` heading. A summary under a follow-up ticket's heading, a line that is not
a bullet and names follow-up, to create or file first, is that ticket's and is skipped until a
line names the key or a rule of dashes ends it. The first summary found is the one printed; a
summary said to be unchanged, or none found at all, prints the summary as filed. A paste file that
cannot be read exits 1.
"""

import re
import sys
from pathlib import Path

FOLLOW_UP = re.compile(r"follow-?up|to create|file (this )?first|new\b.*\bticket", re.I)
BULLET = re.compile(r"^\s*(?:[*•]|-\s)")
RULE = re.compile(r"^\s*-{3,}\s*$")
LABEL = re.compile(r"^[\s*#=>-]*(?:\d+\.\s*)?(?:title \(the )?summary\b(?P<rest>.*)$", re.I)
CHANGE = re.compile(r'["“](?P<now>[^"”]+)["”]\s*(?:→|->|to)\s*["“](?P<after>[^"”]+)["”]')


def value(rest: str, following: list[str]) -> str:
    """The summary a labelled line gives: after a colon, or on the next non-blank line."""
    change = CHANGE.search(rest)
    if change:
        return change.group("after")
    after = rest.split(":", 1)[1].strip() if ":" in rest else ""
    after = after.strip("=").strip()
    if after:
        return after.strip('"“”')
    return next((line.strip().strip("=").strip() for line in following if line.strip()), "")


def summary(text: str, key: str, filed: str) -> str:
    lines = text.splitlines()
    follow_up, last = False, ""
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        label = LABEL.match(line)
        if RULE.match(line):
            if not (follow_up and FOLLOW_UP.search(last)):
                follow_up = False
        elif not label and FOLLOW_UP.search(line) and not BULLET.match(line):
            follow_up = True
        elif key in line and not re.search(r"relates to|blocks|depends on", line, re.I):
            follow_up = False
        elif label and not follow_up:
            if re.search(r"\bunchanged\b|\bnone\b", label.group("rest"), re.I):
                return filed
            found = value(label.group("rest"), lines[i + 1:])
            if found:
                return found
        elif re.match(r"^\s*field changes?:\s*none\b", line, re.I) and not follow_up:
            return filed
        last = line
    heading = re.compile(rf"^\s*{re.escape(key)}\s*·\s*(?P<s>.+)$")
    for line in lines:
        m = heading.match(line)
        if m and not re.search(r"paste|output", m.group("s"), re.I):
            return m.group("s").strip()
    return filed


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: ticket_summary.py <paste file> <key> <the summary as filed>")
    path, key, filed = sys.argv[1:]
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        sys.exit(f"ticket_summary.py: {e}")
    print(summary(text, key, filed))
