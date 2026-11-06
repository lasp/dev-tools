"""Tests for sandbox/run.py, with no model calls. Run with `python3 -m unittest discover -s tests`.

The runner needs PyYAML; these skip without it. The summary tests read
`tests/fixtures/sandbox/quickstart.jsonl`, a made-up log of the generic quickstart scenario in the
shape of a real one: its init, the tool use the settings denied, the denial and the result; they
change one field of a copy where a test needs another outcome. A scenario pack in a directory of
its own under `sandbox/` is held to its own facts by its own test.
"""

import contextlib
import fnmatch
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
# A shadow period in the shell that runs the tests is not theirs.
os.environ.pop("PROFILE_SHADOW_ROOT", None)

try:
    import yaml  # noqa: F401

    _spec = importlib.util.spec_from_file_location("sandbox_run", ROOT / "sandbox" / "run.py")
    run = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(run)
    _spec = importlib.util.spec_from_file_location("sandbox_rule_cases", ROOT / "sandbox" / "rule_cases.py")
    rule_cases = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rule_cases)
    _spec = importlib.util.spec_from_file_location("sandbox_smoke", ROOT / "sandbox" / "smoke.py")
    smoke = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(smoke)
except ImportError:
    run = rule_cases = smoke = None

FIXTURE = ROOT / "tests" / "fixtures" / "sandbox" / "quickstart.jsonl"
EXPECT_KEYS = {"skills", "agents", "mcp", "files", "ends", "max_cost", "max_turns", "max_ticket_words", "says", "not_says", "files_absent", "agents_absent", "never_anywhere"}


def fixture() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text().splitlines()]


def well_formed(case: unittest.TestCase, known: dict, repos: set) -> None:
    """Every scenario in `known` has the fields run.py reads, runs in one of `repos`, and names
    only skills and agents this plugin has."""
    skills = {p.parent.name for p in ROOT.glob("skills/*/SKILL.md")}
    agents = {p.stem for p in ROOT.glob("agents/*.md")}
    for s in known.values():
        case.assertLessEqual({"id", "repo", "turns", "must_not_run", "look_at"}, set(s), s["id"])
        case.assertIn(s["repo"], repos, s["id"])
        case.assertTrue(s["turns"] and all(isinstance(t, str) for t in s["turns"]), s["id"])
        case.assertTrue(all(isinstance(c, str) for c in s.get("verify", [])), s["id"])
        case.assertTrue(all(isinstance(c, str) for c in s.get("setup", [])), s["id"])
        case.assertLessEqual(set(s.get("expect", {})), EXPECT_KEYS, s["id"])
        case.assertEqual(s["expect"]["ends"], "success", s["id"])
        case.assertLessEqual(set(s["expect"].get("agents", [])), agents, s["id"])
        case.assertLessEqual(set(s["expect"].get("skills", [])), skills, s["id"])
        if "origin" in s:
            case.assertTrue(s.get("why"), s["id"])


GITHUB_SERVER = {"type": "http", "url": "https://api.githubcopilot.com/mcp/"}
ATLASSIAN_SERVER = {"command": "uvx", "args": ["mcp-atlassian@0.23.1", "--read-only"], "env": {"READ_ONLY_MODE": "true"}}


@unittest.skipIf(run is None, "sandbox/run.py needs PyYAML")
class TriggerPack(unittest.TestCase):
    """sandbox/triggers/: one plain-language request per skill a person types and the model may call."""

    PACK = ROOT / "sandbox" / "triggers" / "scenarios.yaml"

    def setUp(self):
        patch = mock.patch.object(run, "SCENARIOS", self.PACK)
        patch.start()
        self.addCleanup(patch.stop)
        self.known = run.scenarios()

    def test_every_scenario_is_well_formed_and_asks_in_words(self):
        well_formed(self, self.known, {"widgets"})
        for s in self.known.values():
            self.assertTrue(s["id"].startswith(("trigger-", "notrigger-")), s["id"])
            self.assertEqual(len(s["turns"]), 1, s["id"])
            self.assertNotIn("/", s["turns"][0].split()[0], s["id"])
            if s["id"].startswith("notrigger-"):
                self.assertTrue(any(r.startswith("Skill(") for r in s["must_not_run"]), s["id"])

    def test_each_skill_a_request_can_reach_has_a_trigger_scenario_and_the_set_holds_the_pack(self):
        reachable = set()
        for path in ROOT.glob("skills/*/SKILL.md"):
            front = yaml.safe_load(path.read_text().split("---", 2)[1])
            if front.get("user-invocable", True) and not front.get("disable-model-invocation", False):
                reachable.add(front["name"])
        triggers = {s["id"]: s for s in self.known.values() if s["id"].startswith("trigger-")}
        for name in reachable:
            with self.subTest(skill=name):
                self.assertIn(f"trigger-{name}", triggers)
        for i, s in triggers.items():
            with self.subTest(scenario=i):
                skills = s["expect"].get("skills")
                self.assertEqual(len(skills), 1)
                name = skills[0]
                self.assertIn(name, reachable)
                self.assertTrue(i == f"trigger-{name}" or i.startswith(f"trigger-{name}-"))
                self.assertNotIn(name, s["turns"][0].lower())
        self.assertEqual(set(smoke.smoke_set(self.PACK)), set(self.known))

    def test_the_pack_plants_no_credentials(self):
        spec = importlib.util.spec_from_file_location("secret_scan_tests", ROOT / "tests" / "test_secret_scan.py")
        scan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scan)
        planted = scan.planted
        pack = "sandbox/triggers/"
        files = [str(p.relative_to(ROOT)) for p in (ROOT / pack).rglob("*") if p.is_file()]
        self.assertTrue(files)
        self.assertEqual(planted(files), {})


@unittest.skipIf(run is None, "sandbox/run.py needs PyYAML")
class TrackerPack(unittest.TestCase):
    """sandbox/tracker/: scenarios against a Jira project the pack's read-only stub serves."""

    PACK = ROOT / "sandbox" / "tracker" / "scenarios.yaml"
    STUB = ROOT / "sandbox" / "tracker" / "fixture" / "mcp-atlassian-stub.py"
    SERVER = {"command": "python3", "args": ["-I", "${SBX_FIXTURES}/mcp-atlassian-stub.py", "--read-only"],
              "env": {"READ_ONLY_MODE": "true"}}

    def setUp(self):
        patch = mock.patch.object(run, "SCENARIOS", self.PACK)
        patch.start()
        self.addCleanup(patch.stop)
        self.known = run.scenarios()

    def serve(self, *requests: dict) -> list[dict]:
        lines = "".join(json.dumps({"jsonrpc": "2.0", **r}) + "\n" for r in requests)
        out = subprocess.run([sys.executable, "-I", str(self.STUB), "--read-only"], input=lines,
                             capture_output=True, text=True, check=True).stdout
        return [json.loads(line) for line in out.splitlines()]

    def test_every_scenario_is_well_formed_and_copies_fixtures_the_pack_holds(self):
        self.assertEqual(len(self.known), 5)
        well_formed(self, self.known, {"widgets"})
        for s in self.known.values():
            self.assertTrue(s["id"].startswith("tracker-"), s["id"])
            for name in re.findall(r'"\$SBX_FIXTURES/([^"]+)"', " ".join(s.get("setup", []))):
                self.assertTrue((run.fixture_dir() / name).is_file(), (s["id"], name))

    def test_the_documented_server_gets_the_atlassian_rules_and_is_read_only(self):
        self.assertIn(json.dumps(self.SERVER["args"][1]), self.PACK.read_text())
        self.assertEqual(run.server_kind(self.SERVER), "atlassian")
        sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, sandbox)
        (sandbox / "mcp.json").write_text(json.dumps({"mcpServers": {"atlassian": self.SERVER}}))
        run.write_settings(sandbox, ROOT)
        allow = json.loads((sandbox / "settings.json").read_text())["permissions"]["allow"]
        self.assertIn("mcp__atlassian", allow)

    def call(self, name: str, **arguments) -> dict:
        (reply,) = self.serve({"id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
        return reply["result"]

    def test_the_stub_lists_no_write_tool(self):
        (listed,) = self.serve({"id": 1, "method": "tools/list"})
        names = {t["name"] for t in listed["result"]["tools"]}
        self.assertLessEqual({"jira_get_issue", "jira_search"}, names)
        self.assertFalse({n for n in names if re.match(r"(jira|confluence)_(create|update|delete|add|transition|link|assign|move|remove)", n)})

    def test_a_search_returns_the_description_as_stored(self):
        issues = json.loads(self.call("jira_search", jql="key = PROJ-57")["content"][0]["text"])["issues"]
        self.assertEqual([i["key"] for i in issues], ["PROJ-57"])
        self.assertIn("\nh1. Context\n", issues[0]["description"])
        self.assertIn("\n# An inventory with A-1 at -2", issues[0]["description"])

    def test_a_search_for_several_keys_returns_each(self):
        issues = json.loads(self.call("jira_search", jql="key in (PROJ-57, PROJ-58) ORDER BY key")["content"][0]["text"])["issues"]
        self.assertEqual([i["key"] for i in issues], ["PROJ-57", "PROJ-58"])

    def test_a_search_for_a_quoted_key_or_by_issue_returns_that_ticket(self):
        for jql in ('key = "PROJ-57"', "key = 'PROJ-57'", "issue = PROJ-57", 'issue = "PROJ-57"'):
            with self.subTest(jql=jql):
                issues = json.loads(self.call("jira_search", jql=jql)["content"][0]["text"])["issues"]
                self.assertEqual([i["key"] for i in issues], ["PROJ-57"])

    def test_get_issue_converts_headings_and_numbered_items_to_markdown(self):
        description = json.loads(self.call("jira_get_issue", issue_key="PROJ-57")["content"][0]["text"])["description"]
        self.assertIn("\n# Context\n", description)
        self.assertIn("\n## Acceptance Criteria\n", description)
        self.assertIn("\n1. An inventory with A-1 at -2", description)
        self.assertNotIn("\n1. Context", description)

    def test_an_unknown_key_is_an_error_result(self):
        missing = self.call("jira_get_issue", issue_key="PROJ-99")
        self.assertTrue(missing["isError"])
        self.assertIn("PROJ-99", missing["content"][0]["text"])

    def test_a_call_naming_no_tool_is_a_protocol_error(self):
        (reply,) = self.serve({"id": 1, "method": "tools/call", "params": {}})
        self.assertEqual(reply["error"]["code"], -32602)

    def test_the_mcp_expectation_fails_a_run_the_server_did_not_answer(self):
        scenario = self.known["tracker-work-no-page"]
        summary = {"subtype": "success", "is_error": False, "skills": [], "agents": {"source-reader": 1}, "files": [],
                   "mcp": {"mcp__atlassian__jira_search": 1}, "cost_usd": 0.1, "turns": 6,
                   "final": "PROJ-42 · To Do\nNext: implement-change.\n", "must_not_run": []}
        self.assertEqual(run.check(summary, scenario), "pass")
        self.assertEqual(run.check({**summary, "mcp": {}}, scenario), "fail: no mcp tool mcp__atlassian__jira_*")
        self.assertIn("does not say", run.check({**summary, "final": "Next: not implement-change."}, scenario))

    def test_the_pack_plants_no_credentials(self):
        spec = importlib.util.spec_from_file_location("secret_scan_tests", ROOT / "tests" / "test_secret_scan.py")
        scan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scan)
        planted = scan.planted
        pack = "sandbox/tracker/"
        files = [str(p.relative_to(ROOT)) for p in (ROOT / pack).rglob("*") if p.is_file()]
        self.assertTrue(files)
        self.assertEqual(planted(files), {})


@unittest.skipIf(run is None, "sandbox/run.py needs PyYAML")
class Sandbox(unittest.TestCase):
    def setUp(self):
        self.sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.sandbox)
        servers = {"github-example": GITHUB_SERVER, "github": GITHUB_SERVER, "atlassian": ATLASSIAN_SERVER}
        (self.sandbox / "mcp.json").write_text(json.dumps({"mcpServers": servers}))
        self.quickstart = run.scenarios()["quickstart"]

    def test_a_line_separator_inside_a_string_is_not_a_line_break(self):
        # JSON leaves U+2028 and U+0085 raw in a string, as in a binary file a tool read.
        log = self.sandbox / "stream.jsonl"
        entries = [{"type": "user", "text": "before\u2028after\x85end"}, {"type": "result"}]
        log.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
        self.assertEqual(run.events(log), entries)

    def test_every_generic_scenario_is_well_formed_and_runs_in_the_fixture(self):
        known = run.scenarios()
        self.assertEqual(len(known), 25)
        well_formed(self, known, {"widgets"})

    def test_every_fixture_a_scenario_copies_is_in_the_pack(self):
        for s in run.scenarios().values():
            for name in re.findall(r'"\$SBX_FIXTURES/([^"]+)"', " ".join(s.get("setup", []) + s.get("verify", []))):
                self.assertTrue((run.fixture_dir() / name).is_file(), (s["id"], name))

    def test_the_no_standard_scenario_quotes_works_no_rules_file_line(self):
        work = " ".join((ROOT / "skills/work/SKILL.md").read_text().split())
        line = re.search(r'"(no rules file here: [^"]+)"', work).group(1)
        self.assertIn(f'"{line}"', " ".join(run.scenarios()["no-standard"]["look_at"].split()))

    def test_the_quickstart_log_summarizes_to_its_facts(self):
        events = fixture()
        result = events[-1]
        summary = run.summarize(events, self.quickstart, [])
        self.assertEqual(summary["skills"], [])
        self.assertEqual(summary["agents"], {})
        self.assertEqual(summary["mcp"], {})
        self.assertEqual(len(summary["denials"]), 1)
        self.assertTrue(summary["denials"][0].startswith("Bash: ") and "claude plugin list" in summary["denials"][0])
        self.assertEqual(summary["must_not_run"], [])
        self.assertEqual((summary["subtype"], summary["is_error"]), ("success", False))
        self.assertEqual(summary["cost_usd"], round(result["total_cost_usd"], 4))
        self.assertEqual(summary["turns"], result["num_turns"])
        self.assertEqual(summary["first_line"], result["result"].strip().splitlines()[0])

    def test_an_undenied_use_of_a_must_not_run_pattern_is_a_hit(self):
        events = fixture()
        events[-1]["permission_denials"] = []
        summary = run.summarize(events, self.quickstart, [])
        self.assertEqual(len(summary["must_not_run"]), 1)
        self.assertTrue(summary["must_not_run"][0].startswith("Bash(claude *): "))
        self.assertEqual(summary["denials"], [])

    def test_a_denied_use_of_a_must_not_try_pattern_is_a_hit(self):
        scenario = {**self.quickstart, "must_not_run": [], "must_not_try": ["Bash(claude *)"]}
        summary = run.summarize(fixture(), scenario, [])
        self.assertEqual(len(summary["denials"]), 1)
        self.assertEqual(len(summary["must_not_run"]), 1)
        self.assertTrue(summary["must_not_run"][0].startswith("Bash(claude *): "))
        self.assertIn("ran Bash(claude *): ", run.check(summary, scenario))

    def test_a_use_two_rules_hold_is_one_hit(self):
        events = fixture()
        events[-1]["permission_denials"] = []
        scenario = {**self.quickstart, "must_not_run": ["Bash(claude *)", "Bash(*plugin*)"], "must_not_try": ["Bash(claude *)"]}
        summary = run.summarize(events, scenario, [])
        self.assertEqual(len(summary["must_not_run"]), 1)
        self.assertTrue(summary["must_not_run"][0].startswith("Bash(claude *): "))

    def test_a_bash_rule_matches_each_command_of_a_compound_one(self):
        def bash(command):
            return {"name": "Bash", "input": {"command": command}}
        self.assertTrue(run.matches("Bash(claude *)", bash("cd /sandbox/repos/gizmos; claude plugin list 2>&1 | head -30")))
        self.assertTrue(run.matches("Bash(git push*)", bash("git add -A && git push origin HEAD")))
        self.assertTrue(run.matches("Bash(git push*)", bash("make || git push")))
        self.assertFalse(run.matches("Bash(claude *)", bash("cat ~/.claude/settings.json | head")))
        self.assertFalse(run.matches("Bash(claude *)", {"name": "Read", "input": {"file_path": "claude x"}}))
        self.assertTrue(run.matches("Skill(*pr-review)", {"name": "Skill", "input": {"skill": "lasp-dev:pr-review"}}))

    def test_the_check_holds_the_summary_to_the_expect_block(self):
        summary = run.summarize(fixture(), self.quickstart, [])
        self.assertEqual(run.check(summary, self.quickstart), "pass")
        failing = {**self.quickstart, "expect": {"ends": "success", "skills": ["work"], "agents": ["source-reader"],
                                                 "files": [".review/context/*.md"], "max_cost": 0.01}}
        self.assertEqual(run.check(summary, failing),
                         "fail: no skill work; no agent source-reader; no file .review/context/*.md; "
                         f"cost {summary['cost_usd']:.2f} over 0.01")

    def test_the_check_fails_a_run_that_stopped_early_or_ran_a_forbidden_tool(self):
        events = fixture()
        events[-1].update({"subtype": "error_max_budget_usd", "is_error": True, "permission_denials": []})
        check = run.check(run.summarize(events, self.quickstart, []), self.quickstart)
        self.assertTrue(check.startswith("fail: ends error_max_budget_usd; ran Bash(claude *): "), check)

    def test_ticket_words_counts_the_description_without_markup(self):
        context = self.sandbox / ".review" / "context"
        context.mkdir(parents=True)
        (context / "PROJ-1.jira.txt").write_text(
            "Summary:     Five words in the summary\n\n"
            "h1. Context\n*Touches:* {{io/netcdf.py}}\nSee the [design page|https://example.org/p].\n"
            "h2. Acceptance Criteria\n# A test: it raises\n"
            "----------\nComment to post\nOriginal request, not counted\n")
        self.assertEqual(run.ticket_words(self.sandbox, [".review/context/PROJ-1.jira.txt"]), 13)
        (context / "PROJ-2.jira.txt").write_text(
            "Summary:     Five words in the summary\n\n"
            "ticket-draft: drafted 2026-10-12 by A · open questions: 0\n"
            "h1. Motivation\n*Touches:* {{io/netcdf.py}}\nSee the [design page|https://example.org/p].\n"
            "h2. Acceptance Criteria\n# A test: it raises\n"
            "----------\nComment to post\nOriginal request, not counted\n")
        self.assertEqual(run.ticket_words(self.sandbox, [".review/context/PROJ-2.jira.txt"]), 13)
        (context / "PROJ-3.jira.txt").write_text(
            "=== 1. Follow-up ticket ===\nticket-draft: follow-up from PROJ-3, written 2026-10-12 by A\n"
            "h1. Motivation\nFound while drafting, and not counted here.\n\n"
            "=== 2. Description ===\n"
            "ticket-draft: drafted 2026-10-12 by A · open questions: 0\n"
            "h1. Motivation\n*Touches:* {{io/netcdf.py}}\nSee the [design page|https://example.org/p].\n"
            "h2. Acceptance Criteria\n# A test: it raises\n"
            "=== 3. Session comment ===\nticket-draft reformat, not counted\n")
        self.assertEqual(run.ticket_words(self.sandbox, [".review/context/PROJ-3.jira.txt"]), 13)
        self.assertEqual(run.ticket_words(self.sandbox, ["README.md"]), 0)

    def test_pr_words_counts_the_shown_description_without_its_details_block(self):
        final = ("**Title:** x\n\n````markdown\nTicket: PROJ-1 \u2014 a b\n## Summary\nOne two three.\n"
                 "<details><summary>Already checked</summary>\nBuild: passed\n</details>\n````\n\nOpen it?")
        self.assertEqual(run.pr_words(final), 10)
        self.assertEqual(run.pr_words("no description here"), 0)

    def test_max_ticket_words_fails_a_longer_ticket(self):
        summary = {**run.summarize(fixture(), self.quickstart, []), "ticket_words": 650}
        self.assertEqual(run.check(summary, {"expect": {"max_ticket_words": 600}}), "fail: ticket of 650 words over 600")
        self.assertEqual(run.check(summary, {"expect": {"max_ticket_words": 700}}), "pass")

    def test_says_and_not_says_hold_the_last_message(self):
        summary = run.summarize(fixture(), self.quickstart, [])
        first = summary["first_line"]
        self.assertEqual(run.check(summary, {"expect": {"says": [re.escape(first[:10])]}}), "pass")
        self.assertEqual(run.check(summary, {"expect": {"says": ["^no such line$"]}}), "fail: does not say ^no such line$")
        self.assertEqual(run.check(summary, {"expect": {"not_says": ["^no such line$"]}}), "pass")
        self.assertEqual(run.check(summary, {"expect": {"not_says": [re.escape(first[:10])]}}), f"fail: says {re.escape(first[:10])}")

    def test_never_anywhere_finds_a_token_said_mid_run_or_put_in_an_agent_prompt(self):
        def said(*content):
            return {"type": "assistant", "message": {"content": list(content)}}
        evs = [said({"type": "text", "text": "The notes say ZEBRA-4471."}),
               said({"type": "tool_use", "name": "Agent", "input": {"prompt": "Plan from ZEBRA-4471"}}),
               {"type": "result", "subtype": "success", "result": "Stopped."},
               {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ZEBRA-4471 read"}]}},
               said({"type": "text", "text": "Cleared, ZEBRA-4471 is in the notes."}),
               {"type": "result", "subtype": "success", "result": "Done."}]
        self.assertEqual(run.said_leaks(evs, ["ZEBRA-4471"]),
                         [(1, "ZEBRA-4471 in a reply, turn 1"), (1, "ZEBRA-4471 in Agent's input, turn 1"),
                          (2, "ZEBRA-4471 in a reply, turn 2")])
        self.assertEqual(run.said_leaks(evs, ["OTTER-9"]), [])
        self.assertEqual(run.canaries({"expect": {"never_anywhere": ["A"]}}), (["A"], None))
        self.assertEqual(run.canaries({"expect": {"never_anywhere": {"tokens": ["A"], "through_turn": 1}}}), (["A"], 1))
        self.assertEqual(run.canaries({}), ([], None))

    def test_never_anywhere_finds_a_token_in_a_file_the_run_wrote_or_a_commit_not_the_setups_copy(self):
        repo = self.sandbox / "repo"
        repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"], ["config", "commit.gpgsign", "false"]):
            run.git(repo, *args)
        (repo / ".gitignore").write_text(".review/\n")
        run.git(repo, "add", ".gitignore")
        run.git(repo, "commit", "-qm", "base")
        base = run.git(repo, "rev-parse", "HEAD")
        (repo / "notes.md").write_text("ITAR\nZEBRA-4471\n")
        before = run.snapshot(repo)
        self.assertEqual(run.file_leaks(repo, base, before, ["ZEBRA-4471"], 1), [])
        (repo / ".review").mkdir()
        (repo / ".review" / "frame.md").write_text("from ZEBRA-4471")
        self.assertEqual(run.file_leaks(repo, base, before, ["ZEBRA-4471"], 1), [(1, "ZEBRA-4471 in .review/frame.md, turn 1")])
        (repo / ".review" / "frame.md").unlink()
        (repo / "a.txt").write_text("x")
        run.git(repo, "add", "a.txt")
        run.git(repo, "commit", "-qm", "summary of ZEBRA-4471")
        self.assertEqual(run.file_leaks(repo, base, before, ["ZEBRA-4471"], 2), [(2, "ZEBRA-4471 in a commit, turn 2")])

    def test_never_anywhere_fails_the_check_by_its_leaks(self):
        summary = {**run.summarize(fixture(), self.quickstart, []), "leaks": ["ZEBRA-4471 in a reply, turn 1"]}
        self.assertEqual(run.check(summary, {}), "fail: leaked ZEBRA-4471 in a reply, turn 1")
        self.assertIn("leaked", run.flags(summary))
        self.assertEqual(run.check({**summary, "leaks": []}, {}), "pass")

    def test_files_absent_and_agents_absent_name_what_ran(self):
        summary = {**run.summarize(fixture(), self.quickstart, [".review/audit/x.md"]), "agents": {"pr-reader": 1}}
        self.assertEqual(run.check(summary, {"expect": {"files_absent": ["src/*"], "agents_absent": ["source-reader"]}}), "pass")
        self.assertEqual(run.check(summary, {"expect": {"files_absent": [".review/audit/*"]}}), "fail: wrote .review/audit/x.md")
        self.assertEqual(run.check(summary, {"expect": {"agents_absent": ["pr-reader"]}}), "fail: ran agent pr-reader")

    def test_a_failed_verify_command_fails_the_check(self):
        summary = run.summarize(fixture(), self.quickstart, [])
        self.assertEqual(run.check({**summary, "verify": []}, {}), "pass")
        self.assertEqual(run.check({**summary, "verify": ["test -f report.md"]}, {}), "fail: verify failed: test -f report.md")

    def test_max_turns_counts_the_runs_turns(self):
        summary = run.summarize(fixture(), self.quickstart, [])
        self.assertEqual(run.check(summary, {"expect": {"max_turns": summary["turns"]}}), "pass")
        self.assertEqual(run.check(summary, {"expect": {"max_turns": summary["turns"] - 1}}),
                         f"fail: {summary['turns']} turns over {summary['turns'] - 1}")

    def test_compare_counts_the_runs_that_passed_the_check(self):
        out = self.sandbox / "runs" / "quickstart"
        base = run.summarize(fixture(), self.quickstart, [])
        for n, result in enumerate(["pass", "fail: does not say x"], 1):
            d = out / "baseline" / str(n)
            d.mkdir(parents=True)
            (d / "summary.json").write_text(json.dumps({**base, "run": n, "check": result}))
            (d / "final.md").write_text(f"message {n}\n")
        row = next(line for line in run.compare(out).splitlines() if line.startswith("| baseline"))
        cells = [c.strip() for c in row.strip("|").split("|")]
        self.assertEqual(cells[2 + len(run.METRICS)], "1/2")

    def test_settings_repeat_server_rules_per_server_of_their_kind(self):
        run.write_settings(self.sandbox, self.sandbox / "repos" / "dev-tools")
        perms = json.loads((self.sandbox / "settings.json").read_text())["permissions"]
        self.assertIn("mcp__github-example__pull_request_read", perms["allow"])
        self.assertIn("mcp__github__pull_request_read", perms["allow"])
        self.assertIn("mcp__atlassian", perms["allow"])
        self.assertIn("mcp__github-example__add_issue_comment", perms["deny"])
        self.assertIn("mcp__atlassian__jira_update_issue", perms["deny"])
        self.assertNotIn("mcp__atlassian__pull_request_read", perms["allow"])
        self.assertFalse([r for r in perms["allow"] + perms["deny"] if "{" in r])

    def test_settings_tell_a_servers_kind_by_what_it_is_not_its_name(self):
        servers = {"code-host": GITHUB_SERVER,
                   "local-code": {"command": "docker", "args": ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server"]},
                   "code-binary": {"command": "/usr/local/bin/github-mcp-server", "args": ["stdio"]},
                   "issue-tracker": {"command": "docker", "args": ["run", "ghcr.io/sooperset/mcp-atlassian:0.23.1", "--read-only"],
                                     "env": {"READ_ONLY_MODE": "true"}},
                   "github-docs": {"type": "http", "url": "https://example.org/api.githubcopilot.com/mcp/"},
                   "atlassian-notes": {"command": "uvx", "args": ["notes-server"]}}
        (self.sandbox / "mcp.json").write_text(json.dumps({"mcpServers": servers}))
        run.write_settings(self.sandbox, self.sandbox / "repos" / "dev-tools")
        perms = json.loads((self.sandbox / "settings.json").read_text())["permissions"]
        for name in ("code-host", "local-code", "code-binary"):
            self.assertIn(f"mcp__{name}__add_issue_comment", perms["deny"])
            self.assertIn(f"mcp__{name}__pull_request_read", perms["allow"])
        self.assertIn("mcp__issue-tracker__jira_update_issue", perms["deny"])
        self.assertIn("mcp__issue-tracker", perms["allow"])
        for name in ("github-docs", "atlassian-notes"):
            self.assertFalse([r for r in perms["allow"] + perms["deny"] if f"mcp__{name}" in r], name)

    def test_settings_refuse_an_atlassian_server_that_is_not_read_only(self):
        for server in ({"command": "uvx", "args": ["mcp-atlassian@0.23.1"], "env": {"READ_ONLY_MODE": "true"}},
                       {"command": "uvx", "args": ["mcp-atlassian@0.23.1", "--read-only"]}):
            (self.sandbox / "mcp.json").write_text(json.dumps({"mcpServers": {"issue-tracker": server}}))
            with self.assertRaises(SystemExit) as raised:
                run.write_settings(self.sandbox, self.sandbox / "repos" / "dev-tools")
            self.assertIn("issue-tracker", str(raised.exception))
            self.assertFalse((self.sandbox / "settings.json").exists())

    def test_settings_run_bash_in_the_sandbox_with_no_fallback_reaching_a_fixed_list(self):
        run.write_settings(self.sandbox, self.sandbox / "repos" / "dev-tools")
        box = json.loads((self.sandbox / "settings.json").read_text())["sandbox"]
        self.assertTrue(box["enabled"] and box["failIfUnavailable"] and box["autoAllowBashIfSandboxed"])
        self.assertFalse(box["allowUnsandboxedCommands"])
        self.assertEqual(set(box["network"]), {"allowedDomains", "allowLocalBinding"})
        self.assertTrue(box["network"]["allowLocalBinding"])
        domains = box["network"]["allowedDomains"]
        self.assertEqual(domains[:2], ["github.com", "naif.jpl.nasa.gov"])
        self.assertFalse([d for d in domains if "*" in d or "anthropic" in d])
        self.assertEqual(box["filesystem"]["allowWrite"], ["/tmp", "/private/tmp"])

    def test_settings_keep_credentials_and_the_settings_files_from_sandboxed_commands(self):
        servers = {"github-example": {**GITHUB_SERVER, "headers": {"Authorization": "Bearer ${GITHUB_MCP_PAT_EXAMPLE}"}},
                   "atlassian": {**ATLASSIAN_SERVER, "env": {**ATLASSIAN_SERVER["env"], "JIRA_PERSONAL_TOKEN": "${JIRA_TOKEN}"}}}
        (self.sandbox / "mcp.json").write_text(json.dumps({"mcpServers": servers}))
        run.write_settings(self.sandbox, self.sandbox / "repos" / "dev-tools")
        text = (self.sandbox / "settings.json").read_text()
        settings = json.loads(text)
        box = settings["sandbox"]
        env = {e["name"] for e in box["credentials"]["envVars"] if e["mode"] == "deny"}
        self.assertTrue({"GH_TOKEN", "GITHUB_TOKEN", "SBX_FIXTURES", "GITHUB_MCP_PAT_EXAMPLE", "JIRA_TOKEN"} <= env)
        files = {f["path"] for f in box["credentials"]["files"] if f["mode"] == "deny"}
        self.assertTrue({"~/.config/gh", "~/.git-credentials", "~/.netrc"} <= files)
        for name in ("settings.json", "mcp.json"):
            for root in run.spellings(self.sandbox):
                self.assertIn(f"/{root}/{name}", box["filesystem"]["denyWrite"])
                self.assertIn(f"Edit(//{root}/{name})", settings["permissions"]["deny"])
        self.assertNotRegex(text, r"\{(sandbox|plugin|github|atlassian)\}")

    def test_settings_exclude_every_instruction_file_above_the_sandbox_and_the_persons_own(self):
        run.write_settings(self.sandbox, self.sandbox / "repos" / "dev-tools")
        excluded = json.loads((self.sandbox / "settings.json").read_text())["claudeMdExcludes"]
        names = ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md", ".claude/rules/**", "AGENTS.md", ".claude/AGENTS.md")
        for root in run.spellings(self.sandbox):
            for parent in Path("/" + root).parents:
                for name in names:
                    self.assertIn(str(parent / name), excluded)
            for own in ("CLAUDE.md", ".claude/CLAUDE.md", ".claude/rules/x.md", "AGENTS.md"):
                path = f"/{root}/repos/gizmos/{own}"
                self.assertFalse([p for p in excluded if fnmatch.fnmatchcase(path, p)], path)
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": "/elsewhere/config"}):
            self.assertIn("/elsewhere/config/CLAUDE.md", run.outside_instructions(self.sandbox))

    def test_settings_refuse_a_sandbox_path_a_glob_would_misread(self):
        with self.assertRaises(SystemExit) as raised:
            run.outside_instructions(self.sandbox / "Projects (2026)" / "sbx")
        self.assertIn("glob character", str(raised.exception))

    def test_settings_turn_auto_memory_off(self):
        run.write_settings(self.sandbox, self.sandbox / "repos" / "dev-tools")
        self.assertIs(json.loads((self.sandbox / "settings.json").read_text())["autoMemoryEnabled"], False)

    def test_the_judge_runs_under_the_sandbox_settings(self):
        run_dir = self.sandbox / "runs" / "x" / "v" / "1"
        run_dir.mkdir(parents=True)
        (run_dir / "final.md").write_text("done")
        reply = json.dumps({"result": '{"score": 7, "sentence": "Fine."}', "total_cost_usd": 0.01})
        with mock.patch.object(run, "child", return_value=mock.Mock(stdout=reply, stderr="")) as called:
            run.judge("rubric", {"final": "done"}, run_dir, self.sandbox)
        argv = called.call_args[0][0]
        self.assertEqual(argv[argv.index("--settings") + 1], str(self.sandbox / "settings.json"))
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "project,local")

    def test_settings_deny_every_write_tool_of_mcp_atlassian_0_23_1(self):
        writes = """jira_add_watcher jira_remove_watcher jira_create_issue jira_batch_create_issues
            jira_update_issue jira_assign_issue jira_delete_issue jira_move_issue jira_add_comment
            jira_edit_comment jira_add_worklog jira_link_to_epic jira_create_issue_link
            jira_create_remote_issue_link jira_remove_issue_link jira_transition_issue
            jira_create_sprint jira_update_sprint jira_add_issues_to_sprint
            jira_move_issues_to_backlog jira_create_customer_request jira_create_version
            jira_batch_create_versions jira_update_version jira_update_proforma_form_answers
            confluence_add_label confluence_create_page confluence_update_page
            confluence_update_page_section confluence_delete_page confluence_move_page
            confluence_add_comment confluence_reply_to_comment confluence_add_inline_comment
            confluence_upload_attachment confluence_upload_attachments confluence_delete_attachment
            confluence_create_page_from_template confluence_set_page_restrictions
            confluence_copy_page""".split()
        run.write_settings(self.sandbox, self.sandbox / "repos" / "dev-tools")
        deny = json.loads((self.sandbox / "settings.json").read_text())["permissions"]["deny"]
        self.assertEqual([t for t in writes if f"mcp__atlassian__{t}" not in deny], [])

    def test_settings_bound_every_file_and_script_rule_to_the_sandbox_or_the_plugin(self):
        variant = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, variant)
        run.write_settings(self.sandbox, variant)
        allow = json.loads((self.sandbox / "settings.json").read_text())["permissions"]["allow"]
        roots = run.spellings(self.sandbox) + run.spellings(variant)
        for bare in ("Read", "Edit", "Write", "Bash(cat *)", "Bash(mkdir *)", "Bash(python3 *)", "Bash(.venv/bin/python *)",
                     "Bash(bash *)", "Bash(find *)"):
            self.assertNotIn(bare, allow)
        for rule in allow:
            if rule.startswith(("Bash(python3 ", "Bash(.venv/bin/python ")) and " -m " not in rule:
                self.assertTrue(any(f"/{root}/" in rule for root in roots), rule)
            if rule.startswith(("Read(", "Edit(", "Write(", "Bash(cat ", "Bash(find ", "Bash(bash ", "Bash(/")):
                self.assertTrue(any(f"/{root}/" in rule for root in roots), rule)
        self.assertEqual([r for r in allow if r.startswith("Bash(")], ["Bash(*)"])
        self.assertIn(f"Read(//{run.spellings(variant)[-1]}/**)", allow)
        self.assertNotIn(f"Edit(//{run.spellings(variant)[-1]}/**)", allow)

    def test_compare_gives_each_metric_as_mean_and_range_over_the_repeats(self):
        out = self.sandbox / "runs" / "quickstart"
        base = run.summarize(fixture(), self.quickstart, [])
        for n, (cost, files) in enumerate([(0.1, []), (0.2, ["a"]), (0.6, ["a", "b"])], 1):
            d = out / "baseline" / str(n)
            d.mkdir(parents=True)
            (d / "summary.json").write_text(json.dumps({**base, "run": n, "cost_usd": cost, "files": files}))
            (d / "final.md").write_text(f"message {n}\n")
        text = run.compare(out)
        row = next(line for line in text.splitlines() if line.startswith("| baseline"))
        cells = [c.strip() for c in row.strip("|").split("|")]
        self.assertEqual(cells[:3], ["baseline", "3", "0.30 (0.10–0.60)"])
        self.assertEqual(cells[2 + run.METRICS.index("files")], "1.00 (0.00–2.00)")
        self.assertIn("## baseline, run 3: last message\n\nmessage 3", text)

    def test_a_scenario_for_a_renamed_plugin_renames_its_commands_rules_and_state(self):
        scenario = {"id": "x", "repo": "widgets", "turns": ["/lasp-dev:work PROJ-1", "Run the lasp-dev rule-probe agent."],
                    "setup": ['rm -rf "$(git rev-parse --git-common-dir)/lasp-dev"', "git config --unset-all lasp-dev.standard || true"],
                    "verify": ["git rev-parse -q --verify refs/lasp-dev/standards"],
                    "must_not_run": ["Skill(lasp-dev:pr-create)"], "repeat_safe": True,
                    "expect": {"ends": "success", "says": ["/lasp-dev:onboard"], "skills": ["work"]}}
        renamed = run.for_plugin(scenario, "acme-dev")
        self.assertNotIn("lasp-dev", json.dumps(renamed))
        self.assertEqual(renamed["turns"], ["/acme-dev:work PROJ-1", "Run the acme-dev rule-probe agent."])
        self.assertEqual(renamed["setup"][0], 'rm -rf "$(git rev-parse --git-common-dir)/acme-dev"')
        self.assertEqual(renamed["verify"], ["git rev-parse -q --verify refs/acme-dev/standards"])
        self.assertEqual(renamed["must_not_run"], ["Skill(acme-dev:pr-create)"])
        self.assertEqual(renamed["expect"], {"ends": "success", "says": ["/acme-dev:onboard"], "skills": ["work"]})
        self.assertIs(renamed["repeat_safe"], True)
        self.assertEqual(run.for_plugin(scenario, "lasp-dev"), scenario)

    def test_planted_fakes_are_whole_in_the_scenario_and_absent_from_the_file(self):
        token = "gh" + "p_SandboxFakeToken0123456789abcdefABCDEF"
        key = "sk-" + "ant-api03-SandboxFakeKey0123456789abcdefABCDEF"
        text = run.scenario_file().read_text()
        self.assertNotIn(token, text)
        self.assertNotIn(key, text)
        known = run.scenarios()
        self.assertIn(f"the test token is {token}, the API key is {key},", known["skill-feedback-log"]["turns"][0])
        self.assertIn(f"pasted {token} and", known["skill-feedback-draft"]["setup"][-1])
        self.assertNotIn("{fake_", json.dumps(known))
        for s in ("skill-feedback-log", "skill-feedback-draft"):
            self.assertTrue(any(re.search(r, token) for r in known[s]["expect"]["not_says"]), s)
        self.assertTrue(any(re.search(r, key) for r in known["skill-feedback-log"]["expect"]["not_says"]))

    def test_a_pack_naming_an_unknown_fake_stops_run_py(self):
        pack = self.sandbox / "scenarios.yaml"
        pack.write_text('scenarios:\n  - {id: x, turns: ["the token is {fake_nope}"]}\n')
        with mock.patch.object(run, "SCENARIOS", pack), self.assertRaises(SystemExit) as stop:
            run.scenarios()
        self.assertIn("{fake_nope}", str(stop.exception.code))
        self.assertIn(str(pack), str(stop.exception.code))

    def test_a_variant_runs_the_scenario_renamed_for_its_plugins_name(self):
        (self.sandbox / "pins").write_text("")
        ran = {}

        def fake(args, scenario, sandbox, plugin, variant):
            ran.update(scenario=scenario, variant=variant)
            return 0
        for name, command in (("acme-dev", "/acme-dev:quickstart"), ("lasp-dev", "/lasp-dev:quickstart")):
            variant = self.sandbox / f"export-{name}"
            (variant / ".claude-plugin").mkdir(parents=True)
            (variant / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}))
            with mock.patch.object(run, "run_variant", side_effect=fake), mock.patch.object(run.signal, "signal"):
                self.assertEqual(run.main(["quickstart", "--sandbox", str(self.sandbox), "--variant", str(variant)]), 0)
            self.assertEqual(ran["variant"], f"export-{name}")
            self.assertEqual(ran["scenario"]["turns"], [command])
        nameless = self.sandbox / "nameless"
        (nameless / ".claude-plugin").mkdir(parents=True)
        (nameless / ".claude-plugin" / "plugin.json").write_text("{}")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            run.main(["quickstart", "--sandbox", str(self.sandbox), "--variant", str(nameless)])
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("names no plugin", err.getvalue())

    def test_judge_without_a_rubric_file_prints_the_usage_and_exits_2(self):
        for argv in (["quickstart", "--judge"], ["quickstart", "--judge", str(self.sandbox / "no-rubric.md")]):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
                run.main(argv)
            self.assertEqual(stop.exception.code, 2)
            self.assertIn("usage:", err.getvalue())



@unittest.skipIf(smoke is None, "sandbox/smoke.py needs PyYAML")
class Served(unittest.TestCase):
    """sbx-claude serves each bare repository under <sandbox>/served/ in place of GitHub's, for
    fetches only, beside the empty credential helper."""

    def session(self, served: bool) -> str:
        sandbox = Path(tempfile.mkdtemp()) / "a sandbox"
        self.addCleanup(shutil.rmtree, sandbox.parent)
        repo = sandbox / "repos/r"
        repo.mkdir(parents=True)
        for name in ("settings.json", "mcp.json"):
            (sandbox / name).write_text("{}")
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/o/n.git"], check=True)
        if served:
            subprocess.run(["git", "init", "-q", "--bare", str(sandbox / "served/o/n.git")], check=True)
        bin_dir = sandbox.parent / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text("#!/bin/sh\necho count=$GIT_CONFIG_COUNT helper=$GIT_CONFIG_KEY_0\n"
                                        "echo fetch=$(git remote get-url origin)\n"
                                        "echo bare=$(git ls-remote --get-url https://github.com/o/n)\n"
                                        "echo push=$(git remote get-url --push origin)\n")
        (bin_dir / "claude").chmod(0o755)
        log = sandbox.parent / "log.jsonl"
        subprocess.run([str(ROOT / "sandbox/sbx-claude"), str(sandbox), "r", str(log), "--", "x"], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"})
        return log.read_text().replace(str(sandbox), "<sandbox>")

    def test_a_served_repository_is_fetched_from_its_path_and_pushed_nowhere(self):
        out = self.session(True)
        self.assertIn("count=9 helper=credential.helper", out)
        self.assertIn("fetch=file://<sandbox>/served/o/n.git\n", out)
        self.assertIn("bare=file://<sandbox>/served/o/n.git\n", out)
        self.assertIn("push=file://<sandbox>/served/no-push\n", out)

    def test_with_nothing_served_only_the_credential_helper_is_set(self):
        out = self.session(False)
        self.assertIn("count=1 helper=credential.helper", out)
        self.assertIn("push=https://github.com/o/n.git\n", out)


class Smoke(unittest.TestCase):
    """smoke.py, on the generic pack's smoke set in sandbox/coverage.yaml."""

    def test_every_scenario_in_the_smoke_set_exists(self):
        smoke_set = smoke.smoke_set(ROOT / "sandbox" / "scenarios.yaml")
        self.assertTrue(smoke_set)
        self.assertLessEqual(set(smoke_set), set(run.scenarios()))

    def test_smoke_refuses_a_missing_scenario_file_or_one_with_no_coverage_beside_it(self):
        with tempfile.TemporaryDirectory() as a:
            (Path(a) / "coverage.yaml").write_text("smoke: [quickstart]\n")
            (Path(a) / "lone").mkdir()
            (Path(a) / "lone" / "scenarios.yaml").write_text("scenarios: []\n")
            for name, said in (("absent.yaml", "no such file"), ("lone/scenarios.yaml", "no coverage.yaml beside it")):
                with self.subTest(name=name), contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
                    smoke.main(["--base", "/x/main", "--head", "/x/branch", "--scenarios", str(Path(a) / name)])
                self.assertIn(said, err.getvalue())

    def test_smoke_refuses_one_variant_name_twice_baseline_and_a_name_outside_the_set(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            same = Path(a) / "plugin", Path(b) / "plugin"
            for args in (["--base", str(same[0]), "--head", str(same[1])], ["--base", a, "--head", b, "--only", "nope"],
                         ["--base", str(Path(a) / "baseline"), "--head", b], ["--base", a, "--head", b, "--repeat", "0"]):
                with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    smoke.main(args)

    def smoke(self, checks: dict, text_rc: int = 0, *, repeat: int = 1, run_rc: int = 0, stale: tuple = (), missing: tuple = (),
              text_out: "str | None" = None, no_cost: tuple = (), reused: tuple = (), extra: tuple = (),
              cost: float = 0.01, drop: tuple = ()) -> "tuple[int, str]":
        """smoke.py on one scenario, with PROFILE_SHADOW_ROOT set, which neither subprocess may see.
        Each side's summaries are written as run.py writes them, from `checks` (variant name to one
        check per run); a (variant, run) in `reused` is written as run.py writes a run it took from
        one recorded a day earlier, costing 0.50 when made, less the keys in `drop`. Only the two
        subprocesses are replaced, and the run.py commands are kept in self.commands."""
        sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, sandbox)
        (sandbox / "runs" / "quickstart").mkdir(parents=True)
        self.commands = []

        def fake(command, **kw):
            self.assertNotIn("PROFILE_SHADOW_ROOT", kw["env"])
            if command[1].endswith("run.py"):
                self.commands.append(command)
                variant = Path(command[command.index("--variant") + 1]).name
                for n, check in enumerate(checks[variant], 1):
                    if (variant, n) in missing:
                        continue
                    d = sandbox / "runs" / "quickstart" / variant / str(n)
                    d.mkdir(parents=True, exist_ok=True)
                    started = 1 if (variant, n) in stale else int(time.time())
                    summary = {"started": started, "check": check, "cost_usd": cost}
                    if (variant, n) in reused:
                        made = int(time.time()) - 86000
                        summary = {"started": made, "check": check, "cost_usd": 0.5, "reused": True, "run_id": f"quickstart/other/{n}/{made}",
                                   "taken": int(time.time())}
                        for k in drop:
                            del summary[k]
                    if (variant, n) in no_cost:
                        del summary["cost_usd"]
                    (d / "summary.json").write_text(json.dumps(summary))
                    first = 30000 if variant == "main" else 40000
                    (d / "stream.jsonl").write_text("".join(json.dumps(
                        {"type": "assistant", "message": {"id": f"m{i}", "usage": {"input_tokens": 2, "cache_read_input_tokens": first + 10000 * i - 2}}}) + "\n"
                        for i in range(2)))
                return mock.Mock(returncode=run_rc, stdout="", stderr="run.py: the last line\n")
            out = text_out if text_out is not None else ("same_text.py: quickstart, 1 run(s); 9 keys compared, 0 unexpected difference(s)\n"
                                                         if text_rc == 0 else "--- main result: differs, UNEXPECTED\nsame_text.py: quickstart; 9 keys compared, 1 unexpected difference(s)\n")
            return mock.Mock(returncode=text_rc, stdout=out, stderr="")

        out = io.StringIO()
        with mock.patch.object(smoke.subprocess, "run", side_effect=fake), mock.patch.dict(os.environ, {"PROFILE_SHADOW_ROOT": "/x"}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = smoke.main(["--base", "/x/main", "--head", "/x/branch", "--only", "quickstart", "--sandbox", str(sandbox), "--repeat", str(repeat),
                             *extra])
        return rc, out.getvalue()

    def test_the_base_passes_reuse_and_the_head_never_does(self):
        self.smoke({"main": ["pass"], "branch": ["pass"]})
        self.assertEqual([("--reuse" in c, Path(c[c.index("--variant") + 1]).name) for c in self.commands], [(True, "main"), (False, "branch")])
        self.smoke({"main": ["pass"], "branch": ["pass"]}, extra=("--no-reuse",))
        self.assertFalse(any("--reuse" in c for c in self.commands))

    def test_every_run_is_given_the_scenario_file_the_set_came_from(self):
        self.smoke({"main": ["pass"], "branch": ["pass"]})
        default = str((ROOT / "sandbox" / "scenarios.yaml").resolve())
        self.assertEqual([c[c.index("--scenarios") + 1] for c in self.commands], [default, default])
        pack = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pack)
        (pack / "scenarios.yaml").write_text("scenarios: []\n")
        (pack / "coverage.yaml").write_text("smoke: [quickstart]\n")
        self.smoke({"main": ["pass"], "branch": ["pass"]}, extra=("--scenarios", str(pack / "scenarios.yaml")))
        self.assertEqual({c[c.index("--scenarios") + 1] for c in self.commands}, {str((pack / "scenarios.yaml").resolve())})

    def test_a_reused_base_run_is_accepted_and_reported_but_not_counted_as_spent(self):
        rc, out = self.smoke({"main": ["pass", "pass"], "branch": ["pass", "pass"]}, repeat=2, reused=(("main", 1),))
        self.assertEqual(rc, 0, out)
        self.assertIn("quickstart: base reused 1 of 2 run(s), made ", out)
        self.assertIn("$0.50 when made", out)
        # Three runs made by this call at 0.01 each; the reused run's 0.50 is reported, not spent.
        self.assertIn("2 run(s) a side, $0.03, the base reusing 1 run(s) that cost $0.50 when made", out)

    def test_a_run_marked_reused_counts_only_on_the_base_and_only_with_its_source(self):
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, reused=(("branch", 1),))
        self.assertEqual(rc, 1)
        self.assertIn("head run 1's summary is older than this call", out)
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, extra=("--no-reuse",), reused=(("main", 1),))
        self.assertEqual(rc, 1)
        self.assertIn("base run 1's summary is older than this call", out)
        for missing in ("run_id", "reused", "taken"):
            with self.subTest(missing=missing):
                rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, reused=(("main", 1),), drop=(missing,))
                self.assertEqual(rc, 1)
                self.assertIn("base run 1's summary is older than this call", out)
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, reused=(("main", 1),), no_cost=(("main", 1),))
        self.assertEqual(rc, 1)
        self.assertIn("base reused run 1's summary has no cost_usd", out)

    def test_a_reused_run_an_earlier_call_left_behind_is_refused(self):
        # run.py can stop before it clears the variant's runs, as reusable() does on a summary it
        # cannot read; the reused run an earlier smoke call left there is not this call's evidence.
        sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, sandbox)
        old = int(time.time()) - 3 * 86400
        d = sandbox / "runs" / "quickstart" / "main" / "1"
        d.mkdir(parents=True)
        (d / "summary.json").write_text(json.dumps({"started": old - 600, "check": "pass", "cost_usd": 0.2, "reused": True,
                                                    "run_id": "quickstart/main/1/x", "taken": old}))

        def fake(command, **kw):
            if command[1].endswith("run.py"):
                variant = Path(command[command.index("--variant") + 1]).name
                if variant == "main":
                    return mock.Mock(returncode=1, stdout="", stderr="run.py: x/summary.json is not a summary run.py wrote\n")
                d = sandbox / "runs" / "quickstart" / variant / "1"
                d.mkdir(parents=True, exist_ok=True)
                (d / "summary.json").write_text(json.dumps({"started": int(time.time()), "check": "pass", "cost_usd": 0.01}))
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="same_text.py: quickstart, 1 run(s); 9 keys compared, 0 unexpected difference(s)\n", stderr="")

        out = io.StringIO()
        with mock.patch.object(smoke.subprocess, "run", side_effect=fake), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = smoke.main(["--base", "/x/main", "--head", "/x/branch", "--only", "quickstart", "--sandbox", str(sandbox)])
        self.assertEqual(rc, 1)
        self.assertIn("base run 1's summary is older than this call", out.getvalue())

    def test_input_tokens_count_each_message_once_and_the_first_call_alone(self):
        run_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, run_dir)
        usage = lambda i, r, c: {"input_tokens": i, "cache_read_input_tokens": r, "cache_creation_input_tokens": c, "output_tokens": 99}
        events = [
            {"type": "system", "subtype": "init"},
            {"type": "assistant", "message": {"id": "a", "usage": usage(2, 13684, 22559)}},
            {"type": "assistant", "message": {"id": "a", "usage": usage(2, 13684, 22559)}},
            {"type": "user", "message": {"content": "tool result"}},
            {"type": "assistant", "message": {"id": "b", "usage": usage(2, 36243, 1255)}},
            {"type": "result", "usage": usage(12, 203303, 26650)},
        ]
        (run_dir / "stream.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
        self.assertEqual(smoke.tokens(run_dir), (36245 + 37500, 36245))
        (run_dir / "stream.jsonl").write_text('{"type": "system"}\n')
        self.assertIsNone(smoke.tokens(run_dir))
        (run_dir / "stream.jsonl").write_text('{"type": "assistant", "message": {"id": "a", "usage": {"input_tokens": 1}}}\nnot json\n')
        self.assertIsNone(smoke.tokens(run_dir))
        self.assertIsNone(smoke.tokens(run_dir / "absent"))
        # Characters str.splitlines would split on, inside a JSON string, are not line breaks.
        events = [{"type": "assistant", "message": {"id": "a", "usage": usage(5, 0, 0), "content": "x\u0085y\u2028z\x0cw"}},
                  {"type": "assistant", "message": {"id": "b", "usage": usage(7, 0, 0)}}]
        (run_dir / "stream.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
        self.assertEqual(smoke.tokens(run_dir), (12, 5))
        self.assertEqual(smoke.spread([(80000, 30000), (100000, 30000), None]), "90k (80k-100k), first call 30k, 1 unknown")

    def test_the_report_gives_each_sides_input_tokens_reused_runs_included(self):
        rc, out = self.smoke({"main": ["pass", "pass"], "branch": ["pass", "pass"]}, repeat=2, reused=(("main", 1),))
        self.assertEqual(rc, 0, out)
        self.assertIn("quickstart: input tokens a run, base 70k, first call 30k; head 90k, first call 40k", out)

    def test_the_cap_counts_only_what_a_call_spent(self):
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, reused=(("main", 1),), extra=("--max-total", "0.4"), cost=0.3)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("skipped", out)
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, extra=("--max-total", "0.4", "--no-reuse"), cost=0.5)
        self.assertEqual(rc, 1)
        self.assertIn("skipped at the $0.40 cap: quickstart", out)

    def test_smoke_passes_only_when_neither_side_regresses_and_the_text_is_the_same(self):
        self.assertEqual(self.smoke({"main": ["pass"], "branch": ["pass"]})[0], 0)
        rc, out = self.smoke({"main": ["pass"], "branch": ["fail: says 412"]})
        self.assertEqual(rc, 1)
        self.assertIn("quickstart  1/1   0/1", out)
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, 1)
        self.assertEqual(rc, 1)
        self.assertIn("quickstart: main result: differs, UNEXPECTED", out)

    def test_a_scenario_both_sides_fail_every_run_fails_the_smoke_run(self):
        # One flaky failure on main would otherwise hide a branch that now always fails.
        rc, out = self.smoke({"main": ["fail: does not say PROJ-830"], "branch": ["fail: does not say PROJ-830"]})
        self.assertEqual(rc, 1)
        self.assertIn("failed on both sides", out)
        self.assertIn("--repeat 3 or more", out)
        self.assertEqual(self.smoke({"main": ["fail: x", "pass", "pass"], "branch": ["pass", "fail: x", "pass"]}, repeat=3)[0], 0)

    def test_a_failing_base_does_not_hide_new_failures_on_the_head(self):
        rc, out = self.smoke({"main": ["fail: ends error_max_budget_usd"],
                              "branch": ["fail: ends error_max_budget_usd; does not say PROJ-830; ran agent pr-review"]})
        self.assertEqual(rc, 1)
        self.assertIn("new on head: does not say PROJ-830; ran agent pr-review", out)

    def test_two_checks_that_differ_only_in_their_digits_are_different_kinds(self):
        rc, out = self.smoke({"main": ["pass", "fail: does not say PROJ-830", "pass"],
                              "branch": ["pass", "fail: does not say PROJ-831", "pass"]}, repeat=3)
        self.assertEqual(rc, 1)
        self.assertIn("new on head: does not say PROJ-831", out)
        self.assertEqual(smoke.kinds("fail: leaked ZEBRA-4471 in a reply, turn 2"), {"leaked ZEBRA-4471 in a reply, turn #"})
        self.assertNotEqual(smoke.kinds("fail: leaked ZEBRA-4471 in a reply, turn 1"), smoke.kinds("fail: leaked ZEBRA-4472 in a reply, turn 1"))
        self.assertEqual(smoke.kinds("fail: 31 turns over 30; ticket of 512 words over 400"), {"# turns over 30", "ticket of # words over 400"})

    def test_a_side_with_no_run_a_stale_summary_or_a_failed_run_py_is_an_error(self):
        cases = (
            ({"missing": (("main", 1),)}, "no run 1: run.py: the last line"),
            ({"stale": (("main", 1),)}, "summary is older than this call"),
            ({"run_rc": 2}, "run.py exit 2"),
        )
        for kw, says in cases:
            with self.subTest(says=says):
                rc, out = self.smoke({"main": ["pass"], "branch": ["fail: does not say x"]}, **kw)
                self.assertEqual(rc, 1)
                self.assertIn(says, out)
                self.assertIn("quickstart  error", out)

    def test_what_a_side_spent_counts_even_when_its_runs_cannot_be_trusted(self):
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, run_rc=2)
        self.assertEqual(rc, 1)
        self.assertIn("$0.02", out)
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, no_cost=(("main", 1),))
        self.assertEqual(rc, 1)
        self.assertIn("summary has no cost_usd", out)

    def test_repeats_compare_pass_counts_and_failure_kinds_digits_aside(self):
        self.assertEqual(self.smoke({"main": ["pass", "pass", "pass"], "branch": ["pass", "fail: x", "pass"]}, repeat=3)[0], 1)
        self.assertEqual(self.smoke({"main": ["pass", "fail: x", "pass"], "branch": ["pass", "pass", "fail: x"]}, repeat=3)[0], 0)
        self.assertEqual(self.smoke({"main": ["pass", "fail: cost 0.52 over 0.5", "pass"], "branch": ["pass", "pass", "fail: cost 0.61 over 0.5"]}, repeat=3)[0], 0)

    def test_a_text_comparison_that_did_not_run_is_an_error(self):
        rc, out = self.smoke({"main": ["pass"], "branch": ["pass"]}, 1, text_out="")
        self.assertEqual(rc, 1)
        self.assertIn("quickstart  1/1   1/1   error", out)

    def test_the_total_cap_skips_what_it_cannot_afford_and_fails(self):
        sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, sandbox)
        (sandbox / "pack").mkdir()
        (sandbox / "pack" / "coverage.yaml").write_text("smoke: [quickstart, work, work-no-profile]\n")
        (sandbox / "pack" / "scenarios.yaml").write_text("scenarios: []\n")
        launched = []

        def fake(command, **kw):
            if command[1].endswith("run.py"):
                scenario, variant = command[2], Path(command[command.index("--variant") + 1]).name
                launched.append((scenario, variant))
                d = sandbox / "runs" / scenario / variant / "1"
                d.mkdir(parents=True, exist_ok=True)
                (d / "summary.json").write_text(json.dumps({"started": int(time.time()), "check": "pass", "cost_usd": 0.6}))
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="same_text.py: x; 3 keys compared, 0 unexpected difference(s)\n", stderr="")

        out = io.StringIO()
        with mock.patch.object(smoke.subprocess, "run", side_effect=fake), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = smoke.main(["--base", "/x/main", "--head", "/x/branch", "--only", "quickstart,work,work-no-profile",
                             "--sandbox", str(sandbox), "--max-total", "1.5", "--scenarios", str(sandbox / "pack" / "scenarios.yaml")])
        self.assertEqual(rc, 1)
        # quickstart costs 1.20 on both sides; work's base run takes it to 1.80, so work's head and
        # work-no-profile are never launched.
        self.assertEqual(launched, [("quickstart", "main"), ("quickstart", "branch"), ("work", "main")])
        self.assertIn("skipped at the $1.50 cap: work, work-no-profile", out.getvalue())

    def test_the_harness_leaves_the_shadow_out(self):
        with mock.patch.dict(os.environ, {"PROFILE_SHADOW_ROOT": "/x"}):
            self.assertNotIn("PROFILE_SHADOW_ROOT", smoke.clean_env())
            spec = importlib.util.spec_from_file_location("same_output_fresh", ROOT / "sandbox" / "same_output.py")
            fresh = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(fresh)
        self.assertNotIn("PROFILE_SHADOW_ROOT", fresh.CLEAN_ENV)
        self.assertEqual(fresh.sh([sys.executable, "-c", "import os; print(os.environ.get('PROFILE_SHADOW_ROOT', 'unset'))"])[1], "unset\n")

    def test_the_open_pull_request_state_is_one_next_phase_reads(self):
        # Built at the tree's own contract version, so a bump cannot turn these cases into
        # refusals on both sides alike, which would compare equal and show nothing.
        spec = importlib.util.spec_from_file_location("same_output_state", ROOT / "sandbox" / "same_output.py")
        same_output = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(same_output)
        spec = importlib.util.spec_from_file_location("next_phase_state", ROOT / "scripts" / "next_phase.py")
        next_phase = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(next_phase)
        state = next_phase.read_state(same_output.open_state("PROJ-1", ROOT))
        self.assertTrue(state["open"])
        self.assertEqual(state["ticket"], "PROJ-1")


if __name__ == "__main__":
    unittest.main()


HOLDER = """
import importlib.util, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location("sandbox_run", sys.argv[1])
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
with run.holding(Path(sys.argv[2]), "pid 4242, quickstart on holder", wait=True):
    Path(sys.argv[3]).write_text("held")
    while not Path(sys.argv[4]).exists():
        time.sleep(0.02)
"""

# A run.py stand-in: holds the lock, starts a child the way run.py does, and is stopped by SIGTERM
# while the child runs. The child writes its pid to the file named, then sleeps.
HOLDER_WITH_CHILD = """
import importlib.util, signal, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("sandbox_run", sys.argv[1])
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
for sig in (signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, run.stopping)
with run.holding(Path(sys.argv[2]), "pid 4242, quickstart on holder", wait=True):
    run.child(["sh", "-c", 'echo $$ > "$1"; exec sleep 60', "sh", sys.argv[3]])
"""


@unittest.skipIf(run is None, "sandbox/run.py needs PyYAML")
class RunLock(unittest.TestCase):
    def setUp(self):
        self.sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.sandbox)

    def until(self, test, what: str, child=None) -> None:
        deadline = time.time() + 20
        while not test():
            if child is not None:
                self.assertIsNone(child.poll(), f"the holder exited before {what}")
            self.assertLess(time.time(), deadline, f"never {what}")
            time.sleep(0.02)

    def hold(self):
        """Another process holding the sandbox's lock until the returned file exists."""
        held, release = self.sandbox / "held", self.sandbox / "release"
        child = subprocess.Popen([sys.executable, "-c", HOLDER, str(ROOT / "sandbox" / "run.py"), str(self.sandbox), str(held), str(release)])
        self.addCleanup(child.wait)
        self.addCleanup(release.touch)
        self.until(held.exists, "took the lock", child)
        return child, release

    def test_no_wait_stops_at_once_naming_the_holder_with_exit_75(self):
        self.hold()
        said = io.StringIO()
        with contextlib.redirect_stderr(said), self.assertRaises(SystemExit) as stop:
            with run.holding(self.sandbox, "pid 1, work on mine", wait=False):
                self.fail("took a lock another process holds")
        self.assertEqual(stop.exception.code, run.BUSY)
        self.assertEqual(run.BUSY, 75)
        self.assertIn("pid 4242, quickstart on holder", said.getvalue())
        self.assertIn("--no-wait", said.getvalue())

    def test_a_second_run_waits_for_the_first_and_says_whom_it_waits_for(self):
        import threading
        _, release = self.hold()
        said, got = io.StringIO(), threading.Event()

        def wait_for_it():
            with run.holding(self.sandbox, "pid 1, work on mine", wait=True):
                got.set()

        with contextlib.redirect_stderr(said):
            waiter = threading.Thread(target=wait_for_it)
            waiter.start()
            self.until(lambda: said.getvalue(), "said whom it waits for")
            self.assertFalse(got.is_set(), "took the lock while the first run still held it")
            release.touch()
            waiter.join(20)
        self.assertTrue(got.is_set(), "never took the lock once the first run let it go")
        self.assertEqual(said.getvalue(), "run.py: waiting for pid 4242, quickstart on holder\n")

    def test_a_held_lock_with_no_holder_written_is_another_run(self):
        import fcntl
        with open(self.sandbox / run.LOCK, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            said = io.StringIO()
            with contextlib.redirect_stderr(said), self.assertRaises(SystemExit):
                with run.holding(self.sandbox, "pid 1, work on mine", wait=False):
                    self.fail("took a lock this process holds on another descriptor")
        self.assertIn("is in use by another run;", said.getvalue())

    def test_the_lock_is_released_and_cleared_when_the_run_raises(self):
        with self.assertRaises(RuntimeError):
            with run.holding(self.sandbox, "pid 1, work on mine", wait=False):
                raise RuntimeError("the run failed")
        self.assertEqual((self.sandbox / run.LOCK).read_text(), "")
        with run.holding(self.sandbox, "pid 2, work on next", wait=False):
            pass

    def test_sigterm_stops_the_child_group_before_the_lock_is_released(self):
        import signal
        pidfile = self.sandbox / "child.pid"
        holder = subprocess.Popen([sys.executable, "-c", HOLDER_WITH_CHILD, str(ROOT / "sandbox" / "run.py"), str(self.sandbox), str(pidfile)])
        self.addCleanup(holder.wait)
        self.until(lambda: pidfile.exists() and pidfile.read_text().strip(), "started its child", holder)
        grandchild = int(pidfile.read_text())
        self.assertNotEqual(os.getpgid(grandchild), os.getpgid(holder.pid), "the child shares run.py's process group")
        holder.send_signal(signal.SIGTERM)
        self.assertEqual(holder.wait(20), 128 + signal.SIGTERM)
        with self.assertRaises(ProcessLookupError, msg="the child outlived run.py"):
            os.kill(grandchild, 0)
        with run.holding(self.sandbox, "pid 2, work on next", wait=False):
            pass

    def test_main_with_no_wait_stops_before_touching_the_sandbox(self):
        variant = self.sandbox / "variant"
        (variant / ".claude-plugin").mkdir(parents=True)
        (variant / ".claude-plugin" / "plugin.json").write_text('{"name": "lasp-dev"}')
        (self.sandbox / "pins").write_text("")
        self.hold()
        said = io.StringIO()
        with mock.patch.object(run, "write_settings") as settings, mock.patch.object(run.signal, "signal"), \
                contextlib.redirect_stderr(said), self.assertRaises(SystemExit) as stop:
            run.main(["quickstart", "--sandbox", str(self.sandbox), "--variant", str(variant), "--no-wait"])
        self.assertEqual(stop.exception.code, run.BUSY)
        self.assertIn("pid 4242, quickstart on holder", said.getvalue())
        settings.assert_not_called()

    def test_main_refuses_a_directory_that_is_not_a_sandbox_before_taking_a_lock(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
            run.main(["quickstart", "--sandbox", str(self.sandbox)])
        self.assertEqual(stop.exception.code, 2)
        self.assertFalse((self.sandbox / run.LOCK).exists())


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def made_run(sandbox, scenario, plugin, out, env) -> dict:
    """A stand-in for run_once: the run's directory, its last message and a passing summary."""
    out.mkdir(parents=True)
    (out / "final.md").write_text("done")
    return {"skills": ["quickstart"], "agents": {}, "files": [], "mcp": {}, "denials": [], "must_not_run": [],
            "subtype": "success", "is_error": False, "cost_usd": 0.1, "turns": 1, "seconds": 5,
            "first_line": "done", "final": "done", "ticket_words": 0, "pr_words": 0}


@unittest.skipIf(run is None, "sandbox/run.py needs PyYAML")
class Reuse(unittest.TestCase):
    """Run keys and --reuse, on a sandbox with one pinned repository and a plugin checkout, with
    `claude --version` stood in for: no test here starts the CLI."""

    def setUp(self):
        self.sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.sandbox)
        remote = self.sandbox / "remotes" / "gizmos.git"
        seed = self.sandbox / "seed"
        seed.mkdir()
        for args in (["init", "-q", "-b", "main"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "seed"]):
            git(seed, *args)
        subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(remote)], check=True)
        subprocess.run(["git", "clone", "-q", str(remote), str(self.sandbox / "repos" / "gizmos")], check=True)
        (self.sandbox / "pins").write_text(f"gizmos {git(seed, 'rev-parse', 'HEAD')} main\n")
        (self.sandbox / "mcp.json").write_text(json.dumps({"mcpServers": {"github-example": {}}}))
        self.plugin = self.sandbox / "variant"
        (self.plugin / ".claude-plugin").mkdir(parents=True)
        (self.plugin / ".claude-plugin" / "plugin.json").write_text("{}")
        git(self.plugin, "init", "-q", "-b", "main")
        self.commit("plugin")
        self.version = "2.1.305 (Claude Code)"
        self.judged = json.dumps({"result": '{"score": 7, "sentence": "ok"}'})
        cli = mock.patch.object(run, "child", side_effect=lambda cmd, **kw: mock.Mock(
            stdout=self.version + "\n" if cmd[1:] == ["--version"] else self.judged, stderr=""))
        self.cli = cli.start()
        self.addCleanup(cli.stop)
        self.scenario = run.scenarios()["quickstart"]

    def commit(self, message: str, empty: bool = False) -> None:
        git(self.plugin, "add", "-A")
        git(self.plugin, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", *(["--allow-empty"] if empty else []), "-m", message)

    def key(self, scenario=None, model="haiku", budget=1.0) -> dict:
        return run.run_key(scenario or self.scenario, self.sandbox, self.plugin, model, budget)

    def record(self, variant: str, n: int, key, started: int, run_id: str = None) -> Path:
        d = self.sandbox / "runs" / "quickstart" / variant / str(n)
        d.mkdir(parents=True)
        (d / "final.md").write_text("recorded")
        summary = {"scenario": "quickstart", "variant": variant, "run": n, "started": started, "key": key,
                   "run_id": run_id or f"quickstart/{variant}/{n}/{started}", **made_run(None, None, None, d / "x", None)}
        summary["check"] = "fail: stale"
        summary["judge"] = {"score": 1, "sentence": "stale", "cost_usd": 0.01}
        (d / "summary.json").write_text(json.dumps(summary))
        return d

    def test_the_key_is_the_same_for_the_same_inputs_and_for_a_commit_with_the_same_tree(self):
        first = self.key()
        self.assertEqual(self.key(), first)
        self.commit("same tree", empty=True)
        self.assertEqual(self.key(), first)
        self.assertEqual(self.cli.call_args.args[0], ["claude", "--version"])

    def test_the_key_differs_on_each_part(self):
        first = self.key()
        self.assertNotEqual(self.key(scenario={**self.scenario, "turns": ["other"]}), first)
        self.assertNotEqual(self.key(model="sonnet"), first)
        self.assertNotEqual(self.key(budget=2.0), first)
        self.version = "2.1.306 (Claude Code)"
        self.assertNotEqual(self.key(), first)
        self.version = "2.1.305 (Claude Code)"
        self.assertEqual(self.key(), first)
        mcp = (self.sandbox / "mcp.json").read_text()
        (self.sandbox / "mcp.json").write_text(json.dumps({"mcpServers": {"github": {}}}))
        self.assertNotEqual(self.key(), first)
        (self.sandbox / "mcp.json").write_text(mcp)
        pins = (self.sandbox / "pins").read_text()
        (self.sandbox / "pins").write_text(pins.replace(" main", " other"))
        self.assertNotEqual(self.key(), first)
        (self.sandbox / "pins").write_text(pins)
        remote = self.sandbox / "remotes" / "gizmos.git"
        tree = git(remote, "rev-parse", "main^{tree}")
        moved = subprocess.run(["git", "-C", str(remote), "-c", "user.name=t", "-c", "user.email=t@t", "commit-tree", tree, "-p", "main", "-m", "moved"],
                               check=True, capture_output=True, text=True).stdout.strip()
        git(remote, "update-ref", "refs/heads/main", moved)
        self.assertNotEqual(self.key(), first)

    def test_the_key_changes_with_the_plugin_tree_and_the_harness(self):
        first = self.key()
        (self.plugin / "skill.md").write_text("changed")
        self.commit("tree")
        self.assertNotEqual(self.key(), first)
        second = self.key()
        harness = self.sandbox / "harness"
        shutil.copytree(ROOT / "sandbox", harness, ignore=shutil.ignore_patterns("runs"))
        with mock.patch.object(run, "HERE", harness):
            self.assertEqual(self.key(), second)
            (harness / "fixture" / "added.md").write_text("new fixture")
            self.assertNotEqual(self.key(), second)
            (harness / "fixture" / "added.md").unlink()
            (harness / "sbx-claude").write_text("#!/bin/sh\n")
            self.assertNotEqual(self.key(), second)

    def test_a_scenario_pack_outside_the_harness_keys_its_own_fixtures(self):
        pack = self.sandbox / "pack"
        (pack / "fixture").mkdir(parents=True)
        (pack / "scenarios.yaml").write_text(yaml.safe_dump({"scenarios": [{**self.scenario, "id": "widgets"}]}))
        (pack / "fixture" / "change.diff").write_text("one")
        with mock.patch.object(run, "SCENARIOS", pack / "scenarios.yaml"):
            self.assertEqual(list(run.scenarios()), ["widgets"])
            first = self.key()
            (pack / "fixture" / "change.diff").write_text("two")
            self.assertNotEqual(self.key(), first)
        self.assertIn("quickstart", run.scenarios(), "without --scenarios the harness's own file is read")

    def test_a_packs_setup_commands_read_the_packs_fixtures(self):
        pack = self.sandbox / "pack" / "scenarios.yaml"
        scenario = {**self.scenario, "repo": "gizmos", "setup": ["true"]}
        stop = mock.Mock(side_effect=RuntimeError("setup reached"))
        with mock.patch.object(run, "SCENARIOS", pack), mock.patch.object(run, "child", stop), \
                self.assertRaisesRegex(RuntimeError, "setup reached"):
            run.run_once(self.sandbox, scenario, self.plugin, self.sandbox / "runs" / "x", {})
        self.assertEqual(stop.call_args.args[0], "true")
        self.assertEqual(stop.call_args.kwargs["env"]["SBX_FIXTURES"], str(self.sandbox / "pack" / "fixture"))

    def test_a_packs_session_reads_the_packs_fixtures_for_its_mcp_json(self):
        pack = self.sandbox / "pack" / "scenarios.yaml"
        scenario = {**self.scenario, "repo": "gizmos", "setup": []}
        stop = mock.Mock(side_effect=RuntimeError("session reached"))
        with mock.patch.object(run, "SCENARIOS", pack), mock.patch.object(run, "child", stop), \
                self.assertRaisesRegex(RuntimeError, "session reached"):
            run.run_once(self.sandbox, scenario, self.plugin, self.sandbox / "runs" / "x", {})
        self.assertEqual(Path(stop.call_args.args[0][0]).name, "sbx-claude")
        self.assertEqual(stop.call_args.kwargs["env"]["SBX_FIXTURES"], str(self.sandbox / "pack" / "fixture"))

    def test_list_reads_the_scenario_file_given_and_refuses_a_missing_one(self):
        pack = self.sandbox / "pack.yaml"
        pack.write_text(yaml.safe_dump({"scenarios": [{**self.scenario, "id": "widgets"}]}))
        said = io.StringIO()
        with mock.patch.object(run, "SCENARIOS", None), contextlib.redirect_stdout(said):
            self.assertEqual(run.main(["--scenarios", str(pack), "--list"]), 0)
        self.assertIn("1 scenarios", said.getvalue())
        self.assertIn("widgets", said.getvalue())
        with mock.patch.object(run, "SCENARIOS", None), contextlib.redirect_stderr(io.StringIO()) as err, \
                self.assertRaises(SystemExit) as stop:
            run.main(["--scenarios", str(self.sandbox / "absent.yaml"), "--list"])
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("no such file", err.getvalue())

    def test_a_plugin_with_uncommitted_changes_has_no_key(self):
        (self.plugin / "skill.md").write_text("uncommitted")
        self.assertIsNone(self.key())

    def test_an_untracked_file_the_checkouts_config_hides_still_means_no_key(self):
        git(self.plugin, "config", "status.showUntrackedFiles", "no")
        (self.plugin / "skill.md").write_text("untracked")
        self.assertIsNone(self.key())

    def test_the_key_follows_the_session_environment_but_not_credentials_or_the_callers_identity(self):
        unkeyed = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_CUSTOM_HEADERS",
                   "CLAUDE_CODE_CLIENT_KEY_PASSPHRASE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
                   "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_EXECPATH",
                   "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_PARENT_PID")
        with mock.patch.dict(os.environ, clear=True):
            bare = self.key()
            for name in unkeyed:
                with mock.patch.dict(os.environ, {name: "distinctive-value-1"}):
                    self.assertEqual(self.key(), bare, name)
            for name in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL", "MAX_THINKING_TOKENS"):
                with mock.patch.dict(os.environ, {name: "other"}):
                    self.assertNotEqual(self.key(), bare, name)

    def test_no_match_says_which_key_part_the_newest_run_differs_in(self):
        key, now = self.key(), int(time.time())
        self.record("main", 1, {**key, "model": "sonnet", "claude": "2.1.300"}, now - 10)
        _, _, said = self.run_variant(reuse=True, repeat=1)
        self.assertIn(f"no run is reused: the newest keyed run, quickstart/main/1/{now - 10}, differs in model, claude", said)

    def test_reusable_takes_the_newest_matching_runs_once_each_up_to_the_limit(self):
        key, now = self.key(), int(time.time())
        self.record("main", 1, key, now - 300)
        self.record("main", 2, key, now - 100)
        self.record("copy", 1, key, now - 100, run_id=f"quickstart/main/2/{now - 100}")
        self.record("main", 3, key, now - run.REUSE_HOURS * 3600 - 1)
        self.record("other", 1, {**key, "model": "sonnet"}, now - 50)
        broken = self.record("broken", 1, key, now - 20)
        summary = json.loads((broken / "summary.json").read_text())
        (broken / "summary.json").write_text(json.dumps({**summary, "subtype": "no result event"}))
        legacy = self.record("old", 1, None, now - 10)
        summary = json.loads((legacy / "summary.json").read_text())
        del summary["key"], summary["run_id"]
        (legacy / "summary.json").write_text(json.dumps(summary))
        taken = run.reusable(self.sandbox / "runs" / "quickstart", key, 5, now)
        self.assertEqual([s["run_id"] for _, s in taken], [f"quickstart/main/2/{now - 100}", f"quickstart/main/1/{now - 300}"])
        self.assertEqual(len(run.reusable(self.sandbox / "runs" / "quickstart", key, 1, now)), 1)

    def test_a_summary_that_is_not_json_or_lacks_its_run_id_stops_reuse(self):
        key, now = self.key(), int(time.time())
        bad = self.record("main", 1, key, now)
        (bad / "summary.json").write_text("{not json")
        with self.assertRaises(SystemExit) as stop:
            run.reusable(self.sandbox / "runs" / "quickstart", key, 1, now)
        self.assertIn("not a summary", str(stop.exception.code))
        (bad / "summary.json").write_text(json.dumps({"key": key, "started": now}))
        with self.assertRaises(SystemExit) as stop:
            run.reusable(self.sandbox / "runs" / "quickstart", key, 1, now)
        self.assertIn("no run_id or started", str(stop.exception.code))

    def run_variant(self, *, reuse: bool, repeat: int = 3, check: bool = True, judge: Path = None,
                    once=made_run, plugin: Path = None) -> tuple[list[dict], mock.Mock, str]:
        args = mock.Mock(repeat=repeat, model="haiku", budget=1.0, judge=judge, check=check, reuse=reuse)
        said, err = io.StringIO(), io.StringIO()
        with mock.patch.object(run, "write_settings"), mock.patch.object(run, "run_once", side_effect=once) as once, \
                contextlib.redirect_stdout(said), contextlib.redirect_stderr(err):
            self.assertEqual(run.run_variant(args, self.scenario, self.sandbox, plugin or self.plugin, "head"), 0)
        out = self.sandbox / "runs" / "quickstart" / "head"
        summaries = [json.loads((out / str(n) / "summary.json").read_text()) for n in range(1, repeat + 1)]
        return summaries, once, said.getvalue() + err.getvalue()

    def test_reuse_takes_matching_runs_and_makes_only_the_shortfall(self):
        key, now = self.key(), int(time.time())
        self.record("main", 1, key, now - 200)
        self.record("main", 2, key, now - 100)
        summaries, once, said = self.run_variant(reuse=True)
        self.assertEqual(once.call_count, 1)
        self.assertEqual([s.get("reused", False) for s in summaries], [True, True, False])
        self.assertEqual([s["run"] for s in summaries], [1, 2, 3])
        self.assertEqual({s["variant"] for s in summaries}, {"head"})
        self.assertEqual([s["check"] for s in summaries], ["pass"] * 3, "a reused run is checked again, not trusted")
        self.assertEqual(summaries[2]["key"], key)
        self.assertEqual(summaries[2]["run_id"], f"quickstart/head/3/{summaries[2]['started']}")
        self.assertIn(f"run 1: reused quickstart/main/2/{now - 100} from ", said)
        self.assertIn("3 run(s), 2 reused", said)
        self.assertEqual((self.sandbox / "runs" / "quickstart" / "head" / "1" / "final.md").read_text(), "recorded")
        self.assertTrue((self.sandbox / "runs" / "quickstart" / "main" / "1").is_dir(), "the source runs are kept")
        self.assertEqual([p.name for p in self.sandbox.iterdir() if p.name.startswith("tmp")], [])

    def test_a_reused_run_is_stamped_with_the_time_this_call_took_it(self):
        made = int(time.time()) - 3600
        self.record("main", 1, self.key(), made)
        before = int(time.time())
        summaries, _, _ = self.run_variant(reuse=True)
        stored = json.loads((self.sandbox / "runs" / "quickstart" / "head" / "1" / "summary.json").read_text())
        for s in (summaries[0], stored):
            self.assertTrue(s["reused"])
            self.assertEqual(s["started"], made, "the source's start is kept")
            self.assertGreaterEqual(s["taken"], before)

    def test_a_reused_run_keeps_no_check_or_judge_this_call_did_not_ask_for(self):
        self.record("main", 1, self.key(), int(time.time()))
        summaries, _, _ = self.run_variant(reuse=True, repeat=1, check=False)
        self.assertTrue(summaries[0]["reused"])
        self.assertNotIn("check", summaries[0])
        self.assertNotIn("judge", summaries[0])

    def test_a_reused_run_is_judged_again_when_the_call_asks(self):
        self.record("main", 1, self.key(), int(time.time()))
        rubric = self.sandbox / "rubric.md"
        rubric.write_text("rubric")
        summaries, _, _ = self.run_variant(reuse=True, repeat=1, judge=rubric)
        self.assertEqual(summaries[0]["judge"]["sentence"], "ok")
        self.assertEqual(self.cli.call_args.kwargs["cwd"], self.sandbox / "runs" / "quickstart" / "head" / "1")

    def test_a_stop_while_judging_a_reused_run_leaves_it_marked_as_this_variants(self):
        self.record("main", 1, self.key(), int(time.time()))
        rubric = self.sandbox / "rubric.md"
        rubric.write_text("rubric")
        self.judged = "garbage"
        args = mock.Mock(repeat=1, model="haiku", budget=1.0, judge=rubric, check=True, reuse=True)
        with mock.patch.object(run, "write_settings"), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            run.run_variant(args, self.scenario, self.sandbox, self.plugin, "head")
        left = self.sandbox / "runs" / "quickstart" / "head" / "1" / "summary.json"
        if left.exists():
            summary = json.loads(left.read_text())
            self.assertEqual((summary["variant"], summary["run"], summary.get("reused")), ("head", 1, True))
            self.assertNotIn("check", summary)
            self.assertNotIn("judge", summary)

    def test_each_fresh_run_is_keyed_after_its_own_reset(self):
        remote = self.sandbox / "remotes" / "gizmos.git"

        def moves_main(sandbox, scenario, plugin, out, env):
            tree = git(remote, "rev-parse", "main^{tree}")
            moved = subprocess.run(["git", "-C", str(remote), "-c", "user.name=t", "-c", "user.email=t@t", "commit-tree", tree,
                                    "-p", "main", "-m", "pushed"], check=True, capture_output=True, text=True).stdout.strip()
            git(remote, "update-ref", "refs/heads/main", moved)
            git(sandbox / "repos" / "gizmos", "fetch", "-q", "origin", "main")
            return made_run(sandbox, scenario, plugin, out, env)

        summaries, _, _ = self.run_variant(reuse=False, repeat=2, once=moves_main)
        self.assertNotEqual(summaries[0]["key"], summaries[1]["key"])

    def test_a_reset_points_origin_back_at_the_url_the_sandbox_was_built_with(self):
        repo = self.sandbox / "repos" / "gizmos"
        built = git(repo, "remote", "get-url", "origin")
        git(repo, "config", "sandbox.fetch", built)
        git(repo, "remote", "set-url", "origin", "https://github.com/someone/gizmos.git")
        run.reset(self.sandbox)
        self.assertEqual(git(repo, "remote", "get-url", "origin"), built)

    def conflicting_branches(self) -> Path:
        """The pinned clone with `main` and `side` each changing f.txt's one line, `side` checked out."""
        repo = self.sandbox / "repos" / "gizmos"
        commit = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "-am"]
        (repo / "f.txt").write_text("a\n")
        git(repo, "add", "f.txt")
        git(repo, *commit, "base")
        git(repo, "switch", "-q", "-c", "side")
        (repo / "f.txt").write_text("side\n")
        git(repo, *commit, "side")
        git(repo, "switch", "-q", "main")
        (repo / "f.txt").write_text("main\n")
        git(repo, *commit, "main")
        git(repo, "switch", "-q", "side")
        return repo

    def test_a_reset_leaves_no_rebase_a_run_left_paused(self):
        repo = self.conflicting_branches()
        paused = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "rebase", "main"], capture_output=True)
        self.assertNotEqual(paused.returncode, 0)
        rebase_dir = repo / git(repo, "rev-parse", "--git-path", "rebase-merge")
        self.assertTrue(rebase_dir.is_dir())
        run.reset(self.sandbox)
        self.assertFalse(rebase_dir.exists())

    def test_a_reset_leaves_no_merge_a_run_left_paused(self):
        repo = self.conflicting_branches()
        paused = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "merge", "main"], capture_output=True)
        self.assertNotEqual(paused.returncode, 0)
        merge_head = repo / git(repo, "rev-parse", "--git-path", "MERGE_HEAD")
        self.assertTrue(merge_head.is_file())
        run.reset(self.sandbox)
        self.assertFalse(merge_head.exists())

    def test_a_pinned_plugin_clone_a_run_left_untracked_files_in_is_keyed_after_its_reset(self):
        remote = self.sandbox / "remotes" / "dev-tools.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(self.plugin), str(remote)], check=True)
        clone = self.sandbox / "repos" / "dev-tools"
        subprocess.run(["git", "clone", "-q", str(remote), str(clone)], check=True)
        with (self.sandbox / "pins").open("a") as pins:
            pins.write(f"dev-tools {git(clone, 'rev-parse', 'HEAD')} main\n")

        def leaves_a_file(sandbox, scenario, plugin, out, env):
            (plugin / "left.md").write_text("a run's leftover")
            return made_run(sandbox, scenario, plugin, out, env)

        (clone / "left.md").write_text("an earlier call's leftover")
        summaries, _, _ = self.run_variant(reuse=False, repeat=2, once=leaves_a_file, plugin=clone)
        self.assertIsNotNone(summaries[0]["key"])
        self.assertEqual(summaries[1]["key"], summaries[0]["key"])
        self.assertEqual([s["plugin"] for s in summaries], [git(clone, "rev-parse", "HEAD")] * 2)

    def test_a_variant_run_again_with_reuse_takes_its_own_earlier_runs(self):
        self.run_variant(reuse=False, repeat=2)
        summaries, once, _ = self.run_variant(reuse=True, repeat=3)
        self.assertEqual(once.call_count, 1)
        self.assertEqual(len({s["run_id"] for s in summaries}), 3)

    def test_without_reuse_every_run_is_made_and_still_recorded_with_its_key(self):
        key, now = self.key(), int(time.time())
        self.record("main", 1, key, now - 100)
        summaries, once, said = self.run_variant(reuse=False)
        self.assertEqual(once.call_count, 3)
        self.assertNotIn("reused", said)
        self.assertEqual([s["key"] for s in summaries], [key] * 3)

    def test_reuse_on_a_plugin_with_uncommitted_changes_makes_every_run_and_says_why(self):
        self.record("main", 1, self.key(), int(time.time()))
        (self.plugin / "skill.md").write_text("uncommitted")
        summaries, once, said = self.run_variant(reuse=True)
        self.assertEqual(once.call_count, 3)
        self.assertIn("has uncommitted changes, so no run is reused", said)
        self.assertEqual([s["key"] for s in summaries], [None] * 3)

    def test_the_judge_is_not_told_the_run_id_or_key(self):
        summary = {"final": "x", "variant": "head", "plugin": "abc", "run_id": "quickstart/head/1/1", "key": {"plugin": "t"},
                   "reused": True, "taken": 1792600000, "cost_usd": 0.1}
        run_dir = self.sandbox / "judged"
        run_dir.mkdir()
        (run_dir / "final.md").write_text("done")
        self.cli.side_effect = lambda cmd, **kw: mock.Mock(stdout=json.dumps({"result": '{"score": 7, "sentence": "ok"}'}), stderr="")
        run.judge("rubric", summary, run_dir, self.sandbox)
        prompt = self.cli.call_args.args[0][2]
        for hidden in ("quickstart/head/1/1", '"key"', '"reused"', '"taken"', "abc"):
            self.assertNotIn(hidden, prompt)


class Widgets(unittest.TestCase):
    """fixture/make_widgets.sh, whose commits the generic pack's pins and run keys rest on."""

    MAIN, BRANCH = "9ab28e46900a3b31dd318196241258b87299102f", "fb66716b6acfea908d3598ba7d765e314fe63833"

    def build(self, env: dict) -> Path:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        subprocess.run(["bash", str(ROOT / "sandbox" / "fixture" / "make_widgets.sh"), str(tmp / "widgets")],
                       check=True, capture_output=True, stdin=subprocess.DEVNULL, env={**os.environ, **env})
        return tmp / "widgets"

    def test_every_build_has_the_same_commits_whatever_the_persons_git_setup(self):
        hostile = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, hostile)
        (hostile / "git").mkdir()
        (hostile / "git" / "ignore").write_text("README.md\n")
        (hostile / "git" / "attributes").write_text("* text eol=crlf\n")
        (hostile / "gitconfig").write_text("[user]\n\tname = someone\n[core]\n\tautocrlf = true\n")
        for env in ({}, {"XDG_CONFIG_HOME": str(hostile), "GIT_CONFIG_GLOBAL": str(hostile / "gitconfig")}):
            with self.subTest(env=sorted(env)):
                repo = self.build(env)
                self.assertEqual(git(repo, "rev-parse", "main", "PROJ-42-csv-loader").split(), [self.MAIN, self.BRANCH])
                self.assertIn("README.md", git(repo, "ls-files").split())

    def test_it_refuses_a_directory_that_exists(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        done = subprocess.run(["bash", str(ROOT / "sandbox" / "fixture" / "make_widgets.sh"), str(tmp)],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(done.returncode, 1)
        self.assertIn("exists", done.stderr)
        self.assertEqual(list(tmp.iterdir()), [])


class SandboxScript(unittest.TestCase):
    """sandbox.sh on throwaway clones: what each clone fetches from and pushes to, and its refusals."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.seed = self.tmp / "widgets"
        self.seed.mkdir()
        git(self.seed, "init", "-q", "-b", "main")
        git(self.seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "seed")

    def build(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(ROOT / "sandbox" / "sandbox.sh"), str(self.tmp / "sbx"), "--plugin-ref", "HEAD", *args],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def test_each_repo_fetches_from_the_owner_and_pushes_to_its_bare_copy(self):
        done = self.build("--owner", "acme", "--repo", f"widgets={self.seed}@main")
        self.assertEqual(done.returncode, 0, done.stderr)
        clone = self.tmp / "sbx" / "repos" / "widgets"
        self.assertEqual(git(clone, "remote", "get-url", "origin"), "https://github.com/acme/widgets.git")
        self.assertEqual(git(clone, "config", "sandbox.fetch"), "https://github.com/acme/widgets.git")
        self.assertEqual(Path(git(clone, "remote", "get-url", "--push", "origin")).resolve(),
                         (self.tmp / "sbx" / "remotes" / "widgets.git").resolve())
        pins = (self.tmp / "sbx" / "pins").read_text().splitlines()
        self.assertEqual([line.split()[0] for line in pins], ["dev-tools", "widgets"])
        self.assertEqual(pins[1].split()[1:], [git(self.seed, "rev-parse", "HEAD"), "main"])

    def test_a_detached_source_pins_the_branch_at_its_commit(self):
        git(self.seed, "checkout", "-q", "--detach")
        done = self.build("--owner", "acme", "--repo", f"widgets={self.seed}@HEAD")
        self.assertEqual(done.returncode, 0, done.stderr)
        pins = (self.tmp / "sbx" / "pins").read_text().splitlines()
        self.assertEqual(pins[1].split()[1:], [git(self.seed, "rev-parse", "HEAD"), "main"])

    def test_it_refuses_a_build_with_no_owner_no_repo_or_a_venv_it_does_not_clone(self):
        for args, said in ((["--repo", f"widgets={self.seed}@main"], "usage"),
                           (["--owner", "acme"], "usage"),
                           (["--owner", "acme", "--repo", f"widgets={self.seed}"], "is not <name>=<path>@<ref>"),
                           (["--owner", "acme", "--repo", f"={self.seed}@main"], "is not <name>=<path>@<ref>"),
                           (["--owner", "acme", "--repo", f"widgets={self.seed}@main", "--repo", f"widgets={self.seed}@main"], "given twice"),
                           (["--owner", "acme", "--repo", f"dev-tools={self.seed}@main"], "the plugin's clone"),
                           (["--owner", "acme", "--repo", f"widgets={self.seed}@main", "--venv", "dev-tools"], "not a --repo name"),
                           (["--owner", "acme", "--repo", f"widgets={self.seed}@main", "--venv", "gadgets"], "not a --repo name")):
            with self.subTest(args=args):
                done = self.build(*args)
                self.assertEqual(done.returncode, 2)
                self.assertIn(said, done.stderr)
                self.assertFalse((self.tmp / "sbx").exists(), "a refused build writes nothing")
        for repo, said in ((f"widgets={self.tmp / 'absent'}@main", "no git clone at"),
                           (f"widgets={self.seed}@nosuch", "nosuch is not a commit")):
            with self.subTest(repo=repo):
                done = self.build("--owner", "acme", "--repo", repo)
                self.assertEqual(done.returncode, 1)
                self.assertIn(said, done.stderr)
                self.assertFalse((self.tmp / "sbx").exists(), "a refused build writes nothing")


@unittest.skipIf(rule_cases is None, "sandbox/rule_cases.py needs PyYAML")
class RuleCases(unittest.TestCase):
    def test_the_cases_are_well_formed_and_the_rule_is_found(self):
        import yaml
        cases = yaml.safe_load((ROOT / "sandbox" / "rule_cases.yaml").read_text())["cases"]
        self.assertEqual(len({c["id"] for c in cases}), len(cases))
        for c in cases:
            self.assertIn(c["expect"], ("stop", "read", "either"), c["id"])
            self.assertTrue(c["item"].strip(), c["id"])
        rule = rule_cases.rule_text()
        self.assertTrue(rule.startswith("## Controlled content"))
        self.assertNotIn("\n## ", rule)

    def test_warn_and_ask_stop_read_reads_and_anything_else_misses(self):
        self.assertEqual(rule_cases.verdict("**WARN** — a banner"), "WARN")
        self.assertEqual(rule_cases.verdict("Ask: unclear"), "ASK")
        self.assertEqual(rule_cases.verdict(""), "(empty)")
        self.assertTrue(rule_cases.holds("stop", "WARN") and rule_cases.holds("stop", "ASK"))
        self.assertFalse(rule_cases.holds("stop", "READ"))
        self.assertTrue(rule_cases.holds("read", "READ"))
        self.assertFalse(rule_cases.holds("read", "ASK"))
        self.assertTrue(rule_cases.holds("either", "READ") and rule_cases.holds("either", "WARN"))
        self.assertFalse(rule_cases.holds("either", "MAYBE"))
