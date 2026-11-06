#!/usr/bin/env python3
"""Judge the sweep's mechanical claims over a window's merged pull requests, with no agent.

`revise` `prepare` step 2 writes `.review/revision/claims.md`, a `### C-n · <path>:<line> · every
change|code` heading per documented claim; one a script can judge carries ` · script: <check>
[<arg>]` after it (`docs/contracts.md`, "The sweep's claims"). This script judges those, on the
pull requests `window_merges.py` listed with --doc and --dumps (its printout, --merges), from git
and the harvest's dumps (--dumps), and prints what `block_tally.py sweep` prints for a probe's
blocks:

    claim · C-n · judged <n> · follows <n> · breaks <n> · not touched <n> · not judged <n>[ · drift]
    break · C-n · pr-NNNN · <where> · <what>

An `every change` claim is judged only on the pull requests its document's `doc <path>:` line
lists, those opened after it reached the base branch; a `code` claim on every one listed. Checks:

- `template`: the claim's path is the pull request template, and its line the part it claims: a
  label opening that line (`Ticket:`), which the body, from `<dumps>/pr-NNNN/pr.json`, must open a
  line with, or else the heading on or above it, which the body must hold as a heading, case and
  level aside; not judged with no `pr.json` or an empty body.
- `changelog <file> <path>[,<path>]`: a pull request that changes a file under one of the paths,
  the code a user sees, also changes <file>; one that changes none of them is not touched.
- `todo`: no line it adds holds `TODO` without a ticket key matching --ticket-pattern on that
  line; not touched when it adds no `TODO`.
- `history`: no comment line it adds, `#` or `//`, says how the code used to be: "used to",
  "previously", "no longer", "was changed", "now uses", "the old"; not touched when it adds none.
  A heuristic: each break quotes the line for a person to judge.

`drift` follows a claim broken in more than half of the pull requests it touched. Exits 2 naming
why, printing nothing, for a claims or merges file that cannot be read, an unknown check, a
`changelog` with no file or paths, a `todo` with no --ticket-pattern, a template line with no
heading or label at or above it, or a git that cannot read a listed commit. Stdlib only, Python 3.9.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

CLAIM = re.compile(r"^### (C-\d+) · (.+?):(\d+) · (every change|code) · script: (\w+)(?: (\S+))?(?: (\S+))?\s*$", re.M)
MERGE = re.compile(r"^(pr-\d+) ([0-9a-f]{40}) \d{4}-\d{2}-\d{2}(?: (.*))?$")
DOC = re.compile(r"^doc (.+?): (pr-\d+(?: pr-\d+)*)$")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
LABEL = re.compile(r"^([A-Z][\w ]{0,30}):(?:\s|$)")
HISTORY = re.compile(r"(?i)\b(used to|previously|no longer|was changed|now uses|the old)\b")
CHECKS = ("template", "changelog", "todo", "history")


class CannotRun(Exception):
    """An input this script cannot judge from."""


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise CannotRun(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def added(repo: Path, sha: str) -> list[tuple[str, int, str]]:
    """The lines a merge adds against its first parent, as (path, line, text)."""
    out, path, line = [], None, 0
    for row in git(repo, "diff", "-U0", f"{sha}^1", sha).splitlines():
        if row.startswith("+++ "):
            path = row[6:] if row.startswith("+++ b/") else None
        elif row.startswith("@@"):
            line = int(re.match(r"@@ -\S+ \+(\d+)", row)[1])
        elif row.startswith("+") and path:
            out.append((path, line, row[1:]))
            line += 1
    return out


def template_needs(repo: Path, path: str, line: int, ref: str) -> tuple[list[str], list[str]]:
    """What the claim's line of the template asks of a body: the heading or label on that line, or
    else the nearest heading above it."""
    lines = git(repo, "show", f"{ref}:{path}").splitlines()
    for n in range(min(line, len(lines)), 0, -1):
        h, label = HEADING.match(lines[n - 1]), LABEL.match(lines[n - 1])
        if label and n == line:
            return [], [label[1]]
        if h:
            return [h[1].strip().lower()], []
    raise CannotRun(f"{path}:{line} has no heading or label at or above it to require")


def judge(check: str, arg: str | None, pr: str, sha: str, files: list[str], body: str | None, repo: Path,
          needs: tuple[list[str], list[str]] | None, ticket: re.Pattern | None) -> tuple[str, str, str]:
    """(verdict, where, what) for one claim on one pull request."""
    if check == "template":
        if not body or not body.strip():
            return "not judged", "", ""
        lines = body.splitlines()
        have = {m[1].strip().lower() for m in map(HEADING.match, lines) if m}
        for h in needs[0]:
            if h not in have:
                return "breaks", "description", f'no "{h}" heading'
        for label in needs[1]:
            if not any(x.startswith(f"{label}:") for x in lines):
                return "breaks", "description", f'no line opening "{label}:"'
        return "follows", "", ""
    if check == "changelog":
        code = [f for f in files if f != arg[0] and any(f.startswith(prefix) for prefix in arg[1])]
        if not code:
            return "not touched", "", ""
        return ("follows", "", "") if arg[0] in files else ("breaks", code[0], f"changes code and not {arg[0]}")
    found = []
    for path, line, text in added(repo, sha):
        if check == "todo" and "TODO" in text:
            found.append((path, line, text, not ticket.search(text)))
        elif check == "history" and re.match(r"\s*(#|//)", text) and HISTORY.search(text):
            found.append((path, line, text, True))
    if not found:
        return "not touched", "", ""
    bad = [f for f in found if f[3]]
    if not bad:
        return "follows", "", ""
    path, line, text, _ = bad[0]
    return "breaks", f"{path}:{line}", text.strip()[:120]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--ref", default="origin/main")
    p.add_argument("--claims", type=Path, required=True)
    p.add_argument("--merges", type=Path, required=True)
    p.add_argument("--dumps", type=Path, required=True)
    p.add_argument("--ticket-pattern", help="the profile's ticket.pattern, for the todo check")
    args = p.parse_args(argv)
    try:
        try:
            claims, merges = args.claims.read_text(), args.merges.read_text()
        except OSError as e:
            raise CannotRun(str(e)) from e
        ticket = re.compile(args.ticket_pattern) if args.ticket_pattern else None
        listed, opened_after = {}, {}
        for line in merges.splitlines():
            m, d = MERGE.match(line), DOC.match(line)
            if m:
                listed[m[1]] = (m[2], (m[3] or "").split())
            elif d:
                opened_after[d[1]] = set(d[2].split())
        rows, breaks = [], []
        for cid, path, line, kind, check, arg, code in CLAIM.findall(claims):
            if check not in CHECKS:
                raise CannotRun(f"{cid}: no check {check!r}; one of {', '.join(CHECKS)}")
            if check == "changelog" and not (arg and code):
                raise CannotRun(f"{cid}: changelog names no file, or no code paths, `changelog <file> <path>[,<path>]`")
            if check == "todo" and ticket is None:
                raise CannotRun(f"{cid}: the todo check needs --ticket-pattern")
            if kind == "every change" and path not in opened_after:
                raise CannotRun(f"{cid}: the merges file has no `doc {path}:` line")
            needs = template_needs(args.repo, path, int(line), args.ref) if check == "template" else None
            given = (arg, tuple(code.split(","))) if check == "changelog" else arg or None
            counts = Counter()
            for pr, (sha, files) in listed.items():
                if kind == "every change" and pr not in opened_after[path]:
                    continue
                body = None
                pr_json = args.dumps / pr / "pr.json"
                if pr_json.is_file():
                    body = json.loads(pr_json.read_text()).get("body")
                verdict, where, what = judge(check, given, pr, sha, files, body, args.repo, needs, ticket)
                counts[verdict] += 1
                if verdict == "breaks":
                    breaks.append(f"break · {cid} · {pr} · {where} · {what}")
            touched = counts["follows"] + counts["breaks"]
            drift = " · drift" if 2 * counts["breaks"] > touched else ""
            rows.append(f"claim · {cid} · judged {sum(counts.values())} · follows {counts['follows']} · breaks {counts['breaks']}"
                        f" · not touched {counts['not touched']} · not judged {counts['not judged']}{drift}")
    except CannotRun as e:
        print(f"CANNOT RUN: {e}", file=sys.stderr)
        return 2
    print("\n".join([*rows, *breaks]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
