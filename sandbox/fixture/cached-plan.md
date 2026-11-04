Base: main
# Fetch the inventory from the warehouse service

Source: prompt: Fetch the day's inventory CSV from the warehouse service for the nightly count.

## Brief

- **Goal**: `widgets.fetch.fetch(url)` returns the body of the day's inventory CSV from the warehouse service.
- **Scope and non-goals**: parsing stays in `widgets.loader`.
- **Constraints**: the standard library only.
- **Design choices**: none.
- **Acceptance criteria**:
  1. The body of the response at the URL is returned.
- **Assumptions**: none.

## Steps

- [x] 1. Add `fetch` — `src/widgets/fetch.py` — unit test, new
- [x] 2. A test for the criterion — `tests/test_fetch.py`

### Signatures
- `widgets.fetch.fetch(url: str) -> bytes` · added · public

## Approach

One function around `urllib.request.urlopen`.

Approved by: not recorded
Depth: standard
