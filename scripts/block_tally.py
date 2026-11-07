#!/usr/bin/env python3
"""Count the blocks revise's agents wrote, so the report's numbers come from the files.

`analysis <dir> pr-NNNN [...]` reads the named pull requests' `pr-NNNN.md`, each a `thread-analyst`
wrote under `.review/harvest/analysis/`; `sweep --claims <claims.md> [--merges <file>] <dir>
pr-NNNN [...]` each a `diff-probe` wrote under `.review/revision/sweep/`, every block judging every
`C-n` claim the claims file heads, except one marked ` · script: <check>`, which
`scripts/drift_checks.py` judges, and an `every change` claim whose document's `doc` line in
`--merges`, `scripts/window_merges.py`'s printout, does not name that pull request. Any other file in the directory, such as a block an earlier run left, is not
read. docs/contracts.md's "The analysis blocks" and "The sweep blocks" give both forms and both
printouts.

Exits 2 with one `CANNOT RUN` line on stderr, printing nothing, when the directory, a named block
or the sweep's claims or merges file is missing, a pull request is named twice or not as `pr-NNNN`, or a
block does not hold its form: a heading missing or naming another pull request than its file,
a line of no form the block takes, a `Procedure:`, `Not read:` or `Read:` line missing or
repeated, a line holding two verdicts, a claim judged twice in one sweep block, or a sweep block
missing a `C-n` claim it owes. A line holds two verdicts when an ask line carries a second `·
outcome:` or `· diff:`, or a sweep line's place or reason opens a field with a verdict word or
reads `judged as` one; the quoted line, which is code, is not read for it.
Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

BY = ("human", "bot", "ai-drafted")
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
# A claim's heading, and its check when a script judges it (`scripts/drift_checks.py`).
CLAIM_HEADING = re.compile(
    r"^### (?P<id>C-\d+) · (?P<path>.+?):(?P<line>\d+) · (?P<kind>every change|code)"
    r"(?: · script: (?P<check>template|todo|history|changelog (?P<arg>\S+ [^\s,]+(?:,[^\s,]+)*)))?$",
    re.M,
)
VERDICT = re.compile(
    r"^(?P<id>[RC]-\d+) · (?:follows · (?P<follows>.+)"
    r'|breaks · (?P<place>.+?) · "(?P<line>.*)" · (?P<why>.+)'
    r"|(?P<untouched>not touched)|(?P<unjudged>not judged · no description))$"
)
TAILS = ("Procedure:", "Not read:", "Read:")
# A second verdict in a sweep line's own words: a field that opens with one, or "judged as" one.
SECOND_VERDICT = re.compile(r"(?:^|· )(?:follows|breaks|not touched|not judged)\b|\bjudged as (?:follows|breaks|not touched|not judged)\b", re.I)


class CannotRun(Exception):
    """A block does not hold its form."""


def blocks(folder: Path, prs: list[str]) -> list[tuple[str, list[str]]]:
    """Each named pull request's `pr-NNNN.md` under folder, with its non-blank lines, in number order."""
    if not folder.is_dir():
        raise CannotRun(f"no directory {folder}")
    for pr in prs:
        if not re.fullmatch(r"pr-\d+", pr):
            raise CannotRun(f"{pr}: not a pull request as pr-NNNN")
    if len(set(prs)) != len(prs):
        raise CannotRun(f"a pull request named twice: {' '.join(sorted(p for p in set(prs) if prs.count(p) > 1))}")
    out = []
    for pr in sorted(prs, key=lambda p: int(p[3:])):
        path = folder / f"{pr}.md"
        if not path.is_file():
            raise CannotRun(f"{pr}: no block {path}")
        out.append((pr, [line.rstrip() for line in path.read_text().splitlines() if line.strip()]))
    return out


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


def analysis(folder: Path, prs: list[str]) -> list[str]:
    counts: Counter = Counter()
    asks = none = mismatches = 0
    unanswered, procedure, not_read, mismatched = [], [], [], []
    found = blocks(folder, prs)
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
            if line.count(" · outcome: ") > 1 or line.count(" · diff: ") > 1:
                raise CannotRun(f"{pr}: two verdicts in one ask line: {line}")
            if a["asked"] == "none":
                none += 1
                continue
            asks += 1
            outcome = "declined" if a["outcome"].startswith("declined") else a["outcome"]
            counts[(a["by"], a["source"], a["category"], outcome)] += 1
            if outcome == "unanswered":
                unanswered.append(f"outcome unanswered · {pr} · {a['source']} {a['id']} · by: {a['by']} · diff: {a['diff']}")
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


def opened_after(merges: Path) -> dict[str, set[str]]:
    """Each document's pull requests from window_merges' `doc <path>: pr-NNNN [...]` and `doc <path>: none` lines."""
    after: dict[str, set[str]] = {}
    for line in merges.read_text().splitlines():
        m = re.match(r"doc (.+?): (pr-\d{4,}(?: pr-\d{4,})*|none|not on \S+)$", line)
        if m:
            after.setdefault(m[1], set()).update(m[2].split() if m[2].startswith("pr-") else ())
    return after


def sweep(folder: Path, prs: list[str], claims: Path | None, merges: Path | None = None) -> list[str]:
    if claims is None or not claims.is_file():
        raise CannotRun(f"no claims file {claims}" if claims else "the sweep needs --claims <claims.md>")
    if merges is not None and not merges.is_file():
        raise CannotRun(f"no merges file {merges}")
    text = claims.read_text()
    headings = list(CLAIM_HEADING.finditer(text))
    if len(headings) != len(re.findall(r"^### C-\d+\b", text, re.M)):
        raise CannotRun(f"{claims}: a `### C-n` heading is not `### C-n · <path>:<line> · every change|code[ · script: <check>]`")
    documented = [(h["id"], h["path"], h["kind"]) for h in headings if not h["check"]]
    after = opened_after(merges) if merges else None
    for cid, path, kind in documented:
        if after is not None and kind == "every change" and path not in after:
            raise CannotRun(f"{cid}: {merges} has no `doc {path}` line")
    verdicts: dict[str, Counter] = {}
    breaks: list[tuple[str, str]] = []
    not_read = []
    found = blocks(folder, prs)
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
            own = (v["follows"], v["place"], v["why"])
            if any(f and SECOND_VERDICT.search(f) for f in own):
                raise CannotRun(f"{pr}: two verdicts in one line: {line}")
            if v["id"] in seen:
                raise CannotRun(f"{pr}: {v['id']} judged twice")
            seen.add(v["id"])
            word = "follows" if v["follows"] else "breaks" if v["place"] else "not touched" if v["untouched"] else "not judged"
            verdicts.setdefault(v["id"], Counter())[word] += 1
            if word == "breaks":
                breaks.append((v["id"], f"break · {v['id']} · {pr} · {v['place']}"))
        owed = [c for c, path, kind in documented if after is None or kind == "code" or pr in after[path]]
        missing = [c for c in owed if c not in seen]
        if missing:
            raise CannotRun(f"{pr}: no line for {', '.join(missing)}, which it is judged on")
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
    p.add_argument("prs", nargs="+", help="the pull requests whose blocks to count, as pr-NNNN")
    p.add_argument("--claims", type=Path, help="sweep only, and required there: .review/revision/claims.md")
    p.add_argument("--merges", type=Path, help="sweep only: window_merges.py's printout with --doc, .review/revision/merges.txt")
    args = p.parse_args(argv)
    try:
        if args.kind == "analysis":
            lines = analysis(args.folder, args.prs)
        else:
            lines = sweep(args.folder, args.prs, args.claims, args.merges)
    except CannotRun as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
