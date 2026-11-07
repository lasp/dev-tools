# In a Repository With a Standard

`pr-create` reads this when the repository has `standards/review-rules.md`,
`standards/decisions.md` or a `standard:` pointer in `standards/profile.yaml`, as its "In a Repository With a Standard"
says.

Such a repository has adopted the standards workflow. Fill
`<plugin root>/skills/pr-create/body.md` below the `Ticket:` line of the template the profile's `template`
names (`python3 "<plugin root>/scripts/profile.py" <owner/repo> --field template`, with
`<owner/repo>` the `origin` remote's), `<standard>/templates/<name>/PULL_REQUEST_TEMPLATE.md`, `<standard>` being what
`python3 "<plugin root>/scripts/profile.py" --standard` prints. When either exits 1 for a reason
other than the repository having no standard, the message ending "the repository has no
standard", show the person `profile.py`'s message and stop before writing the body. When the
repository has no standard, or the template reads `not yet recorded`, the repository's own
`.github/PULL_REQUEST_TEMPLATE.md` is the template, and with none, `body.md`'s headings alone. Its headings are the template's plus three, "Key design choices and
open questions", "What was tested" and "What changed", and the Already checked block; `body.md`'s
placeholders and comments say what each holds. The format is the repository's, and it is kept:
the why goes into the Summary. When the problem as it stood, how bad it was and the goal cannot
be stated in the Summary without losing the "because", **say so loudly** before showing the
description, in its own paragraph above it: name the template, the parts that could not hold the
why, and what was cut to fit. A template that cannot carry the reason for a change likely makes
weak summaries for every pull request in the repository, which is worth raising with whoever owns
it; do not restructure the body to work around it. Reasoning that does not fit the Summary,
incidental changes, unverified prerequisites and anything that widens what can be committed,
deployed or exposed go under "Key design choices and open questions", one bullet of at most two
sentences each. After the `<details>` block, end the body with the generated-with line, carrying
the level as `pr-create`'s "The AI Assistance Level" says (D-013); add no other authorship line. Five parts are
not written from the diff:

- **The `Ticket:` line.** The key the context page is filed under
  (`.review/context/<ticket>.md`), or without a context page the key from the branch name, after
  a `feature/`-style prefix if there is one, in any letter case, upper-cased unless the pattern matches it as written; then the ticket's first sentence under Motivation
  (Context on a ticket in the earlier format), from the context page when there is one, and
  otherwise from one `source-reader` running the task `ticket <key>`, asking the author for it,
  as the why-gate does, when the server cannot be reached, said as
  `<plugin root>/skills/work/servers.md` sets out with the ticket's sentence as what is lost.
  Where the tracker is GitHub's (`python3 "<plugin root>/scripts/profile.py" --defaults --field
  issue_tracker.kind` prints `github`), the key is the issue's number and the line writes it
  `Ticket: #<n> · <sentence>`, or `Ticket: <owner/repo>#<n> · <sentence>` when `--field
  issue_tracker.location` prints a repository rather than `none`, so the link opens the tracker's
  issue and not this repository's `#<n>`; the sentence is the issue's first under Motivation, or
  the body's first without one. Never `Closes #<n>` or another
  closing keyword, since a ticket may take more than one pull request. Read a context page's first line
  on its own before the rest (`<plugin root>/skills/writing/references/short.md`, "Controlled content"). A context page that opens with a `Controlled:` line
  puts its key on the line and no sentence yet: name only the key, where it sits and the warning, quoted,
  describe nothing of it, not even where you stopped, and ask whether to read the page; on a yes,
  read the rest of it. A ticket the block lists as `Withheld:` puts its key on the line and no
  sentence: relay its question the same way, and on a yes run the task again with a `Cleared:
  <key>` line. Either way the cleared ticket's sentence goes on the line only on a second yes, to
  that sentence in this pull request, naming the ticket and its warning, and never into a public
  repository's body without it. With no ticket at all,
  `Ticket: none — <why>`, the reason asked of the person. When the plan names more than one pull
  request, the line and the `Claims:` line after it take the form `body.md`'s first comment
  gives, from the `part=` and `base=` that `where.sh --fields` prints and the criteria the plan's
  Pull requests list gives this part. The body has one `Ticket:` line: `scripts/record.py`
  refuses a second.
- **"Used by" and "How to test".** Name a consuming repository, and the run in it that shows the
  change, only when the context page's ripple names that consumer. With a context page and no
  ripple entry for a consumer, "Used by" says `nothing outside this repository` and the
  downstream bullet says none; without a context page, both say
  `not assessed: no ticket context page`. Never invent a consumer or a run.

- **The build line.** The branch's build is `.review/build/` when its `outcome.md` exists and
  `events.jsonl` records this branch as the build's, else `.review/build/done/<branch>/` when it
  holds an `outcome.md`: a build started on another branch since parked it there. Copy its
  `outcome.md`'s `Build:` line into "Already checked", as the block's first line, and its `Depth:`
  line as the second. A change not built through `implement-change` gets no block and no
  substitute line, and the skill asks nothing about it.
- **"Already checked".** After the build line, the `Gates:` and `Tokens since the build started:` lines from
  that build's `already-checked.md`, and the `Rules checked:`, `Declined:`, `Suggestions:`
  `Escalated:` and, when there are any, `Reopened:`, `Nominated:`, `Procedure:`, `Reproduced:` and `Ripple:` lines from
  `outcome.md`. Updating an open pull
  request's description keeps every `Reopened:` line its Already checked block already has and
  adds the outcome's, one per thread or `session-<pr>-<n>` id. Once a description carrying `Reopened:` lines is
  posted, opened or updated, delete the reopened file, `reopened_file=` in `where.sh --fields`: the body now holds the
  reopen, and `work` reads the file as a reopen not yet in it. Copy the lines as they are, `not recorded` and `?`
  included; never drop or estimate one: `scripts/record.py` reads `Build:`, `Plan:`, `Gates:`
  and `Tokens since the build started:` and refuses a block missing any, a labeled line with
  nothing after its label, and a `Rules checked:` or `Declined:` entry that does not open with a
  bare citation. With `outcome.md` and
  no `already-checked.md`, write `Gates: not recorded` and `Tokens since the build started: not
  recorded`. The plan line is `Plan: approved by <login>`, the
  login on the `Approved by:` line of the plan file the Base branch option reads, since the plan gate
  is the person's, `not recorded` copied as written, and `none` after the colon when the plan
  file or the line is absent.
- **The decision in body.md's Summary.** When the context page the `Ticket:`
  line resolved, `.review/context/<ticket>.md`, has a "What changed from the original ticket"
  section, its decisions are the Summary's change paragraph and the alternatives it names,
  instead of composing them from the diff. Without the section, compose them from
  the diff and the ticket, and say so to the person when showing the description.
