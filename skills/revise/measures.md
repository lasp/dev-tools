# Measures

Read by `prepare` after its step 7, only when the person asks for the measures. They go under the
report's "Measures", except where a section below names another. No Dial acts on them except the
Ticket candidates Dial; they show whether the workflow is working, beside the proposals.

## Tickets

The tickets the window's merged pull requests name in their title, body or branch name, whatever
their status. Read them by name, never by a search on resolution date: Jira resolution lags the
merge, and one Jira project is often shared by several repositories. Run one `source-reader` per
ticket with the task `ticket <key>`, launched as harvest.md's "Analysts" launches agents. With no Atlassian server, say so as
`<plugin root>/skills/work/servers.md` sets out, the tickets' text being what is lost; the driver
pastes each description into `.review/harvest/tickets/<key>.md`, each reader gets that file in
place of the key, and the report's second line says the tickets came from files.

Read each block as two texts. The baseline comment, as `using-jira` defines it, is what a person
wrote before any agent touched the ticket; a baseline whose first line ends `(body written by
pr-create)` is settled text, not a person's. The description is the settled text. A ticket with
no baseline comment predates the convention: read it as one text and say so. A human source is
the baseline, a pull request reply, or a person's later edit the changelog shows. A ticket the
block lists as `Withheld:` is counted `withheld`, never as predating the convention; its question
goes to the person, and nothing of it is scored until they clear it.

Candidates, each listed with its tickets:
- a constraint, or a thing typed into free text, as often as the Ticket candidates Dial says: a
  candidate rule, or a candidate template field;
- an answered question that settles a convention: a candidate `D-`;
- a term people used that the code does not: a candidate `T-`;
- a pasted link: a candidate `context/` entry.

Counted from human sources only; the same thing only in settled text is listed and counts toward
nothing. Beside them: tickets still open whose pull request merged; merged pull requests naming
no ticket; and, in the "Head" cost line, the count of tickets carrying `using-jira`'s `Written
after the change` line. Then the ripple: each ticket's footprint `Used by:` line against
its records' `inner.ripple`, the consumers with a use site, verified, and broken; a consumer that
broke and the footprint did not name is a `ticket-draft` miss.

## Escaped defects

A defect fixed in the window is a merged pull request whose ticket is a Bug, or whose record's
`inner.reproduced` is not `none`. For each, find the commit that introduced it in this
repository: `git log -S` with a line the fix removed or changed, or `git blame -w -M -C` at the
fix's parent on the changed lines, with `--ignore-revs-file` where the repository keeps one; for a
fix that only adds lines, `git log -L` on the enclosing function at the fix's parent. Then the
merged pull request that carries it. Run one `thread-analyst` per defect in `defect` mode, launched as
harvest.md's "Analysts" launches agents, each given the repository's path, the introducing and fixing merge commits, the
introducing pull request's merge date, `standards/review-rules.md` and `prepare.md` step 6's held
candidates as text.

A line naming a rule or a held candidate is `escaped` evidence beside it on the candidate list,
counted apart and never toward admission or breadth. A `predates rule` line is no evidence about
that rule; its candidate and check count as on any other line. A line naming a check joins
`prepare.md` step 9's checks. An introducing pull request not found, or `not traced`, is listed
as `not traced` with its fix.

## Build yield

From the records' `inner:` lines and the hooks' counts: lint passes, test runs and reviewer rounds
per build, and how often the implementation reviewer found nothing once lint and tests were green.
The finding rates by `inner.depth`. Recurring `build:` phrases: `blocked by a pre-existing
failure` on the same module, an undocumented environment; `review cap reached`, with the finding
keys that recur. Lint averaging two passes: name the auto-fixer and hook that disagree. The
reviewer's most-cited rules on green branches: graduation candidates.

## What the build missed

On pull requests whose record says `build: passed`, the people's threads the analyst marks
`changed as asked` or `changed differently`, by category and by clustered ask. A cluster of them
is a rule gap when no rule covers it, and a do-not-flag or wording gap when one does. Report
`rework_rounds` apart. A ticket in several pull requests, the records' `stack:`, is one unit for
rework, reopens and open-to-merge time. Count the records' `inner.reopened` per ticket, beside
whether the ticket had a group session; a reopen's clause is a candidate `D-`.
