---
name: downstream
description: >
  Says which consuming repositories a change breaks and what bump it owes; also diagnoses a red
  CI run and follows a release to the consumers' pins. Use when asked "who does this break",
  "check downstream" or "why did main go red".
argument-hint: "[check [branch | symbol] | ci <run> | release <version>]"
metadata:
  author: lasp-dev
  version: 1.0.4
---

## When to run

- **`check`**, the default: before a change that removes or renames anything consumers import
  merges. With no argument, the working tree's diff against the base: the base the review wave
  passes, or else the default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`); with
  a branch, that branch's commits against the same base; with a symbol, that one name.
  `implement-change`'s review wave runs it when `scripts/surface_diff.py` lists anything.
- **`ci <run>`**: a red run on main or the daily build with no change of its own.
- **`release <version>`**: after an upstream release, to say which consumers' pins now lag.

The constellation, the blast radius and the pin semantics are
`${CLAUDE_SKILL_DIR}/../using-curryer/SKILL.md` and its `references/downstream.md`. Read both
first. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.
Every file it writes follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`, "Writing a
file".

Every checkout this skill makes is a `git clone --shared` under `.review/downstream/`: it reads
the sibling clone's objects and writes nothing into that clone, its branch, its lock file or its
`.git`. The person's sibling clones are only read. A checkout an earlier run left
(`src-<consumer>`, `self-<branch>`, `upstream-<tag>`) is removed before its clone is made again,
so a verdict never names a sha its lane did not run at.

## check

1. **The surface.** Run `python3 "${CLAUDE_SKILL_DIR}/../../scripts/surface_diff.py" <base>` from
   the repository's top level, adding `--head <branch>` for a branch, and write its output to
   `.review/downstream/surface.txt`. With a symbol as the argument, the surface is that one name.
   An exit of 1 is a stop: say its stderr, and never read the empty output as nothing removed.
   Nothing listed: say so and stop, since nothing a consumer imports went away; when stderr says
   the product definitions were not read, say that too, since a removal there is not covered.
2. **The consumers.** The list `using-curryer`'s `references/downstream.md` section 1 points to
   for this repository. A consumer not cloned beside this one
   (`$(git rev-parse --show-toplevel)/../<repo>`) is named as unread.
3. **The consumer's default branch.** For each cloned consumer, its default branch as the
   sibling clone last fetched it, `git -C ../<consumer> rev-parse refs/remotes/origin/HEAD`, never
   the branch the clone has checked out. With no `origin/HEAD`, the consumer is unread, and the
   report says to run `git remote set-head origin --auto` there. Clone it, `git clone -q --shared
   --no-checkout ../<consumer> .review/downstream/src-<consumer>` and `git -C
   .review/downstream/src-<consumer> checkout -q --detach <sha>`, and record `git -C ../<consumer>
   status --porcelain --ignored` as it stands, ignored files included, since a lock file or a
   venv the consumer ignores is what an install there would write. Everything below reads and runs in `src-<consumer>`.
4. **The use sites.** For each surface line, its name's last dotted part and, on an `enum` or
   `identifier` line, its fourth field, the member's value, run `git -C
   .review/downstream/src-<consumer> grep -n -w -F -e <term>` for each: per consumer, the use
   sites as `repo/path:line`, or none. When this repository is curryer, also launch one
   `ticket-investigator` per consumer, in one message, fresh, for use through libera_utils: its
   goal "find what calls the libera_utils functions that call these names", the surface lines as
   its claims, and no synonyms.
5. **The pins.** Read each consumer's pin as `references/downstream.md` step 3 says, and say
   when the change would reach it.
6. **The consumer lanes.** For each consumer with a use site, and only those, after one line
   naming them and saying each install takes minutes:
   - create `.review/downstream/venv-<consumer>/` with `python3 -m venv`; install the consumer
     with its test dependencies from `src-<consumer>`, as its instruction files say (a Poetry
     project: `VIRTUAL_ENV=<venv> poetry install --with dev` there). A lock file the install
     refuses as out of date is an install failure; the skill never runs `poetry lock`. When the
     consumer commits no lock file, say that the install resolved one fresh. Then install this
     repository over it with `pip install --no-deps`, from the working tree (for `check` with no
     argument) or from `.review/downstream/self-<branch>`, a `git clone --shared` of this
     repository checked out at the branch;
   - run the consumer's unit lane, its profile's `tests.command` or the lane its instruction
     files name, never a lane that needs the network, through `pytest-runner`, given the
     venv's interpreter and `src-<consumer>` as the top level.
   An install that fails is reported as that, never as a break. Then compare `git -C ../<consumer>
   status --porcelain --ignored` with what step 3 recorded: any difference is a stop that names the
   changed paths, since the run wrote into the person's clone.
7. **The verdict**, per consumer, naming the consumer's ref and sha it was read at: `breaks` (a
   lane test fails on a removed name, or a use site names one and no lane covers it), `does not
   break`, or `unread`; when it breaks, the bump this repository owes (a removal is a major bump
   wherever the version is 1.0 or above, a minor one below) and the pin change the consumer owes.
8. **The drafts.** For each consumer that breaks, write `.review/downstream/ripple-<consumer>.md`,
   a prompt `ticket-draft` takes as its source: the removed names, the use sites, the failing
   tests, and the pin to move to. Then the pin-bump plan: per consumer, its pin line now and
   after, in the order they land, upstream first.

Write the whole report to `.review/downstream/report.md` and print its verdict lines:
`<consumer> @ <ref> <sha> · breaks | does not break | unread · <one-line reason>`, then `Ripple:
predicted <consumers or none> · verified <consumers or none> · breaks <consumers or none>`:
predicted, the consumers with a use site in step 4; verified, the ones whose lane ran in step 6;
breaks, the verdicts. Each slot that names no consumer reads `none`: `scripts/record.py` refuses
an empty one.

## ci <run>

Read the red run and the last green run of the same workflow on the same branch through the
GitHub server `${CLAUDE_SKILL_DIR}/../using-github/SKILL.md` picks, or `gh run view --log` on the
gh path. When the server cannot read them, say so as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the two runs' logs being what is lost,
and offer the `gh` path; when that cannot read them either, say so and stop.

Compare the dependency versions each run resolved, from its install step's log. When an upstream
in the constellation released between them, run `check` on the upstream's tags: step 1 runs
`surface_diff.py <green tag> --head <red tag>` with the upstream's sibling clone as its working
directory, which reads that clone and writes nothing to it; the consumer is this repository, cloned
to `src-<repo>` at the red run's commit in place of step 3's default branch; and step 6 installs the
upstream from `.review/downstream/upstream-<red tag>`, a `git clone --shared` of the upstream's
sibling clone checked out at the red tag. Otherwise report the failing tests and the commits between the
two runs, and hand to `ticket-draft` with a prompt written to `.review/downstream/ci-<run>.md`,
as a Bug.

## release <version>

1. Confirm the version on `main` matches `<version>`, is above the last tag, and has a changelog
   heading where the repository keeps a changelog. Say any mismatch and stop.
2. Print the tag command for the lead to run, `git tag <version> <sha> && git push origin
   <version>`, in the repository's tag format. Never run it.
3. For each consumer, its pin against `<version>`: current, or lagging with the bump class the
   release carries, and the consumer-lane result from `check` against the release when one has
   run in this session, else `not run`.

## Never

- Post, push, tag, or open anything.
- Write outside `.review/downstream/`, or into a sibling clone: no checkout, worktree, lock file
  or install there.
- Install into anything but a venv under `.review/downstream/`, or run a lane that needs the
  network or real credentials.
- Report a consumer as safe without reading it.
