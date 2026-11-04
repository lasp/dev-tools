---
name: implement-change
description: >
  Takes one change request (a file, a Jira ticket, a GitHub issue or the prompt) to an agreed
  plan, verified code and an offered pull request. Use when asked to "implement this", "build
  this feature" or "plan and implement". Not for routing a ticket to its next phase, which is
  work.
argument-hint: "[file | ticket key | issue | description]"
metadata:
  author: llm-tooling
  version: 1.16.0
---

# Implement Change

Turn a change request into implemented, verified code. The **implementation-planner** agent drafts
the approach, the **person** decides what gets built, you build it. Every question, and every file
it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is
`${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## Options

| Option | Default |
|---|---|
| Source | A markdown or text file, a Jira ticket, a GitHub issue or discussion, or the change described in the prompt; asked for when none is given |

## How Each Turn Reads

The person comes back to each turn without the last in their head, so every message can be acted
on without scrolling up.

- **Open with where things stand**: the step, what just finished, what it produced. "Step 5 of 12:
  plan agreed, written to `implementation-plan-retry.md`." The plan file's checkboxes carry
  progress; do not retell the plan.
- **Close on the one thing you need.** When a turn waits on the person, its last line is that ask.
- **Show what now works**, concretely: the test that passes, the command that runs.
- **State an error as cause and fix**: "`test_retry.py:42` expected 3 attempts, got 1: the policy
  never reaches `Client.__init__`."
- **Hold tangents.** A second problem found mid-step comes up once, as its own question, when the
  step is done.
- **Show at most five items per list**, grouped and ranked. The plan table, open questions and
  review findings are shown whole.
- **Name the specific thing**, and size work in real units: "about 40 lines across 3 files". Say
  what you verified and what you inferred.
- **Size every offered change first.** When you ask whether to make a change, or answer by
  proposing one, the first words name its size: `one line`, `a few lines`, `an hour` or `changes
  the plan`. A widget option that offers a change opens its description with the same word.
- **No preamble, recap, or sign-off**, and no word
  `${CLAUDE_SKILL_DIR}/../writing/references/prose-standards.md` flags unless it passes the truth
  test there.

A request to explain something gets the full explanation, under headers; it still opens with the
answer.

## Where the Files Live

The plan and the build's outcome live under `.review/`, which is never committed; the hook keeps it
ignored.

**The plan** is `.review/implementation-plan-<name>.md`: `<name>` is the ticket key, lowercased
(`implementation-plan-proj-42.md`), or with no ticket the branch step 6 will create, `/` as
`-`, which step 2 names. `bash "${CLAUDE_PLUGIN_ROOT}/hooks/where.sh" --fields` prints it as `plan=`
for the ticket or, once branched, for the branch; `work`, `pr-create` and the session-start line
look for exactly that file. A new change on a branch that already has a plan uses its own name,
never the current branch's `plan=`.

**A provisional decision** is an answer the build rests on for now: the answer, `Revisit because:`
(why it is not final), `Affects:` and `Final when:` (the evidence, measurement or named person's
call that would make it final). The plan keeps each under `## Provisional decisions` with the
steps that build on it. One with no reason it is not final is a final decision.

**Read on these paths only:**

- **A plan for this work may exist.** Before step 1, run `where.sh --fields`, with `--ticket <key>`
  when the invocation names a ticket. When its `plan=` file exists, or with no ticket a draft
  `.review/implementation-plan-*.md`, one with no `Approved by:` line, not yet branched for,
  whose `Source:` line is this invocation's source (any such draft when it gives none), read
  `${CLAUDE_SKILL_DIR}/resume.md` and go on where it says.
- **The repository has `standards/review-rules.md`, `standards/decisions.md` or
  a `standard:` pointer in `standards/profile.yaml`.** Read `${CLAUDE_SKILL_DIR}/standard-repo.md`
  before the first step this run takes, step 1 or the one `resume.md` names; it changes steps 1,
  3, 4, 6 and 8.
- **The ticket has an Open Questions section.** Read `${CLAUDE_SKILL_DIR}/ticket-questions.md` at
  step 1.

## The Build Record

The build hook records the lock, the measurements and the outcome under `.review/build/`. To go
back into a build whose `outcome.md` exists, remove `outcome.md` and run `printf
'{"session_id":"%s"}' "${CLAUDE_SESSION_ID}" | bash "${CLAUDE_PLUGIN_ROOT}/hooks/build-record.sh"
start`. Run the same command once step 6 has created a branch for a later part: it starts that
branch's own record and moves the previous branch's finished build aside. For a new change, run it
with `start fresh` once step 6 has branched: an open build this session carried onto the new
branch is dropped, a finished one is moved aside, and the new branch's record starts empty.

## 1. The Source

Before reading the source, say in a line when the person is needed (the brief, the plan, the diff,
the pull request) and that the branch, build and review loop run without them unless a stop needs
them.

**Run from the repository being changed.** When the change is to another repository, say so: the
hooks record under this session's `.review/`, so the Already checked block would read zeros and the
other repository would show a lock it does not hold. Ask: **Stop**, to start a session in that
repository (recommended); **Go on unrecorded**, where `pr-create` writes the block's measured lines
as `not recorded`; or **Let's discuss**.

The request comes from one of these. Find a remote source's tools with a `ToolSearch` keyword
search for what the tool does, never a server prefix.

- **The prompt itself**: the person describes the change inline.
- **A file**: a path to a markdown or text spec in the repo or on disk.
- **A Jira ticket**: an issue key or URL, read by one `source-reader` running the task `ticket
  <key>`. Its block carries the description, with the Acceptance Criteria under Driving
  Requirements, the comments, the linked issues, and whether there is an Open Questions section.
  A ticket the block lists as `Withheld:` warns it is controlled: relay its question as `${CLAUDE_PLUGIN_ROOT}/skills/writing/references/short.md`, "Controlled content"
  says, naming only the ticket, where it sits and the warning, quoted, and describing nothing of it, not
  even where it stopped, never asking for its text; on the person's yes run the task again with a
  `Cleared: <key>` line.
- **A GitHub issue or discussion**: search `github issue read`.
- Anything else the person points at: a URL, a pasted transcript, a design doc.

Follow a link one level deep when the source leans on it. Say what you read. Any source here,
the ticket included, a file, an issue, a link or what the person points at, is read first line
first, and one that warns it is controlled is held as `${CLAUDE_PLUGIN_ROOT}/skills/writing/references/short.md`, "Controlled content" says: stop at the warning, name only
it, where it sits and the warning, quoted, describe nothing of it, not even where you stopped, ask whether
to read it, skip it or stop, and pass nothing of it to the planner until the person clears it.

A server that cannot be reached stops this step, said as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the issue's or the ticket's text being
what is lost. Offer the alternative: for GitHub the `gh` CLI, as `using-github` "When the server
cannot be reached" says; for either, text the person pastes, saved under
`.review/context/<key>.pasted.md` and given to `source-reader` as a file.

With no source at all, ask what the change is. Do not infer one from the repo state.

## 2. The Brief

Restate the request as a brief, matched in length to the change:

- **Goal**: what is different when this is done.
- **Scope and non-goals**: especially anything the source mentions that you are *not* doing.
- **Constraints**: compatibility, deadlines, interfaces that cannot move, stated preferences.
- **Design choices**: each choice about how that the ticket's Technical Requirements or the person
  names, with its source. They are the plan's defaults, and the planner re-checks each.
- **Acceptance criteria**: how the person will judge it.
- **Assumptions**: every place you filled a gap the source left open, marked as yours.
- **Branch**, with no ticket: the name step 6 will create, in the repository's branch naming. The
  plan is written under it from step 3.

**A bug.** When the source is a Bug ticket, or a prompt that describes wrong output, the brief
says so, with the wrong value and where it was seen, and requires the plan's first step to be a
failing test at the step that produced the wrong value, run red before any fix. The root cause,
once found, goes to `pr-create` at step 11.

**The depth floor.** Run `python3 "${CLAUDE_SKILL_DIR}/../../scripts/depth_floor.py" HEAD` with
`--paths` and the files the brief names, relative to the repository's top level. It prints
`depth:` light, standard or deep and its reason. **Light** is the light build
`${CLAUDE_SKILL_DIR}/reviews/wave.md` "Depth" defines, with no plan reviewer and the planner
optional; **standard** is the wave there; **deep** is the wave, with the planner and the plan
review always run. The person may raise the depth, and lower a standard floor to light at step 5;
deep is never lowered.

**Then ask, in one widget**, every question about the brief that changes the shape of the work, up
to three, and what to do next: **Plan it**, steps 3 to 5, recommended at standard or deep; **Build
it now**, recommended at light and, at standard, a lowering to light, which skips the planner and
the plan review and brings a short plan to step 5's gate, and not offered at deep; **Stop**, with
nothing written; **Let's discuss**. Ask nothing you can answer by reading the code; that is step 3's job. At light, a
one-line change may skip the question and say so. Write a Build it now plan as the draft with `procedure: step 2:
build it now` under `## Corrections`. At standard, step 5's gate asks for the lowering's reason;
if the person keeps standard there, go back to step 3.

## 3. Draft the Approach

Invoke the **implementation-planner** agent with the brief, the verbatim source text, the context
page's For planning section when there is one, and each provisional decision from step 1, which
the plan builds on and names the steps that depend on. It returns findings with real file
references, an approach, ordered steps, a test strategy, risks, and open questions. Write its draft
to the plan path, under the `Source:` line and the brief, with step 1's `## Provisional decisions`
and no `Approved by:` line, so the plan reviewer reads a file and an interrupted session resumes at
step 4.

Skip the planner, and say why, only for a light change the person did not choose **Plan it** for
and for **Build it now**. At standard the planner runs, however small the diff, unless the person
chose **Build it now**, their lowering to light; at deep it always runs. At standard, skipping it
is the person's choice, not your judgment.

## 4. Adversarial Plan Review

Invoke the **implementation-plan-reviewer** agent with the brief, the verbatim source, and the
draft plan file's path. It returns `CLEAN` or `CHANGES REQUESTED` with findings marked blocking or
non-blocking.

Revise the draft for each blocking finding and invoke it again with the revision, its previous
findings, and your reason for each one you declined, until it returns `CLEAN` or after three
rounds. A non-blocking finding you decline, or a blocking one still standing at the cap, goes to
the person in step 5 with the reviewer's reasoning. A finding that turns on a decision only the
person can make is an open question: carry it into step 5.

Skip this step when step 3 skipped the planner, and at light depth.

## 5. Agree the Plan — Gate

Show the plan as ordered steps:

```
#   Step                                  Files                     Verified by
1   Add the retry policy type             src/http/policy.py        unit test, new
2   Thread it through the client          src/http/client.py        existing client tests
3   Default it in the config loader       src/config.py             unit test, new
4   Document the new setting              README.md                 —
```

Then the plan's `### Signatures`, public ones first, and the planner's **Pull requests** list when
it names more than one, each with its base, its steps and the criteria it claims. After that, only
what needs the person's call: each open question, the planner's and the plan review's, with your
recommendation and its evidence; each design choice the plan's `### Design choices` marks
challenged, to keep or to take the planner's alternative; any plan-review finding left standing;
each provisional decision, with the steps that build on it; anything the planner flagged as
larger than the request implied. The approach, the risks and the depth take one line each; the
plan file holds the rest.

**The depth line.** Run the script again with `--paths` and the plan's files and `--signatures` and
the plan file: `Depth: <level> (floor: <level>; reason: <reason>)`, with what planning cost so far
(the planner's and plan reviewer's time and tokens) and what the level runs, as wave.md "Depth" and
"Who runs" set out. A plan written without the planner carries a `### Signatures` section too,
`none` or one template line per signature; the script exits 1 on a missing or malformed section,
which you fix before running it again. An epic is deep whatever the script says. A deep line on a
plan the planner did not draft goes back to step 3 before the gate, since at deep the planner and
the plan reviewer always run.

**Ask in one widget**, up to four questions: each open question, the recommended answer first,
and the plan itself, its question naming the draft at the plan path as a link, **Approve** (recommended), **Request changes** (then ask, as free text, what
to change), **Stop**, keeping the draft at its path, or **Let's discuss**. A recommendation is never an answer the person did not choose.
An answer other than the recommended one revises the plan, and the gate asks again. A question the
person answers only for now becomes a provisional decision, with your read of `Affects:` as a
draft; one they give no reason for is final. In the same widget when they apply: at a standard
floor the person lowered, the reason, and the focused reviewer's brief, `documentation` for a
change with no code and `simplicity` otherwise unless they name another; on a dirty tree, what is
uncommitted and whether to go on; off the default branch, which base to branch from, the current
branch or the default branch. When the questions exceed four, ask all but the plan first, and the
plan in the next widget.

Take free-form direction: reorder, split, drop, or add steps, change the approach, cut scope, push
back on a risk. Where you disagree, say so once with the reason, then do it. Approval of one step
is not approval of the plan.

**Record each correction.** When the person overrules the draft (reorders, cuts or adds a step,
rejects the approach, overrides a plan-review finding), append one line under `## Corrections`:
`plan gate: <what the draft said> -> <what the person said, in their words>`, prefixed
`procedure:` when it is about how this skill or its agents worked rather than the code. A lowered
depth is `procedure: plan gate: depth standard -> light (brief: <brief>), <their reason>`. Answers
to open questions are decisions, not corrections; a changed design choice also goes to `pr-create`
at step 11.

**Write the agreed plan** to the plan path. It holds a `Source:` line (the ticket key, the file's
path, the issue's URL, or `prompt: <its first sentence>`); the brief; the steps, with a checkbox
each; the approach; the settled questions with their answers; `## Provisional decisions` when
there are any; `Approved by: <login>`, the login `get_me` returns on the server `using-github`
"Resolving the tools" and "Picking the server" find, or `gh api user --jq .login` once the person
has said to use `gh`, or `Approved by: not recorded` where that file would stop because the server
cannot be reached, said once as `servers.md` sets out, never a guessed login; `Depth: <level>`, and,
from step 6, `Base:`. Mention it once.

## 6. Branch

Branch from the base step 5 settled, the default branch when the current branch is it. Write
`Base: <branch>` as the second line of the plan file, then branch from the up-to-date base, with
the name step 2 gave or the repo's branch naming. When the plan names several pull requests, branch
for the first; each part's base is its own line, `Base: <branch> (part k of n)`, written as that
part is branched, the later parts based on the previous part's branch. A later part is built by
invoking this skill again on the ticket: it resumes from the plan, and branches part k from a
clean tree only, from part k-1's branch, or from the default branch once part k-1 has merged. If
the repo's instructions say it commits to its default branch, stay on it and say so.

## 7. Implement

Work the steps in order, keeping the plan file's checkboxes current. On the bug path, run the
first step's test before any fix and write its failure under that step in the plan file, `Red:
<test> · <the failure line>`; a test that passes before the fix reproduces nothing, so go back to
the person. Follow the conventions in the repo's instruction files.

Code, comments, docstrings, and docs describe the code as it now is. A comment can say why the
code works this way, but not how it got there: no mention of this session, the plan, options you
rejected, or what the code used to do.

**A TODO the change does not address stays**, wherever the build rewrites or moves its code,
honing included. One the change completes goes, and step 9 names it with its tracking reference.
One that looks obsolete is kept and raised with the person as a tangent, with the reason, and
removed only on their word.

Build what the plan says. A discovery that invalidates a step (the interface is not what it
looked like, the change is twice the size, a dependency is missing) goes back to the person with
what you found and what you propose instead. **Do not absorb a plan change silently**, and do not
widen the work because you are already in the file.

## 8. Verify

Do not run the tests or linters yourself. Verification is the wave
`${CLAUDE_SKILL_DIR}/reviews/wave.md` sets out, at the plan's depth: who is in it, how the digests
are merged, when it converges, the honing passes after it and when it stops. Read it before the
first wave.

First run `python3 "${CLAUDE_SKILL_DIR}/../../scripts/depth_floor.py" <base>` again over the diff
itself: a floor above the plan's `Depth:` raises it, and you say so in one line; it never lowers
it. A standard floor does not raise a plan the person lowered at step 5 while every changed file
is one the plan's steps name; a changed file outside them raises it to standard, and you say
which. A deep floor always does. When the reason names an untracked path the change does not own,
say so and run it again with `--paths` and the change's files; a light floor that run calls
provisional counts as standard. A floor raised to deep on a plan the planner did not draft goes
back to step 3 before the wave, the diff kept, so the planner and the plan reviewer read it.

**Hone a converged build.** At standard or deep, when the diff changed code, a converged wave is
followed by wave.md's "Honing" before the outcome below is written: up to two passes that tighten
the passing diff without changing its behavior. Step 9 says what honing applied and what it left.

Where the change is observable in the running app rather than only in tests, exercise it yourself
and say what you saw.

**Record how the build ended.** When the loop stops, for whatever reason, write
`.review/build/outcome.md`:

- `Build: <phrase>`: `passed` when the implementation reviewer returned SATISFIED and, at light,
  the focused reviewer has no blocking finding; otherwise the phrase of the stop wave.md's "Stops"
  lists.
- `Depth: <level>`, the level the build ran at; each `Reopened:` line in the reopened file, copied
  in; on a passed build, each failure the reviewer named as predating the change, on a line of its
  own with its evidence.
- In `${CLAUDE_SKILL_DIR}/../pr-create/body.md`'s "Already checked" format, four lines built over
  every wave, not the last: `Rules checked:` every citation any wave raised, each as `<key> fixed`
  or `<key> declined`; `Declined:` each cited finding left unfixed, as `<key> — <one-sentence
  reason, with no semicolon>`, separated by `;`; `Suggestions:` each non-blocking finding left for
  the person, as `<key> — <what was suggested>`, and each uncited one as `<file>::<symbol> — <the
  reason>`; `Escalated:` each finding taken to the person at a stop, with what they decided. `none`
  after the colon where there is nothing to list. A key is written bare, with no backticks:
  `scripts/record.py` refuses a `Rules checked:` or `Declined:` entry that does not open with a
  citation.
- From the plan's `## Corrections`: one `Nominated:` line holding every code correction and one
  `Procedure:` line holding every `procedure:` one, entries separated by semicolons and none inside
  an entry, `none` when there are none.
- On the bug path, `Reproduced: <test> failed before the fix`, once the implementation reviewer
  has confirmed it. When a wave ran `downstream check`, its `Ripple:` line from the last run.

`pr-create` reads it and the hooks' `.review/build/already-checked.md` into the pull request body.

## 9. Review the Diff — Gate

Show `git diff` grouped by plan step, so the person can check the code against what they approved.
Call out anything you changed that no step called for, and why, what honing applied or restored,
and any non-blocking finding you left unaddressed.

**Ask in one widget.** When the plan has `## Provisional decisions`, list each with where the diff
applies it and what the build showed, and ask whether that makes any final. Then the diff itself:
**Commit, then the pull request** (recommended), which commits at step 10 and runs `pr-create` at
step 11, which shows the description and asks before it pushes; **Commit only**; **Stop**,
keeping the diff uncommitted, then step 12; or **Let's discuss**. The question says that a change is asked for by
typing it in Other. Nothing is committed without one of the two commit answers.

A decision made final leaves the section for the settled questions, with its answer, the evidence
and who decided; the rest stay provisional for the pull request. A final answer that differs from
the one the diff was built on is a diff-gate correction, and the build goes back to step 7.

Record each correction the person makes here as step 5 does, with `diff gate:`; when they approve
after one, add it to `outcome.md`'s `Nominated:` or `Procedure:` line too. For changes, go back
into the build as "The Build Record" says, then to step 7; step 8 runs again before the next
approval.

## 10. Commit

Use the **commit** skill (`/lasp-dev:commit`): it decides what belongs in the commit and writes
the message.

## 11. The Pull Request

On **Commit, then the pull request**, use the **pr-create** skill (`/lasp-dev:pr-create`),
which writes the description, asks, and pushes on a yes. Only this session holds the goal, so hand
it the why, **verbatim, not summarized**:

- the source's own statement of the problem, in its words;
- the brief's goal and acceptance criteria as the person agreed them;
- the questions settled in steps 1, 5 and 9, with their answers and who gave them, a ticket's
  Open Questions entry included, and each challenged design choice the person changed;
- on the bug path, the root cause;
- defects found along the way, and how bad each is;
- the incidental changes called out in step 9, and why each rode along;
- the plan's `## Provisional decisions`, each with its answer, why it is not final, what it
  affects, what would make it final and where the diff applies it; for a part of a plan in
  several pull requests, only those with a dependent step in this part.

On **Commit only**, say what is committed locally and go to step 12. **Never open a pull request
or push unprompted.**

## 12. Report

What was implemented, the commit SHAs, whether the last wave's checks ran on the tree that was
committed (pre-commit changed nothing), and if not, what changed after them, the pull request URL
if one was opened, and anything from the plan you did not do, with the reason. When a `ticket/`
finding was kept as a departure, or the person changed a challenged design choice of the ticket,
name `/lasp-dev:ticket-draft settle <key>` to record it on the ticket. The last line names
the next command, `/lasp-dev:work`, which picks the next phase; when `work` invoked this skill,
skip this offer: `work` asks.

Then release the working tree: `printf '{"session_id":"%s"}' "${CLAUDE_SESSION_ID}" | bash
"${CLAUDE_PLUGIN_ROOT}/hooks/build-record.sh" release`. Release it the same way wherever the skill
ends sooner, at a stop that hands the work back to the person or when they say to stop; a question
that waits for their answer is not an end.

## Rules

- **The person approves the plan before any file is touched**, and approves the diff before it is
  committed. The plan's approval is an answer to step 5's gate, or a request that names it: an
  instruction given before the plan is shown that does not, such as "take your recommended answer
  to every question", settles the gate's other questions, never the approval.
- **Never invent a requirement the source does not carry.** A gap is an assumption you state in the
  brief or a question you ask, not a decision you bury in the code.
