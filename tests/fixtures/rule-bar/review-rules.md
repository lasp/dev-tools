# Review rules

A hand-written ledger for tests/test_rule_lint.py: two reviewer rules and one graduated to a
check. `{sha}` stands for the commit the test builds.

### R-001 · Validate a path where it is constructed

tier: reviewer · status: established · since: 2026-09 · evidence: pr-0001, pr-0002 · implements `D-001`

Wording: [R-001 in the instruction file](../instructions.md#r-001--validate-a-path-where-it-is-constructed)

scope: pkg/*.py
example: fires on fix#1 PRRT_abc123; not on fix#2@{sha} pkg/loader.py::load "path: Path"

Do not flag: a path validated by its caller, when the docstring says so.

### R-002 · Narrow the annotation to what the body handles

tier: reviewer · status: provisional · since: 2026-10 · evidence: pr-0003 · **one pull request, needs a second**

Wording: [R-002 in the instruction file](../instructions.md#r-002--narrow-the-annotation-to-what-the-body-handles)

scope: pkg/*.py
example: fires on fix#3@{sha} pkg/loader.py::read "source: str | Path"; not on fix#2@{sha} pkg/loader.py::load "path: Path"

Do not flag: a union the body converts at its first line.

### R-003 · Deferred work carries a ticket tag

tier: check · status: graduated · since: 2026-08 · evidence: pre-commit
