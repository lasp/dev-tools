"""Tests for scripts/rule_lint.py, on the fixture under tests/fixtures/rule-bar/ built into a
scratch repository. Run with `python3 -m unittest discover -s tests`."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "rule-bar"

_spec = importlib.util.spec_from_file_location("rule_lint", ROOT / "scripts" / "rule_lint.py")
rule_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rule_lint)


class RuleLint(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        self.repo = rule_lint.fixture_repo(FIXTURE, tmp / "repo")

    def edit(self, name: str, old: str, new: str) -> None:
        path = self.repo / name
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def run_it(self, *extra: str) -> tuple[int, list[str]]:
        args = ["--ledger", str(self.repo / "review-rules.md"), "--instructions", str(self.repo / "instructions.md")]
        args += ["--repo", str(self.repo), "--decisions", str(self.repo / "decisions.md"), *extra]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(args)
        return rc, out.getvalue().splitlines()

    def test_the_fixture_repository_runs_no_background_maintenance(self):
        config = lambda key: subprocess.run(["git", "-C", str(self.repo), "config", "--get", key], capture_output=True, text=True).stdout.strip()
        self.assertEqual((config("maintenance.auto"), config("gc.auto")), ("false", "0"))

    def test_the_fixture_passes_with_and_without_changed(self):
        self.assertEqual(self.run_it(), (0, []))
        self.assertEqual(self.run_it("--changed", "R-001"), (0, []))

    def test_the_anchor_form_parses(self):
        m = rule_lint.ANCHOR.fullmatch('fix#2@abc1234 pkg/loader.py::load "path: Path"')
        self.assertEqual((m["repo"], m["pr"], m["sha"], m["path"], m["symbol"], m["shape"]), ("fix", "2", "abc1234", "pkg/loader.py", "load", "path: Path"))
        self.assertIsNotNone(rule_lint.THREAD.fullmatch("fix#1 PRRT_abc123"))

    def test_a_thread_id_with_a_hyphen_is_a_thread(self):
        self.edit("review-rules.md", "fix#1 PRRT_abc123;", "fix#1 PRRT_synthetic-002;")
        self.assertEqual(self.run_it(), (0, []))
        self.edit("review-rules.md", "fix#1 PRRT_synthetic-002;", "fix#1 PRRT_synthetic.002;")
        rc, out = self.run_it()
        self.assertEqual(rc, 1)
        self.assertTrue(out[0].startswith("anchors: R-001: "), out)

    def test_a_wording_heading_with_no_entry(self):
        self.edit("instructions.md", "## Other", "### R-009 · An orphan\n\nOne line.\nTwo lines.\n\n## Other")
        self.assertEqual(self.run_it(), (1, ["sync: R-009: a wording heading with no ledger entry"]))

    def test_an_entry_title_that_differs_from_its_heading(self):
        self.edit("instructions.md", "### R-001 · Validate a path where it is constructed", "### R-001 · Validate a path where it enters")
        rc, out = self.run_it()
        self.assertEqual(rc, 1)
        self.assertIn("sync: R-001: the wording heading's title is 'Validate a path where it enters', the ledger's 'Validate a path where it is constructed'", out)

    def test_a_link_whose_anchor_is_not_the_headings_slug(self):
        self.edit("review-rules.md", "#r-001--validate-a-path-where-it-is-constructed)", "#r-001-validate)")
        self.assertEqual(
            self.run_it(),
            (1, ["sync: R-001: the Wording: link ends #r-001-validate, the heading's anchor is #r-001--validate-a-path-where-it-is-constructed"]),
        )

    def test_a_five_line_wording(self):
        self.edit("instructions.md", "rather than deep in a caller that cannot.", "rather than deep in a caller that cannot.\nThree.\nFour.\nFive.")
        self.assertEqual(self.run_it(), (1, ["wording: R-001: 5 lines, not two to four"]))

    def test_a_wording_naming_a_record(self):
        self.edit("instructions.md", "rather than deep in a caller that cannot.", "rather than deep in a caller that cannot, as pr-0012 asked.")
        self.assertEqual(self.run_it(), (1, ["wording: R-001: names pr-0012"]))

    def test_an_established_rule_implementing_a_provisional_decision(self):
        self.edit("review-rules.md", "implements `D-001`", "implements `D-002`")
        self.assertEqual(self.run_it(), (1, ["status: R-001: established, but implements D-002, which is provisional"]))

    def test_a_needs_a_second_marker_on_an_established_rule(self):
        self.edit("review-rules.md", "status: provisional · since: 2026-10", "status: established · since: 2026-10")
        self.assertEqual(self.run_it(), (1, ["status: R-002: a needs-a-second marker on a rule that is established"]))

    def test_a_scope_glob_matching_nothing(self):
        self.edit("review-rules.md", "scope: pkg/*.py", "scope: src/*.py")
        self.assertEqual(self.run_it(), (1, ["scope: R-001: src/*.py matches no tracked file"]))

    def test_an_example_whose_shape_is_absent_at_its_sha(self):
        self.edit("review-rules.md", 'pkg/loader.py::load "path: Path"', 'pkg/loader.py::load "path: str"')
        rc, out = self.run_it()
        self.assertEqual(rc, 1)
        self.assertEqual(len(out), 1)
        self.assertRegex(out[0], r'^anchors: R-001: "path: str" is not in load in pkg/loader.py at [0-9a-f]{7}$')

    def test_an_example_whose_sha_does_not_exist(self):
        text = (self.repo / "review-rules.md").read_text()
        sha = rule_lint.ANCHOR.search(text)["sha"]
        self.edit("review-rules.md", f"fix#2@{sha}", "fix#2@0000000")
        self.assertEqual(self.run_it(), (1, ["anchors: R-001: 0000000:pkg/loader.py does not resolve"]))

    def test_a_changed_rule_missing_example_fails_and_unchanged_only_prints(self):
        text = (self.repo / "review-rules.md").read_text()
        line = next(x for x in text.splitlines() if x.startswith("example: fires on fix#3"))
        self.edit("review-rules.md", line + "\n", "")
        self.assertEqual(self.run_it("--changed", "R-002"), (1, ["fields: R-002: no example: line"]))
        self.assertEqual(self.run_it("--changed", "R-001"), (0, ["fields: R-002: no example: line"]))

    def test_entry_checks_a_drafted_rule_and_always_gates_fields(self):
        ledger = (self.repo / "review-rules.md").read_text()
        entry = ledger[ledger.index("### R-001") : ledger.index("### R-002")]
        wording = (self.repo / "instructions.md").read_text()
        words = wording[wording.index("### R-001") : wording.index("### R-002")]
        draft = self.repo / "R-001.entry.md"
        draft.write_text(entry + words)
        args = ["--entry", str(draft), "--repo", str(self.repo), "--decisions", str(self.repo / "decisions.md")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(rule_lint.main(args), 0)
        self.assertEqual(out.getvalue(), "")
        draft.write_text(entry.replace("scope: pkg/*.py\n", "") + words)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(rule_lint.main(args), 1)
        self.assertEqual(out.getvalue(), "fields: R-001: no scope: line\n")

    def test_a_repos_line_names_repositories_the_standard_covers(self):
        self.edit("review-rules.md", "scope: pkg/*.py\n", "scope: pkg/*.py\nrepos: [alpha]\n")
        self.assertEqual(self.run_it(), (1, ["fields: R-001: a repos: line in a standard with no profiles/, which covers one repository"]))
        (self.repo / "profiles").mkdir()
        (self.repo / "profiles" / "Alpha.yaml").write_text("public: true\n")
        self.assertEqual(self.run_it(), (0, []))
        self.edit("review-rules.md", "repos: [alpha]", "repos: [alpha, beta]")
        self.assertEqual(self.run_it(), (1, ["fields: R-001: repos: names beta, which has no profiles/beta.yaml"]))
        self.edit("review-rules.md", "repos: [alpha, beta]", "repos: alpha")
        self.assertEqual(self.run_it(), (1, [
            "budget: R-001: repos: alpha is not a list of names, so no repository's budget is counted",
            "fields: R-001: repos: alpha is not a list of repository names such as [my_repo]",
        ]))

    def inline(self) -> None:
        """Moves each rule's wording from the instruction file into its ledger entry, as `> ` lines
        in place of its Wording: link."""
        words = rule_lint.wordings((self.repo / "instructions.md").read_text())
        text = (self.repo / "review-rules.md").read_text()
        for rid, (_, lines) in words.items():
            link = re.search(rf"^Wording: \[{rid} .*$", text, re.M).group(0)
            text = text.replace(link, "\n".join(f"> {line}" for line in lines))
        (self.repo / "review-rules.md").write_text(text)

    def run_inline(self, *extra: str) -> tuple[int, list[str]]:
        args = ["--ledger", str(self.repo / "review-rules.md"), "--repo", str(self.repo), "--decisions", str(self.repo / "decisions.md"), *extra]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(args)
        return rc, out.getvalue().splitlines()

    def test_wording_in_the_ledger_passes_and_is_held_to_the_gates(self):
        self.inline()
        self.assertEqual(self.run_inline(), (0, []))
        self.edit("review-rules.md", "> rather than deep in a caller that cannot.\n", "")
        self.edit("review-rules.md", "> A path is checked where it enters, so a bad value fails at the boundary that can name it\n", "")
        self.assertEqual(self.run_inline(), (1, ["sync: R-001: no wording: no `> ` lines in the entry"]))

    def test_wording_in_the_ledger_is_two_to_four_lines_naming_no_record(self):
        self.inline()
        self.edit("review-rules.md", "> rather than deep in a caller that cannot.", "> rather than deep in a caller that cannot, as #12 showed.")
        self.assertEqual(self.run_inline(), (1, ["wording: R-001: names #12"]))
        self.edit("review-rules.md", "> rather than deep in a caller that cannot, as #12 showed.", "> b\n> c\n> d\n> e")
        self.assertEqual(self.run_inline(), (1, ["wording: R-001: 5 lines, not two to four"]))

    def test_a_retired_rule_with_wording_in_the_ledger_fails_sync(self):
        self.inline()
        self.edit("review-rules.md", "tier: reviewer · status: provisional", "tier: — · status: retired")
        self.assertEqual(self.run_inline("--checks", "sync"), (1, ["sync: R-002: a retired rule has wording"]))

    def test_a_fence_in_an_entry_holds_no_wording(self):
        self.inline()
        self.edit("review-rules.md", "Do not flag: a path validated by its caller", "```python\n# a comment\n>>> load(\"x\")\n```\n\nDo not flag: a path validated by its caller")
        self.assertEqual(rule_lint.inline(rule_lint.load_counts().parse_entries((self.repo / "review-rules.md").read_text(), "r"))["R-001"][1],
                         ["A path is checked where it enters, so a bad value fails at the boundary that can name it",
                          "rather than deep in a caller that cannot."])

    def test_a_rule_neither_live_nor_a_check_with_wording_fails_sync(self):
        self.inline()
        self.edit("review-rules.md", "tier: reviewer · status: provisional", "tier: — · status: provisional")
        self.assertEqual(self.run_inline("--checks", "sync"), (1, ["sync: R-002: a —-tier, provisional rule has wording"]))

    def test_wording_in_the_entry_of_a_ledger_that_keeps_it_elsewhere_says_so(self):
        self.inline()
        (self.repo / "instructions.md").write_text("# Instructions\n\n## Review Rules\n\n## Other\n")
        self.assertIn("sync: R-001: wording in the entry, but this ledger keeps its wording in the instruction file", self.run_it()[1])

    def test_wording_in_both_places_fails_sync(self):
        self.inline()
        self.assertIn("sync: R-001: wording in the entry and in the instruction file; it lives in one place", self.run_it()[1])

    def test_a_drafted_entry_with_its_wording_in_it(self):
        self.inline()
        text = (self.repo / "review-rules.md").read_text()
        entry = re.search(r"^### R-002.*?(?=^### )", text, re.M | re.S).group(0)
        (self.repo / "entry.md").write_text(entry)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(["--entry", str(self.repo / "entry.md"), "--repo", str(self.repo), "--decisions", str(self.repo / "decisions.md")])
        self.assertEqual((rc, out.getvalue()), (0, ""))

    def test_a_decision_is_tagged_once_with_covered_names_and_keeps_its_status(self):
        (self.repo / "profiles").mkdir()
        (self.repo / "profiles" / "alpha.yaml").write_text("public: true\n")
        self.edit("decisions.md", "### D-001 · Paths are validated at the boundary\n", "### D-001 · Paths are validated at the boundary\nrepos: [alpha]\n")
        self.assertEqual(self.run_it(), (0, []))
        self.edit("decisions.md", "**established** · source: fix#1", "**provisional** · source: fix#1")
        self.assertEqual(self.run_it(), (1, ["status: R-001: established, but implements D-001, which is provisional"]))
        self.edit("decisions.md", "**provisional** · source: fix#1", "**established** · source: fix#1")
        self.edit("decisions.md", "repos: [alpha]\n", "repos: [alpha]\nrepos: [gamma]\n")
        self.assertEqual(self.run_it("--checks", "fields"), (1, ["fields: D-001: 2 repos: lines; a block takes one"]))

    def test_a_missing_instruction_file_cannot_run(self):
        (self.repo / "instructions.md").unlink()
        rc, out = self.run_it()
        self.assertEqual(rc, 2)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("CANNOT RUN: no file "))

    def test_a_slug_keeps_underscores_as_github_does(self):
        self.assertEqual(rule_lint.slug("R-020 · Use `paths_to_files`"), "r-020--use-paths_to_files")

    def test_a_duplicated_wording_heading_or_entry_fails_sync(self):
        self.edit("instructions.md", "## Other", "### R-001 · Validate a path where it is constructed\n\nOne.\nTwo.\n\n## Other")
        self.assertIn("sync: R-001: 2 wording headings", self.run_it()[1])

    def test_a_graduated_rule_may_keep_a_wording_heading_the_wording_gate_does_not_measure(self):
        self.edit("instructions.md", "## Other", "### R-003 · Deferred work carries a ticket tag\n\nOne.\nTwo.\nThree.\nFour.\nFive, as pr-0012 asked.\n\n## Other")
        self.assertEqual(self.run_it(), (0, []))

    def test_a_retired_rule_with_a_wording_heading_fails_sync(self):
        self.edit("review-rules.md", "tier: check · status: graduated", "tier: — · status: retired")
        self.edit("instructions.md", "## Other", "### R-003 · Deferred work carries a ticket tag\n\nOne.\nTwo.\n\n## Other")
        self.assertEqual(self.run_it(), (1, ["sync: R-003: a retired rule has a wording heading"]))

    def test_a_not_on_anchor_at_another_pull_requests_merge_fails(self):
        self.edit("review-rules.md", "not on fix#2@", "not on fix#41@")
        rc, out = self.run_it()
        self.assertEqual(rc, 1)
        self.assertEqual(len(out), 1)
        self.assertRegex(out[0], r"^anchors: R-001: [0-9a-f]{7} is not #41's merge; its subject is 'Load and read a path \(#2\)'$")

    def test_a_merge_commits_subject_names_its_pull_request(self):
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--amend", "-m", "Merge pull request #2 from fork/branch"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
        head = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "--short=7", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        text = (self.repo / "review-rules.md").read_text()
        (self.repo / "review-rules.md").write_text(text.replace(rule_lint.ANCHOR.search(text)["sha"], head))
        self.assertEqual(self.run_it(), (0, []))
        self.edit("review-rules.md", "not on fix#2@", "not on fix#20@")
        self.assertEqual(self.run_it(), (1, [f"anchors: R-001: {head} is not #20's merge; its subject is 'Merge pull request #2 from fork/branch'"]))

    def test_a_live_rule_outside_the_reviewer_tier_with_a_wording_heading_fails_sync(self):
        self.edit("review-rules.md", "tier: check · status: graduated", "tier: — · status: provisional")
        self.edit("instructions.md", "## Other", "### R-003 · Deferred work carries a ticket tag\n\nOne.\nTwo.\n\n## Other")
        self.assertEqual(self.run_it(), (1, ["sync: R-003: a —-tier, provisional rule has a wording heading"]))

    def test_an_implements_off_the_status_line_fails(self):
        self.edit("review-rules.md", "pr-0001, pr-0002 · implements `D-001`", "pr-0001, pr-0002 ·\nimplements `D-001`")
        self.assertEqual(self.run_it(), (1, ["status: R-001: implements `D-001` is off the status line, which is never wrapped"]))

    def test_a_not_on_anchor_off_the_default_branch_fails(self):
        (self.repo / "pkg" / "loader.py").write_text((self.repo / "pkg" / "loader.py").read_text() + "\n# unmerged\n")
        for args in (["checkout", "-qb", "feature"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "Unmerged (#2)"]):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        head = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "--short=7", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        text = (self.repo / "review-rules.md").read_text()
        sha = rule_lint.ANCHOR.search(text)["sha"]
        self.edit("review-rules.md", f"not on fix#2@{sha}", f"not on fix#2@{head}")
        self.assertEqual(self.run_it(), (1, [f"anchors: R-001: {head} is not on origin/main"]))

    def test_an_example_whose_halves_are_the_same_place_fails(self):
        self.edit("review-rules.md", 'pkg/loader.py::read "source: str | Path"', 'pkg/loader.py::load "path: Path"')
        self.assertEqual(self.run_it(), (1, ["anchors: R-002: the fires-on and not-on halves are the same place"]))

    def test_no_origin_head_cannot_run_a_not_on_anchor(self):
        subprocess.run(["git", "-C", str(self.repo), "symbolic-ref", "--delete", "refs/remotes/origin/HEAD"], check=True)
        rc, out = self.run_it()
        self.assertEqual(rc, 2)
        self.assertTrue(out[0].startswith("CANNOT RUN: no origin/HEAD in "))

    def test_the_symbol_is_a_definition_and_the_shape_is_inside_it(self):
        for symbol, shape, line in (
            ("lo", "path: Path", "no def or class lo in pkg/loader.py"),
            ("read", "path: Path", '"path: Path" is not in read in pkg/loader.py'),
        ):
            with self.subTest(symbol=symbol):
                self.edit("review-rules.md", 'pkg/loader.py::read "source: str | Path"', f'pkg/loader.py::{symbol} "{shape}"')
                rc, out = self.run_it()
                self.assertEqual(rc, 1)
                self.assertRegex(out[0], rf"^anchors: R-002: {re.escape(line)} at [0-9a-f]{{7}}$")
                self.edit("review-rules.md", f'pkg/loader.py::{symbol} "{shape}"', 'pkg/loader.py::read "source: str | Path"')

    def test_a_definition_spans_its_signature_and_body_and_a_method_its_class(self):
        text = (
            "class Reader:\n"
            "    def open(\n"
            "        self,\n"
            "        path: Path,\n"
            "    ) -> str:\n"
            "        return str(path)\n"
            "\n"
            "    def close(self, handle: int) -> None:\n"
            "        pass\n"
            "\n"
            "def open(source: str) -> None:\n"
            "    pass\n"
        )
        method = rule_lint.definition(text, "Reader.open")
        self.assertIn("path: Path", method)
        self.assertIn("return str(path)", method)
        self.assertNotIn("handle: int", method)
        self.assertNotIn("source: str", method)
        self.assertIn("source: str", rule_lint.definition(text, "open"))
        self.assertIsNone(rule_lint.definition(text, "Reader.read"))

    def test_a_bold_or_misspelled_tier_is_read_or_refused(self):
        new = "### R-004 · A new rule\n\ntier: {} · status: provisional · since: 2026-10 · evidence: pr-0005\n\n"
        self.edit("review-rules.md", "### R-003", new.format("**reviewer**") + "### R-003")
        rc, out = self.run_it("--changed", "R-004")
        self.assertEqual(rc, 1)
        self.assertEqual(out, ["sync: R-004: no wording heading", "fields: R-004: no scope: line", "fields: R-004: no example: line"])
        self.edit("review-rules.md", "tier: **reviewer** · status: provisional · since: 2026-10", "tier: Reviewer · status: provisional · since: 2026-10")
        rc, out = self.run_it("--changed", "R-004")
        self.assertEqual(rc, 1)
        self.assertIn("status: R-004: tier 'Reviewer' is not reviewer, check or —", out)

    def test_a_ledger_with_no_entries_cannot_run(self):
        for text in ("", "# Review rules\n\n## R-001 · Validate a path where it is constructed\n\ntier: reviewer · status: established\n"):
            with self.subTest(text=text[:20]):
                (self.repo / "review-rules.md").write_text(text)
                rc, out = self.run_it()
                self.assertEqual(rc, 2)
                self.assertTrue(out[0].endswith("holds no ### R-NNN entry"))

    def test_implements_and_needs_a_second_are_read_in_any_spelling(self):
        for old, new, line in (
            ("implements `D-001`", "Implements D-002", "status: R-001: established, but implements D-002, which is provisional"),
            ("implements `D-001`", "implements [D-002](decisions.md)", "status: R-001: established, but implements D-002, which is provisional"),
            ("implements `D-001`", "after D-001", "status: R-001: names D-001 outside an `implements <id>`"),
            ("pr-0001, pr-0002 · implements", "pr-0001, pr-0002 · **Needs a second** · implements", "status: R-001: a needs-a-second marker on a rule that is established"),
        ):
            with self.subTest(new=new):
                self.edit("review-rules.md", old, new)
                self.assertEqual(self.run_it(), (1, [line]))
                self.edit("review-rules.md", new, old)

    def test_a_decision_marked_with_a_suffix_reads_its_status(self):
        self.edit("decisions.md", "**provisional** · source: fix#3", "**provisional · team input needed** · source: fix#3")
        self.assertEqual(rule_lint.decision_statuses([self.repo / "decisions.md"]), {"D-001": "established", "D-002": "provisional"})

    def test_a_scope_with_an_empty_or_match_all_glob_fails(self):
        for scope, line in (
            ("*", "scope: R-001: * matches every file; name the paths the rule is about"),
            ("**", "scope: R-001: ** matches every file; name the paths the rule is about"),
            (",", "scope: R-001: the scope: line holds an empty glob"),
        ):
            with self.subTest(scope=scope):
                self.edit("review-rules.md", "scope: pkg/*.py\nexample: fires on fix#1", f"scope: {scope}\nexample: fires on fix#1")
                rc, out = self.run_it()
                self.assertEqual(rc, 1)
                self.assertIn(line, out)
                self.edit("review-rules.md", f"scope: {scope}\nexample: fires on fix#1", "scope: pkg/*.py\nexample: fires on fix#1")

    def test_checks_runs_only_the_named_gates(self):
        ledger = (self.repo / "review-rules.md").read_text()
        entry = ledger[ledger.index("### R-001") : ledger.index("### R-002")]
        wording = (self.repo / "instructions.md").read_text()
        words = wording[wording.index("### R-001") : wording.index("### R-002")]
        draft = self.repo / "R-001.entry.md"
        draft.write_text(entry.replace("scope: pkg/*.py\n", "").replace(entry[entry.index("example:") : entry.index("\n", entry.index("example:")) + 1], "") + words)
        args = ["--entry", str(draft), "--repo", str(self.repo), "--decisions", str(self.repo / "decisions.md")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(rule_lint.main([*args, "--checks", "status"]), 0)
            self.assertEqual(rule_lint.main([*args, "--checks", "status,fields"]), 1)
            self.assertEqual(rule_lint.main([*args, "--checks", "status,lint"]), 2)
        self.assertEqual(
            out.getvalue().splitlines(),
            ["fields: R-001: no scope: line", "fields: R-001: no example: line", "CANNOT RUN: --checks names 'lint', which is not one of sync, wording, status, scope, anchors, fields, budget"],
        )

    def test_a_separator_line_is_not_a_wording_line(self):
        self.edit("instructions.md", "rather than deep in a caller that cannot.", "rather than deep in a caller that cannot.\n\n---")
        self.assertEqual(self.run_it(), (0, []))

    def test_implements_a_decision_no_file_holds(self):
        self.edit("review-rules.md", "implements `D-001`", "implements `D-099`")
        self.assertEqual(self.run_it(), (1, ["status: R-001: implements D-099, which no decisions file holds"]))

    def test_an_unmarked_decision_is_not_compared_and_shared_reads_as_its_id(self):
        self.edit("decisions.md", "_2026-09 · **established** · source: fix#1_", "_2026-09, source: fix#1_")
        self.edit("review-rules.md", "implements `D-001`", "implements shared D-001")
        self.assertEqual(self.run_it(), (0, []))

    def test_a_symbol_missing_at_the_sha_and_a_malformed_example_fail_anchors(self):
        self.edit("review-rules.md", 'pkg/loader.py::load "path: Path"', 'pkg/loader.py::save "path: Path"')
        rc, out = self.run_it()
        self.assertEqual(rc, 1)
        self.assertRegex(out[0], r"^anchors: R-001: no def or class save in pkg/loader\.py at [0-9a-f]{7}$")
        text = (self.repo / "review-rules.md").read_text()
        line = next(x for x in text.splitlines() if x.startswith("example: fires on fix#1"))
        self.edit("review-rules.md", line, "example: fires on fix#1 PRRT_abc123")
        self.assertEqual(self.run_it(), (1, ["anchors: R-001: the example line is not one line, `fires on <anchor or thread>; not on <anchor>`"]))

    def test_changed_naming_no_ledger_id_cannot_run(self):
        for value in ("R-02", "R-001 R-002", "R-009"):
            with self.subTest(value=value):
                rc, out = self.run_it("--changed", value)
                self.assertEqual(rc, 2)
                self.assertTrue(out[0].startswith("CANNOT RUN: --changed names "))

    def test_entry_whose_wording_is_under_another_id_fails_sync(self):
        ledger = (self.repo / "review-rules.md").read_text()
        entry = ledger[ledger.index("### R-001") : ledger.index("### R-002")]
        draft = self.repo / "R-001.entry.md"
        draft.write_text(entry + "### R-009 · Another rule\n\nOne.\nTwo.\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(["--entry", str(draft), "--repo", str(self.repo), "--decisions", str(self.repo / "decisions.md")])
        self.assertEqual((rc, out.getvalue()), (1, "sync: R-001: the drafted wording is under R-009, not R-001\n"))

    def test_the_other_cannot_run_causes(self):
        self.edit("instructions.md", "## Review Rules", "## Rules")
        self.assertEqual(self.run_it()[0], 2)
        self.edit("instructions.md", "## Rules", "## Review Rules")
        rc, out = self.run_it("--repo", str(self.repo / "pkg" / "nowhere"))
        self.assertEqual(rc, 2)
        self.assertTrue(out[0].startswith("CANNOT RUN: git in "))
        draft = self.repo / "R-001.entry.md"
        ledger = (self.repo / "review-rules.md").read_text()
        draft.write_text(ledger[ledger.index("### R-001") : ledger.index("### R-002")])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(["--entry", str(draft), "--repo", str(self.repo), "--decisions", str(self.repo / "decisions.md")])
        self.assertEqual(rc, 1)
        self.assertIn("sync: R-001: no wording: no `> ` lines in the entry", out.getvalue())


# A rule entry of `n` lines in all, its wording inline: heading, blank, status line, blank, wording
# lines and a closing blank.
def entry(rid: str, n: int, tier: str = "reviewer", repos: str = "") -> str:
    status = "graduated" if tier == "check" else "provisional"
    head = f"### {rid} · Rule {rid}\n" + (f"repos: [{repos}]\n" if repos else "") + f"\ntier: {tier} · status: {status} · since: 2026-10\n\n"
    return head + "".join(f"> Line {i}.\n" for i in range(n - head.count("\n") - 1)) + "\n"


class Budget(unittest.TestCase):
    """The budget gate, on ledgers written here, run with `--checks budget` against the rule-bar
    fixture's repository, which the gate does not read but `Lint` needs for `git ls-files`."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        self.repo = rule_lint.fixture_repo(FIXTURE, tmp / "repo")
        self.ledger = tmp / "standard" / "review-rules.md"
        self.ledger.parent.mkdir()

    def lint(self, text: str, *extra: str) -> tuple[int, list[str]]:
        self.ledger.write_text(text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(["--ledger", str(self.ledger), "--repo", str(self.repo), "--checks", "budget", *extra])
        return rc, out.getvalue().splitlines()

    def test_a_ledger_at_its_budget_passes_and_one_line_over_fails(self):
        head = "# Review rules\n\n**Budget: 20 lines**\n\n"
        self.assertEqual(self.lint(head + entry("R-001", 16)), (0, ["budget ok: ledger: 20 of 20 lines"]))
        self.assertEqual(
            self.lint(head + entry("R-001", 17)),
            (1, ["budget: ledger: 21 lines over a budget of 20; retire, merge or narrow a rule, or raise the budget in the ledger's header with the reason"]),
        )

    def test_a_check_tier_entry_and_the_held_candidates_are_not_counted(self):
        head = "# Review rules\n\n**Budget: 20 lines**\n\n"
        held = "## Candidates below the criteria\n\n" + "- held\n" * 30
        self.assertEqual(self.lint(head + entry("R-001", 16) + entry("R-002", 30, tier="check") + held), (0, ["budget ok: ledger: 20 of 20 lines"]))

    def test_each_covered_repository_is_counted_with_only_the_rules_tagged_for_it(self):
        (self.ledger.parent / "profiles").mkdir()
        for name in ("alpha", "beta"):
            (self.ledger.parent / "profiles" / f"{name}.yaml").write_text("public: true\n")
        text = "# Review rules\n\n**Budget: 30 lines**\n\n" + entry("R-001", 10) + entry("R-002", 10, repos="alpha") + entry("R-003", 17, repos="Beta")
        rc, out = self.lint(text)
        self.assertEqual(rc, 1)
        self.assertEqual([line.split(";")[0] for line in out], ["budget ok: alpha: 24 of 30 lines", "budget: beta: 31 lines over a budget of 30"])

    def test_a_budget_failure_fails_a_changed_run_only_when_a_changed_rule_counts_there(self):
        (self.ledger.parent / "profiles").mkdir()
        for name in ("alpha", "beta"):
            (self.ledger.parent / "profiles" / f"{name}.yaml").write_text("public: true\n")
        text = "# Review rules\n\n**Budget: 30 lines**\n\n" + entry("R-001", 10, repos="alpha") + entry("R-002", 27, repos="beta")
        self.assertEqual(self.lint(text, "--changed", "R-001")[0], 0)
        self.assertEqual(self.lint(text, "--changed", "R-002")[0], 1)

    def test_a_ledger_stating_no_budget_takes_the_rule_budget_dial(self):
        dial = (ROOT / "standards" / "dials.md").read_text()
        limit = int(re.search(r"^\| Rule budget \| (\d+) lines", dial, re.M).group(1))
        self.assertEqual(rule_lint.budget_of("# Review rules\n"), limit)
        rc, out = self.lint("# Review rules\n\n" + entry("R-001", limit - 1))
        self.assertEqual((rc, out[0].split(";")[0] if out else None), (1, f"budget: ledger: {limit + 1} lines over a budget of {limit}"))

    def test_with_instructions_each_counted_rule_adds_its_wording(self):
        # The fixture's ledger with a budget line counts 29 lines, R-003 left out as check-tier,
        # and R-001's and R-002's wording two lines each.
        self.assertEqual(self.lint_instructions(budget=None)[0], 0)
        self.assertEqual(self.lint_instructions(budget=33), (0, ["budget ok: ledger: 33 of 33 lines"]))
        self.assertEqual(self.lint_instructions(budget=32), (1, ["budget: ledger: 33 lines over a budget of 32; retire, merge or narrow a rule, or raise the budget in the ledger's header with the reason"]))

    def test_a_ledger_stating_no_budget_with_no_rule_budget_dial_cannot_run(self):
        dials = self.ledger.parent / "dials.md"
        dials.write_text("| Dial | Default | Either way |\n| --- | --- | --- |\n| Revision | monthly | — |\n")
        with mock.patch.object(rule_lint, "DIALS", dials):
            rc, out = self.lint("# Review rules\n\n" + entry("R-001", 8))
        self.assertEqual((rc, out), (2, [f"CANNOT RUN: the ledger states no budget and {dials} has no Rule budget Dial"]))

    def test_a_budget_stated_in_another_form_cannot_run(self):
        for line in ("**Budget:** 250 lines", "**Budget: 250 lines.**", "**Budget: 1 line**"):
            rc, out = self.lint(f"# Review rules\n\n{line}\n\n" + entry("R-001", 8))
            self.assertEqual((rc, out), (2, [f"CANNOT RUN: the ledger names a budget as {line!r}, not as `**Budget: N lines**`"]), line)

    def test_changed_on_a_standard_of_one_repository_fails_only_for_a_counted_rule(self):
        text = "# Review rules\n\n**Budget: 20 lines**\n\n" + entry("R-001", 17) + entry("R-002", 6, tier="check")
        self.assertEqual(self.lint(text, "--changed", "R-001")[0], 1)
        self.assertEqual(self.lint(text, "--changed", "R-002")[0], 0)

    def test_a_malformed_repos_line_fails_a_changed_run_whichever_rule_is_named(self):
        (self.ledger.parent / "profiles").mkdir()
        (self.ledger.parent / "profiles" / "alpha.yaml").write_text("public: true\n")
        text = "# Review rules\n\n**Budget: 10 lines**\n\n" + entry("R-001", 6).replace("\n\ntier:", "\nrepos: alpha\n\ntier:", 1) + entry("R-002", 30)
        rc, out = self.lint(text, "--changed", "R-002")
        self.assertEqual((rc, out), (1, ["budget: R-001: repos: alpha is not a list of names, so no repository's budget is counted"]))

    def test_bold_budget_in_a_rule_s_prose_is_not_a_stated_budget(self):
        text = "# Review rules\n\n" + entry("R-001", 8).replace("> Line 1.", "> Keep the **budget** of a loop small.")
        self.assertEqual(self.lint(text)[0], 0)

    def test_a_run_of_every_gate_prints_no_budget_ok_line(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(["--ledger", str(self.repo / "review-rules.md"), "--instructions", str(self.repo / "instructions.md"), "--repo", str(self.repo), "--decisions", str(self.repo / "decisions.md")])
        self.assertEqual((rc, out.getvalue()), (0, ""))

    def test_an_empty_profiles_directory_cannot_run(self):
        (self.ledger.parent / "profiles").mkdir()
        rc, out = self.lint("# Review rules\n\n" + entry("R-001", 8))
        self.assertEqual((rc, out), (2, [f"CANNOT RUN: {self.ledger.parent / 'profiles'} holds no repository's file, so no repository's budget can be counted"]))

    def test_the_budget_gate_named_with_entry_cannot_run(self):
        self.ledger.write_text(entry("R-001", 8))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(["--entry", str(self.ledger), "--repo", str(self.repo), "--checks", "budget"])
        self.assertEqual((rc, out.getvalue()), (2, "CANNOT RUN: --checks budget reads a whole ledger; give --ledger, not --entry\n"))

    def lint_instructions(self, budget: int | None) -> tuple[int, list[str]]:
        path = self.repo / "review-rules.md"
        text = re.sub(r"\n\*\*Budget: \d+ lines\*\*\n", "", path.read_text())
        if budget is not None:
            text = text.replace("# Review rules\n", f"# Review rules\n\n**Budget: {budget} lines**\n", 1)
        path.write_text(text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = rule_lint.main(["--ledger", str(path), "--instructions", str(self.repo / "instructions.md"), "--repo", str(self.repo), "--checks", "budget"])
        return rc, out.getvalue().splitlines()

    def test_the_count_reads_what_standard_file_loads_for_each_repository(self):
        """The gate's selection, held to `standard_file.sh`'s on one standard: the lines it loads
        for each covered repository are the blocks the budget starts from."""
        tmp = self.ledger.parent.parent / "own"
        (tmp / "standards" / "profiles").mkdir(parents=True)
        for name in ("alpha", "beta"):
            (tmp / "standards" / "profiles" / f"{name}.yaml").write_text("public: true\n")
        text = ("# Review rules\n\nHeader.\n\n" + entry("R-001", 8) + entry("R-002", 8, repos="beta")
                + entry("R-003", 7, tier="check", repos="Alpha") + "```\n### R-009 · Inside a fence\n```\n\n"
                + "## Candidates below the criteria\n\n- held\n")
        (tmp / "standards" / "review-rules.md").write_text(text)
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "s"]):
            subprocess.run(["git", "-C", str(tmp), *args], check=True, capture_output=True)
        for name in ("alpha", "beta"):
            subprocess.run(["git", "-C", str(tmp), "remote", "remove", "origin"], capture_output=True)
            subprocess.run(["git", "-C", str(tmp), "remote", "add", "origin", f"https://github.com/example/{name}.git"], check=True)
            done = subprocess.run(["bash", str(ROOT / "scripts" / "standard_file.sh")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            shown = done.stdout.splitlines()
            section = shown[shown.index("# standards/review-rules.md") + 2 : -1]
            self.assertEqual(section, [line for _, _, lines in rule_lint.loaded(text, name) for line in lines], name)


if __name__ == "__main__":
    unittest.main()
