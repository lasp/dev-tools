# Revise a published page

`revise <page ID | URL> [what changed]` brings a process page, how-to or guide in line with how
things are done now: a step the team changed, a tool replaced, a proposal now in use, a command
that no longer works. It runs in place of the skill's steps and uses its Reads, its "How the page
reads" and its gates, with `using-confluence`'s "Revising a page" for the reads and the write.

1. **Read the page** as "Revising a page" steps 1 and 2 say, into `.review/process/<page ID>/`.
2. **Find what changed.** From the person: what they say changed, asked for in one turn when the
   invocation gives nothing. From the sources, as the skill's step 2: pages and decisions newer
   than the page's last-modified date that touch its steps, tickets that changed the process, and
   for each command or option the page names, whether the code still holds it. Process changes
   live in people's heads, so a page with no finding from the sources is not current until the
   person says so.
3. **Show what has drifted**, at most ten lines, each with the page's words quoted beside what
   says otherwise and its source; and the Status row, when a proposal is now in use or the page
   is retired. Then the purpose: when nothing touches it, quote it and ask whether it still
   holds, in the same turn; when the page has none, or a change touches it, run the skill's step
   3 gate. Nothing is drafted before the purpose is confirmed. A changed step goes through the
   skill's step 4.

   Ask **Fix all of it** (Recommended), **Choose what to fix**, or **Stop**, which keeps
   `page.md`.
4. **The shape.** A page in `template.md`'s shape for its kind keeps it. A page in another shape
   keeps its own unless it hides the purpose or the steps from a reader, or mixes kinds, when the
   turn proposes the sections, or the split into pages, that would fix it; the person decides,
   with no option marked recommended.
5. **Choose the write**, as "Revising a page" step 3 says.
6. **Draft and review**, as the skill's step 7: each changed section in full, or the whole page in
   `draft.md`, with `Last reviewed` moved to today. A flow diagram whose roles, steps, order or
   branches changed goes back through `/lasp-dev:drawio` with its exported XML, if the person
   gives it, or as a new diagram to place.
7. **The gate**, under `using-confluence`'s "Writing to Confluence": each write as a diff against
   `page.md`, what each write drops, and the prompt at each call. Ask **Write it** (Recommended),
   **Change it**, **Paste it myself**, or **Stop**.
8. **Write**: read the version again, and when it moved, read, diff and ask again. Then each
   section write in order, each only after the one before it landed, or the one whole-page write,
   with `content_format: markdown`, `content_file` the absolute path of the draft (inline
   `content` from the same file when the server refuses the path) and a `version_comment` naming
   this skill. A failed write, or a no at the hook's prompt, hands over what it did not write,
   and every section after it, to paste. Then "Revising a page" step 4, and give the URL and the
   new version.
