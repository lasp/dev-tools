#!/usr/bin/env python3
"""Print what a `rule-probe` is given from one drafted entry: the rule's title, wording and `Do not flag:` line.

The entry is `.review/backtest/R-NNN.entry.md`, as harvest.md's "The bar" drafts it: one
`### R-NNN · <title>` entry, its wording as the entry's `> ` lines, or under a second heading of
the same id and title after the entry, where the ledger keeps its wording in an instruction file.
The entry's `example:`, `scope:` and status lines are never printed, since the probe tests the
example line and must not be shown it.

Prints `R-NNN · <title>`, the wording one line each, then the `Do not flag:` line. Exits 2 with
one `CANNOT RUN` line on stderr, printing nothing, when the file is missing, holds no entry heading
or more than two, a second heading whose id or title differs from the entry's, no wording, wording
both in `> ` lines and under a second heading, or not exactly one `Do not flag:` line. Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^### (R-\d+)\b[ \t]*(?:·[ \t]*)?(.*?)[ \t]*$", re.M)
DO_NOT_FLAG = re.compile(r"^Do not flag:.*$", re.M)


class CannotRun(Exception):
    """The entry does not hold what the probe is given."""


def probe_input(text: str) -> list[str]:
    """The lines a probe is given from one drafted entry's text."""
    heads = list(HEADING.finditer(text))
    if not heads:
        raise CannotRun("no ### R-NNN entry")
    if len(heads) > 2:
        raise CannotRun(f"{len(heads)} ### R-NNN headings; an entry has one, and one more for its drafted wording")
    rid, title = heads[0].group(1), heads[0].group(2)
    entry = text[heads[0].end() : heads[1].start() if len(heads) == 2 else len(text)]
    quoted = [re.sub(r"^>[ \t]?", "", line) for line in entry.splitlines() if line.startswith(">")]
    quoted = [line for line in quoted if line.strip()]
    if len(heads) == 2:
        if heads[1].group(1) != rid or heads[1].group(2) != title:
            raise CannotRun(f"the wording heading is {heads[1].group(1)} · {heads[1].group(2)!r}, the entry {rid} · {title!r}")
        if quoted:
            raise CannotRun(f"{rid} has wording in its `> ` lines and under a second heading; it lives in one place")
        below = text[heads[1].end() :]
        wording = [line for line in below.splitlines() if line.strip() not in ("", "---") and not DO_NOT_FLAG.match(line)]
    else:
        wording = quoted
    if not wording:
        raise CannotRun(f"{rid} has no wording")
    flags = DO_NOT_FLAG.findall(text)
    if len(flags) != 1:
        raise CannotRun(f"{rid} has {len(flags)} `Do not flag:` lines; the probe is given one")
    return [f"{rid} · {title}", *wording, flags[0].rstrip()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("entry", type=Path, help="a drafted entry, .review/backtest/R-NNN.entry.md")
    args = p.parse_args(argv)
    try:
        if not args.entry.is_file():
            raise CannotRun(f"no file {args.entry}")
        lines = probe_input(args.entry.read_text())
    except CannotRun as e:
        print(f"CANNOT RUN: {args.entry}: {e}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
