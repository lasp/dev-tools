# Capture

`revise`'s `capture` mode: harvest the window's merged pull requests, read the threads and the
comments of those new or changed since the last capture, and keep it all in the standard's log, so
`prepare` reads the month from the log instead of harvesting it at once (`docs/contracts.md`, "The
capture"). It changes no rule and writes no report. The driver runs it weekly, or whenever pull
requests have merged; `prepare` runs it when the log does not hold the window. Each capture
harvests the whole window again, one `pr-reader`, so every record and comment list takes the
replies posted since the last; only the pull requests whose comments changed, or that are new, get
an analyst and the extractor.

Read `<plugin root>/skills/revise/harvest.md` now; this mode runs its "Records", "Analysts" and
"Guidance". The standard, `<standard files>` and `<log>` are `revise`'s "The standard's
repository", clone included; a capture `prepare` runs for another covered repository writes that
repository's `<log>`.

1. **The days.** The window's first day, as `revise`'s Options set it, through today in UTC. Say
   them before anything is harvested.
2. **Records.** Run harvest.md's "Records" for the repository from the first day, and write
   `pr-reader`'s report, the block it returns, to `.review/harvest/report.md`. Copy the records into
   `<log>` with `python3 "<plugin root>/scripts/archive_records.py" .review/harvest/records <log>`,
   and answer a refusal as `prepare` step 1 says.
3. **What to read.** Run `python3 "<plugin root>/scripts/capture.py" pending --log <log> --threads
   .review/harvest/threads`: the pull requests it prints are the ones to read; with none, go to
   step 5.
4. **Read them.** For this repository, remove `.review/harvest/analysis/` and run harvest.md's
   "Analysts" on the records of the pull requests step 3 printed; another repository's capture runs
   none, since an analyst reads the code of the repository it runs in. Then run harvest.md's
   "Guidance" into `.review/harvest/guidance/` on those pull requests' comment lists alone, up to
   and including `guidance_check.py`, sending a refused slice back once as it says.
5. **Store.** Run `python3 "<plugin root>/scripts/capture.py" store --log <log> --report
   .review/harvest/report.md --threads .review/harvest/threads --from <the first day> --through
   <today> --slices <the slices the check passed> --not-read <the numbers of the pull requests in a
   slice still refused> --analysis .review/harvest/analysis`, leaving out `--slices` when step 3
   printed none, `--not-read` when every slice passed, and `--analysis` when no analyst ran. It
   replaces each pull request's capture, keeping the items and analysis of those it did not read
   again, and adds the days to `covered.txt`. A refusal prints its lines and writes nothing:
   rerun the step they name.
6. **Keep it.** Show the files changed under `<log>` and ask **Commit and open a pull request**
   (Recommended: on a branch `capture/<repo>-YYYY-MM-DD` in the standard's repository, this one when
   the standard is its own, pushed as `using-github` sets out; `prepare` reads a capture once it is
   on `main`, or in this working tree), **Leave it uncommitted**, the files named, which with a
   clone discards the capture when the clone is removed, its path named, or **Let's discuss**. A
   capture's pull request merges before the next capture: one branched from `main` without it reads
   its pull requests again and conflicts with it, so with one still open, say so first and ask
   **Wait for it to merge** (Recommended) or **Capture anyway**. A capture `prepare` runs is
   committed with its records, at its step 10.

End with one line per pull request from step 5's printout, the days covered, and what step 6 did.

A record and its items are as fresh as the last capture: `prepare` reads them as they were then,
so run `capture` before `prepare` to take the replies since.

## Never

Write a report, change a rule, or write outside `.review/` and `<log>`. Commit or push without the
yes step 6 asks for.
