Base: main
# Total an inventory CSV

Source: prompt: Report the total widget count in an inventory CSV.

## Brief

- **Goal**: `widgets.total.total_from_csv(path)` returns the total count in an inventory CSV.
- **Scope and non-goals**: no change to `widgets.loader`.
- **Constraints**: the standard library only.
- **Design choices**: none.
- **Acceptance criteria**:
  1. The sum of the count column is returned.
- **Assumptions**: none.

## Steps

- [x] 1. Add `total_from_csv` — `src/widgets/total.py` — unit test, new
- [x] 2. A test for the criterion — `tests/test_total.py`

### Signatures
- `widgets.total.total_from_csv(path: Path) -> int` · added · public

## Approach

Read the rows with `csv.DictReader` and sum the count column.

Approved by: not recorded
Depth: standard
