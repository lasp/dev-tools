"""Tests for scripts/save_page.py, the hook that saves pull_request_read results. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("save_page", ROOT / "scripts" / "save_page.py")
save_page = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(save_page)


class SavePage(unittest.TestCase):
    def setUp(self):
        self.cwd = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.cwd)])
        subprocess.run(["git", "init", "-q", str(self.cwd)], check=True)
        self.folder = self.cwd / ".review" / "pages" / "org-repo" / "pr-0094"

    def event(self, method, response, cwd=None, **args):
        return {
            "hook_event_name": "PostToolUse",
            "cwd": str(cwd or self.cwd),
            "tool_name": "mcp__github-org__pull_request_read",
            "tool_input": {"method": method, "owner": "org", "repo": "repo", "pullNumber": 94, **args},
            "tool_response": response,
        }

    def call(self, method, response, cwd=None, **args):
        event = self.event(method, response, cwd, **args)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), unittest.mock.patch("sys.stdin", io.StringIO(json.dumps(event))):
            rc = save_page.main()
        self.assertEqual(rc, 0)
        text = out.getvalue()
        return json.loads(text)["hookSpecificOutput"]["additionalContext"] if text else None

    def page(self, cursor, more):
        return json.dumps({"pageInfo": {"endCursor": cursor, "hasNextPage": more}, "review_threads": [], "totalCount": 0})

    def test_each_result_is_written_byte_for_byte_under_the_name_a_dump_reads(self):
        body = '{"number":94,"body":"na\\u00efve \\"quoted\\"\\n"}'
        self.assertEqual(self.call("get", body), f"saved get as {self.folder}/get.json")
        self.assertEqual(self.call("get_reviews", "[]", perPage=100, page=2), f"saved get_reviews as {self.folder}/get_reviews-2.json")
        self.assertEqual(self.call("get_comments", "[]"), f"saved get_comments as {self.folder}/get_comments-1.json")
        self.assertEqual((self.folder / "get.json").read_text(), body)

    def test_review_comment_pages_are_numbered_by_the_cursor_they_follow(self):
        self.call("get_review_comments", self.page("A", True))
        self.call("get_review_comments", self.page("B", True), after="A")
        note = self.call("get_review_comments", self.page("C", False), after="B")
        self.assertEqual(note, f"saved get_review_comments as {self.folder}/get_review_comments-3.json")
        self.call("get_review_comments", self.page("Z", False))
        self.assertEqual(json.loads((self.folder / "get_review_comments-1.json").read_text())["pageInfo"]["endCursor"], "Z")

    def test_a_get_after_its_siblings_removes_none_of_their_pages(self):
        self.call("get_comments", "[]")
        self.call("get_reviews", "[]")
        self.call("get", "{}")
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["get.json", "get_comments-1.json", "get_reviews-1.json"])

    def test_other_methods_are_left_alone(self):
        self.assertIsNone(self.call("get_diff", "diff --git"))
        self.assertFalse((self.cwd / ".review").exists())

    def test_a_session_in_a_subdirectory_saves_at_the_top_level_and_git_ignores_it(self):
        (self.cwd / "pkg").mkdir()
        self.assertEqual(self.call("get", "{}", cwd=self.cwd / "pkg"), f"saved get as {self.folder}/get.json")
        self.assertEqual(subprocess.run(["git", "-C", str(self.cwd), "check-ignore", "-q", ".review/pages/x"]).returncode, 0)

    def test_the_shell_hook_prints_the_note(self):
        out = subprocess.run(["bash", str(ROOT / "hooks" / "save-page.sh")], input=json.dumps(self.event("get", "{}")),
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"], f"saved get as {self.folder}/get.json")

    def test_what_cannot_be_saved_says_so_and_writes_nothing(self):
        note = self.call("get_review_comments", self.page("B", False), after="unknown")
        self.assertEqual(note, "not saved: get_review_comments: no saved page ends at the cursor unknown")
        self.assertEqual(self.call("get", [{"type": "text", "text": "{}"}]), "not saved: get: the response is a list, not text")
        self.assertTrue(self.call("get_reviews", "[]", page="two").startswith("not saved: get_reviews: ValueError"))
        self.assertEqual([p.name for p in self.folder.iterdir()], [])
        self.assertTrue(self.call("get", "{}", pullNumber=None).startswith("not saved: get: TypeError"))
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(outside)])
        self.assertEqual(self.call("get", "{}", cwd=outside), f"not saved: get: {outside} is not in a git repository")
        self.assertFalse((outside / ".review").exists())

    def test_a_size_limit_notice_is_not_saved_as_a_page(self):
        self.call("get_reviews", "[]", perPage=100, page=1)
        notice = "Error: result (61,204 tokens) exceeds maximum allowed tokens (25,000). Use pagination."
        note = self.call("get_reviews", notice, perPage=100, page=1)
        self.assertEqual(note, f"not saved: get_reviews: the response is not JSON, so not a page: {notice!r}")
        self.assertEqual((self.folder / "get_reviews-1.json").read_text(), "[]")

    def test_a_first_review_comments_page_removes_an_earlier_runs_pages(self):
        self.call("get_review_comments", self.page("A", True))
        self.call("get_review_comments", self.page("B", True), after="A")
        self.call("get_review_comments", self.page("C", False), after="B")
        self.call("get_reviews", "[]")
        self.call("get_review_comments", self.page("B", False))
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["get_review_comments-1.json", "get_reviews-1.json"])
        self.assertEqual(self.call("get_review_comments", self.page("D", False), after="B"), f"saved get_review_comments as {self.folder}/get_review_comments-2.json")

    def test_a_write_that_fails_says_so(self):
        self.folder.parent.mkdir(parents=True)
        self.folder.write_text("in the way")
        self.assertTrue(self.call("get", "{}").startswith("not saved: get: FileExistsError"))

    def test_input_that_is_not_json_is_ignored(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), unittest.mock.patch("sys.stdin", io.StringIO("not json")):
            self.assertEqual(save_page.main(), 0)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
