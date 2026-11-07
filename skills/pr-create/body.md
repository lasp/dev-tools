<!-- A ticket in several pull requests: the template's own Ticket: line, never a second one,
becomes `Ticket: <key> · part k of n · base: <branch>`, a GitHub issue's key written `#<n>`, or `<owner/repo>#<n>` for a tracker in another repository, and the line after it
`Claims: AC-1, AC-3`, the Acceptance Criteria this part claims. A ticket in one pull request
keeps the template's line as it is and has no Claims: line. -->

## Summary

<!-- Context to detail, in three short paragraphs a reviewer reads in a minute. A reader who
stops after the first knows what is affected, for whom, and why it changes. -->

<Context and problem: the function this change touches, in the repository's own words, when it
runs and what relies on it; then what it could not do or did wrong, with the failure, the number
and its unit, or the ticket's ask in this function's terms.>

<The change and why it is built this way, in the function's terms, not its mechanics; an
alternative a reviewer could have expected, and why it lost, only where there was one.>

<Consequences: what is true once this merges, what is now committed or harder, and any accepted
limitation, stated plainly.>

Used by: <who calls it, naming each consumer that does from this repository's list, which
`<plugin root>/skills/downstream/SKILL.md`'s `check` step 2 gives, or "nothing outside this repository">

## Key design choices and open questions

- <a Build: phrase other than passed, verbatim, first; each failure outcome.md lists as
  predating the change, with its evidence; on a bug fix, the root cause; every escalation, every design choice the plan left
  open with what was chosen and why, every question settled at the plan gate with its answer and who
  gave it, every provisional decision, marked `Provisional:`, with the answer it builds on, why it is
  not final, what it affects, what would make it final and where the diff applies it, every departure from the approved plan with its reason>

<!-- When there is nothing: "Nothing outside the plan." and nothing else. -->

## What was tested

<!-- One row per Acceptance Criterion on the ticket, # its number there (the n of ticket/AC-n);
without a ticket, the plan's goals. Status is pass only when the build's test gate ran the test
at this head, else not run or by review. -->

| #   | Criterion | Test | Status |
| --- | --------- | ---- | ------ |
| 1   | <a few words naming it; the ticket holds its text> | <the test that guards it, or none> | <pass, not run or by review> |

Run: `<the one command>`

## How to test

<!-- For the reviewer: the command to run here, and where a consumer is affected, the
downstream run that shows it, such as "run the consumer's processing step and check the new file is picked
up". -->

- Here: <what to do beyond the Run line above, or "the Run line above">
- Downstream: <the run in the consuming repository and what to look for, or "none: no consumer
  is affected">

## What changed

- <each behavior or public-surface change the Summary did not already state, one line each; never a file tour>
- Public signatures: <added, altered or behavior, or "none">

<details><summary>Already checked</summary>

Build: <the phrase from `.review/build/outcome.md`>
Depth: <light | standard | deep, from `.review/build/outcome.md`>
Gates: lint N · types N · tests N · reviewer rounds N · reviewers N · wall clock N min[ · patterns: <as the hook wrote it>]
Tokens since the build started: N in · N out · N cached, main session plus N subagents
Plan: <approved by login | none>
Rules checked: <key> fixed | <key> declined, ...
Declined: <key, bare, as standards/review-contract.md defines it> — <one-sentence reason, with no semicolon>; ...
Suggestions: <key, or file::symbol for an uncited finding> — <what was suggested, or why it was left>; ...
Escalated: <what, or "none">
Nominated: <a correction the person made at the plan or diff gate>; ...
Procedure: <a correction about how the skill or its agents worked>; ...
Reproduced: <test> failed before the fix, on a bug fix
Ripple: predicted <consumers or none> · verified <consumers or none> · breaks <consumers or none>, when `downstream check` ran
Reopened: <thread id, or session-<pr>-<n>> · <one clause>, when review reopened the design

</details>
