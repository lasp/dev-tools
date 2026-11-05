Base: main
# Rename get_inventory to fetch

Source: prompt: Rename widgets.fetch.get_inventory to fetch, to match the other modules' verbs.

## Brief

- **Goal**: `widgets.fetch.fetch(url)` is the name of the function that returns the inventory CSV's body.
- **Scope and non-goals**: the function's behavior is unchanged.
- **Constraints**: the standard library only.
- **Design choices**: none.
- **Acceptance criteria**:
  1. `widgets.fetch.fetch(url)` returns the body of the response at the URL.
- **Assumptions**: none.

## Steps

- [x] 1. Rename `get_inventory` to `fetch` — `src/widgets/fetch.py` — unit test, changed
- [x] 2. A test for the criterion — `tests/test_fetch.py`

### Signatures
- `widgets.fetch.fetch(url: str) -> bytes` · renamed from `get_inventory` · public

## Approach

A rename of the public function.

Approved by: not recorded
Depth: standard
