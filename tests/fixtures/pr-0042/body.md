Driving requirement: report rows of the wrong width or length in `load_rows` without changing the rows returned.

## In context

Function: CSV loading, `load_rows`, which reads a file with `csv.reader`, rejects a duplicate `id` when `strict` is True, and returns the rows keyed by their `id` column.
Problem: a row can have fewer or more fields than the header, and a row is one parsed record, which spans several lines of the file when a quoted field holds a line break. Nothing looked at row width, so we could not tell whether or how often that happens; a `TODO` sat at the width check.
Options: report after parsing, rows untouched (chosen) · pad or trim rows to the header width (out of scope: the rows stay as read) · raise on a short row (deferred until we know how often it happens; see Questions)
Decision: one pass over the parsed rows. A row with fewer fields than the header is short, one with more fields or more than `ROW_LIMIT` characters is long, and anything else is normal.
Consequences: loads now say when a row is the wrong width, with enough detail to find it. The rows returned, their order and their values are unchanged. A row with a stray delimiter reads as one long row; a quoted line break never reads as a short row, since the parser has already joined it.

## Look at this

- **Should a short row raise rather than report (R-002)?** It reports for now, because the goal is to see whether and how often it happens. Reviewers: say if you think it should stop the load.
- **`ROW_LIMIT = 4096`, new here, is a first guess**, pending word from whoever owns the export on the longest row it writes. Nothing in the repository supports a particular value.
- **Per-row detail goes to `logger.warning`, not `warnings.warn`.** Nothing in `widgets` routes warnings into logging, so per-row `warnings.warn` would never reach the logs where a bad file would be diagnosed. The short-row summary is both a `UserWarning` and a `logger.warning`.
- **Long rows are logged as a count only, with no `UserWarning`.** The sample export has trailing delimiters on most rows; a warning there would fire on every load and fail the warnings-as-errors tests.
- **The version moves 2.4.0 -> 2.4.2.** Another pull request takes 2.4.1 and merges first.
- With `summary_only=False`, per-row detail has no limit. A badly broken file could log one line per row.

## How to verify

| #   | Criterion | Test | Status |
| --- | --------- | ---- | ------ |
| 1   | Short row reported with its index, width and the header width | `test_report_short_rows_classifies_rows[short]`, `test_report_short_rows_reports_detail` | pass |
| 2   | A file with no trailing newline and a quoted line break are not short rows | `test_report_short_rows_classifies_rows[no-trailing-newline]`, `[quoted-line-break]` | pass |
| 3   | Long row counted, not warned | `test_report_short_rows_classifies_rows[long]`, `[trailing-delimiter]`; `test_report_short_rows_logs_long_rows_without_warning` | pass |
| 4   | Clean input produces no warning and no log line | `test_report_short_rows_clean_input_is_silent` | pass |
| 5   | `summary_only=True` gives the summary only; `verbose=True` adds detail | `test_report_short_rows_summary_only_limits_detail` | pass |
| 6   | Returned rows identical to the current code's | `test_load_rows_short_rows_leave_rows_unchanged` | pass |
| 7   | `ROW_LIMIT` defined once, documented as a first guess | `ROW_LIMIT` in `widgets/loader.py` | review |
| 8   | TODO removed | `prevent-dangling-todos` hook | pass |
| 9   | PR asks the R-002 question and states the first-guess limit | "Look at this" above | done |
| 10  | Changelog records the report | `CHANGELOG.md` `## 2.4.2` | done |

Run: `pytest tests/test_loader.py`

## What changed

- `widgets/loader.py`: the new public constant `ROW_LIMIT`; private `_report_short_rows`, called after parsing; the TODO replaced by a comment; on `load_rows`, `summary_only`/`verbose` docstrings, a Notes paragraph, and a `Raises` section listing the `KeyError` for a header with no `id` column and the existing `ValueError` for a duplicate `id` when `strict` is True.
- `tests/test_loader.py`: classification, reporting and quieting tests for the helper; two `load_rows` tests, one checking that `summary_only` and `verbose` reach the report.
- `pyproject.toml`, `CHANGELOG.md`: 2.4.2 with a FEAT entry.
- `standards/log/pr-0042.yaml`: the standards review record for this PR.
- Public signatures: none

<details><summary>Already checked</summary>

Build: passed
Gates: lint 1 · types 0 · tests 6 · reviewer rounds 1 · wall clock 24 min
Tokens since the build started: 418902 in · 29114 out · 6120457 cached, main session plus 3 subagents
Plan: approved by alice
Rules checked: R-002, R-004, R-006, R-007, R-009, R-012, R-013
Declined: none
Suggestions: test/failure-path/widgets/loader.py::_report_short_rows — add a parametrize case for the documented KeyError when the header has no id column; other/widgets/loader.py::load_rows — the public Notes paragraph names the private helper _report_short_rows
Questions: should a short row raise rather than report (R-002)?
Escalated: none

</details>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
