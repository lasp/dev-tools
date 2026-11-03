#!/usr/bin/env python3
"""Run the smoke set on two plugin checkouts and say, per scenario, how often each passed its
checks and whether the text the model received differs: what a pull request that rewords the
generic skills shows, on main and on its branch, besides `same_output.py`.

The set is `smoke` in the coverage.yaml beside the scenario file, `scenarios.yaml` beside this
script unless --scenarios names another, which run.py is given too. Each scenario runs --repeat
times on each checkout through run.py `--check`, on Haiku unless --model says otherwise, then same_text.py compares the two, its
output kept in <sandbox>/runs/<scenario>/same_text.txt. The checkouts are variants as run.py names
them, by their directories' names, so the two must differ, and neither may be named `baseline`,
which is the sandbox's own clone. PROFILE_SHADOW_ROOT is left out of every run.

    sandbox/smoke.py --base ../main-checkout --head . [--scenarios FILE] [--only work,quickstart] [--repeat 3] [--max-total 5] [--expected FILE] [--no-reuse]

The base side passes run.py --reuse, so a base run recorded in the last 24 hours with the same key
is taken instead of made again; the head, the change under test, never reuses. A reused run is one
whose summary run.py marked `reused` in this call, with `taken` no earlier than the call and the
run_id and start of the run it came from. It is accepted though it started before the call, its
cost when made is reported beside the call's but not counted as spent, and the notes name how many
runs each scenario's base reused and when they were made. --no-reuse makes every base run afresh.

One row per scenario: each side's passes out of its runs, the text `same`, `differs` or `error`, and
what the call spent on them, then the differing keys, and each side's input tokens a run, mean and
range: every model call's input, cache-read and cache-creation tokens from the run's stream.jsonl,
and the first call's alone, which approximates what loads at session start. A reused run reports
the stream it was recorded with.

A scenario regresses when the head passes fewer of its runs than the base, or fails a check the
base never failed: checks are compared as kinds, with only the numbers run.py measures ignored (a
cost, a turn count, a ticket's length, the turn of a leak), so those do not count as new while a
scenario's own patterns keep their digits. A side with a run that did not happen, a run.py that
exited other than 0 or 1, a summary older than the call that run.py did not reuse for the base in
this call, or one with no check or missing cost_usd, is an error. A scenario that failed every run
on both sides fails the smoke run too, since it shows nothing about the change: run it again with
--repeat 3 or more, or say why it fails on main. One run a side cannot show a behavior change on a
scenario the model sometimes passes unaided, so the controlled-content scenarios want --repeat 3
or more. With --max-total, no run is launched once the set has spent that many dollars, counting
the cost_usd of every run a call made, not of those it reused, and each scenario left out, named
in the summary, fails the smoke run, since it showed nothing. Exits 1 on a regression, an error, a scenario failed on both sides, a
skipped scenario, or a text difference beyond the expected-changes file, which same_text.py reads; 0
otherwise. Needs pyyaml.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BASELINE = "baseline"
BOTH = ("failed on both sides, so it shows nothing about the change: run it again with --repeat 3 or more, "
        "or say in the pull request why it fails on main")


def smoke_set(scenarios: Path) -> list[str]:
    return yaml.safe_load((scenarios.parent / "coverage.yaml").read_text())["smoke"]


def clean_env() -> dict:
    return {k: v for k, v in os.environ.items() if k != "PROFILE_SHADOW_ROOT"}


# The numbers run.py measures in a failed check, which differ from run to run of the same failure:
# a cost, a turn count, a ticket's length, the turn a leak came in. A scenario's own patterns,
# globs, tokens and commands keep their digits, so two of them that differ only there stay apart.
MEASURED = (
    (re.compile(r"^cost [\d.]+ over "), "cost # over "),
    (re.compile(r"^\d+ turns over "), "# turns over "),
    (re.compile(r"^ticket of \d+ words over "), "ticket of # words over "),
    (re.compile(r", turn \d+$"), ", turn #"),
)


def kinds(check: str) -> set[str]:
    """A failed check's parts, `fail: a; b`, with the numbers run.py measures ignored."""
    if not check.startswith("fail"):
        return set()
    out = set()
    for part in (p.strip() for p in check.split(":", 1)[1].split("; ")):
        for pattern, replacement in MEASURED:
            part = pattern.sub(replacement, part)
        if part:
            out.add(part)
    return out


def reused(s: dict, called: int) -> bool:
    """Whether run.py took this run from a recorded one in this call: marked `reused`, with the
    run_id and start of the run it was taken from, and `taken` no earlier than the call, so a reused
    run an earlier call left behind does not count."""
    return (s.get("reused") is True and isinstance(s.get("run_id"), str) and isinstance(s.get("started"), int)
            and isinstance(s.get("taken"), int) and s["taken"] >= called - 1)


def tokens(run: Path) -> "tuple[int, int] | None":
    """A run's input tokens from its stream.jsonl: each model call's input, cache-read and
    cache-creation tokens, counted once per message id and summed, and the first call's alone, which
    approximates what loads at session start. None when the stream is missing, holds a line that is
    not JSON, or carries no usage."""
    path = run / "stream.jsonl"
    if not path.is_file():
        return None
    seen, calls = set(), []
    # Split on newlines only: a JSON string may hold U+0085, U+2028 or a form feed, which
    # str.splitlines would also split on.
    lines = path.read_text().split("\n")
    for line in lines[:-1] if lines[-1] == "" else lines:
        try:
            event = json.loads(line)
        except ValueError:
            return None
        message = event.get("message") if isinstance(event, dict) and event.get("type") == "assistant" else None
        usage = message.get("usage") if isinstance(message, dict) else None
        if not isinstance(usage, dict) or message.get("id") in seen:
            continue
        seen.add(message.get("id"))
        calls.append(sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")))
    return (sum(calls), calls[0]) if calls else None


def spread(counts: list) -> str:
    """Mean and range of a side's input tokens per run, in thousands, and of the first call's."""
    known = [c for c in counts if c is not None]
    if not known:
        return "unknown"
    k = lambda n: f"{n / 1000:.0f}k"
    span = lambda xs: k(sum(xs) / len(xs)) + ("" if min(xs) == max(xs) else f" ({k(min(xs))}-{k(max(xs))})")
    return (f"{span([t for t, _ in known])}, first call {span([f for _, f in known])}"
            + (f", {len(counts) - len(known)} unknown" if len(known) < len(counts) else ""))


def side(scenario: str, variant: Path, args: argparse.Namespace, sandbox: Path, reuse: bool = False) -> dict:
    """The side's checks, one per run, what this call spent, the runs it reused as (run_id, started,
    cost when made), and an error when its runs cannot be trusted."""
    called = int(time.time())
    p = subprocess.run([sys.executable, str(HERE / "run.py"), scenario, "--variant", str(variant), "--model", args.model,
                        "--repeat", str(args.repeat), "--check", "--budget", str(args.budget), "--sandbox", str(sandbox),
                        "--scenarios", str(args.scenarios)]
                       + (["--reuse"] if reuse else []),
                       capture_output=True, text=True, env=clean_env())
    tail = " | ".join(p.stderr.strip().splitlines()[-3:])
    runs = sandbox / "runs" / scenario / variant.resolve().name
    # What this call spent: every summary it made counts, whether or not its runs can be trusted. A
    # reused run keeps the start of the run it came from, so it is left out: it was paid for then.
    cost = 0.0
    for path in sorted(runs.glob("*/summary.json")):
        s = json.loads(path.read_text())
        if s.get("started", 0) < called - 1:
            continue
        if "cost_usd" not in s:
            return {"checks": [], "cost": cost, "reused": [], "error": f"run {path.parent.name}'s summary has no cost_usd"}
        cost += float(s["cost_usd"])
    if p.returncode not in (0, 1):
        return {"checks": [], "cost": cost, "reused": [], "error": f"run.py exit {p.returncode}: {tail}"}
    checks, taken, used = [], [], []
    for n in range(1, args.repeat + 1):
        path = runs / str(n) / "summary.json"
        if not path.is_file():
            return {"checks": checks, "cost": cost, "reused": taken, "error": f"no run {n}: {tail}"}
        s = json.loads(path.read_text())
        if reuse and reused(s, called):
            if "cost_usd" not in s:
                return {"checks": checks, "cost": cost, "reused": taken, "error": f"reused run {n}'s summary has no cost_usd"}
            taken.append((s["run_id"], s["started"], float(s["cost_usd"])))
        elif s.get("started", 0) < called - 1:
            return {"checks": checks, "cost": cost, "reused": taken, "error": f"run {n}'s summary is older than this call"}
        if "check" not in s:
            return {"checks": checks, "cost": cost, "reused": taken, "error": f"run {n} has no check"}
        checks.append(s["check"])
        used.append(tokens(runs / str(n)))
    return {"checks": checks, "cost": cost, "reused": taken, "tokens": used, "error": None}


def judge(base: dict, head: dict) -> tuple[str, bool]:
    """A note on the pair and whether it is a regression or an error."""
    if base["error"] or head["error"]:
        return "error: " + "; ".join(f"{n} {s['error']}" for n, s in (("base", base), ("head", head)) if s["error"]), True
    passes = [sum(c == "pass" for c in s["checks"]) for s in (base, head)]
    new = set().union(*map(kinds, head["checks"])) - set().union(*map(kinds, base["checks"]))
    notes = []
    if passes[1] < passes[0]:
        notes.append(f"head passes {passes[1]} of {len(head['checks'])}, base {passes[0]} of {len(base['checks'])}")
    if new:
        notes.append("new on head: " + "; ".join(sorted(new)))
    if notes:
        return "regression: " + "; ".join(notes), True
    if passes == [0, 0]:
        return BOTH, True
    return "", False


def text(scenario: str, args: argparse.Namespace, sandbox: Path) -> tuple[str, list[str]]:
    """same_text.py's verdict, `same`, `differs` or `error`, and the differing keys."""
    command = [sys.executable, str(HERE / "same_text.py"), scenario, "--sandbox", str(sandbox),
               "--base", args.base.resolve().name, "--head", args.head.resolve().name]
    if args.expected:
        command += ["--expected", str(args.expected)]
    t = subprocess.run(command, capture_output=True, text=True, env=clean_env())
    (sandbox / "runs" / scenario / "same_text.txt").write_text(t.stdout + t.stderr)
    keys = [line[4:] for line in t.stdout.splitlines() if line.startswith("--- ") and (line.endswith("UNEXPECTED") or "did not happen" in line)]
    if t.returncode == 0:
        return "same", keys
    if "keys compared" in t.stdout:
        return "differs", keys
    return "error", [(t.stderr or t.stdout).strip().splitlines()[-1] if (t.stderr or t.stdout).strip() else "same_text.py gave no output"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", type=Path, required=True, help="the checkout compared against, such as a worktree of main")
    p.add_argument("--head", type=Path, required=True, help="the checkout with the change")
    p.add_argument("--scenarios", type=Path, default=HERE / "scenarios.yaml", metavar="FILE",
                   help="the scenario file, its set in the coverage.yaml beside it; default, scenarios.yaml beside smoke.py")
    p.add_argument("--only", help="a comma-separated part of the set")
    p.add_argument("--repeat", type=int, default=1, help="runs per side and scenario; default 1, 3 or more for the controlled-content scenarios")
    p.add_argument("--model", default="haiku", help="default haiku")
    p.add_argument("--budget", type=float, default=1.0, help="the dollar cap on each turn; default 1")
    p.add_argument("--max-total", type=float, help="launch no run once the set has spent this many dollars; a scenario left out fails")
    p.add_argument("--no-reuse", action="store_true", help="make every base run afresh instead of passing run.py --reuse")
    p.add_argument("--expected", type=Path, help="same_text.py's expected-changes file")
    p.add_argument("--sandbox", type=Path, default=Path.cwd(), help="the sandbox (default: the current directory)")
    args = p.parse_args(argv)
    if not args.scenarios.is_file():
        p.error(f"--scenarios {args.scenarios}: no such file")
    if not (args.scenarios.parent / "coverage.yaml").is_file():
        p.error(f"--scenarios {args.scenarios}: no coverage.yaml beside it to name the smoke set")
    args.scenarios = args.scenarios.resolve()
    names = smoke_set(args.scenarios)
    if args.only:
        wanted = args.only.split(",")
        unknown = [w for w in wanted if w not in names]
        if unknown:
            p.error(f"not in the smoke set: {', '.join(unknown)}")
        names = [n for n in names if n in wanted]
    if args.repeat < 1:
        p.error("--repeat must be at least 1")
    base_name, head_name = args.base.resolve().name, args.head.resolve().name
    if base_name == head_name:
        p.error("--base and --head are variants by directory name, so the two names must differ")
    if BASELINE in (base_name, head_name):
        p.error(f"a checkout named {BASELINE} would be taken for the sandbox's own clone; rename it")
    if args.repeat < 3 and any("controlled" in n for n in names):
        print(f"smoke.py: --repeat {args.repeat} on a controlled-content scenario cannot show a behavior change the model sometimes makes unaided; use 3 or more", file=sys.stderr)
    sandbox = args.sandbox.resolve()
    header = ("scenario", "base", "head", "text", "cost")
    rows, notes, skipped, failed, both, total, taken, worth = [], [], [], False, 0, 0.0, 0, 0.0
    spent = lambda: args.max_total is not None and total >= args.max_total
    for name in names:
        if spent():
            skipped.append(name)
            continue
        base = side(name, args.base, args, sandbox, reuse=not args.no_reuse)
        total += base["cost"]
        if spent():
            skipped.append(name)
            continue
        head = side(name, args.head, args, sandbox)
        total += head["cost"]
        note, bad = judge(base, head)
        same, keys = text(name, args, sandbox)
        failed |= bad or same != "same"
        both += note == BOTH
        count = lambda s: "error" if s["error"] else f"{sum(c == 'pass' for c in s['checks'])}/{len(s['checks'])}"
        rows.append((name, count(base), count(head), same, f"${base['cost'] + head['cost']:.2f}"))
        notes += [f"{name}: {note}"] if note else []
        if not (base["error"] or head["error"]):
            notes.append(f"{name}: input tokens a run, base {spread(base['tokens'])}; head {spread(head['tokens'])}")
        if base["reused"]:
            taken += len(base["reused"])
            worth += sum(c for _, _, c in base["reused"])
            when = sorted(time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) for _, t, _ in base["reused"])
            notes.append(f"{name}: base reused {len(base['reused'])} of {len(base['checks'])} run(s), made "
                         + (when[0] if when[0] == when[-1] else f"{when[0]} to {when[-1]}")
                         + f", ${sum(c for _, _, c in base['reused']):.2f} when made")
        notes += [f"{name}: {key}" for key in keys[:8]] + ([f"{name}: and {len(keys) - 8} more, in same_text.txt"] if len(keys) > 8 else [])
        print(f"{name}: base {base['checks'] or base['error']}; head {head['checks'] or head['error']}; text {same}", flush=True)
    widths = [max(len(r[i]) for r in rows + [header]) for i in range(5)]
    for r in [header] + rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))
    for line in notes:
        print(f"  {line}")
    failed |= bool(skipped)
    verdict = "a regression, an error, a skipped scenario or a text difference" if failed else "no regression, no unexpected text difference"
    print(f"smoke.py: {len(rows)} scenario(s), {args.repeat} run(s) a side, ${total:.2f}"
          + (f", the base reusing {taken} run(s) that cost ${worth:.2f} when made" if taken else "") + f"; {verdict}"
          + (f"; {both} failed on both sides, which fails the smoke run" if both else "")
          + (f"; skipped at the ${args.max_total:.2f} cap: {', '.join(skipped)}" if skipped else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
