#!/usr/bin/env python3
"""Copy a harvest's records into the log, never replacing one that holds findings the new one lacks.

For revise step 1: each `pr-NNNN.yaml` in the harvest's records directory replaces the
log's record of the same number, or is added. The threads are the record's source, so a rewrite
loses nothing it can rebuild; a finding recorded some other way, such as the `## Loop review`
comment `pr-0066.yaml`'s findings came from, which `record.py` does not read, it cannot. So a
harvested record whose findings, counted per rule as `ratchet_counts.py` counts them, fall short
of the log's record for any rule is refused: nothing is copied, each refused record is printed with
the findings it would drop, and the exit is 1. `--keep N` leaves the log's record of pull request
N as it is and copies the rest; a `--keep` naming a record that would drop nothing, or that the
harvest did not write, is refused, so a kept record is always one the threads cannot rebuild, and
so is one whose harvested record holds findings, per rule, the log's lacks, since keeping it would
drop those instead.

Prints `copied pr-NNNN` or `kept pr-NNNN · <n> finding(s) the threads do not carry` per record.
A record either side whose findings cannot be read, or a directory that is not one, exits 1 with
the reason. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from collections import Counter
from pathlib import Path

_spec = importlib.util.spec_from_file_location("ratchet_counts", Path(__file__).with_name("ratchet_counts.py"))
ratchet_counts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ratchet_counts)


def rules(path: Path) -> Counter:
    """A record's findings, counted per rule."""
    return Counter(f["rule"] for f in ratchet_counts.findings(path.read_text(), path.name))


def dropped(old: Path, new: Path) -> Counter:
    """The findings, per rule, `old` holds and `new` does not."""
    return rules(old) - rules(new)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("records", type=Path, help="the harvest's .review/harvest/records/")
    p.add_argument("log", type=Path, help="the standards/<repo>/log/ directory")
    p.add_argument("--keep", type=int, action="append", default=[], help="a pull request whose log record stays as it is")
    args = p.parse_args(argv)
    try:
        for d in (args.records, args.log):
            if not d.is_dir():
                raise ValueError(f"{d} is not a directory")
        harvested = sorted(args.records.glob("pr-*.yaml"))
        losses = {
            path.name: lost
            for path in harvested
            if (args.log / path.name).exists()
            for lost in [dropped(args.log / path.name, path)]
            if lost
        }
        kept = {f"pr-{n:04d}.yaml" for n in args.keep}
        for name in sorted(kept - set(losses)):
            raise ValueError(f"--keep {name[3:7].lstrip('0')}: {name} is not a harvested record that would drop findings")
        for name in sorted(kept):
            gained = dropped(args.records / name, args.log / name)
            if gained:
                counts = ", ".join(f"{rule} ×{n}" for rule, n in sorted(gained.items()))
                raise ValueError(f"--keep {name[3:7].lstrip('0')}: the harvested {name} holds findings the log's does not, which keeping it would drop: {counts}")
    except (ValueError, OSError) as e:
        print(f"archive_records.py: {e}", file=sys.stderr)
        return 1
    refused = {name: lost for name, lost in losses.items() if name not in kept}
    if refused:
        for name, lost in sorted(refused.items()):
            counts = ", ".join(f"{rule} ×{n}" for rule, n in sorted(lost.items()))
            print(f"refused {name[:-5]} · the log's record holds findings the harvested one does not: {counts}")
        return 1
    for path in harvested:
        if path.name in kept:
            print(f"kept {path.stem} · {sum(losses[path.name].values())} finding(s) the threads do not carry")
        else:
            shutil.copyfile(path, args.log / path.name)
            print(f"copied {path.stem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
