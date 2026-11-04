# First rules

`onboard`'s step 6, on the person's yes: a repository's first review rules, drafted from its
merged review threads, its instruction files, its code and the documents the person names. A
repository whose `standards/review-rules.md` exists already has its rules, and
`/lasp-dev:revise` changes them. The harvest, the analysts, the clustering and the bar are the
sections of `<plugin root>/skills/revise/harvest.md` each step names, the ones every revision
runs.

## The shared corpus

"Shared" below means two places: `<plugin root>/standards/`, which holds `rule-bar.md` and
`dials.md`, and the standard, `<standard>/`, the directory `python3 "<plugin root>/scripts/profile.py" --standard` prints, the standard elsewhere or the repository's own `standards/`, which holds `terminology.md`, `decisions.md`, `context/` and `archive/`;
when it exits 1 ending "the repository has no standard", only the first place is read, and any
other exit 1 stops this step with its message. This step only reads them: its candidates for them
go to `.review/harvest/`, and a person commits the ones kept where `revise`'s "The standard's
repository" puts them, asked before any push, never in the installed plugin. A bare `standards/` path means this repository's own. A read of the
shared corpus that fails is an error: say so with the path, and never read a copy from anywhere
else or invent a term or a decision to fill the gap.

## Reads

- Merged pull requests and their review threads, through harvest.md's "Records" and "Analysts".
- `.github/instructions/*.instructions.md`, `CLAUDE.md`, `AGENTS.md`,
  `.github/copilot-instructions.md`, `pyproject.toml`, `.pre-commit-config.yaml`,
  `doc/source/developer-docs/`.
- Public names and the docstrings that explain a subsystem.
- The shared `standards/rule-bar.md`, which every candidate passes before it is a rule.
- The Confluence pages and Jira epics the person lists, through the Atlassian MCP server,
  read-only.

## The sample

The sample is every merged pull request with a thread, review body or conversation comment a
person wrote, the pull request author's own included, at most thirty, ranked past thirty as harvest.md's "Analysts" ranks them. It must hold:

- **At least five merged pull requests with review threads** a person wrote (`authorship:
  human`), whoever wrote them, the pull request's author and whoever runs the harvest included:
  on a small team one person's well-founded ask is as good as anyone's.
- **At least one pull request merged before the repository adopted AI assistance, if one
  exists**, in place of a ranked one when the ranking leaves it out. The date is the first thread
  written by a review bot, not the pull request that added the instruction files: the two can be
  months apart, with the bot first. A repository a bot has reviewed since the beginning has no
  baseline; say so rather than calling the oldest pull request one. A harvest that started at a
  window's first day did not read before it: say the baseline was outside the window, not that
  none exists.
- Every thread carries **who wrote it** and whether it was **human or AI-drafted**.

Report the sample against each of these before writing a single candidate. If it cannot be
met — a young repository with few reviewed pull requests — say so, and ask, as `onboard`'s
step 6 says, before drawing what exists; every candidate the shortfall affects is marked, rather than quietly
harvesting a narrower sample.

## A standard elsewhere

For a repository whose standard lives in another repository, the candidates are for that
standard: read its ledger, decisions and terms from the clone onboarding's step 1 made, or, run
alone, from the directory `python3 "<plugin root>/scripts/profile.py" --standard` prints. Drop a
cluster a rule there already covers, naming the rule. Number the candidates from the ledger's
next free id, and give each a `repos: [<this repository>]` line, since its evidence is this
repository's alone; the person widens it when the rule is the project's. Lint them with `--profiles`
naming the standard's `profiles/`, which holds `profiles/<this repository>.yaml` by then: `onboard`'s
step 6 drafts for a standard elsewhere only once the repository is covered. The person commits the ones kept in the standard's repository,
as `revise`'s "The standard's repository" sets out.

## Writes

`.review/harvest/` and `.review/backtest/` only: `threads.yaml` (the per-thread records below),
`measurements.md`, the rules (`review-rules.md`, the ledger entries, every one provisional unless it implements a decision, whose status it carries,
since the Established Dial counts agreed findings that cite a rule and no finding cites one before
it exists, each entry holding its rule's wording as `> ` lines, the one copy), `terminology.md`, `decisions.md`, `context/`, and
`already-checked-by-tools.md`, with the bar's entries and probe blocks under `.review/backtest/`.
Rule and decision wording follows `<plugin root>/skills/writing/SKILL.md`. `review-rules.md` ends
with a section headed exactly `## Candidates below the criteria`, the line `standard_file.sh` stops
the loaded standard at: every cluster not admitted, with its evidence pull requests, authors and
the criterion it fails. Nothing under `standards/`. A person cuts the candidates and commits.

Every harvested thread is one record, and these fields are what the monthly revision later filters on:

```yaml
pr: 43
pr_author: <handle>
merged: 2026-08-24
thread_author: <handle>
source: thread # thread | review | comment
authorship: human # human | bot | ai-drafted
asks_for: a change # a change | a question | an acknowledgment
cluster: units-on-published-quantities
```

`authorship` is as `record.py`'s `authorship_of` decides and `thread-analyst` reports it. Report
the share of AI-drafted threads in its own right, separate from which rules it disqualifies.

## Steps

1. Run harvest.md's "Records" from the repository's first merge, or from the first day of the
   window the person chose at `onboard`'s step 6, telling `pr-reader` `Judge: no`,
   since nothing here reads a verdict. Records already in `.review/harvest/records/` stand in for
   it, and the report names the earliest merge they cover and how many of the pull requests that
   `main`'s first-parent subjects name, as `merge_commit.py` reads them (`(#N)` or `Merge pull
   request #N`), have no record; `pr-reader` writes none for a pull request with no review, and a
   rebase merge names none. An analysis block already in
   `.review/harvest/analysis/` stands in for "Analysts" for its pull request, so that pull request
   needs no dump. A sampled pull request with neither a block nor a dump under
   `.review/harvest/threads/` cannot be analyzed: it leaves the sample as one that could not be
   read, below. Draw the sample from the records and report it against the three requirements
   above. Then run "Analysts" on the sample, its pull requests in place of every record. A pull
   request it could not read leaves the sample, with its reason, and the sample is reported again
   against the floor; a shortfall goes to `onboard`'s step 6 question. Write the per-thread
   records into `.review/harvest/threads.yaml` from the records' `author:` and `authorship:` and
   the analysts' `by:` and `asked:` lines of every source, each with its `source:`, before
   anything is clustered.
2. Count, and write the counts into `.review/harvest/measurements.md`: merged pull requests per
   month, threads per pull request, review bodies and conversation comments with a person's ask
   per pull request, the AI-drafted share, the share a linter could have caught,
   and distinct concerns raised more than once.
3. Run harvest.md's "Clusters" on every thread, review body and conversation comment, reading
   each `asked:` line, never sorting them by keyword; report a cluster whose lines are all
   AI-drafted as a candidate for a check, never as a rule. Drop
   anything a configured linter or pre-commit hook already enforces and list it under "already
   checked by tools" with the tool and rule ID: it is the measurement's linter share, and a
   do-not-flag line on any candidate it overlaps.
4. Drop anything that was a one-off design question; it belongs in `context/`, not a rule.
5. For each surviving cluster write the candidate's wording, as the writing skill's
   "Conventions" says under Rule wording, then its `Do not flag:` line for the ledger; the
   evidence pull requests, with their authors, go on its ledger entry. Number the candidates from
   R-001, since a repository with no ledger has no rule ids to collide with, or, for a standard
   elsewhere, from its next free id.
6. Extract terms where two names mean one thing, or a name carries a unit, frame or epoch.
7. Reduce each listed page to a link, today's date and one paragraph saying what it decides and
   which parts of the code it constrains, from one `source-reader` with the task `page <id>` per
   page, all in one message. Copy nothing. A page the block lists as `Withheld:` gets no paragraph
   until the person clears it; its question goes to them.
8. Run harvest.md's "The bar" on each candidate that meets admission, with the decisions files
   `<standard>/decisions.md` and, when this run wrote one, `.review/harvest/decisions.md`. Each
   admitted candidate's ledger entry in `.review/harvest/review-rules.md` carries the `scope:` and
   `example:` lines of its `R-NNN.entry.md`; the `bar:` and `probe:` lines go in this step's
   report, never the ledger. A candidate a gate fails goes
   under "Candidates below the criteria" with the check named, not into the rules. Then run the
   budget gate, `python3 "<plugin root>/scripts/rule_lint.py" --ledger <ledger> --repo . --checks
   budget --changed <the admitted candidates' ids>`, where `<ledger>` is
   `.review/harvest/review-rules.md`, or for a standard elsewhere a copy of its ledger with the
   candidates added and `--profiles` naming its `profiles/`; `--changed` holds the run to the
   budget the candidates reach, so a standard already over it does not fail them all. When the
   run prints a `budget: <repository>: N lines over a budget of B` line, move the
   lowest-ranked admitted candidate under "Candidates below the criteria", the budget named as
   the criterion, and run it again with the ids left, until no such line is printed or no
   candidate is admitted. A budget line still printed then is the standard's own, reported as a
   finding beside the draft, not cleared here. A `budget: R-NNN: ... is not a list of names` line
   is the standard's too: it is reported as a finding and moves no candidate, since the budget
   is not counted. Exit 2 is a `CANNOT RUN`: its line is reported and the budget is not known, so
   no candidate is moved for it. Then report which candidates meet the
   admission criteria, which waited on the budget, and everything that could not be read.

## Bounds

25 candidate rules; terms and context entries within the caps `terminology.md` and
`context/README.md` state, one pass. Admission, establishment, expiry
and the line budget are the Dials in the shared `standards/dials.md`; a rule may implement a
decision when it says what a diff must show and names the decision on its evidence line. If the
admitted candidates exceed the budget, step 8's gate says so, and the ranking says which wait.
Each rule's wording follows the writing skill's "Rule wording".

## Never

Write to `standards/`, Confluence, Jira or GitHub. Copy a page. Write a rule from a one-off
design question, or from AI-drafted threads alone. Report a
sample as met when it is not. Publish an internal URL into a repository that is public.
