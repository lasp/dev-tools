#!/usr/bin/env python3
"""Sample a revision's guidance items for a spot check, and count what the check found.

`sample --seed <text> [--n 10] <slice> [...]` reads the guidance slices `scripts/guidance_check.py`
passed (`docs/contracts.md`, "The guidance items") and picks `--n` of their items at random, every
item when there are fewer, the same ones for the same seed and slices, and prints one line each,
in the slices' order:
`spot · <dir>/<slice>#<n> · pr-NNNN · <url> · <kind> · <generality> · "<quote>" · <principle>`,
`<dir>` the slice's directory name, `<slice>` its name without `.json` and `<n>` the item's place
in it from 1.

`tally --seed <text> [--n 10] --checked <file> <slice> [...]` samples again and reads the check, one
line per sampled item, `<dir>/<slice>#<n> · right` or `<dir>/<slice>#<n> · wrong · <what>`, blank
lines ignored. It prints `spot check: <n> items · <wrong> wrong · error rate <percent>%`, the
percent rounded to a whole number, then `wrong · <id> · <what>` per wrong item, and exits 0.

Exits 1 with one `refused · <where> · <why>` line per fault, printing nothing else: a slice that
cannot be read or holds no `items` list, an `--n` below 1, and for `tally` a line of neither form,
an item not sampled, or a sampled item with no line or with two. With no items at all, `sample`
prints nothing and `tally` prints `spot check: 0 items`. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

LINE = re.compile(r"(?P<id>\S+#\d+) · (?:(?P<right>right)|wrong · (?P<what>\S.*))")


def items(slices: list[Path], faults: list[str]) -> list[tuple[str, dict]]:
    out = []
    for path in slices:
        try:
            listed = json.loads(path.read_text())["items"]
            if not isinstance(listed, list):
                raise TypeError("items is not a list")
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
            faults.append(f"refused · {path} · not a guidance slice: {e}")
            continue
        out += [(f"{path.parent.name}/{path.stem}#{i}", item) for i, item in enumerate(listed, 1)]
    return out


def sample(slices: list[Path], seed: str, n: int, faults: list[str]) -> list[tuple[str, dict]]:
    if n < 1:
        faults.append(f"refused · --n · {n} is below 1")
        return []
    every = items(slices, faults)
    picked = set(random.Random(seed).sample(range(len(every)), min(n, len(every))))
    return [every[i] for i in sorted(picked)]


def tally(picked: list[tuple[str, dict]], checked: Path, faults: list[str]) -> list[str]:
    try:
        lines = [line.strip() for line in checked.read_text().splitlines() if line.strip()]
    except OSError as e:
        faults.append(f"refused · {checked} · cannot be read: {e}")
        return []
    owed = {i for i, _ in picked}
    seen: dict[str, str | None] = {}
    for line in lines:
        m = LINE.fullmatch(line)
        if not m:
            faults.append(f"refused · {checked} · not `<id> · right` or `<id> · wrong · <what>`: {line}")
        elif m["id"] not in owed:
            faults.append(f"refused · {checked} · {m['id']} was not sampled")
        elif m["id"] in seen:
            faults.append(f"refused · {checked} · {m['id']} checked twice")
        else:
            seen[m["id"]] = m["what"]
    faults += [f"refused · {checked} · {i} not checked" for i, _ in picked if i not in seen]
    if not picked:
        return ["spot check: 0 items"]
    wrong = [(i, what) for i, what in seen.items() if what is not None]
    return [
        f"spot check: {len(picked)} items · {len(wrong)} wrong · error rate {round(100 * len(wrong) / len(picked))}%",
        *(f"wrong · {i} · {what}" for i, what in wrong),
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("sample", "tally"))
    ap.add_argument("slices", type=Path, nargs="+")
    ap.add_argument("--seed", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--checked", type=Path)
    a = ap.parse_args(argv)
    if a.command == "tally" and a.checked is None:
        ap.error("tally needs --checked <file>")
    faults: list[str] = []
    picked = sample(a.slices, a.seed, a.n, faults)
    if a.command == "sample":
        out = [
            f'spot · {i} · pr-{item["pr"]:04d} · {item["url"]} · {item["kind"]} · {item["generality"]} · "{item["quote"]}" · {item["principle"]}'
            for i, item in picked
        ]
    else:
        out = tally(picked, a.checked, faults) if not faults else []
    if faults or out:
        print("\n".join(faults or out))
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
