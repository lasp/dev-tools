# Re-reviews

`pr-review` reads this when step 1.3 finds an earlier review, and on `gh` at step 1.3, as its
"Re-reviews" says. The steps named are `pr-review`'s.

The review is keyed to the commit it reviewed, not to the person who ran it. A posted summary
carries `reviewed: <full sha>`, and that line is what a later run looks for, and
`standards: <sha>`, or `none` without a standard, which the harvested record takes as its
`standards_sha`; a local review carries its `Head:` line. The head is the branch's latest
commit. Anyone may review again; the run says it is a re-review and which head the earlier one
covered.

- **A local review of the current head, not yet decided.** Ask: present it again and go on from
  step 3 without running the reviewer (Recommended); review afresh; or decide on posting now.
  This is what `work` routes to after the person stopped before deciding.
- **A local review of the current head, kept local.** Say the person chose to keep it
  local, and review afresh only when they ask.
- **A posted review names the current head.** Review afresh when the person asks for it: the
  findings are shown as usual, and step 2's deduplication leaves out every key that already has
  a thread, so only what is new can post. Name `/lasp-dev:pr-fix` for answering the threads
  already there.
- **The head has moved since a posted review.** Review a delta: findings on the lines the commits
  since the reviewed head changed; one on code the earlier review saw unchanged is left out, and
  the summary says how many. After a rebase onto a base that moved, the delta covers the pull
  request's own commits only, not what the base brought. Step 2's deduplication decides what is
  new: a key with a thread is not raised again, whatever its line. Say in the summary which
  commit the delta is against. A local review of an earlier head is replaced by a new file.
- **No review yet.** The full set.
- **On `gh`.** Read the reviews with `gh api repos/<owner>/<repo>/pulls/<n>/reviews`. When one is a
  findings review, its first line `## Review` and its body carrying the attribution line, the
  findings are presented but not posted: without the threads nothing can be deduplicated, and a
  delta needs the GitHub MCP server. Say so as `<plugin root>/skills/work/servers.md` sets out,
  the threads and the posting being what is lost.

Never post a second full set of findings: it doubles every finding and splits the verdicts across
two threads.
