#!/usr/bin/env python3
"""Run the plugin's scripts and hooks at a base commit and in this working tree on the same inputs,
and diff what they print: the first check that a change moved a value without changing what any
skill, agent or person is handed.

Both trees are copied into a scratch directory, the base from `git archive` and this tree from its
tracked and untracked files, so neither the repository nor its git state is touched. The defaults
come first, from profile.py `--defaults` whole and on every field, the project ones included, run
from the scratch directory, which no standard covers. Fixture code repositories are made once per
tree: `core` and `infra`, named as repositories a project's standard would cover; `rad`, `lib` and
`analysis`, named as ones it would not; a repository of another owner nobody has heard of;
`acme-widgets`, whose own `standards/profile.yaml` sets every key; `refused`, whose own `standards/profile.yaml` the schema
refuses; and one with no remote. Each commits a product
definition under core/data/ and under schema/, a light and a deep glob of the fixtures' profiles,
and a pyproject.toml. In each, the cases run profile.py on every field,
surface_diff.py with one variable of both product definitions and one DataProductIdentifier member
removed in the working tree, so the
profile's depth.deep globs decide what it reads, depth_floor.py once on that change and once per
path for a path matching each light and deep glob, where.sh's fields and session-start line,
standard_file.sh, record.py's ticket pattern, next_phase.py at every Jira status, one lowercased
and one the workflow does not have, with and without a context page and, with none, given no pull
request, plus one status given an open pull request at the tree's own state contract,
transcript_excerpt.py's redaction of a fixed text, and the build hook's gate counts and Gates line.

Every case runs with PROFILE_SHADOW_ROOT left out, which a base from before the shadow was deleted
still reads, so a shadow period there does not change what is compared. Every case's exit code, standard output and standard error are compared after the tree's
path, the fixture's path, timestamps and the wall clock are normalized. A difference fails unless the
expected-changes file names the case: one `<case glob>: <why>` per line, `#` for a comment. An
expected change that did not happen is reported too, since the file then says something false.

    sandbox/same_output.py                      # against origin/main
    sandbox/same_output.py --base 7b5c7e2 --expected sandbox/expected/<change>.txt

Exits 0 when every difference is expected, 1 otherwise. Needs git, bash, jq and python3.
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP = HERE.parent

FIELDS = [
    "source", "ticket.pattern", "ticket.project", "public", "template", "downstream",
    "tests.command", "coverage.command", "lint.command", "lint.regex", "types.regex", "gates.tests",
    "github_server", "posted_text", "depth.light", "depth.deep",
]
# Set only by a standard's project settings and the default profile, so read through --defaults alone.
PROJECT_FIELDS = ["jira.statuses", "jira.roles", "jira.pr_statuses", "internal.domains", "internal.private_repositories",
               "attribution.phrases", "surface.identifiers"]

# The settings a fixture repository's own standards/profile.yaml holds, by its name in REPOS.
OWN_PROFILES = {
    "acme": (
        "ticket:\n  pattern: 'WID-\\d+'\n  project: WID\npublic: false\n"
        "template: not yet recorded\ndownstream: [acme-app]\ntests:\n  command: 'npm test'\n"
        "coverage:\n  command: 'npm run coverage'\nlint:\n  command: 'npm run lint'\n"
        "  regex: 'npm[[:space:]]+run[[:space:]]+lint'\ntypes:\n  regex: 'tsc'\n"
        "gates:\n  tests: 'npm[[:space:]]+test'\ngithub_server: github\nposted_text: plain\n"
        "depth:\n  light:\n    - {glob: 'docs/**', brief: documentation}\n  deep: ['schema/**']\n"
    ),
    "refused": "flavor: blue\n",
}

# name, origin URL (None: no remote), branch, ticket key
REPOS = [
    ("core", "https://github.com/acme/widgets-core.git", "PROJ-830-src-seq", "PROJ-830"),
    ("infra", "https://github.com/acme/widgets-infra.git", "PROJ-12-infra", "PROJ-12"),
    ("rad", "https://github.com/acme/widgets-rad.git", "PROJ-7-rad", "PROJ-7"),
    ("lib", "https://github.com/acme/geo-lib.git", "PROJ-3-lib", "PROJ-3"),
    ("analysis", "https://github.com/acme/widgets-analysis.git", "PROJ-4-analysis", "PROJ-4"),
    ("unknown", "https://github.com/someorg/unknown-tool.git", "PROJ-6-unknown", "PROJ-6"),
    ("acme", "https://github.com/acme/acme-widgets.git", "WID-3-widget", "WID-3"),
    ("refused", "https://github.com/o/refused.git", "PROJ-5-refused", "PROJ-5"),
    ("noremote", None, "PROJ-9-local", "PROJ-9"),
]

GATE_COMMANDS = ["pre-commit run --files a.py", "pytest -q", "mypy .", "npm test", "npm run lint", "tsc", "tox -e py"]
# Every status of the example workflow, one written as a person might type it, and one it does not have.
STATUSES = ["New", "To Do", "Upcoming", "Exploration", "Under Development", "External Needs", "In Review", "Done", "Abandoned", "in review", "Blocked"]
# A product definition with two variables; the working tree drops LAT.
PRODUCT_DEF = "variables:\n  RAD:\n    units: W\n    dimensions: [time]\n  LAT:\n    units: deg\n    dimensions: [time]\n"
# One path for each light and deep glob of the default profile's and acme-widgets' profiles,
# and one that matches none.
DEPTH_PATHS = ["CHANGELOG.md", "README.md", "docs/a.md", "doc/b.md", "pyproject.toml", "skills/x/SKILL.md",
               "core/data/p.yaml", "core/io/product_definition.py", "x/manifest.json", "schema/p.yaml"]
REDACT_TEXT = (
    "see https://jira.internal.example/browse/PROJ-1 and git@gitlab.internal.example:x/y.git;\n"
    "token=abc123def456 and Bearer abcdefghijkl; https://example.org/ok and someone@internal.example\n"  # gitleaks:allow
)


CLEAN_ENV = {k: v for k, v in os.environ.items() if k != "PROFILE_SHADOW_ROOT"}


def sh(args: list[str], cwd: Path | None = None, stdin: str = "", env: dict | None = None) -> tuple[int, str, str]:
    p = subprocess.run(args, cwd=cwd, input=stdin, capture_output=True, text=True, env=CLEAN_ENV if env is None else env)
    return p.returncode, p.stdout, p.stderr


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)


def copy_tree(base: str, dest: Path) -> None:
    """The base commit's files, or this working tree's when base is None."""
    dest.mkdir(parents=True)
    if base:
        archive = subprocess.run(["git", "archive", base], cwd=TOP, check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
        return
    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=TOP, check=True, capture_output=True, text=True).stdout
    for rel in filter(None, files.split("\0")):
        src = TOP / rel
        if src.is_file() and not src.is_symlink():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
        elif src.is_symlink():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            os.symlink(os.readlink(src), dest / rel)


# An identifier enum and an ordinary one, so surface_diff.py's identifier classes are compared.
IDS = 'from enum import Enum\n\n\nclass DataProductIdentifier(str, Enum):\n    L1A_RAD = "L1A-RAD"\n    L1B_CAM = "L1B-CAM"\n'


def make_repo(path: Path, origin: str | None, branch: str, key: str, profile: str | None = None) -> None:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", branch)
    (path / "README.md").write_text("# fixture\n")
    (path / "standards").mkdir()
    (path / "standards/review-rules.md").write_text("# Review rules\n\n### R-001 · A rule\n\nStatus: live\n")
    if profile is not None:
        (path / "standards/profile.yaml").write_text(profile)
    for rel in ("core/data/p.yaml", "schema/p.yaml"):
        (path / rel).parent.mkdir(parents=True)
        (path / rel).write_text(PRODUCT_DEF)
    (path / "pyproject.toml").write_text('[project]\nname = "fixture"\nversion = "1.0.0"\n')
    (path / "core/ids.py").write_text(IDS)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "init")
    if origin:
        git(path, "remote", "add", "origin", origin)
    (path / ".review/context").mkdir(parents=True)
    with open(path / ".git/info/exclude", "a") as f:
        f.write(".review/\n")
    page = f"# {key} · a fixture ticket\nBranch: {branch}\n\n## Goal\n\nA fixture.\n"
    (path / f".review/context/{key}.md").write_text(page)
    (path / ".review/context.md").write_text(page)


def cases(root: Path, repo: Path, origin: str | None, key: str) -> list[tuple[str, list[str], str]]:
    """(case, argv, stdin) for one fixture repository against one tree."""
    slug = re.sub(r"^.*github\.com/|\.git$", "", origin) if origin else None
    py, hooks, scripts = sys.executable, root / "hooks", root / "scripts"
    out: list[tuple[str, list[str], str]] = []
    if slug:
        out.append(("profile", [py, str(scripts / "profile.py"), slug], ""))
        out += [(f"profile.{f}", [py, str(scripts / "profile.py"), slug, "--field", f], "") for f in FIELDS]
        record = (
            "import importlib.util, sys\n"
            f"s = importlib.util.spec_from_file_location('record', {str(scripts / 'record.py')!r})\n"
            "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
            "try:\n    print(m.ticket_pattern(sys.argv[1]))\nexcept m.Unsupported as e:\n    print('Unsupported:', e)\n"
        )
        out.append(("record.ticket_pattern", [py, "-c", record, slug], ""))
        if origin.endswith("widgets-core.git"):
            out.append(("transcript_excerpt", [py, str(scripts / "transcript_excerpt.py"), "--stdin"], REDACT_TEXT))
        out += [(f"depth_floor({path})", [py, str(scripts / "depth_floor.py"), "HEAD", "--repo", slug, "--paths", path], "") for path in DEPTH_PATHS]
    out.append(("where.fields", ["bash", str(hooks / "where.sh"), "--fields"], ""))
    out.append(("where.fields.ticket", ["bash", str(hooks / "where.sh"), "--fields", "--ticket", key], ""))
    out.append(("where.line", ["bash", str(hooks / "where.sh")], json.dumps({"cwd": str(repo), "session_id": "s0"})))
    out.append(("standard_file", ["bash", str(scripts / "standard_file.sh")], ""))
    return out


def gate_cases(root: Path, repo: Path) -> list[tuple[str, tuple[int, str, str]]]:
    """The build hook's gate counts and Gates line, after a build starts and each gate command runs."""
    hook = str(root / "hooks/build-record.sh")
    sh(["bash", hook, "prompt"], repo, json.dumps({"prompt": "/lasp-dev:implement-change X", "session_id": "s1"}))
    out = []
    for c in GATE_COMMANDS:
        before = (repo / ".review/build/events.jsonl").read_text() if (repo / ".review/build/events.jsonl").exists() else ""
        sh(["bash", hook, "event"], repo, json.dumps({"tool_name": "Bash", "session_id": "s1", "tool_input": {"command": c}}))
        after = (repo / ".review/build/events.jsonl").read_text() if (repo / ".review/build/events.jsonl").exists() else ""
        gates = [json.loads(l).get("gate") for l in after[len(before):].splitlines() if '"gate"' in l]
        out.append((f"gate({c})", (0, " ".join(g for g in gates if g) + "\n", "")))
    rc, so, se = sh(["bash", hook, "summary"], repo, json.dumps({"session_id": "s1"}))
    checked = repo / ".review/build/already-checked.md"
    line = next((l for l in checked.read_text().splitlines() if l.startswith("Gates:")), "") if checked.exists() else "(no already-checked.md)"
    out.append(("gates.line", (rc, line + "\n", se)))
    return out


def run_tree(name: str, root: Path, work: Path) -> dict[str, tuple[int, str, str]]:
    results: dict[str, tuple[int, str, str]] = {}
    profile = [sys.executable, str(root / "scripts/profile.py"), "--defaults"]
    results["defaults"] = norm(sh(profile, work), root, work, work)
    for f in [f for f in FIELDS if f != "source"] + PROJECT_FIELDS:
        results[f"defaults.{f}"] = norm(sh([*profile, "--field", f], work), root, work, work)
    for rname, origin, branch, key in REPOS:
        repo = work / f"{name}-repos" / rname
        make_repo(repo, origin, branch, key, OWN_PROFILES.get(rname))
        for case, argv, stdin in cases(root, repo, origin, key):
            results[f"{rname}/{case}"] = norm(sh(argv, repo, stdin), root, repo, work)
        if origin:
            # A change that removes a variable from both product definitions, read through the
            # profile's depth.deep globs, then put back so the cases below see a clean tree.
            slug = re.sub(r"^.*github\.com/|\.git$", "", origin)
            for rel in ("core/data/p.yaml", "schema/p.yaml"):
                (repo / rel).write_text(PRODUCT_DEF.split("  LAT:")[0])
            (repo / "core/ids.py").write_text(IDS.replace('    L1B_CAM = "L1B-CAM"\n', ""))
            scripts = root / "scripts"
            results[f"{rname}/surface_diff"] = norm(sh([sys.executable, str(scripts / "surface_diff.py"), "HEAD", "--repo", slug], repo), root, repo, work)
            results[f"{rname}/depth_floor(diff)"] = norm(sh([sys.executable, str(scripts / "depth_floor.py"), "HEAD", "--repo", slug], repo), root, repo, work)
            git(repo, "checkout", "-q", "--", ".")
        fields = repo / ".review/fields.txt"
        rc, so, _ = sh(["bash", str(root / "hooks/where.sh"), "--fields"], repo)
        fields.write_text(so)
        # With no context page here, next_phase routes on the ticket's Jira status.
        bare = repo / ".review/fields-no-page.txt"
        bare.write_text(re.sub(r"(?m)^context=.*$", "context=", so))
        for status in STATUSES:
            for label, path in (("", fields), (" no page", bare)):
                argv = [sys.executable, str(root / "scripts/next_phase.py"), "--fields", str(path), "--ticket-status", status]
                results[f"{rname}/next_phase({status}{label})"] = norm(sh(argv, repo), root, repo, work)
        # A status that asks for the pull request's state (jira.pr_statuses), given none, which
        # routes on the status's `next`, at every status. Given an open one, the pull request's rows
        # decide before any profile value is read, so one status per repository shows it.
        key = re.search(r"(?m)^ticket=(.*)$", so)
        states = {" no pull request": ("pull request: none\n", STATUSES),
                  " open pull request": (open_state(key.group(1) if key else "", root), ["In Review"])}
        for label, (text, statuses) in states.items():
            state = repo / f".review/state{label.replace(' ', '-')}.txt"
            state.write_text(text)
            for status in statuses:
                argv = [sys.executable, str(root / "scripts/next_phase.py"), "--fields", str(bare), "--ticket-status", status, "--state", str(state)]
                results[f"{rname}/next_phase({status} no page{label})"] = norm(sh(argv, repo), root, repo, work)
        for case, got in gate_cases(root, repo):
            results[f"{rname}/{case}"] = norm(got, root, repo, work)
    return results


def open_state(ticket: str, root: Path) -> str:
    """record.py --state's block for an open pull request of `ticket` with no review yet, at the
    contract version the tree's own record.py writes, so a contract change cannot turn the cases
    back into early refusals on both sides alike."""
    contract = re.search(r"(?m)^CONTRACT = (\d+)$", (root / "scripts/record.py").read_text())
    if not contract:
        raise SystemExit(f"same_output.py: no CONTRACT in {root / 'scripts/record.py'}")
    header = ("id | key, or opener | severity, or resolved | headline | path:line | verdict | contested | replies after"
              " | proposed, or outdated | after the verdict | judged")
    return "\n".join(["## pr-0007 — state", f"contract: {contract.group(1)}", f"head: {'c' * 40}", "draft: false", "state: open", "author: a-author",
                      f"ticket: Ticket: {ticket} · x" if ticket else "ticket: none", "build: Build: passed",
                      "findings review: none", "threads: 0", header]) + "\n"


def norm(got: tuple[int, str, str], root: Path, repo: Path, work: Path) -> tuple[int, str, str]:
    def n(s: str) -> str:
        for real, label in ((repo, "<repo>"), (root, "<plugin>"), (work, "<work>")):
            s = s.replace(str(real.resolve()), label).replace(str(real), label)
        s = re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z?", "<time>", s)
        s = re.sub(r"wall clock [0-9?]+ min", "wall clock <n> min", s)
        return s
    return got[0], n(got[1]), n(got[2])


def load_expected(path: Path | None) -> list[tuple[str, str]]:
    if not path:
        return []
    rules = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
        if line:
            glob, _, why = line.partition(":")
            rules.append((glob.strip(), why.strip()))
    return rules


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", default="origin/main", help="the commit to compare against (default origin/main)")
    p.add_argument("--expected", type=Path, help="the expected-changes file")
    p.add_argument("--keep", action="store_true", help="keep the scratch directory and print its path")
    p.add_argument("--dump", type=Path, help="write each tree's results here, one JSON file per tree, for reading")
    args = p.parse_args(argv)
    for tool in ("git", "bash", "jq"):
        if not shutil.which(tool):
            print(f"same_output.py: needs {tool}", file=sys.stderr)
            return 1
    work = Path(tempfile.mkdtemp(prefix="same-output-"))
    try:
        trees = {}
        for name, ref in (("base", args.base), ("head", None)):
            root = work / name
            copy_tree(ref, root)
            trees[name] = run_tree(name, root, work)
            if args.dump:
                args.dump.mkdir(parents=True, exist_ok=True)
                (args.dump / f"{name}.json").write_text(json.dumps(trees[name], indent=1, sort_keys=True))
        rules = load_expected(args.expected)
        used = set()
        unexpected = 0
        for case in sorted(set(trees["base"]) | set(trees["head"])):
            a, b = trees["base"].get(case), trees["head"].get(case)
            if a == b:
                continue
            match = next(((g, w) for g, w in rules if fnmatch.fnmatch(case, g)), None)
            label = f"expected ({match[1]})" if match else "UNEXPECTED"
            if match:
                used.add(match[0])
            else:
                unexpected += 1
            print(f"--- {case}: {label}")
            for part, x, y in zip(("exit", "stdout", "stderr"), a or (None, "", ""), b or (None, "", "")):
                if x != y:
                    lines = difflib.unified_diff(str(x).splitlines(), str(y).splitlines(), "base", "head", lineterm="", n=1)
                    print(f"  {part}:")
                    print("\n".join("    " + l for l in list(lines)[2:40]))
        unused = [g for g, _ in rules if g not in used]
        for g in unused:
            print(f"--- expected change {g!r} did not happen")
        total = len(set(trees["base"]) | set(trees["head"]))
        print(f"same_output.py: {total} cases against {args.base}; {unexpected} unexpected difference(s), {len(used)} expected, {len(unused)} expected but absent")
        return 1 if unexpected or unused else 0
    finally:
        if args.keep:
            print(f"scratch: {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
