---
name: writing
description: >
  Reviews or rewrites prose a person reads (tickets, pull request and commit bodies, docs) for
  structure and clarity without changing a fact. Use when asked to "review this doc", "tighten
  this README", "make this clearer" or "check the wording". Not for review comments, docstrings
  or code comments.
argument-hint: "[text | file]"
metadata:
  author: lasp-dev
  version: 1.2.1
---

# Writing for a reader

Two jobs. **Structure**, so every ticket and pull request reads the same way and a reader who
has learned the shape finds what they need without reading everything. **Clarity**, so each
sentence says one specific thing and claims no more than the evidence supports.

## Options

| Option | Default |
|---|---|
| Text | Pasted text or a file path |
| Kind and audience | Read from the text; a doc, ticket, pull request body or formal deliverable, and who reads it |

Every rule here passes one test: would a reader who has never met the author understand the text
faster, or more exactly, because of it? Nothing here is about sounding like anyone.

Every question to the person follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## Facts do not change

Moving, splitting, trimming and rewording are the tools. Changing a number, a name, a unit, the
strength or scope of a claim, or anything a reader would act on is not. When a clearer sentence
would need a fact the text does not contain ("robust to what?"), ask for it; never supply one.
A rewrite that alters what the text asserts is a defect, however much better it reads.

## Structure

Which sections a document has belongs to its format: the ticket format in `using-jira`, the pull
request sections in the repository's `.github/PULL_REQUEST_TEMPLATE.md`, and in an adopted
repository `pr-create/body.md`, a document's own template. This section sets how each of those sections reads.

- **Summary first.** The opening says what changes and why, in a sentence or two. A reader who
  stops there knows whether the document concerns them.
- **Each section leads with its point.** A pull request's Context opens with one sentence that
  names the affected function and what goes wrong in it; how the function works follows. A
  ticket's opens with why the work is needed. A "Key design choices and
  open questions" bullet opens with the thing to look at, a decision with what was decided.
  Detail follows.
- **Consequence before cause.** For a bug, a finding or an impact: what goes wrong and for whom,
  then the cause, then the fix. A reader learns whether to worry before learning why.
- **Fit the structure to the content.** A list for parallel items, a table for items compared
  across the same attributes, prose for reasoning that connects one fact to the next. A list of
  labeled items is fine when the items are parallel; a paragraph cut into bullets is not.
- **One idea per bullet**, on one line where it fits. Reasoning that needs more gets its own
  bullet or section rather than a longer one.
- **The same word for the same thing** throughout, matching the shared
  `<standard>/terminology.md` (`<standard>` is what `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints, and a
  repository it exits 1 for, ending "the repository has no standard", has none; any other exit 1 is a failed read), the
  template's labels and the code's names.
- **Detail on demand.** What most readers skip, such as logs, full test lists and counts, goes
  last or in a collapsed block.
- **Length follows the change.** A one-line fix gets a short ticket and a short body. Size caps
  belong to the skill that owns the format, where it has one.

## Clarity

- **The first sentence carries information.** No sentence that sets a scene before the subject
  arrives; delete it and start at the next one.
- **Be specific.** Name the function, the file, the number with its unit, the failure. A
  concrete claim can be checked and needs no adjective to prop it up.
- **Check every number the text states against what it counts.**
- **Claim what the evidence supports.** An absolute names what enforces it, and one hedge sits on
  the part that is uncertain, as `references/prose-standards.md`'s "Overclaiming" says.
- **Show why a point matters instead of saying that it does.** "It's important to note that" and
  its relatives delay the point; delete the announcement and the reason usually stands.
- **Plain words, domain terms kept.** Marketing vocabulary hides what the code does. Radiometric
  calibration, boresight and ECEF are the names of things and stay.
- **Say a point once.** No restating the question before answering it, no closing recap.
- **Not a telegram**, as `references/prose-standards.md`'s "Over-correction" says.

`references/page.md` adds what a Confluence page a person reads to learn something needs, its
header and how it reads; `architecture-doc` and `process-doc` write to it.

`references/short.md` is this skill's own excerpt of Structure and Clarity for a commit body or
a pull request body, which `commit` and `pr-create` read instead of this file.

Flagged words, phrases, structures and worked rewrites are in `references/prose-standards.md`.
Read it before reviewing; a flagged word passes its truth test there or goes.

## Conventions

Contractions, addressing the reader as "you", heading style and formality follow the document's
existing convention, then the repository's, then the template's. A formal deliverable follows its
own template; formality never licenses a paragraph of context before the first real sentence.

Spelling follows the repository's own codespell configuration; a skill never introduces a
dictionary the repository does not run.

Links, and which repositories are public, follow `references/short.md`, "Links and public
repositories", the one copy of that rule; content marked as controlled follows its "Controlled
content".

**Rule wording.** A rule's wording is a general principle in two to four lines: what a diff must
show, and why. When it does not apply is the ledger entry's `Do not flag:` line, never the
wording. The case it came from is named on the ledger entry's
evidence line, never in the wording, and no pull request number, file name or symbol appears in
it, so the rule reads the same to a change that looks nothing like the first one.

## Reviewing existing text

A person invokes this skill on text or a file. Short text, a diff or a file under about 200
lines is reviewed here; a longer document goes to the `prose-reviewer` agent, so this session
never has to read it whole.

**Inline.** Report each change with its location, the original quoted, and the replacement:

```
docs/guide.md:14  sets a scene before the subject
    In today's world of satellite data processing,
  → delete; the paragraph starts at its second sentence
```

Mark each one **mechanical** (the text holds everything the change needs: structure, a flagged
phrase, a word that fails the truth test), **question** (it needs a fact the text lacks; the line
ends `? <question>`) or **advisory**: sentence and paragraph lengths all the same, more than one
em dash in a short document, a sentence that would read oddly aloud, a denser format than the
content needs. Get the questions answered first, then close with the counts and one
`AskUserQuestion`: **Apply all** (recommended), **Choose rows**, or **Apply none**, keeping the
report. Edit nothing before the answer.

When the person declines a change for a reason that would hold for any text (the word is the
domain term, the rule misfires), say so in one line and offer `/lasp-dev:revise correct`
with that reason.

**Delegated.**

1. **Spawn** `prose-reviewer` with the document's absolute path, its kind and audience, and the
   path `${CLAUDE_SKILL_DIR}/references/prose-standards.md`. It returns a plan of mechanical
   changes, questions and advisory notes, and edits nothing.
2. **Answer** every question you can from what this session already knows, such as a fact about
   the code or the term the repository uses.
3. **Ask the person** the rest: whether a section is wrong rather than badly written, what a
   claim's scope is, anything that turns on intent. A guessed answer becomes a confident wrong
   sentence.
4. **Show** the settled plan, one line per change, with the answers you supplied, and ask as the
   inline review does. On approval, resume it with `SendMessage` to its agent id; if it cannot be
   resumed, spawn a fresh `prose-reviewer` with the approved plan and the answers, which re-reads
   the document and applies only those.

