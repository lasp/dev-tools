"""Tests for scripts/guidance_tally.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("guidance_tally", ROOT / "scripts" / "guidance_tally.py")
guidance_tally = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guidance_tally)
FIXTURE = ROOT / "sandbox" / "harvest"
spec = importlib.util.spec_from_file_location("harvest_recall", ROOT / "sandbox" / "harvest_recall.py")
harvest_recall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harvest_recall)

BODY = "Fixed.\n\nIn general, import dependencies directly;   no guards."
COMMENT = {"pr": 7, "id": 12, "url": "u12", "author": "bob", "authorship": "human", "kind": "reply", "thread": "PRRT_a",
           "path": "x.py", "line": 5, "created": "2026-10-01T11:00:00Z", "body": BODY}
ITEM = {"pr": 7, "comment_id": 12, "url": "u12", "author": "bob", "authorship": "human",
        "quote": "In general, import dependencies directly; no guards.", "generality": "general",
        "signal": "states a principle", "kind": "rule", "principle": "Import directly.", "rationale": None,
        "covered_by": None, "outcome": "changed as asked"}


class Tally(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def tally(self, comments: list[dict], *items: dict) -> tuple[int, list[str]]:
        lists = self.dir / "pr-0007.json"
        lists.write_text(json.dumps({"pr": 7, "comments": comments}))
        found = self.dir / "slice-1.json"
        found.write_text(json.dumps({"prs": [7], "comments_read": len(comments), "items": list(items)}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = guidance_tally.main([str(found), "--comments", str(lists)])
        return code, out.getvalue().splitlines()

    def test_a_persons_signaled_statement_admits_and_the_rest_is_held_or_supports(self):
        agent = {**COMMENT, "id": 13, "url": "u13", "author": "alice", "authorship": "ai-drafted",
                 "body": "Should fix: check units here, and in general at the boundary."}
        bot = {**COMMENT, "id": 14, "url": "u14", "author": "copilot", "authorship": "bot", "body": "Always add types."}

        def on(c: dict, **kw) -> dict:
            return {**ITEM, "comment_id": c["id"], "url": c["url"], "author": c["author"], "authorship": c["authorship"], **kw}

        code, lines = self.tally(
            [COMMENT, agent, bot],
            ITEM,
            {**ITEM, "quote": "Fixed.", "generality": "pr-specific", "signal": "none"},
            {**ITEM, "quote": "no guards.", "covered_by": "R-002"},
            {**ITEM, "quote": "no guards.", "signal": "cites a source", "kind": "agent-guidance"},
            {**ITEM, "quote": "no guards.", "signal": "none"},
            {**ITEM, "quote": "no guards.", "kind": "data-convention"},
            on(agent, quote="in general at the boundary."),
            on(agent, quote="check units here", outcome="declined"),
            on(bot, quote="Always add types."),
            {**ITEM, "quote": "no guards.", "signal": "none", "kind": "tool-config"},
        )
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            "admit · s1-0 · pr-0007 · 12 · bob · rule · states a principle · u12 · "
            "In general, import dependencies directly; no guards.",
            "covered · s1-2 · pr-0007 · 12 · bob · rule · R-002 · u12 · no guards.",
            "hold · s1-3 · pr-0007 · 12 · bob · agent-guidance · signal cites a source, not one that admits · u12 · no guards.",
            "hold · s1-4 · pr-0007 · 12 · bob · rule · no signal of generality · u12 · no guards.",
            "admit · s1-5 · pr-0007 · 12 · bob · data-convention · states a principle · u12 · no guards.",
            "support · s1-6 · pr-0007 · 13 · alice · rule · u13 · in general at the boundary.",
            "admit · s1-9 · pr-0007 · 12 · bob · tool-config · none · u12 · no guards.",
            "items: 10 · admit: 3 · covered: 1 · hold: 2 · support: 1 · not listed: 3",
        ])

    def test_a_kind_whose_bar_reads_no_signal_admits_without_one(self):
        for kind in ("tool-config", "exemplar", "review-calibration", "open-question"):
            with self.subTest(kind=kind):
                code, lines = self.tally([COMMENT], {**ITEM, "quote": "no guards.", "signal": "none", "kind": kind})
                self.assertEqual((code, lines[0].split(" · ")[:1] + lines[0].split(" · ")[5:7]), (0, ["admit", kind, "none"]))
        self.assertTrue(self.tally([COMMENT], {**ITEM, "quote": "no guards.", "signal": "none", "kind": "process"})[1][0]
                        .startswith("hold · "))

    def test_a_data_convention_or_decision_that_cites_its_source_admits_and_a_rule_that_does_is_held(self):
        for kind, word in (("data-convention", "admit"), ("decision", "admit"), ("rule", "hold"), ("process", "hold")):
            with self.subTest(kind=kind):
                lines = self.tally([COMMENT], {**ITEM, "quote": "no guards.", "signal": "cites a source", "kind": kind})[1]
                self.assertTrue(lines[0].startswith(f"{word} · "), lines)

    def test_a_persons_ask_to_keep_a_point_admits_whatever_its_kind_and_an_agents_does_not(self):
        for kind in guidance_tally.load_check().KINDS:
            with self.subTest(kind=kind):
                lines = self.tally([COMMENT], {**ITEM, "quote": "no guards.", "signal": "asks for guidance", "kind": kind})[1]
                self.assertEqual(lines[0].split(" · ")[:1] + lines[0].split(" · ")[6:7], ["admit", "asks for guidance"])
        agent = {**COMMENT, "authorship": "ai-drafted"}
        lines = self.tally([agent], {**ITEM, "authorship": "ai-drafted", "quote": "no guards.", "signal": "asks for guidance",
                                     "outcome": "declined"})[1]
        self.assertTrue(lines[0].startswith("items: 1 · admit: 0"), lines)
        code, lines = self.tally([COMMENT], {**ITEM, "quote": "no guards.", "generality": "pr-specific", "signal": "asks for guidance"})
        self.assertEqual(code, 1)
        self.assertIn("a pr-specific item has signal 'asks for guidance'", lines[0])

    def test_refuses_a_run_the_guidance_check_refuses(self):
        code, lines = self.tally([COMMENT], {**ITEM, "quote": "never said"})
        self.assertEqual(code, 1)
        self.assertIn("the quote is not in the comment's own words", "\n".join(lines))


class Benchmark(unittest.TestCase):
    """On sandbox/harvest/, every labeled statement with a signal reaches the tally, every data
    convention and process statement admits as its own kind rather than held as a rule, and no
    negative admits."""

    def test_the_recorded_run(self):
        lists = sorted((FIXTURE / "comments").glob("pr-*.json"))
        comments = {c["id"]: c for p in lists for c in json.loads(p.read_text())["comments"]}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = guidance_tally.main([*map(str, sorted((FIXTURE / "runs").glob("*.json"))), "--comments", *map(str, lists)])
        self.assertEqual(code, 0)
        lines = [line.split(" · ") for line in out.getvalue().splitlines()[:-1]]
        labels = json.loads((FIXTURE / "labels.json").read_text())

        def read(label: dict) -> set[tuple[str, str]]:
            return {(cells[0], cells[5]) for cells in lines if int(cells[3]) == label["comment_id"] and harvest_recall.finds(
                {"comment_id": label["comment_id"], "quote": cells[-1]}, label, comments[label["comment_id"]]["body"])}

        def words(label: dict) -> set[str]:
            return {word for word, _ in read(label)}

        signaled = [i for i in labels["items"] if i["signal"] in guidance_tally.SIGNALS and not i.get("covered_by")]
        self.assertEqual([i["id"] for i in signaled if not words(i) & {"admit", "hold"}], [])
        self.assertEqual([i["id"] for i in labels["items"] if i.get("covered_by") and words(i) != {"covered"}], [])
        astray = {"L25", "L46"}  # tool-checkable asks the recorded run's extractor read as process and agent guidance
        for kind in ("data-convention", "process", "tool-config"):
            with self.subTest(kind=kind):
                labeled = {i["id"] for i in labels["items"] if i["kind"] == kind}
                routed = {i["id"] for i in labels["items"] if i["kind"] == kind and ("admit", kind) in read(i)}
                self.assertEqual(labeled - routed, labeled & astray)
        self.assertEqual([i["id"] for i in labels["items"] if "hold" in words(i) and i["signal"] in guidance_tally.SIGNALS], [])
        admitted = {int(cells[3]) for cells in lines if cells[0] == "admit"}
        self.assertEqual([n for n in labels["negatives"] if n in admitted], [])


if __name__ == "__main__":
    unittest.main()
