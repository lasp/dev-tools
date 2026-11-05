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

# Two ledger shapes with a wrapped Do not flag paragraph: R-001's runs straight into its scope:
# line, R-009's runs four lines; both open with repos: and R-001 is marked needs a second.
R001_STATUS = """### R-001 · Validate a name where it is constructed
repos: [widgets]

tier: reviewer · status: provisional · since: 2026-09 · evidence: pr-0012 (asked twice) · **one pull request, needs a second**
"""
R001_WORDING = [
    "An invalid name is rejected by the constructor that receives it,",
    "so the failure reaches the caller who can fix it.",
]
R001_FLAG = """Do not flag: a validator deliberately deferred because it needs data the constructor does
not have, when the docstring says so.
scope: widgets/*.py
"""
R009_STATUS = """### R-009 · Comments describe the code as it is
repos: [widgets]

tier: reviewer · status: provisional · since: 2026-09 · evidence: pr-0037, pr-0058 · widened to names 2026-10-06
"""
R009_WORDING = [
    "A comment or a name describes the code as it is, not how it got there,",
    "and reads correctly with only the code around it.",
]
R009_FLAG = """Do not flag: a tagged deferred-work marker such as `TODO[PROJ-1234]`, which is
forward-looking; a comment citing an external
document that the code implements; a name that tells apart two versions the code keeps side by
side on purpose.
scope: widgets/*.py, tests/*.py
"""


def inline_form(status, wording, flag):
    return status + "\n" + "".join(f"> {line}\n" for line in wording) + "\n" + flag


def linked_form(status, wording, flag):
    heading = status.splitlines()[0]
    return status + "\nWording: [the instruction file](../instructions.md#r)\n\n" + flag + "\n" + heading + "\n\n" + "\n".join(wording) + "\n"


class ProbeInput(unittest.TestCase):
    def test_a_wrapped_do_not_flag_paragraph_is_given_whole_and_stops_at_the_next_field(self):
        for status, wording, flag in ((R001_STATUS, R001_WORDING, R001_FLAG), (R009_STATUS, R009_WORDING, R009_FLAG)):
            want = [status.splitlines()[0][4:], *wording, *flag.splitlines()[:-1]]
            for form in (inline_form, linked_form):
                with self.subTest(rule=want[0][:5], form=form.__name__):
                    code, out, err = self.run_it(form(status, wording, flag))
                    self.assertEqual((code, err), (0, ""))
                    self.assertEqual(out.splitlines(), want)
                    for field in ("scope:", "repos:", "tier:", "needs a second"):
                        self.assertNotIn(field, out)

    def test_a_wrapped_do_not_flag_paragraph_under_the_wording_heading_stays_out_of_the_wording(self):
        text = R009_STATUS + "\nscope: widgets/*.py\n\n### R-009 · Comments describe the code as it is\n\n" + "\n".join(R009_WORDING) + "\n\n" + R009_FLAG.rsplit("scope:", 1)[0]
        code, out, _ = self.run_it(text)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["R-009 · Comments describe the code as it is", *R009_WORDING, *R009_FLAG.splitlines()[:-1]])

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
        self.assertNotIn("example", out)

    def test_what_follows_the_wording_under_a_later_heading_is_not_read(self):
        trailing = "\n## Notes\n\nexample: fires on r#9 PRRT_zzz; not on r#9@abc1234 pkg/x.py::f \"x\"\nDo not flag: a second case.\n"
        for text in (INLINE + trailing, LINKED + trailing):
            code, out, _ = self.run_it(text)
            self.assertEqual((code, out.splitlines()), (0, WANT))

    def test_the_wording_heading_before_the_entry_is_refused(self):
        entry, wording = LINKED.rsplit("### R-004", 1)
        code, out, err = self.run_it("### R-004" + wording + "\n" + entry)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("no scope: or example: line", err)

    def test_a_line_that_would_show_the_probe_a_field_is_refused(self):
        code, out, err = self.run_it(LINKED + "scope: pkg/*.py\n")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("would show the probe 'scope: pkg/*.py'", err)

    def test_three_entry_headings_are_refused(self):
        code, _, err = self.run_it(LINKED + "\n### R-004 · Validate a path where it is constructed\n\nMore.\n")
        self.assertEqual(code, 2)
        self.assertIn("3 ### R-NNN headings", err)

    def test_a_wording_heading_with_the_same_id_and_another_title_is_refused(self):
        entry, wording = LINKED.rsplit("### R-004 · Validate a path where it is constructed", 1)
        code, _, err = self.run_it(entry + "### R-004 · Check paths early" + wording)
        self.assertEqual(code, 2)
        self.assertIn("the wording heading is R-004 · 'Check paths early'", err)

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
