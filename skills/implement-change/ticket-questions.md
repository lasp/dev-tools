# A ticket with Open Questions

`implement-change` reads this at step 1 when `source-reader`'s block says the ticket has an Open
Questions section. No question crosses into the build unanswered.

- **Answered for now.** A question the ticket answered for now moves on as a provisional
  decision: its answer, `Revisit because:` from the ticket's `Open because:`, `Affects:` and
  `Final when:`. List them all and carry them in one confirmation; the person may change any.
- **No answer.** Say what is unknown, then do the research it needs: read the code, compare the
  ticket's `Options:` with what the code shows, or talk it through, and give your recommendation.
  The person decides it, final and recorded in the brief's Assumptions as their decision, or for
  now as a provisional decision. Ask a question each, at most four to a widget.
- **Settle first.** Either kind may instead be settled in the estimation meeting: stop, and name
  `/lasp-dev:ticket-draft settle <key>` for after it.

The closing summary says the ticket still needs settling whenever any question was decided here.
Provisional decisions go into the plan's `## Provisional decisions`.
