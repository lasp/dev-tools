# The page's sections

A catalog, not a form. Every page has the required sections, in this order and at this heading
text, so a reader who knows one page finds the purpose and the interfaces on the next. The
optional sections appear when the system has content for them, in the order below unless another
order reads better for this system. A section the system needs and this catalog lacks is added
where a reader would look for it, under a plain name; a pipeline's How it works may be "Processing
steps", a library's interfaces its public calls.

Every section heading is `##`, and its own subheadings `###`, so `revise`'s section write, which
replaces everything from a heading to the next at its level or higher, stops at the next section.
No two headings share their text. No heading is left empty and no line says only "TBD": an
unknown is a line saying what is not known and who would know.

Only the fenced block is the page. The notes after it are for the skill and are never written to
the page.

```markdown
## Status

| | |
|---|---|
| AI assistance level | 5/5 (not read by a person) |
| Owner | <mention> |
| Reflects | <repository> at <short commit>, <YYYY-MM-DD>; or "as described by <name>, <YYYY-MM-DD>" |
| Last verified | <YYYY-MM-DD> |
| Design docs | <links, or none> |

## Purpose

<Two to four sentences: what the system does, for whom, and what would be missing without it.>

<Optional: what it does not do, where a reader might expect it to, and what does.>

## Interfaces

<One sentence on where the system sits in the larger system.>

<Context diagram: caption line naming it.>

| Interface | Other side | Direction | What crosses | Started by | Contract |
|---|---|---|---|---|---|
| <name> | <system, store or person> | in, out or both | <data, request or action, with its format> | <event, schedule, person> | <schema, API, convention or procedure, linked> |

### <An interface that needs more than its row>

<What a reader needs to use it or to debug it: an example, the error cases, the limits.>

## How it works

<One sentence: how it works, in one line.>

| Component | Does | Code |
|---|---|---|
| <name> | <one line> | <repository path> |

<The main path through the components in prose, in the order things happen: why each waits on the
one before, what it hands on.>

## Data

<What the system stores, where, in what format, for how long, and who else reads it.>

## Running it

<Where it runs, what starts it, what it needs to run (configuration, credentials by name, other
services), how anyone knows it is working, and what happens when it fails: retries, what a person
does, where to look.>

## Limitations

- <What it cannot do or does badly today, with the ticket when one exists.>

## Why it is this way

- <A decision a reader would otherwise question, in one line, linked to the design doc or ticket
  that made it.>

## Glossary

| Term | Meaning |
|---|---|
| <term> | <one line> |

## Related pages

- <Title, link, and why a reader would go there.>
```

## Notes on each section

- **Required**: Status, Purpose, Interfaces, How it works. A system so small that How it works
  is one sentence puts it under Purpose and drops the heading.
- **Status**: `Reflects` names the code the page describes, each repository at the commit read,
  and each branch or pull request about to merge as `<repository> <branch or #NNN>, about to
  merge`; for a system with no code, whose description it is. `Last verified` is the date the
  page was last checked against that state, which `revise` moves. The owner is a mention, as
  `using-confluence`'s "Macros and mentions" says. The AI assistance level is `comment-style.md`'s
  "AI assistance level", 5/5 until the person names another.
- **Purpose**: the confirmed text from `facts.md`, word for word.
- **Interfaces**: runtime interfaces, people included, as the skill's "When to run" says. A
  tracking ticket or a list of tickets goes in as a Jira macro.
- **Running it**: names configuration and credentials, never their values.
- **Limitations** and **Why it is this way**: from the code, tickets, design docs and the person;
  never an opinion of the skill's.
