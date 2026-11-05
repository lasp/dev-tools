# Review rules

## R-001 · Validate inputs at the boundary

> Check shape, dtype, units and time range where data enters the library (a reader opening a file) and raise there; downstream code does not repeat the check.

## R-002 · No silent fallbacks

> Do not catch broad exceptions, substitute defaults or coerce bad values to keep going; when an input cannot be used, raise.
