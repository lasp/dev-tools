"""Tests for scripts/standard_index.py. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("standard_index", ROOT / "scripts" / "standard_index.py")
standard_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(standard_index)

ASSEMBLED = """# dev-tools/standards/review-contract.md

# Review contract

### R-999 · An example inside the contract is not a rule

# example/standard/standards/review-rules.md

# Review rules

### R-001 · Validate at the boundary
repos: [widgets]

tier: reviewer · status: **established** · since: 2026-09 · evidence: pr-0001

> Validate the input where it enters.

```
### R-050 · A heading inside a fence
tier: reviewer · status: provisional
```

### R-002 · A retired rule

tier: — · status: retired · since: 2026-08

### R-003 · A rule with no tier

tier: · status: provisional · since: 2026-10

# example/standard/standards/decisions.md

# Decisions

### D-001 · Paths are validated at the boundary

_2026-09 · **established** · source: fix#1_

### D-002 · Undated
repos: [widgets, gadgets]

A decision with no status line.

### D-003 · retired 2026-10-02

### D-004 · Moved to `D-009` (2026-09-23)

### D-005 · A status with a suffix

*2026-09-02, PR widgets#41 review thread · **provisional · team input needed***

### D-006 · Retired files are archived, not deleted

_2026-10 · **established** · source: fix#6_

# example/standard/standards/terminology.md

| ID | Code name | Also called |
| --- | --- | --- |
| T-001 | `obsid` | observation ID |
| T-002 | `apid` | — |
| T-003 | `x` | - |
| T-004 | `y` |  |
| T-005 | `flags` | `a \| b`, either |
"""

EXPECTED = [
    "Review contract: dev-tools/standards/review-contract.md",
    "Rules, from example/standard/standards/review-rules.md:",
    "  R-001 · Validate at the boundary · established · reviewer · repos: widgets",
    "  R-002 · A retired rule · retired · —",
    "  R-003 · A rule with no tier · provisional · -",
    "Decisions, from example/standard/standards/decisions.md:",
    "  D-001 · Paths are validated at the boundary · established",
    "  D-002 · Undated · no status line · repos: widgets, gadgets",
    "  D-003 · retired 2026-10-02 · retired",
    "  D-004 · Moved to `D-009` (2026-09-23) · moved",
    "  D-005 · A status with a suffix · provisional",
    "  D-006 · Retired files are archived, not deleted · established",
    "Terminology, from example/standard/standards/terminology.md: 5 terms",
    "  T-001 · `obsid`: observation ID",
    "  T-002 · `apid`",
    "  T-003 · `x`",
    "  T-004 · `y`",
    "  T-005 · `flags`: `a \\| b`, either",
]


def run(argv, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "stdin", io.StringIO(stdin)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = standard_index.main(argv)
    return rc, out.getvalue(), err.getvalue()


class Render(unittest.TestCase):
    def test_each_rule_and_decision_gets_its_number_title_status_and_source(self):
        self.assertEqual(standard_index.render(ASSEMBLED).splitlines(), EXPECTED)

    def test_a_two_column_terminology_table_lists_the_code_name_alone(self):
        text = "# own/standards/terminology.md\n\n| ID | Code name |\n| --- | --- |\n| T-001 | `obsid` |\n"
        self.assertIn("  T-001 · `obsid`\n", standard_index.render(text))

    def test_a_decision_status_agrees_with_rule_lint(self):
        rule_lint = standard_index.rule_lint
        statuses = rule_lint.statuses_in(ASSEMBLED.split("# example/standard/standards/decisions.md")[1])
        self.assertEqual(statuses["D-005"], "provisional")
        self.assertIn("  D-005 · A status with a suffix · provisional", standard_index.render(ASSEMBLED))

    def test_a_rule_with_no_status_line_stops_the_listing(self):
        text = "# own/standards/review-rules.md\n\n### R-001 · No status\n\nJust prose.\n"
        rc, out, err = run([], text)
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("R-001 has no status line", err)

    def test_an_unclosed_fence_ends_with_its_section(self):
        text = ("# own/standards/review-rules.md\n\n```\nnever closed\n"
                "# own/standards/decisions.md\n\n### D-001 · Kept\n\n_**established**_\n")
        self.assertIn("  D-001 · Kept · established", standard_index.render(text))

    def test_a_section_with_no_entries_says_none_and_no_rules_or_decisions_is_no_standard(self):
        out = standard_index.render("# own/standards/review-contract.md\n\n# own/standards/decisions.md\n\n# Decisions\n")
        self.assertIn("Decisions, from own/standards/decisions.md:\n  none\n", out)
        self.assertNotIn("No standard", out)
        self.assertTrue(standard_index.render("# own/standards/review-contract.md\n\nText.\n").endswith(
            "No standard: no rules or decisions apply here.\n"))

    def test_context_lists_each_entry_by_its_title_and_a_missing_directory_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "README.md").write_text("# Context\n")
            (Path(d) / "b-topic.md").write_text("# A topic\n\nText.\n")
            (Path(d) / "a-untitled.md").write_text("No heading.\n")
            out = standard_index.render(ASSEMBLED, contexts=[Path(d), Path(d) / "missing"])
        self.assertIn(f"Context, from {d}: 2 entries\n  a-untitled.md · a-untitled\n  b-topic.md · A topic\n", out)
        self.assertIn(f"Context: no {d}/missing\n", out)


class Main(unittest.TestCase):
    def test_reads_stdin_and_the_source_line_when_given(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "source"
            src.write_text("example/standard@abc1234\n")
            rc, out, _ = run(["--source", str(src)], ASSEMBLED)
            self.assertEqual(rc, 0)
            self.assertEqual(out.splitlines(), ["Standard: example/standard@abc1234"] + EXPECTED)
            rc, out, _ = run(["--source", str(Path(d) / "absent")], ASSEMBLED)
            self.assertEqual(out.splitlines(), EXPECTED)

    def test_a_standard_set_to_none_is_named_with_the_command_that_reads_it(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "source"
            src.write_text("example/standard@none\n")
            rc, out, _ = run(["--source", str(src)], "# x/standards/review-contract.md\n\nText.\n")
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), [
            "Standard: example/standard, not read: `git config lasp-dev.standard none` is set; "
            "`git config --unset lasp-dev.standard` reads it again",
            "Review contract: x/standards/review-contract.md",
        ])

    def test_text_with_no_section_heading_is_refused(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md") as f:
            f.write("# Review rules\n\n### R-001 · x\n")
            f.flush()
            rc, out, err = run([f.name])
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("not the file standard_file.sh prints", err)


if __name__ == "__main__":
    unittest.main()
