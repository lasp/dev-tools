# Correct

`revise`'s `correct` mode: corrects a misreading in the standards corpus everywhere it is carried,
once the person chooses the fix. Not for disagreeing with a rule, which goes through Disagree and
the monthly revision.

## When to run

When a person says the corpus has something wrong: "there is a standard to never touch xyz in
widgets, but that was for one specific test, not a general thing". A misreading rarely lives in
one file: the rule's wording, its ledger entry and its `Do not flag:` line, a decision restating
it, another repository's copy, and the records of findings raised under it.

## Options

| Option | Default |
| --- | --- |
| Correction | Free text: what is wrong, where (a rule, decision or term ID, a page, a file, or just the words), what it should say, and why, with the source; asked for when missing |
| Scope | The standard and this repository, the plugin's text read and reported, never edited; a copy in another adopted repository is read through GitHub, reported, and corrected by running the skill there |

## Reads

Read-only until step 6, a note or a draft at step 2 aside. The standard, where `revise`'s "The standard's repository" puts it:
`<standard files>`, with its `terminology.md`, `decisions.md`, `tracker.md`, `wiki.md`, `context/`,
`archive/`, `profile.yaml`, `profiles/` and `templates/`, and `<log>`; and the plugin's `skills/` and `agents/` text, read
from `<plugin root>`, which can carry the same wording. In each adopted repository in scope:
`standards/`, the instruction file the ledger links to if it still keeps wording there, `.github/PULL_REQUEST_TEMPLATE.md` and
check configuration. The review threads an entry's `evidence:` line names, read-only, through
GitHub as `using-github` sets out. A Confluence page or Jira issue the correction cites, read-only, as
`using-confluence` and `using-jira` describe. The shared `standards/rule-bar.md`, which a
corrected rule still passes.

## Writes

A note, `<log>/note-<YYYY-MM-DD>-<id>.yaml`, when step 2 writes one,
and a `skill-feedback` draft, `.review/revision/feedback/correct-<YYYY-MM-DD>-<name>.md` here, when
step 2 finds a procedure complaint.
After the person's choice in step 5 only: the chosen edits, in each repository they fall in,
the standard's repository included. One record,
`<log>/correction-<YYYY-MM-DD>-<id>.yaml`, never in the installed plugin, where `<repo>` is the adopted repository the correction was raised about,
asked when the scope holds more than one, even when the edits reach others:

```yaml
date: 2026-09-30
ids: [R-017, D-004@widgets]        # every ID touched, as a finding key cites it
kind: misread                      # misread | source-changed | settled
source: PR example/widgets#12, review thread PRRT_x · read 2026-09-30
by: alice                          # the person who ran it
clause: the rule came from one test's fixture, not a general constraint
pull_requests: []                  # the person adds the numbers once they exist
```

`settled` is an open question the corpus held, answered in review or by its source. A
correction record is a count for the revision, never evidence: no citation, no verdict.

A note, which step 2 writes, has the same `date`, `ids` and `by`:

```yaml
date: 2026-09-30
ids: [R-017]
kind: disagreement
by: alice
reason: the team keeps the rule's exception for vendored code
thread: PRRT_x                     # when there is one
```

## Steps

1. **Find, by every route, and read what is found.**
   - *By ID.* The rule, decision or term the correction names or implies. Then everything that
     links to it: its ledger entry in `standards/review-rules.md` with its wording, the `> `
     lines or the instruction file's section under the anchor it links, and its `Do not flag:` line, a
     decision or term restating it in the repository's `decisions.md` and
     `terminology.md`, and its archive entry if it has one.
   - *By words.* The phrase and its obvious variants across everything "Reads" names. A copy
     in a second repository or in the plugin's text is a place like any other.
   - *By evidence.* The entry's `evidence:` line names the pull requests it was harvested from.
     Read those threads and say whether they support the correction, the entry, or neither. A
     thread an agent drafted supports nothing on its own (`authorship: ai-drafted` in
     `record.py`'s terms). In the example, this is where the thread turns out to be about one test, and the
     report says the harvest generalized it.
   - *Downstream.* The records under `<log>` whose finding keys cite the ID,
     counted, never edited: a correction changes what the next revision makes of them: the
     correction record's `date` is the cut, and the revision counts the verdicts of pull requests
     merged before and after it apart.
   - *Prior corrections.* Every `correction-*.yaml` under the same `log/` naming the ID, shown as
     its own row, so a rule corrected one way last month is not silently corrected back.
   - *By source.* A Confluence page or Jira issue the correction cites, read through one
     `source-reader`, with the task `page <id>` or `ticket <key>`. An item the block lists as
     `Withheld:` is not drawn on until the person clears it; its question goes to them.

   When no route finds the ID or the words, say so with what was searched, and stop.
2. **Classify and scope** on what step 1 read, one line each, before any report. Only the first
   three kinds are this skill's to make:
   - *Misread*: the corpus misread its source. Fix the entries, cite the source and its
     version, and say on the evidence line what was misread, so the next harvest does not
     re-add it. The evidence line names a decision only in the entry's `implements <id>`, which
     `rule_lint.py`'s status gate holds it to; the decision's ID goes on the record's `source:`
     line.
   - *Source changed*: refresh the entry's paragraph and its dates.
   - *Settled*: an open question the corpus held is answered, in review or by its source. Replace
     the question with the answer and cite where it was given. The record carries `kind: settled`.
   - *Procedure*: the plugin's skills or agents do something the team did not want. Not an
     edit here: a change to the plugin starts as a `skill-feedback` issue. Write the draft
     `<plugin root>/skills/skill-feedback/SKILL.md` step 1 reads, its `**Skill:**` the skill or
     agent, its `**Source:**` this correction and its date, and the person's correction as
     written under What happened, with the change they ask for under What I would like instead
     when they named one. Say its path and that `/lasp-dev:skill-feedback <path>` files it,
     shown whole before its yes. Only places that describe what a skill or agent does leave the
     report, with no record and no note; a copy of the standard's wording in the plugin's text is
     named in the same kind of draft and leaves the report too, since the plugin changes only
     through its own pull requests, and the correction's other places stay Misread rows. When no place is left, stop.
   - *Disagreement*: the team disagrees with a rule. Not an edit: a rule's status is evidence,
     and that goes through Disagree with a reason on findings and the monthly revision.

   Then the scope: the tier and repository of each row; whether an archive entry is required
   (a rule reworded, retired or graduated: yes, in `<archive>`, in a pull request that merges
   before the code repository's when `<archive>` is in a clone, as the archive's README requires, `<archive>/README.md`; `<plugin root>/skills/revise/apply.md`
   says what stub a retired rule leaves in the ledger); whether the
   line budget or an ID is affected (IDs are never reused); and how many pull requests, where, in what
   order. A correction narrows a rule: it may add a `Do not flag:` clause or narrow its `scope:`.
   Replacing a clause that misread its source with what the source says is a *Misread*
   correction, even when the new clause excuses less and the rule fires in more places. Any
   other correction that removes a clause or widens the scope is a broadening, which only the
   revision proposes with evidence.

   **A disagreement or a broadening stops here.** List the places step 1 found, with no proposed
   change, say why this skill does not make it, and ask: **Write, commit and push a note**
   (Recommended: the revision reads it as a count beside the rule; it pushes the branch it is
   committed on and opens its pull request, as `revise`'s "The standard's repository" says), **Write and commit a note**,
   naming the branch and any clone's path, **Stop**, nothing written, or **Let's discuss**. The note is
   `<log>/note-<YYYY-MM-DD>-<id>.yaml`, in the form "Writes" shows,
   with `kind: disagreement`, committed there; with no clone, on a branch `correction/<id>-YYYY-MM-DD`
   made here, with `/lasp-dev:commit`, and opened through `/lasp-dev:pr-create` on the
   first answer. Stop.
3. **Source wins.** When the source step 1 read contradicts the correction, or says nothing that
   supports it, say what it says and ask, recommending neither, since only the person knows where
   the source lives and whether it is current: **The source is elsewhere** (read that one the same
   way and redo steps 1 and 2), **The source is outdated**, **Stop**, nothing edited, or **Let's
   discuss**. Outdated: fixing a
   page or ticket is a person's job in Confluence or Jira, and a pull request thread is not
   revised at all; the entry gets one dated sentence saying what the source now says or that it
   is under revision, step 5 offers only that sentence, and nothing else changes until the source
   does.
4. **Report before touching anything.** One row per place, and only places actually opened:

   ```
   #  Where (path or thread)   Says today   How it got there   Proposed change   Size
   ```

   How it got there is the thread it was harvested from, the adoption it was copied at, or the
   decision it restates. Size is `one line`, `a few lines`, `an hour` or `changes the plan`. A
   source read (a thread, a page) is a row with no proposed change, and is never offered for
   choosing; a file the change requires, such as an archive entry, is a row too.
   Then a shorter list, **might also carry it**, for places the words suggest but a read did not
   confirm. A place not read is not a row.
5. **Ask** which rows to change: **Apply all rows** (Recommended when every row's source read
   supports it), **Choose rows**, **Stop**, nothing edited, or **Let's discuss**. On Choose, one
   follow-up: the rows with a proposed change, as multi-select options, four to a question, as
   many questions as that takes.
6. **Draft, in format.** Every chosen row in its file's own shape: the ledger entry's fields,
   its wording as the entry's `> ` lines, or a linked instruction file's anchored heading (a
   changed title changes the anchor, so the ledger link changes with it), the contract's line, the `D-` or `T-` form, a context entry's source
   and dates. Word it as `<plugin root>/skills/writing/SKILL.md` sets out. Internal links only
   on the private side, a public repository as `writing`'s `short.md` tells one. The ID stays; the
   evidence line of a corrected entry gains `corrected <YYYY-MM-DD>: <one clause>`, the clause naming no decision ID. A correction
   that changes a rule's wording writes an archive entry of kind `corrected`; one that changes
   only an evidence line or a term does not. For a corrected reviewer-tier entry, provisional or
   established, write the entry and its wording to `.review/backtest/R-NNN.entry.md` and run
   `python3 "<plugin root>/scripts/rule_lint.py" --entry` on it, with `--repo .` and the
   `--decisions` and `--profiles` files `prepare.md` step 7 names, before showing the diff. A correction
   that changes the rule's title or wording is a rewording and meets the whole bar, so draft its
   `scope:` and `example:` lines as the shared `standards/rule-bar.md` sets out. Any other
   correction runs only the gates of the lines it changes, named with `--checks`: `status`
   always, since the status line gains the `corrected` clause, then `scope` when it changes
   `scope:` and `anchors` when it changes `example:`. A rule whose `repos:` line leaves this
   repository out runs only the `fields`, `status` and `wording` gates here, and the diff marks it
   "check from <a repository it names>", since its `scope:` and `example:` are another
   repository's. A rewording also runs the budget gate on the whole ledger: apply the drafted
   entry to a copy of the ledger under `mktemp -d`, and the drafted wording to a copy of the
   instruction file it links if any, and run `python3 "<plugin root>/scripts/rule_lint.py"
   --ledger <the copy> --repo . --checks budget --changed R-NNN`, with `--instructions <the
   instruction file's copy>` for a linked one and the `--profiles` above. A failure is shown with
   the diff and stops the commit; a rewording of a rule counted toward an over-budget repository
   goes through `revise`'s `apply`, with the proposals that bring the repository back under. Show the diff per repository, the standard's
   first, then this repository; a copy in another repository is listed with the command to run
   there. Then ask: **Commit and open both** (Recommended when the lint passed; it pushes the
   clone's branch and opens both pull requests), **Commit only**, **Stop**, nothing committed, or
   **Let's discuss**. With no clone there is one repository: the first answer reads **Commit and
   open it**.
7. **Record, then hand off.** On either commit answer, write the record in `<log>`, commit a
   clone's changes with `git -C <dir>` and this repository's with `/lasp-dev:commit`, with no
   clone on a branch `correction/<id>-YYYY-MM-DD` made here. On the
   first answer, also push a clone's branch and open its pull request, as `revise`'s "The standard's repository" says, then this repository's through `/lasp-dev:pr-create`, the standard's
   first when a change crosses tiers, stopping before the push where the repository forbids an
   agent's push. The body carries the correction, the source and its version, and the "might
   also carry it" list if it was not empty. Name `/lasp-dev:work` only if a ticket was
   involved; otherwise the last line says the pull requests are the next step, and in which
   order they merge.

## Bounds

The report shows every row; the "might also carry it" list, at most ten. One read per evidence
thread.

## Never

Edit without a yes. Push, or open a pull request without a yes. Adjudicate a disagreement with
a rule. Edit or delete a pull request record. Reuse an ID. Write to Confluence or Jira. Add a
row for a place it did not read. Count a correction as evidence for or against a rule.
