#!/usr/bin/env python3
"""Run one scenario from a scenario file in a sandbox, repeat it, and report what happened.

    sandbox/run.py [--scenarios FILE] --list
    sandbox/run.py <scenario> [--scenarios FILE] [--variant DIR] [--repeat N] [--model M] [--budget USD]
        [--sandbox DIR] [--check] [--judge RUBRIC] [--no-wait] [--reuse]
    sandbox/run.py compare <scenario> [--sandbox DIR]

The scenario file is `scenarios.yaml` beside this script unless --scenarios names another, such as
a project's own scenario pack kept outside the plugin; its fixtures are the `fixture/` directory
beside it, which setup and verify commands read as `$SBX_FIXTURES`.

A run resets both sandbox clones to their pins, runs the scenario's setup, then its turns in one
session through `sbx-claude`, the second and later resuming the first, and stops at the first
turn that does not end in success, then runs its verify commands, recording each that fails. Run
<n> of a variant goes to <sandbox>/runs/<scenario>/<variant>/<n>/: `stream.jsonl`, `final.md` (the
last message) and `summary.json`, the facts every reader below works from. Running a variant
again replaces its runs.

Each summary records its run's key, taken after the run's reset: digests of the scenario, of the
harness files that shape a run (this script, `sbx-claude`, `settings.template.json` and
the scenario file's `fixture/`), of the sandbox (its pins, `mcp.json` and each bare remote's `main`), of the
environment variables that change a session (`ANTHROPIC_*`, `CLAUDE_CODE_*` and
`MAX_THINKING_TOKENS`, but no credential or the calling Claude Code process's own identity), the
plugin's git tree, the model, the per-turn budget and `claude --version`. A plugin checkout with uncommitted changes, untracked files included,
has no key. With --reuse, run <n> of the variant is taken from a recorded run of the scenario, any
variant's, with the same key, started in the last 24 hours and reaching a result event, newest
first and each run once however many copies hold it, and only the runs still short of --repeat
are made; when none is taken, run.py says why in one line. Each taken run is copied in, marked
`reused` with `taken`, the time this call took it, and checked and judged again as this call asks;
it keeps its first run's `plugin` commit, whose tree is the same, `run_id` and `started`. Two variants
whose plugins share a tree therefore share runs. With --reuse on a clean plugin, a summary under
the scenario's runs that is not a JSON object, or one with this key but no `run_id` or `started`,
stops run.py.

One run.py at a time holds a sandbox: every run resets all its clones and rewrites its
settings.json, so two at once would undo each other's setup. A second one waits for
<sandbox>/run.lock, saying once whose run it waits for, and with --no-wait stops at once, naming it,
with exit 75. Each child run.py starts (setup and verify commands, the session, the judge) runs in
its own process group, and Ctrl-C, SIGTERM or SIGHUP to run.py stops that group before the lock is
released, so no session outlives the run that holds the sandbox.

--variant is another checkout of the plugin, such as a git worktree of a branch with a changed
skill, loaded as the plugin directory in place of the sandbox's clone and named for its
directory; the clone at its pin is the variant `baseline`. A variant whose `plugin.json` names it other than
`lasp-dev`, such as an export, runs each scenario with every `lasp-dev` in it renamed to
that name, so its commands, rules and state paths are the ones that plugin answers to. An export
names its own repository and leaves some paths out, so against the clone a difference can include
that absence. --budget caps each turn, in dollars.

The report, printed and written to <sandbox>/runs/<scenario>/report.md, is one row per run, then
the scenario's `look_at`, then each run's last message. --check adds a column holding each run's
summary to the scenario's `expect` block, `must_not_run` and `verify`, and exits 1 when any run
fails it. `expect`'s `never_anywhere` lists canary strings a run must carry nowhere: not in any
reply text or tool input of the main session, in any turn, nor in a file the run changed or made
or a commit it added, checked at the end of each turn; with `through_turn: N` beside its `tokens`,
only turns 1 to N are held to it, for a scenario whose later turn is cleared to use them. What the
model read, the tool results, is not checked, nor a subagent's own calls, which the main stream
does not hold; what a subagent wrote to a file is.
--judge runs one more Sonnet turn per run, with no tools, in the run's directory rather than a
sandbox repository, given the rubric, the last message and `summary.json`, and records its score
from 0 to 10 and one sentence in `summary.json`, the report and the comparison. A reply that is
not a score and a sentence stops run.py. `compare` tabulates every variant's runs of a scenario, each metric as its mean and range over
the repeats, then the last messages, into <sandbox>/runs/<scenario>/compare.md.

The settings each session runs under are written to <sandbox>/settings.json from
`settings.template.json`: a rule naming `{github}` or `{atlassian}` once per server of that kind
in <sandbox>/mcp.json, the kind told by what the server is, not by its name: GitHub's when its
`url`'s host is `api.githubcopilot.com` or its command or an argument names `github-mcp-server`,
Atlassian's when its command or an argument names `mcp-atlassian`, the test `sandbox.sh` applies
before it forces the server read-only. An Atlassian server without `--read-only` and
`READ_ONLY_MODE=true`, which `sandbox.sh` sets, stops run.py, since its rules allow every tool. A
server of neither kind gets no rule, so under `dontAsk` every call to it is refused. `{sandbox}` and `{plugin}` are repeated once per spelling of the sandbox's path and the
plugin directory's, so file and shell rules stay inside them. Its `sandbox` block is copied as it
stands: Bash runs in Claude Code's sandbox, which allows it without a rule. `claudeMdExcludes`
lists every `CLAUDE.md`, `AGENTS.md` and rules file above the sandbox and the person's own, and
`autoMemoryEnabled` is off, so a session, the judge's included, reads the repository's
instructions and no one's personal ones or an earlier run's memory.

A scenario file names a planted fake credential by placeholder, `{fake_github_token}` or
`{fake_anthropic_key}`, which run.py replaces with the full string when it reads the file, so no
tracked file holds one a secret scanner would flag.

Needs PyYAML (`python3 -m pip install pyyaml`).
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    sys.exit("run.py needs PyYAML: python3 -m pip install pyyaml")

HERE = Path(__file__).resolve().parent
BASELINE = "baseline"
PLUGIN = "lasp-dev"  # the name the scenarios are written for
LOCK = "run.lock"
BUSY = 75  # EX_TEMPFAIL: the sandbox is held and --no-wait was given
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")
METRICS = ("cost_usd", "turns", "seconds", "agents", "files", "must_not_run", "ticket_words", "pr_words")
JUDGE_MODEL, JUDGE_BUDGET_USD = "sonnet", 0.5
HARNESS = ("run.py", "sbx-claude", "settings.template.json")
SESSION_ENV = re.compile(r"(ANTHROPIC_|CLAUDE_CODE_)\w*|MAX_THINKING_TOKENS")
# Credentials, and the identity of the Claude Code process run.py was started from, which differs
# in every session and would keep any two calls' keys apart.
UNKEYED_ENV = re.compile(r"SESSION|SOCKET|EXECPATH|ENTRYPOINT|SSE_PORT|PID|PASSPHRASE|(KEY|TOKEN)$|^ANTHROPIC_CUSTOM_HEADERS$")
REUSE_HOURS = 24  # the README's "run both variants the same day": live scenarios read that day's servers
SCENARIOS = None  # --scenarios; None is scenarios.yaml beside this script
# Joined here so no tracked file holds a whole credential-shaped string.
FAKES = {"fake_github_token": "gh" + "p_SandboxFakeToken0123456789abcdefABCDEF",
         "fake_anthropic_key": "sk-" + "ant-api03-SandboxFakeKey0123456789abcdefABCDEF"}


def child(cmd, check: bool = False, capture_output: bool = False, **kw) -> subprocess.CompletedProcess:
    """subprocess.run in a process group of its own, stopped whole before an exception leaves: a
    session that outlived run.py would write into a sandbox the next run has already reset."""
    if capture_output:
        kw.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with subprocess.Popen(cmd, start_new_session=True, **kw) as proc:
        try:
            out, err = proc.communicate()
        except BaseException:
            stop_group(proc)
            raise
    done = subprocess.CompletedProcess(proc.args, proc.returncode, out, err)
    if check:
        done.check_returncode()
    return done


def stop_group(proc: subprocess.Popen) -> None:
    """SIGTERM to the child's process group, then SIGKILL if it is still there after 10 s."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


def stopping(signum, frame) -> None:
    """SIGTERM and SIGHUP end run.py through its `finally` blocks, as Ctrl-C does, not around them."""
    raise SystemExit(128 + signum)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def scenario_file() -> Path:
    return SCENARIOS or HERE / "scenarios.yaml"


def fixture_dir() -> Path:
    """The scenario file's fixtures, which setup and verify commands read as $SBX_FIXTURES."""
    return scenario_file().parent / "fixture"


def scenarios() -> dict[str, dict]:
    text = scenario_file().read_text()
    for name, value in FAKES.items():
        text = text.replace("{" + name + "}", value)
    if unknown := re.search(r"\{fake_\w+\}", text):
        raise SystemExit(f"run.py: {scenario_file()} names {unknown.group()}, which is not a planted fake: {', '.join(FAKES)}")
    return {s["id"]: s for s in yaml.safe_load(text)["scenarios"]}


def for_plugin(node: object, name: str) -> object:
    """A scenario as written for a plugin named `name`: every `lasp-dev` in its strings, the
    command prefix, a rule's `Skill(lasp-dev:...)` and the state the plugin keeps under its
    name (`lasp-dev.standard`, `.git/lasp-dev/`, `refs/lasp-dev/`), renamed."""
    if isinstance(node, dict):
        return {k: for_plugin(v, name) for k, v in node.items()}
    if isinstance(node, list):
        return [for_plugin(v, name) for v in node]
    return node.replace(PLUGIN, name) if isinstance(node, str) else node


def pins(sandbox: Path) -> dict[str, tuple[str, str]]:
    """Each sandbox repository's pinned commit and branch, from sandbox.sh's pins file."""
    out = {}
    for line in (sandbox / "pins").read_text().splitlines():
        name, sha, branch = line.split()
        out[name] = (sha, branch)
    return out


def find_sandbox(start: Path) -> Path:
    """The sandbox holding `start`: the nearest directory at or above it with a pins file."""
    for d in (start, *start.parents):
        if (d / "pins").is_file():
            return d
    raise SystemExit(f"run.py: {start} is not inside a sandbox; give --sandbox")


def spellings(path: Path) -> list[str]:
    """A path as given and with symlinks resolved (macOS's /var is /private/var), without the
    leading slash the rule syntax adds."""
    return list(dict.fromkeys(str(x).lstrip("/") for x in (path.absolute(), path.resolve())))


INSTRUCTION_FILES = ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md", ".claude/rules/**", "AGENTS.md", ".claude/AGENTS.md")


def outside_instructions(sandbox: Path) -> list[str]:
    """Every instruction file Claude Code would load from outside the sandbox: each ancestor
    directory's, which it reads as the project's whatever `--setting-sources` says, AGENTS.md
    included, which it reads in place of a CLAUDE.md a repository lacks, and the person's own.
    The patterns are globs, so a sandbox path with a glob character in it is refused."""
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    paths = [str(config / "CLAUDE.md"), str(config / "rules" / "**")]
    for root in spellings(sandbox):
        if re.search(r"[*?\[\]{}()!]", root):
            raise SystemExit(f"run.py: the sandbox path /{root} has a glob character, so its instruction files cannot be excluded")
        for parent in Path("/" + root).parents:
            paths += [str(parent / name) for name in INSTRUCTION_FILES]
    return list(dict.fromkeys(paths))


def server_kind(server: dict) -> str | None:
    """`atlassian` for an mcp-atlassian command, by the test `sandbox.sh` applies before it forces
    the server read-only; `github` for a server at `api.githubcopilot.com` or a `github-mcp-server`
    command, its docker image or its binary; otherwise None."""
    words = [str(x) for x in [server.get("command"), *(server.get("args") or [])]]
    if any("mcp-atlassian" in w for w in words):
        return "atlassian"
    if urlparse(server.get("url") or "").hostname == "api.githubcopilot.com" or any("github-mcp-server" in w for w in words):
        return "github"
    return None


def write_settings(sandbox: Path, plugin: Path) -> None:
    """The template with each placeholder string repeated once per value, wherever it sits, every
    environment variable `mcp.json` reads added to the variables sandboxed commands lose, and every
    instruction file outside the sandbox excluded."""
    template = json.loads((HERE / "settings.template.json").read_text())
    mcp = (sandbox / "mcp.json").read_text()
    servers = json.loads(mcp)["mcpServers"]
    kinds = {name: server_kind(server) for name, server in servers.items()}
    for name, kind in kinds.items():
        server = servers[name]
        if kind == "atlassian" and ("--read-only" not in (server.get("args") or [])
                                    or (server.get("env") or {}).get("READ_ONLY_MODE") != "true"):
            raise SystemExit(f"run.py: the mcp-atlassian server {name} in mcp.json lacks --read-only or READ_ONLY_MODE=true; "
                             "rebuild the sandbox with sandbox.sh, which sets both")
    values = {"github": [n for n, k in kinds.items() if k == "github"], "atlassian": [n for n, k in kinds.items() if k == "atlassian"],
              "sandbox": spellings(sandbox), "plugin": spellings(plugin)}

    def expand(node):
        if isinstance(node, dict):
            return {k: expand(v) for k, v in node.items()}
        if isinstance(node, list):
            out = []
            for item in node:
                if not isinstance(item, str):
                    out.append(expand(item))
                    continue
                items = [item]
                for key, options in values.items():
                    if "{" + key + "}" in item:
                        items = [r.replace("{" + key + "}", v) for r in items for v in options]
                out += items
            return out
        return node

    settings = expand(template)
    env = settings["sandbox"]["credentials"]["envVars"]
    for name in sorted(set(re.findall(r"\$\{(\w+)\}", mcp)) - {e["name"] for e in env}):
        env.append({"name": name, "mode": "deny"})
    settings["claudeMdExcludes"] = outside_instructions(sandbox)
    (sandbox / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")


@contextlib.contextmanager
def holding(sandbox: Path, who: str, wait: bool):
    """The sandbox's run lock, an exclusive flock on <sandbox>/run.lock, released on any exit. The
    holder writes `who` into the file, so a run that finds it held can name the run it waits for."""
    with open(sandbox / LOCK, "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.seek(0)
            holder = f.read().strip() or "another run"
            if not wait:
                print(f"run.py: {sandbox} is in use by {holder}; run without --no-wait to wait for it, or use another sandbox",
                      file=sys.stderr, flush=True)
                raise SystemExit(BUSY)
            print(f"run.py: waiting for {holder}", file=sys.stderr, flush=True)
            fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        f.truncate()
        f.write(who + "\n")
        f.flush()
        try:
            yield
        finally:
            f.seek(0)
            f.truncate()
            f.flush()


def reset(sandbox: Path) -> None:
    """Both clones back to their pinned commits, with untracked and ignored files gone but .venv kept,
    origin fetching from the URL `sandbox.sh` gave it and kept as `sandbox.fetch`, and `main` and `origin/main` back at the `main`
    of the bare repository under remotes/, the source's `main` when the sandbox was built, which a
    scenario's setup may have moved."""
    for name, (sha, branch) in pins(sandbox).items():
        repo = sandbox / "repos" / name
        fetch = subprocess.run(["git", "-C", str(repo), "config", "--get", "sandbox.fetch"], capture_output=True, text=True).stdout.strip()
        if fetch:
            git(repo, "remote", "set-url", "origin", fetch)
        git(repo, "checkout", "-q", "-f", "-B", branch, sha)
        git(repo, "reset", "-q", "--hard", sha)
        git(repo, "clean", "-q", "-fdx", "-e", ".venv")
        main = git(sandbox / "remotes" / f"{name}.git", "rev-parse", "--verify", "refs/heads/main")
        git(repo, "update-ref", "refs/remotes/origin/main", main)
        if branch != "main":
            git(repo, "update-ref", "refs/heads/main", main)


def events(log: Path) -> list[dict]:
    out = []
    # Newlines only: str.splitlines also splits on characters JSON leaves raw inside a string.
    for line in log.read_text().split("\n"):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def results(evs: list[dict]) -> list[dict]:
    return [e for e in evs if e.get("type") == "result"]


def tool_uses(evs: list[dict]) -> list[dict]:
    return [c for e in evs if e.get("type") == "assistant" for c in e["message"].get("content", []) if c.get("type") == "tool_use"]


def argument(use: dict) -> str:
    i = use.get("input", {})
    return str(i.get("command") or i.get("skill") or i.get("file_path") or i.get("subagent_type") or "")


def matches(rule: str, use: dict) -> bool:
    """A permission-rule-shaped pattern, `Tool(arg glob)` or a tool-name glob, against one tool use.
    A Bash rule is tested against each command a compound one runs, split on `;`, `&&`, `||`, `|`
    and newlines, as Claude Code applies its deny rules, so `Bash(claude *)` catches
    `cd repo; claude plugin list`. The split ignores quoting."""
    m = re.fullmatch(r"(\w+)\((.*)\)", rule)
    if not m:
        return fnmatch.fnmatch(use["name"], rule)
    if use["name"] != m.group(1):
        return False
    parts = re.split(r"&&|\|\||[;|\n]", argument(use)) if use["name"] == "Bash" else [argument(use)]
    return any(fnmatch.fnmatch(part.strip(), m.group(2)) for part in parts)


def written(evs: list[dict], repo: Path, base: str) -> list[str]:
    """Files under the repository the run wrote and that exist at its end: the main session's
    undenied Edit and Write targets, the working tree's diff from `base`, and every untracked
    file, ignored ones included since `.review/` is ignored, outside .venv and Python caches.
    The reset before the run removed every untracked file but .venv, so each one is the run's."""
    denied = {d.get("tool_use_id") for r in results(evs) for d in r.get("permission_denials", [])}
    paths = set(git(repo, "diff", "--name-only", base).splitlines())
    for flags in (["--exclude-standard"], ["--ignored", "--exclude-standard"]):
        paths |= set(git(repo, "ls-files", "--others", *flags, "--", ".", ":!.venv", ":!**/__pycache__/**",
                         ":!.pytest_cache", ":!.ruff_cache").splitlines())
    for use in tool_uses(evs):
        target = Path(use.get("input", {}).get("file_path", "/")).resolve()
        if use["name"] in WRITE_TOOLS and use.get("id") not in denied and target.is_relative_to(repo):
            paths.add(str(target.relative_to(repo)))
    return sorted(p for p in paths if p and (repo / p).exists())


def canaries(scenario: dict) -> tuple[list[str], int | None]:
    """`expect.never_anywhere` as its tokens and the last turn held to it, None for every turn."""
    spec = scenario.get("expect", {}).get("never_anywhere", [])
    return (list(spec), None) if isinstance(spec, list) else (list(spec["tokens"]), spec.get("through_turn"))


def said_leaks(evs: list[dict], tokens: list[str]) -> list[tuple[int, str]]:
    """Each token in a main-session reply or tool input, with its turn: a turn ends at its result."""
    turn, out = 1, []
    for e in evs:
        if e.get("type") == "result":
            turn += 1
        elif e.get("type") == "assistant":
            for c in e["message"].get("content", []):
                if c.get("type") == "text":
                    text, where = c.get("text", ""), "a reply"
                elif c.get("type") == "tool_use":
                    text, where = json.dumps(c.get("input", {}), ensure_ascii=False), f"{c.get('name')}'s input"
                else:
                    continue
                out += [(turn, f"{token} in {where}, turn {turn}") for token in tokens if token in text]
    return out


def snapshot(repo: Path) -> dict[str, bytes]:
    """Every untracked file, ignored ones included, outside .venv and caches, as it stands."""
    paths = set()
    for flags in (["--exclude-standard"], ["--ignored", "--exclude-standard"]):
        paths |= set(git(repo, "ls-files", "--others", *flags, "--", ".", ":!.venv", ":!**/__pycache__/**").splitlines())
    return {p: (repo / p).read_bytes() for p in paths if p and (repo / p).is_file()}


def file_leaks(repo: Path, base: str, before: dict[str, bytes], tokens: list[str], turn: int) -> list[tuple[int, str]]:
    """Each token in a file the run changed or made, set against `before`, the files the setup left,
    or in a commit it added since `base`."""
    now = snapshot(repo)
    changed = {p for p in git(repo, "diff", "--name-only", base).splitlines() if (repo / p).is_file()}
    changed |= {p for p, data in now.items() if before.get(p) != data}
    out = []
    for path in sorted(changed):
        data = (repo / path).read_bytes().decode("utf-8", "replace")
        out += [(turn, f"{token} in {path}, turn {turn}") for token in tokens if token in data]
    commits = git(repo, "log", "-p", f"{base}..HEAD")
    return out + [(turn, f"{token} in a commit, turn {turn}") for token in tokens if token in commits]


def summarize(evs: list[dict], scenario: dict, files: list[str]) -> dict:
    """The facts of one run from its stream log. Cost is the last result's: Claude Code reports
    a resumed session's cost as the session's total. Turns and seconds are each turn's, summed."""
    ends = results(evs)
    last = ends[-1] if ends else {}
    denials = {d.get("tool_use_id"): d for r in ends for d in r.get("permission_denials", [])}
    uses = tool_uses(evs)
    agents, mcp = {}, {}
    for use in uses:
        if use["name"] in ("Agent", "Task"):
            name = str(use["input"].get("subagent_type", "")).split(":")[-1]
            agents[name] = agents.get(name, 0) + 1
        elif use["name"].startswith("mcp__"):
            mcp[use["name"]] = mcp.get(use["name"], 0) + 1
    final = last.get("result") or ""
    return {
        "skills": sorted({str(u["input"].get("skill", "")).split(":")[-1] for u in uses if u["name"] == "Skill"}),
        "agents": agents,
        "files": files,
        "mcp": mcp,
        "denials": [f"{d.get('tool_name')}: {argument({'input': d.get('tool_input', {})})}" for d in denials.values()],
        "must_not_run": [f"{rule}: {argument(u)}" for u in uses if u.get("id") not in denials
                         for rule in scenario.get("must_not_run", []) if matches(rule, u)],
        "subtype": last.get("subtype", "no result event"),
        "is_error": bool(last.get("is_error", True)),
        "cost_usd": round(last.get("total_cost_usd", 0.0), 4),
        "turns": sum(r.get("num_turns", 0) for r in ends),
        "seconds": round(sum(r.get("duration_ms", 0) for r in ends) / 1000),
        "first_line": next((line.strip() for line in final.splitlines() if line.strip()), ""),
        "final": final,
    }


def ticket_words(repo: Path, files: list[str]) -> int:
    """Words in the description of the ticket the run wrote: the last `.review/context/*.jira.txt`
    in `files`, from the first `h1.` heading after its `ticket-draft: drafted` status line, or the
    file's first `h1.` without one, so a follow-up ticket's block before it is not counted, up to
    the next line of dashes or `=` signs, or the `Comment to post` or `Session comment` heading,
    with wiki markup and URLs left out, as `using-jira` counts a ticket's length. 0 when the run
    wrote none."""
    tickets = sorted(f for f in files if fnmatch.fnmatch(f, ".review/context/*.jira.txt"))
    if not tickets:
        return 0
    lines = (repo / tickets[-1]).read_text().splitlines()
    status = next((i for i, line in enumerate(lines) if line.startswith("ticket-draft: drafted")), 0)
    start = next((i for i in range(status, len(lines)) if lines[i].strip().startswith("h1.")), len(lines))
    end = next((i for i in range(start, len(lines))
                if re.match(r"(-{4,}|={3,})|(Comment to post|Session comment)", lines[i].strip(), re.I)), len(lines))
    text = re.sub(r"\[([^|\]]*)\|[^\]]*\]", r"\1", "\n".join(lines[start:end])).replace("{{", "").replace("}}", "")
    markup = re.compile(r"(h[1-6]\.|[*#]+|-+|\||https?://\S*)")
    return sum(1 for word in text.split() if not markup.fullmatch(word))


def pr_words(final: str) -> int:
    """Words in the pull request description a run's last message shows: the first fenced block,
    up to the fence that closes it, without the collapsed `<details>` block. 0 when there is none."""
    lines = final.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("```")), None)
    if start is None:
        return 0
    fence = re.match(r"`+", lines[start]).group(0)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == fence), len(lines))
    words, collapsed = 0, False
    for line in lines[start + 1:end]:
        collapsed = collapsed or "<details>" in line
        if not collapsed:
            words += len(line.split())
        collapsed = collapsed and "</details>" not in line
    return words


def check(summary: dict, scenario: dict) -> str:
    """`pass`, or `fail: ` and each unmet expectation, from the summary alone."""
    expect, fails = scenario.get("expect", {}), []
    if "ends" in expect and (summary["subtype"] != expect["ends"] or summary["is_error"]):
        fails.append(f"ends {summary['subtype']}")
    fails += [f"no skill {s}" for s in expect.get("skills", []) if s not in summary["skills"]]
    fails += [f"no agent {a}" for a in expect.get("agents", []) if a not in summary["agents"]]
    fails += [f"no file {g}" for g in expect.get("files", []) if not fnmatch.filter(summary["files"], g)]
    if "max_cost" in expect and summary["cost_usd"] > expect["max_cost"]:
        fails.append(f"cost {summary['cost_usd']:.2f} over {expect['max_cost']}")
    if "max_ticket_words" in expect and summary.get("ticket_words", 0) > expect["max_ticket_words"]:
        fails.append(f"ticket of {summary['ticket_words']} words over {expect['max_ticket_words']}")
    if "max_turns" in expect and summary["turns"] > expect["max_turns"]:
        fails.append(f"{summary['turns']} turns over {expect['max_turns']}")
    final = summary.get("final", "")
    fails += [f"does not say {r}" for r in expect.get("says", []) if not re.search(r, final, re.M)]
    fails += [f"says {r}" for r in expect.get("not_says", []) if re.search(r, final, re.M)]
    fails += [f"wrote {f}" for g in expect.get("files_absent", []) for f in fnmatch.filter(summary["files"], g)]
    fails += [f"ran agent {a}" for a in expect.get("agents_absent", []) if a in summary["agents"]]
    fails += [f"ran {hit}" for hit in summary["must_not_run"]]
    fails += [f"verify failed: {command}" for command in summary.get("verify", [])]
    fails += [f"leaked {leak}" for leak in summary.get("leaks", [])]
    return "pass" if not fails else "fail: " + "; ".join(fails)


def judge(rubric: str, summary: dict, run_dir: Path, sandbox: Path) -> dict:
    """The rubric's score for one run, from a turn that sees only the rubric, the last message and
    the summary, without the variant's name, plugin commit, run id, key or reuse marks, so the judge cannot tell which wrote it,
    under the sandbox's settings, so no one's instructions, plugins or hooks load with it."""
    prompt = (f"{rubric.strip()}\n\n## The run's last message\n\n{(run_dir / 'final.md').read_text().strip()}\n\n"
              f"## The run's summary.json\n\n{json.dumps({k: v for k, v in summary.items() if k not in ('final', 'variant', 'plugin', 'run_id', 'key', 'reused', 'taken')}, indent=2)}\n\nScore the run against the rubric above, "
              'from 0 to 10. Reply with one JSON object and nothing else: {"score": <integer>, "sentence": "<one sentence>"}')
    done = child(["claude", "-p", prompt, "--model", JUDGE_MODEL, "--tools", "", "--strict-mcp-config",
                  "--settings", str(sandbox / "settings.json"), "--setting-sources", "project,local",
                  "--output-format", "json", "--max-budget-usd", str(JUDGE_BUDGET_USD)],
                 cwd=run_dir, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    try:
        result = json.loads(done.stdout)
        verdict = json.loads(re.search(r"\{.*\}", result["result"], re.S).group(0))
    except (ValueError, KeyError, TypeError, AttributeError):
        raise SystemExit(f"run.py: the judge gave no JSON reply for {run_dir}: {done.stdout[-300:]}{done.stderr[-300:]}")
    score, sentence = verdict.get("score"), verdict.get("sentence")
    if type(score) is not int or not 0 <= score <= 10 or not isinstance(sentence, str) or not sentence.strip():
        raise SystemExit(f"run.py: the judge's reply for {run_dir} is not a score from 0 to 10 and a sentence: {verdict}")
    return {"score": score, "sentence": sentence.strip(), "cost_usd": round(result.get("total_cost_usd", 0.0), 4)}


def flags(summary: dict) -> list[str]:
    return ([f"error: {summary['subtype']}"] if summary["is_error"] or summary["subtype"] != "success" else []) + \
        (["must_not_run hit"] if summary["must_not_run"] else []) + \
        (["verify failed"] if summary.get("verify") else []) + \
        (["leaked"] if summary.get("leaks") else [])


def run_once(sandbox: Path, scenario: dict, plugin: Path, out: Path, env: dict) -> dict:
    repo = sandbox / "repos" / scenario["repo"]
    shell_env = {**os.environ, "SBX_FIXTURES": str(fixture_dir())}
    for command in scenario.get("setup", []):
        child(command, shell=True, check=True, cwd=repo, env=shell_env)
    base = git(repo, "rev-parse", "HEAD")
    tokens, through = canaries(scenario)
    before, in_files = (snapshot(repo) if tokens else {}), []
    out.mkdir(parents=True)
    log, session = out / "stream.jsonl", None
    log.write_text("")
    for turn, prompt in enumerate(scenario["turns"], 1):
        cmd = [str(HERE / "sbx-claude"), str(sandbox), scenario["repo"], str(log), *(["--resume", session] if session else [])]
        child([*cmd, "--", prompt], check=False, capture_output=True, text=True,
              env={**os.environ, **env, "SBX_PLUGIN_DIR": str(plugin)})
        if tokens:
            in_files += file_leaks(repo, base, before, tokens, turn)
        ends = results(events(log))
        if not ends or ends[-1].get("subtype") != "success" or ends[-1].get("is_error"):
            break
        session = ends[-1]["session_id"]
    evs = events(log)
    (out / "final.md").write_text((results(evs)[-1].get("result") or "") if results(evs) else "")
    summary = summarize(evs, scenario, written(evs, repo, base))
    if tokens:
        summary["leaks"] = sorted({leak for turn, leak in said_leaks(evs, tokens) + in_files
                                   if through is None or turn <= through})
    if "verify" in scenario:
        summary["verify"] = []
        for command in scenario["verify"]:
            ran = child(command, shell=True, cwd=repo, env=shell_env, capture_output=True, text=True)
            if ran.returncode:
                said = (ran.stdout + ran.stderr).strip().splitlines()
                summary["verify"].append(f"{command}: {said[-1] if said else f'exit {ran.returncode}'}")
    return {**summary, "ticket_words": ticket_words(repo, summary["files"]), "pr_words": pr_words(summary["final"])}


def cell(value) -> str:
    if isinstance(value, dict) and "score" in value:
        return f"{value['score']}: {value['sentence']}"
    if isinstance(value, dict):
        return ", ".join(f"{k} {v}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value).replace("|", "\\|")


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in rows]) + "\n"


def digest(*parts: bytes) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(len(part).to_bytes(8, "big") + part)
    return h.hexdigest()


def dirty(plugin: Path) -> bool:
    """Uncommitted changes or untracked files, whatever the checkout's git config hides."""
    return bool(git(plugin, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=none"))


def run_key(scenario: dict, sandbox: Path, plugin: Path, model: str, budget: float) -> dict | None:
    """What determines a run's input, each part a digest or a value; None for a plugin checkout
    with uncommitted changes, whose tree git does not name. Credentials are left out of `env`."""
    if dirty(plugin):
        return None
    pack = scenario_file().parent
    fixtures = sorted(f for f in fixture_dir().rglob("*") if f.is_file())
    harness = [x for f, root in [*((HERE / name, HERE) for name in HARNESS), *((f, pack) for f in fixtures)]
               for x in (str(f.relative_to(root)).encode(), f.read_bytes())]
    remotes = [git(sandbox / "remotes" / f"{name}.git", "rev-parse", "--verify", "refs/heads/main").encode()
               for name in sorted(pins(sandbox))]
    remotes += [path.name.encode() + git(path, "rev-parse", "--verify", "HEAD").encode()
                for path in sorted(sandbox.glob("served/*/*.git"))]
    version = child(["claude", "--version"], check=True, capture_output=True, text=True).stdout.strip()
    return {
        "scenario": digest(json.dumps(scenario, sort_keys=True).encode()),
        "harness": digest(*harness),
        "sandbox": digest((sandbox / "pins").read_bytes(), (sandbox / "mcp.json").read_bytes(), *remotes),
        "env": digest(*sorted(f"{k}={v}".encode() for k, v in os.environ.items()
                              if SESSION_ENV.fullmatch(k) and not UNKEYED_ENV.search(k))),
        "plugin": git(plugin, "rev-parse", "HEAD^{tree}"),
        "model": model,
        "budget": repr(budget),
        "claude": version,
    }


def reusable(runs: Path, key: dict, limit: int, now: float) -> list[tuple[Path, dict]]:
    """Up to `limit` recorded runs under `runs`, any variant's, with `key`, started within
    REUSE_HOURS of `now`, newest first, each run_id once. A run with no result event, where the
    session never finished, is not taken: it says more about that moment than about the plugin."""
    found = []
    for path in sorted(runs.glob("*/*/summary.json")):
        try:
            summary = json.loads(path.read_text())
        except ValueError:
            summary = None
        if not isinstance(summary, dict):
            raise SystemExit(f"run.py: {path} is not a summary run.py wrote; remove its run directory")
        if summary.get("key") != key:
            continue
        if not isinstance(summary.get("run_id"), str) or not isinstance(summary.get("started"), int):
            raise SystemExit(f"run.py: {path} has this run's key but no run_id or started; remove its run directory")
        if now - summary["started"] <= REUSE_HOURS * 3600 and summary.get("subtype") != "no result event":
            found.append((path.parent, summary))
    taken, seen = [], set()
    for run_dir, summary in sorted(found, key=lambda f: -f[1]["started"]):
        if summary["run_id"] not in seen and len(taken) < limit:
            seen.add(summary["run_id"])
            taken.append((run_dir, summary))
    return taken


def unmatched(runs: Path, key: dict) -> str:
    """Why no recorded run under `runs` was taken: the key parts in which the newest keyed run
    differs, or that the ones with this key are too old or never finished."""
    keyed = [s for s in (json.loads(p.read_text()) for p in runs.glob("*/*/summary.json")) if isinstance(s.get("key"), dict)]
    if not keyed:
        return "no recorded run of this scenario has a key"
    newest = max(keyed, key=lambda s: s.get("started", 0))
    parts = [part for part in key if newest["key"].get(part) != key[part]]
    if parts:
        return f"the newest keyed run, {newest.get('run_id')}, differs in {', '.join(parts)}"
    return f"the runs with this key are older than {REUSE_HOURS} hours or never reached a result event"


def report(scenario: dict, variant: str, summaries: list[dict], out: Path) -> str:
    keys = ["subtype", "cost_usd", "turns", "seconds", "skills", "agents", "files", "mcp", "denials", "must_not_run"]
    keys += [k for k in ("verify", "check", "judge") if k in summaries[0]]
    flagged = [f"run {s['run']} ({'; '.join(flags(s))})" for s in summaries if flags(s)]
    reused = sum(1 for s in summaries if s.get("reused"))
    head = f"{scenario['id']} on {variant}, {len(summaries)} run(s)" + (f", {reused} reused" if reused else "") + ": " + \
        (f"flagged {', '.join(flagged)}" if flagged else "nothing flagged")
    rows = [[str(s["run"]), "; ".join(flags(s)), *(cell(s[k]) for k in keys), cell(s["first_line"])] for s in summaries]
    text = head + "\n\n" + table(["run", "flags", *keys, "first line"], rows)
    text += f"\n## What a good run shows\n\n{scenario['look_at'].strip()}\n"
    for s in summaries:
        text += f"\n## Run {s['run']}: last message\n\n" + (out / variant / str(s["run"]) / "final.md").read_text().strip() + "\n"
    return text


def spread(values: list[float]) -> str:
    return f"{statistics.mean(values):.2f} ({min(values):.2f}–{max(values):.2f})"


def metric(summary: dict, key: str) -> float:
    value = summary[key]["score"] if key == "judge" else summary.get(key, 0)
    return float(sum(value.values()) if isinstance(value, dict) else len(value) if isinstance(value, list) else value)


def compare(out: Path) -> str:
    """Every variant's runs under `out`, baseline first: each metric's mean and range, the last
    messages' first lines side by side, then each last message in full."""
    variants = sorted((d.name for d in out.iterdir() if d.is_dir()), key=lambda v: (v != BASELINE, v))
    runs = {v: sorted((json.loads(p.read_text()) for p in (out / v).glob("*/summary.json")), key=lambda s: s["run"]) for v in variants}
    runs = {v: s for v, s in runs.items() if s}
    if not runs:
        raise SystemExit(f"run.py: no runs under {out}")
    judged = all("judge" in x for s in runs.values() for x in s)
    rows = []
    for v, s in runs.items():
        passed = sum(x.get("check") == "pass" for x in s)
        checks = f"{passed}/{len(s)}" if any("check" in x for x in s) else "-"
        rows.append([v, str(len(s)), *(spread([metric(x, k) for x in s]) for k in METRICS), checks,
                     *([spread([metric(x, "judge") for x in s])] if judged else [])])
    header = ["variant", "runs", *METRICS, "check", *(["judge"] if judged else [])]
    text = f"{out.name}: mean (range) over each variant's runs; check, the runs that passed --check\n\n" + table(header, rows)
    side = [[str(i + 1), *(cell(s[i]["first_line"]) if i < len(s) else "" for s in runs.values())] for i in range(max(map(len, runs.values())))]
    text += "\nEach run's last message, first line:\n\n" + table(["run", *runs], side)
    for v, s in runs.items():
        for x in s:
            text += f"\n## {v}, run {x['run']}: last message\n\n" + (out / v / str(x["run"]) / "final.md").read_text().strip() + "\n"
    return text


def main_compare(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="run.py compare", description="Tabulate every variant's runs of a scenario.")
    p.add_argument("scenario", help="the scenario id whose runs to compare")
    p.add_argument("--sandbox", type=Path, help="a directory sandbox.sh built; default, the one holding the working directory")
    args = p.parse_args(argv)
    out = (args.sandbox or find_sandbox(Path.cwd())).resolve() / "runs" / args.scenario
    if not out.is_dir():
        p.error(f"no runs of {args.scenario} under {out.parent}")
    text = compare(out)
    (out / "compare.md").write_text(text)
    print(text, end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["compare"]:
        return main_compare(argv[1:])
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0], epilog="sandbox/run.py compare --help: the comparison")
    p.add_argument("scenario", nargs="?", help="the scenario id to run")
    p.add_argument("--list", action="store_true", help="print the scenarios, and run nothing")
    p.add_argument("--scenarios", type=Path, metavar="FILE", help="the scenario file, its fixtures in fixture/ beside it; default, scenarios.yaml beside run.py")
    p.add_argument("--variant", type=Path, help="a plugin checkout to load in place of the sandbox's clone")
    p.add_argument("--repeat", type=int, default=1, help="how many times to run the scenario; default 1")
    p.add_argument("--model", default="sonnet", help="the model each turn runs on; default sonnet")
    p.add_argument("--budget", type=float, default=5.0, help="the dollar cap on each turn; default 5")
    p.add_argument("--sandbox", type=Path, help="a directory sandbox.sh built; default, the one holding the working directory")
    p.add_argument("--check", action="store_true", help="hold each run to the scenario's expect block, must_not_run and verify; exit 1 on a failure")
    p.add_argument("--judge", type=Path, metavar="RUBRIC", help="score each run against this rubric file in one more Sonnet turn")
    p.add_argument("--no-wait", action="store_true", help="stop at once, naming the holder, when another run holds the sandbox")
    p.add_argument("--reuse", action="store_true",
                   help=f"take runs recorded in the last {REUSE_HOURS} hours with the same key, any variant's, and make only the rest")
    args = p.parse_args(argv)
    if args.judge and not args.judge.is_file():
        p.error(f"--judge {args.judge}: no such file")

    if args.scenarios:
        if not args.scenarios.is_file():
            p.error(f"--scenarios {args.scenarios}: no such file")
        global SCENARIOS
        SCENARIOS = args.scenarios.resolve()
    known = scenarios()
    if args.list:
        print(f"{len(known)} scenarios")
        print(table(["scenario", "repo", "turns", "first turn"],
                    [[s["id"], s["repo"], str(len(s["turns"])), s["turns"][0]] for s in known.values()]), end="")
        return 0
    if args.scenario not in known:
        p.error(f"name a scenario: {', '.join(known)}")
    if args.repeat < 1:
        p.error("--repeat must be at least 1")
    scenario = known[args.scenario]
    sandbox = (args.sandbox or find_sandbox(Path.cwd())).resolve()
    if not (sandbox / "pins").is_file():
        p.error(f"--sandbox {sandbox}: not a sandbox, no pins file; sandbox.sh builds one")
    plugin = args.variant.resolve() if args.variant else sandbox / "repos" / "dev-tools"
    variant = plugin.name if args.variant else BASELINE
    if args.variant and (variant == BASELINE or not (plugin / ".claude-plugin" / "plugin.json").is_file()):
        p.error(f"--variant {args.variant}: not a plugin checkout, or named {BASELINE}")
    if args.variant:
        name = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text()).get("name")
        if not isinstance(name, str) or not name:
            p.error(f"--variant {args.variant}: its plugin.json names no plugin")
        scenario = for_plugin(scenario, name)
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stopping)
    with holding(sandbox, f"pid {os.getpid()}, {scenario['id']} on {variant}", wait=not args.no_wait):
        return run_variant(args, scenario, sandbox, plugin, variant)


def finish(summary: dict, args: argparse.Namespace, scenario: dict, run_dir: Path, sandbox: Path) -> None:
    """The judge's score and the check this call asks for, then the summary written beside the run."""
    if args.judge:
        summary["judge"] = judge(args.judge.read_text(), summary, run_dir, sandbox)
    if args.check:
        summary["check"] = check(summary, scenario)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def run_variant(args: argparse.Namespace, scenario: dict, sandbox: Path, plugin: Path, variant: str) -> int:
    write_settings(sandbox, plugin)

    out = sandbox / "runs" / scenario["id"]
    taken = []
    if args.reuse:
        reset(sandbox)
        key = run_key(scenario, sandbox, plugin, args.model, args.budget)
        if key is None:
            print(f"run.py: {plugin} has uncommitted changes, so no run is reused", file=sys.stderr, flush=True)
        else:
            taken = reusable(out, key, args.repeat, time.time())
            if not taken:
                print(f"run.py: no run is reused: {unmatched(out, key)}", file=sys.stderr, flush=True)
    summaries = []
    with tempfile.TemporaryDirectory(dir=sandbox) as held:
        reused = []
        for n, (run_dir, recorded) in enumerate(taken, 1):
            shutil.copytree(run_dir, Path(held) / str(n))
            summary = {k: v for k, v in recorded.items() if k not in ("check", "judge")}
            summary.update(variant=variant, run=n, reused=True, taken=round(time.time()))
            (Path(held) / str(n) / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            reused.append((summary, recorded))
        shutil.rmtree(out / variant, ignore_errors=True)
        for n, (summary, recorded) in enumerate(reused, 1):
            (out / variant).mkdir(parents=True, exist_ok=True)
            shutil.move(str(Path(held) / str(n)), str(out / variant / str(n)))
            finish(summary, args, scenario, out / variant / str(n), sandbox)
            summaries.append(summary)
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(recorded["started"]))
            print(f"run {n}: reused {recorded['run_id']} from {when}, {summary['subtype']}, ${summary['cost_usd']:.2f}", flush=True)
    # A wave's coverage run outlasts print mode's default ten-minute wait for background agents.
    env = {"SBX_MODEL": args.model, "SBX_BUDGET_USD": str(args.budget),
           "CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS": os.environ.get("CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS", "3600000")}
    for n in range(len(taken) + 1, args.repeat + 1):
        reset(sandbox)
        key = run_key(scenario, sandbox, plugin, args.model, args.budget)
        sha = git(plugin, "rev-parse", "HEAD") + ("+dirty" if dirty(plugin) else "")
        started = round(time.time())
        summary = {"scenario": scenario["id"], "variant": variant, "run": n, "plugin": sha, "model": args.model, "started": started,
                   "run_id": f"{scenario['id']}/{variant}/{n}/{started}", "key": key,
                   **run_once(sandbox, scenario, plugin, out / variant / str(n), env)}
        finish(summary, args, scenario, out / variant / str(n), sandbox)
        summaries.append(summary)
        print(f"run {n}: {summary['subtype']}, ${summary['cost_usd']:.2f}, {summary['seconds']} s", flush=True)

    text = report(scenario, variant, summaries, out)
    (out / "report.md").write_text(text)
    print(text, end="")
    return 1 if any(s.get("check", "").startswith("fail") for s in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(main())
