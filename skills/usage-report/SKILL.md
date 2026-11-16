---
name: usage-report
description: >
  Counts how you have used the lasp-dev plugin from your own Claude Code transcripts on this
  machine, shows you your summary and then the whole report, numbers and fixed words only, and on
  your yes sends it to the plugin's maintainer as a `usage-report` issue, or writes it to a file.
  `collect`, for the maintainer, merges the reports sent into one table, posting nothing.
  Use when asked to "run usage-report", "send a usage report", "report my plugin usage", "how
  have I used lasp-dev", "collect the usage reports" or "merge the usage reports". Not for a
  complaint about a skill, which is skill-feedback's, or for Claude Code's built-in `/usage` (also
  `/cost` and `/stats`), which shows session cost and plan limits, `/insights`, which analyzes
  recent sessions, or `/skill-doctor` (Claude Code 2.1.252 or later), which shows each skill's
  context cost and use.
argument-hint: "[file | collect [<report file>...]] [since YYYY-MM-DD]"
metadata:
  author: lasp-dev
  version: 1.0.0
---

# Usage report

The report tells the maintainer which skills carry the load, where runs stop and which questions
get clicked through, from everyone who runs it. Every value in it is a number, a duration or a word
from a fixed list; the one text it carries is a note the person types. `scripts/usage_report.py`
builds it and checks every value it is given, and nothing leaves the machine before the person's
yes to the report as shown. Every question follows
`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`.

The files live in a directory of this run's own under the temporary directory, outside every
repository and outside `~/.claude`, which Claude Code's sandbox keeps commands from writing. Step 2
makes it and calls it `<run>`:

- the report: `<run>/payload.json`;
- the runs to classify, which hold the person's own words and are never sent: `<run>/pending.json`;
- the person's note: `<run>/notes.txt`; the issue's body: `<run>/body.md` on the `gh` path, and
  as read back after the send, `<run>/sent.md`.

Nothing records a report once it is sent: the next report finds where this one closed from the
person's issues titled `usage-report: …`. The title, which this skill always writes, is how a
report is found; the `usage-report` label is optional, since GitHub drops it without a word when
the sender has no push access to the repository.

Where `${CLAUDE_PLUGIN_ROOT}` is not set, such as under Copilot, there are no Claude Code
transcripts to count: say so and stop.

The arguments set the destination. With none, it is `dev-tools`: an issue on the plugin's
repository. With `file`, it is `file`: the report is written where the person says, and the skill
stops. Either may be followed by `since YYYY-MM-DD`. With `collect`, nothing is counted: read
`${CLAUDE_SKILL_DIR}/collect.md` and follow it in place of the steps below; the plugin root it
writes as `<plugin root>` is `${CLAUDE_PLUGIN_ROOT}`. Any other argument stops the skill before it
counts anything, with one line: "usage-report takes no argument, `file`, or `collect` and any report
files, each optionally with `since YYYY-MM-DD`; nothing was counted."

## 1. Where the window opens

The window closes now. It opens at the first of these that applies, and the summary says which:

1. the date the arguments give, `since YYYY-MM-DD`, for either destination;
2. for `dev-tools`, where the person's last report closed: the `window.end` of the newest issue
   titled `usage-report: …` they opened on the plugin's repository, open or closed;
3. 30 days ago, when there is no such issue, none in the first 3 pages, the GitHub server cannot
   be reached, or the destination is `file`:

   ```bash
   python3 -c 'from datetime import datetime, timedelta, timezone; print(f"{datetime.now(timezone.utc) - timedelta(days=30):%Y-%m-%dT%H:%M:%SZ}")'
   ```

For the second, the plugin's repository is the `homepage` in
`${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`, `https://github.com/<owner>/<repo>`. Resolve
the GitHub tools, the issue write tool among them, as `${CLAUDE_SKILL_DIR}/../using-github/SKILL.md`
says, and take the person's login from `get_me`. Then `list_issues` on `<owner>/<repo>` with
`orderBy: CREATED_AT`, `direction: DESC`, `fields: ["number", "title", "user", "created_at"]` and
`perPage: 100`, and no `state` or `labels`, so closed and unlabeled issues count too, paging with
`after` until an issue whose title begins `usage-report:` and whose author is that login, or none
is left, or 3 pages are read; past 3 pages, the window opens 30 days ago and the summary line says
no report of theirs was among the newest 300 issues.
Read only the person's issue, with `issue_read` `get`: its body is a report this skill sent, in a
`json` fence, and its `window.end` is where this window opens, passed to the script as it reads. On
`gh`, when the person has said so:

```bash
gh issue list --repo <owner>/<repo> --search 'in:title "usage-report:" sort:created-desc' --author @me --state all --limit 100 --json number,title,body --jq 'first(.[] | select(.title | startswith("usage-report:"))) | {number, body}'
```

No output is no such issue.

An issue whose body holds no `window.end`, or whose `window.end` the script refuses at step 2,
stops the skill before it counts anything: name the issue, and say that `since YYYY-MM-DD` sets the
start. A `plugin.json` with no GitHub `homepage`, or no GitHub server, or a call that fails, is said
as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, where this report's window opens being
what is lost, and the window opens 30 days ago.

## 2. Count

Make the run's directory, from any directory:

```bash
mktemp -d "${TMPDIR:-/tmp}/usage-report.XXXXXX"
```

and write the path it prints in full wherever `<run>` stands below. Then, with the Bash tool's
`timeout` at 600000, since the script reads every transcript in the window:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/usage_report.py" --plugin-root "${CLAUDE_PLUGIN_ROOT}" --since <start> --out <run>/payload.json --pending <run>/pending.json
```

`<start>` is step 1's date or time. A nonzero exit is a refusal: show its stderr as it reads and
stop; nothing was written. When `<start>` is an issue's `window.end`, also name the issue and say
that `since YYYY-MM-DD` sets the start.

## 3. What the person did next

Read the runs with `cat <run>/pending.json`: at most the 40 most recent plugin skill runs, in
order, each with the skill and `next_message`, the person's first message after the run started,
cut to 400 characters, or null. Give each run exactly one label:

- `approve`: accepts what the run did or proposed, or tells it to go on: "looks good", "yes, go
  ahead", "thanks", "commit it".
- `correct`: says something the run did or produced is wrong, or asks for it changed: "no, the
  key is PROJ-51", "make it shorter", "that test is not needed".
- `status`: asks about the result or where things stand, without accepting or correcting it:
  "what did the tests say?", "which files changed?".
- `new_task`: turns to work that does not follow from the run: another ticket, an unrelated
  question, a typed command that does not act on the run's result.
- `interrupt`: stops or halts the run: "stop", "wait", "cancel that", or an interruption marker.
- `none`: `next_message` is null. Only a null is `none`, and a null is always `none`.

A message that does more than one takes the first that fits, in this order: `interrupt`,
`correct`, `approve`, `status`, `new_task`; "looks good, but fix the title" is `correct`. The
messages stay here: none is quoted in the summary, the report or any message to the person.

## 4. Overlap with the person's own skills

Print the frontmatter of the person's own skills and agents, at most 15 lines of each of the
first 50 files, each line cut to 300 characters:

```bash
awk -f "${CLAUDE_SKILL_DIR}/frontmatter.awk" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/skills/*/SKILL.md "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/agents/*.md < /dev/null
```

A kind whose pattern matches no file has none, and no output means the person has neither. A last
line `== <n> more files left out` means those were not compared; the summary's overlap line says so.
Compare each description with the plugin's skills and agents as this session lists them. A personal skill or
agent counts toward a plugin skill or agent when a request the plugin one is for would plausibly
reach the personal one instead: the same job, not shared words. A personal `meeting-review` skill
for meeting notes does not compete with `pr-review`; a personal `review-my-pr` does. One personal
skill may count toward several plugin ones. Only the counts go into the report.

## 5. Fill the report

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/usage_report.py" --fill <run>/payload.json --pending <run>/pending.json --labels <one label per run, in order, space-separated> --plugin-root "${CLAUDE_PLUGIN_ROOT}" --overlap <skill:<name>=<n> or agent:<name>=<n> for each plugin one with a count>
```

`--labels` with no labels is zero runs; `--overlap` with no items is no overlap. The script counts
the labels per skill, refuses a count that does not match the runs or a `none` that does not match
a null, and prints the report as written, then its `sha256:` digest. A refusal names what was
wrong: correct it and run the command again; a second refusal stops the run, its stderr shown.

## 6. The person's view

For `dev-tools`, the repository and the GitHub tools are step 1's, resolved now as it says when
`since` meant step 1 read no issue. A `plugin.json` with no GitHub `homepage`, or no GitHub
server, is said as `${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, the issue being what is
lost, and `Write it to a file instead` is then recommended in place of sending, with `gh` offered.

One message, in this order:

1. **Your summary**, this size whatever the use:
   - one line: the window's dates and which of step 1's starts applied, sessions, plugin skill
     runs (typed, and started by Claude) and plugin agent runs;
   - a table of the skills with the most runs, at most eight: skill, runs, median turns, median
     tokens, and the label given most often after a run (`-` for a skill with no labeled run);
   - one line each for the questions (answered, and how many took the recommended option), the
     denials and hook asks or denies (totals), and how many of the person's own skills and agents
     overlap a plugin one, with how many were left out uncompared, if any.
2. **The report as it will be sent**: what step 5 printed, whole, in one `json` fence, then the
   digest line. Never cut, reorder or retype a value; it is what the person checks.
3. **Where it goes**, in one line before the question:
   - `dev-tools`: an issue on `<owner>/<repo>`, titled `usage-report: <window start date> to
     <window end date>`, with the report as its body. Everyone who can see
     `<owner>/<repo>` can read it, under the person's GitHub login.
   - `file`: written where the person says, and sent by them as they choose; nothing is sent or
     recorded from here, so the next report does not start where this one closes: it starts 30
     days back, at the person's `since`, or, sent as an issue, where their last `usage-report: …`
     issue closed.
4. **One widget, two questions**:
   - **A note?** "Anything to add in your own words? It goes into the report's `notes` as you
     type it." `No note (Recommended)` and `Let's discuss`; a note is typed through "Other".
   - For `dev-tools`, **Send it?** `Send it (Recommended)`: open the issue as described;
     `Write it to a file instead`, which asks the `file` question below, with the `file` line of
     "Where it goes"; `Don't send`: nothing is sent, the report stays at `<run>/payload.json`,
     and the next report covers this window again.
   - For `file`, **Where?** `<home directory>/usage-report-<window end date>.json (Recommended)`
     and `Don't write it`; another path through "Other".

A note typed in "Other": `rm -f <run>/notes.txt`, write the note as typed to that file with the
Write tool, as `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`'s "Writing a file" says, then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/usage_report.py" --fill <run>/payload.json --notes <run>/notes.txt
```

The report changed, so an answer already given to the send or where question no longer counts:
show the note as it now reads in the report, the new digest, and the report's path as a link for
the whole of it, saying only `notes` changed, and ask that question again. Any other change the
person asks for, such as a label, reruns step 5 and shows the whole report again.

Only `Send it`, or a path the person gave or chose, sends or writes anything; a standing answer
such as "take the recommended answers" is not one, as
`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`'s "What does not change" says. Nor is a
request made before the report was shown that names the send, such as "send my usage report to the
maintainers": the yes is to the report as shown.

## 7. Sending

**An issue.** Reach GitHub as `${CLAUDE_SKILL_DIR}/../using-github/SKILL.md` says, for the
plugin's `<owner>`: the MCP server by default, `gh` when the person has said so. The body is the
report as step 5 last printed it, byte for byte, in a `json` fence, then the digest line in
backticks, then `Filed with /lasp-dev:usage-report.` on a line of its own.

- **The server:** `issue_write` with method `create`, owner `<owner>`, repo `<repo>`, the title,
  the body and labels `["usage-report"]`; then read the issue back with `issue_read` `get` and
  write its `body` to `<run>/sent.md` with the Write tool, exactly as it came: no character
  changed, added or dropped.
- **`gh`:** write the body to `<run>/body.md` with the Write tool, then:

  ```bash
  gh api repos/<owner>/<repo>/issues -f 'title=usage-report: <window start date> to <window end date>' -F body=@<run>/body.md -f 'labels[]=usage-report' --jq .number
  ```

  Then `gh issue view <number> --repo <owner>/<repo> --json body --jq .body > <run>/sent.md`; the
  issue's URL is `https://github.com/<owner>/<repo>/issues/<number>`.

Then check the body as GitHub holds it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/usage_merge.py" --out <run>/check.json --report sender <run>/sent.md
```

Exit 0: report the issue's URL. The label is not checked: reports are found by their title.

Exit 1: the issue's body does not match the report shown, so `collect` will refuse it. Say so, with
the script's line and the issue's URL, link the text either write option would send, `<run>/body.md`
on `gh` or `<run>/payload.json` otherwise, with its sha256 digest, as the report shown at step 6,
unchanged; on the server the body sent is that report in a `json` fence, the digest line and
`Filed with /lasp-dev:usage-report.`, as above. Then ask one question:
`Correct the issue (Recommended)`, which replaces its body with that report's body (`issue_write`
`update` with `issue_number` and `body`; on `gh`, `gh api -X PATCH
repos/<owner>/<repo>/issues/<number> -F body=@<run>/body.md`), then reads it back and checks it
again; `Close it and send again`, which closes it (`state: closed`, `state_reason: not_planned`;
on `gh`, `gh issue close <number> --repo <owner>/<repo> --reason "not planned"`) and creates a new
issue as above; `Leave it`, which leaves the issue as it is, named as one `collect` will
refuse; and `Let's discuss`. Only `Correct the issue` or `Close it and send again` writes, as
only `Send it` sent the report. A body that still does not match after a correction or a resend
is said with the issue's URL, and nothing more is written. Never leave a mismatch unsaid.

A failed create is said as `servers.md` sets out, the error verbatim: nothing was sent; offer
`Write it to a file instead`. A create that succeeded and a read-back that failed is said apart
from that: the report was sent but could not be confirmed, with the issue's number or URL when the
create returned one, and the error verbatim. Nothing is offered, so no second issue follows, and
the next report still opens where this one closed, since step 1 finds the issue.

**A file.** At the path the person gave or chose, never replacing a file: `test -e <path>` first,
and when it exists, ask for another path. Then `cp <run>/payload.json <path>`. Say the path, and
that the report is theirs to send as they choose. Then stop.
