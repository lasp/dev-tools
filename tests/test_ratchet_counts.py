"""Tests for scripts/ratchet_counts.py. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import datetime
import importlib.util
import io
import re
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Two records in the two shapes a record takes, flow and block, and a correction, all naming R-012.
LOG = ROOT / "tests" / "fixtures" / "ratchet-log"

_spec = importlib.util.spec_from_file_location("ratchet_counts", ROOT / "scripts" / "ratchet_counts.py")
ratchet_counts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ratchet_counts)


class Counts(unittest.TestCase):
    def test_r012_has_one_disagree_and_one_agree_across_the_two_records(self):
        row = ratchet_counts.count(LOG)["R-012"]
        self.assertEqual((row["firings"], row["agree"], row["disagree"], row["discuss"]), (2, 1, 1, 0))

    def test_contested_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            (log / "pr-0001.yaml").write_text(
                "pr: 1\nfindings:\n  - key: R-003/x.py::f\n    verdict: disagree\n    contested: true\nquestions: []\n"
            )
            row = ratchet_counts.count(log)["R-003"]
            self.assertEqual((row["firings"], row["disagree"], row["contested"]), (1, 1, 1))
            self.assertEqual(ratchet_counts.missing(log, [1, 2]), [2])

    def test_a_contested_findings_lines_are_not_read_as_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            (log / "pr-0001.yaml").write_text(
                "pr: 1\nfindings:\n  - key: R-003/x.py::f\n    verdict: disagree\n    contested: true\n"
                '    lines:\n      - "bob: Agree."\n      - "carol: Disagree, not here"\n'
                "  - key: R-004/x.py::g\n    verdict: agree\nquestions: []\n"
            )
            table = ratchet_counts.count(log)
            self.assertEqual((table["R-003"]["firings"], table["R-003"]["contested"]), (1, 1))
            self.assertEqual(table["R-004"]["agree"], 1)
            self.assertEqual(sum(row["firings"] for row in table.values()), 2)

    def test_a_record_counts_the_same_with_or_without_its_contract_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            text = "pr: 1\nfindings:\n  - key: R-003/x.py::f\n    verdict: agree\nquestions: []\n"
            (log / "pr-0001.yaml").write_text(text)
            (log / "pr-0002.yaml").write_text("contract: 1\n" + text.replace("pr: 1", "pr: 2"))
            self.assertEqual(ratchet_counts.count(log)["R-003"]["agree"], 2)

    def test_notes_are_counted_per_rule_beside_the_corrections(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            (log / "note-2026-10-05-R-003.yaml").write_text(
                "date: 2026-10-05\nids: [R-003]\nkind: disagreement\nby: alice\nreason: too broad\n"
            )
            (log / "note-2026-10-06-pr-review.yaml").write_text("date: 2026-10-06\nids: [pr-review]\nkind: procedure\nby: bob\nreason: x\n")
            table = ratchet_counts.count(log)
            self.assertEqual((table["R-003"]["notes"], table["pr-review"]["notes"], table["R-003"]["firings"]), (1, 1, 0))

    def test_a_note_without_ids_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "note-2026-10-07-x.yaml").write_text("date: 2026-10-07\nkind: disagreement\nby: a\n")
            with self.assertRaisesRegex(ValueError, "note-2026-10-07-x.yaml: no 'ids"):
                ratchet_counts.count(Path(tmp))

    def test_a_note_missing_a_field_is_refused_whatever_the_window(self):
        full = {"date": "2026-10-07", "ids": "[R-003]", "kind": "disagreement", "by": "a", "reason": "x"}
        for field in ("date", "kind", "by"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                log = Path(tmp)
                (log / "note-2026-10-07-R-003.yaml").write_text("".join(f"{k}: {v}\n" for k, v in full.items() if k != field))
                with self.assertRaisesRegex(ValueError, f"note-2026-10-07-R-003.yaml: no '{field}:' line"):
                    ratchet_counts.count(log)

    def test_a_correction_missing_a_field_is_refused_whatever_its_date(self):
        full = {"date": "2026-09-01", "ids": "[R-003]", "kind": "settled", "source": "PR o/r#1", "by": "a", "clause": "x"}
        for field in ("date", "kind", "source", "by", "clause"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                log = Path(tmp)
                text = "".join(f"{k}: {v}\n" for k, v in full.items() if k != field)
                (log / "correction-2026-09-01-R-003.yaml").write_text(text)
                with self.assertRaisesRegex(ValueError, f"correction-2026-09-01-R-003.yaml: no '{field}:' line"):
                    ratchet_counts.count(log, datetime.date(2026, 10, 1) if field != "date" else None)

    def test_a_quoted_key_counts_under_its_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            (log / "pr-0001.yaml").write_text(
                'pr: 1\nfindings:\n  - key: "R-003/x.py::f"\n    verdict: agree\n'
                '  - key: "term/T-010/x.py::g"\n    verdict: disagree\nquestions: []\n'
            )
            table = ratchet_counts.count(log)
            self.assertEqual((table["R-003"]["agree"], table["term/T-010"]["disagree"]), (1, 1))

    def test_corrections_are_counted_per_rule_beside_the_verdicts(self):
        table = ratchet_counts.count(ROOT / "tests" / "fixtures" / "corrections")
        self.assertEqual((table["R-003"]["firings"], table["R-003"]["agree"], table["R-003"]["corrections"]), (1, 1, 2))
        self.assertEqual((table["D-004@widgets"]["disagree"], table["D-004@widgets"]["corrections"]), (1, 1))
        self.assertEqual((table["term/T-010"]["firings"], table["term/T-010"]["corrections"]), (0, 1))
        self.assertIn("corrections", ratchet_counts.render(table).splitlines()[0])

    def test_corrects_correction_and_note_are_counted_under_each_id(self):
        skill = (ROOT / "skills" / "revise" / "correct.md").read_text()
        record, note = re.findall(r"^```yaml\n(.*?)^```", skill, re.M | re.S)[:2]
        date = re.search(r"^date: (\S+)", record, re.M).group(1)
        ids, note_ids = ([i.strip() for i in re.search(r"^ids: \[(.*?)\]", r, re.M).group(1).split(",")] for r in (record, note))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / f"correction-{date}-x.yaml").write_text(record)
            (Path(tmp) / f"note-{date}-x.yaml").write_text(note)
            table = ratchet_counts.count(Path(tmp), datetime.date.fromisoformat(date))
        self.assertEqual([table[i]["corrections"] for i in ids], [1] * len(ids))
        self.assertEqual([table[i]["notes"] for i in note_ids], [1] * len(note_ids))
        prepare = (ROOT / "skills" / "revise" / "prepare.md").read_text()
        self.assertIn("`kind: procedure`", prepare)
        self.assertNotIn("kind: procedure", skill)

    def test_a_procedure_note_written_before_correct_stopped_writing_them_is_still_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "note-2026-09-30-pr-review.yaml").write_text(
                "date: 2026-09-30\nids: [pr-review]\nkind: procedure\nby: alice\nreason: x\n"
            )
            self.assertEqual(ratchet_counts.count(Path(tmp))["pr-review"]["notes"], 1)

    def test_a_correction_without_ids_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "correction-2026-09-30-x.yaml").write_text("date: 2026-09-30\nkind: misread\n")
            with self.assertRaisesRegex(ValueError, "no 'ids"):
                ratchet_counts.count(Path(tmp))


    def test_a_judged_findings_quoted_basis_is_no_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            (log / "pr-0001.yaml").write_text(
                'pr: 1\nfindings:\n  - key: R-003/x.py::f\n    verdict: agree\n    judged: true\n    basis: "contested: true, it says"\n'
                "questions: []\n"
            )
            row = ratchet_counts.count(log)["R-003"]
            self.assertEqual((row["agree"], row["contested"]), (1, 0))


class LedgerAndWindow(unittest.TestCase):
    LEDGER = ROOT / "tests" / "fixtures" / "ledger" / "review-rules.md"

    def test_every_ledger_rule_gets_a_row_with_its_status_bold_or_not(self):
        rules = ratchet_counts.ledger(self.LEDGER)
        self.assertEqual(rules, {"R-003": ("established", "2026-09"), "R-020": ("provisional", "2026-10"), "R-021": ("retired", "2026-08")})
        lines = ratchet_counts.render(ratchet_counts.count(ROOT / "tests" / "fixtures" / "corrections"), rules).splitlines()
        self.assertEqual(lines[0].split()[:4], ["rule", "status", "since", "firings"])
        r020 = next(line.split() for line in lines if line.startswith("R-020"))
        self.assertEqual(r020[:4], ["R-020", "provisional", "2026-10", "0"])
        self.assertEqual(next(line.split() for line in lines if line.startswith("term/T-010"))[1:3], ["-", "-"])

    def test_the_window_counts_only_records_merged_on_or_after_it(self):
        log = ROOT / "tests" / "fixtures" / "corrections"
        inside = ratchet_counts.count(log, datetime.date(2026, 10, 1))
        self.assertEqual((inside["R-003"]["firings"], inside["R-003"]["corrections"]), (0, 1))
        self.assertEqual((ratchet_counts.count(log)["R-003"]["firings"]), 1)

    def test_a_record_reviewed_before_the_window_and_merged_inside_it_is_in_the_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pr-0001.yaml").write_text(
                "contract: 3\npr: 1\ndate: 2026-09-28\nmerged: 2026-10-03\nfindings:\n  - key: R-003/x.py::f\n    verdict: agree\nquestions: []\n"
            )
            self.assertEqual(ratchet_counts.count(Path(tmp), datetime.date(2026, 10, 1))["R-003"]["agree"], 1)
            self.assertEqual(ratchet_counts.count(Path(tmp), datetime.date(2026, 10, 4))["R-003"]["agree"], 0)

    def test_a_record_that_predates_merged_is_in_no_window_and_in_all_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            text = "pr: 1\ndate: 2026-10-05\nfindings:\n  - key: R-003/x.py::f\n    verdict: agree\nquestions: []\n"
            (log / "pr-0001.yaml").write_text(text)
            (log / "pr-0002.yaml").write_text("contract: 2\n" + text.replace("pr: 1", "pr: 2"))
            self.assertEqual(ratchet_counts.count(log, datetime.date(2026, 10, 1))["R-003"]["agree"], 0)
            self.assertEqual(ratchet_counts.count(log)["R-003"]["agree"], 2)
            self.assertEqual(ratchet_counts.unplaced(log), ["pr-0001.yaml", "pr-0002.yaml"])
            out = io.StringIO()
            with unittest.mock.patch("sys.stdin", io.StringIO("3\n")), contextlib.redirect_stdout(out):
                self.assertEqual(ratchet_counts.main([str(log), "--since", "2026-10-01"]), 0)
            self.assertIn("records with no merged: line, in no window or expiry count: pr-0001.yaml, pr-0002.yaml\n", out.getvalue())

    def test_a_record_that_predates_merged_yet_merged_in_the_window_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pr-0002.yaml").write_text("contract: 2\npr: 2\ndate: 2026-10-05\nfindings: []\nquestions: []\n")
            err = io.StringIO()
            with unittest.mock.patch("sys.stdin", io.StringIO("1\n2\n")), contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ratchet_counts.main([tmp]), 1)
            self.assertIn("pr-0002.yaml: merged in the window but predates 'merged:'", err.getvalue())

    def test_entries_reads_each_rule_and_its_optional_bar_lines(self):
        got = ratchet_counts.entries(self.LEDGER)
        self.assertEqual(list(got), ["R-003", "R-020", "R-021"])
        self.assertEqual(
            [got[r]["title"] for r in got],
            ["One exception type per condition", "A rule nobody has cited", "A retired rule"],
        )
        self.assertEqual((got["R-003"]["tier"], got["R-003"]["status"], got["R-003"]["evidence"]), ("reviewer", "established", "pr-0001"))
        self.assertNotIn("scope", got["R-020"])
        self.assertNotIn("example", got["R-020"])

    def test_repo_keeps_only_the_rules_that_apply_to_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review-rules.md"
            text = self.LEDGER.read_text()
            text = text.replace("evidence: pr-0001\n", "evidence: pr-0001\nrepos: [alpha, 'Beta']\n")
            text = text.replace("evidence: pr-0002\n", "evidence: pr-0002\nrepos: [gamma]\n")
            path.write_text(text)
            self.assertEqual(set(ratchet_counts.ledger(path, "beta")), {"R-003", "R-021"})
            self.assertEqual(set(ratchet_counts.ledger(path, "gamma")), {"R-020", "R-021"})
            self.assertEqual(set(ratchet_counts.ledger(path)), {"R-003", "R-020", "R-021"})
            out = io.StringIO()
            with contextlib.redirect_stdout(out), unittest.mock.patch("sys.stdin", io.StringIO("")):
                self.assertEqual(ratchet_counts.main([str(ROOT / "tests" / "fixtures" / "corrections"), "--ledger", str(path), "--repo", "gamma"]), 0)
            rows = {line.split()[0] for line in out.getvalue().splitlines() if line.startswith("R-")}
            self.assertIn("R-020", rows)
            path.write_text(text.replace("repos: [gamma]", "repos: gamma"))
            with self.assertRaisesRegex(ValueError, "is not a list of repository names"):
                ratchet_counts.ledger(path, "beta")

    def test_a_fence_hides_headings_and_fields_inside_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review-rules.md"
            text = self.LEDGER.read_text()
            text = text.replace("evidence: pr-0001\n", "evidence: pr-0001\n\n```python\n# set up\n```\n\nrepos: [alpha]\n\n````yaml\nrepos: none\n```\n### R-099\n````\n")
            path.write_text(text)
            rules = ratchet_counts.entries(path)
            self.assertEqual(rules["R-003"]["repos"], "[alpha]")
            self.assertNotIn("R-099", rules)
            self.assertIn("# set up", rules["R-003"]["text"])
            self.assertEqual(set(ratchet_counts.ledger(path, "beta")), {"R-020", "R-021"})

    def test_a_ledger_heading_with_no_status_line_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review-rules.md"
            path.write_text("### R-001 · A rule\n\nWording: somewhere\n")
            with self.assertRaisesRegex(ValueError, "R-001 has no status line"):
                ratchet_counts.ledger(path)

    def test_a_contract_3_record_without_a_merged_day_is_refused(self):
        for head in ("contract: 3\n", "contract: 3\nmerged: soon\n", "merged: 2026-10\n"):
            with self.subTest(head=head), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "pr-0001.yaml").write_text(head + "pr: 1\ndate: 2026-10-02\nfindings: []\nquestions: []\n")
                with self.assertRaisesRegex(ValueError, "pr-0001.yaml: no 'merged: YYYY-MM-DD' line"):
                    ratchet_counts.count(Path(tmp))

    def test_expiry_reads_the_last_firing_and_the_records_since(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)

            def write(n: int, merged: str, cited: str = "", fired: str = "") -> None:
                body = f"  - key: {cited}/x.py::f\n    verdict: agree\n" if cited else ""
                (log / f"pr-{n:04d}.yaml").write_text(
                    f"contract: 3\npr: {n}\ndate: {merged}\nmerged: {merged}\ninner:\n  fired: [{fired}]\n"
                    f"findings:{chr(10) + body if body else ' []' + chr(10)}questions: []\n"
                )

            write(1, "2026-08-20", cited="R-003")
            write(2, "2026-09-15", cited="R-003")
            write(3, "2026-09-20", fired='"R-020"')
            write(4, "2026-10-02")
            write(5, "2026-10-03")
            (log / "pr-0006.yaml").write_text("pr: 6\ndate: 2026-10-04\nfindings:\n  - key: R-021/x.py::f\n    verdict: agree\nquestions: []\n")
            rules = ratchet_counts.ledger(self.LEDGER)
            ages = ratchet_counts.expiry(log, rules)
            # R-003, established since 2026-09, fired on 09-15: not unfired, though the October window holds no firing.
            self.assertEqual(ages["R-003"], ("2026-09-15", "4", "3"))
            self.assertEqual(ratchet_counts.count(log, datetime.date(2026, 10, 1))["R-003"]["firings"], 0)
            # R-020, provisional since 2026-10, is fired by a build's inner.fired before its admission month.
            self.assertEqual(ages["R-020"], ("2026-09-20", "2", "2"))
            # R-021 fires only in a record that predates merged:, which places nothing.
            self.assertEqual(ages["R-021"], ("-", "5", "5"))
            self.assertIn("checked-since-admitted", ratchet_counts.render_expiry(ages, rules).splitlines()[0])

    def test_the_ledger_alone_prints_the_expiry_table_and_the_unplaced_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pr-0001.yaml").write_text("pr: 1\nfindings:\n  - key: R-003/x.py::f\n    verdict: agree\nquestions: []\n")
            out = io.StringIO()
            with unittest.mock.patch("sys.stdin", io.StringIO("")), contextlib.redirect_stdout(out):
                self.assertEqual(ratchet_counts.main([tmp, "--ledger", str(self.LEDGER)]), 0)
        self.assertIn("records with no merged: line, in no window or expiry count: pr-0001.yaml\n", out.getvalue())
        self.assertIn("\nexpiry\nrule   status       since    last-fired  checked-since-admitted  checked-since-fired\n", out.getvalue())

    def test_a_ledger_since_that_is_not_a_month_or_a_day_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "R-001: since: '2026-9' is not YYYY-MM or YYYY-MM-DD"):
                ratchet_counts.expiry(Path(tmp), {"R-001": ("provisional", "2026-9")})

    def test_distinct_prs_agreed_counts_each_pull_request_once_whoever_wrote_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            for n, author in ((1, "alice"), (2, "alice"), (3, "alice")):
                (log / f"pr-{n:04d}.yaml").write_text(
                    f"pr: {n}\nauthor: {author}\nfindings:\n  - key: R-003/x.py::f\n    verdict: agree\n"
                    "  - key: R-003/y.py::g\n    verdict: agree\nquestions: []\n"
                )
            (log / "pr-0004.yaml").write_text("pr: 4\nauthor: carol\nfindings:\n  - key: R-003/x.py::f\n    verdict: disagree\nquestions: []\n")
            row = ratchet_counts.count(log)["R-003"]
            self.assertEqual((row["firings"], row["agree"], row["distinct-prs-agreed"]), (7, 6, 3))

    def test_a_pull_request_nothing_checked_ages_no_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            body = "pr: {n}\nmerged: 2026-10-0{n}\nstandards_sha: {sha}\ninner: {inner}\nfindings: []\nquestions: []\n"
            for n, sha, inner in ((1, "none", "none"), (2, "abc1234", "none"), (3, "none", "\n  exit: clean"), (4, "none", "none")):
                (log / f"pr-{n:04d}.yaml").write_text(body.format(n=n, sha=sha, inner=inner))
            self.assertEqual(ratchet_counts.expiry(log, {"R-001": ("provisional", "2026-10")})["R-001"], ("-", "2", "2"))

    def test_a_review_on_uncommitted_standards_and_a_build_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            (log / "pr-0001.yaml").write_text("pr: 1\nmerged: 2026-10-01\nstandards_sha: none + uncommitted\ninner: none\nfindings: []\nquestions: []\n")
            (log / "pr-0002.yaml").write_text(
                "pr: 2\nmerged: 2026-10-02\nstandards_sha: none\ninner:\n  gates: \"lint 1 · types 0 · tests 2\"\n  exit: clean\nfindings: []\nquestions: []\n"
            )
            self.assertEqual(ratchet_counts.expiry(log, {"R-001": ("provisional", "2026-10")})["R-001"], ("-", "2", "2"))

    def test_a_record_that_cites_a_rule_is_checked_whatever_its_review_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)
            (log / "pr-0001.yaml").write_text(
                "pr: 1\nmerged: 2026-10-03\nstandards_sha: none\ninner: none\nfindings:\n  - key: R-001/x.py::f\n    verdict: agree\nquestions: []\n"
            )
            self.assertEqual(ratchet_counts.expiry(log, {"R-001": ("established", "2026-09")})["R-001"], ("2026-10-03", "1", "0"))


class WindowLine(unittest.TestCase):
    def test_the_outlines_window_line_is_the_form_revise_reads(self):
        line = re.search(r"^```\n(window: .*)$", (ROOT / "skills/revise/outline.md").read_text(), re.M).group(1)
        self.assertEqual(line, "window: <from YYYY-MM-DD>..<to YYYY-MM-DD>")
        self.assertIn("first line `window: <from>..<to>`", (ROOT / "skills/revise/SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
