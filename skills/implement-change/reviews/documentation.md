# Documentation

The focus: whether what the change says about itself is true and complete.

## Raise

- A public symbol whose docstring does not say what it does and what it raises.
- A quantity with no unit, or a time with no epoch, where the repository's standard asks for
  one.
- Implementation history or process narration in a docstring or a page; a comment is the
  simplicity reviewer's.
- A README or doc page the change made wrong.

## Leave to others

Code structure and names (the simplicity reviewer); tests (the tests reviewer); scope (the
implementation reviewer).

## Read first

1. In `.review/standard.md`: the rules on docstrings and on units, found by title in the rule
   ledger and cited by the IDs it gives.
2. For a doc page or README the change touches, `../../writing/SKILL.md`, relative to this
   brief. It owns prose and leaves docstrings and code comments out, so a docstring is judged
   here against the standard and a page against that skill.
3. Without a standard file, the repository's instruction file.
