---
name: rebase
description: >
  Rebases the current branch onto the fetched default branch, or its pull request's base,
  resolving every conflict whose resolution the two sides' commits show, dropping commits the
  target already holds, and asking only where the sides want incompatible behavior; then pushes
  on your yes, its lease pinned where the branch is published. Use when asked to "rebase this", "rebase onto main", "replay my
  commits on top of main", "bring my branch up to date with main" or "my branch is behind main".
  Not for answering a review: pr-fix rebases within its round by this skill's conflict rules.
argument-hint: "[target] [just show me]"
metadata:
  author: lasp-dev
  version: 1.0.0
---

# Rebase

Bring the current branch up to date with its target, resolve what the commits on both sides show
the answer to, and stop only at what needs the person's judgment. Invoking this skill is the
authorization to rewrite the local branch; the push is a gate, asked at step 6 with the exact
command. Every question follows
`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is
`${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## Options

The person's words override each default, at invocation or at any stop.

| Option | Default |
|---|---|
| Target | `<remote>/<default branch>`, fetched first; `<remote>/<base>` of the open pull request when the person picks it in step 2. A branch the person names, such as "main", means `<remote>/<name>` when the remote has it, fetched first; the local branch only when they say "local", or name `refs/heads/…` or a commit |
| Conflicts | Resolve the ones the commits show the answer to, ask at the rest; "don't resolve anything" or "just show me" resolves none and shows each one as step 4 shows a conflict it asks about |
| Commits the target holds | Dropped and named in step 6; "keep every commit" asks at each instead |
| Push | Asked at step 6 with the exact command; "and push" at invocation is the yes, given in advance. Printed for the person to run when they choose, or when the loaded rules forbid an agent's push |

## 1. Check the Tree

**A rebase already in progress comes first**: `git rev-parse --git-path rebase-merge` and `--git-path
rebase-apply` name directories that exist only during one. In it, `head-name` holds the branch,
`orig-head` the recovery point and `onto` the target. Say so and ask: carry it on (Recommended,
since the conflicts already resolved in it are kept), abort it, or stop. To carry it on, take the
branch, recovery point and target from those files; a `head-name` of `detached HEAD` is no
branch, so step 6 offers no push. HEAD is detached and holds only part of the branch, so step 2's
check of where the branch is published takes the branch from `head-name`, compares the recovery
point in place of HEAD, and leaves out what the target brings in, since after `git pull --rebase`
the target is the published copy itself: `git log --oneline --cherry-pick --right-only <recovery
point>...<push remote>/<dest> --not <onto>`. Then step 3, then step 4 at the current stop. Under
`rebase-merge`, a stop with no conflicted file is an edit, a break or a failed exec, which the
last line of `done` names: say which, and ask rather than continue. Under `rebase-apply`, every
stop is a patch that did not apply, `next` of `last` naming which. Never `git rebase --continue`
over staged or unstaged changes this skill did not make.

Otherwise `git status -sb`, and stop, saying why and what the person can run, when:

- a merge, cherry-pick or bisect is in progress: say which.
- the tree has staged, unstaged or untracked changes: name the paths. **Never stash, commit or
  discard them to make room**; the person chooses.
- HEAD is detached, or the current branch is the target itself.

When the rules this session loaded (`CLAUDE.md` and what it imports, `AGENTS.md`, the standard's
rules) forbid a rebase, a force-push or rewriting a branch's published history in words that
name it, say so, quoting the line, and ask:
stop and merge the target instead, which the person runs (Recommended, as the rules ask); rebase
anyway; or `Let's discuss`. General care with git, such as asking before a destructive command,
forbids neither: invoking this skill is the ask.

## 2. Choose the Target

The remote is `origin`. When an `upstream` remote also exists, as in a fork, ask which the target
comes from, `upstream` recommended, since that is where a pull request from a fork merges. Say
which remote the target comes from. Find the default branch from `git symbolic-ref
refs/remotes/<remote>/HEAD`; when that is not set, ask rather than guess. A target the person
named ends the search.

Look for the branch's open pull request, reaching GitHub as
`${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md` sets out; its head is read below, where the
branch is published. With no target named, when its base is not the default branch, ask which to
rebase onto, the pull request's base first and recommended, since that is where the branch will
merge, with the default branch and `Let's discuss`. When the server cannot be reached, say so as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the pull request's base and head being
what is lost, and go on with the default branch.

`git fetch <remote> <branch>`; the target is `<remote>/<branch>` from here on. Skip the fetch when
the person says not to fetch or the target is local. When a local target differs from its
`<remote>/` copy, say so, with how many commits each has that the other lacks, before rebasing.
When the fetch fails, show the error and ask whether to go on against `<remote>/<branch>` as last
fetched, naming its commit and date, or stop.

**Where the branch is published.** Step 6's command pushes to one destination, `<dest>` on
`<push remote>`, chosen here from two cases, in order:

- `git config branch.<branch>.merge` is `refs/heads/<branch>`: `<dest>` is `<branch>`, on the
  first remote set of `branch.<branch>.pushRemote`, `remote.pushDefault` and
  `branch.<branch>.remote`.
- The branch's open pull request was found: `<dest>` is its head ref, on the remote whose URL
  (`git remote -v`) names the head's repository. When no remote does, say so; step 6 offers no
  push.

Otherwise read the branch's upstream (`git rev-parse --abbrev-ref --symbolic-full-name @{u}`).
One that is the target, any remote's default branch or a local branch is where the branch
started, not where it is published, as `git switch -c <branch> origin/main` sets by default: say
that it is set aside, and why. Any other upstream may be where the branch is published under
another name, as a pull request's head on a fork is: say so and ask the person where the branch is
published. Their answer is `<dest>` and `<push remote>`; until they give one, step 6 offers no
push. With no upstream, or one set aside, `<dest>` is `<branch>`, on the first remote set of
`branch.<branch>.pushRemote`, `remote.pushDefault` and `origin`. When `<dest>` is the target's
branch or any remote's default branch (`git symbolic-ref refs/remotes/<remote>/HEAD`), say so;
step 6 offers no push.

When `<push remote>/<dest>` exists, fetch it, unless the person said not to fetch, then `git log
--oneline --cherry-pick --right-only HEAD...<push remote>/<dest>`. Any commit it lists is on the
remote and not on this branch, which a rebase and a forced push would lose: stop and name them.
Otherwise record `git rev-parse <push remote>/<dest>` as the lease for step 6.

Say the target, how far behind it the branch is (`git rev-list --count HEAD..<target>`), and
how many of the branch's commits will be replayed. When the branch is not behind, say so and
stop. When the branch holds merge commits (`git rev-list --merges <target>..HEAD`), say that a
rebase drops them and ask. When every one brings in the target, its second parent reachable from
the target (`git merge-base --is-ancestor <merge>^2 <target>`), recommend dropping them, since
the rebase replaces what they did. When any merges another branch, recommend keeping them with
`--rebase-merges`. Offer both, and `Let's discuss`.

**Commits the target already holds.** Git drops a commit whose patch the target holds unchanged
(`git cherry <target> HEAD` marks it `-`). It does not catch one the target holds in another form:
a pull request merged by squash, possibly with review changes, or a fix cherry-picked and amended.
Compare the branch's commits with the target's since the merge base, by subject, pull request
number and diff. When the branch's first commits are already in the target this way, every change
each one makes present in the target as written or as review changed it, say which and why, and
step 4 rebases with `git rebase --onto <target> <the last of them>`, which drops them in one step.
A commit that also carries a change the target lacks, such as one amended after the squash, is
replayed instead, and step 4 takes the target's side only of the hunks the target holds. Any later
duplicate is dropped at its stop in step 4. When the person said to keep every commit, use no
`--onto`: step 4 asks at each.

## 3. Read the Test Command

Where `git remote get-url <remote>`, for the remote the target comes from, names a repository,
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field tests.command` prints the
suite. An empty value, `not yet recorded`, or an exit 1 is no command; say so, and go on
without it.

## 4. Rebase and Resolve

Print `git rev-parse HEAD`, the recovery point, then `git rebase <target>`, or the `--onto` form
step 2 chose. At each stop, take
every conflicted file (`git diff --name-only --diff-filter=U`) and read both sides of each hunk,
with the commit being replayed (`git show REBASE_HEAD`) and what the target changed in that file
since the merge base.

**In a rebase, "ours" is the target and "theirs" is the branch's commit being replayed**, the
reverse of a merge. Name the sides to the person as the target and the branch, never as ours and
theirs.

**Resolve a conflict yourself when the commits show its answer**: what each side set out to do,
read from its commit, can both be kept, or one side's change already holds or supersedes the
other's. Among them:

- non-overlapping edits that git placed in one hunk because they touch or adjoin;
- a file moved on one side and edited on the other, or code refactored on one side and edited on
  the other, the edit carried into the new code. A renamed symbol is resolved only when a grep of
  the whole repository then finds the old name nowhere it should not be;
- a change of whitespace, formatting or import order on one side. Indentation that changes block
  structure, as in Python, YAML or a Makefile, is not whitespace, and an import with side effects
  keeps its place;
- independent additions at the same place, such as imports, list entries, changelog lines or
  separate tests and functions, all kept, in the order the file uses;
- the same change on both sides, or one side's fuller version of it: keep the fuller one;
- a commit the target already holds, as step 2 describes, possibly with review changes since:
  take the target's side of each hunk the target holds, and when the commit then changes
  nothing, `git rebase --skip` it and name it in step 6. When the person said to keep every
  commit, ask at each instead;
- a lockfile (`uv.lock`, `poetry.lock`, `package-lock.json`, `Cargo.lock` and the like) or other
  generated file: resolve its sources, then regenerate it with the repository's tool (`uv lock`,
  `npm install --package-lock-only` and the like) when that tool is installed. Without the tool,
  it is the person's.

**Ask only when the sides want incompatible behavior**: they change the same behavior to
different results, take different approaches to one problem, or one side removes what the other
relies on, and neither commit says which should win. So is a binary file, a file one side
modified and the other deleted, a file both sides added with different contents, and a conflict
the commits leave you unable to resolve with evidence you could state.
Resolve the other hunks in a file first, then ask about the rest of that file in one question:
per conflict, the file and lines, both sides as short excerpts, what each side's commit set out
to do in its own words, and a recommendation with its evidence, or none and why. For a binary,
modify/delete or add/add file, show each side's commit summary and each side's size or hash in
place of excerpts. Offer: the recommended resolution, the other side's, `Abort the rebase`, and
`Let's discuss`; a combination comes through "Other". Leave the rebase paused while the person
decides; the conflict markers stay until they answer.

Resolve a conflicted text file hunk by hunk. Take a whole file from one side only for a binary,
modify/delete or add/add conflict, or when the person says to, by naming its commit: `git checkout
REBASE_HEAD -- <file>` for the branch's commit being replayed, `git checkout HEAD -- <file>` for
the target's side, and `git rm <file>` for the side that deleted it; never `--ours` or `--theirs`.

**The target's side is `HEAD`, never the target's name.** When the person says "take main's side"
or "use origin/main's version", run `git checkout HEAD -- <file>`, not `git checkout origin/main
-- <file>`. During a rebase HEAD is the target plus the branch's commits replayed so far, so it
keeps their changes to the file; the target's name would silently drop them.

Run nothing else that rewrites files while the rebase is in progress, beyond regenerating a
lockfile as above: no formatter, linter fix or hook. After resolving a file, check that no
conflict markers remain, then `git add <file>`, naming it.

When every conflict at a stop is resolved, `git rebase --continue`, with `GIT_EDITOR=true` so
the commit keeps its message. `git rebase --skip` only a commit the target already holds, as
above, or one the person names; never to get past a conflict. An abort is theirs to choose, at
any stop.

## 5. Check the Result

When the rebase completes and any conflict was resolved or commit dropped, run the test command once, when there
is one. A failure is reported with the resolution most likely behind it; ask whether to fix it,
undo the rebase (`git reset --hard <recovery point>`, named in the question), or leave it.

## 6. Report and Push

Say the target and its commit, how many commits were replayed, each commit dropped and why, and
each conflict: the file, what each side did, and whether you resolved it, and how, or the person
chose. Then whether the test command ran and passed. Name the recovery point: `git reset --hard
<sha>` returns the branch to where it was, and `git reflog` holds it after that.

A rebase rewrites the branch's commits, so the one command that publishes them always names an
explicit destination, which no `push.default` or push refspec can redirect:

- when step 2 recorded a lease: `git push --force-with-lease=refs/heads/<dest>:<recorded sha>
  <push remote> HEAD:refs/heads/<dest>`, which git refuses when the remote branch has moved since;
- otherwise: `git push -u <push remote> HEAD:refs/heads/<dest>`, which also makes it the branch's
  upstream.

Never run or print plain `--force`, a bare `--force-with-lease`, or a push without
`HEAD:refs/heads/<dest>`. **Before asking, check the command's destination**: it is
`refs/heads/<dest>` as step 2 chose it, and neither the target's branch nor any remote's default
branch. When the check fails, offer no push and print no command, and say why.

Then ask, showing the command: **Push**, **Print it** for the person to run, or **Stop here**,
keeping the rebase local. Recommend **Push**, since a published branch's pull request shows the
old commits until it runs and a new branch needs it before a pull request can be opened, unless a step-4 conflict was resolved and
the test command failed or there is none: then recommend **Print it**, so the person looks first.
A yes the person gave at invocation that named the push answers the question: say so and run it,
except in that case, where the question is asked again with the resolutions shown.

When the loaded rules forbid an agent's push, or the person chose to rebase anyway under a rule
that forbids a force-push, print the command, quoting the rule, as `using-github`'s "Pushing"
sets out (`${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md`), rather than offering to run it.

If git refuses the push, someone pushed there since: run `git fetch <push remote> <dest>` and
`git log --oneline <recovery point>..<push remote>/<dest>`, show what it lists, and ask; never
force, and never rebase or merge it in on your own. Against HEAD, the rebased commits would show
too. With a printed command, tell the person the same.
