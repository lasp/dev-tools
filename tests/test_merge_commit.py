"""Tests for scripts/merge_commit.py, on a scratch repository. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("merge_commit", ROOT / "scripts" / "merge_commit.py")
merge_commit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(merge_commit)


class MergeCommit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.repo = self.tmp / "repo"
        self.git("init", "-q", "-b", "main", str(self.repo), cwd=self.tmp)
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.commit("Start")
        self.squash = self.commit("Write products through a path (#66)")
        self.commit("Fix the loader (#6)")
        self.git("checkout", "-q", "-b", "feature")
        self.commit("Work on the side (#68)")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "feature", "-m", "Merge pull request #67 from org/feature")
        self.merge = self.git("rev-parse", "HEAD")

    def git(self, *args, cwd=None):
        out = subprocess.run(["git", *args], cwd=cwd or self.repo, capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def commit(self, subject):
        self.git("commit", "-q", "--allow-empty", "-m", subject)
        return self.git("rev-parse", "HEAD")

    def pr(self, number, merged=True):
        path = self.tmp / f"pr-{number}.json"
        path.write_text(json.dumps({"number": number, "merged": merged}))
        return str(path)

    def run_it(self, *prs, ref="main"):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = merge_commit.main(["--repo", str(self.repo), "--ref", ref, *prs])
        return rc, out.getvalue().splitlines(), err.getvalue()

    def test_a_squash_merge_and_a_merge_commit_are_found_by_number(self):
        rc, out, _ = self.run_it(self.pr(66), self.pr(67))
        self.assertEqual((rc, out), (0, [f"pr-0066 {self.squash}", f"pr-0067 {self.merge}"]))

    def test_a_commit_off_the_first_parent_history_is_not_the_merge(self):
        rc, out, _ = self.run_it(self.pr(66), self.pr(68))
        self.assertEqual((rc, out), (1, [f"pr-0066 {self.squash}", "pr-0068 none · no commit on the first-parent history names #68"]))

    def test_two_commits_naming_the_number_are_refused(self):
        self.commit('Revert "Write products through a path (#66)" again (#66)')
        rc, out, _ = self.run_it(self.pr(66))
        self.assertEqual(rc, 1)
        self.assertRegex(out[0], r"^pr-0066 none · 2 commits name #66: ")

    def test_an_unmerged_pull_request_or_an_unknown_ref_cannot_run(self):
        rc, out, err = self.run_it(self.pr(66, merged=False))
        self.assertEqual((rc, out), (2, []))
        self.assertIn("is not merged", err)
        rc, out, err = self.run_it(self.pr(66), ref="origin/main")
        self.assertEqual((rc, out), (2, []))
        self.assertIn("git log origin/main", err)


if __name__ == "__main__":
    unittest.main()
