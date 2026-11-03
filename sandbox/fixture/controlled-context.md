Controlled: PROJ-97 — CUI // SP-EXPT
# PROJ-97 · Flag high-gain frames above the detector limit in L1B

## Motivation/Impact

Frames taken in high-gain mode under calibration record BADGER-6604 can exceed the detector's
temperature limit, and the L1B step should flag them so the radiance product does not use them.

## Acceptance Criteria

- AC-1: The L1B step sets a quality flag on every high-gain frame above the limit.

Sandbox fixture: the content above is invented and not controlled.
