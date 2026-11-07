"""Tests for scripts/spot_check.py."""

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("spot_check", ROOT / "scripts" / "spot_check.py")
spot_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spot_check)


def item(i: int) -> dict:
    return {"pr": 7, "url": f"https://github.com/o/r/pull/7#discussion_r{i}", "kind": "rule", "generality": "general",
            "quote": f"quote {i}", "principle": f"principle {i}"}


class SpotCheck(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / "guidance").mkdir()
        self.slices = []
        for s, n in ((1, 8), (2, 6)):
            path = self.dir / "guidance" / f"slice-{s}.json"
            path.write_text(json.dumps({"prs": [7], "comments_read": 1, "items": [item(100 * s + i) for i in range(n)]}))
            self.slices.append(str(path))

    def run_it(self, *args: str) -> tuple[int, list[str]]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = spot_check.main([*args, *self.slices])
        return code, out.getvalue().splitlines()

    def sampled(self, seed: str = "2026-10-01..2026-10-31") -> list[str]:
        code, out = self.run_it("sample", "--seed", seed)
        self.assertEqual(code, 0)
        return [line.split(" · ")[1] for line in out]

    def test_ten_items_the_same_for_the_same_seed_each_with_what_to_check(self):
        code, out = self.run_it("sample", "--seed", "w")
        self.assertEqual(code, 0)
        self.assertEqual(len(out), 10)
        self.assertEqual(self.sampled("w"), [line.split(" · ")[1] for line in out])
        self.assertNotEqual(self.sampled("w"), self.sampled("v"))
        self.assertRegex(out[0], r'^spot · guidance/slice-\d#\d+ · pr-0007 · https://\S+ · rule · general · "quote \d+" · principle \d+$')

    def test_fewer_items_than_asked_are_all_sampled(self):
        code, out = self.run_it("sample", "--seed", "w", "--n", "20")
        self.assertEqual((code, len(out)), (0, 14))

    def test_the_tally_counts_wrong_items_into_an_error_rate(self):
        ids = self.sampled("w")
        checked = self.dir / "spot-check.md"
        checked.write_text("\n".join([f"{ids[0]} · wrong · the principle says more than the quote", "", *(f"{i} · right" for i in ids[1:])]))
        code, out = self.run_it("tally", "--seed", "w", "--checked", str(checked))
        self.assertEqual((code, out), (0, ["spot check: 10 items · 1 wrong · error rate 10%",
                                           f"wrong · {ids[0]} · the principle says more than the quote"]))

    def test_an_item_unchecked_checked_twice_or_not_sampled_is_refused(self):
        ids = self.sampled("w")
        every = {f"guidance/slice-{s}#{i}" for s, n in ((1, 8), (2, 6)) for i in range(1, n + 1)}
        stray = sorted(every - set(ids))[0]
        checked = self.dir / "spot-check.md"
        checked.write_text("\n".join([*(f"{i} · right" for i in ids[1:]), f"{ids[1]} · right", f"{stray} · right", "looks fine"]))
        code, out = self.run_it("tally", "--seed", "w", "--checked", str(checked))
        self.assertEqual(code, 1)
        self.assertEqual(out, [
            f"refused · {checked} · {ids[1]} checked twice",
            f"refused · {checked} · {stray} was not sampled",
            f"refused · {checked} · not `<id> · right` or `<id> · wrong · <what>`: looks fine",
            f"refused · {checked} · {ids[0]} not checked",
        ])

    def test_an_unreadable_slice_is_refused(self):
        Path(self.slices[1]).write_text("{}")
        code, out = self.run_it("sample", "--seed", "w")
        self.assertEqual(code, 1)
        self.assertTrue(out[0].startswith(f"refused · {self.slices[1]} · not a guidance slice"))

    def test_no_items_reads_zero(self):
        for s in self.slices:
            Path(s).write_text(json.dumps({"prs": [7], "comments_read": 0, "items": []}))
        checked = self.dir / "spot-check.md"
        checked.write_text("")
        self.assertEqual(self.run_it("sample", "--seed", "w"), (0, []))
        self.assertEqual(self.run_it("tally", "--seed", "w", "--checked", str(checked)), (0, ["spot check: 0 items"]))


if __name__ == "__main__":
    unittest.main()
