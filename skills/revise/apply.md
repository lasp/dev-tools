# Apply

`revise`'s `apply` mode: from the report the group decided on to the diff here and, when the standard lives
elsewhere, the commit in a clone of its repository; `<standard files>`, `<log>`, `<archive>` and
`<context>` are where `revise`'s "The standard's repository" puts them.

Read the report first: in a clone, from the branch's head after `git -C <dir> pull` when
the branch was pushed; with no clone, from `<log>` here. A report with no proposal has nothing to mark: go to step 2, which writes its held
candidates.

**Settle the marks.** The group decides in its own words, wherever it discussed: on a proposal's
`Mark:` line; with a clone, in the draft pull request `prepare` may have opened on the report's
branch, found as step 2 finds it and read through `using-github` (each review comment and its
replies, the reviews' bodies and the conversation comments), with no clone, or a branch never
pushed, there being none to look for; and in meeting notes the driver pastes into
`.review/revision/meeting/`, which `prepare` never reads, so an ask pasted for `prepare` into
`revision/notes/` is not taken for a decision. A review comment belongs to the proposal its
`diff_hunk` ends in, read against the report at the comment's own commit, never the head's line
numbers, which later edits shift. When the branch was pushed and its pull request's threads
cannot be read, the server unreachable or the check for the pull request failing, say so as
`<plugin root>/skills/work/servers.md` words it and ask: **Paste the threads** into
`revision/meeting/`, read in their place, **Go on without them**, the table saying the pull
request was not read, or **Stop**. Read them all, then settle each proposal to one mark:
`accept`, `accept, reworded: "<the words agreed>"`, `decline: <reason>`, `escalate: <reason>`,
`accept, override: <reason>`, `accept, owner: <name>`, `answer: <the answer>`, or blank, deferred;
a held proposal or a change to a live data convention given new words takes both parts,
`accept, reworded: "<words>", override: <reason>` or `accept, reworded: "<words>", owner: <name>`,
and agreed words that hold a double quote write it as a single one. A `reworded:` mark holds the
whole new wording, the agreed change applied to the proposal's text, never only the phrase that
changed. `reworded` is for a proposal
with wording: a rule admitted, reworded, promoted or broadened, and an `A-`, `F-` or `D-` entry;
new words for any other settle it to `unclear`. Or `unclear: <why>`, when what was said does not
settle it. A `Mark:` line with a `discussed:` line beneath it is one `apply` wrote on an earlier
yes, blank ones included: it is settled, read as the group's mark or as deferred, not as
discussion.

Only people's words decide. A bot's reply, and an answer `revise` itself posted, are read for
what they say, never as the group's verdict. A reply a person posted is theirs, however an agent
worded it, when its attribution shows they read it, any level below `5/5`; one at `5/5`, or with
no sign it was read, stays the agent's, as `docs/design.md` explains for the revision's evidence.
A person's reply is read for what it decides, as `pr-review`'s "Whose reply counts" judges a reply
that opens with no word. A proposal settles to `unclear` when people disagree with no outcome, when its sources
disagree (a `Mark:` line and a thread, or two notes), since neither carries a time to order them,
when an accept on a held proposal gives no reason, and when an accept on a change to a live data
convention names no owner. A question a comment asks is answered as
`<plugin root>/skills/revise/discuss.md` says, and settles nothing on its own.

Write the settled marks to `.review/revision/marks.md`, a table of every proposal in the
report's order: its id, the mark settled, and what it rests on, the comment's link, the `Mark:`
line or the note's file, quoted where short; above it, one line naming each file read from
`revision/meeting/`, so a stale one is seen. It is what the yes approves, so the message before
the question shows the table too, or, when it is long, the unclear and reworded rows with the
file named as a link, as `decision-points.md` says of longer text. Then ask:
**Write these marks** (Recommended, when none is unclear), **Change some**, the person naming the
proposal and the mark, or **Let's discuss**. An `unclear` mark is settled with the person before
anything is written, or left blank, deferred, on their word. On the yes, write each mark on its
proposal's `Mark:` line, blank for a deferred one, with a `discussed:` line beneath it holding
the words the group had written there, or `discussed: none on this line`, so none is lost and a
rerun knows the mark is settled; tick the box of each accepted proposal and each answered
`question/`, the report being
the record of what the group decided; nothing below reads the discussion again. Every `Mark:` line empty after
that, the meeting having deferred everything: stop, there is nothing to write, and name the
report's path and, in a clone, its branch. Then, by mark:
- A proposal not marked `accept` gets no archive entry, no diff line of its own and no ticket. A
  declined, escalated or blank admission, the last one the meeting deferred, returns to the held
  candidates with its evidence and its quotes, a `question/` included, with `kind:
  open-question`; one marked `answer:` is settled, and becomes a decision.
- A held proposal whose held line says `no override` returns to the held candidates whatever its
  mark.
- A proposal held by the bar is accepted only by a mark carrying `override: <reason>`. A held
  admission not so marked returns to the held candidates; a held rewording, promotion or
  broadening not so marked leaves its rule as it stands. A held proposal marked a plain `accept`,
  or `accept, reworded` with no override, stops `apply`, naming it, until its mark carries the
  reason.
- A mark carrying `reworded: "<words>"` drafts those words in place of the rule's proposed
  wording, its `> ` lines, or the drafted entry's statement, the rest of its `entry:` lines kept
  as they are; it is named in the lint like any other change, so the bar judges the words the
  group agreed. With an override too, it is still named, and the override waives only the gate
  the proposal was held on, as `rule-bar.md`'s "Overrides" says.

1. **Archive every rule that leaves.** For each rule graduating, retiring, expiring, demoted to
   the prose tier or rewritten, write all of these:
   - `<archive>/R-NNN.md`: the rule's full text as it read, why it was admitted,
     its firing history with every decline reason quoted, why it left, what replaced it and where,
     and what the replacement cannot catch;
   - its stub in the ledger: the entry reduced to its heading, its status line and a pointer to
     the archive entry;
   - its wording removed, in the diff, from its entry's `> ` lines, or from the instruction file
     a ledger that keeps it there links; for a demotion, its sentence moves into the instruction
     file's own text, outside any `## Review Rules` section and with no `### R-NNN` heading, and
     its stub reads `tier: —` and `status: retired`, which `rule_lint.py` accepts;
   - for a graduation, the back-pointer comment on the check it became;
   - a Confluence page body with the same content in `.review/archive-pages/`; the report says a
     person has to publish it.

   The same for a retired `context/` entry, a superseded decision, and an agent guidance entry or
   data convention that retires, each to `<archive>/<id>.md` with no stub left behind. A rule may not leave the
   corpus in a revision pull request without all of them. With a clone, the archive entries go in
   its pull request, which merges first, and the pull request here links it.
2. **Draft, lint, then write.** Draft the diff for the accepted proposals and the accepted
   context refreshes, as `context-refresh.md` says. A rule's wording goes in its entry as `> `
   lines. A ledger whose entries still link an instruction file keeps every rule's wording there,
   a new one's under a `### R-NNN · <title>` heading with a `Wording:` link from its entry, since
   the lint refuses a ledger that mixes the two; a changed title changes that file's anchor, and
   the ledger's link changes with it. Whatever the marks, the diff also rewrites the
   ledger's `## Candidates below the criteria` from the held candidates, of every kind, each
   other than a rule with a `kind: <kind>` line, and each with a `prs:` line, each entry
   `<repo>/pr-NNNN` in a standard with `profiles/` and a bare one there read as this repository's: a continued
   candidate's, its cluster's `asked` line from `guidance_clusters.py`; a candidate no cluster
   continued, its line as it stands, or, with none, the pull requests a person asked on that its
   evidence names, written once; the admissions declined,
   escalated or deferred, and the held admissions not accepted with an override, each with its evidence, its
   quotes and the criterion or check it fails. An admitted, reworded, promoted or broadened entry takes its
   `scope:` and `example:` lines verbatim from under its proposal. An admitted rule's `since:` is
   the month its entry reaches `main`, never the window's, since the Provisional expiry Dial counts
   from then. An accepted override goes on the entry's evidence line as `rule-bar.md` says, or,
   for a `D-NNN`, on its date line as harvest.md's "Destinations" says. An
   accepted `doc/<path>` proposal changes that document to say what its pull requests show, in
   the same diff, and touches nothing else in it; an accepted `exemplar/<path>` adds a pointer to
   that code to the instruction file.

   The other destinations, as harvest.md's "Destinations" names them, each taking its drafted text
   verbatim from its `entry:` lines in the report:
   - `A-NNN` and `F-NNN` entries go at the end of `<standard files>/agent-guidance.md` and
     `data-conventions.md`, each file started from `<plugin root>/standards/templates/` when the
     standard has none, their months the month the entry reaches `main`. A change to a live
     `F-NNN` is written only when its mark carries `owner: <name>`, its owner the one named, and
     `owner: <name> · <YYYY-MM>` goes on its `source:` line; marked an accept with no owner, it stops
     `apply`, naming it, as a held proposal does. Whatever the marks, each agent guidance entry the
     report's "Rules" lists as seen again takes its new `seen` month.
   - `D-NNN` entries go at the end of `<standard files>/decisions.md`, and so does each answered
     `question/`, as a provisional `D-NNN` stating the answer, numbered as harvest.md says, so a
     later revision finds it covered.
   - `tool/<rule>`, proposed only with no violations on `main`, changes the lint configuration
     the repository's instruction files or CI name, in this repository's diff, enabling that rule
     and nothing else.

   Lint each changed agent guidance or data conventions file with `python3 "<plugin
   root>/scripts/entries_lint.py"` on its copy beside the ledger's; a refusal stops as the ledger's
   lint does. Append each `D-NNN` to a copy of `decisions.md` beside them and pass that copy as
   the lint's `--decisions` below, with `--checks fields` run on it even when nothing is named.

   Apply the drafted diff to copies of the ledger, and of the instruction file it links if any,
   under `mktemp -d` and run `rule_lint.py` on them with `--ledger`, `--instructions` only for a
   linked instruction file, `--repo .`, the `--decisions` and `--profiles` files `prepare.md`
   step 7 names, the copied `decisions.md` in place of its own, and `--changed` naming each accepted proposal that admits,
   rewords, promotes or broadens a rule, less those accepted with an override and no new words, whose lint lines
   go into the report beside the reason (one reworded with an override is named, as "Settle the
   marks" says, its held gate's line beside the reason and any other failure stopping), and less each marked "check from <repo>": that one is
   linted apart on its own `--entry` with `--checks sync,wording,status,fields`, since `scope` and
   `anchors` read another repository's code, and named in a second run of the applied copy,
   `--checks budget --changed <its ids>`, so it cannot carry its repositories over budget; its
   mark stays on its entry's evidence line. With nothing to name and no new decision, skip the lint. A failure stops,
   with its lines, and nothing is written. Once a repository is over its budget, any named
   change to a rule counted there fails the budget gate, a narrowing included, so the proposals
   that bring it back under go in the same apply; an admission accepted with an override and no
   new words is not named, so it passes with its budget line printed beside the reason, while one
   reworded with an override is named and stops on the budget gate unless that is the gate it was
   held on.

   Write the diff to `.review/ratchet-proposal.diff`, in `git diff` form with `a/` and `b/` paths
   relative to this repository, and the side in the standard's repository, when that is another,
   into its clone. With a clone, first check, as `pr-create` step 4 does, for an open pull request
   on the standard's repository whose head is the branch, `revision/<repo>-YYYY-MM`, the draft
   `prepare` may have opened. Then ask: **Commit, push and open the standard's pull request**
   (Recommended: the code repository's pull request links it and it merges first), **Commit only**,
   naming the clone's path and branch, **Stop**, nothing committed and the clone's path named, or
   **Let's discuss**. When that pull request exists, the first option reads **Commit, push and
   update pull request #N**: it pushes to it and replaces its description with one for the
   accepted changes, shown in the question as it will be sent, rather than opening another; the
   run ends by saying that marking it ready for review is the person's step. The diff for this
   repository stays in `.review/ratchet-proposal.diff` for the driver.
3. **Hand over the tickets.** Whatever the answer above, clear `.review/revision/tickets/`, then
   write each accepted `ticket/` proposal, in the report's order, as
   `.review/revision/tickets/<n>-<slug>.md`, opening with a line naming the report and the
   proposal it came from, so `ticket-draft` does not take it for a person's own words: what is wrong and where,
   the pull request and thread or line it came from, the rule, claim or ask it breaks, and what
   done looks like, a prompt `ticket-draft` takes as its source. With none, stop. Otherwise list
   them, one line each with its position, `Ticket 2/5 · <slug>`, then ask about each in turn:
   **Draft it** (Recommended: runs `/lasp-dev:ticket-draft <its path>`, which keeps its own
   write plan and yes, then comes back for the next), **Skip it**, **Stop here**, the rest left
   in their files for later, or **Let's discuss**. Stop after the last.
