# A pull request or a slug as the source

Read by `ticket-draft` when its source is a pull request, or a slug whose page exists under
`.review/context/`. Each says what differs from the skill's steps; the rest runs as written.

## A pull request

Run `pr-reader` in `state` mode and read the dump's `body.md` and `pr.json`, then the branch's
diff against its base (`git diff <base>...<head>` on a fetched head), and draft the ticket from
them.

- Motivation opens with the line `Written after the change, from pull request <repo>#<n>`, and
  The code today describes the base branch, as `using-jira` says.
- `<ticket>.original.txt` holds the pull request body verbatim, as the baseline. The `Comment to
  post` takes its name and date from `pr.json`, the pull request's author and opened date; when
  the body has an Already checked block, its first line ends `(body written by pr-create)`, as
  `using-jira` says.
- The work exists, so there is no rough size, no split and no estimate, and the open questions
  do not hold the work back.
- **Refine <ticket key> instead** keeps these rules, since the work is still the pull request's:
  step 1 writes that ticket's description to `<key>.original.txt` as the baseline, the pull
  request body joins it as the person's words, and the hand-off below goes on with that key, with
  nothing to rename.
- The page's second line is `Branch: <the pull request's head branch>`, since the work is built
  there, not in this working tree, and `.review/context.md` is left as it is.
- **Hand-off.** Once step 8's write plan creates the ticket, or the person files it and gives the
  key, the page and its files carry the key as SKILL.md step 8 says. When `pr-review` invoked this skill, it carries on by itself with the
  key; otherwise the last line names `/lasp-dev:pr-review <n>` for an open pull request, to
  review it against the drafted criteria, and no next command for a merged or closed one. If the
  ticket is not filed yet, the page stays under its slug: point at `<slug>.jira.txt`; under
  `pr-review` the review goes on as for a pull request with no ticket.

## A page filed under a slug

As `work` names for a page with no key yet: ask for the ticket's key. If the ticket is not filed
yet, offer to create it from the page through a write plan, as SKILL.md steps 7 and 8 set out
(Recommended where the write tools are there), or point at `<slug>.jira.txt` and stop. With the
key, rename and re-key as SKILL.md step 8 says, and hand off as it says. A page whose ticket
carries "Written after the change, from pull request <repo>#<n>" is a pull request source, handed
off as above with that `<n>`. Never rewrite `<slug>.original.txt`.
