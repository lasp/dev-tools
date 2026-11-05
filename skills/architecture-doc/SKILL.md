---
name: architecture-doc
description: >
  Writes a Confluence page on how a system or codebase is built: its purpose, confirmed with you,
  its interfaces to the larger system and its users, and how it works, from the code and your
  description; publishes on your yes. `revise` brings a published page up to date with the code.
  Use when asked to "document this system", "write an architecture page", "update the architecture
  doc" or "bring this page up to date". Not for a change still to be designed (design-doc), how a
  task is done (process-doc) or an explanation in the conversation.
argument-hint: "[revise] <repository | page ID | URL | file | text>"
metadata:
  author: lasp-dev
  version: 1.1.3
---

Every question, and every file it writes, follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## When to run

When a system, a service, a pipeline or a component needs a page a person can read to learn what
it is for, what it talks to and how it works, or when such a page has fallen behind the code.
The page describes what exists. A change still being designed is `/lasp-dev:design-doc`'s;
its doc links to this page once the change lands.

The reader is the point. Someone new to the system, an operator or a neighboring team opens the
page to answer a question, and the page succeeds when they find the answer quickly and trust it.
Two things they must get right are the ones the skill must not guess:

- **The purpose**: why the system exists and for whom. Code shows what a system does, never why;
  a purpose inferred from it reads well and may be wrong, and every reader builds on it. So step
  3's purpose gate holds even when the person asks to skip ahead, the one step
  `decision-points.md`'s reorder freedom does not reach.
- **The interfaces**: every place the system meets something outside it, a person included.
  These are the runtime interfaces: what calls it, what it calls, what it reads and writes, what
  people do with it. The build, test and release tooling is an interface only when the system
  is itself development or operations tooling, or the person asks for it.

## Options

| Option | Default |
|---|---|
| Mode | `draft`; `revise` brings a published page up to date, `${CLAUDE_SKILL_DIR}/revise.md` in place of these steps. A `draft` run on a system that already has a page offers `revise` instead |
| Subject | What the person names: one or more repositories, a description, a file or a page; this repository when they name nothing and the request is about it |
| State described | Each repository's default branch at its head. The alternatives the person names: a branch or pull request about to merge, read in its place and named on the page; or, for a system with no code to read, such as one set up by hand, the person's description and the pages they point at |
| Diagram | A `context` diagram through `/lasp-dev:drawio`; the person may decline it or ask for more |

## Reads

`using-confluence` for the spaces, where living-state pages sit, and how a page carries Jira
macros, mentions and diagrams; the shared `<standard>/terminology.md`, `<standard>` being
the directory `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints, so the page
uses the project's names; when it exits 1 ending "the repository has no standard", the page uses the
repository's own names, and any other exit 1 is a refusal shown to the person. A failed read names
the path. A page, file or ticket that warns it is
controlled, read here or listed as `Withheld:` by `source-reader`, follows "Controlled content"
in `${CLAUDE_SKILL_DIR}/../writing/references/short.md`: ask the person before reading on, and pass
their yes to `source-reader` as a `Cleared:` line.

- **The checkout's state**, before any investigator: each repository's branch and
  `git -C <repo> rev-parse --short HEAD`. The investigator reads only what is checked out, so
  when that is not the state the Options row names, the default branch or the branch the person
  named, stop and ask the person to check it out. The commit goes into `facts.md` for the page's
  `Reflects` line.
- **The code** through `ticket-investigator`, one per repository, at the path the person gives
  or cloned beside this one (`$(git rev-parse --show-toplevel)/../<repo>`). Each gets as its goal
  "what this repository does at run time and every place it meets something outside it:
  entry points, what calls it, what it calls, what it reads and writes, configuration, and what
  a person does with it; list every interface, not ten", and as claims the person's description
  and any page's statements about that repository. A repository not on disk is named as unread.
- **A branch or pull request about to merge**, when the person names one: checked out as above,
  and its description and changed files through GitHub, as `using-github` says, given to the
  investigator with the claims.
- **A page the person gives as the source or to write over**, in this session:
  `confluence_get_page` with Markdown, and once more with `convert_to_markdown: false` to list
  what the Markdown read drops, as `design-doc` reads its notes page, since `notes.md` and the
  publish gate's diff need it whole.
- **Other pages** through `source-reader` `page`: the area's design docs and the system's
  existing page, found as the project's `wiki.md` (`using-confluence`'s "The wiki") says.
- **Tickets**, only those the person names or a page links, through `source-reader` `ticket`,
  for the page's Status table.

A server stops only the step that needs it, said once as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out: without the Atlassian server, the code
and the person's description still draft, and step 8 hands the page over to paste.

## Writes

`.review/architecture/<slug>/`, where `<slug>` is the page ID once one exists, or a short slug
from the system's name:

- `notes.md`: what the person gave, verbatim, written before anything else, unless the source
  warns it is controlled and the person has not cleared it, when nothing is written; with `Page:
  <id> · Version: <n>` as its first line when it came from a page, after the `Controlled:` line
  when cleared. The other files written from a cleared source open with the same line.
- `facts.md`: what the page will say and where each fact came from: `file:line`, a pull request,
  a page, or `<name>, <YYYY-MM-DD>` for the person. The purpose carries `Purpose confirmed:
  <YYYY-MM-DD>` once the person confirms it at step 3, and a later run with the same subject
  resumes from it.
- `<diagram>.drawio`: each diagram, from `drawio`.
- `draft.md`: the page, in the shape step 5 settles.

Confluence only at step 8, and in `revise` mode, as `using-confluence`'s "Writing to Confluence"
sets out.

## How each turn reads

Open with where things stand in a line; close on the one thing needed. Show the person the
page's content in the page's own words, so what they confirm is what readers will read.

## Steps

1. **Read what the person brings.** If it warns it is controlled, stop at the warning and ask
   as `${CLAUDE_PLUGIN_ROOT}/skills/writing/references/short.md`, "Controlled content" says, naming
   only the item, where it sits and the warning; write nothing until the person clears it.
   Otherwise write `notes.md`, with the Write tool. Say in a line what the subject is, which
   state the page will describe, and who it is for, the readers the person names, or "people
   new to the system" when they name none.
2. **Research**, after one line saying what runs and that it takes a few minutes, all in one
   message: the investigators, the branch reads and the page reads from Reads.
   Collect every report, then show in at most eight lines: what the system does at run time,
   the interfaces found, any list an investigator marked `truncated:`, the system's existing
   page if one was found, and each statement in the person's description or a page that the code
   does not hold, with its `file:line`. Write what holds to `facts.md`, each fact with its source.
   When the system already has a page, offer `revise` and stop unless the person says to write a
   new one.
   Without code to read, the facts are the person's: ask for the interfaces and the parts in one
   turn rather than inferring them.
3. **The purpose: the gate.** Draft the purpose in two to four plain sentences: what the system
   does, for whom, and what would be missing without it; then, when a reader might expect it,
   what it does not do. Build it from the person's words first, then the pages, the README and
   the code, each sentence marked with its source. Show it in plain prose, not
   `AskUserQuestion`, whose options would put words in the person's mouth, and ask the person to
   confirm it as written or rewrite it. Push back on a purpose that is a list of features (what
   goes wrong for someone without it?) or a restatement of the name. A sentence the code
   contradicts is quoted beside the code, and the person says which is right.

   Only the person's yes to the exact text confirms it; record `Purpose confirmed: <date>` in
   `facts.md`. Nothing in step 5 starts before it, and a request to draft anyway gets this
   question again.
4. **The interfaces.** Show them as the page will hold them, one row each: what is on the other
   side, the direction, what crosses (the data, the request or the action, with its format),
   what starts it, and the contract (a schema, an API, a file convention, a manual procedure),
   each from `facts.md`. People are rows: who uses it, and what they do. Mark each row the code
   could not confirm, and each from a branch not yet merged. Ask: **These are right**
   (Recommended), **Change them**, folded in and asked again, or **Let's discuss**. An interface
   the person adds is theirs and is marked so in `facts.md`.
5. **The shape.** Propose the page's sections as headings, each with one line on what it holds,
   from `${CLAUDE_SKILL_DIR}/template.md`: its required sections, the optional ones this system has
   content for, and any section the system's nature calls for that the template lacks. Say what
   each choice is for: a pipeline reads best by its steps, a library by the calls its users make,
   a process run by hand by who does what. A clear page for this system matters more than a
   page shaped like the others. Ask the shape with the diagram: **Draft it** (Recommended), **Change
   the sections**, or **Stop**, which keeps `facts.md`; and whether to draw the context diagram,
   recommended for any system with more than two interfaces.
6. **Diagrams.** Run `/lasp-dev:drawio` `context` with the system, each interface as a line
   labeled with what crosses, and the output path `.review/architecture/<slug>/context.drawio`;
   any other diagram the person asked for the same way. Pass its questions to the person.
7. **Draft and review.** Write `draft.md` in the settled shape, following "How the page reads"
   below, which starts from `page.md`, and `${CLAUDE_SKILL_DIR}/template.md`'s guidance on each
   section. Tickets go in as Jira
   macros and the owner as a mention, as `using-confluence`'s "Macros and mentions" says; each
   diagram is a caption line naming it until the person places it. Then review the prose as
   `${CLAUDE_SKILL_DIR}/../writing/SKILL.md`'s "Reviewing existing text" sets out, which sends a long
   document to the `prose-reviewer` agent, with the readers from step 1 as its audience. Show the
   draft with its Status table, the AI assistance level `5/5 (not read by a person)` until the
   person names another, as `${CLAUDE_PLUGIN_ROOT}/skills/pr-review/comment-style.md`'s "AI
   assistance level" sets, and ask: **Looks right** (Recommended), **Change it**, folded in and
   asked again, **Stop**, which keeps `draft.md`, or **Let's discuss**.
8. **Publish: the gate.** `ToolSearch` for `confluence_create_page`, or `confluence_update_page`
   when the person gave a page to write over; without it, say that the server is read-only, in
   one line, or not connected, as `servers.md` sets out with the publish as what is lost, and hand
   over `draft.md` to paste. Otherwise show, in the message
   that asks, as "Writing to Confluence" says:
   - **Where it goes**: for a new page, a space and parent proposed from the project's
     `wiki.md` (`using-confluence`'s "The wiki"), with why, for the person to confirm or replace, or asked for when it
     names none for this kind of page, and the title, the system's name as
     the team uses it; for a page given, its title and `git diff --no-index` of `notes.md`
     against `draft.md`, and what the write drops from it, as "Writing to Confluence" says.
   - **A cleared source**: when `notes.md` opens with a `Controlled:` line, the item and its
     warning, since the page carries its content.
   - **The prompt that follows**: Claude Code asks again at the call, as the plugin's hook asks
     at every Confluence write; a no there writes nothing.

   Ask **Publish to <page title>** (Recommended), **Change it**, **Paste it myself**, or
   **Stop**. On Publish, write as "Writing to Confluence" sets out: for a page given, read its
   version again, and when it moved, read, diff and ask again. Then one call, made once and
   never retried: `confluence_create_page` with the space, the parent and the title, or
   `confluence_update_page` with the title and a `version_comment` naming this skill; either
   with `content_file` the absolute path of `draft.md` (inline `content` from the same file when
   the server refuses the path) and `content_format: markdown`. A failure hands over `draft.md`
   to paste. Read it back and give the URL and the version; save a new page's ID in `facts.md`
   and rename the slug directory to it, so `revise` finds it.
9. **Place the diagrams.** Each diagram's file, the `drawio` hand-over, and where on the page
   it goes: the caption line it replaces, as `drawio`'s "Into Confluence" says.

The closing summary gives the page's URL, what was written, the diagrams left to place, and any
interface or fact left unconfirmed.

## How the page reads

`${CLAUDE_SKILL_DIR}/../writing/references/page.md` sets how a page a person reads to learn
something reads, its Status table's AI assistance level included. A page on a system adds:

- **It describes the code as it stands.** A fact from a branch about to merge is written as
  current, and the Status table names the branch.
- **Code paths only where a reader would go next.** A component's row names where its code
  lives; no tour of functions, and no line numbers on the page, which go stale.
- **The code's names match the page's.** A component is called on the page, in the diagram and
  in the code column what the team calls it; where the code's name differs, the row gives both.

## Bounds

The person's sources, five other pages through `source-reader` and the tickets the person or a page names. At
most six `ticket-investigator` agents, each reading one repository, and three branches or pull
requests about to merge.

## Never

Publish a purpose the person has not confirmed, or fill it from inference. Describe an interface
or a part that neither the code nor the person states. Describe planned work as current, beyond
the branches the person named. Write to Confluence beyond step 8's one write and `revise`'s, each
after its own gate; delete, move, copy, label, restrict or comment on a page. Write to Jira.
Upload a diagram or an attachment.
