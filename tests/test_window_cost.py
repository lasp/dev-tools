"""Tests for scripts/window_cost.py."""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("window_cost", ROOT / "scripts" / "window_cost.py")
window_cost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window_cost)


class WindowCost(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        for n, opened, merged, built in ((7, "2026-10-01T00:00:00Z", "2026-10-02T12:00:00Z", False),
                                         (8, "2026-10-01T00:00:00Z", "2026-10-01T12:00:00Z", True),
                                         (9, "2026-10-01T00:00:00Z", "2026-10-05T00:00:00Z", False)):
            self.add(n, opened, merged, built)

    def add(self, n, opened, merged, built):
        """A dump as a harvest leaves it, record or none: an unreviewed pull request has no record."""
        dump = self.dir / "threads" / f"pr-{n:04d}"
        dump.mkdir(parents=True, exist_ok=True)
        (dump / "pr.json").write_text(json.dumps({"created_at": opened, "merged_at": merged}))
        if built is not None:
            block = "<details><summary>Already checked</summary>\n\nBuild: passed\n</details>\n" if built else ""
            (dump / "body.md").write_text(f"Ticket: none\n\n{block}")

    def run_it(self) -> tuple[int, list[str]]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = window_cost.main(["--threads", str(self.dir / "threads")])
        return code, out.getvalue().splitlines()

    def test_the_median_and_longest_open_to_merge_and_the_unbuilt_count(self):
        self.assertEqual(self.run_it(), (0, ["cost: open-to-merge median 1.5d, longest 4.0d · 2 merged without a build · 3 pull requests"]))

    def test_a_dump_with_no_body_or_no_merge_time_is_refused(self):
        self.add(10, "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", None)
        self.add(11, "2026-10-01T00:00:00Z", None, False)
        self.add(12, "2026-10-03T00:00:00Z", "2026-10-02T00:00:00Z", False)
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertEqual([line.split(" · ")[-1].split(":")[0] for line in out],
                         ["no body.md in the dump", "no created_at and merged_at to read", "merged before it was opened"])

    def test_no_pull_request_says_so(self):
        shutil.rmtree(self.dir / "threads")
        (self.dir / "threads").mkdir()
        self.assertEqual(self.run_it(), (0, ["cost: no merged pull request"]))


if __name__ == "__main__":
    unittest.main()
