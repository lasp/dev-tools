---
name: quickstart
description: >
  Checks the lasp-dev setup and says what to type next, or answers a question about the
  plugin from its own files. Use when asked "how do I use lasp-dev", "where do I start",
  "what does this plugin do", "what should I type", "explain the workflow", or what or why about
  the plugin: "what is the corpus", "what is a record", "why do rules retire", "what is the
  revision" or "the ratchet". Also lists what the standard applies in this repository: "what
  applies here", "which rules apply" or "what does the plugin enforce here".
argument-hint: "[question]"
metadata:
  author: dev-tools
  version: 1.8.0
---

# Quickstart

The first command in any repository: with no argument it checks the setup and says what to type
here; with a question it answers from the plugin's files. It writes nothing but
`.review/standard.md`, `.review/standard/` and a pointer's fetched standard, which "What applies
here" makes, calls no MCP server's tool, reads no token or variable, and asks no question; `ToolSearch`, which it runs, only looks up
which tools Claude Code has registered.

## Options

| Option | Default |
|---|---|
| Question | None, which runs the setup check |

## Without an argument

### 1. Look

Run these from the repository's top level (`git rev-parse --show-toplevel`), and nothing else
but the two `ToolSearch` lookups below. Each finding carries its fix.

- `claude plugin list`: the `Version:` line under `lasp-dev@lasp-dev-tools`, the installed commit. A
  `libera-tools@libera` entry, enabled, is the plugin this one replaced: every skill and agent
  shows twice, and both plugins' hooks run. The fix is `claude plugin disable
  libera-tools@libera`; anyone who set `libera-tools.standard` in git's config sets
  `lasp-dev.standard` again.
- `claude mcp list`, for three services, whatever the servers' names:
  - **GitHub**: a connected server whose line carries `api.githubcopilot.com`.
  - **Jira** and **Confluence**: a connected Atlassian server, whose command carries
    `mcp-atlassian`. With it connected, `ToolSearch` on `jira_` and on `confluence_`: the server
    registers a service's tools only when that service is configured, so a service with none is
    `not configured`, as Confluence is on a server set up for Jira alone.

  The fix is in `${CLAUDE_PLUGIN_ROOT}/README.md` "Install", printed as an absolute path: for a
  missing server, its command in step 5; for one listed but not connected, steps 3, 4 and 6 (its
  token, the variable, a restart from a shell that has it); for a service `not configured`, that
  service's URL and token in step 5's command, its token from steps 3 and 4, and step 6. For
  GitHub, telling the skill you use the `gh` CLI also works (`gh auth status` shows whether it is
  signed in), and for Jira or Confluence, pasting a ticket's or page's text when a skill asks.
  With more than one GitHub server, the agents pick one as
  `${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md`'s "Picking the server" says; when that matches none or several, say so with the names,
  and the fix is `claude mcp remove` and `add-json` under a name that matches. Check no variable by
  name, and report only each server's name, status and URL or command.

  Every other server the list shows is named with its status alone, and what it means here: a further GitHub server, its line carrying `api.githubcopilot.com`, serves another owner's
  repositories, picked by the owner in its name as
  `${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md`'s "Picking the server" says; any other
  server is not used by this plugin's skills.

Then, in this repository: whether it has a standard, `standards/review-rules.md`,
`standards/decisions.md` or a `standard:` pointer in `standards/profile.yaml`, and the branch's ticket key,
matched by the profile's `ticket.pattern` in any letter case, upper-cased unless the pattern matches it as written
(`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field ticket.pattern`), if it
has one, and the profile it runs on (`--field source`), each asked with the `origin` remote's
owner and repository and no other. When `--field source` exits 1, the profile is refused: report
`profile: refused` with `profile.py`'s message, and its fix is what the message says, for the
person to run; no ticket key or template is read, and the repository is never looked up under
another owner to fill them. `<standard>` is the absolute path
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard` prints. When it exits 1 ending "the
repository has no standard", `none` is expected, reported as `profile: this repository's own files
and the plugin's default profile`, and the template check below is skipped; any other exit 1 is a
refusal, reported with its message. With a standard, `none` comes only from the repository's own
`standards/` with no `profile.yaml`, reported as `profile: none — the standard sets nothing for
this repository`; the fix is `/lasp-dev:onboard`, which surveys the repository and, on your
yes, writes its `standards/profile.yaml`. When its survey stops with an error, the alternative is
to copy `${CLAUDE_PLUGIN_ROOT}/standards/profile.example.yaml`, printed as an absolute path, to that
file and fill it. A pointer to a standard for several repositories whose `profiles/` has no
`<repo>.yaml` for this one is not `none` but refused, as above. With a standard, also:

- The live-rule count, when the ledger exists, from its status lines, not its headings:
  `grep -cE 'status: \**(provisional|established)' standards/review-rules.md`. Zero prints
  `standard: present`. Decisions with no ledger print `standard: decisions, no rules yet`: the
  first rules are not drafted. A pointer prints `standard: from <owner>/<repo>`, the repository
  it names, with no count: the rules are that repository's and are not fetched here.
- Whether `.github/PULL_REQUEST_TEMPLATE.md` matches (`cmp -s`) the template the profile names
  (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo> --field template`),
  `<standard>/templates/<name>/PULL_REQUEST_TEMPLATE.md`. Missing: copy it from there.
  Different: decide which copy is right and make them match. A template that reads `not yet
  recorded` is not a problem and skips the comparison: `pr-create` then fills
  `.github/PULL_REQUEST_TEMPLATE.md`, or with none its `body.md`.
- Whether `.review/` is ignored, and by which file (`git check-ignore -v .review/x`). Not ignored,
  or ignored only by `info/exclude` (the hook's file for this clone alone, reported as
  `ignored locally only`): the fix is to add `.review/` to `.gitignore`.
- The newest `ratchet-*.md` in any of the standard's records directories, this repository's `<log>` as `revise`'s "The standard's
  repository" places it (`log/<repo>/` under the directory `bash
  "${CLAUDE_PLUGIN_ROOT}/scripts/standard.sh" --cached` prints for a pointer;
  `standards/log/<repo>/` here for its own standard), with `<repo>` the name in `git remote get-url origin`, is the
  last revision. None is
  `last revision: none`, normal before a first revision and not a problem.

A setup command above that is denied or cannot start is reported as `<command> did not run:`
with the reason, and the repository checks go on.

### 2. Say

In this order, and nothing else:

1. **Two status lines**, fields separated by ` · `:

   ```
   lasp-dev <commit> · GitHub: <name> <status> · Jira: <status> · Confluence: <status>
   <repo> · <branch> · standard: N rules · <.review/ ignored?> · <template matches?> · last revision: <YYYY-MM>
   ```

   Jira's and Confluence's status is the Atlassian server's name and status, or `not configured`.
   A missing server is `none`, zero rules is `standard: present`, decisions with no ledger
   `standard: decisions, no rules yet`, and the two questions get two
   or three words each. Without a standard the second line is `<repo> · <branch> · no standard`,
   ending with the line `work` prints in that case, quoted from
   `${CLAUDE_PLUGIN_ROOT}/skills/work/SKILL.md` step 1, never written from memory.
2. **Each problem step 1 found**, one line each, with the fix step 1 gives. Add no fix of your
   own. Then, when `claude mcp list` showed other servers, one line naming each with its status
   and what it means here, as step 1 says.
3. **`Next:`**: `/lasp-dev:work` with the branch's key. When the branch has no key, both
   `/lasp-dev:work <ticket key>`, for a ticket that exists, and
   `/lasp-dev:ticket-draft <description>`, for a new one.
4. **This table**, its rows in this order:

   | Group | Command | What it does |
   | --- | --- | --- |
   | Setup | `/lasp-dev:onboard` | Survey this repository for the facts the plugin works from (templates, contributing guide, test commands, pre-commit, history, and the tracker's statuses and fields when the servers are connected), say where each is read from, and write a drop-in profile on your yes |
   | Tickets | `/lasp-dev:ticket-draft [investigate | settle | reformat] <ticket key | description | pull request>` | Write a ticket in the team's format, refine one, or write one for a pull request with none; `investigate` briefs you on the code and the design choices first; `reformat` moves a ticket to the current format, asking only what it needs |
   | | `/lasp-dev:design-doc [revise] <page ID | URL | file | text> [change]` | Turn your notes page into a design doc for work that spans several tickets, existing or yet to be drafted, the problem and goals settled with you first; publishes the page on your yes |
   | | `/lasp-dev:ticket-audit` | Report on the Jira project, then its proposed actions applied in Jira on your yes: gaps against the year plan, duplicates, stale tickets, link and estimate consistency, what each open pull request waits on; the report under `.review/audit/` |
   | Implementation | `/lasp-dev:work <ticket key>` | Take a ticket from draft to merged pull request, one phase at a time |
   | | `/lasp-dev:implement-change <ticket key | file | description>` | Plan, build and verify one change |
   | | `/lasp-dev:commit` | Choose what belongs in the commit and write the message |
   | | `/lasp-dev:test-suite-review <diff | branch>` | Say whether a test change weakens, misplaces or duplicates tests; reports only |
   | | `/lasp-dev:downstream [check | ci <run> | release <version>]` | Say which consuming repositories a change breaks, by running their tests against it; why main went red; which pins lag a release |
   | Pull requests | `/lasp-dev:pr-create` | Write the description and open a draft |
   | | `/lasp-dev:pr-review <PR>` | Review a pull request and show the findings at their lines; on your yes, post one review |
   | | `/lasp-dev:pr-fix <PR>` | Act on the review: implement what reviewers agreed to, reply to the rest, push |
   | Standards | `/lasp-dev:revise` | Monthly: prepare the revision report before the meeting; `apply` drafts what the group accepted |
   | | `/lasp-dev:revise correct <what is wrong>` | Fix a term, decision or rule wording the shared standards got wrong |
   | Writing | `/lasp-dev:writing` | Review the wording of a ticket, pull request body or rule |
   | | `/lasp-dev:architecture-doc [revise] <repository | page ID | URL | file | text>` | Write a page on a system as it stands, its purpose confirmed with you and its interfaces from the code; `revise` brings a published page up to date; publishes on your yes |
   | | `/lasp-dev:process-doc [revise] <page ID | URL | file | text>` | Write a page on how something is done, a team process, a how-to or a user guide, its purpose and steps settled with you; `revise` brings a published one in line; publishes on your yes |
   | | `/lasp-dev:drawio <what to draw>` | Draw a diagram as draw.io XML to paste into a Confluence draw.io macro |
   | Feedback | `/lasp-dev:skill-feedback [skill: what you did not like]` | File a complaint about a skill or agent as a `skill-feedback` issue, in your words, with the session's last turns if you choose; nothing is filed before your yes |

   Without a standard, the Standards group is one row: `/lasp-dev:onboard rules`, "Draft
   this repository's first rules from its merged pull requests", and the same with decisions and
   no ledger, since `revise` needs the ledger.
5. **Three closing lines**, as they are:

   Every command stops before it posts, pushes or writes to Jira or Confluence; the plan and the
   diff are yours to approve.
   What your agents can reach, and what they do under your credentials, is your responsibility:
   `${CLAUDE_PLUGIN_ROOT}/README.md`, "Your responsibility".
   `/lasp-dev:quickstart <question>` answers a question about the plugin.

## With a question

Skip steps 1 and 2. Read the files the question's row names, from `${CLAUDE_PLUGIN_ROOT}` (for a
rule, from this repository's `standards/`), answer in one or two paragraphs, and name the file, by
its absolute path, and the section. A question no row covers is answered from `GUIDE.md`, and the
answer says so.

| The question is about | Read |
| --- | --- |
| what the plugin does, the phases, the agents | `GUIDE.md` "The flow"; `docs/design.md` "What runs beside your session" |
| why it exists, why it is built this way | `GUIDE.md` "Why"; `docs/design.md` "Why it is built this way" |
| the corpus, what is shared and what is per repository | `standards/README.md`; `README.md` "How the corpus grows" |
| a rule, its status, evidence and wording | the standard's `review-rules.md`, its wording the entry's `> ` lines, or the instruction file a ledger that keeps it there links; the archive `revise`'s "The standard's repository" names once it has left |
| how the reviewer behaves, severity | `standards/review-contract.md` |
| answering a finding, what my reviewer sees | `skills/pr-review/SKILL.md` "Whose reply counts"; `GUIDE.md` "Reviewing a pull request" |
| what a new ticket needs, filing, its statuses | `skills/using-jira/SKILL.md`, "The ticket workflow", the project's `tracker.md` (its Fields and workflow), and `GUIDE.md` "The estimation meeting" |
| the revision, the ratchet | `skills/revise/SKILL.md` "When to run"; `GUIDE.md` "How the rules change" |
| a record | `docs/contracts.md` "The record"; the records directory `revise`'s "The standard's repository" names |
| the `.review/` files | `README.md` "Layout" |
| how the rules were generated and measured | `skills/onboard/first-rules.md` for a repository's first rules; `skills/revise/harvest.md` for a revision's; a project's own harvest report, where it keeps one, in its standard's log |
| what is the bar, why was my rule held | `standards/rule-bar.md` |
| a term, a decision | `<standard>/terminology.md`; `<standard>/decisions.md` and the repository's |
| what the first merge left out, what is planned | `ROADMAP.md` |
| setup, servers, models, time, cost | `README.md` "Install", "MCP servers", "Models" |

### What applies here

When the question is what the plugin applies in this repository, which rules or decisions, run
from the repository's top level, in place of reading a row, the standard first, as `pr-review`
writes it:

```
mkdir -p .review && bash "${CLAUDE_PLUGIN_ROOT}/scripts/standard_file.sh" > .review/standard.md.tmp && mv .review/standard.md.tmp .review/standard.md || { rm -f .review/standard.md.tmp; false; }
```

When it exits non-zero, say its message, which names the fix, and list nothing. Otherwise:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/standard_index.py" .review/standard.md --source .review/standard/source --context <context>
```

`<context>` is the standard's `context/`: under the directory that `bash
"${CLAUDE_PLUGIN_ROOT}/scripts/standard.sh" --cached` prints second for a `standard:` pointer;
otherwise `standards/context`. When `.review/standard/source`
ends `@none`, the standard is not read: pass no `--context`. `standard_index.py` lists
what every build and review loads: each rule and decision with its number, title, status and
`repos:` tag, the terminology and the context entries, each under the file it came from. Show its
output as it prints, in a code block, then one line: a rule's wording is its entry's `> ` lines,
and each file changes by a pull request to the repository it came from, as
`${CLAUDE_PLUGIN_ROOT}/README.md` "How the corpus grows" says. When its last line is `No
standard: …`, add `/lasp-dev:onboard` as the way to start one; when its first line says the
standard is not read, it already names the command that reads it again.

## Bounds

Under a minute without an argument; with one, only the files its row names, or the scripts
"What applies here" runs. Never proposes installing
from a branch or a pin, and never says the plugin is behind.
