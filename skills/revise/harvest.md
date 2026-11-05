# Harvest

What `revise`'s `prepare` and `onboard`'s first rules both do with merged pull requests: harvest
their records, read their threads, cluster what people asked for, and hold each drafted rule to
the bar. The caller names what differs: the first day, the cap, where the clusters go and the
decisions files the lint reads. Each section is cited by its heading.

## Records

Run `pr-reader` in `harvest` mode, given this repository and the first day the caller names. It
writes each merged pull request's dump to `.review/harvest/threads/pr-NNNN/` and its record to
`.review/harvest/records/pr-NNNN.yaml`. Given another repository, it writes the same directories,
emptied first, so the caller copies those records away before the next harvest and harvests this
repository last; the sections below read this repository's records alone, since they read its
code.

Then run `python3 "<plugin root>/scripts/comment_list.py"` with each of this repository's dumps,
`.review/harvest/threads/pr-NNNN/`, which writes `comment-list.json` in each: every comment,
replies and review summaries included, with its own authorship (`docs/contracts.md`, "The
comment list"). An exit 1 stops the step with its line.

## Analysts

Run one `thread-analyst` per merged pull request the harvest wrote a record for, at most thirty:
past thirty, the thirty whose records hold the most findings plus pointers under `threads:`,
`reviews:` and `comments:` whose `by:` is not `bot`, the author's own included. First fetch
`main` and run `python3 "<plugin root>/scripts/merge_commit.py" --repo . --ref origin/main` with
each of those dumps' `pr.json`, which prints each pull request's merge commit, the one commit on
`main`'s first-parent history whose subject names it; the `get` result carries none. Then launch
them in messages of at most twenty, Claude Code's limit on agents running together, each sent once
the previous one's agents have all returned; every other launch of many agents in `revise` cites
this. Each is given this repository's path, its dump `.review/harvest/threads/pr-NNNN/`, its
record `.review/harvest/records/pr-NNNN.yaml`, its merge commit, the categories design,
correctness, tests, naming, docs, scope, process and style, and the path
`.review/harvest/analysis/pr-NNNN.md`, where it writes its block and returns `wrote <path>`. A pull request the script prints
`none` for gets no analyst, since a guessed commit would put the `diff:` verdict on the wrong
tree; an exit 2 stops the step with its line. Never repeat a block: an analyst that returns
`write failed: <error>` could not write it, and you write the block that follows that line, without
it, to its path. Then run `python3 "<plugin root>/scripts/block_tally.py" analysis
.review/harvest/analysis/ <pr-NNNN ...>`, naming each pull request this step analyzed and each
whose block the caller let stand in, since the directory keeps blocks from earlier runs; it
counts the blocks and lists what they did not read, and an exit 2
names the block that does not hold its form, to rerun that analyst. The pull requests past the cap or with no merge
commit, the script's reason beside each, and the tally's `mismatch` and `not read` lines are what
was not read.

## Clusters

Group by what was asked: the analysts' `asked:` lines from threads (people's, bots' and a review's
uncited findings), review bodies and conversation comments, leaving out `asked: none`, with
whatever else the caller adds. From people's threads, review bodies and conversation comments,
count only the lines whose analyst `by:` is `human` (the analyst's word, not the record's login),
the pull request author's own included; a cluster whose lines are all AI-drafted is not admitted
as a rule.

## The bar

For each drafted rule, draft its entry with `scope:` and `example:` lines as the shared
`rule-bar.md` sets out, the not-on anchor at the merge commit of the fix its evidence pull request
merged, and its wording, into `.review/backtest/R-NNN.entry.md`: as the entry's `> ` lines, or, where
the ledger still links an instruction file, under a `### R-NNN · <title>` heading after the entry. If you cannot think of a case
where the rule should not apply, say so on its `Do not flag:` line rather than inventing one. Run `python3 "<plugin
root>/scripts/rule_lint.py" --entry <that file> --repo .` with a `--decisions` for each decisions
file the caller names; an exit 2 (`CANNOT RUN`) stops the step with its line. Then one
`rule-probe` per anchor of the `example:` line, launched as "Analysts" launches agents, each given this repository's
path, the text `python3 "<plugin root>/scripts/probe_input.py" <that file>` prints, the drafted
title, wording and `Do not flag:` line and never the entry file or its `example:` line, and one
anchor, or one thread with its pull request's merge commit; an exit 2 stops the step with its
line. Write their blocks to `.review/backtest/R-NNN.md`. Under the proposal or candidate, in the caller's report: the drafted
`scope:` and `example:` lines, then `bar: ok` or the lint's lines, then `probe: <anchor>
fires|silent|cannot read; <anchor> fires|silent|cannot read`. A rule a gate fails is held, with the failed check named,
and never admitted or recommended a plain `accept`. A probe that disagrees with the example line
is printed and holds nothing.
