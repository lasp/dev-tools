# The report's outline

The shape of `ratchet-YYYY-MM.md`. The meeting gives it a thirty-minute slot: the driver reads
the head, then the overview, then each proposal aloud in the overview's order, and the group
marks it. Everything under "Reference" is
read before the meeting, or when a proposal points to it, never aloud. A section with nothing in
it reads "none". The step that fills each section is `prepare.md`'s.

```
window: <from YYYY-MM-DD>..<to YYYY-MM-DD>
<only when they apply, one line each: rests on <n> records, below the Revision floor Dial ·
 tickets came from pasted files · <n> records predate merged:>

# Standards revision · <repo> · YYYY-MM

## Head                                     steps 1, 2
standard: <where it is stored>
scope, one line per repository covered: <repo> · <the rules that reach it> · <threads read and diffs swept | archived and counted, threads not read | archived only, no rule reaches it>
records: <n> harvested · <n> missing (<the Missing-record alarm Dial, when it fires>) · <n> baseline
cost: open-to-merge median <d>, longest <d> · <n> merged without a build · corrections: <n>, on <ids>
agree rate by severity · share unanswered · share of agreed findings changed as asked
counted: <verdicts, firings, contested, missing, from record.py and ratchet_counts.py>; read by the analyst: <categories, outcomes, procedure ids>

## Overview                                 step 10: every proposal below, the held ones included, one line each
| Priority | Proposal | Applies to | Impact | Rests on | Apply changes |
| high | ticket/<slug> | <project-wide | <repo>, …> | <n> pull requests, <n> files | <people's asks, a break on main, findings' agree rates> | <the standard's repository | this repository's diff | Jira, through ticket-draft> |

## Proposals                                steps 3 to 8, in the overview's order
- [ ] R-0NN · <proposal> · <Dial> · <evidence pointers>
  Recommended: <accept | accept, override: <reason> | decline: <reason> | escalate: <reason>> — <the evidence that decides it>
  scope: … / example: … / bar: ok | <lint lines> / probe: … fires|silent|cannot read; … fires|silent|cannot read
  Mark:
- [ ] context/<name> · refresh · <source> · <old date> → <new date>
  Recommended: …
  Mark:
- [ ] ticket/<slug> · <the break or the unanswered ask, in a line> · <pull request, path:line or thread id>
  Recommended: …
  Mark:
- [ ] doc/<path> · <claim C-n> · drift · <the pull requests that break it>
  Recommended: …
  Mark:

### Held by the bar                         step 7; marked like any proposal
- [ ] R-0NN · … · <the check that failed>
  Recommended: …
  Mark:

## Dials at the margin                      step 4
<Dial>: at <value>, <proposals gained or lost>; at <value>, <…>
Other Dials: no change one step either way.

## Reference

### Rules                                   steps 1, 3
the window's and all records' count tables and the expiry table, every row the script prints, each ledger rule included at 0 when it has no firing; contested rules and what the
disagreements shared; rules held provisional for breadth and what would release them

### Held candidates                         step 6
### What review asked for                   step 2
### Practice                                step 2's sweep, report only: per claim, judged on, follows, breaks, untouched; drift; missed by review; rules not swept
### About the procedure                     step 2: each skill-feedback draft's path and ask; each settled finding and what settled it
### Graduation checks                       step 9
### Context                                 step 8: unreachable, unrefreshable, new pages
### Measures                                measures.md, only when it ran
### Not read                                step 2: unanalysed pull requests, Not read: ids
```

A held proposal is never recommended a plain `accept`. The meeting takes the proposals in the
overview's order and stops when its time is up; a proposal it leaves blank is deferred, and
`apply` returns a blank admission to the held candidates with its evidence.
