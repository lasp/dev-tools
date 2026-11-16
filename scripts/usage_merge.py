#!/usr/bin/env python3
"""Merge usage reports into one result, refusing any report it cannot vouch for.

    usage_merge.py --out MERGED --report AUTHOR PATH [--report AUTHOR PATH ...]

Each `--report` names a report and who sent it: an issue body as the `usage-report` skill files
it, the report in a `json` fence, then `` `sha256:<hex>` `` and an optional
`Filed with /<plugin>:usage-report.` line, blank lines allowed between them; or a payload file as
`usage-report file` writes it, the report's JSON alone. A body's digest is checked against the
JSON's bytes. AUTHOR, a GitHub login or any name used for one sender throughout, is read only to
find one sender's overlapping reports: it never enters the result, and nor does a path.

Writes MERGED, one JSON object, version 1 in `docs/contracts.md`'s "The merged usage reports":
counts summed across the reports, `{median, p90}` kept per report as `[runs, median, p90]`, since
a median of medians is not a median, the values of the list fields counted per report, the
windows' earliest start and latest end, the notes as a sorted list. Prints a short summary of it.

Exits 1, writing nothing, with one line per refused report on stderr naming its path: a body whose
digest does not match its JSON, a file that is neither a body of that shape nor JSON, a report of
a schema version other than this script's, or one not in the shape `usage_report.py` writes,
`after_run` and `overlap` filled; and, among the reports that pass, the same report given twice,
or two reports by one author whose windows overlap. Exits 2, writing nothing, when an AUTHOR is empty
or holds a space. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

_spec = importlib.util.spec_from_file_location("usage_report", Path(__file__).with_name("usage_report.py"))
usage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(usage)

MERGED_SCHEMA = 1
BODY = re.compile(r"```json\n(?P<json>.*?\n)```\n+`sha256:(?P<digest>[0-9a-f]{64})`\n+(?:Filed with /[\w-]+:usage-report\.\n*)?\Z", re.S)
WINDOW = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
AUTHOR = re.compile(r"\S{1,100}\Z")
TOP = ("schema", "plugin_commit", "claude_code_versions", "models", "window", "repos", "sessions", "turns", "skills", "questions",
       "scripts", "hooks", "denials", "chains", "after_run", "agents", "overlap", "notes")
SKILL_COUNTS = ("runs", "typed", "model_triggered", "reruns", "compacted")
REPO_COUNTS = ("with_plugin_use", "with_standard", "not_a_repository")


class Refused(Exception):
    pass


def count(value, where: str) -> int:
    if type(value) is not int or value < 0:
        raise Refused(f"{where} is not a count")
    return value


def counts(value, where: str, keys=None) -> dict:
    """A dict of counts, its keys strings, from `keys` when given."""
    if not isinstance(value, dict):
        raise Refused(f"{where} is not an object of counts")
    for k, v in value.items():
        if keys is not None and k not in keys:
            raise Refused(f"{where} holds {k!r}, not one of {', '.join(keys)}")
        count(v, f"{where}.{k}")
    return value


def table(value, where: str, check) -> dict:
    """A dict whose every value `check` accepts."""
    if not isinstance(value, dict):
        raise Refused(f"{where} is not an object")
    for k, v in value.items():
        check(v, f"{where}.{k}")
    return value


def spread(value, where: str) -> None:
    counts(value, where, ("median", "p90"))
    if set(value) != {"median", "p90"}:
        raise Refused(f"{where} is not {{median, p90}}")


def skill(value, where: str) -> None:
    table(value, where, lambda v, w: None)
    if not {"runs", "turns", "tokens"} <= set(value):
        raise Refused(f"{where} lacks runs, turns or tokens")
    counts({k: v for k, v in value.items() if k not in ("turns", "tokens")}, where, SKILL_COUNTS)
    spread(value["turns"], f"{where}.turns")
    spread(value["tokens"], f"{where}.tokens")


def agent(value, where: str) -> None:
    table(value, where, lambda v, w: None)
    if not {"runs", "models", "tokens"} <= set(value) or not set(value) <= {"runs", "models", "tokens", "unfinished"}:
        raise Refused(f"{where} is not {{runs, models, tokens[, unfinished]}}")
    count(value["runs"], f"{where}.runs")
    count(value.get("unfinished", 0), f"{where}.unfinished")
    counts(value["models"], f"{where}.models")
    spread(value["tokens"], f"{where}.tokens")


def script(value, where: str) -> None:
    if not isinstance(value, dict) or set(value) != {"runs", "exits"}:
        raise Refused(f"{where} is not {{runs, exits}}")
    count(value["runs"], f"{where}.runs")
    counts(value["exits"], f"{where}.exits")


def strings(value, where: str) -> None:
    if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
        raise Refused(f"{where} is not a list of strings")


def checked(report) -> dict:
    """The report when it has the shape `usage_report.py` writes, filled; else Refused, naming the field."""
    if not isinstance(report, dict):
        raise Refused("is not a JSON object")
    if report.get("schema") != usage.SCHEMA:
        raise Refused(f"its schema is {report.get('schema')!r}; this script merges schema {usage.SCHEMA}")
    if set(report) != set(TOP):
        missing, extra = sorted(set(TOP) - set(report)), sorted(set(report) - set(TOP))
        raise Refused(f"its fields differ from schema {usage.SCHEMA}'s: missing {missing or 'none'}, extra {extra or 'none'}")
    if not isinstance(report["plugin_commit"], str) or not usage.COMMIT.match(report["plugin_commit"]):
        raise Refused("plugin_commit is not 12 hex digits")
    strings(report["claude_code_versions"], "claude_code_versions")
    strings(report["models"], "models")
    window = report["window"]
    if (not isinstance(window, dict) or set(window) != {"start", "end"}
            or not all(isinstance(t, str) and WINDOW.match(t) for t in window.values()) or window["start"] >= window["end"]):
        raise Refused("window is not {start, end}, UTC times to the second, start before end")
    counts(report["repos"], "repos", REPO_COUNTS)
    count(report["sessions"], "sessions")
    count(report["turns"], "turns")
    table(report["skills"], "skills", skill)
    answers = usage.ANSWER_TYPES + ("free_text_median_chars",)
    table(report["questions"], "questions", lambda v, w: table(v, w, lambda c, x: counts(c, x, answers)))
    table(report["scripts"], "scripts", script)
    table(report["hooks"], "hooks", lambda v, w: counts(v, w, ("runs",) + usage.HOOK_OUTCOMES))
    table(report["denials"], "denials", counts)
    chains = report["chains"]
    if not isinstance(chains, dict) or set(chains) != {"transitions", "push_after", "pr_open_after"}:
        raise Refused("chains is not {transitions, push_after, pr_open_after}")
    table(chains, "chains", counts)
    if report["after_run"] is None or report["overlap"] is None:
        raise Refused("after_run or overlap is null: the report was not filled, as the usage-report skill fills it before it is sent")
    table(report["after_run"], "after_run", lambda v, w: counts(v, w, usage.OUTCOMES))
    table(report["agents"], "agents", agent)
    overlap = report["overlap"]
    if not isinstance(overlap, dict) or set(overlap) != {"skills", "agents"}:
        raise Refused("overlap is not {skills, agents}")
    table(overlap, "overlap", counts)
    if report["notes"] is not None and not isinstance(report["notes"], str):
        raise Refused("notes is neither text nor null")
    return report


def read(path: Path) -> dict:
    """The report at `path`, an issue body whose digest matches or a payload file; else Refused."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        raise Refused(f"cannot be read as text: {e}") from e
    if text.startswith("```"):
        m = BODY.match(text)
        if not m:
            raise Refused("is not a usage-report issue body: a json fence, then `sha256:<64 hex>`, then at most the Filed with line")
        digest = hashlib.sha256(m.group("json").encode("utf-8")).hexdigest()
        if digest != m.group("digest"):
            raise Refused(f"its digest line says sha256:{m.group('digest')}, but its JSON's sha256 is {digest}: the report was changed after it was shown")
        text = m.group("json")
    try:
        report = json.loads(text)
    except ValueError as e:
        raise Refused(f"is not JSON: {e}") from e
    return checked(report)


def add(into: dict, more: dict) -> None:
    """Sum the counts of `more` into `into`, nested objects included."""
    for k, v in more.items():
        if isinstance(v, dict):
            add(into.setdefault(k, {}), v)
        else:
            into[k] = into.get(k, 0) + v


def triples(rows: list) -> list:
    return sorted(rows, reverse=True)


def merge(reports: list[dict], authors: int) -> dict:
    """One result from checked, distinct reports: summed where the field is a count, kept per report where it is not."""
    out = {
        "schema": MERGED_SCHEMA, "report_schema": usage.SCHEMA, "reports": len(reports), "authors": authors,
        "window": {"start": min(r["window"]["start"] for r in reports), "end": max(r["window"]["end"] for r in reports)},
        "plugin_commits": dict(sorted(Counter(r["plugin_commit"] for r in reports).items())),
        "claude_code_versions": dict(sorted(Counter(v for r in reports for v in set(r["claude_code_versions"])).items())),
        "models": dict(sorted(Counter(m for r in reports for m in set(r["models"])).items())),
        "repos": {}, "sessions": sum(r["sessions"] for r in reports), "turns": sum(r["turns"] for r in reports),
        "skills": {}, "questions": {}, "scripts": {}, "hooks": {}, "denials": {},
        "chains": {"transitions": {}, "push_after": {}, "pr_open_after": {}},
        "after_run": {}, "agents": {}, "overlap": {"skills": {}, "agents": {}},
        "notes": sorted(r["notes"] for r in reports if r["notes"] is not None),
    }
    for r in reports:
        add(out["repos"], r["repos"])
        for name, s in r["skills"].items():
            into = out["skills"].setdefault(name, {"turns": [], "tokens": []})
            add(into, {k: v for k, v in s.items() if k not in ("turns", "tokens")})
            into["reports"] = into.get("reports", 0) + 1
            for k in ("turns", "tokens"):
                into[k].append([s["runs"], s[k]["median"], s[k]["p90"]])
        for name, headers in r["questions"].items():
            for header, c in headers.items():
                into = out["questions"].setdefault(name, {}).setdefault(header, {})
                add(into, {k: v for k, v in c.items() if k != "free_text_median_chars"})
                if "free_text_median_chars" in c:
                    into.setdefault("free_text_median_chars", []).append([c.get("free_text", 0), c["free_text_median_chars"]])
        add(out["scripts"], r["scripts"])
        add(out["hooks"], r["hooks"])
        add(out["denials"], r["denials"])
        add(out["chains"], r["chains"])
        add(out["after_run"], r["after_run"])
        add(out["overlap"], r["overlap"])
        for name, a in r["agents"].items():
            into = out["agents"].setdefault(name, {"tokens": []})
            add(into, {k: v for k, v in a.items() if k != "tokens"})
            into["reports"] = into.get("reports", 0) + 1
            into["tokens"].append([a["runs"], a["tokens"]["median"], a["tokens"]["p90"]])
    for group in ("skills", "agents"):
        for entry in out[group].values():
            for k in ("turns", "tokens"):
                if k in entry:
                    entry[k] = triples(entry[k])
    for headers in out["questions"].values():
        for c in headers.values():
            if "free_text_median_chars" in c:
                c["free_text_median_chars"] = triples(c["free_text_median_chars"])
    return out


def duplicates(reports: list[tuple[str, Path, dict]]) -> list[str]:
    """A refusal per pair: the same report twice, or one author's two reports whose windows overlap."""
    problems = []
    for i, (author_a, path_a, a) in enumerate(reports):
        for author_b, path_b, b in reports[i + 1:]:
            if usage.text_of(a) == usage.text_of(b):
                problems.append(f"{path_b}: the same report as {path_a}; give it once")
            elif author_a.lower() == author_b.lower() and a["window"]["start"] < b["window"]["end"] and b["window"]["start"] < a["window"]["end"]:
                problems.append(f"{path_b}: by the same author as {path_a}, with an overlapping window "
                                f"({b['window']['start']} to {b['window']['end']} and {a['window']['start']} to {a['window']['end']}); give one of them")
    return problems


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def brief(n: int) -> str:
    return f"{n / 1e6:.1f}M" if n >= 1e6 else f"{n / 1e3:.0f}k" if n >= 1e3 else str(n)


def span(rows: list, i: int, fmt=str) -> str:
    values = [row[i] for row in rows]
    lo, hi = min(values), max(values)
    return fmt(lo) if lo == hi else f"{fmt(lo)} to {fmt(hi)}"


def summary(m: dict) -> str:
    skill_runs = sum(s.get("runs", 0) for s in m["skills"].values())
    agent_runs = sum(a.get("runs", 0) for a in m["agents"].values())
    lines = [f"Merged {plural(m['reports'], 'report')} from {plural(m['authors'], 'author')}, {m['window']['start'][:10]} to {m['window']['end'][:10]}: "
             f"{plural(m['sessions'], 'session')}, {plural(m['turns'], 'turn')}, {skill_runs} plugin skill runs, {agent_runs} plugin agent runs.", ""]
    lines += ["| Skill | Runs | Reports | Median turns | Median tokens | After a run |", "| --- | --- | --- | --- | --- | --- |"]
    for name, s in sorted(m["skills"].items(), key=lambda kv: (-kv[1].get("runs", 0), kv[0]))[:10]:
        after = ", ".join(f"{k} {v}" for k, v in sorted(m["after_run"].get(name, {}).items(), key=lambda kv: (-kv[1], kv[0]))[:3]) or "-"
        lines.append(f"| {name} | {s.get('runs', 0)} | {s['reports']} | {span(s['turns'], 1)} | {span(s['tokens'], 1, brief)} | {after} |")
    if m["agents"]:
        lines += ["", "| Agent | Runs | Reports | Median tokens | Unfinished |", "| --- | --- | --- | --- | --- |"]
        for name, a in sorted(m["agents"].items(), key=lambda kv: (-kv[1].get("runs", 0), kv[0]))[:8]:
            lines.append(f"| {name} | {a.get('runs', 0)} | {a['reports']} | {span(a['tokens'], 1, brief)} | {a.get('unfinished', 0)} |")
    answers: dict = {}
    for headers in m["questions"].values():
        for c in headers.values():
            add(answers, {k: v for k, v in c.items() if k != "free_text_median_chars"})
    denials: Counter = Counter()
    for c in m["denials"].values():
        denials.update(c)
    hooks: dict = {}
    for c in m["hooks"].values():
        add(hooks, c)
    overlap = sum(sum(c.values()) for c in m["overlap"].values())
    lines += ["",
              f"Questions: {sum(answers.values())} answered, {answers.get('recommended', 0)} recommended, {answers.get('other_option', 0)} another option, "
              f"{answers.get('free_text', 0)} free text, {answers.get('declined', 0)} declined.",
              f"Denials: {sum(denials.values())}" + (f", most {', '.join(f'{k} {v}' for k, v in denials.most_common(3))}." if denials else "."),
              f"Hooks: {hooks.get('ask', 0)} asks, {hooks.get('deny', 0)} denies.",
              f"Overlap: {overlap} personal skills and agents compete with a plugin one.",
              f"Notes: {len(m['notes'])}."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="where the merged result is written")
    parser.add_argument("--report", nargs=2, action="append", required=True, metavar=("AUTHOR", "PATH"),
                        help="who sent a report, and the issue body or payload file holding it")
    args = parser.parse_args(argv)
    refused, good = [], []
    for author, path in args.report:
        if not AUTHOR.match(author):
            parser.error(f"author {author!r} for {path} is empty or holds a space")
        try:
            good.append((author, Path(path), read(Path(path))))
        except Refused as e:
            refused.append(f"{path}: {e}")
    refused += duplicates(good)
    if refused:
        for line in refused:
            print(f"usage_merge.py: {line}", file=sys.stderr)
        print(f"usage_merge.py: {len(refused)} refused; nothing was written", file=sys.stderr)
        return 1
    merged = merge([r for _, _, r in good], len({a.lower() for a, _, _ in good}))
    args.out.write_text(usage.text_of(merged), encoding="utf-8")
    print(summary(merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
