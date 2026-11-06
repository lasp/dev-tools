---
name: ticket-draft
description: >
  Drafts, refines and files a ticket in the team's format, a Jira ticket or a GitHub issue,
  placed among existing work, from a description, a ticket or a pull request with none; can brief
  you on the code first, fold in later answers, or reformat a ticket to the current format; files
  only on your yes. Use when asked to "open a GitHub issue for", "open an issue on this repo",
  "write a ticket for", "file a ticket", "create a Jira ticket", "log a bug", "refine this ticket",
  "is this ticket ready", "what is this ticket missing" or "groom this ticket". Not for a complaint
  about a lasp-dev skill or agent, even one asked for as an issue on the plugin, which is
  skill-feedback's.
argument-hint: "[investigate | settle | reformat] <ticket key | issue #n | description | pull request> [thread id]"
metadata:
  author: lasp-dev
  version: 1.11.0
---

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## When to run

When someone describes a change they want ticketed, or brings an existing ticket to refine;
with the group in the room for an epic or a ticket at the group-session threshold, before
`/lasp-dev:implement-change` plans it. A New ticket needs only a title and a few sentences,
as the Ticket Management page says; this skill vets it in the filed status, before a ticket
writer approves it and moves it to the approved status (the profile's `jira.roles`, "Writes"), and is
not a requirement for filing one.

**Always start from a person's prompt** or a ticket key they name. Never generate tickets from
the repository's state, a TODO sweep or a roadmap on its own initiative.

## Options

| Option | Default |
|---|---|
| Mode | `draft`; `investigate` adds a briefing on the code and the design choices, and the person's questions, before the draft; `settle` folds answers that arrived since the draft, from the estimation meeting, a comment or a pull request thread, into a drafted ticket, and records a departure the work keeps as a comment; `reformat` rewrites a ticket that already holds its requirements in the current format, with no search or investigation |
| Source | A Jira ticket key, or on a GitHub tracker an issue's number, `#12`, a description of the change, a markdown file whose text is the prompt, or a pull request number or URL; asked for when none is given. `work` names a slug whose page is under `.review/context/` for a ticket not filed yet, and `pr-fix` passes `settle <key> <thread id>` |

## Reads

`${CLAUDE_PLUGIN_ROOT}/standards/ticket-format.md` for the format; `using-jira` for its Jira markup, the fields and the estimate scheme; `using-confluence` for the year
plan. The shared `<standard>/terminology.md` and `<standard>/decisions.md`, `<standard>`
being the directory `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints, and the repository's own `standards/` when
it has one; a failed read names the path. The titles under `<standard>/context/`: its README
and each entry's first heading, not the bodies. When `--standard` exits 1 ending "the repository has no
standard", none of its files are read; any other exit 1 is a refusal, shown to the person before going on without them. Jira, Confluence and GitHub only through `source-reader`, or `pr-reader` for a pull
request source, never directly, passing `gh` when the person has said so in this session. The code through `ticket-investigator`; in the
session, only the lines a fact rests on and what an `investigate` answer needs. A source that
warns it is controlled, whether the person gave it or a `source-reader` block lists it as
`Withheld:`, follows "Controlled content" in `${CLAUDE_SKILL_DIR}/../writing/references/short.md`:
ask the person before reading on, never ask them to paste its text, and pass their yes to
`source-reader` as a `Cleared:` line.

A server stops the draft only where the source needs it: Atlassian for an existing ticket and in
`settle`, as `using-jira`'s "When the server cannot be reached" says; GitHub for a pull request
source, as `using-github`'s "When the server cannot be reached" says. Every other read goes on
without it: the Jira or the GitHub half of the search, the year plan, a page an answer would cite.
Say so once per server as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the reads
skipped being what is lost. Placement says `not searched: <server> not connected` or
`not searched: <server> failed: <error verbatim>` for each read skipped, and the hand-off says to
run the draft again before the ticket is filed, since the duplicate check did not run.

## Writes

`.review/context/<ticket>.md`, where `<ticket>` is the key or, for a new ticket, a short slug, a
letter then letters, digits, `.`, `_` or `-`; and `.review/context.md`, a copy of the most recent
for the session-start line and `work`, except for a pull request source, whose page gets no copy.
`pr-create` reads the page's What changed section. The page's first line is `# <ticket> ·
<summary>`, from which `hooks/where.sh` reads the key only as its first word, or the slug when it
opens with no key, so nothing else comes before it; a page written from a cleared controlled item
opens with its `Controlled:` line, and the heading follows it. Sections in this order:

0. **Investigation**, only when that mode ran: the briefing, then each question the person asked
   and its answer, with what was read, one line each.
1. **Placement.** Overlaps, each with a verdict of same, subset, superset or adjacent · the
   epic · blocked by and blocks · ripple, each a one-line scope question naming the consuming
   repository · the year-plan month, or none. Then each investigator's report as returned.
2. **Open questions**, as written, each with its recommendation and evidence.
3. **Estimate**, with its reasoning. It stays in `.review/`.
4. **The ticket**: the field block and the description. For an existing ticket, the revised
   description and a list of field changes.
5. **Actions proposed**: tickets to link, to merge as duplicates or to file as follow-ups, and why
   each field the block leaves none or proposes is so. Each is an item of step 7's write plan.
6. **What changed from the original ticket**, from step 7: added, removed and reworded, one line
   each, then the decisions and assumptions taken in session, one line each.
7. **For planning**: the implementation leads the ticket leaves out, such as the function to
   change, a library, a data source or a test pattern to follow, each with its `file:line`, for
   `implement-change`'s planner. None of them binds the plan.

Beside the page, two plain-text files. `.review/context/<ticket>.original.txt` holds the text
before this session touched it, written in step 1 before anything else, unless step 1 stops on a
warning. `<ticket>.jira.txt` holds
section 4 laid out as `using-jira`'s "Copy-paste output" sets: its `Comment to post` carries
`<ticket>.original.txt`'s text with its markup put right as that section says, signed with the `ticket` block's reporter and created date, or
for a new ticket the person and today; its `Session comment` comes from What changed.

In the tracker, only at step 8 and only the items of the write plan the person approved at step 7, as
`using-jira`'s "Writing to Jira" and `${CLAUDE_SKILL_DIR}/../using-jira/write-plan.md` set out.
The filed and the approved status are the profile's: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py"
--defaults --field jira.roles` prints them, and an error from it, or `not yet recorded`, is a stop
for the status move, as `write-plan.md` says.
Each text sent is kept under `.review/context/<ticket>.send/`, as shown (`.txt`) and as sent
(`.md`), with `stored.txt`, the description as read back, and each item's outcome in
`.review/context/<ticket>.writes.md`. Whatever the plan did not write stays in
`<ticket>.jira.txt` to paste. On a GitHub tracker the paste file is `<ticket>.issue.md` and the
plan is GitHub's, as `${CLAUDE_SKILL_DIR}/github.md` says.

## How each turn reads

A heading per block, bullets and tables, each line one fact, no paragraph over three lines. Say
only what bears on the ticket: a rule the change must meet goes under Technical Requirements,
never in a preamble. Nothing comes before step 1's opening block.

## Steps

On a GitHub tracker, where `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --defaults --field
issue_tracker.kind` prints `github`, read `${CLAUDE_SKILL_DIR}/github.md` first, which says what
changes in every step below and in the files.

A pull request as the source, or a slug whose page exists under `.review/context/`, which `work`
names for a page with no key yet: read `${CLAUDE_SKILL_DIR}/sources.md` first, which says what
changes. `settle` mode is `${CLAUDE_SKILL_DIR}/settle.md` in place of these steps, and `reformat`
mode `${CLAUDE_SKILL_DIR}/reformat.md`.

1. **Read the source**, a file's first line on its own first. If it warns it is controlled, or
   the block lists it as `Withheld:`, stop at the warning and ask as `${CLAUDE_PLUGIN_ROOT}/skills/writing/references/short.md`, "Controlled content" says, naming only the
   item, where it sits and the warning, quoted, and describing nothing of it, not even where you stopped;
   write no `<ticket>.original.txt`, and no context page, until the person clears it; one written after that opens with the `Controlled:` line, and the `Comment to post`
   that carries it names the item and its warning. For an existing ticket, run one `source-reader`
   with the task `ticket <key>`, and write the description it returns, verbatim, to
   `.review/context/<ticket>.original.txt` with the Write tool
   (`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`, "Writing a file"); for a new ticket, write the person's prompt there
   verbatim, and for a markdown file its text. When the block's `Original request comment:` is
   `yes`, the ticket was settled before: it gets no `Comment to post`, since that comment is the
   baseline, and `<ticket>.original.txt` holds the settled text this session replaces. When
   comments cannot be read, ask whether it has one. On `Markup: damaged`, add one line after the
   opening block naming the lines that may be run together in Jira, to check there.

   Then show the opening block, and nothing before it:

   ```
   ## PROJ-43 · Write each exported inventory with its generation metadata
   Task · New · no estimate · epic: none

   **The ticket says**
   - Some metadata keys are common to every exported inventory but their values change per file
   - Generate the values (creation time, the source file, the row count) and add them to what
     the inventory writer writes

   **Goal I am searching for:** every exported inventory carries its generation metadata, filled
   in by the writer, without a caller supplying it.

   **Where it likely lands** (from the ticket and this repository; the investigators confirm it)
   | Repository   | Pull request      | Why                                          |
   | widgets      | the change        | the inventory writer is here                 |
   | widgets-cli  | none expected     | it calls the writer (unconfirmed)            |

   **Looks missing**
   - No acceptance criteria
   ```

   For a new ticket the heading is the slug and the first block is **The request says**. **The
   ticket says** is two to four bullets in the ticket's own terms. **Where it likely lands**
   names each repository the change reaches and whether it needs a pull request there, a
   follow-up or none, from the ticket, this repository and the profile's `downstream` list.
   **Looks missing** lists at most three gaps against `ticket-format.md`, or is left out. Go
   straight on to step 2: the goal is confirmed with the placement. Only a source too thin to
   state a goal, such as a sentence that names no behavior, is asked for one first. An existing
   ticket that is already detailed and not in the current format is asked first, before any
   reader runs. It is already detailed when its status line opens `ticket-draft: drafted`, or
   when it says what the work must accomplish and how to tell it is done, as requirements and
   criteria or what stands for them, whoever wrote it and whatever its headings. It is in the
   current format when its sections are `ticket-format.md`'s, Motivation first, with no Context, Where
   it fits or Not this ticket. Say so in one line, "This ticket is already detailed: reformat it,
   or draft it again?", with what it holds, and ask: **Reformat it** (Recommended), which goes on as
   `${CLAUDE_SKILL_DIR}/reformat.md` from its step 2, or **Draft it again**, which goes on to step
   2 here. A ticket with only a title and a few sentences goes straight on. A ticket whose status
   line opens `ticket-draft: follow-up from` is a follow-up (`using-jira`, "A follow-up ticket"):
   it is drafted in full, and its `Comment to post` first line ends `(follow-up written by
   ticket-draft)`.
2. **Launch the readers**, all in one message, after one line saying what runs and that it takes
   a few minutes, such as "Reading up to 200 PROJ tickets, the year plan and 3 repositories; a
   few minutes." First expand the goal's terms with the synonyms in `terminology.md`, so the
   search finds tickets written in the other words for the same thing. Then:
   - one `source-reader` running `search`, given the goal, the synonyms, the repository and
     `Jira: <project>`, the profile's `ticket.project`
     (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field ticket.project`);
   - one `source-reader` running `plan` for the current month and the next two;
   - fresh `ticket-investigator` agents, one for this repository and one for each repository the
     consumers list (the list `${CLAUDE_PLUGIN_ROOT}/skills/downstream/SKILL.md`'s `check` step 2
     names) that is cloned beside this one
     (`$(git rev-parse --show-toplevel)/../<repo>`). Each gets its repository's path, the goal,
     the claims the source makes about that repository and the synonyms. A repository not
     cloned beside is named in Placement as unread.

   Collect every report before step 3.
3. **Place it, size it, and ask how to go on.**
   - Re-judge every `same` and `superset` from the quoted criteria: those two say the work is
     already ticketed, so they are not left to the reader.
   - Dependencies, from the goal and the investigators' Callers lines; the epic; the year-plan
     month, which sets the due date, saying so when its milestone names the person drafting, by
     name or initials.
   - A rough size on the team's scale, from the search block's `References:` and the reports'
     Touches, called provisional until step 5's estimate.

   Show **Placement**: the overlaps with their verdicts and quoted criteria, the epic, the
   dependencies, the year-plan month, and each repository the change reaches with its report's
   Touches in a line, the full reports going to the context page. Then the rough size, and
   whether it calls for a group ticket session: an estimate of 5 or more, or an epic. Then one
   widget, two questions:
   - **The goal** searched for: **Right** (Recommended), or **Correct it**, which runs step 2
     again on the corrected goal.
   - **How to go on**, the options that apply, the recommended one first:
     - **Refine <ticket key> instead**, recommended on an upheld `same` or `superset`: step 1
       again with that key, this source's text added as the person's words, then step 4 with the
       reports reused and that ticket left out of the overlaps. When the source is itself a
       ticket, Actions proposed lists merging it into <ticket key>, as `using-jira`'s "Merging
       two tickets" sets out: this option keeps <ticket key>, and **Draft this ticket** on an
       upheld `same` keeps the source and merges <ticket key> into it. The option's description
       names the ticket that section recommends keeping.
     - **Split**, recommended when the reports show two goals or the rough size is at or above
       an estimate of 8, at which a ticket is split before work starts, proposes the
       pieces, each a goal in one line, in the order they must land and which can go in
       parallel; on a yes, each is drafted from step 4 with the reports reused, through its own
       step 7, and step 7's write plan for the last piece holds every piece's items. The first
       piece to land keeps the source's key or slug and its `.original.txt`; each other piece
       gets its own slug and a copy of that `.original.txt`, the text it was split from, and is
       created with the source's epic and a link to it: `blocks` from a piece that must land
       first, `relates to` between pieces that go in parallel. Each piece lists the others under
       Related Out of Scope Tickets. An epic is split the same way, naming the children that
       already exist as open tickets.
     - **Draft this ticket**, recommended otherwise.
     - **Stop**, which writes nothing beyond `<ticket>.original.txt`.

   **In `investigate` mode**, or when the person asks a question here, brief them between
   Placement and the widget, in at most six lines: what the code does now, in one line; who
   calls it, in one line; and the design choices the ticket must make, such as a contract, where
   the code lives, the failure behavior or the effect downstream, one line each with the two or
   three options the code shows and the one recommended, with its evidence. Nothing more: the
   person asks for the detail they want. Answer from the code, the shared corpus, and Confluence
   and Jira through `source-reader`, saying what was read; a question about another repository
   may go to one `ticket-investigator`. An answer none of them holds is said to be missing and
   offered as an Open Question. Each answer ends `Say "next" to choose how to go on.`, and the
   widget waits for it. A design choice the person makes goes into Technical Requirements with
   its source, other conclusions into Motivation, The code today or For planning.
4. **Find the gaps**: missing requirements, criteria nobody could check, inconsistencies with
   existing tickets or `decisions.md`, incompatibilities with the code as it is, side effects on
   callers and downstream repositories, and a source that says what to do but not why. Every "does
   not hold" and "cannot tell" in an investigator's Claims is one, every "Beyond the goal" line a
   scope gap (does the goal need it, or is it out of scope), as is every ripple candidate in
   Placement, and every reader's `Questions:` line this session cannot answer from what it holds.
   Each becomes an Open Question in the draft with a recommended answer and its evidence (a
   `file:line`, a quoted criterion, a page), or none and why. A missing why has none, since the why
   is the person's, and step 6 offers it no For now. **Never fill a gap with a requirement the
   person did not give**: a recommendation is not an answer until the person takes it. Raise only
   what changes what the ticket requires or decides: the goal, the scope, an acceptance criterion, a
   contract or a design choice. A question whose answer changes only how the code is written is the
   planner's, and one the reports already answer is not raised.
   - **Design choices**, as `ticket-format.md` defines them, come from the source or the person and go
     into Technical Requirements with their source, whatever the investigation thinks of them.
     A finding against one is a question ("<the choice> conflicts with <finding>; keep it,
     change it, or leave it to planning?"), never a silent rewrite. A design-level question the
     investigation raises becomes a design choice only when the person answers it. Every other
     how goes to For planning.
   - **Conflicting sources.** When the ticket and a page or ticket it cites disagree, the draft
     picks no side, even for the newer text or the same author's: the question's options name
     each source's position, and only the person settles it.
   - **Re-check what the ticket rests on.** Read again in the code each fact that contradicts the
     source or goes under `Missing:`, and give it its `file:line` on the context page. A fact no
     line confirms ends `(unconfirmed)` in the ticket; two reports that disagree on it are a
     question.
   - **Test the criteria** the source gives. The cheat test: describe the laziest change that
     passes every criterion; if it is unacceptable, raise "the laziest passing change is <it>;
     add a criterion?". The over-constraint test: a criterion a good, unanticipated implementation
     would fail is a route; raise "criterion <n> is a route; keep it as a design choice, or cut it
     to For planning?". A cheatable criterion is fixed by a sharper observable outcome, never a
     prescribed mechanism, and neither test changes a criterion itself.
5. **Write the draft and show it**, in the format `ticket-format.md` sets, cut as its "Readers and
   length" says, and in Jira's markup as `using-jira`'s "The description format" renders it. Where each part comes from:
   - The Component/s field from the search block's `Components:` line, the list's name nearest
     the change, never one outside it.
   - Every fact an existing ticket holds lands in one place: a section, a field or link, or For
     planning. A neighbor its text names becomes an issue link: `depends on` a ticket it builds
     on or follows, `relates to` any other. One the draft does not keep is listed under Removed
     at step 7 with its reason, as `reformat.md` step 2 lists it; nothing is dropped unlisted.
   - Motivation: the why from the source and the person, never supplied by the agent, a source
     with none being step 4's gap; Impact from the goal and the reports, beyond the code. The
     epic, the year-plan month and the dependencies from Placement go to the fields and links,
     not the description.
   - The code today: Touches and Most of the change from this repository's report; Used by
     from its Callers and each other repository's Touches, naming the repository; a line no
     report confirms ends `(unconfirmed)`.
   - Technical Requirements from the design choices, each with its source; implementation to For
     planning. A choice the existing ticket states keeps the source it had and gains no name or
     date the ticket does not give. One the source and the person did not state, such as a term,
     a decision or a rule the change must meet, is not added: it is a question at step 6, `one
     line: add <the requirement> (<its source>)?`.
   - Acceptance Criteria as outcomes, as `ticket-format.md` defines them; how each is checked, the test
     and what it needs, to For planning.
   - Related Out of Scope Tickets from the overlaps that own part of the work and the scope
     questions step 6 answers out of scope, each a ticket that exists or a follow-up ticket, also
     under Actions proposed.
   - Related Docs from every document the draft cites, each with the URL its reader or the
     source gave.
   - A `context:` line under Considerations only for a shared `context/` entry whose subject the
     change touches, never the nearest one.
   - Open Questions from step 4, each with its `Affects:` from the reports, and followed in the
     session by `→ Recommended: <answer> · <evidence>` or `→ No recommendation: <why>`. That line
     goes to the context page, not the ticket.
   - The wording as `${CLAUDE_SKILL_DIR}/../writing/SKILL.md`'s "Structure" sets out.

   Estimate on the team's scale as the median effort, against the search block's `References:`
   line; with none at a size, say so rather than estimating from memory. Name what drives it:
   amount of work, risk and uncertainty, complexity. Show the field block, the description, and
   the estimate in one line.
6. **Walk the open questions against the draft**, up to four to a widget, in the draft's order,
   aiming to answer each now: an answered question is one fewer for every later turn. Each
   question's options: the recommended answer, marked `(Recommended)`, its evidence in the
   description; the next answer the evidence supports; **For now: <the recommended answer>**,
   which uses it in the ticket and keeps the question to revisit; **Keep it open**, for when
   nobody can answer it yet. The question's text says that another answer, an answer for now
   (`for now: <answer>`) or **Drop** is typed under Other. A question with no recommendation
   offers its answers and Keep it open, and says what would decide it. Where an option changes
   the ticket or the code it describes, its first words name the size: `one line`, `a few
   lines`, `an hour` or `changes the plan`.

   **A scope question**, from a Beyond the goal line, a ripple candidate or the person, takes
   these options instead: **In scope**; **Out of scope: <ticket key>**, when a ticket owns the
   work, linked and listed under Related Out of Scope Tickets; **Out of scope: file a
   follow-up**, recommended when none does, which adds a follow-up ticket to the write plan
   (`using-jira`, "A follow-up ticket") from what the session holds, with nothing more asked;
   **Out of scope: a boundary**, a Technical Requirement that the change leaves it as it is. Left
   out with neither, or **Drop**, is typed under Other.

   Fold each answer into the draft as it lands: a design choice into Technical Requirements with
   its source (`(<name>, <date>)`), a criterion, a boundary, a Related Out of Scope Tickets
   line, Motivation or The code today. An answer for
   now goes where it applies, marked `(for now, see Open Questions)`, and its question stays with
   `Answered for now:`. A question kept open or answered for now gets `Open because:`, drafted
   from the reports for the person to keep or correct at step 7; the reason they keep there is
   theirs, as `ticket-format.md` defines the field. One the person cannot give a reason for is offered
   back as a decision, with the recommendation first. Every question ends answered, answered for
   now, open or dropped by the person, who may add one of their own at any point. More than five
   kept open is a sign of two tickets: say so, and offer step 3's split.
7. **Review the draft.** Say what changed from the original, the ticket as fetched or the
   person's own description: added, removed and reworded, one line each, then each question
   answered in session and each assumption taken, then the questions kept open, those answered
   for now marked so. For an existing ticket, Removed names every fact of the original the draft
   no longer holds, with its reason, and Reworded every one whose words changed or that moved to a
   field, a link or For planning. This is the page's What changed and the ticket's `Session
   comment`. When the description of an existing ticket changes, read its summary against the
   revised Driving Requirements, whose main point a summary names, not each requirement: one that
   no longer names it, or names work now out of scope, gets a new summary proposed in the form
   `using-jira`'s "Copy-paste output" sets, shown now and after as a field change and listed under
   Reworded. One that still names it and names nothing now out of scope is kept as it reads,
   whatever its form: a summary is not replaced for its form alone. A new summary the person
   declines here, at Change it, is listed nowhere: not under Reworded, and not in the paste. Show
   the draft as it now stands, each kept-open question's drafted reason and effect named as
   theirs to keep or correct, and ask: **Looks right** (Recommended), which writes the files,
   step 8's page, context copy and paste file; **Change it**, folded in and asked again;
   **Stop**, which writes none of them and leaves the draft in this conversation; **Let's
   discuss**. Nothing in step 8 runs before Looks right. The write plan's `.review/jira-plan.md`,
   written to show the plan below, is not one of the files.

   The same widget asks a second question, the write plan's gate, built as
   `${CLAUDE_SKILL_DIR}/../using-jira/write-plan.md` sets out, the plan shown above the widget:
   - For an existing ticket: the `Comment to post`, then the description, then each field change,
     the `Session comment` last. A ticket settled before has no `Comment to post`.
   - For a new ticket: the create, with the field block and the description, then the `Comment to
     post`, the person's own words, and the `Session comment`.
   - Each piece of a split, the same way, with its epic and its links.
   - Each item of Actions proposed: a link; a follow-up ticket, its create, description and
     link, as `using-jira`'s "A follow-up ticket" sets out; a merge of two tickets, as its
     "Merging two tickets" sets out, keeping the ticket step 3's choice kept, with the two
     ticket blocks step 1 returned.
   - An assignee, and the move from the filed status to the approved status, as `using-jira`'s
     "Writing to Jira" allows them, each status as the profile's `jira.roles` names it ("Writes").

   Ask **Write all <n>** (Recommended), **Drop some** or **Paste it all**, beside Looks right;
   the answer counts only with Looks right, and is asked again after a Change it. Without the
   write tools, say so in one line and ask no gate.
8. **Write the files, write the plan, and hand off.** Write the page, its `.review/context.md`
   copy except for a pull request source, and `<ticket>.jira.txt` first, so the paste is ready
   whatever follows. Then run the plan, as the plan file sets out, its texts under
   `.review/context/<ticket>.send/` and its record in `.review/context/<ticket>.writes.md`:
   - A create's key replaces the slug: rename `.review/context/<slug>.md`, `<slug>.jira.txt`,
     `<slug>.original.txt`, `<slug>.send/` and `<slug>.writes.md` to the key, and put the key in
     the page's heading and, when it has one, in its `.review/context.md` copy.
   - When a description write landed and the read-back does not flag it as a Markdown
     conversion, read it with one `source-reader` running `ticket <key>`, write it to
     `<ticket>.send/stored.txt`, and run the script again with `--stored` on it, `<
     .review/context/<ticket>.send/description.txt`: exit 0 is a match, exit 3 lists what
     differs. Say whether the ticket now has its `Original request` comment.

   The closing summary lists what was written to Jira, with the keys, and gives the path of
   `<ticket>.jira.txt` for what was not, to paste from rather than out of the terminal, in the order
   `using-jira`'s "Copy-paste output" sets. On a ticket settled before, it says there is no `Comment
   to post` and why. Except for a pull request source or a reformat, it states the estimate in one
   line, such as "Estimate: 3 points, below the split threshold". A new ticket the plan did not
   create stays under its slug: ask for the key once Jira has given one, then rename as above.
   Unless the plan moved it, the last line says the next step is a ticket writer's approval and the
   move to the approved status (the profile's `jira.roles`), and names `/lasp-dev:work <key>` for
   when the ticket is picked up, which runs `implement-change` with the ticket and its page; when
   `work` invoked this skill, it leaves out the command: `work` asks.

## Bounds

10 related tickets read in full, as `source-reader`'s search reads them. 5 ripple candidates. At
most six `ticket-investigator` agents per draft, each reading one repository. An investigation
reads what these bounds allow; it does not widen them. For a change too small to need a ticket,
such as a typo fix, say so and stop.

## Never

Write to the tracker outside step 8's approved write plan, or to GitHub other than a GitHub
tracker's issues there. Put an estimate in the ticket
block or Story Points. Call two tickets the same without quoting the criteria that match. Write a
ticket nobody asked for. Write step 8's files before the person's Looks right; the write plan's
`.review/jira-plan.md` is the one file written to show it.
