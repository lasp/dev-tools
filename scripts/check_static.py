#!/usr/bin/env python3
"""Check the plugin's text against its own files, with no model calls.

Sixteen checks, each failure printed as `<check>: <file>: <what>`:

- frontmatter: every skill and agent opens with a frontmatter block whose keys Claude Code
  documents, whose `name` matches its directory or file, and whose description is not empty; an
  agent's `model`, `tools`, `disallowedTools` and `skills` name things that exist, each `skills`
  entry written `<plugin>:<skill>`, the plugin's name read from `.claude-plugin/plugin.json`.
- references: what a skill or agent names resolves: `/<plugin>:<skill>`, a path under
  `${CLAUDE_SKILL_DIR}` or `${CLAUDE_PLUGIN_ROOT}`, a `scripts/` or `hooks/` path, an agent by
  its role suffix (`-reviewer`, `-reader`, ...), and a flag given after one of the plugin's
  scripts, which must appear in that script.
- plugin-vars: no file under `skills/` or `agents/` but a `SKILL.md` or an agent names
  `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_SKILL_DIR}`, since Claude Code expands them only there; a
  support file writes `<plugin root>/...`, each such path must exist, and the skill that reads it
  says where that is; and a file that writes a `<standard>/...` path says the directory is what
  `profile.py --standard` prints.
- review-map: every `.review/` path the skills, agents, hooks and scripts name has a row in the
  README's `.review/` table, and every row names its writer and reader.
- copilot-links: every skill has its symlink `.github/skills/<name>` and every agent its
  `.github/agents/<name>.agent.md`, each resolving to that skill's directory or agent's file, and
  no link there names anything else.
- readme-skills: in the README's "What is included", every skill has a row in the skills table
  whose Started reads `hidden` for a skill marked `user-invocable: false` and `typed only` or
  `typed or asked` otherwise; the list above the table names exactly the skills not so marked;
  every name in either is a skill.
- round-trip: `record.py` builds records from the test fixtures, their review bodies and
  conversation comments read back from the `reviews:` and `comments:` pointers by id, login and
  authorship, including a settled contest, an open one, an unanswered and an unparsed finding,
  and `ratchet_counts.py` reads them back, each placed in a window by its `merged:` line, with
  the same keys, verdicts and contested flags the records carry.
- contract: the review summary and the finding comment `pr-review` "The review" shows, and the
  severity example in `comment-style.md`, parse with `record.py` as the record reads them, so a
  wording edit on either side fails; `pr-reader`'s "The dump" names the dump's four JSON files.
- body: the Already checked block in `pr-create/body.md` carries every line `record.py`'s
  `REQUIRED_LINES` and `OPTIONAL_LINES` name.
- sections: a reference to a section of a skill or document, `` `<name>` "<Section>" ``,
  `` `<name>`'s "<Section>" ``, `` `<name>`, "<Section>" ``, `the README's "<Section>"`,
  `the README, "<Section>"`, `the corpus README's "<Section>"` or `the corpus README, "<Section>"`,
  across line breaks, names a heading that file has, in the skills, agents and documents.
  `<name>` is a skill, a document, or any `.md` path that exists from the top level or from the
  citing file's directory, with `${CLAUDE_PLUGIN_ROOT}/` read as the top level and
  `${CLAUDE_SKILL_DIR}/` as the citing skill's directory; a `<summary>` label counts as a heading,
  and so does a row of `standards/dials.md`.
- paths: in the documents, every backticked path under `skills/`, `agents/`, `scripts/`,
  `hooks/`, `docs/`, `tests/`, `sandbox/` or `standards/` exists, placeholders and
  globs skipped, and paths in an adopting repository (`IN_ADOPTING_REPO`) exempt; every relative markdown link
  outside code names a file that exists and, with a `#anchor`, a heading of that file.
- dials: in the skills, agents and documents, a Dial named as `the <Row> Dial`, with the row's
  capital, two or more joined by commas, `or` or `and` before `Dial` or `Dials`, or as
  `"<Row>" threshold`, is a row of `standards/dials.md`, with or without its parenthetical.
- profiles: the default profile, `standards/default-profile.yaml`, passes `profile.py`, each of its
  `depth.light` briefs is a file in `skills/implement-change/reviews/`, and
  `standards/profile.example.yaml` has exactly the keys `profile.py` knows.
- contracts: every section of `docs/contracts.md` has a `Pinned by: <test file>::<test name>`
  line whose file exists and contains the named test.
- rule-bar: `rule_lint.py` passes the fixture in `tests/fixtures/rule-bar/`, built as its test
  builds it, and fails a copy whose `example:` line quotes a shape the code does not hold, so the
  script and its fixture cannot drift apart silently; `revise`, its `correct.md` and
  `onboard`'s `first-rules.md` name `rule-bar.md`, `revise` and its `harvest.md` name `rule-probe`,
  and `prepare.md` and `first-rules.md` name `harvest.md`.
- coupling: in each file under `skills/`, `agents/`, `hooks/`, `scripts/` and `standards/`, outside
  `__pycache__/` and the paths `scripts/coupling.json`'s `mission` lists, the matches of its
  `patterns`, the mentions, number exactly the file's entry in its `counts`, or none for a file
  with no entry. A `mission` directory leaves out every file under it but a `README.md` directly
  in it, which says the format its entries follow. A file above its count fails until the new
  mention goes, or, for a file with no entry, until its old entry moves by hand if it moved or its
  path joins `mission` if it is mission content; the failure names an entry gone from the scan
  with the same count. A file below its count fails until the count is lowered, so the baseline
  tightens as mentions are removed. A `mission` path that does not exist, a directory written
  without a trailing `/` or a file with one, or a path under another `mission` directory, fails. The total goes to stderr.

`--update-coupling` runs only the coupling scan and rewrites `counts` from the tree, sorted, then
prints the total; it refuses, writing nothing, when any file is above its count, so a count rises
only by a hand edit a reviewer sees.

Exit 0 when nothing fails, 1 otherwise. Stdlib only, so CI needs no environment.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import importlib.util
import io
import json
import re
import sys
import tempfile
from pathlib import Path

SKILL_KEYS = {
    "name", "description", "argument-hint", "disable-model-invocation", "user-invocable", "metadata",
    "allowed-tools", "model", "context", "agent", "hooks", "license", "effort", "paths", "shell",
}
AGENT_KEYS = {
    "name", "description", "tools", "disallowedTools", "model", "skills", "isolation", "color",
    "maxTurns", "memory", "effort", "background",
}
MODELS = {"sonnet", "opus", "haiku", "fable", "inherit"}
TOOLS = {
    "Read", "Write", "Edit", "Bash", "Grep", "Glob", "Agent", "ToolSearch", "TodoWrite", "NotebookEdit",
    "Skill", "WebFetch", "WebSearch", "ListMcpResourcesTool", "ReadMcpResourceTool", "AskUserQuestion",
    "EnterPlanMode", "ExitPlanMode",
}
# An agent is named by its role; a backticked or bold name ending in one of these must be an agent.
AGENT_SUFFIXES = ("-reviewer", "-reader", "-planner", "-runner", "-investigator", "-describer", "-locator", "-probe")
SCRIPT = re.compile(r"\b([\w-]+\.(?:py|sh))\b")
PLACEHOLDER = re.compile(r"<[^>]+>|NNNN|YYYY-MM-DD")
# The README skills table's Started values for a skill a person types.
TYPED = {"typed only", "typed or asked"}


def frontmatter(text: str) -> dict | None:
    """The top-level keys of a leading `---` block, with scalar, folded and list values."""
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return None
    block = lines[1 : lines.index("---", 1)]
    out: dict = {}
    key = None
    for line in block:
        m = re.match(r"([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                out[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
            elif value in (">", "|", ">-", "|-", ""):
                out[key] = "" if value else None
            else:
                out[key] = value
        elif key and line.strip().startswith("- "):
            out[key] = (out[key] if isinstance(out[key], list) else []) + [line.strip()[2:].strip()]
        elif key and line.strip() and isinstance(out.get(key), str):
            out[key] = (out[key] + " " + line.strip()).strip()
        elif key and line.strip() and out.get(key) is None:
            out[key] = {}
    return out


# `<name>` "<Section>" or `<name>`'s "<Section>": a reference to a section of a skill or document.
SECTION_REF = re.compile(r"`([\w./${}-]+)`(?:'s|,)?\s+\"([^\"]+?)\"")
# The README named in words: the top-level one, or the corpus's.
README_REF = re.compile(r"(?<![Cc]orpus )\b[Tt]he\s+README(?:'s|,)\s+\"([^\"]+?)\"")
CORPUS_README_REF = re.compile(r"[Tt]he\s+corpus\s+README(?:'s|,)\s+\"([^\"]+?)\"")
# A markdown link, `[text](path#anchor)`; one with a scheme, such as https:, is not checked.
LINK = re.compile(r"\]\(([^)\s]+)\)")
# `the Admission Dial`, `the Low agree rate or Established expiry Dial`, `"Recurring ask" threshold`.
DIAL_NAME = r"[A-Z][\w-]*(?:\s+[a-z][\w-]*)*"
DIAL_JOIN = r",\s+(?:or\s+|and\s+)?|\s+(?:or|and)\s+"
DIAL_NAMED = re.compile(rf"\b[Tt]he\s+({DIAL_NAME}(?:(?:{DIAL_JOIN}){DIAL_NAME})*)\s+Dials?\b")
DIAL_QUOTED = re.compile(r"\"([^\"]+?)\"\s+threshold\b")
PATH_REF = re.compile(r"`((?:skills|agents|scripts|hooks|docs|tests|sandbox|standards)/[^`\s]*)")
# Paths the documents name in an adopting repository, not in this plugin.
IN_ADOPTING_REPO = {
    "standards/review-rules.md",  # each adopting repository's ledger
    "standards/decisions.md",  # each adopting repository's own decisions
    "standards/agent-guidance.md",  # each adopting repository's own agent guidance
    "standards/data-conventions.md",  # each adopting repository's own data conventions
    "standards/evidence.yaml",  # the pull requests each rule fired on, as the ROADMAP plans
    "standards/profiles/",  # each repository's settings in a standard for several
    "standards/archive/",  # the archive a repository would keep for itself, as the ROADMAP plans
    "standards/profile.yaml",  # a repository's facts, as the ROADMAP plans
    "standards/log/",  # a repository's review records, as the ROADMAP plans
}
# The coupling count's patterns, excluded paths and per-file baseline, which the scan skips.
COUPLING = "scripts/coupling.json"
# The generic plugin files the coupling count scans. docs/, sandbox/, tests/, README.md, GUIDE.md and .github/ are documentation,
# fixtures and tests, rewritten with the scenario packs and the rename.
GENERIC = ("skills", "agents", "hooks", "scripts", "standards")


def moved_hint(rel: str, spec: dict, counts: dict[str, int]) -> str:
    """For a file with mentions and no entry: move an entry by hand if the file moved, naming
    the first entry gone from the scan with the same count, or list it in `mission`."""
    gone = [old for old, n in sorted(spec["counts"].items()) if n == counts[rel] and old not in counts]
    moved = f"if it moved from {gone[0]}, move that entry by hand" if gone else "if it moved, move its old entry by hand"
    return f"{moved}; if it is mission content, add its path to `mission` with why"


def normal(heading: str) -> str:
    """A heading compared case aside, bold markers and a leading step number stripped."""
    return re.sub(r"^\d+\.\s+", "", heading.replace("**", "").strip()).casefold()


def headings(text: str) -> list[tuple[int, int, str]]:
    """Each heading outside a fenced block, as (line index, level, text)."""
    out, fenced = [], False
    for i, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and (m := re.match(r"(#+)\s+(.+?)\s*$", line)):
            out.append((i, len(m.group(1)), m.group(2)))
    return out


def heading_set(text: str) -> set[str]:
    return {normal(h) for _, _, h in headings(text)}


def anchors(text: str) -> set[str]:
    """The `#anchor`s GitHub gives a file's headings: lower case, punctuation dropped, spaces as
    hyphens, and `-1`, `-2` ... after a repeat."""
    out: set[str] = set()
    for _, _, h in headings(text):
        slug = re.sub(r"[^\w\- ]", "", h.casefold()).replace(" ", "-")
        n = 0
        while (f"{slug}-{n}" if n else slug) in out:
            n += 1
        out.add(f"{slug}-{n}" if n else slug)
    return out


def prose_only(text: str) -> str:
    """The text with its fenced blocks and inline code spans blanked, line count kept."""
    lines, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            lines.append("")
        else:
            lines.append("" if fenced else re.sub(r"`[^`]*`", "", line))
    return "\n".join(lines)


def dial_rows(text: str) -> set[str]:
    """The row names of the Dials table, each with and without its parenthetical, case aside."""
    rows = set()
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0] not in ("Dial", "") and not set(cells[0]) <= set("-: "):
            rows |= {cells[0].casefold(), re.sub(r"\s*\(.*\)$", "", cells[0]).casefold()}
    return rows


def section_text(text: str, heading: str) -> str | None:
    """The text under a heading, up to the next heading of the same or a higher level."""
    lines, found = text.splitlines(keepends=True), headings(text)
    start = next(((i, level) for i, level, h in found if h == heading), None)
    if start is None:
        return None
    end = next((i for i, level, _ in found if i > start[0] and level <= start[1]), len(lines))
    return "".join(lines[start[0] + 1 : end])


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return value
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


class Plugin:
    def __init__(self, root: Path):
        self.root = root
        self.name = json.loads((root / ".claude-plugin/plugin.json").read_text())["name"]
        self.skills = {p.parent.name: p for p in sorted(root.glob("skills/*/SKILL.md"))}
        self.agents = {p.stem: p for p in sorted(root.glob("agents/*.md"))}
        self.scripts = {p.name: p for d in ("scripts", "hooks") for p in sorted((root / d).glob("*")) if p.is_file()}
        self.failures: list[str] = []
        self.coupling_total: int | None = None

    def fail(self, check: str, path: Path, what: str) -> None:
        self.failures.append(f"{check}: {path.relative_to(self.root)}: {what}")

    def check_frontmatter(self) -> None:
        for name, path in self.skills.items():
            fm = frontmatter(path.read_text())
            if fm is None:
                self.fail("frontmatter", path, "no frontmatter block")
                continue
            for k in sorted(set(fm) - SKILL_KEYS):
                self.fail("frontmatter", path, f"unknown key {k!r}")
            if fm.get("name") != name:
                self.fail("frontmatter", path, f"name {fm.get('name')!r} is not the directory name {name!r}")
            if not fm.get("description"):
                self.fail("frontmatter", path, "empty description")
        for name, path in self.agents.items():
            fm = frontmatter(path.read_text())
            if fm is None:
                self.fail("frontmatter", path, "no frontmatter block")
                continue
            for k in sorted(set(fm) - AGENT_KEYS):
                self.fail("frontmatter", path, f"unknown key {k!r}")
            if fm.get("name") != name:
                self.fail("frontmatter", path, f"name {fm.get('name')!r} is not the file name {name!r}")
            if not fm.get("description"):
                self.fail("frontmatter", path, "empty description")
            if fm.get("model") not in MODELS:
                self.fail("frontmatter", path, f"model {fm.get('model')!r} is not one of {sorted(MODELS)}")
            for key in ("tools", "disallowedTools"):
                for tool in as_list(fm.get(key)):
                    # A permission-rule form such as Bash(git log:*) names the tool before the parenthesis.
                    if tool.split("(", 1)[0] not in TOOLS and not tool.startswith("mcp__"):
                        self.fail("frontmatter", path, f"{key} names unknown tool {tool!r}")
            for skill in as_list(fm.get("skills")):
                plugin, _, name = skill.rpartition(":")
                if plugin != self.name:
                    # A bare name another loaded plugin shares preloads that plugin's skill, unwarned.
                    self.fail("frontmatter", path, f"skills names {skill!r}; write it {self.name}:<skill>")
                elif name not in self.skills:
                    self.fail("frontmatter", path, f"skills names {skill!r}, which is not a skill here")

    def check_references(self) -> None:
        logins = self.load("record").BOT_LOGINS
        for path in [*self.skills.values(), *self.agents.values()]:
            text = path.read_text()
            for m in re.finditer(rf"/{re.escape(self.name)}:([\w-]+)", text):
                if m.group(1) not in self.skills:
                    self.fail("references", path, f"/{self.name}:{m.group(1)} is not a skill")
            for var, base in (("CLAUDE_SKILL_DIR", path.parent), ("CLAUDE_PLUGIN_ROOT", self.root)):
                for m in re.finditer(r"\$\{" + var + r"\}/([\w./<>-]+)", text):
                    rel = m.group(1).rstrip(".")
                    if PLACEHOLDER.search(rel):
                        continue
                    if not (base / rel).resolve().exists():
                        self.fail("references", path, f"${{{var}}}/{rel} does not exist")
            for m in re.finditer(r"(?<![\w./-])((?:scripts|hooks)/[\w.-]+\.(?:py|sh|json))", text):
                if not (self.root / m.group(1)).exists():
                    self.fail("references", path, f"{m.group(1)} does not exist")
            for m in re.finditer(r"(?:`|\*\*)([a-z]+(?:-[a-z]+)+)(?:`|\*\*)", text):
                name = m.group(1)
                if name.endswith(AGENT_SUFFIXES) and name not in self.agents and name not in logins:
                    self.fail("references", path, f"{name} reads as an agent, and there is no agents/{name}.md")
            for span in re.findall(r"`([^`\n]+)`", text):
                self.check_flags(path, span)

    def check_plugin_vars(self) -> None:
        expanded = {*self.skills.values(), *self.agents.values()}
        for path in sorted({*self.root.glob("skills/**/*"), *self.root.glob("agents/**/*")}):
            if path in expanded or not path.is_file():
                continue
            text = path.read_text(errors="replace")
            for var in sorted(set(re.findall(r"\$\{(CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR)\}", text))):
                self.fail("plugin-vars", path, f"${{{var}}} is expanded only in a SKILL.md or an agent")
            for rel in sorted(set(re.findall(r"<plugin root>/([\w./-]+[\w])", text))):
                if not (self.root / rel).exists():
                    self.fail("plugin-vars", path, f"<plugin root>/{rel} does not exist")
        for path in sorted({*self.root.glob("skills/**/*"), *self.root.glob("agents/**/*")}):
            text = path.read_text(errors="replace") if path.is_file() else ""
            if "<standard>/" in text and "--standard" not in text:
                self.fail("plugin-vars", path, "writes <standard>/ and does not say it is what profile.py --standard prints")

    def check_flags(self, path: Path, span: str) -> None:
        """Each flag after one of the plugin's scripts, in one code span, must appear in that script."""
        current = None
        for token in span.split():
            m = SCRIPT.search(token)
            if m and m.group(1) in self.scripts:
                current = m.group(1)
                continue
            if current and re.fullmatch(r"--[a-z][\w-]*", token.rstrip(",;:.")):
                flag = token.rstrip(",;:.")
                if not re.search(re.escape(flag) + r"(?![\w-])", self.scripts[current].read_text()):
                    self.fail("references", path, f"{current} has no {flag}")

    def review_rows(self) -> list[tuple[str, str, str]]:
        readme = (self.root / "README.md").read_text()
        m = re.search(r"^\| File in `\.review/` \|.*?\n\|[- |]+\|\n((?:\|.*\n)+)", readme, re.M)
        if not m:
            self.fail("review-map", self.root / "README.md", "no `.review/` table")
            return []
        rows = []
        for line in m.group(1).splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            files = re.findall(r"`([^`]+)`", cells[0])
            rows += [(f, cells[1], cells[2]) for f in files]
        return rows

    def check_review_map(self) -> None:
        rows = self.review_rows()
        patterns = []
        for f, writer, reader in rows:
            if not writer or not reader:
                self.fail("review-map", self.root / "README.md", f"`{f}` has no writer or no reader")
            rx = "[^/]+".join(re.escape(part) for part in PLACEHOLDER.split(f))
            patterns.append(re.compile(rx + (".*" if f.endswith("/") else "") + "$"))
        files = [*self.skills.values(), *self.agents.values()]
        files += [p for p in self.scripts.values() if p.exists() and p.suffix in (".py", ".sh")]
        files += sorted(self.root.glob("skills/*/*.md")) + sorted(self.root.glob("skills/*/*/*.md"))
        seen = set()
        for path in files:
            if path in seen:
                continue
            seen.add(path)
            text = path.read_text()
            for m in re.finditer(r"\.review/((?:[\w./-]|<[^>\n]*>)+)", text):
                mention = m.group(1).rstrip(".")
                # `.review/x` is quickstart's probe for whether .review/ is ignored.
                if mention in ("", "x"):
                    continue
                # A shell string built on, as `.review/implementation-plan-${x}.md`, is a prefix.
                prefix = text[m.end() : m.end() + 1] in ("$", "*", "{")
                sample = PLACEHOLDER.sub("X", mention)
                directory = sample.rstrip("/") + "/"
                matched = any(p.match(sample) for p in patterns) or any(
                    f.startswith(directory) or (prefix and PLACEHOLDER.sub("X", f).startswith(sample))
                    for f, _, _ in rows
                )
                if not matched:
                    self.fail("review-map", path, f".review/{mention} has no row in the README's `.review/` table")

    def check_copilot_links(self) -> None:
        want = {self.root / ".github/skills" / name: self.root / "skills" / name for name in self.skills}
        want |= {self.root / ".github/agents" / f"{name}.agent.md": path for name, path in self.agents.items()}
        for link, target in want.items():
            rel = f"../../{target.relative_to(self.root).as_posix()}"
            if not link.is_symlink():
                self.fail("copilot-links", link, f"is not a symlink to {rel}")
            elif link.resolve() != target.resolve():
                self.fail("copilot-links", link, f"links to {link.readlink()}, not {rel}")
        for d in (".github/skills", ".github/agents"):
            for link in sorted((self.root / d).glob("[!.]*")):
                if link not in want:
                    self.fail("copilot-links", link, "names no skill or agent")

    def check_readme_skills(self) -> None:
        readme = self.root / "README.md"
        section = section_text(readme.read_text(), "What is included") or ""
        m = re.search(r"^\| Group \| Skill \| Started \|.*\n\|[- |]+\|\n((?:\|.*\n)+)", section, re.M)
        if not m:
            self.fail("readme-skills", readme, '"What is included" has no skills table')
            return
        listed = set(re.findall(r"^- `([\w-]+)`:", section[: m.start()], re.M))
        rows = {}
        for line in m.group(1).splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 3:
                self.fail("readme-skills", readme, f"the skills table row {line.strip()!r} has no Started cell")
                continue
            rows |= {name: cells[2] for name in re.findall(r"`([\w-]+)`", cells[1])}
        hidden = {n for n, p in self.skills.items() if (frontmatter(p.read_text()) or {}).get("user-invocable") == "false"}
        for name in self.skills:
            if name not in rows:
                self.fail("readme-skills", readme, f"`{name}` has no row in the skills table")
            elif name in hidden and rows[name] != "hidden":
                self.fail("readme-skills", readme, f"`{name}` is user-invocable: false and Started reads {rows[name]!r}, not 'hidden'")
            elif name not in hidden and rows[name] not in TYPED:
                self.fail("readme-skills", readme, f"`{name}` is typed and Started reads {rows[name]!r}, not one of {sorted(TYPED)}")
        for name in sorted((listed | set(rows)) - set(self.skills)):
            self.fail("readme-skills", readme, f"`{name}` is not a skill")
        for name in sorted(set(self.skills) - hidden - listed):
            self.fail("readme-skills", readme, f"`{name}` is not in the list above the skills table")
        for name in sorted(listed & hidden):
            self.fail("readme-skills", readme, f"`{name}` is user-invocable: false and in the list above the skills table")

    def check_round_trip(self) -> None:
        record, counts = self.load("record"), self.load("ratchet_counts")
        tests = self.root / "tests"
        test_record = self.load("test_record", "tests")  # the fixtures' builders: PR, REVIEW, BODY, thread()
        cases = []
        pointed = 0
        for name, repo, sha in (("pr-0042", "o/r", "9f01488"), ("severity", "o/r", "abc1234")):
            d = tests / "fixtures" / name
            comments = json.loads((d / "comments.json").read_text())
            conversation = json.loads((d / "issue-comments.json").read_text())
            lines = record.build(
                test_record.merged_0042() if name == "pr-0042" else json.loads((d / "pr.json").read_text()),
                json.loads((d / "reviews.json").read_text()),
                comments["review_threads"], (d / "body.md").read_text(), repo, sha, issue_comments=conversation,
            )[0]
            cases.append(lines)
            # The comments: pointers carry each fixture comment's id, login and authorship.
            text = "\n".join(lines) + "\n"
            section = text.split("\ncomments:", 1)[1] if "\ncomments:" in text else ""
            got = re.findall(r"^  - comment: (\d+)\n    by: (\S+)\n    authorship: (\S+)$", section, re.M)
            want = sorted(
                (str(c["id"]), "bot" if record.is_bot(c["user"]["login"]) else c["user"]["login"],
                 record.authorship_of({"author": c["user"]["login"], "body": c["body"]}))
                for c in conversation
            )
            if sorted(got) != want:
                self.fail("round-trip", self.root / "scripts/record.py", f"the {name} record's comments: are {sorted(got)}, the dump's {want}")
            # The reviews: pointers carry each review body's id, login and authorship.
            reviews = json.loads((d / "reviews.json").read_text())
            findings = {r["id"] for r, _ in record.findings_reviews(reviews)}
            section = text.split("\nreviews:", 1)[1].split("\ncomments:", 1)[0] if "\nreviews:" in text else ""
            got = re.findall(r"^  - review: (\d+)\n    by: (\S+)\n    authorship: (\S+)$", section, re.M)
            want = sorted(
                (str(r["id"]), "bot" if record.is_bot(r["user"]["login"]) else r["user"]["login"],
                 record.authorship_of({"author": r["user"]["login"], "body": r["body"]}))
                for r in reviews
                if r["id"] not in findings and (r.get("body") or "").strip()
            )
            if sorted(got) != want:
                self.fail("round-trip", self.root / "scripts/record.py", f"the {name} record's reviews: are {sorted(got)}, the dump's {want}")
            pointed += len(want)
        if not pointed:
            self.fail("round-trip", tests / "fixtures", "no fixture has a review body to read back from a reviews: pointer")
        contested = test_record.thread(
            "Should fix", ("bob", "Agree."), ("carol", "Disagree, not here"), ("alice", "Disagree: carol is right")
        )
        cases.append(record.build(test_record.PR, [test_record.REVIEW], [contested], test_record.BODY, "o/r", "abc1234", issue_comments=[])[0])
        unsettled = [
            test_record.thread("Should fix"),
            test_record.thread("Should fix", ("bob", "Looks odd.")),
            test_record.thread("Should fix", ("bob", "Agree."), ("carol", "Disagree, not here")),
            test_record.thread("Should fix", ("bob", "Agree.")),
        ]
        # A severity label that is not one of the four, recorded `severity: unparsed`.
        unsettled[-1]["comments"][0]["body"] = unsettled[-1]["comments"][0]["body"].replace("**Should fix** — a finding", "**Suggestion — a finding**")
        for i, th in enumerate(unsettled):
            th["id"] = f"PRRT_u{i}"
            th["comments"][0]["body"] = th["comments"][0]["body"].replace("R-001/x.py::f", f"R-00{i + 1}/x.py::u")
        cases.append(record.build(test_record.PR, [test_record.REVIEW], unsettled, test_record.BODY, "o/r", "abc1234", issue_comments=[])[0])
        # A judged verdict counts as its word does; its basis sits after the verdict line it explains.
        judged = test_record.thread("Should fix", ("bob", "Yes, that's a bug."))
        judged["id"] = "PRRT_j"
        judgment = record.read_judged(
            [{"thread": "PRRT_j", "reply": 0, "verdict": "agree", "basis": "contested: true, it says"}], record.undecided([judged], "alice")
        )
        cases.append(record.build(test_record.PR, [test_record.REVIEW], [judged], test_record.BODY, "o/r", "abc1234", issue_comments=[], judged=judgment)[0])
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            want = {k: 0 for k in ("firings", "agree", "disagree", "discuss", "unanswered", "unlabeled", "open-contest", "contested")}
            column = {"unparsed": "unanswered", "contested": "open-contest"}
            for i, lines in enumerate(cases, 1):
                text = "\n".join(lines) + "\n"
                (log / f"pr-{i:04d}.yaml").write_text(text)
                section = text.split("\nfindings:", 1)[1].split("\nquestions:", 1)[0]
                for item in re.split(r"^  - key: ", section, flags=re.M)[1:]:
                    v = column.get(*[re.search(r"^    verdict: (\w+)$", item, re.M).group(1)] * 2)
                    if re.search(r"^    severity: unparsed$", item, re.M):
                        v = "unlabeled"
                    want["firings"] += 1
                    want[v] += 1
                    want["contested"] += v != "open-contest" and "\n    contested: true" in item
            try:
                # Under a window from the earliest date, every record is placed by its merged: line.
                table = counts.count(log, datetime.date.min)
            except ValueError as e:
                self.fail("round-trip", self.root / "scripts/ratchet_counts.py", f"cannot read record.py's output: {e}")
                return
            got = {k: sum(row[k] for row in table.values()) for k in want}
            if got != want:
                self.fail("round-trip", self.root / "scripts/ratchet_counts.py", f"counted {got}, the records carry {want}")

    def check_contract(self) -> None:
        reader = self.root / "agents/pr-reader.md"
        dump = section_text(reader.read_text(), "The dump") or "" if reader.is_file() else ""
        for name in ("pr.json", "reviews.json", "comments.json", "issue-comments.json"):
            if f"`{name}`" not in dump:
                self.fail("contract", reader, f'"The dump" does not name `{name}`')
        record = self.load("record")
        path = self.root / "skills/pr-review/SKILL.md"
        section = section_text(path.read_text(), "The review")
        blocks = re.findall(r"^```\n(.*?)^```", section or "", re.M | re.S)
        summary = next((b for b in blocks if "## Review" in b), None)
        comment = next((b for b in blocks if "**Should fix**" in b), None)
        if summary is None or comment is None:
            self.fail("contract", path, '"The review" has no summary block or no Should fix comment block')
            return
        summary = summary.replace("<full sha>", "a" * 40).replace("<sha, or none>", "abc1234").replace("<n>", "0")
        review = {"id": 1, "state": "COMMENTED", "body": summary.replace("@<github-login>", "@alice"), "submitted_at": "2026-01-01T00:00:00Z"}
        try:
            found = record.findings_reviews([review])
        except record.Unsupported as e:
            found = []
            self.fail("contract", path, f"the summary does not parse: {e}")
        if found != [(review, "a" * 40)]:
            self.fail("contract", path, "record.py does not read the summary as a findings review on its reviewed: sha")
        if record.standards_line(review) != "abc1234":
            self.fail("contract", path, "record.py does not read the summary's standards: line")
        trial = {**review, "body": review["body"].replace("standards: abc1234", "standards: abc1234 + uncommitted")}
        if record.standards_line(trial) != "abc1234 + uncommitted":
            self.fail("contract", path, "record.py does not read a standards: line ending + uncommitted")
        first = {"body": comment.replace("@<github-login>", "@alice"), "path": "x.py", "original_line": 1, "author": "alice", "created_at": "2026-01-01T00:00:00Z"}
        try:
            f = record.parse_finding({"id": "PRRT_contract", "comments": [first]})
        except record.Unsupported as e:
            self.fail("contract", path, f"the finding comment does not parse: {e}")
            return
        want = ("should-fix", "R-003/src/widgets/inventory.py::is_known_part", "a predicate raises on a part it does not know")
        if f is None or (f["severity"], f["key"], f["title"]) != want:
            self.fail("contract", path, f"record.py reads the finding comment as {f and (f['severity'], f['key'], f['title'])}, not {want}")
        style = self.root / "skills/pr-review/comment-style.md"
        example = re.search(r"^```\n(.*?)^```", section_text(style.read_text(), "Severity Line") or "", re.M | re.S)
        if not example or not record.LABEL.match(example.group(1)):
            self.fail("contract", style, "the Severity Line example does not match record.py's LABEL")

    def check_body(self) -> None:
        record = self.load("record")
        path = self.root / "skills/pr-create/body.md"
        block = record.already_checked(path.read_text())
        if block is None:
            self.fail("body", path, "no Already checked block")
            return
        for label in record.REQUIRED_LINES:
            if not re.search(rf"^{re.escape(label)}", block, re.M):
                self.fail("body", path, f"the Already checked block has no {label!r} line, which record.py requires")
        for label in record.OPTIONAL_LINES:
            if not re.search(rf"^{re.escape(label)}", block, re.M):
                self.fail("body", path, f"the Already checked block has no {label!r} line, which record.py reads")

    def documents(self) -> list[Path]:
        """GUIDE, README and the other documents people read: the roadmap, `docs/` outside its
        history, the sandbox README, the contributor notes and the corpus."""
        files = [self.root / "GUIDE.md", self.root / "README.md", self.root / "ROADMAP.md"]
        files += [*self.root.glob("docs/*.md"), self.root / "sandbox/README.md", self.root / ".claude/CLAUDE.md"]
        files += [*self.root.glob("standards/**/*.md")]
        return sorted({f for f in files if f.is_file()})

    def check_sections(self) -> None:
        targets = {name: path for name, path in self.skills.items()}
        targets |= {
            "GUIDE.md": self.root / "GUIDE.md", "README.md": self.root / "README.md",
            "review-contract.md": self.root / "standards/review-contract.md",
            "comment-style.md": self.root / "skills/pr-review/comment-style.md",
            "standards/README.md": self.root / "standards/README.md",
            "ROADMAP.md": self.root / "ROADMAP.md", "docs/design.md": self.root / "docs/design.md",
            "docs/contracts.md": self.root / "docs/contracts.md",
            "standards/dials.md": self.root / "standards/dials.md",
            "sandbox/README.md": self.root / "sandbox/README.md",
        }
        headings = {}
        for path in self.prose():
            text = path.read_text()
            refs = [(m.group(1), " ".join(m.group(2).split())) for m in SECTION_REF.finditer(text)]
            refs += [("README.md", " ".join(m.group(1).split())) for m in README_REF.finditer(text)]
            refs += [("standards/README.md", " ".join(m.group(1).split())) for m in CORPUS_README_REF.finditer(text)]
            for name, section in refs:
                # A path names its file: `.../skills/<name>/SKILL.md`, or a document by its file name.
                skill = re.search(r"(?:skills|\.\.)/([\w-]+)/SKILL\.md$", name)
                if skill:
                    name = skill.group(1)
                elif "/" in name and name.rsplit("/", 1)[1] in ("comment-style.md", "review-contract.md"):
                    name = name.rsplit("/", 1)[1]
                name = name.removeprefix("${CLAUDE_PLUGIN_ROOT}/")
                if PLACEHOLDER.search(section) or PLACEHOLDER.search(name):
                    continue
                if name in targets:
                    target = targets[name]
                elif target := self.markdown(name, path):
                    name = str(target.relative_to(self.root))
                else:
                    continue
                if target not in headings:
                    text = target.read_text() if target.is_file() else ""
                    summaries = {normal(s) for s in re.findall(r"<summary>(.*?)</summary>", text)}
                    rows = dial_rows(text) if target == self.root / "standards/dials.md" else set()
                    headings[target] = heading_set(text) | summaries | rows
                if normal(section) not in headings[target]:
                    self.fail("sections", path, f'`{name}` "{section}" is not a heading in {target.relative_to(self.root)}')

    def prose(self) -> list[Path]:
        """The skills' and agents' markdown and the documents."""
        files = [*self.root.glob("skills/*/SKILL.md"), *self.root.glob("skills/*/*.md"), *self.root.glob("skills/*/*/*.md")]
        files += [*self.root.glob("agents/*.md"), *self.documents()]
        return sorted({f for f in files if f.is_file()})

    def markdown(self, name: str, citing: Path) -> Path | None:
        """The `.md` file a cited name resolves to inside the plugin, from the top level or from the
        citing file's directory, `${CLAUDE_SKILL_DIR}/` being the citing skill's directory; None
        when it names no such file."""
        if not name.endswith(".md"):
            return None
        bases = [self.root, citing.parent]
        if name.startswith("${CLAUDE_SKILL_DIR}/"):
            skill = next((d for d in citing.parents if d.parent == self.root / "skills"), None)
            bases, name = ([skill] if skill else []), name.removeprefix("${CLAUDE_SKILL_DIR}/")
        root = self.root.resolve()
        for base in bases:
            target = (base / name).resolve()
            if target.is_file() and target.is_relative_to(root):
                return self.root / target.relative_to(root)
        return None

    def check_paths(self) -> None:
        for path in self.documents():
            text = path.read_text()
            for m in PATH_REF.finditer(text):
                rel = m.group(1).split("::")[0].rstrip(".,;:)")
                if PLACEHOLDER.search(rel) or any(c in rel for c in "*?{$") or rel in IN_ADOPTING_REPO:
                    continue
                if not (self.root / rel).exists():
                    self.fail("paths", path, f"`{rel}` does not exist")
            for m in LINK.finditer(prose_only(text)):
                link = m.group(1)
                if re.match(r"[a-z]+:", link):
                    continue
                file, _, fragment = link.partition("#")
                target = (path.parent / file) if file else path
                if not target.exists():
                    self.fail("paths", path, f"the link ({link}) names a file that does not exist")
                elif fragment and target.suffix == ".md" and fragment not in anchors(target.read_text()):
                    self.fail("paths", path, f"the link ({link}) names no heading of {target.relative_to(self.root)}")

    def check_dials(self) -> None:
        dials = self.root / "standards/dials.md"
        rows = dial_rows(dials.read_text())
        for path in self.prose():
            if path == dials:
                continue
            text = path.read_text()
            named = [n for m in DIAL_NAMED.finditer(text) for n in re.split(DIAL_JOIN, m.group(1))]
            named += [m.group(1) for m in DIAL_QUOTED.finditer(text)]
            for name in named:
                if " ".join(name.split()).casefold() not in rows:
                    self.fail("dials", path, f'"{" ".join(name.split())}" is not a row of standards/dials.md')

    def check_profiles(self) -> None:
        profile = self.load("profile")
        default = self.root / profile.DEFAULT_PROFILE
        try:
            light = profile.defaults_here(self.root)["depth"]["light"]
        except (profile.ProfileError, OSError) as e:
            self.fail("profiles", default, str(e))
            light = []
        for brief in sorted({e["brief"] for e in light} if isinstance(light, list) else set()):
            if not (self.root / "skills/implement-change/reviews" / f"{brief}.md").is_file():
                self.fail("profiles", default, f"depth.light names the brief {brief!r}, not a file in skills/implement-change/reviews/")
        example = self.root / "standards/profile.example.yaml"
        if not example.is_file():
            self.fail("profiles", self.root / "standards", "no profile.example.yaml")
            return
        try:
            keys = set(profile.parse(example.read_text(), example.name))
        except profile.ProfileError as e:
            self.fail("profiles", example, str(e))
            return
        if keys != set(profile.SCHEMA):
            self.fail("profiles", example, f"its keys differ from profile.py's: {sorted(keys ^ set(profile.SCHEMA))}")

    def check_contracts(self) -> None:
        path = self.root / "docs/contracts.md"
        if not path.is_file():
            self.fail("contracts", self.root, "no docs/contracts.md")
            return
        text = path.read_text()
        for _, _, title in [h for h in headings(text) if h[1] == 2]:
            body = section_text(text, title) or ""
            pin = re.search(r"^Pinned by: (\S+?)::(.+?)\s*$", body, re.M)
            if not pin:
                self.fail("contracts", path, f'"{title}" has no Pinned by: line')
                continue
            test, name = self.root / pin.group(1), pin.group(2).strip('"')
            # The test's definition: a Python `def <name>(` or a shell `check "<name>"`.
            if not test.is_file() or not re.search(rf'(def {re.escape(name)}\(|check "{re.escape(name)}")', test.read_text()):
                self.fail("contracts", path, f'"{title}" is pinned by {pin.group(1)}::{pin.group(2)}, which does not exist')

    def check_rule_bar(self) -> None:
        for rel, names in (("skills/revise/SKILL.md", ("rule-bar.md", "rule-probe")),
                           ("skills/revise/harvest.md", ("rule-bar.md", "rule-probe")),
                           ("skills/revise/prepare.md", ("harvest.md",)),
                           ("skills/onboard/first-rules.md", ("rule-bar.md", "harvest.md")),
                           ("skills/revise/correct.md", ("rule-bar.md",))):
            path = self.root / rel
            text = path.read_text() if path.is_file() else ""
            for name in names:
                if name not in text:
                    self.fail("rule-bar", path, f"does not name {name}")
        lint = self.load("rule_lint")
        fixture = self.root / "tests" / "fixtures" / "rule-bar"
        here = self.root / "scripts" / "rule_lint.py"
        with tempfile.TemporaryDirectory() as tmp:
            repo = lint.fixture_repo(fixture, Path(tmp) / "repo")
            args = ["--ledger", str(repo / "review-rules.md"), "--instructions", str(repo / "instructions.md")]
            args += ["--repo", str(repo), "--decisions", str(repo / "decisions.md")]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = lint.main(args)
            if rc != 0:
                self.fail("rule-bar", here, f"the fixture fails: {out.getvalue().strip()}")
            ledger = repo / "review-rules.md"
            ledger.write_text(ledger.read_text().replace('::load "path: Path"', '::load "path: Altered"', 1))
            with contextlib.redirect_stdout(io.StringIO()):
                rc = lint.main(args)
            if rc != 1:
                self.fail("rule-bar", here, "an example quoting a shape the code does not hold passes")

    def coupling(self) -> tuple[dict, dict[str, int]] | None:
        """The baseline and, per generic file with any, its mentions, the patterns' matches; None,
        with a failure, when the baseline cannot be read."""
        path = self.root / COUPLING
        try:
            spec = json.loads(path.read_text())
        except (OSError, ValueError) as e:
            self.fail("coupling", path, f"cannot read the baseline: {e}")
            return None
        if not isinstance(spec, dict) or sorted(spec) != ["counts", "mission", "patterns"] or not all(isinstance(v, dict) for v in spec.values()):
            self.fail("coupling", path, "the baseline is not an object of three objects, counts, mission and patterns")
            return None
        if not all(type(n) is int and n > 0 for n in spec["counts"].values()):
            self.fail("coupling", path, "a count is not a positive integer")
            return None
        try:
            patterns = [re.compile(p) for p in spec["patterns"]]
        except re.error as e:
            self.fail("coupling", path, f"a pattern is not a regular expression: {e}")
            return None
        bad = False
        for m in spec["mission"]:
            target = self.root / m
            if not target.exists():
                self.fail("coupling", path, f"mission's {m} does not exist: remove its entry")
            elif target.is_dir() != m.endswith("/"):
                self.fail("coupling", path, f"mission's {m} is a {'directory' if target.is_dir() else 'file'}: write a directory with a trailing / and a file without")
            elif under := [d for d in spec["mission"] if d.endswith("/") and d != m and m.startswith(d)]:
                self.fail("coupling", path, f"mission's {m} is under mission's {under[0]}: remove it")
            else:
                continue
            bad = True
        if bad:
            return None
        mission = tuple(spec["mission"])
        counts = {}
        for d in GENERIC:
            for p in sorted((self.root / d).rglob("*")):
                rel = p.relative_to(self.root).as_posix()
                if not p.is_file() or "__pycache__" in p.parts or rel == COUPLING:
                    continue
                if rel.startswith(mission) and not (p.name == "README.md" and f"{p.parent.relative_to(self.root).as_posix()}/" in spec["mission"]):
                    continue
                n = sum(len(rx.findall(line)) for line in p.read_text(errors="replace").splitlines() for rx in patterns)
                if n:
                    counts[rel] = n
        self.coupling_total = sum(counts.values())
        return spec, counts

    def check_coupling(self) -> None:
        got = self.coupling()
        if got is None:
            return
        spec, counts = got
        for rel in sorted(set(counts) | set(spec["counts"])):
            now, allowed = counts.get(rel, 0), spec["counts"].get(rel, 0)
            if now > allowed:
                hint = "" if allowed else f"; {moved_hint(rel, spec, counts)}"
                self.fail("coupling", self.root / rel, f"{now} mention(s), {allowed} in {COUPLING}: remove the new mention{hint}")
            elif now < allowed:
                self.fail("coupling", self.root / rel, f"{now} mention(s), {allowed} in {COUPLING}: lower it with `python3 scripts/check_static.py --update-coupling`")

    def update_coupling(self) -> None:
        got = self.coupling()
        if got is None:
            return
        spec, counts = got
        raised = [(rel, now, spec["counts"].get(rel, 0)) for rel, now in sorted(counts.items()) if now > spec["counts"].get(rel, 0)]
        for rel, now, allowed in raised:
            hint = "" if allowed else f"; {moved_hint(rel, spec, counts)}"
            self.fail("coupling", self.root / rel, f"{now} mention(s), {allowed} in {COUPLING}: the update only lowers a count{hint}")
        if raised:
            return
        spec["counts"] = counts
        (self.root / COUPLING).write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")

    def load(self, name: str, directory: str = "scripts"):
        """Execute `<directory>/<name>.py` under this root afresh, never a module cached in `sys.modules`."""
        spec = importlib.util.spec_from_file_location(name, self.root / directory / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="the plugin's top level")
    p.add_argument("--update-coupling", action="store_true", help=f"lower {COUPLING}'s counts to the tree's; refuses a raise")
    args = p.parse_args(argv)
    plugin = Plugin(args.root.resolve())
    if args.update_coupling:
        plugin.update_coupling()
    else:
        plugin.check_frontmatter()
        plugin.check_references()
        plugin.check_plugin_vars()
        plugin.check_review_map()
        plugin.check_copilot_links()
        plugin.check_readme_skills()
        plugin.check_round_trip()
        plugin.check_contract()
        plugin.check_body()
        plugin.check_sections()
        plugin.check_paths()
        plugin.check_dials()
        plugin.check_profiles()
        plugin.check_contracts()
        plugin.check_rule_bar()
        plugin.check_coupling()
    for line in plugin.failures:
        print(line)
    if plugin.coupling_total is not None:
        print(f"coupling: {plugin.coupling_total} mention(s) in the generic files", file=sys.stderr)
    print(f"check_static.py: {len(plugin.failures)} failure(s)", file=sys.stderr)
    return 1 if plugin.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
