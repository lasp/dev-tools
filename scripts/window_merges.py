#!/usr/bin/env python3
"""List the pull requests merged into the base branch in a window, and the rules each falls under, for revise.

Reads git only, so the sweep runs without a GitHub server. A merged pull request is a commit on
the first-parent history of --ref whose committer date, as a UTC day like GitHub's `merged_at`, is
--since or later, and whose subject names it as `merge_commit.py` reads one: `(#N)` at the end, as
GitHub writes a squash merge, or `Merge pull request #N `, as it writes a merge commit. A rebase
merge names none, and a subject naming two numbers names no one pull request; neither is listed.
Its files are those it changed against its first parent.

Prints, oldest first, one line per merged pull request:

    pr-NNNN <full sha> <YYYY-MM-DD, UTC> <path> [<path> ...]

With --ledger, then one line per live reviewer-tier rule, in ledger order:

    R-NNN pr-NNNN [pr-NNNN ...]     the pull requests with a file its scope: globs match
    R-NNN none                      none matched
    R-NNN predates pr-NNNN [...]    matched, but merged before the month its since: names
    R-NNN not swept: no scope       the rule has no scope: line

A glob matches as `rule_lint.py`'s scope check does: `fnmatch` against the path, `*` matching `/`.
A rule with no scope: line is never matched against every file; a rule with no since: is never
`predates`.

With --doc, one per document a claim of every change cites, and --dumps, the harvest's threads
directory, then one line per document, in the order given:

    doc <path>: pr-NNNN [pr-NNNN ...]          opened at or after the document reached --ref
    doc <path>: none                           none was
    doc <path>: predates pr-NNNN [...]         opened before it did
    doc <path>: no opened day pr-NNNN [...]    no <dumps>/pr-NNNN/pr.json to read it from
    doc <path>: not on <ref>                   no commit on --ref's first-parent history adds it

A document reaches --ref with the latest commit on its first-parent history that adds the path,
compared against its first parent, by committer time, so a document deleted and added again is
dated from its return; a pull request is opened at its pr.json's
`created_at`. Every pull request listed is on one of the first four lines.

A git that cannot read --ref, a --since that is not a date, a ledger that cannot be read or whose
since: is not `YYYY-MM` or `YYYY-MM-DD`, --doc without --dumps, a --dumps that is not a
directory, or a pr.json that is not JSON or
whose `created_at` is not a UTC time like `2026-10-01T12:00:00Z` prints the reason on stderr and
exits 2. Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


class CannotRun(Exception):
    """An input the script needs is missing or unreadable."""


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if out.returncode:
        raise CannotRun(f"git {' '.join(args)} in {repo}: {out.stderr.strip()}")
    return out.stdout


def merges(repo: Path, ref: str, since: str, pr_numbers) -> list[tuple[int, str, str, list[str]]]:
    """Each merged pull request in the window: its number, sha, merge day and changed files, oldest first."""
    found = []
    earlier = datetime.date.fromisoformat(since) - datetime.timedelta(days=2)
    log = git(repo, "log", "--first-parent", f"--since={earlier}", "--format=%H%x09%ct%x09%s", ref, "--")
    for line in reversed(log.splitlines()):
        sha, stamp, subject = line.split("\t", 2)
        day = datetime.datetime.fromtimestamp(int(stamp), datetime.timezone.utc).date().isoformat()
        numbers = pr_numbers(subject)
        if day < since or len(numbers) != 1:
            continue
        files = git(repo, "diff-tree", "-r", "-z", "--no-commit-id", "--name-only", "--root", "-m", "--first-parent", sha)
        found.append((numbers.pop(), sha, day, sorted(set(f for f in files.split("\0") if f))))
    return found


def in_scope(files: list[str], scope: str) -> bool:
    globs = [g.strip() for g in scope.split(",") if g.strip()]
    return any(fnmatch.fnmatchcase(f, g) for f in files for g in globs)


def rule_lines(entries: dict, found: list[tuple[int, str, str, list[str]]]) -> list[str]:
    lines = []
    for rid, e in entries.items():
        if e["tier"] != "reviewer" or e["status"] not in ("provisional", "established"):
            continue
        if "scope" not in e:
            lines.append(f"{rid} not swept: no scope")
            continue
        hit = [(n, day) for n, _, day, files in found if in_scope(files, e["scope"])]
        since = e["since"] if e["since"] != "-" else ""
        swept = [f"pr-{n:04d}" for n, day in hit if day[: len(since)] >= since]
        early = [f"pr-{n:04d}" for n, day in hit if day[: len(since)] < since]
        lines.append(f"{rid} {' '.join(swept)}" if swept else f"{rid} none")
        if early:
            lines.append(f"{rid} predates {' '.join(early)}")
    return lines


def reached(repo: Path, ref: str, path: str) -> int | None:
    """When `path` reached `ref`: the committer time of the latest first-parent commit adding it, or None."""
    adds = git(repo, "log", "--root", "--first-parent", "--diff-merges=first-parent", "--no-patch", "--diff-filter=A", "--format=%ct", ref, "--", path).split()
    return int(adds[0]) if adds else None


def opened(dumps: Path, n: int) -> int | None:
    """When pull request `n` was opened, from its dump's pr.json, or None with no pr.json."""
    path = dumps / f"pr-{n:04d}" / "pr.json"
    if not path.is_file():
        return None
    try:
        stamp = json.loads(path.read_text())["created_at"]
        return int(datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp())
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise CannotRun(f"{path}: no created_at like 2026-10-01T12:00:00Z: {e!r}") from e


def doc_lines(repo: Path, ref: str, docs: list[str], dumps: Path, found: list[tuple[int, str, str, list[str]]]) -> list[str]:
    days = {n: opened(dumps, n) for n, _, _, _ in found}
    lines = []
    for path in docs:
        since = reached(repo, ref, path)
        if since is None:
            lines.append(f"doc {path}: not on {ref}")
            continue
        after = [f"pr-{n:04d}" for n, t in days.items() if t is not None and t >= since]
        early = [f"pr-{n:04d}" for n, t in days.items() if t is not None and t < since]
        unknown = [f"pr-{n:04d}" for n, t in days.items() if t is None]
        lines.append(f"doc {path}: {' '.join(after)}" if after else f"doc {path}: none")
        if early:
            lines.append(f"doc {path}: predates {' '.join(early)}")
        if unknown:
            lines.append(f"doc {path}: no opened day {' '.join(unknown)}")
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, required=True, help="the repository's path")
    p.add_argument("--ref", required=True, help="the base branch, fetched, such as origin/main")
    p.add_argument("--since", required=True, help="the window's first day, YYYY-MM-DD")
    p.add_argument("--ledger", type=Path, help="the repository's standards/review-rules.md")
    p.add_argument("--doc", action="append", default=[], help="a document a claim of every change cites, relative to --repo; repeatable")
    p.add_argument("--dumps", type=Path, help="the harvest's .review/harvest/threads/, holding pr-NNNN/pr.json")
    args = p.parse_args(argv)
    try:
        if args.doc and args.dumps is None:
            raise CannotRun("--doc needs --dumps, which says when each pull request was opened")
        if args.dumps is not None and not args.dumps.is_dir():
            raise CannotRun(f"--dumps {args.dumps} is not a directory")
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
                raise ValueError("not YYYY-MM-DD")
            datetime.date.fromisoformat(args.since)
        except ValueError as e:
            raise CannotRun(f"--since {args.since}: {e}") from e
        entries = {}
        if args.ledger:
            try:
                entries = load("ratchet_counts").parse_entries(args.ledger.read_text(), args.ledger.name)
            except (OSError, ValueError) as e:
                raise CannotRun(f"{args.ledger}: {e}") from e
            for rid, e in entries.items():
                if e["since"] != "-" and not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", e["since"]):
                    raise CannotRun(f"{args.ledger}: {rid}'s since: {e['since']} is not YYYY-MM or YYYY-MM-DD")
        found = merges(args.repo, args.ref, args.since, load("merge_commit").pr_numbers)
        docs = doc_lines(args.repo, args.ref, args.doc, args.dumps, found) if args.doc else []
    except CannotRun as e:
        print(f"window_merges.py: {e}", file=sys.stderr)
        return 2
    for n, sha, day, files in found:
        print(f"pr-{n:04d} {sha} {day} {' '.join(files)}")
    for line in [*rule_lines(entries, found), *docs]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
