# Reformat

`ticket-draft reformat <key>`: rewrite a ticket that already holds its requirements in the current
format, `<plugin root>/standards/ticket-format.md`, as `using-jira`'s "The description format" renders it in Jira, keeping every fact and asking only where the format
needs what the old text cannot supply. It runs no search and no investigation unless the person
asks, and needs the Atlassian server, as SKILL.md's Reads say. It suits any ticket that already says
what the work must accomplish and how to tell it is done, whoever wrote it and whatever its
headings. A ticket that is mostly free text, with no requirements or criteria to carry, gains
nothing from the mapping: say so in one line and offer the full draft, `ticket-draft <key>`.

1. **Read the ticket** with its comments and links, with one `source-reader` running `ticket
   <key>`. Write its description, verbatim, to `.review/context/<ticket>.original.txt` with the
   Write tool, and keep its `Original request comment:` line, as SKILL.md step 1 does.
2. **Map it.** Every fact in the old text lands in one place in the new, or on a list of what
   was removed, each with its reason: said twice, or how the code is built, which goes to the
   context page's For planning. Nothing else is cut, and nothing is added that the old text, its
   comments or the person did not say.

   | Old | New |
   | --- | --- |
   | Context's code survey: Touches, Used by, what is true and missing | The code today |
   | The code today, with `Already true:` and `Missing:` as prose | The same, one bullet per fact |
   | Context's why and effect | Motivation and Impact |
   | Where it fits, and the epic, milestone or neighbors named in the text | The epic; a neighbor it builds on or follows, `depends on`, any other `relates to`; a due date from a month the text names; each one Jira lacks an item of the write plan. A milestone's name goes into Motivation's why-now sentence, with no label of its own |
   | Not this ticket, an entry with a ticket | Related Out of Scope Tickets, and its link when Jira lacks it |
   | Not this ticket, an entry with none (`candidate`, `not covered`) | Step 3's scope question |
   | A criterion that says how it is checked (`observed by`, a test, a fixture) | The outcome alone; the check to For planning |
   | A document cited, with its link in the text | Related Docs |
   | Driving Requirements, Technical Requirements, a criterion that names no check, Considerations, Open Questions | As they are, in the format's order and wording, an Open Question's fields each on its own line |
   | A section the table does not name, such as a hand-written ticket's Technical Considerations or Out of Scope | By what each line holds: a requirement, a boundary, a consideration, an out-of-scope entry or a question |

3. **Ask only what the format needs**, together, as SKILL.md step 6 asks:
   - a why the old text does not give: Motivation's question, with no recommendation, as
     SKILL.md step 4 raises it;
   - each Not this ticket entry with no ticket: SKILL.md step 6's scope question, a follow-up
     ticket recommended;
   - each criterion whose outcome alone is a route, which only one implementation would meet:
     SKILL.md step 4's over-constraint question. A criterion whose rewrite only deletes the
     check's words, changing no other word, is shown before and after, and not asked; one whose
     outcome takes words from the check, or loses or tightens a word of its own, is asked, with
     both shown: keep the rewrite, or keep the outcome's own words;
   - each document named without a link: its URL, or listed ending `(link not found)`.

   Nothing about the requirements themselves is asked; the person who wants them examined runs
   `ticket-draft <key>`. The same widget offers **Re-check The code today**: one
   `ticket-investigator` for this repository, given the ticket's claims about it, each claim that
   no longer holds a question. Recommended when the code it names has changed since the ticket's
   last pass, `git log --since=<date> -- <the Touches paths>` printing a commit, `<date>` the latest
   on its status line, or its created date when it has none.
4. **Review and write**, as SKILL.md steps 7 and 8, the write plan included, with two
   differences. The context page is kept: its The ticket, Actions proposed and What changed are
   replaced, the checks moved out of criteria are added to For planning, and the rest stays, as
   the planner reads it; with no page on this machine, one is created with only those sections,
   as `settle.md` step 1 does. The closing summary states no estimate. What changed lists
   what moved, what was rewritten and what was removed, with the reason for each, and every answer
   from step 3. The `Session comment` is a reformat pass's, as `using-jira` opens it. The status
   line keeps its `drafted`, and its `updated` names this pass; a ticket with none gets one,
   `drafted` naming the ticket's reporter and created date. The plan holds the `Original request`
   comment when the ticket has none, the description, the links and fields from step 2, and the
   follow-up tickets from step 3.
