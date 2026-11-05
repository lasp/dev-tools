"""Tests for scripts/probe_input.py. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("probe_input", ROOT / "scripts" / "probe_input.py")
probe_input = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe_input)

INLINE = """### R-004 · Validate a path where it is constructed

tier: reviewer · status: provisional · since: 2026-11 · evidence: pr-0001

scope: pkg/*.py
example: fires on r#1 PRRT_abc123; not on r#2@abc1234 pkg/loader.py::load "path: Path"

> A path is checked where it enters,
> so a bad value fails at the boundary.

Do not flag: a path validated by its caller, when the docstring says so.
"""

LINKED = """### R-004 · Validate a path where it is constructed

tier: reviewer · status: provisional · since: 2026-11 · evidence: pr-0001

Wording: [R-004 in the instruction file](../instructions.md#r-004)

scope: pkg/*.py
example: fires on r#1 PRRT_abc123; not on r#2@abc1234 pkg/loader.py::load "path: Path"

Do not flag: a path validated by its caller, when the docstring says so.

### R-004 · Validate a path where it is constructed

A path is checked where it enters,
so a bad value fails at the boundary.
"""

WANT = [
    "R-004 · Validate a path where it is constructed",
    "A path is checked where it enters,",
    "so a bad value fails at the boundary.",
    "Do not flag: a path validated by its caller, when the docstring says so.",
]


class ProbeInput(unittest.TestCase):
    def run_it(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "R-004.entry.md"
            path.write_text(text)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = probe_input.main([str(path)])
        return code, out.getvalue(), err.getvalue()

    def test_an_inline_entry_gives_its_title_wording_and_do_not_flag_line_and_never_its_example(self):
        code, out, _ = self.run_it(INLINE)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), WANT)
        self.assertNotIn("example", out)
        self.assertNotIn("PRRT_", out)

    def test_wording_under_a_second_heading_is_read_from_there(self):
        code, out, _ = self.run_it(LINKED)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), WANT)

    def test_an_entry_without_a_do_not_flag_line_is_refused(self):
        code, out, err = self.run_it(INLINE.replace("Do not flag: a path validated by its caller, when the docstring says so.\n", ""))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("0 `Do not flag:` lines", err)

    def test_an_entry_with_two_do_not_flag_lines_is_refused(self):
        code, _, err = self.run_it(INLINE + "Do not flag: a second case.\n")
        self.assertEqual(code, 2)
        self.assertIn("2 `Do not flag:` lines", err)

    def test_an_entry_with_no_wording_is_refused(self):
        code, _, err = self.run_it(INLINE.replace("> A path is checked where it enters,\n> so a bad value fails at the boundary.\n", ""))
        self.assertEqual(code, 2)
        self.assertIn("R-004 has no wording", err)

    def test_wording_in_both_places_is_refused(self):
        code, _, err = self.run_it(LINKED.replace("Wording: [R-004", "> A quoted line.\n\nWording: [R-004"))
        self.assertEqual(code, 2)
        self.assertIn("lives in one place", err)

    def test_a_wording_heading_for_another_rule_is_refused(self):
        entry, wording = LINKED.rsplit("### R-004", 1)
        code, _, err = self.run_it(entry + "### R-005" + wording)
        self.assertEqual(code, 2)
        self.assertIn("the wording heading is R-005", err)

    def test_a_file_with_no_entry_is_refused(self):
        code, _, err = self.run_it("# Nothing here\n")
        self.assertEqual(code, 2)
        self.assertIn("no ### R-NNN entry", err)

    def test_a_missing_file_is_refused(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = probe_input.main([str(ROOT / "no-such-entry.md")])
        self.assertEqual(code, 2)
        self.assertIn("CANNOT RUN", err.getvalue())


if __name__ == "__main__":
    unittest.main()
