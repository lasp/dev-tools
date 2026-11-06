---
name: pr-create
description: >
  Writes a reviewer-focused description for the current branch and opens the pull request, a
  draft by default. Use when asked to "open a PR", "put up a PR", "create a pull request" or
  "write a PR description".
metadata:
  author: llm-tooling
  version: 3.8.0
---

# Open a Pull Request

Describe what this branch does, then open the PR. The description is written for a reviewer who knows the project but not this change.

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## Options

Take these from the person's request when present; otherwise use the default:

| Option | Default |
|---|---|
| Draft | Draft, unless the person asks for it ready for review |
| Title | Derived from the change, in the style `commit`'s "Message" sets, since a squash merge lands the title on the default branch; a single-commit branch may use its subject |
| Base branch | The `base=` line `bash "${CLAUDE_PLUGIN_ROOT}/hooks/where.sh" --fields` prints, the `Base:` line of this branch's plan; otherwise the repo's default branch |
| Assignees | The PR author — the login `get_me` returns |
| Labels, reviewers | None |

## GitHub Access

GitHub is needed at two steps: the check for an open pull request (Branch and Changeset, 4) and the opening (Confirm, Then Open). Reach it there as `${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md` sets out; `gh` carries both once the person has chosen it. Everything between is written without it. A server that is not connected or fails is said as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out. At the check, what is lost is knowing whether a pull request is already open: say so and go on drafting; the check runs again before the opening. At the opening, the pull request itself is lost: stop with that message and print the full description in a code block, so the work is kept.

## Branch and Changeset

1. `git branch --show-current`. If HEAD is detached, stop and say so. If the tree has uncommitted changes, say what they are — they will not be in the PR — and ask whether to proceed or commit first.
2. Resolve the base branch, from the plan file's `Base:` line first, then `git fetch origin <base>` and `git merge-base HEAD origin/<base>`.
3. `git log --oneline <merge-base>..HEAD` and `git diff <merge-base>...HEAD`. With no commits ahead of the base, stop — there is nothing to open a PR for.
4. Check whether a PR is already open for this branch. If one is, do not create a second: offer to update its description, title, and options instead. When `work` runs this skill after a reopen (`why: reopened-body`), the update is the description, with the revision's Already checked block.

## Understand the Change

Read `CLAUDE.md` (and what it imports), `README.md`, and any roadmap file **before** the diff — that ordering is what lets the description say how the change fits the project instead of restating the diff.

Then read the changed files for surrounding context and cluster the changes into the conceptual groups a reviewer would form. Past ~50 files, cover the significant groups and give the mechanical ones a line.

## Changelog and Version

Infer from what exists (`CHANGELOG.md`, `.changeset/`, `changelog.d/`; the version in `pyproject.toml`, `package.json`, `Cargo.toml`) and what comparable merges touched whether this branch owes an entry or a bump. Where release tooling — release-please, changesets, towncrier — generates them, nothing is owed.

If one is owed and missing, name it and offer to add it in the existing format before opening the PR; on a yes, add it, commit it with `/lasp-dev:commit`, and reread the changeset. Never edit those files silently. Nothing to infer from, nothing to say.

## The Why

**No description is drafted until you can state why this work exists.** The diff cannot supply
it, and what a person or a calling skill hands you varies in clarity and specificity, so judge it
yourself every time, whoever invoked you.

Gather the motivation from what the person or the calling skill supplied (`implement-change`
hands over the source's own statement of the problem, the agreed goal and acceptance criteria,
the settled questions, the defects found, the incidental changes and the provisional decisions,
verbatim), the ticket, the
context page the `Ticket:` line resolved, `.review/context/<ticket>.md`, the plan file's brief and
settled questions, which are the agreed framing when no calling skill handed one over, and the
commit messages or other planning notes. The plan's steps and approach inform what changed and
the design choices, never the why. Then check that, from those sources and not from the diff, you could
write each of the three things the description leads with: the problem as it stood, how bad it
was, and the goal.

Any doubt on any of them, a gap, a contradiction, a vague problem statement, or a why that only
restates the change ("makes X safe to redrive"), means stop. So does a why that rests only on
what happened while the change was built: the work done, the bugs hit and the steps taken say
what was done, not why it was needed. When no ticket, brief, issue or statement from the person
names the problem, ask the person why the work was necessary, and keep asking until the answer
is a reason, not a summary of the work. Ask the author in plain prose, not
with `AskUserQuestion`, whose fixed choices would put your guesses in their mouth: say what is
understood and exactly what is missing, and end the turn on what you need before drafting the
description. Do not draft, and offer no candidate answers. Repeat
until all three are clear. What the person or a calling skill supplies wins over anything
inferred, including their framing of why.

## Write the Description

Word the body as `${CLAUDE_SKILL_DIR}/../writing/references/short.md` sets out, and read its "Links and public repositories" before a Jira or Confluence link goes in, the person's included. Write for a colleague who knows the project, has a couple of minutes, and will read the diff
next. A reviewer can judge whether a change achieves its goal only if they know the goal, and
the diff cannot tell them; a change can pass every test and still miss the point. Give them what
the diff cannot: why this change is being made, and why it is built this way. Most of the words
go there.

Without a standard, a repository's own pull request template sets the sections and this guidance
fills them. Length follows the change, not the author's thoroughness: a small fix gets a
paragraph of why and a line naming the test that guards it, with no headings, and a large change
grows in what changed, never in the why.

**Each fact once.** The ticket owns the goal, the scope and the Acceptance Criteria; the
description cites them (`Ticket:`, `AC-n`) and does not retell them. Within the description, a
fact is stated in the section that owns it and nowhere else: the goal once, in the why, with
each change tied to it in a line rather than a paragraph that states the goal again; one command
to run the tests; a fact about a stack of pull requests on the `Ticket:` line, not in the prose
of each. A fact the Summary or the why has stated is not stated again under design choices,
what changed or limits: those sections add only what the earlier ones did not say.

**Lead with why.**

- The problem as it stood: what was broken, missing or undefined, and what it cost. A decision
  nobody had made counts; name it as open, then give the answer.
- How bad it was, by impact rather than by how it was found. Where a defect survived because it
  is expensive to test, say so and name the test that now guards it.
- The goal: what is true once this merges, stated so the reviewer can check the diff against it,
  as the last sentence of the why rather than a line of its own that says the why again.

**Then what changed, tied to the why.** For each goal, how the change meets it, and the reasoning
behind any approach a reviewer might question. Mechanics the diff shows plainly need no words.
Group by concept when the branch spans several. No reading order and no file tour.

**Incidental changes** get their own short section only when a reviewer must check them: a
latent bug fixed on the way, a refactor that changes what a caller sees. One line each on what it
fixes and, where it is not obvious, why it rode along. A serious latent bug is still called
serious here. A comment reworded or a test tidied needs no line.

Wherever they apply, also say:

- behavior changes that reach other callers or services, such as an event emitted again;
- known limits, and prerequisites not yet verified for deploying or using the change;
- each provisional decision, from `implement-change`'s hand-over or the plan's `## Provisional
  decisions`, marked `Provisional:`: the answer the change builds on, why it is not final, what
  it affects, what would make it final and where the diff applies it, so the reviewers and the
  author know where to come back to;
- a small change that widens what can be committed, deployed or exposed (`.gitignore`,
  permissions, public endpoints), flagged with its reason; never as a neutral one-liner.

Write it to be read:

- Order it from context to detail: what the code does and who relies on it, the problem, the
  change and why it is built this way, its consequences, then what changed, how it was tested and
  how to test it. A reader who stops after the first paragraph knows what is affected and why.

- Size it to what a reviewer needs to judge the goal, not to the diff. Cut mechanics before
  motivation; a small fix to a serious problem still gets its why.
- Headings once there are several sections, named for goals and problems, not files.
- Formatting as the GitHub Markdown bullet in `${CLAUDE_SKILL_DIR}/../pr-review/comment-style.md`'s
  Form says. Where the change adds a workflow, an architecture pattern or a dependency between
  components that a diagram shows faster than prose, consider a Mermaid diagram
  ([diagrams](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams)),
  which GitHub renders inline.
- Plain words, as to a teammate at their desk. Say how bad a problem was.
- Argue why the goal matters; do not argue that the change is good. The reviewer judges that
  against the goal.
- Leave pass/fail to CI and line counts to the diff: no test counts, no "pre-commit passes".
  Say what was not verified and which test guards the goal.
- What changed is behavior and the public surface, never a file tour: the diff lists the files.
  Internals get words only where a reviewer would question them.

**The edit before showing.** Write `.review/pr-audit.md`, replacing any earlier one, then edit
the draft by it:

1. **Facts.** One line per fact the draft states, with every section it appears in. A fact in
   more than one section stays in the first and is cut from the rest.
2. **First paragraph.** Copy it, then answer from it alone, one line each: what is affected, who
   relies on it, why it changes. A question it cannot answer means rewriting the paragraph.
3. **Size.** The diff's changed lines, from `git diff --shortstat`, and the draft's words. Under
   about 50 changed lines, the description is a paragraph of why and a line naming the test that
   guards it, inside only the headings the template requires; the paragraph keeps the reason for
   any part of the change a reviewer would question, such as why something stays.
4. **Cuts.** Each sentence a reviewer would not miss, by its first words, and each removed.

Show the edited draft, not the audit. If a reviewer could not judge the diff from the why alone,
or it restates the what, rewrite it.

## The AI Assistance Level

A description's attribution line is the generated-with line this session supplies, with the
level appended as its last sentence, as `${CLAUDE_SKILL_DIR}/../pr-review/comment-style.md`'s
"AI assistance level" sets out:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code). AI assistance level: 5/5 (not read by a person).
```

Append it to whatever that line reads, so a model suffix stays. An update to an open pull
request's description keeps the level the person last set unless they set another, with its
meaning from `comment-style.md`'s table. Where the person or the repository's instructions say to add no attribution, the
description has no attribution line and so carries no level.

## In a Repository With a Standard

When the repository has `standards/review-rules.md`, `standards/decisions.md` or
a `standard:` pointer in `standards/profile.yaml`, read
`${CLAUDE_SKILL_DIR}/standard-repo.md` before The Why: its `Ticket:` line names the context page The Why reads.

## Confirm, Then Open

Show the full description, the title, the base branch, and every option — draft status, labels, reviewers, assignees — as they will be submitted, and remind the author to review their own diff before any colleague does; name each controlled item the body carries text from, and its warning (`${CLAUDE_SKILL_DIR}/../writing/references/short.md`, "Controlled content"). Opening a PR notifies people and starts CI, so ask, naming what happens: **Open the draft** (Recommended), or **Open it ready for review** when that was asked, written **Push `<branch>` and open the draft** when the branch has no upstream or has unpushed commits; **Change something**; or **Stop here**, printing the description in a code block so it is kept. Silence or an ambiguous reply opens nothing.

On approval:

1. Push with `git push -u origin <branch>` when the question named it, or as `using-github`'s "Pushing" says where the repository's instructions forbid an agent's push.
2. Create the PR through the server, or `gh`, as resolved, with the title, body, base, and draft flag.
3. Apply labels, reviewers (only if explicitly requested), and assignees. A label that does not exist, or a reviewer without access, will be rejected — report which one and leave the PR open without it rather than failing the whole operation.
4. Report the PR URL and number.

On a draft, close by offering the self-review: `/lasp-dev:pr-review` on this pull request now (Recommended), which posts its findings if the author chooses, so the last round of AI-assisted review is on GitHub for colleagues to see. Ask the author, too, to read the whole diff on GitHub and leave a comment on each thing to change: they own the change before a colleague sees it, and `/lasp-dev:pr-fix` walks their comments with everyone's, ahead of the findings. The author then answers both with `/lasp-dev:pr-fix` and marks the pull request ready. When `work` invoked this skill, skip this offer: `work` asks.

If creation fails, print the full description in a code block so the work is not lost, and report the error verbatim, as `servers.md` sets out.

Never merge the PR, never force-push, and never push to the base branch.
