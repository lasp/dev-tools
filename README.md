# lasp-dev

`lasp-dev` is a Claude Code plugin for software development at LASP. It takes a ticket to a
merged pull request: it drafts the ticket, plans and builds the change, and reviews the pull
request against the repository's written standard, with a person approving each plan, diff,
post and write to Jira. [`GUIDE.md`](GUIDE.md) says how to use it, and its
[glossary](GUIDE.md#glossary) defines the terms both documents use.

**What it is not tied to.** The workflow is the same for any team and any language: ticket,
plan, build, review, pull request, and a standard that changes with what reviewers say. What
differs between teams is meant to live in each repository's standard, not in the plugin: the
review rules and decisions, the Jira project and its workflow, the Confluence spaces, the pull
request template, the test commands. It is not all there yet: Libera's names still appear in a
number of skills and agents, which [`ROADMAP.md`](ROADMAP.md) tracks in "Neutral examples in
generic skills". A repository keeps its standard in its own `standards/`, or points at a
project's shared standard in another repository. Tools for one domain, such as flight software or
engineering, belong in plugins of their own installed beside this one.

**What it does in your repository.** With no standard, every skill runs on what it finds in the
repository and the default profile: it plans, builds, reviews and opens pull requests, and the
review applies only the plugin's review contract. `/lasp-dev:onboard` surveys the repository
and writes its settings on your yes; on a second yes, given merged pull requests with review
threads a person wrote, it drafts candidate rules into `.review/harvest/`, and reviews cite them
once a person commits the ones the team keeps. A monthly revision then proposes changes to the
rules from how people answered. "Adopting the standards workflow in a repository" below is the order.

Libera's science data system was the first team to adopt it: its examples (its Jira tickets, the
libera_utils repository, its shared standard) show one team's standard, not a requirement.

Without the tokens, the skills in the "Neither" row of "Which skill needs which server" below
work once the plugin is installed.

It is shipped as one Claude Code plugin, `lasp-dev`, from the marketplace Install's step 2
adds, in three parts:

- **General skills and agents**: they plan, implement and verify a change, commit, open pull
  requests, review them and answer review. Five of them began from
  [`medley56/llm-tooling`](https://github.com/medley56/llm-tooling) at the commit `UPSTREAM`
  records and have since been substantially rewritten (`NOTICE`).
- **The standards workflow**: a written standard per repository, reviews keyed to its rules, a
  record per pull request, and a monthly revision of the standard. Three skills
  (`work`, `onboard`, whose last step drafts the first rules, and `revise` with its `correct` mode), the build hooks and the
  shared corpus in `standards/`; the forked `pr-review`, `implement-change` and `pr-create`
  follow the standard in any repository that has one.
- **The Atlassian skills**: how to read a project's Confluence and Jira, drafting a ticket in the
  project's format, and sweeps across a Jira project whose proposed actions are written on your
  yes. The project's own fields, statuses and spaces come from its standard's `tracker.md` and
  `wiki.md`.

New here: install as below, then open Claude Code in your repository and type
`/lasp-dev:quickstart`. This README is the
reference: setup, the skills and agents, adoption, the working files, and changing the tooling.
Planned work is in [`ROADMAP.md`](ROADMAP.md).

## Install

Once per machine, in this order.

1. **Check you have:**
   - Claude Code installed and logged in. A fresh install says `Not logged in · Please run
     /login` until you do.
   - `bash` and `jq`. Without `jq` the build hooks record nothing, `work`, `pr-create` and
     `implement-change` cannot read where a ticket stands, and every Jira or Confluence call,
     reads included, asks first. macOS 15 and later ship `jq`.
   - `python3`, 3.9 or later, for the scripts the skills run. Standard library only.
   - `uv`, for the Atlassian server's `uvx`, if your team uses Jira or Confluence.
2. **Install the plugin.** It carries the skills, the agents, the hooks and the shared corpus in
   `standards/`; nothing else is cloned.

   ```bash
   claude plugin marketplace add lasp/dev-tools
   claude plugin install lasp-dev@lasp-dev-tools
   ```

3. **Create the personal access tokens**: one on GitHub, and one each on Jira and Confluence if
   your team uses them. The permissions each needs are under "MCP servers" below.
4. **Export them** in your shell profile; the Jira and Confluence lines only if you created
   those tokens:

   ```bash
   export GITHUB_MCP_TOKEN=<GitHub token>
   export JIRA_TOKEN=<Jira token>
   export CONFLUENCE_TOKEN=<Confluence token>
   ```

5. **Add the MCP servers**, which are not part of the plugin: GitHub's always, and the Atlassian
   server only if your team uses Jira or Confluence. Replace `ORG` in the GitHub server's name
   with the organization whose repositories you work in, as "MCP servers" below says; Libera's is
   `github-libera`. Replace `JIRA_HOST` and `CONFLUENCE_HOST` with your servers' base URLs, `PROJ`
   with your Jira project key and `SPACE` with your Confluence spaces, comma-separated.

   ```bash
   claude mcp add-json --scope user github-ORG '{"type": "http", "url": "https://api.githubcopilot.com/mcp/", "headers": {"Authorization": "Bearer ${GITHUB_MCP_TOKEN}"}}'
   claude mcp add-json --scope user atlassian '{"command": "uvx", "args": ["mcp-atlassian@0.23.1"], "env": {"JIRA_URL": "JIRA_HOST", "JIRA_PERSONAL_TOKEN": "${JIRA_TOKEN}", "CONFLUENCE_URL": "CONFLUENCE_HOST", "CONFLUENCE_PERSONAL_TOKEN": "${CONFLUENCE_TOKEN}", "READ_ONLY_MODE": "true", "JIRA_PROJECTS_FILTER": "PROJ", "CONFLUENCE_SPACES_FILTER": "SPACE", "TOOLSETS": "default,jira_agile,jira_projects,jira_links"}}'
   ```

6. **Restart Claude Code**, from a shell that has the variables.
7. **Type `/lasp-dev:quickstart`** in a repository you work in. It checks the plugin, the servers
   for GitHub, Jira and Confluence, and the repository's setup, and says what to type next.

Skills run as `/lasp-dev:<name>`, from the terminal, VS Code, JetBrains or the desktop app.
Which model the build and its reviewers run on is a session setting, not a plugin option; see
"Models" below.

Start Claude Code in the repository you are changing. The build's lock and record go into the
`.review/` of the session's working directory, so a session started in one repository and used
to change another records the build in the wrong place.

### MCP servers

The tokens step 3 creates:

- **GitHub:** a fine-grained personal access token whose resource owner is the organization that
  holds your repositories (LASP-Libera, for Libera's), with access to the repositories you work
  in. The organization may have to approve it before it works.
  GitHub's server offers no sign-in, because it does not support the dynamic client
  registration Claude Code's OAuth needs. Its repository permissions:
  - Contents read, for files and commits;
  - Pull requests read and write, for `pr-create`, `pr-review` and `pr-fix`;
  - Issues read and write: read for `ticket-draft`'s search, write for `skill-feedback` to file
    an issue on this plugin's repository. A fine-grained token has one resource owner, so when
    that owner is not the plugin repository's, filing needs a second token from that owner, on a
    second GitHub server whose name contains the owner; without one, `skill-feedback`'s filing
    call fails and it hands over the title, the body and the new-issue link to paste;
  - Checks read, so the skills can read a pull request's check runs, which a token without it
    cannot do on a private repository.
- **Jira and Confluence:** a personal access token from your own profile on each server, never
  the shared automation account: on each server, your avatar, Profile, Personal Access Tokens, Create
  token. The account needs read permission on every space step 5's `CONFLUENCE_SPACES_FILTER`
  names.

What a token can read, the server's tools can read and send to the model. Only the GitHub token
can be scoped; keep it to what the skills need. A Jira or Confluence personal access token reads
whatever its account can. The Atlassian server's `JIRA_PROJECTS_FILTER` holds on reads, but
`CONFLUENCE_SPACES_FILTER` limits only search, and a page read by its ID ignores it (mcp-atlassian
0.23.1). So the account itself is the control: run the skills under one that cannot read a project
or space holding export-controlled or other controlled content. A skill that meets an item
warning that it is controlled stops and asks you before reading on
(`skills/writing/references/short.md`, "Controlled content"), but by then what it read has reached
the model.

Only the `${...}` references go into `~/.claude.json`, never a token's value; Claude Code reads
the values from your shell when it starts a server. Another variable name works if the command
uses it too.

A session the desktop app or an IDE starts was not started from your shell, so it may not have
your profile's exports, and the servers then get no token. Claude Code applies the `env` block
in `~/.claude/settings.json` to its own environment at start, however it was launched, so the
`${...}` references in step 5's commands should expand to these values; this is read from the
Claude Code docs and not yet confirmed from a desktop-app session. The values then sit in that
file as plain text: keep it out of any dotfiles repository or sync, and readable only by you
(`chmod 600 ~/.claude/settings.json`).

```json
{
  "env": {
    "GITHUB_MCP_TOKEN": "<GitHub token>",
    "JIRA_TOKEN": "<Jira token>",
    "CONFLUENCE_TOKEN": "<Confluence token>"
  }
}
```

Step 5 runs the Atlassian server with `READ_ONLY_MODE`, so it refuses a write if anything tries
one. With `"READ_ONLY_MODE": "false"` it accepts writes your token allows, and `ticket-draft` and
`ticket-audit` write to Jira themselves: each shows every write it proposes as one numbered list,
a write plan, and makes them after your yes to that list (`skills/using-jira/SKILL.md`, "Writing
to Jira"). `design-doc`, `architecture-doc` and `process-doc` are the skills that write to Confluence: each
publishes or updates its page after your yes to exactly that write, and Claude Code asks again at each call
(`skills/using-confluence/SKILL.md`, "Writing to Confluence"). `jira_links` in `TOOLSETS` loads the tools that link tickets and set an epic; a
server without it leaves those items to paste. With `READ_ONLY_MODE` on, all three hand you the
writes to paste instead.

A server you already have works under any name: the skills find its tools with `ToolSearch`.
With one GitHub server, its name does not matter; with more than one, the skills pick the server
whose name contains the repository owner, or its last hyphenated part (`libera` in
`github-libera`), unless the profile's `github_server` names one.
The skills use the GitHub MCP server by default and the `gh` CLI when you tell them to, once per
session; either way nothing posts or pushes without your yes. Review threads need the server:
on `gh`, `pr-fix` stops at its start and `pr-review` posts only a pull request's first review. The rule the skills apply is
`skills/using-github/SKILL.md`.

**Which skill needs which server:**

| Server | Skills |
| --- | --- |
| GitHub | `work`, `pr-create`, `pr-review`, `pr-fix`, `ticket-draft`, `ticket-audit`, `revise`, `skill-feedback`; `implement-change` when its source is a GitHub issue; `downstream`, for `ci <run>`; `onboard`, when connected, and its first rules |
| Jira | `ticket-draft`, `design-doc`, `architecture-doc` and `process-doc` (only the tickets you or a page name), `ticket-audit`, `revise` (with `measures`, for an epic it adds or a context entry reads, or for an issue `correct` cites); `pr-review`, for the ticket when no context page holds it; `work`, for a ticket's status when it has no context page here; `implement-change` when its source is a ticket; `onboard`, when connected, and its first rules |
| Confluence | `design-doc` (your notes, the area's pages, and the publish), `architecture-doc` (the system's page, the area's pages, and the publish), `process-doc` (your notes, the pages you point at, and the publish), `ticket-draft` (the year plan, and `investigate`), `revise` (the context refresh, or a page `correct` cites), `ticket-audit` (the year plan); `onboard`, when connected, and its first rules |
| Neither | `commit`, `drawio`, `architecture-doc` and `process-doc` until they publish, `implement-change` from a file or a description, `test-suite-review`, `writing`, `quickstart`, `onboard` with no server connected, the repository alone |

The hidden reference skills load when another skill needs them: `using-jira` and
`using-confluence` by `source-reader`, `using-github` by every skill and agent that reaches
GitHub, and `using-curryer` by the planner, `github-pr-reviewer`, `ticket-draft` and
`downstream`.

#### When a server is missing or failing

A skill that needs a server it cannot reach says, in two or three lines, which server and whether
it is not connected or its call failed, what that step loses, whether the run goes on, and how to
fix it (`skills/work/servers.md`). It stops only at a step that cannot go on without the server,
and then offers the `gh` CLI for GitHub, or pasted text or a file for Jira and Confluence.

To check, type `/lasp-dev:quickstart`, which reports each of GitHub, Jira and Confluence with
its fix; `/mcp` in a session, or `claude mcp list` in a shell, shows each server's status.

A connected server fails in two ways:

- **Every call fails**: the token is expired or revoked, or, for GitHub, missing from the shell
  Claude Code started in. Create a new one (Install, steps 3 and 4) and restart (step 6). A Jira
  or Confluence token missing from that shell shows differently: the Atlassian server leaves that
  service's tools out, and quickstart reports it as `not configured`.
- **One repository, project or space fails** while others read: the token's account cannot see
  it. A Jira or Confluence token reads what its account can, so a ticket or page a colleague reads
  may be out of your token's reach; ask for access, or use a token from an account that has it.

Claude Code's guide to MCP servers is https://code.claude.com/docs/en/mcp.

### Updating

The plugin stays at the commit you installed until you move it. Three ways, none required:

- `claude plugin marketplace update lasp-dev-tools && claude plugin update lasp-dev@lasp-dev-tools`, by hand
  or from wherever you run things: a shell alias, a container's start command or a cron job.
- The marketplace's auto-update, off by default: in Claude Code, `/plugin`, the Marketplaces
  tab, `lasp-dev-tools`, Enable auto-update. It updates after a session starts, and the update loads at
  the next.
- Staying put, and installing from a ref to move or roll back, as "Changing the tooling" says.

`claude plugin list` shows the installed commit as the plugin's `Version:`. No skill or hook
checks for updates.

The plugin this one replaces, `libera-tools@libera`, still loads if it is installed and
enabled: every skill and agent shows twice, and both plugins' hooks run.
`/lasp-dev:quickstart` says so, and `claude plugin disable libera-tools@libera` turns it off.
Anyone who set `libera-tools.standard` in git's config sets `lasp-dev.standard` again; the
old key is not read.

### Beside your own tooling

When a request in words matches a skill here and another skill, Claude Code picks by
description, and this plugin cannot make itself preferred. The usual overlap is
`medley56/llm-tooling`, whose forked skills have the same names under `/llm-tooling:`. To choose
which one answers:

1. The `/lasp-dev:` prefix always picks this plugin's skill.
2. To have this plugin answer in a repository, turn the other plugin off there, for
   yourself only: `.claude/settings.local.json` in that repository holding
   `{"enabledPlugins": {"llm-tooling@llm-tooling": false}}`.
3. A personal skill that overlaps becomes slash-only with `disable-model-invocation: true` in
   its frontmatter, so it never fires on a phrase this plugin's skills claim.
4. One line in your own instructions, `~/.claude/CLAUDE.md` or a repository's
   `.claude/CLAUDE.local.md`: in the repositories you use it in, `lasp-dev` is the first
   choice when a task matches one of its skills and another tool's.

Agents overlap the same way. A personal agent such as a `test-runner` and this plugin's
`pytest-runner` both fit "run the tests", and Claude Code picks between them by description when
you ask in words. The skills here start their own agents by name, so the overlap reaches only what
you ask for directly: name the agent in the request, or name the preferred one in the
instruction line in item 4 above.

### Permissions

Each skill asks before it posts, pushes, opens a pull request or writes to Jira or Confluence. The plugin's
`hooks/atlassian-gate.sh`, whatever the server is named and whether or not it runs read-only,
allows a Jira write only when your session makes it and `.review/jira-approval.json`, which the
skill writes at your yes to a write plan, lists that tool on that ticket, so a plan's writes do
not prompt one by one. It asks before every other Atlassian call that is not a read: a write no
record from this session in the last 30 minutes lists, a write a subagent makes, a delete, a
removed link, a move to another project, an edited comment, an update that uploads local files,
and any write to Confluence. It asks rather than staying silent because a hook's ask still
prompts in auto mode, where a silent hook leaves the call to the classifier. An `ask` rule you add for a Jira write tool prompts again at each call of a plan,
whatever the hook decides. Claude Code's own permission rules are a second
layer that does not depend on the skill text, and that still asks in auto mode. A recommended block for your user settings,
`~/.claude/settings.json`, with `github-libera` replaced by your GitHub server's name:

```json
{
  "permissions": {
    "ask": [
      "Bash(git push*)",
      "mcp__github-libera__create_pull_request",
      "mcp__github-libera__update_pull_request",
      "mcp__github-libera__pull_request_review_write",
      "mcp__github-libera__add_comment_to_pending_review",
      "mcp__github-libera__add_reply_to_pull_request_comment",
      "mcp__github-libera__add_issue_comment"
    ],
    "deny": [
      "Bash(git push --force)",
      "Bash(git push --force *)",
      "Bash(git push -f *)",
      "Bash(gh pr merge*)",
      "Bash(gh pr review*)",
      "mcp__github-libera__merge_pull_request",
      "mcp__github-libera__push_files",
      "mcp__github-libera__create_or_update_file",
      "mcp__github-libera__delete_file",
      "mcp__github-libera__update_pull_request_branch"
    ]
  }
}
```

Nothing in the plugin needs a denied tool: `pr-fix` pushes with `--force-with-lease` only after
a rebase the person chose, which the `ask` rule covers and the `--force` rules do not match. Rules
match a command's prefix, so this is a backstop, not a complete list. The review tool cannot be
asked about by event, so a posted review's verdict, COMMENT, REQUEST_CHANGES or APPROVE, is the one
the person chose at `pr-review`'s post step, and the prompt this block keeps asks again. On the
`gh` path, `gh api` both reads and posts, so only the skill's own yes guards it. The sandbox's
`settings.template.json` denies every write, for runs that must post nothing.

`hooks/secret-gate.sh` stops what would carry a line that looks like a credential, naming the
file or field, the line and the kind but never the value:

- a `git commit`, read as the shell reads the command (comments, quotes, `$( )`, heredocs), in the
  repository `cd`, `git -C`, `--git-dir` or `--work-tree` names, run directly or through
  `bash -c`, `timeout`, `nice`, `nohup`, `xargs` or an alias whose first word is `commit`: its
  staged changes, the unstaged ones it or a `git add` in
  the same command would stage, the untracked files that `git add` names (ignored ones too with
  `-f`), its message and a `-F` message file;
- a `gh` command that creates, edits, comments on, reviews, merges, closes or reopens an issue or
  pull request, creates or edits a gist, release or repository, or `gh api` with fields or a body:
  its text and the files it sends;
- any tool of a GitHub server (one whose name holds `github`) or of the Atlassian server but a
  read: every string in its input.

It knows a fixed list of forms (`scripts/secret_scan.py`): private keys, AWS, GitHub, GitLab,
Slack, Atlassian Cloud, Anthropic and Google keys, JSON web tokens, bearer headers and a value
assigned to a token variable these servers name. An Atlassian Data Center token has no form of its
own, so it is found only when assigned to such a variable. When it cannot scan (a repository it
cannot resolve, such as `cd "$DIR"`, a shell alias that commits, git failing, or more than it can
check inside the hook's timeout), it asks rather than letting the call through. A variable the
same command sets once, on its own after the start, `;` or `&&` (an `&&` chain is read as running
through), to a literal value, as `S=/tmp/x; git commit -F $S/msg` or `C=/repo && git -C $C commit`,
is read as that value; one set any other way is not, and none is after control flow, `eval` or
`source`. In a message or body file's name it is read so only when the command writes no file
with `>`. A message or body file it cannot name, such as `-F "$M"`, is asked about too, unless the
same command writes it with `>` only from its own text: a bare `cat` reading a heredoc that
expands nothing, or `echo` or `printf` whose words expand nothing, and named nowhere else in the
command but the option that reads it, after the write, since the scan reads that text as the
command's. A file another program in the command writes, as `cp`, `tee` or `sed -i` does, is read as
it stands before the command runs. A false hit is
committed or posted outside Claude, or marked `gitleaks:allow` on its line. It is a backstop, not a
guarantee: a credential in a form it does not know passes, and so does one committed by a script,
a `make` target or a program other than `git` and `gh`, a commit run through `eval`, backticks,
a quoted `"$(git commit …)"` or `sh <<EOF`, an untracked file over 1 MB, a tag or merge message,
or a message file written from a `cat`, `echo` or `printf` that a shell function shadows.

`hooks/controlled-gate.sh` stops at a `.review/` file that opens with `Controlled:`, the line
`skills/writing/references/short.md`'s "Controlled content" puts on what is written from an item
that warns it is controlled. A Read, Edit, MultiEdit or NotebookEdit of such a file, a Grep
showing its lines, or a shell command that names it or a `.review/` directory holding it in a
part that may print a file's text is asked about, naming the item and its warning. Your yes
clears that item for the rest of the session: the hook records it in
`.review/controlled-cleared.json` once the call has run, and later reads of it pass; a session
that writes such a file, `Controlled:` line and all, has its item cleared the same way. A read of
the first line alone passes, and so do a Write that keeps that line, parts such as `ls`, `mkdir`,
`rm`, `find` without `-exec`, `git status` or `git commit -m`, and every command that does not
name the file. It is there to
catch a mistake, not to stop someone determined: a path built from a variable, a program that
opens a path the command does not name, and a recursive read from above `.review/` are not seen,
and the record is a file the session could write (`scripts/controlled_gate.py`).

### Your responsibility

You are responsible for what you give your agents access to, and for what they do with it. A
session acts under your credentials: your tokens, your MCP servers and the projects, spaces and
repositories they reach, and your shell. Give each the least access the work needs, keep secrets
and controlled data out of what they can read, and read what a skill proposes before you say yes.
The plugin's gates, hooks and checks catch mistakes; they are not a security boundary, and neither
is the model's judgment.

### Models

Each agent runs on the first of these that is set: the model a skill passes when it invokes the
agent, the agent's own `model:` line, the `CLAUDE_CODE_SUBAGENT_MODEL` environment variable, and
then your session's model. An agent's `model:` line wins over the environment variable unless
`CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` is also set (Claude Code 2.1.257 and later).

Agents that fetch or review one focus run on Sonnet; the rest are `inherit` and run on whatever
model your session uses; the agents table's Model column names each. On a Pro plan, start with `claude --model sonnet` or switch with `/model`, and the whole
build follows. To run the inheriting reviewers on a stronger or
weaker model than your session, set `CLAUDE_CODE_SUBAGENT_MODEL` in the `env` block of your
user settings. Never set `model` in a repository's project settings: it outranks each person's
own settings and binds the whole team. Why the agents are split this way is in
[`docs/design.md`](docs/design.md).

**How long things take, and what they cost.** The skills' time and cost in the sandbox are in
[`sandbox/README.md`](sandbox/README.md), "Cost". A planner run alone takes about a quarter of an
hour. The first ticket through `work` (Libera's, September 2026) took four sittings
and cost about $17 at API prices on Opus, most of it cache reads; a Pro plan's usage window will
not hold a full build on Opus.

## What is included

The skills a person types, in the order they meet them:

**Start here**
- `quickstart`: checks this machine and repository, says what to type next, and answers questions
  about the plugin; changes no tracked file.
- `onboard`: surveys a repository for the facts the plugin works from, asks only what it cannot
  detect, and writes the settings on your yes; on a second yes, drafts first review rules from
  merged review threads.

**Tickets and design**
- `ticket-draft`: drafts or refines a Jira ticket in the team's format, placed among existing work,
  and writes it to Jira only on your yes.
- `design-doc`: turns your notes into a design doc for work that spans several tickets, settling the
  problem and goals with you first, and publishes on your yes.
- `ticket-audit`: sweeps the Jira project for gaps, duplicates, stale tickets and links, and applies
  the actions you approve in one write plan.

**Build**
- `work`: works out where a ticket or its pull request stands and runs the next phase; each phase
  keeps its own approvals.
- `implement-change`: takes one change to an agreed plan, code verified by a wave of reviewers, and
  an offered pull request.

**Pull requests**
- `pr-create`: writes a reviewer-focused description and opens the pull request as a draft.
- `pr-review`: reviews the pull request against its ticket and the repository's standard, shows the
  findings at their lines, and posts one review only on your yes.
- `pr-fix`: takes each review thread to a verdict, implements the agreed fixes and drafts the
  replies, and asks before it pushes or posts.

**The standard**
- `revise`: prepares the monthly revision from how reviews were answered, proposing rules to add,
  reword or retire; `apply` drafts what the group accepted, and `correct` fixes a misreading between
  revisions.

**Docs**
- `architecture-doc`: writes a Confluence page on a system as it stands, from the code and your
  description, and publishes on your yes.
- `process-doc`: writes a Confluence page on how something is done, a process, a how-to or a user
  guide, and publishes on your yes.
- `drawio`: draws a context, component, flow or deployment diagram as draw.io XML, checked before it
  is handed over.
- `writing`: reviews or rewrites prose for structure and clarity without changing a fact.

**Supporting**
- `commit`: chooses what belongs in a commit and writes the message; never pushes.
- `test-suite-review`: judges test changes for loosening, missed failure paths and factoring; reads
  only.
- `downstream`: says which consuming repositories a change breaks, why a CI run went red, and which
  pins a release leaves behind.
- `skill-feedback`: files a complaint about a skill as an issue here, shown to you whole before your
  yes.

The `using-*` skills are not typed: they load when another skill reads GitHub, Jira, Confluence or a
shared library. The table below is the reference.

Most days need one command, `work`. Started, in the skills table: `typed only` runs only as a
`/lasp-dev:` command; `hidden` is not in the `/` menu and loads when a skill needs it;
`typed or asked` also runs when you ask in words or another skill calls it.

| Group | Skill | Started | Use it to |
| --- | --- | --- | --- |
| Entry point | `work` | typed or asked | Take a ticket through the workflow: reads where it stands and runs the next phase skill; each phase keeps its own approval gates |
| | `quickstart` | typed or asked | Say where this machine and repository stand, what to fix first and what to type next, with `onboard` first in a repository with no standard, and the skills by group; with a question, answer it from the plugin's own files. Reads only |
| | `onboard` | typed or asked | Survey a repository for the facts the plugin works from, its committed templates, contributing guide, test commands (instruction files, docs, CI) and pre-commit, and its history, and the tracker's statuses and fields when the servers are connected; say where each fact would be read from, the repository's own file first; first asking where the repository's rules live, here or in another repository's standard; then ask where facts should live, which value holds where the repository's files disagree, and which proposals to keep. Writes only `.review/onboard/` unless the person says yes to a named write: the repository's standard, or its `standard:` pointer and the standard's `profiles/<repo>.yaml` |
| Phases, also run alone | `ticket-draft` | typed or asked | Turn a prompt, an existing ticket or a pull request with none into one in the team's format: duplicates merged, dependencies, follow-up tickets for out-of-scope work, an in-session estimate, and an Open Questions section for what cannot be settled yet. `investigate` answers your questions about the code first; `settle` folds later answers in and records a departure the work keeps as a comment; `reformat` moves a drafted ticket to the current format, asking only what the format needs. Run directly for an epic or a group ticket session |
| | `implement-change` | typed or asked | Take a change request to an agreed plan, an implementation and a diff verified by a wave of reviewers |
| | `pr-create` | typed or asked | Write a reviewer-focused description and open the pull request |
| | `pr-review` | typed or asked | Review a pull request and present the findings at their lines, each citing a rule, decision, term, ticket criterion or test check when one applies, and no key otherwise; draft comments when asked, and post one review with the verdict you choose only on your yes. A posted review's threads are what the revision reads; a review kept local leaves it nothing |
| | `pr-fix` | typed or asked | Assess every thread, your own comments included, take your agree, disagree or discuss on each (posting them is optional, and each run links the ones not yet on GitHub), offer a rebase when the branch is behind, then plan, implement and reply to the agreed feedback on a pull request, people's comments before AI findings |
| Called by other skills, also typed | `commit` | typed or asked | Choose what belongs in a commit and write the message, Conventional Commits unless another style is asked for; never pushes |
| | `test-suite-review` | typed or asked | Judge test changes: loosening, failure paths, factoring, placement and lanes; run it directly on a colleague's test changes |
| | `downstream` | typed or asked | Say which consuming repositories a change breaks, why a run went red, and which pins a release leaves behind |
| Reference, hidden | `using-jira` | hidden | How a project's tickets are read and drafted: the format, the write plan and copy-paste markup, with the project's own fields, statuses and JQL read from its `tracker.md` |
| | `using-confluence` | hidden | How a project's Confluence is read and written, with its spaces, pages and macro values read from its `wiki.md`; what the tools cannot read |
| | `using-curryer` | hidden | curryer, a LASP-wide library that Libera and other LASP projects build on: who consumes curryer and libera_utils, and whether code belongs in curryer |
| | `using-github` | hidden | How the skills and agents reach GitHub: the server, the `gh` alternative and the push stop |
| Occasional | `design-doc` | typed or asked | Turn your notes page into a design doc for work that spans several tickets, existing or yet to be drafted: coaches you through the problem, goals and considerations before drafting, settles each design choice with you, draws the target architecture with `drawio`, maps the work onto tickets, and publishes the page in place on your yes; its `revise` mode changes a published one |
| | `architecture-doc` | typed or asked | Write a page on a system as it stands, from the code and your description: its purpose, confirmed with you, its runtime interfaces, people included, and how it works, in plain language and in a shape that suits the system; publishes on your yes. Its `revise` mode checks a published page against the code and brings it up to date |
| | `process-doc` | typed or asked | Write a page on how something is done, a team process, a how-to or a user guide, from your notes and the pages you point at: its purpose, readers and status confirmed with you, the steps and who does each settled with you, in plain language and a shape that suits its kind; publishes on your yes. Its `revise` mode brings a published page in line with how things are done now |
| | `drawio` | typed or asked | Draw a context, component, flow or deployment diagram as draw.io XML, checked by `scripts/drawio_check.py`, to paste into a Confluence draw.io macro; `architecture-doc`, `design-doc` and `process-doc` run it for their diagrams |
| | `writing` | typed or asked | How tickets, PR bodies, commit bodies and rule wording are structured and worded; run it to review existing text. Never changes a fact |
| | `revise` | typed only | Monthly: prepare the revision report before the meeting, with `measures` adding tickets, escaped defects and build yield; a sweep of the window's merged diffs reports where they follow or break the rules and the documented practice; `apply` drafts what the group accepted; `correct`, between revisions, corrects something the shared standards got wrong, everywhere it is carried, while a disagreement with a rule goes through Disagree and the revision |
| | `ticket-audit` | typed only | Sweeps across the project's Jira, written to `.review/audit/`, then the actions they propose applied in Jira through one write plan on your yes |
| | `skill-feedback` | typed or asked | File a complaint about a skill or agent as a `skill-feedback` issue here, in your words, with the session's last turns attached when you choose, or a draft `revise` wrote for a procedure finding; you see the whole issue before your yes |

`implement-change`, `commit`, `pr-create`, `pr-review` and `pr-fix` began from upstream and have
since been rewritten; the rest were written here.

| Agent | Model | Role |
| --- | --- | --- |
| `implementation-planner` | inherit | Drafts an approach for a change; plans only |
| `implementation-plan-reviewer` | inherit | Adversarially reviews a draft plan for over-building and missed detail |
| `implementation-reviewer` | inherit | Runs the tests and linters and judges a finished diff against the plan and scope |
| `focused-reviewer` | sonnet | One focus of the build's review wave (simplicity, documentation or tests), from a brief in `skills/implement-change/reviews/`; never edits the change |
| `github-pr-reviewer` | inherit | Run by `pr-review`: reviews one pull request's head and writes the findings, organized by concept, for `pr-review` to deduplicate, draft and post |
| `github-pr-fix-planner` | inherit | Run by `pr-fix`: assesses each review thread against the pull request with a recommended disposition, and names where a person's comment and an AI finding conflict, then plans a response to each agreed one, people's comments first; never edits or posts |
| `pytest-runner` | sonnet | Runs pytest and summarizes the result |
| `prose-reviewer` | inherit | Reviews a long document for `writing` in two phases: a plan of changes and questions, then only the approved edits |
| `ticket-investigator` | sonnet | Reads one repository for `ticket-draft`, `design-doc`, `architecture-doc`, `process-doc` and `downstream`: what the goal touches there, its callers, whether the source's claims hold, and scope beyond the goal; reads only |
| `pr-reader` | sonnet | Fetches a pull request's reviews, threads, conversation comments and body for `work`, `pr-review`, `pr-fix`, `ticket-draft` and `ticket-audit`, saves them under `.review/threads/`, judges the replies written in a person's own words, and returns what `scripts/record.py` prints: where the pull request stands, or, for `revise` and `onboard`, the records it rebuilt from the merged pull requests; never posts |
| `source-reader` | sonnet | Reads Jira, Confluence and GitHub for one task (a ticket, the ten closest tickets, the year plan, a page, or one `ticket-audit` sweep) and returns a fixed block; carries `using-jira` and `using-confluence`; never writes to Jira, Confluence or GitHub |
| `rule-probe` | sonnet | Reads one rule and one place in merged code and says whether the rule fires there, with the line; run on both anchors of a proposed rule's example line; reads only |
| `diff-probe` | sonnet | Reads one merged pull request's diff, commits and description for `revise`'s sweep and says, per rule or documented claim, whether the change follows it, breaks it (with the line) or leaves it untouched; reads only |
| `thread-analyst` | sonnet | Reads one merged pull request's review threads, reviewers' summaries and conversation comments, and the files they anchor to, for `revise`: what each asked for, what the diff did, and which asked about the procedure; in `defect` mode, which rule, candidate or check should have caught a fixed defect; reads only |

| Other | Role |
| --- | --- |
| `hooks/` | Measure a build (lint passes and test runs, never a `--collect-only`, `--version` or `--help` call, reviewer rounds and wave reviewers, wall clock less the waits before each resume, tokens) into `.review/build/`; hold the branch for one session at a time through `.review/lock`; at session start, print where the ticket on this branch stands and load the review rules that apply to the repository, fetching a standard elsewhere the first time a clone needs it; gate the Atlassian calls that are not reads, stop a commit, a `gh` write or a GitHub or Atlassian write that carries what looks like a credential, and ask before a read past the first line of a `.review/` file marked `Controlled:`, as "Permissions" above says; save each `pull_request_read` result to `.review/pages/` as the server returned it, for `pr-reader` to copy into its dump |
| `standards/` | The plugin's shared standards files, listed in `standards/README.md`. A project's own terminology, decisions, context, archive and review records live in its standard |

Text the skills compose for people on a pull request, or a page `design-doc`, `architecture-doc` or `process-doc` publishes,
carries an AI assistance level, `5/5` until you lower it; the scale and where it goes are
`skills/pr-review/comment-style.md`, "AI assistance level".

## Adopting the standards workflow in a repository

Once per repository. It needs:

| File | Where it comes from |
| --- | --- |
| `standards/review-rules.md`, the ledger, each entry holding its rule's wording as `> ` lines | `onboard`'s step 6 drafts it into `.review/harvest/`; people cut and commit |
| `standards/decisions.md`, optional | written by hand; a pipeline that produces a defined product adopts the fail-loud decision in `docs/standards.md`, "Example decision: fail loud" |
| `.github/PULL_REQUEST_TEMPLATE.md` | copied byte for byte from the standard's `templates/<name>/`, in the directory `scripts/profile.py --standard` prints; `/lasp-dev:quickstart` reports drift |
| `.review/` in `.gitignore` | the skills and hooks write their working files there |

`/lasp-dev:quickstart` names anything missing.

In this order:

1. Run `/lasp-dev:onboard` in the repository; on your yes it writes the repository's settings
   into its standard: the standard's `profile.yaml`, or `profiles/<repo>.yaml` in a standard for
   several repositories. When its survey stops with an error, write that file by hand from
   `standards/profile.example.yaml`.
   A repository whose tests are not pytest names its test command and its gate patterns in the
   profile first: the review wave passes the command to the implementation reviewer, and the
   build's gate counts come from the patterns. Until the file exists, the repository runs on what
   `profile.py` detects in its own files and the default profile (`docs/contracts.md`, "The profile").
   With no GitHub server connected, onboard cannot search for a shared standard and recommends
   neither answer to where the rules live (`onboard`'s "Where the rules live, then the survey").
2. Run `/lasp-dev:onboard` and, at its last step, draft the first rules from the
   repository's merged pull request history (`/lasp-dev:onboard rules` goes straight there).
   It needs at least five merged pull requests on GitHub with review threads a person wrote, the
   author's own included. It runs one agent per pull request with review threads, up to thirty.
3. A person cuts the candidates in `.review/harvest/` down to the rules the team wants.
4. Copy the PR template from the standard's `templates/<name>/`, the name the profile's `template` gives.
5. Add `.review/` to `.gitignore`.
6. Run `/lasp-dev:quickstart` in the repository.

In a public repository, nothing committed may carry an internal Confluence or Jira link or
content: the profile's `public` says which repositories are, as `libera_utils`, `libera_rad` and
`libera_cam` are for Libera, and the standard's `internal.domains` names the hosts that count as
internal.

Every skill works in a repository with no standard, and a standard adds to what they do. A
repository's standard is its `standards/` folder as checked out: the ledger,
`standards/review-rules.md`, and its decisions, `standards/decisions.md`, either one enough.
Decisions with no ledger are a standard with no rules yet, and `onboard`'s step 6 drafts them. A
ledger with no rules, by the team's choice or because no candidate met the bar, is a standard
with none admitted: step 6 does not draft them again, and `revise` admits them. A project whose
code spans several repositories keeps one standard in one of them, as `docs/standards.md` sets
out; each other repository's `standards/profile.yaml` is the one line `standard: <owner>/<repo>`,
and its standard is that repository's `standards/`, which `standard_file.sh` fetches with git at
each build and review, on origin's host and in its form, with no prompt, so the session's Bash
must reach it with the person's git credentials or the step stops naming it. The person may then
go on without it, `git config lasp-dev.standard none`, and the review's `standards:` line
says so; `git config lasp-dev.standard <absolute path>` reads a local checkout of the
standard's repository instead, for a trial of changes not yet merged. A repository has its own
standard or a pointer, never both.
A pull request that `implement-change` did not build is reviewed all the same. What differs:

| Skill | With no standard | With decisions and no ledger | With a `standard:` pointer | On a change not built |
| --- | --- | --- | --- | --- |
| `pr-review` | Reviews against the review contract alone, with no rule citations; the revision still reads the threads | Reviews against the repository's decisions too, with no rule citations | Reviews against the named repository's rules, decisions and terminology, fetched | Says so |
| `work` | Runs the same review stage | The same | The same | The same |
| `implement-change`, `pr-create` | Neither reads its `standard-repo.md` | Each reads its `standard-repo.md`: the standard for every agent, the project's pull request template and the Already checked block | As with decisions, the standard fetched | Unchanged |
| `pr-fix` | Writes no standard before its wave | Rewrites `.review/standard.md` before its wave | The same, fetched | Unchanged |
| `quickstart` | Reports `none` and offers `/lasp-dev:onboard` next | Reports `decisions, no rules yet` and offers `/lasp-dev:onboard rules` | Reports `from <owner>/<repo>` | Unchanged |
| `onboard` | Step 6 drafts the first rules | The same | Step 6 drafts from this repository's threads for the named standard, each tagged `repos: [<this repository>]`, once the standard covers it | Unchanged |
| `revise` | Does not run | Does not run | Runs here and writes into a clone of the named repository (`revise`'s "The standard's repository") | Unchanged |
| Everything else | Unchanged | Unchanged | Unchanged | Unchanged |

## How the corpus grows

Each kind of file has one home, and one way to change it:

| What | Where it lives | How it changes |
| --- | --- | --- |
| A repository's standard: `standards/review-rules.md`, each rule's wording in its entry, and `decisions.md`, either file enough | That repository's `standards/`, or the repository its `standard:` pointer names | A pull request there |
| Shared vocabulary, cross-repository decisions, context and the archive | The standard (`revise`'s "The standard's repository") | A pull request there |
| Archived review records | Beside the standard, in `log/<repo>/` (`revise`'s "The standard's repository") | The revision rebuilds each merged pull request's record from its threads and archives it there |
| The procedure: skills, agents, hooks | This plugin | A pull request here |

`/lasp-dev:quickstart what applies here` lists what a repository's standard applies to it:
each rule and decision with its number, title and status, the terminology and the context
entries, each under the file it comes from.

Who does what:

- **Everyone** answers the findings on their pull requests, as `GUIDE.md` "Reviewing a pull
  request" says.
- **The author** of a change runs `work`.
- **The month's driver**, a role that rotates, runs the monthly revision and commits that month's
  review records.
- **A personal preference** lives in your own Claude Code instructions. It becomes a rule only
  through review evidence, at a revision.

How a rule is admitted, established and retired: `GUIDE.md` "How the rules change"; the
thresholds are `standards/dials.md`.

**Tiers.** A rule sits in one of three. `prose` is the instruction file only: the author is
expected to know it and the reviewer does not check it, and it has no ledger entry. `reviewer` adds a ledger entry in
`standards/review-rules.md`, which the reviewer checks every diff against. `check` is a tool's
configuration, with the ledger entry kept as a pointer so the reviewer knows the ground is
covered. Each entry carries its status, `provisional`, `established`, `graduated` or `retired`,
on its own line. A rule is established by agreed findings in two different pull requests,
whoever wrote or agreed with them, and a candidate clustered from people's threads counts only
the threads a person wrote, not a bot's. A rule graduates when a check catches every agreed instance
in the window with no false positive on `main`, by the revision's judgment rather than a Dial,
and the check's configuration carries a header naming the rule it replaced and its archive
entry, which someone who hits a failing check follows to the reasoning.

**The archive.** Every rule that leaves keeps an entry in the standard's `archive/` (`revise`'s
"The standard's repository"): its
text as it read, why it was admitted, every decline reason quoted, and what replaced it. The
revision checks it before re-admitting a rule, for the reasons `docs/design.md`, "Why it is built
this way", gives.

**The harvest** is the pass that reads merged pull requests' review threads into records: once
at adoption by `onboard`'s step 6, and at each revision by `pr-reader` in harvest mode.

One line per file type:

- `review-rules.md`: the ledger, one entry per rule, with its wording, the one copy, as `> `
  lines, which `hooks/rules.sh` loads into every session in a repository the rule applies to.
- `review-contract.md`: how a reviewer behaves and what it never raises, one copy, in the plugin, that every repository's review uses.
- `decisions.md`: settled questions, so nobody asks them again.
- `terminology.md`: one name per thing across the repositories.
- `<repo>/log/`: `pr-NNNN.yaml`, one pull request's findings and replies, rebuilt from its threads at the revision; `correction-<date>-<id>.yaml`, one correction; `note-<date>-<id>.yaml`, one note.
- `archive/`: why a rule existed, kept after it leaves.

## Layout

```text
.claude-plugin/         # marketplace.json, plugin.json ("lasp-dev", rooted here)
skills/ agents/         # the skills and agents
hooks/                  # build measurement, the branch lock, the session-start line, the Atlassian write gate, the secret scan, the controlled-file gate, the saved pages
scripts/                # stdlib scripts the skills and hooks run: record.py, profile.py and the rest;
                        # jira_markup.py is mcp-atlassian 0.23.1's converter, copied (MIT)
standards/              # the plugin's shared standards files (standards/README.md)
tests/                  # the scripts' and hooks' tests, and their fixtures
sandbox/                # running a skill in a sandbox, repeated and compared
release/                # export.py, which writes the tree lasp/dev-tools ships, and is left out of it
docs/                   # contracts.md, design.md and standards.md
GUIDE.md                # the workflow, for people using it
ROADMAP.md              # planned and deferred work, and the team's open questions
UPSTREAM                # the fork point
LICENSE NOTICE          # MIT; the project's origins and the code it contains from elsewhere
.github/workflows/      # CI: the tests and drift checks
.github/skills, .github/agents   # symlinks into the plugin, for Copilot
.devcontainer/          # a dev container for working on this repository
```

The real files sit in the plugin and `.github/` links to them. A checkout without symlink
support, such as Windows without developer mode, writes a symlink as a one-line text file;
with the links pointing this way, such a checkout still installs a working plugin and loses
only Copilot's view.

### Working files in .review/

In a code repository, the tools keep their state in `.review/`, which the repository gitignores,
and which the hook keeps out of git through `.git/info/exclude` where it does not. It belongs to
the working tree, not the branch, and sits at the repository's top level, which the hooks find
from wherever in the repository the session stands. A detached HEAD is no branch: nothing is named
or parked for it, and a build started there is only its own session's. Nothing in it is committed. When the
session-start line or `work` says something unexpected, these files are what it read:

| File in `.review/` | Written by | Read by | Cleared when |
| --- | --- | --- | --- |
| `context/<ticket>.md` | `ticket-draft`, with the `Branch:` line for a pull request's ticket; `implement-change` adds its `Branch:` line | `work`, to see whether the ticket was drafted, and, with a `Branch:` line and no plan, which branch's pull request to read | Not cleared by the tools |
| `context/<ticket>.pasted.md` | `work`, `ticket-draft` and `implement-change`: a ticket's text the person pasted when the Atlassian server could not be reached | `source-reader`, given it as a file | Not cleared by the tools |
| `context.md` | `ticket-draft`, a copy of the latest page, never of a pull request's; `implement-change` adds `Branch:` | `work` and the session-start line, for the ticket the branch is on | Replaced by the next `ticket-draft` |
| `context/<ticket>.jira.txt`, `context/<ticket>.original.txt` | `ticket-draft`: the paste file, and the text before the session | The person, pasting into Jira what the write plan did not write; `ticket-draft`, for the `Original request` comment it writes | Not cleared by the tools |
| `context/<ticket>.send/` | `ticket-draft`'s write plan: each description and comment as shown (`.txt`) and as sent (`.md`), and the description as read back (`stored.txt`) | `scripts/jira_markdown.py`; the person, to see what was sent | Rewritten at each plan |
| `jira-plan.md` | The write plan, run by `ticket-draft` and `ticket-audit`: each item, numbered, with its text in full as it will be sent, written before the plan is shown | You, from the link at the plan's gate | Replaced at the next showing of a plan |
| `jira-approval.json` | The write plan, run by `ticket-draft` and `ticket-audit`: this session's id, the time and each approved item's tool and target, written at your yes before the first call | `hooks/atlassian-gate.sh`, which allows only a call it lists | Removed by the skill when the plan finishes or stops; allows nothing after 30 minutes |
| `controlled-cleared.json` | `hooks/controlled-gate.sh`, after a read of a `.review/` file marked `Controlled:` that you allowed, or the session's own write of one: this session's id and the items cleared | The same hook, which lets this session's later reads of those items through | Replaced when another session clears an item |
| `context/<ticket>.writes.md` | `ticket-draft`'s write plan: each item and whether it was written, with its key, failed, dropped or left to paste | The person | Rewritten at each plan |
| `implementation-plan-<ticket>.md` | `implement-change`: a draft from the planner, before the plan review, `Approved by:` at it, `Base:` at the branch, `## Corrections` at the plan and diff gates, `## Provisional decisions` for each decision made for now, and each `## Revision` with its own `Approved by:`; named for the branch with no ticket | `implement-change` on resume and at step 8 (`Depth:`, and `## Corrections` for a lowered depth), `work` and the session-start line (`Approved by:`), `pr-create` (`Base:`, `Approved by:`, `## Provisional decisions`), `commit` (the reason) | Not cleared by the tools |
| `pr-audit.md` | `pr-create`: each fact of its draft and the sections it appears in, the first paragraph's answers, the size and the cuts | `pr-create`, to edit the draft before showing it | Replaced at every description |
| `standard.md` | `scripts/standard_file.sh`, run by `implement-change` and `pr-review` | The planner and the reviewers | Rewritten at every build start and every review in a repository with a standard; the ledger's held candidates are left out |
| `lock.tmp` | The build hook, when it tells a session its lock was taken | Nobody: it is moved over `lock` | Left behind only by a failed write |
| `standard/` | `scripts/standard_file.sh`: `source`, in a repository whose standard is elsewhere, the named repository and the commit its standard was read at, `local` or `none` | `pr-review`, for the summary's `standards:` line; the person | Removed and written again whenever the standard is |
| `standard.md.tmp` | `scripts/standard_file.sh`'s callers, `implement-change` and `pr-review` | Nobody: it is moved over `standard.md` on success | Left behind only by a failed write |
| `build/events.jsonl` | The build hook | The hook's summary, `work`, `pr-create`, the session-start line | Started over when a build starts on another branch, after a finished build is parked under `build/done/<branch>/` |
| `build/already-checked.md` | The build hook, at each stop and when `pr-create` starts, the last being the first after `outcome.md` | `pr-create`, into the pull request body | Removed when a build starts on its branch, or resumes without `outcome.md`; parked under `build/done/<branch>/` with a finished build |
| `build/outcome.md` | `implement-change`, when the build loop stops | `work`, `pr-create`, the session-start line | Removed by `implement-change` when it goes back into the build, which `build-record.sh start` reopens; kept on a resume; parked under `build/done/<branch>/` when a build starts on another branch, or when `build-record.sh start fresh` starts a new change's record |
| `build/wave-<N>.md` | `implement-change` step 8: the wave's merged list, from the reviewers' digests | The person | Removed with an open build when a build starts on another branch; parked with a finished one |
| `build/wave-<N>-<focus>.md` | Each wave reviewer, its full report: `conformance` from the implementation reviewer, `simplicity`, `documentation` or `tests` from a focused reviewer, `honing` from a honing pass; `implement-change` writes the returned report when a reviewer did not | `implement-change`, only for a finding it is fixing; the person | Removed with an open build when a build starts on another branch; parked with a finished one |
| `build/done/<branch>/` | The build hook: a finished build, all its files, moved here when a build starts on another branch; one with no branch is dropped instead | `pr-create` and the session-start line for that branch | Moved back when a build starts on that branch again |
| `reopened/<ticket or branch>.txt` | `pr-fix`, on approving a reopen, one `Reopened:` line per thread, or `session-<pr>-<n>` for one decided in a session; keyed by the branch, `/` as `-`, when there is no ticket | `implement-change`, `pr-create`, `where.sh --fields` | Deleted by `pr-create` once the pull request's description carries its lines |
| `work-fields.txt`, `work-state.txt`, `work-stack.txt` | `work`: `where.sh --fields`, `pr-reader`'s state block, and a stacked ticket's pull requests | `scripts/next_phase.py` | Rewritten at each look |
| `lock` | The build hook, when `implement-change` or `pr-fix` starts, or `build-record.sh take` when the person takes it over; touched by its session's own hook events | The build hook, when either starts in another session; `work`, through `where.sh --fields`, before running either; the session-start line | Removed by `build-record.sh release` at the skill's last step, or when the holding session ends; one untouched for four hours is stale, and the next phase skill takes it; the session it was taken from is told once, at its next prompt or tool call, and that call is refused when it is a Bash, Write or Edit call |
| `pr-<n>-review-post.md` | `pr-review`, when it cannot be posted (no write access) | The person, to post it | Replaced by the next draft for that pull request |
| `pr-<n>-review.md` | The `github-pr-reviewer` agent, for `pr-review` | `pr-review` | Replaced by the next review of that pull request |
| `pr-<n>-review-submission.md` | `pr-review`, from step 3, zero findings included: `Head: <sha>`, `Posting: undecided, declined or posted`, its progress, the findings and, once drafted, the comments | `next_phase.py`, through `work`; `pr-review` on a re-review; the person, and the posted record | Replaced when the head moves; otherwise not cleared by the tools |
| `pr-<n>-fix-plan.md` | `pr-fix`, from step 5: `Head: <sha>`, its progress, the dispositions with each thread's link and `fixed <sha>` mark, and from step 7 the draft plan, replaced by the approved one | The implementation reviewer, as its plan file; `pr-fix` on a later run | Started afresh on a new head, keeping the dispositions not yet posted and the `fixed <sha>` rows whose fix reply has not posted |
| `fix/pr-<n>/` | `pr-fix` step 9's review wave: `wave-<N>.md` and each reviewer's `wave-<N>-<focus>.md`, as `build/` holds a build's | `pr-fix`, only for a finding it is fixing; the person | Emptied at the start of each `pr-fix` round on that pull request |
| `pages/<owner>-<repo>/pr-NNNN/` | `hooks/save-page.sh`, through `scripts/save_page.py`, after each `pull_request_read`: the result as the server returned it, named as a dump's `pages/` | `pr-reader`, which copies each page a hook note names into its dump | Each page replaced by the next call of its name; never cleared |
| `threads/pr-NNNN/` | `pr-reader`, the pull request's dump: `pages/`, the server's results as returned, and from them `pr.json`, `reviews.json`, `comments.json`, `issue-comments.json` and `body.md`, and its `judged.json` | `scripts/record.py --state`; `github-pr-fix-planner`, for `pr-fix` | Rewritten at each state call |
| `audit/` | `ticket-audit`: each sweep's report, and from Apply the write plan's texts (`<date>-send/`) and record (`<date>-writes.md`) | The person | Not cleared by the tools |
| `onboard/survey.md` | `onboard`: the survey's table, `scripts/survey.py`'s printout and what the servers showed | The person | Replaced at each survey |
| `onboard/downstream.json` | `onboard`, from its read-only code search when GitHub is connected: the repositories that import or depend on this one's package, each with its count of files | `scripts/survey.py --downstream-from`, for the candidate's proposed `downstream` | Replaced at each survey |
| `onboard/profile.yaml` | `onboard`, through `scripts/survey.py --profile`: the candidate profile, every key it cannot fill reading `not yet recorded`, with downstream repositories and depth globs proposed for the person to trim, and `profile.sources.json` beside it, where each value came from | `sandbox/onboard_roundtrip.py`; the person | Replaced at each survey |
| `onboard/answers.json` | `onboard`, from the person's answers: each key they confirmed, trimmed or typed, in the form `scripts/survey.py --answers` takes | `scripts/survey.py --drop-in`; `sandbox/onboard_roundtrip.py`; the person | Replaced at each run that asks |
| `onboard/project.yaml` | `onboard`, for a new standard: the project's settings the person gave, the tracker's workflow and the internal domains, in the profile's form | `onboard`, at step 5, into the standard's `profile.yaml` on the person's yes | Replaced at each run that asks |
| `onboard/profile.dropin.yaml` | `onboard`, through `scripts/survey.py --drop-in --answers`: only the keys the survey filled and the person settled, so the team's values stand for the rest | `onboard`, at step 5, on the person's yes; the person, to place it; a sandbox variant in place of the hand-written profile | Replaced at each run that asks |
| `onboard/clone/<owner>__<repo>` | `onboard`, for a standard in another repository, in the main working tree's `.review/` whichever working tree it runs in: a clone of it, read-only until its step 5 writes this repository's settings there on a branch | `git config lasp-dev.standard`, which names it until the standard's pull request merges; `onboard`'s next run, which uses it as it stands | Kept; removed by the person once the pull request merges and the config is unset |
| `design/<slug>/` | `design-doc`, under the page ID or a topic slug: `notes.md`, `frame.md` (confirmed with `Confirmed:`), a `.drawio` file per diagram, `draft.md`, a `tickets/<n>.md` prompt per ticket to create; `page.md` in `revise` | `design-doc`, resuming from the frame and publishing `draft.md`; `ticket-draft`, given a prompt; the person, placing the diagrams | Not cleared by the tools |
| `architecture/<slug>/` | `architecture-doc`, under the page ID or a slug from the system's name: `notes.md`, `facts.md` (the purpose confirmed with `Purpose confirmed:`), a `.drawio` file per diagram, `draft.md`; `page.md` and `page.storage.html` in `revise` | `architecture-doc`, resuming from `facts.md` and publishing `draft.md`; the person, placing the diagrams | Not cleared by the tools |
| `process/<slug>/` | `process-doc`, under the page ID or a topic slug: `notes.md`, `facts.md` (the purpose confirmed with `Purpose confirmed:`), a `.drawio` file per diagram, `draft.md`; `page.md` and `page.storage.html` in `revise` | `process-doc`, resuming from `facts.md` and publishing `draft.md`; the person, placing the diagrams | Not cleared by the tools |
| `diagrams/<slug>.drawio` | `drawio`, when its caller names no path | The person, pasting it into a draw.io macro | Not cleared by the tools |
| `downstream/` | `downstream`: `surface.txt`, `report.md`, a `ripple-<consumer>.md` or `ci-<run>.md` prompt for `ticket-draft`, and a throwaway venv and `git clone --shared` checkout per consumer, read at its default branch | The person; `ticket-draft`, given a prompt | Not cleared by the tools |
| `feedback/` | `skill-feedback`: the person's words (`words.txt`), and on the `gh` path the issue's title (`title.txt`) and body (`body.md`) | `scripts/transcript_excerpt.py --stdin`, for the words; `gh api`, for the title and body | Replaced at the next filing |
| `backtest/` | `revise` and `onboard`, each proposal's drafted entry and probe blocks (`R-NNN.entry.md`, `R-NNN.md`); the `rule-probe` sandbox scenario, `calibration.md` | The month's driver | Not cleared by the tools |
| `harvest/threads/`, `harvest/records/` | `pr-reader` in `harvest` mode, for `revise` and `onboard`: each merged pull request's dump (`pages/`, `pr.json`, `reviews.json`, `comments.json`, `issue-comments.json`, `body.md`, `judged.json`) and the record `scripts/record.py` rebuilt from it | `revise`, which copies the records into `standards/<repo>/log/` with `scripts/archive_records.py`; `thread-analyst`, for each record's authorship | Replaced at each harvest |
| `harvest/analysis/` | `thread-analyst`, one `pr-NNNN.md` per merged pull request with a record, within the cap of `revise`'s `harvest.md`, for `revise` and `onboard` | `revise`, for the report's front page; never copied into the log | Replaced at each revision |
| `harvest/` | `onboard`'s first rules: `threads.yaml`, `measurements.md` | The person | Not cleared by the tools |
| `harvest/context-refresh.md` | `revise`, its context refresh | The person, marking the refresh proposals | Rewritten at each revision |
| `ratchet-proposal.diff` | `revise`: the accepted change to this repository's `standards/`, instruction file and pull request template, and to the documents accepted `doc/` proposals name | The driver, to apply and open as a pull request | Not cleared by the tools |
| `checks/`, `archive-pages/` | `revise`: drafted checks, Confluence page bodies | The person | Not cleared by the tools |
| `revision/claims.md`, `revision/sweep/` | `revise`'s sweep at `prepare` step 2: the rules and documented claims it judges, and one `diff-probe` block per merged pull request (`pr-NNNN.md`) | `revise`, for the report's Practice section | Replaced at each revision |
| `revision/notes/` | The driver, before `revise` `prepare`: meeting or chat notes, pasted | `revise`, read as asks at `prepare` step 5 | Not cleared by the tools |
| `revision/tickets/` | `revise` `apply`: each accepted `ticket/` proposal as a prompt (`<n>-<slug>.md`) | `ticket-draft`, given a prompt's path, one at a time | Replaced at each `apply` |
| `revision/feedback/` | `revise`: a `skill-feedback` draft per procedure finding, from `prepare` step 2 and `correct` step 2 | `skill-feedback`, given a draft's path | Not cleared by the tools |

## Changing the tooling

Change files here through a pull request reviewed by the team. A new skill or agent needs its
link (`.github/skills/<name>` or `.github/agents/<name>.agent.md`) and a row in the skills or
agents table. Planned work is in [`ROADMAP.md`](ROADMAP.md).

The files and printouts one skill writes and another reads are in
[`docs/contracts.md`](docs/contracts.md), each with its version and the test that holds it. A
change to any of them bumps its version there and in the script that writes it.

To run what you are changing, one of three ways:

- **Install from your clone:** `claude plugin marketplace remove lasp-dev-tools`, then `claude plugin
  marketplace add <path to the clone>` and `claude plugin install lasp-dev@lasp-dev-tools`. Claude
  Code refuses to add a marketplace under a name it already holds from another source, hence the
  remove. Switch back the same way, with `claude plugin marketplace add
  lasp/dev-tools`.
- **One session:** `claude --plugin-dir <path>` loads a checkout without changing the install,
  but beside it: with the plugin installed, every skill and agent appears twice. Run `claude
  plugin disable lasp-dev@lasp-dev-tools` first and `claude plugin enable lasp-dev@lasp-dev-tools`
  after, or pass `--settings` a file holding `{"enabledPlugins": {"lasp-dev@lasp-dev-tools":
  false}}` for that session. `CLAUDE_CODE_PLUGIN_DIRS` is the same thing as an environment
  variable, for a shell or container where every session should load a checkout.
- **The dev container** in `.devcontainer/` registers the checkout as the marketplace, so there
  the checkout is the plugin, live at the next session or after `/reload-plugins`.

Keep pull requests small. How much review each kind of change gets:

| Change | Review |
| --- | --- |
| Review records | None; the month's driver commits them |
| The monthly revision's pull request | The group session is the review; one approval after it |
| Skills, agents and hooks | One reviewer, reading a text diff; CI runs the tests and the drift checks on every pull request |

How a change to the tooling's behavior is proposed and reviewed:

- A change to what a skill, agent or hook does carries three lines in its pull request
  description. `Origin:` the `skill-feedback` issue, the review thread or the note it answers.
  `Sandbox:` the scenario that states the complaint and its `check` pass rate as the current
  plugin and as the branch, from `sandbox/run.py compare`. `Canary:` the days the maintainer ran
  the branch on real work before asking for review, a week for a change to a gate or a post. It
  bumps the skill's or agent's `metadata.version`. A pull request whose change is wording, tests,
  or a script change that alters no gate or output carries none of the three.
- Issues labeled `skill-feedback` on this repository are the one place a complaint about a skill
  goes; anyone files one, with `/lasp-dev:skill-feedback` or by hand, and `revise` drafts one
  for each procedure finding it does not find settled, for the driver to file. The maintainer writes one
  disposition on each within the month, as a label: `accepted`, with a scenario and a pull
  request to follow; `declined`, with the reason in a comment; `held`, dropped after six months
  with no new evidence; `corpus`, when it is reviewer behavior, which `revise`'s `correct` mode handles; `safety`, fixed at once, outside the
  month, for a post, push or write without a yes or internal content in a public repository. The
  last five minutes of the monthly revision meeting list the tooling pull requests merged since
  the previous meeting with their `Origin:` lines, and the open issues with their dispositions;
  the maintainer decides, and anyone who disagrees says so there or on the issue.
- No change is made from an agent's reading alone. A `Procedure:` pointer from the analyst, and
  the issue drafted from it, or a judge's score sends the maintainer to read something; a person's words or a deterministic count
  is the evidence.

Everyone's rollback is installing from a commit they trust: `claude plugin marketplace remove
lasp-dev-tools`, then `claude plugin marketplace add lasp/dev-tools#<ref>` and the same
install command. The plugin's `git log` is the changelog a reviewer reads.

`plugin.json` carries no `version`. Claude Code keys an install by its version, so a fixed one
makes `plugin update` report an install as current however much the files changed. Without one,
the install is keyed by commit, and `claude plugin list` shows the commit's SHA. `claude plugin
validate .` warns that the version is missing; the warning is expected.

The five forked skills upstream still changes (`implement-change`, `pr-create`, `pr-review`,
`pr-fix` and `commit`), and the agents the fork brought with them, are diffed against upstream's
HEAD about once a quarter, and anything worth having is ported by hand in a pull request here;
nothing syncs. From the checkout's root, this prints what upstream changed in its skills and
agents since the last review, or the fork commit:

```bash
from=$(sed -n 's/^reviewed: [0-9-]* //p' UPSTREAM); from=${from:-$(sed -n 's/^commit: //p' UPSTREAM)}; d=$(mktemp -d) && git clone -q "$(sed -n 's/^upstream: //p' UPSTREAM)" "$d" && git -C "$d" diff "$from" HEAD -- '*skills/*' '*agents/*'
```

The command diffs from the last review, or from the fork commit while `reviewed:` reads `none`. A
review that ports or declines what it found sets the line to `reviewed: <YYYY-MM-DD> <upstream
HEAD sha>`.
`create-gauntlet-loop-prompt` and `repo-instructions-update-planner` stay upstream and are not
carried here; the gauntlet's tests of an acceptance criterion are in `ticket-draft`.

The devcontainer runs `uv sync` at creation: `pyproject.toml` pins the dev tools (pyyaml,
codespell, pre-commit) and `.python-version` the Python, and `.venv/bin` leads `PATH`, so `python3` is the
project's. CI runs the same `uv sync`. Outside the devcontainer, `uv sync` does the same; the
scripts themselves need only the standard library; `jira_markup.py` is mcp-atlassian 0.23.1's
wiki markup converter, copied so that `jira_markdown.py` needs no package either.

Run `uv run pre-commit install` once in your clone: `.pre-commit-config.yaml` then runs gitleaks on
what each commit stages, whoever makes it. CI does not run it; the plugin's own
`hooks/secret-gate.sh` covers the commits a session makes.

CI (`.github/workflows/checks.yml`) runs, on every pull request:

- `uv run python -m unittest discover -s tests`: the scripts' tests, one module per script, and the
  sandbox runner's; `tests/fixtures/` holds their inputs, and `test_sandbox.py` needs PyYAML,
  which `uv sync` installs. `test_jira_markdown.py` checks the copied
  converter against mcp-atlassian 0.23.1 where uvx has it cached, which CI's step before it does,
  and skips that check otherwise; when the install command's version changes, copy the converter
  again from that version.
- `bash tests/test_build_record.sh`: `hooks/build-record.sh`.
- `bash tests/test_where.sh`: `hooks/where.sh`, the start-of-session line.
- `bash tests/test_standard_file.sh`: `scripts/standard_file.sh`, `scripts/standard.sh`, which it fetches through, and `hooks/rules.sh`, the rules loaded at session start.
- `bash tests/test_atlassian_gate.sh`: `hooks/atlassian-gate.sh`, against every tool of mcp-atlassian 0.23.1.
- `uv run python scripts/check_static.py`: what the skills and agents name exists, and no
  shipped file gains a mention of Libera (`scripts/coupling.json`; after removing mentions,
  `--update-coupling` lowers the baseline).
- The tests and `check_static.py` again on Python 3.9, the floor "Install" names, with
  `uv run --isolated --python 3.9`.
- codespell, with `en-GB_to_en-US`, for American spelling.
- `claude plugin validate .`, on the plugin and marketplace manifests.

To try a skill change before its pull request, run it in [`sandbox/`](sandbox/README.md): the
skill's scenario on a worktree of your branch beside the current plugin, repeated, then
compared, and `--check --repeat 2` on it before the merge. Nothing there runs in CI.
