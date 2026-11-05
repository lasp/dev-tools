#!/usr/bin/env python3
"""Check a repository's rules against the seven gates of `standards/rule-bar.md`.

Reads the ledger (`--ledger`, a standard's `review-rules.md`), whose entries hold each rule's
wording as the `> ` lines of the entry, the decisions (`--decisions`, repeatable: the standard's
and the shared `decisions.md`), and the repository itself (`--repo`, for `git ls-files` and `git
show`). A ledger whose wording is still in an instruction file names it with `--instructions`, the
file whose `## Review Rules` section holds each rule under its `### R-NNN · <title>` heading, and
each entry links it on a `Wording:` line. With `--entry <file>` in place of the ledger, it reads
one drafted entry, its wording in it, or followed by its drafted wording under the same heading
for an instruction file, as `revise` and `onboard` write them; `sync` then compares only the
drafted wording's heading with the entry, and `fields` always applies. `--checks` runs only the gates it names, for a correction that touches some of an
entry's lines and not its wording.

- sync: no id has two ledger entries; every reviewer-tier entry, provisional or established, has
  its wording, and a retired rule none; a graduated or check-tier rule may keep it, as guidance
  for authors. With an instruction file, the wording is one heading with the entry's title, the
  `Wording:` link ends in that heading's GitHub anchor, no id has two headings, and a heading has
  an entry.
- wording: for a reviewer-tier rule, provisional or established, two to four non-blank lines,
  with no `#<n>`, `pr-NNNN` or `PRRT_` in them.
- status: the tier is reviewer, check or `—`; the status is provisional, established, retired or
  graduated; a rule whose evidence line says `implements <id>`, in any case, the id bare, in
  backticks or as a link, has the status of that decision, the `**provisional**` or
  `**established**` opening the bold text on the first non-blank line after the decision's
  heading, and a decision whose line carries neither is not compared; an `implements` naming no
  decision in any `--decisions` file fails, and so does a decision id on the evidence line
  outside an `implements`, or an `implements` anywhere in the entry off its status line; a
  "needs a second" marker, in any case, appears only on a provisional
  rule.
- scope: the `scope:` line holds no empty glob and no glob of only `*` and `/`, and each glob
  matches a file `git ls-files` lists, by `fnmatch`, where `*` matches `/` too.
- anchors: the `example:` line reads `fires on <anchor or thread>; not on <anchor>`, its two
  halves different places; a thread, `<repo>#<PR> PRRT_...`, is checked for form only; each
  anchor, `<repo>#<PR>@<sha> <path>::<symbol> "<shape>"`, resolves: `git show <sha>:<path>`
  succeeds, defines the symbol, a function or class or `Class.method`, by `def` or `class`, and
  holds the shape verbatim inside that definition. The not-on anchor's sha is also on the
  default branch, `origin/HEAD`, and its subject names the pull request, `(#<PR>)` or `Merge pull
  request #<PR>`, so the example cites what that pull request merged.
- fields: a reviewer-tier entry, provisional or established, carries `scope:` and `example:`. A
  `repos:` line, at most one, on any entry or on a decision in a `--decisions` file, anywhere in
  its block outside its wording, is a flow list of repository names, `[<repo>, ...]`, each with a
  settings file in the standard's `profiles/` (`--profiles`, by default beside the ledger); a
  standard with no `profiles/` covers one repository and takes no `repos:` line.
- budget: for each repository the standard covers, one per `profiles/` file, or the ledger's one
  repository without them, the lines of the ledger as the build and review agents load it there,
  in `standard_file.sh`'s assembly (the session hook loads only live rules' wording): its text up
  to `## Candidates below the criteria`, less each `### R-NNN` or `### D-NNN` block whose `repos:`
  line leaves that repository out, and less every check-tier entry, which a tool enforces; with
  `--instructions`, each counted rule's non-blank wording lines too. The total is at most the
  `**Budget: N lines**` the ledger states, or the Rule budget Dial of `standards/dials.md` when it
  states none, since that Dial is the default a ledger's own figure overrides. Not run on
  `--entry` by default, one entry having no budget of its own.

Each failure is one line, `<check>: R-NNN: <what>`, or for the budget
`budget: <repository>: <what>`, the repository `ledger` for a standard without `profiles/`, and
every failure is printed. With `--checks` naming budget, each covered repository within its
budget is printed first too, `budget ok: <repository>: <total> of <limit> lines`, so a run in
which every repository fits says so; a run of all seven by default prints only failures. A block
whose `repos:` line is not a list of names is a budget failure on that block's id, no repository's budget is counted, and with `--changed` the failure fails
the run whichever rule is named. Exit 1 when a failure is on a rule `--changed` names, a budget failure
when a rule it counts is named, or on any failure when `--changed` is not given; 0 otherwise. Exit 2 with one `CANNOT RUN` line when an input file, the `## Review Rules` heading, or
git in `--repo` is missing, when the ledger holds no `### R-NNN` entry, when `--changed` names an
id the ledger does not hold or `--checks` a gate that is not one of the seven, when the Rule
budget Dial cannot be read with the ledger stating no budget, when a line opening
`**Budget` names a budget in another form than `**Budget: N lines**`, when `profiles/` holds no repository's file, when a
`--checks budget` is given with
`--entry`, or when a not-on
anchor is to be checked and `--repo` has no `origin/HEAD`. Under `--entry`, the drafted
wording's heading must carry the entry's id and title. Stdlib only.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

# The anchor and thread forms of an `example:` line, the one copy the contract test reads.
ANCHOR = re.compile(r'(?P<repo>[\w.-]+)#(?P<pr>\d+)@(?P<sha>[0-9a-f]{7,40}) (?P<path>[^\s:]+)::(?P<symbol>[\w.]+) "(?P<shape>[^"]+)"')
THREAD = re.compile(r"(?P<repo>[\w.-]+)#(?P<pr>\d+) (?P<thread>PRRT_[\w-]+)")
EXAMPLE = re.compile(r"^fires on (?P<fires>.+?); not on (?P<not_on>.+)$")
STATUSES = {"provisional", "established", "retired", "graduated"}
LIVE = {"provisional", "established"}
TIERS = {"reviewer", "check", "—"}
CHECKS = ("sync", "wording", "status", "scope", "anchors", "fields", "budget")
BUDGET = re.compile(r"\*\*Budget: (\d+) lines\*\*")
DIALS = Path(__file__).resolve().parents[1] / "standards" / "dials.md"
# `implements D-002`, `implements shared D-005`, `implements \`my_repo/D-006\``, `implements [D-002](decisions.md)`.
IMPLEMENTS = re.compile(r"\bimplements\s+(?:shared\s+)?(?:`|\[)?((?:[\w-]+/)?D-\d+)\b(?:`|\]\([^)]*\))?", re.I)
DECISION = re.compile(r"\b(?:[\w-]+/)?D-\d+\b")


class CannotRun(Exception):
    """An input the lint needs is missing."""


def load_counts():
    spec = importlib.util.spec_from_file_location("ratchet_counts", Path(__file__).with_name("ratchet_counts.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: lowercase, every character that is not a word character
    (a letter, a digit or `_`), a space or a hyphen removed, spaces to hyphens."""
    return re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-")


def wordings(text: str) -> dict[str, tuple[str, list[str]]]:
    """Each `### R-NNN · <title>` heading's title and its non-blank lines up to the next heading."""
    out = {}
    for m in re.finditer(r"^### (R-\d+)\b[ \t]*(?:·[ \t]*)?([^\n]*)\n(.*?)(?=^#{1,3} |\Z)", text, re.M | re.S):
        out[m.group(1)] = (m.group(2).strip(), [line for line in m.group(3).splitlines() if line.strip() and line.strip() != "---"])
    return out


def inline(entries: dict) -> dict[str, tuple[str, list[str]]]:
    """Each entry's title and its wording, the `> ` lines of its block with the marker removed,
    for the entries that hold any."""
    out = {}
    for rid, e in entries.items():
        lines = [re.sub(r"^>[ \t]?", "", line) for line in load_counts().unfenced(e["text"]).splitlines() if line.startswith(">")]
        lines = [line for line in lines if line.strip()]
        if lines:
            out[rid] = (e["title"], lines)
    return out


def decision_statuses(paths: list[Path]) -> dict[str, str | None]:
    """Each decision id, as a rule's evidence names it, with its status or None when unmarked."""
    out: dict[str, str | None] = {}
    for path in paths:
        out.update(statuses_in(path.read_text()))
    return out


def statuses_in(text: str) -> dict[str, str | None]:
    """decision_statuses for one decisions file's text."""
    out: dict[str, str | None] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^### ((?:[\w-]+/)?D-\d+)\b", line)
        if not m:
            continue
        following = next((x for x in lines[i + 1 :] if x.strip() and not x.startswith("repos:")), "")
        marked = re.search(r"\*\*(provisional|established)\b[^*\n]*\*\*", following, re.I)
        out[m.group(1)] = marked.group(1).lower() if marked else None
    return out


def budget_of(ledger: str) -> int:
    """The ledger's stated `**Budget: N lines**`, or the Rule budget Dial's default."""
    stated = BUDGET.search(ledger)
    if stated:
        return int(stated.group(1))
    other = re.search(r"^[ \t]*\*\*[ \t]*budget\b.*$", load_counts().unfenced(ledger), re.M | re.I)
    if other:
        raise CannotRun(f"the ledger names a budget as {other.group(0).strip()!r}, not as `**Budget: N lines**`")
    dial = re.search(r"^\| Rule budget \| (\d+) lines", DIALS.read_text() if DIALS.is_file() else "", re.M)
    if not dial:
        raise CannotRun(f"the ledger states no budget and {DIALS} has no Rule budget Dial")
    return int(dial.group(1))


def loaded(ledger: str, repo: str | None) -> list[tuple[str | None, bool, list[str]]]:
    """The ledger's blocks as `standard_file.sh` loads them for `repo`, or every block for None,
    up to the held candidates: each block's rule id or None, whether it is a check-tier entry,
    and its lines. A `repos:` line that is not a list of names raises ValueError with the block's
    id and the line, since which repositories load that block cannot be known."""
    counts = load_counts()
    plain = counts.unfenced(ledger)
    heads = [m.start() for m in re.finditer(r"^#{1,3} ", plain, re.M)]
    blocks = []
    for start, end in zip([0, *heads], [*heads, len(ledger)]):
        block, head = plain[start:end], plain[start:end].split("\n", 1)[0]
        if re.fullmatch(r"## Candidates below the criteria\s*", head):
            break
        m = re.match(r"### ([RD]-\d+)", head)
        tag = re.search(r"^repos:[ \t]*(\S.*?)[ \t]*$", block, re.M) if m else None
        names = counts.repos(tag.group(1)) if tag else None
        if tag and names is None:
            raise ValueError(m.group(1), tag.group(0).strip())
        if repo is not None and tag and repo.lower() not in names:
            continue
        rid = m.group(1) if m and m.group(1).startswith("R-") else None
        blocks.append((rid, bool(m and re.search(r"\btier:\s*\**check\b", block)), ledger[start:end].splitlines()))
    return blocks


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def definition(text: str, symbol: str) -> str | None:
    """The source of `symbol` in a file's text, a function or class, `Class.method` for a method:
    from its `def` or `class` line up to the next line indented no deeper that does not close a
    bracket or open a comment. Each name is the least indented definition of it in the text or
    the class around it, so a module's function is not taken for a method of the same name. None
    when the text defines no such name."""
    for name in symbol.split("."):
        found = list(re.finditer(rf"^([ \t]*)(?:async[ \t]+)?(?:def|class)[ \t]+{re.escape(name)}\b", text, re.M))
        if not found:
            return None
        m = min(found, key=lambda f: len(f.group(1).expandtabs()))
        depth = len(m.group(1).expandtabs())
        lines = text[m.start() :].splitlines(keepends=True)
        end = 1
        while end < len(lines):
            line = lines[end]
            if line.strip() and not line.lstrip().startswith((")", "]", "}", "#")) and len(line.expandtabs()) - len(line.expandtabs().lstrip()) <= depth:
                break
            end += 1
        text = "".join(lines[:end])
    return text


class Lint:
    def __init__(self, repo: Path, decisions: dict[str, str | None], profiles: Path | None = None):
        self.repo = repo
        self.decisions = decisions
        self.profiles = profiles
        self.failures: list[tuple[str, str, str]] = []
        self.counted: dict[str, set[str]] = {}
        self.fits: list[str] = []
        self.default: str | None = None
        files = git(repo, "ls-files")
        if files.returncode:
            raise CannotRun(f"git in {repo}: {files.stderr.strip()}")
        self.files = files.stdout.splitlines()

    def default_branch(self) -> str:
        """`origin/HEAD`'s branch, which a not-on anchor's sha must be on."""
        if self.default is None:
            head = git(self.repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
            if head.returncode:
                raise CannotRun(f"no origin/HEAD in {self.repo} to check a not-on anchor against; `git remote set-head origin --auto` sets it")
            self.default = head.stdout.strip()
        return self.default

    def fail(self, check: str, rid: str, what: str) -> None:
        self.failures.append((check, rid, what))

    def duplicates(self, ledger: str, wording: str) -> None:
        for text, what in ((ledger, "ledger entries"), (wording, "wording headings")):
            ids = re.findall(r"^### (R-\d+)\b", text, re.M)
            for rid in sorted({i for i in ids if ids.count(i) > 1}):
                self.fail("sync", rid, f"{ids.count(rid)} {what}")

    def sync_inline(self, entries: dict, words: dict) -> None:
        for rid, e in entries.items():
            if e["tier"] == "reviewer" and e["status"] in LIVE:
                if rid not in words:
                    self.fail("sync", rid, "no wording: no `> ` lines in the entry")
            elif rid in words and e["status"] == "retired":
                self.fail("sync", rid, "a retired rule has wording")
            elif rid in words and e["status"] != "graduated" and e["tier"] != "check":
                self.fail("sync", rid, f"a {e['tier']}-tier, {e['status']} rule has wording")

    def sync(self, entries: dict, words: dict) -> None:
        for rid in inline(entries):
            if rid in words:
                self.fail("sync", rid, "wording in the entry and in the instruction file; it lives in one place")
            else:
                self.fail("sync", rid, "wording in the entry, but this ledger keeps its wording in the instruction file")
        for rid, e in entries.items():
            if e["tier"] == "reviewer" and e["status"] in LIVE:
                if rid not in words:
                    self.fail("sync", rid, "no wording heading")
                    continue
                if words[rid][0] != e["title"]:
                    self.fail("sync", rid, f"the wording heading's title is {words[rid][0]!r}, the ledger's {e['title']!r}")
                link = re.search(r"^Wording:.*\]\([^)#]*#([^)]+)\)", e["text"], re.M)
                anchor = slug(f"{rid} · {words[rid][0]}")
                if not link:
                    self.fail("sync", rid, "no Wording: link")
                elif link.group(1) != anchor:
                    self.fail("sync", rid, f"the Wording: link ends #{link.group(1)}, the heading's anchor is #{anchor}")
            elif rid in words and e["status"] == "retired":
                self.fail("sync", rid, "a retired rule has a wording heading")
            elif rid in words and e["status"] != "graduated" and e["tier"] != "check":
                self.fail("sync", rid, f"a {e['tier']}-tier, {e['status']} rule has a wording heading")
        for rid in words:
            if rid not in entries:
                self.fail("sync", rid, "a wording heading with no ledger entry")

    def wording(self, rid: str, lines: list[str]) -> None:
        if not 2 <= len(lines) <= 4:
            self.fail("wording", rid, f"{len(lines)} lines, not two to four")
        for line in lines:
            m = re.search(r"#\d+|\bpr-\d{4}\b|PRRT_", line)
            if m:
                self.fail("wording", rid, f"names {m.group(0)}")
                break

    def status(self, rid: str, e: dict) -> None:
        if e["tier"] not in TIERS:
            self.fail("status", rid, f"tier {e['tier']!r} is not reviewer, check or —")
        if e["status"] not in STATUSES:
            self.fail("status", rid, f"status {e['status']!r} is not provisional, established, retired or graduated")
        read = []
        for m in IMPLEMENTS.finditer(e["evidence"]):
            read.append(m.span())
            did = m.group(1)
            if did not in self.decisions:
                self.fail("status", rid, f"implements {did}, which no decisions file holds")
            elif self.decisions[did] and self.decisions[did] != e["status"]:
                self.fail("status", rid, f"{e['status']}, but implements {did}, which is {self.decisions[did]}")
        for m in DECISION.finditer(e["evidence"]):
            if not any(a <= m.start() < b for a, b in read):
                self.fail("status", rid, f"names {m.group(0)} outside an `implements <id>`")
        for m in IMPLEMENTS.finditer(e["text"]):
            if m.group(0) not in e["evidence"]:
                self.fail("status", rid, f"{m.group(0)} is off the status line, which is never wrapped")
        if re.search(r"needs a second", e["text"], re.I) and e["status"] != "provisional":
            self.fail("status", rid, f"a needs-a-second marker on a rule that is {e['status']}")

    def scope(self, rid: str, e: dict) -> None:
        if "scope" not in e:
            return
        for glob in (g.strip() for g in e["scope"].split(",")):
            if not glob:
                self.fail("scope", rid, "the scope: line holds an empty glob")
            elif re.fullmatch(r"[*/]+", glob):
                self.fail("scope", rid, f"{glob} matches every file; name the paths the rule is about")
            elif not any(fnmatch.fnmatchcase(f, glob) for f in self.files):
                self.fail("scope", rid, f"{glob} matches no tracked file")

    def anchor(self, rid: str, text: str, merged: bool) -> re.Match | None:
        """Check one anchor; `merged` for the not-on half, whose sha must be the cited pull
        request's merge on the default branch. Returns the parsed anchor, or None when it is not one."""
        m = ANCHOR.fullmatch(text.strip())
        if not m:
            self.fail("anchors", rid, f"not an anchor: {text.strip()}")
            return None
        shown = git(self.repo, "show", f"{m['sha']}:{m['path']}")
        if shown.returncode:
            self.fail("anchors", rid, f"{m['sha']}:{m['path']} does not resolve")
            return m
        body = definition(shown.stdout, m["symbol"])
        if body is None:
            self.fail("anchors", rid, f"no def or class {m['symbol']} in {m['path']} at {m['sha']}")
        elif m["shape"] not in body:
            self.fail("anchors", rid, f'"{m["shape"]}" is not in {m["symbol"]} in {m["path"]} at {m["sha"]}')
        if merged:
            branch = self.default_branch()
            subject = git(self.repo, "log", "-1", "--format=%s", m["sha"]).stdout.strip()
            if git(self.repo, "merge-base", "--is-ancestor", m["sha"], branch).returncode:
                self.fail("anchors", rid, f"{m['sha']} is not on {branch}")
            elif not re.search(rf"\(#{m['pr']}\)|^Merge pull request #{m['pr']}\b", subject):
                self.fail("anchors", rid, f"{m['sha']} is not #{m['pr']}'s merge; its subject is {subject!r}")
        return m

    def anchors(self, rid: str, e: dict) -> None:
        if "example" not in e:
            return
        m = EXAMPLE.match(e["example"])
        if not m:
            self.fail("anchors", rid, "the example line is not one line, `fires on <anchor or thread>; not on <anchor>`")
            return
        fires = None if THREAD.fullmatch(m["fires"].strip()) else self.anchor(rid, m["fires"], merged=False)
        not_on = self.anchor(rid, m["not_on"], merged=True)
        where = ("sha", "path", "symbol", "shape")
        if fires and not_on and fires.group(*where) == not_on.group(*where):
            self.fail("anchors", rid, "the fires-on and not-on halves are the same place")

    def fields(self, rid: str, e: dict, always: bool) -> None:
        if always or (e["tier"] == "reviewer" and e["status"] in LIVE):
            for field in ("scope", "example"):
                if field not in e:
                    self.fail("fields", rid, f"no {field}: line")
        self.tags(rid, e["text"])

    def tags(self, rid: str, text: str) -> None:
        """A block's `repos:` line: at most one, a list of names, each with a profiles/ file."""
        lines = [line for line in load_counts().unfenced(text).splitlines() if line.startswith("repos:")]
        if len(lines) > 1:
            self.fail("fields", rid, f"{len(lines)} repos: lines; a block takes one")
        if not lines:
            return
        tag = lines[0][len("repos:"):].strip()
        names = load_counts().repos(tag)
        if names is None:
            self.fail("fields", rid, f"repos: {tag} is not a list of repository names such as [my_repo]")
        elif self.profiles is None or not self.profiles.is_dir():
            self.fail("fields", rid, "a repos: line in a standard with no profiles/, which covers one repository")
        else:
            covered = {p.stem.lower() for p in self.profiles.glob("*.yaml")}
            for name in names:
                if name not in covered:
                    self.fail("fields", rid, f"repos: names {name}, which has no profiles/{name}.yaml")


    def budget(self, ledger: str, words: dict, instructions: bool) -> None:
        """Each covered repository's loaded lines against the ledger's budget."""
        limit = budget_of(ledger)
        covered = sorted(p.stem for p in self.profiles.glob("*.yaml")) if self.profiles and self.profiles.is_dir() else [None]
        if not covered:
            raise CannotRun(f"{self.profiles} holds no repository's file, so no repository's budget can be counted")
        try:
            loaded(ledger, None)
        except ValueError as e:
            rid, line = e.args
            self.fail("budget", rid, f"{line} is not a list of names, so no repository's budget is counted")
            # Uncounted, the budget could be over anywhere: any rule a run names fails it.
            self.counted[rid] = set(re.findall(r"^### (R-\d+)\b", load_counts().unfenced(ledger), re.M))
            return
        for repo in covered:
            blocks = [b for b in loaded(ledger, repo) if not b[1]]
            kept = {rid for rid, _, _ in blocks if rid}
            total = sum(len(lines) for _, _, lines in blocks) + (sum(len(words[r][1]) for r in kept if r in words) if instructions else 0)
            label = repo or "ledger"
            self.counted[label] = kept
            if total > limit:
                self.fail("budget", label, f"{total} lines over a budget of {limit}; retire, merge or narrow a rule, or raise the budget in the ledger's header with the reason")
            else:
                self.fits.append(f"budget ok: {label}: {total} of {limit} lines")


def fixture_repo(fixture: Path, dest: Path) -> Path:
    """Build the `tests/fixtures/rule-bar/` repository under `dest`, for the tests and
    `check_static.py`'s rule-bar check: one commit holding `pkg/loader.py`, its subject naming
    pull request #2 as a squash merge's does, on `main`, which `origin/HEAD` points at as in a
    clone; and the ledger with `{sha}` replaced by that commit. Returns `dest`, which holds
    `review-rules.md`, `instructions.md` and `decisions.md` beside the repository's own files."""
    (dest / "pkg").mkdir(parents=True)
    (dest / "pkg" / "loader.py").write_text((fixture / "loader.py").read_text())
    for args in (
        ["init", "-q"],
        # No background maintenance after a commit: a detached one can still be writing into
        # .git when a test removes the repository.
        ["config", "maintenance.auto", "false"],
        ["config", "gc.auto", "0"],
        ["add", "pkg"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "Load and read a path (#2)"],
        ["update-ref", "refs/remotes/origin/main", "HEAD"],
        ["symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"],
    ):
        subprocess.run(["git", "-C", str(dest), *args], check=True, capture_output=True)
    sha = git(dest, "rev-parse", "--short=7", "HEAD").stdout.strip()
    (dest / "review-rules.md").write_text((fixture / "review-rules.md").read_text().replace("{sha}", sha))
    for name in ("instructions.md", "decisions.md"):
        (dest / name).write_text((fixture / name).read_text())
    return dest


def run(args) -> int:
    parse_entries = load_counts().parse_entries
    checks = {c.strip() for c in args.checks.split(",")} if args.checks else set(CHECKS)
    for c in checks - set(CHECKS):
        raise CannotRun(f"--checks names {c!r}, which is not one of {', '.join(CHECKS)}")
    if args.entry and args.checks and "budget" in checks:
        raise CannotRun("--checks budget reads a whole ledger; give --ledger, not --entry")
    for path in [*(args.decisions or []), *([args.entry] if args.entry else [args.ledger, *([args.instructions] if args.instructions else [])])]:
        if path is None or not path.is_file():
            raise CannotRun(f"no file {path}")
    profiles = args.profiles or (args.ledger.parent / "profiles" if args.ledger else None)
    lint = Lint(args.repo, decision_statuses(args.decisions or []), profiles)
    if args.entry and len(re.findall(r"^### R-\d+", args.entry.read_text(), re.M)) == 1:
        entries = parse_entries(args.entry.read_text(), args.entry.name)
        words = inline(entries)
        if "sync" in checks:
            lint.sync_inline(entries, words)
    elif args.entry:
        text = args.entry.read_text()
        heads = [m.start() for m in re.finditer(r"^### R-\d+", text, re.M)]
        if not heads:
            raise CannotRun(f"{args.entry} holds no ### R-NNN entry")
        if len(heads) < 2:
            raise CannotRun(f"{args.entry} holds no wording heading after its entry")
        entries = parse_entries(text[: heads[1]], args.entry.name)
        words = wordings(text[heads[1] :])
        (rid, entry), = entries.items()
        if "sync" not in checks:
            pass
        elif list(words) != [rid]:
            lint.fail("sync", rid, f"the drafted wording is under {', '.join(words)}, not {rid}")
        elif words[rid][0] != entry["title"]:
            lint.fail("sync", rid, f"the drafted wording's title is {words[rid][0]!r}, the entry's {entry['title']!r}")
    elif not args.instructions:
        entries = parse_entries(args.ledger.read_text(), args.ledger.name)
        if not entries:
            raise CannotRun(f"{args.ledger} holds no ### R-NNN entry")
        words = inline(entries)
        if "sync" in checks:
            lint.duplicates(args.ledger.read_text(), "")
            lint.sync_inline(entries, words)
        if "budget" in checks:
            lint.budget(args.ledger.read_text(), words, instructions=False)
    else:
        instructions = args.instructions.read_text()
        section = re.search(r"^## Review Rules\s*$(.*?)(?=^## |\Z)", instructions, re.M | re.S)
        if not section:
            raise CannotRun(f"no ## Review Rules heading in {args.instructions}")
        entries = parse_entries(args.ledger.read_text(), args.ledger.name)
        if not entries:
            raise CannotRun(f"{args.ledger} holds no ### R-NNN entry")
        words = wordings(section.group(1))
        if "sync" in checks:
            lint.duplicates(args.ledger.read_text(), section.group(1))
            lint.sync(entries, words)
        if "budget" in checks:
            lint.budget(args.ledger.read_text(), words, instructions=True)
    if "fields" in checks:
        for path in args.decisions or []:
            for m in re.finditer(r"^### (D-\d+)\b.*?(?=^#{1,3} |\Z)", load_counts().unfenced(path.read_text()), re.M | re.S):
                lint.tags(m.group(1), m.group(0))
    for rid, e in entries.items():
        if "wording" in checks and rid in words and e["tier"] == "reviewer" and e["status"] in LIVE:
            lint.wording(rid, words[rid][1])
        if "status" in checks:
            lint.status(rid, e)
        if "scope" in checks:
            lint.scope(rid, e)
        if "anchors" in checks:
            lint.anchors(rid, e)
        if "fields" in checks:
            lint.fields(rid, e, always=bool(args.entry))
    changed = {c.strip() for c in args.changed.split(",")} if args.changed else None
    for c in changed or ():
        if not re.fullmatch(r"R-\d+", c) or c not in entries:
            raise CannotRun(f"--changed names {c!r}, which is not an R-NNN id the ledger holds")
    if args.checks and "budget" in checks:
        for line in lint.fits:
            print(line)
    for check, rid, what in lint.failures:
        print(f"{check}: {rid}: {what}")
    return 1 if any(changed is None or rid in changed or (changed & lint.counted.get(rid, set()) if check == "budget" else False) for check, rid, _ in lint.failures) else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ledger", type=Path, help="the repository's standards/review-rules.md")
    p.add_argument("--instructions", type=Path, help="for a ledger whose wording is still in an instruction file: the file whose ## Review Rules section holds it")
    p.add_argument("--repo", type=Path, default=Path("."), help="the repository git ls-files and git show run in")
    p.add_argument("--decisions", type=Path, action="append", help="a decisions.md; repeat for the repository's and the shared one")
    p.add_argument("--changed", help="R-NNN[,R-NNN...]: the rules whose failures fail the run")
    p.add_argument("--entry", type=Path, help="one drafted entry and its wording, in place of --ledger")
    p.add_argument("--profiles", type=Path, help="the standard's profiles/ directory, by default beside --ledger")
    p.add_argument("--checks", help=f"{','.join(CHECKS)}: the gates to run, by default all seven")
    args = p.parse_args(argv)
    if not args.entry and args.ledger is None:
        p.error("give --ledger, or --entry")
    try:
        return run(args)
    except (CannotRun, ValueError) as e:
        print(f"CANNOT RUN: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
