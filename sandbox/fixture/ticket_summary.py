#!/usr/bin/env python3
"""Print the summary a ticket-draft paste file leaves on one existing ticket, for a scenario's verify.

    python3 ticket_summary.py <paste file> <key> <the summary as filed>

The paste file's layout is the model's, so this reads the forms runs write. A summary line opens
with `Summary`, `Summary field`, `New summary` or `Proposed summary`, after any bullet, heading or
bold marks, and goes on with a separator or with kept, unchanged or changed: `Summary: <value>`,
`**Summary:** <value>`, `| Summary | <value> |`, `Summary (<qualifier>): <value>`. A line with no
value, such as the heading `== Summary (field change) ==`, takes it from the next non-blank line,
or from the `After:` line of a `Now:`/`After:` pair. A value that is a change, `<now> → <after>` or
`->`, its sides quoted, backticked or bare, or `"<now>" to "<after>"`, gives its after; one that
ends `(was: …)` or `(changed from …)` gives what comes before; a `<key> · ` before it is dropped.
A `Reworded:` line that names the summary with a quoted change gives that change's after.

These print the summary as filed: a summary line whose value, or whose qualifier, is unchanged,
kept, none or no change, or whose value ends `(unchanged)` or `— kept …`; a `Field changes:` or
`Fields:` line, or such a heading with the next non-blank line, that says none or no change; and a
`Kept:` line that names the summary.

A follow-up ticket's summary is skipped. A line of at most 120 characters that opens with
`Follow-up`, `New follow-up` or `File the follow-up`, after any heading marks or number, opens its
block. The block ends at its first summary line, or at a heading with text (`## …`, `== … ==`) that
opens no other follow-up; a bare rule, an `h1.` line or a Jira `#` list item ends nothing. A
summary line whose label names the key, as `Summary (<key>):`, is the ticket's own, inside a block
or not, unless the label also names a follow-up. A line that opens with `Comment to post` or
`Original request` starts a section that quotes the ticket as filed, so nothing in it is read, up
to the next heading, rule, banner between rules (`----- Session comment -----`), upper-case
label line (`FIELD CHANGES:`) or `Field changes` line.

The first summary found is printed. With none, the summary a `<key> · <summary>` heading names,
also as `Ticket: <key> · …` or `h1. <key> · …`, is printed. Otherwise nothing is printed and the
exit is 1, as it is when the file cannot be read. A verify reads the status through
`out=$(python3 ticket_summary.py …)`, since a pipe into grep would hide it: a scenario that needs a
new summary fails on an empty read, and the control, where saying nothing about a summary that
still fits is right, fails only on a different one.
"""

import re
import sys
from pathlib import Path
from typing import List, Optional

FOLLOW_UP = re.compile(r"^[\s#=>|]*(?:\*\*)?(?:\d+[.)]\s*)?(?:new\s+|file\s+the\s+)?follow-?up\b", re.I)
FOLLOW_UP_WORD = re.compile(r"follow-?up", re.I)
HEADING = re.compile(r"^\s*(?:#{2,6}\s*\S|={2,}\s*[^\s=])")
QUOTE_SECTION = re.compile(r"^[\s#=*>|-]*(?:\d+[.)]\s*)?(?:comment to post|original request)\b", re.I)
RULE = re.compile(r"^\s*[-=]{3,}\s*$")
BANNER = re.compile(r"^\s*[-=]{3,}\s*\S.*[-=]{3,}\s*$")
UPPER_LABEL = re.compile(r"^[A-Z][A-Z ]{3,}:")
LABEL = re.compile(
    r"^[\s*#=>|-]*(?:\d+\.\s*)?(?:(?:new|proposed)\s+)?"
    r"(?P<label>title \(the summary[^)]*\)|summary(?:\s+field)?)"
    r"(?P<rest>(?:\s*\([^)]*\))?(?:\s*[:|=*—–-].*|\s+(?:kept|unchanged|changed|stays)\b.*)?)$",
    re.I,
)
FIELDS = re.compile(r"^[\s*#=-]*(?:\d+\.\s*)?fields?(?:\s+changes?)?\s*=*\s*(?::\s*(?P<v>.*))?$", re.I)
KEPT = re.compile(r"^[\W_]*(?:unchanged|kept|(?:none|no change)(?=\s*(?:[.,;:()]|$)))", re.I)
KEPT_TAIL = re.compile(r"(?:\(\s*(?:unchanged|kept)\b[^)]*\)|\s[—–]+\s*(?:unchanged|kept)\b.*)\s*$", re.I)
QUOTED = re.compile(r'["“`](?P<now>[^"”`]+)["”`]\s*(?:→|->|\bto\b)\s*["“`](?P<after>[^"”`]+)["”`]')
ARROW = re.compile(r"\s*→\s*|\s->\s")
WAS = re.compile(r"\s*\((?:was:?|changed from)\b.*\)\s*$", re.I)


def clean(text: str, key: str) -> str:
    text = text.strip().strip("*`|=\"“” —–").strip()
    return re.sub(rf"^{re.escape(key)}\s*·\s*", "", text).strip()


def changed(text: str, key: str) -> Optional[str]:
    """The after side of a change, the text itself when it is not one, or None when it is kept."""
    quoted = QUOTED.search(text)
    if quoted:
        return clean(quoted.group("after"), key)
    if ARROW.search(text):
        return clean(ARROW.split(text)[-1], key)
    if KEPT_TAIL.search(text):
        return None
    return clean(WAS.sub("", text), key)


def value(rest: str, following: List[str], key: str) -> Optional[str]:
    """The summary a summary line gives, "" for none, or None when it says the summary is kept."""
    qualifier = re.match(r"\s*\((?P<q>[^)]*)\)", rest)
    if qualifier:
        if KEPT.match(qualifier.group("q")):
            return None
        rest = rest[qualifier.end():]
    if QUOTED.search(rest):
        return changed(rest, key)
    rest = re.sub(r"^[\s*:|=—–-]+", "", rest)
    if KEPT.match(rest):
        return None
    if clean(rest, key):
        return changed(rest, key)
    nonblank = [line for line in following if line.strip()]
    if not nonblank:
        return ""
    if re.match(r"^\W*now\W*:", nonblank[0], re.I):
        after = next((line for line in nonblank[1:3] if re.match(r"^\W*after\W*:", line, re.I)), "")
        return changed(after.split(":", 1)[1], key) if after else ""
    if KEPT.match(nonblank[0]):
        return None
    return changed(nonblank[0], key)


def summary(text: str, key: str, filed: str) -> Optional[str]:
    """The summary the paste file leaves on <key>, or None when it says nothing about it."""
    lines = text.splitlines()
    follow_up = quoting = False
    headings = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if QUOTE_SECTION.match(line):
            quoting = True
            continue
        if quoting:
            if HEADING.match(line) or RULE.match(line) or BANNER.match(line) or UPPER_LABEL.match(line) or FIELDS.match(line):
                quoting = False
            else:
                continue
        heading = re.match(rf"^[\s#=*]*(?:h\d\.\s*)?(?:ticket:?\s*)?{re.escape(key)}\s*·\s*(?P<s>.+)$", line, re.I)
        if heading:
            headings.append(heading.group("s"))
        label = LABEL.match(line)
        if label:
            qualifier = re.match(r"\s*\([^)]*\)", label.group("rest"))
            own = bool(qualifier) and key in qualifier.group(0) and not FOLLOW_UP_WORD.search(qualifier.group(0))
            if follow_up and not own:
                follow_up = False
                continue
            found = value(label.group("rest"), lines[i + 1:], key)
            if found is None:
                return filed
            if found:
                return found
            continue
        fields = FIELDS.match(line)
        if fields and not follow_up:
            said = fields.group("v")
            if said is None:
                said = next((later for later in lines[i + 1:] if later.strip()), "")
            if KEPT.match(said):
                return filed
            continue
        if follow_up:
            if HEADING.match(line) and not FOLLOW_UP.match(line):
                follow_up = False
            continue
        if FOLLOW_UP.match(line) and len(line.strip()) <= 120:
            follow_up = True
        elif re.match(r"^[\s*-]*kept:.*\bsummary\b", line, re.I):
            return filed
        elif re.match(r"^[\s*-]*reworded:\s*(?:the\s+)?summary\b", line, re.I):
            after = QUOTED.search(line) or re.search(r"\bafter:?\s*[\"“`](?P<after>[^\"”`]+)", line, re.I)
            if after:
                return clean(after.group("after"), key)
    for named in headings:
        named = re.split(r"\s+[—–-]\s+|\s+\(", named)[0]
        if not re.search(r"paste|output", named, re.I):
            return clean(named, key)
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
