---
name: using-github
description: >
  How the plugin reaches GitHub: the server by repository owner, the `gh` alternative, an
  unreachable server and the push stop. Applies whenever a skill or agent uses GitHub.
user-invocable: false
metadata:
  author: dev-tools
  version: 1.1.1
---

## Resolving the tools

Resolve the GitHub tools with `ToolSearch` by what a tool does (`pull request read`, `get me`),
never by a server prefix: the server can be registered under any name. Resolve the write tools
the skill will post with (a review, a reply, creating or updating a pull request) at the same
time, so a server without them is known before any work. Call `get_me` to confirm the server
answers and to record the login, which goes in every attribution line. A skill resolves the
tools at the first step that reads GitHub, not before work that needs none.

## Picking the server

A `github_server` in the repository's profile, which
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo>` prints, names the server and
ends the search. Otherwise,
with one GitHub server, use it whatever its name. With more than one, use the one whose name
contains the repository owner, case aside, or the owner's last hyphenated part (`github-widgets`
for Example-Widgets). When none of them does, ask, naming the servers found, rather than guessing;
an agent returns the question to its caller. A 404 or 403 from the server that matched, on a
repository that exists, is reported with the servers' names, never retried on another server by
guess.

## Default and alternative

The MCP server by default. `gh` once the person has said so in this session; agents still only
read, and every write still waits for the person's yes. A post goes through the same server, or
`gh`, as the reads.

`gh` cannot build the thread table: `pr-reader` reads the MCP server's output, and told
`GitHub: gh` it returns one refusal line (`ROADMAP.md`, the `gh api` adapter). A step that needs
the table stops there on `gh`; each skill says which of its steps that is.

## When the server cannot be reached

A server stops a skill only at the step that reads from it; elsewhere the skill goes on and names
what it skipped. Say so as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out: which case it is, what is lost, whether the run goes on, and the fix,
with `/lasp-dev:quickstart`, the README's "MCP servers" and Claude Code's MCP guide. At the
step that needs the server, stop and offer the `gh` CLI; then wait. If `gh` is chosen and is
missing or unauthenticated, say so in one line, name `gh auth login`, and stop. An agent returns
the message to its caller and ends, without troubleshooting or reviewing from local state; the
caller asks the person.

## Passing it down

Tell every agent a skill spawns `GitHub: <server name>` or `GitHub: gh`. The agent reads with
that and nothing else.

## Pushing

A push waits for a yes that names it; it may share an option with the action that needs it, as
the gates in `skills/work/decision-points.md` allow. Where the repository's loaded instructions
(`CLAUDE.md` and what it imports, `AGENTS.md`) forbid an agent to push: print the exact command,
wait until the person says it is pushed, check that the remote has the commits, and go on.
