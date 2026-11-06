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
repository last; "Analysts" and "The bar" read this repository's records alone, since they read its code;
"Guidance" runs on each covered repository's comment lists, before the next harvest empties its
directories, into `<guidance>`: `.review/harvest/guidance/` for this repository and
`.review/harvest/guidance-<repo>/` for another, so neither run removes the other's; "Clusters"
pools them all.

Then run `python3 "<plugin root>/scripts/comment_list.py"` with each of the harvest's dumps,
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

## Guidance

Read every comment for guidance, apart from how its thread was settled, for the repository just
harvested, into its `<guidance>` ("Records"). First remove that directory alone, since its slices
are numbered afresh. Then cut the repository's comment lists, each `.review/harvest/threads/pr-NNNN/comment-list.json` "Records" wrote, into
slices of whole pull requests in order of number, each slice adding pull requests until the next
would take it past 300 comments; a pull request of more than 300 is a slice alone. Run one
`guidance-extractor` per slice, launched as "Analysts" launches agents, each given its slice's
comment lists, the standard's ledger, its decisions file, its agent guidance and data conventions
files and the instruction file, each path or `none`, the instruction file `none` for another
repository, whose own is not checked out here, and the path `<guidance>/slice-<n>.json`, n from 1. Never repeat a slice's
JSON: an extractor that returns `write failed: <error>` could not write it, and you write the JSON
that follows that line, without it, to its path.

Then run `python3 "<plugin root>/scripts/guidance_check.py" <every slice> --comments <every comment
list>` once. A `refused` line naming a comment list is a fault in "Records", and stops the step
with its line. A `refused` line naming a slice sends that slice's extractor back once, given its
lines. A `pr <n> · in no slice` line sends back the slice the cut gave pull request n, or, when no
slice was given it, is a cut to make again, as is a slice too large. Then check again. A slice
still refused, after it went back once, is not read: check again without it and its comment
lists, and name its pull requests and its lines with what was not read. The printout of the
check that passes is the guidance's count. Then run `python3 "<plugin root>/scripts/guidance_tally.py"`
with the same slices and lists, writing its printout to `<guidance>/tally.txt`: its
`admit`, `covered`, `hold` and `support` lines, each with the comment's own words, and its `ask`
lines, each a person asking for a point to be kept, are what "Clusters" and the caller read (`docs/contracts.md`, "The guidance tally"). With
no comment list, or none left once the unread slices are set aside, no check runs, and the count
is `none read`.

## Clusters

Group what people asked for by the principle it states, whatever its words and whichever pull
request it came from: two statements join when the same change to the standard would answer both,
and a cluster whose statements would need two different changes, such as one rule for docstrings
and another for user documents, is two clusters. A statement joins one cluster only, and one that
joins nothing is a cluster of one.

With "Guidance" run, the statements are the guidance tally's `admit`, `hold` and `support` lines;
its `covered` lines support the entry they name and join nothing. Write
`.review/harvest/clusters.json` (`docs/contracts.md`, "The guidance clusters"): each cluster's
kind, the destination "Destinations" sends it to, the kind of most of its people's lines, since
the script takes only a kind one of its lines carries; its principle in one sentence; its tally lines by key; as notes, each analyst `asked:` line not `none`,
`pr-NNNN · <opener login> · <by> · <source> <id>: <asked>`, so a person's ask the extractor read as
one pull request's still counts toward the Recurring ask Dial, and each pasted note as `pasted
<file> · <name> · <the ask>`; and the title of the ledger's held candidate it continues, when one
states the same principle, so the evidence of earlier revisions joins it. Then run `python3
"<plugin root>/scripts/guidance_clusters.py" --clusters .review/harvest/clusters.json --tally
.review/harvest/guidance/tally.txt --ledger <the ledger>`, adding, for a standard covering
several repositories, one with `profiles/`, `--repo <this repository>`, and `--tally-from <repo>=.review/harvest/guidance-<repo>/tally.txt`
for each other whose "Guidance" ran this run, the rest named under "Not read", whose tally lines are keyed `<repo>:s<n>-<i>` and pull requests `<repo>/pr-NNNN`
in the clusters file, its notes and the ledger's `prs:` lines; on its `refused` lines, correct the file
and run it again. Its printout is the clusters the caller reads: each one's pull requests, people
and clearest quotes, counted by the script, never by hand: its pull requests are those a person
asked on, which the Recurring ask Dial counts, and a cluster whose people are none, all its words
an agent's or a bot's, is not admitted. The partition and each cluster's kind are the driver's
judgment, and the script holds them to one cluster per statement, a kind one of its lines carries,
and does the counting.

Without "Guidance", group the analysts' `asked:` lines from threads (people's, bots' and a review's
uncited findings), review bodies and conversation comments, leaving out `asked: none`, with
whatever else the caller adds. From people's threads, review bodies and conversation comments,
count only the lines whose analyst `by:` is `human` (the analyst's word, not the record's login),
the pull request author's own included; a cluster whose lines are all AI-drafted is not admitted
as a rule.

## Destinations

Each admitted cluster goes where its kind sends it, held to the rest of that kind's bar; the
guidance tally has already read the part of the bar a statement's signal decides. Without
"Guidance", every cluster is a rule.

| Kind | The rest of its bar | Proposal | Where `apply` writes it |
| --- | --- | --- | --- |
| `rule` | `rule-bar.md`, through "The bar" | `R-NNN` | the ledger |
| `agent-guidance` | a person's quote that names the habit | `A-NNN` | `agent-guidance.md` |
| `data-convention` | its source, the document with its version and section or the data's owner, named in the evidence or found by the driver | `F-NNN` | `data-conventions.md` |
| `process` | practiced in two merged pull requests, its cluster's `prs` 2 or more, or stated as the team's way by a person, an `admit` line whose signal is `states a principle` | `D-NNN` | `decisions.md` |
| `decision` | as `process` | `D-NNN` | `decisions.md` |
| `tool-config` | the rule exists in the linter the repository configures, and its count of violations on `origin/main`, run with that rule alone, is shown under the proposal; at none, proposed; otherwise held `no override` with that count, and a `ticket/` for the fixes proposed in its place, so the setting comes once `main` is clean | `tool/<rule>` | the lint configuration, in this repository's diff |
| `exemplar` | the code it points to is still at its path on `main`, by `git ls-files` | `exemplar/<path>`, the code's path | the instruction file |
| `review-calibration` | as a rewording when it names a rule; none otherwise | `R-NNN`, rewording the rule's one `Do not flag:` line; otherwise `D-NNN` | the rule's entry, held to "The bar"; otherwise `decisions.md` |
| `open-question` | none | `question/<slug>` | `decisions.md`, as a `D-NNN` stating the group's answer |

An `A-NNN` or `F-NNN` entry is drafted in the form `docs/contracts.md`'s "Agent guidance and data
conventions" sets, numbered after the highest in the file and in `<archive>`, as a `D-NNN` is in `decisions.md`, its months the
window's last until `apply` sets the month it reaches `main`, its `said:` lines the cluster's
people's quotes, into `.review/backtest/<id>.entry.md`, and under its proposal in the report, as a rule's
`scope:` and `example:` lines are. Append it to a copy of the file, or of
`<plugin root>/standards/templates/<file>` when the standard has none, under `mktemp -d`, keeping
the file's name, and run `python3 "<plugin root>/scripts/entries_lint.py"` on the copy; a `D-NNN`
takes the form of `docs/standards.md`'s "Example decision: fail loud", appended to a copy of
`decisions.md` under `mktemp -d` that `rule_lint.py --checks fields` reads as a `--decisions` file
with `--ledger` and `--profiles` as "The bar" gives them, its status `**provisional**`, since
a rule that implements a decision carries its status, with a `repos:` line naming this repository
in a standard with `profiles/`. A proposal whose bar or lint fails is held, the failed
check named, and never recommended a plain `accept`; a data convention with no source is held
`no source named`, and agent guidance whose quotes are all pasted, with no link, `no quote with a
link`; no override accepts either, nor a lint failure, since the entry cannot be written. An
override accepts only a rule's gates and the `process` and `decision` count, its reason on a
decision's date line as `override <YYYY-MM-DD>: <reason>`.

A cluster a live entry of its kind already covers changes that entry: a rule is reworded, a
decision superseded by a new `D-NNN`, an agent guidance entry seen again, and a data convention
gets a proposal on its `F-NNN`, recommended `escalate: <its source>`, since only its owner changes
it. A `covered` line naming an `A-NNN`, or
a finding keyed `agent/A-NNN` in the window's records, is the habit seen again: that entry's
`seen` month moves to the window's last; either is enough.

## The bar

For each drafted rule, draft its entry with `scope:` and `example:` lines as the shared
`rule-bar.md` sets out, the not-on anchor at the merge commit of the fix its evidence pull request
merged, and its wording, into `.review/backtest/R-NNN.entry.md`: as the entry's `> ` lines, or, where
the ledger still links an instruction file, under a `### R-NNN · <title>` heading after the entry. If you cannot think of a case
where the rule should not apply, say so on its `Do not flag:` line rather than inventing one. Run `python3 "<plugin
root>/scripts/rule_lint.py" --entry <that file> --repo .` with a `--decisions` for each decisions
file the caller names; an exit 2 (`CANNOT RUN`) stops the step with its line. The lint's
`anchors` gate checks each anchor resolves in merged code; a probe, which asks an agent whether
the rule fires there, runs only when the person asks for one, since a probe shown its own example
confirms it. On that ask, one
`rule-probe` per anchor of the `example:` line, launched as "Analysts" launches agents, each given this repository's
path, the text `python3 "<plugin root>/scripts/probe_input.py" <that file>` prints, the drafted
title, wording and `Do not flag:` line and never the entry file or its `example:` line, and one
anchor, or one thread with its pull request's merge commit; an exit 2 stops the step with its
line. Write their blocks to `.review/backtest/R-NNN.md`. Under the proposal or candidate, in the caller's report: the drafted
`scope:` and `example:` lines, then `bar: ok` or the lint's lines, then `probe: <anchor>
fires|silent|cannot read; <anchor> fires|silent|cannot read`, or `probe: none` when none was asked for. A rule a gate fails is held, with the failed check named,
and never admitted or recommended a plain `accept`. A probe that disagrees with the example line
is printed and holds nothing.
