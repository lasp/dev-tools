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
REPORT = ("## harvest — o/r since 2026-10-01\nmerged: 3; records written: 1; labels unparsed: 2\n"
          "pr-0007 · created 2026-09-30 · merged 2026-10-02 · built · record · 2 label(s) unparsed\n"
          "pr-0008 · created 2026-09-30 · merged 2026-10-05 · not built · no review\n"
          "pr-0009 · created 2026-09-30 · merged 2026-10-06 · not built · no review\n")


def comment(pr: int, id_: int, body: str = BODY) -> dict:
    return {"pr": pr, "id": id_, "url": f"u{id_}", "author": "bob", "authorship": "human", "kind": "reply",
            "thread": "PRRT_a", "path": "x.py", "line": 5, "created": "2026-10-01T11:00:00Z", "body": body}


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
            for f in capture.DUMP:
                (dump / f).write_text("{}")
            (dump / "scratch.out").write_text("x")
            self.comments(pr, [comment(pr, pr * 10)])
        (self.threads / "pr-0009" / "comment-list.json").unlink()
        (self.log / "pr-0007.yaml").write_text("pr: 7\n")
        self.report = self.dir / "report.md"
        self.report.write_text(REPORT)
        self.slice = self.slice_of("slice-1.json", item(7, 70), item(8, 80))
        self.analysis = self.dir / "analysis"
        self.analysis.mkdir()
        for pr in (7, 9):
            (self.analysis / f"pr-{pr:04d}.md").write_text(f"## pr-{pr:04d}\n")

    def comments(self, pr: int, comments: list[dict]) -> None:
        (self.threads / f"pr-{pr:04d}" / "comment-list.json").write_text(json.dumps({"pr": pr, "comments": comments}))

    def slice_of(self, name: str, *items: dict, prs: tuple[int, ...] = ()) -> Path:
        path = self.dir / name
        prs = sorted(set(prs) | {it["pr"] for it in items})
        read = sum(len(json.loads((self.threads / f"pr-{n:04d}" / "comment-list.json").read_text())["comments"]) for n in prs)
        path.write_text(json.dumps({"prs": prs, "comments_read": read, "items": list(items)}))
        return path

    def run_capture(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = capture.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def pending(self) -> str:
        return self.run_capture("pending", "--log", str(self.log), "--threads", str(self.threads))[1]

    def store(self, *extra: str, start: str = "2026-10-01", through: str = "2026-10-07",
              slices: tuple[Path, ...] | None = None) -> tuple[int, str, str]:
        given = [str(p) for p in (slices if slices is not None else (self.slice,))]
        return self.run_capture("store", "--log", str(self.log), "--report", str(self.report), "--threads", str(self.threads),
                                "--from", start, "--through", through, *(["--slices", *given] if given else []),
                                "--analysis", str(self.analysis), *extra)

    def load(self, since: str = "2026-10-01", through: str = "2026-10-07", *extra: str) -> tuple[int, str, str]:
        return self.run_capture("load", "--log", str(self.log), "--since", since, "--through", through,
                                "--out", str(self.dir / "harvest"), "--guidance", str(self.dir / "harvest" / "guidance"), *extra)

    def test_store_files_each_pull_request_and_the_days_it_searched(self):
        self.assertEqual(self.pending(), "pr-0007\npr-0008\n")
        code, out, _ = self.store()
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["captured pr-0007 · items 1 · analysis", "captured pr-0008 · items 1",
                                            "captured pr-0009", "covered 2026-10-01..2026-10-07"])
        seven = self.log / "capture" / "pr-0007"
        self.assertEqual(sorted(p.name for p in seven.iterdir()),
                         sorted(["analysis.md", "comment-list.json", "harvest.txt", "items.json", *capture.DUMP]))
        self.assertEqual(json.loads((seven / "items.json").read_text()), {"prs": [7], "comments_read": 1, "items": [item(7, 70)]})
        self.assertFalse((self.log / "capture" / "pr-0009" / "analysis.md").exists())
        self.assertEqual((self.log / "capture" / "covered.txt").read_text(), "2026-10-01 2026-10-07\n")
        self.assertEqual(self.pending(), "\n")

    def test_a_later_capture_reads_only_what_changed_and_keeps_the_rest(self):
        self.store()
        self.comments(8, [comment(8, 80), comment(8, 81, "Agreed.")])
        (self.analysis / "pr-0007.md").write_text("## a block from another run\n")
        self.assertEqual(self.pending(), "pr-0008\n")
        code, out, _ = self.store(through="2026-10-09", slices=(self.slice_of("slice-2.json", prs=(8,)),))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[:2], ["captured pr-0007 · items kept 1 · analysis kept", "captured pr-0008 · items 0"])
        self.assertEqual((self.log / "capture" / "pr-0007" / "analysis.md").read_text(), "## pr-0007\n")
        self.assertEqual((self.log / "capture" / "covered.txt").read_text(), "2026-10-01 2026-10-07\n2026-10-01 2026-10-09\n")

    def test_a_pull_request_whose_slice_was_not_read_is_kept_without_items(self):
        code, out, _ = self.store("--not-read", "8", slices=(self.slice_of("seven.json", item(7, 70)),))
        self.assertEqual(code, 0, out)
        self.assertIn("captured pr-0008 · not read", out)
        self.assertFalse((self.log / "capture" / "pr-0008" / "items.json").exists())
        self.assertEqual(self.load()[1].splitlines()[-1], "not read · pr-0008")
        self.assertEqual(self.pending(), "pr-0008\n")

    def test_a_pull_request_read_before_and_not_read_now_drops_its_items_and_takes_its_new_block(self):
        self.store()
        self.comments(7, [comment(7, 70), comment(7, 71, "Agreed.")])
        (self.analysis / "pr-0007.md").write_text("## pr-0007, with the reply\n")
        code, out, _ = self.store("--not-read", "7", slices=())
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], "captured pr-0007 · not read · analysis")
        seven = self.log / "capture" / "pr-0007"
        self.assertFalse((seven / "items.json").exists())
        self.assertEqual((seven / "analysis.md").read_text(), "## pr-0007, with the reply\n")
        (self.analysis / "pr-0007.md").unlink()
        self.store("--not-read", "7", slices=())
        self.assertFalse((seven / "analysis.md").exists())

    def test_store_refuses_items_the_guidance_check_refuses_and_writes_nothing(self):
        code, out, _ = self.store(slices=(self.slice_of("seven.json", item(7, 70)),))
        self.assertEqual(code, 1)
        self.assertIn("pr 8 · in no slice", out)
        self.assertFalse((self.log / "capture").exists())
        code, out, _ = self.store(slices=())
        self.assertEqual(code, 1)
        self.assertIn("refused · --slices · none given for pr-0007, pr-0008", out)

    def test_store_refuses_a_report_it_cannot_read(self):
        for report, why in ((REPORT.replace("merged: 3;", "merged: 4;"), "says 4 merged and it lists 3"),
                            (REPORT.replace("merged: 3; records written: 1; labels unparsed: 2\n", ""), "no `merged: <n>"),
                            (REPORT.replace("pr-0008 · created", "pr-8 · created"), "a report line not"),
                            (REPORT.replace("merged 2026-10-05", "merged 2026-10-05T10:00:00Z"), "a report line not"),
                            (REPORT.replace("merged: 3", "merged: 4") + REPORT.splitlines()[2] + "\n", "names pr-0007 twice")):
            with self.subTest(why=why):
                self.report.write_text(report)
                code, _, err = self.store()
                self.assertEqual(code, 1)
                self.assertIn(why, err)
                self.assertFalse((self.log / "capture").exists())

    def test_store_refuses_inputs_it_cannot_read(self):
        for extra, why in ((dict(start="2026-10-08"), "is after --through"), (dict(start="10/01"), "is not a day")):
            with self.subTest(why=why):
                code, _, err = self.store(**extra)
                self.assertEqual(code, 1)
                self.assertIn(why, err)
        shutil.rmtree(self.log)
        self.assertIn("is not a directory", self.store()[2])

    def test_load_restores_the_window_and_prints_the_harvest_block(self):
        self.store()
        code, out, _ = self.load("2026-10-03")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[1:], [
            "merged: 2; records written: 0; labels unparsed: 0",
            "pr-0008 · created 2026-09-30 · merged 2026-10-05 · not built · no review",
            "pr-0009 · created 2026-09-30 · merged 2026-10-06 · not built · no review"])
        code, out, _ = self.load()
        self.assertEqual(out.splitlines()[1], "merged: 3; records written: 1; labels unparsed: 2")
        harvest = self.dir / "harvest"
        self.assertEqual(sorted(p.name for p in (harvest / "threads" / "pr-0007").iterdir()),
                         sorted([*capture.DUMP, "comment-list.json"]))
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

    def test_load_reads_overlapping_and_gapped_spans(self):
        self.store(start="2026-10-01", through="2026-10-04")
        self.store(start="2026-10-03", through="2026-10-05", slices=())
        self.store(start="2026-10-07", through="2026-10-07", slices=())
        code, out, _ = self.load("2026-10-01", "2026-10-08")
        self.assertEqual((code, out.splitlines()), (2, ["uncovered · 2026-10-06 · 2026-10-06", "uncovered · 2026-10-08 · 2026-10-08"]))
        self.assertEqual(self.load("2026-10-02", "2026-10-05")[0], 0)

    def test_load_refuses_days_and_merges_not_captured_and_writes_nothing(self):
        self.store(start="2026-10-03", through="2026-10-07")
        merges = self.dir / "merges.txt"
        merges.write_text(f"pr-0011 {'a' * 40} 2026-10-07 x.py\npr-0012 {'b' * 40} 2026-10-20 x.py\n"
                          f"pr-0008 {'c' * 40} 2026-10-04 x.py\n")
        code, out, _ = self.load("2026-10-01", "2026-10-09", "--merges", str(merges))
        self.assertEqual(code, 2)
        self.assertEqual(out.splitlines(), ["uncovered · 2026-10-01 · 2026-10-02", "uncovered · 2026-10-08 · 2026-10-09",
                                            "uncaptured · pr-0011 · 2026-10-07"])
        self.assertFalse((self.dir / "harvest").exists())
        merges.write_text(f"pr-0007 {'d' * 40} 2026-10-04 x.py\n")
        self.assertEqual(self.load("2026-10-03", "2026-10-07", "--merges", str(merges))[0], 0)

    def test_load_refuses_a_capture_with_no_record_or_a_failed_fetch(self):
        self.report.write_text(REPORT.replace("merged 2026-10-06 · not built · no review", "merged 2026-10-06 · get failed: 502"))
        (self.log / "pr-0007.yaml").unlink()
        self.store()
        self.assertEqual(self.load()[1].splitlines(), ["missing · pr-0007 · 2026-10-02", "failed · pr-0009 · 2026-10-06"])

    def test_a_log_not_yet_made_holds_no_capture(self):
        shutil.rmtree(self.log)
        merges = self.dir / "merges.txt"
        merges.write_text(f"pr-0008 {'c' * 40} 2026-10-05 x.py\n")
        code, out, _ = self.load("2026-10-01", "2026-10-09", "--merges", str(merges))
        self.assertEqual((code, out.splitlines()), (2, ["uncovered · 2026-10-01 · 2026-10-09", "uncaptured · pr-0008 · 2026-10-05"]))

    def test_load_refuses_inputs_it_cannot_read(self):
        self.store()
        for since, through, why in (("2026-10-08", "2026-10-07", "is after --through"), ("10/01", "2026-10-07", "is not a day")):
            with self.subTest(why=why):
                code, _, err = self.load(since, through)
                self.assertEqual(code, 1)
                self.assertIn(why, err)
        (self.log / "capture" / "covered.txt").write_text("2026-10-01\n")
        self.assertIn("is not `<from> <through>`", self.load()[2])
        (self.log / "capture" / "covered.txt").write_text("2026-10-01 2026-10-07\n")
        (self.log / "capture" / "pr-0008" / "harvest.txt").write_text("pr-0008\n")
        code, _, err = self.load()
        self.assertEqual(code, 1)
        self.assertIn("is not a harvest report line", err)


if __name__ == "__main__":
    unittest.main()
