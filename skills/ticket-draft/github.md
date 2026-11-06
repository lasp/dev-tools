# A GitHub tracker

Read by `ticket-draft` where `python3 "<plugin root>/scripts/profile.py" --defaults --field
issue_tracker.kind` prints `github`. The ticket is an issue, its key the number: `12` in file
names, `#12` wherever a person reads it. The issue's fields, the plan's items, the record, the
read-back and the paste file are `<plugin root>/skills/using-github/issues.md`'s; read it before
step 7. What differs from SKILL.md's steps is below; the rest runs as written, `settle.md` and
`reformat.md` included.

- **The source.** An issue's number, `#12` or `12`, is read with one `source-reader` running
  `ticket 12`; a block that says `Not an issue: #12 is a pull request` makes it a pull request
  source (`sources.md`). GitHub stops the draft for an existing issue where SKILL.md says
  Atlassian does; Atlassian is needed only for the year plan, which is skipped without it and said
  once, as "Reads" says.
- **Step 1.** `<ticket>.original.txt` holds the issue's body verbatim. The opening block's heading
  is `## #12 · <title>` and its second line `Issue · <state> · <labels, or no labels>`.
- **Step 2.** The `search` reader is given `Tracker: github <owner/repo>`, the tracker's location
  or this repository when `--field issue_tracker.location` prints `none`, in place of `Jira:
  <project>`.
- **Steps 3 and 5.** An issue has no epic, component, due date or typed link. The year-plan month,
  when the plan was read, is said in Placement and goes nowhere else. A neighbor the text names
  stays in the body: under Related Out of Scope Tickets when it takes work out of scope, otherwise
  in The code today, each as `#<n>`. A piece of a split or a follow-up names the issues created
  before it by number and those after it by title. With no `References:`, the estimate says it has
  none to compare with, as step 5 says, and stays in `.review/`.
- **Step 7's plan** is the items `issues.md` gives, shown in `.review/github-plan.md`:
  - For an existing issue: the `Comment to post` unless the block's `Original request comment:`
    is `yes`, then the body, and the title when step 7 proposes a new one, as one update, then the
    `Session comment`.
  - For a new issue: the create, with its title, the body and no labels unless the person names
    some the repository has, then the `Comment to post` and the `Session comment`.
  - A merge closes the issue not kept with `state_reason: duplicate` and `duplicate_of` the kept
    one, after its `Merged from` comment on the kept one.
  - A move into a role is a labels update, offered only when the person asks for it and only
    when `--defaults --field issue_tracker.roles.<role>` prints a label; `none` skips it, said in
    one line. `jira.roles` is not read.
- **Step 8.** The paste file `<ticket>.issue.md` is written first, as `issues.md`'s "The paste
  file" lays it out. Then, on Write all:
  1. Write `.review/github-approval.json` listing the approved items, as `issues.md` says.
  2. Make each call in order. A create's number, the last part of its `url`, replaces
     `new:<slug>` in the items after it, which go in the record once it is written again.
  3. Read each issue back as `issues.md`'s "Read it back" says, record each item's outcome in
     `<ticket>.writes.md`, and remove the record.
  4. A create's number replaces the slug: rename `.review/context/<slug>.md`, `<slug>.issue.md`,
     `<slug>.original.txt`, `<slug>.send/` and `<slug>.writes.md` to the number, and write the
     page's heading, and its `.review/context.md` copy's, as `# #12 · <title>`.

  Without the write tools, or on Paste it all, the paste file is the hand-off: say so in one
  line and give its path. The closing summary names each issue written as `#12` with the URL the
  create or the read-back gave. Unless the plan moved it, the last line says a ticket writer
  approves the issue next, by the `approved` role's label or, with none mapped, on the issue
  itself, and names `/lasp-dev:work 12`.
