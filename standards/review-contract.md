# Review contract

How a reviewer behaves in every repository with a standard: the wave's implementation and focused
reviewers, and `github-pr-reviewer` under `pr-review`, also where a repository has no rules
file.

## What the reviewer loads

`.review/standard.md`: this contract, the ledger, the repository's and the shared decisions, and
the terminology; each rule's wording is its ledger entry's `> ` lines, or, for a ledger whose
entries link an instruction file, that file's Review Rules section. Load a shared
`context/` entry only when the ticket's Considerations line, or a file the diff touches, names it.
Read the ticket and the plan before the diff. A comment, docstring, changelog line or pull
request body sentence is a claim: read the code it describes before relying on it. A claim the
code contradicts is a finding, under the repository's rule for comments or docstrings where it has
one, `ticket/plan` where it departs from the approved plan, and otherwise with no key.

## Severity

| Tag | Handling |
| --- | --- |
| must-fix | Ranked. Quote the lines from the file, not only the diff; one not anchored to lines is downgraded |
| should-fix | Ranked |
| suggestion | At most the Suggestions per review Dial (`dials.md`), ranked; a Disagree needs no reason |
| question | At most the Questions per review Dial. When a decision in either `decisions.md` answers it, cite the decision instead |

A must-fix or should-fix with a Proposed line, and a key where Citation gives one, is always
posted. The summary line counts findings by severity. A `test/` finding takes the severity the
`test-suite-review` checklist's Keys table gives its key. Wherever a finding is marked blocking,
in a build's wave or by `test-suite-review`, `blocking` is must-fix or should-fix and
`non-blocking` is suggestion; `pre-existing` is outside this scale.

## Citation

A finding carries a key built from these parts: its citation (a rule ID; a shared decision
`D-nnn`, or the repository's own `D-nnn@<repository>`; `ticket/AC-n`, `ticket/scope` or
`ticket/plan`; `term/T-nnn`; a `test/` key from `test-suite-review`; or `helper/path::symbol`),
then `/`, the file path, `::` and the enclosing symbol, or in a non-code file the key or heading,
`-` when there is none. A finding keeps its key however it is phrased. A citation
holds no `/` of its own except the two-part `test/`, `ticket/` and `term/` ones; a
`helper/path::symbol` citation is already a full key. A finding none of these covers has no key.

## Ticket findings

- `ticket/AC-n` — an acceptance criterion, the numbered list under Driving Requirements, not met or met with no test
- `ticket/scope` — work a boundary in the ticket's Technical Requirements excludes, or a ticket under its Related Out of Scope Tickets owns (its Not this ticket list, on a ticket in the earlier format)
- `ticket/plan` — a departure from the approved plan that the PR body does not explain

A `ticket/` finding's Proposed line changes the code, or, where the work should keep its
departure from the ticket, records it: in the pull request body, and on the ticket with
`ticket-draft settle <key>`, given the thread id when there is one, which comments rather than
rewriting the description. It never proposes rewriting the ticket's requirements or criteria to
match the code; that is the person's call, when the ticket's intent was wrong. An item a
`Departed:` line already records is held to the departure, not the description (`using-jira`, "The description
format", Departures).

A design choice or open question the pull request body leaves out is a **must-fix**, ranked
above anything about the code.

## Terms

A new public name that disagrees with `terminology.md` is a should-fix keyed `term/T-nnn`; one in
neither the code nor `terminology.md` is a question.

## Test scrutiny

When the diff changes code or tests, apply the `test-suite-review` checklist your caller passes;
its keys are the `test/` citations above, and it owns the test checks. The lanes, their commands,
the coverage command and the mocking libraries come from the testing document the instruction
file names or, where there is none, from the test layout and the CI configuration. New shared
setup becomes a fixture where the repository keeps its fixtures.

## New surface

Keyed `helper/path::symbol`. Each function, method or class the diff adds that the plan's
`### Signatures` list did not name is reported with its call sites, its length, and whether
nearby code already does it. One caller and under about ten lines is a candidate to inline; a
duplicate of an existing function is a finding; a helper extracted from code with two or more
call sites is reported as the good case, not as new surface. Never raise `helper/...` on a symbol a decorator
registers with a framework: `@pytest.fixture`, `@field_validator`, `@model_validator`,
`@contextmanager` used as a fixture, `@functools.singledispatch` registrations, and framework
hooks generally.

## Comments

A comment tells a reader who never saw the change being made why the code is as it is, in a line
or two. Judge each comment the diff adds, starting from those `scripts/comment_scan.py` marks; a
mark is a candidate, and a comment it misses is judged the same way.

- A comment that narrates the change or the session, such as what was asked, what the code used
  to do, a step or a review round, is out of date once the change merges: a should-fix, proposed
  as the comment removed or rewritten to say why.
- Later work is one `TODO` line in the repository's form carrying a ticket key, `TODO[<key>]`
  where the repository has no form of its own, with the detail in the ticket. A TODO with no key,
  or a note about later work that is not a TODO, is a should-fix, proposed as that line and a
  ticket `ticket-draft` can draft; several lines of follow-up notes become one.
- A comment that restates the code it sits on, or runs past a few lines where its neighbors are
  short, is a suggestion. A comment that gives a unit, a frame, an epoch or why the code raises
  is not one.

Each is keyed under the repository's rule for comments where it has one, otherwise with no key.

## Fail loud

These repositories turn defined inputs into a defined product, or stop. Where the diff lets a
condition that invalidates the product pass, raise it: a broad `except` or a handler that logs
and continues, a silent coercion (`nan_to_num`, `errors="coerce"`, clipping, zero-filling a gap),
a default standing in for a required input, a `warnings.warn` where the output is unusable, a
retry or a fallback to a cached product or another calibration. It is a should-fix, or a must-fix
when the product would be wrong with no trace, citing the repository's rule when one covers it.
The Proposed line is the raise and the test that asserts it, never logging, a retry or graceful
degradation. Pre-existing code is in scope only where the diff makes it wrong.

## Do not flag

- Anything a configured lint, format, pre-commit or CI check enforces, tests aside.
- Style preferences with no rule, and nits.

## What the reviewer never does

Approve or request changes on its own, resolve a thread, apply a label, merge, or push. Post a
second full set of findings, a finding whose key already has a thread, or a reply the person did
not choose. Adjudicate a finding itself; reading what a person's reply means is not adjudicating,
deciding the finding is.
Edit anything under `standards/`.
