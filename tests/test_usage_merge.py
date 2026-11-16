"""Tests for scripts/usage_merge.py. Run with `python3 -m unittest discover -s tests`."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("usage_merge", ROOT / "scripts" / "usage_merge.py")
merge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(merge)
_spec = importlib.util.spec_from_file_location("test_usage_report", ROOT / "tests" / "test_usage_report.py")
writer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(writer)


def report(start="2026-10-01T00:00:00Z", end="2026-10-31T00:00:00Z", **changes) -> dict:
    """A filled report as usage_report.py writes it, every field holding a value."""
    r = {
        "schema": 1, "plugin_commit": "abcdef012345", "claude_code_versions": ["2.1.300", "2.1.301"], "models": ["claude-opus-5-5"],
        "window": {"start": start, "end": end}, "repos": {"with_plugin_use": 2, "with_standard": 1}, "sessions": 10, "turns": 50,
        "skills": {"work": {"runs": 4, "typed": 3, "model_triggered": 1, "reruns": 1, "turns": {"median": 3, "p90": 8},
                            "tokens": {"median": 1000, "p90": 5000}}},
        "questions": {"work": {"Next step": {"recommended": 2, "free_text": 1, "free_text_median_chars": 40}}},
        "scripts": {"next_phase": {"runs": 5, "exits": {"0": 4, "1": 1}}},
        "hooks": {"issue-gate": {"runs": 3, "allow": 2, "ask": 1}},
        "denials": {"Bash": {"Git Destructive": 1}},
        "chains": {"transitions": {"work -> commit": 2}, "push_after": {"work": 1}, "pr_open_after": {}},
        "after_run": {"work": {"approve": 3, "none": 1}},
        "agents": {"test-runner": {"runs": 2, "models": {"claude-sonnet-5-5": 2}, "tokens": {"median": 300, "p90": 900}}},
        "overlap": {"skills": {"pr-review": 1}, "agents": {}},
        "notes": None,
    }
    r.update(changes)
    return r


def text(r: dict) -> str:
    return json.dumps(r, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def body(r: dict, digest: "str | None" = None) -> str:
    t = text(r)
    return f"```json\n{t}```\n`sha256:{digest or hashlib.sha256(t.encode()).hexdigest()}`\nFiled with /lasp-dev:usage-report.\n"


class Merge(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.out = self.tmp / "merged.json"

    def put(self, name: str, content: str) -> str:
        (self.tmp / name).write_text(content, encoding="utf-8")
        return str(self.tmp / name)

    def run_merge(self, *reports: tuple[str, str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        argv = ["--out", str(self.out)] + [x for author, path in reports for x in ("--report", author, path)]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = merge.main(argv)
        return code, out.getvalue(), err.getvalue()

    def merged(self, *reports: tuple[str, str]) -> dict:
        code, _, err = self.run_merge(*reports)
        self.assertEqual(code, 0, err)
        return json.loads(self.out.read_text())

    def two(self) -> dict:
        second = report("2026-11-01T00:00:00Z", "2026-11-10T00:00:00Z", plugin_commit="0123456789ab", claude_code_versions=["2.1.301"],
                        models=["claude-opus-5-5", "claude-sonnet-5-5"], repos={"with_plugin_use": 1, "not_a_repository": 1},
                        sessions=5, turns=20, notes="the gates ask too often")
        second["skills"] = {"work": {"runs": 6, "typed": 6, "turns": {"median": 5, "p90": 12}, "tokens": {"median": 2000, "p90": 9000}},
                            "commit": {"runs": 1, "typed": 1, "turns": {"median": 1, "p90": 1}, "tokens": {"median": 10, "p90": 10}}}
        second["questions"] = {"work": {"Next step": {"recommended": 1, "declined": 1}, "Which issue": {"free_text": 3, "free_text_median_chars": 12}}}
        second["scripts"] = {"next_phase": {"runs": 2, "exits": {"0": 1, "background": 1}}}
        second["hooks"] = {"issue-gate": {"runs": 1, "deny": 1}}
        second["denials"] = {"Bash": {"Git Destructive": 2, "user_rejected": 1}}
        second["chains"] = {"transitions": {"work -> commit": 1}, "push_after": {}, "pr_open_after": {"work": 1}}
        second["after_run"] = {"work": {"approve": 1, "correct": 2}}
        second["agents"] = {"test-runner": {"runs": 1, "models": {"claude-haiku-5-5": 1}, "tokens": {"median": 700, "p90": 700}, "unfinished": 1}}
        second["overlap"] = {"skills": {"pr-review": 2}, "agents": {"test-runner": 1}}
        return self.merged(("bob", self.put("b.json", text(second))), ("alice", self.put("a.md", body(report(notes="more examples")))))

    def test_counts_are_summed_and_the_list_fields_counted_per_report(self):
        m = self.two()
        self.assertEqual((m["schema"], m["report_schema"], m["reports"], m["authors"]), (1, 1, 2, 2))
        self.assertEqual(m["window"], {"start": "2026-10-01T00:00:00Z", "end": "2026-11-10T00:00:00Z"})
        self.assertEqual(m["plugin_commits"], {"0123456789ab": 1, "abcdef012345": 1})
        self.assertEqual(m["claude_code_versions"], {"2.1.300": 1, "2.1.301": 2})
        self.assertEqual(m["models"], {"claude-opus-5-5": 2, "claude-sonnet-5-5": 1})
        self.assertEqual(m["repos"], {"with_plugin_use": 3, "with_standard": 1, "not_a_repository": 1})
        self.assertEqual((m["sessions"], m["turns"]), (15, 70))
        self.assertEqual(m["scripts"], {"next_phase": {"runs": 7, "exits": {"0": 5, "1": 1, "background": 1}}})
        self.assertEqual(m["hooks"], {"issue-gate": {"runs": 4, "allow": 2, "ask": 1, "deny": 1}})
        self.assertEqual(m["denials"], {"Bash": {"Git Destructive": 3, "user_rejected": 1}})
        self.assertEqual(m["chains"], {"transitions": {"work -> commit": 3}, "push_after": {"work": 1}, "pr_open_after": {"work": 1}})
        self.assertEqual(m["after_run"], {"work": {"approve": 4, "correct": 2, "none": 1}})
        self.assertEqual(m["overlap"], {"skills": {"pr-review": 3}, "agents": {"test-runner": 1}})
        self.assertEqual(m["notes"], ["more examples", "the gates ask too often"])

    def test_medians_stay_per_report_beside_each_reports_runs(self):
        m = self.two()
        self.assertEqual(m["skills"]["work"], {"runs": 10, "typed": 9, "model_triggered": 1, "reruns": 1, "reports": 2,
                                               "turns": [[6, 5, 12], [4, 3, 8]], "tokens": [[6, 2000, 9000], [4, 1000, 5000]]})
        self.assertEqual(m["skills"]["commit"]["reports"], 1)
        self.assertEqual(m["agents"]["test-runner"], {"runs": 3, "reports": 2, "unfinished": 1,
                                                      "models": {"claude-haiku-5-5": 1, "claude-sonnet-5-5": 2},
                                                      "tokens": [[2, 300, 900], [1, 700, 700]]})
        self.assertEqual(m["questions"]["work"]["Next step"], {"recommended": 3, "free_text": 1, "declined": 1,
                                                               "free_text_median_chars": [[1, 40]]})
        self.assertEqual(m["questions"]["work"]["Which issue"], {"free_text": 3, "free_text_median_chars": [[3, 12]]})

    def test_no_author_or_path_reaches_the_result_and_the_summary_names_the_totals(self):
        code, out, _ = self.run_merge(("alice-login", self.put("first.md", body(report()))),
                                      ("bob-login", self.put("second.json", text(report("2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z")))))
        self.assertEqual(code, 0)
        written = self.out.read_text()
        for secret in ("alice-login", "bob-login", "first.md", "second.json", str(self.tmp)):
            self.assertNotIn(secret, written + out)
        self.assertTrue(out.startswith("Merged 2 reports from 2 authors, 2026-10-01 to 2026-11-02: 20 sessions, 100 turns, 8 plugin skill runs, 4 plugin agent runs."))
        self.assertIn("| work | 8 | 2 | 3 | 1k | approve 6, none 2 |", out)

    def test_the_summary_counts_one_session_and_one_turn_in_the_singular(self):
        _, out, _ = self.run_merge(("alice", self.put("one.json", text(report(sessions=1, turns=1)))))
        self.assertIn(": 1 session, 1 turn, ", out)

    def test_a_report_is_refused_by_name_and_nothing_is_written(self):
        bad = {
            "wrong digest": body(report(), "0" * 64),
            "edited after the digest": body(report()).replace('"sessions": 10', '"sessions": 11'),
            "no digest line": f"```json\n{text(report())}```\nFiled with /lasp-dev:usage-report.\n",
            "text after the footer": body(report()) + "and more\n",
            "not JSON": "{not json\n",
            "schema 2": text(report(schema=2)),
            "no schema": text({k: v for k, v in report().items() if k != "schema"}),
            "a field missing": text({k: v for k, v in report().items() if k != "hooks"}),
            "an extra field": text(report(author="alice")),
            "not filled": text(report(after_run=None)),
            "overlap not filled": text(report(overlap=None)),
            "a negative count": text(report(sessions=-1)),
            "a count that is text": text(report(turns="50")),
            "a boolean count": text(report(sessions=True)),
            "an unknown label": text(report(after_run={"work": {"liked": 1}})),
            "an unknown answer type": text(report(questions={"work": {"Next step": {"skipped": 1}}})),
            "a spread missing p90": text(report(skills={"work": {"runs": 1, "turns": {"median": 1}, "tokens": {"median": 1, "p90": 1}}})),
            "a window backwards": text(report("2026-11-01T00:00:00Z", "2026-10-01T00:00:00Z")),
            "a window not UTC": text(report("2026-10-01", "2026-10-31T00:00:00Z")),
            "a short commit": text(report(plugin_commit="abc")),
            "notes as a number": text(report(notes=3)),
            "a list": "[]\n",
            "a path that does not exist": None,
            "a script without exits": text(report(scripts={"next_phase": {"runs": 5}})),
            "an unknown hook outcome": text(report(hooks={"issue-gate": {"runs": 1, "blocked": 1}})),
            "chains missing a key": text(report(chains={"transitions": {}, "push_after": {}})),
            "overlap with an extra key": text(report(overlap={"skills": {}, "agents": {}, "hooks": {}})),
            "an agent with an extra key": text(report(agents={"test-runner": {"runs": 1, "models": {}, "tokens": {"median": 1, "p90": 1}, "cost": 1}})),
            "versions not a list": text(report(claude_code_versions="2.1.300")),
            "models not a list": text(report(models={"claude-opus-5-5": 1})),
            "a skill without tokens": text(report(skills={"work": {"runs": 1, "turns": {"median": 1, "p90": 1}}})),
        }
        for case, content in bad.items():
            with self.subTest(case):
                self.out.unlink(missing_ok=True)
                path = self.put("bad.md", content) if content is not None else str(self.tmp / "missing.md")
                code, _, err = self.run_merge(("alice", self.put("good.json", text(report()))), ("bob", path))
                self.assertEqual(code, 1, case)
                self.assertIn(f"usage_merge.py: {path}: ", err, case)
                self.assertNotIn("good.json", err, case)
                self.assertFalse(self.out.exists(), case)

    def test_an_author_with_a_space_exits_2(self):
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()) as err:
            merge.main(["--out", str(self.out), "--report", "alice smith", self.put("a.json", text(report()))])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("is empty or holds a space", err.getvalue())
        self.assertFalse(self.out.exists())

    def test_the_schema_and_digest_refusals_say_why(self):
        _, _, err = self.run_merge(("alice", self.put("two.json", text(report(schema=2)))))
        self.assertIn("its schema is 2; this script merges schema 1", err)
        _, _, err = self.run_merge(("alice", self.put("digest.md", body(report(), "0" * 64))))
        self.assertIn("its digest line says sha256:" + "0" * 64, err)
        _, _, err = self.run_merge(("alice", self.put("unfilled.json", text(report(after_run=None)))))
        self.assertIn("the report was not filled", err)

    def test_every_refusal_is_listed_in_one_run(self):
        a, b = self.put("a.json", text(report(schema=2))), self.put("b.md", body(report(), "1" * 64))
        code, _, err = self.run_merge(("alice", a), ("bob", b), ("carol", self.put("c.json", text(report()))))
        self.assertEqual(code, 1)
        self.assertEqual([line.split(": ")[1] for line in err.splitlines()[:2]], [a, b])
        self.assertIn("2 refused; nothing was written", err)

    def test_the_same_report_twice_is_refused_even_from_two_authors_or_two_forms(self):
        first = self.put("issue.md", body(report()))
        second = self.put("file.json", text(report()))
        code, _, err = self.run_merge(("alice", first), ("bob", second))
        self.assertEqual(code, 1)
        self.assertIn(f"{second}: the same report as {first}", err)
        self.assertFalse(self.out.exists())

    def test_one_authors_overlapping_windows_are_refused_and_adjacent_ones_merge(self):
        october = self.put("oct.json", text(report("2026-10-01T00:00:00Z", "2026-10-31T00:00:00Z")))
        overlapping = self.put("late-oct.json", text(report("2026-10-30T00:00:00Z", "2026-11-05T00:00:00Z")))
        code, _, err = self.run_merge(("alice", october), ("Alice", overlapping))
        self.assertEqual(code, 1)
        self.assertIn(f"{overlapping}: by the same author as {october}, with an overlapping window", err)
        self.assertEqual(self.merged(("alice", october), ("bob", overlapping))["authors"], 2)
        adjacent = self.put("nov.json", text(report("2026-10-31T00:00:00Z", "2026-11-05T00:00:00Z")))
        m = self.merged(("alice", october), ("ALICE", adjacent))
        self.assertEqual((m["reports"], m["authors"]), (2, 1))

    def test_a_body_may_have_blank_lines_between_its_parts_and_no_footer(self):
        t = text(report())
        digest = hashlib.sha256(t.encode()).hexdigest()
        for content in (f"```json\n{t}```\n\n`sha256:{digest}`\n\nFiled with /lasp-dev:usage-report.\n\n",
                        f"```json\n{t}```\n`sha256:{digest}`\n"):
            with self.subTest(content[-40:]):
                self.assertEqual(self.merged(("alice", self.put("x.md", content)))["reports"], 1)

    def test_a_report_in_a_payload_file_matches_the_same_report_in_a_body(self):
        r = report(notes="café")
        self.assertEqual(self.merged(("alice", self.put("x.md", body(r)))), self.merged(("alice", self.put("x.json", text(copy.deepcopy(r))))))


class WrittenReport(writer.Fixture):
    def test_a_report_usage_report_py_wrote_and_filled_merges(self):
        session = self.write(writer.busy_session())
        agent = writer.Transcript()
        agent.claude({"type": "text", "text": "x"}, request="ra", usage_={"input_tokens": 1000, "output_tokens": 0}, model="claude-haiku-5-5")
        self.write_agent(session, "x1", {"agentType": "lasp-dev:test-runner", "toolUseId": "a1", "finished": False}, agent)
        _, runs = self.ok()
        payload, pending = self.tmp / "out" / "payload.json", self.tmp / "out" / "pending.json"
        labels = ["none" if run["next_message"] is None else "approve" for run in runs]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(writer.usage.main(["--fill", str(payload), "--pending", str(pending), "--labels", *labels,
                                                "--plugin-root", str(self.plugin), "--overlap", "skill:work=1", "agent:test-runner=1"]), 0)
        out, err = self.tmp / "merged.json", io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = merge.main(["--out", str(out), "--report", "alice", str(payload)])
        self.assertEqual(code, 0, err.getvalue())
        m = json.loads(out.read_text())
        self.assertEqual((m["reports"], m["skills"]["work"]["reports"], m["agents"]["test-runner"]["reports"]), (1, 1, 1))
        self.assertEqual(m["overlap"], {"skills": {"work": 1}, "agents": {"test-runner": 1}})


if __name__ == "__main__":
    unittest.main()
