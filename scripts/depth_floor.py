#!/usr/bin/env python3
"""Print the lowest review depth a change may take: light, standard or deep.

Run anywhere in the repository, with the base the change is diffed against. The changed paths,
relative to the repository's top level, are the tracked files that differ from the base's merge
base with HEAD, working tree included, renames counted at both paths, and the untracked files git
does not ignore; a reason that names an untracked path asks whether it is part of the change,
since an unrelated note in the tree decides the floor as much as the change does. With `--paths`,
the paths given instead, relative to the top level, such as the files a brief or a plan names
before anything is written; the base is not read, and an entry with
a hunk pattern matches by its glob alone, provisionally, which the reason says: the run over the
diff after the build checks its lines.

- deep: any changed path matches a glob in the profile's `depth.deep`, or the plan file given with
  `--signatures` lists, under its `### Signatures` heading, a public signature as altered or
  removed (a line `` `<signature>` · altered · public `` or `· removed · public`). A `behavior`
  line, the same signature doing something different, does not.
- light: every changed path matches an entry of the profile's `depth.light`, and for an entry with
  a `hunk` pattern the path is tracked and has changed lines, and every one of them, added or
  removed, matches it. An untracked file, a mode change or a binary file has no changed lines, so
  it never matches an entry with a hunk pattern. The diff is git's own, with no color, external
  diff driver or textconv filter, whatever the configuration.
- standard: anything else, a change with no changed path included. A profile that leaves out
  `depth.light`, or a repository with none, takes the allowlist in the default profile, the
  changelog, the README and docs/; one whose `depth` reads `not yet recorded` has an empty
  allowlist, so nothing is light.

Prints `depth: <level>` and `reason: <the path, hunk or rule that decided it>`, the allowlist
named as the default one when the profile does not set it, and for light
`brief: <the focused-reviewer briefs the entries name>`. A person may raise the depth, and lower
a standard floor to light at `implement-change`'s plan gate; deep is never lowered. Exits 1 with
the reason when git or the profile fails, and when the plan given with `--signatures` has no
`### Signatures` section, or a line in it that is not `none`, a `Note:` line that holds no
signature line, or the template's
`` `<signature>` · added|altered|removed|behavior · public|private ``, the signature in single or
doubled backticks. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# git's own diff output whatever the configuration: no color, external driver, textconv filter,
# renames or path relative to a subdirectory.
DIFF = ("diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames", "--no-relative")
SIGNATURE = re.compile(r"(?:[-*]\s+)?(`+)(?!`).+?\1\s*·\s*(added|altered|removed|behavior)\s*·\s*(public|private)\b")
NONE = re.compile(r"(?:[-*]\s+)?none\b", re.I)
NOTE = re.compile(r"(?:[-*]\s+)?note:", re.I)
SHAPE = "`none`, `Note: <text>`, or `` `<signature>` · added|altered|removed|behavior · public|private ``"


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


def glob_regex(glob: str) -> re.Pattern:
    """A path glob as a regex: `**/` any directories, `**` anything, `*` and `?` within a part."""
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out + r"\Z")


def changed_lines(top: str, base: str, path: str) -> list[str]:
    """The added and removed lines of one tracked path against the base: the lines inside its hunks,
    so a header line is never read as one, whatever it starts with."""
    out, in_hunk = [], False
    for line in git("-C", top, "--literal-pathspecs", *DIFF, "-U0", base, "--", path).splitlines():
        if line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line[:1] in ("+", "-"):
            out.append(line[1:])
    return out


def altered_public(plan: Path) -> str | None:
    """The first line under the plan's `### Signatures` that marks a public signature altered or
    removed. Raises RuntimeError when the section is absent or empty, or a line in it is neither
    `none`, a `Note:` line nor in the template's shape."""
    m = re.search(r"^### Signatures[ \t]*$(.*?)(?=^#{1,3} |\Z)", plan.read_text(), re.M | re.S)
    if not m:
        raise RuntimeError(f"{plan} has no ### Signatures section")
    lines = [line.strip() for line in m.group(1).splitlines() if line.strip()]
    for line in lines:
        if NOTE.match(line) and SIGNATURE.search(line):
            raise RuntimeError(f"{plan}'s ### Signatures has a signature line inside a note: {line!r}; each line is {SHAPE}")
    lines = [line for line in lines if not NOTE.match(line)]
    if not lines:
        raise RuntimeError(f"{plan}'s ### Signatures section is empty")
    if len(lines) == 1 and NONE.match(lines[0]):
        return None
    for line in lines:
        if not SIGNATURE.match(line):
            raise RuntimeError(f"{plan}'s ### Signatures has a line not in the template's shape: {line!r}; each line is {SHAPE}")
    for line in lines:
        sig = SIGNATURE.match(line)
        if sig.group(2) in ("altered", "removed") and sig.group(3) == "public":
            return line.strip(" -*")
    return None


def floor(
    base: str, depth: dict, plan: Path | None, given: list[str] | None = None, allowlist: str = "the light allowlist"
) -> tuple[str, str, list[str]]:
    if given is None:
        top = git("rev-parse", "--show-toplevel").strip()
        # Against the merge base, so a base that moved on adds none of its own changes; with no
        # renames, so a moved file counts at its old path and its new one. NUL-separated and from
        # the top level, so a path is never quoted or relative to a subdirectory.
        base = git("merge-base", base, "HEAD").strip()
        tracked = [p for p in git("-C", top, *DIFF, "--name-only", "-z", base).split("\0") if p]
        untracked = [p for p in git("-C", top, "ls-files", "-z", "--others", "--exclude-standard").split("\0") if p]
        paths = sorted(set(tracked) | set(untracked))
    else:
        top, tracked, untracked, paths = "", [], [], sorted(set(given))
    deep = [] if depth["deep"] == "not yet recorded" else depth["deep"]
    light = [] if depth["light"] == "not yet recorded" else depth["light"]
    altered = altered_public(plan) if plan is not None else None

    def named(path: str) -> str:
        return f"{path} (untracked: part of the change?)" if path in untracked else path

    for path in paths:
        for glob in deep:
            if glob_regex(glob).match(path):
                return "deep", f"{named(path)} matches the deep glob {glob}", []
    if altered:
        return "deep", f"the plan alters a public signature: {altered}", []
    if not paths:
        return "standard", "no change against the base", []
    briefs, provisional = [], []

    def lines_match(entry: dict, path: str) -> bool:
        if given is not None:
            provisional.append(path)
            return True
        lines = changed_lines(top, base, path) if path in tracked else []
        return bool(lines) and all(re.search(entry["hunk"], line) for line in lines)

    for path in paths:
        entry = next(
            (e for e in light if glob_regex(e["glob"]).match(path) and ("hunk" not in e or lines_match(e, path))),
            None,
        )
        if entry is None:
            return "standard", f"{named(path)} is not on {allowlist}", []
        briefs.append(entry["brief"])
    reason = f"every changed path is on {allowlist}"
    if provisional:
        reason += f"; provisionally for {', '.join(provisional)}, whose hunk pattern the run over the diff checks"
    return "light", reason, sorted(set(briefs))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("base", help="the commit or branch the change is diffed against")
    p.add_argument("--signatures", type=Path, help="the plan file, whose ### Signatures section is read")
    p.add_argument("--repo", help="owner/repo; by default the origin remote's")
    p.add_argument("--paths", nargs="+", help="judge these paths instead of the diff")
    args = p.parse_args(argv)
    profile = load_profile()
    try:
        repo = args.repo or re.sub(r"\.git$", "", git("remote", "get-url", "origin").strip()).replace(":", "/")
        depth = profile.resolve(repo, ROOT)["depth"]
        if depth == "not yet recorded":
            depth = {"light": [], "deep": []}
        default = depth["light"] == profile.parse((ROOT / profile.DEFAULT_PROFILE).read_text(), profile.DEFAULT_PROFILE)["depth"]["light"]
        allowlist = "the default light allowlist" if default else "the light allowlist"
        level, reason, briefs = floor(args.base, depth, args.signatures, args.paths, allowlist)
    except (RuntimeError, OSError, profile.ProfileError) as e:
        print(f"depth_floor.py: {e}", file=sys.stderr)
        return 1
    print(f"depth: {level}\nreason: {reason}")
    if briefs:
        print(f"brief: {', '.join(briefs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
