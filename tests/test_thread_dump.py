"""Tests for scripts/thread_dump.py. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("thread_dump", ROOT / "scripts" / "thread_dump.py")
thread_dump = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(thread_dump)

GET = {"number": 7, "user": {"login": "alice"}, "state": "closed", "draft": False, "merged": True,
       "merged_at": "2026-10-14T15:26:17Z", "head": {"ref": "fix", "sha": "c" * 40}, "body": "Fix the loader.\n", "additions": 3}
REVIEW = {"id": 1, "state": "APPROVED", "body": "| File | Description |\r\n| --- | --- |", "html_url": "https://github.com/o/r/pull/7#pullrequestreview-1",
          "user": {"login": "bob"}, "commit_id": "a" * 40, "submitted_at": "2026-10-14T13:19:04Z", "author_association": "MEMBER"}
COMMENT = {"author": "bob", "body": "Why?", "created_at": "2026-10-14T13:07:18Z", "html_url": "https://github.com/o/r/pull/7#discussion_r1",
           "line": 82, "original_line": 81, "path": "pkg/a.py", "updated_at": "2026-10-14T13:19:04Z"}
THREAD = {"id": "PRRT_synthetic-002", "is_resolved": True, "is_outdated": False, "is_collapsed": True, "total_count": 1, "comments": [COMMENT]}
ISSUE = {"id": 5, "body": "Looks good.", "html_url": "https://github.com/o/r/pull/7#issuecomment-5", "user": {"login": "carol"}, "created_at": "2026-10-14T12:00:00Z"}


class RealPages(unittest.TestCase):
    """Slices of the GitHub MCP server's pages as it returns them, names and text replaced: it leaves
    out an empty field rather than sending null, so an open pull request's `get` has no `merged_at`,
    and a review posted with a batch of thread replies has no `body`."""

    def test_the_servers_pages_build_a_dump_record_py_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp)
            shutil.copytree(ROOT / "tests/fixtures/thread-pages", dump / "pages")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(thread_dump.main([str(dump)]), 0)
            self.assertEqual((dump / "pr.json").read_text(), (dump / "pages/get.json").read_text())
            self.assertEqual((dump / "body.md").read_text(), "")
            reviews = json.loads((dump / "reviews.json").read_text())
            self.assertEqual(reviews, json.loads((dump / "pages/get_reviews-1.json").read_text()))
            self.assertNotIn("body", reviews[1])
            threads = json.loads((dump / "comments.json").read_text())["review_threads"]
            self.assertEqual((threads[0]["comments"][0]["line"], threads[1]["comments"][0]["original_start_line"]), (82, 146))
            args = [f"--{flag}={dump / name}" for flag, name in (("pr", "pr.json"), ("reviews", "reviews.json"), ("comments", "comments.json"),
                                                               ("issue-comments", "issue-comments.json"), ("body", "body.md"))]
            out = subprocess.run([sys.executable, str(ROOT / "scripts/record.py"), "--state", *args, "--repo", "o/r"], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("state: open", out.stdout)


class Dump(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dump = Path(tmp.name)
        self.pages = self.dump / "pages"
        self.pages.mkdir()
        self.page("get.json", GET)
        self.page("get_reviews-1.json", [REVIEW])
        self.page("get_review_comments-1.json", {"pageInfo": {"hasNextPage": True, "endCursor": "x"}, "review_threads": [THREAD], "totalCount": 2})
        self.page("get_review_comments-2.json", {"pageInfo": {"hasNextPage": False}, "review_threads": [{**THREAD, "id": "PRRT_b"}], "totalCount": 2})
        self.page("get_comments-1.json", [ISSUE])

    def page(self, name, data):
        (self.pages / name).write_text(json.dumps(data))

    def run_it(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = thread_dump.main([str(self.dump)])
        return rc, err.getvalue()

    def test_the_pages_join_into_the_dump_with_every_field_kept(self):
        self.assertEqual(self.run_it(), (0, ""))
        self.assertEqual(json.loads((self.dump / "pr.json").read_text()), GET)
        self.assertEqual(json.loads((self.dump / "reviews.json").read_text()), [REVIEW])
        self.assertEqual(json.loads((self.dump / "comments.json").read_text()), {"review_threads": [THREAD, {**THREAD, "id": "PRRT_b"}]})
        self.assertEqual(json.loads((self.dump / "issue-comments.json").read_text()), [ISSUE])
        self.assertEqual((self.dump / "body.md").read_text(), "Fix the loader.\n")

    def test_a_full_page_of_reviews_needs_the_next(self):
        self.page("get_reviews-1.json", [{**REVIEW, "id": n} for n in range(100)])
        self.assertEqual(self.run_it(), (1, "thread_dump.py: get_reviews-1.json holds 100 items: the pages stop early\n"))
        self.page("get_reviews-2.json", [])
        self.assertEqual(self.run_it()[0], 0)
        self.assertEqual(len(json.loads((self.dump / "reviews.json").read_text())), 100)

    def test_a_retyped_page_missing_a_field_is_refused_and_nothing_is_written(self):
        for name, data, says in (
            ("get_reviews-1.json", [{k: v for k, v in REVIEW.items() if k != "html_url"}], "get_reviews-1.json item 0 has no 'html_url'"),
            ("get_review_comments-2.json", {"pageInfo": {"hasNextPage": False}, "review_threads": [{**THREAD, "comments": [{k: v for k, v in COMMENT.items() if k != "path"}]}], "totalCount": 2},
             "thread PRRT_synthetic-002 comment 0 has no 'path'"),
            ("get.json", {**GET, "head": {"ref": "fix"}}, "get.json has no 'head.sha'"),
            ("get_comments-1.json", [{k: v for k, v in ISSUE.items() if k != "user"}], "get_comments-1.json item 0 has no 'user.login'"),
        ):
            with self.subTest(name=name):
                self.setUp()
                self.page(name, data)
                rc, err = self.run_it()
                self.assertEqual(rc, 1)
                self.assertIn(says, err)
                self.assertEqual(sorted(p.name for p in self.dump.iterdir()), ["pages"])

    def test_paging_that_stops_short_or_skips_a_page_is_refused(self):
        self.page("get_review_comments-2.json", {"pageInfo": {"hasNextPage": False}, "review_threads": [], "totalCount": 2})
        self.assertEqual(self.run_it(), (1, "thread_dump.py: the pages hold 1 threads, but totalCount is 2\n"))
        (self.pages / "get_review_comments-2.json").rename(self.pages / "get_review_comments-3.json")
        self.assertEqual(self.run_it(), (1, "thread_dump.py: the get_review_comments pages are [1, 3], not 1 to 2\n"))
        (self.pages / "get_review_comments-3.json").unlink()
        self.assertEqual(self.run_it(), (1, "thread_dump.py: get_review_comments-1.json says hasNextPage True, but it is page 1 of 1\n"))
        self.page("get_review_comments-1.json", {"pageInfo": {"hasNextPage": False}, "review_threads": [THREAD], "totalCount": 1})
        (self.pages / "get_comments-1.json").write_text('[{"id": 5, "body": "Looks')
        self.assertIn("get_comments-1.json cannot be read as JSON", self.run_it()[1])


if __name__ == "__main__":
    unittest.main()
