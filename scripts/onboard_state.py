#!/usr/bin/env python3
"""Print, as `key: value` lines, what onboarding's first step needs to know about a checkout, so
one command answers what would otherwise take several. Read-only: it runs git and reads files,
and never a standard, and writes nothing.

    top: <this working tree's top level>
    clone directory: <where the standard's clone goes>/.review/onboard/clone
    clone directory note: none | <why it is not the main working tree, or that it is outside this one>
    own standard: <its files under standards/, comma-separated> | none
    pointer: <owner/repo> | <owner/repo> (uncommitted) | none
    standard setting: <git config lasp-dev.standard> | unset
    standard setting clone: <path>, origin <owner/repo> | <path>, missing | <path>, not a git checkout | -
    clone: <owner__repo>, origin <owner/repo>, branch <name>, <n> commits its origin does not hold
    clone: <name>, not a git checkout

The clone directory is in the main working tree, the directory holding the common git directory,
when that directory is a working tree of this repository, so every working tree finds the same
clone; otherwise, as with a separate git directory, a bare repository's worktrees or a submodule,
it is in this working tree, and the note says so. From a linked working tree the note says the
main working tree is outside this one, where each file write asks unless `/add-dir` names it.
One `clone:` line is printed per directory already under the clone directory.

The pointer is the `standard:` line of `standards/profile.yaml` as the working tree holds it, marked
`(uncommitted)` when `HEAD`'s file names another standard or none. A directory under the clone
directory that git does not read as a checkout of its own, such as one with a broken `.git`, is a
`clone: <name>, not a git checkout` line, and a count git cannot make is said to be unknown, never 0. Exit 1, naming the cause on stderr,
outside a git checkout. Stdlib only, Python 3.9.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

POINTER = re.compile(r"""^standard:\s+['"]?([\w.-]+/[\w.-]+)""", re.M)
OWN = ("standards/review-rules.md", "standards/decisions.md", "standards/agent-guidance.md", "standards/data-conventions.md",
       "standards/profile.yaml")


def git(where: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


def owner_repo(url: str) -> str:
    m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def clone_home(top: Path) -> tuple[Path, str]:
    """Where `.review/onboard/clone` goes, and the note to say about it."""
    common = git(top, "rev-parse", "--path-format=absolute", "--git-common-dir")
    parent = Path(common).parent if common else None
    if parent and git(parent, "rev-parse", "--show-toplevel") == str(parent) \
            and git(parent, "rev-parse", "--path-format=absolute", "--git-common-dir") == common:
        if parent.resolve() == top.resolve():
            return parent, "none"
        return parent, (f"the main working tree, {parent}, is outside this one: each write there asks "
                        f"unless `/add-dir {parent}` adds it")
    return top, "this working tree has a clone of its own: the repository has no main working tree to share one"


def pointer(top: Path) -> str:
    path = top / "standards/profile.yaml"
    m = POINTER.search(path.read_text()) if path.is_file() else None
    if not m:
        return "none"
    committed = subprocess.run(["git", "-C", str(top), "show", "HEAD:standards/profile.yaml"],
                               capture_output=True, text=True)
    held = POINTER.search(committed.stdout) if committed.returncode == 0 else None
    return m.group(1) if held and held.group(1) == m.group(1) else f"{m.group(1)} (uncommitted)"


def is_checkout(path: Path) -> bool:
    """Whether git reads `path` as a checkout's top level, not a broken one or a directory inside
    another checkout."""
    top = git(path, "rev-parse", "--show-toplevel")
    return bool(top) and Path(top).resolve() == path.resolve()


def clone_line(clone: Path) -> str:
    if not is_checkout(clone):
        return f"{clone.name}, not a git checkout"
    origin = owner_repo(git(clone, "remote", "get-url", "origin")) or "none"
    branch = git(clone, "branch", "--show-current") or "detached"
    ahead = git(clone, "rev-list", "--count", "--branches", "--not", "--remotes") or "an unknown number of"
    return f"{clone.name}, origin {origin}, branch {branch}, {ahead} commits its origin does not hold"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, default=Path.cwd(), help="a directory inside the checkout")
    args = p.parse_args(argv)
    top_s = git(args.repo, "rev-parse", "--show-toplevel")
    if not top_s:
        print(f"onboard_state.py: {args.repo} is not inside a git checkout", file=sys.stderr)
        return 1
    top = Path(top_s)
    home, note = clone_home(top)
    clones = home / ".review/onboard/clone"
    own = [f for f in OWN if (top / f).is_file()]
    point = pointer(top)
    if point != "none":
        own = [f for f in own if f != "standards/profile.yaml"]
    setting = git(top, "config", "lasp-dev.standard") or "unset"
    if setting in ("unset", "none"):
        setting_clone = "-"
    else:
        path = Path(setting)
        setting_clone = (f"{setting}, origin {owner_repo(git(path, 'remote', 'get-url', 'origin')) or 'none'}"
                         if is_checkout(path) else f"{setting}, {'not a git checkout' if path.is_dir() else 'missing'}")
    lines = [f"top: {top}", f"clone directory: {clones}", f"clone directory note: {note}",
             f"own standard: {', '.join(own) or 'none'}", f"pointer: {point}",
             f"standard setting: {setting}", f"standard setting clone: {setting_clone}"]
    if clones.is_dir():
        lines += [f"clone: {clone_line(c)}" for c in sorted(clones.iterdir()) if c.is_dir()]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
