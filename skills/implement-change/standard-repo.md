# In a repository with a standard

`implement-change` reads this when the repository has `standards/review-rules.md`,
`standards/decisions.md` or a `standard:` pointer in `standards/profile.yaml`, the standards workflow. Three things change there; everything
else in the skill stands.

- **Context first (step 1).** For an epic, or a ticket in the profile's ticket key pattern with no
  `.review/context/<ticket>.md`, offer `/lasp-dev:ticket-draft` on it before the brief; its
  estimate, against the "Group ticket session" threshold in the plugin's `standards/dials.md`,
  says whether the group should settle the plan. With the source, read
  `.review/context/<ticket>.md`, its first line on its own first: a page that opens with a
  `Controlled:` line is held as `<plugin root>/skills/writing/references/short.md`, "Controlled content" says, and nothing of it reaches the planner until the
  person clears it. `.review/context.md` stays the session-start line's copy.
- **Every agent gets the standard as one file (steps 3, 4 and 8).** Before invoking the planner,
  write `.review/standard.md` afresh, from the repository's top level: `bash
  "<plugin root>/scripts/standard_file.sh" > .review/standard.md.tmp && mv
  .review/standard.md.tmp .review/standard.md`, so a failure keeps the last good file. It holds
  the review contract, the repository's rules and decisions, or with a pointer those the script
  fetches from the repository it names, and the plugin's shared decisions and terminology. Exit 1
  names the missing file, which stops the build; a standard that cannot be fetched stops it too,
  and the person may choose to go on without it, `git config lasp-dev.standard none`, which
  lasts until `git config --unset lasp-dev.standard`; say so to the person and in a sentence of
  the pull request's description; a failed read of the plugin's
  `standards/` names the path. Give the planner, the plan reviewer and every reviewer in each
  step 8 wave that one path, to load before judging. Leave the instruction file out: they load
  it with `CLAUDE.md` already. Every reviewer in the wave keys each finding as the contract's
  Citation section defines and raises nothing on its do-not-flag list.
- **The context page names the branch (step 6).** When step 6 creates or chooses the branch and
  `.review/context/<ticket>.md` exists, write `Branch: <branch>` as its second line, under the
  `#` title, in it and in its `.review/context.md` copy; for a ticket in several pull requests,
  one line per part as it is branched, `Branch: <branch> (part k of n)`. `work` and the
  session-start line use the page only on that branch. A build from a file or a prompt has no
  context page.
