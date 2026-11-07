#!/usr/bin/env python3
"""Print what a revision window's merged pull requests cost, for the report's Head.

`window_cost.py --threads <dir> --records <dir>` reads every `pr-NNNN/pr.json` under --threads, a
harvest's dumps (`docs/contracts.md`, "The thread dump"), and each one's record,
`<records>/pr-NNNN.yaml` ("The record"). It prints one line,
`cost: open-to-merge median <d>d, longest <d>d · <n> merged without a build · <n> pull requests`,
each duration in days to one decimal, from `created_at` to `merged_at`; a pull request merged
without a build is one whose record reads `build: none`, its body having no Already checked block.
With no pull request it prints `cost: no merged pull request`.

Exits 1 with one `refused · <path> · <why>` line per fault, printing nothing else: a `pr.json` that
cannot be read or lacks `created_at` or `merged_at` as an ISO 8601 UTC time, a merge before its
opening, or a pull request with no record or a record with no `build:` line. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

BUILD = re.compile(r"^build: (.*)$", re.M)


def when(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{value!r} is not a time")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threads", type=Path, required=True)
    ap.add_argument("--records", type=Path, required=True)
    a = ap.parse_args(argv)
    faults: list[str] = []
    days: list[float] = []
    unbuilt = 0
    for path in sorted(a.threads.glob("pr-*/pr.json")):
        try:
            pr = json.loads(path.read_text())
            opened, merged = when(pr.get("created_at")), when(pr.get("merged_at"))
        except (OSError, json.JSONDecodeError, ValueError, AttributeError) as e:
            faults.append(f"refused · {path} · no created_at and merged_at to read: {e}")
            continue
        if merged < opened:
            faults.append(f"refused · {path} · merged before it was opened")
            continue
        record = a.records / f"{path.parent.name}.yaml"
        build = BUILD.search(record.read_text()) if record.is_file() else None
        if build is None:
            faults.append(f"refused · {record} · no record with a `build:` line")
            continue
        days.append((merged - opened).total_seconds() / 86400)
        unbuilt += build.group(1) == "none"
    if faults:
        print("\n".join(faults))
        return 1
    if not days:
        print("cost: no merged pull request")
        return 0
    print(f"cost: open-to-merge median {statistics.median(days):.1f}d, longest {max(days):.1f}d"
          f" · {unbuilt} merged without a build · {len(days)} pull requests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
