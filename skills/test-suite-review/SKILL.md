---
name: test-suite-review
description: >
  Judges a branch's or a diff's tests, read-only: whether they cover the change and its failure
  path, whether existing tests were loosened, and their factoring. Use when asked "are these tests
  any good", "is this well tested", "did this weaken the tests" or "review the test changes". Not
  for running the tests.
argument-hint: "[diff | branch | suite]"
metadata:
  author: lasp-dev
  version: 1.1.7
---

## When to run

On any diff that adds, changes or deletes tests, or changes code its tests should cover: by a
person, by the tests member of a build's wave, and by `pr-review`'s reviewer. It judges the
tests, never whether they pass. The checks, their keys and each key's severity are
`${CLAUDE_SKILL_DIR}/checklist.md`.

## Run by a person

Launch, in one message, one `focused-reviewer` with
`${CLAUDE_SKILL_DIR}/../implement-change/reviews/tests.md` and no wave number, and, when the diff
changes code as `${CLAUDE_SKILL_DIR}/../implement-change/reviews/wave.md` "Who runs" defines it
(a diff of test files or `conftest.py` alone gets no coverage run), one `test-runner` in
coverage mode with the coverage command and the base. In place of a plan file the reviewer's
prompt names what to judge, the base, the lanes and their markers and the mocking libraries, and
"every blocking finding; non-blocking ones up to the Suggestions per review Dial". The base is a
commit, as the wave's is: for a branch,
`git merge-base <branch> HEAD`, so commits that branch gained since the change began are not read,
reversed, as part of it. Turn the runner's uncovered lines into `test/uncovered` findings; a
runner that did not run, denied or with no environment, is said first, with its reason, and no
uncovered line is read as covered. Relay the result in the Output shape below. A whole suite has no diff, so Loosening and
`test/uncovered` do not apply and no runner is spawned.

## Reads (whoever applies this skill)

The diff against its base, and the whole of every test module it touches, whatever its length.
The lanes, the coverage command and the mocking libraries come from where the review contract's
"Test scrutiny" section says, never assumed, such as a testing document under `doc/` or
`docs/`. With no lane command found, no runner is spawned. A fact
not found is said once, with where you looked.

## Output

Findings only, grouped by the checklist's sections, Loosening, New tests, Factoring and Lanes,
strongest evidence first, each with `file:line`, its key, one line on what is wrong, and
`Proposed: <size>, <the change>`; for `test/loosened`, the assertion as it should read:

```
LOOSENING (n)
tests/unit/test_geolocation.py:88   test/loosened  tolerance 1e-9 -> 1e-6, no code change explains it
                                    Proposed: one line, assert_allclose(..., rtol=1e-9)
```

Each finding is marked blocking or non-blocking as the review contract's "Severity" section maps
the checklist's severities. A clean test diff gets `no findings` and one sentence on what it
covers well. End on the counts of blocking and non-blocking findings.

## Bounds

Every blocking finding is shown; non-blocking ones up to the Suggestions per review Dial
(`standards/dials.md`), the rest a count per key.

## Never

Edit, move, delete or add a test. Run the suite or the coverage command itself. Ask for a lane,
fixture location or library the repository does not have. Call a test loosened without saying
what it used to catch.
