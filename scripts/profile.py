#!/usr/bin/env python3
"""Print a repository's profile: the facts the hooks, scripts and skills read about it.

Each key is answered by the first of these that gives it:

1. the repository's standard's settings, read where the working directory's checkout, when it is
   the repository, keeps its standard: its own `standards/`, as it stands, committed or not; or,
   when its `standards/profile.yaml` is the one line `standard: <owner>/<repo>`, the standard of
   the repository it names, as `standard.sh` gives it (fetched on the first read in a clone that
   never has, then as of the clone's last fetch, which each build and review makes; with
   `STANDARD_OFFLINE` set, as a hook runs, never fetched; or a local checkout git's config names).
   A standard with a `profiles/` directory covers several repositories: its `profile.yaml` holds
   the project settings, `PROJECT_KEYS`, and `profiles/<repo>.yaml` each repository's own, the
   rest; a setting in the other file, or a repository with no file there, is refused. A standard
   with no `profiles/` covers its own repository alone, whose `profile.yaml` holds both kinds, and
   a pointer to one is refused. `git config lasp-dev.standard none` reads a pointing
   repository without its standard, the person's choice when it cannot be fetched, and its
   `source` says so;
2. what `survey.py` detects in that checkout: the keys its drop-in profile fills from the
   repository's own files and history, never the proposals a person trims, cached as
   `lasp-dev/detected/<commit>-<top>-<hash>.yaml` in the checkout's git directory, by the
   commit it read, the plugin top level and a hash of the survey, this file, the default profile,
   the standard's settings, and a shallow clone's boundary, the last commit's only;
3. the plugin's default profile, `standards/default-profile.yaml`, which sets every key: how the
   tools operate for a repository with no standard, with a value only a repository can give
   reading `not yet recorded`.

The run's owner is the argument's, or the `origin` remote's in the working directory when the
argument names none; the working directory's checkout is the repository when its `origin` names
it and that owner, so a fork reads its own `origin`, whatever its `upstream` remote names.
`--standard` prints the absolute path of that checkout's standard's directory:
the fetched standard its pointer names, or its own `standards/`. A checkout with neither exits 1,
its message ending "the repository has no standard"; any other exit 1 is a refusal: a working
directory that is not the repository's checkout, a pointer that cannot be read, a standard not
read, and anything the repository's profile refuses but what is detected, such as a standard that
does not cover it or that the schema refuses.

Every one of these files takes the same schema. Any key, or any whole section, may read `not yet recorded`, which is
printed as it stands: a value nobody has looked up is never guessed. The default profile and a
standard's project settings also set sections a repository's own profile in a standard for several
may not: `issue_tracker` (the tracker's `kind`, `jira` or `github`; for GitHub, the `location`
whose issues the project's are, `owner/repo`, when not each repository's own; the workflow's
statuses, a Jira status or a GitHub label each, each with the phase a ticket with no context page
goes to and, for some, the role a generic skill names it by; and the statuses at which its pull
request may exist) and `internal` (the domains no posted text may name, and the private
repositories, by name: for one of those `public` is false, and a profile that sets it true is
refused). Neither is printed for a repository. A file's `jira:` section is read as
`issue_tracker:` with `kind: jira`, once the files are stacked; one that sets both, or a `kind` or
`location` under `jira:`, is refused, and a refusal names its fields as `issue_tracker.<field>
(jira:)`. With no `location`, it prints `none`. The default profile's
`issue_tracker` reads `not yet recorded`, so where no standard records a workflow, a field under it
prints `not yet recorded`; a standard that records one sets its `kind`, `statuses` and
`pr_statuses`. For Jira, each of the roles in `ROLES` is on exactly one status; for GitHub, on at
most one label, a role with none reading `none`, since an issue's own open and closed states stand
for filed, finished and abandoned. `--defaults` prints them as `issue_tracker.roles`, so
`--defaults --field issue_tracker.roles.finished` prints the finished status's name. `--field
jira.<field>` reads `issue_tracker.<field>` when its kind is `jira`, and `not yet recorded`
otherwise.

With `--field a.b` it prints that one value: a scalar as it is, a list one item per line (a map
item as JSON), a section as `key.path: value` lines. Without it, the whole profile as
`key.path: value` lines, after a first line `source: <the standard's files read in 1, joined by
`, `>`, a fetched one's as `<owner>/<repo>@<sha>:standards/<file>`; or `source: none` when there
is none and every value is the detected or the default profile's; `--field source` prints that
value alone. With `--defaults` in place of the repository, the default profile's values under the
working directory's repository's standard's, with no `source` line.
The file is a small subset of YAML, read by the parser below: top-level keys, maps two levels
deep, scalars, flow lists, and block lists of scalars or one-line flow maps. A key the schema does not know, a value of the wrong shape, or a line the parser cannot
read exits 1 naming it, as does a `ticket.pattern` or a `depth.light` entry's `hunk` that is not a
regular expression, and a default profile under a standard's settings that leaves a key out, has a
section other than `issue_tracker` reading `not yet recorded`, leaves a field of
`issue_tracker`, `internal`, `attribution` or `surface` unrecorded (a `location` may be left out, never unrecorded), names a
tracker kind other than `jira` or `github`, a location that is not `owner/repo` or one for Jira, a
GitHub label `none`, names a status twice or with spaces around it, gives a status a role not in `ROLES`, gives a role two statuses or,
for Jira, none, names a pull request status that is not one of its statuses, names a domain that is not a bare host name, or a private repository that is
not a bare repository name. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

NOT_RECORDED = "not yet recorded"

# Each key's shape: a section maps its subkeys to theirs. "str", "bool", "list" (of strings) and
# "light" (a list of {glob, brief, hunk?} maps).
SCHEMA: dict = {
    "ticket": {"pattern": "str", "project": "str"},
    "public": "bool",
    "template": "str",
    "downstream": "list",
    "tests": {"command": "str"},
    "coverage": {"command": "str"},
    "lint": {"command": "str", "regex": "str"},
    "types": {"regex": "str"},
    "gates": {"tests": "str"},
    "github_server": "str",
    "posted_text": "str",
    "depth": {"light": "light", "deep": "list"},
}

# The values under every standard's, relative to the plugin's top level.
DEFAULT_PROFILE = "standards/default-profile.yaml"
# The detected values' cache, under the checkout's git directory.
DETECTED = "lasp-dev/detected"
# A repository's own settings, or its pointer to the standard elsewhere, in its checkout.
REPO_PROFILE = "standards/profile.yaml"
POINTER = "standard"
# Keys a repository's own profile in a standard for several does not set, the project's: its issue
# tracker's workflow, its internal hosts and its private repositories, by name whatever the owner; the
# wordings beside the plugin's attribution line that mark a comment as AI-drafted (record.py); and
# the enum classes whose members are data product identifiers (surface_diff.py).
PROJECT_SCHEMA: dict = {
    "issue_tracker": {"kind": "str", "location": "str", "statuses": "statuses", "pr_statuses": "list"},
    "internal": {"domains": "list", "private_repositories": "list"},
    "attribution": {"phrases": "list"},
    "surface": {"identifiers": "list"},
}
# The settings every repository a standard covers shares: in a standard for several, only its
# profile.yaml sets them, and only its profiles/<repo>.yaml sets the rest.
# The name `issue_tracker` had when Jira was the only tracker; a file's `jira:` is read as
# `issue_tracker:` with `kind: jira`.
ALIAS = "jira"
PROJECT_KEYS = ("ticket", "posted_text", "github_server", "issue_tracker", ALIAS, "internal", "attribution", "surface")
# The issue_tracker fields a standard may leave out: with no location, each repository's own issues.
OPTIONAL = {"issue_tracker.location"}
# Set to 1, as a hook runs, to read a standard elsewhere only as already fetched.
OFFLINE = "STANDARD_OFFLINE"
# The source of a pointing repository read without its standard, the person's choice.
UNREAD = "'s standard, not read (lasp-dev.standard is none)"
PHASES = {"ticket-draft", "implement-change", "nothing"}
# The roles generic skills name a status by, each on exactly one status: the status a ticket is
# filed in, the one a ticket writer's approval moves it to, the one its implementation is under,
# and the ones a ticket closes to with its work done and with its work not done.
ROLES = ("filed", "approved", "implementation", "finished", "abandoned")
REPO = re.compile(r"[A-Za-z0-9._-]+")
OWNER = re.compile(r"[A-Za-z0-9-]+")
OWNER_REPO = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+")
# The owner and repository at the end of a remote's URL: git@github.com:owner/repo.git,
# https://github.com/owner/repo or ssh://git@github.com/owner/repo.git.
REMOTE = re.compile(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$")
# A template is a directory of the standard's templates/ by its bare name.
TEMPLATE = re.compile(r"[A-Za-z0-9_-]+")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
HOST = re.compile(r"(?i)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+")

CHOICES = {"posted_text": {"workflow", "plain"}, "issue_tracker.kind": {"jira", "github"}}
# The keys a file may set: the alias takes the section's shape, and `folded` refuses its kind and location.
FILE_SCHEMA: dict = {**SCHEMA, **PROJECT_SCHEMA, ALIAS: PROJECT_SCHEMA["issue_tracker"]}
LIGHT_KEYS = {"glob", "brief", "hunk"}


class ProfileError(Exception):
    """A profile the parser or the schema refuses."""


def strip_comment(line: str) -> str:
    """The line without a `#` comment that starts outside quotes, at its start or after a space."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def split_flow(inner: str) -> list[str]:
    """Split the inside of a flow list or map on commas outside quotes and braces."""
    parts, depth, quote, start = [], 0, None, 0
    for i, ch in enumerate(inner):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(inner[start:i])
            start = i + 1
    parts.append(inner[start:])
    return [p.strip() for p in parts if p.strip()]


def split_key(text: str, where: str) -> tuple[str, str]:
    m = re.match(r"([A-Za-z_][\w-]*):(?:\s+(.*))?$", text)
    if not m:
        raise ProfileError(f"{where}: not a `key: value` line: {text!r}")
    return m.group(1), (m.group(2) or "").strip()


def value(text: str, where: str):
    if text.startswith("["):
        if not text.endswith("]"):
            raise ProfileError(f"{where}: an unclosed flow list: {text!r}")
        return [value(p, where) for p in split_flow(text[1:-1])]
    if text.startswith("{"):
        if not text.endswith("}"):
            raise ProfileError(f"{where}: an unclosed flow map: {text!r}")
        return dict((k, value(v, where)) for k, v in (split_key(p, where) for p in split_flow(text[1:-1])))
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if text in ("true", "false"):
        return text == "true"
    return text


def parse(text: str, name: str) -> dict:
    """The profile as nested dicts and lists, from the subset of YAML the profiles use."""
    data: dict = {}
    section = sub = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw).rstrip()
        if not line.strip():
            continue
        where = f"{name}:{n}"
        indent, body = len(line) - len(line.lstrip(" ")), line.strip()
        if indent == 0:
            key, rest = split_key(body, where)
            if key in data:
                raise ProfileError(f"{where}: {key} is given twice")
            data[key] = value(rest, where) if rest else {}
            section, sub = (key if not rest else None), None
        elif indent == 2 and section is not None and body.startswith("- "):
            if data[section] == {}:
                data[section] = []
            if not isinstance(data[section], list):
                raise ProfileError(f"{where}: a list item under the map {section}")
            data[section].append(value(body[2:].strip(), where))
        elif indent == 2 and section is not None and isinstance(data[section], dict):
            key, rest = split_key(body, where)
            if key in data[section]:
                raise ProfileError(f"{where}: {section}.{key} is given twice")
            data[section][key] = value(rest, where) if rest else []
            sub = key if not rest else None
        elif indent == 4 and sub is not None and body.startswith("- "):
            data[section][sub].append(value(body[2:].strip(), where))
        else:
            raise ProfileError(f"{where}: a line the profile parser does not read: {raw.strip()!r}")
    return data


def check(data: dict, name: str, schema: dict = SCHEMA) -> None:
    """Refuse a key the schema does not know, or a value of the wrong shape."""
    for key, got in data.items():
        if key not in schema:
            raise ProfileError(f"{name}: unknown key {key!r}")
        shape = schema[key]
        if got == NOT_RECORDED:
            continue
        if isinstance(shape, dict):
            if not isinstance(got, dict):
                raise ProfileError(f"{name}: {key} is a section of {', '.join(shape)}, not {got!r}")
            for sub, v in got.items():
                path = f"issue_tracker.{sub} ({ALIAS}:)" if key == ALIAS else f"{key}.{sub}"
                if sub not in shape:
                    raise ProfileError(f"{name}: unknown key '{path}'")
                check_leaf(path, shape[sub], v, name)
        else:
            check_leaf(key, shape, got, name)


def check_leaf(path: str, shape: str, got, name: str) -> None:
    if got == NOT_RECORDED:
        return
    ok = {
        "str": isinstance(got, str),
        "bool": isinstance(got, bool),
        "list": isinstance(got, list) and all(isinstance(v, str) for v in got),
        "light": isinstance(got, list)
        and all(
            isinstance(v, dict) and {"glob", "brief"} <= set(v) <= LIGHT_KEYS and all(isinstance(x, str) for x in v.values())
            for v in got
        ),
        "statuses": isinstance(got, list)
        and all(
            isinstance(v, dict)
            and set(v) in ({"name", "next"}, {"name", "next", "role"})
            and all(isinstance(x, str) for x in v.values())
            and v["next"] in PHASES
            for v in got
        ),
    }[shape]
    if not ok:
        raise ProfileError(f"{name}: {path} should be {shape}, not {got!r}")
    if path == "template" and not TEMPLATE.fullmatch(got):
        raise ProfileError(f"{name}: template is a bare name such as my_team, not {got!r}")
    allowed = CHOICES.get(path)
    if allowed and any(v not in allowed for v in (got if isinstance(got, list) else [got])):
        raise ProfileError(f"{name}: {path} takes {', '.join(sorted(allowed))}, not {got!r}")
    if path == "ticket.pattern":
        patterns = [got]
    elif path == "depth.light":
        patterns = [e["hunk"] for e in got if "hunk" in e]
    else:
        patterns = []
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as e:
            raise ProfileError(f"{name}: {path} has {pattern!r}, which is not a regular expression: {e}") from e


def repo_name(repo: str) -> str:
    """The name part of an `owner/repo` argument; one that is not a bare repository name is refused."""
    name = repo.rstrip("/").split("/")[-1]
    if not REPO.fullmatch(name) or name.endswith(".git"):
        raise ProfileError(f"{repo!r}: its name part is not a bare repository name such as my_repo")
    return name


def git(*args: str) -> str | None:
    """A git command's output in the working directory, stripped, or None when it fails; with no
    git to run, raises ProfileError, since then no repository can be told from another."""
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True)
    except OSError as e:
        raise ProfileError(f"git cannot be run: {e}") from e
    return out.stdout.strip() if out.returncode == 0 else None


def remote(name: str) -> tuple[str, str] | None:
    """The owner and repository the working directory's git remote `name` points at, or None when
    there is no such remote or its URL ends in no owner and repository."""
    found = REMOTE.search(git("remote", "get-url", name) or "")
    return (found.group(1), found.group(2)) if found else None


def owners(repo: str | None) -> tuple[str, ...]:
    """The run's owner: the argument's, or the `origin` remote's when the argument names none and
    `origin` is a repository of the same name, or when there is no argument; none otherwise."""
    parts = repo.rstrip("/").split("/") if repo else []
    if len(parts) >= 2:
        return (parts[-2],) if repo_name(repo) else ()
    origin = remote("origin")
    name = repo_name(repo) if repo else (origin[1] if origin else None)
    return (origin[0],) if origin and name and origin[1].lower() == name.lower() else ()


def checkout(repo: str | None, run_owners: tuple[str, ...]) -> Path | None:
    """The working directory's checkout when it is the repository, `repo`'s name, or the `origin`
    remote's when None, and one of the run's owners; None for any other directory."""
    top = git("rev-parse", "--show-toplevel")
    origin = remote("origin")
    name = repo_name(repo) if repo else (origin[1] if origin else "")
    if not top or not origin or origin[1].lower() != name.lower() \
            or origin[0].lower() not in {o.lower() for o in run_owners}:
        return None
    return Path(top)


def local(repo: str | None, run_owners: tuple[str, ...]) -> tuple[dict, list[str], Path | None]:
    """The settings of the standard the working directory's checkout keeps, when it is the
    repository, `repo`'s name and one of the run's owners: its own `standards/`, or the one its
    pointer names; with the files they came from, for the `source` line, and the directory of a
    standard elsewhere, None for its own or none. For another repository of the run's owners, the
    settings that standard gives it when its `profiles/` covers it, as a revision harvesting every
    repository a standard covers reads them. {} with no standard, no checkout, or a standard that
    does not cover `repo`. A file the parser or the schema refuses, a setting in the wrong file,
    and a pointer that cannot be read or fetched raise ProfileError, for a query about another
    repository of the same owner too: no standard's values are guessed."""
    top = checkout(repo, run_owners)
    sibling = top is None
    if sibling:
        top = checkout(None, run_owners) if repo else None
        if top is None:
            return {}, [], None
    name = repo_name(repo) if repo else remote("origin")[1]
    found = standard_of(top)
    if found is None:
        return {}, [], None
    directory, label, pointed = found
    if directory is None:
        return ({}, [], None) if sibling else ({}, [label], None)
    if sibling and not any(p.stem.lower() == name.lower() for p in (directory / "profiles").glob("*.yaml")):
        return {}, [], None
    values, sources = settings(directory, name, label, pointed or sibling)
    return values, sources, directory if pointed else None


def standard_of(top: Path) -> tuple[Path | None, str, bool] | None:
    """The standard the checkout at `top` keeps: its directory, the label its files are named
    after, and whether its pointer led there; the directory None and the label `<owner>/<repo>`
    marked unread when the person chose to go on without it; None with no standard."""
    own = parse((top / REPO_PROFILE).read_text(), REPO_PROFILE) if (top / REPO_PROFILE).is_file() else {}
    if POINTER not in own:
        return (top / "standards", "standards/", False) if (top / "standards").is_dir() else None
    named = own[POINTER]
    if set(own) != {POINTER} or not isinstance(named, str) or not OWNER_REPO.fullmatch(named):
        raise ProfileError(f"{REPO_PROFILE}: holds a standard: line, so it holds that one line alone, standard: <owner>/<repo>")
    beside = [f for f in ("review-rules.md", "decisions.md", "agent-guidance.md", "data-conventions.md") if (top / "standards" / f).is_file()]
    if beside:
        raise ProfileError(f"{REPO_PROFILE} names the standard {named}, and standards/{beside[0]} is here too; a repository's standard is in one place")
    script = Path(__file__).resolve().parent / "standard.sh"
    out = subprocess.run(["bash", str(script), "--offline" if os.environ.get(OFFLINE) == "1" else "--cached"],
                         cwd=top, capture_output=True, text=True)
    if out.returncode:
        raise ProfileError(out.stderr.strip() or f"standard.sh exited {out.returncode}")
    fields = out.stdout.rstrip("\n").split("\t")
    if len(fields) != 3:
        raise ProfileError(f"standard.sh printed {out.stdout.strip()!r}, not <owner>/<repo>, the directory and the commit")
    _, directory, version = fields
    if version == "none":
        return None, f"{named}{UNREAD}", True
    label = f"{named} at {directory} (local):" if version == "local" else f"{named}@{version[:7]}:standards/"
    return Path(directory), label, True


def standard_directory(repo: str | None, root: Path) -> Path:
    """The absolute path of the standard the working directory's checkout keeps, when it is `repo`,
    or the `origin` remote's repository when None: the fetched standard its pointer names, as of the
    last fetch, or its own `standards/` as it stands. A checkout with neither raises ProfileError
    ending "the repository has no standard"; any other ProfileError is a refusal, among them every
    refusal of the repository's profile under the plugin top level `root`, what is detected aside,
    so a standard that does not cover the repository or that the schema refuses is never printed."""
    run_owners = owners(repo)
    top = checkout(repo, run_owners)
    if top is None:
        raise ProfileError(f"the working directory is not a checkout of {repo or 'a repository on a GitHub remote'}")
    found = standard_of(top)
    if found is None:
        raise ProfileError(f"{top} has no standards/ and no standard: pointer; the repository has no standard")
    directory, label, _ = found
    if directory is None:
        raise ProfileError(label)
    resolve(repo or "/".join(remote("origin")), root, detect=False)
    return directory.resolve()


def one_tracker(data: dict, name: str) -> None:
    """Refuse a file that sets the tracker under both its names, in any form."""
    if ALIAS in data and "issue_tracker" in data:
        raise ProfileError(f"{name}: sets issue_tracker twice, as issue_tracker: and as {ALIAS}:, its alias; keep one")


def settings(directory: Path, name: str, label: str, pointed: bool) -> tuple[dict, list[str]]:
    """The settings the standard in `directory` gives the repository `name`, and the files they
    came from, each named after `label`; `pointed` when another repository's pointer led here."""
    schema = FILE_SCHEMA
    sources: list[str] = []
    project: dict = {}
    if (directory / "profile.yaml").is_file():
        project = parse((directory / "profile.yaml").read_text(), f"{label}profile.yaml")
        if POINTER in project:
            raise ProfileError(f"{label}profile.yaml names another standard; a pointer is followed one level")
        check(project, f"{label}profile.yaml", schema)
        one_tracker(project, f"{label}profile.yaml")
        sources.append(f"{label}profile.yaml")
    if not (directory / "profiles").is_dir():
        if pointed:
            raise ProfileError(f"{label} has no profiles/, so the standard covers only its own repository, not {name}")
        return project, sources
    misplaced = [k for k in project if k not in PROJECT_KEYS]
    if misplaced:
        raise ProfileError(f"{label}profile.yaml sets {', '.join(misplaced)}, which a repository sets; "
                           f"in a standard with profiles/, each repository's settings are in profiles/<repo>.yaml")
    mine = [p for p in (directory / "profiles").glob("*.yaml") if p.stem.lower() == name.lower()]
    if len(mine) > 1:
        raise ProfileError(f"{label} has {', '.join(sorted(p.name for p in mine))} in profiles/, one repository's settings twice")
    if not mine:
        if not pointed:
            # The standard's own repository, which the standard need not cover: the project's settings.
            return project, sources
        raise ProfileError(f"{label} has no profiles/{name}.yaml, so the standard does not cover {name}")
    rel = f"{label}profiles/{mine[0].name}"
    data = parse(mine[0].read_text(), rel)
    check(data, rel, schema)
    one_tracker(data, rel)
    misplaced = [k for k in data if k in PROJECT_KEYS]
    if misplaced:
        raise ProfileError(f"{rel} sets {', '.join(misplaced)}, which the project sets; it belongs in {label}profile.yaml")
    sources.append(rel)
    return stacked(project, data), sources


def detected(repo: str, run_owners: tuple[str, ...], root: Path, mine=lambda: ({}, [], None)) -> dict:
    """The keys `survey.py --drop-in` fills for the working directory's checkout, when it is the
    repository: `repo`'s name and one of the run's owners; {} for any other directory. Cached in the
    checkout's git directory, outside the working tree, under the commit and a hash of the files
    that decide the values, so a new commit, a deepened shallow clone or a plugin that detects
    differently surveys again; the survey reads the plugin top level `root`, and the hash covers it
    and the standard's settings, `mine()` as `local` gives them, which the survey's values read; the
    survey writes beside the cache and the file is moved into place whole. A survey that fails
    raises ProfileError: a value it cannot detect is left out, never guessed."""
    found = checkout(repo, run_owners)
    if found is None:
        return {}
    top = str(found)
    head = git("rev-parse", "--verify", "HEAD")
    if not head:
        raise ProfileError(f"{top} has no commit, so nothing about it can be detected")
    here = Path(__file__).resolve().parent
    detector = hashlib.sha1()
    for path in (here / "survey.py", here / "profile.py", root / DEFAULT_PROFILE):
        detector.update(path.read_bytes() if path.is_file() else b"-")
    detector.update(json.dumps(mine()[:2], sort_keys=True).encode())
    # The survey reads history, so a shallow clone's boundary is part of what decides the values.
    shallow = Path(git("rev-parse", "--git-path", "shallow") or "")
    if shallow.is_file():
        detector.update(shallow.read_bytes())
    gitdir = git("rev-parse", "--absolute-git-dir")
    if not gitdir:
        raise ProfileError(f"{top}: git names no git directory for the checkout")
    top_level = hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:8]
    cache = Path(gitdir) / DETECTED / f"{head}-{top_level}-{detector.hexdigest()[:8]}.yaml"
    if not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        partial = cache.with_name(f"{cache.name}.{os.getpid()}.tmp")
        out = subprocess.run([sys.executable, str(here / "survey.py"), "--repo", top, "--root", str(root), "--drop-in", str(partial)],
                             capture_output=True, text=True)
        if out.returncode:
            partial.unlink(missing_ok=True)
            raise ProfileError(f"survey.py could not read {top}: {out.stderr.strip()}")
        os.replace(partial, cache)
        # Only the commit checked out is read, so an older commit's values go, and this top level's
        # under another hash, while the same commit's for another top level stay; and a
        # survey's file left by a process stopped mid-survey goes once it is a minute old.
        for old in cache.parent.iterdir():
            try:
                stale = not old.name.startswith(f"{head}-") or old.name.startswith(f"{head}-{top_level}-")
                if old.suffix == ".yaml" and old != cache and stale or old.suffix == ".tmp" and time.time() - old.stat().st_mtime > 60:
                    old.unlink(missing_ok=True)
            except FileNotFoundError:
                pass  # another survey moved its file into place since the listing
    data = parse(cache.read_text(), str(cache))
    check(data, str(cache))
    return data


def overlay(base: dict, top: dict) -> dict:
    """`base` with each key `top` gives in its place; a section `top` gives in part keeps the rest."""
    out: dict = {}
    for key, default in base.items():
        got = top.get(key)
        if isinstance(default, dict) and isinstance(got, dict):
            out[key] = {**default, **got}
        else:
            out[key] = default if got is None else got
    return out


def stacked(*layers: dict) -> dict:
    """Each layer's keys over the earlier layers'; a section a later layer gives in part keeps the rest."""
    out: dict = {}
    for top in layers:
        for key, got in top.items():
            out[key] = {**out[key], **got} if isinstance(out.get(key), dict) and isinstance(got, dict) else got
    return out


def nothing() -> tuple[dict, list[str], Path | None]:
    return {}, [], None


def once(ask):
    """`ask`, called at most once, on the first call that needs it, for each plugin top level it is
    given; its value, or the error it raised, raised again, is the answer to every later call."""
    kept: dict = {}

    def answer(root: Path | None = None):
        if root not in kept:
            try:
                kept[root] = (ask(root) if root is not None else ask(), None)
            except (ProfileError, OSError) as e:
                kept[root] = (None, e)
        value, error = kept[root]
        if error is not None:
            raise error
        return value

    return answer


def defaults_here(root: Path, mine=nothing) -> dict:
    """The default profile's values for every key under the standard's, `mine()` as `local` gives
    them, from the plugin's top level `root` alone."""
    values, sources, _ = mine()
    data = parse((root / DEFAULT_PROFILE).read_text(), DEFAULT_PROFILE)
    return valid(stacked(data, values), " over ".join([*sources, DEFAULT_PROFILE]))


def folded(data: dict, name: str) -> tuple[dict, bool]:
    """`data` with a `jira:` section read as `issue_tracker:` with `kind: jira`, and whether it had one."""
    if ALIAS not in data:
        return data, False
    rest = {k: v for k, v in data.items() if k != ALIAS}
    jira = data[ALIAS]
    if isinstance(jira, dict):
        if "kind" in jira:
            raise ProfileError(f"{name}: issue_tracker.kind ({ALIAS}:) is set by the alias; drop it, or write issue_tracker: to name another")
        if "location" in jira:
            raise ProfileError(f"{name}: issue_tracker.location ({ALIAS}:) names a GitHub repository; "
                               "a Jira tracker's project is ticket.project")
        jira = {"kind": "jira", **jira}
    return {**rest, "issue_tracker": jira}, True


def valid(data: dict, name: str) -> dict:
    """`data`, the values for every key named by `name`, the default profile under a standard's
    settings, checked, with the roles added under `issue_tracker`, which may read `not yet recorded`."""
    schema = {**SCHEMA, **PROJECT_SCHEMA}
    data, aliased = folded(data, name)
    check(data, name, schema)
    # A field of a section a file wrote as `jira:` is named as the section it is read as.
    tag = f" ({ALIAS}:)" if aliased else ""

    def field(sub: str) -> str:
        return f"issue_tracker.{sub}{tag}"

    missing = [key for key in schema if key not in data]
    missing += [field(sub) if key == "issue_tracker" else f"{key}.{sub}" for key, shape in schema.items()
                if isinstance(shape, dict) and isinstance(data.get(key), dict)
                for sub in shape if sub not in data[key] and f"{key}.{sub}" not in OPTIONAL]
    # A section must be written out, since a profile's own subkey merges into it; a field may read
    # `not yet recorded`.
    missing += [f"{key} (it reads {NOT_RECORDED})" for key, shape in schema.items()
                if isinstance(shape, dict) and data.get(key) == NOT_RECORDED and key != "issue_tracker"]
    if missing:
        raise ProfileError(f"{name}: leaves out {', '.join(missing)}; the default profile sets every key, and a standard sets a section whole")
    # The project's fields are the facts a script acts on, so none may be left unrecorded.
    unrecorded = [field(sub) if key == "issue_tracker" else f"{key}.{sub}"
                  for key in PROJECT_SCHEMA if isinstance(data[key], dict) for sub, v in data[key].items() if v == NOT_RECORDED]
    if unrecorded:
        raise ProfileError(f"{name}: {', '.join(unrecorded)} reads {NOT_RECORDED}; a script acts on it, so it is recorded")
    tracker = data["issue_tracker"]
    if tracker != NOT_RECORDED:
        kind = tracker["kind"]
        location = tracker.get("location")
        if location is not None and kind == "jira":
            raise ProfileError(f"{name}: {field('location')} names a GitHub repository; a Jira tracker's project is ticket.project")
        if location is not None and not OWNER_REPO.fullmatch(location):
            raise ProfileError(f"{name}: {field('location')} is owner/repo, such as my_org/my_repo, not {location!r}")
        names = [s["name"] for s in tracker["statuses"]]
        bad = [n for n in names if not n or n != n.strip()]
        if bad:
            raise ProfileError(f"{name}: {field('statuses')} has a name that is empty or has spaces around it: {bad!r}")
        # A role with no label prints `none`, so no label may be named that.
        if kind == "github" and any(n.lower() == "none" for n in names):
            raise ProfileError(f"{name}: {field('statuses')} has a label named none, which reads as a role with no label")
        seen: set = set()
        twice = [n for n in names if n.lower() in seen or seen.add(n.lower())]
        if twice:
            raise ProfileError(f"{name}: {field('statuses')} names {', '.join(twice)} twice")
        for s in tracker["statuses"]:
            if s.get("role", ROLES[0]) not in ROLES:
                raise ProfileError(f"{name}: {field('statuses')} gives {s['name']} the role {s['role']!r}, not one of {', '.join(ROLES)}")
        for role in ROLES:
            holders = [s["name"] for s in tracker["statuses"] if s.get("role") == role]
            if len(holders) > 1 or not holders and kind == "jira":
                raise ProfileError(f"{name}: {field('statuses')} gives the role {role} to {', '.join(holders) or 'no status'}; "
                                   f"it takes {'exactly' if kind == 'jira' else 'at most'} one")
        stray = [s for s in tracker["pr_statuses"] if s.lower() not in seen]
        if stray:
            raise ProfileError(f"{name}: {field('pr_statuses')} names {', '.join(stray)}, not in {field('statuses')}")
        roles = {s["role"]: s["name"] for s in tracker["statuses"] if "role" in s}
        data["issue_tracker"] = {"kind": kind, "location": location or "none", "statuses": tracker["statuses"],
                                 "pr_statuses": tracker["pr_statuses"], "roles": {role: roles.get(role, "none") for role in ROLES}}
    hosts = [d for d in data["internal"]["domains"] if not HOST.fullmatch(d)]
    if hosts:
        raise ProfileError(f"{name}: internal.domains has {hosts!r}, not a bare host name such as example.org")
    repos = [r for r in data["internal"]["private_repositories"] if not REPO.fullmatch(r)]
    if repos:
        raise ProfileError(f"{name}: internal.private_repositories has {repos!r}, not a bare repository name such as my_repo")
    blank = [v for v in data["attribution"]["phrases"] if not v.strip()]
    if blank:
        raise ProfileError(f"{name}: attribution.phrases has an empty phrase")
    classes = [v for v in data["surface"]["identifiers"] if not IDENTIFIER.fullmatch(v)]
    if classes:
        raise ProfileError(f"{name}: surface.identifiers has {classes!r}, not a Python class name such as ProductId")
    return {key: data[key] for key in schema}


def resolve_here(repo: str, root: Path, found=lambda r: {}, mine=nothing) -> dict:
    """The repository's standard's settings over what was `found(root)` in its checkout, over the
    default profile's; under the plugin's top level alone."""
    values = defaults_here(root, mine)
    data = stacked(found(root), mine()[0])
    name = repo_name(repo).lower()
    private = name in {r.lower() for r in values["internal"]["private_repositories"]}
    if private and data.get("public") is True:
        said = " over ".join([*mine()[1], "the detected values"])
        listed = " over ".join([*mine()[1], DEFAULT_PROFILE])
        raise ProfileError(f"{said}: public is true, but {listed} lists the repository as private")
    out = overlay({k: v for k, v in values.items() if k in SCHEMA}, data)
    if private:
        out["public"] = False
    return out


def defaults(root: Path, repo: str | None = None) -> dict:
    """The default profile's values under the standard of `repo`, or of the working directory's
    repository when None."""
    run_owners = owners(repo)
    return defaults_here(root, once(lambda: local(repo, run_owners)))


def resolve(repo: str, root: Path, detect: bool = True) -> dict:
    """The repository's profile: its standard's settings over what its checkout states and the
    default profile's. `detect` False leaves the checkout's history and files unsurveyed, as
    `survey.py`, which does the detecting, asks; its own facts are read either way."""
    run_owners = owners(repo)
    mine = once(lambda: local(repo, run_owners))
    found = once(lambda r: detected(repo, run_owners, r, mine) if detect else {})
    return resolve_here(repo, root, found, mine)


def render(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(json.dumps(i) if isinstance(i, dict) else i for i in v) + "]"
    return str(v)


def lines(prefix: str, v) -> list[str]:
    if isinstance(v, dict):
        return [line for k, sub in v.items() for line in lines(f"{prefix}.{k}" if prefix else k, sub)]
    return [f"{prefix}: {render(v)}"]


def answer(args: argparse.Namespace, root: Path, found, mine) -> tuple[int, str, str]:
    """The exit status, output and error the question gets from the plugin top level `root` alone."""
    try:
        profile = defaults_here(root, mine) if args.defaults else resolve_here(args.repo, root, found, mine)
        if not args.defaults:
            profile = {"source": ", ".join(mine()[1]) or "none", **profile}
    except (ProfileError, OSError) as e:
        return 1, "", f"profile.py: {e}\n"
    if not args.field:
        return 0, "\n".join(lines("", profile)) + "\n", ""
    tracker = {**PROJECT_SCHEMA["issue_tracker"], "roles": dict.fromkeys(ROLES, "scalar")}
    v, shape = profile, {**SCHEMA, **PROJECT_SCHEMA, "issue_tracker": tracker}
    parts = args.field.split(".")
    if parts[0] == ALIAS and "issue_tracker" in profile:
        # The old name reads the tracker only when it is Jira's.
        given = profile["issue_tracker"]
        jira = given if isinstance(given, dict) and given["kind"] == "jira" else NOT_RECORDED
        v, shape = {**profile, ALIAS: jira}, {**shape, ALIAS: tracker}
    for part in parts:
        # A field under a section that reads `not yet recorded` is not recorded either.
        if v == NOT_RECORDED and isinstance(shape, dict) and part in shape:
            shape = shape[part]
            continue
        shape = shape.get(part) if isinstance(shape, dict) else None
        if not isinstance(v, dict) or part not in v:
            return 1, "", f"profile.py: no field {args.field!r}\n"
        v = v[part]
    if isinstance(v, dict):
        return 0, "\n".join(lines(args.field, v)) + "\n", ""
    if isinstance(v, list):
        return 0, "".join((json.dumps(i) if isinstance(i, dict) else i) + "\n" for i in v), ""
    return 0, render(v) + "\n", ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("repo", nargs="?", help="owner/repo, as `git remote get-url origin` names it, without `.git`")
    p.add_argument("--defaults", action="store_true", help="the default profile's values under the standard's, for no repository")
    p.add_argument("--standard", action="store_true", help="print the standard's directory's absolute path, and nothing else")
    p.add_argument("--field", help="one dotted key, such as ticket.pattern")
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="the plugin's top level")
    args = p.parse_args(argv)
    args.root = args.root.resolve()
    if args.standard:
        if args.defaults or args.field:
            p.error("--standard takes no --defaults or --field")
        try:
            print(standard_directory(args.repo, args.root))
        except (ProfileError, OSError) as e:
            print(f"profile.py: {e}", file=sys.stderr)
            return 1
        return 0
    if bool(args.repo) == args.defaults:
        p.error("give a repository or --defaults, one of them")
    try:
        run_owners = owners(args.repo)
    except (ProfileError, OSError) as e:
        print(f"profile.py: {e}", file=sys.stderr)
        return 1
    mine = once(lambda: local(args.repo, run_owners))
    found = once(lambda r: {} if args.defaults else detected(args.repo, run_owners, r, mine))
    rc, out, err = answer(args, args.root, found, mine)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return rc

if __name__ == "__main__":
    raise SystemExit(main())
