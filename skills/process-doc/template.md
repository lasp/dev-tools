# The page's sections, by kind

A catalog for each kind, not a form. Every page has the Status table and Purpose, and its kind's
required sections, in this order, so a reader who knows one page finds the steps on the next.
Optional sections appear when the page has content for them. A section the content needs and
the catalog lacks is added where a reader would look for it, under a plain name.

Every section heading is `##`, and its own subheadings `###`, so `revise`'s section write stops at
the next section. No two headings share their text. No heading is left empty and no line says
only "TBD": an unknown is a line saying what is not known and who would know.

Only the fenced blocks are the page. The notes after them are for the skill and are never
written to the page.

## Every kind

```markdown
## Status

| | |
|---|---|
| AI assistance level | 5/5 (not read by a person) |
| Owner | <mention> |
| Status | <In use since YYYY-MM | Proposed | Retired, replaced by <link>> |
| Applies to | <the team, the repositories, or the product and its version> |
| Last reviewed | <YYYY-MM-DD> |

## Purpose

<One to three sentences: what a reader can do or knows after following this page, and why it
exists. Then who follows it and when they come to it.>

<When it applies and, where a reader might expect otherwise, when it does not.>
```

## `process`: how people work together

Required: Roles, Steps. Optional: Inputs and outputs, Exceptions, Tools, Related pages.

```markdown
## Roles

| Role | Who | Does |
|---|---|---|
| <role> | <mention, a team, or "anyone"> | <one line> |

## Steps

<Flow diagram: caption line naming it.>

### 1. <Stage, named as an action>

<Who does it, what it needs, what it produces, and how they know it is done.>

## Exceptions

- <The case, and what happens instead.>

## Tools

| Tool | Used for |
|---|---|
| <tool, linked> | <the steps that use it> |

## Related pages

- <Title, link, and why a reader would go there.>
```

## `how-to`: one task

Required: Before you start, Steps. Optional: Check it worked, If something goes wrong, Related
pages.

````markdown
## Before you start

- <Access, tools and versions the reader needs, each with how to get it.>

## Steps

1. <One action, imperative.>

   ```
   <exact command, with <placeholders>>
   ```

   <What the reader sees when it worked.>

## Check it worked

<How the reader confirms the task is done.>

## If something goes wrong

| What you see | Why | What to do |
|---|---|---|
| <message or symptom> | <cause> | <fix, or who to ask> |
````

## `guide`: a software or data product

Required: Getting started, and a section per task a user comes to do. Optional: Reference,
If something goes wrong, Getting help, Related pages.

```markdown
## Getting started

<The shortest path to a first result: access, install, one example run, and what it produces.>

## <A task a user comes to do, named as an action>

<A short how-to: numbered steps, exact commands, the result.>

## Reference

| <Option, field or file> | Meaning | Default |
|---|---|---|
| <name> | <one line> | <value> |

## Getting help

<Where to ask, and what to include.>
```

## Notes

- **Status**: `In use since` is the month the person says practice began, not the page's date;
  a proposal is `Proposed` until the person says it is in use, which `revise` records. The AI
  assistance level and the owner are as `writing/references/page.md`'s "The header" sets.
- **Purpose**: the confirmed text from `facts.md`, word for word.
- **Steps**: each from step 4's confirmed skeleton. A stage of a process that is itself a task
  links its how-to rather than holding its commands.
- **Reference**: from the product's code or documentation, through the investigator, each row
  checked; a row nobody could check is left out and named to the person.
