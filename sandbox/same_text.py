#!/usr/bin/env python3
"""Compare the text the model received in two variants' runs of one scenario: the check that a
change moved a value without changing what any skill or agent is handed, after `same_output.py`
has shown the scripts print the same, and the one that sees what loads and when.

Each run's transcripts, the main session's and every subagent's, are read from Claude Code's
project directory, and every piece of text the model received is keyed by what it is, per agent
type: the system prompt and each tool's definition, from the recorded request shapes; each skill
body, preloaded or invoked; each system reminder, by its first line; each attachment; and each
tool result, by the tool and its input. Left out: text a model wrote (a subagent's prompt, its
hand-back, a task notification, the session's own messages), an MCP server's tool definitions,
which list a default in a different order each session, and the budget and token counters. The
plugin's and the sandbox's paths, ids, timestamps, file listing dates, hook durations, a commit at
the start of a git log line, which a scenario's setup makes afresh each run, and the arguments the
model gives a skill it invokes are normalized.

A key both variants have is compared as the set of texts it carried across each variant's runs,
and a key only one has, such as a reminder, a preloaded skill or a tool only one variant was
given, counts too. Each difference fails unless the expected-changes file names it: one
`<key>: <why>` per line, split at the last `: `, so the reason holds none; a key with `*` or `?`
in it is a glob, and any other is matched exactly, so a key copied from the output names itself.
`#` starts a comment. An expected change that did not happen fails too.

What depends on the model's route is listed and never fails, since the route varies between
repeats: a tool result, a skill or command that arrives after the model's first turn, an agent
started or a hook fired on one side only, a server's data, what the SessionStart hook says, which
reports the state the route left and which `same_output.py` checks on fixed inputs, and the
notices Claude Code adds when the model edits a file, reads part of one or changes directory. A
skill or command that arrives before the model's first turn is a preload or the scenario's own,
and a hook that fired on both sides, keyed by its name and command, is compared. Claude Code also
turns some of its own tools on and off between sessions; a tool only one variant was given fails,
and when the change touches no agent's `tools:` line, the expected file names it.

    sandbox/same_text.py work --sandbox ~/sbx/1002 --base baseline --head my-change
    sandbox/same_text.py work --base baseline --head my-change --expected sandbox/expected/<change>.txt

Run the two variants the same day on the same Claude Code version. The request records are Claude
Code's internal format: a transcript without them or their shapes, an entry missing a field this
reads, and a session that started more agents than it has subagent transcripts are refused rather
than compared on less. Exits 0 when every difference is expected, 1 otherwise.
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

DROP = re.compile(r"^(<total_tokens>|USD budget:|The user hasn't heard from you|The following deferred tools are now available)")
DROP_REMINDER = re.compile(r"^\[SYSTEM NOTIFICATION")
ROUTE_ATTACHMENTS = {"edited_text_file", "read_truncation_notice", "silent_turn_reminder"}
CHANGED_ON_DISK = re.compile(r"^Note: \S+ changed on disk since")
SPLIT = re.compile(r"\n+(?=Note: \S+ changed on disk since|# Environment update)")
DROP_ATTACHMENTS = {"budget_usd", "total_tokens_reminder", "prompt_snapshot", "date", "deferred_tools_record", "deferred_tools_delta"}
NORMALIZE = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<uuid>"),
    (re.compile(r"\btoolu_[A-Za-z0-9]+"), "<tool-use>"),
    (re.compile(r"\bagent-?a[0-9a-f]{16}\b"), "<agent>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z?"), "<time>"),
    (re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) +\d{1,2} +\d{1,2}:\d{2}\b"), "<date>"),
    (re.compile(r"<total_tokens>\d+ tokens left</total_tokens>"), "<total_tokens>"),
    (re.compile(r"(?m)^(?=[0-9a-f]*\d)[0-9a-f]{7,40}(?= )"), "<sha>"),
    (re.compile(r"(?m)^ARGUMENTS: .*$"), "ARGUMENTS: <args>"),
    (re.compile(r"USD budget: \$[\d.]+/\$[\d.]+; \$[\d.]+ remaining"), "<budget>"),
]
PLUGIN_PATH = re.compile(r"(/[^\s\"'`()<>:]+?)/(?:skills|agents|hooks|scripts|standards|teams)/")


def transcripts(run: Path) -> list[tuple[str, Path]]:
    """The run's transcript files as (agent, path): the main session's, then each subagent's by
    its agent type."""
    sessions, cwd = [], None
    for line in (run / "stream.jsonl").read_text().split("\n"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            cwd = cwd or event["cwd"]
            if event["session_id"] not in sessions:
                sessions.append(event["session_id"])
    if not sessions:
        raise SystemExit(f"same_text.py: {run}/stream.jsonl has no init event")
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    project = home / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd)
    files = []
    for session in sessions:
        main = project / f"{session}.jsonl"
        if not main.exists():
            raise SystemExit(f"same_text.py: no transcript {main}")
        subagents = sorted((project / session / "subagents").glob("agent-*.jsonl"))
        started = sum(agent_starts(path) for path in [main, *subagents])
        if started > len(subagents):
            raise SystemExit(f"same_text.py: session {session} started {started} agent(s) and has {len(subagents)} subagent transcript(s)")
        files.append(("main", main))
        for path in subagents:
            files.append((json.loads(path.with_suffix(".meta.json").read_text())["agentType"], path))
    return files


def jsonl(path: Path) -> list[dict]:
    """A JSONL file's entries, split on newlines only: `str.splitlines` also splits on characters
    JSON leaves raw inside a string, such as U+2028 among the bytes of a binary file a tool read."""
    return [json.loads(line) for line in path.read_text().split("\n") if line.strip()]


def agent_starts(path: Path) -> int:
    """How many agents a transcript's model started: its Agent and Task calls, less those that came
    back as an error, which start none."""
    calls, failed = set(), set()
    for entry in jsonl(path):
        for b in blocks(entry.get("message", {}).get("content", [])) if entry.get("type") in ("assistant", "user") else []:
            if b.get("type") == "tool_use" and b["name"] in ("Agent", "Task"):
                calls.add(b["id"])
            elif b.get("type") == "tool_result" and b.get("is_error"):
                failed.add(b["tool_use_id"])
    return len(calls - failed)


def plugin_roots(texts: list[str]) -> set[str]:
    """Every path in the run's text that is a plugin checkout, found by its manifest on disk."""
    roots = set()
    for text in texts:
        for match in PLUGIN_PATH.finditer(text):
            root = match.group(1)
            while root not in roots and root != "/" and not Path(root, ".claude-plugin", "plugin.json").exists():
                root = str(Path(root).parent)
            if root != "/":
                roots.add(root)
    return roots


def blocks(content) -> list[dict]:
    return content if isinstance(content, list) else [{"type": "text", "text": content}]


def flatten(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", json.dumps(b, sort_keys=True)) for b in content if b.get("type") != "image")


def text_key(text: str) -> str | None:
    """What a text block is, or None for one that is dropped."""
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    if DROP.match(first) or not first:
        return None
    if CHANGED_ON_DISK.match(first) or first.startswith(("[Truncated", "# Environment update")):
        return "notice:" + re.sub(r"\d+", "N", first)[:70]
    if first.startswith("Base directory for this skill:"):
        return "skill:" + first.rstrip("/").rsplit("/", 1)[-1]
    if first.startswith("<command-message>"):
        return "command:" + re.sub(r"</?command-message>", "", first)
    if first.startswith("<system-reminder>"):
        body = text.lstrip()[len("<system-reminder>"):].lstrip().splitlines()
        if body and DROP_REMINDER.match(body[0]):
            return None
        return "reminder:" + re.sub(r"\d+", "N", body[0] if body else "")[:70]
    return "text:" + re.sub(r"\d+", "N", first)[:70]


def add_text(items: list[tuple[str, str]], text: str, acted: bool, only: tuple[str, ...] = ()) -> None:
    """Key each part of a text block, keeping only the kinds `only` names when it names any. A
    skill or command that arrives after the model has acted is one it invoked; before, it is a
    preload or the scenario's own command."""
    for part in SPLIT.split(text):
        key = text_key(part)
        if key and (not only or key.startswith(only)):
            if part.startswith("SessionStart hook"):
                key = "notice:SessionStart hook"
            elif acted and key.startswith(("skill:", "command:")):
                key = "invoked-" + key
            items.append((key, part))


def extract(agent: str, path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """The (key, text) pairs one transcript file records the model receiving, and the Claude Code
    versions its request records name."""
    items, versions, uses, shapes, acted = [], set(), {}, 0, False
    for entry in jsonl(path):
        kind = entry.get("type")
        if kind == "api-request":
            versions.add(entry["version"])
        elif kind == "api-request-shape":
            shapes += 1
            for i, block in enumerate(entry["shape"]["system"]):
                items.append((f"system:{i}", block["text"]))
            for tool in entry["shape"]["tools"]:
                if not tool.get("name", "").startswith("mcp__"):
                    items.append((f"tool:{tool.get('name')}", json.dumps(tool, sort_keys=True)))
        elif kind == "api-request-blob":
            role = entry["message"]["role"]
            for block in blocks(entry["message"]["content"]):
                if block.get("type") == "text" and role in ("user", "system"):
                    add_text(items, block["text"], acted, () if role == "system" else ("reminder:", "skill:", "command:"))
        elif kind == "attachment":
            att = entry["attachment"]
            if att.get("type") not in DROP_ATTACHMENTS:
                att = {k: v for k, v in att.items() if k != "durationMs"}
                rendered = json.dumps(att, sort_keys=True, indent=1, ensure_ascii=False).replace("\\n", "\n")
                if att.get("hookEvent") == "SessionStart" or att.get("type") in ROUTE_ATTACHMENTS or (att.get("type") == "environment" and "changes" in att):
                    key = f"notice:{att.get('type')}"
                elif "hookEvent" in att:
                    key = f"hook:{att.get('hookName', att['hookEvent'])}:{att.get('command', '')}:{att.get('type')}"
                else:
                    key = f"attachment:{att.get('type')}"
                items.append((key, rendered))
        elif kind == "assistant":
            acted = True
            for block in blocks(entry["message"]["content"]):
                if block.get("type") == "tool_use":
                    uses[block["id"]] = (block["name"], block["input"])
        elif kind == "user":
            content = entry["message"]["content"]
            if not entry.get("isMeta") and not any(b.get("type") == "tool_result" for b in blocks(content)):
                if agent == "main" and not flatten(content).lstrip().startswith("<task-notification>"):
                    items.append(("prompt", flatten(content)))
                continue
            for block in blocks(content):
                if block.get("type") == "tool_result":
                    name, given = uses[block["tool_use_id"]]
                    if name == "Agent":
                        continue
                    shown = {k: v for k, v in given.items() if k not in ("description",)}
                    kind = "external" if name.startswith("mcp__") else "result"
                    items.append((f"{kind}:{name}:{json.dumps(shown, sort_keys=True)}", flatten(block.get("content", ""))))
                elif block.get("type") == "text":
                    add_text(items, block["text"], acted)
    if versions and not shapes:
        raise SystemExit(f"same_text.py: {path} records requests but no request shape; this Claude Code version's transcript is not one this script reads")
    return [(f"{agent} {k}", t) for k, t in items], sorted(versions)


def side(out: Path, variant: str, sandbox: Path) -> tuple[dict[str, set[str]], set[str], int]:
    runs = sorted((d for d in (out / variant).iterdir() if (d / "stream.jsonl").exists()), key=lambda d: d.name)
    if not runs:
        raise SystemExit(f"same_text.py: no runs under {out / variant}")
    texts: dict[str, set[str]] = {}
    versions: set[str] = set()
    for run in runs:
        pairs = []
        for agent, path in transcripts(run):
            got, v = extract(agent, path)
            if not v:
                raise SystemExit(f"same_text.py: {path} records no API requests; this Claude Code version's transcript is not one this script reads")
            pairs += got
            versions.update(v)
        roots = sorted(plugin_roots([t for _, t in pairs] + [k for k, _ in pairs]), key=len, reverse=True)
        subs = [(re.escape(r), "<plugin>") for r in roots] + [(re.escape(str(sandbox)), "<sandbox>")]

        def norm(s: str) -> str:
            for pattern, repl in subs:
                s = re.sub(pattern, repl, s)
            for pattern, repl in NORMALIZE:
                s = pattern.sub(repl, s)
            return s

        for key, text in pairs:
            texts.setdefault(norm(key), set()).add(norm(text))
    return texts, versions, len(runs)


def load_expected(path: Path | None) -> list[tuple[str, str]]:
    if not path:
        return []
    rules = []
    for raw in path.read_text().splitlines():
        line = "" if raw.lstrip().startswith("#") else raw.strip()
        if line:
            glob, _, why = line.rpartition(": ") if ": " in line else (line, "", "")
            rules.append((glob.strip(), why.strip()))
    return rules


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("scenario")
    p.add_argument("--sandbox", type=Path, default=Path.cwd(), help="the sandbox (default: the current directory)")
    p.add_argument("--base", default="baseline", help="the variant compared against (default baseline)")
    p.add_argument("--head", required=True, help="the variant with the change")
    p.add_argument("--expected", type=Path, help="the expected-changes file")
    p.add_argument("--dump", type=Path, help="write each variant's keyed texts here, one JSON file per variant")
    args = p.parse_args(argv)
    sandbox = args.sandbox.expanduser().resolve()
    out = sandbox / "runs" / args.scenario
    sides = {}
    for name in (args.base, args.head):
        sides[name] = side(out, name, sandbox)
        if args.dump:
            args.dump.mkdir(parents=True, exist_ok=True)
            (args.dump / f"{name}.json").write_text(json.dumps({k: sorted(v) for k, v in sorted(sides[name][0].items())}, indent=1))
    (a, va, na), (b, vb, nb) = sides[args.base], sides[args.head]
    if va != vb:
        print(f"same_text.py: the variants ran on different Claude Code versions ({', '.join(va)} and {', '.join(vb)}); run them the same day", file=sys.stderr)
        return 1
    rules = load_expected(args.expected)
    used, unexpected = set(), 0

    def judge(key: str, what: str) -> None:
        nonlocal unexpected
        match = next(((g, w) for g, w in rules if (fnmatch.fnmatchcase(key, g) if re.search(r"[*?]", g) else key == g)), None)
        if match:
            used.add(match[0])
        else:
            unexpected += 1
        print(f"--- {key}: {what}, {'expected (' + match[1] + ')' if match else 'UNEXPECTED'}")

    route = []
    for key in sorted(set(a) & set(b)):
        if a[key] == b[key]:
            continue
        if key.split(" ", 1)[1].startswith(("external:", "notice:")):
            route.append(f"differs: {key[:160]}")
            continue
        judge(key, "differs")
        x, y = "\n=====\n".join(sorted(a[key])), "\n=====\n".join(sorted(b[key]))
        diff = list(difflib.unified_diff(x.splitlines(), y.splitlines(), args.base, args.head, lineterm="", n=1))[2:60]
        print("\n".join("    " + line for line in diff))
    agents = {k.split(" ", 1)[0] for k in a} & {k.split(" ", 1)[0] for k in b}
    for name, keys in ((args.base, set(a) - set(b)), (args.head, set(b) - set(a))):
        for key in sorted(keys):
            agent, what = key.split(" ", 1)
            if agent not in agents or what.startswith(("result:", "external:", "invoked-skill:", "invoked-command:", "notice:", "hook:")):
                route.append(f"only in {name}: {key[:160]}")
            else:
                judge(key, f"only in {name}")
    if route:
        print(f"--- route differences, not compared ({len(route)}):")
        print("\n".join("    " + line for line in route))
    unused = [g for g, _ in rules if g not in used]
    for g in unused:
        print(f"--- expected change {g!r} did not happen")
    print(f"same_text.py: {args.scenario}, {na} run(s) of {args.base} and {nb} of {args.head} on Claude Code {', '.join(va)}; "
          f"{len(set(a) & set(b))} keys compared, {unexpected} unexpected difference(s), {len(used)} expected, "
          f"{len(unused)} expected but absent, {len(route)} route difference(s)")
    return 1 if unexpected or unused else 0


if __name__ == "__main__":
    raise SystemExit(main())
