#!/usr/bin/env python3
"""The usage-report scenarios' fixture: a Claude Code configuration directory of hand-labeled runs.

    usage_config.py make <dir> <plugin name>    write <dir> and the clone's .sbx-env, and note the clone's files
    usage_config.py issue <dir> <plugin name>   add the person's earlier usage-report issue, and a newer one by another login, to the GitHub stub's writes
    usage_config.py labels <dir>                exit 1 unless the report's after_run is the hand labels
    usage_config.py unsent <dir>                exit 1 when the run wrote a file in the clone
    usage_config.py counted <dir>               exit 1 unless a report exists and its skills' runs are the fixture's
    usage_config.py opened <dir>                exit 1 unless the report's window opens where the earlier issue's closed
    usage_config.py sent <file> <dir>           exit 1 unless <file> holds the report's bytes and the run wrote no other file

`make` writes one main transcript under `<dir>/projects/`, of twelve plugin skill runs typed a day
ago, each followed by a person's message whose outcome is plain (`RUNS`), or by none; two
personal skills and one personal agent, one skill and the agent doing a plugin skill's and agent's
job; and `<dir>/expected.json`, the after_run and overlap a correct run gives, and the files the
clone holds outside `.git`, `<dir>` and `.sbx-env`, each with its size and modification time. It
empties or makes `/tmp/usage-report-sbx-<12 hex digits of <dir>'s absolute path's sha256>`, a
temporary directory outside every repository that sandboxed Bash may write, and records it as `tmp`
in `expected.json`. It writes `.sbx-env` in the working directory, the clone, exporting
`CLAUDE_CONFIG_DIR=<dir>` and `TMPDIR=<tmp>` for the session's Bash commands (sandbox/sbx-claude),
so the skill's run directory, which it makes under `$TMPDIR`, is `<tmp>/<one directory>/`, holding
`payload.json`. A check that finds no such directory, or more than one, exits 1.

`issue` appends to `.git/github-writes.jsonl` two `issue_write` creates the stub replays at start,
each a `usage-report` issue whose body is a report in a `json` fence and whose author and creation
time are `seeded`: first the person's (`PERSON`, the stub's `get_me` login), created when its window
ends two days ago, that end recorded as `since` in `<dir>/expected.json`; then one by another login,
created when its window ends a day ago, so it is the highest numbered, the newest and, newest
first, listed first. Run from the clone, as a scenario's setup and verify run.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Each run: the skill typed, the person's next message (None: the next skill starts first, or the
# session ends) and its hand label.
RUNS = [
    ("work", "Looks good, go ahead.", "approve"),
    ("commit", "Yes, commit it, thanks.", "approve"),
    ("pr-review", "No, finding 2 is wrong: that function is tested in test_inventory.py.", "correct"),
    ("ticket-draft", "Make it shorter; the change is one line.", "correct"),
    ("work", "What did the test run report?", "status"),
    ("pr-review", "Which files did the review read?", "status"),
    ("commit", "Something else now: how does the CSV loader handle quoted fields?", "new_task"),
    ("ticket-draft", "Unrelated question: what does the restock script do on a holiday?", "new_task"),
    ("work", "Stop, don't run that.", "interrupt"),
    ("pr-review", "Wait, cancel this.", "interrupt"),
    ("commit", None, "none"),
    ("quickstart", None, "none"),
]
PERSON = "sbx-person"
PERSONAL_SKILLS = {
    "review-my-pr": "Reviews a GitHub pull request and lists the problems it finds, file by file.",
    "grocery-list": "Keeps the weekly grocery list and sorts it by aisle.",
}
PERSONAL_AGENTS = {"run-tests": "Runs the project's test suite and summarizes the failures."}
EXPECTED_OVERLAP = {"skills": {"pr-review": 1}, "agents": {"test-runner": 1}}


def expected_after_run() -> dict:
    out: dict = {}
    for skill, _, label in RUNS:
        out.setdefault(skill, {}).setdefault(label, 0)
        out[skill][label] += 1
    return out


def make(directory: Path, plugin: str) -> None:
    start = datetime.now(timezone.utc) - timedelta(days=1)
    entries = []

    def add(entry: dict) -> None:
        stamp = (start + timedelta(seconds=len(entries))).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        entries.append({**entry, "timestamp": stamp, "uuid": uuid.uuid4().hex, "version": "2.1.300", "cwd": "/nonexistent/widgets"})

    for skill, message, _ in RUNS:
        add({"type": "user", "message": {"role": "user", "content": f"<command-name>/{plugin}:{skill}</command-name>"}})
        if message:
            add({"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": message}})
    project = directory / "projects" / "-fixture"
    project.mkdir(parents=True, exist_ok=True)
    (project / "session.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    for name, description in PERSONAL_SKILLS.items():
        (directory / "skills" / name).mkdir(parents=True, exist_ok=True)
        (directory / "skills" / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\nDo it.\n")
    (directory / "agents").mkdir(parents=True, exist_ok=True)
    for name, description in PERSONAL_AGENTS.items():
        (directory / "agents" / f"{name}.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\nDo it.\n")
    tmp = Path("/tmp") / f"usage-report-sbx-{hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:12]}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    expected = {"after_run": expected_after_run(), "overlap": EXPECTED_OVERLAP, "files": files(directory), "tmp": str(tmp)}
    (directory / "expected.json").write_text(json.dumps(expected, indent=2) + "\n")
    Path(".sbx-env").write_text(f"export CLAUDE_CONFIG_DIR='{directory.resolve()}'\nexport TMPDIR='{tmp}'\n")


def files(directory: Path) -> dict:
    """The clone's files outside `.git`, `directory` and `.sbx-env`, each as [size, modification time in ns]."""
    out = {}
    for path in Path(".").rglob("*"):
        if path.parts[0] in (".git", ".sbx-env") or path.resolve().is_relative_to(directory.resolve()) or not path.is_file():
            continue
        out[str(path)] = [path.stat().st_size, path.stat().st_mtime_ns]
    return out


def stamp(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def create(plugin: str, start: str, end: str) -> dict:
    report = json.dumps({"schema": 1, "window": {"end": end, "start": start}}, indent=2, sort_keys=True) + "\n"
    body = f"```json\n{report}```\n`sha256:{hashlib.sha256(report.encode()).hexdigest()}`\nFiled with /{plugin}:usage-report.\n"
    return {"method": "create", "owner": "owner", "repo": "repo", "title": f"usage-report: {start[:10]} to {end[:10]}", "body": body,
            "labels": ["usage-report"]}


def issue(directory: Path, plugin: str) -> None:
    end = stamp(2)
    with Path(".git/github-writes.jsonl").open("a") as f:
        f.write(json.dumps({"tool": "issue_write", "arguments": create(plugin, stamp(32), end),
                            "seeded": {"login": PERSON, "created_at": end}}) + "\n")
        f.write(json.dumps({"tool": "issue_write", "arguments": create(plugin, stamp(31), stamp(1)),
                            "seeded": {"login": "another-filer", "created_at": stamp(1)}}) + "\n")
    expected = json.loads((directory / "expected.json").read_text())
    (directory / "expected.json").write_text(json.dumps({**expected, "since": end}, indent=2) + "\n")


def run_dir(tmp: Path) -> Path:
    found = sorted(tmp.glob("*/payload.json"))
    if len(found) != 1:
        raise SystemExit(f"{len(found)} run directories with a payload.json under {tmp}, not one")
    return found[0].parent


def written(directory: Path, before: dict) -> list:
    """The clone's files that appeared or changed since `make`, and those it removed."""
    now = files(directory)
    return sorted({p for p in now if before.get(p) != now[p]} | (set(before) - set(now)))


def main(argv: list[str]) -> int:
    arity = {"make": 3, "issue": 3, "labels": 2, "unsent": 2, "counted": 2, "opened": 2, "sent": 3}
    if not argv or arity.get(argv[0]) != len(argv):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    command = argv[0]
    if command == "make":
        make(Path(argv[1]), argv[2])
        return 0
    if command == "issue":
        issue(Path(argv[1]), argv[2])
        return 0
    directory = Path(argv[-1])
    expected = json.loads((directory / "expected.json").read_text())
    if command == "unsent":
        changed = written(directory, expected["files"])
        if changed:
            print(f"the run wrote or removed {changed} in the clone", file=sys.stderr)
            return 1
        return 0
    payload_path = run_dir(Path(expected["tmp"])) / "payload.json"
    payload = json.loads(payload_path.read_text())
    if command == "counted":
        runs = {skill: [s for s, _, _ in RUNS].count(skill) for skill, _, _ in RUNS}
        got = {k: v.get("runs") for k, v in payload["skills"].items()}
        if got != runs:
            print(f"the report's runs per skill are {got}, the fixture's {runs}", file=sys.stderr)
            return 1
        return 0
    if command == "labels":
        if payload["after_run"] != expected["after_run"]:
            print(f"after_run is {json.dumps(payload['after_run'], sort_keys=True)}, the hand labels "
                  f"{json.dumps(expected['after_run'], sort_keys=True)}", file=sys.stderr)
            return 1
        return 0
    if command == "opened":
        if payload["window"]["start"] != expected["since"]:
            print(f"the window opens at {payload['window']['start']}, not the earlier issue's end {expected['since']}", file=sys.stderr)
            return 1
        return 0
    copy = Path(argv[1])
    if not copy.is_file() or copy.read_bytes() != payload_path.read_bytes():
        print(f"{copy} does not hold the bytes of {payload_path}", file=sys.stderr)
        return 1
    others = [p for p in written(directory, expected["files"]) if Path(p) != copy]
    if others:
        print(f"the run also wrote or removed {others} in the clone", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
