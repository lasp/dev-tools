#!/usr/bin/env python3
"""Score onboarding's candidate profile for a repository against what the plugin reads for it today.

The candidate is the profile `scripts/survey.py --profile` writes, every key of the profile schema
in it, with the `.sources.json` file beside it that says where each value came from and names the
repository. Run from the repository's checkout, so `profile.py` reads its standard. Each key is
compared with what `profile.py <owner/repo>` resolves from this plugin, and classed:

- `match`: the candidate's value is the plugin's. Commands compare as `survey.py` compares them,
  lists as sets, a `depth.light` entry by all its fields;
- `differs`: the candidate's value is not the plugin's, which may read `not yet recorded`. Which is right is the person's call, so both are
  printed with where they came from, and a note says when a repository file the survey read states
  the plugin's value too, or when the candidate came from a repository file and no file the survey
  read states the plugin's value, so the plugin's copy is likely stale;
- `conflict`: the repository's own sources disagree, so the candidate records none of them; the
  note says whether the plugin's value is among them;
- `project default`: the candidate reads `not yet recorded`, and the plugin resolves the same value
  for the repository without its own settings, from the standard's project settings (`PROJECT_KEYS`)
  over the default profile, and their rule for it (its private list), so a drop-in profile, which
  leaves the key out, resolves the same: a project or person setting such as `posted_text`;
- `missing`: the candidate reads `not yet recorded`, and without its own settings the plugin would
  resolve another value;
- `asked` and `confirmed`, with `--answers`: the person typed the value, or accepted the
  candidate's proposal, trimmed or whole. A typed value counts as asked, never as captured.

For `downstream`, `depth.light` and `depth.deep`, which onboarding can only propose, `covers` says
whether the proposal holds every value the plugin has, apart from whether it is exactly the same;
the note of a covering proposal counts the values beyond the plugin's, which a person trims, and of
one that does not cover, the plugin's values it leaves out.

`tier` says where the fact lives, for the question of how much a repository's own files can carry:
`derived` (worked out at run time from git history, the code host or another fact, or inferred from
a file, as a `pre-commit run` lint command is from the pre-commit file), `agent file`
(the tool-neutral agent instructions, `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`,
`.github/copilot-instructions.md` and `.github/instructions/`), `human file` (any other committed
file people read or tools run: a template, a doc, `pyproject.toml`, `.pre-commit-config.yaml`, CI),
`plugin store` (only the standard or the default profile holds it) or `person` (asked). A key whose
sources disagree names each of their tiers, in the survey's order; the count line under the table
counts every key once, by its first tier.

`loads` says how the fact reaches the model when read from there, for what it costs a context
window: `script` (a script resolves it and hands over only the value: `profile.py --field`, or
`survey.py` reading the history, the code host, `pyproject.toml`, the pre-commit file, CI or a
template), `on demand` (a skill reads the file when it needs it) or `always` (loaded into every
session: `CLAUDE.md`, `.claude/CLAUDE.md` and what they import with `@path`). The last two give the
file's size in tokens, estimated as characters / 4. A line under the table gives what every
session loads at its start from the repository's committed files, estimated the same way.

`--answers` is a JSON object, `{"<key>": {"how": "asked" | "confirmed", "value": <value>}}`; a
confirmed value must be the candidate's, or for the three proposal keys a subset of it.

    sandbox/onboard_roundtrip.py .review/onboard/profile.yaml
    sandbox/onboard_roundtrip.py candidate.yaml --answers answers.json --json

A report, so a mismatch never fails it. Exits 1, naming the cause, on a candidate, sources file or
answers file that is malformed: a candidate that leaves out a key or that the schema refuses; a
sources file that is missing, leaves out or adds a key, or disagrees with the candidate (a key whose
sources disagree that the candidate records or that lists fewer than two sources, a recorded value
with no source, a source for a value it does not record, a source with no entry in `files`, or a
session start naming a file `files` does not hold or a total that is not its files' sum); or when
profile.py refuses the plugin's files.
Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

TOP = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOP / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile = load("profile")
survey = load("survey")
NR = profile.NOT_RECORDED
COMMANDS = {"tests.command", "coverage.command", "lint.command"}
PROPOSALS = {"downstream", "depth.light", "depth.deep"}
HEADER = "key | class | tier | loads | onboarding | plugin today | covers | note"
AGENT_DIRS = (".github/instructions/",)


class Malformed(Exception):
    """An input the scorer cannot read as what it should be."""


def get(data: dict, key: str):
    top, _, sub = key.partition(".")
    v = data.get(top, NR)
    if sub:
        return v.get(sub, NR) if isinstance(v, dict) else v
    return v


def held(data: dict, key: str) -> bool:
    """Whether the profile writes the key, a value or `not yet recorded`, a section's key under it."""
    top, _, sub = key.partition(".")
    return top in data and (not sub or (isinstance(data[top], dict) and sub in data[top]))


def items(v) -> set:
    return {tuple(sorted(i.items())) if isinstance(i, dict) else i for i in v}


def same(key: str, a, b) -> bool:
    if NR in (a, b):
        return a == b
    if key in COMMANDS:
        return survey.canonical(str(a)) == survey.canonical(str(b))
    if isinstance(a, list) and isinstance(b, list):
        return items(a) == items(b)
    if isinstance(a, str) and isinstance(b, str):
        return " ".join(a.split()) == " ".join(b.split())
    return a == b


def answers_of(path: Path | None, candidate: dict) -> dict:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise Malformed(f"{path}: {e}") from e
    if not isinstance(data, dict):
        raise Malformed(f"{path}: not a JSON object")
    for key, a in data.items():
        if key not in survey.LEAVES:
            raise Malformed(f"{path}: {key!r} is no profile key")
        if not isinstance(a, dict) or a.get("how") not in ("asked", "confirmed") or "value" not in a:
            raise Malformed(f"{path}: {key} needs how (asked or confirmed) and value")
        top, _, sub = key.partition(".")
        try:
            profile.check({top: {sub: a["value"]} if sub else a["value"]}, str(path))
        except profile.ProfileError as e:
            raise Malformed(str(e)) from e
        if a["how"] == "confirmed":
            proposed = get(candidate, key)
            kept = (proposed != NR and isinstance(a["value"], list) and isinstance(proposed, list)
                    and items(a["value"]) <= items(proposed)) if key in PROPOSALS else same(key, a["value"], proposed)
            if proposed == NR or not kept:
                raise Malformed(f"{path}: {key} is confirmed as {a['value']!r}, which is not the candidate's {proposed!r}")
    return data


def sources_of(path: Path, candidate: dict) -> dict:
    """The sources file, checked against the candidate it describes."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise Malformed(f"{path}: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("repo"), str) or not data["repo"] \
            or not isinstance(data.get("keys"), dict) or not isinstance(data.get("files"), dict) \
            or not isinstance(data.get("session_start"), dict):
        raise Malformed(f"{path}: not a sources file: it needs repo, keys, files and session_start")
    keys = data["keys"]
    if set(keys) != set(survey.LEAVES):
        wrong = sorted(set(keys) ^ set(survey.LEAVES))
        raise Malformed(f"{path}: keys should be the profile's, and {', '.join(wrong)} is not or is left out")
    for key, src in keys.items():
        if not isinstance(src, dict) or set(src) != {"source", "conflict", "seen"} \
                or not isinstance(src["source"], (str, type(None))) or not isinstance(src["conflict"], bool) \
                or not isinstance(src["seen"], list) \
                or not all(isinstance(x, dict) and isinstance(x.get("source"), str) and "value" in x for x in src["seen"]):
            raise Malformed(f"{path}: {key} needs source (a string or null), conflict (true or false) and seen")
        value = get(candidate, key)
        if src["conflict"] and len(src["seen"]) < 2:
            raise Malformed(f"{path}: {key}'s sources disagree, but it lists {len(src['seen'])} of them")
        if src["conflict"] and value != NR:
            raise Malformed(f"{path}: {key}'s sources disagree, but the candidate records {value!r}")
        if (value == NR) != (src["source"] is None):
            raise Malformed(f"{path}: {key} reads {profile.render(value)!r} in the candidate, but its source is {src['source']!r}")
    files = data["files"]
    for name, f in files.items():
        if not isinstance(f, dict) or f.get("loads") not in ("script", "on demand", "always") or not isinstance(f.get("chars"), int):
            raise Malformed(f"{path}: files.{name} needs loads (script, on demand or always) and chars")
    named = [src["source"] for src in keys.values() if src["source"] is not None]
    named += [x["source"] for src in keys.values() for x in src["seen"]]
    unlisted = sorted({n for n in named if n not in files})
    if unlisted:
        raise Malformed(f"{path}: {', '.join(unlisted)} is a source with no entry in files")
    start = data["session_start"]
    if not isinstance(start.get("files"), list) or not all(isinstance(n, str) and n in files for n in start["files"]) \
            or not isinstance(start.get("chars"), int):
        raise Malformed(f"{path}: session_start needs files, each one in files, and chars")
    total = sum(files[n]["chars"] for n in start["files"])
    if start["chars"] != total:
        raise Malformed(f"{path}: session_start.chars is {start['chars']}, but its files hold {total}")
    return data


def tier_of(source: str | None) -> str:
    """The tier of one place a value came from; a value inferred from a file is derived."""
    path = (source or "").split(" (")[0]
    if path in ("history", "GitHub", "git", "clones") or (source or "").endswith(" (inferred)"):
        return "derived"
    if path in survey.INSTRUCTIONS or path.startswith(AGENT_DIRS):
        return "agent file"
    return "human file"


def tiers(row: dict, src: dict) -> str:
    if row["cls"] == "asked":
        return "person"
    if row["cls"] == "conflict":
        return ", ".join(dict.fromkeys(tier_of(s["source"]) for s in src["seen"]))
    if row["candidate_source"]:
        return tier_of(row["candidate_source"])
    return "plugin store" if row["plugin"] != NR else "-"


def cost(source: str, files: dict) -> str:
    f = files.get(source, {})
    how = f.get("loads", "-")
    return f"{how} ~{f.get('chars', 0) // 4} tok" if how in ("on demand", "always") else how


def loads_of(row: dict, src: dict, files: dict) -> str:
    if row["cls"] == "asked":
        return "script"
    if row["cls"] == "conflict":
        return ", ".join(dict.fromkeys(cost(s["source"], files) for s in src["seen"]))
    if row["candidate_source"]:
        return cost(row["candidate_source"], files)
    return "script" if row["plugin"] != NR else "-"


def note_for(key: str, plugin, source: dict, set_here: bool) -> str:
    """Whether a repository file the survey read states the plugin's value, or none does. A value the
    repository's own settings do not set is no copy of the repository's, so it is never called stale."""
    stated = [s["source"] for s in source["seen"] if same(key, s["value"], plugin)]
    if stated:
        return f"{stated[0]} states the plugin's value"
    from_file = source["conflict"] or tier_of(source["source"]) in ("agent file", "human file")
    if set_here and from_file and source["seen"] and plugin not in (NR, ""):
        return "no file the survey read states the plugin's value: likely stale"
    return ""


def without_profile(repo: str, root: Path, project: dict, sources: list[str]) -> dict:
    """What the plugin resolves for the repository without its own settings: the default profile
    under the standard's `project` settings, and their rules for the repository, such as its private
    list; what a drop-in profile resolves to for every key it leaves out."""
    return profile.resolve_here(repo, root, mine=lambda: (project, sources[:1], None))


def score(candidate: dict, sources: dict, answers: dict, repo: str, root: Path, files: dict) -> list[dict]:
    plugin = profile.resolve(repo, root, detect=False)
    values, read, elsewhere = profile.local(repo, profile.owners(repo))
    # A standard of the repository's own with no profiles/ covers it alone, so every key it sets is
    # the repository's own.
    single = elsewhere is None and bool(read) and not (Path(profile.git("rev-parse", "--show-toplevel") or ".") / "standards/profiles").is_dir()
    project = {} if single else {k: v for k, v in values.items() if k in profile.PROJECT_KEYS}
    own = {k: v for k, v in values.items() if k not in project}
    team = without_profile(repo, root, project, read)
    out = []
    for key in survey.LEAVES:
        src = sources[key]
        today = get(plugin, key)
        top, _, sub = key.partition(".")
        set_here = top in own and (not sub or not isinstance(own[top], dict) or sub in own[top])
        row = {"key": key, "candidate": get(candidate, key), "candidate_source": src["source"],
               "plugin": today, "plugin_source": read[-1] if set_here else read[0] if top in project else profile.DEFAULT_PROFILE,
               "covers": None, "note": ""}
        if key in answers:
            value = answers[key]["value"]
            row.update(cls=answers[key]["how"], answer=value,
                       note="the plugin's value" if same(key, value, today) else "not the plugin's value")
        elif row["candidate"] == NR:
            value = None
            if src["conflict"]:
                row.update(cls="conflict", note=note_for(key, today, src, set_here) or "the plugin's value is none of them")
            elif today != NR and same(key, get(team, key), today):
                row.update(cls="project default", note="what the plugin resolves without the repository's own settings, which a drop-in keeps")
            else:
                kept = [x["source"] for x in src["seen"]]
                row.update(cls="missing", note=f"{kept[0]} is held, matching no template of the standard" if key == "template" and kept
                           else "the plugin records none either" if today == NR else "")
        else:
            value = row["candidate"]
            row["cls"] = "match" if same(key, value, today) else "differs"
            if row["cls"] == "differs":
                row["note"] = "the plugin records none" if today == NR else note_for(key, today, src, set_here)
            if (src["source"] or "").endswith(" (inferred)") and not row["note"]:
                origin = src['source'][:-len(' (inferred)')]
                row["note"] = f"inferred from {origin}"
        if key in PROPOSALS and isinstance(value, list) and isinstance(today, list):
            row["covers"] = items(today) <= items(value)
            extra = len(items(value) - items(today))
            if row["covers"] and extra and row["cls"] == "differs":
                row["note"] = f"covers the plugin's, with {extra} more for the person to trim"
            elif not row["covers"]:
                short = len(items(today) - items(value))
                row["note"] = f"leaves out {short} of the plugin's values"
        row["tier"] = tiers(row, src)
        row["loads"] = loads_of(row, src, files)
        out.append(row)
    return out


def table(repo: str, rows: list[dict], start: dict | None = None) -> str:
    counts = Counter(r["cls"] for r in rows)
    order = ("match", "project default", "differs", "conflict", "missing", "asked", "confirmed")
    head = f"roundtrip: {repo} · {len(rows)} keys · " + " · ".join(f"{c} {counts[c]}" for c in order if counts[c])
    lines = [head, HEADER]
    for r in rows:
        mine = r.get("answer", r["candidate"])
        onboarding = survey.short(profile.render(mine)) + (f" ({r['candidate_source']})" if r["candidate_source"] and "answer" not in r else "")
        today = f"{survey.short(profile.render(r['plugin'])) or chr(39) * 2} ({r['plugin_source']})"
        covers = "-" if r["covers"] is None else ("yes" if r["covers"] else "no")
        lines.append(" | ".join((r["key"], r["cls"], r["tier"], r["loads"], onboarding, today, covers, r["note"] or "-")))
    by_tier = Counter(r["tier"].split(", ")[0] for r in rows)
    tier_order = ("derived", "agent file", "human file", "plugin store", "person", "-")
    lines.append("tiers: " + " · ".join(f"{t} {by_tier[t]}" for t in tier_order if by_tier[t]))
    if start is not None:
        loaded = ", ".join(start["files"]) or "none"
        lines.append(f"session start: ~{start['chars'] // 4} tokens (characters / 4) from {loaded}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("candidate", type=Path, help="the candidate profile survey.py --profile wrote")
    p.add_argument("--sources", type=Path, help="its sources file; default, <candidate stem>.sources.json beside it")
    p.add_argument("--answers", type=Path, help="the person's answers, asked or confirmed, by key")
    p.add_argument("--root", type=Path, default=TOP, help="the plugin's top level")
    p.add_argument("--json", action="store_true", help="the rows as a JSON list")
    args = p.parse_args(argv)
    try:
        try:
            candidate = profile.parse(args.candidate.read_text(), str(args.candidate))
            profile.check(candidate, str(args.candidate))
        except (OSError, profile.ProfileError) as e:
            raise Malformed(str(e)) from e
        missing = [k for k in survey.LEAVES if not held(candidate, k)]
        if missing:
            raise Malformed(f"{args.candidate}: leaves out {', '.join(missing)}; a candidate holds every key")
        sources = sources_of(args.sources or args.candidate.with_name(f"{args.candidate.stem}.sources.json"), candidate)
        repo = sources["repo"]
        answers = answers_of(args.answers, candidate)
        rows = score(candidate, sources["keys"], answers, repo, args.root.resolve(), sources["files"])
    except (Malformed, profile.ProfileError, OSError) as e:
        print(f"onboard_roundtrip.py: {e}", file=sys.stderr)
        return 1
    print(json.dumps(rows, indent=1) if args.json else table(repo, rows, sources["session_start"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
