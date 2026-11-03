# Review rules

The rules a reviewer checks every widgets diff against.

### R-001 · A loader validates a row's shape where it reads it

tier: reviewer · status: **established** · since: 2026-09 · evidence: pr-0003, pr-0007

> A loader checks each row's column count and types where it reads the row, and raises naming
> the row; it never pads, truncates or skips a short row.

scope: widgets/*.py · example: fires on example/widgets#7 widgets/loader.py::load "row"; not on example/widgets#3 widgets/report.py::write "row"

### R-002 · A count in a message names what it counts

tier: reviewer · status: provisional · since: 2026-10 · evidence: pr-0011 · **one pull request, needs a second**

> A message that reports a count says what was counted, parsed rows or file lines.

scope: widgets/*.py · example: fires on example/widgets#11 widgets/loader.py::load "rows"; not on example/widgets#3 widgets/report.py::write "rows"
