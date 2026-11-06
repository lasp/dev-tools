---
name: pr-fix
description: >
  Answers the review on your pull request: takes each thread, your own comments included, to a
  verdict, then implements the agreed fixes, pushes and replies. Use when asked to "answer the
  review findings", "reply agree or disagree", "address review comments", "fix the PR feedback"
  or "respond to my reviewer".
argument-hint: "[PR number or URL] [scope] [skip the gate] [rebase]"
metadata:
  author: llm-tooling
  version: 2.8.1
---

# PR Fix

Turn reviewer feedback into pushed changes and answered threads. The **github-pr-fix-planner** agent assesses the comments and plans the response; the person decides which fixes happen; you implement, verify, and reply.

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## Options

| Option | Default |
|---|---|
| Pull request | A number, URL or branch; otherwise the current branch's |
| Scope | Every thread; or one reviewer's, or only the blocking ones |
| Plan review | On: step 7 stops for approval before any code is touched. Off only when said at invocation ("skip the gate", "just apply the fixes"); not mentioning it, or a plan that looks obvious, is not permission |
| Rebase | Asked at step 4 when the branch is behind its base; "rebase" at invocation answers it with rebase now |

## The Outline

Before step 1, print the outline, then open every later turn with the step it is on, "Step 5 of 13: three threads left to decide", so a person who comes back knows where the round stands:

```
pr-fix on #<n>: 1 input · 2 GitHub · 3 branch · 4 base · 5 disposition the threads · 6 plan · 7 approve the plan · 8 implement · 9 verify · 10 the diff · 11 commit · 12 push and reply · 13 report
Stops for you: 3 when the tree is dirty or the remote moved, 4 when the branch is behind its base, 5, 7, 9 when a failure predates the round, 10, and 12 (the push and the replies).
```

The progress file, `.review/pr-<n>-fix-plan.md`, written from step 5, opens with `Head: <sha>` and a `## Progress` checklist, one box per step, checked as each finishes; step 5 adds `## Dispositions` and step 7 `## Draft plan`, then `## Plan` on approval. A later run on the same head reads it and goes on from the first unchecked box; a new head starts the file afresh, keeping the dispositions not yet posted and the rows marked `fixed <sha>` whose fix reply has not posted.

## 1. Input

From the person's request: the PR identifier (number, URL, or branch — otherwise detect from the current branch), any scope limit ("just the comments from @alice", "only the blocking ones"), whether the plan gate is waived, and context that should inform the fixes. All optional.

## 2. GitHub Access

Reach GitHub as `${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md` sets out, and pass the server to every agent this skill runs. This skill cannot run on `gh`, since step 5's thread table needs the server: when the server is not connected or fails, or the person has chosen `gh`, say so here as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the review threads being what is lost, and stop, before any branch or rebase question.

## 3. Resolve the PR and the Working Tree

Record owner, repo, number, head and base branch, head SHA, and author. If no PR resolves, stop and ask for a valid identifier.

- **The PR's head branch must be checked out.** If `git branch --show-current` does not match, stop and say which branch to check out.
- **Uncommitted changes** — if the tree is dirty, say what is uncommitted and ask whether to proceed. Your commits should contain the fixes, not whatever was already in progress.
- **The remote may have moved.** `git fetch origin <head>`; if the remote branch is ahead, the author pushed since you last looked: say by how many commits, and ask whether to pull (recommended). On a yes, `git pull --ff-only`; when it will not fast-forward, stop and let the person reconcile. A no to the pull stops the skill: every later step would work on a stale head, and step 12's push would discard the remote's commits. A pull is a merge, and some repositories' instructions forbid one nobody asked for.

## 4. Check the Base Branch

The base branch may have moved while the review sat. `git fetch origin <base>`, then `git merge-base --is-ancestor origin/<base> HEAD`. When the branch already holds the base, say so in one line and go on.

When it is behind, **stop**: say by how many commits and whether the base's new commits touch files this pull request changes, and ask. Fixing first keeps the review's line numbers; rebasing first fixes against what will merge.

- **Rebase now** — rebase onto `origin/<base>` before anything is planned; recommended when the base's new commits touch this pull request's files. Not offered on a dirty tree; say why.
- **Fix first, rebase before the push** — step 11 rebases the committed fixes; recommended otherwise.
- **Don't rebase** — the round goes on against the current base; recommended when the repository's instructions forbid a rebase nobody asked for, which the question then says.

"Rebase" at invocation is the first answer, given in advance; on a dirty tree, say it cannot run yet and ask between the other two. Conflicts stop the skill — report the files and hand them to the person rather than resolving or `--skip`ping them.

**Do not push the rebase.** Step 12 pushes it together with the fixes.

## 5. Disposition the Threads

Every thread ends this step with one of four dispositions: **agree**, **disagree** or **discuss**, the three verdict words of `pr-review`'s "Whose reply counts", or **answer** for a question. Step 7 refines an agree into one of two kinds, each posted as `Agree`: **move**, for a comment that belongs in a sibling pull request of the stack or upstream as D-006 says, whose reply names where it goes and whose code change here is none; and **reopen**, for a thread whose `Proposed:` line opens `changes the plan`, or a person's thread the author marks as design: the review showed the design is wrong.

**Read them.** One `pr-reader` call in `state` mode, given the repository and the pull request, lists every thread, finding threads and people's threads alike, with its state in the script's words: `agree`, `disagree`, `discuss`, `unanswered`, `unparsed`, `answered` for a question, `none`, and `contested: yes`, and in its last column whether the verdict was judged from a reply in the person's own words (`yes, <login>: <basis>`), and `unclear: <basis>` where the judge could not tell. A contested row shows the first verdict's word in the verdict column and `yes` in the contested column, so read that column before the word.

Read `.review/pr-<n>-fix-plan.md`'s `## Dispositions` too, when it exists, for decisions an earlier run made. A local decision is on GitHub when its thread's row shows the word it posts as:

| Local disposition | Posted when the row shows |
|---|---|
| agree, move, reopen | `agree` |
| disagree, discuss | its own word |
| answer | `answered` |

Otherwise it is not posted, whatever its line says. An `agree` row, not contested, that has replies after the Agree, or whose text after the verdict names a commit or opens with step 12's reply only, follow-up or moved form, was answered in an earlier round: count it, and do not walk or plan it again.

**Assess them.** Invoke the **github-pr-fix-planner** agent in `assess` mode with the dump directory, `.review/threads/pr-NNNN/`, every row except those answered in an earlier round, the pull request author's login, and the context from step 1. For each thread it returns what the comment relates to in this pull request, whether its claim holds in the code, with the evidence, who gave the verdict already on it, if any, and a recommended disposition with its reason and, for an agree, its size. Always invoke it; never triage threads by hand.

**Take the author's answers as given.** A thread whose verdict reply is the pull request author's, on GitHub or in the local `## Dispositions`, is dispositioned by it, and is not asked again, whether the row read their word or judged their own words; a judged one is shown with its basis, so the author can change it. A verdict from someone else is shown, and the author still decides.

**The author's own comments are review comments.** A thread the author opened on their own pull request is walked like anyone's: the author reviewing their own diff is a reviewer, and only differs in that they also answer. A resolved thread is walked too, since resolving it is no answer; the walk shows that it is resolved, and the assessment says when the code already does what it asks. When the `get_me` login is the author and they opened no thread, say in one line that reading the whole diff and commenting on GitHub is the self-review `pr-create` asks for, and go on.

**Walk the rest** with the author: the rows whose verdict is `unanswered` or `unparsed`, whose contested column reads `yes`, whatever their verdict word, or whose verdict is from someone other than the author, and the `discuss` rows with a reply after the author's Discuss. Four at a time, one question per thread in one widget; each gives a finding's severity, headline and location, or a person's thread's opener, first line and location, then the assessment's one-line relation and whether the claim holds, and offers how to address it: **Fix it** (`Agree`), **Reply only** (`Agree`, with a reply and no code change, such as `a note for reviewers, no change` on a comment that only tells reviewers something), **Decline** (`Disagree`) and **Discuss**, the assessment's recommendation first, its description opening with the size where it offers a change. On `Disagree` to a must fix or should fix, ask once for the reason. A Question finding, or a person's thread that asks a question, gets no widget: ask for the answer as free text, offering the assessment's draft. The person may take several recommendations in one reply. When the `get_me` login is not the pull request's author, walk only finding threads that have no reply yet, and say that people's threads, the author's own among them, and contested findings need the author's reply. This may take several rounds; the person may stop to look at code or ask about a thread before deciding.

**Show the result**: every thread, grouped under agree, disagree, discuss and answer, each with its location, its reason where it has one, and whether the decision is already on GitHub. Write it to `.review/pr-<n>-fix-plan.md` under `## Dispositions`, one line per thread: its id, location, disposition, reason, its thread's link, `posted` or `not posted`, and `fixed <sha>` once step 12 pushes its fix. A Reply only choice is an agree whose reason is `reply only: <the response>`. The link is the `html_url` of the thread's first comment in the dump's `comments.json`; read only that field.

Decisions not yet on GitHub post once, at step 12, with the fix replies. Until a decision is on GitHub the record counts its thread unanswered, so `work` routes back here and the next run raises it again. When the round ends before step 12 (nothing is agreed for a fix, or the person stops here), or the person asks to post the decisions now, list each with its thread as a link, `[skills/x.py:48](<html_url>)`, and the reply as step 12 drafts it (an agree whose fix or response is not yet planned posts as `Agree` and its reason, and stays to fix until step 12 replies; a reply only row's post is its answer), and ask: **Post them here** (Recommended), each under its own thread and marked `posted`; **I'll reply on GitHub myself**; or **Skip for now**.

## 6. Plan the Response

Invoke the **github-pr-fix-planner** agent in `plan` mode with the dump directory, `.review/threads/pr-NNNN/`, the rows below with the assessment's entries for them, the findings reviews' ids, the context from step 1, and, in a repository with a standard, the path of `.review/standard.md`, written first as `pr-review` step 2 does, for the rules a fix must keep. It reads the threads from the dump's `comments.json` and the code they anchor to in the working tree, and calls no GitHub tool. It returns a plan sorting the rows into **Clear Actions**, **Discussion-Only**, **Moves** and **Needs Clarification**. If step 4 rebased, say so — the line numbers in the dump may not match the local files. Always invoke it — never fetch and triage comments by hand.

**The rows to plan** are the ones step 5 dispositioned **agree** that no earlier round answered and that are not marked `fixed <sha>`, posted or not, finding threads and people's threads alike; leave out the rest and give their count. **People's comments come before AI findings:** the threads people opened, the author's and other developers', then the findings, in the planner's input and in the plan, since a person's comment is more often about the design and a finding agreed to may have missed the mark. A finding's thread, from a review whose summary's first line is `## Review` (or `## Standards review` on an earlier one) and that carries the attribution line, is the agent's proposal, not a person's request, and its `Proposed:` line is the change to make. A **disagree** or **discuss** thread is not planned, and an **answer** goes out as step 12's reply. An agree whose reason names a follow-up ticket or a later pull request is listed with that text, not planned, and gets step 12's follow-up reply. An agree whose reason opens `reply only:` is listed with its response, not planned, and gets step 12's reply only reply unless step 5 posted it. A row marked `fixed <sha>` is listed with its sha and gets step 12's fixed reply. When every row is a follow-up, reply only or fixed, go to step 12.

**Conflicts.** The assessment's Conflicts section names each place where a person's comment and an agreed AI finding ask for different things in the same code, and whether the difference is at the design level. At the design level the person's comment governs: the plan follows it, and the finding is shown beside it for a new disposition. Pass the conflicts to the planner with the rows.

## 7. Review the Plan With the Person — Default Gate

**The person approves the plan before implementation begins**, unless they waived the gate at invocation.

Answer the **Needs Clarification** questions first — nothing downstream is trustworthy while they are open. Then show each conflict from step 6, the person's comment and the finding side by side with what the plan does, before the table: a conflict means the plan rests on two readings of the change, so the whole plan is discussed before anything is approved. With any conflict, **Let's discuss** is the recommended answer to the approval question below, and the finding's disposition is the person's to change there. Ask them together, in one widget where the choices are discrete. Never guess at an ambiguous comment or implement anything depending on an unanswered one. **These questions are asked even when the gate is waived** — the planner raised them because they cannot be resolved from the code.

Then show every planned thread as a table, and under it one line counting what step 5 left out of the plan:

```
#   Thread                        Reviewer   Type        Disposition   Plan
1   src/auth/tokens.py:48         @alice     bug fix     agree         Return the expiry error instead of None
2   src/api/routes.py:112         @alice     refactor    agree         Extract the pagination branch
3   src/api/routes.py:12          @bob       docs        agree         Reply only: the import order is pinned for the plugin loader
4   src/geo/frames.py:30          @carol     refactor    move          Belongs in part 2 of 2, PROJ-42-two; reply naming it
Not planned: 1 disagree, 1 discuss, 2 answer.
```

A findings thread whose `Proposed:` line opens `changes the plan` is shown as a reopen: the person confirms it, or changes its disposition. An agree with no code change, from the planner's Discussion-Only section, is planned as a reply only. Take free-form direction: change a disposition, adjust an approach, split a comment into several changes, ask why something was classified as it was. Changing a row to **disagree** or **discuss** takes it out of the plan. **Disagreeing is a legitimate outcome** — a reviewer can be wrong or working from stale context. Say so plainly when you think a comment should be disagreed with, and give the reason. A thread whose Agree is already posted stays agree unless the person changes it; changing it to disagree changes a posted verdict, which the record cannot take back: say so before accepting it, and the reply gives the reason.

Whenever you offer a change, or answer a question by proposing one, its first words name its size, in the words `pr-review`'s "The review" lists.

Before asking, write the planner's whole plan, each planned row with its files, change and tests, to `.review/pr-<n>-fix-plan.md` under `## Draft plan`, replacing an earlier one, and name the file as a link in the question. A draft is never the approved plan: a resumed run reads only `## Plan`.

Then ask: **Approve** (Recommended); **Approve with a light review**, offered when the depth floor would be standard and every planned row is sized `one line` or `a few lines`, which runs step 9 at light and is recorded under `## Corrections` in the progress file as `implement-change` step 5 records a lowering, the rows' sizes as the reason unless the person gives another; **Stop here**, keeping the dispositions and the plan in the progress file; or **Let's discuss**. **Nothing is implemented before they approve**, and a reply about one thread is not approval of the rest. On approval, write the approved table to `.review/pr-<n>-fix-plan.md` under `## Plan`, replacing an earlier round's, remove `## Draft plan`, and update `## Dispositions` for any row the person changed: it is the plan step 9's reviewers read.

If the gate was waived, still print the table before starting so the person can interrupt, then proceed with the planner's approaches for the threads the person agreed with in step 5. Where you disagree with one, say so in a line rather than silently implementing it.

**A reopen hands the design back to a build, after this round.** Steps 8 to 12 run for the other planned rows, and step 12 posts the reopen's reply with theirs: one reply opening `Agree` that says the design is reopened. Then, before step 13's report, append `Reopened: <thread id> · <one clause>` to the file `where.sh --fields` prints as `reopened_file=`, `.review/reopened/<ticket>.txt`, or with no ticket `.review/reopened/<branch, / as ->.txt`, which a build's start does not clear and `pr-create` deletes once the pull request's description carries its lines. After step 13, with a ticket, run `ticket-draft settle <key> <thread id>` with the thread as the source of a departure, which it records on the ticket as a comment unless the person says the ticket's intent was wrong (`settle.md`, "A departure"); then `implement-change`, with the ticket as its argument or, with none, no argument, which re-plans from the existing plan file under a `## Revision N — <thread id>` heading with the thread's text in the brief, never a fresh plan. pr-fix ends there; the round after the revision's build replies on the thread as fixed.

An agreed `ticket/` thread whose planned fix keeps the code and records the departure, as the review contract's "Ticket findings" says, runs `ticket-draft settle <key> <thread id>` after step 13 the same way, with no reopen.

A reopen the person decides in this session, not on a thread, is recorded the same way as `Reopened: session-<pr>-<n> · <one clause>`, `<pr>` this pull request's number and `n` one more than the highest `session-<pr>-` id in the plan file's `## Revision` headings and the reopened file, so a second one is never mistaken for the first, and on a ticket in several pull requests another part never takes it for its own. It has no thread to settle against or reply on, so it runs no `ticket-draft settle` and gets no reply; `implement-change` re-plans under `## Revision N — session-<pr>-<n>` with the clause, in the person's words, in the brief.

## 8. Implement

Work one thread at a time, in table order, so each change stays traceable to the comment that prompted it. Follow the conventions the planner surfaced.

Change only what the comment calls for. A reviewer asking for a rename has not asked you to restructure the module.

If a fix turns out to be wrong, impossible, or much larger than the plan implied, stop and say so. That comment goes back to the person for a new disposition.

## 9. Verify

**The depth** is the floor `python3 "${CLAUDE_SKILL_DIR}/../../scripts/depth_floor.py" HEAD` prints over the round's diff, raised one level when any planned row is sized `an hour` or `changes the plan`. When the reason names an untracked path the round does not own, run it again with `--paths` and the round's files; a light floor the reason calls provisional counts as standard. A lowering the person chose at step 7 holds over a standard floor while every changed file is one a planned row names; a deep floor is never lowered. Say it in one line, `Depth: <level> (floor: <level>; reason: <reason>)`, before the reviewers run.

**What runs** at that depth is what `${CLAUDE_SKILL_DIR}/../implement-change/reviews/wave.md` sets out for it, with the plan file `.review/pr-<n>-fix-plan.md`, the brief (the approved table's Plan column as the goal, and "only what each thread asks" as the scope), the base `HEAD`, the commit the uncommitted fixes sit on, and the report folder `.review/fix/pr-<n>/`, emptied first so a round reads no earlier round's waves. Read `implement-change` step 9 and step 12 as this skill's steps 10 and 13; write no `outcome.md` and no `Suggestions:` line: non-blocking findings go to step 10. In a repository with `standards/review-rules.md`, `standards/decisions.md` or a `standard:` pointer in `standards/profile.yaml`, first rewrite `.review/standard.md` as `pr-review` step 2 does, so the reviewers read the current standard.

**Failures block the push.** Report them with output. Fix what your changes caused; for a failure that predates them, say so, show the evidence, and ask whether to proceed. A gate that did not run, wave.md's `not verified` stop, blocks it the same way: name the check and why, and ask; when the person goes on, step 12's question says which check did not run.

## 10. Review the Diff

Show `git diff` grouped by the thread each hunk answers, so the person can check the response against the request. Call out anything you changed that no comment asked for, and why.

Get explicit approval before committing. If the person wants changes, go back to step 8.

## 11. Commit

Commit the approved work through `/lasp-dev:commit`, which keeps `.review/` and the plan out — one commit per thread when the fixes are independent, a single commit when they are one coherent change. Use the repo's existing message style. Describe what changed, not that a reviewer asked for it.

When step 4's answer was **fix first, rebase before the push**, rebase the committed fixes onto `origin/<base>` now, after `git fetch origin <base>`. Conflicts stop the skill, as in step 4. Step 9's checks ran before the rebase: say so at step 12, and run step 9 again first when the person asks.

## 12. Push and Reply

**Draft every reply** now that the commits are final. Every planned thread, every follow-up and fixed row step 6 listed, every reply only row step 5 did not post, every answer, and every disagree and discuss decision not yet on GitHub gets a reply on its own thread, so the reviewer sees the response in context. A reply follows the Substance, Form and Attribution sections of `${CLAUDE_SKILL_DIR}/../pr-review/comment-style.md`, ends with the attribution line and its AI assistance level, and carries no severity line.

Its first line carries the decision when it is not yet on GitHub, so each thread gets one reply:

- **Agree, fixed**: `Agree, fixed in <sha>: <what changed and where>`, or, when the author's own Agree is already posted, `Fixed in <sha>: …`. Not "done." The sha on the first line is what tells a later run, and `work`, that the thread is answered.
- **Agree, reply only**, **Follow-up** and **Moved**: `Agree, reply only: <the response step 5 or the plan gave>`; `Agree, follow-up in <ticket or pull request>: …`, saying this pull request leaves it unchanged; or `Agree, moved to <sibling pull request or upstream repository>: …`, saying what it takes. When the author's own Agree is already posted, the reply opens with the response. The form on the first line is what tells a later run that the thread is answered, as `docs/contracts.md`'s "The agreed reply" names it; a bare `Agree` reads as still to fix.
- **Reopened**: one reply opening `Agree` that says the design is reopened (a `session-<pr>-<n>` reopen has no thread, so no reply); its row stays `agree` with `0` after.
- **Answer**: the first line is the answer itself, at the length the question deserves.
- **Disagree**: `Disagree, <the reason>` on the first line when not yet posted, then what you are not changing and why, without hedging into a fake apology. If it is a judgment call, say that and leave the thread open.
- **Discuss**: `Discuss` on the first line when not yet posted, then what is open, in the person's words.

A conversation-tab comment is not a thread and is read at the harvest, not here; reply only if the person asks.

**Ask once, for the push and the replies.** Show every reply in final form, with its thread's link, then ask, naming the branch, the commits and the count: **Push N commits to `<branch>` and post M replies** (Recommended); **Push only**, keeping the replies for the next run; **Edit the replies**; or **Stop here**, keeping the commits local. When the round has no new commits, the options are **Post M replies** (Recommended), **Edit the replies** or **Stop here**. Where the branch was rebased, at step 4 or step 11, the push is not a fast-forward: say so in the question, and push with `--force-with-lease`, which refuses if the remote moved since you fetched. **Never plain `--force`**, and never push to the base branch. Where the repository's instructions forbid an agent's push, the first option is to post the replies once the person has pushed, as `using-github`'s "Pushing" says. Silence or an ambiguous answer pushes and posts nothing.

If the push is rejected, the author pushed while you worked. Stop and let the person choose how to reconcile — do not rebase, merge, or force anything on your own, and post no reply that names a commit not on the remote.

After the push, mark each row whose fix is in it `fixed <sha>` in `## Dispositions`; post the replies, mark each posted decision `posted`, and drop a row's `fixed <sha>` once its fix reply is out. If a reply fails to post, report which thread and why, and keep the remaining replies going.

Do not resolve threads — that is the reviewer's call. Offer it only if the person asks.

## 13. Report

Give the pushed SHAs, the count of threads agreed and fixed, answered, moved, disagreed and left in discussion, which decisions stayed unposted, each with its thread's link, and that until each is on GitHub the record counts its thread unanswered, so `work` keeps routing to pr-fix and the next run raises it again, and any comment left unaddressed with the reason. Note whether the suite passed at the pushed commit, and whether the branch was rebased, at step 4 or before the push. After a reopen, say that the design goes back to `ticket-draft settle` and `implement-change` now, as step 7 says, and after a kept `ticket/` thread, that `ticket-draft settle` records its departure now. Otherwise the last line names the next command, `/lasp-dev:work`, which picks the next phase; when `work` invoked this skill, skip this offer: `work` asks.

Then release the working tree: `printf '{"session_id":"%s"}' "${CLAUDE_SESSION_ID}" | bash "${CLAUDE_PLUGIN_ROOT}/hooks/build-record.sh" release`. Release it the same way wherever the skill ends sooner, at a stop that hands the work back to the person or when they say to stop; a question that waits for their answer is not an end.

## Rules

- **The person decides what gets fixed and what is said.** No code change, push or reply happens without their say-so.
- **Never claim a fix you did not verify.** "Fixed in abc123" is a factual claim about tested code.
