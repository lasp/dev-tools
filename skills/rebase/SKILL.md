---
name: rebase
description: >
  Rebases the current branch onto the fetched default branch, or its pull request's base,
  resolving the conflicts that have one objectively clear resolution and stopping to ask at any
  where the two sides differ in intent or approach. Never pushes: it prints the push command for
  you to run. Use when asked to "rebase this" or "rebase onto main". Not for the rebase pr-fix
  offers during a review round.
argument-hint: "[target] [just show me]"
metadata:
  author: lasp-dev
  version: 1.0.0
---

# Rebase

Bring the current branch up to date with its target, resolve what has one right answer, and
stop at what needs the person's judgment. Invoking this skill is the authorization to rewrite
the local branch, and nothing more: **this skill never pushes**; step 6 prints the command for
the person to run. Every question follows
`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is
`${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## Options

The person's words override each default but the push, at invocation or at any stop.

| Option | Default |
|---|---|
| Target | `<remote>/<default branch>`, fetched first; `<remote>/<base>` of the open pull request when the person picks it in step 2. A branch the person names, such as "main", means `<remote>/<name>` when the remote has it, fetched first; the local branch only when they say "local", or name `refs/heads/…` or a commit |
| Conflicts | Resolve the clear ones, ask at the rest; "don't resolve anything" or "just show me" resolves none and shows each one as step 4 shows a conflict it asks about |
| Push | Never, even when asked: step 6 prints the command for the person to run |

## 1. Check the Tree

**A rebase already in progress comes first**: `git rev-parse --git-path rebase-merge` and `--git-path
rebase-apply` name directories that exist only during one. In it, `head-name` holds the branch,
`orig-head` the recovery point and `onto` the target. Say so and ask: carry it on (Recommended,
since the conflicts already resolved in it are kept), abort it, or stop. To carry it on, take the
branch, recovery point and target from those files; a `head-name` of `detached HEAD` is no
branch, so step 6 prints no push. HEAD is detached and holds only part of the branch, so step 2's
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
rules) forbid a rebase or a force-push, say so, quoting the line, and ask: stop and merge the
target instead, which the person runs (Recommended, as the rules ask); rebase anyway; or `Let's
discuss`.

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
  (`git remote -v`) names the head's repository. When no remote does, say so; step 6 prints no
  command.

Otherwise read the branch's upstream (`git rev-parse --abbrev-ref --symbolic-full-name @{u}`).
One that is the target, any remote's default branch or a local branch is where the branch
started, not where it is published, as `git switch -c <branch> origin/main` sets by default: say
that it is set aside, and why. Any other upstream may be where the branch is published under
another name, as a pull request's head on a fork is: say so and ask the person where the branch is
published. Their answer is `<dest>` and `<push remote>`; until they give one, step 6 prints no
command. With no upstream, or one set aside, `<dest>` is `<branch>`, on the first remote set of
`branch.<branch>.pushRemote`, `remote.pushDefault` and `origin`. When `<dest>` is the target's
branch or any remote's default branch (`git symbolic-ref refs/remotes/<remote>/HEAD`), say so;
step 6 prints no command.

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

## 3. Read the Test Command

Where `git remote get-url <remote>`, for the remote the target comes from, names a repository,
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field tests.command` prints the
suite. An empty value, `not yet recorded`, or an exit 1 is no command; say so, and go on
without it.

## 4. Rebase and Resolve

Print `git rev-parse HEAD`, the recovery point, then `git rebase <target>`. At each stop, take
every conflicted file (`git diff --name-only --diff-filter=U`) and read both sides of each hunk,
with the commit being replayed (`git show REBASE_HEAD`) and what the target changed in that file
since the merge base.

**In a rebase, "ours" is the target and "theirs" is the branch's commit being replayed**, the
reverse of a merge. Name the sides to the person as the target and the branch, never as ours and
theirs.

**A conflict is clear** when one resolution keeps both sides' changes and neither contradicts
the other:

- non-overlapping edits that git placed in one hunk because they touch or adjoin;
- a file moved on one side and edited on the other. A renamed symbol is clear only when, after
  the resolution, a grep of the whole repository finds the old name nowhere it should not be;
- a change of whitespace only, on one side. Indentation that changes block structure, as in
  Python, YAML or a Makefile, is not whitespace;
- a change of import order only, on one side, where no import moved has side effects;
- the same change on both sides, up to whitespace that changes no structure.

Both sides adding code at the same place is clear only when the additions are independent. Two
versions of the same function, test, setting or document section are not.

**Every other conflict is the person's**: the sides change the same behavior differently, take
different approaches to one problem, or one side removes what the other relies on. So is any
conflict you are unsure of, and always a binary file, a lockfile (`uv.lock`, `poetry.lock`,
`package-lock.json`, `Cargo.lock` and the like) or other generated file, which is regenerated
rather than merged, a file one side modified and the other deleted, and a file both sides added.
Resolve the clear hunks in a file first, then ask about the rest of that file in one question:
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
During a rebase HEAD is the target plus the branch's commits replayed so far, so it keeps their
changes to the file, which `<target>` would drop. Run nothing that rewrites files while the
rebase is in progress: no formatter, linter fix or hook. After resolving a file, check that no
conflict markers remain, then `git add <file>`, naming it.

When every conflict at a stop is resolved, `git rebase --continue`, with `GIT_EDITOR=true` so
the commit keeps its message. **Never `git rebase --skip`** unless the person says to skip that
commit by name; a commit whose changes the target already holds is one to show them. An abort
is theirs to choose, at any stop.

## 5. Check the Result

When the rebase completes and any conflict was resolved, run the test command once, when there
is one. A failure is reported with the resolution most likely behind it; ask whether to fix it,
undo the rebase (`git reset --hard <recovery point>`, named in the question), or leave it.

## 6. Report and Print the Push

Say the target and its commit, how many commits were replayed, and each conflict: the file, what
each side did, and whether you resolved it, and how, or the person chose. Then whether the test
command ran and passed. Name the recovery point: `git reset --hard <sha>` returns the branch to
where it was, and `git reflog` holds it after that.

**This skill never pushes**, whatever the person says; asked to, say so and print the command. A
rebase rewrites the branch's commits, so print the one command that publishes them, always with
an explicit destination, which no `push.default` or push refspec can redirect:

- when step 2 recorded a lease: `git push --force-with-lease=refs/heads/<dest>:<recorded sha>
  <push remote> HEAD:refs/heads/<dest>`, which git refuses when the remote branch has moved since;
- otherwise: `git push -u <push remote> HEAD:refs/heads/<dest>`, which also makes it the branch's
  upstream.

When the person chose to rebase anyway under a rule that forbids a force-push, quote that rule
again beside a `--force-with-lease` command.

Never print plain `--force`, a bare `--force-with-lease`, or a push without
`HEAD:refs/heads/<dest>`. **Before printing, check the command's destination**: it is
`refs/heads/<dest>` as step 2 chose it, and neither the target's branch nor any remote's default
branch. When the check fails, print no command, and say why.

With the command, tell the person: if git refuses it, someone pushed there since; run `git fetch
<push remote> <dest>` and `git log --oneline <recovery point>..<push remote>/<dest>` and decide;
do not force. Against HEAD, the rebased commits would show too.
