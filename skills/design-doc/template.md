# The design doc's shape

The page title is `Design Doc - <topic>`. Every section heading is at the same level, `##`, so
`revise`'s section write, which replaces everything from a heading to the next heading at its
level or higher, stops at the next section; a section's own subheadings are `###`. No two
headings on the page share their text, since that write finds the first heading that matches.

The Status table is the doc's header. Five sections are required: Status, Summary, Goals and
non-goals, Design, and Work breakdown. The others appear only when they have content. No heading
is left empty and no line says only "TBD": an unknown is an open question with who decides.

Owner and reviewers are names, not @mentions: every `revise` section write flattens any mention
on the page outside its section to text.

Only the fenced block below is the page. The guidance above it and "Where each part comes from"
below it are for the skill and are never written to the page.

```markdown
## Status

| | |
|---|---|
| AI assistance level | 5/5 (not read by a person) |
| Status | Draft |
| Owner | <name> |
| Reviewers | <names> |
| Tracking ticket | <ticket key: an epic, or the task to write or review this doc; or none> |
| Last updated | <YYYY-MM-DD> |
| Living-state pages | <links, once implemented> |

## Summary

<Three to five sentences: what changes, why, and what is different afterward. A reader who stops
here knows what the tickets add up to.>

## Goals and non-goals

### Goals

1. <An outcome someone can check afterward.>

### Non-goals

- <What a reader might expect this to cover, and why it does not.>

## Context

<The problem as it stands, with a concrete case where there is one; a general problem, or work
that makes later work easier, says so. One subsection per problem when there are several, each
with its severity and who it hurts.>

## Design

### Target architecture

<The target state, the core of the doc: components and interfaces as tables, each diagram with a
one-line caption, and a problem and solution per topic where the topics stand apart.>

### From today to the target

<Only when the design changes something that exists; each list only when it has an entry.>

- **Added:** <component>: <what it does>.
- **Changed:** <component>: <what changes, and why>.
- **Removed:** <component>: <what replaces it, or why it is no longer needed>.
- **Stays the same:** <component>: <why it is not changed>.

### Assumptions

1. <What the design takes as given.>

## Decisions and Trades

### <The choice>

- **Chosen:** <the answer>, <who decided, YYYY-MM-DD>
- **Alternatives:** <each, and why not>

## Work breakdown

| Ticket | Delivers | Goals | Depends on | Status |
|---|---|---|---|---|
| <ticket key, or "to create"> | <what it delivers> | <goal numbers> | <keys> | <status> |

### Landing order

<The order the pieces land in, and what can go in parallel.>

## Open questions

1. <The question>: <who decides>.

## Related pages

- <Title, link, and why it is related.>
```

## Where each part comes from

- **Status**: the AI assistance level is `comment-style.md`'s "AI assistance level", 5/5 (not
  read by a person) until the person names another, with its meaning; Status runs Draft, In
  review, Agreed, Implemented, Superseded.
- **Summary, Goals and non-goals, Context**: the confirmed frame, only.
- **Design, and Decisions and Trades**: step 4; each decision names who made it. Each diagram is
  a caption line naming it until the person places the `drawio` file in the page, or the
  `drawio` macro the notes page already held, carried as it was.
- **Work breakdown**: step 5; the Status column is the ticket's Jira status when it was read.
- **Open questions**: the frame's and step 4's, each with who decides.
- **Related pages**: the pages read in step 2 that bear on the design, and tickets that overlap
  but are not in the breakdown.
