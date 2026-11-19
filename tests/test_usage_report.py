"""Tests for scripts/usage_report.py. Run with `python3 -m unittest discover -s tests`."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("usage_report", ROOT / "scripts" / "usage_report.py")
usage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(usage)

NOW = datetime.now(timezone.utc)
COMMIT = "abcdef012345"
PERSONAL = "zanzibar-pr-review"


def stamp(days_ago=0.0, seconds=0):
    return (NOW - timedelta(days=days_ago) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Transcript:
    """A main transcript built entry by entry, each a second after the last."""

    def __init__(self, days_ago=1.0):
        self.entries = []
        self.days_ago = days_ago
        self.n = 0

    def add(self, entry):
        self.n += 1
        entry.setdefault("timestamp", stamp(self.days_ago, self.n))
        entry.setdefault("version", "2.1.300")
        entry.setdefault("cwd", "/nonexistent/repo")
        entry.setdefault("uuid", uuid.uuid4().hex)
        self.entries.append(entry)
        return self

    def person(self, text):
        return self.add({"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": text}})

    def typed(self, command):
        return self.add({"type": "user", "message": {"role": "user", "content": f"<command-name>{command}</command-name>"}})

    def claude(self, *blocks, request=None, usage_=None, model="claude-opus-5-5"):
        message = {"role": "assistant", "model": model, "content": list(blocks)}
        if usage_ is not None:
            message["usage"] = usage_
        entry = {"type": "assistant", "message": message}
        if request:
            entry["requestId"] = request
        return self.add(entry)

    def result(self, use_id, content, is_error=False, tool_result=None):
        entry = {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": use_id, "content": content, "is_error": is_error}]}}
        if tool_result is not None:
            entry["toolUseResult"] = tool_result
        return self.add(entry)


def call(use_id, name, **tool_input):
    return {"type": "tool_use", "id": use_id, "name": name, "input": tool_input}


def hook_attachment(name, decision=None, kind="hook_success"):
    stdout = json.dumps({"hookSpecificOutput": {"permissionDecision": decision}}) if decision else ""
    return {"type": "attachment", "attachment": {"type": kind, "hookName": "PreToolUse:Bash", "hookEvent": "PreToolUse",
                                                 "command": f'"${{CLAUDE_PLUGIN_ROOT}}/hooks/{name}.sh"', "stdout": stdout}}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config = self.tmp / "config"
        self.plugin = self.tmp / "cache" / "lasp-dev" / COMMIT
        (self.plugin / ".claude-plugin").mkdir(parents=True)
        (self.plugin / ".claude-plugin" / "plugin.json").write_text('{"name": "lasp-dev"}')
        for skill in ("work", "commit", "pr-review"):
            (self.plugin / "skills" / skill).mkdir(parents=True)
            (self.plugin / "skills" / skill / "SKILL.md").write_text("Ask the Next step question, then the Scope question.\n")
        (self.plugin / "agents").mkdir()
        (self.plugin / "agents" / "test-runner.md").write_text("x")
        (self.plugin / "scripts").mkdir()
        (self.plugin / "scripts" / "profile.py").write_text("x")
        (self.plugin / "hooks").mkdir()
        (self.plugin / "hooks" / "secret-gate.sh").write_text("x")
        shutil.copy(ROOT / "scripts" / "coupling.json", self.plugin / "scripts")
        (self.config / "skills" / PERSONAL).mkdir(parents=True)
        (self.config / "skills" / PERSONAL / "SKILL.md").write_text("x")
        (self.config / "agents").mkdir()
        (self.config / "agents" / "test-runner.md").write_text("x")
        self.session_count = 0

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, transcript, project="-proj"):
        self.session_count += 1
        path = self.config / "projects" / project / f"s{self.session_count}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(e) + "\n" for e in transcript.entries))
        return path

    def write_agent(self, session_path, agent_id, meta, transcript):
        directory = session_path.with_suffix("") / "subagents"
        directory.mkdir(parents=True, exist_ok=True)
        for e in transcript.entries:
            e["isSidechain"] = True
        (directory / f"agent-{agent_id}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in transcript.entries))
        if meta is not None:
            (directory / f"agent-{agent_id}.meta.json").write_text(json.dumps(meta))

    def run_report(self, *extra, since=stamp(30)):
        out, pending = self.tmp / "out" / "payload.json", self.tmp / "out" / "pending.json"
        argv = ["--plugin-root", str(self.plugin), "--since", since, "--out", str(out), "--pending", str(pending), *extra]
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config)}), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = usage.main(argv)
        payload = json.loads(out.read_text()) if code == 0 else None
        runs = json.loads(pending.read_text()) if code == 0 else None
        return code, payload, runs, stderr.getvalue()

    def ok(self, *extra, since=stamp(30)):
        code, payload, runs, err = self.run_report(*extra, since=since)
        self.assertEqual(code, 0, err)
        return payload, runs


FIELDS = {"schema", "plugin_commit", "claude_code_versions", "models", "window", "repos", "sessions", "turns", "skills",
          "questions", "scripts", "hooks", "denials", "chains", "after_run", "agents", "overlap", "notes"}
SKILLS, AGENTS, SCRIPTS, HOOKS = {"work", "commit", "pr-review"}, {"test-runner"}, {"profile"}, {"secret-gate"}
HEADERS = {"Next step", "Scope"}
BUILTIN_TOOLS = {"Agent", "AskUserQuestion", "Bash", "Edit", "Read", "Skill", "Write"}
CATEGORIES = {"Git Destructive"}
SPREAD = {"median", "p90"}


def outside_vocabulary(p):
    """Each value or key of the payload not allowed at its own position, as `path: value`."""
    bad = []

    def check(where, value, allowed):
        if not (allowed(value) if callable(allowed) else value in allowed):
            bad.append(f"{where}: {value!r}")

    def counts(where, record, keys):
        for k, v in record.items():
            check(where, k, keys)
            check(f"{where}.{k}", v, lambda n: type(n) is int and n > 0)

    def spread(where, record):
        check(where, set(record), lambda keys: keys == SPREAD)
        for v in record.values():
            check(where, v, lambda n: type(n) is int and n >= 0)

    def fullmatch(pattern):
        return lambda v: isinstance(v, str) and re.fullmatch(pattern, v) is not None

    def names(group):
        return group | {"other"}

    check("keys", set(p), lambda keys: keys == FIELDS)
    check("schema", p["schema"], {1})
    check("plugin_commit", p["plugin_commit"], fullmatch(r"[0-9a-f]{12}"))
    for v in p["claude_code_versions"]:
        check("claude_code_versions", v, lambda v: v == "other" or fullmatch(r"\d+\.\d+\.\d+")(v))
    for v in p["models"]:
        check("models", v, lambda v: v == "other" or fullmatch(r"claude-(opus|sonnet|haiku|fable)-[0-9-]+")(v))
    check("window", set(p["window"]), lambda keys: keys == {"start", "end"})
    for v in p["window"].values():
        check("window", v, fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"))
    counts("repos", p["repos"], {"with_plugin_use", "with_standard", "not_a_repository"})
    for k in ("sessions", "turns"):
        check(k, p[k], lambda n: type(n) is int and n >= 0)
    for skill, record in p["skills"].items():
        check("skills", skill, names(SKILLS))
        counts(f"skills.{skill}", {k: v for k, v in record.items() if k not in ("turns", "tokens")},
               {"runs", "typed", "model_triggered", "reruns", "compacted"})
        spread(f"skills.{skill}.turns", record["turns"])
        spread(f"skills.{skill}.tokens", record["tokens"])
    for skill, headers in p["questions"].items():
        check("questions", skill, names(SKILLS))
        for header, record in headers.items():
            check(f"questions.{skill}", header, names(HEADERS))
            counts(f"questions.{skill}.{header}", record, set(usage.ANSWER_TYPES) | {"free_text_median_chars"})
    for script, record in p["scripts"].items():
        check("scripts", script, SCRIPTS)
        check(f"scripts.{script}", set(record), lambda keys: keys == {"runs", "exits"})
        counts(f"scripts.{script}.exits", record["exits"], lambda k: k in usage.EXIT_WORDS or k.isdigit())
    for hook, record in p["hooks"].items():
        check("hooks", hook, HOOKS)
        counts(f"hooks.{hook}", record, {"runs", *usage.HOOK_OUTCOMES})
    for tool, record in p["denials"].items():
        check("denials", tool, BUILTIN_TOOLS | {f"mcp__{t}" for t in usage.MCP_TOOLS} | {"mcp__other"})
        counts(f"denials.{tool}", record, set(usage.DENIAL_KINDS) | CATEGORIES | {"other"})
    check("chains", set(p["chains"]), lambda keys: keys == {"transitions", "push_after", "pr_open_after"})
    counts("chains.transitions", p["chains"]["transitions"],
           lambda k: len(k.split(" -> ")) == 2 and all(n in names(SKILLS) for n in k.split(" -> ")))
    counts("chains.push_after", p["chains"]["push_after"], names(SKILLS))
    counts("chains.pr_open_after", p["chains"]["pr_open_after"], names(SKILLS))
    for agent, record in p["agents"].items():
        check("agents", agent, names(AGENTS))
        counts(f"agents.{agent}", {k: v for k, v in record.items() if k not in ("models", "tokens")}, {"runs", "unfinished"})
        counts(f"agents.{agent}.models", record["models"], lambda v: v == "other" or fullmatch(r"claude-(opus|sonnet|haiku|fable)-[0-9-]+")(v))
        spread(f"agents.{agent}.tokens", record["tokens"])
    if p["overlap"] is not None:
        check("overlap", set(p["overlap"]), lambda keys: keys == {"skills", "agents"})
        counts("overlap.skills", p["overlap"]["skills"], SKILLS)
        counts("overlap.agents", p["overlap"]["agents"], AGENTS)
    for skill, record in (p["after_run"] or {}).items():
        check("after_run", skill, names(SKILLS))
        counts(f"after_run.{skill}", record, set(usage.OUTCOMES))
    # The person's notes are their own words, the one field outside the vocabulary.
    check("notes", p["notes"], lambda v: v is None or isinstance(v, str))
    return bad


def busy_session():
    """A session touching every field group."""
    t = Transcript()
    t.typed("/lasp-dev:work")
    t.claude({"type": "text", "text": "x"}, request="r1", usage_={"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100})
    t.claude(call("a1", "Agent", subagent_type="lasp-dev:test-runner"), request="r1",
             usage_={"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100})
    t.claude(call("q1", "AskUserQuestion", questions=[
        {"question": "Go?", "header": "Next step", "options": [{"label": "Go (Recommended)"}, {"label": "Stop"}]},
        {"question": "Where?", "header": "Marmot", "options": [{"label": "Here (Recommended)"}]},
    ]))
    t.result("q1", "answered", tool_result={"answers": {"Go?": "Go (Recommended)", "Where?": "somewhere private"}})
    t.claude(call("b1", "Bash", command="python3 /x/plugins/cache/lasp-dev-tools/lasp-dev/123/scripts/profile.py --standard"))
    t.result("b1", "Exit code 1\nno", is_error=True)
    t.add(hook_attachment("secret-gate", "ask"))
    t.add(hook_attachment("someone-elses", "deny"))
    t.claude(call("b2", "Bash", command="rm -rf ~"))
    t.result("b2", "Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Git Destructive]. More.",
             is_error=True)
    t.claude(call("m1", "mcp__private-server__issue_write", title="x"))
    t.result("m1", "Permission to use mcp__private-server__issue_write has been denied.", is_error=True)
    t.add({"type": "system", "subtype": "compact_boundary"})
    t.person("looks good, go on")
    t.claude(call("s1", "Skill", skill="lasp-dev:commit"))
    t.claude(call("b3", "Bash", command="git push origin HEAD"))
    t.person("thanks")
    t.claude(call("s2", "Skill", skill=PERSONAL))
    return t


class FieldGroups(Fixture):
    def setUp(self):
        super().setUp()
        session = self.write(busy_session())
        agent = Transcript()
        agent.claude({"type": "text", "text": "x"}, request="ra", usage_={"input_tokens": 1000, "output_tokens": 0},
                     model="claude-haiku-5-5")
        agent.claude(call("ab", "Bash", command="${CLAUDE_PLUGIN_ROOT}/scripts/profile.py"), request="ra",
                     usage_={"input_tokens": 1000, "output_tokens": 0}, model="claude-haiku-5-5")
        agent.result("ab", "ok", tool_result={"stdout": "", "backgroundTaskId": "x"})
        self.write_agent(session, "x1", {"agentType": "lasp-dev:test-runner", "toolUseId": "a1", "finished": False}, agent)
        personal = Transcript()
        personal.claude({"type": "text", "text": "x"}, request="rp", usage_={"input_tokens": 7, "output_tokens": 0})
        self.write_agent(session, "x2", {"agentType": "test-runner", "toolUseId": "zz"}, personal)
        self.payload, self.pending = self.ok()

    def test_the_payload_has_the_contract_fields(self):
        self.assertEqual(set(self.payload), FIELDS)
        self.assertEqual(self.payload["schema"], 1)
        for field in ("after_run", "overlap", "notes"):
            self.assertIsNone(self.payload[field], f"{field} is the skill's to fill")
        self.assertNotIn("reruns", self.payload["skills"]["work"], "a count of zero is left out")
        self.assertNotIn("declined", self.payload["questions"]["work"]["Next step"])

    def test_environment(self):
        p = self.payload
        self.assertEqual(p["plugin_commit"], COMMIT)
        self.assertEqual(p["claude_code_versions"], ["2.1.300"])
        self.assertEqual(p["models"], ["claude-haiku-5-5", "claude-opus-5-5"])
        self.assertEqual((p["sessions"], p["turns"]), (1, 3))
        self.assertEqual(p["repos"], {"not_a_repository": 1})
        self.assertTrue(p["window"]["start"] < p["window"]["end"])

    def test_skill_runs(self):
        work = self.payload["skills"]["work"]
        self.assertEqual((work["runs"], work["typed"], work.get("model_triggered")), (1, 1, None))
        self.assertEqual(work["turns"], {"median": 2, "p90": 2})
        self.assertEqual(work["tokens"]["median"], 115 + 1000, "one request counted once, plus the agent it started")
        self.assertEqual(work["compacted"], 1)
        commit = self.payload["skills"]["commit"]
        self.assertEqual((commit["runs"], commit.get("typed"), commit["model_triggered"]), (1, None, 1))
        self.assertEqual(commit["turns"], {"median": 1, "p90": 1}, "a model-triggered run's turns start at the next message")

    def test_questions(self):
        questions = self.payload["questions"]["work"]
        self.assertEqual(questions["Next step"]["recommended"], 1)
        self.assertEqual(questions["other"]["free_text"], 1)
        self.assertEqual(questions["other"]["free_text_median_chars"], len("somewhere private"))

    def test_scripts_hooks_and_denials(self):
        p = self.payload
        self.assertEqual(p["scripts"]["profile"], {"runs": 2, "exits": {"1": 1, "background": 1}})
        self.assertEqual(p["hooks"], {"secret-gate": {"runs": 1, "ask": 1}})
        self.assertEqual(p["denials"], {"Bash": {"Git Destructive": 1}, "mcp__issue_write": {"permission_denied": 1}})

    def test_chains(self):
        chains = self.payload["chains"]
        self.assertEqual(chains["transitions"], {"work -> commit": 1, "commit -> other": 1})
        self.assertEqual(chains["push_after"], {"commit": 1})
        self.assertEqual(chains["pr_open_after"], {})

    def test_agents(self):
        self.assertEqual(self.payload["agents"], {"test-runner": {
            "runs": 1, "models": {"claude-haiku-5-5": 1}, "tokens": {"median": 1000, "p90": 1000}, "unfinished": 1}})

    def test_a_personal_skill_name_never_appears(self):
        text = json.dumps(self.payload)
        self.assertNotIn("zanzibar", text)
        self.assertNotIn("Marmot", text)
        self.assertNotIn("somewhere private", text)
        self.assertNotIn("private-server", text)

    def test_every_payload_value_is_in_the_vocabulary_of_its_position(self):
        self.assertEqual(outside_vocabulary(self.payload), [])

    def test_the_vocabulary_check_finds_a_value_out_of_place(self):
        planted = json.loads(json.dumps(self.payload))
        planted["questions"]["work"]["Marmot"] = {"free_text": 1}
        planted["denials"]["Bash"]["Next step"] = 1
        planted["skills"]["work"]["reruns"] = 0
        self.assertEqual(len(outside_vocabulary(planted)), 3)

    def test_the_pending_file_holds_the_next_message(self):
        self.assertEqual([r["skill"] for r in self.pending], ["work", "commit"])
        self.assertEqual(self.pending[0]["next_message"], "looks good, go on")
        self.assertEqual(self.pending[1]["next_message"], "thanks")


class Bucketing(Fixture):
    def test_names_outside_the_plugin_become_other(self):
        t = Transcript()
        t.typed("/libera-tools:work").person("ok")
        t.claude(call("s1", "Skill", skill="lasp-dev:retired-skill"))
        t.claude(call("b1", "Bash", command="ls"))
        t.result("b1", "Permission for this action was denied by the Claude Code auto mode classifier. Reason: [weird: thing]",
                 is_error=True)
        t.claude(call("s2", "Skill", skill="other-plugin:work"), model="gpt-something")
        self.write(t)
        payload, _ = self.ok()
        self.assertEqual(sorted(payload["skills"]), ["other", "work"])
        self.assertEqual(payload["chains"]["transitions"], {"work -> other": 1, "other -> other": 1})
        self.assertEqual(payload["denials"], {"Bash": {"other": 1}})
        self.assertIn("other", payload["models"])

    def test_hook_outcomes(self):
        t = Transcript().person("hi")
        t.add(hook_attachment("secret-gate", "deny"))
        t.add(hook_attachment("secret-gate", kind="hook_cancelled"))  # codespell:ignore cancelled
        t.add(hook_attachment("secret-gate", kind="hook_non_blocking_error"))
        self.write(t)
        payload, _ = self.ok()
        self.assertEqual(payload["hooks"]["secret-gate"], {"runs": 3, "deny": 1, "canceled": 1, "error": 1})

    def test_a_typed_personal_skill_ends_the_run(self):
        t = Transcript()
        t.typed("/lasp-dev:work").person("one").typed(f"/{PERSONAL}").person("two")
        self.write(t)
        payload, runs = self.ok()
        self.assertEqual(payload["skills"]["work"]["turns"]["median"], 2)
        self.assertEqual(payload["chains"]["transitions"], {"work -> other": 1})

    def test_a_typed_project_skill_or_command_ends_the_run(self):
        project = self.tmp / "project"
        (project / ".claude" / "skills" / "zanzibar-check").mkdir(parents=True)
        (project / ".claude" / "commands").mkdir()
        (project / ".claude" / "commands" / "zanzibar-ship.md").write_text("x")
        for name in ("zanzibar-check", "zanzibar-ship"):
            t = Transcript()
            t.typed("/lasp-dev:work").person("one").typed(f"/{name}").person("two").person("three")
            for e in t.entries:
                e["cwd"] = str(project)
            self.write(t)
        payload, _ = self.ok()
        self.assertEqual(payload["skills"]["work"]["turns"], {"median": 2, "p90": 2})
        self.assertEqual(payload["chains"]["transitions"], {"work -> other": 2})
        self.assertNotIn("zanzibar", json.dumps(payload))

    def test_a_rerun_within_three_turns_is_counted(self):
        t = Transcript()
        t.typed("/lasp-dev:work").person("a").typed("/lasp-dev:work")
        t.person("b").person("c").person("d").person("e").typed("/lasp-dev:work")
        self.write(t)
        payload, _ = self.ok()
        self.assertEqual(payload["skills"]["work"]["reruns"], 1)

    def test_a_header_only_another_skill_holds_is_other(self):
        (self.plugin / "skills" / "commit" / "SKILL.md").write_text("Ask the Zebra phase question.\n")
        t = Transcript()
        t.typed("/lasp-dev:work")
        t.claude(call("q", "AskUserQuestion", questions=[{"question": "Q", "header": "Zebra phase", "options": [{"label": "A"}]}]))
        t.result("q", "x", tool_result={"answers": {"Q": "A"}})
        self.write(t)
        payload, _ = self.ok()
        self.assertEqual(list(payload["questions"]["work"]), ["other"])

    def test_question_answer_types(self):
        t = Transcript()
        t.typed("/lasp-dev:work")
        options = [{"label": "A (Recommended)"}, {"label": "B"}, {"label": "C"}]
        for n, result in enumerate([{"answers": {"Q": "B"}}, "User rejected tool use", "Error: something broke",
                                    {"answers": {"Q": "B, C"}}]):
            t.claude(call(f"q{n}", "AskUserQuestion", questions=[{"question": "Q", "header": "Scope", "options": options,
                                                                    "multiSelect": n == 3}]))
            t.result(f"q{n}", "x", is_error=isinstance(result, str), tool_result=result)
        self.write(t)
        payload, _ = self.ok()
        self.assertEqual(payload["questions"]["work"]["Scope"], {"other_option": 2, "declined": 1, "not_shown": 1})


class Leaks(Fixture):
    def test_a_word_in_every_free_text_slot_never_appears(self):
        t = Transcript()
        t.typed("/lasp-dev:work")
        t.entries[-1]["cwd"] = str(self.tmp / "Marmot")
        t.claude(call("q", "AskUserQuestion", questions=[{"question": "Q", "header": "Marmot", "options": [{"label": "A"}]}]),
                 model="claude-marmot-5")
        t.result("q", "x", tool_result={"answers": {"Q": "A"}})
        t.add({"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": "go"}, "version": "Marmot"})
        t.claude(call("a1", "Agent"), call("a2", "Agent"), model="Marmot")
        t.claude(call("b", "Bash", command="ls"), call("m", "mcp__Marmot__Marmot_write", body="x"))
        t.result("b", "Permission for this action was denied by the Claude Code auto mode classifier. Reason: [Marmot]", is_error=True)
        t.result("m", "Permission to use mcp__Marmot__Marmot_write has been denied.", is_error=True)
        t.claude(call("s1", "Skill", skill="lasp-dev:Marmot"))
        t.claude(call("s2", "Skill", skill="Marmot"))
        session = self.write(t)
        for n, agent_type in enumerate(("Marmot", "lasp-dev:Marmot")):
            agent = Transcript()
            agent.claude({"type": "text", "text": "x"}, model="claude-marmot")
            self.write_agent(session, f"x{n}", {"agentType": agent_type, "toolUseId": f"a{n + 1}"}, agent)
        payload, _ = self.ok()
        self.assertNotIn("marmot", json.dumps(payload).lower())
        self.assertEqual(outside_vocabulary(payload), [])
        self.assertEqual(payload["denials"], {"Bash": {"other": 1}, "mcp__other": {"permission_denied": 1}})

    def test_the_mcp_tools_kept_are_ones_the_plugins_skills_and_agents_name(self):
        text = "\n".join(p.read_text() for d in ("skills", "agents") for p in sorted((ROOT / d).rglob("*.md")))
        self.assertEqual([t for t in sorted(usage.MCP_TOOLS) if not re.search(rf"\b{t}\b", text)], [])
        self.assertEqual(usage.tool_word("mcp__a__proj__x"), "mcp__other")
        self.assertEqual(usage.tool_word("mcp__srv__issue_read"), "mcp__issue_read")


class Headers(Fixture):
    def test_a_header_naming_a_project_or_in_another_case_is_other(self):
        (self.plugin / "skills" / "work" / "SKILL.md").write_text("Ask the LASP question, the CSDS question and the Scope question.\n")
        t = Transcript()
        t.typed("/lasp-dev:work")
        questions = [{"question": h, "header": h, "options": [{"label": "A"}]} for h in ("LASP", "CSDS", "scope", "Scope")]
        t.claude(call("q", "AskUserQuestion", questions=questions))
        t.result("q", "x", tool_result={"answers": {h: "A" for h in ("LASP", "CSDS", "scope", "Scope")}})
        self.write(t)
        payload, _ = self.ok()
        self.assertEqual(payload["questions"]["work"], {"Scope": {"other_option": 1}, "other": {"other_option": 3}})


class Sessions(Fixture):
    def test_history_two_main_transcripts_share_is_counted_once(self):
        first = Transcript()
        first.typed("/lasp-dev:work")
        first.claude({"type": "text", "text": "x"}, request="r1", usage_={"input_tokens": 10, "output_tokens": 0})
        first.person("a")
        older = self.write(first)
        os.utime(older, (NOW.timestamp() - 3600, NOW.timestamp() - 3600))
        resumed = Transcript(days_ago=0.5)
        resumed.entries = [dict(e) for e in first.entries]
        resumed.person("b")
        resumed.claude({"type": "text", "text": "y"}, request="r2", usage_={"input_tokens": 5, "output_tokens": 0})
        resumed.typed("/lasp-dev:commit")
        self.write(resumed)
        payload, _ = self.ok()
        self.assertEqual((payload["sessions"], payload["turns"]), (2, 4))
        self.assertEqual(payload["skills"]["work"]["runs"], 1)
        self.assertEqual(payload["skills"]["work"]["turns"]["median"], 3)
        self.assertEqual(payload["skills"]["work"]["tokens"]["median"], 15)
        self.assertEqual(payload["chains"]["transitions"], {"work -> commit": 1})

    def test_a_resumed_run_does_not_make_a_later_start_a_rerun(self):
        first = Transcript()
        first.typed("/lasp-dev:work")
        for n in range(10):
            first.person(f"m{n}")
        older = self.write(first)
        os.utime(older, (NOW.timestamp() - 3600, NOW.timestamp() - 3600))
        resumed = Transcript(days_ago=0.5)
        resumed.entries = [dict(e) for e in first.entries]
        resumed.typed("/lasp-dev:work")
        self.write(resumed)
        payload, _ = self.ok()
        self.assertEqual(payload["skills"]["work"]["runs"], 2)
        self.assertNotIn("reruns", payload["skills"]["work"])

    def test_another_plugins_typed_command_ends_the_run(self):
        t = Transcript()
        t.typed("/lasp-dev:work").person("one").typed("/other-plugin:thing").person("two")
        self.write(t)
        payload, _ = self.ok()
        self.assertEqual(payload["skills"]["work"]["turns"]["median"], 2)
        self.assertEqual(payload["chains"]["transitions"], {"work -> other": 1})

    def test_a_sandbox_session_and_its_agents_are_left_out(self):
        t = Transcript()
        t.entries.append({"type": "custom-title", "customTitle": usage.SANDBOX_TITLE, "sessionId": "s"})
        t.typed("/lasp-dev:work")
        t.claude(call("a1", "Agent"))
        session = self.write(t)
        agent = Transcript()
        agent.claude({"type": "text", "text": "x"})
        self.write_agent(session, "x", {"agentType": "lasp-dev:test-runner", "toolUseId": "a1"}, agent)
        self.write(Transcript().typed("/lasp-dev:commit"))
        payload, _ = self.ok()
        self.assertEqual((payload["sessions"], sorted(payload["skills"]), payload["agents"]), (1, ["commit"], {}))

    def test_the_sandbox_runner_names_its_sessions_so(self):
        for runner in ("sandbox/sbx-claude", "sandbox/run.py"):
            self.assertIn(usage.SANDBOX_TITLE, (ROOT / runner).read_text(), runner)


class RunAgents(Fixture):
    def test_denials_in_the_agents_a_run_started_count(self):
        t = Transcript()
        t.typed("/lasp-dev:work")
        t.claude(call("g1", "Agent", subagent_type="general-purpose"))
        session = self.write(t)
        denied = "Permission to use Bash has been denied."
        for n, (launched, child) in enumerate((("g1", "g2"), ("g2", None), ("zz", None))):
            agent = Transcript()
            if child:
                agent.claude(call(child, "Agent"))
            agent.claude(call(f"b{n}", "Bash", command="ls"))
            agent.result(f"b{n}", denied, is_error=True)
            self.write_agent(session, f"x{n}", {"agentType": "general-purpose", "toolUseId": launched}, agent)
        payload, _ = self.ok()
        self.assertEqual(payload["denials"], {"Bash": {"permission_denied": 2}})


class Repos(Fixture):
    def session_in(self, cwd):
        t = Transcript().typed("/lasp-dev:work")
        t.entries[-1]["cwd"] = str(cwd)
        self.write(t)

    def test_repositories_and_plain_directories_are_told_apart(self):
        repo = self.tmp / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "standards").mkdir()
        (repo / "standards" / "profile.yaml").write_text("x")
        (self.tmp / "plain").mkdir()
        for cwd in (repo, self.tmp / "plain", self.tmp / "gone"):
            self.session_in(cwd)
        payload, _ = self.ok()
        self.assertEqual(payload["repos"], {"with_plugin_use": 1, "with_standard": 1, "not_a_repository": 2})

    def test_any_other_git_failure_raises(self):
        (self.tmp / "plain").mkdir()
        self.session_in(self.tmp / "plain")
        failed = subprocess.CompletedProcess([], 128, "", "fatal: detected dubious ownership in repository")
        with mock.patch.object(usage.subprocess, "run", return_value=failed):
            code, _, _, err = self.run_report()
        self.assertEqual(code, 1)
        self.assertIn("dubious ownership", err)


class Forks(Fixture):
    def test_a_forks_copy_of_its_parent_is_not_counted_again(self):
        t = Transcript()
        t.typed("/lasp-dev:work")
        t.claude(call("b1", "Bash", command="${CLAUDE_PLUGIN_ROOT}/scripts/profile.py"), request="r1",
                 usage_={"input_tokens": 10, "output_tokens": 0})
        t.result("b1", "ok", tool_result={"stdout": ""})
        t.claude(call("f1", "Agent", subagent_type="fork"), request="r2", usage_={"input_tokens": 10, "output_tokens": 0})
        session = self.write(t)
        fork = Transcript()
        fork.entries = [dict(e) for e in t.entries[1:]]
        fork.result("f1", "Fork started")
        fork.claude({"type": "text", "text": "x"}, request="r3", usage_={"input_tokens": 100, "output_tokens": 0})
        self.write_agent(session, "f", {"agentType": "fork", "isFork": True, "toolUseId": "f1"}, fork)
        payload, _ = self.ok()
        self.assertEqual(payload["scripts"]["profile"]["runs"], 1)
        self.assertEqual(payload["skills"]["work"]["tokens"]["median"], 120)


class Failures(Fixture):
    def assert_refused(self, entry, words):
        t = Transcript()
        t.person("hi")
        t.entries.append({"uuid": "refused", **entry})
        path = self.write(t)
        self.assert_fails(words, str(path))

    def assert_fails(self, *words, since=stamp(30), extra=()):
        code, _, _, err = self.run_report(*extra, since=since)
        self.assertEqual(code, 1, err)
        for w in words:
            self.assertIn(w, err)
        self.assertFalse((self.tmp / "out" / "payload.json").exists())

    def assistant(self, content, **message):
        return {"type": "assistant", "timestamp": stamp(1), "message": {"content": content, **message}}

    def test_an_entry_with_no_uuid_raises(self):
        self.assert_refused({"type": "user", "timestamp": stamp(1), "uuid": None, "message": {"content": "x"}}, "has no uuid")

    def test_a_typed_command_with_no_cwd_raises(self):
        self.assert_refused({"type": "user", "timestamp": stamp(1), "message": {"content": "<command-name>/zanzibar-check</command-name>"}},
                            "a typed command's entry has no cwd")

    def test_a_usage_that_is_not_a_record_raises(self):
        self.assert_refused(self.assistant([], usage="lots"), "usage is not a record")

    def test_assistant_content_that_is_not_a_list_raises(self):
        self.assert_refused(self.assistant("text"), "has no content list")

    def test_assistant_content_that_is_not_blocks_raises(self):
        self.assert_refused(self.assistant(["text"]), "holds a str, not a block")

    def test_a_tool_call_with_no_name_id_or_input_raises(self):
        self.assert_refused(self.assistant([{"type": "tool_use", "id": "x", "input": {}}]), "a tool call has no name, id or input")

    def test_a_bash_call_with_no_command_raises(self):
        self.assert_refused(self.assistant([call("b", "Bash")]), "a Bash call has no command")

    def test_user_content_that_is_neither_text_nor_a_list_raises(self):
        self.assert_refused({"type": "user", "timestamp": stamp(1), "message": {"content": 5}}, "a user entry's message has no content")

    def test_a_tool_result_with_no_tool_use_id_raises(self):
        self.assert_refused({"type": "user", "timestamp": stamp(1), "message": {"content": [{"type": "tool_result"}]}},
                            "a tool result has no tool_use_id")

    def test_an_entry_with_no_message_raises(self):
        self.assert_refused({"type": "user", "timestamp": stamp(1)}, "a user entry has no message")

    def test_an_attachment_with_no_type_raises(self):
        self.assert_refused({"type": "attachment", "timestamp": stamp(1), "attachment": {}}, "has no attachment type")

    def test_a_transcript_that_is_not_json_raises(self):
        path = self.write(Transcript().person("hi"))
        path.write_text(path.read_text() + "not json\n")
        self.assert_fails(str(path), "is not JSON")

    def test_a_plugin_root_with_no_coupling_patterns_raises(self):
        (self.plugin / "scripts" / "coupling.json").write_text("{}")
        self.assert_fails("coupling.json holds no patterns of project names")

    def test_a_plugin_root_with_no_skills_raises(self):
        shutil.rmtree(self.plugin / "skills")
        self.assert_fails("holds no skills/*/SKILL.md")

    def test_a_plugin_commit_that_cannot_be_read_raises(self):
        (self.plugin / ".git").mkdir()
        self.assert_fails("git cannot read its commit")
        (self.plugin / ".git").rmdir()
        self.plugin = self.plugin.rename(self.plugin.with_name("latest"))
        self.assert_fails("neither a git checkout nor a cache directory")

    def test_a_since_that_is_neither_a_date_nor_a_utc_time_raises(self):
        for since in ("last week", "2026-13-01", "2026-11-01T00:00:00", "2026-11-01T00:00:00+01:00", "2026-02-30T00:00:00Z"):
            self.assert_fails(f"--since {since!r} is not a date YYYY-MM-DD or a UTC time", since=since)

    def test_a_since_not_before_now_raises(self):
        self.assert_fails("is not before now", since=stamp(-1))

    def test_a_meta_with_no_agent_type_raises(self):
        session = self.write(Transcript().person("hi"))
        agent = Transcript()
        agent.claude({"type": "text", "text": "x"})
        self.write_agent(session, "x", {"toolUseId": "a"}, agent)
        self.assert_fails("agent-x.meta.json has no agentType")

    def test_agents_nested_too_deep_raise(self):
        t = Transcript()
        t.typed("/lasp-dev:work")
        t.claude(call("a0", "Agent"))
        session = self.write(t)
        for n in range(22):
            agent = Transcript()
            agent.claude(call(f"a{n + 1}", "Agent"))
            self.write_agent(session, f"x{n}", {"agentType": "general-purpose", "toolUseId": f"a{n}"}, agent)
        self.assert_fails("nests more than 20 deep")

    def test_an_entry_with_no_type_raises(self):
        self.assert_refused({"message": {}}, "has no type")

    def test_a_skill_call_with_no_skill_raises(self):
        self.assert_refused({"type": "assistant", "timestamp": stamp(1), "message": {"content": [call("s", "Skill")]}},
                            "Skill call has no skill name")

    def test_an_entry_with_no_timestamp_raises(self):
        self.assert_refused({"type": "assistant", "message": {"content": []}}, "timestamp")

    def test_a_usage_that_is_not_counts_raises(self):
        self.assert_refused({"type": "assistant", "timestamp": stamp(1),
                             "message": {"content": [], "usage": {"input_tokens": "many"}}}, "not a count")

    def test_a_malformed_question_result_raises(self):
        t = Transcript()
        t.typed("/lasp-dev:work")
        t.claude(call("q", "AskUserQuestion", questions=[{"question": "Q", "header": "Scope"}]))
        t.result("q", "x", tool_result={"nothing": 1})
        path = self.write(t)
        code, _, _, err = self.run_report()
        self.assertEqual(code, 1)
        self.assertIn(str(path), err)

    def test_an_answered_question_call_with_no_questions_raises(self):
        t = Transcript()
        t.typed("/lasp-dev:work")
        t.claude(call("q", "AskUserQuestion", question="Q?"))
        t.result("q", "x", tool_result={"answers": {"Q?": "yes"}})
        path = self.write(t)
        code, _, _, err = self.run_report()
        self.assertEqual(code, 1)
        self.assertIn(f"{path}: an answered AskUserQuestion call's questions are not a list", err)

    def test_an_errored_question_call_with_no_questions_counts_as_not_shown(self):
        t = Transcript()
        t.typed("/lasp-dev:work")
        t.claude(call("q", "AskUserQuestion", question="Q?"))
        t.result("q", "<tool_use_error>Error: No such tool available</tool_use_error>", is_error=True,
                 tool_result="Error: No such tool available: AskUserQuestion.")
        self.write(t)
        payload, _ = self.ok()
        self.assertEqual(payload["questions"]["work"]["other"]["not_shown"], 1)

    def test_an_agent_with_no_meta_raises(self):
        session = self.write(Transcript().person("hi"))
        agent = Transcript()
        agent.claude({"type": "text", "text": "x"})
        self.write_agent(session, "x", None, agent)
        code, _, _, err = self.run_report()
        self.assertEqual(code, 1)
        self.assertIn("meta.json", err)

    def test_other_entry_kinds_are_not_read(self):
        t = Transcript().person("hi")
        t.entries.append({"type": "some-future-kind", "anything": [1]})
        self.write(t)
        self.ok()

    def test_a_plugin_root_with_no_manifest_raises(self):
        shutil.rmtree(self.plugin / ".claude-plugin")
        code, _, _, err = self.run_report()
        self.assertEqual(code, 1)
        self.assertIn("plugin manifest", err)


class Window(Fixture):
    def setUp(self):
        super().setUp()
        self.write(Transcript(days_ago=40).typed("/lasp-dev:work"))
        self.write(Transcript(days_ago=10).typed("/lasp-dev:commit"))
        self.write(Transcript(days_ago=1).typed("/lasp-dev:pr-review"))

    def test_the_window_opens_at_a_utc_time(self):
        payload, _ = self.ok(since=stamp(5))
        self.assertEqual(sorted(payload["skills"]), ["pr-review"])
        self.assertEqual(payload["window"]["start"], stamp(5)[:19] + "Z")

    def test_the_window_opens_at_the_start_of_a_date(self):
        day = (NOW - timedelta(days=50)).strftime("%Y-%m-%d")
        payload, _ = self.ok(since=day)
        self.assertEqual(sorted(payload["skills"]), ["commit", "pr-review", "work"])
        self.assertEqual(payload["window"]["start"], f"{day}T00:00:00Z")

    def test_a_reports_window_end_opens_the_next_and_its_runs_are_not_counted_again(self):
        payload, _ = self.ok()
        later, _ = self.ok(since=payload["window"]["end"])
        self.assertEqual(later["window"]["start"], payload["window"]["end"])
        self.assertEqual(later["skills"], {})

    def test_since_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            usage.main(["--plugin-root", "p", "--out", "o", "--pending", "q"])
        self.assertIn("build needs --since", err.getvalue())


class Caps(Fixture):
    def test_an_oversized_payload_is_refused_not_cut(self):
        self.write(Transcript().typed("/lasp-dev:work"))
        code, _, _, err = self.run_report("--max-bytes", "100")
        self.assertEqual(code, 1)
        self.assertIn("over --max-bytes 100", err)
        self.assertFalse((self.tmp / "out" / "payload.json").exists())

    def test_the_pending_file_keeps_the_last_40_runs_cut_to_400_characters(self):
        t = Transcript()
        for n in range(45):
            t.typed("/lasp-dev:work").person(f"{n:02d}" + "x" * 500)
        self.write(t)
        payload, runs = self.ok()
        self.assertEqual(len(runs), 40)
        self.assertTrue(runs[0]["next_message"].startswith("05"))
        self.assertEqual(len(runs[0]["next_message"]), 400)
        self.assertNotIn("xxxx", json.dumps(payload))


class Fill(Fixture):
    """--fill: the skill's labels, overlap counts and notes written into the payload, checked."""

    def setUp(self):
        super().setUp()
        t = Transcript()
        t.typed("/lasp-dev:work").person("looks good, go on")
        t.typed("/lasp-dev:commit")
        t.typed("/lasp-dev:work").person("no, the title is wrong")
        self.write(t)
        self.ok()
        self.out, self.pending_path = self.tmp / "out" / "payload.json", self.tmp / "out" / "pending.json"

    def fill(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = usage.main(["--fill", str(self.out), *argv])
            except SystemExit as e:
                code = e.code
        return code, stdout.getvalue(), stderr.getvalue()

    def labels(self, *labels):
        return self.fill("--pending", str(self.pending_path), "--labels", *labels)

    def refused(self, result, says):
        code, _, err = result
        self.assertEqual(code, 1, err)
        self.assertIn(says, err)
        self.assertIsNone(json.loads(self.out.read_text())["after_run"], "a refusal writes nothing")

    def test_labels_count_per_skill_and_the_payload_prints_with_its_digest(self):
        code, out, err = self.labels("approve", "none", "correct")
        self.assertEqual(code, 0, err)
        written = self.out.read_text()
        self.assertEqual(json.loads(written)["after_run"], {"commit": {"none": 1}, "work": {"approve": 1, "correct": 1}})
        text, digest = out.rsplit("sha256:", 1)
        self.assertEqual(text, written)
        self.assertEqual(digest.strip(), hashlib.sha256(written.encode()).hexdigest())
        self.assertEqual(outside_vocabulary(json.loads(written)), [])
        self.assertNotIn("title is wrong", written)

    def test_a_label_count_that_is_not_the_run_count_is_refused(self):
        self.refused(self.labels("approve", "none"), says="2 labels for the 3 runs")

    def test_none_is_the_label_of_a_run_with_no_next_message_and_of_no_other(self):
        self.refused(self.labels("approve", "approve", "correct"), says="run 2 (commit) has no next message")
        self.refused(self.labels("none", "none", "correct"), says="run 1 (work) has a next message")

    def test_a_label_outside_the_outcomes_is_refused(self):
        code, _, err = self.labels("approve", "none", "grumble")
        self.assertEqual(code, 2)
        self.assertIn("invalid choice: 'grumble'", err)

    def test_a_pending_run_not_in_the_written_shape_is_refused(self):
        self.pending_path.write_text(json.dumps([{"skill": "work"}]))
        self.refused(self.labels("approve"), says="run 1 is not {skill, started, next_message}")

    def test_a_pending_file_that_is_not_json_or_not_a_list_is_refused_and_nothing_written(self):
        before = self.out.read_text()
        for text, says in (("not json", "is not a readable pending file"), ("{}", "is not a pending file: it holds a dict")):
            self.pending_path.write_text(text)
            code, _, err = self.labels("approve", "none", "correct")
            self.assertEqual(code, 1, text)
            self.assertIn(says, err)
            self.assertEqual(self.out.read_text(), before, text)

    def test_a_notes_file_that_cannot_be_read_is_refused_and_nothing_written(self):
        before = self.out.read_text()
        code, _, err = self.fill("--notes", str(self.tmp / "missing.txt"))
        self.assertEqual(code, 1)
        self.assertIn("missing.txt cannot be read as text", err)
        self.assertEqual(self.out.read_text(), before)

    def test_overlap_names_the_plugins_skills_and_agents_with_counts_of_one_or_more(self):
        code, _, err = self.fill("--plugin-root", str(self.plugin), "--overlap", "skill:pr-review=2", "agent:test-runner=1")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(self.out.read_text())["overlap"], {"skills": {"pr-review": 2}, "agents": {"test-runner": 1}})
        code, _, err = self.fill("--plugin-root", str(self.plugin), "--overlap")
        self.assertEqual(json.loads(self.out.read_text())["overlap"], {"skills": {}, "agents": {}}, err)
        for items, says in ((["skill:zanzibar-pr-review=1"], "is not skill:<name>=<n>"), (["agent:work=1"], "is not skill:<name>=<n>"),
                            (["skill:work=0"], "is not skill:<name>=<n>"), (["skill:work=1", "skill:work=2"], "names skill work twice")):
            code, _, err = self.fill("--plugin-root", str(self.plugin), "--overlap", *items)
            self.assertEqual(code, 1, items)
            self.assertIn(says, err)
        self.assertEqual(json.loads(self.out.read_text())["overlap"], {"skills": {}, "agents": {}}, "a refusal writes nothing")

    def test_notes_are_kept_as_typed_and_empty_notes_are_null(self):
        notes = self.tmp / "notes.txt"
        notes.write_text("  The commit skill asks one question too many. Ça va.\n")
        code, out, err = self.fill("--notes", str(notes))
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(self.out.read_text())["notes"], "The commit skill asks one question too many. Ça va.")
        self.assertIn("Ça va.", out)
        notes.write_text("\n")
        self.fill("--notes", str(notes))
        self.assertIsNone(json.loads(self.out.read_text())["notes"])

    def test_a_filled_payload_over_the_cap_is_refused_and_nothing_written(self):
        before = self.out.read_text()
        notes = self.tmp / "notes.txt"
        notes.write_text("x" * 70000)
        code, _, err = self.fill("--notes", str(notes))
        self.assertEqual(code, 1)
        self.assertIn("over --max-bytes 60000", err)
        self.assertEqual(self.out.read_text(), before)

    def test_a_payload_this_script_did_not_write_is_refused(self):
        self.out.write_text('{"schema": 1}')
        code, _, err = self.fill("--notes", str(self.out))
        self.assertEqual(code, 1)
        self.assertIn("not a payload this script wrote", err)

    def test_each_mode_takes_only_its_own_options(self):
        for argv, says in ((["--since", "2026-11-01"], "fill takes no --since"), ([], "--fill needs --labels, --overlap or --notes"),
                           (["--labels", "none"], "--labels needs --pending"), (["--overlap"], "--overlap needs --plugin-root")):
            code, _, err = self.fill(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn(says, err)
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            usage.main(["--plugin-root", "p", "--since", "2026-11-01", "--out", "o", "--pending", "q", "--labels", "none"])
        self.assertIn("build takes no --labels", err.getvalue())


class OverlapRead(unittest.TestCase):
    """The skill's awk command that prints the person's own skills' and agents' frontmatter."""

    SKILL = ROOT / "skills" / "usage-report" / "SKILL.md"
    COMMAND = next(line for line in SKILL.read_text().splitlines() if line.startswith("awk -f "))

    def read(self, config: Path) -> subprocess.CompletedProcess:
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config)}
        command = self.COMMAND.replace("${CLAUDE_SKILL_DIR}", str(self.SKILL.parent))
        return subprocess.run(["bash", "-c", command], capture_output=True, text=True, env=env)

    def test_the_skill_body_holds_no_positional_argument_token(self):
        self.assertIsNone(re.search(r"\$\d", self.SKILL.read_text()), "Claude Code replaces $N in a skill body with an argument")

    def write(self, path: Path, description: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\nname: {path.stem}\ndescription: {description}\n---\n\nbody\n")

    def test_a_kind_with_no_directory_does_not_stop_the_other(self):
        for present in ("skills/mine/SKILL.md", "agents/mine.md"):
            with self.subTest(present=present), tempfile.TemporaryDirectory() as tmp:
                self.write(Path(tmp) / present, "does a job")
                done = self.read(Path(tmp))
                self.assertEqual((done.returncode, done.stderr), (0, ""))
                self.assertEqual(done.stdout.splitlines()[1:], [f"name: {Path(present).stem}", "description: does a job"])

    def test_each_line_is_cut_to_300_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(Path(tmp) / "skills" / "long" / "SKILL.md", "x" * 500)
            lines = self.read(Path(tmp)).stdout.splitlines()
        self.assertEqual(lines[2], ("description: " + "x" * 500)[:300])


if __name__ == "__main__":
    unittest.main()
