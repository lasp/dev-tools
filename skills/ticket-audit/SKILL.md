---
name: ticket-audit
description: >
  Sweeps the team's Jira project for gaps in planned work, duplicate, outdated and badly linked
  tickets, estimate accuracy and what open pull requests wait on, then applies the actions in
  Jira on one yes.
argument-hint: "[planned | duplicates | links | estimates | pulls]"
disable-model-invocation: true
metadata:
  author: lasp-dev
  version: 1.3.9
---

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## When to run

When a person asks for one of the sweeps below, typically before monthly planning or a ticket
lineup. A plain Jira query needs no skill; this one is for questions that depend on the year
plan, the repositories or the team's conventions.

## Options

| Option | Default |
|---|---|
| Sweeps | Asked for when not named: `planned`, `duplicates`, `links`, `estimates`, `pulls` |

## Reads

Every read is a `source-reader`'s, which carries `using-jira` and `using-confluence`; the session
reads none of it, apart from the list of open pull requests and the `pr-reader` blocks the
`pulls` sweep gathers first, and, at Apply, the project's status roles, `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --defaults --field jira.roles`,
for the status each close moves a ticket to. A non-zero exit from it, or `not yet
recorded` is a stop for every close: no Status item is built from any other source, and each close
is left to paste as `write-plan.md` says. Pass `gh` when the person has said so in this session. A
`Withheld:` line in a block is asked of the person as "Controlled content" in
`${CLAUDE_SKILL_DIR}/../writing/references/short.md` says; the withheld item gets no finding unless
they clear it, and a cleared one is read again with a `Cleared:` line.

The four ticket sweeps, planned work, duplicates and outdated tickets, links and estimates, need
the Atlassian server: if it cannot be resolved or reached, stop those sweeps and say so as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the sweeps being what is lost. A sweep
cannot be pasted: it reads every ticket in its bound. The `pulls` sweep needs the GitHub server,
and without Atlassian it goes on with each ticket's status as `not read: <error verbatim>`. A
ticket sweep whose GitHub reads, pull request sizes or commits, cannot be made goes on and says
which of its evidence was not read. Each server missing or failing is said once, as `servers.md`
sets out.

## Sweeps

The person picks one or more; when they did not say, ask, recommending the sweep their words
point to, or `planned` when nothing does. Then run one `source-reader` per sweep
chosen, with the task `sweep <slug>`, all in one message. Each writes its sweep's file as
"Writes" says, within the bounds, and returns the summary line, the counts and what the bound
left out. Read each file's `merge`, `close` and `re-scope` groups and re-judge each from the quoted
criteria or the commit; mark any you would not propose `reader's verdict, not upheld: <why>` in the file,
beside the item, and show the summary lines with the count upheld, and the file paths. Then Apply.

1. **Planned work** (`planned`). The tickets due in the current month of the year plan and the next two.
   - Gaps: a milestone with no ticket behind it.
   - Incompatibilities: two tickets whose criteria contradict, or that change the same
     interface in different directions.
   - Order: a ticket due before one it depends on.
   - Missing work: open tickets with no due date, or in the saved filters for work to pick up
     between milestones and for tickets proposed for closing (the saved filters and JQL `using-jira`'s "The project" reads from `tracker.md`),
     that a milestone needs.
   - Drift: a milestone whose name or initials (the legend is in the project's `wiki.md`) do not
     match the assignee of the tickets behind it; a ticket whose due month is not its
     milestone's month; more than one ticket in the status `tracker.md`'s Fields table limits to
     one ticket across the team (a per-developer limit is not this finding).
2. **Duplicates and outdated tickets** (`duplicates`). Start from the saved filter of tickets
   proposed for closing (the saved filters and JQL `using-jira`'s "The project" reads from `tracker.md`) and open tickets with no update in 180
   days, and report, saying which of the two each ticket came from:
   - Pairs that ask for the same thing, with the criteria quoted.
   - Tickets the code already satisfies, with the commit or pull request that did it.
   - Tickets whose premise the code no longer matches.
3. **Links** (`links`). Dependencies implied by the descriptions or the code but not linked; links whose
   direction or type is wrong; Blocks chains whose due dates run backwards; children outside
   their epic.
4. **Estimates** (`estimates`). For tickets with Story Points in the finished status
   (the project's status roles, `jira.roles`): elapsed time runs from the first transition into the
   implementation status to the finished status, from
   the changelog (`jira_batch_get_changelogs`); pull request size is the merged pull request whose
   title or branch names the key, in lines changed.
   - Are equal estimates similar in elapsed time and pull request size?
   - Where do outliers cluster, by component or by type?
   - Which tickets waiting for an estimate, in the approved status with no Story Points
     (the saved filters and JQL `using-jira`'s "The project" reads from `tracker.md`), most need one next?
   The question is whether the scale is consistent, not whether one person estimated well:
   report by ticket and component, never by person.
5. **Open pull requests** (`pulls`). Every open pull request in the adopted repositories, those
   the standard covers, a `<repo>.yaml` in the `profiles/` directory of the standard
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints, or this repository alone
   for a standard with no `profiles/`; when it exits 1 ending "the repository has no standard",
   the sweep covers it alone, and any other exit 1 stops the sweep with its message. Before the sweep's `source-reader`, list
   them through the GitHub server, tell the person how many there are and that one reader runs
   per pull request, a repository at a time, so it takes minutes, and run one `pr-reader` in `state` mode per pull request, all
   of one repository's in one message, one repository at a time, since the dumps are keyed by
   number. After each repository's readers return, write their state blocks, each under a `##
   <owner/repo>#<n>` heading, to `.review/audit/<YYYY-MM-DD>-pulls/state.md`, and copy each
   dump's `pr.json` beside it as `<repo>-pr-NNNN.json`; give the sweep that directory. Per pull
   request: its age, and whose move is next, from the state block, the `pr.json`, and the
   ticket's status the reader fetches:
   - a requested reviewer who has not reviewed;
   - the author owing a reply, the threads they have not answered;
   - findings unanswered since the date of their review;
   - a draft open for more than a month;
   - a branch behind its base;
   - a ticket still in the filed status (the profile's `jira.roles`).
   One proposed action for a person each. Report by pull request, never by person, and never
   comment or ping.

## Apply

The sweep gathers; this turns it into the writes. Say how many upheld actions each group holds,
and ask: **Apply them** (Recommended where the server's write tools are there), which builds the
write plan; **Choose groups**, typed under Other; **Stop**, the report kept in `.review/audit/`;
**Let's discuss**. Without the write tools, say so in one line and offer only the report.

The plan, as `${CLAUDE_PLUGIN_ROOT}/skills/using-jira/write-plan.md` sets out, holds an item per
upheld action, the evidence beside it in a clause:

| Action | Item |
| --- | --- |
| link | A link of the type the finding names, or a corrected one: the wrong link is removed only when the person asks in their own words, as its own write |
| merge | No item: the next step is `/lasp-dev:ticket-draft <the ticket to close>`, whose step 3 offers Refine <the ticket to keep> instead and merges the two, as `using-jira`'s "Merging two tickets" sets out; the sweep file names the ticket that section recommends keeping |
| close | A move to the finished status for a ticket the code already satisfies, with a comment naming the commit or pull request, or to the status for a ticket closed with its work not done for one whose premise the code no longer matches, with the evidence; the team's `jira.roles` names both |
| re-date | The due date, now and after, from the milestone's month |
| assign | The assignee, now and after, where a milestone names someone the ticket does not (`using-jira`, "Writing to Jira") |
| re-scope, split, file the ticket | No item: the next step is `/lasp-dev:ticket-draft <key>`, which drafts the change and writes it through its own plan |
| estimate, and `pulls`' review, reply, rebase, mark ready | No item: an estimate is the team's, and the rest is a person's move on GitHub |

An item marked `reader's verdict, not upheld` is left out unless the person adds it. The texts go
under `.review/audit/<YYYY-MM-DD>-send/` and the record in `.review/audit/<YYYY-MM-DD>-writes.md`.
The closing summary lists what was written with its keys, and the `ticket-draft` command for each
ticket to merge, re-scope or split.

## Writes

`.review/audit/<YYYY-MM-DD>-<slug>.md`: each finding with the tickets involved, the evidence (quoted
criteria, a commit, a date) and one proposed action for a person to take, grouped by action (link,
merge, close, re-date, assign, re-scope, split, estimate; for `pulls`, review, reply, rebase, mark
ready, or file the ticket). A summary line per sweep first. The session then adds its `reader's
verdict, not upheld: <why>` mark beside each `merge`, `close` or `re-scope` item it would not
propose; nothing else in the file changes.

## Bounds

A sweep covers at most 200 tickets; say what was left out when the query returns more. Each
sweep is one Sonnet `source-reader` reading up to that many tickets, so it takes minutes.
Report no more than 20 findings per sweep, strongest evidence first. Estimates need at least
ten finished, estimated tickets before any conclusion; below that, report the count and stop.

## Never

Write to Jira outside Apply's approved write plan. Estimate a ticket; the fourth
sweep says which tickets need one, and the team estimates them. Name a finding as someone's
fault.
