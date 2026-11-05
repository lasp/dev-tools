# Test checklist

What a reviewer raises on the tests a change adds, changes or deletes, and the key each finding
carries. `test-suite-review` applies it for a person; the tests member of a build's wave applies
it there; `pr-review`'s reviewer applies it to a pull request.

## Keys

| Key | Raised for | Severity |
| --- | --- | --- |
| `test/loosened` | an existing test that no longer catches what it caught, with no reason in the code | must-fix |
| `test/failure-path` | a `raise` the diff adds that no test asserts | must-fix |
| `test/uncovered` | a changed line no test runs, from a `test-runner` list | should-fix |
| `test/mock` | a test whose mocks replace the code the diff changed | should-fix |
| `test/assert` | a smoke-only assertion, or a downstream aggregate asserted in place of the step | should-fix |
| `test/lane` | a test in a lane its dependencies do not belong to | should-fix |
| `test/rework` | a new test whose subject an existing test already covers | should-fix |
| `test/mock-library` | a second way to mock what the suite already mocks one way | should-fix |
| `test/placement` | a test outside the module that tests its subject | suggestion; must-fix for a new module whose subject already has one |
| `test/duplicate` | the same subject, input and assertion in two places | suggestion |
| `test/name` | a test whose name or docstring does not say what it pins down | suggestion |

The severity is the key's unless the text below names another for a case. Which severities block a
build is the review contract's "Severity" section.

## Loosening

The finding that matters most, because a green CI run hides it. For every modified test, ask
what it used to catch that it no longer catches. Keyed `test/loosened`, and a must-fix when no
reason points at the code.

| Change | Legitimate when | Suspect when |
| --- | --- | --- |
| Tolerance widened | The algorithm's precision genuinely changed, and the new bound is derived | The bound was raised until the test passed |
| Expected value changed | The code intentionally changed that number, and the new one is derivable | The new value was copied out of the failure output |
| `pytest.raises` removed or broadened | The contract deliberately stopped raising | The code started raising something else and the test was widened to absorb it |
| Parametrize case dropped | That input is no longer meaningful | That case was the one failing |
| `skip` or `xfail` added | An environment fact, with the reason recorded | A green suite bought by hiding a real failure |
| Assertion weakened to a smoke check | Never, in a unit test | The specific assertion became inconvenient |
| Test moved to another lane or file | The dependency changed, as the lanes define it | It escaped a guard, such as a network block, rather than mocking |

The test to apply: is the new expected value derivable from the code change, or was it read
off the output? Every change to an existing test needs a reason that points at the code. "We
changed the frame transform, so the expected ECEF vector moved" is a reason; "updated test" is
not. A golden value changed without the plan, or at review the pull request body, saying so is
a science claim made silently, and a must-fix.

## New tests

- **Behavior and failure path.** New behavior needs a test that names it. Every `raise` the
  diff adds needs a test asserting it, a must-fix keyed `test/failure-path`: an untested raise
  is an unenforced contract.
- **Changed lines no test runs**, keyed `test/uncovered`, listed as `file:line`. They come from
  `test-runner` in its coverage mode, given the repository's coverage command and the
  base ref; the reviewer never runs it. Never a percentage: a percentage produces tests written
  to the metric.
- **Assert the value**, keyed `test/assert`. A test that only checks nothing raised passes when
  the function returns garbage.
- **Mocking away the change.** A test whose mocks replace the code the diff changed exercises
  nothing new, however green. Keyed `test/mock`.
- **Names**, keyed `test/name`. Each test says what it pins down, in its name or a one-line
  docstring. `test_read_granule_raises_on_frame_mismatch` needs nothing more; `test_edge_cases`
  needs a rewrite.
- **Coverage is not the target.** A test written to color a line, asserting nothing anyone
  relies on, is a maintenance cost with no return, keyed `test/assert`.
- Fixtures and reference files a test references must be committed. A missing local data file
  that is deliberately not in the repository is an environment fact, not a defect.

## Factoring

How an agent asked to make a suite green usually differs from a person who knows the suite:
it adds where the person would edit.

- **Extend before adding**, keyed `test/rework`. A new test whose subject an existing test
  already covers belongs in that test, as an added assertion or a `parametrize` case. Count
  test functions added, modified (the same name on both sides of the diff) and deleted, and
  compare added against modified plus deleted: a rewrite that drops fifteen and adds nine is a
  consolidation. When added is the larger, the change grew the suite, and a new test module
  for a subject that already has one is a must-fix `test/placement`; a new module for a new
  source module is where it belongs.
- **Parametrize** many small tests that differ only in their inputs. One test, one behavior
  still holds: a parametrized test is one behavior over many inputs. A parametrize axis whose
  values reach the code identically is `test/duplicate`.
- **Duplicate coverage**, keyed `test/duplicate`: the same subject fed the same input for the
  same assertion in two places. Judge on the subject, not the assertion.
- **Existing fixtures first.** Setup the repository already has as a fixture is requested by
  name, not rebuilt inline; new shared setup becomes a fixture where the repository keeps them,
  not a helper module.
- **The repository's mocking library**, keyed `test/mock-library`. A test that brings in a
  second way to mock what the suite already mocks one way, such as `unittest.mock.patch` of a
  `boto3` client where the suite uses `moto`, is a finding.
- **Placement within the suite**, keyed `test/placement`. A test goes in the module that tests
  its subject, beside the tests of the same code, not in a new module and not appended to the end
  of the nearest file. It should be easy to find the tests for any part of the code.

A framework-invoked symbol is not a helper: a `@pytest.fixture`, a pydantic validator, a
registered hook is called by the framework, so "one caller" is its normal case and never a
finding.

## Lanes

Where the repository's testing docs set a convention, it overrides this file. Read the lanes
from the repository; never ask for a lane it does not have. "There is no e2e directory"
describes the repository; it is not a finding.

- **A test's lane is decided by what it depends on**, not by how many modules it runs through:
  files outside the checked-in test data, a real subprocess, the network, a live service, and
  runtime. A fast unit test may call a few levels down the stack instead of mocking them, and
  mocking only to keep a test "unit" usually multiplies tests without adding coverage. Keyed
  `test/lane`.
- **Unit tests are fast**: fake or checked-in data, no external dependencies. A unit test that
  reads a large file or sleeps is a finding; name its runtime when the caller supplies one.
- **Assert at the step under test**, to the precision that step delivers; a downstream
  aggregate asserted in place of the step is a finding, keyed `test/assert`.

## Applied by a reviewer

Raise `test/uncovered` only from a `test-runner` list the caller passes; with none, raise none
and do not estimate. The caller's format and caps replace the skill's Output and Bounds.
