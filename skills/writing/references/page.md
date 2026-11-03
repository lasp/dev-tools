# A page a person reads to learn

The rules for a Confluence page a skill writes so that a person can learn something from it: a
system, a process, a task. `architecture-doc` and `process-doc` read this file; their own
rules for their kind of page add to it. `writing/SKILL.md`'s Structure and Clarity govern every
sentence, and `prose-standards.md`'s flagged words apply.

## The header

The page opens with a Status table whose first row is the AI assistance level, `AI assistance
level | 5/5 (not read by a person)` until the person names another, as
`<plugin root>/skills/pr-review/comment-style.md`'s "AI assistance level" sets. The skill never
lowers it on its own reading; it asks whether the level still holds whenever the person edits the
draft or a change replaces text a person wrote. The owner is a mention, as `using-confluence`'s
"Macros and mentions" says.

## How it reads

- **The reader is new.** Each term the reader may not know is defined where it first appears,
  in a clause, or in a Glossary; a name from the code or the team's shorthand is introduced as
  what it is ("the manifest, a JSON file listing a job's inputs").
- **The page answers the reader's question in its first lines.** The Purpose says what this is
  and who it is for, so a reader who opened the wrong page knows within two sentences.
- **Each section opens with its answer**; detail follows.
- **Present tense for what is.** No history ("was moved to"); a planned change is a link to its
  design doc or ticket, not a paragraph in the future tense.
- **The one who acts is the subject.** "The reviewer approves the pull request", not "the pull
  request is approved". Short sentences, one fact each.
- **Pictures for shape, tables for lookups, numbered steps for order, prose for reasons.** A
  diagram shows what connects to what; a table holds what a reader looks up; a numbered list
  holds what is done in order; prose carries why.
- **Numbers carry units and a source**: "about 2 GB a day (October 2026)".
- **One name for one thing**, the project's from `<standard>/terminology.md`, `<standard>` being
  what `python3 "<plugin root>/scripts/profile.py" --standard` prints (a repository it exits 1 for,
  ending "the repository has no standard", has none; any other exit 1 is a failed read), the same in the text,
  the tables and the diagrams.
- **Links over copies.** A fact another page owns is linked, not restated, so it changes in one
  place; tickets go in as Jira macros, as "Macros and mentions" says.
- **Nothing the sources do not hold.** A sentence that needs a fact nobody gave is a question to
  the person, never filled in.
