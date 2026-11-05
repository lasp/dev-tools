#!/usr/bin/env python3
"""Score a harvest's reading of a month of review comments against a labelled answer key.

The benchmark `revise`'s reading of review comments is measured on (`sandbox/README.md`, "Harvest
recall"). A fixture directory holds `comments/pr-NNNN.json`, comment lists in the form
`scripts/comment_list.py` writes, each an object with `pr` and `comments`, and `labels.json`:
`themes`, each `{id, name, principle, prs}`; `items`, the general guidance a full read found, each
`{id, comment_id, pr, author, quote, kind, generality, signal, theme, principle}` and optionally
`covered_by`; and `negatives`, the ids of people's comments that ask only for a change in their
own pull request.

What is scored is one of:
- `--items <file> ...`, `guidance-extractor` slices (`docs/contracts.md`, "The guidance items");
- `--analyst <dir>`, the `thread-analyst` blocks of the fixture's pull requests, `pr-NNNN.md`
  (`docs/contracts.md`, "The analysis blocks"), a pull request with none, such as one past the
  analysts' cap, printed `no block · pr-NNNN` and read as finding nothing, each block read as the
  clusters read it: each line whose
  `asked:` is not `none` and whose `by:` is `human` stands, as a general item with no quote, for
  its source's comment, a thread's opening comment or the review or conversation comment it names;
- `--openers`, that reading with no run: a general item with no quote on each person's thread
  opener, review summary and conversation comment, and none on a reply. It places an item on an
  approval the analyst would read as `asked: none`, so it reports no precision and no negatives.

A predicted item finds a label on the same comment when their quotes overlap there: each quote is
located as `scripts/guidance_check.py` places one, in the comment's own passages and never inside
a word, and the two character spans share a character. A label's quote, written by a person, may
leave words out at `...` or `…`; only the words it keeps count, never the gap. A quote that cannot be located, which `scripts/guidance_check.py` refuses,
finds nothing, and `quotes exact` counts it. An item with no quote finds every label on its
comment. A label is **found** when
an item finds it, and **found general** when that item is `general`.

An analyst line's one-line `asked:` may or may not carry a label's principle, which only a reader
can tell: `--pairs <file>` writes, for each label an item finds, the label's principle and quote
beside the lines that find it, for a judge, and `--carried <file>`, the judge's answer, a JSON
object of each of those labels' ids to `carried` or `local`, adds `recall (principle carried)`.
For `--items`, whose quote is the comment's own words, a label found general is carried.

It prints, as `key: value` lines:
- `recall`: found general over labels, and `recall (any)`: found over labels;
- `recall · kind · <kind>` and `recall · signal · <signal>` for each label kind and signal;
- `recall · in replies` and `recall · in replies to agents`: the labels in a reply, and in a reply
  to a thread an agent's comment opened;
- `theme · <id> · <found general>/<items> · prs <found prs>/<prs> · <on two prs | on fewer>`, a
  theme whose found general items span two pull requests or more being one a two-pull-request bar
  can meet once its items are clustered together, which this script does not do;
- `themes on two prs`: those themes over the themes;
- `kind agreement`: the found labels whose item's kind is the label's (`--items` only);
- `precision`: the general items on people's comments that find a label, over all of them, then
  each that finds none as `unmatched · pr-NNNN · <comment id> · <principle>`, for a person to judge,
  since the key may have missed it (not for `--openers`);
- `negatives read general`: the negatives with a general item on them, over the negatives (not for
  `--openers`);
- `quotes exact`: the items whose quote is in their comment's body (`--items` only).

With `--json <file>` it also writes the figures as JSON. Exits 1 with the reason on a fixture or
input that cannot be read: an item on a comment the fixture does not hold; for `--analyst`, a
`record mismatch` block, or a block `block_tally.py` refuses or whose source is not that comment's
kind, or an id the fixture does not hold; for `--carried`, a value other than `carried` or
`local`, or a label `--pairs` lists with no answer. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Refused(Exception):
    """A fixture or input the scorer cannot read."""


def flat(text: str) -> str:
    return " ".join(text.split())


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise Refused(f"{path} cannot be read as JSON: {e}") from e


def fixture(directory: Path) -> tuple[dict[int, dict], dict]:
    comments = {}
    for path in sorted((directory / "comments").glob("pr-*.json")):
        for c in read_json(path)["comments"]:
            comments[c["id"]] = c
    if not comments:
        raise Refused(f"{directory}/comments holds no comment list")
    labels = read_json(directory / "labels.json")
    for item in labels["items"]:
        if item["comment_id"] not in comments:
            raise Refused(f"label {item['id']} is on comment {item['comment_id']}, which the fixture does not hold")
    return comments, labels


def from_items(paths: list[Path], comments: dict[int, dict]) -> list[dict]:
    out = []
    for path in paths:
        for item in read_json(path)["items"]:
            if item["comment_id"] not in comments:
                raise Refused(f"{path}: an item is on comment {item['comment_id']}, which the fixture does not hold")
            out.append(item)
    return out


def block_tally():
    spec = importlib.util.spec_from_file_location("block_tally", ROOT / "scripts" / "block_tally.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def from_analyst(directory: Path, comments: dict[int, dict]) -> list[dict]:
    """Each human ask line of the fixture's blocks, as an item on the comment its source names; a
    pull request with no block as `{"no_block": pr}`. A block is read with `block_tally.py`'s own
    grammar, so a block it refuses is refused here."""
    bt = block_tally()
    openers = {c["thread"]: c for c in comments.values() if c["kind"] == "thread"}
    if not directory.is_dir():
        raise Refused(f"no directory {directory}")
    out = []
    for pr in sorted({c["pr"] for c in comments.values()}):
        name = f"pr-{pr:04d}"
        path = directory / f"{name}.md"
        if not path.is_file():
            out.append({"no_block": pr})
            continue
        lines = [line.rstrip() for line in path.read_text().splitlines() if line.strip()]
        if lines and bt.MISMATCH.match(lines[0]):
            raise Refused(f"{path.name} is a record mismatch")
        head = bt.ANALYSIS_HEAD.match(lines[0]) if lines else None
        if not head or head.group(1) != name:
            raise Refused(f"{path.name}: the first line is not `## {name} — threads read`")
        try:
            bt.tails(name, lines[1:], bt.TAILS)
        except bt.CannotRun as e:
            raise Refused(f"{path.name}: {e}") from e
        for line in lines[1:]:
            if any(line.startswith(t) for t in bt.TAILS):
                continue
            m = bt.ASK.match(line)
            if not m:
                raise Refused(f"{path.name}: a line of no form: {line[:80]}")
            ref = m["id"]
            c = openers.get(ref) if m["source"] == "thread" else comments.get(int(ref)) if ref.isdigit() else None
            if c is None or c["pr"] != pr or c["kind"] != m["source"]:
                raise Refused(f"{path.name}: {m['source']} {ref} is not one of pull request {pr}'s comments in the fixture")
            if m["by"] == "human" and m["asked"] != "none":
                out.append({"comment_id": c["id"], "pr": c["pr"], "quote": None, "generality": "general", "kind": None,
                            "principle": m["asked"], "authorship": "human"})
    return out


def from_openers(comments: dict[int, dict]) -> list[dict]:
    return [{"comment_id": c["id"], "pr": c["pr"], "quote": None, "generality": "general", "kind": None,
             "principle": "(opener)", "authorship": "human"}
            for c in comments.values() if c["kind"] != "reply" and c["authorship"] == "human"]


def guidance_check():
    spec = importlib.util.spec_from_file_location("guidance_check", ROOT / "scripts" / "guidance_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GC = guidance_check()


def spans(quote: str, body: str, elided: bool = False) -> list[tuple[int, int]]:
    """Where quote lies in body, as `scripts/guidance_check.py` places a quote: in the comment's own
    passages, those between the lines that open `>`, whitespace runs read as one space, never
    starting or ending inside a word. With elided, a label's quote may leave words out at `...` or
    `…`: its parts are found in order, and each part's span is returned, never the gap. Empty when
    it is not there."""
    text = "\n".join(GC.own_words(body))
    parts = re.split(r"\s*(?:\.\.\.|…)\s*", flat(quote)) if elided else [flat(quote)]
    out, where = [], 0
    for part in filter(None, parts):
        left = r"(?<!\w)" if re.match(r"\w", part) else ""
        right = r"(?!\w)" if re.search(r"\w$", part) else ""
        m = re.compile(left + re.escape(part) + right).search(text, where)
        if not m:
            return []
        out.append(m.span())
        where = m.end()
    return out


def finds(item: dict, label: dict, body: str) -> bool:
    """Whether item finds label, both on the comment whose text is body."""
    if item["comment_id"] != label["comment_id"]:
        return False
    if item["quote"] is None:
        return True
    return any(a < d and c < b for a, b in spans(item["quote"], body) for c, d in spans(label["quote"], body, elided=True))


def ratio(n: int, d: int) -> str:
    return f"{n}/{d} = {n / d:.2f}" if d else "0/0"


def score(comments: dict[int, dict], labels: dict, items: list[dict], mode: str,
          carried: dict | None = None) -> tuple[list[str], dict]:
    on = defaultdict(list)
    for it in items:
        on[it["comment_id"]].append(it)
    labs = labels["items"]
    hits = {lab["id"]: [it for it in on[lab["comment_id"]] if finds(it, lab, comments[lab["comment_id"]]["body"])]
            for lab in labs}
    found = {k: bool(v) for k, v in hits.items()}
    general = {k: any(it["generality"] == "general" for it in v) for k, v in hits.items()}
    out, fig = [], {}

    def put(key: str, n: int, d: int) -> None:
        out.append(f"{key}: {ratio(n, d)}")
        fig[key] = [n, d]

    put("recall", sum(general.values()), len(labs))
    put("recall (any)", sum(found.values()), len(labs))
    if carried is not None:
        put("recall (principle carried)", sum(general[lab["id"]] and carried[lab["id"]] == "carried" for lab in labs
                                              if lab["id"] in carried), len(labs))
    for field in ("kind", "signal"):
        for value in sorted({lab[field] for lab in labs}):
            group = [lab for lab in labs if lab[field] == value]
            put(f"recall · {field} · {value}", sum(general[lab["id"]] for lab in group), len(group))
    openers = {c["thread"]: c for c in comments.values() if c["kind"] == "thread"}
    replies = [lab for lab in labs if comments[lab["comment_id"]]["kind"] == "reply"]
    to_agents = [lab for lab in replies if openers[comments[lab["comment_id"]]["thread"]]["authorship"] == "ai-drafted"]
    put("recall · in replies", sum(general[lab["id"]] for lab in replies), len(replies))
    put("recall · in replies to agents", sum(general[lab["id"]] for lab in to_agents), len(to_agents))
    two = 0
    for theme in labels["themes"]:
        group = [lab for lab in labs if lab["theme"] == theme["id"]]
        prs = {lab["pr"] for lab in group if general[lab["id"]]}
        ok = len(prs) >= 2
        two += ok
        n = sum(general[lab["id"]] for lab in group)
        out.append(f"theme · {theme['id']} · {n}/{len(group)} · prs {len(prs)}/{len({lab['pr'] for lab in group})} · "
                   f"{'on two prs' if ok else 'on fewer'}")
        fig[f"theme · {theme['id']}"] = [n, len(group), len(prs), ok]
    put("themes on two prs", two, len(labels["themes"]))
    if mode == "items":
        put("kind agreement", sum(any(it.get("kind") == lab["kind"] for it in hits[lab["id"]]) for lab in labs
                                  if found[lab["id"]]), sum(found.values()))
    if mode != "openers":
        mine = [it for it in items if it["generality"] == "general" and comments[it["comment_id"]]["authorship"] == "human"]
        unmatched = [it for it in mine if not any(finds(it, lab, comments[it["comment_id"]]["body"]) for lab in labs)]
        put("precision", len(mine) - len(unmatched), len(mine))
        out += [f"unmatched · pr-{it['pr']:04d} · {it['comment_id']} · {it['principle']}" for it in unmatched]
        neg = set(labels.get("negatives", []))
        put("negatives read general",
            len({it["comment_id"] for it in items if it["comment_id"] in neg and it["generality"] == "general"}), len(neg))
    if mode == "items":
        put("quotes exact", sum(bool(spans(it["quote"], comments[it["comment_id"]]["body"])) for it in items),
            len(items))
    return out, fig


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("fixture", type=Path)
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--items", type=Path, nargs="+")
    what.add_argument("--analyst", type=Path)
    what.add_argument("--openers", action="store_true")
    p.add_argument("--json", type=Path)
    p.add_argument("--pairs", type=Path, help="write each label an item finds, beside the lines that find it, for a judge")
    p.add_argument("--carried", type=Path, help="the judge's answer: each of those labels' ids to carried or local")
    args = p.parse_args(argv)
    mode = "items" if args.items else "openers" if args.openers else "analyst"
    try:
        comments, labels = fixture(args.fixture)
        items = (from_items(args.items, comments) if mode == "items" else from_openers(comments) if mode == "openers"
                 else from_analyst(args.analyst, comments))
        unread = [it["no_block"] for it in items if "no_block" in it]
        items = [it for it in items if "no_block" not in it]
        pairs = [{"label": lab["id"], "principle": lab["principle"], "quote": lab["quote"],
                  "lines": [it["principle"] for it in items if finds(it, lab, comments[lab["comment_id"]]["body"])]}
                 for lab in labels["items"]]
        pairs = [x for x in pairs if x["lines"]]
        carried = None
        if args.carried:
            carried = read_json(args.carried)
            bad = {k: v for k, v in carried.items() if v not in ("carried", "local")} if isinstance(carried, dict) else carried
            if bad:
                raise Refused(f"{args.carried}: answers other than carried or local: {bad}")
            missing = [x["label"] for x in pairs if x["label"] not in carried]
            if missing:
                raise Refused(f"{args.carried}: no answer for {', '.join(missing)}")
        elif mode == "items":
            carried = {lab["id"]: "carried" for lab in labels["items"]}
    except (Refused, KeyError) as e:
        print(f"harvest_recall.py: {e}", file=sys.stderr)
        return 1
    if args.pairs:
        args.pairs.write_text(json.dumps(pairs, ensure_ascii=False, indent=1))
    lines, fig = score(comments, labels, items, mode, carried)
    print("\n".join([*(f"no block · pr-{pr:04d}" for pr in unread), *lines]))
    if args.json:
        args.json.write_text(json.dumps(fig, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
