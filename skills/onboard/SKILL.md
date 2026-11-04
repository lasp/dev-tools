---
name: onboard
description: >
  Asks where the repository's rules live, here or in another repository that holds its project's
  standard, then surveys it for the facts the plugin works from (its templates, contributing guide,
  the test commands its instructions and CI give, pre-commit, history habits) and, when the servers are connected, the tracker's
  statuses and fields, shows where each fact would be read from, asks only what neither detection
  nor the standard answers, and writes the standard's settings, or the pointer to it, only on a
  yes, otherwise only under .review/onboard/. Where the
  repository has no review rules, it then offers to draft the first ones from its merged review
  threads, into .review/harvest/, on a yes. Use when asked to "onboard this repository", "survey
  this repo", "what does the plugin know about this repo" or "draft the first review rules". Not
  for checking this machine's setup, which is quickstart, or for changing existing rules, which
  is revise.
argument-hint: "[rules [Confluence page or Jira epic to add]]"
metadata:
  author: lasp-dev
  version: 0.6.1
---

# Onboard

The first look at a repository the plugin is to work in. It first asks where the repository's
rules live: in a standard of its own, or in the one standard its project keeps in another
repository (`<plugin root>/docs/standards.md`, in the plugin's repository). It reads what the
repository already keeps, compares it with what the plugin reads today, and says where each fact
would come from. Then it asks what only the person can settle: which value stands where the
repository's own files disagree, which of its proposals hold, and, for a new standard, the
tracker's workflow and the internal domains. Where the repository has no review rules yet, it last offers to draft
them from its merged review threads. It writes nothing outside `.review/onboard/` without a yes to
that write in particular, nothing to Jira or Confluence, and nothing to GitHub but, on its own
yes, a standard elsewhere's branch and pull request.

Every question, and every file it writes, follows
`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`, and every item read follows
`${CLAUDE_PLUGIN_ROOT}/skills/writing/references/short.md`, "Controlled content". The plugin root
those files write as `<plugin root>` is `${CLAUDE_PLUGIN_ROOT}`.

The person may be new to the plugin. The first time a question or table uses one of these words,
say what it means in a clause: the **rules**, the checks a review applies to every pull request;
the **standard**, the rules with the project's decisions and the settings below, kept in one place
the plugin reads; a **build**, the plugin's run that makes a change, tests it and reviews it before
a pull request. A question and the table's prose name what a setting does, never a profile key, a
script, an option, an exit code or a file under `.review/`; those go in the one line that follows
an answer, or in reply to the person asking how.

## Options

| Option | Default |
|---|---|
| Servers | Read when connected; say "skip the servers" to leave them out |
| Start | Step 1. `rules` starts at step 6, for a repository already onboarded |
| Pages and epics | None. Confluence pages or Jira epics named after `rules`, or at step 6, are read for the first rules |

## 1. Where the rules live, then the survey

First run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/onboard_state.py"`, once, with nothing in front
of it: its `key: value` lines are what this step reads about the checkout, and no other command
is run for them. Every command this skill runs is written as it gives it, with the literal paths
the state's lines print: nothing after it but the `>/dev/null` a command here names (no
`; echo`), no shell variable, no `$(...)` or `$PWD`, and no `cd` in front, since each of those
makes the person approve a command they cannot allow once for every run. The one exception is step
5's readback after a move, which names its own form. When the repository already has a standard, say where in one
line and go on: its own `standards/`, the files its `own standard:` line lists, or the repository
its `pointer:` line names, which is cloned as for "another repository" below, so step 5 can write
this repository's settings there; a `pointer:` marked `(uncommitted)` is the working tree's,
not yet committed, often an earlier run's write whose pull request has not merged, and the
standard it names is the part before the mark. Only those lines say so: a `standard setting:` naming a clone,
with no pointer, is an earlier onboarding's unfinished write, not a standard; ask the question
below, and step 5 writes the pointer.

Otherwise, with GitHub connected and the servers not skipped, first look for the project's
standard: one `search_code` for `path:standards/profiles org:<owner>`. A repository with hits there
keeps a standard for several repositories, and one holding `standards/profiles/<this repo>.yaml`
already covers this one. Then ask, before anything else:

> Where do this repository's rules live?

- **Here, in this repository** (Recommended for a repository on its own, or the first of a
  project's): its rules, decisions and settings live in its own `standards/`, and its pull requests
  change them.
- **In another repository**: the project's repositories share one standard there; this repository
  keeps one line naming it, and its settings live in that standard, whose pull requests change
  them. Recommended, naming the repository, when the search found a standard that covers this
  repository, or a single standard for several; the person otherwise names it, `<owner>/<repo>`.
- **Let's discuss**.

The question says what each answer means for the person and names the standard the search found,
with what it covers; it carries no path, command or sandbox step, which follow in one line once
the person has chosen.

When GitHub is not connected, or the person skipped the servers, there was no search, so nothing
says whether the project already keeps a standard: ask the same question with no option marked
recommended, saying that a project whose other repositories already share a standard should name
it, since answering "Here" for such a repository starts a second, separate one. Before the
question, say in two lines that the GitHub server is not connected, that onboarding goes on
without the search for the project's standard, the repository's visibility and default branch,
and the search for the repositories that use it, and that the README's "MCP servers" section in
the plugin and Claude Code's guide, https://code.claude.com/docs/en/mcp, say how to connect it.

For another repository, clone it into the state's `clone directory:`, as
`<clone directory>/<owner>__<repo>`. That directory outlives this session, and every working tree
of the repository finds the same clone there, as it reads the same `git config`; when the
`clone directory note:` line is not `none`, say it in the message that reports the clone, the
`/add-dir` it names included, since without it each of step 5's writes there asks.
The clone stays read-only until step 5. Before cloning, run
`bash "${CLAUDE_PLUGIN_ROOT}/scripts/review_dir.sh" <the directory holding .review/>`, so git
ignores it, then `git clone --template= <origin's form of the URL> <clone path>`, each with
nothing in front of it, so either can be allowed once for every run; `--template=` copies no hooks.
Claude Code's sandbox refuses a clone's hooks and its `.git/config`, so there the clone, like step
5's `git config`, runs outside the sandbox on the person's yes. The `standard setting clone:` line
names the clone `git config lasp-dev.standard` points at: one whose origin is the repository
the person named is used as it stands, from any working tree; one `missing` is said, and cloned
afresh. A `clone:` line for that repository that the setting does not name is said, with its
branch and the commits its origin does not hold, and the person asked: **Use it as it stands**
(Recommended: an earlier onboarding's unpushed work may be there, and step 5 shows each file
against what the clone holds), **Clone afresh**, which removes the existing clone, those commits
included, and clones again, or **Let's discuss**. A `clone:` line for that repository reading
`not a git checkout` is a leftover directory a clone cannot go into: say so and ask **Remove it and
clone afresh** (Recommended: git cannot read anything in it) or **Let's discuss**. A clone that
fails is said and the person answers again. Its `standards/` is the standard: with `profiles/`, a standard for several
repositories, which this one joins; with none at all, a new one this run starts; with
`standards/` and no `profiles/`, a standard for its own repository alone, which cannot take
another until its settings move into `profiles/<its repo>.yaml`: say so and ask: **Move its
settings** (Recommended when the person named this repository as the project's standard: it is
the one change that lets the standard cover a second repository without changing what its own
repository loads), after which step 5 also writes, in the clone, `profiles/<its repo>.yaml` with
the repository settings its `profile.yaml` holds, leaving only `PROJECT_KEYS` there, and tags
every entry of its ledger and every decision `repos: [<its repo>]`, since untagged they would
apply to every repository the standard covers once it has `profiles/`; **Name another
repository**; or **Let's discuss**. A
`profiles/<this repo>.yaml` already there means this repository is covered: say so; step 5 then
offers to update that file, and steps 3 and 4 compare with that file, not the default profile:
read `<clone>/standards/profiles/<this repo>.yaml`, show its value beside each of the survey's rows,
and take a row as differing only where that file sets a value the repository's own files
contradict. A value the file leaves out that the repository states is read from the repository,
and is not asked about. A pointer whose standard does not cover this repository yet, written
by hand or by an earlier run whose pull request has not merged, would stop the survey: run it with
`--standard none`, which reads the repository as though `git config lasp-dev.standard` were
`none`, so it compares with the default profile, and say so; every later survey run in this
onboarding, step 3's and step 4's, carries the same option. Until step
5 writes the pointer, the survey script itself compares with the default profile, not the standard
joined, so its `match` column is set aside where the standard covers this repository, as above;
step 3 says so once, and step 5 compares the drop-in's project settings with the standard's.

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/survey.py" --repo <top>`, the state's `top:` line, adding `--ref origin/<default branch>` when
the checkout is on another branch, so the survey reads what the repository has committed on its
default branch. With GitHub connected and the servers not skipped, the default branch is the one
step 2's `search_repositories` call names, made now, before the survey: the checkout's `origin/HEAD` can name a branch the
repository long since left. It reads committed files only, and names on its `not committed` row a local file,
such as an uncommitted `CLAUDE.md`, that it left alone. It prints one row per fact family: where the
repository keeps it, a short value, the value the plugin reads today with the file it comes from,
and whether the two agree (`docs/contracts.md`, "The survey", in the plugin). When it exits 1, say
its message and stop: nothing else here works without it.

## 2. Read the servers, when connected

Only reads, and only names, counts and categories: never a ticket's description or comments,
never a page's body. Find each server's tools with `ToolSearch`; a server that is not connected,
or a call that fails, is a line in step 3's "could not detect" group, and the rest goes on. Say
so once per server, at the first step that needs it, as
`${CLAUDE_PLUGIN_ROOT}/skills/work/servers.md` sets out, naming what is lost: for GitHub, step 1's
search for the project's standard, the repository's visibility and default branch and the search
for the repositories that use it; for Jira, the statuses and fields; for Confluence, the space keys.

- **GitHub**, as `${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md` sets out: whether the
  repository is private and its default branch, from the `search_repositories` call step 1 made
  before the survey (`repo:<owner>/<repo>`, its `private` and `default_branch` fields), not made
  again. The default branch it names replaces the survey's,
  which is only the checkout's local `origin/HEAD` and can be stale; when the two differ, say so.
  Then the repositories that use this one, when the survey's `package` row names a package
  (`<module>` is its name with `-` as `_`). Run each of these `search_code` queries once, never
  joined with `OR`, which GitHub's code search undercounts, paging each (`perPage` 100) until its
  `total_count` is read:
  1. `"from <module>" org:<owner> language:python`
  2. `"import <module>" org:<owner> language:python`
  3. `"<package>" org:<owner> filename:pyproject.toml`
  4. `"<package>" org:<owner> filename:requirements.txt`

  Every repository the hits name, apart from this one, is a candidate, and its evidence is the
  number of distinct files the four queries' pages hold for it. Code search also matches inside
  longer names (`rad` finds `radiometer_cal`), so read each
  candidate's hit files with `get_file_contents`, in turn, until one names the module or package
  whole: an import of `<module>` followed by `.`, a space or the line's end, or a dependency entry
  of `<package>` (`-` and `_` alike) followed by no further letter, digit, `-` or `_`. A candidate
  none of whose files does is dropped, and the table names it with the longer name it matched.
  Code search allows few calls a minute, so beside step 1's search for the standard, run no other
  query. Otherwise a candidate is never dropped: when a query's pages hold fewer hits than its
  `total_count`, or a call is refused, the counts are lower bounds and the list may be
  incomplete, which the table says. Write them to `.review/onboard/downstream.json` with
  the Write tool, as a JSON list of `{"repo": "<name>", "evidence": <count>}`, the name bare with no owner, most first, or skip
  the file when none is found.
- **Jira**, for the project the survey's `ticket project` row names, or the profile's
  `ticket.project` when the history names none:
  - the statuses, sampled: `jira_search` with `project = <key> ORDER BY updated DESC`, `fields`
    `status`, `limit` 50, each distinct status with its category (To Do, In Progress, Done);
  - the fields a skill uses by role, found by `jira_search_fields`: an epic link and an estimate
    (story points), each with its ID.
- **Confluence**: the space keys of the pages a `confluence_search` for the project key returns,
  `limit` 10. The server lists no spaces on their own, so each hit arrives with an excerpt of its
  page's text: read the title and the excerpt only for a warning, as "Controlled content" says,
  and take nothing from them but the space key. A hit that warns it is controlled is named by its
  title and space, counted, and never followed; the rest of its excerpt is not repeated.

## 3. Present one table

Group the families, in this order:

1. **In the repository**: the survey's rows with a path, `git` or `history`, each with its
   `match`.
2. **Elsewhere**: what only the plugin or a server holds, with where: the standard's file or the default profile the
   survey names, or the server and the call.
3. **Missing**: a family neither holds.
4. **Could not detect**: a server not connected, a call that failed, or a family no tool lists.
   A server's row names its case and the fix, as `servers.md` sets out.

Each row says where the fact would be read from: the repository's file when it holds it, and
otherwise the pointer to where it lives. An `inferred` row holds what implies the plugin's value,
such as a pre-commit file for a `pre-commit run` command, not the value itself. A `differs` row
names both values, which the person decides between, and never which is right. A `(also)` row
is a later source giving the same family, such as CI beside the instruction file the survey read
first. Rows marked `conflict;` mean the repository's own sources disagree: list every source's
command with what its own `match` says against the plugin, and say that onboarding records none of
them until the person says which is the repository's, since a fact kept in two places with two
values has no one answer. A `symlinks not followed` row names committed links the survey could not
follow within the commit, which it did not read and counts as absent. Then a line or two on what
stands out: a family the
repository could hold but does not, such as a pull request template or secret scanning, and a
value the plugin reads that the repository contradicts.

Show the table in the reply, then write it, the survey's printout and the server findings to
`.review/onboard/survey.md`
with the Write tool, as `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`, "Writing a file",
says, replacing any earlier one. Then run the survey again with the same `--ref`, adding
`--profile .review/onboard/profile.yaml`, `--public false` or `--public true` when GitHub said
whether the repository is private, and `--downstream-from .review/onboard/downstream.json` when
step 2 wrote it: it writes the candidate profile, in the plugin's profile format
with every key it cannot fill reading `not yet recorded` and none taken where the repository's
sources disagree, and `profile.sources.json` beside it, saying where each value came from.
Then show its proposals, which a person confirms or trims and never takes as found: the repositories
`downstream` names, with each one's count, and the `depth.light` and `depth.deep` paths, worked
out from the tree by the survey's stated rules (`docs/contracts.md`, "The survey"), so some are
paths no review needs to treat as light or as deep. None of them goes into a drop-in profile until
the person confirms or trims it.

## 4. Ask what only the person can settle

At one point, in one widget, or as few widgets of four as the questions need
(`${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`), each with what bears on it and a
recommendation. A reply typed in chat answers as well, several at once included. When the survey
and the standard leave no question to ask, say so in one line; step 5's question is then the next
one.

Each question opens with what the setting does in the plugin, in plain words rather than its key,
and each option says what choosing it changes. Recording a value writes it into the standard, where
it outranks what the repository's own files state and stops following them, and leaving it
unrecorded keeps the plugin reading it from the repository; so a value the repository states in
one form, which the plugin would read anyway, is shown in the table and not asked about. For a
repository already onboarded, a question whose answer the file holding its settings already
records (its own `standards/profile.yaml`, or, in a standard for several repositories, the
standard's `profile.yaml` for the project's keys, such as the ticket key, `jira` and `internal`,
and its `profiles/<this repo>.yaml` for the rest) is not asked, a proposal included: the table shows that value as settled, with the file, and the person reopens it by
saying so. Of the keys that file records, only one the repository's own files contradict is
asked, so a rerun on a repository whose settings are current asks nothing it settled; a key the
file leaves out is asked as for a new repository.

- **One per command whose sources disagree** (a `conflict;` row), and one per command whose
  repository value differs from a value the plugin reads from a profile or a standard, never from
  one it would detect: the options are each source's command as written,
  the plugin's, and leaving it unrecorded. Open with what the command is for, in plain words
  rather than its key: the test command is what a build runs to check the change passes, and the
  coverage command is what a build's test review runs to find changed lines no test executes.
  Each option then says what choosing it changes in practice, such as which tests a run includes
  and what that costs, and which file states it. Recommend the one the repository's agent
  instruction file states when there is one, since that is what agents are told today.
- **A test command no source states**: when the survey's `test command` row reads `none` and no
  profile or standard sets one, ask for it, since otherwise a build runs no tests. Open with what
  the command is for, as above. The options, each saying what it changes:
  - **A command the person types**: a build runs it, from the standard, ahead of any command the
    repository's own files state later.
  - **One read from a file the survey does not read**, such as a Dockerfile or a Makefile, proposed
    only with that file named and its line quoted, and saying that a build runs it on this machine,
    not inside the image or the make target, so it needs what that file would have installed.
  - **Leaving it unrecorded**: a build runs no tests until the repository's own files name a
    command, which the plugin then reads with no new onboarding.

  Either command is written to `answers.json` as `asked`, its gate pattern following from it.
  Recommend recording one when the repository has tests (test files in the tree, or a `pytest
  settings` row other than `none`), naming that evidence, and leaving it unrecorded when it has
  none. A coverage command may be given in the same answer.
- **Downstream**: the repositories that use this one, which `ticket-draft` scopes follow-up work
  in and a build's downstream check runs when a change alters this one's public interface. Keep
  every proposed repository, or name the ones to drop; a repository the search did not find may be
  added by the person. Propose only what the search found: a repository known from anywhere else,
  such as the person's own instructions, is named as one they may add, never recommended, and
  while one is named, `[]` is not recommended: leaving it unrecorded is. Recommend recording none, `[]`, which says nothing uses it, only when all four queries ran
  and their pages were read whole; when the search was skipped, refused or incomplete, or the
  survey names no package, recommend leaving it unrecorded and say why, since `[]` turns the
  downstream check off. Either way, say the search covered only `<owner>`, so a user in another
  organization is one to add by name.
- **For a new standard only, the project's settings**, which the default profile states for no
  project, asked only when step 2 read the tracker's statuses (otherwise say the question was
  skipped, so no workflow is recorded and no skill moves a ticket's status or routes by it, and
  the standard names no internal host of its own, until its `profile.yaml` records them): the tracker's workflow, each
  status with the phase a ticket in it goes to, `ticket-draft`, `implement-change` or `nothing`,
  and, for five of them, the role a generic skill names it by, `filed`, `approved`,
  `implementation`, `finished` and `abandoned`, each on exactly one status, a status the sample
  missed typed in by the person; the statuses at which a pull request may be open, each one of
  them; and the internal domains, the hosts no posted text may name and every transcript is
  scrubbed of, from the Confluence and Jira hosts the servers use. Recommend each from the status
  names and categories. Write the answers to `.review/onboard/project.yaml` with the Write tool,
  as `jira:` (`statuses`, each `{name, next, role}` with the role only where one was given, and
  `pr_statuses`) and `internal:` (`domains`, and `private_repositories: []`), never into
  `answers.json`, whose keys are the survey's. A standard the repository joins already states
  them, and they are not asked.
- **A command the standard's file sets that the repository has no tool for**, such as a lint
  command with no config for its tool, or a test or coverage command where the repository has no
  tests: one question each, saying that a build would run it and fail, with **Clear it**
  (Recommended) or **Keep it**, for a tool the repository is about to add. The gate patterns,
  `lint.regex`, `gates.tests` and `types.regex`, only recognize those runs for the build record
  and make no build ask for one, so they are never asked about: one goes with its cleared
  command, and otherwise stays. A cleared command, and the gate pattern that goes with it, is
  written to `answers.json` as `asked` with the value `''`, which the drop-in carries, so step 5's
  file empties each and its diff shows it.
- **Light and deep paths**: how much review a build gives a change. A change whose every line is
  on a light path, such as a changelog entry, gets the lightest build, one implementation reviewer
  beside one focused reviewer; a change touching a deep path always gets the deepest, planned
  first and reviewed in full; anything else is standard. Keep the proposal, or name the paths to
  drop; a path may be added. Say which proposed paths match no file the plugin's profile names, so
  the person sees what trimming would remove.

From the answers, write `.review/onboard/answers.json` with the Write tool, in the form the
plugin's `docs/contracts.md`, "The survey", gives for `--answers`: a value the person took from
the candidate as `confirmed`, a proposal they trimmed as `confirmed` with what they kept, and a
value they picked between disagreeing sources, added or typed as `asked`, and a key they chose to
leave unrecorded as `asked` with the value `not yet recorded`, which keeps it out of the drop-in so
the default profile's value stands. A question they skip writes nothing for its key. Then run the survey once more with the same options, adding
`--drop-in .review/onboard/profile.dropin.yaml --answers .review/onboard/answers.json`. When it
exits 1, say its message: the answers file names a value the candidate cannot take, and the
question that wrote it is asked again.

## 5. Where each part lives

Show the drop-in profile's values, each with the file it would go to, and, for a standard here,
which is one file, that file whole with its difference from one already there, then ask, as one question,
which of these happens. Recommend writing the standard, with the repository edits for the commands
whose sources disagree, and keeping it in `.review/onboard/` when the person skipped a question
step 4 asked. This question is a gate that holds, as `decision-points.md` allows a skill to name
one: it is asked even when step 4 asked none, the turn ends on it, and none of the writes below
is made before a reply to it. No earlier reply stands in for it, "take the
recommended option for everything" included, since the person has not yet seen the values it
would write. The recommendation says why, in
what the next session changes: what the plugin would read from the standard that it does not read
today, or that nothing changes when nothing would. Both writes can be taken together, named
through "Other".

- **Keep it for a later run**: nothing else is written, and a later run takes it from the files
  this one kept, in `.review/onboard/`.
- **Write the standard**: only what detection cannot
  find, since the standard outranks what is detected and a value written here would stop
  following the repository's own files: the drop-in's value for each key `answers.json` settled
  (a command picked where sources disagree or given where none stated one, the downstream and depth paths kept) and the gate
  patterns the survey derived for it, never a key that reads `not yet recorded`; `public` when
  GitHub said; and, for a new standard, `.review/onboard/project.yaml`'s project settings. For a standard here, all of it
  in `standards/profile.yaml`. For a standard elsewhere, this repository's `standards/profile.yaml`
  as the one line `standard: <owner>/<repo>`, and, in the clone, on a branch
  `onboard/<repo>-YYYY-MM-DD`, `standards/profiles/<this repo>.yaml` with the repository's settings
  and, for a new standard, `standards/profile.yaml` with the project's and `standards/decisions.md`,
  headed and with no decision yet, so the standard loads as one with no rules yet: the settings `profile.py`
  names in `PROJECT_KEYS` go only in the second, the rest only in the first, as
  `docs/standards.md`, "How a setting is found", says; a project setting the drop-in holds that
  differs from the joined standard's is named, and not written. For a standard here, that file
  is the whole write: it stays uncommitted in the working tree, on the branch the checkout is on,
  for the person to commit with their next change; no branch is made and nothing is committed or
  pushed, and the clone's question below is not asked. After step 1's **Move its
  settings**, the clone's branch also carries the move: `standards/profiles/<its repo>.yaml`
  written, its `standards/profile.yaml` trimmed to the project's settings, and a `repos: [<its
  repo>]` line on each of its ledger entries and decisions. Show each file it would write,
  and, when one is there already, the difference from it; write each on a yes to that file, one
  question per file, never one yes for several and never an option offering one. Each question
  says in plain words what the file holds, what writing it changes for the next session, and
  recommends writing it, or not, with why. When the standard is one file, shown in full before
  this step's question, with its difference from the file already there, choosing **Write the
  standard** is its yes, and it is not asked again; otherwise each file is asked as above;
  and,
  for a standard elsewhere, `git config lasp-dev.standard <the clone's path>`, so this
  repository reads the standard from the clone until its pull request merges. Then read them back
  through `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <owner/repo>` and `bash
  "${CLAUDE_PLUGIN_ROOT}/scripts/standard_file.sh" >/dev/null`, and, after a move, the moved
  repository's own read, `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" <its owner/repo>`
  and `bash "${CLAUDE_PLUGIN_ROOT}/scripts/standard_file.sh" >/dev/null` run from the clone's top
  level, which reads its standard as its own, each as `cd <clone> && <the command>`, since neither
  script takes a directory, so the session's own directory stays this repository's, after `bash "${CLAUDE_PLUGIN_ROOT}/scripts/review_dir.sh"
  <clone>`, so the `.review/` that read writes there is never committed to the standard, and `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/rule_lint.py"
  --ledger <clone>/standards/review-rules.md --repo <clone> --checks fields`, which checks each tag
  against `profiles/`. The same `rule_lint.py` runs once before the first write, on the clone as
  it stands, and a message both runs print is the standard's already, said in one line and no
  failure of this write, whatever its exit code. On exit 1 from `profile.py` or
  `standard_file.sh`, or a `rule_lint.py` message the first run did not print, put back
  what each file held before, removing one that was not there, unset that config, and show the
  message. Nothing here is committed.
  In the clone, and only there, ask then: **Commit, push and open its pull request** (Recommended: the standard's
  repository reviews the change). For an empty repository, one where `git -C <clone> for-each-ref
  refs/remotes/origin` prints nothing, since it has no branch, this option is not offered: the first branch pushed to
  an empty repository on GitHub becomes its default branch, unreviewed. Say that a maintainer first
  creates its default branch, as with a README made on GitHub, and recommend **Commit only** until
  then, pushing the branch and opening the pull request as
  `${CLAUDE_PLUGIN_ROOT}/skills/using-github/SKILL.md` sets out, its description saying what each
  changed key does and why, and ending with the attribution line and AI assistance level that
  `${CLAUDE_PLUGIN_ROOT}/skills/pr-create/SKILL.md`'s "The AI Assistance Level" sets; **Commit only**, naming the
  clone's path and branch; **Stop**, the clone's path named; or **Let's discuss**. Whichever, the clone and the
  config stay, and the last line says to run `git config --unset lasp-dev.standard` once the
  pull request merges, after which the pointer reads the standard's default branch.
- **Make the repository's own files agree**: for a command whose sources disagree, show the edit
  that makes each of them state the value the person picked, and make each edit on a yes to that
  edit; a command already in the agent instruction file is replaced only on its own yes. Nothing
  goes into a file `profile.sources.json` marks as loaded every session (`files.<path>.loads` is
  `always`) unless every session needs it. Nothing is committed.
- **Let's discuss**.

## 6. First rules, on a yes

Only where this repository has no ledger of its own, `standards/review-rules.md`, on its default
branch; where it does, say in one line that `/lasp-dev:revise` changes the rules, and go on to
step 7. For a standard elsewhere, the rules are drafted from this repository's threads for that
standard, as `first-rules.md`'s "A standard elsewhere" says, and only once the standard covers
this repository, its `profiles/<this repo>.yaml` in the clone or the fetched standard, since each
candidate's `repos:` tag is linted against it; until then, say so, name step 5's write as what
covers it, and go on to step 7. Drafting them reads every merged pull request in the range, then
runs about one agent per merged pull request with review threads, up to thirty, so it starts only
on the person's yes to this question.

First count, before anything is spent, as `first-rules.md`'s "The sample" counts. When
`.review/harvest/records/` already holds records, count those: the pull requests whose records
name a thread, review body or conversation comment a person wrote, the author's own included. Otherwise, with GitHub connected, one `search_pull_requests` with `repo:<owner>/<repo>
is:pr is:merged`, `perPage` 100: the merged pull requests, saying that which of them have review
threads is known only after the harvest. When it finds more than 100, a second search adds
`merged:>=<the date six months before today>`: the window's count. With GitHub not connected or
the search failing, say so as `servers.md` sets out, the count being what is lost, as no GitHub
server, above, when step 2 already said it.

Then say what a yes spends, from the counts, for the whole history and, when it was counted, the
window:

- **Reads**: about four GitHub reads per merged pull request in the range; none when records
  stand in. The four are `pr-reader`'s `get`, reviews, review comments and conversation comments,
  more where a list pages: the basis for the count, not text for the person.
- **Agents**: one thread analyst per pull request with review threads a person wrote, up to
  thirty, then a rule probe for each example a candidate cites, often two per candidate.
- **Cost**: the reads at about 4 cents per merged pull request, plus at most about 15 cents per
  analyst, its share of the probes included, which at the cap of thirty is about $4 to $5. Say
  that these rates were measured on one run in November 2026, the agents on Sonnet, and change
  when the agents' model does.

Then ask:

- **Draft the first rules**: read `${CLAUDE_SKILL_DIR}/first-rules.md` and follow it, with any
  Confluence pages or Jira epics the person names in the answer. Recommended when records reach
  the sample's floor, five merged pull requests with review threads a person wrote, or the search
  finds five or more merged pull requests and the window is not recommended. With only the search,
  say that which pull requests have review threads a person wrote, not a bot, is known only once
  they are read, and that drafting stops there, before any analyst runs, when fewer than five do,
  so a yes that finds too few costs the reads stated and no more.
- **Draft from the last six months**, offered when the window was counted: the same, with the
  window's first day as the harvest's first day. Recommended when the window holds thirty or more
  merged pull requests, since the analysts stop at thirty and older history mostly changes which
  thirty run. Say plainly that a window of thirty merged pull requests may yield fewer than thirty
  analysts, since not every one has review threads a person wrote, and that the floor check after
  the reads still stops the draft below five. Say that it can leave out the pull request from before the review bot that the
  sample asks for; the sample report then says so.
- **Not yet**: nothing is spent; rerunning onboard, or `/lasp-dev:onboard rules`, offers it
  again. Recommended below the floor, or below five merged pull requests from
  the search, since the rules would rest on too few pull requests, and when nothing could be counted.
- **Let's discuss**.

A date the person names through "Other" is the harvest's first day, its reads and agents stated
again, and asked again, before it starts.

When the harvest's sample falls short of what `first-rules.md`'s "The sample" requires, say how,
and ask again: **Draft anyway, marked** (each candidate the shortfall affects is marked),
**Stop here** (Recommended), or **Let's discuss**.

## 7. Stop

Say in a line what was written and where, then ask what to do next: **Run
`/lasp-dev:quickstart`**, for this machine's setup (Recommended when a server was not
connected or a check here failed for a reason the setup would explain, naming it), **Stop here**
(Recommended otherwise), or **Let's discuss**. When step 6
drafted rules, the line says a person cuts the candidates in `.review/harvest/` and commits the
ones kept, as the README's "Adopting the standards workflow in a repository" sets out. Nothing is
committed, pushed or posted but the clone's branch and pull request step 5 had a yes for, and
nothing is written to Jira or Confluence.

## Bounds

The survey and its tables in two minutes or less. No server write but step 5's push and pull
request, on their yes. No file but `.review/onboard/`'s `survey.md`, `downstream.json`,
`profile.yaml`, `profile.sources.json`, `answers.json`, `project.yaml` and `profile.dropin.yaml`,
and a clone of the standard's repository under `.review/onboard/clone/` where step 1 places it, read-only until step 5, except
the step 5 writes the person says yes to, each by name, `git config lasp-dev.standard` among
them, and on step
6's yes what `first-rules.md`'s "Writes" names under `.review/harvest/` and `.review/backtest/`. No
ticket is read beyond its status, and no page is fetched, but the pages and epics the person names
at step 6; a Confluence search's excerpts are read only for a warning, and nothing of them is
kept.
