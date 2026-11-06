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
  version: 1.11.0
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
but the two `ToolSearch` lookups below, each command in a Bash call of its own, so a denied
`claude` command stops none of the repository checks. Each finding carries its fix.

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

Then, in this repository: whether it has a standard, a `standards/` directory or a `standard:`
pointer in `standards/profile.yaml`, and the branch's ticket key,
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

- The live-rule count, when the ledger exists, from its status lines, not its headings, printed
  `standard: N rules`:
  `grep -cE 'status: \**(provisional|established)' standards/review-rules.md`. Zero prints
  `standard: no rules admitted yet`. Decisions with no ledger print `standard: decisions, no rules
  yet`: the first rules are not drafted. Neither a ledger nor decisions, only settings such as
  `profile.yaml`, prints `standard: settings only, no rules yet`. A pointer prints `standard: from <owner>/<repo>`, the repository
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

In this order, and nothing else, short enough to read at a glance. Parts 2 to 7 each open with
their bold label; part 1 has none.

1. **The opening line**, word for word and with no label: lasp-dev takes a ticket to a merged pull request: it drafts the
   ticket, plans and builds the change, and reviews the pull request against the repository's
   standard where it has one, stopping for your yes before anything posts, pushes or writes to
   Jira or Confluence.
2. **Setup**, one bullet each: `Plugin: <commit>`, `GitHub: <name>, <status>`, `Jira: <status>`
   and `Confluence: <status>`. Jira's and Confluence's status is the Atlassian server's name and
   status, or `not configured`; a missing server is `none`; a setup command that did not run makes
   its bullets `not checked: <command> did not run: <reason>`. When `claude mcp list` showed other
   servers, a last bullet, `Other servers:`, names each with its status and what it means here, as
   step 1 says.
3. **This repository**, the label followed by `<repo> on <branch>` on the same line, then one
   bullet each:
   - `Standard:` what step 1 prints after `standard:`, or `none` with no standard.
   - `Profile:` step 1's `profile:` report.
   - `.review/ ignored:` `yes`, `locally only` or `no`.
   - `PR template:` `matches`, `missing`, `differs` or `not yet recorded`; `not checked` when the
     profile is refused. With no standard, print no `PR template:` bullet.
   - `Last revision:` `<YYYY-MM>` or `none`. With no standard, print no `Last revision:` bullet.
4. **Fix first**, only when step 1 found a problem: a numbered list, each problem in a few words
   with the fix step 1 gives, a refused profile and a `profile:` report that carries a fix among
   them. Add no fix of your own.
5. **Next**, the command to type and one sentence on why, from the first of these that applies:
   - with a refused profile, the fix under **Fix first**, since every skill reads the profile;
   - with no standard, or `profile: none`, `/lasp-dev:onboard`, to record what the plugin cannot
     detect in this repository, on your yes, and to draft the first rules at its last step; then,
     once it is done, `/lasp-dev:work` with the branch's key, or with no key both
     `/lasp-dev:work <ticket key>` and `/lasp-dev:ticket-draft <description>`;
   - with a standard that has no ledger (`settings only, no rules yet` or `decisions, no rules
     yet`), `/lasp-dev:onboard rules` to draft the first rules, beside `/lasp-dev:work` with the
     branch's key, or `/lasp-dev:work <ticket key>` with none;
   - otherwise, with a key on the branch, `/lasp-dev:work` with that key; with none, both
     `/lasp-dev:work <ticket key>`, for a ticket that exists, and
     `/lasp-dev:ticket-draft <description>`, for a new one.
6. **Skills**, this table as it is, its rows in this order. With a ledger in the standard, the
   Standard row is `/lasp-dev:revise`, "Monthly revision: propose rules to add, reword or retire";
   otherwise it is the row shown.

   | Group | Command | What it does |
   | --- | --- | --- |
   | Start | `/lasp-dev:onboard` | Survey this repository and record its settings, on your yes |
   | Tickets | `/lasp-dev:ticket-draft` | Draft or refine a Jira ticket; writes to Jira on your yes |
   | | `/lasp-dev:design-doc` | Turn your notes into a design doc for work across several tickets |
   | | `/lasp-dev:ticket-audit` | Sweep the Jira project and apply the fixes you approve |
   | Build | `/lasp-dev:work <ticket key>` | Run a ticket's next phase, from draft to merged pull request |
   | | `/lasp-dev:implement-change` | Plan, build and verify one change |
   | Pull requests | `/lasp-dev:pr-create` | Write the description and open a draft pull request |
   | | `/lasp-dev:pr-review <PR>` | Review a pull request; posts one review on your yes |
   | | `/lasp-dev:pr-fix <PR>` | Answer a review: fix, reply and push on your yes |
   | Standard | `/lasp-dev:onboard rules` | Draft the first review rules from merged pull requests |
   | Docs | `/lasp-dev:architecture-doc` | Write a Confluence page on a system as it stands |
   | | `/lasp-dev:process-doc` | Write a Confluence page on how something is done |
   | | `/lasp-dev:drawio` | Draw a diagram as draw.io XML |
   | | `/lasp-dev:writing` | Review prose for structure and clarity |
   | Supporting | `/lasp-dev:commit` | Choose what to commit and write the message; never pushes |
   | | `/lasp-dev:rebase` | Rebase onto the default branch, asking at conflicts of intent; never pushes, and prints the push command |
   | | `/lasp-dev:test-suite-review` | Judge test changes; reads only |
   | | `/lasp-dev:downstream` | Say which consuming repositories a change breaks |
   | | `/lasp-dev:skill-feedback` | Report a problem with a skill; files on your yes |

7. **Read more**, these lines as they are, with `${CLAUDE_PLUGIN_ROOT}` printed as an absolute path:

   Each skill in a line, with its options: `${CLAUDE_PLUGIN_ROOT}/README.md`, "What is included".
   How the workflow goes: `${CLAUDE_PLUGIN_ROOT}/GUIDE.md`.
   `/lasp-dev:quickstart <question>` answers a question about the plugin.
   What your agents can reach, and what they do under your credentials, is your responsibility:
   the same README, "Your responsibility".

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
| suggesting guidance for the standard from a review, `For agents:` | `README.md` "Nominating guidance" |
| a term, a decision | `<standard>/terminology.md`; `<standard>/decisions.md` and the repository's |
| agent guidance, a data convention | `<standard>/agent-guidance.md`, `<standard>/data-conventions.md`; `docs/standards.md` "Agent guidance and data conventions" |
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
`repos:` tag, each term with what it is also called, each agent guidance entry with the month a
review last saw its habit, each data convention, and the context entries, each under the file it
came from. Show its output as it prints, one line per entry in a code block, never recast as a
table and with nothing added from the files it lists, then one line: a rule's wording is its
entry's `> ` lines, and each file changes by a pull request to the repository it came from, as
`${CLAUDE_PLUGIN_ROOT}/README.md` "How the corpus grows" says. When its last line is `No
standard: …`, add `/lasp-dev:onboard` as the way to start one; when its first line says the
standard is not read, it already names the command that reads it again.

## Bounds

Under a minute without an argument; with one, only the files its row names, or the scripts
"What applies here" runs. Never proposes installing
from a branch or a pin, and never says the plugin is behind.
