---
name: pr-review
description: >
  Reviews a pull request and presents ranked findings at their lines; drafts comments when asked
  and posts one review only on your yes. Use when asked to "review this PR", "what's wrong with
  this PR", "review and post comments", "submit a PR review" or "publish my review". Not for
  answering a review (pr-fix) or a diff with no pull request (/code-review).
argument-hint: "[PR number or URL] [focus area]"
metadata:
  author: lasp-dev
  version: 6.14.0
---

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## When to run

At review, triggered by anyone: the author once the pull request is open, so the findings are
ready before a human reviewer arrives, a reviewer, or anyone else who wants a second reading.
Any pull request is reviewed, with or without a rules file (`standards/review-rules.md`), a
ticket or an Already checked block; the step that reads each says what its absence changes.

**The purpose is the review, not the post.** Presenting the findings is the default stopping
point; drafting comments waits on the person asking, and posting waits on their explicit yes. A
posted review's threads and their replies are what the revision harvests from the merged pull
request; a review kept local leaves nothing to harvest, and that is the person's choice.

Reviewers on the web answer in the threads and never need Claude Code.

## Options

| Option | Default |
|---|---|
| Pull request | A number or URL; otherwise the open pull request for the current branch |
| Focus area | None |
| Review document | None; one you supply is read as context, not a substitute |
| Comments | Not drafted until asked; "review and post comments" at invocation asks up front, and the post still waits on a yes |
| Verdict | Chosen with the post at step 4, with a recommendation; only `COMMENT` on your own pull request |

## The outline

Before the first read, print the outline, then open every later turn with the step it is on,
"Step 3 of 5: findings presented", so a person who comes back knows where the review stands:

```
pr-review on #<n>: 1 read · 2 review · 3 present the findings · 4 draft comments · 5 post
Stops for you: after 3 (draft comments?) and after 4 (post, and with which verdict?).
```

The progress file, `.review/pr-<n>-review-submission.md`, carries a `## Progress` checklist, one
box per step, checked as each finishes, so the next run, and `work`, read where this review
stands. See "Writes".

## GitHub Access

Reach GitHub as `${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md` sets out, and pass the
server to every agent this skill runs. A server that is not connected or fails is said as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out: the pull request's diff and threads are
what is lost, and the review stops until the person chooses `gh`. On `gh`, step 1.3 reads the earlier reviews as
"Re-reviews" says, and a review with earlier findings is presented but not posted.

The shared corpus is `${CLAUDE_PLUGIN_ROOT}/standards/` and the standard, `<standard>`, the directory
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints, which a repository it exits 1 for, ending "the repository has no standard",
has none of, and any other exit 1 is a failed read; a bare `standards/` path means this repository's own. A read of the shared corpus that fails is an error: say so with the path, and
never read a copy from anywhere else or invent a term or a decision to fill the gap.

## Writes

The reviewer agent writes `.review/pr-<n>-review.md`, the path step 2 names for it, so nothing
lands outside the gitignored `.review/`.

`.review/pr-<n>-review-submission.md` is written at step 3, with the Write tool
(`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`, "Writing a file") and the steps already
done checked, and kept current at every later step. It opens with two lines that `scripts/next_phase.py`
reads, so `work` does not send the person back to a review they already decided on:

```
Head: <full sha>
Posting: undecided
```

`Head:` is the head the review is on. `Posting:` is the person's choice, and this is the one
place its values are set: `undecided` while they have not chosen, including when they say **Stop
here for now** or give no clear yes to post; `declined` when they say **Keep it local, don't
post**, or when the review goes to `.review/pr-<n>-review-post.md` for lack of write access; `posted <review
URL>` once step 5 posts. Then the `## Progress` checklist, then the findings as step 3 presented
them, and from step 4 every comment's final text, anchor and disposition and the summary, marked
as an unposted draft. After the post it records what was posted, keeping its first two lines. A
new head starts a new file, as "Re-reviews" says.

On the person's yes, one review on the pull request with the verdict they chose: a summary body
and one inline comment per finding. Where the server has no write access, the review goes to
`.review/pr-<n>-review-post.md`, each comment with its path and line, for the person to post.

The hook keeps `.review/` ignored, through `.git/info/exclude` where the repository's
`.gitignore` does not. Nothing is committed.

## Steps

### 1. Read

1. **Note whether `standards/review-rules.md`, `standards/decisions.md` and a `standard:`
   pointer in `standards/profile.yaml` exist**; every later step that names the rules file
   applies only when it does, and one that names the standard when any does. A repository with
   a pointer has the standard of the repository it names, its rules file included, which
   `standard_file.sh` fetches at step 2.
   Without a rules file, no finding cites a rule, and the summary says the repository has no rules
   file.
2. **Check whether the pull request is merged.** If it is, stop: code that already shipped is
   not reviewed here.
3. **Read the earlier reviews, before spending anything**: on `gh`, as "Re-reviews" says;
   otherwise one `pr-reader` call in `state` mode, given the repository and the pull request,
   for its posted reviews and their `reviewed:` shas against its head, and
   `.review/pr-<n>-review-submission.md` for a local one. When either exists, this run is a
   re-review: say so in one line, naming what was found and the head it covered, and go on as
   "Re-reviews" says. On the server, reviews, threads and comments are read only through that
   call, so the raw thread output stays out of the session: the session never calls
   `pull_request_read` with `get_reviews`, `get_review_comments` or `get_comments`. Its own
   `pull_request_read` calls are `get`, for the head and whether the pull request is merged, at
   step 1.2 and step 5, and `get_diff` when step 5 re-anchors.
4. **Find the ticket**: the key on the `ticket:` row `pr-reader` printed, else in the branch
   name or title, matched by the profile's `ticket.pattern` in any letter case, upper-cased unless
   the pattern matches it as written
   (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field ticket.pattern`).
   Its text is `.review/context/<key>.md` when that exists, its first line read on its own
   first: a page that opens with a `Controlled:` line is held as `${CLAUDE_PLUGIN_ROOT}/skills/writing/references/short.md`, "Controlled content" says, and no reviewer
   gets its text until the person clears it. Otherwise it is one `source-reader` with
   the task `ticket <key>`; with no Atlassian server, or a read that fails, say so as `servers.md`
   sets out, the ticket's text being what is lost, and ask once for the text. A ticket the block
   lists as `Withheld:` is asked about as its question says, never pasted; on the person's yes,
   run the task again with a `Cleared: <key>` line, and until they clear it the review goes on
   with no ticket text. With no ticket text,
   the reviewer raises no `ticket/` finding. A pull request with no ticket (the row reads `none`
   or `Ticket: none …`, and no key in the branch or title) is reviewed as it is: the summary says
   it has no ticket, so the code was checked only against itself, and the closing line offers
   `/lasp-dev:ticket-draft <pull request>`. One opened by a dependency bot (Dependabot,
   pre-commit autoupdate) needs no ticket; the summary says so once and offers nothing.

Step 3 writes `.review/pr-<n>-review-submission.md`, zero findings included, unless "Re-reviews"
keeps an existing file: a run abandoned before then leaves nothing that reads as a review.

### 2. Review

1. **Run the reviewer**, on every review, whatever the size of the change or the delta: the
   findings are the `github-pr-reviewer` agent's, and the session never writes findings from its
   own reading of the diff in their place. Invoke the agent with the pull request, the server,
   the path of `${CLAUDE_SKILL_DIR}/comment-style.md`, the absolute path of
   `.review/pr-<n>-review.md` for its review file, and these inputs; its own file says what it
   does with each:
   - the standard. With a rules file, `standards/decisions.md` or a pointer, the
     absolute path of `.review/standard.md`, written first, afresh, from the repository's top
     level:
     `bash "${CLAUDE_SKILL_DIR}/../../scripts/standard_file.sh" > .review/standard.md.tmp && mv
     .review/standard.md.tmp .review/standard.md`, so a failure keeps the last good file; say the
     script's note on stderr, when it prints one, in one line. Note
     `git log -1 --format=%h -- :/standards/` for the summary's `standards:` line, `none` when no
     commit has touched `standards/`, followed by ` + uncommitted` when
     `git status --porcelain -- :/standards/review-rules.md :/standards/decisions.md :/standards/terminology.md :/standards/agent-guidance.md :/standards/data-conventions.md` prints
     anything: the review then ran on a rule or decision nobody has committed, such as one being
     tried before it is proposed, and the person is told so in one line. The suffix covers this
     repository's files only, not the plugin's. With a pointer, the `standards:` line is the
     named repository's commit that `.review/standard/source` records, with the suffix when the
     pointer itself is uncommitted (`git status --porcelain -- :/standards/profile.yaml`). For `<owner>/<repo>@local`, a local checkout, it is that
     checkout's `git -C "$(git config lasp-dev.standard)" log -1 --format=%h -- standards/`
     followed by ` + uncommitted`, whatever its state, or `none + uncommitted` when that prints
     nothing, a standard never committed; for `<owner>/<repo>@none` it is `none`,
     and the summary's first sentence says `<owner>/<repo>`'s standard was not read. A standard
     that cannot be fetched stops the review, naming why; the person may then choose to go on
     with the contract alone, `git config lasp-dev.standard none`, which lasts until
     `git config --unset lasp-dev.standard`. With none of the three,
     the path of the contract, `${CLAUDE_PLUGIN_ROOT}/standards/review-contract.md`, alone; the
     `standards:` line reads `none`;
   - on a delta, the reviewed sha, fetched first with `git fetch origin <sha>` when
     `git cat-file -e <sha>` fails, and whether the base moved since;
   - for a part of a ticket in several pull requests, the criteria its `Claims:` line names and
     the pull request's base branch;
   - the ticket's text, or that there is none, and whether the body has an Already checked block;
   - the keys the build declined, every key that already has a thread with its verdict and,
     under a Disagree, its reason, and each uncited thread's headline;
   - the provisional decisions the body marks `Provisional:` and the ticket's Open Questions
     answered for now;
   - the focus area, and a review document the person supplied;
   - when the diff touches tests, the path `${CLAUDE_SKILL_DIR}/../test-suite-review/checklist.md`.
2. **Map its findings.** Each keeps its severity and `path:line`; a finding with no changed line
   is anchored to the file it most concerns, at file level, and one about the pull request as a
   whole (its ticket, its scope) to the file that shows it. A finding without a key posts without
   the `<details><summary>Standard</summary>` block. Rank and cap as the contract's "Severity"
   says; a question is kept only when the code, the ticket and both `decisions.md` files do not
   answer it and no provisional decision already raises it. On a pull request with no Already
   checked block, a design choice the body leaves out is a question, not a must-fix.
3. **Deduplicate** by finding key: against the build's declines when the body has an Already
   checked block, and against every thread already on this pull request. A cited finding matches
   by its full key, which names the file and symbol; line numbers move between heads and are
   never compared, and a key that already has a thread is not raised again. An uncited finding is
   dropped when the reviewer listed it under Existing Review Comments Noted as repeating a
   thread; the session never matches headlines as text.

A review always runs at full depth: the depth levels govern a build and `pr-fix`'s rounds, never
a review. Step 2 is skipped only where "Re-reviews" goes on from a local review of the current
head, presenting it again or deciding on posting.

### 3. Present the findings — default stop

Present the review in the session, grouped by severity, most severe first: must fix, should fix,
suggestions, questions. Each finding gets its headline, a sentence or two on what is wrong and
why it matters, the rule or decision it cites by ID and title, its proposed change, and its
location as a link the person can open,
`[tokens.py:48](src/auth/tokens.py#L48)`, with every further location it names. Say what
deduplication left out and why, so the person can restore one, and point to
`.review/pr-<n>-review.md` for the reviewer's full detail. When nothing is a must fix or a
should fix, say so plainly. Write the submission file: its first two lines, the `## Progress`
checklist and the findings, or a line saying there are none.

Then **stop** and ask: **Draft comments** (step 4), recommended when a must fix or should fix is
among the findings; **Keep it local, don't post** (the skill ends), recommended otherwise; or
**Stop here for now** (the next run, or `work`, asks again). When the person already asked for
comments at invocation, go on to step 4 without asking. Discuss any finding the person asks
about, but draft no comment until they choose.

### 4. Draft comments, then the post — stop

Shape each finding into a comment as "The review" sets out, and draft the summary. Show each
comment once, in full as it would post, then the working set as a compact table, then the
summary exactly as it would post:

```
#   Severity    Location                      Disposition   Headline
1   must fix    src/auth/tokens.py:48         include       Expired tokens return None but caller assumes str
2   should fix  src/api/routes.py:112-130     include       Unbounded query in the list endpoint
3   suggestion  src/api/routes.py (file)      include       Test coverage gap for the refresh path
```

Take free-form direction and act on it: drop and restore comments, rewrite a body, change a
severity, re-anchor, split a broad finding, merge overlapping ones, add a comment, or explain the
reasoning behind one. Read the code at a location before writing a new comment about it. After
each round, show the comments that changed and the updated table, and write the submission file.

Then **stop** and ask one question that is both the verdict and the post's yes, naming what
posts: "Post N comments + 1 summary on #<n> in <owner>/<repo>?" Every comment and the summary are
shown with it as `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`'s "What does not change"
says. For a review too long to show whole, the table and the summary stay in the message and the
comments are in the file it names, `.review/pr-<n>-review-submission.md`, which holds every
comment's final text. The options:

- **Post as <the recommended verdict>** (Recommended): `REQUEST_CHANGES` when any included comment
  is a must fix, `APPROVE` when nothing included is a must fix or a should fix, `COMMENT`
  otherwise.
- **Post as <the other verdict that fits>**: `COMMENT` beside `REQUEST_CHANGES` or `APPROVE`,
  `REQUEST_CHANGES` beside `COMMENT`. A third named in "Other" is taken as given.
- **Keep it local, don't post**: the drafted comments stay in the file for the person to post by
  hand.
- **Stop here for now**.

GitHub refuses `REQUEST_CHANGES` and `APPROVE` on the person's own pull request: there, only
**Post as COMMENT** is offered, and the question says why. A post option is the yes to exactly
the comments and summary that message shows or links; silence, an ambiguous reply or an
unrelated one posts nothing, and a change to the draft after the question asks it again.

### 5. Post — on step 4's yes

**Post** as one review, never a series of standalone comments, with zero comments too, so the
head is marked reviewed. Re-read the pull request first: if the head moved since step 1, say so,
re-anchor against the new diff, and ask step 4's question again. Create a pending review on the
head sha, add each comment (`LINE` on a changed line, `FILE` otherwise), and submit it with the
chosen verdict. The `get_me` login goes in each attribution line. A comment GitHub rejects,
usually for its anchor, is named with the reason and offered re-anchored, at file level, or
dropped, and the rest go on. If submitting fails after comments were added, say that a pending
review exists and offer to retry or delete it. Then record the post in the submission file, the
review's URL, `https://github.com/<owner>/<repo>/pull/<n>#pullrequestreview-<id>`, taken from a
`pr-reader` state call after the submit, whose rows name the new findings review's id.

The last line says who acts next: reviewers answering on GitHub, or the author, who reads the
whole diff, leaves a comment of their own on GitHub on each thing to change, and answers with
`/lasp-dev:pr-fix`, which walks the author's own comments with everyone's, ahead of the
findings; for a pull request with no ticket, it also offers
`/lasp-dev:ticket-draft`. On a review kept local, it says the findings are in
`.review/pr-<n>-review-submission.md` and leave nothing to harvest. When `work` invoked this
skill, skip these offers: `work` asks.

## Re-reviews

Read `${CLAUDE_SKILL_DIR}/re-review.md` on `gh` at step 1.3, and whenever step 1.3 finds an
earlier review.

## Whose reply counts

A finding's verdict is read from the replies in its thread from people, bots excluded. **The
pull request's author decides**: their first Agree, or Disagree with the reason its severity
needs, is the verdict, whenever it comes and whoever replied before them. Until the author
replies, the first such reply from anyone stands; the person who ran `pr-review` counts like
anyone else, since the findings are the agent's, and the author's self-review is the intended
first use. After someone else's Agree or Disagree, the author's Discuss, must-fix or should-fix
Disagree with no reason, or reply in their own words reopens the finding, as the same reply would
open it first. A reply's first line is read leniently, case and punctuation aside, `Agreed` and
`Disagreed` included, and starts with one of three words:

- `Agree` — the finding stands; from the author, it will be acted on, and a suggestion is taken.
- `Disagree, <reason>` — the finding is wrong or not worth it. A must-fix or should-fix
  disagreement without a reason leaves the finding open, as Discuss does, until the thread gives
  one; a suggestion needs none.
- `Discuss` — the finding is open until a later `Agree` or `Disagree` in the thread settles it.

A question takes any answer; its first reply is the answer. A reply in a person's own words, with
none of the three words, is judged: `pr-reader` reads what it says and the record keeps the
verdict it judged, marked `judged` with a one-line basis, so "Good catch, fix this" is an
`Agree`. Only replies with no word, after the last word in the thread, are judged, so a judgment
never overrides a later word, and a later word settles the thread whatever was judged before it;
the author's judged reply decides as their word would. A reply the judge cannot read leaves the
finding open, as Discuss does, reported as unparsed until a later reply settles it. A reply's
attribution line is no part of its reason. A reaction or a resolved thread is never a verdict.
This section is implemented by `scripts/record.py` with `pr-reader`'s judgments and tested by
`tests/test_record.py`, on the fixtures in `tests/fixtures/`.

**Contested.** Before the author has replied, a second person's verdict that differs from the
first contests the finding, and the author's next Agree or Disagree settles it. The author's
reply is never a rival, their Discuss included: their Agree or Disagree settles it, and a word
after that contests nothing. The record keeps the settled verdict, `contested: true` and both
original lines. Taking the later reply, the stronger wording or the more senior person does not
settle it. A must-fix or should-fix `Disagree` with no
reason neither contests nor settles.

**The author's own comments.** A thread the author opens on their own pull request, in their own
words, is a review comment like anyone's: the author reviewing their own diff is a reviewer. It
is `unanswered` until the author answers it, with a word, in their own words or through
`pr-fix`; one that only tells reviewers something is answered `Agree, reply only: a note for
reviewers, no change`.

## The review

One review per post, whatever the number of findings, with the verdict the person chose at
step 4. Every comment follows `${CLAUDE_SKILL_DIR}/comment-style.md`. The summary is exactly
this, the four lines between `standards:` and the attribution each one line in the posted text.
The `standards:` line ends ` + uncommitted` when step 2.1 found the rules file or decisions
uncommitted. For a pull request whose body has no Already checked block, one line follows `standards:`:
`Not built through implement-change: there are no build declines to skip.`

```
## Review
reviewed: <full sha>
standards: <sha, or none>

A review against this repository's rules.
Reply under each comment: **Agree**, **Disagree** with your reason, or **Discuss**; your own words work too. On a must fix or should fix, a Disagree without a reason leaves the thread open. The pull request author's reply decides, and until they reply the first reply stands, unless someone else answers differently. A question takes any answer.
You can also answer with `/lasp-dev:pr-fix` in Claude Code, which implements the threads the author agrees with. When this pull request merges, the replies are collected to measure which review rules hold up.
<n> comments: <n> must fix before merge · <n> should fix · <n> suggestions · <n> questions · <n> left out for a decline's reason

🤖 _AI-assisted comment, posted by @<github-login>. AI assistance level: 5/5 (not read by a person)._
```

With the profile's `posted_text` reading `plain`
(`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field posted_text`), for a
public repository that should not carry the workflow's text, the summary drops the line naming
`/lasp-dev:pr-fix` and the "Not built through implement-change" line, and keeps the rest:
the record reads the replies the reply line asks for. `scripts/record.py` reads the first three
lines and the attribution line.

When `.review/standard.md` was written from a branch other than the pull request's base, the
summary's first sentence names that branch; the `standards:` line's form does not change, since
`scripts/record.py` parses it.

Each attribution line, the summary's and every comment's, carries the level `comment-style.md`'s
"AI assistance level" sets; a level the person names while the draft is shown changes the number
and its meaning on the summary's line and on those of the comments it concerns.

With no rules file, `standards/decisions.md` or pointer, `standards: none`, and "A review against
this repository's rules" becomes "A review under the shared review contract; this repository has
no rules file". With decisions and no rules file, it becomes "A review against this repository's
decisions under the shared review contract; it has no rules yet". With a pointer, "this
repository's rules" names the repository that holds the standard: "A review against the rules of
<owner>/<repo>". A delta names
the commit it is against in its first sentence; the `## Review` line stays exactly that, since
`scripts/record.py` matches it whole.

Each inline comment opens with its severity line from `comment-style.md` (**Must fix before
merge**, **Should fix**, **Suggestion** or **Question**), then, for a finding that cites a rule
or a decision, what it cites, then the body, which follows that file's Substance section, then
one line `Proposed: <size>, <the change in one sentence>`, then
the keys, collapsed, then the attribution line. The Proposed line is what `pr-fix` implements
on **Agree**, so it is concrete: a wording, a test case, a signature, never "consider". It
holds even where `comment-style.md` would leave the fix to the author. A question carries no
Proposed line. The size is one of `one line`, `a few lines`, `an hour` or `changes the plan`,
the words every skill uses when it offers a change. What a finding cites is the reviewer's Cites
line: a rule's ID, its title and its wording quoted, or a decision's citation as its key gives
it, its title and the sentence of it the finding rests on, quoted, so the author reads why the
finding was raised before what it says.

```
**Should fix** — a predicate raises on a part it does not know

Rule R-003, *<the rule's title>*:
> <the rule's wording>

What is wrong and why it matters.

Proposed: a few lines, return `False` for a part outside the inventory instead of raising `ValueError`.

<details><summary>Standard</summary>

key: `R-003/src/widgets/inventory.py::is_known_part`
</details>

🤖 _AI-assisted comment, posted by @<github-login>. AI assistance level: 5/5 (not read by a person)._
```

An uncited finding is the same comment without the rule and the `<details>` block.

No `F1`-style handle appears anywhere a person reads: the thread is the identifier.

## Never

Post without the person's explicit yes, or choose a verdict they did not. Draft comments before
the person asks for them. Resolve a thread, apply a label, merge, commit or push. Post a second
full set of findings. Adjudicate a finding, including a contested one, and including when a
reply says "do whatever you think": an agent that grades its own review produces a record that
measures nothing. Reading what a person's reply means is not adjudicating; deciding the finding
is. Write a verdict from a reply that is not there, or post a reply the person
did not choose.
