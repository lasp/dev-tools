# Simplicity

The focus: code that is larger, more defensive or more roundabout than the change needs.

## Raise

- A helper with one call site that the plan's `### Signatures` list did not name.
- Logic duplicated where the repository already has it.
- A name that does not match its neighbors, and a new public name that disagrees with
  `terminology.md`, keyed as the review contract's "Terms" section says.
- A comment the review contract's "Comments" section raises, starting from the `comment_scan.py`
  marks the caller's `Notes:` line carries.
- Dead code.
- A defensive check nobody asked for, and an over-broad `except`. Validation where data enters,
  which the review contract's "Fail loud" section asks for, is not one.

## Leave to others

Docstrings and documentation (the documentation reviewer); tests (the tests reviewer); plan
deviations and scope (the implementation reviewer).

## Read first

1. The plan, then the diff.
2. In `.review/standard.md`: the rules on comments, dead code and parsing an input once. Find
   them by title in the rule ledger and cite them by the IDs it gives. Then the review
   contract's "Comments" and "New surface" sections, which already says how to report a helper with its call
   sites, and the terminology.
3. Without a standard file, the repository's instruction file.
