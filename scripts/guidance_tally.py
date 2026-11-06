#!/usr/bin/env python3
"""Say which of a revision's guidance items admit, which are held and which only support.

Reads the slices of one `guidance-extractor` run with the comment lists they read, as
`scripts/guidance_check.py` takes them, and refuses, printing its lines, anything that check
refuses. Then, for each `general` item, as `docs/contracts.md` "The guidance tally" and the
Admission Dial in `standards/dials.md` read it:

- `admit · <key> · pr-NNNN · <comment id> · <author> · <kind> · <signal> · <url> · <quote>`: a
  person's words (`authorship` `human`) that nothing live covers (`covered_by` null) and that meet
  the part of their kind's bar the tally can read: for `rule`, `agent-guidance` and `process`, a
  `signal` of `asks for guidance`, `states a principle`, `addresses agents` or `names a habit`; for `data-convention`
  and `decision`, those or `cites a source`, since a source is what their bar asks; for
  `tool-config`, `exemplar`, `review-calibration` and `open-question`, whose bar reads no signal,
  any. The rest of each kind's bar, and where it goes,
  is `skills/revise/harvest.md`'s "Destinations";
- `covered · <key> · pr-NNNN · <comment id> · <author> · <kind> · <covered_by> · <url> · <quote>`:
  a person's general item a live rule, decision, agent guidance entry, data convention or the
  instruction file already says, which supports it and is no candidate;
- `hold · <key> · pr-NNNN · <comment id> · <author> · <kind> · <criterion> · <url> · <quote>`: a
  person's other general items, of a kind whose bar reads the signal, the criterion `no signal of
  generality` for signal `none` or `signal <signal>, not one that admits`;
- `support · <key> · pr-NNNN · <comment id> · <author> · <kind> · <url> · <quote>`: an agent's
  general item (`ai-drafted`) the pull request's author changed as asked, which never admits.

`<key>` is `s<n>-<i>`, the item's place: the n-th slice given, from 1, and its index in that
slice's items, from 0, so a later step names one item however many share a comment.

An agent's other items, a bot's and every `pr-specific` item are counted, never listed. Lines run
in the slices' order; then one `ask · <key> · pr-NNNN · <author> · <url>` per `admit` or `covered`
line whose item's signal is `asks for guidance`, a person asking for the point to be kept, so the
report names who asked; then a last line, `items: <n> · admit: <n> · covered: <n> · hold: <n> ·
support: <n> · not listed: <n> · asks: <n>`. A quote is printed on one line, its whitespace runs as one space. Exits 0;
exits 1 with the check's lines when it refuses. Stdlib only.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

SIGNALS = ("asks for guidance", "states a principle", "addresses agents", "names a habit")
ANY_SIGNAL = ("tool-config", "exemplar", "review-calibration", "open-question")
SOURCED = ("data-convention", "decision")


def load_check():
    spec = importlib.util.spec_from_file_location("guidance_check", Path(__file__).with_name("guidance_check.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verdict(item: dict) -> tuple[str, str] | None:
    """The tally's word for one item and what follows its kind, or None when it is not listed."""
    if item["generality"] != "general":
        return None
    if item["authorship"] == "human":
        if item["covered_by"] is not None:
            return "covered", item["covered_by"]
        if item["kind"] in ANY_SIGNAL or item["signal"] in SIGNALS or (item["kind"] in SOURCED and item["signal"] == "cites a source"):
            return "admit", item["signal"]
        if item["signal"] == "none":
            return "hold", "no signal of generality"
        return "hold", f"signal {item['signal']}, not one that admits"
    if item["authorship"] == "ai-drafted" and item["outcome"] == "changed as asked":
        return "support", ""
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("slices", type=Path, nargs="+")
    p.add_argument("--comments", type=Path, nargs="+", required=True)
    args = p.parse_args(argv)
    check = load_check()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = check.main([*map(str, args.slices), "--comments", *map(str, args.comments)])
    if code != 0:
        print(out.getvalue(), end="")
        return 1
    counts = {"admit": 0, "covered": 0, "hold": 0, "support": 0}
    items = [(f"s{n}-{i}", it) for n, path in enumerate(args.slices, 1)
             for i, it in enumerate(json.loads(path.read_text())["items"])]
    asks = []
    for key, it in items:
        v = verdict(it)
        if v is None:
            continue
        word, why = v
        counts[word] += 1
        cells = [word, key, f"pr-{it['pr']:04d}", str(it["comment_id"]), it["author"], it["kind"], *([why] if why else []),
                 it["url"], check.flat(it["quote"])]
        print(" · ".join(cells))
        if word in ("admit", "covered") and it["signal"] == "asks for guidance":
            asks.append(f"ask · {key} · pr-{it['pr']:04d} · {it['author']} · {it['url']}")
    print("\n".join(asks), end="\n" if asks else "")
    print(f"items: {len(items)} · " + " · ".join(f"{k}: {n}" for k, n in counts.items())
          + f" · not listed: {len(items) - sum(counts.values())} · asks: {len(asks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
