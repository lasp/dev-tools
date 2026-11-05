# Decisions

### D-001 · Fail loud: a defined product, or the run stops

_2026-11 · **established** · source: example/widgets#5_

This code turns defined inputs into a defined product, or stops. Where a diff lets a condition
that invalidates the product pass, it raises: a broad `except` or a handler that logs and
continues, a silent coercion (`nan_to_num`, `errors="coerce"`, clipping, zero-filling a gap), a
default standing in for a required input, a `warnings.warn` where the output is unusable, a retry
that masks a systematic failure, or a fallback to a cached product or another calibration. A
review raises it as a should-fix, or a must-fix when the product would be wrong with no trace. The
Proposed line is the raise and the test that asserts it, never logging, a retry or graceful
degradation. Pre-existing code is in scope only where the diff makes it wrong.
