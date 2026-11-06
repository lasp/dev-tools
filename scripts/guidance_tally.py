#!/usr/bin/env python3
"""Say which of a revision's guidance items admit, which are held and which only support.

Reads the slices of one `guidance-extractor` run with the comment lists they read, as
`scripts/guidance_check.py` takes them, and refuses, printing its lines, anything that check
refuses. Then, for each `general` item, as `docs/contracts.md` "The guidance tally" and the
Admission Dial in `standards/dials.md` read it:

- `admit · <key> · pr-NNNN · <comment id> · <author> · <kind> · <signal> · <url> · <quote>`: a
  person's words (`authorship` `human`) that nothing live covers (`covered_by` null) and that meet
  the part of their kind's bar the tally can read: for `rule`, `agent-guidance` and `process`, a
  `signal` of `states a principle`, `addresses agents` or `names a habit`; for `data-convention`
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

A person's comment that nominates guidance, a `nominated` entry in its comment list (`README.md`,
"Nominating guidance"), has said it is general: each of its items is listed as `admit` with the
signal `nominated`, whatever its generality and signal, unless it is `covered`. Then, after the
items, one line per nomination of a person's comment, `nominated · pr-NNNN · <comment id> ·
<author> · <the keys of that comment's listed items, comma-separated, or not extracted> · <url> ·
<the nominated text>`, so none is dropped; an agent's or a bot's nomination is not one.

An agent's other items, a bot's and every other `pr-specific` item are counted, never listed.
Lines run in the slices' order, then a last line, `items: <n> · admit: <n> · covered: <n> · hold:
<n> · support: <n> · not listed: <n> · nominated: <n>`. A quote is printed on one line, its whitespace runs as one space. Exits 0;
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

SIGNALS = ("states a principle", "addresses agents", "names a habit")
ANY_SIGNAL = ("tool-config", "exemplar", "review-calibration", "open-question")
SOURCED = ("data-convention", "decision")


def load_check():
    spec = importlib.util.spec_from_file_location("guidance_check", Path(__file__).with_name("guidance_check.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verdict(item: dict, nominated: bool = False) -> tuple[str, str] | None:
    """The tally's word for one item and what follows its kind, or None when it is not listed; a
    person's item on a comment that nominates guidance admits as `nominated` unless covered."""
    if item["authorship"] == "human" and nominated:
        return ("covered", item["covered_by"]) if item["covered_by"] is not None else ("admit", "nominated")
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
    comments = [c for path in args.comments for c in json.loads(path.read_text())["comments"]]
    nominating = {c["id"]: c for c in comments if c["nominated"] and c["authorship"] == "human"}
    items = [(f"s{n}-{i}", it) for n, path in enumerate(args.slices, 1)
             for i, it in enumerate(json.loads(path.read_text())["items"])]
    listed: dict[int, list[str]] = {}
    for key, it in items:
        v = verdict(it, it["comment_id"] in nominating)
        if v is None:
            continue
        word, why = v
        counts[word] += 1
        cells = [word, key, f"pr-{it['pr']:04d}", str(it["comment_id"]), it["author"], it["kind"], *([why] if why else []),
                 it["url"], check.flat(it["quote"])]
        print(" · ".join(cells))
        listed.setdefault(it["comment_id"], []).append(key)
    nominations = [(c, text) for c in nominating.values() for text in c["nominated"]]
    for c, text in nominations:
        print(" · ".join(["nominated", f"pr-{c['pr']:04d}", str(c["id"]), c["author"],
                          ", ".join(listed.get(c["id"], [])) or "not extracted", c["url"], check.flat(text)]))
    print(f"items: {len(items)} · " + " · ".join(f"{k}: {n}" for k, n in counts.items())
          + f" · not listed: {len(items) - sum(counts.values())} · nominated: {len(nominations)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
