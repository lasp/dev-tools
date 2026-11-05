#!/usr/bin/env python3
"""Check a standard's agent guidance and data conventions files hold their entries' form.

`agent-guidance.md` holds `A-NNN` entries, habits coding agents should not repeat, and
`data-conventions.md` holds `F-NNN` entries, facts about inputs and products, each with its source
(`docs/standards.md`, "Agent guidance and data conventions"; the form is `docs/contracts.md`'s).
Each entry is:

    ### A-001 · <title>
    repos: [<repo>, ...]                                optional, at most one
    _YYYY-MM · seen YYYY-MM_                            agent guidance: admitted, last seen
    _YYYY-MM_                                           data conventions: admitted
    habit: <the habit it replaces>                      agent guidance only, exactly one
    > <what to do: the instruction an agent reads>      one or more
    source: <the document, or the data's owner>         data conventions only, exactly one
    said: "<a person's words>" — <login>, <url>         agent guidance one or more; optional otherwise

A retired entry leaves the file for the standard's `archive/`, as a retired rule does. Text before
the first entry is the file's own, and nothing inside a code fence is read, so an example shown in
one is not an entry. Given files by those names, it prints `ok · <file> · <n> entries` for each,
and exits 0; otherwise one `refused · <file>:<line> · <why>` line per fault, every fault found, and
exits 1: a file of another name or that cannot be read; a `## ` or `### ` heading that is not an
entry of the file's letter; an id given twice or out of order; a second `repos:` line; no date line of the file's form
first, or a `seen` month before the admitted one; no `> ` line; not exactly one `habit:` line (agent
guidance) or `source:` line (data conventions), or a line of the other file's kind; a `said:` line
not of the form above, or none in agent guidance. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

MONTH = r"\d{4}-(?:0[1-9]|1[0-2])"
KINDS = {
    "agent-guidance.md": ("A", "habit:", "source:", re.compile(rf"_({MONTH}) · seen ({MONTH})_")),
    "data-conventions.md": ("F", "source:", "habit:", re.compile(rf"_({MONTH})_")),
}
SAID = re.compile(r'said: "\S.*" — [^\s,]+, https?://\S+')

spec = importlib.util.spec_from_file_location("ratchet_counts", Path(__file__).with_name("ratchet_counts.py"))
ratchet_counts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ratchet_counts)


def blocks(lines: list[str]) -> list[tuple[int, str, list[str]]]:
    """Each `## ` or `### ` heading's line number, text and the non-blank lines under it, to the next heading."""
    out: list[tuple[int, str, list[str]]] = []
    for n, line in enumerate(lines, 1):
        if re.match(r"#{1,3} ", line):
            out.append((n, line if re.match(r"#{2,3} ", line) else "", []))
        elif out and line.strip():
            out[-1][2].append(line.rstrip())
    return [b for b in out if b[1]]


def check(path: Path) -> tuple[list[str], int]:
    if path.name not in KINDS:
        return [f"refused · {path} · not agent-guidance.md or data-conventions.md"], 0
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"refused · {path} · cannot be read: {e}"], 0
    letter, own, other, dated = KINDS[path.name]
    faults, last, found = [], 0, blocks(ratchet_counts.unfenced(text).splitlines())
    for n, heading, body in found:
        where = f"{path}:{n}"
        m = re.fullmatch(rf"### {letter}-(\d{{3,}}) · \S.*", heading.rstrip())
        if not m:
            faults.append(f"refused · {where} · a heading not `### {letter}-NNN · <title>`")
            continue
        if int(m[1]) <= last:
            faults.append(f"refused · {where} · {letter}-{m[1]} given twice or out of order")
        last = max(last, int(m[1]))
        if sum(x.startswith("repos:") for x in body) > 1:
            faults.append(f"refused · {where} · a second `repos:` line, which standard_file.sh would not read")
        body = [x for x in body if not x.startswith("repos:")]
        date = dated.fullmatch(body[0]) if body else None
        if not date:
            form = "_YYYY-MM · seen YYYY-MM_" if letter == "A" else "_YYYY-MM_"
            faults.append(f"refused · {where} · no `{form}` line first")
        elif letter == "A" and date[2] < date[1]:
            faults.append(f"refused · {where} · seen {date[2]}, before it was admitted in {date[1]}")
        if not any(x.startswith("> ") for x in body):
            faults.append(f"refused · {where} · no `> ` line")
        if sum(x.startswith(own) for x in body) != 1:
            faults.append(f"refused · {where} · not exactly one `{own}` line")
        if any(x.startswith(other) for x in body):
            faults.append(f"refused · {where} · a `{other}` line, which belongs in the other file")
        said = [x for x in body if x.startswith("said:")]
        if any(not SAID.fullmatch(x) for x in said):
            faults.append(f"refused · {where} · a `said:` line not `said: \"<words>\" — <login>, <url>`")
        if letter == "A" and not said:
            faults.append(f"refused · {where} · no `said:` line: agent guidance quotes a person")
    return faults, len(found)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("files", type=Path, nargs="+")
    args = p.parse_args(argv)
    faults, oks = [], []
    for path in args.files:
        f, n = check(path)
        faults += f
        if not f:
            oks.append(f"ok · {path} · {n} entr{'y' if n == 1 else 'ies'}")
    print("\n".join(faults or oks))
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
