# Prepare

`revise`'s `prepare` mode: from the window's merged pull requests to the report the group
marks. Each step fills the section of `<plugin root>/skills/revise/outline.md` it names. Apply every Dial
by name from the shared `dials.md`; a threshold the Dials do not state is not applied. Steps 1,
2, 5 and 7 run the sections of `<plugin root>/skills/revise/harvest.md` they name; read it at
step 1.

**First, fetch and read the dates.** Run `git fetch origin main` here, and in the clone when
there is one, then read the adoption dates as `revise`'s "The standard's repository" sets out. A
fetch that fails is said in one line, and the dates are read from `origin/main` as the last fetch
left it. With no previous report and no date from the command for this repository, stop and say
so, naming the command and the file: the window has no first day, and no other day stands in.

**Then say what the run covers**, before anything is harvested: the window, where the standard
is stored (this repository's `standards/`, or the repository its pointer names), and, for a
standard whose `profiles/` covers several repositories, what the run does in each. Every
covered repository is harvested and its records archived. A rule reaches a repository when its
`repos:` line names it or it has none (`docs/contracts.md`, "The ledger's bar lines"):
- **Every covered repository** is read for guidance: its comments are extracted and clustered
  with the others', so one run revises the whole standard, and a cluster may draw on several.
- **This repository** also feeds the analysts and the sweep, which read its code: its threads'
  `diff:` verdicts and its merged diffs. A rule drafted only from another repository's evidence
  is marked "check from <repo>" at the bar, since its `scope:` and `example:` lines are checked in
  the repository they name.
- **Every other repository**'s records are counted against the rules that reach it, none when no
  rule does.

Write it as a short list, one repository a line, each with the rules that reach it and what the
run does there, such as "gadgets: R-002; archived, counted and its comments read", then go on.

**Record each stage.** Run `python3 "<plugin root>/scripts/revise_state.py" start`, and after each
stage below `revise_state.py done <stage>`, or `skip <stage> <the reason, in a few words>` when it
did not run, a server it needs not connected or the person's answer included
(`docs/contracts.md`, "The revision's run state"). The report waits on its `check`.

**Then read the project's sources**, before any harvest, since what changed in the project frames
what the threads say: run `<plugin root>/skills/revise/context-refresh.md`, read then, on the
context entries, the watched pages and the page or epic given with `prepare`, the year plan and
design docs only when they are among those, and say under "Context" that the others were not
read; and read the decisions and terminology the changed pages and epics touch, each a candidate for a `D-NNN` or a term where it conflicts with
`decisions.md` or `terminology.md` or adds to them. Its proposals go where step 8 puts them. Then
record `sources`.

1. **Load the window from the capture.** Each repository's merged pull requests are harvested,
   analyzed and read for guidance between revisions, by `revise capture` (`capture.md`), into its
   `<log>`; this step reads them from there, as fresh as the last capture. This repository is
   captured only when the log does not hold the window, which its git shows; every other covered
   repository is captured first, `capture.md` steps 1 to 5 for it, since no git here shows what
   merged there since its last capture, and that capture's `pending` sends only the pull requests
   new or changed since to the extractor. First remove every
   `.review/harvest/guidance-*/`, so no earlier run's tally is read. Then, for each other covered
   repository, from the later of the window's first day and that repository's adoption date
   (`revise`'s "The standard's repository"), since a pull request before it was reviewed against no
   standard, and for this repository last, from the window's first day, run `python3 "<plugin
   root>/scripts/capture.py" load --log <its log> --since <its first day> --through <the last day>
   --out <out> --guidance <guidance>`: for this repository, `<out>` is `.review/harvest`,
   `<guidance>` `.review/harvest/guidance`, the last day the newest that `python3 "<plugin
   root>/scripts/window_merges.py" --repo . --ref origin/main --since <the window's first day>`
   prints, or the first day when it prints none, and `--merges` that printout, saved to a file;
   for another, after its capture, `<out>` is `.review/harvest/captured-<repo>`, `<guidance>`
   `.review/harvest/guidance-<repo>`, and the last day today, in UTC. An exit 2 names the days, the merges and the failed or missing records the log
   does not hold: run `capture.md` steps 1 to 5 for that repository, then load again; a second exit
   2 stops the step with its lines. The block `load` prints is the harvest's report for everything
   below, its `not read · pr-NNNN` lines the pull requests whose comments were not read for
   guidance, which go under "Not read"; the records are already in `<log>`, the threads and
   records in `<out>`, and the guidance slices in `<guidance>`. For each other repository, run harvest.md's
   "Guidance" from `guidance_check.py` on, with no extractor, into its `<guidance>`, on its loaded
   slices and the comment lists of the pull requests they hold, leaving out those `not read`. When `capture.md` step 2 runs, `archive_records.py` refuses, copying nothing, when a harvested record
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
   records `skip bar` and `skip checks` "below the Revision floor" and runs the rest of this step, steps 2, 5 and 6 with no rule proposal, every candidate going
   under "Held candidates" and step 6's `ticket/` and `doc/` proposals still made, and step 10, so the window's asks reach the ledger when `apply` writes the
   held candidates; the report's second line says it rests on few records, and how many.

   Then, for each repository harvested, run `python3 "<plugin root>/scripts/ratchet_counts.py"
   <its log> --ledger <standard files>/review-rules.md --since <the window's first day>`, adding `--repo
   <its name>` for a standard covering several, the paths absolute, with the numbers of the merged
   pull requests the harvest listed for it as created after its adoption date on stdin; with
   several, "Rules" gives each repository's tables under its name. A date that cannot be read is
   said under "Head", that repository's harvest starts at the window's first day, and its pull
   requests are counted as baseline, never as missing; a pull request opened before it had no
   standard to be reviewed against and is counted as baseline, never as missing.

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
   missing records, saying for another repository that they can include pull requests from
   before its pointer merged (`revise`'s "The standard's repository"), and the records the script names as predating `merged:`, the corrections and
   notes as counts, never evidence, and the cost: median and longest open-to-merge time of the
   window's pull requests, and the count merged without a build, whose body has no Already checked
   block.
2. **Read the threads.** Run harvest.md's "Analysts" on the records step 1 loaded that have no
   block in `.review/harvest/analysis/`, none when the capture analyzed them all, and its
   `block_tally.py analysis` on every record loaded; the report cites thread ids. Then run
   harvest.md's "Guidance" from `guidance_check.py` on, with no extractor, on this repository's
   loaded slices and the comment lists of the pull requests they hold, leaving out those `not read`,
   the others' having run at step 1; into
   "Head", one guidance line per repository from its check's printout, never counted by hand, and
   under "Not read" each repository's unread slices. What either did not
   read goes under "Not read".

   **Spot-check the extraction.** Run `python3 "<plugin root>/scripts/spot_check.py" sample
   --seed <the window, as the report's `window:` line gives it> <every slice the guidance checks
   passed, every repository's>`, which picks ten items at random. For each line, read the comment
   at its URL in its pull request's `comment-list.json`, under `.review/harvest/threads/` or
   `.review/harvest/captured-<repo>/threads/`, and judge the item against it: the quote is that
   comment's own words, and its generality, kind and principle say what the comment says, no
   more. Write one line per item to `.review/revision/spot-check.md`, `<id> · right` or `<id> ·
   wrong · <what is wrong, in a few words>`, the id as the sample printed it, then run the script
   with `tally` in place of `sample`, the same seed and slices, and `--checked
   .review/revision/spot-check.md`. Its `spot check:` line goes into "Head" as it prints it, and
   each `wrong` line under "About the procedure"; a refusal names the line to fix. You did not
   extract these items, so you judge them as a reader would; with no slice passed, record none
   and say so in "Head".

   From the blocks, leaving out lines with `asked: none`, the counts from harvest.md's
   `block_tally.py analysis` printout, never counted by hand:
   - **What review asked for**: a table of category by outcome, with counts and a source column
     (`thread`, `review`, `comment`), from its `count` lines; under it, the asks step 5 finds recurring, each with its pull
     requests and each ask's source and id, joining step 5's candidates marked `from people's
     threads`. Then each thread the record holds as `unanswered`, the record's verdict, by its
     analyst line in the block: `diff: addresses it` counts as answered in code, `does not` as
     ignored, `cannot tell` apart, with its thread id. The tally's `outcome unanswered` lines are
     the analyst's reading of the replies and choose nothing here; they count only in the table.
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
   - **Head**: the agree rate by severity, the share of findings left unanswered, as the
     Unanswered share Dial in `dials.md` takes it, and the share of agreed findings the analyst
     marks `changed as asked`.

   **Sweep the diffs**, report only: it fills "Practice", and no Dial reads it, so no rule
   proposal rests on it; step 6 turns a break still on `main` into a `ticket/` proposal and a
   `drift` into a `doc/` one. It runs after step 1's harvest of this repository, never beside an
   earlier one: `diff-probe` reads each description from that harvest's
   `.review/harvest/threads/pr-NNNN/pr.json`, which every harvest empties. First remove `.review/revision/sweep/`, `.review/revision/claims.md`, `.review/revision/merges.txt` and `.review/revision/drift.txt`, which a
   last revision may have left. Run `python3 "<plugin root>/scripts/window_merges.py" --repo .
   --ref origin/main --since <the window's first day> --ledger <standard files>/review-rules.md`,
   writing its output to `.review/revision/merges.txt`, which the rerun below replaces; it
   reads git only; the sweep fetches nothing, so it reads `origin/main` as the last fetch left it,
   and an exit 2 skips it, its line under "Practice". Write `.review/revision/claims.md`: each rule
   on a script line that names a pull request, as `### R-NNN · <title>`, its wording, the
   entry's `> ` lines or the instruction file's section it links, and its `Do not flag:` line;
   then at most twenty claims from the instruction file outside any Review Rules section, `CONTRIBUTING.md`, the pull request template and the
   developer docs, each a statement a merged change, its commits or its description can follow or
   break, as `### C-n · <path>:<line> · every change` when it asks something of every pull request,
   or of every one that makes a kind of change, or `· code` when it governs how code is written,
   and the claim in one line. A claim a script can judge carries ` · script: <check>` after that:
   `template` for a line of the pull request template, its path the template's; `changelog <file>
   <path>[,<path>]` for an entry a change to that code owes; `todo` for a TODO that names its
   ticket; `history` for a comment that says how the code used to be (`<plugin
   root>/scripts/drift_checks.py`). Show the `C-` claims, each with its check or none, and ask once: **Sweep these** (Recommended),
   **Drop some** (the person names the ids), **Rules only**, or **Let's discuss**, removing from
   the claims file every `C-` claim the answer drops. With `every change` claims kept, rerun the
   script adding `--dumps .review/harvest/threads/` and a `--doc <path>` for each document they
   cite, writing its output to `.review/revision/merges.txt`, so each is judged only on the pull
   requests opened after its document reached `main`; an exit 2 on that rerun drops the `every
   change` claims from the claims file, with its line under "Practice". Run `python3 "<plugin
   root>/scripts/drift_checks.py" --repo . --claims .review/revision/claims.md --merges
   .review/revision/merges.txt --dumps .review/harvest/threads/`, with `--ticket-pattern` the
   profile's `ticket.pattern` for a `todo` claim, writing its output to
   `.review/revision/drift.txt`; it judges every scripted claim on every pull request it is owed
   by, with no agent, and prints the lines `block_tally.py` prints, which "Practice" takes the same
   way. On an exit 2, its line goes under "Practice" and ` · script: …` comes off those claims'
   headings, so the probes judge them. Then, when a rule or a claim with no check is owed, one `diff-probe` per
   merged pull request the script listed, at most five, the five merged most recently, launched as
   harvest.md's "Analysts" launches agents, each given this repository's path, its number and sha, the claims file
   and the ids to judge: each rule whose line names it, never one where it is under `predates`,
   each `every change` claim whose document's `doc <path>: pr-…` line names it, never one under
   its `predates` or `no opened day`, and every `code` claim, none of them scripted, and the path
   `.review/revision/sweep/pr-NNNN.md`, where it writes its block and returns `wrote <path>`.
   Never repeat a block: a probe that returns `write failed: <error>` could not write it, and you
   write the block that follows that line, without it, to its path. When a probe ran, run `python3 "<plugin
   root>/scripts/block_tally.py" sweep --claims .review/revision/claims.md [--merges
   .review/revision/merges.txt] .review/revision/sweep/ <pr-NNNN ...>`, the `--merges` when the
   rerun wrote it, naming each pull request probed; an exit 2 names the block that
   does not hold its form, to rerun that probe. Into "Practice", from its `claim` and `break` lines,
   per claim: the pull requests it was judged on and how many follow it, break it,
   leave it untouched and could not be judged for want of a description, each break with its pull request and place; `drift` beside a claim broken
   in more than half of those that touched it, as the tally marks it; `missed by review` beside a break on a pull request
   with a record in which no finding cites the claim's rule, any break on such a pull request for
   a `C-` claim. Then the rules the script printed as `not swept: no scope`, the `predates` lines,
   each `doc` line's `predates`, `no opened day` and `not on` pull requests or document,
   the pull requests past five not probed, and each pull request step 1's harvest listed in the window that
   the script did not, as `not swept: no merge subject`.
   Record `records` once every repository's harvest is archived, and at step 2 `analysts`,
   `sweep` and `guidance`, the last skipped, naming them, when any repository's guidance did not
   run.
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
   rate line reads `keep, insufficient evidence: <agree> agree, <disagree> disagree of <n> settled
   since <date>`, its counts the all-records table's, or step 3's rerun for a reworded or
   corrected rule, so the group sees them build; admission, establishment and expiry rest on no
   rate. A candidate that meets the Admission Dial is proposed whatever the rule count. The Low
   agree rate Dial's "still below at the next revision" reads the rules the previous report, the
   newest `ratchet-*.md` in any `<log>` of the standard, proposed rewording under that Dial. An
   agent guidance entry past the Agent guidance expiry Dial, its `seen` month moved first as
   harvest.md's "Destinations" says, is a proposal `A-NNN · retire`.

5. **Cluster.** Run harvest.md's "Clusters", adding the records' `inner.nominated` corrections,
   the taken suggestions, and each ask in the meeting or chat notes the driver pasted into
   `.review/revision/notes/*.md`, cited by its file and marked `pasted`: a person's line that
   strengthens its cluster's evidence but counts as no merged pull request for the Recurring ask
   Dial; with "Guidance" run, each joins a cluster as a note. List the clusters the Recurring ask
   Dial admits, and those a single statement admits, with their evidence: from the
   `guidance_clusters.py` printout, when "Guidance" ran, each cluster's pull requests, people and
   `said` quotes as it prints them.

   **Single statements.** A cluster admits on one guidance tally `admit` line of its own kind, or
   one a tally `ask` line names, alone, a person's general statement, the `admit` count `guidance_clusters.py` prints, whatever the Recurring ask Dial counts, its quote the evidence. A pasted
   note admits the same way when a named person states a principle or asks for a change in it,
   cited `pasted <file>` with that person's name. A reviewer who asked for a point to be kept, a
   tally `ask` line, is named with it in the report: an ask on an `admit` line admits its cluster
   whatever the cluster's kind, an `ask · <cluster>` line in the `guidance_clusters.py`
   printout, and the cluster is a proposal or, failing its cluster's kind's bar in harvest.md's
   "Destinations", held with that bar's reason; an ask on a `covered` line, an `ask ·
   <covered_by>` line there, is listed under the live entry it names. A line a tally `drafted`
   line names is a reply its poster sent through a skill, theirs as the tally reads it, and the
   report marks it drafted with its AI assistance level from the `drafted · <cluster>` or `drafted ·
   <covered_by>` line, so the meeting knows an agent worded it. Each admitted cluster is a proposal of its kind,
   with the id and destination harvest.md's "Destinations" gives it. A cluster with no `admit` line and a `hold`
   line is held with the tally's criterion. A `covered` line supports the live rule, decision,
   agent guidance entry, data convention or instruction it names, listed under it in "Rules", and
   is no candidate. A `support` line, an agent's statement the author
   changed as asked, never admits; it is listed under its cluster. Every line the tally prints
   reaches the report, as a proposal's evidence, a rule's support or a held candidate, never
   dropped.
   **Before admitting one, search `<archive>`.** If the archived rule graduated,
   this is a gap in the check, not a missing rule; if it retired at a low agree rate, the evidence
   line says what changed; if it expired unfired, say how long it sat idle, which argues for a
   check.
   Each cluster whose `repos` line names one repository is that repository's: its proposal
   carries `repos: [<it>]` in a standard with `profiles/`; a cluster naming several applies
   project-wide, unless its principle is plainly about those repositories' code, which its
   proposal then says. Record `clusters`.
6. **Merge the held candidates.** Merge this window's clusters into the ledger's "Candidates below
   the criteria", a cluster whose `held` line names a candidate into that one, re-judge each
   against the Dials, and propose each that now meets them. The rest
   go under "Held candidates", each with its updated evidence, its quotes, its kind and the
   criterion still failing, never as a proposal to mark; drop one under the Candidate drop Dial
   and say so. A held candidate's kind is its `kind:` line; one without whose criterion reads `a
   <kind> statement: revise proposes rules only`, as an earlier revision wrote it, is that kind,
   re-judged without that criterion; any other without is a rule. A cluster that names a held
   candidate takes the cluster's kind. Then
   consolidate: proposals acting on the same entry become one; candidates asking for the same
   change become one, with both sets of evidence; a candidate a live entry of its kind already
   covers changes that entry, as harvest.md's "Destinations" says, except a tally `covered` line,
   which only supports it.

   **Tickets and documents.** Two kinds of proposal no Dial governs, marked like any other, and
   made below the Revision floor too, since they rest on no count of records:
   - `ticket/<slug>`, one per distinct problem still in the code: a thread step 2 lists as
     `unanswered` with `diff: does not` whose analyst `by:` is `human`; a probe's `break` line of a
     claim not marked `drift`; a `break` line in `.review/revision/drift.txt` of a `todo` or
     `history` claim not marked `drift`, never a `template` or `changelog` one, which names a merged
     description or file list and no line still in the code; or a `tool/` proposal held for its violations on `origin/main`;
     each only while `git grep -nF -e '<the line>' origin/main --
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
   gate fails goes under "Held by the bar". Every other proposal is held to its kind's bar as
   harvest.md's "Destinations" sets out, and one that fails it goes there too.

   A proposal whose evidence is only another repository's runs only the bar's `fields`, `status`
   and `wording` gates here (`--checks`), with no probe, and is marked "check from <that
   repository>" rather than held, as `revise`'s "The standard's repository" says; one with this
   repository's evidence takes its `example:` anchors from it. An `exemplar/` or `tool/` proposal
   from another repository is marked the same way. Record `bar`.

   With measures on, read `<plugin root>/skills/revise/measures.md` now and run it.
8. **The context's proposals**, from the project's sources read first: each refresh and new page
   as `<plugin root>/skills/revise/context-refresh.md` sets them out, and each decision or term
   they bear on.
9. **Draft the checks**, then record `checks`. For each graduation candidate, draft the check into `.review/checks/`
   and report under "Graduation checks" what it would have caught in the window, and any false
   positive on `main`.
10. **Write the report.** First run `python3 "<plugin root>/scripts/revise_state.py" check`: an
    `unrecorded` line is a stage nobody accounted for, so run or skip it with its reason first, and
    the report is not written until the check passes. Its `skipped` lines go under "Head". Every
    figure the report gives, in "Head", a table, an overview cell or a proposal's evidence, is one a
    script printed in this run, copied as printed; none is counted, summed or worked out by hand,
    and a figure no script prints is left out. Then write the overview: every proposal, the held ones and the
    context refreshes among them, one line each, grouped by priority, high, medium and low, and
    within a group by impact: the number of merged pull requests in its evidence, then the number
    of files it would change, most first, both written in its Impact cell. A
    proposal from a cluster takes the priority `guidance_clusters.py` prints for it, and a held
    candidate step 6 proposes with no cluster this window the level its `prs:` line counts, by the
    Recurring ask Dial: what people wrote, the author's own comments and other developers', and
    the agent findings authors changed as asked, counted by merged pull request. A `ticket/` on a
    break still on `main` is high; a proposal that rests only on AI findings' agree rates is low,
    since a person's comment is more often about the design and a finding agreed to may have
    missed the mark; medium otherwise. No cap: the group takes them in order and leaves the
    rest blank. Each line also says what the proposal applies to: project-wide, for a rule,
    decision or entry with no `repos:` line or a `context/` entry, or the repositories its
    `repos:` line names, or, for a
    `ticket/`, `doc/` or `tool/`, the repository whose code, document or configuration it names;
    a proposal from a cluster applies where step 5 tagged it;
    and where `apply` would change it: the standard's repository, this repository's diff, Jira
    through `ticket-draft` for a `ticket/`, or, for a `question/`, the standard's repository once
    answered. Write it as `outline.md` gives it, in the words `writing` sets out, every checkbox blank; no
    diff and no archive entry. Then check its quotes: run `python3 "<plugin
    root>/scripts/quote_check.py" <the report> --comments <every comment-list.json under
    .review/harvest/threads/ and each .review/harvest/captured-<repo>/threads/> --notes
    .review/revision/notes`. Each `refused` line names a `said:` line whose words are not where it
    says: copy the words again from the comment or note it cites, or take the line out when its
    quote cannot be found, and run it again until it passes; the report is not offered for commit
    before. Ask, so `apply` can check the branch out: **Commit and push the
    branch** (Recommended: the group marks it on GitHub or in any checkout), **Commit only**,
    naming the branch and any clone's path, **Stop**, nothing committed and any clone's path named,
    or **Let's discuss**. Either commit answer commits the report in `<log>` with the records and
    `<log>/capture/`, in
    the clone; with no clone, nothing is committed and the question is not asked: the report and
    the records stay in `<log>` here, as `revise`'s "The standard's repository" says, and no draft
    pull request is offered. With a clone, in the same widget, a second question, which counts only with **Commit and push the branch**: open the
    pushed branch as a draft pull request on the standard's repository, as `using-github` sets
    out, so the group can discuss each proposal in its review before or during the meeting?
    **Open a draft pull request** or **No pull request**, neither recommended, since it turns on
    whether the group discusses before it meets. The question shows the title,
    `Standards revision · <repo> · YYYY-MM`, and the body as they will be sent: the report's path
    and the records' count; that no rule, decision, term or context entry has changed, the diff
    being the month's records and the report; that a proposal is
    discussed in a review comment on its line, and its verdict counts once it is on the proposal's
    `Mark:` line in the report, written there on the branch or copied in by the driver, since
    `apply` reads the report, not the threads; and the attribution line `pr-create` appends, at
    the level `<plugin root>/skills/pr-review/comment-style.md`, "AI assistance level", sets.
    Only an answer that names the pull request opens it.

    Then stop with the run's result, in this order, a table where items are compared. A run that
    stops at an earlier step, on the person's answer or a server it cannot reach, ends with the
    same result as far as it got: the scope, and what it changed and did not.
    - **Scope**: where the standard is stored, the window, the scope list from the start of this
      file, each repository with what the run does there as planned at the start, then the step
      the run stopped at, and `revise_state.py check`'s lines: the stages skipped, with why, and
      those not reached.
    - **Proposals**: how many, by priority, then a table of each, its id, what it proposes, what
      it applies to and where `apply` would change it, in the overview's order; the held by the
      bar and the held candidates as counts.
    - **What this run changed**: the records copied into each `<log>`, the report's path, and
      what was committed, pushed or opened, with the branch, any clone's path and the pull
      request's link; `.review/`'s working files in one line.
    - **What it did not change**: no rule, decision, term, context entry or document, here or in
      the standard; `apply` changes them from the marks, and commits, pushes or opens a pull
      request only on its own yes.
    - **Next**: one line on how the group marks: in the meeting the driver writes each verdict on
      its proposal's `Mark:` line and ticks the box, on that branch, on GitHub or in any checkout,
      and commits the marks there, copying in any verdict given in the draft pull request's
      review; when the branch
      was not pushed, where it was committed; with no clone, in the report in this working tree,
      left uncommitted for `apply`. When step 2 wrote drafts, a last line says how many, and that
      `/lasp-dev:skill-feedback <path>` files each, shown whole before its yes.
