# The write plan

How a skill writes to Jira: every write a pass proposes, in one numbered list the person approves
once, run in order, read back and recorded. `ticket-draft` steps 7 and 8 and `ticket-audit`'s
Apply use it; `SKILL.md`'s "Writing to Jira" says what a plan may hold. Where the tracker is
GitHub Issues, a plan follows this file with the items, tools, record and read-back
`<plugin root>/skills/using-github/issues.md` sets in place of Jira's.

## When the tools are there

Find the Atlassian server's write tools with `ToolSearch`. Writing is the default whenever
`jira_create_issue`, `jira_update_issue` and `jira_add_comment` are found, and pasting the
alternative. An item whose tool is not loaded is marked `paste: <tool> not loaded` and left to
paste while the rest is written: the links need the server's `jira_links` toolset, which an
older install command left out (the README, "MCP servers"). With none of the three, hand
everything over to paste and say why: a server that runs read-only in one line, and one that is
not connected or fails as `<plugin root>/skills/work/servers.md` sets out, the plan's writes being
what is lost.

## What an item is

| Item | Tool | Shown as |
| --- | --- | --- |
| Create | `jira_create_issue`: `project_key`, `issue_type`, `summary`, `components`, `description`, and in `additional_fields` `priority` (`{"name": ...}`), `duedate` and `labels` | The field block, and the description as "Showing it" says. Until it exists the ticket is `new:<slug>` in every other item |
| Field | `jira_update_issue` `fields` | The field, its value now and after. Labels are one item for the whole list, now and after, since the call replaces the list |
| Epic | `jira_link_to_epic` | The ticket and the epic, with its name |
| Description | `jira_update_issue` `{"description": ...}` | As "Showing it" says |
| Comment | `jira_add_comment` | As "Showing it" says |
| Link | `jira_create_issue_link` | A sentence, `<key A> blocks <key B>`, in the wording of a type `jira_get_link_types` lists; a type it does not list is never used |
| Status | `jira_transition_issue`, the transition from `jira_get_transitions` on that ticket | The status now and after, and the comment the transition carries: why, such as `Duplicate of <key>` with the criteria quoted, or the commit that did the work |
| Assignee | `jira_assign_issue` | Now and after, and where the name comes from (`SKILL.md`, "Writing to Jira") |

Closing a ticket that is not done is a move to the status for a ticket closed with its work not
done, and closing one whose work is done a move to the finished status, as the profile's roles
name them. `python3 "<plugin root>/scripts/profile.py" --defaults --field jira.roles` prints each
role with its status: `abandoned` for closed with its work not done, `finished` for done, `filed`
for the status a ticket is filed in, and `approved` for the one a ticket writer's approval moves
it to. A non-zero exit from it is a stop for every Status item: none is built from
any other source, a status name in a skill's prose included; each move the plan would hold is
marked `paste: profile.py: <error verbatim>`, named by its role, and a plan that holds nothing
else stops. So is `not yet recorded`, printed where the repository's standard records no Jira
workflow: each move is marked `paste: no Jira workflow is recorded for this repository`, and the
plan says `/lasp-dev:onboard` records one. A move from the filed status to the approved status is the ticket writer's approval:
the item says so, and the person who approves the plan is the one approving the ticket.

## The order

1. An existing ticket's `Original request` comment, before anything replaces its description or
   a split creates a piece of it.
2. Creates, each giving the key the items after it use.
3. Descriptions.
4. Fields, labels and epics.
5. Links.
6. Session comments.
7. Assignees.
8. Status changes, last, since a ticket a transition closes may refuse other edits.

Within a step, the plan's own order. An item that names `new:<slug>` waits for that create; a
new ticket and its follow-ups, which name each other, are created as `SKILL.md`'s "A follow-up
ticket" says.

## Showing it

First write `.review/jira-plan.md`, in the `.review/` at the repository's top level, afresh for
each showing, as `<plugin root>/skills/work/decision-points.md`'s "Writing a file" says of a file
to replace: every item, numbered as the plan numbers it, with its text, a description or a
comment alike, in full as it will be sent. When an item carries text from a cleared controlled
item, the file opens with that item's `Controlled: <key or ID> — <the warning>` line, as
`<plugin root>/skills/writing/references/short.md`'s "Controlled content" says. Then one line on
where things stand, then the plan, numbered, grouped by ticket, one line per item with its tool,
and the texts as
`<plugin root>/skills/work/decision-points.md`'s "What does not change" says: in the message, or
`.review/jira-plan.md` named as a link. Under it:

- which items depend on which: dropping a create drops every item that names it, except a
  description that lists it under Related Out of Scope Tickets, which loses that line and is shown
  again; dropping an `Original request` comment drops its ticket's description and session comment,
  and the creates of a split's pieces, since a description is never replaced, nor its scope copied
  into new tickets, while the original text is only in the paste file; and dropping a merge's
  kept-ticket description drops its `Merged from` comment and the closed ticket's move to the
  status for a ticket closed with its work not done,
  since what only that ticket holds would not have moved (`SKILL.md`, "A follow-up ticket" and
  "Merging two tickets");
- that a posted comment may not be editable or deletable (the account it was tested with could do
  neither);
- each item that carries text from a cleared controlled item, naming the item and its warning
  (`<plugin root>/skills/writing/references/short.md`, "Controlled content");
- each item marked `paste:`, and why.

Then ask, as a gate in `<plugin root>/skills/work/decision-points.md`: **Write all <n>**
(Recommended); **Drop some**, the numbers typed under Other; **Paste it all**; **Let's discuss**.
The yes covers exactly the items shown. A change to any item shows the plan again and asks again.
Where the skill already asks a widget at that point, the gate is one more question in it.

## Running it

- **Convert every text first.** Write each description and comment to `<dir>/<item>.txt`,
  `<dir>` being the folder the skill names, copied verbatim from `.review/jira-plan.md`; a text
  changed after the yes is a changed item, so the plan is shown and asked again. Convert it from the
  repository's top level: `python3 "<plugin root>/scripts/jira_markdown.py" <
  <dir>/<item>.txt > <dir>/<item>.md`, the server's own converter copied, which needs only the
  standard library. The write tools take Markdown, and wiki markup sent to them is mangled. Exit 3 lists every line Jira
  would store differently from what was shown. In an `Original request` comment, a line that
  differs in markup alone is put right as `<plugin root>/skills/using-jira/SKILL.md`'s "Copy-paste
  output" says and converted again, which does not make it a changed item; the fix is listed with
  the others. After all the conversions, show every remaining list and ask, in one widget, a question per text: **Send it as converted** or **Paste it instead**,
  which leaves that text and the items that depend on it to paste. Any other failure leaves the
  texts to paste: say why in one line. A text that is already the server's
  Markdown, as `source-reader` flags a description, is copied rather than converted.
- **Record the yes.** Once the conversions are settled, and before the first call, write the
  approval record `hooks/atlassian-gate.sh` reads, `.review/jira-approval.json` at the
  repository's top level, listing exactly the items to be written: one `{"tool": ..., "target": ...}` per
  item, the tool without its server prefix and the target its `project_key` for a create,
  `"<inward_issue_key> <outward_issue_key>"` for a link, `"<issue_key> <epic_key>"` for an epic,
  and its `issue_key` for the rest (`docs/contracts.md`, "The Jira approval record"):

  ```bash
  jq -n --arg s "${CLAUDE_CODE_SESSION_ID:?}" --argjson t "$(date +%s)" --argjson items '<items>' \
    '{session: $s, t: $t, items: $items}' > "$(git rev-parse --show-toplevel)/.review/jira-approval.json"
  ```

  An item that names `new:<slug>` goes in, with the key, once its create has landed: write the
  record again with the same command. The gate allows only a call the record lists, from this
  session, for 30 minutes; any other call prompts, which is a permission prompt, not a failure.
  Remove the record, `rm -f "$(git rev-parse --show-toplevel)/.review/jira-approval.json"`, when the plan has been read back, and as
  soon as it stops: at **Stop here**, when the person stops it, or when the run ends any other way.
- **One call per item, in order**, each only once the items it depends on have landed. A create's
  key replaces `new:<slug>` in the items after it and in the skill's files, as the skill says.
- **A failure** is reported with its error verbatim and never retried with other arguments
  unasked; a no at a permission prompt is one. The items that depend on it are left to paste.
  Remove the record, then ask: **Go on with the <n> that do not depend on it** (Recommended), or
  **Stop here**, the rest left to paste. On a go-ahead, write the record again listing only the
  items still to run; any other answer leaves it removed.
- **Read it back.** For each ticket the plan touched, one `jira_get_issue` with `fields` set to
  what the plan wrote (`summary,status,assignee,components,priority,duedate,labels,issuelinks` and
  the Epic Link field `tracker.md`'s Fields table names, read as `<plugin root>/skills/using-jira/SKILL.md`'s "The project" says)
  and `comment_limit` 0, and say for each item whether it landed. A description is compared as
  the skill says. A comment the read tools return is the server's Markdown rendering of what it
  stores, not the stored text, so a difference in its markup is not damage and puts no note on
  the ticket.

## The record

The skill names the file: each item's number and line as shown, then `written <key>`, `failed:
<error verbatim>`, `dropped` or `paste: <why>`. Whatever was not written stays in the skill's
paste file. The closing summary lists the keys created and changed, each as
the browse URL `<plugin root>/skills/using-jira/SKILL.md`'s "The project" gives, with the
key in place of its placeholder, and the path of the paste file when anything is
left in it.
