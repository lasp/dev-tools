#!/usr/bin/env python3
"""Print what a revision window's merged pull requests cost, for the report's Head.

`window_cost.py --threads <dir>` reads every `pr-NNNN/` dump under --threads, a harvest's or a
load's (`docs/contracts.md`, "The thread dump"), whether or not the pull request has a record: its
`pr.json` and `body.md`. It prints one line,
`cost: open-to-merge median <d>d, longest <d>d · <n> merged without a build · <n> pull requests`,
each duration in days to one decimal, from `created_at` to `merged_at`; a pull request merged
without a build is one whose body has no Already checked block, as `scripts/record.py` reads it.
With no pull request it prints `cost: no merged pull request`.

Exits 1 with one `refused · <path> · <why>` line per fault, printing nothing else: a `pr.json` that
cannot be read or lacks `created_at` or `merged_at` as an ISO 8601 UTC time, a merge before its
opening, a dump with no `pr.json` or no `body.md`, or a --threads that is not a directory, which
a load always makes. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record import already_checked  # noqa: E402


def when(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{value!r} is not a time")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threads", type=Path, required=True)
    a = ap.parse_args(argv)
    if not a.threads.is_dir():
        print(f"refused · {a.threads} · not a directory")
        return 1
    faults: list[str] = []
    days: list[float] = []
    unbuilt = 0
    for dump in sorted(d for d in a.threads.glob("pr-*") if d.is_dir()):
        path = dump / "pr.json"
        try:
            pr = json.loads(path.read_text())
            opened, merged = when(pr.get("created_at")), when(pr.get("merged_at"))
        except (OSError, json.JSONDecodeError, ValueError, AttributeError) as e:
            faults.append(f"refused · {path} · no created_at and merged_at to read: {e}")
            continue
        if merged < opened:
            faults.append(f"refused · {path} · merged before it was opened")
            continue
        body = path.parent / "body.md"
        if not body.is_file():
            faults.append(f"refused · {body} · no body.md in the dump")
            continue
        days.append((merged - opened).total_seconds() / 86400)
        unbuilt += already_checked(body.read_text()) is None
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
