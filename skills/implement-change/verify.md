# Verifying work written with no plan

`implement-change` reads this when invoked as `verify [goal]`, or asked to review or verify work
the person wrote without a plan. It runs steps 8 to 12 on the branch as it stands, with the goal in
place of the plan. Open by saying when the person is needed (the goal, then the diff) and that the
wave fixes blocking findings in the working tree and commits nothing.

**An approved plan for this branch.** When `bash "<plugin root>/hooks/where.sh" --fields` gives a
`plan=` file with an `Approved by:` line, this is that build: read
`<plugin root>/skills/implement-change/resume.md` and go on where it says, unless the person says
to verify without it.

**The base.** `git symbolic-ref --short refs/remotes/origin/HEAD` names the default branch; the
base is `git merge-base <it> HEAD`, so the change is the commits since then, the working tree and
the untracked files the person says belong to it. With no `origin/HEAD`, ask which branch is the
default; with no answer, stop. With nothing changed against the base and no untracked files, say
so and stop. A stop here releases the working tree as step 12 says.

**Ask in one widget**, skipping a question the invocation answers: the goal, one line on what is
different when this is done, when the invocation gives none; and, when the tree has untracked
files, which belong to the change, the rest going on the wave's `Not part of the change:` line.
The brief is that goal, what the goal needs within the change's files as its scope and the goal
met as its acceptance criterion; nothing else is asked about it.

**Before the wave.** In a repository with a standard, write `.review/standard.md` as
`<plugin root>/skills/implement-change/standard-repo.md`'s "Every agent gets the standard" says.
When `.review/build/outcome.md` exists, go back into the build as "The Build Record" says; the
waves number on from the last.

**The depth.** Run `python3 "<plugin root>/scripts/depth_floor.py" <base>` as step 8 does, an
untracked path the change does not own handled as it says there. Light runs the light build and
standard the wave, as `<plugin root>/skills/implement-change/reviews/wave.md` "Depth" sets out;
the depth is never lowered. At deep, run the wave as at standard and record `Depth: deep`: step
8's return to step 3 does not apply, since there is no plan to draft, and the close names a
planned build, `/lasp-dev:implement-change <the goal>`, as the alternative.

**Step 8** runs as written, each reviewer's header carrying `Plan: none` and the goal as `Brief:`,
and a finding that would change the goal or the scope stopping as `wave.md`'s "Stops" says.
`outcome.md`'s `Nominated:` and `Procedure:` lines hold the corrections made at step 9, a verify
having no plan's `## Corrections`, and read `none` when there are none.

**Step 9** shows the diff grouped by file, not by plan step, and lists each fix the wave made in
the person's work, by finding and file. On the default branch, the same widget asks for a branch
name, in the repository's branch naming, and step 10 branches before it commits, unless the
repository's instructions say it commits to its default branch, as step 6 says. A change asked
for here is a diff-gate correction, kept for those lines: go back into the build as "The Build
Record" says, make the change directly, since verify has no step 7, and run step 8 again.

**Steps 10 to 12** run as written. Step 11 hands `pr-create` the goal, in the person's words, as
the why. The last line of step 12 names `/lasp-dev:pr-create` when no pull request was opened, or
`/lasp-dev:implement-change verify` to go back in, since `/lasp-dev:work` routes no build
without a plan; once one is open, it names `/lasp-dev:work`.
