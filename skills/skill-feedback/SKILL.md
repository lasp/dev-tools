---
name: skill-feedback
description: >
  Files a complaint about a lasp-dev skill or agent as a `skill-feedback` issue on the
  plugin's repository, in the person's words, with the last turns of this session attached when
  they choose; nothing is filed before they see the whole issue and say yes. Use when asked to
  "file feedback", "report this skill", "complain about this skill" or "this skill got it wrong".
  Also files a draft `revise` wrote for a procedure finding, given its path. Not for Claude Code's
  built-in `/feedback`, which sends the conversation to Anthropic.
argument-hint: "[skill: what you did not like | .review/revision/feedback/<draft>.md]"
metadata:
  author: dev-tools
  version: 1.1.1
---

# Feedback

A `skill-feedback` issue on the plugin's repository is the one place a complaint about a
skill goes, and the maintainer answers each within the month (the README's "Changing the
tooling"). This skill files one, so a complaint does not stay in the conversation it was made in.
Every question it asks follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. Nothing
leaves the machine before the person's yes to the issue as shown.

The plugin's repository is the `homepage` in `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`,
`https://github.com/<owner>/<repo>`: read it before step 4 shows the issue. A `plugin.json` that
cannot be read, has no `homepage`, or one that is not a GitHub repository's URL stops at step 4:
say which, and hand over the title and the body with no URL.

## 1. The person's words

The issue carries three answers from the person:

- **What happened**: what the skill or agent did.
- **What they did not like** about it.
- **What they would like instead.**

Take what the arguments already give: `ticket-draft: the ticket is too detailed to read` names the
skill and says what they did not like. Ask, in one message in prose, only for what is still
missing; free text is the answer here, so no widget. A question the person skips is left out of
the issue, not filled in.

**A draft.** An argument that is a path under `.review/revision/feedback/` is a draft `revise`
wrote for a procedure finding, in this form:

```markdown
**Skill:** `<skill or agent, or unknown>`
**Source:** <where the finding came from: a pull request and its thread, review or comment id, or a correction and its date>

**What happened**

<the finding>

**What I would like instead**

<the change asked for>
```

Its headings are step 1's answers, any of the three, and it asks for none that is missing. Its
`**Skill:**` line answers step 2's first question unless it reads `unknown`, and step 2 asks no
log question: the finding came from another session, so the issue is words only. Its words are
the revision's reading of a thread or the person's correction, not typed here; they go in as the
draft holds them. Its `**Source:**` line goes in the body under the `**Skill:**` line, and runs
through step 4's redaction with the answers. A draft files nothing on its own: step 4 shows the whole issue and only `File
it` files it. Reading the draft shows the person nothing, so step 4's preview is never skipped
for one. A path that does not exist, or a file with none of the three headings, stops here:
say which.

The answers go in as the person wrote them: never reworded, summarized or completed from your
reading of the session, since a person's words are the evidence a change is made from. Fix
nothing but what they ask you to fix. The one change is the redaction step 4 runs over them.

## 2. The skill and the log

Work out which skill or agent the complaint is about: the one the arguments name, else the one
the person's words name, else the last lasp-dev skill or agent that ran in this session. Then
ask one widget with the questions still open:

- **Which skill or agent is this about?** The one you worked out, `(Recommended)`, and the other
  lasp-dev skills or agents that ran in this session, up to four. Skip this question when the
  arguments named it.
- **Attach the session?** `The last 10 turns` or `Words only`; another number of turns through
  "Other". Recommend the log when the complaint is about something that happened in this
  session, and words only when it is about the skill in general or the session holds none of it.
  Say what a log holds: each message from the person and Claude's text, the questions Claude
  asked with their answers, every other tool call by name only, and a `!` shell command without
  its output, with tokens, keys, passwords, internal links and the home directory removed, all of
  it shown before anything is filed.

## 3. The excerpt

With a log, from any directory:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/transcript_excerpt.py" --turns <n> --before-skill skill-feedback --max-chars 60000
```

It prints the turns before the one that started this skill as one fenced `text` block, so GitHub
turns no `@login` or `#n` in it into a mention or a link, and on stderr how many turns it kept,
how many of the oldest it dropped to fit, the excerpt's length in characters and what it removed
of each kind. GitHub refuses an issue body over 65,536 characters; `--max-chars 60000` leaves the
rest for the words, so when the three answers run past about 5,000 characters, lower it by as
much. An exit of 1 is a stop for the log: say its stderr in one line
and ask whether to file words only. With zero turns, the session held nothing before this
request: say so and draft the words only. Where `${CLAUDE_PLUGIN_ROOT}` is not set, such as under
Copilot, neither this command nor step 4's runs, and `plugin.json` cannot be read: say so, offer
words only, say in the preview that the words were not redacted, and hand over the issue to paste
as a `plugin.json` that cannot be read does.

## 4. The draft

The plugin commit: `git -C "${CLAUDE_PLUGIN_ROOT}" rev-parse --short HEAD` when the plugin root is
a checkout; otherwise the root's last path component, which names the commit an install is keyed
by.

Run the three answers through the same redaction and use what it prints. No heredoc carries
them, since a line in them equal to its terminator would end it and run the rest as shell: write
them to `.review/feedback/words.txt` with the Write tool, as `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`
"Writing a file" says (`rm -f .review/feedback/words.txt` first when an earlier run left one), then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/transcript_excerpt.py" --stdin < .review/feedback/words.txt
```

A draft is redacted as it stands, never retyped into `words.txt`: the same command with `<
<draft path>` in place of `< .review/feedback/words.txt`.

The redaction knows only the internal hosts of the default profile and of the working directory's
repository's standard. A transcript or answer that names another project's hosts, such as a
session that worked in another repository, keeps them, so the person's preview of the whole issue
before it is filed is the check for those.

The title is `<skill>: <what they did not like>`, in their redacted words, cut to under 70
characters; with no such answer, as from a draft, `<skill>: <what happened>`. The body:

```markdown
**Skill:** `<skill or agent>` · **Plugin commit:** `<sha>`
<from a draft: its **Source:** line>

**What happened**

<their words>

**What I did not like**

<their words>

**What I would like instead**

<their words>

<details>
<summary>The session: the last <n> turns, tool calls by name only, secrets and internal links removed</summary>

<the excerpt as printed, its fence included>

</details>

Filed with `/lasp-dev:skill-feedback`.
```

From a draft, the last line reads ``Drafted by `/lasp-dev:revise`, filed with
`/lasp-dev:skill-feedback`.``

The summary's `<n>` is the count of turns kept, from the stderr `turns:` line, not the count
asked for. A skipped answer drops its heading; words only drops the `<details>` block. An issue is not pull
request prose, so it carries no AI assistance level (`${CLAUDE_PLUGIN_ROOT}/skills/pr-review/comment-style.md`,
"AI assistance level").

Before showing it, when the repository is known, look for a likely duplicate among the open
issues' titles, as step 5 reaches GitHub, one page of ten: `search_issues` with the query
`repo:<owner>/<repo> label:skill-feedback is:open in:title "<skill>:"`, or `gh issue list --repo
<owner>/<repo> --label skill-feedback --state open --search '"<skill>:" in:title' --json
number,title --limit 10`. Read the titles only. One that names the same complaint is a likely
duplicate. When GitHub cannot be reached, the check is skipped, and the message below says so.

Show the whole issue as it would post with the question below, as
`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`'s "What does not change" says: the
repository, the title, the label and the body with the excerpt in full, then in one line how
many turns the excerpt kept, and how many of the oldest it dropped to fit when it dropped any, and what was removed from the words and from the excerpt,
each kind that was not zero. The person's words and a draft's `**Source:**` line stay as typed, so when they hold an `@login`
or a `#n`, say in that line that GitHub will notify that person or link that issue or pull
request. A likely duplicate is named in that line, `#<n> <title>`, and then `Let's discuss` is
recommended in place of filing a second. When the check found GitHub unreachable, that line says
so as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the duplicate check and the filing
being what is lost, and offers `gh`, and `Paste it instead` is recommended in place of filing. Then, in that same message, below the issue, ask:

- `File it (Recommended)`: open the issue on `<owner>/<repo>`, labeled
  `skill-feedback`.
- `Paste it instead`: hand over the title and body; nothing is filed.
- `Let's discuss`.

A change typed in "Other", such as a cut to the excerpt or a different number of turns, is made,
and the whole issue is shown and asked again. Only `File it` files it.

## 5. Filing

Reach GitHub as `${CLAUDE_SKILL_DIR}/../using-github/SKILL.md` says, for the plugin's `<owner>`:
the MCP server by default, `gh` when the person has said so.

- **The server:** `issue_write` with method `create`, owner `<owner>`, repo `<repo>`, the title,
  the body and labels `["skill-feedback"]`; then read the issue back with `issue_read`.
- **`gh`:** the title and the body never go inside a command. Write the title, with no newline
  after it, to `.review/feedback/title.txt` and the body to `.review/feedback/body.md` with the
  Write tool, as step 4 wrote the words, and hand both to `gh api`, whose `-F field=@file` reads
  the field from the file:

  ```bash
  gh api repos/<owner>/<repo>/issues -F title=@.review/feedback/title.txt -F body=@.review/feedback/body.md -f 'labels[]=skill-feedback' --jq .number
  ```

  Then `gh issue view <number> --repo <owner>/<repo> --json url,labels`.

Report the issue's URL. When the issue read back has no `skill-feedback` label, say in one line
that the label did not attach, and that the plugin maintainer, or anyone with push access to the
repository, can add it.

When the server cannot be reached or the call fails, say so as `servers.md` sets out, the error
verbatim, and that nothing was filed: hand over the title and the body in one code block,
its fence longer than the excerpt's, with `https://github.com/<owner>/<repo>/issues/new`, to file by hand with the
`skill-feedback` label. `Paste it instead` hands over the same.
