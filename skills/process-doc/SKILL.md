---
name: process-doc
description: >
  Writes a Confluence page on how something is done: a team process such as development or
  review, a how-to, or a user guide to a software or data product; its purpose and readers
  confirmed with you, the steps and who does each settled with you; publishes on your yes.
  `revise` brings a published page in line with how things are done now. Use when asked to
  "document our process", "write a how-to", "write a user guide" or "update the process page".
  Not for how a system is built (architecture-doc) or a change still being designed (design-doc).
argument-hint: "[revise] <page ID | URL | file | text>"
metadata:
  author: dev-tools
  version: 1.0.2
---

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## When to run

When people need a page that tells them how something is done: how the team works (the
development process, the Git workflow, how a design is reviewed, how work is planned), how to do
one task, or how to use a product. A process page is conceptual: it describes what people do,
which code rarely shows. How a system is built is `/lasp-dev:architecture-doc`'s; a change
still being designed is `/lasp-dev:design-doc`'s.

The reader follows the page, so a wrong page is worse than none: they do what it says. Two
things the skill must not guess:

- **The purpose and the readers**: what the page is for, who follows it, and when. Also whether
  it describes how things are done today or a proposal for how they should be, since a reader
  treats the two differently. Step 3's gate holds even when the person asks to skip ahead, the
  one step `decision-points.md`'s reorder freedom does not reach.
- **The steps and who does each**: the order, the roles, what each step needs and produces, and
  where a step branches. Only the person, or a page or decision they point at, says what the
  team does; the skill does not fill a gap with what teams usually do.

## Options

| Option | Default |
|---|---|
| Mode | `draft`; `revise` brings a published page in line with how things are done now, `${CLAUDE_SKILL_DIR}/revise.md` in place of these steps. A `draft` run on a process that already has a page offers `revise` instead |
| Kind | Read from the request: a `process` people follow together, a `how-to` for one task, or a `guide` to a product; asked when it fits more than one, since the kind sets the page's shape |
| Source | What the person gives: their notes on a page, pasted text or a file, and the pages and decisions they point at; with none, ask for them, since the process lives in people's heads |
| Diagram | A `flow` diagram through `/lasp-dev:drawio` for a process with more than one role or a branch; offered, not drawn, for a how-to or a guide |

## Reads

`using-confluence` for the spaces, where process pages sit, and how a page carries Jira macros,
mentions and diagrams; `using-jira` when the process involves tickets; and the shared
`<standard>/terminology.md` and `<standard>/decisions.md`, `<standard>` being the directory
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints; when it exits 1 ending "the
repository has no standard", neither is read, and any other exit 1 is a refusal shown to the
person. A failed read names the path.
A page, file or ticket that warns it is controlled, read here or listed as `Withheld:` by
`source-reader`, follows "Controlled content" in
`${CLAUDE_SKILL_DIR}/../writing/references/short.md`: ask the person before reading on, and pass
their yes to `source-reader` as a `Cleared:` line.

- **The notes page**, when the person's notes are on a page or they give a page to write over,
  in this session: `confluence_get_page` with Markdown, and once more with
  `convert_to_markdown: false` to list what the Markdown read drops, as `design-doc` reads its
  notes page, since `notes.md` and the publish gate's diff need it whole.
- **Other pages** through `source-reader` `page`: those the person points at, the process's
  existing page and its siblings, found as the project's `wiki.md` (`using-confluence`'s "The wiki") says, for what
  other pages already own and for the team's words.
- **Tickets** the person or a page names, through `source-reader` `ticket`.
- **The tool or product the steps use**, only when the page names one with code on disk: a
  `ticket-investigator` per repository, its goal "what a person does with this repository's
  tools in this process: the commands, options, configuration and files the steps name; list
  every one, not ten", and
  as claims each step's statement about it. A Git workflow reads the repository's contributing
  guide, branch and CI configuration this way; a user guide, the product's commands and formats.
  Nothing else is read from code: the process is the person's.

A server stops only the step that needs it, said once as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out: without the Atlassian server, pasted
notes still draft, and step 8 hands the page over to paste.

## Writes

`.review/process/<slug>/`, where `<slug>` is the page ID once one exists, or a short slug from
the topic:

- `notes.md`: the source verbatim, written before anything else, unless it warns it is
  controlled and the person has not cleared it, when nothing is written; with `Page: <id> ·
  Version: <n>` as its first line when it came from a page, after the `Controlled:` line when
  cleared. The other files written from a cleared source open with the same line.
- `facts.md`: what the page will say and where each part came from: the notes, a page, a
  ticket, `file:line`, or `<name>, <YYYY-MM-DD>` for the person. The purpose carries `Purpose
  confirmed: <YYYY-MM-DD>` once the person confirms it at step 3, and a later run with the same
  source resumes from it.
- `<diagram>.drawio`: each diagram, from `drawio`.
- `draft.md`: the page, in the shape step 5 settles.

Confluence only at step 8, and in `revise` mode, as `using-confluence`'s "Writing to Confluence"
sets out.

## How each turn reads

Open with where things stand in a line; close on the one thing needed. Show the person the
page's content in the page's own words, and quote their notes in their words when reflecting
them back.

## Steps

1. **Read what the person brings.** If it warns it is controlled, stop at the warning and ask as
   `${CLAUDE_PLUGIN_ROOT}/skills/writing/references/short.md`, "Controlled content" says, naming
   only the item, where it sits and the warning; write nothing until the person clears it.
   Otherwise write `notes.md`, with the Write tool. Say in a line the topic, the kind, and who the
   notes suggest the readers are.
2. **Research**, after one line saying what runs, all in one message: the page reads and any
   investigator from Reads. Show in at most eight lines what bears on the page: the process's
   existing page if one was found; pages
   that already describe part of this, which the new page links rather than repeats; decisions
   in `decisions.md` that apply; each step in the notes a page, a decision or the code
   contradicts, quoted beside it; each command or option the code does not hold; and any list an
   investigator marked `truncated:`. When the process already has a page, offer `revise` and stop
   unless the person says to write a new one.
3. **Purpose, readers and status: the gate.** Draft, in plain prose:
   - **the purpose** in one to three sentences: what someone can do or knows after following the
     page, and why the process exists, what goes wrong without it;
   - **the readers**: who follows it, and when they come to it;
   - **the status**: how things are done today, or a proposal;
   - **the scope**: when it applies and, where a reader might expect otherwise, when it does
     not.

   Build each from the person's words first, then the pages, marked with its source. Show it in
   plain prose, not `AskUserQuestion`, whose options would put words in the person's mouth, and
   ask the person to confirm it as written or rewrite it. Push back on a purpose that only names
   the topic ("this page describes the Git workflow": so that what?). Only the person's yes to
   the exact text confirms it; record `Purpose confirmed: <date>` in `facts.md`. Nothing in step
   5 starts before it.
4. **The steps.** Show the skeleton as the page will hold it: for a process, each stage with who
   does it, what it needs, what it produces and when it is done, and each branch with the
   condition; for a how-to, each numbered action with the result the reader should see; for a
   guide, the tasks a user comes to do. Mark each step's source, and each the notes leave open:
   a missing role, an order the notes do not fix, a step with no way to tell it is done. Ask
   for those in plain prose, one topic per turn. Then ask: **These are right** (Recommended),
   **Change them**, folded in and asked again, or **Let's discuss**.
5. **The shape.** Propose the page's sections from `${CLAUDE_SKILL_DIR}/template.md` for the
   kind: its required sections, the optional ones this page has content for, and any the content
   calls for that the template lacks, each with one line on what it holds. A page that reads
   clearly for its readers matters more than one shaped like the others. Ask with the diagram:
   **Draft it** (Recommended), **Change the sections**, or **Stop**, which keeps `facts.md`; and
   whether to draw the flow diagram.
6. **Diagrams.** Run `/lasp-dev:drawio` `flow` with the steps, one lane per role and each
   branch labeled, and the output path `.review/process/<slug>/flow.drawio`; any other diagram
   the person asked for the same way. Pass its questions to the person.
7. **Draft and review.** Write `draft.md` in the settled shape, following "How the page reads"
   below and `${CLAUDE_SKILL_DIR}/template.md`'s guidance. Tickets go in as Jira macros and the
   owner as a mention, as `using-confluence`'s "Macros and mentions" says; each diagram is a
   caption line naming it until the person places it. Review the prose as
   `${CLAUDE_SKILL_DIR}/../writing/SKILL.md`'s "Reviewing existing text" sets out, which sends a
   long document to the `prose-reviewer` agent, with the readers from step 3 as its audience.
   Show the draft with its Status table and its AI assistance level, as
   `${CLAUDE_SKILL_DIR}/../writing/references/page.md` sets, and ask:
   **Looks right** (Recommended), **Change it**, folded in and asked again, **Stop**, which keeps
   `draft.md`, or **Let's discuss**.
8. **Publish: the gate**, under `using-confluence`'s "Writing to Confluence". `ToolSearch` for
   the write tool; without it, say that the server is read-only, in one line, or not connected,
   as `servers.md` sets out with the publish as what is lost, and hand over `draft.md` to paste;
   show, in the message that asks, as "Writing to Confluence" says, where the page goes,
   a space and parent proposed from the project's `wiki.md` for a new page
   with why, or asked for when it names none for this kind of page,
   or the diff of `notes.md` against `draft.md` and what the write drops for a page given; name a
   cleared source and the prompt at the call. Ask **Publish to <page title>** (Recommended),
   **Change it**, **Paste it myself**, or **Stop**. On Publish, one `confluence_create_page` or
   `confluence_update_page`, made once and never retried, with `content_file` the absolute path
   of `draft.md` (inline `content` when the server refuses the path), `content_format:
   markdown`, and a `version_comment` naming this skill on an update. A failure hands over
   `draft.md` to paste. Read it back, give the URL and the version, and save a new page's ID in
   `facts.md`, renaming the slug directory to it.
9. **Place the diagrams**, as `drawio`'s "Into Confluence" says: each file and the caption line
   it replaces.

The closing summary gives the page's URL, what was written, the diagrams left to place, and any
step left unconfirmed.

## How the page reads

`${CLAUDE_SKILL_DIR}/../writing/references/page.md` sets how a page a person reads to learn
something reads, its Status table's AI assistance level included. A page a reader follows adds:

- **Steps are numbered, one action each**, in the imperative ("Open a draft pull request"), with
  who does it when more than one role takes part, and what the reader sees when it worked.
- **A command is exact and copyable**, in a code block, with what to replace marked as
  `<placeholder>` and named in the sentence before it.
- **A choice says how to choose.** A branch in the steps names its condition ("If the tests
  fail, …"), and each way on.
- **A rule says why**, in a clause, so a reader can judge the case the page did not foresee.
- **A proposal says so.** A page whose status is a proposal says it in its Purpose, and in the
  Status table, so nobody follows it as current practice.
- **Each page has one kind.** A process page links its how-tos rather than holding them; a guide
  links the process it belongs to.

## Bounds

The person's sources, five other pages through `source-reader` and the tickets the person or a page names. At most
three `ticket-investigator` agents, each reading one repository.

## Never

Publish a purpose the person has not confirmed, or fill it from inference. Describe a step, a
role or an order that neither the person nor a page they point at states. Present a proposal as
practice. Write to Confluence beyond step 8's one write and `revise`'s, each after its own gate;
delete, move, copy, label, restrict or comment on a page. Write to Jira. Upload a diagram or an
attachment.
