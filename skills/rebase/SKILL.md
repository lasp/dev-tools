---
name: rebase
description: >
  Rebases the current branch onto the default branch, or its pull request's base, resolving
  the conflicts that have one objectively clear resolution and stopping to ask at any where the
  two sides differ in intent or approach; pushes only on your yes. Use when asked to "rebase
  this" or "rebase onto main". Not for the rebase pr-fix offers during a review round.
argument-hint: "[target] [just show me]"
metadata:
  author: lasp-dev
  version: 1.0.0
---

# Rebase

Bring the current branch up to date with its target, resolve what has one right answer, and
stop at what needs the person's judgment. Invoking this skill is the authorization to rewrite
the local branch; a push is not covered by it. Every question follows
`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is
`${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## Options

The person's words override each default, at invocation or at any stop.

| Option | Default |
|---|---|
| Target | `origin/<default branch>`, fetched first; `origin/<base>` of the open pull request when the person picks it in step 2; a branch or ref the person names, used as named |
| Conflicts | Resolve the clear ones, ask at the rest; "don't resolve anything" or "just show me" resolves none and shows each one as step 4 shows a conflict it asks about |
| Push | None; step 6 offers it |

## 1. Check the Tree

`git status -sb`. Stop, saying why and what the person can run, when:

- the tree has staged, unstaged or untracked changes: name the paths. **Never stash, commit or
  discard them to make room**; the person chooses.
- a merge, cherry-pick or bisect is in progress: say which.
- HEAD is detached, or the current branch is the target itself.

A rebase already in progress is asked about: carry it on under step 4 (Recommended, since the
conflicts already resolved in it are kept), abort it, or stop.

When the repository's loaded instructions (`CLAUDE.md` and what it imports, `AGENTS.md`) forbid a
rebase or a force-push, say so, quoting the line, and ask: stop and merge the target instead,
which the person runs (Recommended, as the instructions ask); rebase anyway; or `Let's discuss`.

## 2. Choose the Target

Find the default branch from `git symbolic-ref refs/remotes/origin/HEAD`; when that is not set,
ask rather than guess. A target the person named ends the search.

With no target named, look for the branch's open pull request, reaching GitHub as
`${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md` sets out. When its base is not the default
branch, ask which to rebase onto, the pull request's base first and recommended, since that is
where the branch will merge, with the default branch and `Let's discuss`. When the server cannot
be reached, say so as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the pull request's
base being what is lost, and go on with the default branch.

`git fetch origin <branch>`, and the target is `origin/<branch>` from here on; a local branch is
the target only when the person names it. Skip the fetch when the person says not to fetch or
names a local ref. When the fetch fails, show the error and ask whether to go on against
`origin/<branch>` as last fetched, naming its commit and date, or stop.

When the current branch has an upstream (`git rev-parse --abbrev-ref --symbolic-full-name @{u}`),
fetch it too, then `git rev-list --count HEAD..@{u}`. When that is not 0, the remote holds
commits this branch does not, which a rebase and a forced push would lose: stop and name them
(`git log --oneline HEAD..@{u}`). Otherwise record `git rev-parse @{u}` for step 6.

Say the target, how far behind it the branch is (`git rev-list --count HEAD..<target>`), and
how many of the branch's commits will be replayed. When the branch is not behind, say so and
stop. When the branch holds merge commits, say that a rebase drops them and ask: keep them with
`--rebase-merges` (Recommended, since dropping them changes history the person made on
purpose); drop them; or `Let's discuss`.

## 3. Read the Test Command

Where `git remote get-url origin` names a repository,
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field tests.command` prints the
suite. An empty value, `not yet recorded`, or an exit 1 is no command; say so, and go on
without it.

## 4. Rebase and Resolve

Print `git rev-parse HEAD`, the recovery point, then `git rebase <target>`. At each stop, take
every conflicted file (`git diff --name-only --diff-filter=U`) and read both sides of each hunk,
with the commit being replayed (`git show REBASE_HEAD`) and what the target changed in that file
since the merge base.

**A conflict is clear** when one resolution keeps both sides' changes and neither contradicts
the other:

- non-overlapping edits that git placed in one hunk because they touch or adjoin;
- a file moved on one side and edited on the other. A renamed symbol is clear only when, after
  the resolution, a grep of the whole repository finds the old name nowhere it should not be;
- a change of whitespace only, on one side. Indentation that changes block structure, as in
  Python, YAML or a Makefile, is not whitespace;
- a change of import order only, on one side, where no import moved has side effects;
- the same change on both sides, up to whitespace.

Both sides adding code at the same place is clear only when the additions are independent. Two
versions of the same function, test, setting or document section are not.

**Every other conflict is the person's**: the sides change the same behavior differently, take
different approaches to one problem, or one side removes what the other relies on. So is any
conflict you are unsure of. Resolve the clear hunks in a file first, then ask about the rest of
that file in one question: per conflict, the file and lines, both sides as short excerpts, what
each side's commit set out to do in its own words, and a recommendation with its evidence, or
none and why. Offer: the recommended resolution, the other side's, `Abort the rebase`, and
`Let's discuss`; a combination comes through "Other". Leave the rebase paused while the person
decides; the conflict markers stay until they answer.

Run nothing that rewrites files while the rebase is in progress: no formatter, linter fix or
hook. After resolving a file, check that no conflict markers remain, then `git add <file>`,
naming it.

When every conflict at a stop is resolved, `git rebase --continue`, with `GIT_EDITOR=true` so
the commit keeps its message. **Never `git rebase --skip`** unless the person says to skip that
commit by name; a commit whose changes the target already holds is one to show them. An abort
is theirs to choose, at any stop.

## 5. Check the Result

When the rebase completes and any conflict was resolved, run the test command once, when there
is one. A failure is reported with the resolution most likely behind it; ask whether to fix it,
undo the rebase (`git reset --hard <recovery point>`, named in the question), or leave it.

## 6. Report and Offer the Push

Say the target and its commit, how many commits were replayed, and each conflict: the file, what
each side did, and whether you resolved it, and how, or the person chose. Then whether the test
command ran and passed. Name the recovery point: `git reset --hard <sha>` returns the branch to
where it was, and `git reflog` holds it after that.

A rebase rewrites the branch's commits, so when the branch has an upstream its next push is a
force-push. **Never push on your own**; ask, naming the branch and the command: `Leave it
local` (Recommended), the person reviewing the result first; `Push with git push
--force-with-lease=<branch>:<recorded sha> origin <branch>`, which refuses when the remote branch
is no longer at the commit step 2 recorded; or `Let's discuss`. Never plain `--force` or a bare
`--force-with-lease`, and never push the target. A branch with no upstream pushes with `git push
-u origin <branch>`, asked the same way. Where the repository's instructions forbid an agent's
push, print the command instead, as `using-github`'s "Pushing" says.
