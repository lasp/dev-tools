---
name: revise
description: >
  Prepares the monthly standards revision: from merged pull requests' review records, proposes
  rules to retire, reword, graduate or add, tickets for problems still in the code and fixes to
  documents practice has left behind, for the group to mark, and reports where merged diffs
  follow or break the rules and the documented practice; `apply` drafts what it
  accepted, and `correct` fixes a misreading in the corpus between revisions. Not for
  disagreeing with a rule, which goes through Disagree and the revision.
argument-hint: "[prepare [measures] [Confluence page or Jira epic to add] | apply | correct <what is wrong, where, what it should say, the source>]"
disable-model-invocation: true
metadata:
  author: lasp-dev
  version: 2.13.0
---

# Revise the standard

A group session with one driver. The driver runs `prepare` before the meeting, which writes a
report of proposals with blank checkboxes; the group marks each one in the meeting; the driver
runs `apply` after it, which drafts the accepted changes as one pull request here and, when the
standard lives elsewhere, one in the standard's repository. It runs in the code repository whose standard it revises. Between
revisions, `correct` fixes a misreading one person reports, everywhere the corpus carries it.

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## When to run

Monthly, or sooner when the Revision Dial's count of merged pull requests since the last report
is reached; nothing schedules it.

## Options

| Option | Default |
|---|---|
| Mode | `prepare`: read `${CLAUDE_SKILL_DIR}/prepare.md`. `apply`, after the group has marked the report: read `${CLAUDE_SKILL_DIR}/apply.md`. `correct`, when a person says the corpus has something wrong: read `${CLAUDE_SKILL_DIR}/correct.md` |
| Window | From the day after the `window:` line's end in the newest `ratchet-*.md` in any `<log>` of the standard; before the first, from the date the ledger, or the pointer, reached the repository's `main` |
| Measures | Not read. `measures`, or the person asking for them, has `prepare` also read `${CLAUDE_SKILL_DIR}/measures.md`: tickets, escaped defects, build yield and what the build missed. No Dial acts on them except the Ticket candidates Dial, which applies only in a run that reads them |
| Page or epic to add | None. A named Confluence page or Jira epic is read once and drafted as a context-entry candidate, marked like any other proposal, within `context/README.md`'s ten-entry cap |

## The standard's repository

The revision changes the repository that holds this repository's standard, and this one. Which
repository that is, and where each of its parts lives, is decided once, before anything else:

| This repository | The standard's repository | `<standard files>`, its files | `<log>`, the records | `<archive>`, `<context>` |
|---|---|---|---|---|
| Its `standards/profile.yaml` is a `standard:` pointer | The repository the pointer names, cloned | `<clone>/standards/` | `<clone>/standards/log/<repo>/` | `<standard files>/archive/`, `<standard files>/context/` |
| Otherwise: its standard is its own `standards/` | This repository, with no clone | `standards/` | `standards/log/<repo>/` | `standards/archive/`, `standards/context/` |

Its settings are the standard's too, as `profile.py` reads them. `<repo>` is a GitHub repository's name, and `<log>` names the
records directory of each repository harvested. In either row a standard with
`profiles/` covers several repositories: one run, in any one of them, revises it. `prepare`
harvests this one and every other one a rule reaches, each from the later of the window's start and its adoption date, counts each
with `ratchet_counts.py --repo <name>`, and lints with
`rule_lint.py --profiles <standard files>/profiles/`, which checks each `repos:` tag against the
repositories covered; the threads, the clusters, the sweep and the bar's `scope:` and `example:`
checks read this repository's code alone, so another repository's records are archived and
counted but admit no rule, which `prepare` says before it harvests. A proposal to reword, promote or
broaden a rule whose `repos:` line leaves this repository out runs only the bar's `fields`,
`status` and `wording` gates here (`--checks`), and is marked "check from <a repository it
names>" rather than held, since its `scope:` and `example:` are another repository's. Any other exit 1 from
`profile.py --standard` stops with its message.

A clone goes into a directory from `mktemp -d`, made with `git clone --template=`, which copies no
hooks (Claude Code's sandbox refuses a clone's hooks and its `.git/config`, so there the clone runs
outside the sandbox on the person's yes), on a branch `revision/<repo>-YYYY-MM` for
`prepare` and `apply`, or `correction/<id>-YYYY-MM-DD` for `correct`. `apply` opens the clone
`prepare` left, or clones and checks out that branch where `prepare` pushed it, never a fresh
`main`. Read the standard from there, not the installed plugin. Write there with `git -C <dir>`;
commit, and push that branch and open its pull request as `using-github` sets out, only on the
yes each mode's file asks for. After a push, remove the directory and say where it was; any other
answer leaves it in place and names its path. With no clone, `prepare` writes the records and
the report into `<log>` in this repository's working tree, uncommitted, where the group marks the
report and `apply` reads it; every other change to `<standard files>` goes into this repository's diff,
and the driver commits the records, the report and the diff together in the revision's pull
request here. Nothing is written into the installed plugin.

"Shared" means the plugin's own `standards/`: `dials.md` and `rule-bar.md`, read from `<plugin
root>/standards/`. `<standard files>`'s `terminology.md`, `decisions.md`, `context/`, `archive/`,
`profile.yaml`, `profiles/` and `templates/` are the project's. A bare `standards/` path is this
repository's own; an adopted repository is one with a ledger, its own or the one its pointer
names. A read that fails is an error: say so with the path, and never read a copy from anywhere
else or invent a term or a decision to fill the gap; `correct` stops there.

## The marks

Each proposal in the report is a checklist line, `- [ ] <R-0NN, context/<name>, ticket/<slug>
or doc/<path>> · <proposal> · <the Dial that triggered it, for a rule> · <evidence>`, its detail beneath opening with a `Recommended:` line.
The group writes its verdict on the proposal's `Mark:` line and ticks its box, one proposal at a
time and never in bulk: `accept`,
`decline: <reason>` or `escalate: <reason>`, and, on a proposal the bar held, `accept, override:
<reason>`, the only mark that accepts it (`rule-bar.md` "Overrides"). A `Recommended:` line is the
report's, never a mark. A proposal whose `Mark:` line is empty is deferred. A draft pull request `prepare` opens on the
report's branch is a place to discuss proposals; a verdict given there counts once it is on the
`Mark:` line, which stays the record `apply` reads. A new or reworded rule is worded as `${CLAUDE_SKILL_DIR}/../writing/SKILL.md`
"Conventions" says under Rule wording: a principle with no case in it.

## Files

In `<log>`:
- `pr-NNNN.yaml`, the window's records, harvested by `prepare`.
- `ratchet-YYYY-MM.md`, the report, first line `window: <from>..<to>`, as
  `${CLAUDE_SKILL_DIR}/outline.md` outlines it; marked by the group, read by `apply`.
- `correction-YYYY-MM-DD-<id>.yaml` and `note-YYYY-MM-DD-<id>.yaml`, from `correct`.

In `<archive>` and `<context>`, from `apply`: `R-NNN.md` entries and accepted `context/` refreshes.

In this repository's `.review/`:
- `harvest/analysis/pr-NNNN.md`, each `thread-analyst` block as returned.
- `backtest/R-NNN.entry.md` and `backtest/R-NNN.md`, a proposal's drafted entry and its
  `rule-probe` blocks.
- `revision/claims.md`, the rules and documented claims the sweep judges, and
  `revision/sweep/pr-NNNN.md`, each `diff-probe` block as returned.
- `harvest/context-refresh.md`, from `context-refresh.md`.
- `checks/`, the drafted checks for graduation candidates.
- `revision/feedback/`, a `skill-feedback` draft per procedure finding, from `prepare` step 2 and
  `correct` step 2, for the driver to file with `/lasp-dev:skill-feedback <path>`.
- `ratchet-proposal.diff`, from `apply`: the change to `standards/`, a linked instruction file's
  Review Rules section where a ledger still keeps wording there, the pull request template and the documents an accepted `doc/` proposal names,
  for the driver to apply and open as a pull request.
- `revision/notes/`, meeting or chat notes the driver pastes before `prepare`, read as asks.
- `revision/tickets/<n>-<slug>.md`, from `apply`: each accepted `ticket/` proposal as a prompt
  `ticket-draft` takes.
- `archive-pages/`, from `apply`: a Confluence page body per archive entry, for a person to
  publish.

## Prepare

Read `${CLAUDE_SKILL_DIR}/prepare.md` and follow it.

## Apply

Read `${CLAUDE_SKILL_DIR}/apply.md` and follow it.

## Correct

Read `${CLAUDE_SKILL_DIR}/correct.md` and follow it; its own Bounds and Never hold there in place
of the two below.

## Bounds

One report and one diff: one pull request here, from the driver's diff, and, with a clone, one in
the standard's repository, merged first. Every proposal carries its evidence pointers.
One `thread-analyst` per merged pull request with a record, within `harvest.md`'s cap, and one
`diff-probe` per pull request merged in the window, at most thirty. If
the corpus is over its line budget, the proposal names a retirement. Every proposal reaches the
report, in the overview's order; one the meeting leaves blank is deferred, and a deferred
admission is held as a candidate. Jira is written only by `ticket-draft`, one ticket at a time,
through its own write plan and yes.

## Never

Edit this repository's files, `standards/`, the instruction file and the template included,
`<log>`'s records and report aside when the standard is this repository's own: every other change
to them goes into `.review/ratchet-proposal.diff` for the driver to apply. Edit the plugin's
`skills/` and `agents/` text. Open this
repository's pull request, or the standard's repository's without a yes. Propose a rule without the
evidence its Dial requires. Write to Confluence or Jira; an accepted ticket reaches Jira only
through `ticket-draft`, on the person's yes. Delete a rule's reasoning without
archiving it first. Write a rule, a rewording or a promotion a gate of `rule-bar.md` fails, unless
the group marked it `accept, override: <reason>`.
