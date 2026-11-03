---
name: design-doc
description: >
  Turns your notes on a design, usually a draft Confluence page, into a design doc for work that
  spans several tickets, settling the problem and goals with you before drafting; publishes the
  page on your yes. `revise` changes a published one. Use when asked to "write a design doc",
  "turn my notes into a design doc" or "update the design doc". Not for one ticket's work, which
  is ticket-draft's.
argument-hint: "[revise] <page ID | URL | file | text> [change]"
metadata:
  author: dev-tools
  version: 1.1.0
---

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## When to run

When a piece of work spans several tickets and a reader should be able to see how they fit
without reading them all. The tickets need not exist yet: those still to be written come after
the doc, at step 8. Work one ticket holds goes to `/lasp-dev:ticket-draft` instead.
**Always start from what the person brings**: a page of their notes, text or a file, or a
published design doc to revise. Never write a design doc nobody asked for.

The drafting is the easy part. The skill exists for the framing: what problem this solves, for
whom, how badly, and what the design must and must not do. A draft written before those are
settled reads well and rests on the skill's guesses, and that is worse than no draft: the fluency
hides the guesses from every reader. So step 3's gate holds even when the person asks to skip
ahead, the one step `decision-points.md`'s reorder freedom does not
reach. Every other step can be skipped, repeated or reordered.

## Options

| Option | Default |
|---|---|
| Mode | `draft`; `revise` changes a published design doc, `${CLAUDE_SKILL_DIR}/revise.md` in place of these steps |
| Source | A Confluence page ID or URL holding the person's notes; pasted text or a file is the alternative; with none, ask for them, and go on without notes only when the person says there are none |
| Diagrams | A `components` diagram of the target architecture through `/lasp-dev:drawio`, and a `flow` diagram of the landing order when it has stages; a diagram already on the notes page is kept or redrawn; the person may decline either or ask for more |

## Reads

`using-confluence` for the spaces and what to skip, `using-jira` for tickets, and the shared
`<standard>/terminology.md` and `<standard>/decisions.md`, `<standard>` being the directory
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints; when it exits 1 ending "the repository has no standard", these are not read, and any other exit 1 is a refusal to show the person, with nothing read; a failed read names the path. Notes, a page or a ticket that warns it is controlled, read here or listed as
`Withheld:` by `source-reader`, follow "Controlled content" in
`${CLAUDE_SKILL_DIR}/../writing/references/short.md`: ask the person before reading on, and pass
their yes to `source-reader` as a `Cleared:` line.

- **The notes page, in this session**: `confluence_get_page` with Markdown, and once more with
  `convert_to_markdown: false` to list what the Markdown read drops: the macros (drawio, jira),
  layouts and inline comments. This is the one page read outside `source-reader`, because its wording is
  the person's framing, the published draft replaces it, and the gate's diff and version check
  need it whole. Note its space key for the publish gate.
- **Other pages** through `source-reader` `page`: the design docs and living-state pages of the
  area, found where the project's `wiki.md` (`using-confluence`'s "The wiki") says design docs live, by the area
  page's children, since search may be blind (`using-confluence`'s blindness check, which `wiki.md` says a space needs).
- **The year plan** through one `source-reader` `plan` for this month and the next two, for the
  year-plan consideration at step 3.
- **Tickets** through `source-reader`: `ticket <key>` for each key the notes name, and one
  `search` with the goal and `Jira: <project>`, the profile's `ticket.project`
  (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field ticket.project`).
- **The code** through `ticket-investigator`, one per repository the notes name or the work
  reaches, cloned beside this one (`$(git rev-parse --show-toplevel)/../<repo>`). Each gets the
  goal and the notes' claims about that repository. A repository not cloned beside is named
  as unread.

A server stops only the step that needs it, said once as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out: without the Atlassian server, pasted
notes still frame and draft, the ticket reads are named as skipped, and step 7 hands the page
over to paste.

## Writes

`.review/design/<slug>/`, where `<slug>` is the page ID, or a short slug from the topic until a
page exists:

- `notes.md`: the source verbatim, written before anything else, unless the source warns it is
  controlled and the person has not cleared it, when nothing is written; with `Page: <id> · Version:
  <n>` as its first line when it came from a page, after the `Controlled:` line when the source was
  cleared. `frame.md` and `draft.md` written from a cleared source open with the same line.
- `frame.md`: the frame as it grows, each line with its source. It has no `Confirmed:` line
  until the person confirms at step 3's gate, then `Confirmed: <YYYY-MM-DD>`. A later run with
  the same source resumes from it.
- `draft.md`: the document in `${CLAUDE_SKILL_DIR}/template.md`'s shape, as shown at the gate.
- `architecture.drawio`, `path.drawio`: each diagram, from `drawio`, at steps 4 and 5.
- `tickets/<n>.md`: one prompt per ticket to create, from step 8.

Confluence only at step 7, and in `revise` mode, as `using-confluence`'s "Writing to Confluence"
sets out.

## How each turn reads

Open with where things stand in a line; close on the one thing needed. A heading per block,
bullets and tables, each line one fact. Quote the notes in the person's words when reflecting
them back.

## Steps

1. **Read the source**, its first line on its own first. If it warns it is controlled, stop at
   the warning and ask as `${CLAUDE_PLUGIN_ROOT}/skills/writing/references/short.md`, "Controlled content" says, naming only the item, where it sits and the warning, quoted and
   describing nothing of it, not even where you stopped; write nothing until the person clears
   it. Otherwise write `notes.md` first, with the Write tool. Then show what the notes
   say in four to six bullets in their own terms, the goal they imply in one line, and what they
   name: tickets, repositories, services, pages.
2. **Research**, after one line saying what runs and that it takes a few minutes, all in one
   message: the `source-reader` reads and the `ticket-investigator` agents from Reads, the goal's
   terms expanded with `terminology.md`'s synonyms. Collect every report, then show in at most
   eight lines what bears on the framing: tickets that already cover part of this, with their
   verdicts; existing design docs for the area; each claim in the notes the code does not hold,
   with its `file:line`.
3. **Frame it with the person: the gate.** The frame is:
   - **The problem as it stands**, with a concrete case where there is one: a run that failed, a
     ticket, a request that cannot be met today. A general problem, or work that makes later work
     easier, is a problem too, said as such.
   - **Who it hurts and how badly**: the severity the Context section carries.
   - **Goals**: numbered outcomes someone could check afterward, not tasks.
   - **Non-goals**: what a reader might expect this to cover and it will not.
   - **Constraints**: what is fixed, such as a service limit, an interface another team owns, a
     date.

   Fill each from the notes and the person only, each line marked with its source
   (`notes`, `<name>, <date>`); research supplies evidence and questions, never a frame line.
   Work in plain prose, not `AskUserQuestion`, whose options would put guesses in the person's
   mouth: one topic per turn, starting with the first one the notes leave open, vague or
   contradicted by research. Say what is understood, ask for what is missing, and end the turn on
   `Before I draft the frame I need: <what is missing>.` Push back until the answer is a reason:
   - a problem stated as a solution ("we need a Data Completeness table"): what goes wrong
     without it?
   - a goal stated as a task ("add an Orchestrator"): what is true afterward that is not now?
   - a problem with no case: ask once when it last bit, recommending a case from the notes or the
     research when one fits, unless the notes already say there is no single case. When the notes
     or the person say there is none, because the problem is general or the work enables later
     work, that is the answer: the frame says so, and the question is not asked again.
   - a claim the code does not hold: quote both and ask which is right.

   **Then the considerations**, asked, not answered, in one turn: those the notes and the answers
   so far leave untouched, each with what the skill knows that bears on it:
   - **Breakage and rollout order**: what breaks when this lands, and in what order the pieces
     must deploy.
   - **Failure, redrive and observability**: what happens to a half-processed batch, and how
     anyone finds out.
   - **Reprocessing and versioning**: old data, old algorithm versions and product versions run
     through the new design.
   - **Ownership boundaries**: which repository owns each piece, and who consumes it, as
     `${CLAUDE_PLUGIN_ROOT}/skills/using-curryer/references/downstream.md` maps them.
   - **Compute and cost**: where each piece runs, and what grows with data volume.
   - **People outside the team**: operations, the science and instrument teams, and the
     archives that receive the products.
   - **The year plan**: the milestone this serves and its month, from the `plan` read.

   Each answer goes into the frame as a constraint, a non-goal, a design topic or an open
   question with who decides; "does not apply" is kept with its reason.

   **Check the scope.** One ticket's worth: recommend `/lasp-dev:ticket-draft` and stop
   here. Goals that do not depend on each other: offer to split into a design doc each.

   Show the frame whole and ask: **Confirm the frame** (Recommended), **Change it**, folded in
   and asked again, **Split**, or **Stop**, which keeps `frame.md` for a later run. Confirm is
   offered only once the problem, who it hurts and at least one goal each come from the notes or
   the person, and the case is given or the notes or the person say there is none; until then the
   turn shows the frame with those lines open and asks for them, and a request to draft anyway
   gets that same answer. Any other line may stay open, carried into the doc as an open question
   with who decides. Nothing in step 4 starts before Confirm.
4. **Design.** Draft the Design section from the confirmed frame and the research: the target
   architecture first, the core of the doc, with the components and interfaces as tables, and a
   problem and solution per topic where the topics stand apart; then, when the design changes
   something that exists, the path from today to the target: what is added, what changes, what is
   removed, and what deliberately stays the same with the reason not to change it, each a short
   list of components with a line on each, any list that does not apply left out; then the
   assumptions. Each design choice with more than one workable answer is a decision point: the
   options, each with its evidence, and a recommendation, up to four choices to a widget. A
   choice the notes already made is the person's: a finding against it is a question, never a
   silent rewrite. Each answer goes under Decisions and Trades with what was chosen, the
   alternatives and why, and who decided; a choice nobody can settle yet goes under Open questions
   with who decides.

   **The architecture diagram**, asked with the design's first decision point, or on its own when
   there is none: draw the target architecture, recommended for any design with more than two
   components. Run `/lasp-dev:drawio` `components` with the Design tables' components and
   each interface as a line labeled with what crosses, and the output path
   `.review/design/<slug>/architecture.drawio`; any other diagram the person asks for the same
   way. Pass its questions to the person. In the draft each new diagram is a caption line naming
   it until the person places it. A diagram the notes page already holds for it is handled as the
   next paragraph says, not drawn anew.

   **A diagram already on the notes page**, a stub the person placed or a finished one, is a
   `drawio` macro the second read in Reads listed. Ask which diagram it is meant to hold, and
   whether to keep it as it is or redraw it. Either way its macro is copied into `draft.md` where
   its diagram goes, as `using-confluence`'s "Macros and mentions" says for "An existing diagram",
   so the publish keeps it and its attachment. Kept, nothing is drawn for it. Redrawn, the person
   exports its XML as `drawio`'s "Into Confluence" says for a diagram already on a page, `drawio`
   draws from that, or from the Design tables for an empty stub, and the person pastes the new XML
   into the same macro after the publish.
5. **Work breakdown.** Map the design onto tickets: each row a key from the research, or `to
   create`, with what it delivers, the goals it serves by number, what it depends on, and the
   ticket's status; then the order the pieces land in. A ticket the research found that overlaps
   but is not in the breakdown is a question: in the breakdown, or under Related pages.

   **The path diagram**, when the landing order has more than one stage: offer it, recommended,
   and on a yes run `/lasp-dev:drawio` `flow` with the stages in landing order, each with the
   tickets it lands and what it changes from the path from today to the target, and the output
   path `.review/design/<slug>/path.drawio`; placed as the architecture diagram is.
6. **Assemble and review.** Write `draft.md` in the template's shape, then review it as
   `${CLAUDE_SKILL_DIR}/../writing/SKILL.md`'s "Reviewing existing text" sets out, which sends a
   long document to the `prose-reviewer` agent. Show the draft with its Status table, the AI
   assistance level `5/5 (not read by a person)` until the person names another, as
   `${CLAUDE_PLUGIN_ROOT}/skills/pr-review/comment-style.md`'s "AI assistance level" sets, and
   ask: **Looks right** (Recommended), **Change it**, folded in and asked again, **Stop**, which
   keeps `draft.md`, or **Let's discuss**.
7. **Publish: the gate.** `ToolSearch` for `confluence_update_page`; without it, say that the
   server is read-only, in one line, or not connected, as `servers.md` sets out with the publish
   as what is lost, and hand over `draft.md` to paste. Otherwise
   show, in the message that asks, as `using-confluence`'s "Writing to Confluence" says:
   - **The notes page**: its space, its title now and after (`Design Doc - <topic>`), and `git
     diff --no-index` of `notes.md` against `draft.md`. A page in a personal space (a key that
     starts with `~`) is published where it sits; say so, and that moving it under the area's
     page is the person's to do.
   - **A cleared source**: when `notes.md` opens with a `Controlled:` line, the item and its
     warning, since the page carries its content ("Controlled content" in `short.md`).
   - **What the write drops**: each macro, layout and inline comment the second read listed,
     other than the `drawio` macros the draft carries, and every mention and image on the page, as "Writing to Confluence" says; page history
     keeps them.
   - **The prompt that follows**: Claude Code asks again at the call, as the plugin's hook asks
     at every Confluence write; a no there writes nothing.

   Ask **Publish to <page title>** (Recommended), **Change it**, **Paste it myself**, or
   **Stop**. On Publish, write as "Writing to Confluence" sets out: read the page's version
   again, and when it moved, read, diff and ask again; then one `confluence_update_page` with the
   new title, `content_file` the absolute path of `draft.md` (inline `content` from the same file
   when the server refuses the path), `content_format: markdown`, and a `version_comment`
   naming this skill. Read it back and give the URL and the new version. A failed write hands
   over `draft.md` to paste, as "Writing to Confluence" sets out.

   **With pasted or file notes** there is no page to update. `ToolSearch` for
   `confluence_create_page`; without it, say why as the update's gate does, and hand over
   `draft.md` to paste. Otherwise propose a parent
   from the area's page under "Technical Documentation", with why, and ask the person to confirm
   it or name another. The gate names the space, the parent and the title, and that Claude Code
   asks again at the call; its yes is to that one `confluence_create_page`, with the body and
   format the update takes (the create takes no version comment), made once and never retried. A
   failure hands over `draft.md` to paste. Read it back and give the URL. Save the new page's ID
   in `frame.md`, and rename the slug directory to it, so a later run or `revise` updates the
   page rather than creating another.

   **Then the diagrams**: each new diagram's file, at its path under the renamed directory after a
   create, the `drawio` hand-over, and the caption line or carried macro it goes into, for the
   person to place as `drawio`'s "Into Confluence" says; on a paste, the same beside `draft.md`.
8. **Tickets, last and optional.** When the breakdown has `to create` rows, ask: **Draft the
   tickets** writes a prompt per row to `tickets/<n>.md` (the goal served, what it delivers, what
   it depends on, the page's URL) and runs `/lasp-dev:ticket-draft` on each, one at a time;
   **Leave placeholders** keeps the rows as they are; **Stop**. A key that arrives later goes in
   with `revise`.

The closing summary gives the page's URL, what was written, and what is left: open questions,
`to create` rows, diagrams to place.

## Bounds

The notes and five other page bodies. Ten named tickets, one search, and one year-plan read. At most six
`ticket-investigator` agents, each reading one repository.

## Never

Draft before the frame is confirmed. Fill a frame line from inference. Lower the AI assistance
level on the skill's own reading. Write to Confluence beyond step 7's one write and `revise`'s,
each after its own gate; delete, move, copy, label, restrict or comment on a page. Upload a
diagram or an attachment. Write to Jira:
`ticket-draft` asks for its own writes.
