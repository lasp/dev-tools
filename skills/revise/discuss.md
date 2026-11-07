# Questions about the report

`revise`'s answer to a question about a report or one of its proposals: how a proposal came
about, which cases it rests on, why the bar held it, what a person meant. It is asked at any
time, before the meeting, in it or after, with `/lasp-dev:revise <the question>`, or in `apply`
when a comment asks one, and nothing in the report changes for it. `<log>` and
`<standard files>` are where `revise`'s "The standard's repository" puts them.

**Which report.** With the standard in this repository, the report is in `<log>` here. With it
in another, this month's report is on the revision branch, `revision/<repo>-YYYY-MM`, until
`apply` merges it, not on the standard's `main`: read it in the clone `prepare` left when its path
is known, or through `using-github` from that branch, and the standard's `main` only for a month
already merged. The report is the month the question names, or else the newest one found; say
which month and branch it is in the answer's first line. When the month asked about has no
report where it should be, say so and name where it looked, rather than answering from another
month's, whose ids may name other proposals.

## Where each part of the evidence is

Answer from these files, read from the same place as the report, in this order, and from nothing remembered:

- **The proposal in the report:** its id, its Dial, its evidence pointers, its `said:` lines with
  the comments' URLs, its `Recommended:` line, and its `scope:`, `example:`, `bar:` and `probe:`
  lines; the Head's counts.
- **Its cluster:** `<log>/ratchet-YYYY-MM.clusters.txt`, the `guidance_clusters.py` printout the
  report was written from, beside the report. A proposal from a cluster names it, `C<n>`, among its
  evidence pointers; its `cluster`, `prs`, `people`, `asked`, `said`, `ask`, `drafted` and `note`
  lines give the principle, the pull requests and people counted, and the clearest quotes.
- **Each case:** `<log>/capture/pr-NNNN/`, one per pull request the cluster or the evidence names:
  `items.json`, every guidance item read from it with its verbatim quote, generality, kind and
  principle; `comment-list.json`, every comment with its author, authorship and thread, so a quote
  is read in its thread; `analysis.md`, the analyst's block; `body.md` and `pr.json`, the pull
  request itself. A record, `<log>/pr-NNNN.yaml`, gives a rule's findings and their verdicts.
- **The rule or entry it changes:** its entry in `<standard files>`, and the ledger's
  "Candidates below the criteria" for a held candidate's earlier evidence and `prs:` line.
- **The bar and the Dials:** `<plugin root>/standards/rule-bar.md` and `dials.md`, for why a
  proposal was held or admitted.

Answer in a few lines, the finding first: what the proposal rests on, then each case that bears
on the question with its pull request and the comment's URL, quoting the words it rests on as a
`said:` line does. Say which evidence was a person's and which an agent's, as the report marks it.
Where a link in the chain is missing, such as a report from before the clusters file was kept or
a pull request with no capture, say which file is missing and answer from what remains, never
filling the gap. When the evidence does not bear the proposal out, such as a quote that is one
pull request's case or a cluster joining two principles, say so: it is a reason the group may
decline or reword it.

## A question asked on the pull request

When the question is a comment on the draft pull request `prepare` opened, and the driver asks for
an answer there, read it and its thread through `using-github`, answer it as above, and show the
reply as it will be posted, with the attribution line `<plugin
root>/skills/pr-review/comment-style.md`, "AI assistance level", sets at the level the person
gives. Post it only on the person's yes, as a reply in that thread.
