Base: main
# Fetch the inventory from the warehouse service

Source: prompt: Fetch an inventory CSV from the warehouse service, retrying the failures its API guide says to retry.

## Brief

- **Goal**: `widgets.fetch.fetch(url)` returns the body of an inventory CSV from the warehouse service.
- **Scope and non-goals**: parsing stays in `widgets.loader`; no caching, no authentication.
- **Constraints**: the standard library only.
- **Design choices**: the warehouse service drops connections and answers 502, 503 or 504 during its nightly restart, and its API guide asks every client to retry those with exponential backoff (the person, 2026-10-30).
- **Acceptance criteria**:
  1. A dropped connection or a 502, 503 or 504 is retried, three tries in all, waiting 0.5 s and then 1 s.
  2. When the last try fails, its error is raised.
  3. Any other HTTP error is raised at once, with no retry.
- **Assumptions**: none.

## Steps

- [x] 1. Add `fetch` with its retry — `src/widgets/fetch.py` — unit tests, new
- [x] 2. A test for each criterion — `tests/test_fetch.py`

### Signatures
- `widgets.fetch.fetch(url: str, *, attempts: int = 3, backoff_s: float = 0.5) -> bytes` · added · public
- `widgets.fetch._read(url: str) -> bytes` · added · private

## Approach

One function around `urllib.request.urlopen`, retrying the service's transient failures as its API guide asks and raising everything else.

Approved by: not recorded
Depth: standard
