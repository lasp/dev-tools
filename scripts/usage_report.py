#!/usr/bin/env python3
"""Count how the plugin was used in this person's Claude Code transcripts, as a payload of numbers and fixed words.

Reads the main transcripts, `projects/*/*.jsonl`, and the agents' transcripts,
`projects/*/*/subagents/*.jsonl` with their `.meta.json`, under `$CLAUDE_CONFIG_DIR`, or
`~/.claude` when that is unset. Only entries timestamped inside the window count: from
`--since`, a date `YYYY-MM-DD` or a time in UTC `YYYY-MM-DDTHH:MM:SS[.fff]Z`, to now.
A file last modified before the window opens is not read. A sandbox session, one whose main transcript
holds a `custom-title` entry `lasp-dev-sandbox` (the name `sandbox/sbx-claude` and `sandbox/run.py` give
each session they start), is left out with its agents. Main transcripts are read oldest first, and an
entry whose `uuid` an earlier one held, the history a resumed or forked session repeats, is read once;
a request's tokens count once across the whole report.

The plugin's names come from `--plugin-root`, the installed plugin: its `name` in
`.claude-plugin/plugin.json`, its skills (`skills/*/SKILL.md`), agents (`agents/*.md`),
scripts (`scripts/*.py`, `scripts/*.sh`) and hooks (`hooks/*.sh`). A skill or agent is the
plugin's when it is named `<plugin>:<name>` or `libera-tools:<name>`, the plugin's earlier name;
a name in that namespace the plugin no longer has counts as `other`.

A plugin skill run starts at a typed `/<plugin>:<skill>` or a `Skill` call naming one, in a main
transcript, and ends at the next skill start, typed or called, of any skill, a personal one, a
typed project one (`.claude/skills/<name>/` or `.claude/commands/<name>.md` under the entry's
`cwd`) or another plugin's `/<namespace>:<name>` included, or at the session's end. Its turns are the
person's messages from its start to its end, the one that typed it included; its tokens are the input, cache and output tokens of each request
in it, counted once a request, and those of the agents it started, theirs included.

Writes `--out`, one JSON object, the payload, version 1 in `docs/contracts.md`'s "The usage
report", and `--pending`, a JSON list of the most recent 40 plugin skill runs, each with the
skill, its start time and the person's next message cut to 400 characters, or null when there was
none. The pending file holds the person's words and is never part of the payload; the skill passes a
path in a directory of its own under `$TMPDIR`, outside every repository. Prints one summary line to stdout.
`after_run`, `overlap` and `notes` are written null, for the skill to fill.

`--fill PAYLOAD` replaces those fields in a payload this script wrote, each only when its flag is
given: `--labels`, one outcome per run of `--pending`, in its order, counted per skill into
`after_run`; `--overlap`, `skill:<name>=<n>` or `agent:<name>=<n>` items naming the plugin's skills
and agents of `--plugin-root`, into `overlap`, zeros left out; `--notes FILE`, the file's text,
stripped, into `notes`, or null when it is empty. It rewrites the payload and prints it, then its
`sha256:` digest.

Every string in the payload is a field name or from the vocabulary: the plugin's names, `other`,
Claude Code's built-in tool names, the GitHub and Atlassian MCP tools in `MCP_TOOLS` as
`mcp__<tool>`, their server dropped, and any other MCP tool as `mcp__other`, the auto-mode denial
categories in `AUTO_MODE_CATEGORIES`, Claude model ids (opus, sonnet, haiku or fable), Claude Code versions,
the plugin's commit, timestamps, and the fixed words this script defines. A question header is kept only when the files
of the skill that asked it hold it as a phrase, in the same case, and no pattern in the plugin's
`scripts/coupling.json`, its list of project names, matches it. A value outside the vocabulary is written `other`. A count of zero is left out;
the top-level fields are always present.

Exits 1 with the reason on stderr when the plugin root has no plugin manifest, no skills or no
`scripts/coupling.json` with patterns, `--since` is not a date or a UTC time in
those forms or is not before now, a transcript
cannot be read or is not JSON lines, an entry has no `type`, or an entry of a kind the script reads
(user, assistant, attachment, system) does not have the shape it reads: a timestamp, a uuid, a message
with content, a tool call with a name, id and input, a `Skill` call with a skill name, a `Bash`
call with a command, a typed command, other than a plugin, personal or namespaced one, with a `cwd`, a usage record of counts, an `AskUserQuestion` call or result
`transcript_excerpt.py` refuses (a call that errored is counted, not read), or an agent with no `.meta.json` or no `agentType` in it; each
names the file. Entries of other top-level kinds are skipped unread, since Claude Code adds kinds
often and none of them carries a value reported here. Also exits 1 when git fails on a working
directory for a reason other than its being gone or no repository, when agents nest more than 20
deep, and when the payload is over `--max-bytes`, rather than cut. `--fill` exits 1, writing nothing,
on a payload or pending file that is not the JSON this script writes, a count of labels that is not
the count of runs, a run given `none` that has a next message or one with a next message given
anything but `none`, an overlap item that does not name one of the plugin's skills or agents with a
count of 1 or more or names one twice, and a filled payload over `--max-bytes`. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

_spec = importlib.util.spec_from_file_location("transcript_excerpt", Path(__file__).with_name("transcript_excerpt.py"))
excerpt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(excerpt)

SCHEMA = 1
LEGACY_NAMESPACES = ("libera-tools",)
PENDING_RUNS = 40
PENDING_CHARS = 400
RERUN_TURNS = 3
# Under a GitHub issue body's 65,536 characters, with room for the fence, the digest and the footer.
DEFAULT_MAX_BYTES = 60000
OTHER = "other"
ANSWER_TYPES = ("recommended", "other_option", "free_text", "declined", "not_shown")
# What the person did next after a run, as the skill labels it; `none` is a run with no next message.
OUTCOMES = ("approve", "correct", "status", "new_task", "interrupt", "none")
HOOK_OUTCOMES = ("allow", "ask", "deny", "canceled", "error")
DENIAL_KINDS = ("permission_denied", "dont_ask_mode", "safety_check", "user_rejected")
EXIT_WORDS = ("background", "interrupted", "denied", "error")
READ_KINDS = ("user", "assistant", "attachment", "system")
SANDBOX_TITLE = "lasp-dev-sandbox"
# The GitHub and Atlassian MCP tools the plugin's skills and agents name; any other MCP tool is `mcp__other`.
MCP_TOOLS = frozenset({
    "add_issue_comment", "get_file_contents", "get_label", "get_me", "issue_read", "issue_write", "list_commits", "list_issues",
    "pull_request_read", "search_code", "search_issues", "search_pull_requests", "search_repositories",
    "confluence_create_page", "confluence_get_page", "confluence_get_page_children", "confluence_get_page_diff",
    "confluence_get_space_page_tree", "confluence_search", "confluence_update_page", "confluence_update_page_section",
    "jira_add_comment", "jira_assign_issue", "jira_batch_get_changelogs", "jira_create_issue", "jira_create_issue_link",
    "jira_get_issue", "jira_get_link_types", "jira_get_project_components", "jira_get_project_issue_types",
    "jira_get_transitions", "jira_link_to_epic", "jira_search", "jira_search_fields", "jira_transition_issue",
    "jira_update_issue",
})
# Claude Code's auto-mode denial categories; any other is `other`.
AUTO_MODE_CATEGORIES = frozenset({
    "Auto-Mode Bypass", "Blind Apply", "CI Bypass", "Code from External", "Create Unsafe Agents", "Credential Exploration",
    "External System Writes", "Git Destructive", "Irreversible Local Destruction", "Modify Shared Resources",
    "PII Data Handling", "Production Deploy", "Production Reads", "Protected-Scope IaC Apply", "Self-Modification",
    "Unrequested Commit in a Connected App",
})

TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z\Z")
VERSION = re.compile(r"\d+\.\d+\.\d+\Z")
MODEL = re.compile(r"claude-(?:opus|sonnet|haiku|fable)-\d{1,2}(?:-\d{1,2})?(?:-\d{8})?\Z")
COMMIT = re.compile(r"[0-9a-f]{12}\Z")
BUILTIN_TOOL = re.compile(r"[A-Z][A-Za-z]{1,40}\Z")
HEADER = re.compile(r"[A-Za-z][A-Za-z -]{0,39}\Z")
AUTO_DENIAL = re.compile(r"Permission for this action was denied by the Claude Code auto mode classifier\. Reason: \[([^\]\n]*)\]")
DENIALS = (
    ("dont_ask_mode", re.compile(r"Permission to use .* has been denied because Claude Code is running in don't ask mode", re.S)),
    ("safety_check", re.compile(r"Permission for this command was denied by a built-in Claude Code safety check")),
    ("permission_denied", re.compile(r"Permission to use .* has been denied\.", re.S)),
    ("user_rejected", re.compile(r"The user doesn't want to proceed with this tool use")),
)
EXIT_CODE = re.compile(r"(?:Error: )?Exit code (\d+)\b")
PUSH = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?push\b")
PR_OPEN = re.compile(r"\bgh\s+pr\s+create\b")
HOOK_COMMAND = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/hooks/([\w-]+)\.sh\b")
OVERLAP_ITEM = re.compile(r"(skill|agent):([\w-]+)=([1-9]\d*)")


class UsageError(Exception):
    pass


class Plugin:
    """The installed plugin's names, read from its directory."""

    def __init__(self, root: Path):
        manifest = root / ".claude-plugin" / "plugin.json"
        try:
            self.name = json.loads(manifest.read_text(encoding="utf-8"))["name"]
        except (OSError, ValueError, KeyError, TypeError) as e:
            raise UsageError(f"{manifest} is not a plugin manifest with a name: {e}") from e
        self.root = root
        self.skills = {p.parent.name for p in root.glob("skills/*/SKILL.md")}
        if not self.skills:
            raise UsageError(f"{root} holds no skills/*/SKILL.md")
        self.agents = {p.stem for p in root.glob("agents/*.md")}
        self.scripts = {p.stem for p in root.glob("scripts/*.py")} | {p.stem for p in root.glob("scripts/*.sh")}
        self.hooks = {p.stem for p in root.glob("hooks/*.sh")}
        self.namespaces = (self.name,) + LEGACY_NAMESPACES
        coupling = root / "scripts" / "coupling.json"
        try:
            self.projects = [re.compile(p) for p in json.loads(coupling.read_text(encoding="utf-8"))["patterns"]]
        except (OSError, ValueError, KeyError, TypeError, re.error) as e:
            raise UsageError(f"{coupling} holds no patterns of project names: {e}") from e
        self.skill_text = {s: "\n".join(p.read_text(encoding="utf-8") for p in sorted(root.glob(f"skills/{s}/**/*.md")))
                           for s in self.skills}
        names = "|".join(re.escape(n) for n in sorted(self.scripts, key=len, reverse=True))
        bases = [re.escape(str(root.resolve())), re.escape(str(root)), r"\$\{CLAUDE_PLUGIN_ROOT\}",
                 r"/plugins/cache/[^/\s]+/(?:" + "|".join(re.escape(n) for n in self.namespaces) + r")/[^/\s]+"]
        self.script_call = re.compile(r"(?:" + "|".join(bases) + r")/scripts/(" + names + r")\.(?:py|sh)\b") if names else None

    def commit(self) -> str:
        """The plugin's commit, 12 hex digits: the checkout's HEAD, or the cache directory's name."""
        if (self.root / ".git").exists():
            p = subprocess.run(["git", "-C", str(self.root), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True)
            if p.returncode != 0:
                raise UsageError(f"{self.root}: git cannot read its commit: {p.stderr.strip()}")
            return p.stdout.strip()
        if COMMIT.match(self.root.resolve().name):
            return self.root.resolve().name
        raise UsageError(f"{self.root} is neither a git checkout nor a cache directory named by its commit")

    def named(self, name: str, kind: set[str]) -> str | None:
        """A `<namespace>:<name>` as the plugin's name, `other` for one the plugin does not have, None outside the plugin."""
        name = name.strip().lstrip("/").split()[0] if name.strip() else ""
        namespace, _, rest = name.partition(":")
        if not rest or namespace not in self.namespaces:
            return None
        return rest if rest in kind else OTHER

    def header(self, text: str, skill: str) -> str:
        """The header when the skill's own files hold it as a phrase, in the same case, and it names no project; else `other`."""
        phrase = text.strip()
        if (HEADER.match(phrase) and not any(p.search(phrase) for p in self.projects)
                and re.search(r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])", self.skill_text.get(skill, ""))):
            return phrase
        return OTHER


def tool_word(name: str) -> str:
    """A built-in tool's name; an MCP tool as `mcp__<tool>`, its server dropped, when `MCP_TOOLS` holds it, else `mcp__other`."""
    if name.startswith("mcp__"):
        tool = name.split("__", 2)[2] if name.count("__") >= 2 else ""
        return f"mcp__{tool}" if tool in MCP_TOOLS else f"mcp__{OTHER}"
    return name if BUILTIN_TOOL.match(name) else OTHER


def nonzero(counts: dict) -> dict:
    return {k: v for k, v in counts.items() if v}


def nearest_rank(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def spread(values: list[int]) -> dict:
    return {"median": nearest_rank(values, 0.5), "p90": nearest_rank(values, 0.9)} if values else {"median": 0, "p90": 0}


def result_text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def denial(text: str) -> str | None:
    auto = AUTO_DENIAL.match(text)
    if auto:
        return auto.group(1) if auto.group(1) in AUTO_MODE_CATEGORIES else OTHER
    for kind, pattern in DENIALS:
        if pattern.match(text):
            return kind
    return None


def exit_word(block: dict, result) -> str:
    text = result_text(block.get("content"))
    if block.get("is_error"):
        code = EXIT_CODE.match(text)
        if code:
            return code.group(1)
        return "denied" if denial(text) else "error"
    if isinstance(result, dict) and result.get("interrupted"):
        return "interrupted"
    if isinstance(result, dict) and result.get("backgroundTaskId"):
        return "background"
    return "0"


def tokens(usage, path: Path) -> int:
    if not isinstance(usage, dict):
        raise UsageError(f"{path}: an assistant entry's usage is not a record")
    total = 0
    for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"):
        value = usage.get(key, 0)
        if not isinstance(value, int) or isinstance(value, bool):
            raise UsageError(f"{path}: an assistant entry's usage {key} is {value!r}, not a count")
        total += value
    return total


def tool_uses(entry: dict, path: Path) -> list[dict]:
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        raise UsageError(f"{path}: an assistant entry's message has no content list")
    calls = []
    for block in content:
        if not isinstance(block, dict):
            raise UsageError(f"{path}: an assistant entry's content holds a {type(block).__name__}, not a block")
        if block.get("type") != "tool_use":
            continue
        if not isinstance(block.get("name"), str) or not isinstance(block.get("id"), str) or not isinstance(block.get("input"), dict):
            raise UsageError(f"{path}: a tool call has no name, id or input record")
        name, tool_input = block["name"], block["input"]
        if name == "Skill" and not isinstance(tool_input.get("skill"), str):
            raise UsageError(f"{path}: a Skill call has no skill name")
        if name == "Bash" and not isinstance(tool_input.get("command"), str):
            raise UsageError(f"{path}: a Bash call has no command")
        calls.append(block)
    return calls


def tool_results(entry: dict, path: Path) -> list[dict]:
    content = entry["message"]["content"]
    if isinstance(content, str):
        return []
    out = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            if not isinstance(block.get("tool_use_id"), str):
                raise UsageError(f"{path}: a tool result has no tool_use_id")
            out.append(block)
    return out


def windowed(path: Path, start: str, end: str) -> tuple[list[dict], bool]:
    """The entries of the kinds read, timestamped inside the window, after checking every entry's kind, timestamp and uuid;
    and whether the transcript is a sandbox session's, named `SANDBOX_TITLE`."""
    try:
        entries = excerpt.read_entries(path)
    except excerpt.ExcerptError as e:
        raise UsageError(str(e)) from e
    kept = []
    sandbox = False
    for e in entries:
        kind = e.get("type")
        if not isinstance(kind, str):
            raise UsageError(f"{path}: an entry has no type")
        if kind == "custom-title" and e.get("customTitle") == SANDBOX_TITLE:
            sandbox = True
        if kind not in READ_KINDS:
            continue
        stamp = e.get("timestamp")
        if not isinstance(stamp, str) or not TIMESTAMP.match(stamp):
            raise UsageError(f"{path}: a {kind} entry's timestamp is {stamp!r}, not an ISO time in UTC")
        if not isinstance(e.get("uuid"), str):
            raise UsageError(f"{path}: a {kind} entry has no uuid")
        if kind in ("user", "assistant") and not isinstance(e.get("message"), dict):
            raise UsageError(f"{path}: a {kind} entry has no message")
        if kind == "user" and not isinstance(e["message"].get("content"), (str, list)):
            raise UsageError(f"{path}: a user entry's message has no content")
        if kind == "attachment" and not isinstance((e.get("attachment") or {}).get("type"), str):
            raise UsageError(f"{path}: an attachment entry has no attachment type")
        if start <= stamp[:19] < end:
            kept.append(e)
    return kept, sandbox


class Report:
    def __init__(self, plugin: Plugin, personal: set[str]):
        self.plugin = plugin
        self.personal = personal
        self.versions: set[str] = set()
        self.models: set[str] = set()
        self.sessions = 0
        self.turns = 0
        self.runs: list[dict] = []
        self.questions: dict = defaultdict(lambda: defaultdict(Counter))
        self.free_text: dict = defaultdict(lambda: defaultdict(list))
        self.scripts: dict = defaultdict(Counter)
        self.hooks: dict = defaultdict(Counter)
        self.denials: dict = defaultdict(Counter)
        self.transitions: Counter = Counter()
        self.agents: list[dict] = []
        self.agent_tokens: dict[str, int] = {}
        self.agent_children: dict[str, list[str]] = {}
        self.agent_denials: dict[str, list[tuple[str, str]]] = {}
        self.cwds: set[str] = set()
        self.seen_entries: set[str] = set()
        self.seen_requests: set[str] = set()
        self.run_starts: dict[str, dict] = {}

    def request_tokens(self, e: dict, path: Path) -> int:
        """An assistant entry's tokens, or 0 when its request was counted already."""
        request = e.get("requestId")
        usage = e["message"].get("usage")
        if usage is None or (isinstance(request, str) and request in self.seen_requests):
            return 0
        if isinstance(request, str):
            self.seen_requests.add(request)
        return tokens(usage, path)

    def environment(self, e: dict) -> None:
        if isinstance(e.get("version"), str):
            self.versions.add(e["version"] if VERSION.match(e["version"]) else OTHER)
        model = (e.get("message") or {}).get("model") if e.get("type") == "assistant" else None
        if isinstance(model, str) and model != "<synthetic>":
            self.models.add(model if MODEL.match(model) else OTHER)

    def hook(self, e: dict) -> None:
        att = e["attachment"]
        match = HOOK_COMMAND.search(str(att.get("command", "")))
        if not match or match.group(1) not in self.plugin.hooks:
            return
        counts = self.hooks[match.group(1)]
        counts["runs"] += 1
        if att["type"] == "hook_cancelled":  # codespell:ignore cancelled
            counts["canceled"] += 1
        elif att["type"] == "hook_non_blocking_error":
            counts["error"] += 1
        else:
            try:
                out = json.loads(att.get("stdout") or "{}")
            except json.JSONDecodeError:
                return
            decision = (out.get("hookSpecificOutput") or {}).get("permissionDecision") if isinstance(out, dict) else None
            if decision in ("allow", "ask", "deny"):
                counts[decision] += 1

    def script_calls(self, call: dict) -> list[str]:
        if call["name"] != "Bash" or not self.plugin.script_call:
            return []
        return sorted(set(self.plugin.script_call.findall(call["input"]["command"])))

    def session(self, path: Path, entries: list[dict]) -> None:
        """One main transcript: its turns, plugin skill runs, questions, scripts, hooks and denials. An entry another main
        transcript holds, as a resumed or forked session repeats its history, is counted once; it is still walked, so
        a run it started goes on in this transcript."""
        fresh = {e["uuid"] for e in entries} - self.seen_entries
        if not fresh:
            return
        self.seen_entries |= fresh
        self.sessions += 1
        tools: dict[str, str] = {}
        scripts: dict[str, list[str]] = {}
        asked: dict[str, tuple[str, dict]] = {}
        run: dict | None = None
        last_start: dict[str, int] = {}
        position = 0

        def start(skill: str | None, typed: bool, e: dict, key: str, new: bool) -> None:
            """End the current run and start one of `skill`, or of no plugin skill when it is None. An entry counted
            already resumes the run it started, keyed by `key`."""
            nonlocal run
            if run and new:
                self.transitions[f"{run['skill']} -> {skill or OTHER}"] += 1
            run = None
            if skill is None:
                return
            if not new:
                run = self.run_starts[key]
                last_start[skill] = position
                return
            rerun = skill in last_start and position - last_start[skill] <= RERUN_TURNS
            last_start[skill] = position
            run = {"skill": skill, "typed": typed, "turns": 1 if typed else 0, "tokens": 0, "agents": [], "rerun": rerun,
                   "compacted": False, "push": False, "pr_open": False, "started": e["timestamp"], "next": None}
            self.runs.append(run)
            self.run_starts[key] = run
            if isinstance(e.get("cwd"), str):
                self.cwds.add(e["cwd"])

        for e in entries:
            new = e["uuid"] in fresh
            if new:
                self.environment(e)
            kind = e["type"]
            if e.get("isSidechain"):
                continue
            text = excerpt.person_message(e)
            if text:
                position += 1
                if new:
                    self.turns += 1
                command = excerpt.COMMAND_NAME.search(text) if kind == "user" else None
                name = command.group(1).strip() if command else None
                if name:
                    skill = self.plugin.named(name, self.plugin.skills)
                    if skill is not None:
                        start(skill, True, e, e["uuid"], new)
                        continue
                    word = name.lstrip("/").split()[0]
                    if word in self.personal or ":" in word or project_skill(path, e, word):
                        start(None, True, e, e["uuid"], new)
                if run and new:
                    run["turns"] += 1
                    if run["next"] is None:
                        run["next"] = excerpt.person_text(text)[:PENDING_CHARS]
                continue
            if kind == "assistant":
                count = self.request_tokens(e, path) if new else 0
                if run:
                    run["tokens"] += count
                for call in tool_uses(e, path):
                    tools[call["id"]] = call["name"]
                    called = self.script_calls(call)
                    if called:
                        scripts[call["id"]] = called
                    if call["name"] == "Skill":
                        start(self.plugin.named(call["input"]["skill"], self.plugin.skills), False, e, call["id"], new)
                        continue
                    if not run or not new:
                        continue
                    if call["name"] in ("Agent", "Task"):
                        run["agents"].append(call["id"])
                    elif call["name"] == "AskUserQuestion":
                        asked[call["id"]] = (run["skill"], call)
                    elif call["name"] == "Bash":
                        run["push"] |= bool(PUSH.search(call["input"]["command"]))
                        run["pr_open"] |= bool(PR_OPEN.search(call["input"]["command"]))
                    elif call["name"].endswith("__create_pull_request"):
                        run["pr_open"] = True
            elif kind == "user":
                for block in tool_results(e, path):
                    use = block["tool_use_id"]
                    called = scripts.pop(use, [])
                    if not new:
                        continue
                    for name in called:
                        self.scripts[name]["runs"] += 1
                        self.scripts[name][exit_word(block, e.get("toolUseResult"))] += 1
                    if use in asked:
                        self.answers(*asked.pop(use), e.get("toolUseResult"), path)
                    if run and block.get("is_error"):
                        found = denial(result_text(block.get("content")))
                        if found:
                            self.denials[tool_word(tools.get(use, OTHER))][found] += 1
            elif kind == "attachment" and new:
                self.hook(e)
            elif kind == "system" and e.get("subtype") == "compact_boundary" and run and new:
                run["compacted"] = True

    def answers(self, skill: str, call: dict, result, path: Path) -> None:
        """Count each question's answer type. A call that errored, the model's own malformed calls among them, counts once
        under `other` when its questions cannot be read; a call that was answered must have readable questions."""
        raw = call["input"].get("questions")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = None
        readable = isinstance(raw, list) and raw and all(isinstance(q, dict) for q in raw)
        if isinstance(result, str):
            declined = result.startswith("User rejected") or "doesn't want to proceed" in result
            for q in raw if readable else [{}]:
                self.questions[skill][self.plugin.header(str(q.get("header", "")), skill)]["declined" if declined else "not_shown"] += 1
            return
        if not readable:
            raise UsageError(f"{path}: an answered AskUserQuestion call's questions are not a list of questions")
        texts = [str(q.get("question", "")) for q in raw]
        try:
            excerpt.answers_of(texts, result)
        except excerpt.ExcerptError as e:
            raise UsageError(f"{path}: {e}") from e
        for q, text in zip(raw, texts):
            header = self.plugin.header(str(q.get("header", "")), skill)
            counts = self.questions[skill][header]
            answer = str(result["answers"][text])
            labels = [str(o.get("label", "")) for o in q.get("options") or [] if isinstance(o, dict)]
            recommended = [label for label in labels if label.endswith("(Recommended)")]
            if answer in recommended:
                counts["recommended"] += 1
            elif answer in labels or (q.get("multiSelect") and answer and all(part in labels for part in answer.split(", "))):
                counts["other_option"] += 1
            else:
                counts["free_text"] += 1
                self.free_text[skill][header].append(len(answer))

    def agent(self, path: Path, meta: dict, entries: list[dict]) -> None:
        """One agent's transcript: its tokens, model, scripts, hooks and denials, and the agents it started. A fork's
        transcript opens with a copy of its parent's, through the result of the call that started it; the copy is
        the parent's use and is skipped."""
        launched_by = meta.get("toolUseId")
        for n, e in enumerate(entries):
            if e["type"] == "user" and any(b["tool_use_id"] == launched_by for b in tool_results(e, path)):
                entries = entries[n + 1:]
                break
        own = 0
        denied: list[tuple[str, str]] = []
        tools: dict[str, str] = {}
        scripts: dict[str, list[str]] = {}
        models: Counter = Counter()
        children = []
        for e in entries:
            self.environment(e)
            if e["type"] == "assistant":
                own += self.request_tokens(e, path)
                model = e["message"].get("model")
                if isinstance(model, str) and model != "<synthetic>":
                    models[model if MODEL.match(model) else OTHER] += 1
                for call in tool_uses(e, path):
                    tools[call["id"]] = call["name"]
                    if call["name"] in ("Agent", "Task"):
                        children.append(call["id"])
                    called = self.script_calls(call)
                    if called:
                        scripts[call["id"]] = called
            elif e["type"] == "user":
                for block in tool_results(e, path):
                    for name in scripts.pop(block["tool_use_id"], []):
                        self.scripts[name]["runs"] += 1
                        self.scripts[name][exit_word(block, e.get("toolUseResult"))] += 1
                    if block.get("is_error"):
                        found = denial(result_text(block.get("content")))
                        if found:
                            denied.append((tool_word(tools.get(block["tool_use_id"], OTHER)), found))
            elif e["type"] == "attachment":
                self.hook(e)
        name = self.plugin.named(meta["agentType"], self.plugin.agents)
        if isinstance(launched_by, str):
            self.agent_tokens[launched_by] = own
            self.agent_children[launched_by] = children
            if name is None:
                self.agent_denials[launched_by] = denied
        if name is not None:
            for tool, kind in denied:
                self.denials[tool][kind] += 1
            self.agents.append({"name": name, "tokens": own, "model": models.most_common(1)[0][0] if models else OTHER,
                                "finished": meta.get("finished") is not False})
            cwd = next((e["cwd"] for e in entries if isinstance(e.get("cwd"), str)), None)
            if cwd:
                self.cwds.add(cwd)

    def lineage(self, tool_use_id: str, depth: int = 0) -> list[str]:
        """The agent started by `tool_use_id` and every agent below it."""
        if depth > 20:
            raise UsageError(f"agent {tool_use_id} nests more than 20 deep")
        return [tool_use_id] + [d for c in self.agent_children.get(tool_use_id, []) for d in self.lineage(c, depth + 1)]

    def payload(self, commit: str, start: str, end: str, repos: dict) -> dict:
        for run in self.runs:
            for a in run["agents"]:
                for d in self.lineage(a):
                    for tool, kind in self.agent_denials.get(d, []):
                        self.denials[tool][kind] += 1
        skills: dict = {}
        for name in sorted({r["skill"] for r in self.runs}):
            runs = [r for r in self.runs if r["skill"] == name]
            skills[name] = nonzero({
                "runs": len(runs),
                "typed": sum(r["typed"] for r in runs),
                "model_triggered": sum(not r["typed"] for r in runs),
                "reruns": sum(r["rerun"] for r in runs),
                "compacted": sum(r["compacted"] for r in runs),
            }) | {
                "turns": spread([r["turns"] for r in runs]),
                "tokens": spread([r["tokens"] + sum(self.agent_tokens.get(d, 0) for a in r["agents"] for d in self.lineage(a)) for r in runs]),
            }
        questions = {
            skill: {
                header: nonzero({**{t: counts[t] for t in ANSWER_TYPES},
                                 "free_text_median_chars": nearest_rank(self.free_text[skill][header], 0.5) if self.free_text[skill][header] else 0})
                for header, counts in sorted(headers.items())
            }
            for skill, headers in sorted(self.questions.items())
        }
        agents: dict = {}
        for name in sorted({a["name"] for a in self.agents}):
            runs = [a for a in self.agents if a["name"] == name]
            agents[name] = {"runs": len(runs), "models": dict(sorted(Counter(a["model"] for a in runs).items())),
                            "tokens": spread([a["tokens"] for a in runs]), **nonzero({"unfinished": sum(not a["finished"] for a in runs)})}
        return {
            "schema": SCHEMA,
            "plugin_commit": commit,
            "claude_code_versions": sorted(self.versions),
            "models": sorted(self.models),
            "window": {"start": start + "Z", "end": end + "Z"},
            "repos": nonzero(repos),
            "sessions": self.sessions,
            "turns": self.turns,
            "skills": skills,
            "questions": questions,
            "scripts": {n: {"runs": c["runs"], "exits": {k: v for k, v in sorted(c.items()) if k != "runs"}} for n, c in sorted(self.scripts.items())},
            "hooks": {n: nonzero({k: c[k] for k in ("runs",) + HOOK_OUTCOMES}) for n, c in sorted(self.hooks.items())},
            "denials": {t: dict(sorted(c.items())) for t, c in sorted(self.denials.items())},
            "chains": {
                "transitions": dict(sorted(self.transitions.items())),
                "push_after": {n: v for n, v in sorted(Counter(r["skill"] for r in self.runs if r["push"]).items())},
                "pr_open_after": {n: v for n, v in sorted(Counter(r["skill"] for r in self.runs if r["pr_open"]).items())},
            },
            "after_run": None,
            "agents": agents,
            "overlap": None,
            "notes": None,
        }

    def pending(self) -> list[dict]:
        recent = sorted(self.runs, key=lambda r: r["started"])[-PENDING_RUNS:]
        return [{"skill": r["skill"], "started": r["started"], "next_message": r["next"]} for r in recent]


def window_start(since: str, now: datetime) -> datetime:
    """`--since`, a date or a UTC time to the second, as a UTC datetime before `now`."""
    try:
        start = datetime.strptime(since[:19], "%Y-%m-%dT%H:%M:%S") if TIMESTAMP.match(since) else datetime.strptime(since, "%Y-%m-%d")
    except ValueError as e:
        raise UsageError(f"--since {since!r} is not a date YYYY-MM-DD or a UTC time such as 2026-11-01T00:00:00Z") from e
    start = start.replace(tzinfo=timezone.utc)
    if start >= now:
        raise UsageError(f"--since {since!r} is not before now, {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    return start


def project_skill(path: Path, e: dict, name: str) -> bool:
    """Whether a typed `name` is a skill or command of the project at the entry's working directory, whose typed start ends a run."""
    if not isinstance(e.get("cwd"), str):
        raise UsageError(f"{path}: a typed command's entry has no cwd")
    claude = Path(e["cwd"]) / ".claude"
    return (claude / "skills" / name).is_dir() or (claude / "commands" / f"{name}.md").is_file()


def personal_skills(config: Path) -> set[str]:
    """The person's own skills and commands under the config directory, whose typed start ends a run."""
    return {p.parent.name for p in config.glob("skills/*/SKILL.md")} | {p.stem for p in config.glob("commands/*.md")}


def repos(cwds: set[str]) -> dict:
    """How many repositories the plugin was used in, told apart by their git directory, and how many hold `standards/profile.yaml`.
    A working directory that is gone or is no git repository counts as `not_a_repository`; any other git failure raises."""
    found: dict[str, bool] = {}
    missing = 0
    for cwd in sorted(cwds):
        if not Path(cwd).is_dir():
            missing += 1
            continue
        p = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel", "--git-common-dir"], capture_output=True, text=True)
        if p.returncode != 0 and "not a git repository" in p.stderr:
            missing += 1
            continue
        if p.returncode != 0:
            raise UsageError(f"git cannot read the repository at {cwd}: {p.stderr.strip()}")
        top, common = p.stdout.splitlines()[:2]
        key = str((Path(cwd) / common).resolve())
        found[key] = found.get(key, False) or (Path(top) / "standards" / "profile.yaml").is_file()
    return {"with_plugin_use": len(found), "with_standard": sum(found.values()), "not_a_repository": missing}


def build(plugin: Plugin, config: Path, start: datetime, end: datetime) -> tuple[dict, list[dict]]:
    report = Report(plugin, personal_skills(config))
    lo, hi = start.strftime("%Y-%m-%dT%H:%M:%S"), end.strftime("%Y-%m-%dT%H:%M:%S")
    opens = start.timestamp()
    sandboxes: set[Path] = set()
    for path in sorted(config.glob("projects/*/*.jsonl"), key=lambda p: (p.stat().st_mtime, p)):
        if path.stat().st_mtime < opens:
            continue
        entries, sandbox = windowed(path, lo, hi)
        if sandbox:
            sandboxes.add(path.with_suffix(""))
        elif entries:
            report.session(path, entries)
    for path in sorted(config.glob("projects/*/*/subagents/*.jsonl")):
        if path.stat().st_mtime < opens or path.parent.parent in sandboxes:
            continue
        entries, sandbox = windowed(path, lo, hi)
        if not entries or sandbox:
            continue
        meta_path = path.with_suffix(".meta.json")
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise UsageError(f"{path}: its {meta_path.name} cannot be read as JSON: {e}") from e
        if not isinstance(meta, dict) or not isinstance(meta.get("agentType"), str):
            raise UsageError(f"{meta_path} has no agentType")
        report.agent(path, meta, entries)
    payload = report.payload(plugin.commit(), lo, hi, repos(report.cwds))
    return payload, report.pending()


def text_of(payload: dict) -> str:
    """The payload as written: keys sorted, two-space indents, non-ASCII kept, one final newline."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def read_json(path: Path, kind: type, what: str):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise UsageError(f"{path} is not a readable {what}: {e}") from e
    if not isinstance(data, kind):
        raise UsageError(f"{path} is not a {what}: it holds a {type(data).__name__}")
    return data


def fill(args: argparse.Namespace) -> dict:
    """The payload at `args.fill` with `after_run`, `overlap` and `notes` replaced, each when its flag is given."""
    payload = read_json(args.fill, dict, "payload")
    if not {"schema", "window", "after_run", "overlap", "notes"} <= set(payload):
        raise UsageError(f"{args.fill} is not a payload this script wrote: it lacks schema, window, after_run, overlap or notes")
    if args.labels is not None:
        runs = read_json(args.pending, list, "pending file")
        if len(args.labels) != len(runs):
            raise UsageError(f"{len(args.labels)} labels for the {len(runs)} runs in {args.pending}; give one per run, in its order")
        after: dict = defaultdict(Counter)
        for n, (run, label) in enumerate(zip(runs, args.labels), 1):
            if not isinstance(run, dict) or not isinstance(run.get("skill"), str) or not isinstance(run.get("next_message", 0), (str, type(None))):
                raise UsageError(f"{args.pending}: run {n} is not {{skill, started, next_message}}")
            if (run.get("next_message") is None) != (label == "none"):
                said = "has no next message, so it is none" if run.get("next_message") is None else "has a next message, so it is not none"
                raise UsageError(f"run {n} ({run['skill']}) {said}; it was given {label}")
            after[run["skill"]][label] += 1
        payload["after_run"] = {skill: dict(sorted(c.items())) for skill, c in sorted(after.items())}
    if args.overlap is not None:
        plugin = Plugin(args.plugin_root)
        counts: dict = {"skills": {}, "agents": {}}
        for item in args.overlap:
            m = OVERLAP_ITEM.fullmatch(item)
            kind = f"{m.group(1)}s" if m else None
            if not m or m.group(2) not in getattr(plugin, kind):
                raise UsageError(f"overlap item {item!r} is not skill:<name>=<n> or agent:<name>=<n> for a skill or agent of {args.plugin_root}, n 1 or more")
            if m.group(2) in counts[kind]:
                raise UsageError(f"overlap names {m.group(1)} {m.group(2)} twice")
            counts[kind][m.group(2)] = int(m.group(3))
        payload["overlap"] = {kind: dict(sorted(c.items())) for kind, c in counts.items()}
    if args.notes is not None:
        try:
            notes = args.notes.read_text(encoding="utf-8").strip()
        except (OSError, ValueError) as e:
            raise UsageError(f"{args.notes} cannot be read as text: {e}") from e
        payload["notes"] = notes or None
    return payload


# What each mode needs, and what else it may be given.
MODES = {
    "build": ({"plugin_root", "out", "pending", "since"}, set()),
    "fill": (set(), {"plugin_root", "pending", "labels", "overlap", "notes"}),
}
OPTIONS = ("plugin_root", "out", "pending", "since", "labels", "overlap", "notes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plugin-root", type=Path, help="the installed plugin's directory")
    parser.add_argument("--out", type=Path, help="where the payload is written")
    parser.add_argument("--pending", type=Path, help="where the runs awaiting classification are written, or read by --labels; the skill passes a path under $TMPDIR")
    parser.add_argument("--since", metavar="YYYY-MM-DD|YYYY-MM-DDTHH:MM:SSZ", help="open the window on this date or UTC time")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help=f"refuse a payload larger than this (default {DEFAULT_MAX_BYTES})")
    parser.add_argument("--fill", type=Path, metavar="PAYLOAD", help="fill a written payload's after_run, overlap or notes, and print it")
    parser.add_argument("--labels", nargs="*", choices=OUTCOMES, help="with --fill: one outcome per run of --pending, in its order")
    parser.add_argument("--overlap", nargs="*", metavar="KIND:NAME=N", help="with --fill: skill:<name>=<n> or agent:<name>=<n> per plugin skill or agent with competitors")
    parser.add_argument("--notes", type=Path, help="with --fill: a file holding the person's notes")
    args = parser.parse_args(argv)
    name = "fill" if args.fill else "build"
    needed, optional = MODES[name]
    given = {o for o in OPTIONS if getattr(args, o) is not None}
    if needed - given:
        parser.error(f"{name} needs --{', --'.join(sorted(o.replace('_', '-') for o in needed - given))}")
    if given - needed - optional:
        parser.error(f"{name} takes no --{', --'.join(sorted(o.replace('_', '-') for o in given - needed - optional))}")
    if name == "fill" and not given & {"labels", "overlap", "notes"}:
        parser.error("--fill needs --labels, --overlap or --notes")
    if name == "fill" and (args.labels is not None and args.pending is None or args.overlap is not None and args.plugin_root is None):
        parser.error("--labels needs --pending, and --overlap needs --plugin-root")
    try:
        if name == "fill":
            payload, pending = fill(args), None
        else:
            config = Path(os.environ["CLAUDE_CONFIG_DIR"]) if os.environ.get("CLAUDE_CONFIG_DIR") else Path.home() / ".claude"
            now = datetime.now(timezone.utc)
            start = window_start(args.since, now)
            payload, pending = build(Plugin(args.plugin_root), config, start, now)
        text = text_of(payload)
        size = len(text.encode("utf-8"))
        if size > args.max_bytes:
            raise UsageError(f"the payload is {size} bytes, over --max-bytes {args.max_bytes}; nothing was written")
    except UsageError as e:
        print(f"usage_report.py: {e}", file=sys.stderr)
        return 1
    if name == "fill":
        args.fill.write_text(text, encoding="utf-8")
        print(text + f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    args.pending.parent.mkdir(parents=True, exist_ok=True)
    args.pending.write_text(json.dumps(pending, indent=2) + "\n", encoding="utf-8")
    runs = sum(s["runs"] for s in payload["skills"].values())
    agent_runs = sum(a["runs"] for a in payload["agents"].values())
    print(f"usage report: {runs} plugin skill runs, {agent_runs} plugin agent runs, {payload['window']['start']} to "
          f"{payload['window']['end']}; payload {size} bytes at {args.out}; {len(pending)} runs to classify at {args.pending}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
