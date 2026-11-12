# The review wave

How a change is verified: `implement-change` step 8 runs it for a build, `pr-fix` step 9 for a
round of review fixes, and `implement-change verify` for work written with no plan, its plan file
`none` and its brief the goal the person gave. The plan file, the brief and the report folder are
the caller's: `implement-change` writes the wave reports to `.review/build/`, a verify included,
`pr-fix` to `.review/fix/pr-<n>/`, so a round of fixes leaves the build's reports alone. The base
is a commit, never a branch name: `implement-change` passes `git merge-base <the plan's Base:
branch> HEAD`, a verify `git merge-base <the default branch> HEAD`, and `pr-fix` passes `HEAD`.
Every reviewer and `surface_diff.py` get that commit, so commits the base branch gains during the
build are not read, reversed, as part of the change. Each profile value on this page
is `python3 "<plugin root>/scripts/profile.py" <owner/repo> --field <key>`.

## Depth

The `Lint:` line is `<the profile's lint.command> <the changed files>` when that command is
recorded and not empty, otherwise the linters the instruction files name.

- **A light build** (`implement-change`): one pass of the implementation reviewer, told the round
  is light, with the `Lint:` line, so it runs the linters on the changed files and the tests that
  touch the change, beside one `focused-reviewer` per brief `depth_floor.py` printed, or, for a
  build the person lowered, the brief its `## Corrections` line names. No coverage run. It loops
  as "The loop" step 3 does and passes when the implementation reviewer returns `SATISFIED` and
  no focused reviewer has a blocking finding.
- **A light round** (`pr-fix`): the same pass of the implementation reviewer, alone. A blocking
  finding is fixed and the pass repeated, at most twice; one still standing goes to the person.
- **Standard** and **deep**: the wave below.

## Who runs

A wave is sized to what the diff changes. Read the changed files against the base first, `git
diff --stat <base>` and the untracked files the change owns. Code is the repository's source
outside its test directories; a test file is one under them, or a `conftest.py`; documentation is
a `.md` or `.rst` file, or anything under `doc/` or `docs/`.

| Member | Runs when the diff |
| --- | --- |
| `implementation-reviewer` | always |
| `focused-reviewer`, `simplicity.md` | adds or changes lines of code |
| `focused-reviewer`, `documentation.md` | changes code or documentation |
| `focused-reviewer`, `tests.md` | changes code or a test file |
| the coverage run | changes code |
| `downstream check` | removes or renames a public name, as `surface_diff.py` lists |

**One suite run per wave.** The coverage run is the implementation reviewer's suite run: it gets
`Coverage: <the profile's coverage.command>` in place of `Tests:`, runs it through one
`test-runner` in coverage mode, takes the pass or fail from it, and raises each changed line
the run did not execute as `test/uncovered`. With that command empty or not recorded, the
coverage command the instruction files name; with none there, it runs `Tests:` and the merge
says no coverage ran. An untested `raise` is the tests reviewer's `test/failure-path`; the
implementation reviewer raises it only in a wave with no tests reviewer, such as a light pass,
which its `Notes:` line tells it.

Every member that does not run is named, with its reason, on the first line of the merged list,
`Not run: documentation, only tests changed`, and in the message that
reports the wave. A member that does not run leaves its focus to the implementation reviewer's
own style check.

## The loop

1. **Launch the wave in one message.** The **implementation-reviewer**, with the plan file path,
   the brief, the base, and `Tests:` or `Coverage:` as above: it runs the suite and linters,
   judges the diff against the plan and scope, and returns `SATISFIED` or `NOT SATISFIED`. On the
   bug path, tell it the brief is a bug, so it checks the red-to-green evidence. Beside it, one
   **focused-reviewer** per member the table runs, each with its brief's path in this directory,
   the plan file path, the context page when there is one, `.review/standard.md` when it exists,
   and the base. Fresh agents every wave: a reviewer resumed from an earlier wave defends what it
   said there. The simplicity reviewer's `Notes:` line carries what `python3 "<plugin
   root>/scripts/comment_scan.py" <base>` prints, `comments: none` when it prints nothing.
   Before launching, run `python3 "<plugin root>/scripts/surface_diff.py"
   <base>`. When it lists a removal or a rename, launch one `general-purpose` agent in the same
   message, told to run `<plugin root>/skills/downstream/SKILL.md` "check" with the same
   base, given the expanded plugin root, since a SKILL.md read as a file keeps its plugin
   variables unexpanded (its skill directory is `<plugin root>/skills/downstream`), and return only its verdict lines and its `Ripple:` line, so the consumers' installs stay
   out of this session; read its verdict with the digests. When `surface_diff.py` exits 1 it has
   listed nothing it could vouch for: that is a stop, below, never an empty surface. A later wave
   whose `surface_diff.py` output matches `.review/downstream/surface.txt` reuses the last report.

   Each reviewer's prompt opens with these lines, filled in, `none` where one does not apply, and
   adds nothing the agent's own instructions already say:

   ```
   Wave <N> · <focus> · report: <folder>/wave-<N>-<focus>.md, written before you return the digest
   Brief: <the change's brief: goal, scope, acceptance criteria>
   Focus: <this directory's brief for the focus, or none for the implementation reviewer>
   Plan: <plan file> · Base: <base> · Context page: <path> · Standard: <.review/standard.md>
   Tests: <tests.command> · Coverage: <coverage command> · Lint: <the Lint: line>
   Not part of the change: <untracked paths in the tree the change does not own>
   Delta: <files changed since wave N-1> · Previous findings: <<folder>/wave-<N-1>-<focus>.md>
   Notes: <light round; a bug; the focuses other reviewers hold this wave>
   ```
2. **Collect every digest before touching anything.** Each reviewer writes its full report to
   `<folder>/wave-<N>-<focus>.md` (`conformance` for the implementation reviewer) and
   returns a digest: the counts, every finding keyed in one line with blocking marked, and the
   file's path. A reviewer that returns its report without writing the file: write what it
   returned to that path yourself, and say so in the merge. Write `<folder>/wave-<N>.md` as
   the `Not run:` line and the merged list. Merge findings that share a key, and those with none
   by file and enclosing symbol, keeping the more specific; a `test/uncovered` line inside a
   `raise` the tests reviewer raised as `test/failure-path` merges into that finding. Blocking is
   what `<plugin root>/standards/review-contract.md` "Severity" says it is. Open a
   reviewer's file only for a finding you are about to fix. When two reviewers pull against each
   other, the implementation reviewer's conformance wins, and whatever the simplicity reviewer
   had removed is checked by the implementation reviewer in the next wave. A finding that would
   change the agreed plan, or weaken an existing test, goes to the person now, as the stops below
   say, and so does a digest whose `Checks:` line names a gate as `not run`: no fix answers it.
3. **Fix every blocking finding, then launch the next wave, sized to what is left**: a fresh
   implementation reviewer, with the same `Tests:` or `Coverage:` line, the delta since the
   previous wave and its previous findings, and beside it a fresh focused reviewer only for each
   focus that had a blocking finding in the previous wave, given that focus's previous findings,
   so it can say what still stands. A focus with no blocking finding is not run again, and its
   non-blocking findings stand as written. The tests reviewer also runs again, with its previous
   findings, whenever the delta changes a test file, since the tests a fix adds are new to it. A
   member whose trigger the delta meets for the first time runs as in step 1.
4. **Converge** when the implementation reviewer returns `SATISFIED` and no focused reviewer has
   a blocking finding. Non-blocking findings are not looped on: they go to the person at the diff
   review (`implement-change` step 9), in the report (step 12) and, in a repository with a
   standard, onto `outcome.md`'s `Suggestions:` line. A standard or deep build whose diff
   adds or changes lines of code goes on to "Honing"; any other build, and a `pr-fix` round, end
   here.

## Honing

A converged build still carries what the waves left behind: a comment longer than its file's, a
helper a later fix made redundant. Fix waves answer blocking findings only, so the passing diff is
tightened in passes of its own, numbered on from the last wave, outside the five-wave cap.

1. **One fresh focused reviewer** with `simplicity.md` and the whole diff against the base. Its
   header names the focus `honing`, so its report is `<folder>/wave-<N>-honing.md`; `Tests:`,
   `Coverage:` and `Lint:` are `none`, `Not part of the change:` is the wave's, and `Notes:
   honing; raise only what keeps the behavior, the plan and every test, the change's own
   included, and leaves the code shorter or plainer`, followed by what `comment_scan.py <base>`
   prints now. On the first pass `Delta:` and `Previous findings:` are `none`; on the second they
   are the files the first pass changed and its report, so it raises only what is new.
2. **Save, then apply.** Copy every file the pass will edit to `<folder>/honing-<N>/`, then apply
   each finding that keeps the behavior, the plan and every existing test. One that would change
   any of them, or would remove validation where data enters, is applied by nobody and goes to
   the person at its severity: a blocking one is shown blocking at the diff gate and written to
   `Escalated:`, a non-blocking one to `Suggestions:`.
3. **When anything was applied**, a fresh implementation reviewer with `Tests:` or `Coverage:` as
   in the wave, the files the pass changed as `Delta:`, and `Notes: honing check; judge only the delta, against the behavior
   and the plan; the tests reviewer held this build's tests`. Its report is
   `<folder>/wave-<N>-conformance.md`. On anything but `SATISFIED`, copy the saved files back and end honing: the converged
   tree, which the waves verified, stands, the pass's findings go to the person as suggestions,
   and `outcome.md`'s `Build:` line reads the last wave's verdict, not this one. Remove
   `<folder>/honing-<N>/` when the pass ends.
4. **Stop** when a pass applies nothing, or after two passes. Every pass writes
   `<folder>/wave-<N>.md`, the merged list of its reports, whether or not it applied anything, and
   counts as a wave in `outcome.md`'s lines and in the build hook's reviewer rounds. A pass that
   applies nothing leaves `outcome.md`'s `Build:` line as the converged wave set it.

## Stops

Stop and bring the person the latest wave's reports on any of these, the one list of stops.
`implement-change` writes each stop's phrase to `outcome.md`; `pr-fix` writes none.

- A failure that predates the change keeps the change's own gates from running: a failing test
  or hook, a module that will not import, an absent system dependency. The reviewer shows the
  evidence (`blocked by a pre-existing failure: <what>`). One that does not block them is listed
  and the wave goes on.
- A gate does not run for a reason other than a failure: the suite, the coverage run or a linter
  is denied permission, or no project environment is found. The reviewer names the command and
  the reason on its `Checks:` line. Nothing stands in for the run, neither the caller running it
  nor a `SATISFIED` reached without it (`stopped for a person: not verified: <the command and
  why>`).
- A fix would weaken an existing test: a loosened tolerance or assertion, a removed
  `pytest.raises`, a new skip or xfail, a dropped parametrize case (`stopped for a person:
  weakens <test>`).
- A finding would change the agreed plan (`stopped for a person: changes the plan`), or, with no
  plan, the brief's goal or scope (`stopped for a person: changes the brief`).
- A finding would move code across a repository boundary (`stopped for a person: crosses a
  repository`).
- `downstream check` says a consumer breaks (`stopped for a person: breaks <consumer>`).
- `surface_diff.py` exits 1, so the removals are not known (`stopped for a person: surface not
  read: <its stderr>`).
- The same finding survives two fixes (`a finding kept returning`), or five waves pass (`review
  cap reached`).
