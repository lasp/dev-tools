"""Tests for scripts/window_merges.py, on a scratch repository. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("window_merges", ROOT / "scripts" / "window_merges.py")
window_merges = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(window_merges)

LEDGER = """# Review rules

### R-001 · Old rule

tier: reviewer · status: provisional · since: 2026-09 · evidence: pr-0001
scope: pkg/*.py

### R-002 · Docs rule

tier: reviewer · status: established · since: 2026-10 · evidence: pr-0002
scope: docs/*.md, README.md

### R-003 · No scope

tier: reviewer · status: provisional · since: 2026-09 · evidence: pr-0003

### R-004 · Graduated

tier: check · status: graduated · since: 2026-09 · evidence: pre-commit
scope: pkg/*.py

### R-005 · Retired

tier: — · status: retired · reasoning: archive
"""


class WindowMerges(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.repo = self.tmp / "repo"
        self.git("init", "-q", "-b", "main", str(self.repo), cwd=self.tmp)
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.commit("Start", {"README.md": "x"}, "2026-08-20")
        self.commit("Before the window (#1)", {"pkg/a.py": "1"}, "2026-08-30")
        self.squash = self.commit("Add the loader (#66)", {"pkg/sub/b.py": "1"}, "2026-09-15")
        self.git("checkout", "-q", "-b", "feature")
        self.commit("Work on the side (#68)", {"docs/guide.md": "1"}, "2026-10-02")
        self.git("checkout", "-q", "main")
        self.merge = self.commit_merge("Merge pull request #67 from org/feature", "2026-10-03")
        self.commit("Rebased work, no number", {"pkg/c.py": "1"}, "2026-10-04")
        self.ledger = self.tmp / "review-rules.md"
        self.ledger.write_text(LEDGER)

    def git(self, *args, cwd=None, day=None):
        env = dict(os.environ)
        if day:
            stamp = day if "T" in day else f"{day}T12:00:00+00:00"
            env.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
        out = subprocess.run(["git", *args], cwd=cwd or self.repo, capture_output=True, text=True, check=True, env=env)
        return out.stdout.strip()

    def commit(self, subject, files, day):
        for name, text in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            self.git("add", name)
        self.git("commit", "-q", "-m", subject, day=day)
        return self.git("rev-parse", "HEAD")

    def commit_merge(self, subject, day):
        self.git("merge", "-q", "--no-ff", "feature", "-m", subject, day=day)
        return self.git("rev-parse", "HEAD")

    def run_it(self, *extra, since="2026-09-01", ref="main"):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = window_merges.main(["--repo", str(self.repo), "--ref", ref, "--since", since, *extra])
        return rc, out.getvalue().splitlines(), err.getvalue()

    def test_squash_and_merge_commits_in_the_window_are_listed_with_their_first_parent_files(self):
        rc, out, _ = self.run_it()
        self.assertEqual(rc, 0)
        self.assertEqual(out, [f"pr-0066 {self.squash} 2026-09-15 pkg/sub/b.py", f"pr-0067 {self.merge} 2026-10-03 docs/guide.md"])

    def test_each_live_reviewer_rule_gets_the_pull_requests_its_scope_matches(self):
        rc, out, _ = self.run_it("--ledger", str(self.ledger))
        self.assertEqual(rc, 0)
        self.assertEqual(out[2:], ["R-001 pr-0066", "R-002 pr-0067", "R-003 not swept: no scope"])

    def test_a_merge_before_the_rules_since_month_predates_it(self):
        self.ledger.write_text(LEDGER.replace("since: 2026-09 · evidence: pr-0001", "since: 2026-10 · evidence: pr-0001"))
        _, out, _ = self.run_it("--ledger", str(self.ledger))
        self.assertEqual(out[2:4], ["R-001 none", "R-001 predates pr-0066"])

    def test_a_window_with_no_merge_prints_no_merge_and_none_per_rule(self):
        rc, out, _ = self.run_it("--ledger", str(self.ledger), since="2026-10-05")
        self.assertEqual((rc, out), (0, ["R-001 none", "R-002 none", "R-003 not swept: no scope"]))

    def test_a_rule_with_no_since_never_predates(self):
        self.ledger.write_text(LEDGER.replace("since: 2026-09 · evidence: pr-0001", "evidence: pr-0001"))
        _, out, _ = self.run_it("--ledger", str(self.ledger), since="2026-08-01")
        self.assertEqual(out[3], "R-001 pr-0001 pr-0066")

    def test_the_window_edge_is_the_merge_day_in_utc(self):
        self.commit("Late in Boulder (#70)", {"pkg/d.py": "1"}, "2026-10-04T23:30:00-06:00")
        _, out, _ = self.run_it(since="2026-10-05")
        self.assertEqual([line.split()[0] + " " + line.split()[2] for line in out], ["pr-0070 2026-10-05"])

    def test_a_subject_naming_two_numbers_is_not_listed_and_a_path_with_a_space_is_one_file(self):
        self.commit("Merge pull request #71 from org/x (#72)", {"pkg/e.py": "1"}, "2026-10-06")
        self.commit("A spaced name (#73)", {"docs/my guide.md": "1"}, "2026-10-07")
        _, out, _ = self.run_it(since="2026-10-06")
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("pr-0073 ") and out[0].endswith(" 2026-10-07 docs/my guide.md"))

    def test_a_root_commit_naming_a_pull_request_lists_its_files(self):
        root = self.tmp / "root"
        self.git("init", "-q", "-b", "main", str(root), cwd=self.tmp)
        (root / "a.py").write_text("1")
        self.git("add", "a.py", cwd=root)
        self.git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "First (#1)", cwd=root, day="2026-09-02")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = window_merges.main(["--repo", str(root), "--ref", "main", "--since", "2026-09-01"])
        self.assertEqual(rc, 0)
        self.assertRegex(out.getvalue(), r"^pr-0001 [0-9a-f]{40} 2026-09-02 a[.]py\n$")

    def with_docs(self):
        """The template reaches main with #70; #71 opens as it does; #72 adds a document none was opened after."""
        self.commit("Add the template (#70)", {".github/pull_request_template.md": "Ticket:"}, "2026-10-05T12:00:00+00:00")
        self.commit("Fix (#71)", {"pkg/f.py": "1"}, "2026-10-06")
        self.commit("Late docs (#72)", {"docs/late.md": "1"}, "2026-10-07")
        dumps = self.tmp / "threads"
        for n, created in ((67, "2026-10-02T13:00:00Z"), (70, "2026-10-01T09:00:00Z"), (71, "2026-10-05T12:00:00Z"), (72, "2026-10-06T09:00:00Z")):
            (dumps / f"pr-{n:04d}").mkdir(parents=True)
            (dumps / f"pr-{n:04d}" / "pr.json").write_text(json.dumps({"number": n, "created_at": created}))
        return dumps

    def test_a_document_judges_only_the_pull_requests_opened_after_it_reached_main(self):
        dumps = self.with_docs()
        docs = [".github/pull_request_template.md", "docs/guide.md", "docs/late.md", "missing.md"]
        rc, out, err = self.run_it("--ledger", str(self.ledger), "--dumps", str(dumps), *[a for d in docs for a in ("--doc", d)])
        self.assertEqual(rc, 0, err)
        self.assertEqual(out[-10:], [
            "doc .github/pull_request_template.md: pr-0071 pr-0072",
            "doc .github/pull_request_template.md: predates pr-0067 pr-0070",
            "doc .github/pull_request_template.md: no opened day pr-0066",
            # Added on a side branch: it reaches main with the merge on 2026-10-03, after #67 opened.
            "doc docs/guide.md: pr-0071 pr-0072",
            "doc docs/guide.md: predates pr-0067 pr-0070",
            "doc docs/guide.md: no opened day pr-0066",
            "doc docs/late.md: none",
            "doc docs/late.md: predates pr-0067 pr-0070 pr-0071 pr-0072",
            "doc docs/late.md: no opened day pr-0066",
            "doc missing.md: not on main",
        ])
        self.assertEqual(out[-11], "R-003 not swept: no scope")

    def test_a_doc_without_dumps_or_an_unreadable_opened_day_cannot_run(self):
        dumps = self.with_docs()
        rc, out, err = self.run_it("--doc", "docs/guide.md")
        self.assertEqual((rc, out), (2, []))
        self.assertIn("--doc needs --dumps", err)
        for text in ("not json", json.dumps({"number": 71}), json.dumps({"created_at": "2026-10-05"})):
            (dumps / "pr-0071" / "pr.json").write_text(text)
            rc, out, err = self.run_it("--doc", "docs/guide.md", "--dumps", str(dumps))
            self.assertEqual((rc, out), (2, []), text)
            self.assertIn("pr-0071/pr.json: no created_at", err)

    def test_a_bad_ref_a_bad_date_or_an_unreadable_ledger_cannot_run(self):
        no_status = self.tmp / "no-status.md"
        no_status.write_text("### R-001 · No status\n\nscope: pkg/*.py\n")
        bad_since = self.tmp / "bad-since.md"
        bad_since.write_text(LEDGER.replace("since: 2026-09 · evidence: pr-0001", "since: 2026-9 · evidence: pr-0001"))
        for extra, kw, says in [
            ((), {"ref": "origin/main"}, "git log"),
            ((), {"since": "September"}, "--since September"),
            ((), {"since": "20261005"}, "--since 20261005"),
            ((), {"since": "2026-02-30"}, "--since 2026-02-30"),
            (("--ledger", str(self.tmp / "missing.md")), {}, "missing.md"),
            (("--ledger", str(no_status)), {}, "no status line"),
            (("--ledger", str(bad_since)), {}, "is not YYYY-MM"),
        ]:
            rc, out, err = self.run_it(*extra, **kw)
            self.assertEqual((rc, out), (2, []))
            self.assertIn(says, err)


if __name__ == "__main__":
    unittest.main()
