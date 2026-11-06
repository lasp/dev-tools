"""Tests for scripts/record.py. Run with `python3 -m unittest discover -s tests`.

`tests/fixtures/pr-0042/` holds the four MCP dumps for o/r#42, written by hand, and
`expected.yaml`, the record they produce once the test gives the open pull request a merge date.
Change the dumps and regenerate `expected.yaml` together, in one commit.
`tests/fixtures/severity/` is hand-written: a must-fix on a line and a file-level suggestion.
`tests/fixtures/no-findings/` is the severity pull request with no findings review: two
threads people opened, one on a line and resolved, one at file level, and a body written by hand,
with no Already checked block.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pr-0042"
SEVERITY = ROOT / "tests" / "fixtures" / "severity"
NO_FINDINGS = ROOT / "tests" / "fixtures" / "no-findings"

_spec = importlib.util.spec_from_file_location("ratchet_counts", ROOT / "scripts" / "ratchet_counts.py")
ratchet_counts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ratchet_counts)

_spec = importlib.util.spec_from_file_location("record", ROOT / "scripts" / "record.py")
record = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(record)


# The standard of o/r, the repository the hand-written reviews are on: the fixtures' ticket key and
# the wordings beside the plugin's attribution line that mark a comment as AI-drafted.
PROJECT = ("ticket:\n  pattern: 'PROJ-\\d+'\n  project: PROJ\n"
           "attribution:\n  phrases: [drafted with AI assistance, 'written by `loop-review` against']\n")
CHECKOUT = Path()


def standard_for_o(text: str) -> None:
    """Writes `text` as the standard's profile.yaml in the checkout of o/r."""
    (CHECKOUT / "standards/profile.yaml").write_text(text)


def setUpModule():
    """The plugin's default profile alone under a top level, and a checkout of o/r, with a commit
    and its own standard, as the working directory."""
    global CHECKOUT
    top = Path(tempfile.mkdtemp())
    unittest.addModuleCleanup(shutil.rmtree, top)
    (top / "standards").mkdir()
    shutil.copy(ROOT / "standards/default-profile.yaml", top / "standards/default-profile.yaml")
    unittest.addModuleCleanup(setattr, record, "ROOT", record.ROOT)
    record.ROOT = top
    CHECKOUT = Path(tempfile.mkdtemp())
    unittest.addModuleCleanup(shutil.rmtree, CHECKOUT)
    git = ["git", "-C", str(CHECKOUT), "-c", "user.name=t", "-c", "user.email=t@example.org"]
    subprocess.run(["git", "init", "-q", str(CHECKOUT)], check=True)
    subprocess.run([*git, "remote", "add", "origin", "git@github.com:o/r.git"], check=True)
    (CHECKOUT / "standards").mkdir()
    standard_for_o(PROJECT)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "standard"], check=True)
    unittest.addModuleCleanup(os.chdir, os.getcwd())
    os.chdir(CHECKOUT)

BODY = (
    "PROJ-1 · x\n\n<details><summary>Already checked</summary>\n\nBuild: passed\nGates: lint 0\n"
    "Tokens since the build started: 1 in\nPlan: approved by alice\n\n</details>\n"
)
REVIEW = {
    "id": 1,
    "state": "COMMENTED",
    "body": "## Standards review\nreviewed: " + "a" * 40 + "\n\n🤖 _AI-assisted comment, posted by @alice. AI assistance level: 5/5 (not read by a person)._\n",
    "html_url": "https://github.com/o/r/pull/1#pullrequestreview-1",
    "submitted_at": "2026-09-26T00:10:00Z",
}
PR = {
    "number": 1, "state": "closed", "draft": False, "merged": True, "merged_at": "2026-09-27T18:00:00Z",
    "user": {"login": "alice"}, "head": {"ref": "b"},
}
ATTRIBUTION = "🤖 _AI-assisted comment, posted by @alice. AI assistance level: 5/5 (not read by a person)._"
SLOP_SCORE_ATTRIBUTION = "🤖 _AI-assisted comment, posted by @alice. AI slop score: 5/5._"


def merged_0042() -> dict:
    """o/r#42's `get` result, which is open, as it would read once merged."""
    return {**json.loads((FIXTURE / "pr.json").read_text()), "merged": True, "merged_at": "2026-10-03T16:00:00Z"}


def signed(body: str, who: str) -> str:
    """A reply as pr-fix and pr-review post it: the text, a blank line, then the attribution."""
    return f"{body}\n\n🤖 _AI-assisted comment, posted by @{who}. AI assistance level: 5/5 (not read by a person)._"


def thread(severity: str, *replies: tuple[str, str]) -> dict:
    finding = {
        "body": f"**{severity}** — a finding\n\n<details><summary>Standard</summary>\n\nkey: `R-001/x.py::f`\n</details>\n\n{ATTRIBUTION}",
        "path": "x.py",
        "original_line": 3,
        "author": "alice",
        "created_at": "2026-09-26T00:09:00Z",
    }
    comments = [{"body": signed(body, who), "author": who, "created_at": "2026-09-26T00:20:00Z"} for who, body in replies]
    return {"id": "PRRT_1", "comments": [finding, *comments]}


class RecordFromFixture(unittest.TestCase):
    def setUp(self):
        self._tz = os.environ.get("TZ")
        os.environ["TZ"] = "America/Denver"
        time.tzset()

    def tearDown(self):
        if self._tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._tz
        time.tzset()

    def test_reproduces_the_committed_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, pr = Path(tmp) / "pr-0042.yaml", Path(tmp) / "pr.json"
            pr.write_text(json.dumps(merged_0042()))
            args = ["--pr", pr, "--reviews", FIXTURE / "reviews.json"]
            args += ["--comments", FIXTURE / "comments.json", "--issue-comments", FIXTURE / "issue-comments.json", "--body", FIXTURE / "body.md"]
            args += ["--repo", "o/r", "--standards-sha", "9f01488", "--out", out]
            self.assertEqual(record.main([str(a) for a in args]), 0)
            self.assertEqual(out.read_text(), (FIXTURE / "expected.yaml").read_text())

    def test_date_is_the_first_review_in_local_time_and_merged_the_utc_merge_day(self):
        lines, _ = record.build(PR, [REVIEW, {**REVIEW, "id": 2, "submitted_at": "2026-09-27T00:10:00Z"}], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertEqual(lines[0], "contract: 13")
        self.assertIn("date: 2026-09-25\nmerged: 2026-09-27\n", "\n".join(lines) + "\n")
        # 03:00 UTC is the evening before in Denver; the harvest's merged:>= qualifier reads UTC.
        lines, _ = record.build({**PR, "merged_at": "2026-10-01T03:00:00Z"}, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("merged: 2026-10-01", lines)

    def test_with_no_findings_review_date_is_the_earliest_thread_opened(self):
        late, early = persons_thread("bob"), persons_thread("bob")
        late["comments"][0]["created_at"], early["comments"][0]["created_at"] = "2026-09-29T18:00:00Z", "2026-09-28T18:00:00Z"
        early["id"] = "PRRT_q"
        lines, _ = record.build({**PR, "merge_commit_sha": "d" * 40}, [], [late, early], BODY, "o/r", None, issue_comments=[])
        self.assertIn("date: 2026-09-28", lines)

    def test_no_findings_review_still_makes_a_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pr-0007.yaml"
            args = ["--pr", NO_FINDINGS / "pr.json", "--reviews", NO_FINDINGS / "reviews.json"]
            args += ["--comments", NO_FINDINGS / "comments.json", "--issue-comments", NO_FINDINGS / "issue-comments.json", "--body", NO_FINDINGS / "body.md"]
            args += ["--repo", "o/r", "--out", out]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(record.main([str(a) for a in args]), 0)
            text = out.read_text()
        for line in ("head: bbbbbbb", "date: 2026-09-30\nmerged: 2026-10-01", "standards_sha: none", "adjudicated_by: none", "rework_rounds: []", "findings: []", "questions: []"):
            self.assertIn(line + "\n", text)
        threads = text.split("threads:\n", 1)[1]
        self.assertEqual(threads.count("  - thread: "), 2)
        self.assertIn('  - thread: PRRT_person\n    by: bob\n    authorship: human\n    at: "pkg/reader.py:42"\n', threads)
        self.assertIn('    resolved: true\n    outdated: true\n    replies: 1\n    verdict: unparsed\n    line: "Yes, fixed in the next commit."\n', threads)
        self.assertIn('  - thread: PRRT_file\n    by: bob\n    authorship: human\n    at: "pkg/units.py"\n', threads)
        self.assertIn("    replies: 0\n    verdict: unanswered\n", threads)

    def test_must_fix_and_file_level_findings_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pr-0007.yaml"
            args = ["--pr", SEVERITY / "pr.json", "--reviews", SEVERITY / "reviews.json"]
            args += ["--comments", SEVERITY / "comments.json", "--issue-comments", SEVERITY / "issue-comments.json", "--body", SEVERITY / "body.md"]
            args += ["--repo", "o/r", "--standards-sha", "abc1234", "--out", out]
            self.assertEqual(record.main([str(a) for a in args]), 0)
            findings = out.read_text().split("findings:\n", 1)[1].split("questions:", 1)[0]
        must, file_level = findings.split("  - key: ")[1:]
        self.assertIn("severity: must-fix", must)
        self.assertIn('at: "pkg/reader.py:42"', must)
        self.assertIn("severity: suggestion", file_level)
        self.assertIn('at: "pkg/units.py"\n', file_level)

    def test_six_findings_and_an_uncited_question_with_their_threads(self):
        threads = json.loads((FIXTURE / "comments.json").read_text())["review_threads"]
        lines, report = record.build(
            merged_0042(),
            json.loads((FIXTURE / "reviews.json").read_text()),
            threads,
            (FIXTURE / "body.md").read_text(),
            "o/r",
            "9f01488", issue_comments=[]
        )
        text = "\n".join(lines)
        findings = text.split("findings:\n", 1)[1].split("questions:", 1)[0]
        verdicts = [line.split(": ")[1] for line in findings.splitlines() if line.startswith("    verdict: ")]
        self.assertEqual(verdicts, ["agree", "disagree", "agree", "discuss", "agree", "agree"])
        for t in threads:
            self.assertIn(f"thread: {t['id']}", text)
        self.assertEqual(text.count("  - q: "), 0)
        self.assertIn("  - thread: PRRT_synthetic007\n    by: review\n    authorship: ai-drafted\n    severity: question\n", text)
        self.assertEqual(report, [])


class Adjudication(unittest.TestCase):
    def run_build(self, th: dict) -> tuple[str, list[str]]:
        lines, report = record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[])
        return "\n".join(lines), report

    def test_second_person_disagreeing_contests_until_the_author_settles(self):
        text, report = self.run_build(thread("Should fix", ("bob", "Agree."), ("carol", "Disagree, not here")))
        self.assertIn('    verdict: contested\n    contested: true\n    lines:\n      - "bob: Agree."\n      - "carol: Disagree, not here"', text)
        self.assertEqual(len(report), 1)
        self.assertTrue(report[0].startswith("contested: PRRT_1"))

        text, report = self.run_build(
            thread("Should fix", ("bob", "Agree."), ("carol", "Disagree, not here"), ("alice", "Disagree: carol is right"))
        )
        self.assertEqual(report, [])
        self.assertIn("verdict: disagree", text)
        self.assertIn('reason: "carol is right"', text)
        self.assertIn("contested: true", text)
        self.assertIn('- "bob: Agree."', text)
        self.assertIn('- "carol: Disagree, not here"', text)

    def test_the_authors_word_settling_a_discuss_is_not_a_rival(self):
        text, report = self.run_build(thread("Should fix", ("bob", "Discuss: why here?"), ("alice", "Agree, moving it.")))
        self.assertEqual(report, [])
        self.assertIn("verdict: agree", text)
        self.assertNotIn("contested", text)

        text, report = self.run_build(thread("Should fix", ("bob", "Discuss: why?"), ("bob", "Agree."), ("carol", "Agree.")))
        self.assertEqual(report, [])
        self.assertNotIn("contested", text)

        text, report = self.run_build(thread("Should fix", ("bob", "Discuss: why?"), ("bob", "Agree."), ("carol", "Disagree, no")))
        self.assertTrue(report[0].startswith("contested: PRRT_1"))

        text, report = self.run_build(
            thread("Should fix", ("bob", "Discuss: why?"), ("alice", "Agree."), ("carol", "Disagree, too late"))
        )
        self.assertEqual(report, [])
        self.assertIn("verdict: agree", text)

    def test_the_authors_word_decides_over_an_earlier_one_and_nothing_after_it_contests(self):
        text, report = self.run_build(thread("Should fix", ("bob", "Agree."), ("alice", "Disagree, the caller checks it")))
        self.assertEqual(report, [])
        self.assertIn("verdict: disagree", text)
        self.assertIn('reason: "the caller checks it"', text)
        self.assertNotIn("contested", text)

        text, report = self.run_build(thread("Should fix", ("alice", "Agree, fixed in abc1234."), ("bob", "Disagree, not here")))
        self.assertEqual(report, [])
        self.assertIn("verdict: agree", text)
        self.assertNotIn("contested", text)

    def test_the_authors_reply_decides_in_every_order(self):
        """alice is the pull request's author, and the finding's opener or not. Each order gives
        the state row's verdict, contested and replies-after columns and the record's `by`."""
        agree, reasonless, reason = ("bob", "Agree."), ("alice", "Disagree"), ("alice", "Disagree, the caller checks it")
        orders = {
            "reviewer, then author agreeing": ((agree, ("alice", "Agree.")), ("agree", "no", "0", "alice")),
            "reviewer, then author disagreeing": ((agree, reason), ("disagree", "no", "0", "alice")),
            "author, then reviewer": ((("alice", "Agree."), ("bob", "Disagree, not here")), ("agree", "no", "1", "alice")),
            "author alone": ((("alice", "Agree."),), ("agree", "no", "0", "alice")),
            "author's first word, then their second": ((reason, ("alice", "Agree.")), ("disagree", "no", "1", "alice")),
            "neither, one reply": ((agree,), ("agree", "no", "0", "bob")),
            "neither, two differing": ((agree, ("carol", "Disagree, not here")), ("agree", "yes", "1", None)),
            "author settling a contest": ((agree, ("carol", "Disagree, not here"), ("alice", "Agree.")), ("agree", "no", "0", "alice")),
            "author's Discuss": ((("bob", "Disagree, not needed"), ("alice", "Discuss: why not?")), ("discuss", "no", "0", None)),
            "author's Discuss, then a reviewer's word": ((agree, ("alice", "Discuss: why?"), ("bob", "Agree, it can be None.")), ("agree", "no", "0", "bob")),
            "author's Discuss in a contest": ((agree, ("carol", "Disagree, not here"), ("alice", "Discuss: who is right?")), ("agree", "yes", "2", None)),
            "author's reasonless Disagree": ((agree, reasonless), ("unanswered", "no", "0", None)),
            "author's reasonless Disagree, then the reason": ((agree, reasonless, reason), ("disagree", "no", "0", "alice")),
            "author's reasonless Disagree first": ((reasonless, agree), ("agree", "no", "0", "bob")),
            "author's own words": ((agree, ("alice", "No, the caller validates this already.")), ("unparsed", "no", "0", None)),
        }
        for opener in ("alice", "carol"):
            for name, (replies, expected) in orders.items():
                with self.subTest(order=name, opener=opener):
                    th = thread("Must fix before merge", *replies)
                    th["comments"][0]["author"] = opener
                    row = record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
                    by = re.search(r"^    by: (\S+)$", self.run_build(th)[0], re.M)
                    self.assertEqual((*row[5:8], by and by.group(1)), expected)
        # A suggestion's Disagree needs no reason, so the author's bare one decides.
        th = thread("Suggestion", agree, reasonless)
        self.assertEqual(record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")[5:8], ["disagree", "no", "0"])

    def test_a_rework_round_counts_only_the_findings_since_the_previous_review(self):
        reviews, threads = [], []
        for n, (sha, hour) in enumerate((("a", 0), ("b", 1), ("c", 2))):
            reviews.append({**REVIEW, "id": n, "body": f"## Standards review\nreviewed: {sha * 40}\n\n\n🤖 _AI-assisted comment, posted by @alice. AI assistance level: 5/5 (not read by a person)._", "submitted_at": f"2026-09-26T0{hour}:10:00Z"})
        for n, hour in enumerate((0, 1)):
            th = thread("Should fix", ("bob", "Agree."))
            th["id"] = f"PRRT_{n}"
            th["comments"][0]["created_at"] = f"2026-09-26T0{hour}:09:00Z"
            th["comments"][0]["body"] = th["comments"][0]["body"].replace("R-001/x.py::f", f"R-00{n + 1}/x.py::f")
            threads.append(th)
        lines, _ = record.build(PR, reviews, threads, BODY, "o/r", "abc1234", issue_comments=[])
        rounds = "\n".join(lines).split("rework_rounds:\n", 1)[1].split("findings:", 1)[0]
        self.assertIn("    sent_back_by: [R-001/x.py::f]\n    applied: 1\n", rounds)
        self.assertIn("    sent_back_by: [R-002/x.py::f]\n    applied: 1\n", rounds)

    def test_the_ticket_is_the_key_on_the_ticket_line_only(self):
        text, _ = self.run_build(thread("Should fix"))
        self.assertIn("ticket: none\n", text)
        lines, _ = record.build(PR, [REVIEW], [], BODY + "Ticket: PROJ-9 · y\n", "o/r", "abc1234", issue_comments=[])
        self.assertIn("ticket: PROJ-9", lines)
        lines, _ = record.build(PR, [REVIEW], [], BODY + "Ticket: none, tooling work\n", "o/r", "abc1234", issue_comments=[])
        self.assertIn("ticket: none", lines)
        for line in ("none — split from PROJ-68", "none — split from #68", "see PROJ-9"):
            with self.subTest(line=line):
                lines, _ = record.build(PR, [REVIEW], [], BODY + f"Ticket: {line}\n", "o/r", "abc1234", issue_comments=[])
                self.assertIn("ticket: none", lines)

    def test_the_ticket_key_is_in_the_profiles_pattern(self):
        body = BODY + "Ticket: GEO-12 · y\n"
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn("ticket: none", lines)
        self.addCleanup(standard_for_o, PROJECT)
        standard_for_o("ticket:\n  pattern: 'GEO-\\d+'\n")
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn("ticket: GEO-12", lines)
        standard_for_o("ticket:\n  pattern: not yet recorded\n")
        with self.assertRaisesRegex(record.Unsupported, "no ticket.pattern recorded"):
            record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        standard_for_o("ticket:\n  pattern: 'GEO-('\n")
        with self.assertRaisesRegex(record.Unsupported, "the profile is refused"):
            record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])

    def test_on_a_github_tracker_the_ticket_is_the_issue_number(self):
        self.addCleanup(standard_for_o, PROJECT)
        github = "issue_tracker:\n  kind: github\n  statuses: []\n  pr_statuses: []\n"
        for standard in (github, "ticket:\n  pattern: 'PROJ-\\d+'\n  project: PROJ\n" + github):
            standard_for_o(standard)
            with self.subTest(standard=standard):
                body = "Ticket: #59 · part 1 of 2 · base: main\n" + BODY
                lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
                self.assertIn("ticket: 59", lines)
                self.assertIn('stack: {part: 1, of: 2, base: "main"}', lines)
                lines, _ = record.build(PR, [REVIEW], [], BODY + "Ticket: [#59](https://github.com/o/r/issues/59) · y\n", "o/r", "abc1234", issue_comments=[])
                self.assertIn("ticket: 59", lines)
                lines, _ = record.build(PR, [REVIEW], [], BODY + "Ticket: none — split from #68\n", "o/r", "abc1234", issue_comments=[])
                self.assertIn("ticket: none", lines)
                for line, says in (("PROJ-9 · y", "names PROJ-9, but the tracker is GitHub's"), ("other/r#59 · y", "names other/r#59")):
                    with self.assertRaisesRegex(record.Unsupported, says):
                        record.build(PR, [REVIEW], [], BODY + f"Ticket: {line}\n", "o/r", "abc1234", issue_comments=[])
        standard_for_o(PROJECT)
        lines, _ = record.build(PR, [REVIEW], [], BODY + "Ticket: #59 · y\n", "o/r", "abc1234", issue_comments=[])
        self.assertIn("ticket: none", lines)
        lines, _ = record.build(PR, [REVIEW], [], BODY + "Ticket: none — split from #68\n", "o/r", "abc1234", issue_comments=[])
        self.assertIn("ticket: none", lines)

    def test_a_github_tracker_elsewhere_names_its_issues_by_its_repository(self):
        self.addCleanup(standard_for_o, PROJECT)
        standard_for_o("issue_tracker:\n  kind: github\n  location: o/tracker\n  statuses: []\n  pr_statuses: []\n")
        for line in ("o/tracker#59 · y", "[o/tracker#59](https://github.com/o/tracker/issues/59) · y", "O/Tracker#59 · y"):
            with self.subTest(line=line):
                lines, _ = record.build(PR, [REVIEW], [], BODY + f"Ticket: {line}\n", "o/r", "abc1234", issue_comments=[])
                self.assertIn("ticket: 59", lines)
        with self.assertRaisesRegex(record.Unsupported, "names #59; the tracker's issues are written o/tracker#<n>"):
            record.build(PR, [REVIEW], [], BODY + "Ticket: #59 · y\n", "o/r", "abc1234", issue_comments=[])

    def test_a_part_of_a_stacked_ticket_reads_its_stack_and_claims(self):
        body = "Ticket: PROJ-9 · part 2 of 3 · base: PROJ-9-one\nClaims: AC-1, AC-3\n" + BODY
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn('stack: {part: 2, of: 3, base: "PROJ-9-one"}', lines)
        self.assertIn('claims: ["AC-1", "AC-3"]', lines)
        lines, _ = record.build(PR, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("stack: none", lines)
        self.assertIn("claims: none", lines)
        two = "Ticket: PROJ-9 — the template's line\n" + body
        with self.assertRaisesRegex(record.Unsupported, "2 'Ticket:' lines"):
            record.build(PR, [REVIEW], [], two, "o/r", "abc1234", issue_comments=[])
        with self.assertRaisesRegex(record.Unsupported, "2 'Ticket:' lines"):
            record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [], two, "o/r")
        kept = "<!-- A ticket in parts: its Ticket: line is `Ticket: <key> · part k of n · base: <branch>`. -->\n" + body
        lines, _ = record.build(PR, [REVIEW], [], kept, "o/r", "abc1234", issue_comments=[])
        self.assertIn('stack: {part: 2, of: 3, base: "PROJ-9-one"}', lines)

    def test_plan_build_and_key_are_quoted(self):
        body = BODY.replace("Plan: approved by alice", "Plan: approved by alice: see the thread")
        lines, _ = record.build(PR, [REVIEW], [thread("Should fix", ("bob", "Agree."))], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn('plan: "approved by alice: see the thread"', lines)
        self.assertIn('build: "passed"', lines)
        self.assertIn('  - key: "R-001/x.py::f"', lines)

    def test_the_standards_sha_comes_from_the_findings_review(self):
        review = {**REVIEW, "body": REVIEW["body"] + "standards: 1234567\n"}
        lines, _ = record.build(PR, [review], [], BODY, "o/r", None, issue_comments=[])
        self.assertIn("standards_sha: 1234567", lines)

    def test_a_review_on_uncommitted_standards_keeps_the_suffix(self):
        review = {**REVIEW, "body": REVIEW["body"] + "standards: 1234567 + uncommitted\n"}
        lines, _ = record.build(PR, [review], [], BODY, "o/r", None, issue_comments=[])
        self.assertIn("standards_sha: 1234567 + uncommitted", lines)
        self.assertEqual(record.standards_line({"body": "standards: none + uncommitted"}), "none + uncommitted")
        for line in ("standards: 1234567 + dirty", "standards: 1234567+uncommitted"):
            with self.subTest(line=line):
                self.assertIsNone(record.standards_line({"body": line}))

    def test_disagree_with_no_reason_is_unanswered_on_should_fix_only(self):
        text, report = self.run_build(thread("Should fix", ("bob", "**Disagree**")))
        self.assertIn('    verdict: unanswered\n    why: "disagree with no reason"\nquestions:', text)
        self.assertEqual(report, ["unanswered: PRRT_1 R-001/x.py::f (disagree with no reason)"])

        text, report = self.run_build(thread("Suggestion", ("bob", "disagree")))
        self.assertEqual(report, [])
        self.assertIn("verdict: disagree", text)
        self.assertNotIn("reason:", text)

    def test_a_prose_first_reply_is_settled_by_a_later_agree_whose_author_adjudicates(self):
        text, report = self.run_build(thread("Should fix", ("bob", "Hm, not sure about this."), ("carol", "Agree.")))
        self.assertEqual(report, [])
        self.assertIn("verdict: agree", text)
        self.assertIn("adjudicated_by: carol", text)

    def test_a_reasonless_disagree_is_settled_by_a_disagree_with_its_reason(self):
        text, report = self.run_build(thread("Should fix", ("bob", "Disagree"), ("bob", "Disagree, because fixtures are exempt")))
        self.assertEqual(report, [])
        self.assertIn("verdict: disagree", text)
        self.assertIn('reason: "because fixtures are exempt"', text)

    def test_agreed_reads_as_agree(self):
        text, report = self.run_build(thread("Should fix", ("bob", "Agreed, will fix")))
        self.assertEqual(report, [])
        self.assertIn("verdict: agree", text)
        self.assertEqual(record.verdict_of("I agree"), (None, ""))

    def test_a_prose_first_reply_and_nothing_after_is_unparsed(self):
        text, report = self.run_build(thread("Should fix", ("bob", "Looks odd.")))
        self.assertIn('    verdict: unparsed\n    line: "Looks odd."\n', text)
        self.assertEqual(report, ["unparsed: PRRT_1 R-001/x.py::f (first line: Looks odd.)"])
        _, report = self.run_build(thread("Should fix", ("bob", "Looks odd."), ("carol", "Disagree")))
        self.assertEqual(report, ["unparsed: PRRT_1 R-001/x.py::f (first line: Looks odd.)"])

    def test_after_an_open_first_reply_a_later_rival_contests_and_an_earlier_word_does_not(self):
        _, report = self.run_build(thread("Should fix", ("bob", "Hm."), ("carol", "Agree."), ("dave", "Disagree, not here")))
        self.assertEqual(report, ["contested: PRRT_1 R-001/x.py::f (carol: Agree. | dave: Disagree, not here)"])
        text, report = self.run_build(
            thread("Should fix", ("bob", "Hm."), ("carol", "Agree."), ("dave", "Disagree, not here"), ("alice", "Agree, it stays"))
        )
        self.assertEqual(report, [])
        self.assertIn("verdict: agree", text)
        self.assertIn("contested: true", text)
        text, report = self.run_build(thread("Should fix", ("bob", "Hm."), ("carol", "Discuss: why?"), ("dave", "Agree.")))
        self.assertEqual(report, [])
        self.assertNotIn("contested", text)

    def test_a_reasonless_disagree_neither_settles_a_discuss_nor_contests(self):
        th = thread("Should fix", ("bob", "Discuss: why here?"), ("carol", "Disagree"))
        row = record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual(row[5:7], ["discuss", "no"])

    def test_the_attribution_line_is_not_a_disagrees_reason(self):
        text, report = self.run_build(thread("Should fix", ("alice", "Disagree")))
        self.assertIn('    verdict: unanswered\n    why: "disagree with no reason"\n', text)
        self.assertNotIn("reason:", text)
        self.assertEqual(report, ["unanswered: PRRT_1 R-001/x.py::f (disagree with no reason)"])
        th = thread("Should fix", ("alice", "Disagree"))
        row = record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual(row[5], "unanswered")

        text, report = self.run_build(thread("Should fix", ("alice", "Disagree, x")))
        self.assertEqual(report, [])
        self.assertIn('reason: "x"\n', text)
        self.assertNotIn("AI-assisted", text.split("findings:", 1)[1])

        th = thread("Should fix", ("bob", "Discuss: why here?"))
        th["comments"].append({"body": "Disagree\n\n🤖 _AI-assisted reply, approved by @alice._", "author": "alice", "created_at": "2026-09-26T00:30:00Z"})
        row = record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual(row[5], "discuss")

    def test_only_a_last_line_with_the_robot_and_ai_assisted_is_the_attribution(self):
        self.assertEqual(record.verdict_of("Disagree, x"), ("disagree", "x"))
        self.assertEqual(record.verdict_of("Disagree, x\n\n🤖 AI-assisted reply."), ("disagree", "x"))
        self.assertEqual(record.verdict_of("Disagree, x\n\n" + "🤖 _AI-assisted comment, reviewed and approved by @alice before posting._"), ("disagree", "x"))
        self.assertEqual(record.verdict_of(f"Disagree, x\n\n{SLOP_SCORE_ATTRIBUTION}"), ("disagree", "x"))
        self.assertEqual(record.verdict_of("Disagree, the AI-assisted check misses it"), ("disagree", "the AI-assisted check misses it"))
        self.assertEqual(record.verdict_of("Disagree, the 🤖 AI-assisted line stays"), ("disagree", "the 🤖 AI-assisted line stays"))
        self.assertEqual(record.verdict_of("Disagree\n\n🤖 ships with it\n\nthanks"), ("disagree", "🤖 ships with it\n\nthanks"))

    def test_a_questions_answer_has_no_attribution(self):
        text, _ = self.run_build(thread("Question", ("alice", "It reads the cache first.")))
        self.assertIn('    a: "It reads the cache first."\n', text)

    def test_a_reasonless_disagree_and_nothing_after_is_unanswered_with_the_reason(self):
        _, report = self.run_build(thread("Should fix", ("bob", "Disagree"), ("carol", "Still not sure.")))
        self.assertEqual(report, ["unanswered: PRRT_1 R-001/x.py::f (disagree with no reason)"])

    def test_a_finding_nobody_answered_is_recorded_unanswered(self):
        text, report = self.run_build(thread("Should fix"))
        self.assertIn('  - key: "R-001/x.py::f"\n    severity: should-fix\n    at: "x.py:3"\n    thread: PRRT_1\n    verdict: unanswered\nquestions:', text)
        self.assertEqual(report, ["unanswered: PRRT_1 R-001/x.py::f (no reply from a person)"])

    def test_a_question_nobody_answered_is_kept(self):
        text, _ = self.run_build(thread("Question"))
        self.assertIn("  - q: ", text)
        self.assertIn("    unanswered: true\n", text)
        self.assertNotIn("    a: ", text)

    def test_ratchet_counts_reads_the_unsettled_verdicts_into_their_columns(self):
        threads = [thread("Should fix"), thread("Should fix", ("bob", "Looks odd.")), thread("Should fix", ("bob", "Agree."), ("carol", "Disagree, no"))]
        for i, th in enumerate(threads):
            th["id"] = f"PRRT_{i}"
            th["comments"][0]["body"] = th["comments"][0]["body"].replace("R-001", f"R-00{i + 1}")
        lines, _ = record.build(PR, [REVIEW], threads, BODY, "o/r", "abc1234", issue_comments=[])
        rows = {f["rule"]: f for f in ratchet_counts.findings("\n".join(lines) + "\n", "pr-0001.yaml")}
        self.assertEqual([rows[r]["verdict"] for r in ("R-001", "R-002", "R-003")], ["unanswered", "unanswered", "open-contest"])
        self.assertFalse(rows["R-003"]["contested"])

    def test_an_unmerged_pull_request_is_refused_with_or_without_a_findings_review(self):
        unmerged = {**PR, "state": "open", "merged": False, "merged_at": None}
        for reviews in ([REVIEW], [{**REVIEW, "body": "LGTM", "user": {"login": "bob"}, "commit_id": "b" * 40}]):
            with self.subTest(reviews=reviews[0]["body"][:6]), self.assertRaisesRegex(record.Unsupported, "no 'merged_at'"):
                record.build(unmerged, reviews, [], BODY, "o/r", "abc1234", issue_comments=[])

    def test_no_findings_review_and_nothing_a_reviewer_said_is_refused(self):
        # Bots are not reviewers, and the author's review summaries and conversation comments are not
        # review threads: nothing they wrote makes a record.
        own = {**REVIEW, "body": "LGTM", "user": {"login": "alice"}, "commit_id": "b" * 40}
        bots = {**own, "id": 2, "user": {"login": "copilot-pull-request-reviewer"}}
        cases = {
            "no review at all": ([], [], []),
            "the author's review summary and a bot's": ([own, bots], [], []),
            "the author's and a bot's comments": ([], [], [comment(5, "Ready for another look.", login="alice"), comment(6, "Coverage 91%.", login="ci[bot]")]),
            "a thread a bot opened": ([], [persons_thread("copilot", ("alice", "Thanks."))], []),
            "a thread the author opened with an AI-drafted comment": ([], [ai_drafted_thread("alice")], []),
        }
        for name, (reviews, threads, comments) in cases.items():
            with self.subTest(name), self.assertRaisesRegex(
                record.Unsupported, "no findings review, no thread the author opened in their own words and nothing a reviewer said.*nothing was reviewed"
            ):
                record.build(PR, reviews, threads, BODY, "o/r", None, issue_comments=comments)

    def test_a_thread_the_author_opened_alone_makes_a_record_dated_by_its_opening(self):
        # The author reviewing their own pull request is a reviewer like any other.
        th = persons_thread("alice")
        th["comments"][0]["created_at"] = "2026-09-24T18:00:00Z"
        lines, _ = record.build({**PR, "merge_commit_sha": "d" * 40}, [], [th], BODY, "o/r", None, issue_comments=[])
        self.assertIn("date: 2026-09-24", lines)
        self.assertIn("    verdict: unanswered", lines)
        th = persons_thread("alice", ("bob", "Why not the cached frame?"))
        th["comments"][0]["created_at"], th["comments"][1]["created_at"] = "2026-09-24T18:00:00Z", "2026-09-26T18:00:00Z"
        lines, _ = record.build({**PR, "merge_commit_sha": "d" * 40}, [], [th], BODY, "o/r", None, issue_comments=[])
        self.assertIn("date: 2026-09-24", lines)

    def test_a_reviewers_summary_or_comment_alone_makes_a_record_dated_by_the_first(self):
        summary = {**REVIEW, "id": 2, "state": "APPROVED", "body": "Split the docs out next time.", "user": {"login": "bob"},
                   "commit_id": "b" * 40, "submitted_at": "2026-09-29T18:00:00Z"}
        pr = {**PR, "merge_commit_sha": "d" * 40}
        for reviews, comments, date in (
            ([summary], [], "2026-09-29"),
            ([], [comment(5, "Please add a test.")], "2026-09-25"),
            ([summary], [comment(5, "Ready.", login="alice"), comment(7, "Please add a test.")], "2026-09-27"),
        ):
            with self.subTest(date=date):
                lines, _ = record.build(pr, reviews, [], BODY, "o/r", None, issue_comments=comments)
                self.assertIn(f"date: {date}", lines)
                self.assertIn("merged: 2026-09-27", lines)
                self.assertIn("head: ddddddd", lines)
                self.assertIn("findings: []", lines)

    def test_a_review_headed_review_is_a_findings_review_and_standards_none_reads_as_none(self):
        review = {**REVIEW, "body": "## Review\nreviewed: " + "a" * 40 + "\nstandards: none\n\n\n🤖 _AI-assisted comment, posted by @alice. AI assistance level: 5/5 (not read by a person)._"}
        lines, _ = record.build(PR, [review], [], BODY, "o/r", None, issue_comments=[])
        self.assertIn("standards_sha: none", lines)
        self.assertIn("head: aaaaaaa", lines)
        lines, _ = record.build(PR, [review], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("standards_sha: abc1234", lines)

    def test_a_findings_review_may_carry_any_verdict_the_person_chose(self):
        # A dismissed one too: dismissal withdraws the verdict, not the findings or the head reviewed.
        for verdict in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            with self.subTest(verdict=verdict):
                review = {**REVIEW, "state": verdict}
                self.assertEqual(record.findings_reviews([review]), [(review, "a" * 40)])
        self.assertEqual(record.findings_reviews([{**REVIEW, "state": "PENDING"}]), [])
        notes = {**REVIEW, "state": "DISMISSED", "body": "## Review notes\n\nLooks fine."}
        self.assertEqual(record.findings_reviews([notes]), [])

    def test_a_dismissed_findings_review_keeps_its_head_in_the_state_and_the_record(self):
        pr = {**PR, "head": {"ref": "b", "sha": "c" * 40}, "merge_commit_sha": "d" * 40}
        review = {**REVIEW, "state": "DISMISSED", "user": {"login": "bob"}, "commit_id": "a" * 40}
        self.assertIn("findings review: 1 reviewed: " + "a" * 40, record.state(pr, [review], [], BODY, "o/r"))
        lines, _ = record.build(pr, [review], [thread("Should fix")], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("head: aaaaaaa", lines)
        self.assertIn("reviews: []", lines)

    def test_a_reply_with_an_empty_body_is_refused(self):
        th = thread("Should fix")
        th["comments"].append({"body": " \n", "author": "bob", "created_at": "2026-09-26T00:20:00Z"})
        with self.assertRaisesRegex(record.Unsupported, "PRRT_1 has a reply by bob with an empty body"):
            record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[])
        with self.assertRaisesRegex(record.Unsupported, "empty body"):
            record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [th], BODY, "o/r")
        th["comments"][-1]["author"] = "copilot"
        self.assertIn("    verdict: unanswered\n", self.run_build(th)[0])

    def test_an_empty_labeled_line_is_refused_not_read_from_the_next_line(self):
        cases = {
            "Rules checked:\nDeclined: R-001/x.py::f — y\n": "the 'Rules checked:' line is empty",
            "Rules checked: none.\n": "'Rules checked:' line has 'none.'",
            "Rules checked: None (no rule fired)\n": "'Rules checked:' line has 'None \\(no rule fired\\)'",
            "Declined: fixtures are exempt\n": "'Declined:' line has 'fixtures are exempt'",
        }
        for extra, error in cases.items():
            with self.subTest(extra=extra), self.assertRaisesRegex(record.Unsupported, error):
                record.build(PR, [REVIEW], [], BODY.replace("Plan:", extra + "Plan:"), "o/r", "abc1234", issue_comments=[])
        with self.assertRaisesRegex(record.Unsupported, "the 'Build:' line is empty"):
            record.build(PR, [REVIEW], [], BODY.replace("Build: passed", "Build:"), "o/r", "abc1234", issue_comments=[])
        with self.assertRaisesRegex(record.Unsupported, "the 'Ticket:' line is empty"):
            record.build(PR, [REVIEW], [], "Ticket:\nPROJ-9 · y\n" + BODY, "o/r", "abc1234", issue_comments=[])
        with self.assertRaisesRegex(record.Unsupported, "the 'Ticket:' line is empty"):
            record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [], "Ticket:\nPROJ-9 · y\n" + BODY, "o/r")
        with self.assertRaisesRegex(record.Unsupported, "does not open with a finding key"):
            record.build(PR, [REVIEW], [], BODY.replace("Plan:", "Rules checked: `R-001/x.py::f` fixed\nPlan:"), "o/r", "abc1234", issue_comments=[])

    def test_optional_lines_read_none_and_every_citation_form(self):
        lines, _ = record.build(PR, [REVIEW], [], BODY.replace("Plan:", "Rules checked: none\nPlan:"), "o/r", "abc1234", issue_comments=[])
        self.assertIn("  fired: []", lines)
        body = BODY.replace("Plan:", "Rules checked: D-008@widgets/x.py::f fixed, term/T-010/y.md::- declined\nPlan:")
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn('  fired: ["D-008@widgets/x.py::f fixed", "term/T-010/y.md::- declined"]', lines)

    def test_a_block_missing_a_required_line_is_refused(self):
        for line in ("Build: passed", "Gates: lint 0", "Tokens since the build started: 1 in", "Plan: approved by alice"):
            with self.subTest(line=line), self.assertRaisesRegex(record.Unsupported, "Already checked block has no '" + line.split(":")[0]):
                record.build(PR, [REVIEW], [], BODY.replace(line, ""), "o/r", "abc1234", issue_comments=[])

    def test_the_builds_rules_checked_line_is_its_firings(self):
        lines, _ = record.build(
            merged_0042(), json.loads((FIXTURE / "reviews.json").read_text()), [],
            (FIXTURE / "body.md").read_text(), "o/r", "9f01488", issue_comments=[],
        )
        self.assertIn('  fired: ["R-002", "R-004", "R-006", "R-007", "R-009", "R-012", "R-013"]', lines)
        self.assertIn("  declined: []", lines)
        lines, _ = record.build(PR, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("  fired: []", lines)
        body = BODY.replace("Plan:", "Declined: R-001/x.py::f — fixtures are exempt; R-002/y.py::g — out of scope\nPlan:")
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn('  declined: ["R-001/x.py::f — fixtures are exempt", "R-002/y.py::g — out of scope"]', lines)

    def test_the_gates_corrections_are_its_nominated_and_procedure_lists(self):
        body = BODY.replace("Plan:", "Nominated: plan gate: retry 3 -> retry once; diff gate: x -> y\nProcedure: procedure: plan gate: asked twice -> ask once\nPlan:")
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn('  nominated: ["plan gate: retry 3 -> retry once", "diff gate: x -> y"]', lines)
        self.assertIn('  procedure: ["procedure: plan gate: asked twice -> ask once"]', lines)
        lines, _ = record.build(PR, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("  nominated: []", lines)
        self.assertIn("  procedure: []", lines)

    def test_the_ripple_line_is_its_inner_ripple(self):
        body = BODY.replace("Plan:", "Ripple: predicted gadgets, sprockets · verified gadgets · breaks none\nPlan:")
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn('  ripple: {predicted: ["gadgets", "sprockets"], verified: ["gadgets"], breaks: []}', lines)
        lines, _ = record.build(PR, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("  ripple: none", lines)

        body = BODY.replace("Plan:", "Ripple: predicted none · verified none · breaks none\nPlan:")
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn("  ripple: {predicted: [], verified: [], breaks: []}", lines)

    def test_a_ripple_line_not_as_body_md_gives_it_is_refused(self):
        for line in (
            "Ripple: gadgets broke",
            "Ripple: predicted · verified · breaks none",
            "Ripple:",
            "Ripple: predicted none, gadgets · verified none · breaks none",
            "Ripple: predicted , · verified none · breaks none",
        ):
            with self.subTest(line=line), self.assertRaises(record.Unsupported):
                record.build(PR, [REVIEW], [], BODY.replace("Plan:", f"{line}\nPlan:"), "o/r", "abc1234", issue_comments=[])

    def test_the_reproduced_line_is_its_inner_reproduced_whole(self):
        body = BODY.replace("Plan:", "Reproduced: tests/unit/test_x.py::test_gain failed before the fix; gain was 0.98\nPlan:")
        lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
        self.assertIn('  reproduced: "tests/unit/test_x.py::test_gain failed before the fix; gain was 0.98"', lines)
        # revise reads a defect fix as a record whose inner.reproduced is not `none`: a
        # build with no bug path, or one that wrote `none`, gives exactly that.
        for body in (BODY, BODY.replace("Plan:", "Reproduced: none\nPlan:")):
            lines, _ = record.build(PR, [REVIEW], [], body, "o/r", "abc1234", issue_comments=[])
            self.assertIn("  reproduced: none", lines)
        with self.assertRaisesRegex(record.Unsupported, "'Reproduced:' line is empty"):
            record.build(PR, [REVIEW], [], BODY.replace("Plan:", "Reproduced:\nPlan:"), "o/r", "abc1234", issue_comments=[])

    def test_a_reopened_design_is_its_inner_reopened(self):
        two = "Reopened: PRRT_9 · the frame was wrong\nReopened: PRRT_12 · the cache was wrong\nPlan:"
        lines, _ = record.build(PR, [REVIEW], [], BODY.replace("Plan:", two), "o/r", "abc1234", issue_comments=[])
        self.assertIn('  reopened: ["PRRT_9 · the frame was wrong", "PRRT_12 · the cache was wrong"]', lines)
        lines, _ = record.build(PR, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("  reopened: []", lines)
        with self.assertRaisesRegex(record.Unsupported, "'Reopened:' line is empty"):
            record.build(PR, [REVIEW], [], BODY.replace("Plan:", "Reopened:\nPlan:"), "o/r", "abc1234", issue_comments=[])

    def test_the_builds_depth_line_is_its_inner_depth(self):
        lines, _ = record.build(PR, [REVIEW], [], BODY.replace("Plan:", "Depth: light\nPlan:"), "o/r", "abc1234", issue_comments=[])
        self.assertIn('  depth: "light"', lines)
        lines, _ = record.build(PR, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("  depth: none", lines)
        for depth in ("Light", "deep (raised)", "shallow"):
            with self.assertRaisesRegex(record.Unsupported, f"the 'Depth:' line has '{re.escape(depth)}', not one of light, standard, deep"):
                record.build(PR, [REVIEW], [], BODY.replace("Plan:", f"Depth: {depth}\nPlan:"), "o/r", "abc1234", issue_comments=[])

    def test_a_body_with_no_block_was_not_built(self):
        lines, _ = record.build(PR, [REVIEW], [], "Ticket: PROJ-1 · x\n\n## Summary\n\nBy hand.\n", "o/r", "abc1234", issue_comments=[])
        self.assertEqual([line for line in lines if line.startswith(("build:", "plan:", "inner:"))], ["build: none", "plan: none", "inner: none"])

    def test_a_persons_review_under_a_review_heading_is_not_a_findings_review(self):
        delta = "## Review — delta against 1234567\nreviewed: " + "a" * 40 + "\n\n🤖 _AI-assisted comment, posted by @alice. AI assistance level: 5/5 (not read by a person)._"
        for body in ("## Review notes\n\nLooks fine; one question below.", "## Review\nreviewed: " + "a" * 40 + "\n", delta):
            with self.subTest(body=body.splitlines()[0]):
                person = {**REVIEW, "id": 9, "body": body, "user": {"login": "bob"}, "commit_id": "c" * 40}
                self.assertEqual(record.findings_reviews([person]), [])
                printed = record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [person], [], BODY, "o/r")
                self.assertIn("findings review: none", printed)
                lines, _ = record.build({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [person], [], BODY, "o/r", "abc1234", issue_comments=[])
                self.assertTrue(any("by: bob" in line for line in lines))

    def test_a_findings_review_with_no_reviewed_line_is_refused(self):
        with self.assertRaisesRegex(record.Unsupported, "no 'reviewed: <sha>' line"):
            record.build(PR, [{**REVIEW, "body": "## Standards review\n\n\n🤖 _AI-assisted comment, posted by @alice. AI assistance level: 5/5 (not read by a person)._"}], [], BODY, "o/r", "abc1234", issue_comments=[])

    def test_a_findings_review_with_no_submitted_at_is_refused(self):
        review = {k: v for k, v in REVIEW.items() if k != "submitted_at"}
        with self.assertRaisesRegex(record.Unsupported, "findings review .* has no 'submitted_at'"):
            record.build(PR, [review], [], BODY, "o/r", "abc1234", issue_comments=[])

    def test_a_review_from_another_repository_is_refused(self):
        for url in ("https://github.com/x/y/pull/1", "https://github.com/o/r2/pull/1#pullrequestreview-1", "https://github.com/xo/r/pull/1"):
            with self.subTest(url=url), self.assertRaisesRegex(record.Unsupported, "is not on o/r"):
                record.build(PR, [{**REVIEW, "html_url": url}], [], BODY, "o/r", "abc1234", issue_comments=[])
            with self.subTest(url=url, mode="state"), self.assertRaisesRegex(record.Unsupported, "is not on o/r"):
                record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [{**REVIEW, "html_url": url}], [], BODY, "o/r")

    def test_a_review_with_no_html_url_is_refused(self):
        for review in ({k: v for k, v in REVIEW.items() if k != "html_url"}, {**REVIEW, "html_url": None}, {**REVIEW, "html_url": ""}):
            with self.subTest(review=review.get("html_url")), self.assertRaisesRegex(record.Unsupported, "review 1 has no 'html_url'"):
                record.build(PR, [review], [], BODY, "o/r", "abc1234", issue_comments=[])
            with self.subTest(review=review.get("html_url"), mode="state"), self.assertRaisesRegex(record.Unsupported, "review 1 has no 'html_url'"):
                record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [review], [], BODY, "o/r")

    def test_a_review_on_the_repo_is_accepted_whatever_the_case(self):
        for url in ("https://github.com/o/r/pull/1#pullrequestreview-1", "https://github.com/O/R/pull/1"):
            with self.subTest(url=url):
                lines, _ = record.build(PR, [{**REVIEW, "html_url": url}], [], BODY, "o/r", "abc1234", issue_comments=[])
                self.assertEqual(lines[0], f"contract: {record.RECORD_CONTRACT}")

    def test_no_standards_sha_is_refused(self):
        with self.assertRaisesRegex(record.Unsupported, "no --standards-sha"):
            record.build(PR, [REVIEW], [], BODY, "o/r", None, issue_comments=[])

    def with_key(self, line: str, *replies: tuple[str, str], above: str = "") -> dict:
        th = thread("Should fix", *replies)
        body = th["comments"][0]["body"].replace("key: `R-001/x.py::f`", line)
        th["comments"][0]["body"] = body.replace("\n\n<details>", f"\n\n{above}<details>") if above else body
        return th | {"is_resolved": False, "is_outdated": False}

    def test_a_bare_key_is_read(self):
        for line, key in (
            ("key: R-001/x.py::f", "R-001/x.py::f"),
            ("key: R-001/README.md::Install steps", "R-001/README.md::Install steps"),
            ("key: R-001/x.py::f</details>", "R-001/x.py::f"),
        ):
            with self.subTest(line=line):
                text, _ = self.run_build(self.with_key(line, ("bob", "Agree.")))
                self.assertIn(f'  - key: "{key}"\n', text)

    def test_a_key_line_outside_the_standard_block_is_not_read(self):
        th = self.with_key("key: R-001/x.py::f", ("bob", "Agree."), above="```yaml\nkey: true\n```\n\n")
        text, _ = self.run_build(th)
        self.assertIn('  - key: "R-001/x.py::f"\n', text)
        self.assertNotIn('key: "true"', text)

    def test_a_key_line_after_the_standard_block_is_not_read(self):
        th = self.with_key("", ("bob", "Agree."))
        th["comments"][0]["body"] = th["comments"][0]["body"].replace("</details>\n\n", "</details>\n\nkey: R-001/x.py::f\n\n")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(record.Unsupported, "thread PRRT_1 is a finding with no readable 'key:' line"):
            self.run_build(th)

    def test_a_bare_legacy_other_key_is_uncited(self):
        text, _ = self.run_build(self.with_key("key: other/x.py::f", ("bob", "Agree.")))
        self.assertIn("findings: []", text)
        self.assertIn("  - thread: PRRT_1\n    by: review\n", text)

    def test_a_key_that_is_not_a_citation_is_unreadable(self):
        for line in ("key:", "key: true", "key: **R-001/x.py::f**", "key: R-001 is the rule here"):
            with self.subTest(line=line), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(record.Unsupported, "thread PRRT_1 is a finding with no readable 'key:' line"):
                    self.run_build(self.with_key(line, ("bob", "Agree.")))

    def test_an_unreadable_key_is_listed_by_state_with_its_verdict_and_refused_by_the_record(self):
        broken = self.with_key("key: true", ("bob", "Agree."))
        cited = thread("Suggestion", ("bob", "Agree."))
        cited["id"] = "PRRT_2"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rows = record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [broken, cited], BODY, "o/r")
        self.assertIn("thread PRRT_1 has a Standard block with no readable 'key:' line", err.getvalue())
        rows = {r.split(" | ")[0]: r.split(" | ") for r in rows if r.startswith("PRRT_")}
        self.assertEqual(rows["PRRT_1"][1], "-")
        self.assertEqual(rows["PRRT_1"][5], "agree")
        self.assertEqual(rows["PRRT_2"][1:2] + rows["PRRT_2"][5:6], ["R-001/x.py::f", "agree"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(record.Unsupported, "thread PRRT_1 is a finding with no readable 'key:' line"):
            record.build(PR, [REVIEW], [broken, cited], BODY, "o/r", "abc1234", issue_comments=[])

    def bad_label(self, *replies: tuple[str, str]) -> dict:
        th = self.with_key("key: `R-001/x.py::f`", *replies)
        th["comments"][0]["body"] = th["comments"][0]["body"].replace("**Should fix** — a finding", "**Suggestion — a finding**")
        return th

    def test_a_finding_whose_label_is_not_one_of_the_four_is_recorded_unparsed(self):
        cited = thread("Suggestion", ("bob", "Agree."))
        cited |= {"id": "PRRT_2", "is_resolved": False, "is_outdated": False}
        lines, report = record.build(PR, [REVIEW], [self.bad_label(("bob", "Agree.")), cited], BODY, "o/r", "abc1234", issue_comments=[])
        text = "\n".join(lines)
        self.assertIn(
            '  - key: "R-001/x.py::f"\n    severity: unparsed\n    at: "x.py:3"\n    thread: PRRT_1\n    verdict: unparsed\n'
            '    line: "**Suggestion — a finding**"\n',
            text,
        )
        self.assertIn("    thread: PRRT_2\n    verdict: agree\n", text)
        self.assertIn("adjudicated_by: bob", text)
        self.assertEqual(report, ["unparsed label: PRRT_1 R-001/x.py::f (first line: **Suggestion — a finding**)"])
        # The rule's firing is still counted, its verdict apart from the unanswered.
        counted = ratchet_counts.findings(text + "\n", "pr-0001.yaml")
        self.assertEqual([f["verdict"] for f in counted if f["rule"] == "R-001"], ["unlabeled", "agree"])

    def test_an_uncited_finding_whose_label_is_not_one_of_the_four_is_an_unparsed_review_thread(self):
        th = self.bad_label(("bob", "Disagree."))
        th["comments"][0]["body"] = th["comments"][0]["body"].replace("key: `R-001/x.py::f`", "key: other/x.py::f")
        text, report = self.run_build(th)
        self.assertIn("findings: []", text)
        self.assertIn("    by: review\n    authorship: ai-drafted\n    severity: unparsed\n", text)
        self.assertIn('    replies: 1\n    verdict: unparsed\n    line: "**Suggestion — a finding**"\n', text)
        self.assertEqual(report, ["unparsed label: PRRT_1 (first line: **Suggestion — a finding**)"])

    def test_an_unparsed_label_is_not_judged_and_is_refused_by_state(self):
        th = self.bad_label(("bob", "Yes, that's a bug."))
        self.assertEqual(record.undecided([th], "alice"), [])
        with self.assertRaisesRegex(record.Unsupported, r"thread PRRT_1 is a finding with the label '\*\*Suggestion — a finding\*\*', not one of the four"):
            record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [th], BODY, "o/r")

    def test_the_cli_counts_the_unparsed_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "pr.json").write_text(json.dumps(PR))
            (tmp / "reviews.json").write_text(json.dumps([REVIEW]))
            (tmp / "comments.json").write_text(json.dumps([self.bad_label(("bob", "Agree."))]))
            (tmp / "issue.json").write_text("[]")
            (tmp / "body.md").write_text(BODY)
            args = ["--pr", tmp / "pr.json", "--reviews", tmp / "reviews.json", "--comments", tmp / "comments.json"]
            args += ["--issue-comments", tmp / "issue.json", "--body", tmp / "body.md", "--repo", "o/r", "--standards-sha", "abc1234"]
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(record.main([str(a) for a in [*args, "--out", tmp / "pr-0001.yaml"]]), 0)
            self.assertTrue((tmp / "pr-0001.yaml").exists())
            self.assertTrue(err.getvalue().endswith(": 1 finding(s) unsettled, 1 label(s) unparsed\n"))

    def test_a_finding_with_an_unparsed_label_and_an_unreadable_key_is_still_refused(self):
        th = self.bad_label(("bob", "Agree."))
        th["comments"][0]["body"] = th["comments"][0]["body"].replace("key: `R-001/x.py::f`", "key: true")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(record.Unsupported, "no readable 'key:' line"):
            self.run_build(th)

    def test_a_persons_thread_is_not_a_finding(self):
        th = {"id": "PRRT_2", "comments": [{"body": "**Nitpick** — a person's own label", "author": "bob"}]}
        self.assertIsNone(record.parse_finding(th))
        th = {"id": "PRRT_3", "comments": [{"body": "**Should fix** — a person's own label", "author": "bob"}]}
        self.assertIsNone(record.parse_finding(th))

    def test_an_uncited_finding_agreed_by_a_reviewer_is_a_review_thread(self):
        th = thread("Should fix", ("bob", "Agree, good catch."))
        th["comments"][0]["body"] = th["comments"][0]["body"].split("\n\n<details>")[0] + "\n\n" + ATTRIBUTION
        th |= {"is_resolved": False, "is_outdated": True}
        text, report = self.run_build(th)
        self.assertIn("findings: []", text)
        self.assertEqual(report, [])
        self.assertIn(
            "  - thread: PRRT_1\n    by: review\n    authorship: ai-drafted\n    severity: should-fix\n    at: \"x.py:3\"\n", text
        )
        self.assertIn("    outdated: true\n    replies: 1\n    verdict: agree", text)
        row = record.state({**PR, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual(row[1:3] + row[5:6], ["-", "should-fix", "agree"])

    def test_an_uncited_questions_answer_sits_on_its_pointer(self):
        th = thread("Question", ("bob", "It resets on reboot; see FSW doc"))
        th["comments"][0]["body"] = th["comments"][0]["body"].replace("<details><summary>Standard</summary>\n\nkey: `R-001/x.py::f`\n</details>\n\n", "")
        th |= {"is_resolved": False, "is_outdated": False}
        text, _ = self.run_build(th)
        self.assertIn("    verdict: answered\n    a: \"It resets on reboot; see FSW doc\"", text)

    def test_a_legacy_other_key_is_uncited(self):
        th = thread("Suggestion", ("bob", "Agree."))
        th["comments"][0]["body"] = th["comments"][0]["body"].replace("R-001/x.py::f", "other/x.py::f")
        th |= {"is_resolved": True, "is_outdated": False}
        text, _ = self.run_build(th)
        self.assertIn("findings: []", text)
        self.assertIn("    by: review\n    authorship: ai-drafted\n    severity: suggestion\n", text)
        self.assertNotIn("other/", text)


def ai_drafted_thread(opener: str) -> dict:
    th = persons_thread(opener)
    th["comments"][0]["body"] = signed("Why is this here?", opener)
    return th


def persons_thread(opener: str, *replies: tuple[str, str]) -> dict:
    first = {"body": "Why is this here?", "path": "x.py", "original_line": 5, "author": opener, "created_at": "2026-09-27T12:09:00Z"}
    comments = [{"body": signed(body, who), "author": who, "created_at": "2026-09-27T12:20:00Z"} for who, body in replies]
    return {"id": "PRRT_p", "is_resolved": True, "is_outdated": False, "comments": [first, *comments]}


class Threads(unittest.TestCase):
    def section(self, *threads: dict) -> str:
        lines, _ = record.build(PR, [REVIEW], list(threads), BODY, "o/r", "abc1234", issue_comments=[])
        return "\n".join(lines).split("threads:", 1)[1].split("\nreviews:", 1)[0]

    def test_the_authors_disagree_with_a_reason_is_the_verdict(self):
        text = self.section(persons_thread("bob", ("carol", "Agree."), ("alice", "Disagree, the caller needs it")))
        self.assertEqual(
            text,
            '\n  - thread: PRRT_p\n    by: bob\n    authorship: human\n    at: "x.py:5"\n    opened: 2026-09-27\n    resolved: true\n'
            '    outdated: false\n    replies: 2\n    verdict: disagree\n    reason: "the caller needs it"',
        )

    def test_an_unjudged_prose_reply_is_unparsed_and_another_persons_word_no_verdict(self):
        text = self.section(persons_thread("bob", ("alice", "Moved it, thanks."), ("carol", "Agree.")))
        self.assertIn('    replies: 2\n    verdict: unparsed\n    line: "Moved it, thanks."', text)
        self.assertNotIn("reason:", text)

    def test_the_authors_first_reply_with_a_word_is_the_verdict(self):
        text = self.section(persons_thread("bob", ("alice", "Let me look."), ("alice", "Agree, moved it.")))
        self.assertIn("    replies: 2\n    verdict: agree", text)

    def test_a_bots_thread_is_listed_as_bot_and_findings_are_not_listed(self):
        text = self.section(thread("Should fix", ("bob", "Agree.")), persons_thread("copilot-pull-request-reviewer"))
        self.assertIn("    by: bot\n", text)
        self.assertNotIn("PRRT_1", text)
        self.assertIn("    replies: 0\n    verdict: unanswered", text)

    def test_no_reply_from_the_author_is_unanswered_whoever_opened_it(self):
        self.assertIn("    verdict: unanswered", self.section(persons_thread("bob", ("carol", "Agree."))))
        self.assertIn("    verdict: unanswered", self.section(persons_thread("alice", ("bob", "Agree."))))
        self.assertIn("    verdict: agree", self.section(persons_thread("alice", ("alice", "Agree, reply only: a note for reviewers, no change"))))

    def test_a_thread_the_author_opened_with_an_ai_drafted_comment_is_none(self):
        self.assertIn("    verdict: none", self.section(ai_drafted_thread("alice")))

    def test_a_thread_without_githubs_flags_is_refused(self):
        th = persons_thread("bob")
        del th["is_outdated"]
        with self.assertRaisesRegex(record.Unsupported, "PRRT_p has no 'is_outdated' flag"):
            record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[])

    def test_authorship_of_the_opening_comment(self):
        def opener(who: str, body: str) -> str:
            th = persons_thread(who)
            th["comments"][0]["body"] = body
            return self.section(th)

        self.assertIn("    authorship: ai-drafted\n", opener("bob", f"Why?\n\n{ATTRIBUTION}"))
        self.assertIn("    authorship: ai-drafted\n", opener("bob", f"Why?\n\n{SLOP_SCORE_ATTRIBUTION}"))
        self.assertIn("    authorship: ai-drafted\n", opener("bob", "Why?\n\nDrafted with AI assistance."))
        self.assertIn("    by: bot\n    authorship: bot\n", opener("copilot", "Why?"))
        self.assertIn("    authorship: human\n", opener("bob", "Why?"))

    def test_a_thread_the_author_opened_with_a_reworded_attribution_waits_on_nobody(self):
        th = persons_thread("alice")
        th["comments"][0]["body"] = "Why?\n\n🤖 _AI-assisted reply, posted by alice. AI assistance level: 4/5 (read by a person, not edited)._"
        text = self.section(th)
        self.assertIn("    authorship: ai-drafted\n", text)
        self.assertRegex(text, r"\n    verdict: none(\n|$)")

    def test_authorship_of_reads_each_agent_signature(self):
        drafted = (
            "Done.\n\n🤖 _AI-assisted reply, posted by @alice. AI assistance level: 3/5 (lightly edited by a person)._",
            "Done.\n\n🤖 _AI-assisted reply, posted by alice. AI assistance level: 4/5 (read by a person, not edited)._",
            "Done.\n\n🤖 _Beep boop: AI-assisted reply, reviewed and approved by @alice before posting._",
            "Done.\n\n🤖 _AI-assisted reply, posted by @alice. AI slop score: 5/5._",
            "Fixed.\n\nAI assistance level: 1/5 (written by a person).",
            "Rename this.\n\n🤖 *Comment generated by Claude and reviewed by Alice*",
            "🤖 *Comment generated by Claude and reviewed by Alice*\n\nRename this; it reads as a count.\n\nAnd add a test.",
            "Rename this.\n\n*Review drafted with Copilot.*",
            "_Summary written by an LLM._",
            "Done.\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)",
            "Done.\n\nGenerated with Claude Code.",
            "Done.\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
            "Generated by Claude Code",
            "Done.\n\n_AI-assisted reply, posted by @alice._ 🤖",
            "Done.\n\n🤖 _AI-assisted, posted by @alice._",
            "Done.\n\n🤖 Generated with Copilot",
            "Done.\n```\nx = 1\n~~~\n```\n🤖 _AI-assisted reply, posted by @alice._",
        )
        for body in drafted:
            with self.subTest(body=body[-40:]):
                self.assertEqual(record.authorship_of({"author": "bob", "body": body}), "ai-drafted")

    def test_authorship_of_leaves_a_person_writing_about_agents_human(self):
        human = (
            "Was this generated by Claude?",
            "I left 3 comments via 🤖 that point out a couple of should-fix items.",
            "This looks like something an LLM added reflexively; for future AI scraping, don't.",
            "> 🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\nPlease drop the trailer.",
            "> 🤖 _AI-assisted reply, posted by @alice. AI assistance level: 5/5 (not read by a person)._\n\nNo, keep it.",
            "Agents tend to add co-authored-by: claude trailers; we strip them.",
            "Is this review generated by Copilot?",
            "This comment was generated by Claude.",
            "Was that comment written by an AI? It reads oddly.",
            "Keep the 🤖 and the words AI-assisted on a reworded reply.",
            "Please squash; the message reads:\n```\nfix: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n```",
            "The line should read:\n```\n🤖 _AI-assisted reply, posted by @alice. AI assistance level: 5/5 (not read by a person)._\n```",
            "Use `AI assistance level: 5/5` here.",
            "Please add AI assistance level: 3/5 to your replies.\n\nThanks.",
            "A reworded reply must keep 🤖 and 'AI-assisted reply'.",
            "The 🤖 generated by the tool is noise.",
            "This comment was generated by Copilot and is wrong.\n\nPlease rewrite it.",
            "Example:\n```\n🤖 _AI-assisted comment, posted by @alice. AI assistance level: 5/5 (not read by a person)._\n```\nPlease match it.",
            "Example:\n~~~~\n```\nCo-Authored-By: Claude <noreply@anthropic.com>\n~~~~",
            "Generated by Claude Code, this test asserts nothing.",
            "Should this be AI assistance level: 3/5?",
            "Please reword it to:\n\n🤖 _AI-assisted reply, posted by @alice._\n\nThanks.",
            "The footer should end with `AI assistance level: 3/5`",
            "Example:\n````\n```\n🤖 _AI-assisted reply, posted by @alice._\n```\n````",
            "Example:\n```\n``` not a close\n🤖 _AI-assisted reply, posted by @alice._\n```",
            "_Was this review generated by Copilot?_",
            "Please drop this trailer from the commit:\n\n```\nCo-Authored-By: Claude <noreply@anthropic.com>\n```",
        )
        for body in human:
            with self.subTest(body=body[:40]):
                self.assertEqual(record.authorship_of({"author": "bob", "body": body}), "human")

    def test_a_persons_reply_in_a_thread_an_agent_opened_is_human(self):
        opener = {"author": "bob", "body": f"Should this guard stay?\n\n{ATTRIBUTION}"}
        reply = {"author": "carol", "body": "In general, import dependencies directly; no optional-import guards."}
        self.assertEqual((record.authorship_of(opener), record.authorship_of(reply)), ("ai-drafted", "human"))

    def test_the_ai_drafted_wordings_come_from_the_standard(self):
        phrases_line = "  phrases: [drafted with AI assistance, 'written by `loop-review` against']\n"
        body = {"author": "bob", "body": "Why?\n\nWritten with Copilot."}
        listed = {"author": "bob", "body": "Why?\n\nDrafted with AI assistance."}
        self.addCleanup(record.project_phrases.cache_clear)
        self.addCleanup(standard_for_o, PROJECT)
        for phrases, want in (("[written with copilot]", ("ai-drafted", "human")), ("[]", ("human", "human")),
                              ("[drafted with AI assistance, written with copilot]", ("ai-drafted", "ai-drafted"))):
            with self.subTest(phrases=phrases):
                standard_for_o(PROJECT.replace(phrases_line, f"  phrases: {phrases}\n"))
                record.project_phrases.cache_clear()
                self.assertEqual((record.authorship_of(body), record.authorship_of(listed)), want)
        standard_for_o(PROJECT.replace("attribution:\n" + phrases_line, "attribution: not yet recorded\n"))
        record.project_phrases.cache_clear()
        with self.assertRaisesRegex(record.Unsupported, "is refused: .*leaves out attribution"):
            record.authorship_of(body)

    def test_the_standard_marks_a_loop_review_comment_as_ai_drafted_but_not_a_question_about_it(self):
        loop = "## Loop review\nreviewed: 4b8e1d0\n\nWritten by `loop-review` against `standards/rules.md`."
        self.assertEqual(record.authorship_of({"author": "alice", "body": loop}), "ai-drafted")
        for body in ("> Written by `loop-review` against the rules.\n\nWhy this rule?", "Was this written by `loop-review`?"):
            with self.subTest(body=body[:20]):
                self.assertEqual(record.authorship_of({"author": "bob", "body": body}), "human")

    def test_a_finding_settled_by_a_later_reply_is_by_its_author(self):
        lines, _ = record.build(PR, [REVIEW], [thread("Should fix", ("bob", "Hm."), ("carol", "Agree."))], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("    verdict: agree\n    by: carol", "\n".join(lines))
        lines, _ = record.build(PR, [REVIEW], [thread("Should fix", ("bob", "Discuss, not sure"), ("carol", "Agree."))], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("    verdict: agree\n    by: carol", "\n".join(lines))
        lines, _ = record.build(PR, [REVIEW], [thread("Should fix", ("bob", "Discuss, not sure"))], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn("    verdict: discuss\nquestions:", "\n".join(lines))
        self.assertIn("adjudicated_by: none", lines)
        th = thread("Should fix", ("bob", "Agree."), ("carol", "Disagree, not here"), ("alice", "Disagree: carol is right"))
        lines, _ = record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn('    reason: "carol is right"\n    by: alice', "\n".join(lines))

    def test_a_findings_review_with_no_thread_makes_an_empty_record(self):
        lines, report = record.build(PR, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=[])
        for line in ("findings: []", "questions: []", "threads: []", f"head: {'a' * 7}"):
            self.assertIn(line, lines)
        self.assertEqual(report, [])

    def test_ratchet_counts_ignores_the_threads_section(self):
        text = self.section(persons_thread("bob", ("alice", "Disagree, no")))
        record_text = "findings:\n  - key: \"R-001/x.py::f\"\n    verdict: agree\nquestions: []\nthreads:" + text + "\n"
        self.assertEqual(ratchet_counts.findings(record_text, "pr-0001.yaml"), [{"rule": "R-001", "verdict": "agree", "contested": False}])


def state_of(fixture: Path, repo: str, *extra: str) -> tuple[int, str]:
    args = ["--state", "--pr", fixture / "pr.json", "--reviews", fixture / "reviews.json"]
    args += ["--comments", fixture / "comments.json", "--issue-comments", fixture / "issue-comments.json", "--body", fixture / "body.md", "--repo", repo, *extra]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = record.main([str(a) for a in args])
    return rc, out.getvalue()


def rows(printout: str) -> dict[str, list[str]]:
    """The thread table, keyed by thread id."""
    table = printout.split("\nid | ", 1)[1].splitlines()[1:]
    return {r.split(" | ")[0]: r.split(" | ")[1:] for r in table}


class State(unittest.TestCase):
    def test_pr_0042_rows_carry_key_verdict_and_replies_after(self):
        rc, out = state_of(FIXTURE, "o/r")
        self.assertEqual(rc, 0)
        self.assertIn("head: 10858dbb410edcd7f3ec28e68403eb3851994a5c\ndraft: true\nstate: open\n", out)
        self.assertIn("ticket: none\nbuild: Build: passed\n", out)
        self.assertIn("findings review: 9000000001 reviewed: 49a6f0ba0c4d36c6d254c62dfe78dad21260d2d7\n", out)
        table = rows(out)
        self.assertEqual(len(table), 7)
        verdicts = [(r[0].split("/")[0], r[1], r[4], r[5], r[6]) for r in table.values()]
        self.assertEqual(
            verdicts,
            [
                ("term", "should-fix", "agree", "no", "1"),
                ("R-012", "should-fix", "disagree", "no", "0"),
                ("D-008@r", "suggestion", "agree", "no", "1"),
                ("ticket", "suggestion", "discuss", "no", "0"),
                ("ticket", "suggestion", "agree", "no", "1"),
                ("R-004", "suggestion", "agree", "no", "1"),
                ("-", "question", "answered", "no", "0"),
            ],
        )
        self.assertEqual({r[7] for r in table.values()}, {"none"})

    def test_severity_rows_carry_the_anchor_or_the_file(self):
        rc, out = state_of(SEVERITY, "o/r")
        self.assertEqual(rc, 0)
        table = rows(out)
        self.assertEqual(table["PRRT_must"][:6], ["R-002/pkg/reader.py::read", "must-fix", "the reader drops the last packet", "pkg/reader.py:42", "agree", "no"])
        self.assertEqual(table["PRRT_file"][3], "pkg/units.py")

    def test_no_findings_review_lists_the_threads_people_opened(self):
        rc, out = state_of(NO_FINDINGS, "o/r")
        self.assertEqual(rc, 0)
        self.assertIn("state: merged\n", out)
        self.assertIn("ticket: Ticket: PROJ-7 · A change\n", out)
        self.assertIn("build: none\n", out)
        self.assertIn("findings review: none\n", out)
        table = rows(out)
        self.assertEqual(table["PRRT_person"], ["bob", "true", "The loop stops one short; is the last packet dropped?", "pkg/reader.py:42", "unparsed", "no", "1", "true", "", "no"])
        self.assertEqual(table["PRRT_file"], ["bob", "false", "Units would read better in one module.", "pkg/units.py", "unanswered", "no", "0", "false", "", "no"])

    def test_a_pull_request_without_its_draft_field_is_refused(self):
        pr = {k: v for k, v in PR.items() if k != "draft"}
        with self.assertRaisesRegex(record.Unsupported, "no 'draft' field"):
            record.state({**pr, "head": {"ref": "b", "sha": "c" * 40}}, [REVIEW], [], BODY, "o/r")

    def test_the_text_after_the_verdict_is_its_own_column(self):
        rc, out = state_of(FIXTURE, "o/r")
        r012 = next(r for r in rows(out).values() if r[0].startswith("R-012/"))
        self.assertTrue(r012[8].startswith("Nothing callers rely on changes here"))
        self.assertEqual(r012[9], "no")
        pr = {**PR, "head": {"ref": "b", "sha": "c" * 40}}
        th = thread("Should fix", ("bob", "Agree, in a follow-up (PROJ-900)"))
        self.assertEqual(record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")[-2], "in a follow-up (PROJ-900)")

    def test_the_text_after_the_verdict_is_the_first_lines_or_a_disagrees_whole_reason(self):
        self.assertEqual(record.after_verdict("Agree.\n\nFixed in abc123, thanks"), "")
        self.assertEqual(record.after_verdict("**Agree**\nwill follow up"), "")
        self.assertEqual(record.after_verdict("Disagree, fixtures are exempt\nmore"), "fixtures are exempt more")

    def test_a_multi_line_disagrees_reason_is_printed_as_the_record_keeps_it(self):
        pr = {**PR, "head": {"ref": "b", "sha": "c" * 40}}
        th = thread("Should fix", ("bob", "Disagree.\n\nFixtures are exempt here."))
        self.assertEqual(record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")[5:], ["disagree", "no", "0", "none", "Fixtures are exempt here.", "no"])
        lines, _ = record.build(pr, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[])
        self.assertIn('    reason: "Fixtures are exempt here."', lines)
        th = persons_thread("bob", ("alice", "Disagree.\n\nThe caller\nneeds it."))
        self.assertEqual(record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")[-2], "The caller needs it.")

    def test_a_pipe_in_free_text_is_escaped_so_the_row_keeps_eleven_columns(self):
        pr = {**PR, "head": {"ref": "b", "sha": "c" * 40}}
        th = thread("Should fix", ("bob", "Disagree, a | b is fine"))
        th["comments"][0]["body"] = th["comments"][0]["body"].replace("a finding", "x | y")
        row = record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual(len(row), 11)
        self.assertEqual((row[3], row[9]), ("x \\| y", "a \\| b is fine"))

    def test_the_state_header_names_every_column(self):
        rc, out = state_of(FIXTURE, "o/r")
        self.assertIn(
            "\nid | key, or opener | severity, or resolved | headline | path:line | verdict | contested | replies after"
            " | proposed, or outdated | after the verdict | judged\n",
            out,
        )

    def test_a_persons_thread_counts_the_replies_after_the_authors_verdict(self):
        pr = {**PR, "head": {"ref": "b", "sha": "c" * 40}}
        th = persons_thread("bob", ("carol", "Same question."), ("alice", "Agree, moving it."))
        row = record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual((row[5], row[7], row[9]), ("agree", "0", "moving it."))
        th = persons_thread("bob", ("carol", "Same question."), ("alice", "Let me look."))
        row = record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual((row[5], row[7]), ("unparsed", "2"))

    def test_state_opens_with_its_contract_version(self):
        rc, out = state_of(FIXTURE, "o/r")
        self.assertEqual(out.splitlines()[0], f"contract: {record.CONTRACT}")

    def test_state_names_the_pull_requests_author(self):
        rc, out = state_of(FIXTURE, "o/r")
        self.assertIn("author: alice", out.splitlines())

    def test_state_prints_no_record_line(self):
        rc, out = state_of(FIXTURE, "o/r")
        self.assertEqual(rc, 0)
        self.assertNotIn("record:", out)

    def test_proposed_line_contested_and_settled_discuss(self):
        pr = {**PR, "head": {"ref": "b", "sha": "c" * 40}}
        th = thread("Should fix", ("bob", "Discuss: why here?"), ("bob", "Agree."), ("carol", "Thanks."))
        th["comments"][0]["body"] = th["comments"][0]["body"].replace(
            "a finding\n", "a finding\n\nProposed: one line, return `False` instead.\n"
        )
        row = record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual(row[5:], ["agree", "no", "1", "Proposed: one line, return `False` instead.", "", "no"])

        th = thread("Should fix", ("bob", "Agree."), ("carol", "Disagree, not here"))
        row = record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")
        self.assertEqual(row[5:7], ["agree", "yes"])

    def test_replies_after_counts_from_the_reply_that_settled_an_open_finding(self):
        pr = {**PR, "head": {"ref": "b", "sha": "c" * 40}}
        th = thread("Should fix", ("bob", "Hm."), ("carol", "Agree."))
        self.assertEqual(record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")[5:8], ["agree", "no", "0"])
        th = thread("Should fix", ("bob", "Hm."), ("carol", "Agree."), ("bob", "Thanks."))
        self.assertEqual(record.state(pr, [REVIEW], [th], BODY, "o/r")[-1].split(" | ")[5:8], ["agree", "no", "1"])

    def test_a_findings_reviews_standards_line_is_printed_on_its_row(self):
        pr = {**PR, "head": {"ref": "b", "sha": "c" * 40}}
        review = {**REVIEW, "body": REVIEW["body"] + "standards: 1234567\n"}
        self.assertIn(f"findings review: 1 reviewed: {'a' * 40} standards: 1234567", record.state(pr, [review], [], BODY, "o/r"))
        self.assertIn(f"findings review: 1 reviewed: {'a' * 40}", record.state(pr, [REVIEW], [], BODY, "o/r"))
        trial = {**REVIEW, "body": REVIEW["body"] + "standards: 1234567 + uncommitted\n"}
        self.assertIn(f"findings review: 1 reviewed: {'a' * 40} standards: 1234567 + uncommitted", record.state(pr, [trial], [], BODY, "o/r"))
        self.assertIn("contract: 6", record.state(pr, [trial], [], BODY, "o/r"))

    def test_state_writes_nothing_and_refuses_out(self):
        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
                state_of(SEVERITY, "o/r", "--out", Path(d) / "out.yaml")
            self.assertEqual(stop.exception.code, 2)
            self.assertIn("--out is refused with --state", err.getvalue())
            self.assertEqual(list(Path(d).iterdir()), [])


def review(rid: int, state: str, body: str, login: str = "bob") -> dict:
    return {"id": rid, "state": state, "body": body, "user": {"login": login}, "commit_id": "b" * 40,
            "html_url": f"https://github.com/o/r/pull/1#pullrequestreview-{rid}", "submitted_at": f"2026-09-2{rid % 10}T18:00:00Z"}


def comment(cid: int, body: str, login: str = "bob", **drop: bool) -> dict:
    c = {"id": cid, "user": {"login": login}, "body": body, "created_at": f"2026-09-2{cid % 10}T18:00:00Z",
         "html_url": f"https://github.com/o/r/pull/1#issuecomment-{cid}"}
    return {k: v for k, v in c.items() if not drop.get(k)}


class Conversation(unittest.TestCase):
    def build(self, reviews: list, comments: list) -> str:
        return "\n".join(record.build(PR, [REVIEW, *reviews], [], BODY, "o/r", "abc1234", issue_comments=comments)[0])

    def test_an_approval_with_a_body_is_listed_and_a_blank_one_and_the_findings_review_are_not(self):
        text = self.build([review(2, "APPROVED", "Looks right; split the docs into their own PR."), review(3, "APPROVED", "  ")], [])
        self.assertIn("reviews:\n  - review: 2\n    by: bob\n    authorship: human\n    state: approved\n", text)
        self.assertIn('    headline: "Looks right; split the docs into their own PR."', text)
        self.assertNotIn("review: 3", text)
        self.assertNotIn("review: 1\n", text)
        self.assertIn("comments: []", text)

    def test_a_review_pointer_carries_every_line_and_reviews_come_oldest_first(self):
        text = self.build([review(5, "COMMENTED", "Second."), review(4, "APPROVED", "First.\n\nMore.")], [])
        self.assertIn(
            "reviews:\n  - review: 4\n    by: bob\n    authorship: human\n    state: approved\n"
            f"    submitted: {record.when('2026-09-24T18:00:00Z').astimezone().date().isoformat()}\n"
            f"    commit: bbbbbbb\n    headline: \"First.\"\n  - review: 5\n",
            text,
        )

    def test_a_bots_change_request_is_by_bot(self):
        text = self.build([review(4, "CHANGES_REQUESTED", "Lint failed.", login="ci-helper[bot]")], [])
        self.assertIn("    by: bot\n    authorship: bot\n    state: changes_requested", text)

    def test_a_persons_comment_is_human_and_one_with_the_attribution_line_is_ai_drafted(self):
        text = self.build([], [comment(5, "Please add a test."), comment(6, f"Done.\n\n{ATTRIBUTION}", login="alice")])
        self.assertIn("  - comment: 5\n    by: bob\n    authorship: human\n", text)
        self.assertIn("  - comment: 6\n    by: alice\n    authorship: ai-drafted\n", text)

    def test_a_review_in_an_unknown_state_is_refused_naming_it(self):
        with self.assertRaises(record.Unsupported) as e:
            self.build([review(7, "PENDING", "draft")], [])
        self.assertIn("review 7 has the state 'PENDING'", str(e.exception))

    def test_a_comment_without_its_date_is_refused_naming_its_position(self):
        with self.assertRaises(record.Unsupported) as e:
            self.build([], [comment(8, "ok"), comment(9, "no date", created_at=True)])
        self.assertEqual(str(e.exception), "conversation comment 2 has no 'created_at'")

    def test_a_comment_missing_any_field_is_refused_naming_it(self):
        for broken, name in ((comment(1, "x", id=True), "id"), ({k: v for k, v in comment(1, "x").items() if k != "body"}, "body"),
                             ({**comment(1, "x"), "user": None}, "user.login"), ({**comment(1, "x"), "user": {}}, "user.login"),
                             ({**comment(1, "x"), "user": {"login": None}}, "user.login"), ({**comment(1, "x"), "user": "bob"}, "user.login"),
                             ({**comment(1, "x"), "created_at": None}, "created_at")):
            with self.subTest(name=name), self.assertRaises(record.Unsupported) as e:
                self.build([], [broken])
            self.assertEqual(str(e.exception), f"conversation comment 1 has no '{name}'")

    def test_a_quoted_attribution_line_leaves_a_persons_comment_human_and_its_headline_its_own(self):
        quoting = f"> Disagree, out of scope.\n> {ATTRIBUTION}\n\nI still want this split out."
        text = self.build([review(4, "COMMENTED", quoting)], [comment(5, quoting)])
        self.assertIn('    authorship: human\n    state: commented\n', text)
        self.assertIn('  - comment: 5\n    by: bob\n    authorship: human\n', text)
        self.assertEqual(text.count('    headline: "I still want this split out."'), 2)
        th = persons_thread("bob")
        th["comments"][0]["body"] = quoting
        self.assertIn("    authorship: human\n", "\n".join(record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[])[0]))

    def test_a_listed_review_missing_a_field_is_refused_naming_it(self):
        good = review(4, "APPROVED", "Split the docs.")
        for broken, name in (({**good, "user": None}, "user.login"), ({**good, "user": "bob"}, "user.login"), ({**good, "commit_id": None}, "commit_id"),
                             ({k: v for k, v in good.items() if k != "submitted_at"}, "submitted_at")):
            with self.subTest(name=name), self.assertRaises(record.Unsupported) as e:
                self.build([broken], [])
            self.assertEqual(str(e.exception), f"review 4 has no '{name}'")
        with self.assertRaisesRegex(record.Unsupported, "review 4 has a body that is not text"):
            self.build([{**good, "body": ["x"]}], [])

    def test_a_comment_body_that_is_not_text_is_refused(self):
        with self.assertRaisesRegex(record.Unsupported, "conversation comment 1 has a body that is not text"):
            self.build([], [{**comment(5, "x"), "body": None}])

    def test_reviews_not_one_list_of_objects_are_refused(self):
        for shape in ({"reviews": [REVIEW]}, [[REVIEW]]):
            with self.subTest(shape=type(shape).__name__), self.assertRaisesRegex(record.Unsupported, "--reviews is not one list of review objects"):
                record.build(PR, shape, [], BODY, "o/r", "abc1234", issue_comments=[])

    def test_conversation_comments_not_one_list_of_objects_are_refused(self):
        for shape in ({"comments": [comment(5, "x")]}, [[comment(5, "x")]]):
            with self.subTest(shape=type(shape).__name__), self.assertRaisesRegex(record.Unsupported, "--issue-comments is not one list of comment objects"):
                record.build(PR, [REVIEW], [], BODY, "o/r", "abc1234", issue_comments=shape)

    def test_a_repeated_review_or_comment_id_is_refused_naming_both_positions(self):
        with self.assertRaisesRegex(record.Unsupported, r"conversation comments 1 and 3 are both comment 5"):
            self.build([], [comment(5, "x"), comment(6, "y"), comment(5, "x")])
        with self.assertRaisesRegex(record.Unsupported, r"reviews 2 and 3 are both review 4"):
            self.build([review(4, "APPROVED", "ok"), review(4, "APPROVED", "ok")], [])
        with self.assertRaisesRegex(record.Unsupported, r"^review 2 has no 'id'$"):
            self.build([{k: v for k, v in review(4, "APPROVED", "ok").items() if k != "id"}], [])

    def test_a_comment_state_review_is_not_a_findings_review(self):
        with self.assertRaisesRegex(record.Unsupported, "review 1 has the state 'COMMENT'"):
            record.build(PR, [{**REVIEW, "state": "COMMENT"}], [], BODY, "o/r", "abc1234", issue_comments=[])

    def test_state_is_unchanged_by_the_conversation(self):
        rc, out = state_of(FIXTURE, "o/r")
        self.assertEqual((rc, out), (0, (FIXTURE / "state.txt").read_text()))


class Judged(unittest.TestCase):
    """Verdicts the words leave open, judged by pr-reader from what the replies say."""

    PR = {**PR, "head": {"ref": "b", "sha": "c" * 40}}

    def judge(self, th: dict, reply: int | None, verdict: str, *, reason: str = "", done: bool = False, basis: str = "says so") -> dict:
        data = [{"thread": th["id"], "reply": reply, "verdict": verdict, "reason": reason, "done": done, "basis": basis}]
        return record.read_judged(data, record.undecided([th], "alice"))

    def row(self, th: dict, judged: dict | None = None) -> list[str]:
        return record.state(self.PR, [REVIEW], [th], BODY, "o/r", judged)[-1].split(" | ")

    def test_only_what_the_words_leave_open_is_listed_with_the_replies_a_judgment_may_read(self):
        prose = thread("Should fix", ("alice", "Good catch, will do."), ("bob", "Thanks."))
        self.assertEqual([(u["thread"], u["eligible"]) for u in record.undecided([prose], "alice")], [("PRRT_1", [0, 1])])
        for th in (thread("Should fix", ("alice", "Agree.")), thread("Question", ("alice", "Because of X.")), thread("Should fix")):
            with self.subTest(th=th["comments"][1:]):
                self.assertEqual(record.undecided([th], "alice"), [])
        # A word after the prose settles it, so nothing is left to judge.
        self.assertEqual(record.undecided([thread("Should fix", ("alice", "Hmm."), ("alice", "Disagree, it is fine"))], "alice"), [])

    def test_a_discuss_followed_by_prose_lists_only_the_prose_after_it(self):
        th = thread("Should fix", ("bob", "Discuss: why here?"), ("alice", "OK, let's do it."))
        self.assertEqual(record.undecided([th], "alice")[0]["eligible"], [1])
        self.assertEqual(self.row(th, self.judge(th, 1, "agree"))[5], "agree")

    def test_the_authors_own_thread_answered_in_their_own_words_is_judged(self):
        th = persons_thread("alice", ("alice", "Moved it, thanks."))
        self.assertEqual(record.undecided([th], "alice")[0]["eligible"], [0])
        row = self.row(th, self.judge(th, 0, "agree", done=True, basis="says it moved it"))
        self.assertEqual((row[5], row[10]), ("agree", "yes, alice, done: says it moved it"))

    def test_on_a_persons_thread_only_the_authors_replies_may_be_judged(self):
        th = persons_thread("bob", ("carol", "Same question."), ("alice", "Moved it, thanks."))
        self.assertEqual(record.undecided([th], "alice")[0]["eligible"], [1])
        with self.assertRaisesRegex(record.Unsupported, "reply 0 is not one"):
            self.judge(th, 0, "agree")
        row = self.row(th, self.judge(th, 1, "agree", done=True, basis="says it moved it"))
        self.assertEqual((row[5], row[7], row[10]), ("agree", "0", "yes, alice, done: says it moved it"))

    def test_the_authors_word_after_a_discuss_settles_a_persons_thread(self):
        th = persons_thread("bob", ("alice", "Discuss: is it needed?"), ("alice", "Agree, moving it."))
        self.assertEqual(self.row(th)[5], "agree")

    def test_the_authors_prose_agrees_from_pull_request_42_read_agree(self):
        for words in ("This proposal is reasonable. I want to also add a behavior.", "We can relax this a little bit for flexibility.", "Sure. Agreed.", "Good catch. Fix this."):
            with self.subTest(words=words):
                th = thread("Should fix", ("alice", words), ("alice", "Fixed in 21d4cfd."))
                self.assertEqual(self.row(th)[5], "unparsed")
                row = self.row(th, self.judge(th, 0, "agree", basis="agrees in their own words"))
                self.assertEqual((row[5], row[7], row[9], row[10]), ("agree", "1", words, "yes, alice: agrees in their own words"))

    def test_the_authors_own_words_after_another_persons_word_are_judged_and_decide(self):
        th = thread("Should fix", ("bob", "Agree."), ("alice", "No, the caller validates this already."))
        self.assertEqual(record.undecided([th], "alice")[0]["eligible"], [1])
        row = self.row(th, self.judge(th, 1, "disagree", reason="the caller validates this already", basis="says it is not needed"))
        self.assertEqual((row[5], row[7], row[9], row[10]), ("disagree", "0", "the caller validates this already", "yes, alice: says it is not needed"))

        th = thread("Should fix", ("bob", "Agree."), ("alice", "Fixed in 21d4cfd."))
        self.assertEqual(self.row(th)[5], "unparsed")
        row = self.row(th, self.judge(th, 1, "agree", done=True, basis="says it was fixed"))
        self.assertEqual((row[5], row[7], row[10]), ("agree", "0", "yes, alice, done: says it was fixed"))

    def test_a_judged_finding_is_recorded_as_judged_with_its_basis(self):
        th = thread("Should fix", ("bob", "Yes, that's a bug."))
        lines, _ = record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[], judged=self.judge(th, 0, "agree", basis="calls it a bug"))
        text = "\n".join(lines)
        self.assertIn('    verdict: agree\n    judged: true\n    basis: "calls it a bug"\n    by: bob', text)
        self.assertIn("adjudicated_by: bob", text)

    def test_an_uncited_finding_is_judged_through_its_pointer(self):
        th = thread("Should fix", ("bob", "Yes, that's a bug."))
        th["comments"][0]["body"] = f"**Should fix** — a finding\n\n{ATTRIBUTION}"
        th.update(is_resolved=False, is_outdated=False)
        lines, _ = record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[], judged=self.judge(th, 0, "agree"))
        self.assertIn('    verdict: agree\n    judged: true\n    basis: "says so"', "\n".join(lines))

    def test_a_reply_the_judge_cannot_read_stays_unparsed_and_says_why(self):
        th = thread("Should fix", ("bob", "Hmm, maybe?"))
        row = self.row(th, self.judge(th, None, "unclear", basis="neither agrees nor disagrees"))
        self.assertEqual((row[5], row[10]), ("unparsed", "unclear: neither agrees nor disagrees"))

    def test_a_judged_disagree_keeps_its_reason_or_without_one_is_unanswered(self):
        th = thread("Should fix", ("bob", "No, the caller needs the None."))
        row = self.row(th, self.judge(th, 0, "disagree", reason="the caller needs the None."))
        self.assertEqual((row[5], row[9]), ("disagree", "the caller needs the None."))
        lines, _ = record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[], judged=self.judge(th, 0, "disagree"))
        self.assertIn('why: "disagree with no reason"', "\n".join(lines))

    def test_a_judgment_outside_what_the_words_leave_open_is_refused(self):
        prose = thread("Should fix", ("bob", "Sure."))
        cases = [
            ([{"thread": "PRRT_1", "reply": 0, "verdict": "agree", "basis": "x"}], [thread("Should fix", ("bob", "Agree."))], "never overrides a word"),
            ([{"thread": "PRRT_1", "reply": 0, "verdict": "answered", "basis": "x"}], [prose], "not answered"),
            ([{"thread": "PRRT_1", "reply": 0, "verdict": "disagree", "done": True, "basis": "x"}], [prose], "done is for an agree"),
            ([{"thread": "PRRT_1", "reply": 0, "verdict": "disagree", "reason": "not said", "basis": "x"}], [prose], "not in the reply"),
            ([{"thread": "PRRT_1", "reply": 0, "verdict": "agree", "basis": "a\nb"}], [prose], "one non-empty line"),
            ([{"thread": "PRRT_1", "reply": 0, "verdict": "maybe", "basis": "x"}], [prose], "not one of"),
            ([{"thread": "PRRT_1", "reply": 0, "verdict": "agree", "basis": "x"}] * 2, [prose], "judged twice"),
        ]
        for data, threads, why in cases:
            with self.subTest(why=why), self.assertRaisesRegex(record.Unsupported, why):
                record.read_judged(data, record.undecided(threads, "alice"))

    def test_an_unclear_judgment_on_a_persons_thread_is_not_marked_judged(self):
        th = persons_thread("bob", ("alice", "Hmm, maybe later?"))
        row = self.row(th, self.judge(th, None, "unclear", basis="neither agrees nor declines"))
        self.assertEqual((row[5], row[10]), ("unparsed", "unclear: neither agrees nor declines"))
        lines, _ = record.build(PR, [REVIEW], [th], BODY, "o/r", "abc1234", issue_comments=[], judged=self.judge(th, None, "unclear", basis="x"))
        self.assertNotIn("judged: true", "\n".join(lines))

    def test_a_question_the_author_answered_in_their_own_words_is_answered(self):
        th = persons_thread("bob", ("alice", "It keeps the order the caller expects."))
        row = self.row(th, self.judge(th, 0, "answered", basis="answers why it is here"))
        self.assertEqual((row[5], row[10]), ("answered", "yes, alice: answers why it is here"))
        discussed = persons_thread("bob", ("alice", "Discuss: is it needed?"), ("alice", "It keeps the order."))
        with self.assertRaisesRegex(record.Unsupported, "already opened a discussion"):
            self.judge(discussed, 1, "answered")

    def test_a_word_from_the_opener_leaves_the_authors_prose_eligible(self):
        th = persons_thread("bob", ("alice", "Moved it, thanks."), ("bob", "Agree, looks good."))
        self.assertEqual(record.undecided([th], "alice")[0]["eligible"], [0])

    def test_a_later_word_settles_before_any_judgment_and_a_judgment_settles_a_discuss(self):
        th = thread("Should fix", ("bob", "Yes, worth fixing."), ("carol", "Disagree, it is intended"))
        self.assertEqual(record.undecided([th], "alice"), [])
        th = thread("Should fix", ("bob", "Hmm."), ("carol", "Discuss: is it intended?"), ("bob", "Yes, worth fixing."))
        row = self.row(th, self.judge(th, 2, "agree"))
        self.assertEqual(row[5:7], ["agree", "no"])

    def test_malformed_judgments_are_refused(self):
        open_ = record.undecided([thread("Should fix", ("bob", "Sure."))], "alice")
        for data, why in (({"thread": "PRRT_1"}, "not a JSON list"), (["PRRT_1"], "no thread"), ([{"thread": "PRRT_1", "reply": None, "verdict": "unclear", "reason": "x", "basis": "x"}], "unclear judgment has no reason")):
            with self.subTest(why=why), self.assertRaisesRegex(record.Unsupported, why):
                record.read_judged(data, open_)

    def test_the_cli_lists_the_undecided_and_reads_the_judgments(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            th = thread("Should fix", ("bob", "Yes, that's a bug."))
            (tmp / "pr.json").write_text(json.dumps(self.PR))
            (tmp / "reviews.json").write_text(json.dumps([REVIEW]))
            (tmp / "comments.json").write_text(json.dumps([th]))
            (tmp / "issue.json").write_text("[]")
            (tmp / "body.md").write_text(BODY)
            base = ["--pr", tmp / "pr.json", "--reviews", tmp / "reviews.json", "--comments", tmp / "comments.json"]
            base += ["--issue-comments", tmp / "issue.json", "--body", tmp / "body.md", "--repo", "o/r"]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(record.main([str(a) for a in [*base, "--undecided"]]), 0)
            self.assertEqual(json.loads(out.getvalue())[0]["eligible"], [0])
            (tmp / "judged.json").write_text(json.dumps([{"thread": "PRRT_1", "reply": 0, "verdict": "agree", "basis": "calls it a bug"}]))
            runs = []
            for _ in range(2):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(record.main([str(a) for a in [*base, "--state", "--judged", tmp / "judged.json"]]), 0)
                runs.append(out.getvalue())
            self.assertEqual(runs[0], runs[1])
            self.assertIn("| agree | no | 0 | none | Yes, that's a bug. | yes, bob: calls it a bug", runs[0])
            (tmp / "judged.json").write_text(json.dumps([{"thread": "PRRT_1", "reply": 0, "verdict": "agree", "basis": "a\nb"}]))
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                self.assertEqual(record.main([str(a) for a in [*base, "--state", "--judged", tmp / "judged.json"]]), 1)
            self.assertIn("not one non-empty line", err.getvalue())

    def test_a_dump_file_that_is_missing_is_refused_naming_it(self):
        missing = Path(tempfile.gettempdir()) / "no-such-dir"
        with self.assertRaisesRegex(record.Unsupported, "judged.json cannot be read"):
            record.read_json(missing / "judged.json")
        with self.assertRaisesRegex(record.Unsupported, "body.md cannot be read"):
            record.read_text(missing / "body.md")

    def test_undecided_is_refused_beside_state_out_or_judged(self):
        for extra in (["--state"], ["--out", "x.yaml"], ["--judged", "j.json"]):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                record.main(["--pr", "p", "--reviews", "r", "--comments", "c", "--issue-comments", "i", "--body", "b", "--repo", "o/r", "--undecided", *extra])


class Arguments(unittest.TestCase):
    def test_the_pull_request_inputs_are_required(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            record.main(["--state", "--pr", str(FIXTURE / "pr.json")])
        self.assertEqual(stop.exception.code, 2)
        self.assertIn("required: --reviews, --comments, --issue-comments, --body, --repo", err.getvalue())


class Main(unittest.TestCase):
    def test_unsupported_input_exits_1_with_the_reason_on_stderr(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "pr.json").write_text(json.dumps(PR))
            (d / "reviews.json").write_text(json.dumps([REVIEW]))
            (d / "comments.json").write_text(json.dumps({"review_threads": []}))
            (d / "issue-comments.json").write_text("[]")
            (d / "body.md").write_text(BODY.replace("Build: passed", ""))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = record.main([
                    "--pr", str(d / "pr.json"), "--reviews", str(d / "reviews.json"),
                    "--comments", str(d / "comments.json"), "--issue-comments", str(d / "issue-comments.json"), "--body", str(d / "body.md"),
                    "--repo", "o/r", "--out", str(d / "out.yaml"), "--standards-sha", "abc1234",
                ])
            self.assertEqual(rc, 1)
            self.assertIn("record.py: the Already checked block has no 'Build:' line", err.getvalue())
            self.assertFalse((d / "out.yaml").exists())

    def test_a_dump_file_that_is_not_json_exits_1_naming_it(self):
        for broken in ("pr.json", "reviews.json", "comments.json", "issue-comments.json"):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory() as d:
                d = Path(d)
                (d / "pr.json").write_text(json.dumps(PR))
                (d / "reviews.json").write_text(json.dumps([REVIEW]))
                (d / "comments.json").write_text(json.dumps({"review_threads": []}))
                (d / "issue-comments.json").write_text("[]")
                (d / "body.md").write_text(BODY)
                (d / broken).write_text('[{"id": 1,')
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = record.main([
                        "--pr", str(d / "pr.json"), "--reviews", str(d / "reviews.json"),
                        "--comments", str(d / "comments.json"), "--issue-comments", str(d / "issue-comments.json"), "--body", str(d / "body.md"),
                        "--repo", "o/r", "--out", str(d / "out.yaml"), "--standards-sha", "abc1234",
                    ])
                self.assertEqual(rc, 1)
                self.assertIn(f"record.py: {d / broken} is not JSON", err.getvalue())
                self.assertFalse((d / "out.yaml").exists())

    def test_a_pull_request_without_its_authors_login_exits_1(self):
        no_user = {k: v for k, v in PR.items() if k != "user"}
        for pr in (no_user, {**PR, "user": None}, {**PR, "user": {}}):
            with self.subTest(user=pr.get("user", "missing")), tempfile.TemporaryDirectory() as d:
                d = Path(d)
                (d / "pr.json").write_text(json.dumps(pr))
                (d / "reviews.json").write_text(json.dumps([REVIEW]))
                (d / "comments.json").write_text(json.dumps({"review_threads": []}))
                (d / "issue-comments.json").write_text("[]")
                (d / "body.md").write_text(BODY)
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = record.main([
                        "--pr", str(d / "pr.json"), "--reviews", str(d / "reviews.json"),
                        "--comments", str(d / "comments.json"), "--issue-comments", str(d / "issue-comments.json"), "--body", str(d / "body.md"),
                        "--repo", "o/r", "--state",
                    ])
                self.assertEqual(rc, 1)
                self.assertIn("record.py: the pull request has no 'user.login'", err.getvalue())


if __name__ == "__main__":
    unittest.main()
