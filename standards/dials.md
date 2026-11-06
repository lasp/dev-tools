# Dials

Every number here is the only copy; a skill names the Dial rather than repeating its value.

The defaults every adopted repository uses; a repository's ledger header may state its own rule
budget, which wins. `revise` and `onboard`'s first rules read them here. A threshold another skill
applies, such as a review's suggestion limit or a ticket's split estimate, lives in the file that
applies it.

Rows marked *starting value* are tuned again at each revision, against the recall benchmark
(`sandbox/README.md`, "Harvest recall") where it measures them; the Set from column says when each
was set and from what. One step either way is the two values in the Either way column, the next
values to try. A threshold on a
rule, a candidate or a proposal that this table does not state is not applied. The `context/`
entries' cap and retirement are `context/README.md`'s, the vocabulary's length is
`terminology.md`'s, and a measure the revision only reports, such as lint passes per build, sets
no threshold.

| Dial | Default | Either way | Set from |
| --- | --- | --- | --- |
| Rule budget | 300 lines, the ledger with its wording, as one repository loads it: a rule tagged for other repositories, a check-tier entry and the held candidates do not count; `rule_lint.py`'s budget gate checks it | — | 2026-10-02, no data |
| Admission | one merged pull request with a review thread, a reply, a review summary or a conversation comment a person wrote in their own words, the pull request's author included, since an author reviewing their own pull request is the first reviewer, for a cluster the Recurring ask Dial admits; or, whatever that Dial counts, one general statement by a person, quoted, that the guidance tally prints `admit` (`docs/contracts.md`, "The guidance tally"), or a principle or a request a named person states in a pasted note, each then held to its kind's bar (`skills/revise/harvest.md`, "Destinations"); never as a rule for something a configured tool can check, a `tool/` proposal, or a one-off design question, a `question/`, and never for a bare restatement of a decision (a rule may implement one, as the Bounds of `onboard`'s `first-rules.md` say); and, for a new, reworded or promoted rule, the gates in `rule-bar.md` | — | 2026-11-05, the reference month (#83): 22 merged pull requests, 20 records, 18 rule citations, 8 people; most general statements were said once (#78, #80) |
| Established | agreed findings on the rule in two different merged pull requests, whoever wrote them or agreed, the pull request's author included, as `ratchet_counts.py`'s `distinct-prs-agreed` counts them; a rule that implements a decision carries that decision's status instead, as `rule-bar.md`'s `status` gate checks | — | 2026-10-02, no data |
| Provisional expiry | 20 checked merged pull requests since admission without being established, fired or not: pull requests a review or a build ran the rules on (`ratchet_counts.py`'s `checked-since-admitted`) | — | 2026-10-02, no data |
| Revision | monthly, or at ten merged pull requests | — | 2026-10-02, no data |
| Agree rate | agree / (agree + disagree); discuss and unanswered are reported, not counted (starting value) | — | 2026-10-02, no data |
| Minimum settled firings before a rate is read | 3, since admission or the last rewording, counted across revisions, the rate shown with its counts (starting value) | 2; 4 | 2026-11-05, the reference month (#83): 22 merged pull requests, 20 records, 18 rule citations, 8 people: at 6, no rule's rate would be read for months |
| Low agree rate | below 50% at the minimum: propose a rewording; still below at the next revision: propose retirement (starting value) | 40%; 60% | 2026-10-02, no data |
| Established expiry | 40 checked merged pull requests and no firing (`checked-since-fired`; starting value) | 30; 50 | 2026-10-02, no data |
| Established and unfired at expiry | propose demotion to the prose tier, as `skills/revise/apply.md` step 1 writes it, or a check, before retirement (starting value) | — | 2026-10-02, no data |
| Agent guidance expiry | 12 months after an entry's `seen` month with no review seeing the habit again: propose retiring it (`docs/standards.md`, "Agent guidance and data conventions"; starting value) | 6 months; 18 months | 2026-10-02, no data |
| Recurring ask | the same concern in 2 merged pull requests admits a cluster no single statement admits; and the merged pull requests a cluster's people asked on, with those whose agent findings the author changed as asked, set its priority: 1 low, 2 medium, 3 or more high, as `guidance_clusters.py` prints it (starting value) | 1; 3 | 2026-11-05, the reference month (#83): 22 merged pull requests, 20 records, 18 rule citations, 8 people: six themes said in two pull requests, and most agent guidance, were missed while it gated |
| Authorship | per comment: an agent drafted a comment when its own first or last line names an AI tool, as `scripts/record.py`'s `authorship_of` reads it, whoever posted it | — | 2026-11-05, the reference month: per thread, 40 replies were read one way and 7 threads the other (#76) |
| Agent asks the author changed as asked | support for a cluster's priority, never its admission: the guidance tally's `support` lines | — | 2026-11-05, the reference month: a person accepting an agent's finding is a signal (#78) |
| Candidate drop | no new evidence in 6 months (starting value) | 4 months; 8 months | 2026-10-02, no data |
| Revision floor | 5 records since the last revision; below it the report only (starting value) | 3; 7 | 2026-10-02, no data |
| Unanswered share | a rule's findings unanswered in more than a third of its firings less its `unlabeled` ones, whose severity label could not be read: propose a do-not-flag sentence or a severity change (starting value) | a quarter; a half | 2026-10-02, no data |
| Contested | a rule contested more than once in the window: name it and what the disagreements shared (starting value) | once; three times | 2026-10-02, no data |
| Corrected | a rule corrected twice in the window: propose a rewrite or a do-not-flag sentence, never a promotion (starting value) | once; three times | 2026-10-02, no data |
| Ticket candidates | a constraint in three or more ticket baselines is a candidate rule; a thing typed into free text three or more times is a candidate template field (starting value) | two; four | 2026-10-02, no data |
| Missing-record alarm | above a third of the window's merged pull requests (starting value) | a quarter; a half | 2026-10-02, no data |
