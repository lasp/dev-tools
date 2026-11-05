# Refresh the context

Step 8 of `revise`'s `prepare.md`, loaded when the repository has `context/` entries
or a page or epic was named. Its proposals go under the report's "Proposals", and the
unreachable, unrefreshable and new pages under "Context".

Candidates only: no entry under `context/` is edited here. For each
entry, from the `Source:` and `Read:` lines `context/README.md` defines:
- A Confluence page: its current version and last-updated date, from one `confluence_search`
  on `id = <page>` (several entries in one query), which returns them without the body. For an
  entry missing from the results, run the blindness check `using-confluence` sets on its ID, and
  where search is blind take the version and date from the `page` task below instead. When the version is above the
  entry's `version`, or the date is later than its "page last updated" date, run one
  `source-reader` with the task `page <id>`, one per stale entry, launched as
  `<plugin root>/skills/revise/harvest.md`'s "Analysts" launches agents, and draft a
  candidate paragraph from its block, with the new dates and version, into
  `.review/harvest/context-refresh.md` beside the entry's current paragraph.
  A page the block lists as `Withheld:` gets no candidate paragraph: its question goes to the
  person, and the entry stays as it is until they clear it.
- A Jira epic: `jira_get_issue` and its `updated` field, the same way.
- A merged pull request: listed with its merged date, not re-read.
- No such header: listed as unrefreshable until someone adds it. A source gone or
  unreadable: listed under "unreachable" with the reason the tool gave; a server not connected
  or failing is said once, as `<plugin root>/skills/work/servers.md` sets out.

Then, under each page the project's `wiki.md` (`using-confluence`'s "The wiki") lists as watched for change by the monthly revision, list the pages created or updated since the previous
`ratchet-*.md`'s date (before the first, the earliest `Read:` date among the entries), from
one `confluence_search` per parent on `(id = <id> OR ancestor = <id>) AND lastModified >
"<date>"`, so an edit to the parent itself counts (a watched page may be one page), reading no page
body unless a title suggests a constraint. Where the blindness check finds search blind to the
space, fall back to `using-confluence`'s children read, comparing each child's version
with the previous refresh's record of it. Record every child's version in
`.review/harvest/context-refresh.md` so the next refresh has a baseline; on the first, every
child is listed as unseen. These are candidates for new entries, within the cap and the
retirement `context/README.md` states; at the cap, a new entry's proposal names the retirement
it displaces.

Each candidate joins the report's proposals in their form,
`- [ ] context/<name> · refresh · <source> · <old date> → <new date>`, marked in the session
like any other. A changed page whose ID appears in the plugin's `skills/`, or in the project's `tracker.md` or
`wiki.md`, is also a proposal for `correct`; where the server exposes `confluence_get_page_diff`, show what changed instead
of re-reading the body. An accepted refresh changes `<context>`, so its change goes where the archive
entries go, as `revise`'s "The standard's repository" sets out.
Bounds: the entries and the two parents, nothing else; one read per source.
