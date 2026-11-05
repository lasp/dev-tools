# Dials

Every number here is the only copy; a skill names the Dial rather than repeating its value.

The defaults every adopted repository uses; a repository's ledger header may state its own rule
budget, which wins. `revise` and the planning skills read them here.

Rows marked *starting value* were set on 2026-10-02 without data and are tuned again at each
revision. One step either way is the two values in the Either way column; the revision's report
lists, under "Dials at the margin", the proposals each would gain or lose there. A threshold on a
rule, a candidate or a proposal that this table does not state is not applied. The `context/`
entries' cap and retirement are `context/README.md`'s, the vocabulary's length is
`terminology.md`'s, and a measure the revision only reports, such as lint passes per build, sets
no threshold.

| Dial | Default | Either way |
| --- | --- | --- |
| Rule budget | 300 lines, the ledger with its wording, as one repository loads it: a rule tagged for other repositories, a check-tier entry and the held candidates do not count; `rule_lint.py`'s budget gate checks it | — |
| Admission | one merged pull request with a review thread, a reply, a review summary or a conversation comment a person wrote in their own words, the pull request's author included, since an author reviewing their own pull request is the first reviewer, for a cluster the Recurring ask Dial admits; or, whatever that Dial counts, one general statement of kind `rule` by a person, quoted, that the guidance tally prints `admit` (`docs/contracts.md`, "The guidance tally"), or a principle or a request a named person states in a pasted note; never for something a configured tool can check, a one-off design question, or a bare restatement of a decision (a rule may implement one, as the Bounds of `onboard`'s `first-rules.md` say); and, for a new, reworded or promoted rule, the gates in `rule-bar.md` | — |
| Established | agreed findings on the rule in two different merged pull requests, whoever wrote them or agreed, the pull request's author included, as `ratchet_counts.py`'s `distinct-prs-agreed` counts them; a rule that implements a decision carries that decision's status instead, as `rule-bar.md`'s `status` gate checks | — |
| Provisional expiry | 20 checked merged pull requests since admission without being established, fired or not: pull requests a review or a build ran the rules on (`ratchet_counts.py`'s `checked-since-admitted`) | — |
| Revision | monthly, or at ten merged pull requests | — |
| Suggestions per review | 7 | — |
| Questions per review | 5 | — |
| Group ticket session | estimate 5, and every epic | — |
| Split before starting | estimate 8 | — |
| Agree rate | agree / (agree + disagree); discuss and unanswered are reported, not counted (starting value) | — |
| Minimum settled firings before a rate is read | 6, since admission or the last rewording (starting value) | 4; 8 |
| Low agree rate | below 50% at the minimum: propose a rewording; still below at the next revision: propose retirement (starting value) | 40%; 60% |
| Established expiry | 40 checked merged pull requests and no firing (`checked-since-fired`; starting value) | 30; 50 |
| Established and unfired at expiry | propose demotion to the prose tier, as `skills/revise/apply.md` step 1 writes it, or a check, before retirement (starting value) | — |
| Recurring ask | the same concern in 2 merged pull requests, accumulated across revisions; a cluster that admits on a single statement does not need it (starting value) | 1; 3 |
| Candidate drop | no new evidence in 6 months (starting value) | 4 months; 8 months |
| Revision floor | 5 records since the last revision; below it the report only (starting value) | 3; 7 |
| Unanswered share | a rule's findings unanswered in more than a third of its firings less its `unlabeled` ones, whose severity label could not be read: propose a do-not-flag sentence or a severity change (starting value) | a quarter; a half |
| Contested | a rule contested more than once in the window: name it and what the disagreements shared (starting value) | once; three times |
| Corrected | a rule corrected twice in the window: propose a rewrite or a do-not-flag sentence, never a promotion (starting value) | once; three times |
| Ticket candidates | a constraint in three or more ticket baselines is a candidate rule; a thing typed into free text three or more times is a candidate template field (starting value) | two; four |
| Missing-record alarm | above a third of the window's merged pull requests (starting value) | a quarter; a half |
| Deep review | a public signature, a product definition or manifest, a schema, an epic; or any change a person raises to deep | — |
