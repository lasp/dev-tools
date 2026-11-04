---
name: rebase
description: >
  Rebases the current branch onto the default branch, or its pull request's base, resolving
  the conflicts that have one objectively clear resolution and stopping to ask at any where the
  two sides differ in intent or approach; never pushes. Use when asked to "rebase this", "rebase
  onto main" or "update my branch from main". Not for the rebase pr-fix offers during a review
  round.
argument-hint: "[target] [merge instead] [just show me]"
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
| Target | The repository's default branch, fetched first; the open pull request's base when the person picks it in step 2; a branch or ref the person names |
| How | `git rebase`; "merge instead" runs `git merge <target>` under the same conflict rules, and the merge commit it makes is part of the request |
| Conflicts | Resolve the clear ones, ask at the rest; "don't resolve anything" or "just show me" resolves none and shows each one as step 4 shows a conflict it asks about |
| Push | None; step 6 offers it |

## 1. Check the Tree

`git status -sb`. Stop, saying why and what the person can run, when:

- the tree has staged, unstaged or untracked changes: name the paths. **Never stash, commit or
  discard them to make room**; the person chooses.
- a rebase, merge, cherry-pick or bisect is already in progress: say which, and ask whether to
  carry it on under step 4, abort it, or stop.
- HEAD is detached, or the current branch is the target itself.

## 2. Choose the Target

Find the default branch from `git symbolic-ref refs/remotes/origin/HEAD`; when that is not set,
ask rather than guess. A target the person named ends the search.

With no target named, look for the branch's open pull request, reaching GitHub as
`${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md` sets out. When its base is not the default
branch, ask which to rebase onto, the pull request's base first and recommended, since that is
where the branch will merge, with the default branch and `Let's discuss`. When the server cannot
be reached, say so as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the pull request's
base being what is lost, and go on with the default branch.

`git fetch origin <target>`, unless the person said not to fetch or named a local ref. When the
fetch fails, show the error and ask whether to go on against `origin/<target>` as last fetched,
naming its commit and date, or stop.

Say the target, how far behind it the branch is (`git rev-list --count HEAD..<target>`), and
how many of the branch's commits will be replayed. When the branch is not behind, say so and
stop. When the branch holds merge commits, say that a rebase drops them and ask whether to keep
them with `--rebase-merges`, drop them, or merge instead.

## 3. Read the Quick Check

Where `git remote get-url origin` names a repository,
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field lint.command` prints the
linters that take a list of files, and `--field tests.command` the suite. An empty value, `not
yet recorded`, or an exit 1 is no command; say which is missing, and go on without it.

## 4. Rebase and Resolve

`git rebase <target>`. At each stop, take every conflicted file (`git diff --name-only
--diff-filter=U`) and read both sides of each hunk, with the commit being replayed (`git show
REBASE_HEAD`) and what the target changed in that file since the merge base.

**A conflict is clear** when one resolution keeps both sides' changes and neither contradicts
the other:

- non-overlapping edits that git placed in one hunk because they touch or adjoin;
- a pure rename or move on one side, and an edit to the moved or renamed code on the other;
- a change of whitespace or import order only, on one side;
- the same change on both sides, up to whitespace.

Both sides adding code at the same place is clear only when the additions are independent. Two
versions of the same function, test, setting or document section are not.

**Every other conflict is the person's**: the sides change the same behavior differently, take
different approaches to one problem, or one side removes what the other relies on. So is any
conflict you are unsure of. Resolve the clear hunks in a file first, then ask about the rest of
that file in one question: per conflict, the file and lines, both sides as short excerpts, what
each side's commit set out to do in its own words, and a recommendation with its evidence, or
none and why. Offer: the recommended resolution, the other side's, a combination when one
makes sense, `Abort the rebase`, and `Let's discuss`. Leave the rebase paused while the person
decides; the conflict markers stay until they answer.

After resolving a file, check it: no conflict markers remain, and the lint command, when there is
one, passes on that file. A lint failure on a line the resolution wrote makes that conflict the
person's. Then `git add <file>`, naming it.

When every conflict at a stop is resolved, `git rebase --continue`, with `GIT_EDITOR=true` so
the commit keeps its message; on a merge, `git merge --continue` the same way. **Never `git rebase --skip`** unless the person says to skip that
commit by name; a commit whose changes the target already holds is one to show them. An abort
is theirs to choose, at any stop.

## 5. Check the Result

When the rebase completes and any conflict was resolved, run the test command once, when there
is one. A failure is reported with the resolution most likely behind it; ask whether to fix it,
undo the rebase (`git reset --hard ORIG_HEAD`, named in the question), or leave it.

## 6. Report and Offer the Push

Say the target and its commit, how many commits were replayed, and each conflict: the file, what
each side did, and whether you resolved it, and how, or the person chose. Then whether the lint
and test commands ran and passed.

A rebase rewrites the branch's commits, so when the branch has an upstream its next push is a
force-push. **Never push on your own**; ask, naming the branch and the command: `Leave it
local` (Recommended), the person reviewing the result first; `Push with git push
--force-with-lease`, which refuses when the remote moved since the fetch; or `Let's discuss`.
Never plain `--force`, and never push the target. A branch with no upstream pushes with `git push
-u origin <branch>`, asked the same way. Where the repository's instructions forbid an agent's
push, print the command instead, as `using-github`'s "Pushing" says.
