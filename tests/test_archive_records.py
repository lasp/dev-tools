"""Tests for scripts/archive_records.py. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("archive_records", ROOT / "scripts" / "archive_records.py")
archive_records = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(archive_records)

# The first record's shape: findings with no thread, recorded from a comment record.py does not read.
LEGACY = "pr: 66\nfindings:\n  - { key: R-012, severity: must-fix, verdict: accepted }\n  - { key: other, severity: should-fix, verdict: accepted }\n"
REBUILT = "contract: 9\npr: 66\nmerged: 2026-10-14\nfindings: []\nquestions: []\n"
FOUND = "contract: 9\npr: {n}\nmerged: 2026-10-14\nfindings:\n  - key: R-012/pyproject.toml\n    verdict: agree\n"


class Archive(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.records, self.log = Path(tmp.name) / "records", Path(tmp.name) / "log"
        self.records.mkdir()
        self.log.mkdir()
        (self.log / "pr-0066.yaml").write_text(LEGACY)
        (self.log / "pr-0067.yaml").write_text(FOUND.format(n=67))
        (self.records / "pr-0066.yaml").write_text(REBUILT)
        (self.records / "pr-0067.yaml").write_text(FOUND.format(n=67).replace("agree", "disagree"))
        (self.records / "pr-0068.yaml").write_text(FOUND.format(n=68))

    def run_it(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = archive_records.main([str(self.records), str(self.log), *extra])
        return rc, out.getvalue().splitlines(), err.getvalue()

    def test_a_rewrite_that_drops_findings_is_refused_and_nothing_is_copied(self):
        rc, out, _ = self.run_it()
        self.assertEqual((rc, out), (1, ["refused pr-0066 · the log's record holds findings the harvested one does not: R-012 ×1, other ×1"]))
        self.assertEqual((self.log / "pr-0066.yaml").read_text(), LEGACY)
        self.assertIn("verdict: agree", (self.log / "pr-0067.yaml").read_text())
        self.assertFalse((self.log / "pr-0068.yaml").exists())

    def test_keep_leaves_the_record_and_copies_the_rest(self):
        rc, out, _ = self.run_it("--keep", "66")
        self.assertEqual((rc, out), (0, ["kept pr-0066 · 2 finding(s) the threads do not carry", "copied pr-0067", "copied pr-0068"]))
        self.assertEqual((self.log / "pr-0066.yaml").read_text(), LEGACY)
        self.assertIn("verdict: disagree", (self.log / "pr-0067.yaml").read_text())
        self.assertEqual((self.log / "pr-0068.yaml").read_text(), FOUND.format(n=68))

    def test_keep_on_a_record_that_drops_nothing_is_refused(self):
        rc, out, err = self.run_it("--keep", "66", "--keep", "67")
        self.assertEqual((rc, out), (1, []))
        self.assertIn("--keep 67: pr-0067.yaml is not a harvested record that would drop findings", err)

    def test_keep_on_a_record_each_side_of_which_holds_findings_the_other_lacks_is_refused(self):
        (self.records / "pr-0066.yaml").write_text(REBUILT.replace("findings: []", "findings:\n  - key: R-004/pkg/a.py\n    verdict: agree"))
        rc, out, err = self.run_it("--keep", "66")
        self.assertEqual((rc, out), (1, []))
        self.assertIn("--keep 66: the harvested pr-0066.yaml holds findings the log's does not, which keeping it would drop: R-004 ×1", err)
        self.assertEqual((self.log / "pr-0066.yaml").read_text(), LEGACY)
        self.assertFalse((self.log / "pr-0068.yaml").exists())

    def test_an_unreadable_finding_is_refused(self):
        (self.log / "pr-0067.yaml").write_text("pr: 67\nfindings:\n  - { severity: must-fix }\n")
        rc, out, err = self.run_it("--keep", "66")
        self.assertEqual((rc, out), (1, []))
        self.assertIn("pr-0067.yaml: a finding without a readable key and verdict", err)
        self.assertFalse((self.log / "pr-0068.yaml").exists())


if __name__ == "__main__":
    unittest.main()
