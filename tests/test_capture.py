"""Tests for scripts/capture.py."""

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
spec = importlib.util.spec_from_file_location("capture", ROOT / "scripts" / "capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)

BODY = "In general, import dependencies directly; no guards."


def comment(pr: int, id_: int) -> dict:
    return {"pr": pr, "id": id_, "url": f"u{id_}", "author": "bob", "authorship": "human", "kind": "reply",
            "thread": "PRRT_a", "path": "x.py", "line": 5, "created": "2026-10-01T11:00:00Z", "body": BODY}


def item(pr: int, id_: int) -> dict:
    return {"pr": pr, "comment_id": id_, "url": f"u{id_}", "author": "bob", "authorship": "human", "quote": BODY,
            "generality": "general", "signal": "states a principle", "kind": "rule", "principle": "Import directly.",
            "rationale": None, "covered_by": None, "outcome": "changed as asked"}


class Capture(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.log = self.dir / "log"
        self.log.mkdir()
        self.threads = self.dir / "threads"
        for pr in (7, 8, 9):
            dump = self.threads / f"pr-{pr:04d}"
            dump.mkdir(parents=True)
            (dump / "pr.json").write_text(json.dumps({"number": pr, "created_at": "2026-09-30T00:00:00Z"}))
            (dump / "comment-list.json").write_text(json.dumps({"pr": pr, "comments": [comment(pr, pr * 10)]}))
        (self.threads / "pr-0009" / "comment-list.json").unlink()
        (self.log / "pr-0007.yaml").write_text("pr: 7\n")
        self.report = self.dir / "report.md"
        self.report.write_text("## harvest — o/r since 2026-10-01\nmerged: 3; records written: 1; labels unparsed: 2\n"
                               "pr-0007 · created 2026-09-30 · merged 2026-10-02 · built · record · 2 label(s) unparsed\n"
                               "pr-0008 · created 2026-09-30 · merged 2026-10-05 · not built · no review\n"
                               "pr-0009 · created 2026-09-30 · merged 2026-10-06 · not built · get failed: 502\n")
        self.slice = self.dir / "slice-1.json"
        self.slice.write_text(json.dumps({"prs": [7, 8], "comments_read": 2, "items": [item(7, 70), item(8, 80)]}))
        self.analysis = self.dir / "analysis"
        self.analysis.mkdir()
        (self.analysis / "pr-0007.md").write_text("## pr-0007\n")

    def run_capture(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = capture.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def store(self, *extra: str, start: str = "2026-10-01", through: str = "2026-10-07") -> tuple[int, str, str]:
        return self.run_capture("store", "--log", str(self.log), "--report", str(self.report), "--threads", str(self.threads),
                                "--from", start, "--through", through, "--slices", str(self.slice),
                                "--analysis", str(self.analysis), *extra)

    def load(self, since: str = "2026-10-01", through: str = "2026-10-07", *extra: str) -> tuple[int, str, str]:
        return self.run_capture("load", "--log", str(self.log), "--since", since, "--through", through,
                                "--out", str(self.dir / "harvest"), "--guidance", str(self.dir / "harvest" / "guidance"), *extra)

    def test_store_files_each_pull_request_and_the_days_it_searched(self):
        code, out, _ = self.store()
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["captured pr-0007 · items 1 · analysis", "captured pr-0008 · items 1",
                                            "captured pr-0009", "covered 2026-10-01..2026-10-07"])
        seven = self.log / "capture" / "pr-0007"
        self.assertEqual(sorted(p.name for p in seven.iterdir()),
                         ["analysis.md", "comment-list.json", "harvest.txt", "items.json", "pr.json"])
        self.assertEqual(json.loads((seven / "items.json").read_text()), {"prs": [7], "comments_read": 1, "items": [item(7, 70)]})
        self.assertEqual(sorted(p.name for p in (self.log / "capture" / "pr-0009").iterdir()), ["harvest.txt", "pr.json"])
        self.assertEqual((self.log / "capture" / "covered.txt").read_text(), "2026-10-01 2026-10-07\n")

    def test_storing_again_replaces_a_pull_requests_capture_whole(self):
        self.store()
        (self.log / "capture" / "pr-0007" / "stale.txt").write_text("x")
        self.slice.write_text(json.dumps({"prs": [7, 8], "comments_read": 2, "items": [item(8, 80)]}))
        self.assertEqual(self.store(start="2026-10-07", through="2026-10-08")[0], 0)
        seven = self.log / "capture" / "pr-0007"
        self.assertFalse((seven / "stale.txt").exists())
        self.assertEqual(json.loads((seven / "items.json").read_text())["items"], [])
        self.assertEqual((self.log / "capture" / "covered.txt").read_text(), "2026-10-01 2026-10-07\n2026-10-07 2026-10-08\n")

    def test_store_refuses_items_the_guidance_check_refuses_and_writes_nothing(self):
        self.slice.write_text(json.dumps({"prs": [7], "comments_read": 1, "items": [item(7, 70)]}))
        code, out, _ = self.store()
        self.assertEqual(code, 1)
        self.assertIn("pr 8 · in no slice", out)
        self.assertFalse((self.log / "capture").exists())
        code, _, err = self.run_capture("store", "--log", str(self.log), "--report", str(self.report), "--threads",
                                        str(self.threads), "--from", "2026-10-01", "--through", "2026-10-07")
        self.assertEqual(code, 1)
        self.assertIn("no --slices", err)

    def test_store_refuses_inputs_it_cannot_read(self):
        for extra, why in ((dict(start="2026-10-08"), "is after --through"), (dict(start="10/01"), "is not a day")):
            with self.subTest(why=why):
                code, _, err = self.store(**extra)
                self.assertEqual(code, 1)
                self.assertIn(why, err)
        self.report.write_text(self.report.read_text() + "pr-0007 · created 2026-09-30 · merged 2026-10-02 · no review\n")
        self.assertIn("names pr-0007 twice", self.store()[2])
        shutil.rmtree(self.log)
        self.assertIn("is not a directory", self.store()[2])

    def test_load_restores_the_window_and_prints_the_harvest_block(self):
        self.store()
        code, out, _ = self.load("2026-10-03")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[1:], [
            "merged: 2; records written: 0; labels unparsed: 0",
            "pr-0008 · created 2026-09-30 · merged 2026-10-05 · not built · no review",
            "pr-0009 · created 2026-09-30 · merged 2026-10-06 · not built · get failed: 502"])
        code, out, _ = self.load()
        self.assertEqual(out.splitlines()[1], "merged: 3; records written: 1; labels unparsed: 2")
        harvest = self.dir / "harvest"
        self.assertEqual(sorted(p.name for p in (harvest / "threads").iterdir()), ["pr-0007", "pr-0008", "pr-0009"])
        self.assertEqual([p.name for p in (harvest / "records").iterdir()], ["pr-0007.yaml"])
        self.assertEqual([p.name for p in (harvest / "analysis").iterdir()], ["pr-0007.md"])
        self.assertEqual(sorted(p.name for p in (harvest / "guidance").iterdir()), ["slice-1.json", "slice-2.json"])
        self.assertEqual(json.loads((harvest / "guidance" / "slice-2.json").read_text())["prs"], [8])

    def test_load_empties_what_an_earlier_harvest_left(self):
        self.store()
        stale = self.dir / "harvest" / "threads" / "pr-0001"
        stale.mkdir(parents=True)
        (self.dir / "harvest" / "guidance").mkdir()
        (self.dir / "harvest" / "guidance" / "slice-9.json").write_text("{}")
        self.assertEqual(self.load()[0], 0)
        self.assertFalse(stale.exists())
        self.assertFalse((self.dir / "harvest" / "guidance" / "slice-9.json").exists())

    def test_load_refuses_days_and_merges_not_captured_and_writes_nothing(self):
        self.store(start="2026-10-03", through="2026-10-04")
        self.store(start="2026-10-06", through="2026-10-07")
        merges = self.dir / "merges.txt"
        merges.write_text(f"pr-0011 {'a' * 40} 2026-10-07 x.py\npr-0012 {'b' * 40} 2026-10-20 x.py\n"
                          f"pr-0008 {'c' * 40} 2026-10-05 x.py\n")
        code, out, _ = self.load("2026-10-01", "2026-10-09", "--merges", str(merges))
        self.assertEqual(code, 2)
        self.assertEqual(out.splitlines(), ["uncovered · 2026-10-01 · 2026-10-02", "uncovered · 2026-10-05 · 2026-10-05",
                                            "uncovered · 2026-10-08 · 2026-10-09", "uncaptured · pr-0011"])
        self.assertFalse((self.dir / "harvest").exists())
        (self.log / "pr-0007.yaml").unlink()
        self.store()
        self.assertEqual(self.load()[1].splitlines(), ["missing · pr-0007 · record"])

    def test_load_refuses_a_capture_it_cannot_read(self):
        self.store()
        (self.log / "capture" / "covered.txt").write_text("2026-10-01\n")
        self.assertIn("is not `<from> <through>`", self.load()[2])
        (self.log / "capture" / "covered.txt").write_text("2026-10-01 2026-10-07\n")
        (self.log / "capture" / "pr-0008" / "harvest.txt").write_text("pr-0008\n")
        code, _, err = self.load()
        self.assertEqual(code, 1)
        self.assertIn("is not a harvest report line", err)


if __name__ == "__main__":
    unittest.main()
