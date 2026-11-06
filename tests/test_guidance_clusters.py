"""Tests for scripts/guidance_clusters.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("guidance_clusters", ROOT / "scripts" / "guidance_clusters.py")
guidance_clusters = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guidance_clusters)

TALLY = """\
admit · s1-0 · pr-0101 · 11 · bob · rule · states a principle · u11 · Install the library in CI; never mock it away.
covered · s1-1 · pr-0101 · 12 · bob · rule · R-002 · u12 · Let it raise.
hold · s1-2 · pr-0104 · 41 · carol · rule · no signal of generality · u41 · Put libnetcdf in the image, not a fake.
support · s1-3 · pr-0104 · 42 · alice · rule · u42 · A missing system library is installed, not mocked.
admit · s1-4 · pr-0106 · 61 · dave · rule · addresses agents · u61 · Agents: add the dependency · CI, never skip.
hold · s1-5 · pr-0106 · 62 · dave · process · no signal of generality · u62 · Changelog holds user-visible changes.
items: 9 · admit: 2 · covered: 1 · hold: 2 · support: 1 · not listed: 3 · asks: 0
"""
LEDGER = ("# Review rules\n\n## R-001 · A rule\n\n## Candidates below the criteria\n\n### Changelog scope\n\nEvidence.\n\n"
          "#### Evidence\n\nprs: pr-48, pr-0104\n\n- **Held:** an agent's ask in pr-0061; fails **Admission** twice.\n\n"
          "- **Keyword-only arguments for flags.** Evidence: pr-0048. Held: its one ask is AI-drafted.\nprs: none\n")


class Clusters(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / "tally.txt").write_text(TALLY)
        (self.dir / "rules.md").write_text(LEDGER)

    def run_clusters(self, clusters, ledger: bool = True) -> tuple[int, list[str]]:
        (self.dir / "clusters.json").write_text(json.dumps(clusters))
        args = ["--clusters", str(self.dir / "clusters.json"), "--tally", str(self.dir / "tally.txt")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = guidance_clusters.main([*args, *(["--ledger", str(self.dir / "rules.md")] if ledger else [])])
        return code, out.getvalue().splitlines()

    def two(self, **change) -> dict:
        first = {"id": "C1", "kind": "rule", "principle": "Install a missing system dependency rather than mock it.",
                 "items": ["s1-0", "s1-2", "s1-3", "s1-4"],
                 "notes": ["pr-0108 · erin · human · thread PRRT_x: add libhdf5 · the image",
                           "pr-0109 · copilot · bot · thread PRRT_y: mock the import"], "held": None}
        second = {"id": "C2", "kind": "process", "principle": "The changelog lists only user-visible changes.", "items": ["s1-5"],
                  "notes": ["pasted notes-1.md · erin · keep the changelog to what users see"], "held": "Changelog scope"}
        return {"clusters": [{**first, **change}, second]}

    def test_prints_each_cluster_with_its_people_prs_and_quotes(self):
        code, lines = self.run_clusters(self.two())
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines, [
            "cluster · C1 · rule · admit 2 · hold 1 · support 1 · prs 4 · people 4 · "
            "Install a missing system dependency rather than mock it.",
            "prs · C1 · pr-0101, pr-0104, pr-0106, pr-0108",
            "people · C1 · bob, carol, dave, erin",
            "priority · C1 · high · 4 pull requests",
            "asked · C1 · pr-0101, pr-0104, pr-0106, pr-0108",
            "note · C1 · pr-0108 · erin · human · thread PRRT_x: add libhdf5 · the image",
            "note · C1 · pr-0109 · copilot · bot · thread PRRT_y: mock the import",
            'said · C1 · "Install the library in CI; never mock it away." — bob, u11',
            'said · C1 · "Agents: add the dependency · CI, never skip." — dave, u61',
            'said · C1 · "Put libnetcdf in the image, not a fake." — carol, u41',
            "cluster · C2 · process · admit 0 · hold 1 · support 0 · prs 1 · people 2 · The changelog lists only user-visible changes.",
            "prs · C2 · pr-0106",
            "people · C2 · dave, erin",
            "priority · C2 · high · 3 pull requests",
            "asked · C2 · pr-0048, pr-0104, pr-0106",
            "held · C2 · Changelog scope",
            "note · C2 · pasted notes-1.md · erin · keep the changelog to what users see",
            'said · C2 · "Changelog holds user-visible changes." — dave, u62',
            "clusters: 2 · lines: 5",
        ])

    def test_an_agents_or_a_bots_words_count_for_no_pull_request_or_person(self):
        clusters = {"clusters": [
            {"id": "C1", "kind": "rule", "principle": "One person.", "items": ["s1-2", "s1-3", "s1-0", "s1-4", "s1-5"],
             "notes": ["pr-0201 · alice · ai-drafted · thread PRRT_a: x", "pr-0202 · copilot · bot · review 9: y"],
             "held": None}]}
        head = self.run_clusters(clusters)[1][0]
        self.assertIn("· prs 3 · people 3 ·", head)
        clusters["clusters"][0]["items"] = ["s1-2", "s1-3"]
        clusters["clusters"].append({"id": "C2", "kind": "rule", "principle": "Rest.", "items": ["s1-0", "s1-4", "s1-5"], "notes": [],
                                     "held": None})
        self.assertIn("· support 1 · prs 1 · people 1 ·", self.run_clusters(clusters)[1][0])

    def test_refuses_a_tally_cut_short_or_miscounted(self):
        for tally, why in ((TALLY.rsplit("items:", 1)[0], "no closing `items:` line"),
                           (TALLY.replace("hold: 2", "hold: 3"), "counts hold otherwise"),
                           (TALLY.replace("· u42 · A missing", "· A missing"), None)):
            with self.subTest(why=why):
                (self.dir / "tally.txt").write_text(tally)
                code, lines = self.run_clusters(self.two())
                self.assertEqual(code, 1)
                if why:
                    self.assertIn(why, "\n".join(lines))

    def test_quotes_a_second_line_of_a_pull_request_once_every_one_is_quoted(self):
        quoted = [line for line in self.run_clusters({"clusters": [
            {"id": "C1", "kind": "rule", "principle": "All of it.", "items": ["s1-0", "s1-2", "s1-3", "s1-4", "s1-5"], "notes": [], "held": None}
        ]})[1] if line.startswith("said")]
        self.assertEqual([q.rsplit(", ", 1)[1] for q in quoted], ["u11", "u61", "u41"])

    def test_a_held_candidate_is_a_heading_or_a_bullets_bold_title(self):
        for title in ("Changelog scope", "Keyword-only arguments for flags", "Keyword-only arguments for flags."):
            with self.subTest(title=title):
                self.assertEqual(self.run_clusters(self.two(held=title))[0], 0)

    def test_a_kind_is_one_its_lines_carry_or_any_for_notes_alone(self):
        minority = self.two(items=["s1-0", "s1-2", "s1-3", "s1-4"])
        minority["clusters"][0]["items"].append("s1-5")
        minority["clusters"][0]["kind"] = "process"
        minority["clusters"].pop()
        minority["clusters"].append({"id": "C2", "kind": "open-question", "principle": "Who owns the image?",
                                     "items": [], "notes": ["pasted notes-1.md · erin · who owns the image"], "held": None})
        code, lines = self.run_clusters(minority)
        self.assertEqual(code, 0, lines)
        self.assertEqual([x.split(" · ")[2] for x in lines if x.startswith("cluster ·")], ["process", "open-question"])

    def test_only_an_admit_line_of_its_own_kind_admits_a_cluster(self):
        clusters = {"clusters": [
            {"id": "C1", "kind": "rule", "principle": "Mostly held rules.", "items": ["s1-2", "s1-5"], "notes": [], "held": None},
            {"id": "C2", "kind": "rule", "principle": "Rest.", "items": ["s1-0", "s1-3", "s1-4"], "notes": [], "held": None}]}
        clusters["clusters"][0]["items"] = ["s1-2", "s1-0"]
        clusters["clusters"][1]["items"] = ["s1-3", "s1-4", "s1-5"]
        clusters["clusters"][1]["kind"] = "process"
        code, lines = self.run_clusters(clusters)
        self.assertEqual(code, 0, lines)
        heads = [x for x in lines if x.startswith("cluster ·")]
        self.assertIn("· rule · admit 1 · hold 1 · support 0 ·", heads[0])
        self.assertIn("· process · admit 0 · hold 2 · support 1 ·", heads[1])

    def test_a_persons_ask_admits_its_cluster_whatever_its_kind_and_names_who_asked(self):
        (self.dir / "tally.txt").write_text(TALLY.replace("items: 9", "ask · s1-4 · pr-0106 · dave · u61\nitems: 9")
                                            .replace("asks: 0", "asks: 1"))
        clusters = {"clusters": [
            {"id": "C1", "kind": "rule", "principle": "Rules.", "items": ["s1-0", "s1-2", "s1-3"], "notes": [], "held": None},
            {"id": "C2", "kind": "process", "principle": "Asked.", "items": ["s1-4", "s1-5"], "notes": [], "held": None}]}
        code, lines = self.run_clusters(clusters)
        self.assertEqual(code, 0, lines)
        self.assertIn("· process · admit 1 · hold 1 · support 0 ·", [x for x in lines if x.startswith("cluster · C2")][0])
        self.assertEqual([x for x in lines if x.startswith("ask ·")], ["ask · C2 · dave · u61"])
        (self.dir / "tally.txt").write_text(TALLY.replace("items: 9", "ask · s1-4 · pr-0106 · dave · u61\nitems: 9"))
        self.assertIn("counts asks otherwise", "\n".join(self.run_clusters(clusters)[1]))

    def test_an_ask_on_a_covered_line_is_printed_under_its_entry_and_one_on_no_line_is_refused(self):
        asks = "ask · s1-0 · pr-0101 · bob · u11\nask · s1-1 · pr-0101 · bob · u12\nitems: 9"
        (self.dir / "tally.txt").write_text(TALLY.replace("items: 9", asks).replace("asks: 0", "asks: 2"))
        code, lines = self.run_clusters(self.two())
        self.assertEqual(code, 0, lines)
        self.assertIn("· rule · admit 2 ·", [x for x in lines if x.startswith("cluster · C1")][0])
        self.assertEqual([x for x in lines if x.startswith("ask ·")], ["ask · C1 · bob · u11", "ask · R-002 · bob · u12"])
        for key in ("s1-2", "s1-9"):
            with self.subTest(key=key):
                (self.dir / "tally.txt").write_text(TALLY.replace("items: 9", f"ask · {key} · pr-0104 · carol · u41\nitems: 9")
                                                    .replace("asks: 0", "asks: 1"))
                self.assertIn(f"an ask names no admit or covered line: {key}", "\n".join(self.run_clusters(self.two())[1]))

    def test_a_cluster_of_agents_lines_alone_takes_their_kind_and_people_s_lines_outrank_them(self):
        (self.dir / "tally.txt").write_text(TALLY.replace("support · s1-3 · pr-0104 · 42 · alice · rule ·",
                                                          "support · s1-3 · pr-0104 · 42 · alice · tool-config ·"))
        alone = self.two(items=["s1-0", "s1-2", "s1-4"])
        alone["clusters"].append({"id": "C3", "kind": "tool-config", "principle": "An agent's.", "items": ["s1-3"],
                                  "notes": [], "held": None})
        self.assertEqual(self.run_clusters(alone)[0], 0)
        alone["clusters"][2]["kind"] = "rule"
        self.assertIn("kind rule, which none of its lines is", "\n".join(self.run_clusters(alone)[1]))
        outranked = self.two(kind="tool-config")
        code, lines = self.run_clusters(outranked)
        self.assertEqual(code, 1)
        self.assertIn("kind tool-config, which none of its lines is", "\n".join(lines))

    def test_priority_counts_people_s_and_agents_changed_pull_requests_at_the_recurring_ask_dial(self):
        one = {"id": "C1", "kind": "rule", "principle": "P.", "items": ["s1-2"], "notes": [], "held": None}
        two = {**one, "id": "C2", "items": ["s1-0", "s1-3"]}
        rest = {**one, "id": "C3", "items": ["s1-4", "s1-5"]}
        lines = self.run_clusters({"clusters": [one, two, rest]})[1]
        self.assertEqual([x for x in lines if x.startswith("priority")],
                         ["priority · C1 · low · 1 pull request", "priority · C2 · medium · 2 pull requests",
                          "priority · C3 · low · 1 pull request"])
        agents = {**one, "id": "C4", "items": ["s1-3"]}
        two_only = {**two, "items": ["s1-0"]}
        lines = self.run_clusters({"clusters": [one, two_only, rest, agents]})[1]
        self.assertIn("priority · C4 · low · 0 pull requests", lines)
        held = {**one, "held": "Keyword-only arguments for flags"}
        lines = self.run_clusters({"clusters": [held, two, rest]})[1]
        self.assertIn("priority · C1 · low · 1 pull request", lines)
        held = {**one, "held": "Changelog scope"}
        lines = self.run_clusters({"clusters": [held, two, rest]})[1]
        self.assertIn("priority · C1 · medium · 2 pull requests", lines)
        agents_held = {**agents, "held": "Changelog scope"}
        lines = self.run_clusters({"clusters": [one, two_only, rest, agents_held]})[1]
        self.assertIn("priority · C4 · low · 0 pull requests", lines)
        code, lines = self.run_clusters({"clusters": [{**one, "held": "Held:"}, two, rest]})
        self.assertIn("no held candidate headed 'Held:'", "\n".join(lines))
        three = {**two, "items": ["s1-0", "s1-2", "s1-4"]}
        lines = self.run_clusters({"clusters": [three, {**one, "id": "C3", "kind": "process", "items": ["s1-3", "s1-5"]}]})[1]
        self.assertIn("priority · C2 · high · 3 pull requests", lines)
        dials = self.dir / "dials.md"
        dials.write_text("| Recurring ask | 2 pull requests |\n")
        with unittest.mock.patch.object(guidance_clusters, "DIALS", dials):
            code, lines = self.run_clusters({"clusters": [one, two, rest]})
        self.assertEqual(code, 1)
        self.assertIn("no Recurring ask Dial reading", "\n".join(lines))

    def test_a_cluster_draws_on_every_covered_repository_s_tally(self):
        other = self.dir / "gadgets.txt"
        other.write_text("admit · s1-0 · pr-0101 · 21 · frank · rule · asks for guidance · g21 · Install it in CI.\n"
                         "ask · s1-0 · pr-0101 · frank · g21\n"
                         "items: 1 · admit: 1 · covered: 0 · hold: 0 · support: 0 · not listed: 0 · asks: 1\n")
        clusters = self.two(items=["s1-0", "s1-2", "s1-3", "s1-4", "gadgets:s1-0"],
                            notes=["gadgets/pr-0102 · gina · human · thread PRRT_g: install it"])
        (self.dir / "clusters.json").write_text(json.dumps(clusters))
        args = ["--clusters", str(self.dir / "clusters.json"), "--tally", str(self.dir / "tally.txt"),
                "--ledger", str(self.dir / "rules.md")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = guidance_clusters.main([*args, "--repo", "widgets", "--tally-from", f"gadgets={other}"])
        lines = out.getvalue().splitlines()
        self.assertEqual(code, 0, lines)
        self.assertIn("prs · C1 · gadgets/pr-0101, gadgets/pr-0102, pr-0101, pr-0104, pr-0106", lines)
        self.assertIn("repos · C1 · gadgets, widgets", lines)
        self.assertIn("ask · C1 · frank · g21", lines)
        self.assertIn("repos · C2 · widgets", lines)
        self.assertIn("priority · C1 · high · 5 pull requests", lines)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(guidance_clusters.main([*args, "--tally-from", f"gadgets={other}"]), 1)
        self.assertIn("--tally-from needs --repo", out.getvalue())
        self.assertIn("asked · C1 · gadgets/pr-0101, gadgets/pr-0102, widgets/pr-0101, widgets/pr-0104, widgets/pr-0106", lines)
        for bad, why in ((f"widgets={other}", "is not <another repository>"), ("gadgets", "is not <another repository>")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(guidance_clusters.main([*args, "--repo", "widgets", "--tally-from", bad]), 1)
            self.assertIn(why, out.getvalue())
        (self.dir / "rules.md").write_text(LEDGER.replace("prs: pr-48, pr-0104", "prs: widgets/pr-48, gadgets/pr-0101"))
        clusters["clusters"][0]["notes"] = ["gadget/pr-0102 · gina · human · thread PRRT_g: install it"]
        (self.dir / "clusters.json").write_text(json.dumps(clusters))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(guidance_clusters.main([*args, "--repo", "widgets", "--tally-from", f"gadgets={other}"]), 1)
        self.assertIn("a note names gadget, no repository given with --tally-from", out.getvalue())
        clusters["clusters"][0]["notes"] = []
        (self.dir / "clusters.json").write_text(json.dumps(clusters))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(guidance_clusters.main([*args, "--repo", "widgets", "--tally-from", f"gadgets={other}"]), 0)
        self.assertIn("asked · C2 · gadgets/pr-0101, widgets/pr-0048, widgets/pr-0106", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(guidance_clusters.main([*args[:4], "--repo", "widgets"]), 1)
        self.assertIn("gadgets:s1-0", out.getvalue())
        alone = self.two(notes=["widgets/pr-0108 · erin · human · thread PRRT_x: add libhdf5"])
        (self.dir / "clusters.json").write_text(json.dumps(alone))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(guidance_clusters.main([*args, "--repo", "widgets"]), 0)
        self.assertIn("asked · C1 · widgets/pr-0101, widgets/pr-0104, widgets/pr-0106, widgets/pr-0108", out.getvalue())
        self.assertIn("repos · C1 · widgets", out.getvalue())

    def test_refuses_a_partition_that_is_not_one(self):
        cases = {
            "'s1-1' is no admit, hold or support line": self.two(items=["s1-0", "s1-1", "s1-2", "s1-3", "s1-4"]),
            "s1-5 is also in C1": self.two(items=["s1-0", "s1-2", "s1-3", "s1-4", "s1-5"]),
            "s1-3 · in no cluster": self.two(items=["s1-0", "s1-2", "s1-4"]),
            "an id not C<n>, or given twice": self.two(id="C2"),
            "no principle": self.two(principle=" "),
            "kind 'style', not one of rule, agent-guidance": self.two(kind="style"),
            "kind process, which none of its lines is": self.two(kind="process"),
            "neither an item nor a note": self.two(items=[], notes=[]),
            "notes are not each": self.two(notes=["a free note"]),
            "notes are not each `": self.two(notes=["pasted notes 1.md · erin · x"]),
            "notes are not each `pr": self.two(notes=["pr-101 · bob · human · thread X: install it"]),
            "items not a list of keys": self.two(items=[["s1-0"]]),
            "no held candidate headed 'R-001 · A rule'": self.two(held="R-001 · A rule"),
            "keys": {"clusters": [{"id": "C1", "items": ["s1-0"]}]},
            "no held candidate headed 'Nothing'": self.two(held="Nothing"),
            "not an object with a clusters list": [],
        }
        for why, clusters in cases.items():
            with self.subTest(why=why):
                code, lines = self.run_clusters(clusters)
                self.assertEqual(code, 1)
                self.assertIn(why, "\n".join(lines))
        code, lines = self.run_clusters(self.two(), ledger=False)
        self.assertEqual(code, 1)
        self.assertIn("joins a held candidate, and no --ledger was given", "\n".join(lines))


class Benchmark(unittest.TestCase):
    def test_the_recorded_clusters_partition_the_recorded_runs_tally(self):
        fixture = ROOT / "sandbox" / "harvest"
        spec = importlib.util.spec_from_file_location("guidance_tally", ROOT / "scripts" / "guidance_tally.py")
        tally = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tally)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(tally.main([str(fixture / "runs" / "guidance-extractor-2026-11-05.json"), "--comments",
                                         *map(str, sorted((fixture / "comments").glob("pr-*.json")))]), 0)
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tally.txt").write_text(out.getvalue())
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                code = guidance_clusters.main(["--clusters", str(fixture / "clusters" / "clusters-2026-11-05.json"),
                                               "--tally", str(Path(d) / "tally.txt"),
                                               "--ledger", str(fixture / "standard" / "review-rules.md")])
        self.assertEqual(code, 0, printed.getvalue())

if __name__ == "__main__":
    unittest.main()
