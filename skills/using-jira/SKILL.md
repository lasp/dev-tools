---
name: using-jira
description: >
  How a project's Jira is used: the ticket format, fields, statuses, estimates, JQL and markup,
  with the project's own facts read from its standard's tracker.md. Applies whenever a Jira ticket
  or issue is read, searched, drafted or edited, or JQL is written.
user-invocable: false
metadata:
  author: lasp-dev
  version: 1.9.0
---

## The project

The project's own facts are in `<standard>/tracker.md`, `<standard>` being the directory
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints: its key and the URL a
ticket is browsed at, what it is the tracker of record for, its issue types, statuses and what
each means and holds, its components, the field IDs of the epic link and the estimate, how due
dates, epics and the plan are used, its estimation scale, its JQL and saved filters, and its
workflow's steps. Read it before the first Jira call. When `--standard` exits 1 ending "the
repository has no standard", as outside the project's repositories, or the standard holds no
`tracker.md`, say so and ask which project's standard to read, as `<owner>/<repo>`, whose
`standards/tracker.md` is then read from that repository through GitHub, or whether to go on
without one, with what the person pastes; any other exit 1 is a refusal: show its message and ask
the same. With no file read, take the
project key from the profile's `ticket.project`, read the issue types, statuses and fields from
the server (`jira_get_project_issue_types`, `jira_search_fields`), and ask the person once for what
neither gives. Below, `<KEY>` is the project key and `<browse URL>` the URL `tracker.md` gives,
`<KEY>-NNNN` in place of a key.

Reach it through the Atlassian MCP server, resolved with `ToolSearch` on `jira`. The server may
run read-write, so its create, edit, comment and transition tools may be there; whether a write
happens is decided by "Writing to Jira" below, never by what the server allows.

A status, component, field or filter that differs from `tracker.md` is reported in the block's
`Questions:` as `using-jira drift: <what>`, or, outside a reader, to the person once, never worked
around.

## When the server cannot be reached

A server stops a skill only at the step that reads from it; elsewhere the skill goes on and names
what it skipped. Say so as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out: which case it
is, what is lost, whether the run goes on, and the fix, with `/lasp-dev:quickstart`, the
README's "MCP servers" and Claude Code's MCP guide. At the step that needs Jira or Confluence,
stop and offer to work from text the person pastes instead, a ticket's description or a page's
content, saved under `.review/context/<key>.pasted.md` and given to `source-reader` as a file.

## Fields

`tracker.md`'s Fields table says how the project uses each field: its issue types, its statuses
and what each holds, its priorities, its components, the epic link's and the estimate's field IDs,
its due dates and its links. Whatever it says, a component is read from
`jira_get_project_components`, never from memory, and the estimate is **never written by a skill**
(see Estimates).

## The description format

The format is the plugin's, the same in every tracker:
`${CLAUDE_PLUGIN_ROOT}/standards/ticket-format.md` holds its sections, their order and what each
holds, and `tracker.md` may say how the project adapts it; the `<plugin root>` it names is
`${CLAUDE_PLUGIN_ROOT}`. Read it before a ticket is drafted, reformatted or settled. In Jira it is
written in wiki markup, part for part from that file's Markdown:

| The format's Markdown | Jira's wiki markup |
|---|---|
| `# Motivation`, a section | `h1. Motivation` |
| `## Acceptance Criteria`, a subsection | `h2. Acceptance Criteria` |
| `**Touches:**`, a labeled line | `*Touches:*` |
| `- <item>`, a bullet | `* <item>` |
| `1. <item>`, a numbered item | `# <item>` |
| `   - **Options:** <...>`, an item under a numbered item | `## *Options:* <...>` |

A link `[text](url)` is written `[text|url]`: a related ticket as `[<KEY>-NNNN <its summary>|<browse URL>]`.
The status line is the first line, as plain text. A ticket's id in Jira is its key, `<KEY>-NNNN`,
and its related tickets are linked in Jira, `relates to`, or `blocks` when one must land before the
other.

## The ticket workflow

A ticket moves through the project's statuses, as `tracker.md`'s workflow says. Which status plays
each role the generic skills name it by (filed, approved, implementation, finished, and
abandoned: closed with its work not done) is the profile's, and
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --defaults --field jira.roles` prints them;
where it refuses, the roles are the ones the `tracker.md` read under "The project" names on its
statuses. Where it prints `not yet recorded`,
the repository's standard records no workflow: no status is named by its role, and a move is the
person's to make.
A ticket is filed in the filed status and vetted there, by `ticket-draft` and a ticket writer,
into the format and for scope it misses that the implementation would run into; a ticket
writer, a person, approves it into the approved status, ready for estimation. An Open Questions
section does not by itself keep a ticket filed; the ticket writer judges whether what is still
open is safe to estimate.

A skill moves a ticket only as an item of a write plan the person approved, as "Writing to Jira"
says; the move to the approved status is then the approval of the person who said yes.

## A follow-up ticket

Work found out of scope while one ticket is drafted, that no ticket owns yet, is filed as a
follow-up ticket in the same write plan, so it is neither lost nor written into the ticket at
hand. It is filed in the filed status: only what the session already
holds and knows to be true, enough to find it and start it, not a draft. `ticket-draft <key>`
drafts it properly when someone picks it up.

- **Fields.** Project and issue type as the ticket it came from; a summary that starts with a
  verb, at most twelve words, since it is the link text in that ticket's Related Out of Scope
  Tickets; the component only when a report places the work in one. No epic, due date or
  priority unless the person gives one in the session.
- **Link.** `relates to` the ticket it came from, or `blocks` when the person said one must land
  first. That ticket's Related Out of Scope Tickets lists it.
- **Description**, each line only from the person's words or a report's, and a line nothing
  supports left out:

  ```
  ticket-draft: follow-up from <KEY>-NNNN, written <YYYY-MM-DD> by <name>
  h1. Motivation
  Found while drafting [<KEY>-NNNN <its summary>|<browse URL>], which leaves it out of scope: <why it is out of that ticket's scope, in the person's words or the report's, never what that ticket's earlier text called it>.
  h1. Driving Requirements
  <the work, in one or two sentences, from the scope question's line or the person's answer>
  *Undecided:* <a choice the work turns on that nobody has made, one line each, for its draft to ask>
  h1. The code today
  *Touches:* <from the report that found it, with its repository>
  h1. Related Docs
  * [<title>|<URL>]
  ```

  Driving Requirements states the work, never a question or a "decide whether": a choice nobody
  made goes on an `Undecided:` line, which is left out when there is none. No Acceptance
  Criteria, Open Questions or estimate: those come when it is drafted. No comment:
  a later `ticket-draft` on it posts the description as its `Original request` comment, the first
  line ending `(follow-up written by ticket-draft)`, as "Copy-paste output" says.

**A new ticket and its follow-ups.** When the ticket being drafted is new too, each names the
other's key, so neither create could run first: the ticket is created without its follow-up
lines, then the follow-ups, and one Description item adds the lines once their keys exist.

Without the write tools, each follow-up is a block of its own in the paste file, before the
ticket's, in the order the person files them, its link written as the line `Link: relates to
<the ticket's key or slug>`. The ticket's line for it reads `* <its summary> (follow-up above:
file it, then put its key here)`. Until a write has run, nothing in the paste file says it has:
the session comment names the follow-up by its summary, `out of scope, follow-up: <its
summary>`, and by its key once it is created.

## Merging two tickets

Two tickets that ask for the same thing, or one whose scope holds the other's, are merged rather
than one simply closed: one is kept, and everything only the other holds moves onto it first, so
no requirement, criterion, decision or context is lost.

- **Which is kept** is the person's choice, asked with a recommendation: the one further along
  (its status, an assignee, a linked pull request), otherwise the one whose description holds
  more of the content, otherwise the older key. In `ticket-draft` it is step 3's choice.
- **Read both in full**, each with one `source-reader` running `ticket <key>`, or from the blocks
  the skill already holds: description, comments and links. List what the closed ticket holds that
  the kept one does not: a requirement, a criterion, a boundary, an open question, a decision or
  context in a comment, a document, a link, and a field the kept one leaves empty. A fact the two
  state differently is an Open Question on the kept ticket, its options naming each ticket's
  position, never a side picked. A ticket a block lists as `Withheld:` is merged only once the
  person clears it: ask its question first, and plan nothing from it before.
- **The plan's items**, in the plan's order:
  - on the kept ticket, the `Original request` comment when it has none, then its description
    with each listed fact folded in where the format puts it, ending `(from <KEY>-NNNN)`;
  - each empty field the closed ticket fills, the estimate excepted (Estimates), now and after; each
    link of the closed ticket the kept one lacks, made again on the kept one;
  - on the kept ticket, a session comment, `Merged from <KEY>-NNNN` and one line per fact moved;
  - on the closed ticket, a `duplicates` link where `jira_get_link_types` lists that type and
    `relates to` otherwise, and the move to the abandoned role's status, the comment it carries `Merged into
    <KEY>-NNNN` with the same lines.
- **Nothing is deleted.** The closed ticket keeps its description, comments and links; its links
  are not removed, since a removed link is a write only the person asks for (Writing to Jira).

## Estimates

How the project estimates, its scale and its reference tasks, is `tracker.md`'s.

A skill gives an estimate in the session and in the `.review/` context page only; it never puts
one into the field block, the description or the estimate field. A person who wants it in the
ticket types it.

## Copy-paste output

When a ticket is drafted or edited for a person to paste, give two blocks:

```
Summary:     <one line, starting with a verb, at most twelve words>
Issue type:  <type>
Component/s: <from the live list>
Epic Link:   <KEY>-NNN (<epic name>), or none
Priority:    <priority>
Due date:    <YYYY-MM-DD, or none>
Links:       <link type> <KEY>-NNN (<summary>), one per line
```

The block holds values only. Why a field is none, that an epic is a proposal, or that a link
replaces one already on the ticket goes in the context page's Actions proposed. Then the
description in the format, as "The description format" renders it. Wiki markup, not Markdown: `h1.`/`h2.` headings,
`*` bullets, `#` numbered lists, `{{code}}` for identifiers, `{code}...{code}` for blocks,
`[text|url]` for links.

After `ticket-draft` has run, a second block follows the description, after a line of dashes
and headed `Comment to post`, for the person to paste as a comment before any other this
session adds:

```
Original request, before the ticket session, by <name>, <date>
<what a person wrote before any agent touched the ticket, in its words>
```

The comment is a readable copy of that text, not a byte copy: its words, URLs and list items are
kept as written, in their order, and its markup and link syntax are put right so Jira stores and
shows it cleanly, such as a list marker's spacing, a bare link's brackets or a stray escape. No
word, URL or list item is added, dropped, reworded or reordered; `<ticket>.original.txt` keeps the
raw text.

When that text is a pull request body `pr-create` wrote, the first line ends `(body written by
pr-create)`, and when it is a follow-up ticket's description (A follow-up ticket), `(follow-up
written by ticket-draft)`: the comment is still the baseline, but agent-written.

The earliest comment opening `Original request`, or the older `Original ticket`, case aside, is
the human baseline the monthly revision reads, whatever comments came before it; the description
is the settled text. A ticket that already has one gets no second.

Then, after another line of dashes, a block headed `Session comment`, pasted last, one per
`ticket-draft` pass. It is the ticket's history, which the status line only summarizes:

```
ticket-draft session, <YYYY-MM-DD>, by <name>: <n> answered, <n> open
Added: <one line each, from the context page's What changed>
Removed: <...>
Reworded: <...>
Decided: <the question> — <the answer> (<who>)
```

A `settle` pass opens `ticket-draft settle, <YYYY-MM-DD>, by <name>`, adding `, from <repo>#<n>
thread <id>` when its answers came from a pull request thread, and lists the answers it folded in
as `Decided:` lines and each departure it records as `Departed: <what the ticket asks> — <what
was done instead>, because <why> (<who>)` (`ticket-draft`'s `settle.md`, "A departure"). Every line reads to someone in Jira: none names the `.review/` context page
or For planning, so a check moved out of a criterion is `the check, out of criterion <n>`. A
`Decided:` line that sends work to a follow-up names it by its summary, `out of scope,
follow-up: <its summary>`, until it has a key, never as filed. A `reformat` pass opens `ticket-draft reformat, <YYYY-MM-DD>, by <name>`,
and its next line is `No requirement changed` when no answer changed one. A list with nothing in
it is left out.

The person files any follow-up tickets first (A follow-up ticket), then pastes the fields one by
one, then the description, then `Comment to post` as a comment, then `Session comment`. Where the
server's write tools are there, the skill makes these writes itself through a write plan instead, as
"Writing to Jira" says, and the paste file holds only what the plan did not write.

## Writing to Jira

A skill writes to Jira through a write plan, `${CLAUDE_SKILL_DIR}/write-plan.md`: every write a
pass proposes, shown as one numbered list, approved once with any items dropped, then run in
order and read back. Two skills make one: `ticket-draft`, for the ticket it drafted, the tickets a
split creates, its follow-up tickets, a merge, and the links and fields between them; and
`ticket-audit`, for the actions its sweeps propose, a merge included. Where the write tools are there, writing is the default and pasting
the alternative; anything a plan does not write is handed over to paste, as "Copy-paste output"
sets out. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there. A plan holds to all of this:

- **Show it first.** Every item says the ticket, the tool and exactly what it writes: a field's
  value now and after; a description or a comment in full, as the ticket will show it; a link's
  two tickets and its type; a transition's status before and after; an assignee before and after.
  The write tools take Markdown and store it as wiki markup, and wiki markup sent to them is
  mangled: send Markdown, converted and checked as the plan file says. A posted comment may not
  be editable or deletable, so say so before one is written.
- **One yes per plan, to exactly what it shows.** A yes to a draft, a sweep or an earlier plan is
  not a yes to this one, and a changed item shows the plan again.
- **What a plan may hold:** creating a ticket with its fields; changing a summary, description,
  component, priority, due date, label or epic; a comment; a link; a status change, closing a
  ticket included; an assignee. Never the estimate (Estimates). A status change or an assignee is
  an item like the rest, shown now and after with its reason, and nothing moves without the
  plan's yes. An assignee is a name the person gave, or one a source the item cites names, such
  as a milestone, never a guess. The move from the filed status to the approved one is the ticket writer's approval (The
  ticket workflow), proposed only when the person asks for it.
- **Only when the person asks for it in their own words**, as its own write with its own yes,
  never in a plan: deleting an issue, a comment or a link, editing a posted comment, and moving a
  ticket to another project.
- **Read it back.** After the plan runs, read each ticket it touched and say what landed, with
  its key. A failed call is reported with its error verbatim and is not retried with other
  arguments unasked.
- **A subagent never writes.** It returns the proposed items, and the skill that ran it asks.

The plugin's `hooks/atlassian-gate.sh` allows a write when the main session makes it and the
approval record the plan writes at the person's yes, `.review/jira-approval.json`, lists that tool
on that target for this session, and asks at every other Atlassian write: one no record lists, one
a subagent makes, one a plan cannot hold, an update that uploads local files, and any write to
Confluence. Claude Code's own `ask` rules
still prompt at each call they match (the README, "Permissions").

## JQL that works

`tracker.md`'s JQL and saved filters for the project; with none, these, `<KEY>` its key:

- Open work: `project = <KEY> AND statusCategory != Done`
- Text across summary and description: `project = <KEY> AND text ~ "kernel coverage"`
- Recently closed (for duplicates): `project = <KEY> AND statusCategory = Done AND resolved >= -180d`

Search wide, then read the ten closest in full: summaries alone miss duplicates written in
different words.

## Never

Write an estimate into Jira, into `<ticket>.jira.txt`, or into anything committed (Estimates).
Invent a component, an epic key or a link target: take
each from Jira. Put an internal Jira or Confluence link into a repository for which
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field public` does not print
`false`, as `writing`'s `short.md` says.
