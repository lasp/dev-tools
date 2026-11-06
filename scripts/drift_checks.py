#!/usr/bin/env python3
"""Judge the sweep's mechanical claims over a window's merged pull requests, with no agent.

`revise` `prepare` step 2 writes `.review/revision/claims.md`, a `### C-n · <path>:<line> · every
change|code` heading per documented claim; one a script can judge carries ` · script: <check>`
after it, its form `block_tally.py`'s CLAIM_HEADING (`docs/contracts.md`, "The sweep blocks"). This
script judges those, on the pull requests `window_merges.py` listed (its printout, --merges), from
git and the harvest's dumps (--dumps), and prints what `block_tally.py sweep` prints for a probe's
blocks, a break's last field what it found:

    claim · C-n · judged <n> · follows <n> · breaks <n> · not touched <n> · not judged <n>[ · drift]
    break · C-n · pr-NNNN · <where> · <what>

An `every change` claim is judged only on the pull requests its document's `doc <path>:` line lists,
those opened after it reached the base branch, none for `doc <path>: none` or `not on`; a `code`
claim on every one listed. Checks:

- `template`: the claim's path is the pull request template, as --ref holds it, and its line the
  part it claims: a label opening that line (`Ticket:`), which the body, from `<dumps>/pr-NNNN/
  pr.json`, must open a line with, or else the heading on or above it, which the body must hold as
  a heading, case and level aside. A pull request opened before that label or heading first
  appeared in the template on --ref is not judged on it; one with no `pr.json`, an empty body or no
  `created_at` is not judged either.
- `changelog <file> <path>[,<path>]`: a pull request that changes a file under one of the paths,
  the code a user sees, also changes <file>; one that changes none of them is not touched.
- `todo`: no comment it adds, a line opening `#`, `//`, `/*`, `*` or `<!--`, holds the word `TODO`
  without a ticket key matching --ticket-pattern on that line; not touched when it adds none.
- `history`: no comment line it adds, `#` or `//`, in a file other than Markdown or reStructuredText,
  says how the code used to be: "used to", "previously", "no longer", "was changed", "now uses",
  "the old"; not touched when it adds none. A heuristic: each break quotes the line for a person to
  judge.

A merge's added lines are its diff against its first parent, read with git's own prefixes and no
color, external diff or text conversion, whatever the person's config. `drift` follows a claim
broken in more than half of the pull requests it touched. Exits 2 naming why, printing nothing, for
a claims or merges file that cannot be read, a heading marked ` · script:` that is not of the
form, a `todo` with no --ticket-pattern or one that is not a regular expression, an `every change`
claim whose document has no `doc` line, a template line with no heading or label at or above it, a
`pr.json` that is not JSON, or a git that cannot read a listed commit. Stdlib only, Python 3.9.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

spec = importlib.util.spec_from_file_location("block_tally", Path(__file__).with_name("block_tally.py"))
block_tally = importlib.util.module_from_spec(spec)
spec.loader.exec_module(block_tally)

MERGE = re.compile(r"^(pr-\d+) ([0-9a-f]{40}) \d{4}-\d{2}-\d{2}(?: (.*))?$")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
LABEL = re.compile(r"^([A-Z][\w ]{0,30}):(?:\s|$)")
TODO = re.compile(r"^\s*(#|//|/\*|\*|<!--).*\bTODO\b")
HISTORY = re.compile(r"(?i)\b(used to|previously|no longer|was changed|now uses|the old)\b")
PROSE = (".md", ".rst")


class CannotRun(Exception):
    """An input this script cannot judge from."""


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise CannotRun(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def added(repo: Path, sha: str) -> list[tuple[str, int, str]]:
    """The lines a merge adds against its first parent, as (path, line, text)."""
    diff = git(repo, "-c", "core.quotePath=false", "diff", "--no-color", "--no-ext-diff", "--no-textconv",
               "--src-prefix=a/", "--dst-prefix=b/", "-U0", f"{sha}^1", sha)
    out, path, line, header = [], None, 0, False
    for row in diff.splitlines():
        if row.startswith("diff --git "):
            path, header = None, True
        elif header and row.startswith("+++ "):
            path = row[6:] if row.startswith("+++ b/") else None
        elif row.startswith("@@"):
            header = False
            line = int(re.match(r"@@ -\S+ \+(\d+)", row)[1])
        elif not header and row.startswith("+") and path:
            out.append((path, line, row[1:]))
            line += 1
    return out


def template_part(repo: Path, path: str, line: int, ref: str) -> tuple[str, str, str]:
    """The claim's part of the template, ("heading" | "label", its text, the day it first appeared
    on --ref, a day): the label opening its line, or the heading on or above it."""
    lines = git(repo, "show", f"{ref}:{path}").splitlines()
    for n in range(min(line, len(lines)), 0, -1):
        h, label = HEADING.match(lines[n - 1]), LABEL.match(lines[n - 1])
        if (label and n == line) or h:
            kind, text, source = ("label", label[1], lines[n - 1]) if label and n == line else ("heading", h[1].strip(), lines[n - 1])
            dates = git(repo, "log", "--first-parent", "--format=%cs", "-S", source, ref, "--", path).split()
            return kind, text, min(dates) if dates else ""
    raise CannotRun(f"{path}:{line} has no heading or label at or above it to require")


def judge(check: str, arg, files: list[str], pr_json: dict | None, repo: Path, sha: str,
          part: tuple[str, str, str] | None, ticket: re.Pattern | None) -> tuple[str, str, str]:
    """(verdict, where, what) for one claim on one pull request."""
    if check == "template":
        body, opened = (pr_json or {}).get("body"), (pr_json or {}).get("created_at")
        if not body or not body.strip() or not opened:
            return "not judged", "", ""
        kind, text, since = part
        if since and opened[:10] < since:
            return "not judged", "", ""
        lines = body.splitlines()
        if kind == "heading":
            have = {m[1].strip().lower() for m in map(HEADING.match, lines) if m}
            return ("follows", "", "") if text.lower() in have else ("breaks", "description", f'no "{text}" heading')
        return ("follows", "", "") if any(x.startswith(f"{text}:") for x in lines) else (
            "breaks", "description", f'no line opening "{text}:"')
    if check == "changelog":
        log, prefixes = arg
        code = [f for f in files if f != log and f.startswith(prefixes)]
        if not code:
            return "not touched", "", ""
        return ("follows", "", "") if log in files else ("breaks", code[0], f"changes code and not {log}")
    found = []
    for path, line, text in added(repo, sha):
        if check == "todo" and TODO.search(text):
            found.append((path, line, text, not ticket.search(text)))
        elif check == "history" and not path.endswith(PROSE) and re.match(r"\s*(#|//)", text) and HISTORY.search(text):
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
            ticket = re.compile(args.ticket_pattern) if args.ticket_pattern else None
        except (OSError, re.error) as e:
            raise CannotRun(str(e)) from e
        marked = re.findall(r"^### C-\d+ .* · script:", claims, re.M)
        headings = [h for h in block_tally.CLAIM_HEADING.finditer(claims) if h["check"]]
        if len(headings) != len(marked):
            raise CannotRun("a heading marked ` · script:` is not `### C-n · <path>:<line> · every change|code · script: "
                            "template|todo|history|changelog <file> <path>[,<path>]`")
        listed = {m[1]: (m[2], (m[3] or "").split()) for m in map(MERGE.match, merges.splitlines()) if m}
        after = block_tally.opened_after(args.merges)
        rows, breaks = [], []
        for h in headings:
            cid, path, kind, check, arg = h["id"], h["path"], h["kind"], h["check"].split()[0], h["arg"]
            if check == "todo" and ticket is None:
                raise CannotRun(f"{cid}: the todo check needs --ticket-pattern")
            if kind == "every change" and path not in after:
                raise CannotRun(f"{cid}: the merges file has no `doc {path}:` line")
            part = template_part(args.repo, path, int(h["line"]), args.ref) if check == "template" else None
            given = (arg.split()[0], tuple(arg.split()[1].split(","))) if check == "changelog" else None
            counts = Counter()
            for pr, (sha, files) in listed.items():
                if kind == "every change" and pr not in after[path]:
                    continue
                pr_json = None
                source = args.dumps / pr / "pr.json"
                if source.is_file():
                    try:
                        pr_json = json.loads(source.read_text())
                    except json.JSONDecodeError as e:
                        raise CannotRun(f"{source} is not JSON: {e}") from e
                verdict, where, what = judge(check, given, files, pr_json, args.repo, sha, part, ticket)
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
