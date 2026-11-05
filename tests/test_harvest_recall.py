"""Tests for sandbox/harvest_recall.py and the fixture it scores, sandbox/harvest/."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "sandbox" / "harvest"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harvest_recall = load("harvest_recall", ROOT / "sandbox" / "harvest_recall.py")
guidance_check = load("guidance_check", ROOT / "scripts" / "guidance_check.py")
record = load("record", ROOT / "scripts" / "record.py")
LISTS = sorted((FIXTURE / "comments").glob("pr-*.json"))
RUNS = sorted((FIXTURE / "runs").glob("*.json"))
RECORDED = {
    "recall": "46/46 = 1.00",
    "recall · in replies to agents": "27/27 = 1.00",
    "themes on two prs": "8/8 = 1.00",
    "precision": "45/47 = 0.96",
    "negatives read general": "1/20 = 0.05",
    "quotes exact": "109/109 = 1.00",
}


def score(*args: str) -> dict[str, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = harvest_recall.main([str(FIXTURE), *args])
    assert code == 0, out.getvalue()
    return dict(line.split(": ", 1) for line in out.getvalue().splitlines() if ": " in line and not line.startswith("unmatched"))


class Fixture(unittest.TestCase):
    """The fixture holds the shapes the benchmark measures, and holds them truly."""

    @classmethod
    def setUpClass(cls):
        cls.comments = {c["id"]: c for p in LISTS for c in json.loads(p.read_text())["comments"]}
        cls.labels = json.loads((FIXTURE / "labels.json").read_text())

    def test_each_comment_reads_as_authorship_of_reads_it(self):
        record.project_phrases.cache_clear()
        self.addCleanup(record.project_phrases.cache_clear)
        for c in self.comments.values():
            with self.subTest(comment=c["id"]):
                self.assertEqual(record.authorship_of(c), c["authorship"])

    def test_each_reply_follows_its_threads_opener(self):
        openers = {c["thread"]: c for c in self.comments.values() if c["kind"] == "thread"}
        for c in self.comments.values():
            if c["kind"] == "reply":
                with self.subTest(comment=c["id"]):
                    self.assertLess(openers[c["thread"]]["created"], c["created"])
                    self.assertEqual(openers[c["thread"]]["pr"], c["pr"])

    def test_each_label_quotes_a_persons_own_words(self):
        for item in self.labels["items"]:
            c = self.comments[item["comment_id"]]
            with self.subTest(label=item["id"]):
                self.assertEqual((c["pr"], c["authorship"]), (item["pr"], "human"))
                self.assertTrue(guidance_check.holds(c["body"], item["quote"]))
                self.assertLessEqual(len(item["quote"].split()), guidance_check.MAX_WORDS)
                self.assertIn(item["kind"], guidance_check.KINDS)
                self.assertIn(item["signal"], guidance_check.SIGNALS)

    def test_the_shapes_the_benchmark_measures_are_there(self):
        items = self.labels["items"]
        openers = {c["thread"]: c for c in self.comments.values() if c["kind"] == "thread"}
        replies = [i for i in items if self.comments[i["comment_id"]]["kind"] == "reply"]
        to_agents = [i for i in replies if openers[self.comments[i["comment_id"]]["thread"]]["authorship"] == "ai-drafted"]
        self.assertGreaterEqual(len(replies) / len(items), 0.6)
        self.assertGreaterEqual(len(to_agents), 15)
        for theme in self.labels["themes"]:
            with self.subTest(theme=theme["id"]):
                prs = {i["pr"] for i in items if i["theme"] == theme["id"]}
                self.assertGreaterEqual(len(prs), 2)
                self.assertEqual(sorted(prs), sorted(theme["prs"]))
        labelled = [i["comment_id"] for i in items]
        self.assertGreaterEqual(max(labelled.count(c) for c in labelled), 2)
        for n in self.labels["negatives"]:
            self.assertEqual(self.comments[n]["authorship"], "human")
            self.assertNotIn(n, labelled)
        self.assertGreaterEqual(sum(self.comments[n]["kind"] == "reply" for n in self.labels["negatives"]), 3)

    def test_each_recorded_run_passes_the_guidance_check(self):
        for run in RUNS:
            with self.subTest(run=run.name), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(guidance_check.main([str(run), "--comments", *map(str, LISTS)]), 0)


class Scores(unittest.TestCase):
    """The scores sandbox/README.md "Harvest recall" records, reproduced from the fixture."""

    def test_the_analysts_reading_finds_no_reply(self):
        got = score("--openers")
        self.assertEqual(got["recall"], "14/46 = 0.30")
        self.assertEqual(got["recall · in replies"], "0/32 = 0.00")
        self.assertEqual(got["recall · kind · agent-guidance"], "1/14 = 0.07")
        self.assertEqual(got["themes on two prs"], "1/8 = 0.12")
        self.assertNotIn("precision", got)

    def test_the_recorded_extractor_run(self):
        got = score("--items", str(FIXTURE / "runs" / "guidance-extractor-2026-11-05.json"))
        for key, want in RECORDED.items():
            with self.subTest(key=key):
                self.assertEqual(got[key], want)


class Analyst(unittest.TestCase):
    """--analyst reads the blocks docs/contracts.md "The analysis blocks" defines, and nothing else."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        comments = {c["id"]: c for p in LISTS for c in json.loads(p.read_text())["comments"]}
        labels = json.loads((FIXTURE / "labels.json").read_text())
        self.label = next(i for i in labels["items"] if comments[i["comment_id"]]["kind"] == "thread")
        self.opener = comments[self.label["comment_id"]]
        self.pr = self.opener["pr"]

    def block(self, *lines: str, pr: int | None = None) -> None:
        pr = pr or self.pr
        tail = ["Procedure: none", "Not read: none", "Read: x.py"]
        (self.dir / f"pr-{pr:04d}.md").write_text("\n".join([f"## pr-{pr:04d} — threads read", *lines, *tail]) + "\n")

    def ask(self, by: str = "human", asked: str = "keep the open loud") -> str:
        return (f"thread {self.opener['thread']} · {self.opener['author']} · by: {by} · design · asked: {asked} · "
                f"outcome: changed as asked · diff: addresses it")

    def run_scorer(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = harvest_recall.main([str(FIXTURE), "--analyst", str(self.dir), *extra])
        return code, out.getvalue(), err.getvalue()

    def test_a_persons_ask_line_finds_the_labels_on_its_threads_opener(self):
        self.block(self.ask(), self.ask(by="ai-drafted"), self.ask(asked="none"))
        pairs = self.dir / "pairs.json"
        code, out, _ = self.run_scorer("--pairs", str(pairs))
        self.assertEqual(code, 0)
        self.assertIn("recall: 1/46", out)
        self.assertEqual(out.count("no block · pr-"), 9)
        self.assertEqual([p["lines"] for p in json.loads(pairs.read_text())], [["keep the open loud"]])
        carried = self.dir / "carried.json"
        for answer, want in (("carried", "1/46"), ("local", "0/46")):
            carried.write_text(json.dumps({self.label["id"]: answer}))
            code, out, _ = self.run_scorer("--carried", str(carried))
            self.assertIn(f"recall (principle carried): {want}", out)

    def test_refuses_an_analyst_directory_that_is_not_there(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(harvest_recall.main([str(FIXTURE), "--analyst", str(self.dir / "typo")]), 1)
        self.assertIn("no directory", err.getvalue())

    def test_reads_a_line_block_tally_reads_with_trailing_spaces(self):
        self.block(self.ask() + "  ")
        self.assertIn("recall: 1/46", self.run_scorer()[1])

    def test_refuses_what_it_cannot_place(self):
        carried = self.dir / "carried.json"
        cases = {
            "is a record mismatch": (["record mismatch: PRRT_x"], None),
            "a line of no form": (["some notes on the lines above"], None),
            "is not one of pull request": ([self.ask().replace(self.opener["thread"], "PRRT_nowhere")], None),
            "a line of no form: thread": ([self.ask().replace("changed as asked", "changed")], None),
            f"review {self.opener['id']} is not one of": ([self.ask().replace(f"thread {self.opener['thread']}",
                                                                             f"review {self.opener['id']}")], None),
            "answers other than carried or local": ([self.ask()], {self.label["id"]: "Carried"}),
            "no answer for": ([self.ask()], {}),
        }
        for why, (lines, answers) in cases.items():
            with self.subTest(why=why):
                if lines[0].startswith("record mismatch"):
                    (self.dir / f"pr-{self.pr:04d}.md").write_text(lines[0] + "\n")
                else:
                    self.block(*lines)
                extra = []
                if answers is not None:
                    carried.write_text(json.dumps(answers))
                    extra = ["--carried", str(carried)]
                code, _, err = self.run_scorer(*extra)
                self.assertEqual(code, 1)
                self.assertIn(why, err)


class Matching(unittest.TestCase):
    BODY = "Third swallowed open this month: let the open fail and the traceback name the file. Bump to 0.4.0."
    LABEL = {"id": "L1", "comment_id": 1, "quote": "let the open fail and the traceback name the file."}

    def finds(self, quote, comment_id=1) -> bool:
        return harvest_recall.finds({"comment_id": comment_id, "quote": quote}, self.LABEL, self.BODY)

    def test_an_item_finds_a_label_where_their_quotes_overlap_in_the_comment(self):
        self.assertTrue(self.finds("Third swallowed open this month: let the open fail"))
        self.assertTrue(self.finds("the traceback name the file. Bump to 0.4.0."))
        self.assertTrue(self.finds(None))
        self.assertFalse(self.finds("Bump to 0.4.0."))
        self.assertFalse(self.finds("Third swallowed open this month:"))
        self.assertFalse(self.finds("let the open fail and the traceback name the file.", comment_id=2))

    def test_a_labels_quote_may_leave_words_out(self):
        label = {**self.LABEL, "quote": "Third swallowed open ... name the file."}
        item = {"comment_id": 1, "quote": "the traceback name the file."}
        self.assertTrue(harvest_recall.finds(item, label, self.BODY))
        self.assertFalse(harvest_recall.finds({**item, "quote": "Bump to 0.4.0."}, label, self.BODY))
        self.assertEqual(harvest_recall.spans("Third swallowed open ... name the file.", self.BODY), [])
        self.assertFalse(harvest_recall.finds({**item, "quote": "the open fail"}, label, self.BODY))
        self.assertEqual(harvest_recall.spans("open", "reopen it"), [])
        self.assertEqual(harvest_recall.spans("fail", "> fail\nno"), [])

    def test_a_quote_it_cannot_locate_finds_nothing(self):
        self.assertFalse(self.finds("let the open fail, the traceback names the file"))

    def test_refuses_an_item_on_a_comment_the_fixture_does_not_hold(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"prs": [], "comments_read": 0, "items": [{"comment_id": 1}]}, f)
        bad = Path(f.name)
        self.addCleanup(bad.unlink)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(harvest_recall.main([str(FIXTURE), "--items", str(bad)]), 1)
        self.assertIn("which the fixture does not hold", err.getvalue())


if __name__ == "__main__":
    unittest.main()
