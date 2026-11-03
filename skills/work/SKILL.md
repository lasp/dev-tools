---
name: work
description: >
  Takes a ticket, or its pull request, through the standards workflow: works out where it stands
  and runs the next phase skill. Use when asked to "work this ticket", "continue PROJ-42",
  "what's next on this ticket", "what's next on this PR" or "pick up where I left off".
argument-hint: "[ticket key | PR number | nothing]"
metadata:
  author: dev-tools
  version: 1.8.0
---

# Work

A ticket goes through three sittings. **The author**: `work <ticket key>` takes it to an approved
plan, builds, opens a draft pull request and reviews it, posting the findings when they choose
to; on a draft, the author answers their own review first, then marks it ready. **Reviewers, on
GitHub**: they say under each finding, in their own words, whether they agree, disagree and why,
or want to discuss, without Claude Code. **The author again**: `work` dispositions every thread
with them, fixes the agreed ones and replies on each. Then a person merges.

This skill decides which phase runs next and runs it. It copies none of their steps: plan
approval, diff approval, every yes before something is pushed or posted, and the replies all
happen inside the phase skill, exactly as when it is typed alone. Every question, and every file
it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`.

## Options

| Option | Default |
|---|---|
| What to work on | A ticket key, a pull request number or URL, or nothing, as step 1 resolves it |

## 1. What to work on

In a repository with no `standards/review-rules.md` and no `standard:` pointer in `standards/profile.yaml`, the reply's first line is this, word for
word, before anything else, including a question about which ticket: "no rules file here: the
build, the pull request and a review run without rule citations".

The argument is a ticket key, a pull request number or URL, or nothing. With nothing, the
ticket is the key the branch name starts with, in any letter case, upper-cased unless the pattern matches it
as written, in the ticket key pattern the profile sets
(`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field ticket.pattern`), after a `feature/`-style prefix if
there is one, else the one `.review/context.md` names,
provided the page has no `Branch:` line (not yet branched) or one of its `Branch:` lines, one
per part, names the current branch: `.review/` belongs to the working tree, not the branch. A
key given as the argument is the ticket whatever the branch; when its page names other
branches, step 2 says where it is built. A pull request gives its head branch and the ticket its
body's `Ticket:` line names. A branch with its own plan,
`.review/implementation-plan-<branch, / as ->.md`, and no key in its name is its own work, a
change `implement-change` started here: go on to step 2 with no ticket, as `where.sh` does. With
none of these, or `Branch:` lines naming only other branches, ask which ticket, except when
`.review/context.md` names a slug rather than a key, under the same `Branch:` condition: a ticket
`ticket-draft` drafted that is not filed yet. Go on to step 2 with no ticket, where `where.sh`
gives it as `slug=`.

A server is needed only at the step that reads it: GitHub for step 2's pull request reads and
`get_me`, Atlassian for the ticket's status. Either one missing or failing is said as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out. When GitHub cannot be reached there, the
pull request's state is lost: stop as `using-github` "When the server cannot be reached" says. On
`gh`, which the person chooses there, the phase skills carry their own GitHub reads and gated
posts, but `pr-reader` builds the thread table only from the server, so `pr-fix` stops at its
start and `pr-review` posts only a pull request's first review. When Atlassian cannot be reached,
the ticket's status is lost and the run goes on: run `next_phase.py` without `--ticket-status`,
which reads the status as unknown, and say so on its own line after the script's three lines, with
the error verbatim and the fix; the phase skill that needs the ticket offers the paste.

## 2. Where it stands

Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review_dir.sh"`, which creates `.review/` and keeps it out
of git. When a pull request was given, read it first: one `pr-reader` in `state` mode, given the
repository and the pull request, its block written to `.review/work-state.txt` with the Write
tool (`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`, "Writing a file"). Then write
`bash "${CLAUDE_PLUGIN_ROOT}/hooks/where.sh" --fields` to `.review/work-fields.txt`, adding
`--ticket <key>` when the ticket did not come from the branch: a key given as the argument, or
the key the given pull request's `ticket:` line names.

When the fields have no context page and there is a ticket key, read its Jira status first, with
one `source-reader` and the task `ticket <key>`, and the statuses at which the team's tickets have
a pull request, one per line, from
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --defaults --field jira.pr_statuses`, an error
from which is a stop, as step 1 says; where it prints `not yet recorded`, no workflow is recorded,
and no status is among those. Then,
without a given pull request, the first row that matches says which pull request to read:

| The fields | Read |
|---|---|
| an `outcome=` or a `part=` | this branch's |
| a context page with a `Branch:` line and no plan file: a ticket drafted from its pull request | the `elsewhere=` branch's, or this branch's when that is empty |
| no context page, and a status among those, ignoring case | this branch's when its name starts with the key; else one `search_pull_requests` for `repo:<owner/repo> is:pr <key>` |
| anything else | none |

Each read is one `pr-reader` in `state` mode, its block written to `.review/work-state.txt`.
When no pull request is found, write `pull request: none` there instead. When the search finds
several, ask which, naming each, the open one recommended. Never read reviews and threads in this
session.

Then run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/next_phase.py" --fields .review/work-fields.txt`,
adding:
- `--state .review/work-state.txt` when there is one, and `--pr <n>` when a pull request was given;
- `--ticket-status <status>` when the status was read;
- `--local-review .review/pr-<n>-review-submission.md` when that file exists for the pull
  request, so a review the person chose to keep local does not send them back to `pr-review`;
- `--me <login>` with a state block: the login `get_me` returns on the server `pr-reader` used
  (`gh api user --jq .login` on the `gh` path), so the author who answered a findings review, or a
  thread a person or a bot opened, goes on from the threads rather than back to `pr-review`; left out when the login cannot be read,
  and the row is then the one a reviewer gets. A re-review of the author's own pull request is
  asked for by name, through **Something else**;
- `--reviewed-this-loop` after `pr-review` posted in this invocation;
- with a `part=` in the fields, the ticket ships as several pull requests: find them with one
  search for its key, write `#<n> <open|merged|closed> <head branch> <the Claims: line's
  criteria>` per line to `.review/work-stack.txt`, and add `--stack .review/work-stack.txt` and
  `--criteria` with the ticket's Acceptance Criteria.

Its row decides: `phase:` is the skill to run, `argument:` its argument, `why:` the row, `lock:`
what step 4 checks, and the three lines after them are what step 3 says. The rows are the
script's docstring and its tests, and apply as written without a rules file. An error `pr-reader`
or the script returns is a stop, as step 1 says.

## 3. Say it, then ask

Print the script's three lines as it gives them, then one question:

```
PROJ-42 · pull request #7 · 2 thread(s) to answer
Next: pr-fix.
It will ask you: agree, disagree or discuss on each thread, then the plan, the diff, the push and any reply.
```

When the fields' `profile=` is empty because the profile was not read, or `none` for a repository
with a standard (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints one), say so
in one line after the three, before the question, such as `profile: none — the standard sets
nothing for this repository; /lasp-dev:onboard writes its standards/profile.yaml`; `none` comes
only from the repository's own `standards/` with no `profile.yaml`. When the session-start line
read `profile refused:`, as for a pointer to a standard whose `profiles/` has no `<repo>.yaml` for
this repository, say that line's message instead, with the fix it names. For a repository `--standard` exits 1 for, ending "the
repository has no standard", `none` is expected: its values come from its own files and the
plugin's default profile, and nothing is said.

The options are **Continue** (Recommended), **Something else** (then ask, as free text, what: a
phase the person names runs; the Never rule binds the router's own choice, not the person's),
**Stop**, and **Let's discuss**. When `phase:` is `nothing`, there is nothing to continue: say the
three lines and stop, except on two rows. On `why: open-part`, `argument:` is the ticket's open
part: go back to step 2 with that pull request as the one given. On `why: build-stopped`, the
options are **Retry the build** (`implement-change`, resuming), **Open the pull request anyway**
(`pr-create`, which carries the build line), **Stop** and **Let's discuss**; recommend from the
outcome line: Open anyway when the build was blocked by a pre-existing failure, Retry when it
stopped for a person who has since acted, and Let's discuss when the review cap was reached or a
finding kept returning, since a retry meets the same finding. On `why: unfiled`, the three
lines name the slug's `.jira.txt` to file in Jira and `ticket-draft <slug>`, which files it or
takes its key and renames the page; stop there.

## 4. Run it, then look again

When `lock:` names a skill, which the script prints only before `implement-change` or `pr-fix`,
the two phases that take `.review/lock`, and neither has run in this conversation, another session
holds the working tree and was active in the last four hours; an older lock is stale and the
script prints `lock: none`. Say which skill and since when, and ask: **Stop** (Recommended: the
other session may still be working), **Take over** or **Let's discuss**. On Take over, run
`printf '{"session_id":"%s"}' "${CLAUDE_SESSION_ID}" | bash "${CLAUDE_PLUGIN_ROOT}/hooks/build-record.sh" take <phase>`,
then invoke the phase. `lock: none` runs the phase regardless.

Invoke the phase skill with the Skill tool, with its argument: `ticket-draft <key>`, or `ticket-draft settle <key>` when the person asks for it; `implement-change <key>`, or `implement-change` with no argument when `argument:` is empty, a
branch with no ticket whose own plan it resumes; `pr-create` with no argument, plus `gh` when the person
chose it; `pr-review <n>`; `pr-fix <n>`. When it returns, go back to step 2. If step 2 then picks the row it picked before the
phase ran, or the person declined the phase's own offer of the next step, stop: say what the
phase reported and what would move it on. Never run the same phase twice on the same state in
one invocation.

Stop when the next stage waits on other people, such as reviewers answering on GitHub, when the
stage is the merge, or when the person stops. The last line says what happens next and who does
it: "Reviewers answer on #96; run `/lasp-dev:work` again after."

## Never

Skip a phase skill's gate, answer one of its questions for the person, post, push or merge
itself. Run a phase the state does not call for because it looks quicker.
