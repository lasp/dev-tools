#!/usr/bin/env python3
"""Record which stages of a revision's `prepare` ran, so its report is never written over a stage
nobody accounted for (`skills/revise/prepare.md`; `docs/contracts.md`, "The revision's run state").

The state is `.review/revision/state.json` under the directory given with --dir, the current
directory by default, which `prepare` runs from the code repository's top level: `{"stages": {"<stage>": {"status": "done" | "skipped", "why":
"<reason>" | null}}}`. The stages, in the order `prepare` runs them:

    sources    the project's sources: the context entries, the watched pages and the page or epic
               named, and the decisions and terms they touch (`context-refresh.md`)
    records    every covered repository's records, harvested and archived
    analysts   this repository's threads, read by `thread-analyst`
    guidance   every covered repository's comments, read by `guidance-extractor`
    sweep      this repository's merged diffs, swept by `diff-probe`
    clusters   the guidance and the asks, clustered across the project
    bar        each proposal held to its kind's bar
    checks     the graduation candidates' checks drafted

Commands:

- `start`: a new run; removes the state, so nothing from an earlier run counts.
- `done <stage>`: the stage ran.
- `skip <stage> <reason>`: the stage did not run, and why, in a few words; a blank reason is
  refused.
- `check`: before the report is written. Prints `unrecorded · <stage>` for each stage neither done
  nor skipped and exits 1; otherwise prints `skipped · <stage> · <reason>` for each skipped stage,
  in order, the lines the report's Head carries, then `stages: <n> done · <n> skipped`, and exits 0.

A stage recorded again takes the later record. An unknown stage or command, or a state file that is
not this form, exits 2 naming it, writing nothing. Stdlib only, Python 3.9.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STAGES = ("sources", "records", "analysts", "guidance", "sweep", "clusters", "bar", "checks")


class Refused(Exception):
    """A command or a state file this script cannot act on."""


def path_in(top: Path) -> Path:
    return top / ".review" / "revision" / "state.json"


def load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise Refused(f"{path} is not JSON: {e}") from e
    stages = data.get("stages") if isinstance(data, dict) and set(data) == {"stages"} else None
    if not isinstance(stages, dict) or not all(
            k in STAGES and isinstance(v, dict) and set(v) == {"status", "why"}
            and ((v["status"] == "done" and v["why"] is None)
                 or (v["status"] == "skipped" and isinstance(v["why"], str) and v["why"].strip()))
            for k, v in stages.items()):
        raise Refused(f"{path} is not a revision's run state")
    return stages


def save(path: Path, stages: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"stages": stages}, indent=1) + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dir", type=Path, default=Path("."))
    p.add_argument("command", choices=("start", "done", "skip", "check"))
    p.add_argument("stage", nargs="?")
    p.add_argument("reason", nargs="*")
    args = p.parse_args(argv)
    path = path_in(args.dir)
    try:
        if args.command == "start":
            if args.stage:
                raise Refused("start takes no stage")
            path.unlink(missing_ok=True)
            return 0
        stages = load(path)
        if args.command == "check":
            if args.stage:
                raise Refused("check takes no stage")
            missing = [s for s in STAGES if s not in stages]
            if missing:
                print("\n".join(f"unrecorded · {s}" for s in missing))
                return 1
            skipped = [s for s in STAGES if stages[s]["status"] == "skipped"]
            for s in skipped:
                print(f"skipped · {s} · {stages[s]['why']}")
            print(f"stages: {len(STAGES) - len(skipped)} done · {len(skipped)} skipped")
            return 0
        if args.stage not in STAGES:
            raise Refused(f"stage {args.stage!r} is not one of {', '.join(STAGES)}")
        why = " ".join(args.reason).strip()
        if args.command == "done":
            if why:
                raise Refused("done takes no reason")
            stages[args.stage] = {"status": "done", "why": None}
        else:
            if not why:
                raise Refused(f"skip {args.stage} needs the reason it did not run")
            stages[args.stage] = {"status": "skipped", "why": why}
        save(path, stages)
        return 0
    except Refused as e:
        print(f"revise_state.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
