#!/usr/bin/env python3
"""List what a repository's standard applies to it, for a person to read, from the assembled standard.

Reads the file `standard_file.sh` prints (the path given, or stdin), whose sections each open with
a `# <path>` heading naming the file they came from, and prints one block per kind:

    Standard: <owner>/<repo>@<sha>          with --source, the line .review/standard/source holds
    Review contract: <path>
    Rules, from <path>:
      R-NNN · <title> · <status> · <tier>[ · repos: <names>]
    Decisions, from <path>:
      D-NNN · <title> · <status>[ · repos: <names>]
    Terminology, from <path>: <n> term(s)
      T-NNN · <code name>[: <also called>]
    Context, from <dir>: <n> entr(y|ies)    per --context, a standard's context/ directory
      <file> · <title>

A rule is read as `ratchet_counts.py`'s parse_entries reads a ledger, its tier `-` when it has
none; a rule with no status line stops the listing. A decision's status is the one `rule_lint.py`
compares a rule's against; without one, `retired` for a heading opening `retired <date>`,
`moved` for one opening ``Moved to `<id>` ``, and otherwise `no status line`. `repos:` is a block's first such line, as `standard_file.sh` reads it,
which has already left out the blocks tagged for other repositories. Lines inside a code fence are
not read, and each section starts outside one. A section with no entries prints its heading line
and `  none`. A term's line carries its table row's third column, the names it is also called,
after a colon, and leaves it out when that cell is empty or a dash. A context entry's title is its file's first `# ` heading, its file name otherwise;
README.md is not an entry, and a directory that does not exist prints `Context: no <dir>`.

A source line ending `@none` is a standard the person chose not to read, with `git config
lasp-dev.standard none`: it prints `Standard: <owner>/<repo>, not read` and the command that
reads it again. With neither rules nor decisions otherwise, the last line is `No standard: no
rules or decisions apply here.`

Input with no `# <path>` section heading is not an assembled standard; it, a rule with no status
line, or a file that cannot be read prints the reason on stderr and exits 2. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

SECTION = re.compile(r"^# (.+/(review-contract|review-rules|decisions|terminology)\.md)\s*$")
DECISION = re.compile(r"^### (D-\d+)\b[ \t]*(?:·[ \t]*)?(.*?)\s*$")
TERM = re.compile(r"^\|\s*(T-\d+)\s*\|\s*(.*?)\s*\|(?:\s*(.*?)\s*\|)?")
REPOS = re.compile(r"^repos:\s*\[(.*)\]\s*$")
FENCE = re.compile(r"^(`{3,}|~{3,})")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ratchet_counts = _load("ratchet_counts")
rule_lint = _load("rule_lint")


def sections(text: str) -> list[tuple[str, str, str]]:
    """Split the assembled standard into (kind, path, text). A `# <path>` heading opens a section
    wherever it falls, so a fence a file leaves open ends with its section."""
    out: list[tuple[str, str, list[str]]] = []
    for line in text.splitlines():
        line = line.rstrip("\r")
        s = SECTION.match(line)
        if s:
            out.append((s.group(2), s.group(1), []))
        elif out:
            out[-1][2].append(line)
    return [(kind, path, ratchet_counts.unfenced("\n".join(lines) + "\n")) for kind, path, lines in out]


def names(line: str) -> str:
    return ", ".join(n.strip(" '\"") for n in line.strip().strip("[]").split(","))


def rule_lines(text: str, path: str) -> list[str]:
    out = []
    for rid, e in ratchet_counts.parse_entries(text, path).items():
        out.append(f"  {rid} · {e['title']} · {e['status']} · {e['tier']}" + (f" · repos: {names(e['repos'])}" if "repos" in e else ""))
    return out


def decision_lines(text: str) -> list[str]:
    statuses = rule_lint.statuses_in(text)
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = DECISION.match(line)
        if not m:
            continue
        did, title = m.groups()
        status = statuses.get(did)
        if status is None:
            heading = re.match(r"(retired) \d|(moved) to `", title, re.I)
            status = next(g for g in heading.groups() if g).lower() if heading else "no status line"
        repos = ""
        for x in lines[i + 1 :]:
            if re.match(r"^#{1,3} ", x):
                break
            r = REPOS.match(x)
            if r:
                repos = names(r.group(1))
                break
        out.append(f"  {did} · {title} · {status}" + (f" · repos: {repos}" if repos else ""))
    return out


def context_lines(directory: Path) -> list[str]:
    if not directory.is_dir():
        return [f"Context: no {directory}"]
    rows = []
    for f in sorted(directory.glob("*.md")):
        if f.name == "README.md":
            continue
        title = next((x[2:].strip() for x in f.read_text(encoding="utf-8").splitlines() if x.startswith("# ")), f.stem)
        rows.append(f"  {f.name} · {title}")
    return [f"Context, from {directory}: {len(rows)} entr{'y' if len(rows) == 1 else 'ies'}"] + (rows or ["  none"])


def render(text: str, source: str = "", contexts: list[Path] | None = None) -> str:
    parts = sections(text)
    if not parts:
        raise ValueError("no `# <path>` section heading: not the file standard_file.sh prints")
    out: list[str] = []
    unread = source.endswith("@none")
    if unread:
        out.append(f"Standard: {source[: -len('@none')]}, not read: `git config lasp-dev.standard none` is set; "
                   "`git config --unset lasp-dev.standard` reads it again")
    elif source:
        out.append(f"Standard: {source}")
    found = False
    for kind, path, body in parts:
        if kind == "review-contract":
            out.append(f"Review contract: {path}")
        elif kind == "review-rules":
            found = True
            out.append(f"Rules, from {path}:")
            out.extend(rule_lines(body, path) or ["  none"])
        elif kind == "decisions":
            found = True
            out.append(f"Decisions, from {path}:")
            out.extend(decision_lines(body) or ["  none"])
        else:
            terms = [m for m in (TERM.match(x) for x in body.splitlines()) if m]
            out.append(f"Terminology, from {path}: {len(terms)} term{'' if len(terms) == 1 else 's'}")
            out.extend(f"  {m.group(1)} · {m.group(2)}" + (f": {m.group(3)}" if m.group(3) not in (None, "", "—", "-") else "")
                       for m in terms)
    for directory in contexts or []:
        out.extend(context_lines(directory))
    if not found and not unread:
        out.append("No standard: no rules or decisions apply here.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("standard", nargs="?", help="the assembled standard; stdin when left out")
    ap.add_argument("--source", help="the file holding the standard's source line, .review/standard/source")
    ap.add_argument("--context", action="append", default=[], help="a standard's context/ directory; repeatable")
    args = ap.parse_args(argv)
    try:
        text = Path(args.standard).read_text(encoding="utf-8") if args.standard else sys.stdin.read()
        source = ""
        if args.source and Path(args.source).is_file():
            source = Path(args.source).read_text(encoding="utf-8").strip()
        sys.stdout.write(render(text, source, [Path(c) for c in args.context]))
    except (OSError, ValueError) as e:
        print(f"standard_index.py: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
