"""Tests for scripts/revise_state.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("revise_state", ROOT / "scripts" / "revise_state.py")
revise_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revise_state)


class State(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def run_state(self, *args: str) -> tuple[int, list[str], str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = revise_state.main(["--dir", str(self.dir), *args])
        return code, out.getvalue().splitlines(), err.getvalue()

    def test_the_report_waits_until_every_stage_is_done_or_skipped_with_its_reason(self):
        self.assertEqual(self.run_state("start")[0], 0)
        for stage in ("records", "analysts", "guidance", "sweep", "clusters", "bar", "checks"):
            self.assertEqual(self.run_state("done", stage)[0], 0)
        self.assertEqual(self.run_state("check")[:2], (1, ["unrecorded · sources"]))
        self.assertEqual(self.run_state("skip", "sources", "the", "Confluence", "server", "is", "not", "connected")[0], 0)
        self.assertEqual(self.run_state("check")[:2], (0, ["skipped · sources · the Confluence server is not connected",
                                                            "stages: 7 done · 1 skipped"]))

    def test_start_forgets_an_earlier_run_and_a_later_record_wins(self):
        self.run_state("skip", "sources", "no server")
        self.run_state("done", "sources")
        self.assertEqual(revise_state.load(revise_state.path_in(self.dir))["sources"], {"status": "done", "why": None})
        self.run_state("start")
        self.assertEqual(self.run_state("check")[1][0], "unrecorded · sources")

    def test_refuses_what_it_cannot_record(self):
        for args, why in ((("skip", "sources"), "needs the reason"), (("done", "sources", "because"), "takes no reason"),
                          (("done", "harvest"), "is not one of"), (("check", "sources"), "takes no stage")):
            with self.subTest(args=args):
                code, _, err = self.run_state(*args)
                self.assertEqual(code, 2)
                self.assertIn(why, err)
        revise_state.path_in(self.dir).parent.mkdir(parents=True, exist_ok=True)
        revise_state.path_in(self.dir).write_text('{"stages": {"sources": {"status": "maybe", "why": null}}}')
        code, _, err = self.run_state("check")
        self.assertEqual(code, 2)
        self.assertIn("is not a revision's run state", err)


if __name__ == "__main__":
    unittest.main()
