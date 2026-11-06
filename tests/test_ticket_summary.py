"""sandbox/fixture/ticket_summary.py: the summary a ticket-draft paste file leaves on one ticket."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sandbox" / "fixture" / "ticket_summary.py"
_spec = importlib.util.spec_from_file_location("ticket_summary", SCRIPT)
ticket_summary = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ticket_summary)

FILED = "Refuse a negative count in by_part"
NEW = "Sum the counts of a part listed twice in by_part"


def read(text: str, key: str = "PROJ-57", filed: str = FILED):
    return ticket_summary.summary(text, key, filed)


class Layouts(unittest.TestCase):
    """Layouts the recorded runs wrote."""

    def test_a_follow_up_block_first_is_skipped_for_the_ticket_below_it(self):
        text = (
            "Follow-up ticket (file this first, then put its key in the ticket below):\n\n"
            "Summary:     Decide how total treats negative counts\nIssue type:  Task\n\n"
            "Ticket PROJ-57:\n\nSummary:     Refuse negative counts in by_part, naming each part\n"
        )
        self.assertEqual(read(text), "Refuse negative counts in by_part, naming each part")

    def test_a_follow_up_block_under_a_rule_is_skipped(self):
        text = (
            "Follow-up to file first (relates to PROJ-58)\n============\n"
            "Summary:     Check the weekly run shows the message\n\n"
            "Original request, written by ticket-draft (follow-up written by ticket-draft)\n\n"
            "============\n\nSummary:     Name every part listed twice in by_part's ValueError\n"
        )
        self.assertEqual(read(text, "PROJ-58", "Log a warning"), "Name every part listed twice in by_part's ValueError")

    def test_a_ticket_heading_line_before_the_field_block(self):
        text = (
            "Follow-up ticket (create first)\nSummary: Correct the warehouse export\n\n"
            "------------\n\nTicket: PROJ-57 · Refuse a negative count when counted by part\n\n"
            "Summary:     Refuse a negative count when counted by part\nIssue type:  Task\n"
        )
        self.assertEqual(read(text), "Refuse a negative count when counted by part")

    def test_with_no_summary_line_the_ticket_heading_names_it(self):
        self.assertEqual(read("PROJ-57 · Sum a part listed twice in by_part\n\nFIELDS\nType: Task\n"),
                         "Sum a part listed twice in by_part")
        self.assertEqual(read("PROJ-57 · Refuse a negative count in by_part — paste-ready text\n"), FILED)

    def test_a_paste_heading_names_no_summary(self):
        self.assertIsNone(read("PROJ-57 · Paste in this order. Nothing was written to Jira.\nDESCRIPTION\n"))

    def test_a_file_that_says_nothing_of_the_summary_reads_as_none_for_the_verify_to_judge(self):
        self.assertIsNone(read("FIELDS\nType: Task\n\nDESCRIPTION\nh1. Motivation\n"))

    def test_a_jira_heading_names_the_summary(self):
        self.assertEqual(read(f"h1. PROJ-57 · {NEW}\n"), NEW)

    def test_the_comment_to_post_quotes_the_ticket_and_is_not_read(self):
        text = f"== Comment to post ==\nPROJ-57 · {FILED}\n\n== Field changes ==\nNew summary: {NEW}\n"
        self.assertEqual(read(text), NEW)
        self.assertIsNone(read(f"Original request (bob, 2026-02-02):\nPROJ-57 · {FILED}\nSummary: {FILED}\n"))


class Forms(unittest.TestCase):
    def test_each_form_of_a_new_summary(self):
        cases = {
            "plain": f"Summary:     {NEW}\n",
            "bold label": f"**Summary:** {NEW}\n",
            "backticked value": f"Summary: `{NEW}`\n",
            "table row": f"| Summary | {NEW} |\n",
            "heading, value below": f"== Summary (field change) ==\n{NEW}\n",
            "title heading": f"== 1. Title (the summary field)\n{NEW}\n",
            "quoted arrow": f'- Summary: "{FILED}" → "{NEW}"\n',
            "quoted ascii arrow": f'Summary: "{FILED}" -> "{NEW}"\n',
            "quoted to": f'Summary changed from "{FILED}" to "{NEW}".\n',
            "bare arrow": f"Summary: {FILED} → {NEW}\n",
            "bare ascii arrow": f"Summary: {FILED} -> {NEW}\n",
            "backticked arrow": f"Summary: `{FILED}` → `{NEW}`\n",
            "heading, change below": f'== Summary (field change) ==\n"{FILED}" → "{NEW}"\n',
            "was": f"Summary: {NEW} (was: {FILED})\n",
            "changed from": f'Summary: {NEW} (changed from "{FILED}")\n',
            "now and after": f"== Summary (field change) ==\nNow: {FILED}\nAfter: {NEW}\n",
            "key in the label": f'PROJ-57 · {FILED}\n\nSummary (PROJ-57): "{FILED}" → "{NEW}"\n',
            "summary field label": f"Summary field: {NEW}\n",
            "new summary label": f"New summary: {NEW}\n",
            "key prefix on the value": f"== Summary (field change) ==\nPROJ-57 · {NEW}\n",
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertEqual(read(text), NEW)

    def test_each_form_of_a_kept_summary(self):
        cases = {
            "unchanged": "- Summary: unchanged, \"Refuse a negative count in by_part\"\n",
            "unchanged, why": "Summary:     unchanged (it still names the main point)\n",
            "kept": "Summary kept as filed.\nIssue type:  Task\n",
            "qualifier": "Summary (unchanged): Refuse a negative count in by_part\n",
            "heading, unchanged below": "== Summary ==\nunchanged\n",
            "field changes none": "Field changes: none. Summary, Component/s and Priority are unchanged.\n",
            "kept in what changed": "* Kept: the summary, the Motivation and Impact\n",
            "unchanged after the value": f"Summary: {FILED} (unchanged)\n",
            "kept after a dash": f"Summary: {FILED} — kept, it still names the point\n",
            "field changes heading, none below": "== 3. Field changes ==\nNone.\n",
            "fields no change": "Fields: no change\n",
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertEqual(read(text), FILED)

    def test_none_inside_a_value_is_not_unchanged(self):
        self.assertEqual(read("Summary: Sum the counts of a part listed twice, none dropped\n"),
                         "Sum the counts of a part listed twice, none dropped")
        self.assertIsNone(read("Field changes: three, none of them the summary\n"))


class FollowUps(unittest.TestCase):
    def test_a_follow_up_takes_only_its_own_first_summary(self):
        text = "## Follow-up: new ticket\nSummary: Accept a negative count\n\nSummary: " + NEW + "\n"
        self.assertEqual(read(text), NEW)

    def test_a_heading_with_text_ends_a_follow_up_that_wrote_no_summary(self):
        text = "== 4. Follow-up ticket to create ==\nLink: relates to PROJ-57\n\n== 1. PROJ-57 ==\nSummary: " + NEW + "\n"
        self.assertEqual(read(text), NEW)

    def test_a_bare_rule_does_not_end_a_follow_up(self):
        text = "Follow-up ticket (create, then link)\n----------\nSummary: Correct restock\n----------\nSummary: " + NEW + "\n"
        self.assertEqual(read(text), NEW)

    def test_a_key_line_inside_a_follow_up_does_not_end_it(self):
        text = ("Follow-up ticket to create\nFound while drafting [PROJ-57 Refuse|http://x], which leaves it out\n"
                "Summary: Add a check for negative counts\n---\nSummary: " + FILED + "\n")
        self.assertEqual(read(text), FILED)

    def test_a_follow_up_after_the_ticket_does_not_change_it(self):
        text = "## PROJ-57\nSummary: " + FILED + "\n\n## Follow-up ticket\nSummary: Accept negative counts\n"
        self.assertEqual(read(text), FILED)

    def test_a_bullet_or_a_sentence_naming_a_follow_up_opens_no_block(self):
        for opener in ("* Follow-up, widgets: total() refuses a negative count too (to file)",
                       "Decided: total() is out of scope, follow-up: Refuse a negative count in total"):
            with self.subTest(opener):
                self.assertEqual(read(opener + "\nSummary: " + NEW + "\n"), NEW)

    def test_a_follow_up_summary_that_names_the_key_in_its_value_stays_the_follow_ups(self):
        text = ("== Follow-up ticket ==\nSummary: Refuse negatives in total, as PROJ-57 does for by_part\n\n"
                "== PROJ-57 ==\nSummary: " + NEW + "\n")
        self.assertEqual(read(text), NEW)

    def test_a_jira_list_item_does_not_end_a_follow_up(self):
        text = ("Follow-up ticket\nDescription:\nh1. Acceptance Criteria\n# total refuses a negative count\n"
                "Summary: Refuse a negative count in total\n")
        self.assertIsNone(read(text))

    def test_a_long_line_opening_with_follow_up_opens_no_block(self):
        long_line = "Follow-up " + "x" * 120
        self.assertEqual(read(long_line + "\nSummary: " + NEW + "\n"), NEW)


class Command(unittest.TestCase):
    def run_it(self, text):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "PROJ-57.jira.txt"
            path.write_text(text, encoding="utf-8")
            return subprocess.run([sys.executable, str(SCRIPT), str(path), "PROJ-57", FILED],
                                  capture_output=True, text=True)

    def test_it_prints_the_summary(self):
        done = self.run_it(f"Summary: {NEW}\n")
        self.assertEqual((done.returncode, done.stdout), (0, NEW + "\n"))

    def test_reading_nothing_exits_1_and_prints_nothing(self):
        done = self.run_it("FIELDS\nType: Task\n")
        self.assertEqual((done.returncode, done.stdout), (1, ""))
        self.assertIn("no summary for PROJ-57", done.stderr)

    def test_a_missing_file_exits_1(self):
        done = subprocess.run([sys.executable, str(SCRIPT), "/nonexistent/x.txt", "PROJ-57", FILED],
                              capture_output=True, text=True)
        self.assertEqual((done.returncode, done.stdout), (1, ""))


try:
    import yaml
except ImportError:
    yaml = None


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class Verifies(unittest.TestCase):
    """Each retitle scenario's verify, run through /bin/sh as run.py runs it, on a paste file."""

    SILENT = "FIELDS\nType: Task\n\nDESCRIPTION\nh1. Motivation\n"

    def verdict(self, scenario: str, key: str, text: str) -> bool:
        scenarios = {s["id"]: s for s in yaml.safe_load((ROOT / "sandbox" / "scenarios.yaml").read_text())["scenarios"]}
        with tempfile.TemporaryDirectory() as d:
            paste = Path(d) / ".review" / "context" / f"{key}.jira.txt"
            paste.parent.mkdir(parents=True)
            paste.write_text(text, encoding="utf-8")
            env = {**os.environ, "SBX_FIXTURES": str(SCRIPT.parent)}
            return all(subprocess.run(["/bin/sh", "-c", command], cwd=d, env=env, capture_output=True).returncode == 0
                       for command in scenarios[scenario]["verify"])

    def test_retitle_needs_a_new_summary(self):
        self.assertTrue(self.verdict("ticket-draft-retitle", "PROJ-57", f"Summary: {NEW}\n"))
        self.assertFalse(self.verdict("ticket-draft-retitle", "PROJ-57", f"Summary: {FILED}\n"))
        self.assertFalse(self.verdict("ticket-draft-retitle", "PROJ-57", self.SILENT))

    def test_subtle_needs_a_new_summary_with_no_warning(self):
        old = "Log a warning in by_part for a part listed twice"
        run = lambda text: self.verdict("ticket-draft-retitle-subtle", "PROJ-58", text)  # noqa: E731
        self.assertTrue(run("Summary: Raise one ValueError naming every part listed twice\n"))
        self.assertFalse(run(f"Summary: {old}\n"))
        self.assertFalse(run("Summary: Warn on every part listed twice\n"))
        self.assertFalse(run(self.SILENT))

    def test_control_fails_only_on_a_different_summary(self):
        run = lambda text: self.verdict("ticket-draft-retitle-control", "PROJ-57", text)  # noqa: E731
        self.assertTrue(run(self.SILENT))
        self.assertTrue(run(f"Summary: {FILED}\n"))
        self.assertTrue(run("- Summary: unchanged\n"))
        self.assertFalse(run("Summary: Refuse every negative count in by_part\n"))
        self.assertFalse(run(f'- Summary: "{FILED}" → "{FILED}"\n'))
        self.assertTrue(run(f"Links: relates to PROJ-12 (summary of work -> later)\nSummary: {FILED}\n"))


if __name__ == "__main__":
    unittest.main()
