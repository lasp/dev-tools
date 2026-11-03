# Instructions

## Review Rules

### R-001 · Validate a path where it is constructed

A path is checked where it enters, so a bad value fails at the boundary that can name it
rather than deep in a caller that cannot.

### R-002 · Narrow the annotation to what the body handles

The annotation says what the body accepts; a type the body cannot use is narrowed out of the
signature rather than rejected inside it.

## Other
