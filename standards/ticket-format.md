# The ticket format

The plugin's ticket description, the same whatever tracker files it. A tracker writes it in its
own markup: `using-jira`'s "The description format" says how Jira's wiki markup renders each part,
and a GitHub issue takes it as Markdown, as shown below. A project's standard may adapt it in its
`tracker.md`, which the tracker's skill reads. The fields a ticket carries and the statuses it moves
through are `docs/contracts.md`'s "The ticket shape".

Motivation is the big picture a reader needs before the requirements: why the ticket exists and
what its outcome reaches. Its why is the person's: while the question asking for it is open, its
first line is `Why: Open Question <n>`. A ticket drafted from a pull request after its change opens
Motivation with the line `Written after the change, from pull request <repo>#<n>`, and its The
code today describes the base branch, before the change. Where the ticket sits among other work is
in its fields and links, the epic or parent, the due date and the issue links, not in the
description: the related tickets it names are the ones that take work out of its scope. The survey
of the code comes after the scope, under The code today, where the lines that open `Touches:`,
`Used by:` and `Most of the change:` are the footprint. Sections in this order, under the status
line:

```markdown
ticket-draft: drafted <YYYY-MM-DD> by <name> · updated <YYYY-MM-DD> by <name> · open questions: <n>
# Motivation
<why the work is needed, and why now: the problem or the need and who has it, in one or two sentences, as the source or the person gave it; a milestone it serves is named here only as the why-now>

**Impact:**
- <one thing the outcome reaches beyond the code: a product, people or an operation that changes when it lands, or waits while it does not>

# Driving Requirements
<the point of the ticket: what the work must accomplish, in one or two sentences or up to three
 bullets, close to a user story>

## Technical Requirements
- <a design choice or constraint someone outside this change would notice, with its source: (<name>, <date>), (Data Product Definition Design), (D-nnn)>
- <a boundary: what the change must leave as it is, such as a module or a product, with its source>

## Acceptance Criteria
1. <the input or condition>: <the observable result>
2. <...>

# Related Out of Scope Tickets
- [<ticket id> <its summary>](<its URL>)

# The code today
**Touches:** <the modules the change lands in, with their symbols, and the user-facing docs that describe the interface it changes; "new module <path>" for new code; no tests or changelog>
**Used by:** <what calls them: the pipeline step, each consumer that does from the repository's list, which `<plugin root>/skills/downstream/SKILL.md`'s `check` step 2 gives, by repository and a file only when it is the single caller, or "nothing outside this repository">
**Most of the change:** <the module and function, or "spread across <what>: <why>"; left out when it would repeat Touches>
**Already true:**
- <one fact the change relies on; a claim of the source the code disproves, said plainly>
**Missing:**
- <one thing the code does not do yet>

# Considerations
- <only what no other section carries: a gotcha, a rule (R-) or decision (D-) the ticket bends or a developer would not think to apply, a context entry (`context: <file>`) whose subject the change touches, never the nearest one, what holds if unmerged work it depends on does not land>

# Open Questions
1. <the question, one sentence a person outside the session can answer>?
   - **Options:** <a, one clause on its cost> · <b, ...>
   - **Answered for now:** <the answer, when the person gave one to revisit>
   - **Open because:** <the person's reason>
   - **Affects:** <the criteria, sections, repositories and plan choices that turn on it>
   - **Settles it:** <the measurement, the page, or whose call>
   - **Raised by:** <name>, only when a person raised it

# Related Docs
- [<the document's title>](<its URL>)

# Departures
- Departed: <what the ticket asks> — <what was done instead>, because <why> (<who>)
```

**The status line.** A ticket `ticket-draft` wrote opens with one line saying where it stands:
when it was drafted and by whom, when it was last updated and by whom, and how many Open
Questions it holds. `updated` names the latest pass after the first, a draft, a settle or a
reformat, and is left out until there is one; a `settled` an earlier line carries is dropped. Each
pass rewrites the line in place rather than adding one, and its session comment is the record of
the pass. `by` names the person running the session and each person they say drafted it with
them, `by <name> and <name>`, and the session comment names the same people. A follow-up
ticket's line is its own (the tracker's skill's "A follow-up ticket"). The line is not counted in the
description's length.

**Lines, not paragraphs.** Each line holds one fact. Where a labeled line would hold more, its
facts become bullets under the label, as Impact's are. Prose is kept for reasoning that joins one
fact to the next, such as Motivation's opening, and runs at most three lines.

**Related Out of Scope Tickets.** Every entry is a ticket that exists, or that the same write
plan creates: a follow-up ticket, or another piece of the same split, which each piece lists. It
is linked by its id and summary, so a good summary is what the reader sees; the ticket is also
linked in the tracker, as related, or as blocking when one must land before the other. Adjacent
work with no ticket is not listed: it gets a follow-up ticket, or, when the change must not touch
it, a boundary under Technical Requirements, or it is left out. The section is left out when it
is empty.

**Departures.** Where the built work left a requirement, criterion or boundary above, and keeps
doing so, as `ticket-draft`'s `settle.md` records it: by default a `Departed:` line in a settle
pass's session comment, and only for one a reader must not miss, a line here. Either way the
item is held to its departure, not its text above, by every skill that reads the ticket. Left out
when there is none.

**Related Docs.** Each page, document or outside guidance the ticket cites, by its title as a
link, once. A requirement or a question cites its source by title, and the link is here; a
document whose URL no source gave is listed by title, ending `(link not found)`. Left out when
the ticket cites none. A `context:` line under Considerations is a file in the plugin, not a
document, and stays there.

**Readers and length.** A ticket has three readers: the developer who builds it, the reviewer
who checks the pull request against its Acceptance Criteria, its boundaries and its Related Out
of Scope Tickets, and the estimation meeting that answers its Open Questions. A sentence none of
them would miss is cut; one a reader needs stays. Length follows the change, not a number: a
larger change has more facts its readers need. **The cut pass**, once a description is written:
read it again and ask of each sentence whether any of the three would miss it; cut what none
would, check each fact is stated once, and hold each criterion to the two-implementations test
(Acceptance Criteria). The `.review/` context page keeps the detail the
ticket leaves out.

**One home per fact.** Each fact is stated once, in the section that owns it, and another section
refers to it ("Open Question 2") rather than restating it. Motivation owns why the work is needed
and its effect beyond the code, leaving the code's consumers to Used by; the fields and links,
where the ticket sits among other work; the footprint, where the change lands and who calls it in
code; the lines after it, what is true now and what is missing; Technical Requirements, the
design choices, the constraints the goal cannot be met without and the boundaries, left out when
they would only restate Driving Requirements, with a minor assumption (a boundary case, an edge
value) one line here rather than an Open Question; Related Out of Scope Tickets, the work other
tickets own, what callers in other repositories must do included; Open Questions, the undecided
choices; Related Docs, the links. A name or an id may appear wherever a different fact needs it;
a number appears once.

**Design choices, not implementation.** A ticket says what must be true and the design choices
that shape it, never how the code does it. A choice is design-level when someone outside the
pull request would notice it changing: another repository, a product's user, operations or the
science team. That covers a contract (a public signature, a file, product or event format, an
error rather than a warning, when a failure surfaces), where code lives across repositories, a
technology or service the team will run, a science definition, and a release decision. Which
function, class or library, the algorithm's internals and the tests' layout are implementation,
and stay on the `.review/` context page for planning. A design choice comes from a person, in the
source or an answer, or from a recorded decision, and carries its source; the drafting agent
adds none of its own. Planning re-checks each one, and a better option goes to the person rather
than replacing the choice.

**Acceptance Criteria.** Each criterion is an outcome observable at the change's boundary, an
input and what comes out or what raises, that traces to a Driving Requirement or a design choice.
It says what is true of the product, or what a caller sees, in their terms: a product attribute,
a file format or a public function is the contract and may be named, and a match to a reference
product states its tolerance. How the outcome is checked is not a criterion: no test or test
type, fixture, clock, parsing recipe or private function, and no "observed by" clause; that goes
to the context page's For planning. Two different reasonable implementations both meet a
criterion; one that only a single implementation meets is a route, which goes to For planning,
or to Technical Requirements when a person chose it. Variants of one behavior are one criterion. A
criterion whose reason is not obvious carries it in one clause ("or the inventory definitions stop
loading"); one that pins behavior already true but untested says `(exists, untested)`. What the
repository's rules require of every change (the unit lane passes, a changelog entry, a version
bump) is not a criterion. More than about six is a sign of two tickets, or of implementation
written as criteria.

Considerations and Open Questions are omitted when empty, never left as a bare heading. Acceptance
Criteria is what the reviewer compares the pull request against (`ticket/AC-n`), and the
boundaries and Related Out of Scope Tickets are what `ticket/scope` names.

**Open Questions.** Each question is worth answering while the ticket is drafted, and again at
every later turn, but a ticket may keep one open: sometimes nobody knows yet, an answer invented
to pass a readiness gate is worse than an honest open question, and the implementation often
decides it. A question ends one of three ways. Answered, it is folded in where it applies and
removed. Answered for now, it is still open: the ticket is written with that answer, marked `(for
now, see Open Questions)` where it is used, and the entry stays with `Answered for now:`, so the
plan, the pull request's description and the review track it until it is settled. Kept open, the
entry says why in `Open because:`. Each skill that reads the ticket later offers to settle an open
or for-now question when it holds the evidence: `implement-change` at its brief, where it carries
an answer for now as a provisional decision and researches one with no answer with the person
until it is decided, and again at the diff; `pr-review` where the diff gives the
evidence that decision's `Final when:` names; and `ticket-draft settle` whenever answers arrive,
from the estimation meeting, a comment, a pull request thread or the person.

Older tickets predate the format and many are one line. Read what is there and map it onto
these sections; do not treat a missing section as a defect of the ticket.
