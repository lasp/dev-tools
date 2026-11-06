"""Tests for scripts/drift_checks.py, on a scratch repository with three merged pull requests."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
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
            (self.dumps / f"pr-000{n}" / "pr.json").write_text(json.dumps({"body": body}))
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
            'break · C-2 · pr-0002 · description · no "how to test" heading',
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

    def test_refuses_what_it_cannot_judge(self):
        cases = {
            "the todo check needs --ticket-pattern": (CLAIMS, ()),
            "no check 'lint'": (CLAIMS.replace("script: history", "script: lint"), ("--ticket-pattern", "x")),
            "changelog names no file, or no code paths": (CLAIMS.replace(" CHANGELOG.md src/", ""), ("--ticket-pattern", "x")),
            "has no `doc NOTES.md:` line": (CLAIMS.replace("CONTRIBUTING.md:4", "NOTES.md:4"), ("--ticket-pattern", "x")),
        }
        for why, (claims, extra) in cases.items():
            with self.subTest(why=why):
                (self.dir / "claims.md").write_text(claims)
                code, lines, err = self.run_drift(*extra)
                self.assertEqual((code, lines), (2, []))
                self.assertIn(why, err)


if __name__ == "__main__":
    unittest.main()
