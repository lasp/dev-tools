"""Tests for scripts/block_tally.py. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("block_tally", ROOT / "scripts" / "block_tally.py")
block_tally = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(block_tally)

ANALYSIS_7 = """## pr-0007 — threads read
thread PRRT_a1 · alice · by: human · correctness · asked: check the path where it enters · outcome: changed as asked · diff: addresses it
thread PRRT_a2 · bob · by: human · correctness · asked: raise on an empty table · outcome: declined: "the caller · checks it" · diff: does not
thread PRRT_a3 · lasp-dev · by: ai-drafted · tests · asked: test the failure path · outcome: unanswered · diff: does not
review 101 · carol · by: human · process · asked: bump the version before release · outcome: changed as asked · diff: cannot tell
comment 202 · alice · by: human · design · asked: none · outcome: none · diff: cannot tell
Procedure: none
Not read: none
Read: pkg/loader.py
"""

ANALYSIS_12 = """## pr-0012 — threads read
thread PRRT_b1 · dave · by: human · correctness · asked: check the path where it enters · outcome: changed as asked · diff: addresses it
thread PRRT_b2 · erin · by: human · tests · asked: the review skill flagged a vendored file · outcome: unanswered · diff: cannot tell
Procedure: PRRT_b2
Not read: comment 303
Read: pkg/io.py
"""

SWEEP_7 = """## pr-0007 · abc1234
R-001 · follows · pkg/loader.py:12
C-2 · breaks · none · "no CHANGELOG.md change" · the pull request changed the public loader
C-1 · not touched
Not read: none
"""

SWEEP_12 = """## pr-0012 · def5678
R-001 · breaks · pkg/io.py:40 · "def read(source: str | Path):" · the union reaches the body unconverted
C-2 · breaks · none · "no CHANGELOG.md change" · a user-facing change with no entry
C-1 · not judged · no description
Not read: docs/big.md
"""


class Tally(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, text):
        (self.dir / name).write_text(text)

    def run_it(self, kind, folder=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = block_tally.main([kind, str(folder or self.dir)])
        return code, out.getvalue().splitlines(), err.getvalue()

    def test_the_analysis_counts_asks_by_who_source_category_and_outcome(self):
        self.write("pr-0007.md", ANALYSIS_7)
        self.write("pr-0012.md", ANALYSIS_12)
        self.write("pr-0009.md", "record mismatch: PRRT_x9\n")
        code, out, _ = self.run_it("analysis")
        self.assertEqual(code, 0)
        self.assertEqual(
            out,
            [
                "blocks: 3 · asks: 6 · asked none: 1 · mismatches: 1",
                "count · human · thread · correctness · changed as asked · 2",
                "count · human · thread · correctness · declined · 1",
                "count · human · thread · tests · unanswered · 1",
                "count · human · review · process · changed as asked · 1",
                "count · ai-drafted · thread · tests · unanswered · 1",
                "unanswered · pr-0007 · thread PRRT_a3 · by: ai-drafted · diff: does not",
                "unanswered · pr-0012 · thread PRRT_b2 · by: human · diff: cannot tell",
                "procedure · pr-0012 · PRRT_b2",
                "not read · pr-0012 · comment 303",
                "mismatch · pr-0009 · PRRT_x9",
            ],
        )

    def test_the_sweep_counts_each_claim_and_marks_drift(self):
        self.write("pr-0007.md", SWEEP_7)
        self.write("pr-0012.md", SWEEP_12)
        code, out, _ = self.run_it("sweep")
        self.assertEqual(code, 0)
        self.assertEqual(
            out,
            [
                "blocks: 2",
                "claim · R-001 · judged 2 · follows 1 · breaks 1 · not touched 0 · not judged 0",
                "claim · C-1 · judged 2 · follows 0 · breaks 0 · not touched 1 · not judged 1",
                "claim · C-2 · judged 2 · follows 0 · breaks 2 · not touched 0 · not judged 0 · drift",
                "break · R-001 · pr-0012 · pkg/io.py:40",
                "break · C-2 · pr-0007 · none",
                "break · C-2 · pr-0012 · none",
                "not read · pr-0012 · docs/big.md",
            ],
        )

    def test_an_empty_folder_counts_nothing(self):
        self.assertEqual(self.run_it("sweep"), (0, ["blocks: 0"], ""))

    def refused(self, kind, name, text, says):
        self.write(name, text)
        code, out, err = self.run_it(kind)
        self.assertEqual((code, out), (2, []))
        self.assertIn(says, err)

    def test_a_line_of_no_verdict_form_is_refused(self):
        self.refused("sweep", "pr-0007.md", SWEEP_7.replace("C-1 · not touched", "C-1 · breaks, judged as follows on the evidence"), "not a verdict line: C-1")

    def test_a_claim_judged_twice_is_refused(self):
        self.refused("sweep", "pr-0007.md", SWEEP_7.replace("C-1 · not touched", "R-001 · not touched"), "R-001 judged twice")

    def test_a_sweep_heading_for_another_pull_request_is_refused(self):
        self.refused("sweep", "pr-0008.md", SWEEP_7, "the heading names pr-0007")

    def test_a_sweep_block_without_its_not_read_line_is_refused(self):
        self.refused("sweep", "pr-0007.md", SWEEP_7.replace("Not read: none\n", ""), "no `Not read:` line")

    def test_an_ask_line_with_an_unknown_category_is_refused(self):
        self.refused("analysis", "pr-0007.md", ANALYSIS_7.replace("· process ·", "· release ·"), "not an ask line: review 101")

    def test_an_analysis_block_with_two_procedure_lines_is_refused(self):
        self.refused("analysis", "pr-0007.md", ANALYSIS_7 + "Procedure: PRRT_a1\n", "two `Procedure:` lines")

    def test_an_analysis_block_opening_with_a_write_error_is_refused(self):
        self.refused("analysis", "pr-0007.md", "Write failed: permission denied\n" + ANALYSIS_7, "the first line is not")

    def test_a_file_not_named_for_a_pull_request_is_refused(self):
        self.refused("analysis", "pr-seven.md", ANALYSIS_7, "not named pr-NNNN.md")

    def test_a_missing_folder_is_refused(self):
        code, out, err = self.run_it("analysis", self.dir / "absent")
        self.assertEqual((code, out), (2, []))
        self.assertIn("no directory", err)


if __name__ == "__main__":
    unittest.main()
