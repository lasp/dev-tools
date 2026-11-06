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
thread PRRT_a4 · linter-bot · by: bot · style · asked: wrap the long line · outcome: changed as asked · diff: addresses it
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

CLAIMS = """### R-001 · Validate a path where it is constructed

> A path is checked where it enters.

Do not flag: a path validated by its caller.

### C-1 · CONTRIBUTING.md:12 · every change

The pull request description says how the change was tested.

### C-2 · CONTRIBUTING.md:20 · every change

A user-facing change adds a CHANGELOG.md entry.
"""

ANALYSIS_WANT = [
    "blocks: 3 · asks: 7 · asked none: 1 · mismatches: 1",
    "count · human · thread · correctness · changed as asked · 2",
    "count · human · thread · correctness · declined · 1",
    "count · human · thread · tests · unanswered · 1",
    "count · human · review · process · changed as asked · 1",
    "count · bot · thread · style · changed as asked · 1",
    "count · ai-drafted · thread · tests · unanswered · 1",
    "outcome unanswered · pr-0007 · thread PRRT_a3 · by: ai-drafted · diff: does not",
    "outcome unanswered · pr-0012 · thread PRRT_b2 · by: human · diff: cannot tell",
    "procedure · pr-0012 · PRRT_b2",
    "not read · pr-0012 · comment 303",
    "mismatch · pr-0009 · PRRT_x9",
]


def block_tally_main(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = block_tally.main(args)
    return code, out.getvalue().splitlines(), err.getvalue()


class Tally(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, text):
        (self.dir / name).write_text(text)

    def run_it(self, kind, *prs, folder=None, claims=CLAIMS, merges=None):
        args = [kind, str(folder or self.dir), *prs]
        if kind == "sweep" and claims is not None:
            path = self.dir / "claims.md"
            path.write_text(claims)
            args += ["--claims", str(path)]
        if merges is not None:
            path = self.dir / "merges.txt"
            path.write_text(merges)
            args += ["--merges", str(path)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = block_tally.main(args)
        return code, out.getvalue().splitlines(), err.getvalue()

    def test_the_analysis_counts_asks_by_who_source_category_and_outcome(self):
        self.write("pr-0007.md", ANALYSIS_7)
        self.write("pr-0012.md", ANALYSIS_12)
        self.write("pr-0009.md", "record mismatch: PRRT_x9\n")
        code, out, _ = self.run_it("analysis", "pr-0012", "pr-0007", "pr-0009")
        self.assertEqual(code, 0)
        self.assertEqual(out, ANALYSIS_WANT)

    def test_a_block_an_earlier_run_left_is_not_counted(self):
        self.write("pr-0007.md", ANALYSIS_7)
        self.write("pr-0012.md", ANALYSIS_12)
        self.write("pr-0009.md", "record mismatch: PRRT_x9\n")
        self.write("pr-0003.md", ANALYSIS_12.replace("pr-0012", "pr-0003"))
        self.write("pr-0004.md", "not a block at all\n")
        code, out, _ = self.run_it("analysis", "pr-0007", "pr-0009", "pr-0012")
        self.assertEqual((code, out), (0, ANALYSIS_WANT))

    def test_the_sweep_counts_each_claim_and_marks_drift(self):
        self.write("pr-0007.md", SWEEP_7)
        self.write("pr-0012.md", SWEEP_12)
        self.write("pr-0002.md", SWEEP_12.replace("pr-0012", "pr-0002"))
        code, out, _ = self.run_it("sweep", "pr-0007", "pr-0012")
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

    def refused(self, kind, name, text, says):
        self.write(name, text)
        code, out, err = self.run_it(kind, name[:-3])
        self.assertEqual((code, out), (2, []))
        self.assertIn(says, err)

    def test_a_sweep_block_missing_a_documented_claim_is_refused(self):
        self.write("pr-0007.md", SWEEP_7)
        code, out, err = self.run_it("sweep", "pr-0007", claims=CLAIMS + "\n### C-3 · README.md:4 · every change\n\nA claim.\n")
        self.assertEqual((code, out), (2, []))
        self.assertIn("pr-0007: no line for C-3", err)

    def test_a_scripted_claim_is_owed_by_no_probe(self):
        self.write("pr-0007.md", SWEEP_7)
        code, out, err = self.run_it("sweep", "pr-0007",
                                     claims=CLAIMS + "\n### C-3 · README.md:4 · every change · script: template\n\nA claim.\n")
        self.assertEqual(code, 0, err)
        code, out, err = self.run_it("sweep", "pr-0007", claims=CLAIMS + "\n### C-3 · README.md:4 · every change · scripted\n")
        self.assertEqual((code, out), (2, []))
        self.assertIn("is not `### C-n · <path>:<line> · every change|code[ · script: <check>]`", err)

    def test_an_every_change_claim_is_owed_only_by_the_pull_requests_opened_after_its_document(self):
        self.write("pr-0007.md", SWEEP_7)
        self.write("pr-0012.md", SWEEP_12.replace("C-1 · not judged · no description\n", ""))
        merges = (
            "pr-0007 abc1234 2026-10-01 CONTRIBUTING.md\npr-0012 def5678 2026-10-03 pkg/io.py\nR-001 pr-0007 pr-0012\n"
            "doc CONTRIBUTING.md: pr-0007\ndoc CONTRIBUTING.md: predates pr-0012\n"
        )
        code, out, err = self.run_it("sweep", "pr-0007", "pr-0012", merges=merges)
        self.assertEqual(code, 0, err)
        self.assertIn("claim · C-1 · judged 1 · follows 0 · breaks 0 · not touched 1 · not judged 0", out)
        code, out, err = self.run_it("sweep", "pr-0007", "pr-0012")
        self.assertEqual((code, out), (2, []))
        self.assertIn("pr-0012: no line for C-1", err)

    def test_a_code_claim_is_owed_by_every_block_and_a_document_not_on_main_by_none(self):
        claims = (
            CLAIMS + "\n### C-3 · pkg/x.py:1 · code\n\nA code claim.\n"
            "\n### C-4 · docs/a b: c.md:2 · every change\n\nA claim whose document is not on main.\n"
        )
        merges = (
            "doc CONTRIBUTING.md: pr-0007 pr-0012\ndoc docs/a b: c.md: not on origin/main\n"
        )
        self.write("pr-0007.md", SWEEP_7.replace("Not read:", "C-3 · not touched\nNot read:"))
        self.write("pr-0012.md", SWEEP_12)
        code, out, err = self.run_it("sweep", "pr-0007", "pr-0012", claims=claims, merges=merges)
        self.assertEqual((code, out), (2, []))
        self.assertIn("pr-0012: no line for C-3", err)
        self.write("pr-0012.md", SWEEP_12.replace("Not read:", "C-3 · not touched\nNot read:"))
        code, out, err = self.run_it("sweep", "pr-0007", "pr-0012", claims=claims, merges=merges)
        self.assertEqual(code, 0, err)
        self.assertFalse(any("C-4" in line for line in out))

    def test_a_five_digit_pull_request_on_a_doc_line_is_read(self):
        self.write("pr-10007.md", SWEEP_7.replace("pr-0007", "pr-10007"))
        merges = "doc CONTRIBUTING.md: pr-10007\n"
        code, out, err = self.run_it("sweep", "pr-10007", merges=merges)
        self.assertEqual(code, 0, err)

    def test_a_merges_file_missing_or_without_a_claims_document_is_refused(self):
        self.write("pr-0007.md", SWEEP_7)
        code, out, err = self.run_it("sweep", "pr-0007", merges="doc README.md: pr-0007\n")
        self.assertEqual((code, out), (2, []))
        self.assertIn("has no `doc CONTRIBUTING.md` line", err)
        code, out, err = block_tally_main(["sweep", str(self.dir), "pr-0007", "--claims", str(self.dir / "claims.md"), "--merges", str(self.dir / "absent.txt")])
        self.assertEqual((code, out), (2, []))
        self.assertIn("no merges file", err)

    def test_a_claim_heading_not_in_its_form_is_refused(self):
        self.write("pr-0007.md", SWEEP_7)
        code, out, err = self.run_it("sweep", "pr-0007", claims=CLAIMS + "\n### C-3 · README.md\n\nA claim.\n")
        self.assertEqual((code, out), (2, []))
        self.assertIn("is not `### C-n", err)

    def test_a_sweep_without_its_claims_file_is_refused(self):
        self.write("pr-0007.md", SWEEP_7)
        code, out, err = self.run_it("sweep", "pr-0007", claims=None)
        self.assertEqual((code, out), (2, []))
        self.assertIn("needs --claims", err)

    def test_a_named_block_that_is_missing_is_refused(self):
        self.write("pr-0007.md", SWEEP_7)
        code, out, err = self.run_it("sweep", "pr-0007", "pr-0012")
        self.assertEqual((code, out), (2, []))
        self.assertIn("pr-0012: no block", err)

    def test_a_pull_request_named_twice_or_not_as_pr_nnnn_is_refused(self):
        self.write("pr-0007.md", SWEEP_7)
        self.assertIn("named twice", self.run_it("sweep", "pr-0007", "pr-0007")[2])
        self.assertIn("not a pull request", self.run_it("sweep", "7")[2])

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
        self.refused("analysis", "pr-0007.md", "write failed: permission denied\n" + ANALYSIS_7, "the first line is not")

    def test_an_analysis_heading_for_another_pull_request_is_refused(self):
        self.refused("analysis", "pr-0008.md", ANALYSIS_7, "the heading names pr-0007")

    def test_an_analysis_block_without_its_read_line_is_refused(self):
        self.refused("analysis", "pr-0007.md", ANALYSIS_7.replace("Read: pkg/loader.py\n", ""), "no `Read:` line")

    def test_an_analysis_block_without_its_not_read_line_is_refused(self):
        self.refused("analysis", "pr-0007.md", ANALYSIS_7.replace("Not read: none\n", ""), "no `Not read:` line")

    def test_an_empty_analysis_block_is_refused(self):
        self.refused("analysis", "pr-0007.md", "\n", "pr-0007: empty")

    def test_a_record_mismatch_followed_by_more_lines_is_refused(self):
        self.refused("analysis", "pr-0007.md", "record mismatch: PRRT_a1\n" + ANALYSIS_7, "the first line is not")

    def test_a_missing_folder_is_refused(self):
        code, out, err = self.run_it("analysis", "pr-0007", folder=self.dir / "absent")
        self.assertEqual((code, out), (2, []))
        self.assertIn("no directory", err)


if __name__ == "__main__":
    unittest.main()
