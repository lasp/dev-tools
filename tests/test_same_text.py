"""Tests for sandbox/same_text.py, on synthetic transcripts written in Claude Code's layout: a run's
`stream.jsonl` names the session and its directory, and the session's transcript and a subagent's
are written under a temporary CLAUDE_CONFIG_DIR. Run with `python3 -m unittest discover -s tests`.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("same_text", ROOT / "sandbox" / "same_text.py")
same_text = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(same_text)

WORK = "# Work\n\nRead the ticket, then say where it stands."
READER = "## The project\n\nPROJ, at the team's Jira."


def text(body: str) -> dict:
    return {"type": "user", "isMeta": True, "message": {"role": "user", "content": [{"type": "text", "text": body}]}}


def attachment(**fields) -> dict:
    return {"type": "attachment", "attachment": fields}


class SameText(unittest.TestCase):
    def setUp(self):
        self.top = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.top)
        self.sandbox = self.top / "sbx"
        self.cwd = self.sandbox / "repos" / "widgets"
        self.cwd.mkdir(parents=True)
        env = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.top / "config")})
        env.start()
        self.addCleanup(env.stop)
        self.runs = 0

    def record(self, variant: str, *, work=WORK, reader=READER, preloads=(), plugin="base", version="2.1.304",
               bash="ls", prompt_to_reader="ticket PROJ-830", tools=("Bash",), before=(), after=(),
               agent=True, subagent=True, requests=True):
        """One run of `variant`: the main session loads the work skill, gets `before`, runs a Bash
        command, gets `after` and starts a source-reader, which preloads using-jira and `preloads`
        and gets the prompt it is given."""
        self.runs += 1
        root = self.top / plugin
        (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (root / ".claude-plugin" / "plugin.json").write_text("{}")
        session = f"00000000-0000-0000-0000-{self.runs:012d}"
        runs = self.sandbox / "runs" / "work" / variant
        run = runs / str(len(list(runs.glob("*"))) + 1)
        run.mkdir(parents=True)
        (run / "stream.jsonl").write_text(json.dumps({"type": "system", "subtype": "init", "cwd": str(self.cwd), "session_id": session}) + "\n")
        project = self.top / "config" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.cwd))
        (project / session / "subagents").mkdir(parents=True)
        shape = {"type": "api-request-shape", "shape": {"system": [{"type": "text", "text": "You are Claude Code."}],
                                                         "tools": [*({"name": t, "description": f"The {t} tool."} for t in tools),
                                                                   {"name": "mcp__jira__get_issue", "description": f"fields in order {self.runs}"}]}}
        head = [{"type": "api-request", "version": version}, shape] if requests else []
        main = [
            *head,
            {"type": "user", "message": {"role": "user", "content": "/lasp-dev:work PROJ-830"}},
            text(f"Base directory for this skill: {root}/skills/work\n\n{work}"),
            attachment(type="budget_usd", used=self.runs * 0.1),
            *before,
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": f"toolu_0{self.runs}", "name": "Bash", "input": {"command": bash}}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"toolu_0{self.runs}", "content": f"standards/review-rules.md\n{root}/scripts/x.py"}]}},
            *after,
            *([{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": f"toolu_a{self.runs}", "name": "Agent", "input": {"prompt": prompt_to_reader}}]}}] if agent else []),
        ]
        (project / f"{session}.jsonl").write_text("\n".join(json.dumps(e) for e in main) + "\n")
        if not (agent and subagent):
            return
        sub = [
            *head,
            {"type": "user", "message": {"role": "user", "content": prompt_to_reader}},
            *(text(f"Base directory for this skill: {root}/skills/{name}\n\n{body}") for name, body in (("using-jira", reader), *preloads)),
        ]
        agent = project / session / "subagents" / f"agent-a{self.runs:016x}"
        agent.with_suffix(".jsonl").write_text("\n".join(json.dumps(e) for e in sub) + "\n")
        agent.with_suffix(".meta.json").write_text(json.dumps({"agentType": "lasp-dev:source-reader"}))

    def compare(self, *extra: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = same_text.main(["work", "--sandbox", str(self.sandbox), "--base", "a", "--head", "b", *extra])
        return code, out.getvalue()

    def refused(self) -> str:
        with self.assertRaises(SystemExit) as raised:
            self.compare()
        return str(raised.exception)

    def test_the_same_text_from_two_checkouts_is_no_difference(self):
        self.record("a", plugin="base")
        self.record("b", plugin="head")
        code, out = self.compare()
        self.assertEqual(code, 0, out)
        self.assertIn("0 unexpected difference(s)", out)

    def test_ids_commits_and_a_skills_arguments_are_normalized(self):
        self.record("a", work=WORK + "\n\nSession 11111111-2222-3333-4444-555555555555.\n5999736 Remove the standard\n\nARGUMENTS: one")
        self.record("b", work=WORK + "\n\nSession 66666666-7777-8888-9999-000000000000.\nab12cd3 Remove the standard\n\nARGUMENTS: two")
        code, out = self.compare()
        self.assertEqual(code, 0, out)

    def test_a_changed_skill_body_fails_naming_the_skill(self):
        self.record("a")
        self.record("b", work=WORK + " Then ask.")
        code, out = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("--- main skill:work: differs, UNEXPECTED", out)
        self.assertIn("+Read the ticket, then say where it stands. Then ask.", out)

    def test_a_preloaded_skill_is_compared_in_the_agent_that_preloads_it(self):
        self.record("a")
        self.record("b", reader=READER.replace("PROJ", "WID"))
        code, out = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("--- lasp-dev:source-reader skill:using-jira: differs, UNEXPECTED", out)

    def test_a_skill_preloaded_on_one_side_only_fails(self):
        self.record("a")
        self.record("b", preloads=[("using-confluence", "## The spaces")])
        code, out = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("--- lasp-dev:source-reader skill:using-confluence: only in b, UNEXPECTED", out)

    def test_a_skill_the_model_invoked_on_one_side_only_is_route(self):
        self.record("a")
        self.record("b", after=[text("Base directory for this skill: /x/skills/writing\n\n# Writing")])
        code, out = self.compare()
        self.assertEqual(code, 0, out)
        self.assertIn("only in b: main invoked-skill:writing", out)

    def test_a_tool_only_one_variant_was_given_fails(self):
        self.record("a")
        self.record("b", tools=("Bash", "Monitor"))
        code, out = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("--- main tool:Monitor: only in b, UNEXPECTED", out)

    def test_a_changed_reminder_fails(self):
        self.record("a", before=[text("<system-reminder>\nThe repository's rules.\nKeep it short.")])
        self.record("b", before=[text("<system-reminder>\nThe repository's rules.\nKeep it long.")])
        code, out = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("--- main reminder:The repository's rules.: differs, UNEXPECTED", out)

    def test_a_hook_is_compared_when_it_fired_on_both_sides_and_route_when_on_one(self):
        def hook(message):
            return attachment(type="hook_success", hookEvent="PreToolUse", hookName="PreToolUse:Write", command="build-record.sh guard", stdout=message)
        self.record("a", after=[hook("Added .review/ to .git/info/exclude")])
        self.record("b", after=[hook("Added .review/ to the exclude file")])
        code, out = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("--- main hook:PreToolUse:Write:build-record.sh guard:hook_success: differs, UNEXPECTED", out)
        shutil.rmtree(self.sandbox / "runs" / "work" / "b")
        self.record("b")
        code, out = self.compare()
        self.assertEqual(code, 0, out)
        self.assertIn("only in a: main hook:PreToolUse:Write", out)

    def test_claude_codes_notices_and_the_session_start_line_are_route(self):
        self.record("a", after=[attachment(type="edited_text_file", filename="a.md"), text("SessionStart hook additional context: no plan")])
        self.record("b", after=[attachment(type="edited_text_file", filename="b.md"), text("SessionStart hook additional context: plan drafted")])
        code, out = self.compare()
        self.assertEqual(code, 0, out)
        self.assertIn("differs: main notice:edited_text_file", out)
        self.assertIn("differs: main notice:SessionStart hook", out)

    def test_an_agent_started_on_one_side_only_is_route(self):
        self.record("a")
        self.record("b", agent=False)
        code, out = self.compare()
        self.assertEqual(code, 0, out)
        self.assertIn("only in a: lasp-dev:source-reader skill:using-jira", out)

    def test_an_expected_change_passes_and_one_that_did_not_happen_fails(self):
        self.record("a")
        self.record("b", reader=READER.replace("PROJ", "WID"))
        expected = self.top / "expected.txt"
        expected.write_text("# the project key moves to the team file\n*source-reader skill:using-jira: the key is read from the team file\n")
        code, out = self.compare("--expected", str(expected))
        self.assertEqual(code, 0, out)
        self.assertIn("expected (the key is read from the team file)", out)
        expected.write_text("*skill:work: work is reworded\n*source-reader skill:using-jira: the key is read from the team file\n")
        code, out = self.compare("--expected", str(expected))
        self.assertEqual(code, 1)
        self.assertIn("expected change '*skill:work' did not happen", out)

    def test_an_expected_key_copied_from_the_output_matches_itself(self):
        command = 'gh pr list --json "number,title" [x]'
        self.record("a", bash=command)
        self.record("b", bash=command)
        for path in (self.top / "config" / "projects").glob("*/*-000000000002.jsonl"):
            path.write_text(path.read_text().replace("standards/review-rules.md", "standards/other.md"))
        key = 'main result:Bash:{"command": "gh pr list --json \\"number,title\\" [x]"}'
        code, out = self.compare()
        self.assertIn(f"--- {key}: differs, UNEXPECTED", out)
        expected = self.top / "expected.txt"
        expected.write_text(f"{key}: the rules file moved\n")
        code, out = self.compare("--expected", str(expected))
        self.assertEqual(code, 0, out)

    def test_a_different_route_is_listed_and_does_not_fail(self):
        self.record("a", bash="ls")
        self.record("b", bash="git status")
        code, out = self.compare()
        self.assertEqual(code, 0, out)
        self.assertIn('only in a: main result:Bash:{"command": "ls"}', out)
        self.assertIn('only in b: main result:Bash:{"command": "git status"}', out)

    def test_text_a_model_wrote_and_a_servers_tool_definitions_are_not_compared(self):
        self.record("a", prompt_to_reader="ticket PROJ-830")
        self.record("b", prompt_to_reader="Read PROJ-830 and say its status")
        code, out = self.compare()
        self.assertEqual(code, 0, out)
        self.assertNotIn("mcp__jira__get_issue", out)

    def test_runs_on_different_claude_code_versions_are_refused(self):
        self.record("a", version="2.1.303")
        self.record("b", version="2.1.304")
        code, out = self.compare()
        self.assertEqual(code, 1)
        self.assertIn("different Claude Code versions", out)

    def test_a_transcript_with_no_request_records_is_refused(self):
        self.record("a", requests=False)
        self.record("b")
        self.assertIn("records no API requests", self.refused())

    def test_a_missing_transcript_is_refused(self):
        self.record("a")
        self.record("b")
        for path in (self.top / "config" / "projects").rglob("*-000000000002.jsonl"):
            path.unlink()
        self.assertIn("no transcript", self.refused())

    def test_a_missing_subagent_transcript_is_refused(self):
        self.record("a", subagent=False)
        self.record("b")
        self.assertIn("started 1 agent(s) and has 0 subagent transcript(s)", self.refused())

    def test_an_agent_call_that_failed_needs_no_transcript(self):
        failed = [{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_bad", "name": "Agent", "input": {"subagent_type": "gone"}}]}},
                  {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_bad", "is_error": True, "content": "Agent type 'gone' not found"}]}}]
        self.record("a")
        self.record("b", after=failed)
        code, out = self.compare()
        self.assertEqual(code, 0, out)

    def test_a_run_with_no_init_event_and_a_variant_with_no_runs_are_refused(self):
        self.record("a")
        (self.sandbox / "runs" / "work" / "b").mkdir(parents=True)
        self.assertIn("no runs under", self.refused())
        self.record("b")
        (self.sandbox / "runs" / "work" / "b" / "1" / "stream.jsonl").write_text("{}\n")
        self.assertIn("has no init event", self.refused())

    def test_a_line_separator_inside_a_string_is_not_a_line_break(self):
        # JSON leaves U+2028 and U+0085 raw in a string, as in a binary file a tool read.
        path = self.top / "separators.jsonl"
        entries = [{"type": "user", "content": "before\u2028after\x85end"}, {"type": "api-request", "version": "2.1.304"}]
        path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        self.assertEqual(same_text.jsonl(path), entries)


if __name__ == "__main__":
    unittest.main()
