#!/usr/bin/env python3
"""Print the commit each merged pull request landed as on the base branch, for revise.

The GitHub MCP server's `pull_request_read` `get` result carries no merge commit, so the commit is
read from git: the one commit on the first-parent history of --ref whose subject ends in `(#N)`,
as GitHub writes a squash merge, or starts `Merge pull request #N `, as it writes a merge commit.
Each argument is a dump's `pr.json`; its `number` and `merged: true` are required.

Prints one line per `pr.json`, in the order given: `pr-NNNN <full sha>`, or `pr-NNNN none · <why>`
when no commit or more than one matches, since a guessed commit would put a reading on the wrong
tree; exits 1 when any line is `none`. A `pr.json` that is not JSON, has no number or is not
merged, or a git that cannot read --ref, prints the reason on stderr and exits 2. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


class CannotRun(Exception):
    """An input the script needs is missing or unreadable."""


def first_parent(repo: Path, ref: str) -> list[tuple[str, str]]:
    """The first-parent history of ref, each commit's full sha and subject, newest first."""
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "--first-parent", "--format=%H %s", ref, "--"],
        capture_output=True,
        text=True,
    )
    if out.returncode:
        raise CannotRun(f"git log {ref} in {repo}: {out.stderr.strip()}")
    return [tuple(line.split(" ", 1)) if " " in line else (line, "") for line in out.stdout.splitlines()]


def number_of(path: Path) -> int:
    try:
        pr = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise CannotRun(f"{path}: {e}") from e
    if not isinstance(pr, dict) or not isinstance(pr.get("number"), int):
        raise CannotRun(f"{path}: no 'number'")
    if pr.get("merged") is not True:
        raise CannotRun(f"{path}: pull request #{pr['number']} is not merged")
    return pr["number"]


NAMED = re.compile(r"\(#(\d+)\)\s*$|^Merge pull request #(\d+)\b")


def pr_numbers(subject: str) -> set[int]:
    """The pull request numbers a merge subject names: `(#N)` at its end, or `Merge pull request #N` at its start."""
    return {int(n) for m in NAMED.finditer(subject) for n in m.groups() if n}


def merge_commit(history: list[tuple[str, str]], number: int) -> tuple[str | None, str]:
    """The sha of the one commit whose subject names the pull request, or None and why."""
    found = [sha for sha, subject in history if number in pr_numbers(subject)]
    if len(found) == 1:
        return found[0], ""
    if not found:
        return None, f"no commit on the first-parent history names #{number}"
    return None, f"{len(found)} commits name #{number}: {', '.join(s[:7] for s in found)}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, required=True, help="the repository's path")
    p.add_argument("--ref", required=True, help="the base branch, fetched, such as origin/main")
    p.add_argument("pr_json", type=Path, nargs="+", help="a dump's pr.json")
    args = p.parse_args(argv)
    try:
        numbers = [number_of(path) for path in args.pr_json]
        history = first_parent(args.repo, args.ref)
    except CannotRun as e:
        print(f"merge_commit.py: {e}", file=sys.stderr)
        return 2
    missing = False
    for number in numbers:
        sha, why = merge_commit(history, number)
        missing |= sha is None
        print(f"pr-{number:04d} {sha}" if sha else f"pr-{number:04d} none · {why}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
