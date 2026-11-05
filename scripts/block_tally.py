#!/usr/bin/env python3
"""Count the blocks revise's agents wrote, so the report's numbers come from the files.

`analysis <dir>` reads each `pr-NNNN.md` a `thread-analyst` wrote under
`.review/harvest/analysis/`; `sweep <dir>` each one a `diff-probe` wrote under
`.review/revision/sweep/`. docs/contracts.md's "The analysis blocks" and "The sweep blocks" give
both forms and both printouts.

Exits 2 with one `CANNOT RUN` line on stderr, printing nothing, when the directory is missing or
a block does not hold its form: a heading missing or naming another pull request than its file,
a line of no form the block takes, a `Procedure:`, `Not read:` or `Read:` line missing or
repeated, or a claim judged twice in one sweep block. Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

BY = ("human", "ai-drafted", "bot")
SOURCES = ("thread", "review", "comment")
CATEGORIES = ("design", "correctness", "tests", "naming", "docs", "scope", "process", "style")
OUTCOMES = ("changed as asked", "changed differently", "declined", "discussed, no change", "unanswered", "none")
ASK = re.compile(
    r"^(?P<source>thread|review|comment) (?P<id>\S+) · (?P<opener>.+?) · by: (?P<by>human|bot|ai-drafted)"
    rf" · (?P<category>{'|'.join(CATEGORIES)}) · asked: (?P<asked>.*)"
    r' · outcome: (?P<outcome>changed as asked|changed differently|declined: ".*"|discussed, no change|unanswered|none)'
    r" · diff: (?P<diff>addresses it|does not|cannot tell)$"
)
ANALYSIS_HEAD = re.compile(r"^## (pr-\d+) — threads read$")
MISMATCH = re.compile(r"^record mismatch: (.+)$")
SWEEP_HEAD = re.compile(r"^## (pr-\d+) · [0-9a-f]{7}$")
VERDICT = re.compile(
    r"^(?P<id>[RC]-\d+) · (?:follows · (?P<follows>.+)"
    r'|breaks · (?P<place>.+?) · "(?P<line>.*)" · (?P<why>.+)'
    r"|(?P<untouched>not touched)|(?P<unjudged>not judged · no description))$"
)
TAILS = ("Procedure:", "Not read:", "Read:")


class CannotRun(Exception):
    """A block does not hold its form."""


def blocks(folder: Path) -> list[tuple[str, list[str]]]:
    """Each `pr-NNNN.md` under folder, its pull request and its non-blank lines, in number order."""
    if not folder.is_dir():
        raise CannotRun(f"no directory {folder}")
    found = list(folder.glob("pr-*.md"))
    for path in found:
        if not re.fullmatch(r"pr-\d+", path.stem):
            raise CannotRun(f"{path}: not named pr-NNNN.md")
    found.sort(key=lambda p: int(p.stem[3:]))
    return [(p.stem, [line.rstrip() for line in p.read_text().splitlines() if line.strip()]) for p in found]


def claim_order(cid: str) -> tuple[bool, int]:
    """Rules before documented claims, each by number."""
    return cid[0] != "R", int(cid[2:])


def tails(pr: str, lines: list[str], names: tuple[str, ...]) -> dict[str, str]:
    """The block's closing lines by name, each exactly once."""
    got: dict[str, str] = {}
    for line in lines:
        for name in names:
            if line.startswith(name + " ") or line == name:
                if name in got:
                    raise CannotRun(f"{pr}: two `{name}` lines")
                got[name] = line[len(name) :].strip()
    for name in names:
        if name not in got:
            raise CannotRun(f"{pr}: no `{name}` line")
    return got


def analysis(folder: Path) -> list[str]:
    counts: Counter = Counter()
    asks = none = mismatches = 0
    unanswered, procedure, not_read, mismatched = [], [], [], []
    found = blocks(folder)
    for pr, lines in found:
        if not lines:
            raise CannotRun(f"{pr}: empty")
        m = MISMATCH.match(lines[0])
        if m and len(lines) == 1:
            mismatches += 1
            mismatched.append(f"mismatch · {pr} · {m.group(1)}")
            continue
        head = ANALYSIS_HEAD.match(lines[0])
        if not head:
            raise CannotRun(f"{pr}: the first line is not `## {pr} — threads read` or one `record mismatch:` line")
        if head.group(1) != pr:
            raise CannotRun(f"{pr}: the heading names {head.group(1)}")
        tail = tails(pr, lines[1:], TAILS)
        for line in lines[1:]:
            if any(line.startswith(t) for t in TAILS):
                continue
            a = ASK.match(line)
            if not a:
                raise CannotRun(f"{pr}: not an ask line: {line}")
            if a["asked"] == "none":
                none += 1
                continue
            asks += 1
            outcome = "declined" if a["outcome"].startswith("declined") else a["outcome"]
            counts[(a["by"], a["source"], a["category"], outcome)] += 1
            if outcome == "unanswered":
                unanswered.append(f"unanswered · {pr} · {a['source']} {a['id']} · by: {a['by']} · diff: {a['diff']}")
        if tail["Procedure:"] != "none":
            procedure.append(f"procedure · {pr} · {tail['Procedure:']}")
        if tail["Not read:"] != "none":
            not_read.append(f"not read · {pr} · {tail['Not read:']}")
    order = sorted(counts, key=lambda k: (BY.index(k[0]), SOURCES.index(k[1]), CATEGORIES.index(k[2]), OUTCOMES.index(k[3])))
    return [
        f"blocks: {len(found)} · asks: {asks} · asked none: {none} · mismatches: {mismatches}",
        *(f"count · {' · '.join(k)} · {counts[k]}" for k in order),
        *unanswered,
        *procedure,
        *not_read,
        *mismatched,
    ]


def sweep(folder: Path) -> list[str]:
    verdicts: dict[str, Counter] = {}
    breaks: list[tuple[str, str]] = []
    not_read = []
    found = blocks(folder)
    for pr, lines in found:
        head = SWEEP_HEAD.match(lines[0]) if lines else None
        if not head:
            raise CannotRun(f"{pr}: the first line is not `## {pr} · <sha, 7 characters>`")
        if head.group(1) != pr:
            raise CannotRun(f"{pr}: the heading names {head.group(1)}")
        tail = tails(pr, lines[1:], ("Not read:",))
        seen = set()
        for line in lines[1:]:
            if line.startswith("Not read:"):
                continue
            v = VERDICT.match(line)
            if not v:
                raise CannotRun(f"{pr}: not a verdict line: {line}")
            if v["id"] in seen:
                raise CannotRun(f"{pr}: {v['id']} judged twice")
            seen.add(v["id"])
            word = "follows" if v["follows"] else "breaks" if v["place"] else "not touched" if v["untouched"] else "not judged"
            verdicts.setdefault(v["id"], Counter())[word] += 1
            if word == "breaks":
                breaks.append((v["id"], f"break · {v['id']} · {pr} · {v['place']}"))
        if tail["Not read:"] != "none":
            not_read.append(f"not read · {pr} · {tail['Not read:']}")
    rows = []
    for cid in sorted(verdicts, key=claim_order):
        c = verdicts[cid]
        touched = c["follows"] + c["breaks"]
        drift = " · drift" if 2 * c["breaks"] > touched else ""
        rows.append(
            f"claim · {cid} · judged {sum(c.values())} · follows {c['follows']} · breaks {c['breaks']}"
            f" · not touched {c['not touched']} · not judged {c['not judged']}{drift}"
        )
    breaks.sort(key=lambda b: claim_order(b[0]))
    return [f"blocks: {len(found)}", *rows, *(line for _, line in breaks), *not_read]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("kind", choices=("analysis", "sweep"), help="thread-analyst blocks or diff-probe blocks")
    p.add_argument("folder", type=Path, help="the directory holding the pr-NNNN.md blocks")
    args = p.parse_args(argv)
    try:
        lines = (analysis if args.kind == "analysis" else sweep)(args.folder)
    except CannotRun as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
