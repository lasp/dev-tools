# Contracts between the skills

The files and printouts one part of the plugin writes and another reads. Each section gives the
interface's version, its fields, who writes it and who reads it, and the test that holds it.
A change to an interface bumps its version here, and in the script that writes it where one
does; `check_static.py`'s `contracts` check fails when a section's test is gone.

## The `.review/` file map

Version: 1

Fields: one row per file or directory under `.review/`: the path, its writer, its reader, and when
it is cleared. The table is the README's `.review/` section; every `.review/` path a skill,
agent, hook or script names must have a row.

Writers: the skills, agents and hooks the table names. Readers: the skills, agents and hooks the
table names, and the session-start line.

Pinned by: tests/test_check_static.py::test_a_review_path_with_no_row_fails

## The build outcome

Version: 6

Fields: `.review/build/outcome.md`. Line 1 is `Build: <phrase>`, one of `passed`, `review cap
reached`, `a finding kept returning`, `blocked by a pre-existing failure: <what>` or `stopped for
a person: <why>`. Line 2 is `Depth: light | standard | deep`, the level the build ran at (version
2). `Reopened: <thread id> · <clause>` lines, copied from the reopened file `where.sh --fields`
names, which `pr-fix` writes when review reopens the design (version 3); the id is a thread's, or
`session-<pr>-<n>` for a reopen decided in a session, which widens the value and leaves the line's shape
unchanged. On a passed build, each failure that predates the change follows on its own
line. Then the `Rules checked:`, `Declined:`, `Suggestions:` and `Escalated:` lines, in
`skills/pr-create/body.md`'s Already checked format: `Rules checked:` entries `<key> fixed` or
`<key> declined`, separated by commas; `Declined:` entries `<key> — <reason>`, separated by
semicolons, so a reason holds none. Then one `Nominated:` line, the code corrections, and one
`Procedure:` line, the procedure corrections, each separated by semicolons (version 4). A resume
keeps the file and the build hook's block; `implement-change` removes it to go back into the
build (version 4). When a wave ran `downstream check`, a `Ripple: predicted <consumers or none> ·
verified <consumers or none> · breaks <consumers or none>` line, and on a bug fix a `Reproduced: <test>
failed before the fix` line (version 5). A build starting on another branch moves a finished
build, this file and the others under `.review/build/`, to `.review/build/done/<branch>/`, and a
build starting on that branch again moves it back (version 6).

Writers: `implement-change` step 8. Readers: `pr-create`, `work`, the session-start line
(`hooks/where.sh`), the build hook.

Pinned by: tests/test_where.sh::"a finished build is named, and the line ends at next"

## The plan's `Base:` line and the context page's `Branch:` line

Version: 9

Fields: `.review/implementation-plan-<key or branch>.md`, line 2 `Base: <branch>`, the branch the
build branched from; `.review/context/<ticket>.md` and its `.review/context.md` copy, line 1
`# <ticket> · <summary>`, from which `hooks/where.sh` reads the key only as its first word, a key
in the summary being another ticket's, or, when it opens with no key, the slug, a letter then
letters, digits, `.`, `_` or `-` (version 8), and line 2 `Branch: <branch>`, the
branch the ticket is built on, absent before it is branched. A page written from a cleared
controlled item opens with `Controlled: <key or ID> — <the warning>` above the heading, which is
then line 2 and `Branch:` line 3; `where.sh` reads the heading past it (version 9). A ticket in several pull requests
has one of each per part, `Base: <branch> (part k of n)` and `Branch: <branch> (part k of n)`
(version 2). The plan file also holds the brief, the settled questions,
`Approved by: <login>`, which `pr-create`'s `Plan:` line reads, a `Depth: <light | standard |
deep>` line, and the planner's `### Signatures` section, whose every line is `none`, a `Note:` line holding no signature line, or
`` `<signature>` · added|altered|removed|behavior · public|private ``, the signature in single or
doubled backticks and `behavior` the same signature doing something different (version 5). A
plan file with no `Approved by:` line is a draft, which `work` and the session-start line call
drafted and a resume takes back to the plan review (version 5); a login
that could not be read is written `Approved by: not recorded`. A `## Revision N — <thread id>`
section is approved by its own `Approved by:` line, a draft without one. A `Source:` line names
what the plan was built from, a ticket key, a file's path, an issue's URL or `prompt: <its first
sentence>` (version 4); a resume compares a new invocation's source with it, and with the ticket
key in the file name, and asks before resuming a plan for other work. A `## Provisional decisions`
section, absent when there are none, holds one entry per decision made for now, from the ticket's
Open Questions or the plan gate, with its answer, `Revisit because:`, `Affects:`, `Final when:` and
the steps that build on it (version 6). Versions 3 to 6 wrote a `Second reader: <name>` line at
deep; version 7 writes none, and nothing reads one in an older plan.

Writers: `implement-change` (the plan, and `Branch:` at step 6); `ticket-draft` (the page).
Readers: `pr-create` (`Base:`, `Approved by:`, `## Provisional decisions`), `work` and `hooks/where.sh` (the
heading, line 1 or line 2 after a `Controlled:` line, `Branch:`, `Approved by:`), `implement-change` on a resume (`Source:`, `Approved by:`, `Base:`, the
`## Revision` headings) and at step 8 (`Depth:`, and `## Corrections` for a depth lowered at the
plan gate) and step 9 (`## Provisional decisions`), `scripts/depth_floor.py --signatures` (`### Signatures`,
refusing any other line, and naming the shapes it takes). The `Base:` line has no test of its own yet.

Pinned by: tests/test_where.sh::"no key and a matching Branch: line uses the page"

## The Already checked block

Version: 10

Fields: the `<details><summary>Already checked</summary>` block of a built pull request's body,
which `skills/pr-create/body.md` places after Summary, Key design choices and open questions, What
was tested, How to test and What changed.
Required: `Build:`, `Plan:`, `Gates:` and `Tokens since the build started:`, which
`scripts/record.py`'s `REQUIRED_LINES` names. The build hook's `Gates:` line ends `· patterns:
the default profile's, no profile read`, `the repository's own, else the default profile's`,
`none, the profile is refused: <profile.py's message>`, or `none for <lint, types, tests>, which
the repository does not state` when the repository's profile could not be read, it has no
standard, its profile and the default values are both refused, or a gate pattern reads
`not yet recorded` (version 9), and with the wall clock otherwise (version 7). A build whose session made or
tried a Write, Edit or NotebookEdit in another repository while it was recorded, with the session's
working directory still in the build's repository, reads `Gates: not
recorded, this session also <edits> while its build was recorded here`, where `<edits>` joins with
` and ` one `edited <repository>`, or `tried to edit <repository>` when every attempt there was
refused, per repository, named by its top-level directory's name and never by a path or remote,
and `Tokens since the build started: not recorded` (version 10). A pattern a
profile leaves out takes the default profile's value as every left-out key does. Optional: `Depth:`, one of light, standard or
deep, read into the record's `inner.depth` (version 2); `Reopened:`, one line per reopened thread or `session-<pr>-<n>` reopen, read into the list
`inner.reopened` (version 3); `Nominated:` and `Procedure:`, the corrections a person made at the
plan and diff gates, read into `inner.nominated` and `inner.procedure` (version 4); `Reproduced:` and
`Ripple:`, read into `inner.reproduced` and `inner.ripple` (version 5); `Rules checked:` and `Declined:`, which its `OPTIONAL_LINES` names,
read into the record's `inner.fired` and `inner.declined`, each entry opening with a finding
key's citation, or `none`; `Suggestions:` and `Escalated:`, read by people. A line with nothing
after its label is refused. A body with no block was not built.

Writers: `pr-create`, from `.review/build/outcome.md` and `.review/build/already-checked.md`.
Readers: `scripts/record.py`, `pr-review`.

Pinned by: tests/test_check_static.py::test_a_plan_line_missing_from_body_md_fails_body

## The finding wire format

Version: 8

Fields: the review summary, a review in the verdict the person chose, COMMENT, REQUEST_CHANGES or
APPROVE, whose first line is `## Review` (or `## Standards review` on an earlier one) and that
carries the attribution line, with `reviewed: <full sha>` and `standards: <sha, or none>` lines;
any other review is a person's. Version 2: a person's review headed `## Review notes` no longer
reads as a summary. Version 3: a summary may carry any of the three verdicts, not COMMENT only,
and still reads as one once dismissed on GitHub (`DISMISSED`), since dismissal withdraws the
verdict, not the findings or the head they reviewed. A summary with the heading and the
attribution but no `reviewed:` line is broken output, and `scripts/record.py` refuses it.
Each finding's first comment: the severity line `**<level>** — <headline>`, the level one of
Must fix before merge, Should fix, Suggestion or Question; for a finding citing a rule or a
decision, what it cites, for the reader and read by no script; the body; `Proposed: <size>, <the
change>` except on a question; for a cited finding a `<details><summary>Standard</summary>` block
with `key: <finding key>`; and the attribution line. `scripts/record.py` reads the key from the
Standard block only, up to its `</details>`, in backticks or bare, a bare key ending at the
line's end and holding to the review contract's citations and its `::`. A finding with no key it
can read is named on stderr: `--state` lists it with the key `-` and its verdict, and its pull
request's record is refused (version 7). A reply a skill posts opens with its verdict
word, except an answer to a question, which opens with the answer itself; a person's reply may be
in their own words, which `pr-reader` judges (version 4). The `standards:` line ends
` + uncommitted` when the review ran on a rules file or decisions that are not committed, and
reads `none + uncommitted` for a standard that has never been (version 5). In a repository with
a standard elsewhere, the sha is the named repository's `standards/` commit, which
`.review/standard/source` records, and the suffix marks an uncommitted pointer (version 6); a
local checkout's is its last commit touching `standards/`, always with the suffix, or `none +
uncommitted` when it has none; and a standard
the person chose not to read gives `none`, since no rule was applied, which the summary's text
says (version 8). The line's grammar is unchanged.

Writers: `pr-review`, `pr-fix` (replies). Readers: `scripts/record.py`, `pr-reader`.

Pinned by: tests/test_check_static.py::test_a_renamed_summary_heading_fails_contract

## The local review

Version: 1

Fields: `.review/pr-<n>-review-submission.md`'s first two lines, `Head: <full sha>`, the head the
review is on, and `Posting: undecided | declined | posted <review URL>`, the person's choice; then
the `## Progress` checklist, the findings, none on a review that found nothing, and, once drafted,
the comments. A `Posting: declined`
review of the current head counts as reviewed for routing, and an `undecided` one sends `work`
back to `pr-review` to ask; neither leaves a record for the harvest. A file with `Head:` and no
`Posting:`, as `pr-review` wrote before version 1, routes as no local review.

Writers: `pr-review`. Readers: `scripts/next_phase.py --local-review`, `work`, `pr-review` on a
re-review.

Pinned by: tests/test_next_phase.py::test_a_review_kept_here_asks_whether_to_post_until_the_person_chooses

## The controlled clearance record

Version: 1

Fields: `controlled-cleared.json` in the `.review/` directory that holds a file opening with
`Controlled:`; one JSON object: `session_id`, the hook payload's `session_id`, and `cleared`, an
array of the items cleared in that session, each the text after `Controlled:` up to the first
` — ` or ` - `. The gate lets a read of a held file through when the record's `session_id` is the
call's and `cleared` lists the file's item; a record that does not parse in this shape clears
nothing.

Writers: `hooks/controlled-gate.sh post`, after a call that read a held file ran, or a Write of a
`.review/` file whose content opens with a `Controlled:` line, replacing a record from another
session. Readers: `hooks/controlled-gate.sh pre`.

Pinned by: tests/test_controlled_gate.py::test_once_a_read_ran_later_reads_of_that_item_in_the_session_pass

## The Jira approval record

Version: 1

Fields: `.review/jira-approval.json`, at the repository's top level, which the gate finds from the
hook payload's `cwd`; one JSON object:
`session`, the session id (`$CLAUDE_CODE_SESSION_ID`, the hook payload's `session_id`); `t`, the
epoch seconds it was written, a number; `items`, an array of `{"tool": <tool>, "target":
<target>}`, one per approved item, the tool named without its server prefix. The target is the
`project_key` for `jira_create_issue`, `<inward_issue_key> <outward_issue_key>` for
`jira_create_issue_link`, `<issue_key> <epic_key>` for `jira_link_to_epic`, and the `issue_key` for
`jira_update_issue`, `jira_add_comment`, `jira_transition_issue` and `jira_assign_issue`, as
mcp-atlassian 0.23.1 names its parameters. The gate allows a call of one of those seven tools from
the main session only when the record's session is the call's, `t` is under 30 minutes old and
not in the future, and an item matches the tool and target exactly; anything else, a record that
does not parse in this shape included, allows nothing and the call is asked about.

Writers: the write plan (`skills/using-jira/write-plan.md`, "Running it"), run by `ticket-draft`
and `ticket-audit`, at the person's yes; removed when the plan finishes or stops. Readers:
`hooks/atlassian-gate.sh`.

Pinned by: tests/test_atlassian_gate.sh::with this session's record, every write it lists is allowed

## The `--state` printout

Version: 5

Fields: `contract: 6`, `head:`, `draft:`, `state:`, `author:` (the login that opened the pull
request), `ticket:`, `build:`, one `findings review:`
line per findings review (or `findings review: none`), `threads: <n>`, then a header and one row
per thread: id, key or opener, severity or resolved, headline, path:line, verdict, contested,
replies after, proposed or outdated, after the verdict (on a Disagree, its whole reason on one
line; a judged reply's first line, or a judged Disagree's reason), judged (`no`, `yes, <login>: <basis>`, `yes, <login>, done:
<basis>` when the reply says the change was made, or `unclear: <basis>`). A `|` in any column is
printed `\|`, so a row splits on ` | ` into eleven columns. On a `discuss` row, replies after
counts only the replies after the pull request author's last one (version 2). Version 3 added the
judged column, and a person's thread the author answered with no word the judgment reads is
`unparsed`, where it was `none`. Version 4 added `author:`, which `scripts/next_phase.py` reads
against `--me`, so the author who answered a findings review goes on from the threads. Version 5
reads a thread the author opened in their own words as anyone's: `unanswered` until the author
answers it, or `unparsed` or judged once they reply in their own words, where it was `none`,
which is kept for one they opened with an AI-drafted comment. Version 6: a `findings review:`
row's `standards:` sha may end ` + uncommitted`, as the summary's line does.

When `record.py` refuses its judgments, `pr-reader` adds one line after the rows, `judgments
refused: <the reason>`, which `scripts/next_phase.py` skips.

Writers: `scripts/record.py --state`. Readers: `pr-reader`, which relays it to `work`, `pr-review`,
`pr-fix`, `ticket-draft` and `ticket-audit`; `scripts/next_phase.py`, which reads `author:` and, on a
row that is not a finding, its opener.

Pinned by: tests/test_record.py::test_the_state_header_names_every_column

## The agreed reply

Version: 1

Fields: the first line of the Agree that answers a thread, as the `--state` printout's after the
verdict column carries it, the word and its punctuation dropped: `fixed in <sha>: <what changed>`,
`reply only: <the response>`, `follow-up in <ticket or pull request>: <the response>` or `moved
to <pull request or repository>: <the response>`, the place one token and the response not empty.
`scripts/next_phase.py` reads an agreed thread with no reply after its Agree as answered when that
text is one of these forms or names a commit's sha anywhere; otherwise as awaiting its follow-up
reply when it names a follow-up or a later pull request, such as `in a follow-up (PROJ-900)`,
and as still to fix when it does not, a bare `Agree` included.

Writers: `pr-fix` steps 5 and 12, or the author by hand. Readers: `scripts/next_phase.py`.

Pinned by: tests/test_next_phase.py::test_an_agree_that_carries_its_response_is_answered

## The thread dump

Version: 6

Fields: `.review/threads/pr-NNNN/` (and `.review/harvest/threads/pr-NNNN/`): `pages/`, each
`pull_request_read` result as the server returned it, one file per call, from which
`scripts/thread_dump.py` writes the rest and refuses a page missing or an item without a field it
names; `pr.json`, the
`pull_request_read` `get` result, with `draft`, `state` and `merged`, and `merged_at` once it
merged, since the server leaves out an empty field rather than sending null (a review posted with
a batch of thread replies has no `body`); `reviews.json`,
`get_reviews`, paged 100 at a time, or at the smaller size `thread_dump.py --per-page` names, into one list; `comments.json`, `get_review_comments`, whose
`review_threads` carry GitHub's `is_resolved` and `is_outdated` flags; `issue-comments.json`,
`get_comments`, the conversation comments, paged as `get_reviews` is into one list; `body.md`, the pull request body. As the GitHub MCP
server returns them; each review in `reviews.json` carries its `html_url`, which `record.py`
reads the repository from and refuses a review without. Version 2 added `issue-comments.json`;
version 3 states the `html_url` requirement; version 4 added `pages/` and `thread_dump.py`'s
checks; version 5 has `thread_dump.py` refuse a directory not named `pr-NNNN`; version 6 lets a
list be paged below 100, named by `--per-page`, and has `save_page.py` refuse a response that is
not JSON, such as the harness's size-limit notice, and clear a pull request's
`get_review_comments` pages at its first page. Beside them, `judged.json`, "The
judgments", is `pr-reader`'s own.

Writers: `pr-reader`, copying each page `hooks/save-page.sh` saved under
`.review/pages/<owner>-<repo>/pr-NNNN/`, then `scripts/thread_dump.py`. Readers: `scripts/record.py`, `github-pr-fix-planner`, `thread-analyst`;
`ticket-draft`, for a pull request's body and its answers; `scripts/merge_commit.py`, run by
`revise` and `onboard`, for each merge commit.

Pinned by: tests/test_record.py::test_a_comment_without_its_date_is_refused_naming_its_position

## The comment list

Version: 1

Fields: `.review/harvest/threads/pr-NNNN/comment-list.json`, a JSON object: `pr`, the pull
request's number, and `comments`, every comment in its dump, ordered by `created` then `id` and
empty when no one commented: each review thread's opening comment and
every reply in it, each review whose summary is not blank, and each conversation comment, a bot's
and the pull request author's included. Each item has exactly these keys: `pr`, the number; `id`,
the comment's number (a review comment's from its `html_url`'s `#discussion_r<n>`); `url`;
`author`, the login; `authorship`, `human`, `ai-drafted` or `bot`, as "The record"'s "Authorship"
reads this comment alone; `kind`, `thread`, `reply`, `review` or `comment`; `thread`, the review
thread's id, null for a review or a conversation comment; `path` and `line`, where the comment
anchors, `line` its `original_line`, the line in the commit it was made on, else `line`, null at
file level, both null for a review or a conversation comment; `created`,
GitHub's timestamp (`created_at`, or a review's `submitted_at`); and `body`, the text unchanged.

Every comment is listed, a reply as much as the comment that opened its thread: guidance is read
per comment, apart from how a thread was settled, which the record and `thread-analyst` judge per
thread.

`scripts/comment_list.py <dump> [...]` writes it from a dump `scripts/thread_dump.py` wrote, and
prints `wrote <path>: <n> comments, <n> human, <n> ai-drafted, <n> bot` per dump. An `id` is
unique in the list, since a reader names a comment by its number alone. It exits 1 with the
reason, writing nothing for any dump given, for a dump directory not named `pr-NNNN`, one of
`comments.json`, `reviews.json` and `issue-comments.json` missing or not JSON,
a review comment whose `html_url` has no `#discussion_r<n>`, a review with a body but no
`submitted_at`, an id given twice, across kinds as well as within one, or a profile `record.py`
refuses.

Writers: `scripts/comment_list.py`, run by harvest.md's "Records". Readers: none in the plugin;
it is the input a guidance extraction reads.

Pinned by: tests/test_comment_list.py::test_lists_every_comment_with_its_own_authorship

## The judgments

Version: 1

Fields: `judged.json` in the dump, a JSON list, `[]` when nothing is undecided, one entry per
thread `record.py --undecided` lists: `thread`, its id; `reply`, the index, into the thread's
replies from people, of the eligible reply that decides it, `null` when `unclear`; `verdict`,
`agree`, `disagree`, `discuss`, `answered` (a person's thread's question answered) or `unclear`;
`reason`, a Disagree's reason, a verbatim excerpt of the reply, else empty; `done`, true on an
agree whose reply says the change was made; `basis`, one line saying what decided it. A thread or
reply `--undecided` does not list, so any reply with a verdict word, is refused, as is `answered`
on a finding or after the author's Discuss, `done` on anything but an agree, a reason not in the reply's words and a basis that
is not one line.

Writers: `pr-reader`. Readers: `scripts/record.py --judged`.

Pinned by: tests/test_record.py::test_a_judgment_outside_what_the_words_leave_open_is_refused

## The local facts

Version: 8

Fields: `hooks/where.sh --fields`, one `name=value` per line: `ticket`, `branch` (empty with
none, a detached HEAD included; version 5), `context` (the ticket's context page as an absolute path, or empty; version 5), `plan`
(the plan file's absolute path, existing or not, or empty with neither a ticket nor a branch; version 5), `base` (the
plan's `Base:`), `outcome` (the first line of this branch's `outcome.md`, current or parked under
`.review/build/done/<branch>/` (version 3), or empty),
`outcome_reopened` (the thread ids on that file's `Reopened:` lines, space-separated, or empty;
version 2), `build_branch`, `dirty` (`true` or `false`; an untracked file counts only when made since the build started, or when there is no build, version 5), `lock` (the skill a live `.review/lock` names, whichever
session holds it, or empty; a lock untouched for four hours is stale and empty here, version 3), `profile` (the profile's `source`, a
file or `none`, or empty when the profile was not read; version 7), `part` (`k of n`, or empty), `reopened` (the ids, a thread's or
`session-<pr>-<n>`, of the reopened file, space-separated, or empty), `reopened_file` (that file's absolute path,
`.review/reopened/<ticket>.txt`, or with no ticket `.review/reopened/<branch, / as ->.txt`, whether
or not it exists, or empty with neither; version 4), `slug` (a ticket `ticket-draft` drafted
and nobody filed: the slug `.review/context.md`'s first line opens with, as the context page's
line 1 defines it, when `.review/context/<slug>.md` exists and the page has no `Branch:`
line or one naming this branch, with `ticket` and `context` empty; else empty; version 6) and
`elsewhere` (the first branch the ticket's context page names when none of its `Branch:` lines
names this one, or empty).
`--fields --ticket <key>` takes the ticket from the key. A key, from the branch name or `--ticket`,
is matched ignoring case and written as found when the pattern matches it exactly, else
upper-cased, so `proj-775-x` gives `PROJ-775`. A branch whose key matches only ignoring case
and that has its own plan, `.review/implementation-plan-<branch>.md`, stays its own work, with no
ticket (version 8). The files are read from the
repository's top level, wherever in it the command runs (version 5). The lines print with or without
`.review/`; a key outside the profile's pattern, another argument, no `jq`, or a reopened line
that is not `Reopened: <id> · <clause>` exits 1.

Writers: `hooks/where.sh`. Readers: `scripts/next_phase.py`, `work`, `pr-create`, `pr-fix`,
`implement-change`.

Pinned by: tests/test_where.sh::"--fields prints the facts, one per line, on a clean tree"

## The next phase

Version: 4

Fields: `scripts/next_phase.py`'s printout: `phase:` (a skill, or `nothing`), `argument:`,
`why:` (the row's name in the script's table, `review-unposted` among them from version 3), `lock:`
(the skill a live `.review/lock` names when the phase is `implement-change` or `pr-fix`, else
`none`; a lock untouched for four hours is stale and `none`, version 2), then the three lines
`work` says. Version 3 reads the local review (`--local-review`), so a review the person kept
local routes on. Version 4 reads the fields' `slug=`: a ticket drafted and not filed is `phase:
nothing`, `argument: <slug>`, `why: unfiled`, whose second line names
`.review/context/<slug>.jira.txt`; `--slug` is gone. Fields with a `slug` and a `ticket` or a
`context` exit 1.

Writers: `scripts/next_phase.py`. Readers: `work`.

Pinned by: tests/test_next_phase.py::test_it_prints_the_three_lines_work_says

## The standard pointer

Version: 2

Fields: `standards/profile.yaml` in a code repository whose standard is elsewhere, holding one
line, `standard: <owner>/<repo>`, quoted or not, comments and a carriage return allowed, naming
the repository whose `standards/` is this one's standard (version 2; version 1 was a
separate pointer file); git's config `lasp-dev.standard`, per clone, unset, the absolute
path of a local checkout of that repository for a trial, read as it stands and refused when its
`origin` names another repository, or `none`, the person's choice to go on without the standard
when it cannot be fetched; and `.review/standard/source`, one line, `<owner>/<repo>@<7-character
sha>`, the newest commit on the named repository's default branch touching its `standards/`, or
`@local` or `@none`. A pointer beside any other line, or beside the repository's own
`standards/review-rules.md` or `standards/decisions.md`, is refused, as is a repository that
cannot be fetched, and one with neither a ledger nor decisions there.

Writers: the person, or `onboard` at its step 5 on the person's yes, for the pointer and the config; `scripts/standard_file.sh`, for
`.review/standard/source`, through `scripts/standard.sh`, which fetches the named repository into
a partial clone in the git directory, writes the commit's `standards/` out beside it, and prints
`<owner>/<repo>`, that directory and the commit, `local` or `none` (`-` for the directory).
Readers: `scripts/standard_file.sh`; `scripts/profile.py`, for the standard's settings
(`standard.sh --cached`, which reads offline once a fetch has written the files, marked by the
cache's ref `refs/lasp-dev/standards`, and fetches only before one has; `--offline`, under
`STANDARD_OFFLINE`, as the hooks set it, never fetches and refuses a clone that has not, though
`hooks/rules.sh` first runs `--cached` itself, so a clone's first session fetches once, and after
a failed fetch, marked by `lasp-dev/first-fetch-failed` in the git directory, not again for a day), and
`--standard`, which prints the directory; `pr-review`, whose `standards:` line takes the sha;
`quickstart`, `onboard`, `revise`, `work` and `scripts/survey.py`, for whether the repository has
a standard.

Pinned by: tests/test_standard_file.sh::"a pointer writes the fetched ledger, decisions and terminology"

## The no-rules-file line

Version: 1

Fields: the first line of `work`'s reply in a repository with no `standards/review-rules.md`, word
for word: `no rules file here: the build, the pull request and a review run without rule
citations`.

Writers: `work` step 1. Readers: the `no-standard` scenario in `sandbox/scenarios.yaml`, whose
`look_at` names it.

Pinned by: tests/test_sandbox.py::test_the_no_standard_scenario_quotes_works_no_rules_file_line

## The profile

Version: 15

Fields: each key is, first, the repository's standard's, read in the working directory's checkout
when it is that repository, the owner being the argument's, or the `origin` remote's, never the
`upstream` remote's, so a fork reads its own `origin` (version 15): its own
`standards/`, as it stands, committed or not, or the standard its pointer names ("The standard
pointer"); for another repository of the same owner, that standard when its `profiles/` covers the
repository, as a revision harvesting every repository a standard covers reads it, and a standard
there that is refused or cannot be fetched refuses that query too. A standard with a `profiles/`
directory covers several repositories: its `profile.yaml` holds only the project settings,
`ticket`, `posted_text`, `github_server`, `jira`, `internal`, `attribution` and `surface`, and
`profiles/<repo>.yaml` only each repository's own, the rest; a setting in the other file, a pointer
from a repository with no file there, a pointer to a standard with no `profiles/`, and a pointer in
the standard's own `profile.yaml` are refused (version 13). The standard's own repository, its
`standards/` holding `profiles/` and no file of its own, reads the project settings alone, so a
misnamed file of a repository that both holds and joins the standard reads the same; its `source`
line, which names no `profiles/` file, is the sign. Then what `survey.py` detects in that checkout,
cached as `lasp-dev/detected/<commit>-<top>-<hash>.yaml` in its git directory, per plugin top
level, and a survey that fails is refused; and otherwise the plugin's default profile's,
`standards/default-profile.yaml`, which reads `not yet recorded` for what only a repository can
give (version 11): `ticket` (`pattern`, `project`), `public`, `template`, `downstream`, `tests`
(`command`), `coverage` (`command`), `lint` (`command`, `regex`), `types` (`regex`), `gates`
(`tests`), `github_server`, `posted_text`, `depth` (`light`, `deep`), `corpus` gone (version 13).
No team layer is read: its owners, team files, profiles and the fork refusal are gone
(version 15). Any value but the project sections' below may read `not yet recorded`, and a
standard sets a section whole: one whose section reads `not yet recorded`, other than `jira`, is
refused. `scripts/profile.py`'s `SCHEMA` defines the shapes, and the default profile under a
standard's settings is refused when it leaves a key out or has a key the schema does not know.
`profile.py --standard` prints the absolute path of the standard's directory of the working
directory's checkout, when it is the repository: the fetched standard its pointer names, or its own
`standards/`; a checkout with neither exits 1, its message ending `the repository has no
standard`, and any other exit 1 is a refusal: a working directory that is not the repository's
checkout, a pointer that cannot be read, a standard not read, and anything `profile.py <repo>`
refuses but what is detected, such as a standard that does not cover the repository or that the
schema refuses (version 15).
Sections a standard's project settings and the default profile set, and a standard's
`profiles/<repo>.yaml` does not: `jira`
(`statuses`, each `{name, next}` with `next` one of `ticket-draft`, `implement-change` or `nothing`,
read by `next_phase.py` for a ticket with no context page, and a `role` on the statuses the generic
skills name by role, each of `filed`, `approved`, `implementation`, `finished` and `abandoned` on
exactly one status, which `--defaults` prints as `jira.roles`, so `--defaults --field
jira.roles.finished` prints that status's name (version 8); `pr_statuses`, each one of the
statuses) and `internal` (`domains`, bare host names, the hosts `transcript_excerpt.py` redacts,
the default profile's and the working directory's standard's together (version 15),
and which exits 1 before printing when they cannot be read; `private_repositories`, bare
repository names, for each of which `public` prints `false` and a profile setting it `true` is
refused, ignoring case (version 5)), `attribution` (`phrases`, the wordings beside the review's
attribution line that `record.py` reads as marking a comment AI-drafted, case aside, none of them
empty, the working directory's repository's (version 13)) and `surface` (`identifiers`, the enum classes whose members `surface_diff.py` lists as
`identifier`, each a Python class name) (version 10); either may be an empty list, and no field of
`jira`, `internal`, `attribution` or `surface` may read `not yet recorded`. The default profile's
`jira` reads `not yet recorded`, and its `internal` lists no domain and no repository, so a
repository takes a workflow and internal hosts only from its standard: with none,
`--defaults --field jira.roles`, `jira.roles.<role>` and `jira.pr_statuses` print `not yet
recorded`, `next_phase.py` routes every ticket status to ticket-draft, as with no status read,
naming the status in its reason, and a standard that sets `jira` sets both its fields (version
14). A status named twice, ignoring case, or with spaces around it is refused. The default
profile's `depth.light` is `CHANGELOG.md`, `README.md`, `docs/**/*.md` and `doc/**/*.md` at the
documentation brief, so no skill, agent file, `CLAUDE.md`, `AGENTS.md` or instruction file is
light without a profile that says so (version 2). A `ticket.pattern` or a `hunk` that is not a
regular expression is refused, as is a `template` that is not a bare name, a directory of the
standard's `templates/` (version 15). `profile.py` prints `source: ` the standard's files it read,
joined by `, `, a fetched standard's as `<owner>/<repo>@<sha>:standards/<file>` (version 13); or
`source: none` for a repository with no standard, which runs on the detected and default values,
as its first line, and that value alone with `--field source` (version 2). `profile.py --defaults`
prints the default profile's values under the working directory's repository's standard's, with
no `source` line (version 15); `scripts/profile.sh` reads them when the repository has no remote
or its profile is refused, and gives their value for a field the profile reads as `not yet
recorded`. A standard or a default profile the schema refuses, or a standard elsewhere that cannot
be fetched, or under `STANDARD_OFFLINE` has not been (version 13), is refused for `--defaults`
too, so it gets no values: the session-start line then reads `profile refused: <profile.py's
message> · <branch>` (version 11). With no python3, a hook matches no ticket key, reads no context
page as a ticket and counts no gate, and `standard_file.sh` exits 1 (version 3). `PROFILE_SHADOW_ROOT`
and the shadow read are gone, with `.review/profile-shadow.log` and exit 3 (version 15).

Writers: `onboard`, on the person's yes at its step 5: the drop-in's settled keys and their derived gates, `public`
and, for a new standard, `.review/onboard/project.yaml` with a `decisions.md` holding none yet, into the standard's `profile.yaml` or,
for a standard covering several repositories, its `profiles/<repo>.yaml`, with the pointer here; people, by hand from `standards/profile.example.yaml`;
the plugin, `standards/default-profile.yaml`; each repository's
maintainers, its `standards/profile.yaml`; and `profile.py`, through `survey.py --drop-in`, the
detected cache.
Readers: `scripts/profile.py`, and through it the hooks, `standard_file.sh`, `record.py`, `depth_floor.py`, `next_phase.py` (`jira`), `transcript_excerpt.py` (`internal`) and the skills, `writing`'s `short.md` among them (`public`, `internal.domains`), and `write-plan.md`, `ticket-audit`, `ticket-draft` and `source-reader` (`jira.roles`); `source`
is read by `hooks/where.sh` into its `profile=` field, the build hook's Gates line and
`quickstart`.

Pinned by: tests/test_profile.py::test_a_value_of_the_wrong_shape

## The record

Version: 13

Fields: `<log>/pr-NNNN.yaml`, `<log>` the records directory `revise`'s "The standard's repository"
names, first line `contract: 13`. This section is the one
place the fields are defined; the records directory's own README says how the revision
reads them.

- `pr`, the number; `ticket`, the key on the body's `Ticket:` line in the profile's ticket
  pattern, or `none`.
- `stack`, `{part, of, base}` from that line's `part k of n · base: <branch>`, and `claims`, the
  list on the body's `Claims:` line, the criteria this part claims; each `none` when absent.
- `branch`, the head branch; `head`, the commit the last findings review reviewed, or the merge
  or head commit when there was none. A record whose head is behind the branch at merge is
  missing what came after.
- `date`, the local day of the first findings review, which makes a record whoever posted it, or, when there was none, of the first
  thing a reviewer, a person other than the pull request's author, wrote in a review thread, a
  review summary or a conversation comment, or of the first thread the author opened in their own
  words; `merged`, the UTC day the pull request merged, as the harvest's `merged:>=` search
  compares it, by which the revision places a record in a window.
- `standards_sha`, the `standards/` commit the reviewer ran against, the named repository's in
  a repository whose standard is elsewhere, `none` with no findings review or no standard, ending ` + uncommitted` as the summary's line does, so
  `none + uncommitted` is a standard nobody has committed yet; `profile`, the name of the repository whose profile the
  review ran under; `adjudicated_by`, the logins that settled a finding or answered a cited question, or `none`.
  `scripts/ratchet_counts.py` ages a rule only by a record whose `standards_sha` or `inner` is not
  `none`, or that cites a rule: a pull request the rules were run on.
- `build` and `plan`, the Already checked block's `Build:` phrase and `Plan:` line, and `inner`,
  the build's own lines; all three `none` when the body has no block. `inner` holds `gates` and
  `tokens`, the block's lines; `depth`, `light`, `standard`, `deep` or `none`; `reopened`, a
  list, one `<thread id, or session-<pr>-<n>> · <clause>` per `Reopened:` line; `fired` and `declined`, the build's
  own findings, from `Rules checked:` and `Declined:`; `nominated` and `procedure`, the code and
  procedure corrections a person made at the plan and diff gates; `reproduced`, a bug fix's
  `Reproduced:` line, `none` on any other build; `ripple`, `{predicted, verified, breaks}`, three
  lists of consumers from the `Ripple:` line, `none` when `downstream check` did not run.
- `author`, the login that opened the pull request.
- `rework_rounds`, one entry per findings review at a new head: `round`, `commits` (the range
  from the previous reviewed head), `sent_back_by` (the keys of the round's agreed findings,
  empty when none was agreed), `applied` and `declined` (counts); `[]` with fewer than two
  reviewed heads.
- `findings:`, every cited finding: `key` (the full finding key `review-contract.md` defines),
  `severity`, `at` (the file and line, or the file alone at file level), `thread` (the review thread the verdict was read from),
  `verdict` (agree, disagree, discuss, unanswered, unparsed or contested), with `judged: true` and
  `basis:` when it was judged from a reply's own words, and `done: true` when that reply said the
  change was made, or `basis:` alone when the judge could not tell, `reason` on a
  disagree that gives one, and `by`, the login of the reply that settled it, absent on a finding
  not settled, a discuss included. A must-fix or should-fix answered Disagree with no reason is
  `unanswered` with `why: "disagree with no reason"`; an unparsed finding carries `line:`, the
  first line of the reply that left it open; a finding two reviewers answered differently carries
  `contested: true` and both original lines, `lines:`, beside the verdict the author settled on,
  or `verdict: contested` while the author has not settled it. A finding whose first line is not
  one of the four severity lines has `severity: unparsed`, `verdict: unparsed` and `line:`, that
  first line; its replies are not read, since the severity decides how they read.
  `scripts/ratchet_counts.py` counts it as a firing in its `unlabeled` column, not with the
  unanswered.
- `questions:`, every cited question: `q`, `key`, `at`, `thread`, and `a`, the answer, or
  `unanswered: true`.
- `threads:`, a pointer to every other review thread: a person's, a bot's, or a finding posted
  with no key. Each carries `thread`; `by`, its opener, `bot` for a bot or `review` for an uncited
  finding, which also carries its `severity`, `unparsed` with `verdict: unparsed` and `line:` as
  on a finding; `authorship` of its opening comment, as
  "Authorship" below defines it; `at`; `opened`, the day; `resolved` and `outdated`, GitHub's flags; `replies`,
  the count from people; `verdict`, an uncited finding's read as a finding's, otherwise the pull
  request author's from the first of their replies that starts with one of the three words, or
  judged from one in their own words (`judged`, `basis` and `done` as on a finding), a Discuss
  settled by their next Agree or Disagree, `answered` when the judge read their reply as
  answering a question, `unanswered` when the author never replied, on a thread someone else
  opened or one they opened in their own words, `unparsed` with `line:` when their replies there
  carry no word and no judgment reads them, and `none` on a thread the author opened with an
  AI-drafted comment; `reason` on a disagree; and `a`, an uncited
  question's answer.
- `reviews:`, a pointer to every review that is not a findings review and whose summary is not
  blank: `review`, the id; `by`, `bot` for a bot; `authorship`, read outside quoted lines;
  `state` (`approved`, `changes_requested`, `commented` or `dismissed`); `submitted`, the day;
  `commit`; and `headline`, the summary's first line that is not quoted. A bot's and the pull
  request author's are listed too, and a person's, the author's included, may be an ask.
- `comments:`, a pointer to every conversation comment under the pull request: `comment`, the
  id; `by`; `authorship`; `posted`, the day; and `headline`, as for `reviews:`.

Version 2 added `profile` and `inner.depth`; a record without a `contract:` line predates both.
Version 3 added `merged`, by which `ratchet_counts.py` places a record in a window and in the
expiry counts; a record of an earlier version, which has none, is placed in neither and counted
in "all records", and one the window's merged pull requests name is refused. Version 4 added
`stack`, `claims` and `inner.reopened`, version 5 `inner.nominated` and `inner.procedure`,
version 6 `inner.reproduced` and `inner.ripple`, version 7 `reviews:` and `comments:`, version 8
`judged`, `basis` and `done`, and `unparsed` and `answered` on a person's thread, and version 9
`unanswered`, or `unparsed` or judged once the author replies in their own words, on a thread the
author opened in their own words, by which a pull request whose only review is the author's own
has a record. Version 10: `standards_sha` may end ` + uncommitted`; a record of an earlier
version without it may still have run on uncommitted standards. Version 11: in a repository whose
standard is elsewhere, `standards_sha` is the named repository's commit, not this one's.
Version 12: a finding whose severity label is not one of the four is recorded with `severity:
unparsed`, where earlier versions refused the record of its pull request.
Version 13: `authorship` reads the signatures under "Authorship" as well as the attribution line
and the standard's phrases, so a reply reworded from the attribution line, and an agent's own
signature, read `ai-drafted` where earlier versions read `human`; a thread the author opened that
way reads `verdict: none`, where it read `unanswered` or `unparsed`.

A harvested record reaches the log through `scripts/archive_records.py`, which refuses to
replace a record whose findings, counted per rule, the harvested one falls short of, unless told
to keep that record as it is, and refuses that keep when the harvested record holds findings the
log's lacks.

Writers: `scripts/record.py`, run by `pr-reader` at the harvest; `scripts/archive_records.py`
copies it into the log. Readers:
`scripts/ratchet_counts.py`, `revise`; `thread-analyst`, for each thread's, review's and
comment's `authorship`.

### Authorship

`scripts/record.py`'s `authorship_of` decides who wrote one comment, and every reader of a
comment's authorship uses it: the record's `threads:`, `reviews:` and `comments:`. It reads the
comment alone, never its thread, so a person's reply in a thread an agent opened is `human`. It
reads the comment's own lines that are not blank: not the lines that open `>`, which quote someone
else, and not a fenced code block, which shows text rather than signs the comment; a fence closes on
a line of its own character, at least as long, with nothing after it. Case is ignored.

- `bot`: the login ends `[bot]` or is one of the review bots `BOT_LOGINS` names.
- `ai-drafted`: its own lines carry the review's attribution line, `AI-assisted comment, posted
  by @` or the earlier `AI-assisted comment, reviewed and approved by @`, or one of the
  `attribution.phrases` of the repository's standard; or its first or last own line, where an
  agent signs, with its inline code spans removed, has one of the shapes `AI_SIGNATURES` lists:
  - a line that opens or closes with `🤖` and carries `AI-assisted`, as any rewording of the
    attribution line keeps them (`pr-review/comment-style.md`);
  - a line that ends with `AI assistance level: <n>/5`, its meaning in parentheses after it, and
    no `?`;
  - a line that opens with markup, such as `🤖 *` or `_`, then `comment`, `reply`, `review` or
    `summary`, optionally `this` before it and `was` or `is` after, then `generated`, `drafted`
    or `written`, `by` or `with`, and `Claude`, `Copilot`, or `a` or `an` then `AI` or `LLM`, with no
    `?` after it;
  - a line that opens with `🤖` and then `generated by` or `generated with`;
  - a line that is, after any markup, `generated by Claude Code` or `generated with Claude
    Code`, the name bracketed with its link or not, and nothing after it but punctuation;
  - a line opening `Co-Authored-By: Claude`, so a person who pastes that trailer as their comment's
    first or last line fences it.
- `human`: none of these. A comment that gives no sign is a person's.

A person's sentence about a signature, such as "is this review generated by Copilot?" or "please
add AI assistance level: 3/5 to your replies", has no signature's shape and reads `human`. Every
level of the assistance scale reads `ai-drafted`, 1/5 included: the line says an agent posted the
text, and the level is the person's own account of how much of it they wrote.

Pinned by: tests/test_record.py::test_reproduces_the_committed_record

## The correction and note records

Version: 1

Fields: `<log>/correction-<YYYY-MM-DD>-<id>.yaml` and `<log>/note-<YYYY-MM-DD>-<id>.yaml`, beside
the records, one `<field>: <value>`
per line. `scripts/ratchet_counts.py` reads every `correction-*.yaml` and `note-*.yaml` in the
log directory it is given. Both carry `date: YYYY-MM-DD`; `ids: [<id>, …]`, a list on one line,
not empty, of every ID the correction touched or the note concerns, each cited as a finding key
cites it (`R-012`, `D-004@libera_utils`, `term/T-010`), or a skill's or agent's name on a
procedure note, and each counted under the rule a finding key with that citation counts under;
`kind`; and `by`, the person who ran it. A correction adds `source`, what was read and its
version; `clause`, what was misread, in one clause; and `pull_requests`, a list a person fills in.
`kind` is `misread`, `source-changed` or `settled` on a correction and `disagreement` on a note,
which adds `reason` and, when there is one, `thread`. `procedure`, on either, is no longer
written, since `correct` drafts a `skill-feedback` issue for a procedure complaint, and stays
valid so a record written before still parses.
A correction with no `date`, `ids`, `kind`, `source`, `by` or `clause` line, or a note with no
`date`, `ids`, `kind` or `by` line, is refused whatever its date; with `--since`, so is a `date:`
that is not `YYYY-MM-DD` alone on its line. The script reads neither `kind`'s value nor
`pull_requests`, `reason` or `thread`. Each record is a count per rule, never evidence.

Writers: `revise` `correct`, a correction at step 7, on a commit answer at step 6, and a note at
step 2, in the revision's `<log>` (`revise`'s "The standard's repository"). Readers: `scripts/ratchet_counts.py`, into its `corrections` and
`notes` columns; `revise`, which reports them in the Head as counts and takes a
correction's `date` as the cut between the verdicts before and after it; `revise`
`prepare` step 2, which reads each note whose `kind` is `procedure`, with its `ids` and `thread`,
into About the procedure and a `skill-feedback` draft unless it is settled; `revise` `correct` step 1, the prior corrections
naming an ID.

Pinned by: tests/test_ratchet_counts.py::test_corrects_correction_and_note_are_counted_under_each_id

## The revision report's `window:` line

Version: 1

Fields: the first line of `<log>/ratchet-YYYY-MM.md`, `window: <from>..<to>`, the
first and last days the report covers, each `YYYY-MM-DD`. `<from>` is the day after the previous
report's `<to>`, the newest report in any `<log>` of the standard, or before the first report the
repository's adoption date, as `skills/revise/SKILL.md` "The standard's repository" defines it, and is the `--since` day `ratchet_counts.py` is given. The lines after it,
one per caveat that applies, hold the report's caveats, as `skills/revise/outline.md`
lists them.

Writers: `revise` `prepare`, in the report `skills/revise/outline.md` outlines.
Readers: `revise`, which starts the next window from it (`SKILL.md` "Options").

Pinned by: tests/test_ratchet_counts.py::test_the_outlines_window_line_is_the_form_revise_reads

## The ledger's bar lines

Version: 3

Fields: two optional lines of a ledger entry in an adopting repository's
`standards/review-rules.md`. `scope: <glob>[, <glob>]`, paths relative to the repository.
`example: fires on <anchor or thread>; not on <anchor>`, where an anchor is `<repo>#<PR>@<sha>
<path>::<symbol> "<shape>"` and a thread is `<repo>#<PR> <thread id>`. `scripts/rule_lint.py`'s
`ANCHOR` and `THREAD` are the one copy of both forms. `standards/rule-bar.md` says what each must
hold. `repos: [<repo>, ...]`, on a rule in the ledger or a decision in `decisions.md` of a
standard covering several repositories, a flow list of repository names, each with a
`profiles/<repo>.yaml` there, matched ignoring case: the rule or decision applies only in those
repositories, and one without the line applies in all of them. It is one line, `repos:` at its
start, anywhere in the block outside a code fence and outside the rule's wording; a block with two
is refused by the lint, and only the first is read (version 2). A rule's wording is the entry's `> ` lines, the one
copy; a ledger whose wording is still in an instruction file has none there and a `Wording:` link
to its heading instead (version 3).

Writers: `onboard`'s first rules and `revise` (`apply` and `correct`). Readers:
`scripts/rule_lint.py`, `scripts/window_merges.py`, for `scope:`, and `rule-probe`;
`scripts/standard_file.sh`, which loads a tagged rule or decision only in a repository its line
names, and exits 1 naming a block whose first line is not that flow list; `scripts/rule_lint.py`'s
fields gate and `scripts/ratchet_counts.py --repo`, for `repos:`; `scripts/standard_file.sh
--rules`, which `hooks/rules.sh` runs at session start, for the wording of the live reviewer-tier
rules that apply.

Pinned by: tests/test_rule_lint.py::test_the_anchor_form_parses

## The window's merges

Version: 2

Fields: `scripts/window_merges.py`'s printout. One line per pull request merged into `--ref` from
`--since` on, oldest first, `pr-NNNN <full sha> <YYYY-MM-DD> <path> [<path> ...]`, the merge's
committer date as a UTC day, as GitHub's `merged_at` reads, and the files it changed against its
first parent; with `--ledger`, then one line per live reviewer-tier rule in
ledger order: `R-NNN pr-NNNN [pr-NNNN ...]`, `R-NNN none`, `R-NNN predates pr-NNNN [...]` and
`R-NNN not swept: no scope`. A pull request is named by its merge subject as
`scripts/merge_commit.py`'s `pr_numbers` reads it. With `--doc` and `--dumps`, then per document
in the order given: `doc <path>: pr-NNNN [...]` or `doc <path>: none`, the pull requests opened,
by their `pr.json`'s `created_at`, at or after the latest commit on `--ref`'s first-parent history
that adds the document; `doc <path>: predates pr-NNNN [...]`, those opened before; `doc <path>: no
opened day pr-NNNN [...]`, those with no `pr.json`; or `doc <path>: not on <ref>` alone (version 2).
A `--dumps` that is not a directory exits 2.

Writers: `scripts/window_merges.py`. Readers: `revise` `prepare` step 2, which gives each
`diff-probe` the rules whose line names its pull request, and each `every change` claim whose
document's `doc` line names it.

Pinned by: tests/test_window_merges.py::test_a_document_judges_only_the_pull_requests_opened_after_it_reached_main

## The ledger's held-candidates heading

Version: 1

Fields: the line `## Candidates below the criteria`, word for word, trailing whitespace allowed,
in an adopting repository's `standards/review-rules.md`. Everything from it to the end of the
file is the held candidates, each with its evidence and the criterion or check it fails, so the
section is the ledger's last. `scripts/standard_file.sh` writes the ledger into the standard up
to that line, a ledger without it whole, and exits 1, writing nothing, when the words head a line
at another level or with anything after them. `scripts/ratchet_counts.py`'s ledger entries end
at it as at any heading of level one to three.

Writers: `onboard`'s first rules, whose drafted ledger ends with the section; `revise`
(`apply`, step 2), which rewrites it in `.review/ratchet-proposal.diff`, as
`standards/rule-bar.md` "Overrides" says for a held admission. Readers: `scripts/standard_file.sh`,
run by `implement-change` and `pr-review`; `revise` `prepare` step 6, which merges the
window's clusters into it; `scripts/ratchet_counts.py` and `scripts/rule_lint.py`, through
`parse_entries`.

Pinned by: tests/test_standard_file.sh::"the ledger stops before its held candidates, headed as onboard's first rules and revise's apply head them"

## The analysis blocks

Version: 1

Fields: `.review/harvest/analysis/pr-NNNN.md`, one `thread-analyst` report, its blank lines
ignored. Either the one line `record mismatch: <ids>`, or the heading `## pr-NNNN — threads read`
naming the file's pull request; then one line per ask, `<source> <id> · <opener> · by: <by> ·
<category> · asked: <one line> · outcome: <outcome> · diff: <diff>`, where `source` is `thread`,
`review` or `comment`, `by` is `human`, `bot` or `ai-drafted`, `category` one of design,
correctness, tests, naming, docs, scope, process and style, `outcome` `changed as asked`,
`changed differently`, `declined: "<reason>"`, `discussed, no change`, `unanswered` or `none`, and
`diff` `addresses it`, `does not` or `cannot tell`; then one each of `Procedure: <ids or none>`,
`Not read: <ids or none>` and `Read: <files>`. `scripts/block_tally.py analysis <dir> pr-NNNN
[...]` reads the named pull requests' blocks only, since the directory keeps blocks from earlier
runs, and prints `blocks: <n> · asks: <n> · asked none: <n> · mismatches: <n>`; one line per
combination of the asks other than `asked: none`, `count · <by> · <source> · <category> · <outcome>
· <n>`, a `declined` outcome without its reason, in the orders above; `outcome unanswered ·
pr-NNNN · <source> <id> · by: <by> · diff: <diff>` for each ask the analyst read as unanswered,
which is not the record's verdict; `procedure · pr-NNNN · <the Procedure: text>` and `not read ·
pr-NNNN · <the Not read: text>` for each not `none`; and `mismatch · pr-NNNN · <ids>`. It exits 2
with a `CANNOT RUN` line, printing nothing, on a named block missing, a pull request named twice or
not as `pr-NNNN`, an empty block, a heading missing or naming another pull request, a `record
mismatch:` line with more after it, a line of no form above, or a `Procedure:`, `Not read:` or
`Read:` line missing or repeated.

Writers: `thread-analyst`, at the path harvest.md's "Analysts" gives it. Readers:
`scripts/block_tally.py`, run by harvest.md's "Analysts"; `revise` `prepare` step 2 and `onboard`'s
first rules, for the asks.

Pinned by: tests/test_block_tally.py::test_the_analysis_counts_asks_by_who_source_category_and_outcome

## The sweep blocks

Version: 1

Fields: `.review/revision/sweep/pr-NNNN.md`, one `diff-probe` block, its blank lines ignored: the
heading `## pr-NNNN · <sha, 7 characters>` naming the file's pull request; one line per claim,
`<id> · follows · <place>`, `<id> · breaks · <place> · "<the line>" · <why>`, `<id> · not
touched` or `<id> · not judged · no description`, `id` an `R-NNN` or `C-n`, each id once; then
`Not read: <paths or none>`; every `C-n` claim `.review/revision/claims.md` heads, as `### C-n ·
<path>:<line> · every change|code`, has a line in every block, except an `every change` claim whose
document's `doc <path>:` line in `.review/revision/merges.txt`, `scripts/window_merges.py`'s
printout with `--doc`, does not name that pull request. `scripts/block_tally.py sweep --claims
<claims.md> [--merges <merges.txt>] <dir> pr-NNNN [...]` reads the named pull requests' blocks only
and prints `blocks: <n>`; per claim,
rules first, `claim · <id> · judged <n> · follows <n> · breaks <n> · not touched <n> · not judged
<n>`, with ` · drift` when breaks are more than half of follows and breaks together; `break ·
<id> · pr-NNNN · <place>` per break; and `not read · pr-NNNN · <paths>` for each not `none`. It
exits 2 with a `CANNOT RUN` line, printing nothing, on a named block, the claims file or a named
merges file missing, a `### C-n` heading not in its form, an `every change` claim's document with
no `doc` line in the merges file, a pull request named twice or not as `pr-NNNN`, a heading missing or naming another pull request, a
line of no form above, a claim judged twice, a block with no line for a `C-n` claim it owes, or a `Not
read:` line missing or repeated.

Writers: `diff-probe`, at the path `revise` `prepare` step 2 gives it. Readers:
`scripts/block_tally.py`, run by `prepare` step 2 for "Practice".

Pinned by: tests/test_block_tally.py::test_the_sweep_counts_each_claim_and_marks_drift

## The probe's input

Version: 1

Fields: `scripts/probe_input.py`'s printout from one drafted entry, `.review/backtest/R-NNN.entry.md`:
`R-NNN · <title>`, then the wording, one line each, the entry's `> ` lines without the marker or,
when the entry is followed by a second `### R-NNN · <title>` heading of the same id and title, that
heading's lines, then the entry's one `Do not flag:` line and its paragraph, as written: the lines
after it up to a blank line, a heading or a line opening `scope:`, `example:`, `repos:`, `tier:`,
`Check:`, `Reasoning:` or `Wording:`, which a wrapped line may run straight into. Each block ends at the next heading of
level one to three, as `scripts/rule_lint.py` reads it. Nothing else of the entry is printed, its
`example:` line least of all, since the probe tests it. The script exits 2 with a `CANNOT RUN` line
on an entry with no heading or more than two, a second heading that differs, a first of two
headings with no `scope:` or `example:` line under it, no wording, wording in both places, other
than one `Do not flag:` line, or a line to print opening `example:`, `scope:`, `tier:` or
`Wording:`.

Writers: `scripts/probe_input.py`. Readers: `rule-probe`, given the printout by harvest.md's "The
bar", run by `revise` and `onboard`.

Pinned by: tests/test_probe_input.py::test_a_wrapped_do_not_flag_paragraph_is_given_whole_and_stops_at_the_next_field

## The coupling baseline

Version: 1

Fields: `scripts/coupling.json`, one JSON object, its keys sorted and indented by two spaces.
`patterns` maps each regular expression to what it finds; each match is a mention. `mission`
maps each path the count leaves out, an existing directory written with a trailing `/` or an
existing file, to why it is mission content; a directory leaves out every file under it but a
`README.md` directly in it. `counts` maps each file under `skills/`, `agents/`, `hooks/`,
`scripts/` and `standards/` with a mention to their number, a positive integer; a file with none
has no entry.

Writers: people, for `patterns`, `mission`, a raised count and a moved file's entry;
`check_static.py --update-coupling`, for a lowered count. Readers: `scripts/check_static.py`'s
`coupling` check.

Pinned by: tests/test_check_static.py::test_the_update_writes_the_baseline

## The survey

Version: 10

Fields: `scripts/survey.py`'s printout, from the committed files of `--ref` (default `HEAD`)
only; a candidate file the checkout holds but git does not track is named on the `not committed`
row and never read, and a committed symlink is read as the file it points to in the same commit,
following at most 8 links; one that cannot be followed there (pointing out of the commit, to
nothing in it, to a directory, into a loop or past 8 links) counts as not held and is named, with
its own target, on the `symlinks not followed` row, never read. A first line
`survey: <owner/repo> · <N> families · <M> from the repository` (`no remote` for a checkout without
one; the `(also)`, `not committed` and `symlinks not followed` rows are not counted), then the header `family | found
in | value | plugin today | match`, then one row a family, in a fixed order, fields joined by
` | `, a `|` inside a field written `/`; the test and coverage command families add a
`test command (also)` or `coverage command (also)` row after their own for each later source that
gives one. `found in` is a path in the repository (a contributing
guide's section as `<path>#<heading>`), `git`, `history` or `none`. The `import names` row's
value is the top-level names the package imports as, a namespace package's dotted down to its
first level with an `__init__.py` (`org.pkg`), so an import of the namespace alone is not
counted (version 10). Its `found in` is `pyproject.toml` for the arrays `[tool.setuptools]
packages` or `[tool.poetry] packages` (any other form, such as `{find = ...}`, names none), the
two tables naming different packages being a conflict; else `git (inferred)` for each
`src/<name>/__init__.py`, else each `<name>/__init__.py`, outside a test, doc or example
directory, only the one named for the package (its name with `-` as `_`, or its last `-` part)
when one is, several and none so named being a conflict; else `pyproject.toml (inferred)`, the
package's name with `-` as `_`. A conflict on that row, or a namespace package, is for the person
to confirm. `value` is cut at 60
characters in the table (`--json` gives it whole) and is never a file's text beyond a heading, a
count, a command line or a path, and the
default branch's value names it as the checkout's local `origin/HEAD`; `plugin today` is the
profile key's value and, in parentheses, the file it came from, or `-` for a family no key holds.
`match` compares the row's value with the key's, and is:

- `same`: commands compare as shell words after the runner in front is removed (`poetry run`,
  `uv run` with its options and the values they take, `python -m`, `coverage run -m` and the
  like), so whitespace and quoting do not count, and the options and arguments after `pytest`,
  each option with its value, compare as a set, so their order does not count either, except
  that an option given more than once keeps the order of its values (pytest uses the last), and a
  path argument's trailing `/` does not count; a ticket key agrees when
  the key's pattern is, as a string, the `<KEY>-\d+` the history implies, or else finds, as
  `where.sh` matches a branch, every branch that carries the key in any case; the value keeps the
  branch counts either way, so branches the pattern misses still show;
- `differs`, with both values in the row;
- `inferred`: the repository holds what implies the value, not the value: a
  `.pre-commit-config.yaml` for a `pre-commit run` lint command;
- `repository only`: the repository holds it and the key reads `not yet recorded` or is empty;
- `plugin only`: the key has a value and the repository holds none;
- `-`: a family no key holds.

When the repository's own sources give a family different commands, every row of that family, its
`(also)` rows included, reads `conflict; <match>`, and `--json` gives each such row
`"conflict": true`: none of the commands is taken, and each row's `match` still compares its own
source with the key.

The test and coverage commands are `pytest` commands from five kinds of source, in this order:
the agent instruction files (`AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`,
`.github/copilot-instructions.md`, then `.github/instructions/*.instructions.md`), the testing doc
(`TESTING.md`, or a `test.md`, `tests.md` or `testing.md` under `doc/` or `docs/`), a developer
doc's sections whose heading says test (`developers.md`, `development.md`, `dev-guide.md` and the
like under `doc/` or `docs/`; a `#` line in fenced code is no heading), the `commands =` of
`tox.ini`'s `[testenv]` and `[testenv:<name>]` sections, each labeled by its section, with
`{posargs:<default>}` read as its default, `{posargs}` and `{toxinidir}/` dropped and `{envpython}`
read as `python`, a comment, a factor prefix (`py310: `) and a leading `-` dropped, then CI: the
GitHub workflows' `run:` steps, each starting in the directory its `working-directory:` names,
else its job's `defaults: run: working-directory:`, else the workflow's, one that names a GitHub
expression (`${{ matrix.dir }}`), a space or the top level read with no `cd`, and the `script:`, `before_script:`, `after_script:` and `commands:`
items of `.gitlab-ci.yml` and a `buildspec.yml`, after a comment or an `&anchor` on the key's
line, a block's blank lines kept, each line without its `# comment` and a quoted item unescaped (an
alias `*name`, a tagged value such as `!reference [...]` and every other key's items, such as
`stages:` or `needs:`, are no commands); one key's items, like one `run:` block's lines, run in one
shell, so a `cd` stays in front of the commands after it. In a document a command is a
line of a fenced code block, labeled by its trailing `# comment`, else a comment line just above
it, else the line before the block, or an inline code span that ends its line after a label ending
in a colon; a `$ ` prompt and the comment are dropped. Every command is split at `&&`, `;` and `||`
outside quotes, a `cd` before one kept with it and a `\` left dangling at its end dropped, and one
run through `xvfb-run`, its options and their values skipped, or a shell's `-c` with a quoted script
(`bash -lc '<script>'`) is read as the commands it runs; a
runner after a kept `cd` is removed as one in front would be; one naming a single test
(`::`), a placeholder (`<...>`) or `--version`, `--help` or `--collect-only` is no candidate. One
with `--cov`, or run by `coverage run`, is a coverage command. Within a source, a command whose
label, workflow file name or test path argument says integration, end-to-end, benchmark,
performance, slow or extra is passed over while another candidate remains, unless it deselects
that suite itself (`-m "not integration"`); then one whose label says unit, or that deselects
such a suite, then the first in order. The first source to give a command is the family's row,
and each later one an `(also)` row. The commit style, branch naming and merge strategy rows read the
contributing guide's section titles and, for one it does not cover, a developer git doc
(`git.md`, `git-workflow.md`, `git-usage.md`, `branching.md` or `version-control.md` under `doc/`
or `docs/`). The pull request and issue templates are also read from
`.gitlab/merge_request_templates/` and `.gitlab/issue_templates/`. A ticket key is read only where convention puts one, at a branch name's start
as `where.sh` reads it or at a commit subject's start, a number followed by `-<nn>-<nn>` being a
date and no key (`onboard/WISER-2026-10-29`), and names the project when seen with two numbers or more,
or in a branch name, and with at least twice as many numbers as any other key so seen, so a history
where two projects are seen about as often names none; the commit habit counts the subjects that open with that
key. `--json` prints the same rows, their values whole, as a list of objects with `family`,
`found_in`, `value`, `key`, `plugin_today`, `plugin_source`, `match` and `conflict`.

With `--profile <path>`, it also writes a candidate profile there, in the plugin's profile format
and checked against `scripts/profile.py`'s schema: every key of the schema, those it cannot fill
reading `not yet recorded`. The ticket pattern and project come from the history, the template
from a committed pull request template byte for byte the same as one of the
`templates/<name>/PULL_REQUEST_TEMPLATE.md` of the repository's standard, its own `standards/` or the
one its pointer names (version 9), the test
and coverage commands from the first source that gives one, as that source writes it, none when
the family's sources disagree, the lint command `pre-commit run --files` from a
`.pre-commit-config.yaml`, or, with none, the first linter command the test command's sources give
(`ruff check`, `flake8`, `pylint`, or `black`, `isort` or `ruff format` with `--check`, never with
`--fix`), as that source writes it, which the `lint gate` row shows and compares as a command, and `public` from `--public true` or `--public false`, what the code
host says. By stated rules, each value's source ending ` (inferred)`: `lint.regex` and
`gates.tests` are the gate patterns of the lint command and of the one program every test and
coverage command runs, a chain of commands counted by the one program among them that runs tests or
linters itself, not `make`, `coverage` or `python` (`make generated && cd src/tests && pytest` and
`coverage run -m pytest && coverage report` by `pytest`; a chain with none, or with two that differ
such as `pytest && mypy src`, by nothing), past `env` and any `NAME=value` in front, a subcommand kept for a program
that takes one and the script `run` names (`pre-commit[[:space:]]+run`, `npm[[:space:]]+run[[:space:]]+test`,
`pytest`), none when the program is no plain name, an option, a shell builtin such as `test`, a
shell, `cd` or another launcher, or a script a runner's `run` names rather than a known test or
lint program (`hatch run test`); `types.regex` names the type checkers a pre-commit hook or `pyproject.toml` configures
(`mypy`, or `(mypy|pyright)` for two), and no `corpus` (version 7). The `review rules` row names
`standards/profile.yaml` and `those of <owner>/<repo>` for a repository whose standard is
elsewhere. From the tree (`git (inferred)`) come proposals for a person to trim:
`depth.light`, a top-level changelog or README, `doc/**/*.md` and the like where those documents
are, and `pyproject.toml`'s version line, its hunk the line's start as the file writes it
(`^version =`); `depth.deep`, each outermost `data/` directory and each directory or code file
named for a definition, a manifest, a calibration, a schema, geolocation or a kernel, outside
test, doc and example directories and no `test_` or `mock_` file, matched in its directory
(`pkg/io/manifest*`), or anywhere (`**/manifest*`) when files of that name sit in two directories
or more. With `--downstream-from`,
`downstream` lists the repositories that use the package, most evidence first: from a JSON list of
`{"repo", "evidence"}` the onboarding skill writes from its code search (`GitHub (search)`), or from
a directory of checkouts, each searched at its `origin/HEAD`, else `HEAD`, for a Python file that
imports a name the `import names` row gives or a dependency file that names the package
(`clones (search)`), no checkout searched when that row reads `conflict`, each repository once,
and never the repository itself by name, whatever the owner; its `seen` gives each repository with
its count, and a search git cannot run stops the survey. The candidate is not a drop-in profile: a key reading `not yet recorded` overrides the
default profile's value where a profile is read. `--drop-in <path>` writes the same values with every unfilled
key left out, so the standard's or the default profile's values stand for them, and the three proposals left out too unless
`--answers <file>`, in the scorer's form and checked as the scorer checks it before anything is
written, gives the value the person confirmed (a part of the
proposal) or typed, since an untrimmed proposal is no fact, and any other key the person typed a
value for (`asked`), such as the one test command they pick where the repository's sources
disagree, for a run that uses the candidate in place of a
repository's profile. Beside the candidate,
`<stem>.sources.json` holds `{"repo", "ref", "keys": {<key>: {"source", "conflict", "seen"}},
"files": {<path>: {"loads", "chars"}}, "session_start": {"files", "chars"}}`, with every key of the
schema in `keys`: where each value came from (a path, `history`, `GitHub`, a path or `git` with
` (inferred)`, or `GitHub (search)` or `clones (search)`; `null` for a key left unrecorded), whether the key's sources disagree, and every
repository source of the key with its value as the source writes it; for each place named, how a
fact from it reaches the model (`always`, for the files every session loads; `script`, for the
history, the code host, a search of checkouts, `pyproject.toml`, the pre-commit file, CODEOWNERS, CI and a pull request
template; `on demand` for any other file) and its size in characters; and the files every session
loads at its start, with their total: `CLAUDE.md`, `.claude/CLAUDE.md`, each `.claude/rules/*.md`
with no `paths:` in its frontmatter, and the files any of them imports as `@path` outside code,
relative to the importing file, five hops deep, a scoped rule's imports included, since those load
at the start too.

Writers: `scripts/survey.py`. Readers: `onboard`, which presents the rows and keeps them in
`.review/onboard/survey.md`, with the candidate profile in `.review/onboard/profile.yaml`;
`sandbox/onboard_roundtrip.py`, which reads the candidate and its sources.

Pinned by: tests/test_survey.py::test_the_table_has_its_fixed_header_and_one_row_per_family
