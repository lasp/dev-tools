# GitHub issues as the tracker

How a skill writes a ticket where the standard's tracker is GitHub Issues
(`python3 "<plugin root>/scripts/profile.py" --defaults --field issue_tracker.kind` prints
`github`): the issue's fields, the items a write plan may hold, the read-back and the paste file.
The ticket is an issue at `--field issue_tracker.location`, or this repository's own issues when
that prints `none`; its key is the number, `12` in file names and arguments, `#12` wherever a
person reads it. Showing the plan, its gate, the order, running it and failures are
`<plugin root>/skills/using-jira/write-plan.md`'s, read with the differences below; the server is
picked as `<plugin root>/skills/using-github/SKILL.md` says.

## The issue

- **Title**: one line, starting with a verb, at most twelve words.
- **Body**: the description in `<plugin root>/standards/ticket-format.md`'s format, in Markdown as
  that file shows it, each section under its `#` or `##` heading, never a bold line in its place.
  GitHub stores the body as it is sent, so nothing is converted.
- **Labels**: only labels the repository already has; a label is never created. The server has no
  tool that lists a repository's labels, only `get_label` for one name, so check each label a plan
  would send with `get_label`, and offer only those the profile maps or the repository's issues
  carry (`list_issues`, `issue_read` `get_labels`): a label no issue carries yet is missed unless
  the person names it. One `get_label` cannot find is left out and said so. A role's label is `--defaults --field issue_tracker.roles.<role>`, `none` for a
  role with no label.
- **State**: `open`, or `closed` with a `state_reason`: `completed` for the `finished` role,
  `not_planned` for `abandoned`, and `duplicate`, with `duplicate_of`, for a ticket merged into
  another.

There is no issue type, component, epic, parent, due date, estimate, Projects field or sub-issue:
a plan never holds one, and the hook gives no decision on a call that sends one. Neighbors have
no typed links: a ticket names them as `#<n>` in the body's sections, Related Out of Scope Tickets
for work taken out of its scope, and The code today for one it builds on. A pull request names its
issue on the `Ticket:` line `pr-create` writes, never with a closing keyword.

## What an item is

| Item | Tool | Target | Shown as |
| --- | --- | --- | --- |
| Create | `issue_write`, `method: create`: `owner`, `repo`, `title`, `body`, `labels` | `<owner>/<repo> <title>` | The title, the labels and the body in full. Until it exists the issue is `new:<slug>` in every other item |
| Update | `issue_write`, `method: update`, `owner`, `repo`, `issue_number`, with what changes: the `title`, the `body`, the `labels` as one list, or the `state` with its `state_reason` and, for a duplicate, `duplicate_of` | `<owner>/<repo>#<n>` | Each field now and after; the body in full; labels as the whole list now and after, since the call replaces it |
| Comment | `add_issue_comment`: `owner`, `repo`, `issue_number`, `body` | `<owner>/<repo>#<n>` | The comment in full. An `Original request` or a session comment opens with the plain first line `using-jira`'s "Copy-paste output" gives, no Markdown before its first word, since the revision finds the baseline by it |

Moving a ticket into a role is a labels update: the role's label added and any other mapped
label removed, since an issue carries at most one. A move into a role whose label is `none` is
skipped and said so: an open issue with no mapped label is already `filed`, and `approved` and
`implementation` have nothing to move to. The move from `filed` to `approved` is the ticket
writer's approval, proposed only when the person asks for it. Closing is a state update, last.

The order is `write-plan.md`'s, with these steps empty: links, and assignees, which no plan holds
here.

## Showing it

As `write-plan.md`'s "Showing it" says, written to `.review/github-plan.md` in place of
`.review/jira-plan.md`, each item naming its tool and target. A posted comment can be edited or
deleted on GitHub, but its first text reaches whoever watches the repository, so say so.

## Running it

- **No conversion.** Each text is written to `<dir>/<item>.md`, copied verbatim from
  `.review/github-plan.md`, and sent as it is.
- **Find the tools** with `ToolSearch` by what they do (`issue write`, `add issue comment`), as
  `using-github` says. With neither, hand everything over to paste and say why in one line, a
  server not connected or failing as `<plugin root>/skills/work/servers.md` sets out.
- **Record the yes.** Before the first call, write the approval record `hooks/issue-gate.sh`
  reads, `.review/github-approval.json` at the repository's top level, listing exactly the items to
  be written, one `{"tool": ..., "target": ...}` each, the tool without its server prefix and the
  target as the table gives it, its owner, repository and title copied exactly as the call will
  send them, since the hook compares them case and all (`docs/contracts.md`, "The GitHub approval
  record"). A call sends only the arguments the table names; the hook gives a call with any other,
  such as `assignees`, no decision:

  ```bash
  jq -n --arg s "${CLAUDE_CODE_SESSION_ID:?}" --argjson t "$(date +%s)" --argjson items '<items>' \
    '{session: $s, t: $t, items: $items}' > "$(git rev-parse --show-toplevel)/.review/github-approval.json"
  ```

  An item that names `new:<slug>` goes in once its create has landed, with the number the
  create's `url` ends in: write the record again with the same command. The hook allows only a
  call the record lists, from this session, for 30 minutes, and gives no decision on any other, so
  the person's own permissions decide it. Remove the record,
  `rm -f "$(git rev-parse --show-toplevel)/.review/github-approval.json"`, when the plan has been
  read back, and as soon as it stops, as `write-plan.md` says of the Jira record.
- **A failure** is handled as `write-plan.md` says; a no at a permission prompt is one.

## Read it back

For each issue the plan touched, one `issue_read` `get`, and `get_comments` when the plan posted a
comment, and say for each item whether it landed: the title, the labels and the state as sent, the
body equal to the text sent once line endings are made `\n`, and each comment present. A body that
differs is a failed item, named with the first line that differs.

## The paste file

`.review/context/<ticket>.issue.md`, for a person to file by hand what the plan did not write:

```
Title:  <the title>
Labels: <the labels, comma-separated, or none>

<the body, in Markdown>

----
Comment to post
<the Original request comment, as using-jira's "Copy-paste output" words it, in Markdown>

----
Session comment
<the session comment, as using-jira's "Copy-paste output" words it>
```

A block with nothing to post is left out. The person creates the issue with the title, labels and
body, then posts `Comment to post` and `Session comment` as comments, in that order.
