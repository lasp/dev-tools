# Revise a published page

`revise <page ID | URL>` brings a page that describes a system up to date with the code: what
changed since it was written, an interface added or gone, a section the page lacks. The page may
be one this skill wrote or any older page on the system. It runs in place of the skill's steps
and uses its Reads, its "How the page reads" and its gates, with `using-confluence`'s "Revising a
page" for the reads and the write.

1. **Read the page** as "Revising a page" steps 1 and 2 say, into
   `.review/architecture/<page ID>/`.
2. **Check it against the code**, as the skill's step 2 does, with every statement the page makes
   about a repository as the investigator's claims. A page with no `Reflects` row describes the
   code at its last-modified date; say so.
3. **Show what has drifted**, at most ten lines, each with the page's words quoted beside the
   code's `file:line`: statements that no longer hold, interfaces the code has and the page does
   not, interfaces the page names and the code no longer has, and required sections the page
   lacks. Then the purpose: when the page has one and nothing found touches it, quote it and ask
   whether it still holds, in the same turn; when it has none, or a finding touches it, run the
   skill's step 3 gate. Nothing is drafted before the purpose is confirmed.

   Ask **Fix all of it** (Recommended), **Choose what to fix**, or **Stop**, which keeps
   `page.md`. A changed interface goes through the skill's step 4.
4. **The shape.** A page in `template.md`'s shape keeps it. A page in another shape keeps its own
   unless that shape hides the purpose or the interfaces from a reader, when the turn proposes
   the sections that would, with what moves where and what has no home; the person decides,
   with no option marked recommended, since the shape is theirs. A clear page that differs from
   the template is left as it is.
5. **Choose the write**, as "Revising a page" step 3 says.
6. **Draft and review**, as the skill's step 7: each changed section in full, or the whole page in
   `draft.md`; `Last verified` and `Reflects` moved to what was read. A diagram whose content
   changed goes back through `/lasp-dev:drawio` with its exported XML, if the person gives
   it, or as a new diagram to place.
7. **The gate**, as the skill's step 8 and `using-confluence`'s "Writing to Confluence": each write
   as a diff against `page.md`, what each write drops, and the prompt at each call. Ask **Write
   it** (Recommended), **Change it**, **Paste it myself**, or **Stop**.
8. **Write**: read the version again, and when it moved, read, diff and ask again. Then each
   section write in order, each only after the one before it landed, or the one whole-page write,
   with `content_format: markdown`, `content_file` the absolute path of the draft (inline
   `content` from the same file when the server refuses the path) and a `version_comment` naming
   this skill. A failed write, or a no at the hook's prompt, hands over what it did not write,
   and every section after it, to paste. Then "Revising a page" step 4, and give the URL and the
   new version.
