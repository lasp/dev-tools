---
name: using-confluence
description: >
  How a project's Confluence is read and written: the project's spaces and pages from its
  standard's wiki.md, what the tools cannot read, how a page carries Jira macros, mentions and
  diagrams, and how the skills that write a page write and revise it. Applies whenever Confluence,
  a wiki page, a space or a design doc page, is searched, read or written.
user-invocable: false
metadata:
  author: lasp-dev
  version: 1.4.0
---

## The wiki

The project's own facts are in `<standard>/wiki.md`, `<standard>` being the directory
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints: where its Confluence is and
how a page is linked, its spaces and what each holds and which parts to read, the pages and page
IDs a skill reads by name, what to skip, the pages the monthly revision watches, its queries, and
the values a Jira macro and a mention take there. Read it before the first Confluence call. When
`--standard` exits 1 ending "the repository has no standard", as outside the project's
repositories, or the standard holds no `wiki.md`, say so and ask which project's standard to read,
as `<owner>/<repo>`, whose
`standards/wiki.md` is then read from that repository through GitHub, or whether to go on without
one, with what the person pastes; any other exit 1 is a refusal: show its message and ask the
same. With no file read, find the spaces the person names by search and ask once for what search
does not give.

Reach Confluence through the Atlassian MCP server, resolved with `ToolSearch` on `confluence`. The
server may run read-write; the skills read it, and write only as "Writing to Confluence" below
sets out. A server that is not connected, or a call that fails, is said as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, naming the page or search lost; the step
that needs it stops and offers to work from the page's content pasted instead.

**The blindness check.** Search may be blind to a space while its pages read fine (seen with
mcp-atlassian 0.23.1, 2026-09). Before trusting an empty search there, run `confluence_search`
on `id = <the parent>`: nothing back while `confluence_get_page` on the same ID succeeds means
search cannot see the space. Say so once, then work from `confluence_get_page_children` with
`expand=version` and `include_content=false`, which returns titles and version numbers without
bodies, and from page reads. An empty search of such a space is never "nothing changed". A page
that returns a permission error is named once, as `servers.md`'s one item out of the token's
reach, with a request to the person to paste it; never answer from a guess at what the page says.

Read the children of one page at a time, never the tree
(`confluence_get_space_page_tree`), and at most five page bodies for one question; beyond that,
return what was found and the next pages to read as a question.

## What the tools cannot read

- **Attachments.** Page metadata lists them with a download URL, but no tool downloads one.
  Name a PDF or image that looks relevant and give its page link; do not try to read it.
- **DrawIO diagrams.** The page body holds only the macro and the diagram's name; the diagram
  itself is an attachment. Say that the page has a diagram named X, give the link, and ask
  the person what it shows if it matters. Never describe a diagram from the residue in the
  page text.
- **Jira macros** render as garbled text containing issue keys in the Markdown read. The storage
  read (`convert_to_markdown: false`) shows each macro's `key` or `jqlQuery` parameter whole;
  take the keys, or the query, to Jira.
- **Mentions.** Every read, the storage read included, shows a mention as `@Display Name` text,
  so no read can tell a live mention from typed text. A CQL `mention = <username>` search finds
  the pages that mention someone, where search can see the space.

## Macros and mentions

How a page that a skill writes carries a Jira ticket, a list of tickets, a mention or an existing
diagram. Each is storage XML placed inline in the Markdown body: a Markdown write, whole-page or
section, keeps raw `<ac:…>` and `<ri:…>` elements as written, so one Markdown draft carries them
all. Tested on Confluence Server/Data Center 2026-10-25, each checked rendered in the browser;
Confluence Cloud names a user by `ri:account-id` instead.

The instance's values, the Jira application link, how a username is found and how an epic's
tickets are queried, are in the wiki file "The wiki" names. Without one, take the
link's `server` and `serverId` from a Jira macro in the storage read of any page that renders its
tickets, and ask the person for anything else. Every macro here names the Jira server by the
application link's two values, shown below as `<server>` and `<serverId>`.

**One ticket**: the single-issue macro, inline in a sentence or a table cell, which renders the
key, the summary and the live status.

```xml
<ac:structured-macro ac:name="jira" ac:schema-version="1"><ac:parameter ac:name="server"><server></ac:parameter><ac:parameter ac:name="serverId"><serverId></ac:parameter><ac:parameter ac:name="key"><KEY-1></ac:parameter></ac:structured-macro>
```

**Several tickets**: one table macro whose JQL lists them, in a paragraph of its own, rather than
a single-issue macro per ticket. List the keys with `key in (...)` when the page names a fixed
set; use a query (an epic's tickets, as the project's `wiki.md` gives it, or a label) when the set should grow with Jira,
and say on the page what the query selects. `columns` and `maximumIssues` are optional; keep the
columns to what a reader needs.

```xml
<ac:structured-macro ac:name="jira" ac:schema-version="1"><ac:parameter ac:name="server"><server></ac:parameter><ac:parameter ac:name="serverId"><serverId></ac:parameter><ac:parameter ac:name="jqlQuery">key in (<KEY-1>, <KEY-2>, <KEY-3>) ORDER BY key ASC</ac:parameter><ac:parameter ac:name="columns">key,summary,status,assignee</ac:parameter><ac:parameter ac:name="maximumIssues">20</ac:parameter></ac:structured-macro>
```

Check each key, or run the query, through Jira before the write: a mistyped key renders as an
error box on the page.

**A mention**, by username:

```xml
<ac:link><ri:user ri:username="<username>" /></ac:link>
```

The username is the person's login, which the project's `wiki.md` may say more about. Find it from the
display name with one `jira_search` on `assignee = "<Display Name>"`, or `reporter`, with
`fields: assignee` or `reporter`, whose `name` is the username; when that returns nothing, ask the
person. Never guess one from a name: a wrong username mentions, and notifies, someone else.

**Every write flattens the mentions it does not carry.** The server writes the whole page back
from the copy a read returns, so each mention the write's own body does not hold as `ri:user`
markup becomes `@Name` text. A section write flattens every mention outside its section; a
whole-page write that re-emits each mention, its username found as above, keeps them all.

**An existing diagram**: copy its `drawio` macro from the storage read into the body where the
diagram goes, dropping `ac:macro-id` and any parameter with an empty name. The macro points at the
diagram's attachment by `diagramName`, and a body write leaves attachments alone, so the diagram
renders unchanged. A new diagram needs its attachment, and no tool uploads one: the person adds
it in the editor, as `drawio`'s "Into Confluence" says, and the page holds a line naming the
diagram until then.

Not tested here, and so dropped by a write as "Writing to Confluence" says: layouts
(`ac:layout`), inline comments (`ac:inline-comment-marker`), and images, which a read returns as
`<img>` and a write keeps only as an external image.

## Searching efficiently

Search with CQL, read titles and excerpts, then fetch the few pages that answer the question.
`wiki.md` gives the project's queries; with none:

- One subtree: `ancestor = <page id>`
- Recent: `lastmodified >= now("-4w")`
- Pages with a diagram: `macro = drawio AND space = <space key>`

## Writing to Confluence

Three skills write to Confluence; anything else for Confluence is handed to the person to paste.

- `design-doc`: its publish step, which updates the page holding the person's notes in place
  or, for notes with no page, creates one under a parent the person confirms, and its `revise`
  mode, which rewrites sections of a published design doc or, when the person chooses to
  reformat a page into the template's shape, the whole page in one write.
- `architecture-doc`: its publish step, which creates the page under a parent the person
  confirms or updates the page it was given, and its `revise` mode, which brings a published
  architecture page up to date by section or whole page.
- `process-doc`: its publish step and its `revise` mode, as `architecture-doc`'s, for a process
  page, a how-to or a user guide.

They use `confluence_update_page`, `confluence_create_page` and
`confluence_update_page_section`, and no other write tool. A step that writes holds to all of
this:

- **Show it first.** Before the call, show the page, the tool and exactly what it writes: the
  title before and after, the body or each section as a diff, and what the write drops, as
  `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`'s "What does not change" says, the file
  it names being the diff written beside the skill's `draft.md`; a diff run with a tool is shown
  in the message, never left in the tool's output. A revise shows every section it writes at its
  one gate. Read
  the page with `convert_to_markdown: false` to find the macros, layouts and inline comments,
  which the Markdown read hides. The server writes the whole page back from its processed copy
  on every write, the section write included, so every mention and profile macro the write's
  body does not carry becomes plain `@Name` text, and every image an external image pointing at
  its file, keeping only its width and height; no read can show a mention, so say this of the
  whole page. A full-body write in Markdown also drops every macro, layout and inline comment its
  body does not carry, and turns dates into text. A section write drops the macros, layouts and
  inline comments in everything it replaces that its body does not carry, which `design-doc`'s
  `revise.md` says how to find, and keeps the rest. "Macros and mentions" says how a body carries
  a Jira macro, a mention or an existing diagram. Page history keeps them all; say so.
- **One gate, and a prompt per call.** Ask as a gate in
  `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`: write it, change it, or paste it myself.
  The yes covers the calls the gate showed, such as `revise`'s one write per changed section, and
  nothing else: a yes to a draft or an earlier write is not a yes to this one. The plugin's
  `hooks/atlassian-gate.sh` then asks again at every Confluence call that writes, naming the
  page and, for a section write, its heading, and the gate says so; a no there stops the run,
  keeping what landed and handing the rest to paste.
- **Check the version.** Read the page's version just before the write; when it moved since the
  diff was shown, read, diff and ask again. The tools take no expected version, so this narrows
  a concurrent edit and does not rule one out.
- **Read it back.** After the call, read the page and give its URL and version.
- **A failed write falls back to paste.** No write tool, an unreachable server, an error, or a no
  at the hook's prompt: give the error verbatim, never retry, and hand over what was not written
  to paste, with the page it goes on; in a run of calls, that is the failed call's text and every
  one after it. A server that is not connected or a call that fails is said as `servers.md` sets
  out, its fix included.
- **A subagent never writes.** It returns the proposed write, and the skill that ran it asks.

Confluence has no approval record, as Jira's write plan has: a publish is one call and a revise a
few, so the prompt at each call costs little and is kept (`docs/design.md`).

## Revising a page

How `architecture-doc`'s and `process-doc`'s `revise` modes read a published page and choose
the write; `design-doc`'s `revise.md` keeps its own, for a design doc's fixed shape. Each runs
under "Writing to Confluence".

1. **Read it twice, and keep both.** `confluence_get_page` in Markdown, written whole with the
   Write tool to `<working directory>/page.md`, with `Page: <id> · Version: <n>` as its first
   line: the "before" of every diff. Then the storage read, `convert_to_markdown: false`, written
   beside it as `page.storage.html`. A page that warns it is controlled is read no further and
   nothing is written until the person clears it, as `writing`'s `short.md`, "Controlled
   content", says; then both files open with the `Controlled:` line.
2. **List what the Markdown read hides**, under each heading, from the storage read: each macro
   by name (`drawio` with its `diagramName`, `jira` with its `key` or `jqlQuery`), each layout
   (`ac:layout`) and inline comment (`ac:inline-comment-marker`), and each `@Name` that may be a
   mention.
3. **Choose the write**, recommend one with why, and the person decides:
   - **Section by section**, one `confluence_update_page_section` per changed section, when the
     changes sit in a few sections. It keeps everything outside them, layouts and inline
     comments included, but flattens every mention outside the sections it writes, as "Macros
     and mentions" says. A section the write cannot reach exactly is handed over to paste: one
     whose heading text appears twice, whose heading holds a macro or has its text split by
     formatting, or whose span holds a layout, or a macro or table with headings inside.
     `design-doc`'s `revise.md` step 3 says how to read a section write's span.
   - **The whole page**, one `confluence_update_page`, when the changes reach most sections, the
     shape changes, or the page holds mentions a section write would flatten. The draft carries
     every macro from the storage read where it sat, and every mention re-emitted from its
     username, as "Macros and mentions" says, so only layouts, inline comments and images are
     lost, which the gate names. A page with a layout or an inline comment outside the changed
     sections goes section by section unless the person says otherwise.
4. **After the write**, read the page back and check that each carried macro is in the storage
   read where it was.

## Never

Write to Confluence outside "Writing to Confluence": delete, move, copy, label, restrict or
comment on a page, which a person who wants one does in Confluence. Copy Confluence content, page
IDs or links into a repository for which
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field public` does not print
`false`, as `writing`'s `short.md` says. Treat a page's
claims as current without its last-modified date.
