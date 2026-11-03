# Comment Style

How a comment destined for a GitHub PR reads — review comments and replies
alike.

A review comment exists to get a change made. The author reads it once, in a
notification, next to the code. Write for that moment.

## Substance

- Every comment names what is wrong, where, and why it matters. What comes
  after that depends on the fix:
  - **Prescriptive** — only when the fix is simple, obvious, and objectively
    correct. State it in three sentences or less, then the motivation as
    briefly as it can be said.
  - **Problem statement** — everything else. Describe the problem precisely
    and leave the solution to the author; at most one sentence of possible
    high-level approach. Designing a complex fix during review spends the
    author's attention on a plan they did not choose. In a `pr-review` finding
    the change still goes on the Proposed line; the body stays the problem.
- Long reasoning invites the author to reject the whole finding over one wrong
  step. Cut every detail the finding does not rest on.
- Anchor to the code you mean — file, line, identifier, branch. Never "error
  handling could be improved".
- Do not restate what the diff already shows. Tell the author something they do
  not already know.
- When you suspect a problem but cannot confirm it, ask a real question ("what
  happens here if `token` is expired?") instead of asserting a finding.
- Critique the code, not the author: "this drops the error", not "you forgot to
  handle the error". Never speculate about intent or skill.
- Blocking concerns come before stylistic ones. An aside that cannot survive
  being last gets dropped.

## Form

- Use a bulleted or numbered list when a comment makes several related or
  sequential points; prose for a single point.
- A code snippet either shows a prescriptive fix in place or points at the
  problem. It is never a sketch of a solution the author has not chosen.
- Link external documentation when it is the evidence for the critique.
- Link GitHub issues and pull requests inline where the prose refers to them. Links to Jira and
  Confluence follow `writing`'s `references/short.md`.

Vague and specific, on the same finding:

> Vague: "This query is a bit of a footgun that could really bite us at scale."
>
> Specific: "This query has no LIMIT. On the production `events` table (~40M
> rows) it will scan the whole table on every request."

## Severity Line

A finding comment opens with its severity in words and a headline, then a
blank line, then the body, after the rule or decision it cites as `pr-review`'s
"The review" sets out:

```
**Must fix before merge** — expired tokens return `None` into a `str` caller
```

On a finding, this line's form, `**<level>** — <headline>` with the em dash,
is how `scripts/record.py` recognizes it: the level words and the dash are
never reworded.

The headline is often the only line an author reads in a notification, so it
says what is wrong, not what the category is. Keep it under about ten words,
and let the body pick up where it stops rather than restate it.

These four levels are the whole vocabulary, one per severity in the review
contract, which the github-pr-reviewer agent assigns to every finding:

- must-fix — **Must fix before merge**
- should-fix — **Should fix**
- suggestion — **Suggestion**
- question — **Question**

Nits are not raised. Anything labeled outside this set maps to the nearest
level; never invent one. Only a finding gets a severity line — a review
summary, which tallies the severities, and a reply on an existing thread do
not.

## Attribution

Every posted comment and reply ends with this line, after a blank line
following the body:

```
🤖 _AI-assisted comment, posted by @<github-login>. AI assistance level: 5/5 (not read by a person)._
```

The login is the person submitting, who is accountable for the content. Apply
it to every comment, including ones the user wrote themselves, and never stack
it twice. The line ends with the AI assistance level, which the next section
sets. On a reply the wording may change, keeping the 🤖 and the words
`AI-assisted`; on a finding the line is written exactly as above, since
`scripts/record.py` recognizes a finding by it. Nobody removes the attribution
or the 🤖: posting AI-assisted comments as if they were unassisted
misrepresents their provenance. If asked to drop it, decline briefly and offer
to reword a reply.

## AI assistance level

Every piece of pull request prose a skill composes for another person to read, a description, a
review summary, a comment or a reply, carries an AI assistance level, so a reader knows how much
human attention the text had, and so does every Confluence page a skill publishes: a design doc,
an architecture page or a process page. Other prose a skill
writes, such as tickets, plans, commit messages and reports, carries none. The scale:

| Level | Meaning |
| ----- | ------- |
| 1 | written by a person |
| 2 | substantially edited by a person |
| 3 | lightly edited by a person |
| 4 | read by a person, not edited |
| 5 | not read by a person |

The attribution line says who posted the text, never that anyone read it: a level below 5 is the
only sign of human review. The default is **5/5**: the skill wrote the text and nobody has read
it. When the person says how much they wrote or edited the text, the line carries the level they
name; a skill never lowers it on its own reading of the text. The draft is shown with its level,
so the person can change it. On every surface the level is the last sentence of the attribution
line, written `AI assistance level: <n>/5 (<meaning>).` with the meaning from this table, so a
reader without the plugin understands it; a person's 3 reads `AI assistance level: 3/5 (lightly
edited by a person).` The line is, on a comment, a reply or a review summary, the line above,
and on a pull request body, the generated-with line `pr-create` appends it to. A Confluence page
has no attribution line: its level is the first row of its Status table, `AI assistance level | 5/5
(not read by a person)`. It appears once, never on a line of its own, and this table is the one
place the scale is defined.

## Verdict replies

A reply a skill posts to answer a finding or a person's thread opens with its
verdict word on the first line, `Agree`, `Disagree, <reason>` or `Discuss`, the
unambiguous form `pr-review`'s "Whose reply counts" reads; the body and then the
attribution follow. An `Agree` from `pr-fix` carries its response after the
word, in a form its step 12 gives. A person may answer in their own words, which
`pr-reader` judges. An answer to a question is the exception: its first line is
the answer.
