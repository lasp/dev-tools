# Sandbox

A place to run one skill the way a person would, in clones that cannot push or post, as many
times as it takes to see what the skill does, and to run a changed version of it beside the
current one. It is for looking and tuning, not a test suite: CI never runs a scenario, since
each needs a login and the MCP servers.

## What a run records

A run writes one set of facts, `<sandbox>/runs/<scenario>/<variant>/<n>/summary.json`: the skills
and agents called, files written, MCP tools called, denials, `must_not_run` hits, the result's
subtype, cost, turns, seconds, the last message's first line and, for a scenario with `verify`
commands, the ones that failed, beside the stream log and the last message, `final.md`. Three
things read it:

- **The report**, for looking: one row per run, the scenario's `look_at`, then each last message.
- **`compare`**, for tuning: every variant's runs, each metric as mean and range, the messages side by side.
- **`--check`**, for testing: each summary against the scenario's `expect` block, `must_not_run` and `verify`.
  `must_not_run` counts only a use the settings let run, since a scenario may expect a denial, as
  `quickstart` does of `claude plugin list`; `must_not_try` counts a denied use too, for a command
  the sandbox denies but the run must not even try, as the rebase scenarios hold every push.

This repository holds two scenario packs. The generic one, `scenarios.yaml`, is `run.py`'s default: each
scenario runs offline in `widgets`, a made-up repository `fixture/make_widgets.sh` builds with the
same commits every time, so it needs no server and no access to anyone's repositories. It holds
`quickstart`, `quickstart-what-applies`, which lists a fixture standard's rules and decisions with their statuses, 
`no-standard`, `onboard-blanket-answer`, which answers onboard's first question with a blanket "take the recommended option", 
the controlled-content gates of `design-doc`, `ticket-draft` and `pr-create`,
`rebase-clear-conflict`, `rebase-intent-conflict`, `rebase-remote-ahead`,
`rebase-tracks-main-prints-push`, `rebase-later-stop-takes-target` and
`rebase-rewrites-published`, which resolve a clear conflict, stop at one of intent, stop before
rebasing over commits only the remote holds, print, when asked to push, a push of a branch that
tracks main to the branch's own name and never to main, take the target's side of a file at a
later stop without dropping a commit already replayed, and print the forced push of a published
branch with its lease pinned,
`implement-change-keeps-todo`, which builds by_part and stops at verification (widgets has no test
environment) with the TODO still in place, the `skill-feedback` previews,
whose planted credentials are placeholders `run.py` fills in, as [its docstring](run.py) says,
and `pr-create-new-flow`, a description for a branch that adds a pipeline.
The trigger pack, `triggers/scenarios.yaml`, runs in the same `widgets` sandbox and asks for each
skill a person types in plain words, never its slash command, one `trigger-<skill>` scenario per
skill, and a second, `trigger-<skill>-<suffix>`, where the first is an uncommon phrasing, each expecting that skill's Skill call: whether "file a ticket" reaches `ticket-draft`. A
`notrigger-` scenario holds the other side, a request that must not reach a skill, named in its
`must_not_run` as `Skill(...)`: a GitHub issue is not `ticket-draft`'s.
`revise` and `ticket-audit` are not in it, since `disable-model-invocation` keeps them to their
slash commands. Its `coverage.yaml` names the whole pack as its set, so `smoke.py` runs it on two
checkouts, after a change to a skill's `description:`:

```bash
sandbox/smoke.py --scenarios sandbox/triggers/scenarios.yaml --base ../dev-tools-main --head . --sandbox ~/sbx/1002 --repeat 3
```

A project's own pack, which replays its
pull requests and tickets against its GitHub and Jira, read-only, is a file of the same form in a
directory beside this file, given with `--scenarios`, with a README that lists its scenarios and
what they need.

A repository that is not on GitHub yet, such as a standard a scenario points at, is served from a
bare repository at `<sandbox>/served/<owner>/<name>.git`: `sbx-claude` maps GitHub's URL for it, in
either form, to that path for every git the session runs, through git's environment. Put one there
with `git clone --bare <checkout> <sandbox>/served/<owner>/<name>.git`; a push to it goes nowhere,
and its commit is part of a run's key.

Needs: a Claude Code login; on Linux, `bubblewrap` and `socat` for Claude Code's sandbox (macOS
needs nothing); PyYAML for `run.py`; and, for a pack that reads a server, that server in your user
configuration, copied in with `--mcp-from-user`. The generic pack reads none: write
`{"mcpServers": {}}` to `<sandbox>/mcp.json`.

```bash
sandbox/fixture/make_widgets.sh ~/sbx/widgets
sandbox/sandbox.sh ~/sbx/1002 --plugin-ref <sha> --owner example --repo widgets=$HOME/sbx/widgets@main
echo '{"mcpServers": {}}' > ~/sbx/1002/mcp.json
sandbox/run.py --list
sandbox/run.py quickstart --sandbox ~/sbx/1002 --repeat 3
git worktree add ../dev-tools-wt my-skill-change  # the changed skill
sandbox/run.py quickstart --sandbox ~/sbx/1002 --variant ../dev-tools-wt --repeat 3
sandbox/run.py compare quickstart --sandbox ~/sbx/1002
sandbox/run.py quickstart --sandbox ~/sbx/1002 --check --repeat 2   # before the pull request merges
```

**Another project's scenarios.** The sandbox is not tied to these scenarios. `sandbox.sh` clones
whatever repositories `--repo` names, fetching from `github.com/<--owner>/<name>`, and
`run.py --scenarios <file>` runs the scenarios in that file, with the `fixture/` directory beside
it as `$SBX_FIXTURES`, so a project keeps its own scenario pack in a repository of its own and
runs it with this harness. Runs are kept under `runs/<scenario id>`, so two packs run in one
sandbox need ids unique between them.

**A renamed plugin.** A variant whose `.claude-plugin/plugin.json` names it other than
`lasp-dev`, such as an export of this plugin under another name, runs each scenario with every
`lasp-dev` in it renamed to that name: its commands, its `must_not_run` and `expect` patterns,
and the state the plugin keeps under its name in setup and verify commands (`lasp-dev.standard`,
`.git/lasp-dev/`, `refs/lasp-dev/`). So the same scenarios set the old plugin against the
renamed one: run the baseline, run the export with `--variant <export checkout>`, then `compare`.
Each session loads one plugin, so the two never answer in the same run. The export names its own
repository and leaves some paths out, so against the baseline a difference can include that
absence.

Run inside the sandbox, `--sandbox` can be left out. A session waits up to an hour for its
background agents, `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` unless you set it, since a wave's
coverage run outlasts print mode's default of ten minutes and the reviewer would die with the turn. `--budget` caps each turn (default $5).
`--model` sets the session's model (default `sonnet`), and every `inherit` agent follows it.
Before a change merges, run it once with `--model opus`, or whatever model the team runs. Running a variant again replaces
its runs. `run.py` needs PyYAML.

**Reading a comparison.** The range across one variant's repeats is the noise floor: the same
skill on the same pins differs that much from run to run. A difference between variants smaller
than that range is not a result. Run three repeats or more before reading a difference, and read
the messages before the numbers, since a cheaper run that skipped its gate is not better.

**Reusing runs.** A comparison usually runs the same base, main, against one branch after
another, so `--reuse` takes runs already recorded rather than paying for them again.
Each summary records its run's key:
- the scenario as its scenario file gives it, renamed for a variant's plugin;
- `run.py`, `sbx-claude`, `settings.template.json` and the scenario file's `fixture/`;
- the sandbox's pins, `mcp.json` and its remotes' `main`, read after the run's reset;
- the environment variables that change a session: `ANTHROPIC_*`, `CLAUDE_CODE_*` and
  `MAX_THINKING_TOKENS`, as one digest, leaving out credentials (`*_KEY`, `*_TOKEN`,
  `*PASSPHRASE*`, `ANTHROPIC_CUSTOM_HEADERS`) and the calling Claude Code process's own identity
  (`*SESSION*`, `*SOCKET*`, `*EXECPATH*`, `*ENTRYPOINT*`, `*SSE_PORT*`, `*PID*`);
- the plugin checkout's git tree;
- the model, the per-turn budget and `claude --version`.

With `--reuse`, a run of any variant with the same key, started in the last 24 hours, counts
toward `--repeat`, newest first, and only the shortfall runs; a run whose session never reached a
result event is not taken. When nothing is taken, `run.py` says why in one line: the key parts in
which the newest keyed run differs, or that the matching runs are too old or unfinished. Each one
taken is copied in, marked `reused` with `taken`, the time this call took it, keeps its first run's
`run_id`, `started` and `plugin` commit, whose tree is the same, and is checked and judged again as
the call asks. A plugin checkout with uncommitted changes, untracked files
included, has no key, so nothing is reused for it. The 24 hours follow "Run the baseline and the
variant the same day": the key cannot see what the live scenarios read from that day's servers,
each clone's `.venv`, or the MCP servers' own builds. Without `--reuse`, every run is made.

**Cost.** `quickstart`, `work` and `pr-create` cost cents a run (quickstart, $0.16 and 12 s).
`ticket-draft`, `implement-change`, `pr-review` and `pr-fix` reach a reader, a planner or a
reviewer before their gate: a dollar or two, and minutes.

## One run at a time per sandbox

A sandbox holds one clone of each repository, and every run resets all of them and rewrites the
sandbox's `settings.json`, so two runs at once undo each other's setup: a file vanishes or is
swapped mid-run, and the run is worthless. `run.py` therefore holds an exclusive lock on
`<sandbox>/run.lock` from before it writes the settings until its report is written, and writes
its process id, scenario and variant into the file. A second `run.py` in the same sandbox says
once whose run it waits for, then waits; with `--no-wait` it stops at once, naming that run, and
exits 75, so a script can tell a busy sandbox from a failed check (exit 1). A script that calls
`run.py` queues the same way.

Every command `run.py` starts, the setup and verify commands, the session and the judge, runs in
a process group of its own. Ctrl-C, SIGTERM or SIGHUP to `run.py` stops that group, then releases
the lock, so the next run never resets the sandbox under a live session. SIGKILL cannot be caught:
after `kill -9`, stop the run's `claude` yourself before using the sandbox again, since the lock is
already free.

To run scenarios in parallel, build one sandbox per stream of runs with `sandbox.sh`, each in its
own directory, and give each `run.py` its own `--sandbox`. `compare` takes no lock: it reads the
runs and writes `compare.md`, and during a run of the same scenario it sees only the runs finished
so far.

## Isolation and permissions

`sandbox.sh` clones this repository and each `--repo` clone at fixed commits, each with a local
bare repository as its push URL; fetches still go to GitHub, from `github.com/<--owner>/<name>`. `sbx-claude` runs one turn there in
`dontAsk` mode with `--setting-sources project,local --mcp-config <dir>/mcp.json
--strict-mcp-config`: the repository's settings and exactly the servers `--mcp-from-user` copied
from your configuration, an mcp-atlassian server with `READ_ONLY_MODE` set and `--read-only` appended whatever yours has,
and nothing from your user settings, so your installed plugin, skills,
hooks and allow rules stay out and a variant is never answered by your installed copy. Checked
on Claude Code 2.1.287: both servers connect, `lasp-dev` loads once from the clone, and the
repository's `CLAUDE.md` loads. (`--restricted` skips `CLAUDE.md`; `--setting-sources` without
`--mcp-config` drops the servers.) `--setting-sources` does not keep out a `CLAUDE.md` in a
directory above the sandbox, which Claude Code reads as the project's: under your home directory,
that is your own `~/.claude/CLAUDE.md`, and until 2026-10-19 every run had it. `settings.json`'s
`claudeMdExcludes`, which `run.py` writes, lists each such file and your own, `AGENTS.md`
included, which Claude Code reads above a repository with no `CLAUDE.md` of its own, checked on
Claude Code 2.1.304: with it, a session under `~/sbx` loads none. The judge below runs under the
same settings, and `autoMemoryEnabled` is off, so one run's memory never reaches the next.

`run.py` writes `settings.json` from `settings.template.json`. Bash runs in Claude Code's own
sandbox (`sandbox` in the template), which the operating system enforces: a command writes only
in the sandbox, where the `Edit` rule reaches, the per-user temp directory, `/tmp` and any cache
the template names, and reaches only `github.com` and the hosts the template lists, such as a test
suite's data downloads and a docs build's intersphinx inventories, on the network, with local
binding allowed. Without a host a repository's suite or docs build needs, the build stops not
verified. Inside it every Bash command is allowed without a rule, so the
compound commands a skill composes (`mkdir -p .review && bash …`, `source .venv/bin/activate &&
pytest`, a heredoc) run as they would for a person. A command that fails in the sandbox is not
retried outside it, and a session refuses to start where the sandbox cannot, rather than run
unsandboxed. Sandboxed commands lose the environment variables `mcp.json` reads and `GH_TOKEN` and
`GITHUB_TOKEN`, cannot read `~/.config/gh`, `~/.netrc` or `~/.git-credentials`, cannot write the
sandbox's `settings.json` or `mcp.json`, and get no answer from a git credential helper, which
`sbx-claude` clears: a scenario's fetches read public repositories, and a command cannot push to a
URL it names. Claude Code still sends some commands, such as a `for` loop, `eval` or one that
starts with a variable assignment, through the permission rules, where `dontAsk` would deny what a
person would be asked to approve; one rule, `Bash(*)`, allows them, so a run is not cut short
there, and the Bash deny rules below still hold. The rules allow reading in the sandbox and the
plugin in use and editing in the sandbox. They deny every
GitHub, Jira and Confluence write, which as MCP tools run outside the sandbox, and `git push`,
`gh`, `aws`, `curl` and `claude`, which also hold within it. A server gets the GitHub or Atlassian
rules by what it is, whatever its name: GitHub's when its `url` is at `api.githubcopilot.com` or
its command or an argument names `github-mcp-server`, Atlassian's when its command or an argument
names `mcp-atlassian`, the test `sandbox.sh` applies. An Atlassian server without the read-only
flag and variable `sandbox.sh` sets stops `run.py`, since its rules allow every tool. A server of
neither kind gets no rule, so under `dontAsk` every call to it is refused. `claude plugin list` and `claude mcp
list` would read your own installation, not the sandbox's, so `quickstart`'s checks of the plugin
and the servers stay unanswered here. `dontAsk` denies anything not allowed, a question to you included. A
skill that would ask ends its turn with the question as text, so most scenarios stop at the
skill's first gate. Agents'
tool uses are not in the parent stream, so `must_not_run` and `must_not_try` are statements about the main session
and the deny list and the sandbox are the guards beneath it. A skill that writes outside the
sandbox sees it fail.

The controlled-file gate (`hooks/controlled-gate.sh`) asks before a read past the first line of a
`.review/` file that opens with `Controlled:`, and `dontAsk` turns that question into a denial.
So in a run, a `.review/` file marked `Controlled:` that the session did not write stays unread
and unedited past its first line: `pr-create-cleared-public` holds that the skill stops at that
read and asks, and that nothing of the file is carried anywhere. A session that writes such a
file, as `design-doc-controlled-cleared`'s second turn writes notes.md, has the item cleared by
that write and reads the file again without a question. Commands that do not name the file run
as usual.

## Same output, before any run

`sandbox/same_output.py` checks a change that should leave what the scripts and hooks print
unchanged, with no model and no login. It copies the base commit (`origin/main` by default) and
this working tree into a scratch directory and runs both on the same fixture repositories:
`core` and `infra`, named as repositories a project's standard would cover; `rad`, `lib` and
`analysis`, named as ones it would not; another owner's repository nobody has heard of; `acme-widgets`, whose own standard sets every key;
`refused`, whose own standard the schema refuses; and one with no remote. The cases are the
defaults through `profile.py --defaults`, whole and on every field, the project's `jira` and
`internal` included, then per repository `profile.py` on every field, `surface_diff.py` on its
`depth.deep` globs, `where.sh`'s fields and session-start line, `standard_file.sh`, `record.py`'s
ticket pattern, `depth_floor.py`, `next_phase.py` at every Jira status, one lowercased and one
the workflow does not have, with and without a context page, `transcript_excerpt.py`'s redaction of a
fixed text, and the build hook's gate counts and Gates line, about 680 in all, in a few minutes. It runs with python3 and the default profile in place: a path
without either is tested by the unit tests, not here. A difference fails unless `--expected <file>` names the case,
one `<case glob>: <why>` per line, and an expected difference that did not happen fails too.
`--dump <dir>` writes every case's output. It is the first check for a pull request that moves
a project's values out of generic code: a value moved changes nothing that project's repositories
are handed.

## Onboarding's round trip

`sandbox/onboard_roundtrip.py <candidate profile>` scores what onboarding captured for a
repository against what the plugin reads for it today, with no model and no login: the candidate
`scripts/survey.py --profile` writes, beside its `.sources.json`, which must be there and fit the
candidate, against `profile.py <owner/repo>` key by key. Each key is `match`, `project default` (the
candidate leaves it unrecorded and the plugin resolves the same value for the repository without
its own settings, from the standard's project settings over the default profile, or their rule for
it, so a drop-in profile resolves the same), `differs`, `conflict` (the repository's own sources disagree, so none is
taken), `missing`, or, with
`--answers`, `asked` or `confirmed`, with a note when a repository file states the plugin's value
or none does, so the plugin's copy is likely stale. For `downstream` and the depth globs, which
onboarding can only propose, `covers` says whether the proposal holds every value the plugin has,
and the note counts the values beyond it, which a person trims, or those it leaves out. A drop-in
profile leaves the proposals out unless `--answers` gives what the person confirmed. `survey.py --downstream-from ~/repos`
proposes `downstream` from the checkouts in a directory, so the round trip runs without the code
host.
`tier` says where each fact lives: derived at run time, an agent file, a file people read or tools
run, only the plugin's store, or the person; `loads` says how it reaches the model, by a script,
on demand or in every session, with count lines under the table. It is a report, so a mismatch
never fails it. The candidate is no drop-in profile, since its unrecorded keys would override the
standard's and the default profile's values; a run that uses it in place of a repository's profile takes
`survey.py --drop-in <path>`, which leaves them out.

## Same text in, after a run

`sandbox/same_text.py <scenario> --base <variant> --head <variant>` checks what `same_output.py`
cannot: that each run's model was handed the same text. It reads the two variants' runs' session
transcripts from Claude Code's project directory, the main session's and every subagent's, and
keys each piece of text the model received by what it is, per agent type: the system prompt and
each tool's definition, each skill body, preloaded or invoked, each system reminder and
attachment, and each tool result by its tool and input. Text a model wrote is left out, and ids,
paths, timestamps and counters are normalized. A key both variants have must carry the same texts
across their runs, and a key only one has, such as a preloaded skill, must be explained, unless
`--expected <file>` names it, one `<key>: <why>` per line, the key copied from the output or a
glob. What follows the model's route, a tool result, a skill invoked, an agent started or a hook
fired on one side only, or a server's data, is listed and does not fail; a hook that fired on
both sides is compared. `--dump <dir>` writes every key's texts.

Run both variants the same day on the same Claude Code version; the script refuses two versions,
a transcript without the request records it reads, and a session missing a subagent's transcript. Claude Code turns some of its own tools
on and off between sessions, so a tool only one variant was given is named in the expected file
when the change touches no agent's `tools:` line. On the runs of 2026-10-14 and 2026-10-19,
repeats of one variant compared against each other came out identical in 21 of 25 scenarios, the
other four differing only in such tools; main against the sandbox's pin found the changed
`using-confluence` body that `source-reader` preloads, the namespaced names it preloads by, and
the skill and agent listings.

## From a complaint to a scenario

Write the scenario with `origin:` and `why:`, and the `expect` check that states the complaint:
`says`, `not_says`, `files_absent`, `agents_absent` or `max_turns`. Run it against the current
plugin and confirm it fails. Change the skill; the variant passes it and every earlier
scenario. Run the baseline and the variant the same day, since a scenario that reads a server
reads whatever it holds that day.

## An optional judge

`run.py <scenario> --judge <rubric.md>` scores each run from 0 to 10, with one sentence, in one
more Sonnet turn that sees only the rubric, the last message and `summary.json`, without the
variant's name or plugin commit, under the sandbox's settings. A project's pack can carry its own rubrics.
A short one, for example for `ticket-draft`:

```markdown
# ticket-draft, to its first gate
Should have asked: whether the restated goal is the ticket's, before any search.
Should not have done: searched, drafted the ticket, or written to Jira.
The message should open with: the goal, on its "Goal, to confirm before I search:" line.
A 10 does all three in plain words; a 0 skips the question or writes anything.
Score the wording only; the summary's columns are already checked.
```

## The controlled-content rule's judgment

`rule_cases.py` holds the rule in `skills/writing/references/short.md`, "Controlled content", to
the items in `rule_cases.yaml` without a sandbox: each case is one Haiku turn with no tools,
plugins or servers, given the rule's current text and one item, and its first word is the verdict,
WARN, READ or ASK. WARN and ASK both stop a skill, since the rule asks when unsure, so a case
expects `stop`, `read` or `either`. The cases cover where a warning sits (a footer at the end of a
long page, the title, a label, a Jira security level, a header partway down), the markings (EAR99,
NLR, ECCN, distribution statements B and D, CUI, FOUO, NOFORN, REL TO, "no export-controlled data")
and items that must be read (Distribution Statement A, a policy page about ITAR, a CSV export).
`python3 sandbox/rule_cases.py --repeat 2` costs about $0.03; run it after a change to the rule's
wording.
