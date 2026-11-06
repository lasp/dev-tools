"""Tests for scripts/guidance_check.py."""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("guidance_check", ROOT / "scripts" / "guidance_check.py")
guidance_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guidance_check)

REPLY = {
    "pr": 7, "id": 12, "url": "https://github.com/o/r/pull/7#discussion_r12", "author": "bob", "authorship": "human",
    "kind": "reply", "thread": "PRRT_a", "path": "x.py", "line": 5, "created": "2026-10-01T11:00:00Z", "nominated": [],
    "body": "> Always validate units at the boundary.\n\nFixed the name, thanks.\n\n"
            "In general, import dependencies directly:   a degraded state with broken imports is broken.",
}
ITEM = {
    "pr": 7, "comment_id": 12, "url": REPLY["url"], "author": "bob", "authorship": "human",
    "quote": "In general, import dependencies directly: a degraded state with broken imports is broken.",
    "generality": "general", "signal": "states a principle", "kind": "rule",
    "principle": "Import dependencies at module top; no optional-import guards.",
    "rationale": "a degraded state with broken imports is broken.", "covered_by": None, "outcome": "changed as asked",
}


def comment(i: int, pr: int = 9) -> dict:
    return {**REPLY, "pr": pr, "id": i, "url": f"u{i}", "body": "x"}


class GuidanceCheck(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.lists = [self.write("pr-0007.json", {"pr": 7, "comments": [REPLY]}),
                      self.write("pr-0008.json", {"pr": 8, "comments": []})]

    def write(self, name: str, data) -> Path:
        path = self.dir / name
        path.write_text(json.dumps(data))
        return path

    def run_check(self, *slices) -> tuple[int, str]:
        paths = [self.write(f"slice-{n}.json", found) for n, found in enumerate(slices, 1)]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = guidance_check.main([*map(str, paths), "--comments", *map(str, self.lists)])
        return code, out.getvalue()

    def slice(self, *items: dict, **top) -> dict:
        return {"prs": [7, 8], "comments_read": 1, "items": list(items), **top}

    def assertRefused(self, why: str, *slices) -> None:
        code, out = self.run_check(*slices)
        self.assertEqual(code, 1, out)
        self.assertIn(why, out)

    def test_a_run_true_to_its_comments_passes(self):
        specific = {**ITEM, "quote": "Fixed the name", "generality": "pr-specific", "signal": "none", "rationale": None,
                    "covered_by": "R-001"}
        code, out = self.run_check(self.slice(ITEM, specific))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines(), ["slices: 1 · comments: 1 · items: 2 · general: 1 · pr-specific: 1",
                                            "kind · rule · 1 · 1"])

    def test_covered_by_names_a_rule_a_decision_an_entry_or_the_instruction_file(self):
        for covered in ("R-001", "D-002", "A-003", "F-004", "instruction file"):
            with self.subTest(covered=covered):
                self.assertEqual(self.run_check(self.slice({**ITEM, "covered_by": covered}))[0], 0)
        self.assertRefused("covered_by", self.slice({**ITEM, "covered_by": "T-001"}))

    def test_a_quote_never_spans_a_line_quoted_from_someone_else(self):
        body = "Use units.\n> they said\nAlways."
        self.lists[0] = self.write("pr-0007.json", {"pr": 7, "comments": [{**REPLY, "body": body}]})
        self.assertRefused("the quote is not in the comment's own words", self.slice({**ITEM, "quote": "units. Always.",
                                                                                      "rationale": None}))
        self.assertEqual(self.run_check(self.slice({**ITEM, "quote": "Use units.", "rationale": None}))[0], 0)

    def test_a_quote_ending_at_punctuation_before_a_letter_passes(self):
        self.lists[0] = self.write("pr-0007.json", {"pr": 7, "comments": [{**REPLY, "body": "Keep it simple.Please"}]})
        self.assertEqual(self.run_check(self.slice({**ITEM, "quote": "Keep it simple.", "rationale": None}))[0], 0)

    def test_refuses_an_item_untrue_to_its_comment(self):
        cases = {
            "the quote is not in the comment's own words": {"quote": "import dependencies directly, always"},
            "the quote is not in the comment's own words: 'Always": {"quote": "Always validate units at the boundary."},
            "the quote is not in the comment's own words: 'mport": {"quote": "mport dependencies directly"},
            "the quote is not in the comment's own words: 'import dependencies direct'": {"quote": "import dependencies direct"},
            "the rationale is not in the comment's own words": {"rationale": "it is simpler"},
            "the quote has 41 words": {"quote": "word " * 41},
            "the quote has 0 words": {"quote": "   "},
            "the rationale has 0 words": {"rationale": ""},
            "no such comment": {"comment_id": 99},
            "authorship 'ai-drafted', but the comment's is 'human'": {"authorship": "ai-drafted"},
            "url 'x', but the comment's is": {"url": "x"},
            "author 'carol', but the comment's is 'bob'": {"author": "carol"},
            "a pr-specific item has signal": {"generality": "pr-specific"},
            "not of its form": {"kind": "agent instruction"},
            "covered_by='R-1x'": {"covered_by": "R-1x"},
            "comment_id=True": {"comment_id": True},
        }
        for why, change in cases.items():
            with self.subTest(why=why):
                self.assertRefused(why, self.slice({**ITEM, **change}))
        self.assertRefused("keys", self.slice({k: v for k, v in ITEM.items() if k != "outcome"}))

    def test_refuses_a_slice_that_did_not_read_what_it_says(self):
        for top, why in (({"prs": [7, 7, 8]}, "each once"), ({"prs": ["7", 8]}, "each once"),
                         ({"prs": [7, 8, 9]}, "prs [9] have no comment list given"),
                         ({"comments_read": 2}, "comments_read 2, but its lists hold 1"),
                         ({"comments_read": True}, "comments_read True"), ({"items": {}}, "items is not a list")):
            with self.subTest(why=why):
                self.assertRefused(why, self.slice(ITEM, **top))

    def test_refuses_a_slice_of_no_known_shape(self):
        self.assertRefused("not an object with exactly prs, comments_read and items", [ITEM])

    def test_a_slice_it_cannot_read_hides_no_other_slices_fault(self):
        broken = self.dir / "broken.json"
        broken.write_text("{")
        bad = self.write("bad.json", self.slice({**ITEM, "quote": "never said"}, prs=[7]))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(guidance_check.main([str(broken), str(bad), "--comments", *map(str, self.lists)]), 1)
        self.assertIn("broken.json · cannot be read as JSON", out.getvalue())
        self.assertIn("the quote is not in the comment's own words", out.getvalue())
        self.assertIn("refused · pr 8 · in no slice", out.getvalue())

    def test_holds_the_slices_to_the_lists_together(self):
        self.assertRefused("refused · pr 8 · in no slice", self.slice(ITEM, prs=[7]))
        self.assertRefused("pull request 8 is also in", self.slice(ITEM), {"prs": [8], "comments_read": 0, "items": []})
        self.assertRefused("no such comment in the slice's lists", {"prs": [7], "comments_read": 1, "items": []},
                           {"prs": [8], "comments_read": 0, "items": [ITEM]})

    def test_a_slice_past_300_comments_holds_one_pull_request(self):
        self.lists.append(self.write("pr-0009.json", {"pr": 9, "comments": [comment(1000 + i) for i in range(300)]}))
        self.assertEqual(self.run_check(self.slice(ITEM), {"prs": [9], "comments_read": 300, "items": []})[0], 0)
        self.assertRefused("301 comments over 2 pull requests; past 300 a slice holds one",
                           {"prs": [7, 9], "comments_read": 301, "items": [ITEM]},
                           {"prs": [8], "comments_read": 0, "items": []})

    def test_refuses_a_list_or_a_slice_it_cannot_read(self):
        self.lists.append(self.write("bad.json", [REPLY]))
        self.assertRefused("not a comment list", self.slice(ITEM))
        self.lists[-1] = self.write("again.json", {"pr": 7, "comments": []})
        self.assertRefused("pull request 7 given twice", self.slice(ITEM))
        self.lists.pop()
        broken = self.dir / "broken.json"
        broken.write_text("{")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(guidance_check.main([str(broken), "--comments", *map(str, self.lists)]), 1)
        self.assertIn("cannot be read as JSON", out.getvalue())


if __name__ == "__main__":
    unittest.main()
