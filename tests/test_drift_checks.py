"""Tests for scripts/drift_checks.py, on a scratch repository with three merged pull requests."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("drift_checks", ROOT / "scripts" / "drift_checks.py")
drift_checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift_checks)

TEMPLATE = "Ticket: KEY-NNNN — <why>\n\n## Summary\n\n<what>\n\n## How to test\n\n- Here: <command>\n"
CLAIMS = """# Claims

### C-1 · .github/PULL_REQUEST_TEMPLATE.md:1 · every change · script: template
The body opens with a Ticket line.

### C-2 · .github/PULL_REQUEST_TEMPLATE.md:8 · every change · script: template
The body has a How to test section.

### C-3 · CONTRIBUTING.md:4 · every change · script: changelog CHANGELOG.md src/
A user-visible change has a changelog entry.

### C-4 · CONTRIBUTING.md:6 · code · script: todo
A TODO names its ticket.

### C-5 · CONTRIBUTING.md:8 · code · script: history
A comment says what the code is, not what it was.

### C-6 · CONTRIBUTING.md:9 · code
A claim only a reader can judge.
"""


class Drift(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.write(".github/PULL_REQUEST_TEMPLATE.md", TEMPLATE)
        self.write("CHANGELOG.md", "# Changelog\n")
        self.write("src/app.py", "x = 1\n")
        self.commit("Adopt the template")
        self.shas = {}
        self.merge(1, {"src/app.py": "x = 1\n# TODO KEY-12 widen it\ny = 2\n", "CHANGELOG.md": "# Changelog\n- y\n"})
        self.merge(2, {"src/app.py": "x = 1\n# TODO widen it\ny = 2\n# This used to read the cache\n"})
        self.merge(3, {"tests/test_app.py": "def test(): pass\n"})
        self.dumps = self.dir / "threads"
        for n, body in ((1, "Ticket: KEY-1 — why\n\n## Summary\nx\n\n## How to test\n- Here: pytest"),
                        (2, "Ticket: none — why\n\n## Summary\nx"), (3, "")):
            (self.dumps / f"pr-000{n}").mkdir(parents=True)
            (self.dumps / f"pr-000{n}" / "pr.json").write_text(json.dumps({"body": body, "created_at": "2099-01-01T00:00:00Z"}))
        lines = [f"pr-000{n} {self.shas[n]} 2026-10-0{n} {files}" for n, files in
                 ((1, "CHANGELOG.md src/app.py"), (2, "src/app.py"), (3, "tests/test_app.py"))]
        lines += ["doc .github/PULL_REQUEST_TEMPLATE.md: pr-0001 pr-0002 pr-0003",
                  "doc CONTRIBUTING.md: pr-0001 pr-0002 pr-0003"]
        (self.dir / "merges.txt").write_text("\n".join(lines) + "\n")
        (self.dir / "claims.md").write_text(CLAIMS)

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                              check=True, capture_output=True, text=True).stdout

    def write(self, path: str, text: str) -> None:
        (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / path).write_text(text)

    def commit(self, subject: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-qm", subject)
        return self.git("rev-parse", "HEAD").strip()

    def merge(self, n: int, files: dict[str, str]) -> None:
        for path, text in files.items():
            self.write(path, text)
        self.shas[n] = self.commit(f"Change {n} (#{n})")

    def run_drift(self, *extra: str) -> tuple[int, list[str], str]:
        out, err = io.StringIO(), io.StringIO()
        args = ["--repo", str(self.repo), "--ref", "main", "--claims", str(self.dir / "claims.md"),
                "--merges", str(self.dir / "merges.txt"), "--dumps", str(self.dumps), *extra]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = drift_checks.main(args)
        return code, out.getvalue().splitlines(), err.getvalue()

    def test_judges_each_scripted_claim_and_leaves_the_rest_to_a_reader(self):
        code, lines, err = self.run_drift("--ticket-pattern", r"\bKEY-\d+")
        self.assertEqual(code, 0, err)
        self.assertEqual(lines, [
            "claim · C-1 · judged 3 · follows 2 · breaks 0 · not touched 0 · not judged 1",
            "claim · C-2 · judged 3 · follows 1 · breaks 1 · not touched 0 · not judged 1",
            "claim · C-3 · judged 3 · follows 1 · breaks 1 · not touched 1 · not judged 0",
            "claim · C-4 · judged 3 · follows 1 · breaks 1 · not touched 1 · not judged 0",
            "claim · C-5 · judged 3 · follows 0 · breaks 1 · not touched 2 · not judged 0 · drift",
            'break · C-2 · pr-0002 · description · no "How to test" heading',
            "break · C-3 · pr-0002 · src/app.py · changes code and not CHANGELOG.md",
            "break · C-4 · pr-0002 · src/app.py:2 · # TODO widen it",
            "break · C-5 · pr-0002 · src/app.py:4 · # This used to read the cache",
        ])

    def test_a_pull_request_opened_before_its_document_is_not_judged_on_it(self):
        merges = (self.dir / "merges.txt").read_text().replace(
            "doc .github/PULL_REQUEST_TEMPLATE.md: pr-0001 pr-0002 pr-0003", "doc .github/PULL_REQUEST_TEMPLATE.md: pr-0001")
        (self.dir / "merges.txt").write_text(merges)
        lines = self.run_drift("--ticket-pattern", r"\bKEY-\d+")[1]
        self.assertIn("claim · C-2 · judged 1 · follows 1 · breaks 0 · not touched 0 · not judged 0", lines)

    def test_a_document_no_pull_request_followed_judges_none_and_a_code_claim_needs_no_doc_line(self):
        merges = (self.dir / "merges.txt").read_text().replace(
            "doc .github/PULL_REQUEST_TEMPLATE.md: pr-0001 pr-0002 pr-0003", "doc .github/PULL_REQUEST_TEMPLATE.md: none")
        (self.dir / "merges.txt").write_text(merges)
        lines = self.run_drift("--ticket-pattern", r"\bKEY-\d+")[1]
        self.assertIn("claim · C-1 · judged 0 · follows 0 · breaks 0 · not touched 0 · not judged 0", lines)
        (self.dir / "claims.md").write_text("### C-4 · CONTRIBUTING.md:6 · code · script: todo\n")
        (self.dir / "merges.txt").write_text("\n".join(x for x in merges.splitlines() if not x.startswith("doc")) + "\n")
        self.assertEqual(self.run_drift("--ticket-pattern", r"\bKEY-\d+")[0], 0)

    def test_reads_a_merge_s_first_parent_diff_whatever_its_lines_or_config(self):
        self.git("checkout", "-q", "-b", "side", self.shas[2])
        self.write("src/other.py", "++ not a header\n# TODO later\nTODOS = []\nx = 'TODO'\n")
        self.write("old.txt", "gone\n")
        self.commit("Side work")
        self.git("rm", "-q", "old.txt")
        self.commit("Remove old")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "side", "-m", "Merge pull request #4 from side")
        sha = self.git("rev-parse", "HEAD").strip()
        self.git("config", "diff.noprefix", "true")
        self.git("config", "color.diff", "always")
        found = drift_checks.added(self.repo, sha)
        self.assertIn(("src/other.py", 2, "# TODO later"), found)
        self.assertEqual([f for f in found if f[0] == "old.txt"], [])
        todo = [f for f in found if drift_checks.TODO.search(f[2])]
        self.assertEqual(todo, [("src/other.py", 2, "# TODO later")])

    def test_a_template_section_added_later_judges_only_what_was_opened_after_it(self):
        self.write(".github/PULL_REQUEST_TEMPLATE.md", TEMPLATE + "\n## Checklist\n\n- [ ] done\n")
        self.commit("Add a checklist")
        (self.dir / "claims.md").write_text("### C-7 · .github/PULL_REQUEST_TEMPLATE.md:12 · every change · script: template\n")
        for n in (1, 2):
            (self.dumps / f"pr-000{n}" / "pr.json").write_text(json.dumps({"body": "## Summary", "created_at": "2001-01-01T00:00:00Z"}))
        (self.dumps / "pr-0003" / "pr.json").write_text(json.dumps({"body": "## Summary", "created_at": "2099-01-01T00:00:00Z"}))
        lines = self.run_drift()[1]
        self.assertEqual(lines[0], "claim · C-7 · judged 3 · follows 0 · breaks 1 · not touched 0 · not judged 2 · drift")

    def test_a_template_section_is_dated_to_the_second_and_from_its_first_wording(self):
        for text, when in (("## Checklist\n\n- [ ] done\n", "2030-01-01T23:30:00+0000"),
                           ("## Checklist ##\n\n- [ ] done, and tested\n", "2030-06-01T00:00:00+0000")):
            self.write(".github/PULL_REQUEST_TEMPLATE.md", TEMPLATE + "\n" + text)
            self.git("add", "-A")
            subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "Template"],
                           check=True, env={**os.environ, "GIT_COMMITTER_DATE": when})
        (self.dir / "claims.md").write_text("### C-7 · .github/PULL_REQUEST_TEMPLATE.md:12 · every change · script: template\n")
        for n, opened in ((1, "2030-01-01T23:29:00Z"), (2, "2030-01-01T23:31:00Z"), (3, "2031-02-01T00:00:00Z")):
            (self.dumps / f"pr-000{n}" / "pr.json").write_text(json.dumps({"body": "## Summary", "created_at": opened}))
        lines = self.run_drift()[1]
        self.assertEqual(lines[0], "claim · C-7 · judged 3 · follows 0 · breaks 2 · not touched 0 · not judged 1 · drift")

    def at(self, when: str, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       check=True, capture_output=True, env={**os.environ, "GIT_COMMITTER_DATE": when})

    def test_a_template_section_merged_from_a_branch_or_put_back_is_dated_by_its_last_arrival_on_main(self):
        self.git("checkout", "-q", "-b", "side")
        self.write(".github/PULL_REQUEST_TEMPLATE.md", TEMPLATE + "\n## Checklist\n")
        self.git("add", "-A")
        self.at("2030-01-01T00:00:00+0000", "commit", "-qm", "Add a checklist")
        self.git("checkout", "-q", "main")
        self.at("2030-02-01T00:00:00+0000", "merge", "-q", "--no-ff", "side", "-m", "Merge pull request #9 from side")
        (self.dir / "claims.md").write_text("### C-7 · .github/PULL_REQUEST_TEMPLATE.md:12 · every change · script: template\n")
        for n, opened in ((1, "2030-01-15T00:00:00Z"), (2, "2030-02-02T00:00:00Z"), (3, "2030-05-01T00:00:00Z")):
            (self.dumps / f"pr-000{n}" / "pr.json").write_text(json.dumps({"body": "## Summary", "created_at": opened}))
        self.assertEqual(self.run_drift()[1][0], "claim · C-7 · judged 3 · follows 0 · breaks 2 · not touched 0 · not judged 1 · drift")
        self.write(".github/PULL_REQUEST_TEMPLATE.md", TEMPLATE)
        self.git("add", "-A")
        self.at("2030-03-01T00:00:00+0000", "commit", "-qm", "Drop the checklist")
        self.write(".github/PULL_REQUEST_TEMPLATE.md", TEMPLATE + "\n## Checklist\n")
        self.git("add", "-A")
        self.at("2030-04-01T00:00:00+0000", "commit", "-qm", "Restore the checklist")
        self.assertEqual(self.run_drift()[1][0], "claim · C-7 · judged 3 · follows 0 · breaks 1 · not touched 0 · not judged 2 · drift")

    def test_reads_a_path_with_a_space(self):
        self.write("src/my app.py", "# TODO nothing\n")
        sha = self.commit("Add a spaced file")
        self.assertIn(("src/my app.py", 1, "# TODO nothing"), drift_checks.added(self.repo, sha))

    def test_refuses_what_it_cannot_judge(self):
        cases = {
            "the todo check needs --ticket-pattern": (CLAIMS, ()),
            "a heading marked ` · script:` is not": (CLAIMS.replace("script: history", "script: lint"), ("--ticket-pattern", "x")),
            "a heading marked ` · script:` is not ": (CLAIMS.replace(" CHANGELOG.md src/", ""), ("--ticket-pattern", "x")),
            "is not `### C-n": (CLAIMS.replace("src/", "src/, lib/"), ("--ticket-pattern", "x")),
            "has no `doc NOTES.md:` line": (CLAIMS.replace("CONTRIBUTING.md:4", "NOTES.md:4"), ("--ticket-pattern", "x")),
            "unterminated": (CLAIMS, ("--ticket-pattern", "(")),
            "has no heading or label at or above it": (
                "### C-1 · .github/PULL_REQUEST_TEMPLATE.md:0 · every change · script: template\n", ()),
        }
        for why, (claims, extra) in cases.items():
            with self.subTest(why=why):
                (self.dir / "claims.md").write_text(claims)
                code, lines, err = self.run_drift(*extra)
                self.assertEqual((code, lines), (2, []))
                self.assertIn(why, err)

        (self.dumps / "pr-0001" / "pr.json").write_text(json.dumps({"body": "Ticket: x", "created_at": "2026-10-01"}))
        (self.dir / "claims.md").write_text(CLAIMS)
        code, lines, err = self.run_drift("--ticket-pattern", "x")
        self.assertEqual((code, lines), (2, []))
        self.assertIn("is not like 2026-10-01T12:00:00Z", err)

    def test_refuses_a_template_part_no_commit_added(self):
        real = drift_checks.git
        self.addCleanup(setattr, drift_checks, "git", real)
        drift_checks.git = lambda repo, *args: "" if "log" in args else real(repo, *args)
        with self.assertRaisesRegex(drift_checks.CannotRun, "no commit on main adds the label 'Ticket'"):
            drift_checks.template_part(self.repo, ".github/PULL_REQUEST_TEMPLATE.md", 1, "main")


if __name__ == "__main__":
    unittest.main()
