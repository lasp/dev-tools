# Prepare

`revise`'s `prepare` mode: from the window's merged pull requests to the report the group
marks. Each step fills the section of `<plugin root>/skills/revise/outline.md` it names. Apply every Dial
by name from the shared `dials.md`; a threshold the Dials do not state is not applied. Steps 1,
2, 5 and 7 run the sections of `<plugin root>/skills/revise/harvest.md` they name; read it at
step 1.

1. **Harvest the records.** Run harvest.md's "Records" from the window's first day, for each
   other repository a standard covering several has a `profiles/` file for, in either row of
   `revise`'s "The standard's repository", then for this
   repository last, since each harvest starts its directories afresh, copying each repository's
   records into its `<log>` (`revise`'s "The standard's repository") before the next harvest
   starts, with `python3 "<plugin root>/scripts/archive_records.py" <its records> <its log>`, each
   replacing a record of the same number, and making `<log>` on the repository's first harvest; the threads stay the source, and the copy lets the
   history be read without GitHub. The script refuses, copying nothing, when a harvested record
   would drop findings the log's record holds, which the threads cannot rebuild. Show its
   `refused` lines and ask: **Keep those records** (Recommended: rerun with `--keep <n>` for each,
   so the log's record stays as it is and is named under "Head" with its kept findings),
   **Stop here**, nothing copied, or **Let's discuss**. When the rerun refuses a keep because the
   harvested record also holds findings the log's lacks, neither record can stand alone: show that
   line and ask **Stop here** (Recommended) or **Let's discuss**.

   **The floor.** When the harvest wrote fewer records than the Revision floor Dial, say how many
   and ask: **Stop here**, nothing committed and any clone's path named (Recommended: below the
   floor the Dial allows counts and no proposal, and the next month adds records), **Write the
   counts only**, or **Let's discuss**. Counts only
   runs the rest of this step, steps 2, 5 and 6 with no rule proposal, every candidate going
   under "Held candidates" and step 6's `ticket/` and `doc/` proposals still made, and step 10, so the window's asks reach the ledger when `apply` writes the
   held candidates; the report's second line says it rests on few records, and how many.

   Then, for each repository harvested, run `python3 "<plugin root>/scripts/ratchet_counts.py"
   <its log> --ledger <standard files>/review-rules.md --since <the window's first day>`, adding `--repo
   <its name>` for a standard covering several, the paths absolute, with the numbers of the merged
   pull requests the harvest listed for it as created after the adoption date on stdin; with
   several, "Rules" gives each repository's tables under its name. The adoption date is the date
   of the first commit adding the ledger, or the pointer, to that repository's `main`: from `git
   log` here, and for another repository from its commits touching that file through GitHub, as
   `using-github` sets out; a date that cannot be read is said under "Head", and that repository's
   pull requests are counted as baseline, never as missing; a pull request opened
   before it had no standard to be reviewed against and is counted as baseline, never as missing.

   From its output, into "Rules": the window's table and all records', and the `expiry` table,
   every row the script prints, each ledger rule included at 0 when it has no firing. Each table
   has one row per rule, its id alone in the first cell, however many rows read the same: never
   several ids in one row, a range such as "R-001 to R-007", or a line such as "every other rule
   has none" in place of rows. A provisional rule whose
   `checked-since-admitted` reaches the Provisional expiry Dial is proposed for expiry, fired or
   not; an established rule whose `checked-since-fired` reaches the
   Established expiry Dial is proposed as the Dials' "Established and unfired at expiry" row
   says. Name every rule the Contested Dial catches and say what its disagreements had in common. A rule the Unanswered
   share Dial catches gets a proposed do-not-flag sentence or severity change. Into "Head": the
   missing records and the records the script names as predating `merged:`, the corrections and
   notes as counts, never evidence, and the cost: median and longest open-to-merge time of the
   window's pull requests, and the count merged without a build, whose body has no Already checked
   block.
2. **Read the threads.** Run harvest.md's "Analysts" on the records step 1 wrote; the report
   cites thread ids. What it did not read goes under "Not read".

   From the blocks, leaving out lines with `asked: none`:
   - **What review asked for**: a table of category by outcome, with counts and a source column
     (`thread`, `review`, `comment`); under it, the asks step 5 finds recurring, each with its pull
     requests and each ask's source and id, joining step 5's candidates marked `from people's
     threads`. Then each thread the record holds as `unanswered`, by its analyst line: `diff:
     addresses it` counts as answered in code, `does not` as ignored, `cannot tell` apart, with
     its thread id.
   - **About the procedure**: every `Procedure:` id with its ask, each correction in a record's
     `inner.procedure` line, and every `kind: procedure` note. Each is about the plugin, not this
     repository, so it becomes a `skill-feedback` draft, never a `ROADMAP.md` row, unless it is
     settled. Once per distinct skill or agent named, from the plugin's repository, `<plugin
     root>/.claude-plugin/plugin.json`'s `homepage`, as `using-github` sets out: its commits
     touching `skills/<name>` or `agents/<name>.md` since the earliest merge date among its
     findings, else the record's `date:` (`list_commits` with that `path` and `since`, or `gh api`),
     reading a commit's diff only for a subject that reads as the fix; and one page of thirty
     titles: `search_issues` with `repo:<owner>/<repo> label:skill-feedback in:title
     "<name>:"`, or `gh issue list --repo <owner>/<repo> --label skill-feedback --state all
     --search '"<name>:" in:title' --json number,title,state,stateReason,labels --limit 30`. A
     commit that answers a finding settles it, and so does an issue on it closed as completed or
     labeled `accepted`; an open, declined or held issue settles nothing, and the draft names it
     on its `**Source:**` line. With GitHub unreachable, say the issue check was skipped, as
     `<plugin root>/skills/work/servers.md` sets out. Write
     each unsettled one as `.review/revision/feedback/pr-NNNN-<id>.md`, its thread, review or
     comment id, `pr-NNNN-procedure-<k>.md` for the record line's k-th correction, or
     `note-<date>-<name>.md` for a note, in the form `<plugin root>/skills/skill-feedback/SKILL.md`
     step 1 gives a draft: the skill or agent it names, the source with its id, what happened from
     the ask and its outcome, and the change asked for when the ask names one. Under the heading,
     one line per draft, its path and the ask, then one line per settled finding, its id and the
     sha or `#n` that settled it; "none" when there were none.
   - **Head**: the agree rate by severity, the share of findings left unanswered, and the share of
     agreed findings the analyst marks `changed as asked`.

   **Sweep the diffs**, report only: it fills "Practice", and no Dial reads it, so no rule
   proposal rests on it; step 6 turns a break still on `main` into a `ticket/` proposal and a
   `drift` into a `doc/` one. First remove `.review/revision/sweep/` and `.review/revision/claims.md`, which a
   last revision may have left. Run `python3 "<plugin root>/scripts/window_merges.py" --repo .
   --ref origin/main --since <the window's first day> --ledger <standard files>/review-rules.md`, which
   reads git only; the sweep fetches nothing, so it reads `origin/main` as the last fetch left it,
   and an exit 2 skips it, its line under "Practice". Write `.review/revision/claims.md`: each rule
   on a script line that names a pull request, as `### R-NNN · <title>`, its wording, the
   entry's `> ` lines or the instruction file's section it links, and its `Do not flag:` line;
   then at most twenty claims from the instruction file outside any Review Rules section, `CONTRIBUTING.md`, the pull request template and the
   developer docs, each a statement a merged change, its commits or its description can follow or
   break, as `### C-n · <path>:<line> · every change` when it asks something of every pull request,
   or of every one that makes a kind of change, or `· code` when it governs how code is written,
   and the claim in one line. Show the `C-` claims and ask once: **Sweep these** (Recommended),
   **Drop some** (the person names the ids), **Rules only**, or **Let's discuss**. With `every
   change` claims kept, rerun the script adding `--dumps .review/harvest/threads/` and a `--doc
   <path>` for each document they cite, so each is judged only on the pull requests opened after
   its document reached `main`; an exit 2 on that rerun drops the `every change` claims, with its
   line under "Practice". Then, all in one
   message, one `diff-probe` per merged pull request the script listed, past thirty the thirty
   merged most recently, each given this repository's path, its number and sha, the claims file
   and the ids to judge: each rule whose line names it, never one where it is under `predates`,
   each `every change` claim whose document's `doc <path>: pr-…` line names it, never one under
   its `predates` or `no opened day`, and every `code` claim. Write each block to `.review/revision/sweep/pr-NNNN.md` as returned. Into
   "Practice", per claim: the pull requests it was judged on and how many follow it, break it,
   leave it untouched and could not be judged for want of a description, each break with its pull request and place; `drift` beside a claim broken
   in more than half of those that touched it; `missed by review` beside a break on a pull request
   with a record in which no finding cites the claim's rule, any break on such a pull request for
   a `C-` claim. Then the rules the script printed as `not swept: no scope`, the `predates` lines,
   each `doc` line's `predates`, `no opened day` and `not on` pull requests or document,
   the pull requests past thirty, and each pull request step 1's harvest listed in the window that
   the script did not, as `not swept: no merge subject`.
3. **Check breadth before promoting anything.** A rule's breadth is the `distinct-prs-agreed`
   column of the all-records table: the pull requests with an agreed finding on it, whoever wrote
   or agreed, since on a small team one person's well-founded ask counts as anyone's. A rule
   agreed in fewer pull requests than the Established Dial stays provisional; say which rules are
   held for this and what would release them. A rule the Corrected Dial catches gets a rewrite or a do-not-flag proposal, never a
   promotion. For a corrected rule, read its agree rate since its latest correction, rerunning
   with `--since` that record's `date`; for a rule reworded since admission, since the day the
   commit changing its wording reached `main`, from `git log` of the file that holds it, so a
   decline of the old wording never counts against the new.
4. **Apply the Dials.** Every row of the shared `dials.md`; the Rule budget is what
   `python3 "<plugin root>/scripts/rule_lint.py" --ledger <the standard's ledger> --repo .
   --checks budget`, with `--instructions` naming the instruction file the ledger's `Wording:`
   lines link, if any, and the `--profiles` step 7 names, reports, a line for each covered
   repository with its lines against its budget, `budget ok` or over it. Name the Dial beside each proposal. Below the Minimum settled
   firings before a rate is read Dial, no proposal resting on a rate is made for that rule, and its
   rate line reads `keep, insufficient evidence`; admission, establishment and expiry rest on no
   rate. A candidate that meets the Admission Dial is proposed whatever the rule count. The Low
   agree rate Dial's "still below at the next revision" reads the rules the previous report, the
   newest `ratchet-*.md` in any `<log>` of the standard, proposed rewording under that Dial.

   **Dials at the margin.** For each Dial with values in its Either way column, list the rules
   and candidates whose measured value lies between the default and either value, and the
   proposal each would gain or lose there. A Dial with none is left out; one line says the rest
   changed nothing.
5. **Cluster.** Run harvest.md's "Clusters", adding the records' `inner.nominated` corrections,
   the taken suggestions, and each ask in the meeting or chat notes the driver pasted into
   `.review/revision/notes/*.md`, cited by its file and marked `pasted`: a person's line that
   strengthens its cluster's evidence but counts as no merged pull request for the Admission or
   Recurring ask Dial. List
   the clusters the Recurring ask Dial admits, with their evidence.
   **Before admitting one, search `<archive>`.** If the archived rule graduated,
   this is a gap in the check, not a missing rule; if it retired at a low agree rate, the evidence
   line says what changed; if it expired unfired, say how long it sat idle, which argues for a
   check.
6. **Merge the held candidates.** Merge this window's clusters into the ledger's "Candidates below
   the criteria", re-judge each against the Dials, and propose each that now meets them. The rest
   go under "Held candidates", each with its updated evidence and the criterion still failing,
   never as a proposal to mark; drop one under the Candidate drop Dial and say so. Then
   consolidate: proposals acting on the same rule become one; candidates asking for the same
   change become one, with both sets of evidence; a candidate a live rule already covers becomes a
   proposal to reword that rule.

   **Tickets and documents.** Two kinds of proposal no Dial governs, marked like any other, and
   made below the Revision floor too, since they rest on no count of records:
   - `ticket/<slug>`, one per distinct problem still in the code: a thread step 2 lists as
     `unanswered` with `diff: does not` whose analyst `by:` is `human`, or a sweep `breaks` line of
     a claim not marked `drift`; either only while `git grep -nF -e '<the line>' origin/main --
     <path>` still finds the line it names. Its evidence is the pull request and the thread id or
     `path:line`.
   - `doc/<path>`, for a documented claim the sweep marks `drift`: change the document to say what
     the merged pull requests do, or, when a person's ask in the window says the practice is the
     thing to fix, a `ticket/` in its place. A rule the sweep marks `drift` stays under
     "Practice", since no Dial reads the sweep.
7. **Hold each proposal to the bar.** Run harvest.md's "The bar" on each proposal that admits,
   rewords, promotes or broadens a rule, with one decisions file, the project's, by `revise`'s "The
   standard's repository": `--decisions <clone>/standards/decisions.md` in the pointer's row and
   `--decisions standards/decisions.md` in the other, either only when that file exists. The plugin
   ships no `decisions.md`, so none is passed from `<plugin root>/standards/`. With `profiles/`,
   add `--profiles <standard files>/profiles/`; a rule that applies to only some repositories carries their `repos:`
   line. A proposal a
   gate fails goes under "Held by the bar".

   With measures on, read `<plugin root>/skills/revise/measures.md` now and run it.
8. **Refresh the context**, when the repository has `context/` entries or a page or epic was
   named, as `<plugin root>/skills/revise/context-refresh.md` sets out; read it then.
9. **Draft the checks.** For each graduation candidate, draft the check into `.review/checks/`
   and report under "Graduation checks" what it would have caught in the window, and any false
   positive on `main`.
10. **Write the report.** First write the overview: every proposal, the held ones and the
    context refreshes among them, one line each, grouped by priority, high, medium and low, and
    within a group by impact: the number of merged pull requests in its evidence, then the number
    of files it would change, most first, both written in its Impact cell. A
    proposal is high when it rests on what people wrote, the author's own comments and other
    developers', or on a break still on `main`; low when it rests only on AI findings' agree
    rates, since a person's comment is more often about the design and a finding agreed to may
    have missed the mark; medium otherwise. No cap: the group takes them in order and leaves the
    rest blank. Write it as `outline.md` gives it, in the words `writing` sets out, every checkbox blank; no
    diff and no archive entry. Ask, so `apply` can check the branch out: **Commit and push the
    branch** (Recommended: the group marks it on GitHub or in any checkout), **Commit only**,
    naming the branch and any clone's path, **Stop**, nothing committed and any clone's path named,
    or **Let's discuss**. Either commit answer commits the report in `<log>` with the records, in
    the clone; with no clone, nothing is committed and the question is not asked: the report and
    the records stay in `<log>` here, as `revise`'s "The standard's repository" says. Then
    stop, saying in one line how the group marks: in the meeting the driver writes each verdict
    on its proposal's `Mark:` line and ticks the box, on that branch, on GitHub or in any checkout, and commits the marks there; when the branch was not
    pushed, where it was committed; with no clone, in the report in this working tree, left
    uncommitted for `apply`. When step 2 wrote drafts, a last line says how many, and that
    `/lasp-dev:skill-feedback <path>` files each, shown whole before its yes.
