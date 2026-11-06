"""Tests for scripts/next_phase.py, one case per row of its table. Run with `python3 -m unittest discover -s tests`."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pr-0042"

_spec = importlib.util.spec_from_file_location("next_phase", ROOT / "scripts" / "next_phase.py")
next_phase = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(next_phase)
_spec = importlib.util.spec_from_file_location("record", ROOT / "scripts" / "record.py")
record = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record)

HEAD = "c" * 40
# A plan file the person approved at the plan gate.
PLAN = "# Plan\nApproved by: a-reviewer\n"
HEADER = "id | key, or opener | severity, or resolved | headline | path:line | verdict | contested | replies after | proposed, or outdated | after the verdict | judged"


def state(
    rows: list[tuple], draft: str = "false", st: str = "open", reviewed: str = HEAD, ticket: str = "PROJ-7", n: int = 7, author: str = "a-author"
) -> str:
    """A state block for pull request n with one row per (verdict, contested, replies after[, after the verdict[, judged]]);
    `reviewed` empty is a pull request with no findings review."""
    body = [f"## pr-{n:04d} — state", "contract: 6", f"head: {HEAD}", f"draft: {draft}", f"state: {st}", f"author: {author}"]
    body += [f"ticket: Ticket: {ticket} · x" if ticket else "ticket: none", "build: Build: passed"]
    body += [f"findings review: 1 reviewed: {reviewed}" if reviewed else "findings review: none", f"threads: {len(rows)}", HEADER]
    body += [" | ".join([f"PRRT_{i}", "R-001/x.py::f", "should-fix", "h", "x.py:1", *r[:3], "none", r[3] if len(r) > 3 else "", r[4] if len(r) > 4 else "no"]) for i, r in enumerate(rows)]
    return "\n".join(body) + "\n"


# The working directory's repository's standard records this workflow, which the rows route by.
WORKFLOW = """jira:
  statuses:
    - {name: New, next: ticket-draft, role: filed}
    - {name: To Do, next: implement-change, role: approved}
    - {name: Upcoming, next: implement-change}
    - {name: Exploration, next: ticket-draft}
    - {name: Under Development, next: implement-change, role: implementation}
    - {name: External Needs, next: nothing}
    - {name: In Review, next: nothing}
    - {name: Done, next: nothing, role: finished}
    - {name: Abandoned, next: nothing, role: abandoned}
  pr_statuses: [Under Development, External Needs, In Review]
"""


def setUpModule():
    here = Path(tempfile.mkdtemp())
    unittest.addModuleCleanup(shutil.rmtree, here)
    subprocess.run(["git", "init", "-q", str(here)], check=True)
    subprocess.run(["git", "-C", str(here), "remote", "add", "origin", "git@github.com:someone/routed.git"], check=True)
    (here / "standards").mkdir()
    (here / "standards/profile.yaml").write_text(WORKFLOW)
    unittest.addModuleCleanup(os.chdir, os.getcwd())
    os.chdir(here)


class Rows(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.plan = self.tmp / "plan.md"

    def fields(self, **over: str) -> Path:
        f = {"ticket": "PROJ-7", "branch": "PROJ-7-x", "context": ".review/context/PROJ-7.md", "plan": str(self.plan)}
        f |= {"base": "main", "outcome": "", "outcome_reopened": "", "build_branch": "PROJ-7-x", "dirty": "false", "lock": ""}
        f |= {"part": "", "reopened": "", "slug": "", "elsewhere": ""}
        f |= over
        path = self.tmp / f"fields-{len(list(self.tmp.glob('fields-*')))}.txt"
        path.write_text("".join(f"{k}={v}\n" for k, v in f.items()))
        return path

    def stack(self, text: str, criteria: str = "AC-1,AC-2,AC-3") -> tuple[str, ...]:
        (self.tmp / "stack.txt").write_text(text)
        return ("--stack", str(self.tmp / "stack.txt"), "--criteria", criteria)

    def run_it(self, fields: Path, state_text: str | None = None, *extra: str) -> tuple[int, str]:
        args = ["--fields", str(fields)]
        if state_text is not None:
            (self.tmp / "state.txt").write_text(state_text)
            args += ["--state", str(self.tmp / "state.txt")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = next_phase.main(args + list(extra))
        return rc, out.getvalue()

    def why(self, *args, **kw) -> tuple[str, str]:
        rc, out = self.run_it(*args, **kw)
        self.assertEqual(rc, 0, out)
        got = dict(line.split(": ", 1) for line in out.splitlines()[:3])
        return got["phase"], got["why"]

    def test_the_lock_is_named_only_before_the_two_phases_that_take_it(self):
        rc, out = self.run_it(self.fields(lock="pr-fix"))
        self.assertIn("phase: implement-change\nargument: PROJ-7\nwhy: plan\nlock: pr-fix\n", out)
        rc, out = self.run_it(self.fields(lock="implement-change"), state([]))
        self.assertIn("phase: nothing\nargument: 7\nwhy: answered\nlock: none\n", out)
        rc, out = self.run_it(self.fields(lock="pr-fix"), state([], reviewed="d" * 40))
        self.assertIn("why: pr-review\nlock: none\n", out)
        rc, out = self.run_it(self.fields())
        self.assertIn("lock: none\n", out)

    def test_merged_pull_request(self):
        self.assertEqual(self.why(self.fields(), state([], st="merged")), ("nothing", "pr-closed"))
        self.assertEqual(self.why(self.fields(), state([], st="closed")), ("nothing", "pr-closed"))

    def test_a_merged_single_pull_request_is_not_offered_another(self):
        self.plan.write_text(PLAN)
        built = self.fields(outcome="Build: passed")
        self.assertEqual(self.why(built, state([], st="merged")), ("nothing", "pr-closed"))
        self.assertEqual(self.why(built, state([], st="closed")), ("nothing", "pr-closed"))
        self.assertEqual(self.why(self.fields(outcome="Build: review cap reached"), state([], st="merged")), ("nothing", "pr-closed"))
        self.assertEqual(self.why(built, "pull request: none\n"), ("pr-create", "pr-create"))

    def test_no_review_of_the_head_from_the_pr_0042_fixture(self):
        args = ["--state", "--pr", FIXTURE / "pr.json", "--reviews", FIXTURE / "reviews.json"]
        args += ["--comments", FIXTURE / "comments.json", "--issue-comments", FIXTURE / "issue-comments.json", "--body", FIXTURE / "body.md", "--repo", "o/r"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            record.main([str(a) for a in args])
        rc, printed = self.run_it(self.fields(), "## pr-0042 — state\n" + out.getvalue())
        self.assertIn("phase: pr-review\nargument: 42\nwhy: pr-review\n", printed)

    def state_file(self, text: str) -> Path:
        (self.tmp / "state.txt").write_text(text)
        return self.tmp / "state.txt"

    def local(self, head: str, posting: str) -> tuple[str, str]:
        (self.tmp / "local.md").write_text(f"Head: {head}\nPosting: {posting}\n\n## Progress\n")
        return ("--local-review", str(self.tmp / "local.md"))

    def test_a_review_kept_here_asks_whether_to_post_until_the_person_chooses(self):
        unreviewed = state([], reviewed="d" * 40)
        self.assertEqual(self.why(self.fields(), unreviewed, *self.local(HEAD, "undecided")), ("pr-review", "review-unposted"))
        self.assertEqual(self.why(self.fields(), unreviewed, *self.local(HEAD[:12], "declined")), ("nothing", "answered"))
        self.assertEqual(self.why(self.fields(), state([("unanswered", "no", "0")], reviewed="d" * 40), *self.local(HEAD, "declined")), ("pr-fix", "walk"))
        # A local review of an earlier head, or one marked posted that GitHub does not show, reviews again.
        self.assertEqual(self.why(self.fields(), unreviewed, *self.local("e" * 40, "declined")), ("pr-review", "pr-review"))
        self.assertEqual(self.why(self.fields(), unreviewed, *self.local("e" * 40, "undecided")), ("pr-review", "pr-review"))
        self.assertEqual(self.why(self.fields(), unreviewed, *self.local(HEAD, "posted https://x")), ("pr-review", "pr-review"))

    def test_a_local_review_it_cannot_read_exits_1(self):
        for text, refusal in (("Posting: declined\n", "no 'Head: <sha>' line"), (f"Head: {HEAD}\nPosting: maybe\n", "Posting: line is not")):
            with self.subTest(text=text):
                (self.tmp / "local.md").write_text(text)
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    rc = next_phase.main(["--fields", str(self.fields()), "--state", str(self.state_file(state([], reviewed="d" * 40))), "--local-review", str(self.tmp / "local.md")])
                self.assertEqual(rc, 1)
                self.assertIn(refusal, err.getvalue())

    def test_a_local_review_from_before_the_posting_line_routes_as_none(self):
        (self.tmp / "local.md").write_text(f"Head: {HEAD}\n\nUnposted draft.\n")
        self.assertEqual(self.why(self.fields(), state([], reviewed="d" * 40), "--local-review", str(self.tmp / "local.md")), ("pr-review", "pr-review"))

    def test_reviewers_answer_first(self):
        self.assertEqual(self.why(self.fields(), state([("unanswered", "no", "0")]), "--reviewed-this-loop"), ("nothing", "reviewers-first"))
        self.assertEqual(self.why(self.fields(), state([("unanswered", "no", "0")], draft="true"), "--reviewed-this-loop"), ("pr-fix", "walk"))

    def test_a_column_holding_a_pipe_does_not_shift_the_verdict(self):
        text = state([("agree", "no", "1")]).replace(" | h | x.py:1 | agree", " | use a \\| b here | x.py:1 | unanswered")
        self.assertEqual(self.why(self.fields(), text), ("pr-fix", "walk"))
        text = state([("disagree", "no", "0", "the frame \\| the epoch | agree | no | 0 | is fixed")])
        self.assertEqual(self.run_it(self.fields(), text)[0], 1)
        text = state([("disagree", "no", "0", "the frame \\| agree \\| no \\| 0 \\| is fixed")])
        self.assertEqual(self.why(self.fields(), text), ("nothing", "answered"))
        self.assertEqual(self.run_it(self.fields(), state([]) + "PRRT_x | broken row\n")[0], 1)

    def test_an_empty_after_the_verdict_column_reads(self):
        text = state([("agree", "no", "0")])
        self.assertIn("| none |  | no\n", text)
        self.assertEqual(self.why(self.fields(), text), ("pr-fix", "fix"))

    def test_a_judged_agree_that_says_the_change_was_made_is_answered(self):
        done = ("agree", "no", "0", "Thanks, done.", "yes, a-author, done: says the change was made")
        self.assertEqual(self.why(self.fields(), state([done])), ("nothing", "answered"))
        judged = ("agree", "no", "0", "Good catch.", "yes, a-author: agrees in their own words")
        self.assertEqual(self.why(self.fields(), state([judged])), ("pr-fix", "fix"))

    def test_a_refused_judgments_line_after_the_table_still_routes(self):
        text = state([("agree", "no", "0")]) + "judgments refused: a judgment on PRRT_1 reads a reply outside its eligible\n"
        self.assertEqual(self.why(self.fields(), text), ("pr-fix", "fix"))

    def test_a_fix_taken_as_made_from_a_judged_reply_is_named_to_confirm(self):
        done = ("agree", "no", "0", "Thanks, done.", "yes, a-author, done: says the change was made")
        for draft, why in (("false", "answered"), ("true", "mark-ready")):
            with self.subTest(draft=draft):
                rc, out = self.run_it(self.fields(), state([done], draft=draft))
                self.assertIn(f"why: {why}\n", out)
                self.assertIn("to confirm: PRRT_0", out)
        rc, out = self.run_it(self.fields(), state([("agree", "no", "0", "fixed in 3f2c1ab9d0e4")]))
        self.assertIn("why: answered\n", out)
        self.assertNotIn("to confirm", out)

    def test_a_reply_the_judge_could_not_read_walks(self):
        row = ("unparsed", "no", "1", "", "unclear: asks a question back")
        self.assertEqual(self.why(self.fields(), state([row])), ("pr-fix", "walk"))

    def test_a_judged_column_it_does_not_read_exits_1(self):
        row = ("agree", "no", "0", "", "maybe")
        self.assertEqual(self.run_it(self.fields(), state([row]))[0], 1)

    def test_walk_unanswered_unparsed_contested_or_a_discuss_with_a_reply_after(self):
        for row in (("unanswered", "no", "0"), ("unparsed", "no", "1"), ("agree", "yes", "1"), ("discuss", "no", "1")):
            with self.subTest(row=row):
                self.assertEqual(self.why(self.fields(), state([row])), ("pr-fix", "walk"))
        self.assertEqual(self.why(self.fields(), state([("discuss", "no", "0")])), ("nothing", "answered"))
        self.assertEqual(self.why(self.fields(), state([("none", "no", "0")])), ("nothing", "answered"))

    def test_fix_agreed_threads(self):
        self.assertEqual(self.why(self.fields(), state([("agree", "no", "0"), ("disagree", "no", "0")])), ("pr-fix", "fix"))

    def test_an_agree_that_names_its_commit_is_not_fixed_again(self):
        rows = [("agree", "no", "0", "Renamed in abc1234.")]
        self.assertEqual(self.why(self.fields(), state(rows)), ("nothing", "answered"))
        # pr-fix's `Agree, fixed in <sha>` names a short sha of all digits or all letters too.
        for text in ("fixed in 1234567: x.py", "Fixed in abcdefa: x.py"):
            with self.subTest(text=text):
                self.assertEqual(self.why(self.fields(), state([("agree", "no", "0", text)])), ("nothing", "answered"))
        for text in ("use 3600000 ms as the bound", "the defaced frame"):
            with self.subTest(text=text):
                self.assertEqual(self.why(self.fields(), state([("agree", "no", "0", text)])), ("pr-fix", "fix"))

    def test_an_agree_in_a_follow_up_gets_its_reply_then_stops(self):
        self.assertEqual(self.why(self.fields(), state([("agree", "no", "0", "in a follow-up (PROJ-900)")])), ("pr-fix", "follow-up"))
        both = [("agree", "no", "0", "in a follow-up (PROJ-900)"), ("agree", "no", "0")]
        rc, out = self.run_it(self.fields(), state(both))
        self.assertIn("why: fix\n", out)
        self.assertIn("1 agreed thread(s) to fix", out)
        self.assertEqual(self.why(self.fields(), state([("agree", "no", "1", "in a follow-up (PROJ-900)")])), ("nothing", "answered"))

    def test_an_agree_that_carries_its_response_is_answered(self):
        for text in ("reply only: the import order is pinned", "follow-up in PROJ-900: this pull request leaves it unchanged",
                     "moved to #58: part 2 carries the frame change", "Moved to acme/geolib: the helper is generic"):
            with self.subTest(text=text):
                self.assertEqual(self.why(self.fields(), state([("agree", "no", "0", text)])), ("nothing", "answered"))
        # A form with no response after it, or none of the forms, is not the reply yet.
        for text, why in (("", "fix"), ("reply only:", "fix"), ("moved to #58", "fix"), ("only a reply: the order is pinned", "fix"),
                          ("follow-up in PROJ-900", "follow-up"), ("follow-up in PROJ-900: ", "follow-up")):
            with self.subTest(text=text):
                self.assertEqual(self.why(self.fields(), state([("agree", "no", "0", text)])), ("pr-fix", why))

    def test_one_agreed_reply_answers_its_thread_in_every_order(self):
        """a-author is the pull request's author. Their one reply carrying the response answers the
        thread, before or after a reviewer's reply, where a bare Agree alone is still to fix."""
        sign = "\n\n🤖 _AI-assisted comment, posted by @a-author. AI slop score: 5/5._"
        opener = {"body": "**Should fix** — a finding\n\n<details><summary>Standard</summary>\n\nkey: `R-001/x.py::f`\n</details>\n\n"
                  "🤖 _AI-assisted comment, posted by @a-reviewer. AI slop score: 5/5._", "path": "x.py", "original_line": 3,
                  "author": "a-reviewer", "created_at": "2026-10-01T12:00:00Z"}
        pr = {"number": 7, "state": "open", "draft": False, "merged": False, "user": {"login": "a-author"}, "head": {"ref": "PROJ-7-x", "sha": HEAD}}
        review = {"id": 1, "state": "COMMENTED", "body": f"## Review\nreviewed: {HEAD}\n\n🤖 _AI-assisted comment, posted by @a-reviewer. AI slop score: 5/5._", "html_url": "https://github.com/o/r/pull/7#r1", "submitted_at": "2026-10-01T12:00:00Z"}

        def routed(*replies: tuple[str, str]) -> tuple[str, str]:
            comments = [{"body": b, "path": "x.py", "author": w, "created_at": "2026-10-01T13:00:00Z"} for w, b in replies]
            printed = record.state(pr, [review], [{"id": "PRRT_f", "is_resolved": False, "is_outdated": False, "comments": [opener, *comments]}], "Ticket: PROJ-7 · x\n", "o/r")
            return self.why(self.fields(), "## pr-0007 — state\n" + "\n".join(printed) + "\n")

        for first in ("Agree, fixed in abc1234: x.py raises now.", "Agree, reply only: the import order is pinned for the loader.",
                      "Agree, follow-up in PROJ-900: this pull request leaves it unchanged.", "Agree, moved to #58: part 2 carries it."):
            with self.subTest(reply=first):
                self.assertEqual(routed(("a-author", first + sign)), ("nothing", "answered"))
                self.assertEqual(routed(("a-reviewer", "Agree."), ("a-author", first + sign)), ("nothing", "answered"))
                self.assertEqual(routed(("a-author", first + sign), ("a-reviewer", "Disagree, not here")), ("nothing", "answered"))
        self.assertEqual(routed(("a-author", "Agree." + sign)), ("pr-fix", "fix"))
        self.assertEqual(routed(("a-author", "Agree." + sign), ("a-author", "The import order is pinned for the loader." + sign)), ("nothing", "answered"))

    def test_record_states_rows_for_a_persons_fixed_thread_and_a_reason_holding_a_pipe(self):
        sign = "\n\n🤖 _AI-assisted comment, posted by @a-author. AI assistance level: 5/5 (not read by a person)._"
        person = {
            "id": "PRRT_p", "is_resolved": False, "is_outdated": False,
            "comments": [
                {"body": "Rename this?", "path": "x.py", "original_line": 5, "author": "a-reviewer", "created_at": "2026-10-01T12:00:00Z"},
                {"body": "Agree. Renamed in abc1234." + sign, "path": "x.py", "author": "a-author", "created_at": "2026-10-01T13:00:00Z"},
            ],
        }
        finding = {
            "id": "PRRT_f",
            "comments": [
                {"body": "**Should fix** — a finding\n\n<details><summary>Standard</summary>\n\nkey: `R-001/x.py::f`\n</details>\n\n"
                 "🤖 _AI-assisted comment, posted by @a-author. AI assistance level: 5/5 (not read by a person)._", "path": "x.py", "original_line": 3,
                 "author": "a-author", "created_at": "2026-10-01T12:00:00Z"},
                {"body": "Disagree, a | b is the frame's own notation", "path": "x.py", "author": "a-reviewer", "created_at": "2026-10-01T13:00:00Z"},
            ],
        }
        pr = {"number": 7, "state": "open", "draft": False, "merged": False, "user": {"login": "a-author"}, "head": {"ref": "PROJ-7-x", "sha": HEAD}}
        review = {"id": 1, "state": "COMMENTED", "body": f"## Review\nreviewed: {HEAD}\n\n🤖 _AI-assisted comment, posted by @a-author. AI assistance level: 5/5 (not read by a person)._", "html_url": "https://github.com/o/r/pull/7#r1", "submitted_at": "2026-10-01T12:00:00Z"}
        printed = record.state(pr, [review], [person, finding], "Ticket: PROJ-7 · x\n", "o/r")
        self.assertIn("a \\| b is the frame's own notation", printed[-1])
        rc, out = self.run_it(self.fields(), "## pr-0007 — state\n" + "\n".join(printed) + "\n")
        self.assertIn("why: answered\n", out)

    def test_a_discuss_the_author_answered_last_waits_on_the_reviewer(self):
        opener = {"body": "**Should fix** — a finding\n\n<details><summary>Standard</summary>\n\nkey: `R-001/x.py::f`\n</details>\n\n"
                  "🤖 _AI-assisted comment, posted by @a-author. AI assistance level: 5/5 (not read by a person)._", "path": "x.py", "original_line": 3,
                  "author": "a-author", "created_at": "2026-10-01T12:00:00Z"}
        pr = {"number": 7, "state": "open", "draft": False, "merged": False, "user": {"login": "a-author"}, "head": {"ref": "PROJ-7-x", "sha": HEAD}}
        review = {"id": 1, "state": "COMMENTED", "body": f"## Review\nreviewed: {HEAD}\n\n🤖 _AI-assisted comment, posted by @a-author. AI assistance level: 5/5 (not read by a person)._", "html_url": "https://github.com/o/r/pull/7#r1", "submitted_at": "2026-10-01T12:00:00Z"}

        def routed(*replies: tuple[str, str]) -> tuple[str, str]:
            comments = [{"body": b, "path": "x.py", "author": w, "created_at": "2026-10-01T13:00:00Z"} for w, b in replies]
            printed = record.state(pr, [review], [{"id": "PRRT_f", "comments": [opener, *comments]}], "Ticket: PROJ-7 · x\n", "o/r")
            return self.why(self.fields(), "## pr-0007 — state\n" + "\n".join(printed) + "\n")

        self.assertEqual(routed(("a-reviewer", "Discuss, why here?")), ("nothing", "answered"))
        self.assertEqual(routed(("a-reviewer", "Discuss, why here?"), ("a-author", "Because the frame is fixed.")), ("nothing", "answered"))
        self.assertEqual(routed(("a-reviewer", "Discuss, why here?"), ("a-author", "Because."), ("a-reviewer", "Still unclear.")), ("pr-fix", "walk"))

    def test_a_draft_with_every_thread_answered(self):
        self.assertEqual(self.why(self.fields(), state([("agree", "no", "1")], draft="true")), ("nothing", "mark-ready"))

    def test_every_thread_answered_names_the_discuss_threads(self):
        rc, out = self.run_it(self.fields(), state([("agree", "no", "1"), ("discuss", "no", "0")]))
        self.assertIn("why: answered\n", out)
        self.assertIn("still in discussion: PRRT_1", out)

    def test_no_context_page(self):
        self.assertEqual(self.why(self.fields(context="")), ("ticket-draft", "ticket-draft"))
        self.assertEqual(self.why(self.fields(context=""), None, "--ticket-status", "New"), ("ticket-draft", "ticket-draft"))
        self.assertEqual(self.why(self.fields(context=""), None, "--ticket-status", "To Do"), ("implement-change", "ticket-to-do"))
        self.assertEqual(self.why(self.fields(context=""), None, "--ticket-status", "Upcoming"), ("implement-change", "ticket-to-do"))
        self.assertEqual(self.why(self.fields(context=""), None, "--ticket-status", "Exploration"), ("ticket-draft", "ticket-draft"))
        for status in ("Done", "Abandoned"):
            with self.subTest(status=status):
                self.assertEqual(self.why(self.fields(context=""), None, "--ticket-status", status), ("nothing", "ticket-closed"))
        self.assertEqual(self.run_it(self.fields(context=""), None, "--ticket-status", "Shipped")[0], 1)

    def test_the_statuses_are_the_standards(self):
        plugin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plugin)
        (plugin / "scripts").mkdir()
        shutil.copy(ROOT / "scripts/profile.py", plugin / "scripts")
        (plugin / "standards").mkdir()
        shutil.copy(ROOT / "standards/default-profile.yaml", plugin / "standards")
        repo = self.tmp / "own"
        (repo / "standards").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:example-org/own.git"], check=True)
        (repo / "standards/profile.yaml").write_text(
            "jira:\n  statuses:\n    - {name: Triage, next: implement-change, role: filed}\n"
            "    - {name: To Do, next: implement-change, role: approved}\n"
            "    - {name: Under Development, next: implement-change, role: implementation}\n"
            "    - {name: Done, next: nothing, role: finished}\n    - {name: Abandoned, next: nothing, role: abandoned}\n"
            "  pr_statuses: [Under Development]\n")
        old, cwd = next_phase.ROOT, os.getcwd()
        self.addCleanup(setattr, next_phase, "ROOT", old)
        self.addCleanup(os.chdir, cwd)
        next_phase.ROOT = plugin
        os.chdir(repo)
        self.assertEqual(self.why(self.fields(context=""), None, "--ticket-status", "Triage"), ("implement-change", "ticket-to-do"))
        self.assertEqual(self.run_it(self.fields(context=""), None, "--ticket-status", "New")[0], 1)
        (repo / "standards/profile.yaml").write_text("jira:\n  statuses: []\n  pr_statuses: []\n")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = next_phase.main(["--fields", str(self.fields(context="")), "--ticket-status", "To Do"])
        self.assertEqual(rc, 1)
        self.assertIn("the tracker's statuses could not be read", err.getvalue())
        self.assertEqual(self.why(self.fields()), ("implement-change", "plan"))

    def test_with_no_workflow_recorded_every_status_routes_to_ticket_draft(self):
        plugin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plugin)
        (plugin / "scripts").mkdir()
        shutil.copy(ROOT / "scripts/profile.py", plugin / "scripts")
        (plugin / "standards").mkdir()
        shutil.copy(ROOT / "standards/default-profile.yaml", plugin / "standards")
        repo = self.tmp / "neutral"
        repo.mkdir()
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.org"]
        for args in (["init", "-q"], ["remote", "add", "origin", "git@github.com:example-org/neutral.git"], ["commit", "-q", "--allow-empty", "-m", "x"]):
            subprocess.run(git + args, check=True)
        old, cwd = next_phase.ROOT, os.getcwd()
        self.addCleanup(setattr, next_phase, "ROOT", old)
        self.addCleanup(os.chdir, cwd)
        next_phase.ROOT = plugin
        os.chdir(repo)
        for status in ("To Do", "In Review", "Shipped"):
            with self.subTest(status=status):
                rc, out = self.run_it(self.fields(context=""), None, "--ticket-status", status)
                self.assertEqual(rc, 0, out)
                self.assertIn("phase: ticket-draft\n", out)
                self.assertIn(f"PROJ-7 is {status}, and no workflow is recorded", out)

    def github(self, labels: str, pr_statuses: str = "[]") -> None:
        """This test's working directory: a repository whose standard records a GitHub tracker
        mapping `labels`, under a plugin top level with the default profile alone."""
        plugin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plugin)
        (plugin / "scripts").mkdir()
        shutil.copy(ROOT / "scripts/profile.py", plugin / "scripts")
        (plugin / "standards").mkdir()
        shutil.copy(ROOT / "standards/default-profile.yaml", plugin / "standards")
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo)
        (repo / "standards").mkdir()
        (repo / "standards/profile.yaml").write_text(f"issue_tracker:\n  kind: github\n  statuses:{labels}\n  pr_statuses: {pr_statuses}\n")
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.org"]
        for args in (["init", "-q"], ["remote", "add", "origin", "git@github.com:example-org/github.git"], ["commit", "-q", "--allow-empty", "-m", "x"]):
            subprocess.run(git + args, check=True)
        old, cwd = next_phase.ROOT, os.getcwd()
        self.addCleanup(setattr, next_phase, "ROOT", old)
        self.addCleanup(os.chdir, cwd)
        next_phase.ROOT = plugin
        os.chdir(repo)

    LABELS = ("\n    - {name: needs-refinement, next: ticket-draft, role: filed}\n    - {name: ready, next: implement-change, role: approved}"
              "\n    - {name: in progress, next: implement-change, role: implementation}\n    - {name: blocked, next: nothing}")

    def test_an_open_github_issue_goes_where_its_mapped_label_says(self):
        self.github(self.LABELS)
        issue = self.fields(context="", ticket="59", branch="59-x")
        self.assertEqual(self.why(issue, None, "--issue-state", "open", "--label", "Ready"), ("implement-change", "ticket-to-do"))
        self.assertEqual(self.why(issue, None, "--issue-state", "open", "--label", "bug", "--label", "in progress"), ("implement-change", "ticket-to-do"))
        self.assertEqual(self.why(issue, None, "--issue-state", "open", "--label", "needs-refinement"), ("ticket-draft", "ticket-draft"))
        self.assertEqual(self.why(issue, None, "--issue-state", "open", "--label", "blocked"), ("nothing", "ticket-closed"))
        rc, out = self.run_it(issue, None, "--issue-state", "open", "--label", "ready")
        self.assertEqual(out.splitlines()[1:5], ["argument: 59", "why: ticket-to-do", "lock: none", "#59 · #59 is labeled ready, with no context page here"])

    def test_an_open_github_issue_with_no_mapped_label_is_filed_and_goes_to_ticket_draft(self):
        for labels in (self.LABELS, " []"):
            with self.subTest(labels=labels):
                self.github(labels)
                issue = self.fields(context="", ticket="59", branch="59-x")
                for given in ((), ("--label", "bug")):
                    rc, out = self.run_it(issue, None, "--issue-state", "open", *given)
                    self.assertEqual(rc, 0, out)
                    self.assertIn("phase: ticket-draft\nargument: 59\nwhy: ticket-draft\n", out)
                    self.assertIn("#59 · no context page; #59 is open with no status label\n", out)

    def test_a_closed_github_issue_is_past_the_build_whatever_its_labels(self):
        self.github(self.LABELS)
        issue = self.fields(context="", ticket="59", branch="59-x")
        for labels in ((), ("--label", "ready"), ("--label", "ready", "--label", "blocked")):
            with self.subTest(labels=labels):
                self.assertEqual(self.why(issue, None, "--issue-state", "closed", *labels), ("nothing", "ticket-closed"))
        rc, out = self.run_it(issue, None, "--issue-state", "closed")
        self.assertIn("#59 · #59 is closed\nNothing: the ticket is past the build; open it in the tracker to see why.\n", out)

    def test_a_github_issue_with_two_mapped_labels_is_refused(self):
        self.github(self.LABELS)
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = next_phase.main(["--fields", str(self.fields(context="", ticket="59")), "--issue-state", "open", "--label", "ready", "--label", "Blocked"])
        self.assertEqual(rc, 1)
        self.assertIn("#59 carries ready, Blocked, 2 of the labels the profile's issue_tracker maps; it takes at most one", err.getvalue())

    def test_a_github_label_among_the_pr_statuses_needs_the_state_block(self):
        self.github(self.LABELS, "[in progress]")
        issue = self.fields(context="", ticket="59", branch="59-x")
        self.assertEqual(self.run_it(issue, None, "--issue-state", "open", "--label", "in progress")[0], 1)
        self.assertEqual(self.why(issue, "pull request: none\n", "--issue-state", "open", "--label", "in progress"), ("implement-change", "ticket-to-do"))
        self.assertEqual(self.why(issue, None, "--issue-state", "open", "--label", "ready"), ("implement-change", "ticket-to-do"))
        opened = state([], ticket="#59", n=12)
        self.assertEqual(self.why(issue, opened, "--issue-state", "open", "--label", "in progress"), ("nothing", "answered"))

    def test_a_github_tracker_refuses_the_inputs_of_another(self):
        self.github(self.LABELS)
        issue = self.fields(context="", ticket="59")
        self.assertEqual(self.run_it(issue, None, "--ticket-status", "ready")[0], 1)
        self.assertEqual(self.run_it(issue, None, "--label", "ready")[0], 1)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            next_phase.main(["--fields", str(issue), "--issue-state", "shut"])
        # The state unread, as with the server unreachable, routes as with no status.
        self.assertEqual(self.why(issue), ("ticket-draft", "ticket-draft"))

    def test_issue_state_on_a_jira_tracker_is_refused(self):
        self.assertEqual(self.run_it(self.fields(context=""), None, "--issue-state", "open")[0], 1)
        self.assertEqual(self.why(self.fields(context=""), None, "--ticket-status", "To Do"), ("implement-change", "ticket-to-do"))

    def test_a_pull_request_body_naming_a_github_issue_gives_its_number(self):
        for line in ("#59 · part 1 of 2 · base: main", "[#59](https://github.com/o/r/issues/59) · x"):
            with self.subTest(line=line):
                self.assertEqual(next_phase.read_state(state([], ticket=line))["ticket"], "59")
        self.assertEqual(next_phase.read_state(state([], ticket="PROJ-7 · fixes #59"))["ticket"], "PROJ-7")
        self.assertEqual(next_phase.read_state(state([], ticket="none, tooling work"))["ticket"], "")
        rc, out = self.run_it(self.fields(ticket="59", branch="59-x"), state([], ticket="#59"), "--pr", "7")
        self.assertEqual(rc, 0, out)
        self.assertIn("\n#59 · pull request #7 · every thread answered\n", out)
        self.assertEqual(self.run_it(self.fields(ticket="58", branch="58-x"), state([], ticket="#59"), "--pr", "7")[0], 1)

    def test_a_drafted_ticket_not_filed_stops_and_names_the_file_to_file(self):
        rc, out = self.run_it(self.fields(context="", ticket="", slug="retry-policy"))
        self.assertEqual(
            out.splitlines(),
            [
                "phase: nothing",
                "argument: retry-policy",
                "why: unfiled",
                "lock: none",
                "no ticket · drafted as retry-policy, not filed",
                "Nothing: file `.review/context/retry-policy.jira.txt` in the tracker, or have `/lasp-dev:ticket-draft retry-policy` file it; "
                "give it the key to rename the page, then run `/lasp-dev:work <key>`.",
                "It will ask you: nothing.",
            ],
        )

    def test_a_slug_beside_a_ticket_or_a_context_page_is_refused(self):
        self.assertEqual(self.run_it(self.fields(context="", slug="retry-policy"))[0], 1)
        self.assertEqual(self.run_it(self.fields(ticket="", slug="retry-policy"))[0], 1)

    def test_a_detached_head_with_no_ticket_names_no_plan_and_drafts_a_ticket(self):
        fields = self.fields(ticket="", branch="", context="", plan="", build_branch="")
        self.assertEqual(self.why(fields), ("ticket-draft", "ticket-draft"))

    def test_a_ticket_past_to_do_with_no_page_here_looks_for_its_pull_request_first(self):
        for status in ("Under Development", "External Needs", "In Review"):
            with self.subTest(status=status):
                self.assertEqual(self.run_it(self.fields(context=""), None, "--ticket-status", status)[0], 1)
                self.assertEqual(self.why(self.fields(context=""), state([("agree", "no", "0")]), "--ticket-status", status), ("pr-fix", "fix"))
        none = "pull request: none\n"
        self.assertEqual(self.why(self.fields(context=""), none, "--ticket-status", "Under Development"), ("implement-change", "ticket-to-do"))
        self.assertEqual(self.why(self.fields(context=""), none, "--ticket-status", "In Review"), ("nothing", "ticket-closed"))

    def test_a_ticket_key_given_on_another_branch_names_that_ticket(self):
        fields = self.fields(ticket="PROJ-830", branch="main", context="", plan=str(self.tmp / "plan-830.md"))
        rc, out = self.run_it(fields, None, "--ticket-status", "To Do")
        self.assertIn("phase: implement-change\nargument: PROJ-830\nwhy: ticket-to-do\n", out)
        self.assertEqual(self.why(self.fields(branch="main", elsewhere="PROJ-7-x")), ("nothing", "elsewhere"))

    def test_no_plan_then_no_outcome(self):
        self.assertEqual(self.why(self.fields()), ("implement-change", "plan"))
        self.plan.write_text("# Plan\n### Signatures\nnone\n")
        rc, out = self.run_it(self.fields())
        self.assertIn("why: plan\n", out)
        self.assertIn("the plan is drafted, not yet approved", out)
        self.plan.write_text(PLAN)
        self.assertEqual(self.why(self.fields()), ("implement-change", "build"))

    def test_a_page_drafted_from_its_pull_request_routes_by_that_pull_request_not_to_a_plan(self):
        self.assertEqual(self.why(self.fields(), state([], reviewed="d" * 40)), ("pr-review", "pr-review"))
        self.assertEqual(self.why(self.fields(), state([], st="merged")), ("nothing", "pr-closed"))
        self.assertEqual(self.why(self.fields(branch="review-x", elsewhere="PROJ-7-x"), state([("agree", "no", "0")])), ("pr-fix", "fix"))

    def test_an_outcome_with_a_dirty_tree_is_the_diff_gate(self):
        self.plan.write_text(PLAN)
        self.assertEqual(self.why(self.fields(outcome="Build: passed", dirty="true")), ("implement-change", "diff-gate"))

    def test_a_stopped_build_and_a_passed_one_with_no_pull_request(self):
        self.plan.write_text(PLAN)
        self.assertEqual(self.why(self.fields(outcome="Build: review cap reached")), ("nothing", "build-stopped"))
        self.assertEqual(self.why(self.fields(outcome="Build: passed"), "pull request: none\n"), ("pr-create", "pr-create"))

    def test_the_pull_request_rows_decide_over_local_state(self):
        self.assertEqual(self.why(self.fields(context=""), state([("agree", "no", "0")]), "--pr", "7"), ("pr-fix", "fix"))

    def test_a_given_pull_request_must_be_the_fields_ticket(self):
        other = state([("agree", "no", "0")], ticket="PROJ-830", n=96)
        self.assertEqual(self.run_it(self.fields(ticket="PROJ-900"), other, "--pr", "96")[0], 1)
        rc, out = self.run_it(self.fields(ticket="PROJ-830", context=""), other, "--pr", "96")
        self.assertEqual(out.splitlines()[4], "PROJ-830 · pull request #96 · 1 agreed thread(s) to fix")
        self.assertEqual(self.run_it(self.fields(), "pull request: none\n", "--pr", "7")[0], 1)

    def test_a_given_pull_request_with_no_ticket_reads_none_of_the_local_tickets_facts(self):
        self.plan.write_text(PLAN)
        bare = state([("agree", "no", "1")], ticket="", n=96)
        rc, out = self.run_it(self.fields(ticket="PROJ-900", reopened="PRRT_0"), bare, "--pr", "96")
        self.assertIn("why: answered\n", out)
        self.assertEqual(out.splitlines()[4], "no ticket · pull request #96 · every thread answered")
        args = self.stack("#7 open PROJ-7-x AC-1\n")
        rc, out = self.run_it(self.fields(ticket="PROJ-900", part="1 of 2"), bare, "--pr", "96", *args)
        self.assertIn("why: answered\n", out)

    def test_a_ticket_line_holding_a_link_names_its_key(self):
        self.plan.write_text(PLAN)
        text = state([("agree", "no", "0")]).replace("ticket: Ticket: PROJ-7 · x", "ticket: Ticket: [PROJ-7](https://jira.example/browse/PROJ-7)")
        self.assertEqual(self.why(self.fields(reopened="PRRT_0"), text, "--pr", "7"), ("implement-change", "reopened"))

    def test_a_state_block_of_another_contract_exits_1(self):
        self.assertEqual(self.run_it(self.fields(), state([]).replace("contract: 6", "contract: 5"))[0], 1)

    def test_a_state_block_without_its_author_line_exits_1(self):
        self.assertEqual(self.run_it(self.fields(), state([]).replace("author: a-author\n", ""))[0], 1)

    def test_a_merged_part_with_the_next_part_open_goes_to_that_pull_request(self):
        args = self.stack("#7 merged PROJ-7-x AC-1, AC-2\n#8 open PROJ-7-y AC-3\n")
        rc, out = self.run_it(self.fields(part="1 of 2"), state([], st="merged"), *args)
        self.assertIn("phase: nothing\nargument: 8\nwhy: open-part\n", out)
        self.assertIn("PROJ-7 · stack: #7 merged, #8 open · pull request #8 · #7 is merged; #8 is open", out)

    def test_a_merged_part_with_a_part_not_yet_built_goes_to_implement_change(self):
        args = self.stack("#7 merged PROJ-7-x AC-1, AC-2\n")
        self.assertEqual(self.why(self.fields(part="1 of 2"), state([], st="merged"), *args), ("implement-change", "next-part"))

    def test_a_closed_part_leaves_its_criteria_to_be_built_again(self):
        args = self.stack("#7 closed PROJ-7-x AC-1\n#8 merged PROJ-7-y AC-2, AC-3\n")
        rc, out = self.run_it(self.fields(branch="PROJ-7-y", part="2 of 2"), state([], st="merged", n=8), *args)
        self.assertIn("why: next-part\n", out)
        self.assertIn("1 of the plan's 2 parts without an open or merged pull request; AC-1 claimed by no open or merged part", out)
        args = self.stack("#7 closed PROJ-7-x AC-1\n#8 open PROJ-7-y AC-2, AC-3\n")
        rc, out = self.run_it(self.fields(part="1 of 2"), state([], st="closed"), *args)
        self.assertIn("why: open-part\n", out)
        self.assertIn("#7 is closed; #8 is open; AC-1 claimed by no open or merged part", out)

    def test_every_part_merged_is_the_ticket_done_only_when_they_claim_every_criterion(self):
        args = self.stack("#7 merged PROJ-7-x AC-1, AC-2\n#8 merged PROJ-7-y AC-3\n")
        rc, out = self.run_it(self.fields(part="1 of 2"), state([], st="merged"), *args)
        self.assertIn("why: pr-closed\n", out)
        self.assertIn("every criterion is covered: the ticket is done", out)
        args = self.stack("#7 merged PROJ-7-x AC-1, AC-2\n#8 merged PROJ-7-y AC-3\n", "AC-1,AC-2,AC-3,AC-4")
        rc, out = self.run_it(self.fields(part="1 of 2"), state([], st="merged"), *args)
        self.assertIn("phase: nothing\nargument: 7\nwhy: unclaimed\n", out)
        self.assertIn("the plan's 2 parts leave AC-4 unclaimed", out)

    def test_an_open_part_waiting_on_reviewers_offers_the_next_part(self):
        args = self.stack("#7 open PROJ-7-x AC-1, AC-2\n")
        rc, out = self.run_it(self.fields(part="1 of 2"), state([("agree", "no", "1")]), *args)
        self.assertIn("phase: implement-change\nargument: PROJ-7\nwhy: next-part\n", out)
        self.assertIn("#7: every thread answered; 1 of the plan's 2 parts without an open or merged pull request; AC-3 claimed by no open or merged part", out)
        self.assertEqual(self.why(self.fields(part="1 of 2"), state([("unanswered", "no", "0")]), *args), ("pr-fix", "walk"))
        args = self.stack("#7 open PROJ-7-x AC-1, AC-2\n#8 open PROJ-7-y AC-3\n")
        self.assertEqual(self.why(self.fields(part="1 of 2"), state([("agree", "no", "1")]), *args), ("nothing", "answered"))

    def test_a_stack_and_the_fields_part_come_together(self):
        args = self.stack("#7 open PROJ-7-x AC-1\n")
        self.assertEqual(self.run_it(self.fields(), state([]), *args)[0], 1)
        self.assertEqual(self.run_it(self.fields(part="1 of 2"), state([]))[0], 1)
        self.assertEqual(self.run_it(self.fields(part="one of two"), state([]), *args)[0], 1)

    def test_pull_request_none_is_a_branch_that_never_had_one(self):
        self.plan.write_text(PLAN)
        args = self.stack("#7 merged PROJ-7-x AC-1\n#8 open PROJ-7-y AC-2\n", "AC-1,AC-2")
        self.assertEqual(self.run_it(self.fields(outcome="Build: passed", part="1 of 2"), "pull request: none\n", *args)[0], 1)
        args = self.stack("#7 merged PROJ-7-x AC-1\n", "AC-1,AC-2")
        fields = self.fields(branch="PROJ-7-y", outcome="Build: passed", part="2 of 2")
        self.assertEqual(self.why(fields, "pull request: none\n", *args), ("pr-create", "pr-create"))

    def test_a_stack_line_it_cannot_read_exits_1(self):
        (self.tmp / "stack.txt").write_text("PR 7 merged\n")
        self.assertEqual(self.run_it(self.fields(part="1 of 2"), None, "--stack", str(self.tmp / "stack.txt"))[0], 1)

    def test_a_reopened_design_is_revised_built_then_put_in_the_description(self):
        self.plan.write_text(PLAN)
        fields = self.fields(outcome="Build: passed", reopened="PRRT_0 PRRT_1")
        two = state([("agree", "no", "0"), ("agree", "no", "0")])
        self.assertEqual(self.why(fields, two), ("implement-change", "reopened"))
        self.plan.write_text(PLAN + "\n## Revision 1 — PRRT_0\nApproved by: a-reviewer\n")
        rc, out = self.run_it(fields, two)
        self.assertIn("why: reopened\n", out)
        self.assertIn("review reopened the design in PRRT_1", out)
        # A redesign drafted at the plan gate, with no approval of its own, is not yet approved.
        self.plan.write_text(PLAN + "\n## Revision 1 — PRRT_0\nApproved by: a-reviewer\n\n## Revision 2 — PRRT_1\n")
        rc, out = self.run_it(self.fields(outcome="Build: passed", outcome_reopened="PRRT_0 PRRT_1", reopened="PRRT_0 PRRT_1"), two)
        self.assertIn("why: reopened\n", out)
        self.assertIn("the redesign for PRRT_1 is drafted, not yet approved", out)
        self.plan.write_text(PLAN + "\n## Revision 1 — PRRT_0\nApproved by: a-reviewer\n\n## Revision 2 — PRRT_1\nApproved by: a-reviewer\n")
        self.assertEqual(self.why(self.fields(reopened="PRRT_0 PRRT_1"), two), ("implement-change", "reopened"))
        self.assertEqual(self.why(self.fields(outcome="Build: review cap reached", reopened="PRRT_0", outcome_reopened="PRRT_0"), two), ("nothing", "build-stopped"))
        # The outcome kept from the build before the redesign names neither thread.
        self.assertEqual(self.why(fields, two), ("implement-change", "reopened"))
        self.assertEqual(self.why(self.fields(outcome="Build: passed", outcome_reopened="PRRT_0", reopened="PRRT_0 PRRT_1"), two), ("implement-change", "reopened"))
        fields = self.fields(outcome="Build: passed", outcome_reopened="PRRT_0 PRRT_1", reopened="PRRT_0 PRRT_1")
        self.assertEqual(self.why(fields, two), ("pr-create", "reopened-body"))
        self.assertEqual(self.why(fields, "pull request: none\n"), ("pr-create", "pr-create"))
        self.assertEqual(self.why(self.fields(outcome="Build: passed"), two), ("pr-fix", "fix"))

    def test_another_parts_reopen_does_not_route_this_part(self):
        self.plan.write_text(PLAN)
        args = self.stack("#7 open PROJ-7-x AC-1\n#8 open PROJ-7-y AC-2\n", "AC-1,AC-2")
        fields = self.fields(branch="PROJ-7-y", outcome="Build: passed", part="2 of 2", reopened="PRRT_9")
        self.assertEqual(self.why(fields, state([("agree", "no", "0")], n=8), *args), ("pr-fix", "fix"))

    def test_another_parts_session_reopen_does_not_route_this_part(self):
        self.plan.write_text(PLAN)
        args = self.stack("#7 open PROJ-7-x AC-1\n#8 open PROJ-7-y AC-2\n", "AC-1,AC-2")
        fields = self.fields(branch="PROJ-7-y", outcome="Build: passed", part="2 of 2", reopened="session-7-1")
        self.assertEqual(self.why(fields, state([("agree", "no", "0")], n=8), *args), ("pr-fix", "fix"))
        fields = self.fields(branch="PROJ-7-y", outcome="Build: passed", part="2 of 2", reopened="session-8-1")
        self.assertEqual(self.why(fields, state([("agree", "no", "0")], n=8), *args), ("implement-change", "reopened"))
        # Part 2 built before its pull request exists leaves part 1's session reopen to part 1.
        args = self.stack("#7 open PROJ-7-x AC-1\n", "AC-1,AC-2")
        fields = self.fields(branch="PROJ-7-y", outcome="Build: passed", part="2 of 2", reopened="session-7-1")
        self.assertEqual(self.why(fields, None, *args)[1], "pr-create")

    def test_a_reopen_routes_only_on_its_tickets_branch_and_open_pull_request(self):
        self.plan.write_text(PLAN)
        self.assertEqual(self.why(self.fields(reopened="PRRT_0"), state([("agree", "no", "0")], st="merged")), ("nothing", "pr-closed"))
        fields = self.fields(branch="main", elsewhere="PROJ-7-x", reopened="PRRT_0")
        self.assertEqual(self.why(fields, state([("agree", "no", "0")]), "--pr", "7"), ("pr-fix", "fix"))
        self.assertEqual(self.why(fields), ("nothing", "elsewhere"))

    def test_the_author_goes_on_from_the_threads_after_answering_a_review_of_an_earlier_head(self):
        earlier = state([("agree", "no", "1", "Fixed in abc1234.")], reviewed="d" * 40)
        for me in ("a-author", "A-Author"):
            with self.subTest(me=me):
                self.assertEqual(self.why(self.fields(), earlier, "--me", me), ("nothing", "answered"))
        self.assertEqual(self.why(self.fields(), earlier, "--me", "a-reviewer"), ("pr-review", "pr-review"))
        self.assertEqual(self.why(self.fields(), earlier), ("pr-review", "pr-review"))
        unanswered = state([("unanswered", "no", "0")], reviewed="d" * 40)
        self.assertEqual(self.why(self.fields(), unanswered, "--me", "a-author"), ("pr-fix", "walk"))
        # The author's own review of the new head, kept here and undecided, is still raised.
        self.assertEqual(self.why(self.fields(), earlier, "--me", "a-author", *self.local(HEAD, "undecided")), ("pr-review", "review-unposted"))

    def test_the_author_reviews_a_built_reopen_until_its_thread_is_answered_as_fixed(self):
        fields = self.fields(outcome="Build: passed", outcome_reopened="PRRT_0")
        self.assertEqual(self.why(fields, state([("agree", "no", "0")], reviewed="d" * 40), "--me", "a-author"), ("pr-review", "pr-review"))
        self.assertEqual(self.why(fields, state([("agree", "no", "0")]), "--me", "a-author"), ("pr-fix", "fix"))
        fixed = state([("agree", "no", "1", "Fixed in abc1234.")], reviewed="d" * 40)
        self.assertEqual(self.why(fields, fixed, "--me", "a-author"), ("nothing", "answered"))
        # A review of the new design the author kept here and declined routes on to the fix.
        pending = state([("agree", "no", "0")], reviewed="d" * 40)
        self.assertEqual(self.why(fields, pending, "--me", "a-author", *self.local(HEAD, "declined")), ("pr-fix", "fix"))

    def test_a_pull_request_with_no_findings_review_goes_to_pr_review_for_its_author_too(self):
        self.assertEqual(self.why(self.fields(), state([], reviewed=""), "--me", "a-author"), ("pr-review", "pr-review"))

    def test_the_author_goes_on_from_the_threads_after_answering_a_person_or_a_bot(self):
        def opened_by(opener: str, *rows: tuple) -> str:
            return state(list(rows), reviewed="").replace(" | R-001/x.py::f | should-fix | ", f" | {opener} | false | ")
        for opener in ("a-reviewer", "bot"):
            with self.subTest(opener=opener):
                answered = opened_by(opener, ("agree", "no", "1", "Fixed in abc1234."))
                self.assertEqual(self.why(self.fields(), answered, "--me", "a-author"), ("nothing", "answered"))
                self.assertEqual(self.why(self.fields(), answered, "--me", "a-reviewer"), ("pr-review", "pr-review"))
                self.assertEqual(self.why(self.fields(), answered), ("pr-review", "pr-review"))
        for verdict in ("disagree", "discuss", "unparsed"):
            with self.subTest(verdict=verdict):
                phase, why = self.why(self.fields(), opened_by("a-reviewer", (verdict, "no", "0", "not here")), "--me", "a-author")
                self.assertNotEqual(phase, "pr-review")
                if verdict == "unparsed":
                    self.assertEqual((phase, why), ("pr-fix", "walk"))
        mixed = opened_by("a-reviewer", ("agree", "no", "1", "Fixed in abc1234."), ("unanswered", "no", "0"))
        self.assertEqual(self.why(self.fields(), mixed, "--me", "a-author"), ("pr-fix", "walk"))
        # Before the author answers anything, and on the author's own threads, they review first.
        self.assertEqual(self.why(self.fields(), opened_by("a-reviewer", ("unanswered", "no", "0")), "--me", "a-author"), ("pr-review", "pr-review"))
        self.assertEqual(self.why(self.fields(), opened_by("A-Author", ("agree", "no", "1", "Fixed in abc1234.")), "--me", "a-author"), ("pr-review", "pr-review"))
        # A built reopen awaiting its fixed reply is reviewed again, by the author too.
        reopened = self.fields(outcome="Build: passed", outcome_reopened="PRRT_0")
        self.assertEqual(self.why(reopened, opened_by("a-reviewer", ("agree", "no", "0")), "--me", "a-author"), ("pr-review", "pr-review"))

    def test_a_review_posted_in_this_loop_waits_on_reviewers_before_github_shows_it(self):
        unshown = state([("unanswered", "no", "0")], reviewed="")
        self.assertEqual(self.why(self.fields(), unshown, "--reviewed-this-loop"), ("nothing", "reviewers-first"))
        self.assertEqual(self.why(self.fields(), state([("unanswered", "no", "0")], reviewed="", draft="true"), "--reviewed-this-loop"), ("pr-review", "pr-review"))

    def test_a_reopen_on_a_branch_with_no_ticket_goes_to_implement_change(self):
        self.plan.write_text(PLAN)
        fields = self.fields(ticket="", branch="feature/x", context="", reopened="PRRT_0")
        rc, out = self.run_it(fields, state([("agree", "no", "0")], ticket=""))
        self.assertEqual((rc, out.splitlines()[:3]), (0, ["phase: implement-change", "argument: ", "why: reopened"]))
        self.assertEqual(self.why(fields, state([("agree", "no", "0")], ticket=""), "--pr", "7"), ("implement-change", "reopened"))

    def test_a_second_session_reopen_is_revised_after_the_first_was_built_and_described(self):
        no_ticket = {"ticket": "", "branch": "feature/x", "context": ""}
        built = PLAN + "\n## Revision 1 — session-7-1\nApproved by: a-author\n"
        self.plan.write_text(built)
        pr = state([("agree", "no", "1", "Fixed in abc1234.")], ticket="")
        fields = self.fields(**no_ticket, outcome="Build: passed", outcome_reopened="session-7-1", reopened="session-7-1")
        self.assertEqual(self.why(fields, pr), ("pr-create", "reopened-body"))
        # pr-create put session-7-1 in the description and deleted the file; a second session reopen follows.
        fields = self.fields(**no_ticket, outcome="Build: passed", outcome_reopened="session-7-1", reopened="session-7-2")
        self.assertEqual(self.why(fields, pr), ("implement-change", "reopened"))
        self.plan.write_text(built + "\n## Revision 2 — session-7-2\nApproved by: a-author\n")
        self.assertEqual(self.why(fields, pr), ("implement-change", "reopened"))
        fields = self.fields(**no_ticket, outcome="Build: passed", outcome_reopened="session-7-2", reopened="session-7-2")
        self.assertEqual(self.why(fields, pr), ("pr-create", "reopened-body"))

    def test_bad_inputs_exit_1(self):
        path = self.tmp / "fields.txt"
        path.write_text("ticket=PROJ-7\n")
        self.assertEqual(self.run_it(path)[0], 1)
        self.assertEqual(self.run_it(self.fields(), None, "--pr", "7")[0], 1)
        self.assertEqual(self.run_it(self.fields(), "## pr-0007 — state\nhead: x\n")[0], 1)
        self.assertEqual(self.run_it(self.fields(), state([]).replace("## pr-0007 — state\n", ""))[0], 1)

    def test_it_prints_the_three_lines_work_says(self):
        rc, out = self.run_it(self.fields(), state([("unanswered", "no", "0")]))
        self.assertEqual(
            out.splitlines()[4:],
            [
                "PROJ-7 · pull request #7 · 1 thread(s) to answer",
                "Next: pr-fix.",
                "It will ask you: agree, disagree or discuss on each thread, then the plan, the diff, the push and any reply.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
