"""Tests for scripts/comment_scan.py, on scratch repositories. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("comment_scan", ROOT / "scripts" / "comment_scan.py")
comment_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(comment_scan)

KEY = re.compile(r"PROJ-\d+")


def lines(path, text, start=1):
    return [(path, n, t) for n, t in enumerate(text.splitlines(), start)]


class Scan(unittest.TestCase):
    def test_todo_needs_a_key(self):
        marks = comment_scan.scan(lines("a.py", "# TODO handle leap seconds\n# TODO[PROJ-12] handle leap seconds\n"
                                        "# FIXME see #40\nx = 1  # TODO trailing code is not a comment line\n"), KEY)
        self.assertEqual(marks, ["a.py:1 · todo · TODO handle leap seconds"])

    def test_follow_up_and_session_notes(self):
        marks = comment_scan.scan(lines("a.py", "# Follow-up: cache the kernels\n# Now we check the frame first\n"
                                        "# Radiance in W m-2 sr-1\n"), KEY)
        self.assertEqual(marks, ["a.py:1 · follow-up · Follow-up: cache the kernels",
                                 "a.py:2 · session · Now we check the frame first"])

    def test_algorithm_steps_and_technical_phrases_are_not_session_notes(self):
        text = ("# Step 1. Load the kernels\n# Unload any previously loaded kernels\n# the value used to scale\n"
                "# cloud phase 1-5, as the readers define them\n")
        self.assertEqual(comment_scan.scan(lines("a.py", text), KEY), [])
        self.assertEqual(comment_scan.scan(lines("a.py", "# NetCDF output (NEW - Phase 1)\n"), KEY),
                         ["a.py:1 · session · NetCDF output (NEW - Phase 1)"])

    def test_a_todo_with_a_key_is_not_a_follow_up(self):
        self.assertEqual(comment_scan.scan(lines("a.py", "# TODO[PROJ-9] revisit the tolerance\n"), KEY), [])

    def test_long_runs_and_their_breaks(self):
        block = "".join(f"# line {i}\n" for i in range(6))
        self.assertEqual(comment_scan.scan(lines("a.py", block), KEY), ["a.py:1 · long · 6 lines"])
        broken = "# a\n# b\n# c\nx = 1\n# d\n# e\n# f\n"
        self.assertEqual(comment_scan.scan(lines("a.py", broken), KEY), [])
        gap = lines("a.py", "# a\n# b\n# c\n") + lines("a.py", "# d\n# e\n# f\n", start=10)
        self.assertEqual(comment_scan.scan(gap, KEY), [])

    def test_pragmas_and_other_languages(self):
        self.assertEqual(comment_scan.scan(lines("a.py", "#!/usr/bin/env python3\n# noqa: E501\n# type: ignore\n"), KEY), [])
        self.assertEqual(comment_scan.scan(lines("a.ts", "// TODO wire it\n"), KEY), ["a.ts:1 · todo · TODO wire it"])
        self.assertIsNone(comment_scan.comment("a.ts", "# not a comment here"))


class Diff(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.tmp)
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                     ["remote", "add", "origin", "git@github.com:nobody/thing.git"]):
            subprocess.run(["git", *args], check=True)
        Path("pkg").mkdir()
        Path("pkg/a.py").write_text("x = 1\n# TODO old note\n")
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], check=True)

    def run_scan(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = comment_scan.main(list(args))
        return code, out.getvalue()

    def test_reads_only_what_the_change_adds_and_untracked_files(self):
        Path("pkg/a.py").write_text("x = 1\n# TODO old note\ny = 2\n# TODO new note\n# TODO[ABC-3] keyed\n")
        Path("pkg/b.py").write_text("# as requested, a helper\n")
        Path("notes.md").write_text("# TODO a heading in markdown\n")
        code, out = self.run_scan("main")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["pkg/a.py:4 · todo · TODO new note",
                                            "pkg/b.py:1 · session · as requested, a helper"])

    def test_head_reads_a_committed_revision(self):
        subprocess.run(["git", "switch", "-q", "-c", "topic"], check=True)
        Path("pkg/a.py").write_text("x = 1\n# TODO old note\n# eventually split this\n")
        subprocess.run(["git", "commit", "-q", "-am", "topic"], check=True)
        subprocess.run(["git", "switch", "-q", "main"], check=True)
        code, out = self.run_scan("main", "--head", "topic")
        self.assertEqual((code, out.splitlines()), (0, ["pkg/a.py:3 · follow-up · eventually split this"]))

    def test_nothing_to_mark_prints_nothing(self):
        self.assertEqual(self.run_scan("main"), (0, ""))

    def test_a_bad_base_exits_1(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, _ = self.run_scan("nope")
        self.assertEqual(code, 1)
        self.assertIn("comment_scan.py: git", err.getvalue())


if __name__ == "__main__":
    unittest.main()
