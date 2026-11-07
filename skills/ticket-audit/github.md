# A GitHub tracker

Read by `ticket-audit` where `python3 "<plugin root>/scripts/profile.py" --defaults --field
issue_tracker.kind` prints `github`. The tickets are the issues at `--field
issue_tracker.location`, or, when that prints `none`, this repository's: the owner/repo its
`origin` remote names, from `git remote get-url origin`, never a name guessed. Give it to each
reader as `Tracker: github <owner/repo>`; every item's `owner` and `repo` are its. An issue is `#12`
wherever a person reads it. The issue's fields, the plan's items, the approval record and the read-back are
`<plugin root>/skills/using-github/issues.md`'s; read it before Apply. What differs from
`SKILL.md` is below; the rest runs as written.

## Sweeps

Two sweeps run on GitHub, `duplicates` and `pulls`. Each of the other three, when the person asks
for it, gets one line and no reader:

- `planned: does not apply on a GitHub tracker: an issue has no due date or epic to place it in
  the year plan`
- `links: does not apply on a GitHub tracker: an issue has no typed links`
- `estimates: does not apply on a GitHub tracker: an issue carries no estimate`

When the person names no sweep, ask between `duplicates` and `pulls`, recommending the one their
words point to, or `duplicates` when nothing does. Both need the GitHub server,
and neither needs Atlassian or reads the year plan; a GitHub server that cannot be resolved or
reached stops them, as `<plugin root>/skills/work/servers.md` sets out.

**Duplicates and outdated issues** (`duplicates`) runs over every open issue in place of the saved
filters, saying of each finding's issues which are stale, with no update in 180 days. Its findings
are `SKILL.md`'s, the bodies' and comments' words quoted, with one more judgment on a pair: which
issue to keep, as `using-jira`'s "Merging two tickets" recommends (a mapped label, an assignee or a
pull request naming it; otherwise the fuller body; otherwise the lower number), and whether the
other holds anything the kept one lacks, a requirement, a criterion, a boundary, an open question,
or a decision or context in a comment. A pair whose other issue holds nothing more is a `close` as
a duplicate of the kept one; one that holds more is a `merge`.

**Open pull requests** (`pulls`) runs as `SKILL.md` says. The ticket of a pull request is the issue
its state block's `ticket:` line names, read as `<plugin root>/docs/contracts.md`'s "The record"
reads a body's `Ticket:` line on a GitHub tracker. In place of "a ticket still in the filed
status", one finding of these per pull request:

- it names no issue: no `Ticket:` line, one that starts with `none`, or one from which `profile.py`'s
  `ticket_named` reads no issue without refusing and that links no other tracker, such as
  `Ticket: TBD`; the rest are the next finding's; the action is to file the ticket;
- its `Ticket:` line names something other than the tracker's issue; the action is to correct the
  line. "The record" sets which: a line leading with a Jira-shaped key, or linking another tracker
  such as a Jira URL, is another tracker's; a bare
  `#<n>` is the tracker's only when `issue_tracker.location` prints `none` or names the pull
  request's own repository, and an `<owner/repo>#<n>` or issue URL only when it names the
  location, or with `none` the pull request's repository;
- its issue is closed, with the `state_reason`; the action is to close the pull request or reopen
  the issue, for the person to choose;
- its issue is open and carries neither the `approved` nor the `implementation` role's label,
  where `--defaults --field issue_tracker.roles.approved` prints a label; the action is a ticket
  writer's approval.

## Apply

The roles are `python3 "<plugin root>/scripts/profile.py" --defaults --field
issue_tracker.roles`, in place of `jira.roles`. A non-zero exit is a stop for every item: each is
left to paste with `paste: profile.py: <error verbatim>`.

The plan holds an item per upheld action, as `issues.md`'s "What an item is" sets out, the evidence
beside it in a clause:

| Action | Items |
| --- | --- |
| close | A Comment on the issue giving the evidence: the commit or pull request that did the work, the code that no longer matches the premise, or `Duplicate of #<kept>` with both issues' words quoted. Then one Update: `state: closed` with `state_reason` `completed` for an issue the code satisfies, `not_planned` for one whose premise no longer matches, or `duplicate` with `duplicate_of` the kept issue's number; and, when the issue carries a label the roles map, its `labels` as the whole list with that label removed and the `finished` role's label added for `completed`, or the `abandoned` role's for the others, where `issue_tracker.roles.<role>` prints one |
| merge | No item: the next step is `/lasp-dev:ticket-draft <the issue to close>`, whose merge moves what only that issue holds onto the kept one before closing it as a duplicate (`<plugin root>/skills/ticket-draft/github.md`) |
| re-scope, split, file the ticket | No item, as `SKILL.md` says |
| correct the Ticket: line, approve, close the pull request, reopen the issue, and `pulls`' review, reply, rebase, mark ready | No item: a person's move on GitHub |

No item sets a label the repository does not already use, a Projects field, an estimate, an
assignee, a parent or a sub-issue, and none adds a closing keyword to a pull request.

The plan is written to `.review/github-plan.md` and gated as `issues.md`'s "Showing it" says, its
texts under `.review/audit/<YYYY-MM-DD>-send/`; the turn ends at that gate, since **Apply them**
is not a yes to the plan. It is run on the person's answer to the gate through
`.review/github-approval.json` and `hooks/issue-gate.sh`, as its "Running it" says, and read back as
its "Read it back" says. The record is `.review/audit/<YYYY-MM-DD>-writes.md`, as `SKILL.md` says.
What the plan does not write, an item dropped, failed or marked `paste:`, or the whole plan on
**Paste it all** or without the write tools, is handed over to paste: its text stays in the
`-send/` folder, and the closing summary names each such item with its issue, the call to make by
hand and the path of its text. The closing summary lists each issue written as `#<n>` with its URL.
