# Settle

`ticket-draft settle <key>`, run whenever answers to a ticket's Open Questions arrive, from the
estimation meeting, a comment or the person, or `settle <key> <thread id>`, run by `pr-fix` on a
reopened design or a kept `ticket/` finding: fold answers into the ticket, as `using-jira`'s "The
description format" sets out for Open Questions, and record a departure, below. It needs the
Atlassian server, as SKILL.md's Reads say.

**A departure** is recorded, not folded in: work that left the ticket's design, criteria or scope
and should keep doing so, from a reopened design, an agreed `ticket/` finding, or the person. The
ticket goes on saying what was asked; the record says what was done instead and why, and a
reader holds the item to it (`using-jira`, "The description format", Departures). Step 3 asks how it is recorded. A
reopened design that changes the plan but leaves the ticket's design, criteria and scope as they
are records nothing: the pass says so and ends.

1. **Read the ticket** with its comments, with one `source-reader` running `ticket <key>`, and
   compare its description with `.review/context/<ticket>.jira.txt` as last written. Where they
   differ, as when a teammate edited the description in Jira after the paste, list each
   difference and ask which text to keep: Jira's (Recommended, since it is what the team has
   read) or the local draft's. When `<ticket>.jira.txt` is absent on this machine, the ticket as
   fetched is the text to settle: write it to `<ticket>.original.txt` as for a ticket settled
   before, create the context page with its heading, after its `Controlled:` line when the ticket was cleared, and only What changed, and say once that the draft's page
   was not on this machine.
   A ticket not in the current format, `using-jira`'s "The description format", is asked first, unless the pass only records a departure as a comment, which leaves the description as it is: **Reformat and settle** (Recommended), which runs
   `reformat.md` steps 2 and 3 before step 2 here, in one pass with one write plan, or **Settle
   in its layout**, which folds each answer into the sections the ticket has.
2. **Gather the answers**: from the person in the session, from comments on the ticket since
   the draft, or, with a thread id, from that pull request thread, read from the dump under
   `.review/threads/`. Show each answer beside its question, and a departure as what the ticket
   asks beside what was done instead and why, and ask which section an answer goes to when that is
   not plain.
3. **Fold each in**, as a requirement, a design choice with its source, a criterion, a boundary,
   a Related Out of Scope Tickets line, a follow-up ticket, Motivation or The code today, and
   remove the question; an answer for now is folded in as SKILL.md step 6 folds one, and one still unanswered stays. Each answer goes into the page's What
   changed as a decision.
   A departure is asked first: **Comment on the ticket** (Recommended), a `Departed:` line in the
   `Session comment` with the description untouched; **Append to the description**, the same line
   in its Departures section (`using-jira`, "The description format"), the text above it
   unchanged but the status line, for one a reader of the ticket must not miss; or **Rewrite the
   ticket**, folded in as above, only when the person says the ticket's intent was wrong.
4. **Review and write**, as SKILL.md steps 7 and 8, the write plan included: step 1's ticket
   block says whether the ticket has its `Original request` comment, and without it the comment
   is the first write, as for any ticket. A pass whose only change is a departure recorded as a
   comment writes the `Session comment` alone: nothing replaces the description, so it needs no
   `Original request` comment, its status line stays, `<ticket>.jira.txt` holds the description
   as fetched with the `Session comment` after it, and the closing summary says the description
   was left as it is. Otherwise the status line's `updated` takes this pass's
   date and name, and its count of open questions is the new one. The `Session comment` is a
   settle pass's, as `using-jira` opens it, naming the thread when the answers came from one. For a ticket still
   in the filed status, the closing summary says the next step is a ticket writer's approval and
   the move to the approved status, which questions left open do not by themselves hold back
   (`using-jira`, "The ticket workflow"; the statuses are the profile's `jira.roles`).
