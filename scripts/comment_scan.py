#!/usr/bin/env python3
"""Mark the comments a change adds that the review contract's "Comments" section asks a reviewer to judge.

Run inside the repository, with the base the change is diffed against. The change is the diff from
the base's merge base with HEAD to the working tree, untracked files included, or, with `--head
<rev>`, from the merge base of the base and `<rev>` to `<rev>` as committed. Only line comments in
code are read: `#` in Python, shell, YAML and TOML files, `//` in C-family, Go, Rust, Java and
JavaScript files; docstrings and documentation files are not. One line each, `path:line · kind ·
text`, and nothing at all when there is nothing to mark:

- `todo`: a TODO, FIXME, XXX or HACK with no ticket key, a `#<n>` issue or an issue URL. The key
  is the profile's `ticket.pattern`, or any `ABC-123` when the profile records none.
- `follow-up`: a note about later work with no TODO, such as "follow-up" or "eventually".
- `session`: a comment that narrates the change or the session rather than the code, such as "as
  requested", "now we", "per review", "(NEW" or a phase reference.
- `long`: a run of six or more added comment lines, given at its first line with its length.

A mark is a candidate, not a finding: the reviewer reads the comment and decides. Lint pragmas,
shebangs and encoding lines are never marked.

It runs from anywhere in the repository; the paths are the top level's. Exits 1 naming the cause
when git fails or the profile is refused. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIFF = ("diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames", "--no-relative", "-U0")
HASH = {".py", ".pyi", ".sh", ".bash", ".yaml", ".yml", ".toml", ".cfg", ".r"}
SLASH = {".c", ".h", ".cc", ".cpp", ".hpp", ".go", ".rs", ".java", ".js", ".ts", ".jsx", ".tsx", ".kt", ".swift"}
PRAGMA = re.compile(r"^(!|\s*-\*-|\s*(noqa|type:|pragma|fmt:|pylint:|ruff:|mypy:|isort:|nosec|codespell))", re.I)
TODO = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
ISSUE = re.compile(r"#\d+\b|https?://\S+/(issues|browse|pull)/\S+")
FOLLOW_UP = re.compile(r"\b(follow[- ]?up|eventually|someday|in a later (change|pr|pull request|version)|"
                       r"not (done|handled|implemented) yet|left for later|revisit)\b", re.I)
SESSION = re.compile(r"\b(as requested|as discussed|as asked|per (the )?(review|reviewer|request|user|plan|ticket)|"
                     r"now we|was changed|(?-i:Phase) \d+\b(?![-–])|this (session|pr|pull request|commit)|"
                     r"the plan says|claude|llm)\b|\(new\b", re.I)
LONG = 6


def load_profile():
    spec = importlib.util.spec_from_file_location("profile", ROOT / "scripts" / "profile.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def marker(path: str) -> str | None:
    suffix = Path(path).suffix.lower()
    return "#" if suffix in HASH else "//" if suffix in SLASH else None


def added(top: str, base: str, head: str | None) -> list[tuple[str, int, str]]:
    """Each added line of a code file, as (path, line number on the new side, text)."""
    if head:
        diff = git("-C", top, *DIFF, git("-C", top, "merge-base", base, head).strip(), head)
        untracked = []
    else:
        diff = git("-C", top, *DIFF, git("-C", top, "merge-base", base, "HEAD").strip())
        untracked = [p for p in git("-C", top, "ls-files", "-z", "--others", "--exclude-standard").split("\0") if p]
    out, path, n = [], None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            n = int(re.match(r"@@ -\S+ \+(\d+)", line).group(1))
        elif path and line.startswith("+"):
            out.append((path, n, line[1:]))
            n += 1
    for path in untracked:
        if marker(path):
            try:
                text = (Path(top) / path).read_text(errors="replace")
            except OSError:
                continue
            out += [(path, i, t) for i, t in enumerate(text.splitlines(), 1)]
    return [a for a in out if marker(a[0])]


def comment(path: str, text: str) -> str | None:
    """The comment text of a line that is only a comment, or None."""
    m = marker(path)
    stripped = text.lstrip()
    if not stripped.startswith(m):
        return None
    body = stripped[len(m):]
    return None if PRAGMA.match(body) else body.strip()


def scan(lines: list[tuple[str, int, str]], key: re.Pattern) -> list[str]:
    marks, run = [], []

    def close():
        if len(run) >= LONG:
            marks.append(f"{run[0][0]}:{run[0][1]} · long · {len(run)} lines")
        run.clear()

    for path, n, text in lines:
        body = comment(path, text)
        if body is None:
            close()
            continue
        if run and (run[-1][0] != path or run[-1][1] != n - 1):
            close()
        run.append((path, n))
        excerpt = body if len(body) <= 80 else body[:77] + "..."
        if TODO.search(body):
            if not (ISSUE.search(body) or key.search(body)):
                marks.append(f"{path}:{n} · todo · {excerpt}")
        elif FOLLOW_UP.search(body):
            marks.append(f"{path}:{n} · follow-up · {excerpt}")
        if SESSION.search(body):
            marks.append(f"{path}:{n} · session · {excerpt}")
    close()
    return marks


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("base", help="the commit or branch the change is diffed against")
    p.add_argument("--head", help="read this revision as committed instead of the working tree")
    p.add_argument("--repo", help="owner/repo; by default the origin remote's")
    args = p.parse_args(argv)
    profile = load_profile()
    try:
        top = git("rev-parse", "--show-toplevel").strip()
        repo = args.repo or re.sub(r"\.git$", "", git("remote", "get-url", "origin").strip()).replace(":", "/")
        pattern = profile.resolve(repo, ROOT)["ticket"]["pattern"]
        key = re.compile(pattern if pattern != "not yet recorded" else r"\b[A-Z][A-Z0-9]+-\d+\b")
        marks = scan(added(top, args.base, args.head), key)
    except (RuntimeError, OSError, profile.ProfileError) as e:
        print(f"comment_scan.py: {e}", file=sys.stderr)
        return 1
    if marks:
        print("\n".join(marks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
