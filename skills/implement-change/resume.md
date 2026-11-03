# Resuming a plan

`implement-change` reads this when a plan for this work may already exist, as its "Where the Files
Live" says. "This part" is the one `where.sh --fields` gives as `part=`, or the plan's only one.

## Is it this work?

A plan is resumed only for its own work. The invocation is that work when it gives no source,
when its source is the ticket key in the plan's file name, or when it matches the plan's
`Source:` line; a plan with no `Source:` line is that work only on the first two. Any other source
is a new request: name the plan by its Goal line and path, and ask whether this is **That work**
(resume, recommended when the source is close to the plan's), **A new change** or **Let's
discuss**. A new change starts at step 1 and never writes to that plan: its own plan is written
under its own name, and the old plan file is left as it is.

## Where to go on

**A draft**, a plan with no `Approved by:` line, resumes at step 4, or at step 5 when the depth is
light or the draft carries `procedure: step 2: build it now`.

**An agreed plan**, one with an `Approved by:` line, `not recorded` included: skip steps 1 to 4,
read the plan file, and go on at the first of these that applies.

- The reopened file, `reopened_file=` in `where.sh --fields`, names a thread, or a
  `session-<pr>-<n>` reopen, that the plan has no `## Revision N — <id>` heading for, or one whose
  section has no `Approved by:` line yet: step 5, to re-plan under that heading.
- No `Base:` line: step 6, asking step 5's base question again when the current branch is not
  the default branch.
- This part has an unchecked step: step 7, at the first one.
- Every box of this part checked: step 8 with no `.review/build/outcome.md`; step 9 with it and
  an uncommitted diff; on a clean tree, step 8 again, a retry, when it reads other than `Build:
  passed`, and step 11 when it reads `Build: passed`. When the plan also has a later part with
  no `Base: <branch> (part k of n)` line, ask first whether this part's pull request is open: if
  it is, go on to the next item.
- The plan names several pull requests, and the first part with an unchecked step has no
  `Base: <branch> (part k of n)` line: step 6, for that part, from a clean tree.

The build hook keeps a finished build's `outcome.md` and its Already checked block on a resume.
To go back into the build, at step 5 for a reopen or at step 7 or 8, run the reopen command
`implement-change` "The Build Record" gives.

## A reopened design

When the reopened file names a thread, or a `session-<pr>-<n>` reopen, that the plan has no
`## Revision N — <id>` heading for, review reopened the design: re-plan inside the existing plan
file under that heading, the next N, with the thread's text, or the session reopen's clause, in
the brief, never a fresh plan. On approval, the revision's section gets its own `Approved by:`
line; until then the revision is a draft.
