# Capture

`revise`'s `capture` mode: harvest the pull requests merged since the last capture, read their
threads and their comments for guidance, and keep all of it in the standard's log, so `prepare`
reads the month from the log instead of harvesting it at once (`docs/contracts.md`, "The
capture"). It changes no rule and writes no report. Run it weekly, or whenever pull requests have
merged; a scheduled agent can run it too, as `/schedule` sets one up. `prepare` runs it for
whatever days are left when it starts.

Read `<plugin root>/skills/revise/harvest.md` now; this mode runs its "Records", "Analysts" and
"Guidance". The standard, `<standard files>` and `<log>` are `revise`'s "The standard's
repository", clone included.

1. **The days.** From the last day on any line of `<log>/capture/covered.txt`, that day included,
   since a pull request can merge after a capture's search on the same day, or, with none, from the
   later of the window's first day (`revise`'s Options) and this repository's adoption date; or
   from a day the person gives, `capture <YYYY-MM-DD>`, to capture those days again. Through today,
   in UTC. Say the days before anything is harvested.
2. **Records.** Run harvest.md's "Records" for this repository from the first day, and write
   `pr-reader`'s report, the block it returns, to `.review/harvest/report.md`. Copy the records into
   `<log>` with `python3 "<plugin root>/scripts/archive_records.py" .review/harvest/records <log>`,
   and answer a refusal as `prepare` step 1 does: **Keep those records** (Recommended), **Stop
   here** or **Let's discuss**.
3. **Analysts.** Run harvest.md's "Analysts" on the records step 2 wrote.
4. **Guidance.** Run harvest.md's "Guidance" into `.review/harvest/guidance/`, up to and including
   `guidance_check.py`, and send a refused slice back as it says.
5. **Store.** Run `python3 "<plugin root>/scripts/capture.py" store --log <log> --report
   .review/harvest/report.md --threads .review/harvest/threads --from <the first day> --through
   <today> --slices .review/harvest/guidance/slice-*.json --analysis .review/harvest/analysis`. It
   replaces each harvested pull request's capture whole, so capturing a day again is safe, and adds
   the days to `covered.txt`. A refusal prints its lines and writes nothing: fix what they name and
   run it again.
6. **Keep it.** With no clone, the log is this repository's working tree: the files stay there,
   uncommitted, as `prepare`'s records do, and the revision's pull request commits them; say so.
   With a clone, the log is the standard's repository: show the files changed and ask **Commit and
   open a pull request** (Recommended: on a branch `capture/<repo>-YYYY-MM-DD`, pushed as
   `using-github` sets out; `prepare` reads a capture once it is on the standard's `main`),
   **Leave it in the clone**, its path named, or **Let's discuss**.

End with one line per pull request from step 5's printout, the days covered, and what step 6 did.

A standard covering several repositories is captured in each: run `capture` in each covered
repository, since "Analysts" reads the code of the repository it runs in. `prepare` captures
another repository's missing days itself, without its analysts, which only this repository's
report reads.

## Never

Write a report, change a rule, or write outside `.review/` and `<log>`. Commit to this repository.
Push without the yes step 6 asks for.
