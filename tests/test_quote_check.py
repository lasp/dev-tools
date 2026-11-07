"""Tests for scripts/quote_check.py."""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("quote_check", ROOT / "scripts" / "quote_check.py")
quote_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quote_check)

URL = "https://github.com/o/r/pull/7#discussion_r12"
REPLY = {
    "pr": 7, "id": 12, "url": URL, "author": "bob", "authorship": "human", "kind": "reply", "thread": "PRRT_a",
    "path": "x.py", "line": 5, "created": "2026-10-01T11:00:00Z",
    "body": "> Always validate units at the boundary.\n\nIn general, import dependencies directly:   a degraded\nstate is broken.",
}
REPORT = f"""# Standards revision · r · 2026-10

### Rules
- [ ] R-004 · Import dependencies at module top · Recurring ask · pr-0007
  said: "import dependencies directly: a degraded state is broken." — bob, {URL}
  said: "units go in the column name" — Dana Lee, pasted meeting.md
  entry:
    ### A-001 · Import directly
    said: "In general, import dependencies directly" — bob, {URL}
"""


class QuoteCheck(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.list = self.dir / "comment-list.json"
        self.list.write_text(json.dumps({"pr": 7, "comments": [REPLY]}))
        (self.dir / "notes").mkdir()
        (self.dir / "notes" / "meeting.md").write_text("- Dana: units go in\nthe column name, always.\n")

    def run_it(self, report: str) -> tuple[int, list[str]]:
        path = self.dir / "ratchet-2026-10.md"
        path.write_text(report)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = quote_check.main([str(path), "--comments", str(self.list), "--notes", str(self.dir / "notes")])
        return code, out.getvalue().splitlines()

    def test_every_quote_found_where_it_cites_passes_with_its_counts(self):
        self.assertEqual(self.run_it(REPORT), (0, ["quotes: 3 · from comments: 2 · from notes: 1 · unchecked: 0"]))

    def test_a_quote_absent_from_its_comment_fails_the_report(self):
        code, out = self.run_it(REPORT.replace("a degraded state is broken.", "a degraded state is always broken."))
        self.assertEqual((code, out), (1, [f"refused · line 5 · the quote is not in {URL}'s own words"]))

    def test_words_the_comment_only_quotes_from_someone_else_fail(self):
        code, out = self.run_it(REPORT.replace("In general, import dependencies directly", "Always validate units at the boundary."))
        self.assertEqual((code, out), (1, [f"refused · line 9 · the quote is not in {URL}'s own words"]))

    def test_a_quote_cut_inside_a_word_fails(self):
        code, out = self.run_it(REPORT.replace('"In general, import dependencies directly"', '"In general, import dependencies direct"'))
        self.assertEqual(code, 1)
        self.assertIn("refused · line 9 · the quote is not in", out[0])

    def test_every_fault_is_named_not_only_the_first(self):
        bad = REPORT.replace(URL, "https://github.com/o/r/pull/7#discussion_r99", 1)
        bad = bad.replace("— bob, " + URL, "— carol, " + URL)
        bad = bad.replace("units go in the column name", "units go in the row name")
        code, out = self.run_it(bad)
        self.assertEqual(code, 1)
        self.assertEqual(out, [
            "refused · line 5 · https://github.com/o/r/pull/7#discussion_r99 is no comment in the lists given",
            "refused · line 6 · the quote is not in meeting.md",
            f"refused · line 9 · {URL} is bob's, not carol's",
        ])

    def test_a_said_line_of_no_form_or_past_forty_words_fails(self):
        code, out = self.run_it(REPORT + "  said: import dependencies directly — bob\n")
        self.assertEqual((code, out[-1].split(" · ")[:2]), (1, ["refused", "line 10"]))
        long = " ".join(["word"] * 41)
        code, out = self.run_it(REPORT + f'  said: "{long}" — bob, {URL}\n')
        self.assertEqual((code, out), (1, ["refused · line 10 · 41 words, not 1 to 40"]))

    def test_a_quote_nested_in_a_list_item_table_or_blockquote_is_refused_not_skipped(self):
        for nested in ("  - said:", "> said:", "| R-004 | said:"):
            code, out = self.run_it(REPORT.replace("  said: \"units", nested + ' "units'))
            self.assertEqual((code, out), (1, ["refused · line 6 · not a line of its own `said: \"<words>\" — <login>, <url>` or `— <name>, pasted <file>`"]), nested)

    def test_a_quote_from_a_pull_request_no_list_holds_is_unchecked_not_passed_silently(self):
        old = "https://github.com/o/r/pull/3#discussion_r5"
        code, out = self.run_it(REPORT + f'  said: "an older ask" — bob, {old}\n')
        self.assertEqual((code, out), (0, ["quotes: 3 · from comments: 2 · from notes: 1 · unchecked: 1",
                                           f"unchecked · line 10 · {old}: no comment list given holds its pull request"]))

    def test_a_note_named_with_a_space_can_be_cited(self):
        (self.dir / "notes" / "meeting.md").rename(self.dir / "notes" / "meeting notes.md")
        self.assertEqual(self.run_it(REPORT.replace("pasted meeting.md", "pasted meeting notes.md"))[0], 0)

    def test_an_unreadable_report_is_a_fault(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = quote_check.main([str(self.dir / "missing.md"), "--comments", str(self.list)])
        self.assertEqual(code, 1)
        self.assertIn("missing.md · cannot be read", out.getvalue())

    def test_a_pasted_note_that_is_not_under_notes_fails(self):
        code, out = self.run_it(REPORT.replace("pasted meeting.md", "pasted chat.md"))
        self.assertEqual((code, out), (1, ["refused · line 6 · pasted chat.md is no file under --notes"]))

    def test_an_unreadable_comment_list_is_a_fault(self):
        self.list.write_text("not json")
        code, out = self.run_it(REPORT)
        self.assertEqual(code, 1)
        self.assertTrue(out[0].startswith(f"refused · {self.list} · not a comment list"))


if __name__ == "__main__":
    unittest.main()
