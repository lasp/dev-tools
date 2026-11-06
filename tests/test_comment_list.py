"""Tests for scripts/comment_list.py."""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("comment_list", ROOT / "scripts" / "comment_list.py")
comment_list = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comment_list)
FIXTURE = ROOT / "tests" / "fixtures" / "pr-0042"
ATTRIBUTION = "🤖 _AI-assisted comment, posted by @alice. AI assistance level: 5/5 (not read by a person)._"


def url(n: int, kind: str = "discussion_r") -> str:
    return f"https://github.com/o/r/pull/7#{kind}{n}"


class CommentList(unittest.TestCase):
    def dump(self, threads=(), reviews=(), comments=(), name="pr-0007") -> Path:
        d = Path(tempfile.mkdtemp()) / name
        d.mkdir()
        self.addCleanup(shutil.rmtree, d.parent)
        (d / "pr.json").write_text(json.dumps({"number": 7}))
        (d / "comments.json").write_text(json.dumps({"review_threads": list(threads)}))
        (d / "reviews.json").write_text(json.dumps(list(reviews)))
        (d / "issue-comments.json").write_text(json.dumps(list(comments)))
        return d

    def run_on(self, d: Path) -> list[dict]:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(comment_list.main([str(d)]), 0)
        listed = json.loads((d / "comment-list.json").read_text())
        self.assertEqual(listed["pr"], int(d.name[3:]))
        return listed["comments"]

    def test_lists_every_comment_with_its_own_authorship(self):
        thread = {"id": "PRRT_a", "is_resolved": True, "is_outdated": False, "comments": [
            {"author": "alice", "body": f"**Should fix** — guard\n\n{ATTRIBUTION}", "created_at": "2026-10-01T10:00:00Z",
             "html_url": url(11), "path": "x.py", "original_line": 5},
            {"author": "bob", "body": "In general, import dependencies directly.", "created_at": "2026-10-01T11:00:00Z",
             "html_url": url(12), "path": "x.py", "line": 9, "original_line": 5},
            {"author": "copilot", "body": "Nit.", "created_at": "2026-10-01T12:00:00Z", "html_url": url(13), "path": "x.py"},
        ]}
        reviews = [
            {"id": 21, "state": "COMMENTED", "body": "Going forward, keep the changelog to user-visible changes.",
             "html_url": url(21, "pullrequestreview-"), "user": {"login": "carol"}, "submitted_at": "2026-10-01T09:00:00Z"},
            {"id": 22, "state": "COMMENTED", "body": "", "html_url": url(22, "pullrequestreview-"), "user": {"login": "bob"}},
        ]
        comments = [{"id": "31", "body": "Thanks!", "html_url": url(31, "issuecomment-"), "created_at": "2026-10-02T09:00:00Z",
                     "user": {"login": "dave"}}]
        got = self.run_on(self.dump([thread], reviews, comments))
        self.assertEqual([(c["id"], c["kind"], c["authorship"]) for c in got], [
            (21, "review", "human"), (11, "thread", "ai-drafted"), (12, "reply", "human"), (13, "reply", "bot"), (31, "comment", "human")])
        reply = got[2]
        self.assertEqual(reply, {"pr": 7, "id": 12, "url": url(12), "author": "bob", "authorship": "human", "kind": "reply",
                                 "thread": "PRRT_a", "path": "x.py", "line": 5, "created": "2026-10-01T11:00:00Z",
                                 "nominated": [], "body": "In general, import dependencies directly."})
        self.assertEqual((got[0]["thread"], got[0]["path"], got[0]["line"]), (None, None, None))
        self.assertEqual(got[3]["line"], None)

    def test_a_person_s_own_for_agents_or_standard_line_is_nominated_and_a_quoted_or_fenced_one_is_not(self):
        body = ("Fixed.\n\nFor agents: install a missing system library in CI; never mock its import.\n"
                "standard: Fill values are read per variable.\n> For agents: quoted from someone else\n"
                "```\nFor agents: shown in code\n```\nFor future agents: not the marker\n- **For agents:** bulleted and bold\n"
                "Standards: not the marker\nFor agents:\n_Standard_: in italics")
        thread = {"id": "PRRT_a", "is_resolved": True, "is_outdated": False, "comments": [
            {"author": "bob", "body": body, "created_at": "2026-10-01T11:00:00Z", "html_url": url(12), "path": "x.py"}]}
        got = self.run_on(self.dump([thread]))
        self.assertEqual(got[0]["nominated"], ["install a missing system library in CI; never mock its import.",
                                               "Fill values are read per variable.", "bulleted and bold", "in italics"])

    def test_the_committed_dump_lists_each_of_its_comments_once(self):
        d = Path(tempfile.mkdtemp()) / "pr-0042"
        self.addCleanup(shutil.rmtree, d.parent)
        shutil.copytree(FIXTURE, d)
        got = self.run_on(d)
        threads = json.loads((FIXTURE / "comments.json").read_text())["review_threads"]
        reviews = [r for r in json.loads((FIXTURE / "reviews.json").read_text()) if (r.get("body") or "").strip()]
        issue = json.loads((FIXTURE / "issue-comments.json").read_text())
        self.assertEqual(len(got), sum(len(t["comments"]) for t in threads) + len(reviews) + len(issue))
        self.assertEqual(len({c["id"] for c in got}), len(got))
        self.assertEqual(got, sorted(got, key=lambda c: (c["created"], c["id"])))

    def test_a_pull_request_no_one_commented_on_names_itself(self):
        self.assertEqual(self.run_on(self.dump()), [])

    def test_refuses_what_it_cannot_list(self):
        good = {"author": "bob", "body": "x", "created_at": "2026-10-01T11:00:00Z", "html_url": url(12), "path": "x.py"}
        cases = {
            "not pr-NNNN": self.dump(name="pr-7"),
            "has no #discussion_r": self.dump([{"id": "PRRT_a", "comments": [{**good, "html_url": "https://x/pull/7"}]}]),
            "has a body but no submitted_at": self.dump(reviews=[{"id": 1, "body": "Hm.", "html_url": "u", "user": {"login": "b"}}]),
            "is given twice, as a thread and a reply": self.dump([{"id": "PRRT_a", "comments": [good, good]}]),
        }
        broken = self.dump()
        (broken / "reviews.json").write_text("{")
        cases["reviews.json cannot be read as JSON"] = broken
        gone = self.dump()
        (gone / "issue-comments.json").unlink()
        cases["issue-comments.json cannot be read"] = gone
        for why, d in cases.items():
            with self.subTest(why=why):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(comment_list.main([str(d)]), 1)
                self.assertIn(why, err.getvalue())
                self.assertFalse((d / "comment-list.json").exists())

    def test_writes_no_list_when_any_dump_is_refused(self):
        good, bad = self.dump(), self.dump(name="pr-0008")
        (bad / "comments.json").write_text("{")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(comment_list.main([str(good), str(bad)]), 1)
        self.assertFalse((good / "comment-list.json").exists())

    def test_refuses_when_no_comment_s_authorship_can_be_told(self):
        refused = comment_list.load_record()
        refused.project_phrases = mock.Mock(side_effect=refused.Unsupported("the default profile is refused"))
        d = self.dump(comments=[{"id": "31", "body": "x", "html_url": url(31, "issuecomment-"),
                                 "created_at": "2026-10-02T09:00:00Z", "user": {"login": "dave"}}])
        err = io.StringIO()
        with mock.patch.object(comment_list, "load_record", return_value=refused), contextlib.redirect_stderr(err):
            self.assertEqual(comment_list.main([str(d)]), 1)
        self.assertIn("the default profile is refused", err.getvalue())
        self.assertFalse((d / "comment-list.json").exists())


if __name__ == "__main__":
    unittest.main()
