# Tests

The focus: the tests the change adds, changes or deletes, and the tests its changed code lacks.

## Raise

Exactly what `../../test-suite-review/checklist.md`, relative to this brief, raises, keyed as it
keys them, at the severity its Keys table gives. It is the checklist; this brief does not repeat
it. In a wave, `test/uncovered` is the implementation reviewer's, from its coverage run; raise it
only from an `Uncovered:` list the caller passes.

## Leave to others

Everything that is not a test: code structure, names and docstrings belong to the simplicity
and documentation reviewers, and scope to the implementation reviewer.

## Read first

1. `../../test-suite-review/checklist.md` (relative to this brief).
2. The whole of each test module the diff touches, and its `conftest.py`: `test/rework` and
   `test/duplicate` cannot be judged from hunks.
3. In `.review/standard.md`, when it exists, the review contract's "Test scrutiny" section.
