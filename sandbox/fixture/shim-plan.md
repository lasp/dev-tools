Base: main
# Rename get_inventory to fetch

Source: prompt: Rename widgets.fetch.get_inventory to fetch, to match the other modules' verbs.

## Brief

- **Goal**: `widgets.fetch.fetch(url)` is the name of the function that returns the inventory CSV's body.
- **Scope and non-goals**: the function's behavior is unchanged.
- **Constraints**: the standard library only.
- **Design choices**: keep `get_inventory` as a deprecated alias of `fetch` that warns, so a caller of the old name keeps working.
- **Acceptance criteria**:
  1. `widgets.fetch.fetch(url)` returns the body of the response at the URL.
  2. `widgets.fetch.get_inventory(url)` returns the same and warns `DeprecationWarning`.
- **Assumptions**: none.

## Steps

- [x] 1. Rename `get_inventory` to `fetch` — `src/widgets/fetch.py` — unit test, changed
- [x] 2. Tests for the criteria — `tests/test_fetch.py`

### Signatures
- `widgets.fetch.fetch(url: str) -> bytes` · renamed from `get_inventory` · public
- `widgets.fetch.get_inventory(url: str) -> bytes` · deprecated alias · public

## Approach

A rename of the public function, the old name kept as a warning alias.

Approved by: not recorded
Depth: standard
