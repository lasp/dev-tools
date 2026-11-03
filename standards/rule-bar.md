# The rule bar

What a rule passes before the group marks it. Read by `onboard`'s first rules, `revise`
(its `correct` mode included) and the `rule_lint.py` script under `scripts/`; not loaded into reviewers.

## What it is for

Every reviewer run loads every rule, and every finding costs a person a reply. A rule written from
a thread's words rather than from the code that merged flags the fix the team accepted. The bar is
what a new, reworded, promoted or broadened rule passes before the group marks it; a rule already
in the ledger is measured against it at each revision and brought up to it when it is next
touched.

## The gates

| Criterion | Checked by | What passes |
| --- | --- | --- |
| sync (13) | `rule_lint.py` | Every reviewer-tier entry, provisional or established, has its wording, the entry's `> ` lines, and a retired rule none; a graduated or check-tier rule may keep it as guidance for authors, which the wording gate does not measure. A ledger whose wording is still in an instruction file has one heading there per rule, with the entry's title, that the entry's `Wording:` link anchors, and never wording in both places |
| wording (9) | `rule_lint.py` | A reviewer-tier rule's wording, provisional or established, is two to four lines, with no pull request number, thread id or `pr-NNNN` in them, as the Rule wording paragraph of `skills/writing/SKILL.md` says |
| status (12) | `rule_lint.py` | A rule's tier is reviewer, check or `—`, and its status provisional, established, retired or graduated; a rule that implements a decision has that decision's status, and names a decision on its evidence line only as `implements <id>`; a "needs a second" marker appears only on a provisional rule |
| scope (7) | `rule_lint.py` | Each of the entry's `scope:` globs matches a tracked file, and none is empty or matches every file |
| anchors (10) | `rule_lint.py` | The entry's `example:` line names a fires-on anchor and a not-on anchor at different places; each `@sha` anchor resolves, the symbol defined there and the quoted shape inside it; the not-on anchor's sha is on the default branch and is the merge of the pull request it names |
| fields (7, 10) | `rule_lint.py` | A new, reworded, promoted or broadened entry carries `scope:` and `example:` lines; a `repos:` line, in a standard covering several repositories, names only repositories it has a `profiles/` file for |
| budget | `rule_lint.py` | For each repository the standard covers, the ledger as the build and review agents load it there (`standard_file.sh`'s assembly; a session loads only live rules' wording), check-tier entries and held candidates left out, fits the budget the ledger's header states, or the Rule budget Dial (`dials.md`) when it states none |

`rule_lint.py` checks all seven and prints every failure; it fails the run for a rule it is
told changed, and for every rule when it is told nothing. A budget failure names a repository, not
a rule, and fails the run when a rule it is told changed counts toward that repository. `revise`'s `correct` mode runs only the gates
of the lines a correction changes, unless it rewords the rule.

## The report

The paired probe (criterion 1). `rule-probe` reads one rule and one anchor and says whether the
rule fires there. It is run on both anchors of a proposal's `example:` line, and its answer is
printed beside the proposal. It does not hold a proposal: the first revisions tune it, and the
roadmap says when it becomes a gate.

## The two ledger lines

`scope: <glob>[, <glob>]`, paths relative to the repository, each matched against `git ls-files`
with Python's `fnmatch`, where `*` matches `/` too, so `pkg/*.py` also matches `pkg/sub/x.py`,
while `pkg/**/*.py` needs two slashes and misses `pkg/x.py`. A bare `*` or `**` names no scope
and fails. `scripts/window_merges.py` matches a merged pull request's files the same way, for the
revision's sweep:

```
scope: src/widgets/*.py
```

`example: fires on <anchor or thread>; not on <anchor>`, one line however long, never wrapped. An
anchor is `<repo>#<PR>@<sha> <path>::<symbol> "<shape>"`, a place in code where `git show
<sha>:<path>` defines the symbol, a function, a class or `Class.method`, by `def` or `class`, and
the quoted shape appears inside that definition. The fires-on half is an anchor or `<repo>#<PR>
<thread id>`; the not-on half is always an anchor at the merge commit of the fix the evidence
pull request merged, on the default branch with `(#<PR>)` in its subject, because the merged diff
is what the team accepted:

```
example: fires on r#1 PRRT_synthetic001; not on r#2@abc1234 pkg/loader.py::load "path: Path"
```

A `scope:` line and an `example:` line are two lines of the entry's budget. The status line, which
carries `implements <id>`, is never wrapped either.

## Overrides

The group may accept a proposal a gate fails only by marking it `accept, override: <reason>` in
the report; a plain `accept` on it does not accept it. `apply` carries the reason onto the entry's
evidence line as `override <YYYY-MM-DD>: <reason>`, and the next revision's report lists every
override. A held admission the group does not accept this way goes into the ledger's
`## Candidates below the criteria` with the check it failed; a held rewording, promotion or
broadening leaves its rule as it stands.

## Deferred

Criteria 2 to 6, 8, 11, 14 and 15 are not gates yet. `ROADMAP.md`'s window backtest row brings
back criteria 3 and 14, the cost in findings per pull request; its `rule-critic` row brings back
the rest and the per-rule dossier.
