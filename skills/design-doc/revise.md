# Revise a published design doc

`revise <page ID | URL> [change]` changes a design doc already on Confluence: a key for a `to
create` row, a status, a decision made since, an answered open question. It runs in place of the
skill's steps.

1. **Read the page** with `confluence_get_page` in Markdown. If it warns it is controlled,
   stop at the warning and ask as `<plugin root>/skills/writing/references/short.md`, "Controlled content" says, naming only the page, where it sits and the
   warning and describing nothing of it, not even where you stopped; write no `page.md` until the
   person clears it.
   Otherwise, before anything else, write the whole read, unabridged, with the Write tool to
   `.review/design/<page ID>/page.md`, with `Page: <id> · Version: <n>` as its first line, after
   the `Controlled:` line when the page was cleared: it is the "before" of every diff. Read it once
   more with `convert_to_markdown: false`, the storage read, and note, under each heading,
   what the Markdown read drops: the macros (`ac:structured-macro`, by name: drawio, jira,
   code), layouts (`ac:layout`) and inline comments (`ac:inline-comment-marker`); and any heading
   that holds a macro or whose text formatting splits, and any heading text that appears twice.
   **A page in `template.md`'s shape** has only the template's `##` headings, in its order, each
   once, and no layouts; a section the template makes optional, or one the person declined on a
   reformat, may be missing. **A page not in that shape**, such as a design doc written before
   this skill, gets one question before any other, with no option marked recommended, since the
   shape is the person's call:
   - **Keep its shape**: the change lands one section at a time; say which of its headings it
     lands under.
   - **Reformat it**: one whole-page write puts the page in the template's shape, and drops its
     macros (DrawIO, Jira), layouts, inline comments, mentions, images and dates from the new
     version.

   On Reformat, show which template section each of its headings lands in and what has no home.
   A missing Summary, Goals and non-goals or Context goes through the skill's step 3 gate, since
   those come from the frame only. A missing Design or Work breakdown is offered through steps 4
   and 5, not required: one the person declines stays off the page, named under Open questions,
   and the page is in the template's shape from then on. Write the reformatted page to
   `.review/design/<page ID>/draft.md`.
2. **Ask for the change** when the invocation gives none. A change that reopens the frame, a new
   goal or a problem the doc does not state, goes back to the skill's step 3 with `frame.md`, or
   a new frame from the page when there is none: the frame gate holds in revise too.
3. **Draft it.** Each changed section in full, as its heading will hold it, its subheadings
   included; on Reformat, the change is folded into `draft.md`, so one write carries both. Update
   `Last updated` in the Status table with any change, and ask whether the AI assistance level
   still holds when the change replaces text the person wrote.

   **What a section write replaces.** It finds the first heading, at any level, whose text
   pieces joined with no spaces equal `heading_text`, keeps that heading, and replaces every
   element after it inside the same parent (the page, a layout cell or a macro body) up to the
   next heading there at its level or higher. A heading nested inside a following layout, macro
   or table does not stop it, so a section followed by a layout loses the whole layout. Read
   that span from the storage read, not the Markdown section: it is the "before" the gate shows,
   and what it holds is what the write drops.
   - **A new section**, such as the first Decisions and Trades or Open questions, goes in with the
     section before it on the page: that section's write carries its own text unchanged, then the
     new heading and body, and that section's macros and inline comments are named as dropped.
   - **A section to remove**, or a changed section the write cannot reach exactly, is the
     person's to do in the editor; the gate names it and hands it over. That is a section whose
     heading text appears twice on the page, whose heading holds a macro (such as an anchor) or
     has its text split by formatting, or whose span holds a layout, or a macro or table with
     headings inside.
4. **The gate.** `ToolSearch` for the write tool, `confluence_update_page_section`, or on
   Reformat `confluence_update_page`; without it, say that the server is read-only, in one line,
   or not connected, as `<plugin root>/skills/work/servers.md` sets out with the writes as what is
   lost, and hand over the sections, or `draft.md`, to paste. Otherwise show every
   section in the one message that asks, each once, as `using-confluence`'s "Writing to
   Confluence" says:
   - **Each write**: the section as a diff, before and after, one per call in the order they
     run; or on Reformat `git diff --no-index` of `page.md` against `draft.md` with each macro the
     second read listed.
   - **What each write drops**: each macro in the span a section write replaces is gone from the
     new version, and each inline comment there loses its place in the text; name each, with its
     section. Every write, the section write included, also flattens every mention and profile
     macro on the page to `@Name` text and rewrites every image, as `using-confluence`'s "Writing
     to Confluence" says. Page history keeps them all.
   - **The prompts that follow**: Claude Code asks again at each call, as the plugin's hook asks
     at every Confluence write. A no there stops the run: what landed stays, and the rest is
     handed over to paste.

   Ask **Write it** (Recommended), **Change it**, **Paste it myself**, or **Stop**. When a
   section to write holds a macro or an inline comment, **Write the rest** (Recommended) takes
   Write it's place: it writes every other section and hands that one over to paste, since an
   edit in the editor keeps both. That section is written, dropping them, only when the person
   says so in their own words; it is never one of the options.
5. **Write**, as `using-confluence`'s "Writing to Confluence" sets out: read the version again,
   and when it moved, read, diff and ask again. Then one `confluence_update_page_section` per
   section the yes covers, `heading_text` its heading, `content_format: markdown`,
   `version_comment` naming this skill, each only once the one before it has landed. On
   Reformat, one `confluence_update_page` instead, with the page's title, `content_file` the
   absolute path of `draft.md` (inline `content` from the same file when the server refuses the
   path), `content_format: markdown` and the `version_comment`. A failed write, or a no at the
   hook's prompt, hands over what it did not write, and every section after it, to paste. Read
   the page back and give the URL and the new version.
