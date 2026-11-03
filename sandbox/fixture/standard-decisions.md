# Decisions

### D-001 · CSV input is UTF-8 with a header row

_2026-09 · **established** · source: example/widgets#2_

The loader reads UTF-8 and takes the first row as the header; another encoding is converted before
it reaches the loader.
