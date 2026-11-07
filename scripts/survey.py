#!/usr/bin/env python3
r"""Survey one repository checkout for the facts the plugin reads, and where the repository keeps them.

Run from anywhere inside the checkout. It reads only committed files, those of `--ref` (default
`HEAD`), so a file the checkout holds but git does not track is never read: a candidate one, such as
a local `CLAUDE.md`, ignored or not, is only named, on the `not committed` row. For each fact family
the repository's own files can carry, in a fixed order, it prints where the fact was found (a path,
`history` for the branch names and commit subjects, `git` for the remote and the default branch, or
`none`), a short value, and, for a family a profile key also holds, that key's value as `profile.py`
resolves it today and where from (the file of the repository's standard that sets it, or the
default profile), with whether the two agree. A file's content is never printed beyond the value: a heading's title, a
count, a command line, a path.

The table, after one line `survey: <owner/repo> · <N> families · <M> from the repository` (the
`(also)`, `not committed` and `symlinks not followed` rows are no families and are not counted):

    family | found in | value | plugin today | match

`match` compares the row's value with the key's, and is one of:
- `same`: the repository's value and the key's agree. Commands are compared as shell words, after
  the runner in front (`poetry run`, `uv run` and its options, a value they take included,
  `python -m`, `coverage run -m` and the like) is removed, so whitespace and quoting do not count;
  the options and arguments after `pytest`, each option with the value it takes, compare as a
  set, so their order does not count either, nor a path argument's trailing `/`. A ticket key agrees when the key's pattern is the one
  the history implies, `<KEY>-\d+` as a string, or else when it finds, as `where.sh` matches a
  branch, every branch that carries the key; either way the value keeps the branch counts, so a
  branch the pattern misses still shows.
- `differs`: they disagree, and both values are in the row.
- `inferred`: the repository holds what implies the key's value but not the value itself: a
  `.pre-commit-config.yaml` implies a `pre-commit run` lint command. With no such file, the lint
  gate is the first linter command (`ruff check`, `flake8`, `pylint`, or `black`, `isort` or `ruff
  format` with `--check`) the test command's sources give, compared as a command.
- `repository only`: the repository holds it and the key reads `not yet recorded` or is empty.
- `plugin only`: the key has a value and the repository holds none.
- `-`: a family no key holds.

When the repository's own sources give a family different commands, every row of that family, its
`(also)` rows included, reads `conflict; <match>`: the repository names no one value, each row's
`match` still compares that source with the key, and none is taken over the others.

The test and coverage commands are `pytest` commands, read from five kinds of source in this
order: the agent instruction files (`AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`,
`.github/copilot-instructions.md`, then `.github/instructions/*.instructions.md`), the testing doc,
a developer doc's testing sections (`developers.md` and the like under `doc/` or `docs/`, a `#`
line inside fenced code being no heading), the `commands =` of `tox.ini`'s `[testenv]` sections,
each labeled by its section and `{posargs:<default>}` read as its default, then CI: the GitHub
workflows' `run:` steps, each starting in its `working-directory:` or its job's or workflow's
`defaults: run: working-directory:` (none for a GitHub expression), and the
`script:`, `before_script:`, `after_script:` and `commands:` items of `.gitlab-ci.yml` and a
CodeBuild `buildspec.yml` (a plain item without its `# comment`, a quoted one unescaped; no other
key's items, such as `stages:` or `needs:`). In a document, a command is a line of a fenced code
block, labeled by its trailing `# comment`, else a comment line just above it, else the line before
the block, or an inline code span that ends its line after a label ending in a colon
(`**Run unit tests**: ...`), labeled by it; a shell prompt `$ ` and the comment are dropped. Every
command is split at `&&`, `;` and `||` outside quotes, with a `cd` before one kept with it, and a
`\` left dangling at its end dropped, and one run through `xvfb-run` or a shell's `-c`
(`bash -lc '<script>'`) is read as the commands it runs; one that names a single test (`::`), a placeholder (`<...>`)
or `--version`, `--help` or `--collect-only` is no candidate. A command with `--cov` or run by
`coverage run` is a coverage command, any other a test command. Within one source a command is
passed over, while another candidate remains, when its label, its file's name or a test path
argument says integration, end-to-end, benchmark, performance, slow or extra, unless it deselects
such a suite itself (`-m "not integration"`); then one whose label says unit, or that deselects
such a suite, comes first, then the first in order. Each family's row is the first source in that
order to give a command; every later source that gives one adds a `test command (also)` or
`coverage command (also)` row, so each source considered shows. A committed symlink is read as the
file it points to in the same commit, following at most 8 links; one that cannot be followed there
(it points out of the commit, to nothing in it, to a directory, into a loop or past 8 links) counts
as not held and is listed, with its own target, on the `symlinks not followed` row, never read. A
CI job's or CodeBuild phase's items run in one shell, so a `cd` item stays in front of the commands
after it. The pull request template and issue templates are also
read from `.gitlab/merge_request_templates/` and `.gitlab/issue_templates/`. The commit style,
branch naming and merge strategy rows read the contributing guide's section titles, and, for one it
does not cover, a developer git doc (`git.md`, `git-workflow.md`, `branching.md` and the like under
`doc/` or `docs/`). A ticket key is taken only where convention puts one: in a branch name, where
`where.sh` reads it, or opening a commit subject of `--ref`'s history, a number followed by
`-<nn>-<nn>` being a date and no key; it names the project when seen with two numbers or more, or in a
branch name, and with at least twice as many numbers as any other key so seen; `GH-<n>` is GitHub's
form and names no project. The `issue key` row reads GitHub issue keys in the same places: a branch
name's `issue-<n>`, `GH-<n>` or `<n>` before `-<word>`, `_` or the name's end, each form with its count,
and a subject opening with `#<n>` or `GH-<n>`, then the ticket pattern the branch forms imply,
`(issue-)?\d+` (`where.sh`'s default for a GitHub tracker) for `issue-<n>` and `<n>-words`,
`GH-\d+` for `GH-<n>` alone, `mixed` for `GH-<n>` beside another form, or `none` with no branch
form; no key holds it, since a GitHub tracker's pattern is only ever the standard's. With `--json`, the same rows as a JSON list of
objects with the keys `family`, `found_in`, `value`, `key`, `plugin_today`, `plugin_source`,
`match` and `conflict` (true on every row of a family whose sources disagree), each value whole,
where the table cuts one past 60 characters.

With `--profile <path>`, it also writes the candidate profile there: every key of `profile.py`'s
schema, in its format and checked against it, those the survey cannot fill reading
`not yet recorded`, a command family whose sources disagree included, and each command as the
repository writes it. `--public true` or `--public false`, what the code host says, fills
`public`. The candidate is not a drop-in profile, since a key reading `not yet recorded` overrides
the default profile's value; `--drop-in <path>` writes the same values with every unfilled key left
out, so the standard's or the default profile's values stand for them, and the proposals too,
`downstream`, `depth.light` and `depth.deep`, unless `--answers`, in the scorer's form, gives the value the person confirmed or
typed; a value the person typed for any other key, such as the test command they pick where the
repository's own files disagree, goes in too. Beside the candidate, `<stem>.sources.json` says where each value
came from, whether the key's sources disagree, and every repository source of the key with its
value. Besides the families above, the candidate works out by stated rules, each value's source
ending ` (inferred)`: `lint.regex` and `gates.tests`, the gate pattern of the lint command and of
the program every test and coverage command runs (`pre-commit[[:space:]]+run`, `pytest`), a chain
counted by the one program among its commands that runs tests or linters itself, when all agree and each starts with a plain program name; `types.regex` from the type checkers the
pre-commit file or `pyproject.toml` configures; and, from the tree (`git (inferred)`), proposals for a person to trim:
`depth.light`, the changelog and README at the top, the documents under `doc/` or `docs/` and the
version line of `pyproject.toml`, and `depth.deep`, each outermost `data/` directory and each
directory or code file named for a definition, a manifest, a calibration, a schema, geolocation or
a kernel, outside test, doc and example directories and no `test_` or `mock_` file, in its
directory or, when such files sit in two directories or more, anywhere. With `--downstream-from`,
`downstream` proposes the repositories that use the package, never the repository itself by name:
from the onboarding skill's code search, a JSON list of `{"repo", "evidence"}` (`GitHub (search)`),
or from a directory of checkouts, each searched at its `origin/HEAD` for a Python file importing
a name the `import names` row gives or a dependency file naming the package (`clones (search)`);
that row, from the package's layout (`import_names`), reading `conflict` searches no checkout. For each file named, how a fact from it reaches the model and its size in characters; and
the files every session loads at its start, with their total: `CLAUDE.md`, `.claude/CLAUDE.md`,
each `.claude/rules/*.md` with no `paths:` in its frontmatter, and what any of them imports with
`@path`, a scoped rule's imports included, five hops deep (`docs/contracts.md`, "The survey"). A
fact from one of those is `always` loaded; from the history, the code host, `pyproject.toml`, the
pre-commit file, CODEOWNERS, CI or a pull request template, a script resolves it and hands over
only the value (`script`); from any other file, a skill reads it when it needs it (`on demand`).

`--standard none` reads the checkout as `git config lasp-dev.standard none` would, for every
git the survey runs: a pointer whose standard does not cover the repository yet is not followed,
and the survey compares with the default profile.

Exit 1, naming the cause on stderr, outside a git checkout, with `--standard` when
`GIT_CONFIG_COUNT` is set to no count, for a `--ref` that names no commit, or
when the repository's standard or the default profile is refused (`profile.py`'s errors). Stdlib only,
Python 3.9.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path

# This directory's profile.py, loaded by path: `import profile` would find the standard library's.
_spec = importlib.util.spec_from_file_location("profile", Path(__file__).with_name("profile.py"))
plugin_profile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin_profile)

HEADER = "family | found in | value | plugin today | match"
WIDTH = 60
PR_TEMPLATES = (".github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE.md", "pull_request_template.md",
                "PULL_REQUEST_TEMPLATE.md", "docs/pull_request_template.md", "docs/PULL_REQUEST_TEMPLATE.md")
# GitHub's order: the first file it finds wins.
CODEOWNERS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
CONTRIBUTING = tuple(f"{d}CONTRIBUTING{x}" for d in ("", ".github/", "docs/", "doc/") for x in (".md", ".rst", ".txt", ""))
INSTRUCTIONS = ("AGENTS.md", "CLAUDE.md", ".claude/CLAUDE.md", ".github/copilot-instructions.md")
DECISIONS = ("docs/adr", "doc/adr", "docs/decisions", "doc/decisions", "adr", "decisions")
SECRET_HOOKS = ("gitleaks", "detect-secrets", "trufflehog", "detect-private-key", "detect-aws-credentials")
# Where convention puts a ticket key: a branch name's start, after one optional `<word>/` as in
# `where.sh`, and a commit subject's start; a number followed by `-<nn>-<nn>` is a date, not a key
# (`onboard/WISER-2026-10-29`).
BRANCH_KEY = re.compile(r"^(?:[A-Za-z]+/)?([A-Z][A-Z0-9]+)-(\d+)(?!\d|-\d\d-\d\d)")
SUBJECT_KEY = re.compile(r"^\[?([A-Z][A-Z0-9]+)-(\d+)\b(?!-\d\d-\d\d)")
# A GitHub issue's number in the same places: a branch name's start, after the same optional
# `<word>/`, as `issue-<n>`, `GH-<n>` or `<n>`, each before `-<word>`, `_` or the name's end, so a date
# such as `2026-10-29-notes` is no key; a subject's start as `#<n>` or `GH-<n>`, with the date
# guard above. `GH` is GitHub's form, never a Jira project.
ISSUE_BRANCH = re.compile(r"^(?:[A-Za-z]+/)?(issue-|GH-)?(\d+)(?=-[A-Za-z]|_|$)", re.I)
ISSUE_SUBJECT = re.compile(r"^\[?(#|GH-)(\d+)\b(?!-\d\d-\d\d)", re.I)
ISSUE_FORMS = {"": "<n>-words", "issue-": "issue-<n>", "gh-": "GH-<n>"}
HEADINGS = {"commit style": r"(?<![\w-])commit(s|ting)?\b(?!-)",
            "branch naming": r"\bbranch(es|ing)?\b",
            "merge strategy": r"\b(merg(e|es|ed|ing)|rebas(e|es|ed|ing)|squash(es|ed|ing)?)\b"}
RUNNERS = ("poetry", "uv", "pipenv", "hatch", "pdm", "rye")
# Runner options that take their value as the next word.
RUNNER_VALUES = {"--python", "-p", "--with", "--with-requirements", "--extra", "--group", "--only-group",
                 "--directory", "--project", "--package", "--env-file", "--index", "--env", "-e"}
# pytest options whose value is the next word, so not a test path.
PYTEST_VALUES = {"-k", "-m", "-p", "-c", "-o", "-n", "--ignore", "--ignore-glob", "--deselect", "--rootdir",
                 "--confcutdir", "--basetemp", "--cov", "--cov-report", "--cov-config", "--junitxml",
                 "--durations", "--maxfail", "--log-file", "--override-ini"}
WORD = re.compile(r"""\s*((?:[^\s'"\\]|\\.|'[^']*'|"(?:\\.|[^"\\])*")+)""")
SIDE_SUITES = re.compile(r"(?i)integration|e2e|end.to.end|benchmark|perf")
SIDE_LABELS = re.compile(r"(?i)integration|e2e|end.to.end|benchmark|perf|\bslow\b|\bextra\b")
DESELECTS = re.compile(r"(?i)\bnot\s+(integration|e2e|slow|extra|benchmark)")
PYTEST = re.compile(r"(cd \S+ && )?pytest(?![\w.-])")
TEST_DOC = re.compile(r"(?i)test(ing|s)?\.md")
DEV_DOC = re.compile(r"(?i)(develop|developer|developers|developing|development|dev[-_]?guide|developer[-_]guide)\.md")
CI_FILES = re.compile(r"(^|/)buildspec[\w.-]*\.ya?ml$|^\.gitlab-ci\.ya?ml$")
GIT_DOC = re.compile(r"(?i)(git|git[-_](workflow|usage)|branching|version[-_]control)\.(md|rst)")


def git(top: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


def clean(text: str) -> str:
    """A value on one line, a `|` written `/` so the table keeps its columns."""
    return " ".join(text.split()).replace("|", "/")


def short(text: str) -> str:
    text = clean(text)
    return text if len(text) <= WIDTH else text[: WIDTH - 1] + "…"


class Tree:
    """The files of one commit: names from `git ls-tree`, text from `git show`, so a file the
    checkout holds but has not committed is never read, and names match exactly as committed. A
    symlink is read as the file it points to within the same commit, following at most 8 links. One
    that cannot be followed there, because it points out of the commit, to nothing in it, to a
    directory, into a loop or past 8 links, counts as not held and is listed in `unfollowed` with its
    own target."""

    def __init__(self, top: Path, ref: str):
        self.top, self.ref = top, ref
        out = subprocess.run(["git", "-C", str(top), "ls-tree", "-r", "-z", ref], capture_output=True)
        if out.returncode:
            raise OSError(f"{ref} names no commit in {top}")
        self.modes: dict[str, str] = {}
        for entry in out.stdout.decode(errors="replace").split("\0"):
            meta, _, name = entry.partition("\t")
            if name:
                self.modes[name] = meta.split(" ", 1)[0]
        self.names = sorted(self.modes)
        self.held = set(self.names)
        self.unfollowed: dict[str, str] = {}
        self.resolved: dict[str, str | None] = {}

    def has(self, path: str) -> bool:
        """Whether the commit holds `path` as a file that can be read."""
        return path in self.held and self.resolve(path) is not None

    def first(self, paths) -> str | None:
        return next((p for p in paths if self.has(p)), None)

    def under(self, directory: str) -> list[str]:
        prefix = directory.rstrip("/") + "/"
        return [n for n in self.names if n.startswith(prefix) and self.has(n)]

    def resolve(self, path: str) -> str | None:
        """The committed file `path` reads as: itself, or a symlink's target in the commit; None for
        a symlink that cannot be followed there."""
        if path not in self.resolved:
            seen, current = [path], path
            while self.modes.get(current) == "120000" and current is not None:
                target = self.show(current).decode(errors="replace")
                nxt = posixpath.normpath(posixpath.join(posixpath.dirname(current), target))
                if (nxt.startswith("../") or nxt.startswith("/") or nxt not in self.held or nxt in seen
                        or len(seen) > 8):
                    self.unfollowed[path] = self.show(path).decode(errors="replace")
                    current = None
                    break
                seen.append(nxt)
                current = nxt
            self.resolved[path] = current
        return self.resolved[path]

    def show(self, path: str) -> bytes:
        out = subprocess.run(["git", "-C", str(self.top), "show", f"{self.ref}:{path}"], capture_output=True)
        if out.returncode:
            raise OSError(f"cannot read {path} at {self.ref}")
        return out.stdout

    def read_bytes(self, path: str) -> bytes:
        current = self.resolve(path)
        return self.show(current) if current is not None else b""

    def read(self, path: str) -> str:
        return self.read_bytes(path).decode(errors="replace")


def uncommitted(top: Path) -> list[str]:
    """The files under the names the survey reads that the checkout holds and git does not track,
    ignored ones included: reported, never read."""
    specs = [*PR_TEMPLATES, *CODEOWNERS, *CONTRIBUTING, *INSTRUCTIONS, ".pre-commit-config.yaml",
             "pyproject.toml", "tox.ini", "CHANGELOG.md", "TESTING.md", ".gitlab-ci.yml", ".github/", ".gitlab/",
             ":(glob)**/buildspec*.y*ml", ":(glob)doc/**/*.md", ":(glob)docs/**/*.md",
             ":(glob)doc/**/*.rst", ":(glob)docs/**/*.rst"]
    return sorted(git(top, "ls-files", "--others", "--", *specs).splitlines())


def owner_repo(url: str) -> str:
    m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def default_directories(lines: list[str]) -> list[str | None]:
    """Each line's directory from `defaults: run: working-directory:`, the workflow's or, wherever it
    is written, overridden by the job's: a job's holds from the job's key to the next line as little
    indented. Comment lines bound nothing."""
    out: list[str | None] = [None] * len(lines)
    code = [bool(l.strip()) and not l.lstrip().startswith("#") for l in lines]
    blocks = []
    for i, raw in enumerate(lines):
        m = re.match(r"^(\s*)defaults:\s*$", raw)
        if not m:
            continue
        d = len(m.group(1))
        end = next((j for j in range(i + 1, len(lines)) if code[j] and indent_of(lines[j]) <= d), len(lines))
        wd = next((directory(w.group(1)) for j in range(i + 1, end)
                   for w in [re.match(r"^\s*working-directory:\s*(\S.*)$", lines[j])] if w), None)
        if wd is None:
            continue
        start = next((j for j in range(i - 1, -1, -1) if code[j] and indent_of(lines[j]) < d), -1)
        stop = len(lines) if start < 0 else next(
            (j for j in range(start + 1, len(lines)) if code[j] and indent_of(lines[j]) <= indent_of(lines[start])),
            len(lines))
        blocks.append((start >= 0, start + 1, stop, wd))
    for _, first, stop, wd in sorted(blocks, key=lambda b: b[0]):
        for j in range(first, stop):
            out[j] = wd
    return out


def directory(value: str) -> str:
    """A `working-directory:` value as a directory to `cd` into, normalized: "" for the top level and
    for one a GitHub expression names (`${{ matrix.dir }}`) or that holds a space, which the `cd` in
    front of a command could not take, so its commands are read with no `cd`."""
    value = scalar(value)
    if "${{" in value or re.search(r"\s", value):
        return ""
    value = posixpath.normpath(value)
    return "" if value == "." else value


def step_directory(lines: list[str], i: int, column: int) -> str | None:
    """The `working-directory:` of the step whose `run:` key, at `column`, is on line `i`: a key at
    that column between the step's `- ` and the line after it that is less indented."""
    def item(line: str) -> bool:
        m = re.match(r"^\s*-\s+", line)
        return bool(m) and m.end() == column

    first = next((j for j in range(i, -1, -1) if item(lines[j])), i)
    for j in range(first, len(lines)):
        if j > first and lines[j].strip() and indent_of(lines[j]) < column:
            break
        m = re.match(r"^(\s*(?:-\s+)?)working-directory:\s*(\S.*)$", lines[j])
        if m and len(m.group(1)) == column:
            return directory(m.group(2))
    return None


def run_lines(text: str) -> list[str]:
    """The shell commands of a workflow file's `run:` steps: blocks joined as the shell or YAML
    would, each step's starting in the directory its `working-directory:` names, else its job's or
    the workflow's `defaults: run: working-directory:`."""
    lines = text.splitlines()
    defaults = default_directories(lines)
    steps, block, column, folded = [], None, 0, False
    for i, raw in enumerate(lines):
        m = re.match(r"^(\s*(?:-\s+)?)run:\s*(.*)$", raw)
        if m:
            rest = m.group(2).strip()
            column = len(m.group(1))
            step = step_directory(lines, i, column)
            cd = (defaults[i] if step is None else step) or None
            if rest[:1] in ("|", ">"):
                block, folded = [], rest.startswith(">")
                steps.append((block, folded, cd))
            else:
                block = None
                if rest:
                    steps.append(([rest], False, cd))
            continue
        if block is not None:
            if raw.strip() and len(raw) - len(raw.lstrip()) <= column:
                block = None
            else:
                block.append(raw)
    out: list[str] = []
    for block_lines, folded, cd in steps:
        block_lines = fold(block_lines) if folded else [l.strip() for l in block_lines if l.strip()]
        out += shell([comment_split(line)[0] for line in continued(block_lines)], cd)
    return out


def continued(lines: list[str]) -> list[str]:
    """Shell lines with each `\\` continuation joined to the next, and a `\\` left dangling at the
    end of the last dropped."""
    joined: list[str] = []
    for line in lines:
        if joined and joined[-1].endswith("\\"):
            joined[-1] = joined[-1][:-1].rstrip() + " " + line
        else:
            joined.append(line)
    return [line[:-1].rstrip() if line.endswith("\\") else line for line in joined]


def fold(lines: list[str]) -> list[str]:
    """A folded (`>`) block's lines as YAML reads them: joined by spaces, but a blank line, and a
    line indented past the block's own, each keep a line break."""
    out, current, base = [], [], None
    for raw in lines:
        if not raw.strip():
            if current:
                out.append(" ".join(current))
                current = []
            continue
        indent = len(raw) - len(raw.lstrip())
        base = indent if base is None else base
        if indent > base:
            if current:
                out.append(" ".join(current))
                current = []
            out.append(raw.strip())
        else:
            current.append(raw.strip())
    if current:
        out.append(" ".join(current))
    return out


def commands(line: str) -> list[str]:
    """One shell line's commands, split at `&&`, `;` and `||` outside quotes, each as written, a
    `cd <dir>` kept in front of the command after it, and one run through `xvfb-run` or `bash -c`
    read as the commands it runs. A line with an unclosed quote is skipped."""
    return shell_commands(line)[0]


# xvfb-run's options that take the next word as their value.
XVFB_VALUES = {"-s", "--server-args", "-n", "--server-num", "-e", "--error-file", "-f", "--auth-file", "-p",
               "--xauth-protocol"}
SHELL_C = re.compile(r"""(?:ba|z)?sh\s+(?:-l\s+)?-l?c\s+(?:'([^']*)'|"((?:\\.|[^"\\])*)")""")


def wrapped(command: str) -> str | None:
    """What a command run through `xvfb-run` or a shell's `-c` runs: `xvfb-run -a pytest` runs
    `pytest`, and `bash -lc 'cd src && pytest'` its script; None for any other command."""
    spans = [(m.group(1), m.end()) for m in WORD.finditer(command)]
    launched = bool(spans) and spans[0][0] == "xvfb-run"
    inner = command
    if launched:
        i = 1
        while i < len(spans) and spans[i][0].startswith("-"):
            i += 2 if spans[i][0] in XVFB_VALUES else 1
        if i >= len(spans):
            return None
        inner = command[spans[i - 1][1]:].strip()
    script = SHELL_C.fullmatch(inner)
    if script:
        return script.group(1) if script.group(1) is not None else re.sub(r'\\(["\\$`])', r"\1", script.group(2))
    return inner if launched else None


def shell(lines: list[str], cd: str | None = None) -> list[str]:
    """The commands of lines one shell runs in turn, as a CI job's script or a `run:` block, starting
    in the directory `cd` names: a `cd` on one line stays in front of the commands on the lines
    after it."""
    out = []
    for line in lines:
        found, cd = shell_commands(line, cd)
        out += found
    return out


def shell_commands(line: str, cd: str | None = None) -> tuple[list[str], str | None]:
    """`commands`, starting in the directory `cd` names, and the directory the line ends in."""
    parts, start, i, quote = [], 0, 0, ""
    while i < len(line):
        c = line[i]
        if c == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            quote = "" if c == quote else quote
        elif c in "'\"":
            quote = c
        elif line.startswith(("&&", "||"), i) or c == ";":
            parts.append(line[start:i])
            i += 1 if c == ";" else 2
            start = i
            continue
        i += 1
    if quote:
        return [], cd
    parts.append(line[start:])
    out = []
    for part in (p.strip() for p in parts):
        m = re.fullmatch(r"cd\s+(\S+)", part)
        if m:
            cd = posixpath.normpath(posixpath.join(cd, m.group(1))) if cd and not m.group(1).startswith(("/", "~", "$")) \
                else m.group(1)
            cd = None if cd == "." else cd
        elif part and wrapped(part) is not None:
            out += shell_commands(wrapped(part), cd)[0]
        elif part:
            out.append(f"cd {cd} && {part}" if cd else part)
    return out, cd


def bare(command: str) -> str:
    """A command without the runners in front of it (and the values their options take), whitespace
    collapsed, after a `cd <dir> && ` in front, which is kept. A GitHub expression, `${{ ... }}`,
    counts as one word."""
    cd = re.match(r"cd \S+ && ", command)
    if cd:
        return cd.group(0) + bare(command[cd.end():])
    command = re.sub(r"\$\{\{\s*(.*?)\s*\}\}", lambda m: "${{" + re.sub(r"\s+", "", m.group(1)) + "}}",
                     " ".join(command.split()))
    while True:
        spans = [(m.group(1), m.end()) for m in WORD.finditer(command)]
        words_ = [w for w, _ in spans]
        n = 0
        if words_[:1] and words_[0] in RUNNERS and words_[1:2] == ["run"]:
            n = 2
            while n < len(words_) and words_[n].startswith("-"):
                n += 1 if "=" in words_[n] or words_[n] not in RUNNER_VALUES else 2
        elif words_[:2] in (["python", "-m"], ["python3", "-m"]):
            n = 2
        elif words_[:2] == ["coverage", "run"] and "-m" in words_[2:]:
            n = words_.index("-m", 2) + 1
        if not n or n > len(spans):
            return command
        command = command[spans[n - 1][1]:].strip()


def words(command: str) -> list[str]:
    try:
        return shlex.split(bare(command))
    except ValueError:
        return bare(command).split()


def canonical(command: str) -> tuple:
    """A command as it is compared: its shell words up to `pytest` as written, then its options,
    each with the value it takes, and its arguments, sorted, so their order does not count, except
    that an option given more than once keeps the order of its values, since the last one given is
    the one pytest uses; a path argument's trailing `/` is dropped, so `tests/` and `tests` are one
    directory."""
    ws = words(command)
    if "pytest" not in ws:
        return tuple(ws)
    i = ws.index("pytest") + 1
    groups, rest = [], ws[i:]
    while rest:
        w = rest.pop(0)
        if w.startswith("-") and "=" not in w and w in PYTEST_VALUES and rest:
            groups.append((w, rest.pop(0)))
        else:
            groups.append((w if w.startswith("-") or w == "/" else w.rstrip("/"),))
    repeated = {g[0]: [h[1:] for h in groups if h[0] == g[0]] for g in groups if len(g) == 2}
    merged = sorted({(name, *[v for vs in values for v in vs]) for name, values in repeated.items()}
                    | {g for g in groups if len(g) == 1})
    return tuple(ws[:i]) + tuple(merged)


def test_paths(command: str) -> list[str]:
    """A pytest command's path arguments: words with a `/` that are no option and no option's value."""
    ws = words(command)
    ws = ws[ws.index("pytest") + 1:] if "pytest" in ws else ws
    out, skip = [], False
    for w in ws:
        if skip:
            skip = False
        elif w.startswith("-"):
            skip = "=" not in w and w in PYTEST_VALUES
        elif "/" in w:
            out.append(w)
    return out


def comment_split(line: str) -> tuple[str, str]:
    """A shell line and its trailing comment: a `#` that starts a word outside quotes."""
    quote, i = "", 0
    while i < len(line):
        c = line[i]
        if c == "\\" and quote != "'":
            i += 2
            continue
        if quote:
            quote = "" if c == quote else quote
        elif c in "'\"":
            quote = c
        elif c == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip(), line[i + 1:].strip()
        i += 1
    return line, ""


def prose_commands(text: str) -> list[tuple[str, str]]:
    """A document's shell commands with their labels: each line of a fenced code block, labeled by
    its trailing comment, else a comment line just above it, else the line before the block, and
    each inline code span that ends its line after a label ending in a colon, as in a "Run unit
    tests:" list item, labeled by it."""
    out, block, fenced, before = [], [], False, ""
    for raw in text.splitlines():
        if re.match(r"^\s*(```|~~~)", raw):
            if fenced:
                above = ""
                for line in continued([l.strip() for l in block if l.strip()]):
                    code, note = comment_split(line[2:] if line.startswith("$ ") else line)
                    if not code:
                        above = note
                        continue
                    out += [(c, note or above or label) for c in commands(code)]
                    above = ""
                block = []
            else:
                label = before
            fenced = not fenced
            continue
        if fenced:
            block.append(raw)
            continue
        if raw.strip():
            before = raw.strip()
        for m in re.finditer(r"`([^`]+)`", raw):
            label = raw[:m.start()].rstrip(" *_")
            if label.endswith(":") and not raw[m.end():].strip(" .;,*_"):
                out += [(c, label.strip(" -*_")) for c in commands(m.group(1))]
    return out


def tox_commands(text: str) -> list[tuple[str, str]]:
    """The commands of a `tox.ini`'s `[testenv]` and `[testenv:<name>]` sections, each labeled by its
    section: each line of a `commands =` value, continued lines joined, a comment, a factor prefix
    (`py310: `) and a leading `-` dropped, `{toxinidir}/` dropped, `{envpython}` read as `python`,
    then `{posargs:<default>}` read as its default and `{posargs}` dropped."""
    out, label, held = [], "", None
    for raw in text.splitlines() + ["[end]"]:
        head = re.match(r"^\[([^\]]+)\]", raw)
        key = re.match(r"^([\w-]+)\s*=\s*(.*)$", raw)
        if held is not None and (head or key or (raw.strip() and not raw[:1].isspace())):
            for line in continued([l.strip() for l in held if l.strip() and not l.strip().startswith("#")]):
                line = comment_split(line)[0].replace("{toxinidir}/", "").replace("{envpython}", "python")
                line = re.sub(r"\{posargs:([^}]*)\}", r"\1", line).replace("{posargs}", "")
                line = re.sub(r"^(?:[\w.,{}!-]+:\s+)?-?\s*", "", line)
                out += [(c, label) for c in commands(" ".join(line.split()))]
            held = None
        if head:
            label = head.group(1) if re.fullmatch(r"testenv(:.+)?", head.group(1).strip()) else ""
        elif key and label and key.group(1) == "commands":
            held = [key.group(2)]
        elif held is not None:
            held.append(raw)
    return out


SCRIPT_KEY = re.compile(r"^(\s*)(?:-\s+)?(script|before_script|after_script|commands):\s*(.*)$")


def scalar(item: str) -> str:
    """A YAML scalar's text, without a trailing comment: a quoted one unquoted and unescaped."""
    item = comment_split(item)[0]
    if len(item) > 1 and item[0] == '"' and item.endswith('"'):
        return re.sub(r'\\(["\\])', r"\1", item[1:-1])
    if len(item) > 1 and item[0] == "'" and item.endswith("'"):
        return item[1:-1].replace("''", "'")
    return item


def flow_items(text: str) -> list[str]:
    """A YAML flow sequence's items, `[a, "b, c"]`, split at commas outside quotes."""
    items, start, quote = [], 0, ""
    for i, c in enumerate(text):
        if quote:
            quote = "" if c == quote else quote
        elif c in "'\"":
            quote = c
        elif c == ",":
            items.append(text[start:i])
            start = i + 1
    items.append(text[start:])
    return [i.strip() for i in items if i.strip()]


def yaml_commands(text: str) -> list[str]:
    """The shell commands of a GitLab CI or CodeBuild file: only the items of a `script:`,
    `before_script:`, `after_script:` or `commands:` key, as a list, a flow list or a single value,
    after a trailing comment and an `&anchor` on the key's line; a block's lines, blank ones
    included, joined as YAML reads them; a plain item's comment dropped, a quoted one unescaped. An
    alias (`*name`) or a tagged value (`!reference [...]`) is no command, and neither are the items
    of `stages:`, `needs:`, `tags:` or any other key. One key's items run in one shell, so a `cd`
    item stays in front of the commands after it."""
    groups: list[list[str]] = []
    key_indent = None
    block, column, folded = None, 0, False
    plain_column = None

    def flush():
        lines = fold(block) if folded else [l.strip() for l in block if l.strip()]
        groups[-1].extend(comment_split(l)[0] for l in lines)

    for raw in text.splitlines():
        indent = len(raw) - len(raw.lstrip())
        if block is not None:
            if not raw.strip() or indent > column:
                block.append(raw)
                continue
            flush()
            block = None
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = SCRIPT_KEY.match(raw)
        if m:
            rest = re.sub(r"^(?:&\S+\s*)+", "", comment_split(m.group(3).strip())[0])
            tagged = rest.startswith("!")
            rest = re.sub(r"^!\S+\s*", "", rest) if tagged else rest
            key_indent, plain_column = len(m.group(1)), None
            groups.append([])
            if rest.startswith("*") or (tagged and rest):
                key_indent = None
            elif rest[:1] in ("|", ">"):
                block, column, folded = [], key_indent, rest.startswith(">")
                key_indent = None
            elif rest.startswith("["):
                groups[-1] += [scalar(i) for i in flow_items(rest.strip("[] "))]
                key_indent = None
            elif rest:
                groups[-1].append(scalar(rest))
                key_indent = None
            continue
        if key_indent is None:
            continue
        item = re.match(r"^(\s*)-\s+(.*)$", raw)
        if item and len(item.group(1)) >= key_indent:
            value = item.group(2).strip()
            if value[:1] in ("|", ">"):
                block, column, folded = [], len(item.group(1)), value.startswith(">")
                plain_column = None
            elif value.startswith(("!", "*")):
                plain_column = None
            else:
                groups[-1].append(scalar(value))
                plain_column = len(item.group(1))
        elif plain_column is not None and indent > plain_column and not item:
            groups[-1][-1] = groups[-1][-1] + " " + scalar(raw.strip())
        elif indent <= key_indent:
            key_indent, plain_column = None, None
    if block is not None:
        flush()
    return [c for lines in groups for c in shell(continued([l for l in lines if l]))]


def test_section(text: str) -> str:
    """A developer doc's sections whose Markdown heading says test, each to the next heading as high;
    a `#` line inside fenced code is no heading."""
    out, level, fenced = [], 0, False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
        m = None if fenced else re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if level and len(m.group(1)) <= level:
                level = 0
            if not level and re.search(r"(?i)\btest", m.group(2)):
                level = len(m.group(1))
        if level:
            out.append(line)
    return "\n".join(out)


def pick(candidates: list[tuple[str, str, str]]) -> tuple[tuple[str, str, str] | None, tuple[str, str, str] | None]:
    """One source's test and coverage commands from its candidates, `(path, command, label)` each in
    order: a side suite is passed over while another candidate remains, then one whose label says
    unit or that deselects a side suite itself comes first. Each is `(path, command without its
    runner, command as written)`."""
    found = [(path, bare(cmd), label, bool(re.search(r"--cov\b|\bcoverage\s+run\b", cmd)), cmd)
             for path, cmd, label in candidates
             if PYTEST.match(bare(cmd)) and "::" not in cmd and not re.search(r"<[^>]+>", cmd)
             and not re.search(r"--(version|help|collect-only)\b", cmd)]

    def side(path, cmd, label, _, __):
        named = SIDE_LABELS.search(label) or SIDE_SUITES.search(Path(path).name) \
            or any(SIDE_SUITES.search(w) for w in test_paths(cmd))
        return bool(named) and not DESELECTS.search(cmd)

    main_suite = [c for c in found if not side(*c)] or found
    main_suite.sort(key=lambda c: not (re.search(r"(?i)\bunit\b", c[2]) or DESELECTS.search(c[1])))
    plain = next(((p, c, raw) for p, c, _, cov, raw in main_suite if not cov), None)
    cov = next(((p, c, raw) for p, c, _, cov, raw in main_suite if cov), None)
    return plain, cov


def section(text: str, name: str) -> str:
    """The lines of one `[name]` table of a TOML file, read as text."""
    m = re.search(rf"^\[{re.escape(name)}\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def headings(name: str, text: str) -> list[str]:
    """A guide's section titles: Markdown `#` headings outside fenced code, or reStructuredText titles."""
    path = Path(name)
    lines = text.splitlines()
    titles, fenced = [], False
    for i, line in enumerate(lines):
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = re.match(r"^#{1,4}\s+(.+?)\s*#*\s*$", line)
        if m and path.suffix.lower() in (".md", ""):
            titles.append(m.group(1))
        elif (line.strip() and not line.lstrip().startswith("#") and i + 1 < len(lines)
              and re.fullmatch(r"([=\-~^\"'`#*+])\1{2,}" if path.suffix.lower() != ".md" else r"([=-])\1{2,}",
                               lines[i + 1].strip())
              and len(lines[i + 1].strip()) >= len(line.strip())):
            titles.append(line.strip())
    return titles


def branch_names(top: Path) -> list[str]:
    """Branch names, each once: local branches and remote-tracking ones with the remote dropped."""
    refs = git(top, "for-each-ref", "--sort=-committerdate", "--format=%(refname)", "refs/heads", "refs/remotes")
    seen: dict[str, None] = {}
    for ref in refs.splitlines():
        if ref.startswith("refs/heads/"):
            name = ref[len("refs/heads/"):]
        else:
            parts = ref[len("refs/remotes/"):].split("/", 1)
            if len(parts) < 2 or parts[1] == "HEAD":
                continue
            name = parts[1]
        seen.setdefault(name, None)
    return list(seen)[:200]


def where_matches(pattern: str, names: list[str], flags: int = 0) -> int:
    """How many branch names `where.sh` would take a ticket key from: `^([A-Za-z]+/)?(<pattern>)`."""
    try:
        rx = re.compile(rf"^([A-Za-z]+/)?({pattern})", flags)
    except re.error:
        return 0
    return sum(1 for n in names if rx.search(n))


def project_key(names: list[str], subjects: list[str]) -> str:
    """The ticket project the history names where convention puts a key, at a branch name's start
    or a subject's: seen with two numbers or more, or in a branch name, and with at least twice as
    many numbers as any other key so seen; otherwise the history names none. `GH` is GitHub's
    issue form and names no project."""
    numbers: dict[str, set] = {}
    in_branch = set()
    for text, is_branch in [(n, True) for n in names] + [(s, False) for s in subjects]:
        m = (BRANCH_KEY if is_branch else SUBJECT_KEY).match(text)
        if m and m.group(1) != "GH":
            numbers.setdefault(m.group(1), set()).add(m.group(2))
            if is_branch:
                in_branch.add(m.group(1))
    counts = Counter({k: len(v) for k, v in numbers.items() if len(v) >= 2 or k in in_branch})
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ranked or (len(ranked) > 1 and 2 * ranked[1][1] > ranked[0][1]):
        return ""
    return ranked[0][0]


def issue_key(names: list[str], subjects: list[str]) -> str:
    """The GitHub issue keys the history carries where convention puts one, as the `issue key` row
    gives them: each branch form with how many branch names carry it, how many subjects open with
    one, and the ticket pattern the branch forms imply as `where.sh` reads a GitHub tracker's
    branch: `(issue-)?\\d+`, its default, for `issue-<n>` and `<n>-words`, `GH-\\d+` for `GH-<n>`
    alone, `mixed` for `GH-<n>` beside another form, and `none` when no branch name carries one.
    Empty when neither a branch name nor a subject does."""
    forms = Counter(ISSUE_FORMS[(m.group(1) or "").lower()] for m in map(ISSUE_BRANCH.match, names) if m)
    led = sum(1 for s in subjects if ISSUE_SUBJECT.match(s))
    if not forms and not led:
        return ""
    if not forms:
        pattern = "none"
    elif "GH-<n>" not in forms:
        pattern = r"(issue-)?\d+"
    else:
        pattern = r"GH-\d+" if len(forms) == 1 else "mixed"
    held = ", ".join(f"{form} {n}" for form, n in sorted(forms.items(), key=lambda kv: (-kv[1], kv[0])))
    return f"branches: {held or 'none'} of {len(names)}; subjects: {led} of {len(subjects)}; pattern {pattern}"


def survey(top: Path, root: Path, ref: str = "HEAD", raws: list | None = None) -> tuple[str, list[dict]]:
    """The repository and its rows; `raws`, when given, gets each row's value as the repository
    writes it, a command whole rather than as the table shows it."""
    url = git(top, "remote", "get-url", "origin")
    repo = owner_repo(url)
    tree = Tree(top, ref)
    rows: list[dict] = []

    def add(family, found_in, value, key=None, derived=None, conflict=False):
        rows.append({"family": family, "found_in": clean(found_in), "value": clean(value) if value else "-",
                     "key": key, "derived": derived, "conflict": conflict})

    def docs_named(rx) -> list[str]:
        return [n for d in ("doc", "docs") for n in tree.under(d) if rx.fullmatch(Path(n).name)]

    add("remote", "git" if repo else "none", repo)
    head = git(top, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    add("default branch", "git" if head else "none", f"{head.split('/', 1)[-1]} (local origin/HEAD)" if head else "")

    template = tree.first(PR_TEMPLATES) or next(
        (n for n in tree.under(".gitlab/merge_request_templates") if n.endswith(".md")), None)
    body = tree.read_bytes(template) if template else None
    add("pull request template", template or "none",
        f"{len(body.decode(errors='replace').splitlines())} lines" if template else "", "template", body)
    issues = next((d for d in (".github/ISSUE_TEMPLATE", ".gitlab/issue_templates") if tree.under(d)), None)
    add("issue templates", f"{issues}/" if issues else "none", f"{len(tree.under(issues))} files" if issues else "")

    guide = tree.first(CONTRIBUTING)
    add("contributing guide", guide or "none", "present" if guide else "")
    guides = [(g, headings(g, tree.read(g))) for g in ([guide] if guide else []) + docs_named(GIT_DOC)[:1]]
    for family, pattern in HEADINGS.items():
        hit = next(((g, t) for g, titles in guides for t in titles if re.search(pattern, t, re.I)), None)
        add(family, f"{hit[0]}#{hit[1]}" if hit else "none", hit[1] if hit else "")

    owners = tree.first(CODEOWNERS)
    rules = [l for l in tree.read(owners).splitlines() if l.strip() and not l.lstrip().startswith("#")] if owners else []
    add("code owners", owners or "none", f"{len(rules)} rules" if owners else "")

    flows = [n for n in tree.under(".github/workflows") if re.search(r"\.ya?ml$", n) and n.count("/") == 2]
    other_ci = [n for n in tree.names if CI_FILES.search(n) and tree.has(n)]
    ci = [f"{len(flows)} GitHub workflows"] * bool(flows) + other_ci
    add("CI workflows", ".github/workflows/" if flows else (other_ci[0] if other_ci else "none"), "; ".join(ci))
    found = [p for p in INSTRUCTIONS if tree.has(p)]
    found += [n for n in tree.under(".github/instructions") if n.endswith(".instructions.md")]
    docs = [n for n in ("TESTING.md",) if tree.has(n)] + docs_named(TEST_DOC)
    dev = docs_named(DEV_DOC)
    sources = [[(f, c, label) for c, label in prose_commands(tree.read(f))] for f in found]
    sources += [[(docs[0], c, label) for c, label in prose_commands(tree.read(docs[0]))]] if docs else []
    sources += [[(dev[0], c, label) for c, label in prose_commands(test_section(tree.read(dev[0])))]] if dev else []
    sources += [[("tox.ini", c, label) for c, label in tox_commands(tree.read("tox.ini"))]] if tree.has("tox.ini") else []
    sources.append([(f, line, "") for f in flows for line in run_lines(tree.read(f))]
                   + [(f, line, "") for f in other_ci for line in yaml_commands(tree.read(f))])
    picks = [pick(s) for s in sources]
    for n, (family, key) in enumerate((("test command", "tests.command"), ("coverage command", "coverage.command"))):
        given = [p[n] for p in picks if p[n]]
        disagree = len({canonical(c) for _, c, _ in given}) > 1
        add(family, given[0][0] if given else "none", given[0][1] if given else "", key,
            given[0][2] if given else None, disagree)
        for path, command, raw in given[1:]:
            add(f"{family} (also)", path, command, key, raw, disagree)

    hooks = tree.has(".pre-commit-config.yaml")
    ids = re.findall(r"^\s*-\s+id:\s*([\w.-]+)", tree.read(".pre-commit-config.yaml"), re.M) if hooks else []
    if hooks:
        add("lint gate", ".pre-commit-config.yaml", f"pre-commit, {len(ids)} hooks", "lint.command", "pre-commit")
    else:
        linted = next(((path, cmd) for source in sources for path, cmd, _ in source if is_lint(cmd)), None)
        add("lint gate", linted[0] if linted else "none", bare(linted[1]) if linted else "", "lint.command",
            linted[1] if linted else None)
    secret = [i for i in ids if i in SECRET_HOOKS]
    add("secret scanning", ".pre-commit-config.yaml" if secret else "none", ", ".join(secret))

    text = tree.read("pyproject.toml") if tree.has("pyproject.toml") else ""
    name = re.search(r"""^name\s*=\s*["']([^"']+)["']""", section(text, "project") or section(text, "tool.poetry"), re.M)
    add("package", "pyproject.toml" if name else "none", name.group(1) if name else "")
    found_in, modules, clash = import_names(tree, text, name.group(1)) if name else ("none", [], False)
    add("import names", found_in, ", ".join(modules), conflict=clash)
    ini = section(text, "tool.pytest.ini_options")
    listed = re.search(r"^markers\s*=\s*\[(.*?)\]", ini, re.M | re.S)
    markers = re.findall(r"""["']([\w-]+)\s*:""", listed.group(1)) if listed else []
    paths = re.search(r"^testpaths\s*=\s*(.+)$", ini, re.M)
    value = "; ".join(v for v in (f"markers: {', '.join(markers)}" if markers else "",
                                  f"testpaths: {paths.group(1)}" if paths else "") if v)
    add("pytest settings", "pyproject.toml" if ini else "none", value or ("present" if ini else ""))

    add("testing doc", docs[0] if docs else "none", "present" if docs else "")
    add("developer doc", dev[0] if dev else "none", "present" if dev else "")
    add("agent instructions", found[0] if found else "none", f"{len(found)} files: " + ", ".join(found) if found else "")
    rules_file = tree.has("standards/review-rules.md")
    pointer = re.search(r"""^standard:\s+['"]?([\w.-]+/[\w.-]+)""", tree.read("standards/profile.yaml"), re.M) \
        if tree.has("standards/profile.yaml") else None
    if rules_file or not pointer:
        add("review rules", "standards/review-rules.md" if rules_file else "none", "present" if rules_file else "")
    else:
        add("review rules", "standards/profile.yaml", f"those of {pointer.group(1)}")
    adr = next((d for d in DECISIONS if tree.under(d)), None)
    add("decision records", f"{adr}/" if adr else "none",
        f"{len([n for n in tree.under(adr) if n.endswith('.md')])} files" if adr else "")
    changelog = tree.first(CHANGELOGS)
    log = tree.read(changelog) if changelog else ""
    add("changelog", changelog or "none",
        "Keep a Changelog, [Unreleased]" if re.search(r"^## \[Unreleased\]", log, re.M | re.I) else ("present" if log else ""))
    loose_files = uncommitted(top)
    add("not committed", loose_files[0] if loose_files else "none",
        f"{len(loose_files)} files, not read: " + ", ".join(loose_files) if loose_files else "")
    links = [f"{p} -> {target}" for p, target in sorted(tree.unfollowed.items())]
    add("symlinks not followed", next(iter(sorted(tree.unfollowed)), "none"),
        f"{len(links)} links, not read: " + ", ".join(links) if links else "")

    names = branch_names(top)
    subjects = git(top, "log", "-50", "--no-merges", "--format=%s", ref, "--").splitlines()
    key = project_key(names, subjects)
    pattern = rf"{key}-\d+" if key else ""
    exact, loose = (where_matches(pattern, names), where_matches(pattern, names, re.I)) if key else (0, 0)
    add("ticket key", "history" if key else "none",
        f"{key}-<n>; branches: {exact} of {len(names)} as where.sh, {loose} any case" if key else "",
        "ticket.pattern", {"pattern": pattern, "names": names} if key else None)
    add("ticket project", "history" if key else "none", key, "ticket.project", key or None)
    issue_keys = issue_key(names, subjects)
    add("issue key", "history" if issue_keys else "none", issue_keys)
    led = sum(1 for s in subjects if key and re.match(rf"\[?{re.escape(key)}-\d+\b", s))
    conventional = sum(1 for s in subjects if re.match(r"(feat|fix|docs|chore|refactor|test|build|ci)(\(.+\))?!?:", s))
    habit = (f"{led} of {len(subjects)} subjects open with a ticket key" if led else
             f"{conventional} of {len(subjects)} subjects are conventional commits" if conventional else "")
    add("commit habit", "history" if habit else "none", habit)

    if raws is not None:
        raws.extend(r["derived"] for r in rows)
    compare(rows, repo, root)
    return repo, rows


def is_lint(command: str) -> bool:
    """Whether a command runs a linter that checks without changing a file: `ruff check`, `flake8`,
    `pylint`, or `black`, `isort` or `ruff format` with `--check`, never with an option starting
    `--fix` (`--fix-only`, `--fix=...`)."""
    ws = words(re.sub(r"^cd \S+ && ", "", command))
    if not ws or any(w.startswith("--fix") for w in ws):
        return False
    if ws[0] in ("flake8", "pylint") or ws[:2] == ["ruff", "check"]:
        return True
    return (ws[0] in ("black", "isort") or ws[:2] == ["ruff", "format"]) and any(w.startswith("--check") for w in ws)


def agree(key: str, derived, value) -> str:
    """`match` for a family the repository and the key both hold."""
    if key == "lint.command" and derived != "pre-commit":
        return "same" if canonical(str(derived)) == canonical(str(value)) else "differs"
    if key == "lint.command":
        return "inferred" if words(str(value))[:2] == ["pre-commit", "run"] else "differs"
    if key == "ticket.pattern":
        if derived["pattern"] == str(value):
            return "same"
        names = derived["names"]
        loose = where_matches(derived["pattern"], names, re.I)
        return "same" if loose and where_matches(str(value), names) >= loose else "differs"
    return "same" if canonical(str(derived)) == canonical(str(value)) else "differs"


def standard_files(repo: str) -> Path | None:
    """The directory of the standard the working directory's checkout keeps, when it is `repo`: the
    fetched standard its pointer names, or its own `standards/`; None with neither."""
    top = plugin_profile.checkout(repo, plugin_profile.owners(repo)) if repo else None
    found = plugin_profile.standard_of(top) if top else None
    return found[0] if found else None


def compare(rows: list[dict], repo: str, root: Path) -> None:
    """Fill each row's plugin value, its source and whether it matches what the repository holds."""
    values = plugin_profile.resolve(repo, root, detect=False) if repo else plugin_profile.defaults(root)
    run_owners = plugin_profile.owners(repo) if repo else ()
    own, files, _ = plugin_profile.local(repo, run_owners) if repo else ({}, [], None)
    for row in rows:
        key, derived, conflict = row.pop("key"), row.pop("derived"), row.pop("conflict")
        row.update(key=key, plugin_today="-", plugin_source="-", match="-", conflict=conflict)
        if not key:
            continue
        top, _, sub = key.partition(".")
        value = values[top][sub] if sub and isinstance(values[top], dict) else values[top]
        mine = own.get(top, {}).get(sub) if sub and isinstance(own.get(top), dict) else own.get(top)
        # A standard for several repositories keeps the project's settings in its profile.yaml, the
        # first file, and the repository's in profiles/<repo>.yaml, the last.
        row["plugin_source"] = (files[0] if top in plugin_profile.PROJECT_KEYS else files[-1]) if mine is not None else plugin_profile.DEFAULT_PROFILE
        row["plugin_today"] = clean(str(value)) or "''"
        recorded = value not in (plugin_profile.NOT_RECORDED, "")
        if derived is None:
            row["match"] = "plugin only" if recorded else "-"
        elif not recorded:
            row["match"] = "repository only"
        elif key == "template":
            held = standard_files(repo)
            theirs = held / "templates" / str(value) / "PULL_REQUEST_TEMPLATE.md" if held else None
            row["match"] = "same" if theirs and theirs.is_file() and theirs.read_bytes() == derived else "differs"
        else:
            row["match"] = agree(key, derived, value)


NOT_FAMILIES = ("not committed", "symlinks not followed")


def table(repo: str, rows: list[dict]) -> str:
    families = [r for r in rows if not r["family"].endswith("(also)") and r["family"] not in NOT_FAMILIES]
    held = sum(1 for r in families if r["found_in"] != "none")
    out = [f"survey: {repo or 'no remote'} · {len(families)} families · {held} from the repository", HEADER]
    for r in rows:
        today = f"{short(r['plugin_today'])} ({r['plugin_source']})" if r["key"] else "-"
        match = f"conflict; {r['match']}" if r["conflict"] else r["match"]
        out.append(" | ".join((r["family"], short(r["found_in"]), short(r["value"]), today, match)))
    return "\n".join(out)


# Read by Claude Code at every session start, with every file they import, as `@path`.
SESSION_FILES = ("CLAUDE.md", ".claude/CLAUDE.md")
IMPORT = re.compile(r"(?:^|(?<=\s))@([\w./-]+)")
# Read by a script, so the model sees only the value: these, CI files and a pull request template.
SCRIPTED = (".pre-commit-config.yaml", "pyproject.toml", "tox.ini", *CODEOWNERS)


def imports(tree: Tree, path: str) -> list[str]:
    """The committed files `path` imports, as `@path` outside code, relative to it."""
    text = re.sub(r"```.*?```|~~~.*?~~~|`[^`\n]*`", "", tree.read(path), flags=re.S)
    targets = (posixpath.normpath(posixpath.join(posixpath.dirname(path), m.group(1).rstrip(".,;:)")))
               for m in IMPORT.finditer(text))
    return [t for t in targets if tree.has(t)]


def session_start(tree: Tree) -> list[str]:
    """The committed files every Claude Code session loads: CLAUDE.md, .claude/CLAUDE.md, each
    `.claude/rules/*.md` with no `paths:` in its frontmatter, and what they import, at most five hops
    deep. A rule scoped by `paths:` attaches later, but what it imports loads at the start too."""
    rules = [n for n in tree.under(".claude/rules") if n.endswith(".md")]
    scoped = [n for n in rules if re.match(r"---\n(?:(?!---\n).*\n)*?paths:", tree.read(n))]
    todo = [(p, 0) for p in SESSION_FILES if tree.has(p)] + [(n, 0) for n in rules if n not in scoped]
    todo += [(t, 1) for n in scoped for t in imports(tree, n)]
    found: list[str] = []
    while todo:
        path, depth = todo.pop(0)
        if path in found:
            continue
        found.append(path)
        if depth < 5:
            todo += [(t, depth + 1) for t in imports(tree, path)]
    return found


def loads(path: str, always: list[str]) -> str:
    """How a fact from `path` reaches the model: loaded into every session, read when a skill needs
    the file, or resolved by a script that hands over only the value."""
    path = path.split(" (")[0]
    if path in always:
        return "always"
    if path in ("history", "GitHub", "git", "clones") or path in SCRIPTED or path in PR_TEMPLATES \
            or path.startswith((".github/workflows/", ".gitlab/merge_request_templates/")) or CI_FILES.search(path):
        return "script"
    return "on demand"


LEAVES = [f"{k}.{s}" if s else k for k, shape in plugin_profile.SCHEMA.items()
          for s in (shape if isinstance(shape, dict) else [None])]
# Programs whose first argument names what they do, so a gate pattern keeps it: `pre-commit run`.
SUBCOMMANDS = ("pre-commit", "ruff", "tox", "nox", "make", "just", "hatch", "npm")
# Programs that run another command, so the next word, not they, is what the gate is.
LAUNCHERS = {"cd", "sh", "bash", "zsh", "sudo", "exec", "xargs", "time", "nohup", "eval", "source"}
BUILTINS = {"test", "[", "true", "false", "echo", ":", "printf", "set", "export", "exit"}
# What a runner's `run` may name and still be a program, not one of the project's own scripts.
KNOWN_PROGRAMS = {"pytest", "py.test", "pre-commit", "ruff", "tox", "nox", "mypy", "pyright", "flake8", "black",
                  "pylint", "coverage", "make", "python", "python3"}
# What a chain of commands is counted by: a program that runs tests or linters itself, not one
# that builds (`make`), reports (`coverage report`) or runs anything (`python`).
CHAIN_PROGRAMS = KNOWN_PROGRAMS - {"make", "coverage", "python", "python3"}
TYPE_CHECKERS = ("mypy", "pyright", "pyre", "pytype")
# Directories whose files are no part of what a change to the product touches.
ASIDE = {"test", "tests", "doc", "docs", "example", "examples", "notebooks", "benchmarks"}
# Names a science-critical file or directory tends to carry: a definition of a product or a
# format, a manifest, a calibration, a schema, geolocation, a SPICE kernel.
CRITICAL = ("definition", "manifest", "calibrat", "schema", "geoloc", "kernel")
CODE = (".py", ".pro", ".c", ".h", ".cpp", ".f", ".f90", ".jl", ".m", ".r")
CHANGELOGS = ("CHANGELOG.md", "CHANGELOG.rst", "CHANGES.md", "HISTORY.md", "doc/changelog.md", "docs/changelog.md",
              "doc/CHANGELOG.md", "docs/CHANGELOG.md", "doc/source/changelog.md", "docs/source/changelog.md",
              "doc/source/changelog.rst", "docs/source/changelog.rst")
LIGHT_FILES = ("CHANGELOG.md", "CHANGELOG.rst", "CHANGES.md", "HISTORY.md", "README.md", "README.rst")
DEPENDENCY_FILES = tuple(f":(glob)**/{n}" for n in ("pyproject.toml", "requirements*.txt", "setup.cfg", "setup.py",
                                                    "environment*.yml"))


def gate_pattern(command: str) -> str:
    """The extended regular expression `build-record.sh` counts a command by: the program, without
    its runner, a `cd` before it, `env` or a `NAME=value` in front, and its subcommand for a program
    that takes one, with the script `run` names (`npm run test`); "" when what is left does not
    start with a plain program name, starts with an option, a shell builtin, a shell, `cd`, `sudo`
    or the like, or is a script a runner's `run` names (`hatch run test`) rather than a program
    known to run tests or linters, so nothing is counted rather than the wrong thing. A chain of
    commands is counted by the one test or lint program (`CHAIN_PROGRAMS`) its commands run, the
    rest preparing or reporting: `make generated && cd src/tests && pytest -s .` and `coverage
    run -m pytest && coverage report` by `pytest`; "" when none does or two differ (`pytest &&
    mypy src`)."""
    parts = commands(command)
    if len(parts) > 1:
        gates = [g for g in map(gate_pattern, parts) if g.split("[[:space:]]+")[0].replace("\\", "") in CHAIN_PROGRAMS]
        return gates[0] if len(set(gates)) == 1 else ""
    command = re.sub(r"^cd \S+ && ", "", parts[0] if parts else command)
    raw = command.split()
    while raw and (raw[0] == "env" or re.fullmatch(r"[A-Za-z_]\w*=\S*", raw[0])):
        raw = raw[1:]
    ws = words(" ".join(raw))
    if not ws or ws[0].startswith("-") or not re.fullmatch(r"[A-Za-z0-9_.+-]+", ws[0]) \
            or ws[0] in LAUNCHERS or ws[0] in BUILTINS:
        return ""
    if raw[:1] and raw[0] in RUNNERS and raw[1:2] == ["run"] and ws[0] not in KNOWN_PROGRAMS:
        return ""
    keep = ws[:1]
    if ws[0] in SUBCOMMANDS and len(ws) > 1:
        if ws[1].startswith("-"):
            return ""
        keep = ws[:3] if ws[1] == "run" and len(ws) > 2 and not ws[2].startswith("-") else ws[:2]
    return "[[:space:]]+".join(re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", w) for w in keep)


def one_gate(commands_seen: list[str]) -> str:
    """The gate pattern every command shares, or "" when they name different programs or none."""
    gates = {gate_pattern(c) for c in commands_seen}
    return gates.pop() if len(gates) == 1 else ""


def type_checkers(tree: Tree) -> tuple[list[str], str | None]:
    """The type checkers the repository configures, in a fixed order, and the first file naming one:
    a pre-commit hook, a `[tool.<checker>]` table, or a dependency line in `pyproject.toml`."""
    found: dict[str, str] = {}
    if tree.has(".pre-commit-config.yaml"):
        for hook in re.findall(r"^\s*-\s+id:\s*([\w.-]+)", tree.read(".pre-commit-config.yaml"), re.M):
            for name in TYPE_CHECKERS:
                if re.fullmatch(rf"{name}(-[\w.-]+)?", hook):
                    found.setdefault(name, ".pre-commit-config.yaml")
    if tree.has("pyproject.toml"):
        text = tree.read("pyproject.toml")
        for name in TYPE_CHECKERS:
            if re.search(rf"^\[tool\.{name}[\].]|^\s*[\"']?{name}[\"']?\s*=|^\s*[\"']{name}(?![\w-])[^:]", text, re.M):
                found.setdefault(name, "pyproject.toml")
    names = [n for n in TYPE_CHECKERS if n in found]
    return names, (found[names[0]] if names else None)


def light_paths(tree: Tree) -> list[dict]:
    """Paths a change to which allows a light build, by rule: a changelog or README at the top, the
    Markdown and reStructuredText under `doc/` or `docs/`, and the version line of `pyproject.toml`,
    its hunk pattern the line's start as the file writes it (`^version =`)."""
    out = [{"glob": n, "brief": "documentation"} for n in LIGHT_FILES if tree.has(n)]
    for d in ("doc", "docs"):
        for ext in ("md", "rst"):
            if any(n.endswith(f".{ext}") for n in tree.under(d)):
                out.append({"glob": f"{d}/**/*.{ext}", "brief": "documentation"})
    version = re.search(r"^version\s*=", tree.read("pyproject.toml"), re.M) if tree.has("pyproject.toml") else None
    if version:
        out.append({"glob": "pyproject.toml", "hunk": "^" + version.group(0), "brief": "documentation"})
    return out


def deep_paths(tree: Tree) -> list[str]:
    """Paths a change to which forces a deep build, by rule, for a person to trim: each outermost
    `data/` directory, each directory named for a science-critical thing (`CRITICAL`), and each code
    file so named outside them, in its directory (`pkg/io/product_definition*`), or anywhere
    (`**/manifest*`) when files of that name sit in two directories or more. Nothing under a test,
    doc or example directory counts, nor a file whose name starts `test_` or `mock_`."""
    dirs: list[str] = []
    for name in tree.names:
        parts = name.split("/")[:-1]
        for i, part in enumerate(parts):
            if part.lower() in ASIDE:
                break
            if part == "data" or any(c in part.lower() for c in CRITICAL):
                d = "/".join(parts[: i + 1])
                if d not in dirs:
                    dirs.append(d)
                break
    out = [f"{d}/**" for d in dirs]
    files = []
    for name in tree.names:
        parts = name.split("/")
        stem, ext = posixpath.splitext(parts[-1])
        if ext.lower() in CODE and not any(p.lower() in ASIDE for p in parts[:-1]) \
                and not any(name.startswith(d + "/") for d in dirs) and any(c in stem.lower() for c in CRITICAL) \
                and not stem.lower().startswith(("test_", "mock_")):
            files.append((posixpath.dirname(name), stem))
    places = Counter(stem for _, stem in set(files))
    for where, stem in files:
        glob = f"**/{stem}*" if places[stem] > 1 else f"{where + '/' if where else ''}{stem}*"
        if glob not in out:
            out.append(glob)
    return out


def grep(clone: Path, pattern: str, ref: str, *paths: str, case: bool = True) -> set:
    """The files at `ref` holding an extended regular expression; none is git grep's exit 1, and any
    other failure stops the survey, naming the checkout."""
    out = subprocess.run(["git", "-C", str(clone), "grep", "-l", "-I", *([] if case else ["-i"]), "-E", pattern, ref,
                          "--", *paths], capture_output=True, text=True)
    if out.returncode not in (0, 1):
        raise OSError(f"git grep failed in {clone}: {out.stderr.strip()}")
    return set(out.stdout.splitlines())


def import_names(tree: Tree, text: str, package: str) -> tuple[str, list[str], bool]:
    """Where the top-level names distribution `package` imports as were read, the names, and
    whether its sources disagree. `text` is `pyproject.toml`. The names come from the arrays
    `[tool.setuptools] packages` and `[tool.poetry] packages` (`include`, its path up to a glob),
    `pyproject.toml`, each name cut to its shortest dotted prefix with an `__init__.py` at the top
    or under `src/`, or kept whole when no prefix has one, and dropped under another listed name;
    a `packages` that is no array, such as `{find = ...}`, names none. Else each `src/<name>/__init__.py`, else each `<name>/__init__.py`,
    outside a test, doc or example directory, `git (inferred)`, only the one that is `package` with
    `-` as `_` or its last `-` part when one is, and several, none of them that, disagree. Else
    `package` with `-` as `_`, `pyproject.toml (inferred)`. Two tables that list different names
    disagree, and both tables' names are given. A namespace package's name stays dotted
    (`org.pkg`), so an import of its namespace alone (`from org import pkg`) is not one."""
    def prefix(name: str) -> str:
        parts = name.split(".")
        return next((".".join(parts[:i]) for i in range(1, len(parts) + 1)
                     if tree.has(f"{'/'.join(parts[:i])}/__init__.py") or tree.has(f"src/{'/'.join(parts[:i])}/__init__.py")),
                    name)

    tables = []
    for table, item in (("tool.setuptools", r"""["']([^"']+)["']"""), ("tool.poetry", r"""include\s*=\s*["']([^"']+)["']""")):
        listed = re.search(r"^packages\s*=\s*(\[.*?)(?=^[\w-]+\s*=|\Z)", section(text, table), re.M | re.S)
        found = (re.split(r"/[^/]*[*?[]", n, maxsplit=1)[0].replace("/", ".") for n in re.findall(item, listed.group(1))) if listed else ()
        names = sorted({prefix(n) for n in found if all(p.isidentifier() for p in n.split("."))})
        names = [n for n in names if not any(n.startswith(f"{m}.") for m in names)]
        if names:
            tables.append(names)
    if tables:
        return "pyproject.toml", sorted(set().union(*tables)), any(t != tables[0] for t in tables)
    layout = [sorted(n.split("/")[-2] for n in tree.names if re.fullmatch(rf"{root}[^/]+/__init__\.py", n)
                     and n.split("/")[-2].lower() not in ASIDE) for root in ("src/", "")]
    layout = layout[0] or layout[1]
    if layout:
        own = [n for n in layout if n.lower() in (package.replace("-", "_").lower(), package.rsplit("-", 1)[-1].lower())]
        return "git (inferred)", own or layout, not own and len(layout) > 1
    return "pyproject.toml (inferred)", [package.replace("-", "_")], False


def downstream_from(path: Path, repo: str, package: str, modules: list[str]) -> tuple[list[tuple[str, int]], str]:
    """The repositories that use `package`, with the number of files showing it, most first, and
    the source to name: from a JSON list of `{"repo", "evidence"}` the onboarding skill writes from
    its code search (`GitHub (search)`), or, for a directory, from the committed files of each git
    checkout directly in it, at its `origin/HEAD` or else `HEAD` (`clones (search)`): a Python file
    that imports one of `modules`, the package's top-level import names, or a dependency file that
    names `package`. With no `package` or no `modules`, a directory finds none. A checkout of `repo`
    itself is passed over, by its name whatever the owner, so a fork's checkout is too, and one repository's
    several checkouts count once, by their largest count. A search git cannot run stops it."""
    own = repo.split("/", 1)[-1].lower()
    if path.is_file():
        try:
            data = json.loads(path.read_text())
        except ValueError as e:
            raise OSError(f"{path}: {e}") from e
        if not isinstance(data, list) or not all(
                isinstance(x, dict) and isinstance(x.get("repo"), str) and plugin_profile.REPO.fullmatch(x["repo"])
                and isinstance(x.get("evidence"), int) and not isinstance(x["evidence"], bool) and x["evidence"] > 0
                for x in data):
            raise OSError(f"{path}: not a list of {{\"repo\": <name>, \"evidence\": <count above 0>}}")
        found = {x["repo"]: x["evidence"] for x in data if x["repo"].lower() != own}
        source = "GitHub (search)"
    elif path.is_dir():
        if not package or not modules:
            return [], ""
        module = "(" + "|".join(re.escape(m) for m in modules) + ")"
        named = "[-_]".join(re.escape(part) for part in re.split(r"[-_]", package))
        found = {}
        for clone in sorted(p for p in path.iterdir() if (p / ".git").exists()):
            other = owner_repo(git(clone, "remote", "get-url", "origin"))
            name = other.split("/", 1)[-1]
            if not other or name.lower() == own:
                continue
            ref = "origin/HEAD" if git(clone, "rev-parse", "--verify", "-q", "origin/HEAD") else "HEAD"
            hits = grep(clone, rf"^[[:space:]]*(import|from)[[:space:]]+{module}([.[:space:]]|$)", ref, "*.py")
            hits |= grep(clone, rf"(^|[^a-z0-9_-]){named}([^a-z0-9_-]|$)", ref, *DEPENDENCY_FILES, case=False)
            if hits:
                found[name] = max(found.get(name, 0), len(hits))
        source = "clones (search)"
    else:
        raise OSError(f"{path} is neither a file nor a directory")
    return sorted(found.items(), key=lambda kv: (-kv[1], kv[0])), source


def candidate(top: Path, ref: str, root: Path, repo: str, rows: list[dict], raws: list,
              public: bool | None = None, downstream: Path | None = None) -> tuple[dict, dict]:
    """The profile the survey can fill, every other key `not yet recorded`, and where each value
    came from: `{key: {"source", "conflict", "seen"}}`, `seen` being every repository source of the
    key with its value as the repository writes it, `raws` being survey()'s. A key whose sources
    disagree is left unrecorded, its sources all in `seen`."""
    nr = plugin_profile.NOT_RECORDED
    values = {key: nr for key in LEAVES}
    sources = {key: {"source": None, "conflict": False, "seen": []} for key in LEAVES}
    by_family = {r["family"]: r for r in rows}
    project = by_family["ticket project"]["value"]
    if project != "-":
        values["ticket.pattern"], values["ticket.project"] = rf"{project}-\d+", project
        sources["ticket.pattern"]["source"] = sources["ticket.project"]["source"] = "history"
    if public is not None:
        values["public"] = public
        sources["public"]["source"] = "GitHub"
    tree = Tree(top, ref)
    template = by_family["pull request template"]["found_in"]
    if template != "none":
        body = tree.read_bytes(template)
        sources["template"]["seen"] = [{"source": template, "value": f"{len(body.decode(errors='replace').splitlines())} lines"}]
        held = standard_files(repo)
        names = sorted(p.parent.name for p in (held / "templates").glob("*/PULL_REQUEST_TEMPLATE.md")
                       if p.read_bytes() == body) if held else []
        if names:
            values["template"] = names[0]
            sources["template"]["source"] = template
    for family, key in (("test command", "tests.command"), ("coverage command", "coverage.command")):
        given = [(r, raw) for r, raw in zip(rows, raws)
                 if r["family"] in (family, f"{family} (also)") and r["found_in"] != "none"]
        sources[key]["seen"] = [{"source": r["found_in"], "value": raw} for r, raw in given]
        if given and given[0][0]["conflict"]:
            sources[key]["conflict"] = True
        elif given:
            values[key], sources[key]["source"] = given[0][1], given[0][0]["found_in"]
    lint_row = by_family["lint gate"]
    if lint_row["found_in"] == ".pre-commit-config.yaml":
        values["lint.command"] = "pre-commit run --files"
        sources["lint.command"]["source"] = ".pre-commit-config.yaml (inferred)"
        values["lint.regex"] = gate_pattern(values["lint.command"])
        sources["lint.regex"]["source"] = ".pre-commit-config.yaml (inferred)"
    elif lint_row["found_in"] != "none":
        values["lint.command"] = raws[rows.index(lint_row)]
        sources["lint.command"]["source"] = lint_row["found_in"]
        sources["lint.command"]["seen"] = [{"source": lint_row["found_in"], "value": values["lint.command"]}]
        gate = gate_pattern(values["lint.command"])
        if gate:
            values["lint.regex"] = gate
            sources["lint.regex"]["source"] = f"{lint_row['found_in']} (inferred)"
    commands_seen = sources["tests.command"]["seen"] + sources["coverage.command"]["seen"]
    gate = one_gate([x["value"] for x in commands_seen])
    if gate:
        values["gates.tests"] = gate
        sources["gates.tests"]["source"] = f"{commands_seen[0]['source']} (inferred)"
    checkers, named_in = type_checkers(tree)
    if checkers:
        values["types.regex"] = checkers[0] if len(checkers) == 1 else f"({'|'.join(checkers)})"
        sources["types.regex"]["source"] = f"{named_in} (inferred)"
    light, deep = light_paths(tree), deep_paths(tree)
    if light:
        values["depth.light"], sources["depth.light"]["source"] = light, "git (inferred)"
    if deep:
        values["depth.deep"], sources["depth.deep"]["source"] = deep, "git (inferred)"
    if downstream is not None:
        package, imports = by_family["package"]["value"], by_family["import names"]
        modules = [] if imports["value"] == "-" or imports["conflict"] else imports["value"].split(", ")
        users, source = downstream_from(downstream, repo, "" if package == "-" else package, modules)
        if users:
            values["downstream"] = [name for name, _ in users]
            sources["downstream"]["source"] = source
            sources["downstream"]["seen"] = [{"source": source, "value": f"{name}: {n} files"} for name, n in users]
    always = session_start(tree)
    paths = {p for s in sources.values() for p in [s["source"] or ""] + [x["source"] for x in s["seen"]] if p} | set(always)
    files = {p: {"loads": loads(p, always), "chars": len(tree.read(p.split(" (")[0])) if tree.has(p.split(" (")[0]) else 0}
             for p in sorted(paths)}
    profile: dict = {}
    for key, v in values.items():
        top_key, _, sub = key.partition(".")
        if sub:
            profile.setdefault(top_key, {})[sub] = v
        else:
            profile[key] = v
    return profile, {"repo": repo, "ref": git(top, "rev-parse", ref), "keys": sources, "files": files,
                     "session_start": {"files": always, "chars": sum(files[p]["chars"] for p in always)}}


def yaml_value(v) -> str:
    if v == plugin_profile.NOT_RECORDED:
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(yaml_value(i) for i in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {yaml_value(x)}" for k, x in v.items()) + "}"
    return "'" + str(v).replace("'", "''") + "'"


PROPOSALS = ("downstream", "depth.light", "depth.deep")


def confirmed_of(path: Path, profile: dict) -> dict:
    """The values a person gave, from an answers file in the scorer's form,
    `{"<key>": {"how": "confirmed" | "asked", "value": ...}}`, every key a profile key with a value
    the schema takes, as the scorer checks them: a proposal key's value, confirmed (the proposal or
    a part of it) or asked, and any other key's asked value, such as the one test command a person
    picks where the repository's own files disagree, or `not yet recorded` to leave it out. Any
    other key confirmed must be the candidate's own value, not `not yet recorded`."""
    try:
        data = json.loads(path.read_text())
    except ValueError as e:
        raise OSError(f"{path}: {e}") from e
    if not isinstance(data, dict):
        raise OSError(f"{path}: not a JSON object")
    out = {}
    for key, a in data.items():
        if key not in LEAVES:
            raise OSError(f"{path}: {key!r} is no profile key")
        if not isinstance(a, dict) or a.get("how") not in ("asked", "confirmed") or "value" not in a:
            raise OSError(f"{path}: {key} needs how (asked or confirmed) and value")
        top, _, sub = key.partition(".")
        plugin_profile.check({top: {sub: a["value"]} if sub else a["value"]}, str(path))
        if key not in PROPOSALS:
            current = profile[top][sub] if sub else profile[top]
            if a["how"] == "confirmed" and (current == plugin_profile.NOT_RECORDED or a["value"] != current):
                raise OSError(f"{path}: {key} is confirmed as {a['value']!r}, which is not the candidate's {current!r}")
            out[key] = a["value"]
            continue
        proposed = profile[top][sub] if sub else profile[top]
        if a["how"] == "confirmed" and (not isinstance(proposed, list) or any(v not in proposed for v in a["value"])):
            raise OSError(f"{path}: {key} is confirmed as {a['value']!r}, which is not part of the proposal")
        out[key] = a["value"]
    return out


def profile_text(repo: str, profile: dict, drop_in: bool = False, given: dict | None = None) -> str:
    """A candidate profile in the subset of YAML profile.py reads, which it is checked against. A
    drop-in one leaves out every key it cannot fill, so the standard's or the default profile's
    values stand for them, as for a profile a person wrote, and every proposal (`PROPOSALS`) but
    those `given` names, with the value the person kept, since an untrimmed proposal is no fact,
    and holds every value the person gave in `given`, the gate patterns worked out again from a command they gave unless they gave
    the pattern too, empty when the command has none, so another pattern does not stand for a
    command it does not match; the candidate itself writes the unfilled keys
    `not yet recorded`, which would override the default profile's."""
    nr = plugin_profile.NOT_RECORDED
    if drop_in:
        profile = {k: dict(v) if isinstance(v, dict) else v for k, v in profile.items()}
        for key in PROPOSALS:
            top, _, sub = key.partition(".")
            value = (given or {}).get(key, nr)
            if sub:
                profile[top][sub] = value
            else:
                profile[top] = value
        given = given or {}
        for key, value in given.items():
            top, _, sub = key.partition(".")
            if sub:
                profile[top][sub] = value
            else:
                profile[top] = value
        if "lint.command" in given and "lint.regex" not in given:
            command = profile["lint"]["command"]
            profile["lint"]["regex"] = gate_pattern(command) if command != nr else nr
        if {"tests.command", "coverage.command"} & set(given) and "gates.tests" not in given:
            commands = [c for c in (profile["tests"]["command"], profile["coverage"]["command"]) if c != nr]
            profile["gates"]["tests"] = one_gate(commands) if commands else nr
    if drop_in:
        out = [f"# A drop-in profile for {repo or 'no remote'}, written by scripts/survey.py: only the keys it",
               "# could fill, so the standard's or the default profile's values stand for the rest."]
    else:
        out = [f"# A candidate profile for {repo or 'no remote'}, written by scripts/survey.py from the repository's",
               "# committed files; a key it cannot fill reads `not yet recorded`. Where each value came from",
               "# is in the .sources.json file beside this one."]
    for key, v in profile.items():
        if isinstance(plugin_profile.SCHEMA[key], dict):
            subs = {sub: x for sub, x in v.items() if not (drop_in and x == nr)}
            if subs:
                out.append(f"{key}:")
                out += [f"  {sub}: {yaml_value(x)}" for sub, x in subs.items()]
        elif not (drop_in and v == nr):
            out.append(f"{key}: {yaml_value(v)}")
    text = "\n".join(out) + "\n"
    plugin_profile.check(plugin_profile.parse(text, "candidate"), "candidate")
    return text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true", help="the rows as a JSON list")
    p.add_argument("--repo", type=Path, default=Path.cwd(), help="a directory inside the checkout; default, the working directory")
    p.add_argument("--ref", default="HEAD", help="the commit whose files to read; default, HEAD")
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="the plugin's top level")
    p.add_argument("--profile", type=Path, help="also write the candidate profile here, and its sources beside it")
    p.add_argument("--public", choices=("true", "false"), help="whether the repository is public, as its server says")
    p.add_argument("--drop-in", type=Path, help="also write the profile with only the keys it could fill, for use in place of one")
    p.add_argument("--answers", type=Path,
                   help="the person's answers, in the scorer's form: the proposals they confirmed and the values they gave go into the drop-in")
    p.add_argument("--standard", choices=("none",),
                   help="read the repository as though lasp-dev.standard were none: its pointer's standard is not read")
    p.add_argument("--downstream-from", type=Path,
                   help="the repositories that use this one: the skill's code-search JSON, or a directory of checkouts to search")
    args = p.parse_args(argv)
    if args.answers and not args.drop_in:
        p.error("--answers goes with --drop-in, which is what it fills")
    if args.standard:
        count = os.environ.get("GIT_CONFIG_COUNT", "0") or "0"
        if not count.isdigit():
            print(f"survey.py: GIT_CONFIG_COUNT is {count!r}, not a count, so --standard cannot be added to it", file=sys.stderr)
            return 1
        n = int(count)
        os.environ.update({"GIT_CONFIG_COUNT": str(n + 1), f"GIT_CONFIG_KEY_{n}": "lasp-dev.standard",
                           f"GIT_CONFIG_VALUE_{n}": args.standard})
    top = git(args.repo, "rev-parse", "--show-toplevel")
    if not top:
        print(f"survey.py: {args.repo} is not inside a git checkout", file=sys.stderr)
        return 1
    try:
        raws: list = []
        repo, rows = survey(Path(top), args.root, args.ref, raws)
        if args.profile or args.drop_in:
            public = None if args.public is None else args.public == "true"
            profile, sources = candidate(Path(top), args.ref, args.root, repo, rows, raws, public, args.downstream_from)
            confirmed = confirmed_of(args.answers, profile) if args.answers else {}
        if args.profile:
            args.profile.parent.mkdir(parents=True, exist_ok=True)
            args.profile.write_text(profile_text(repo, profile))
            args.profile.with_name(f"{args.profile.stem}.sources.json").write_text(json.dumps(sources, indent=1) + "\n")
        if args.drop_in:
            args.drop_in.parent.mkdir(parents=True, exist_ok=True)
            args.drop_in.write_text(profile_text(repo, profile, drop_in=True, given=confirmed))
    except (plugin_profile.ProfileError, OSError) as e:
        print(f"survey.py: {e}", file=sys.stderr)
        return 1
    print(json.dumps(rows, indent=1) if args.json else table(repo, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
