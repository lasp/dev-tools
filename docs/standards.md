# Where a standard lives

The plugin is a drill: tools that work on any project, with a default bit fitted. A project's
repositories hold the bits that fit their screws, and onboarding is how they tell the plugin. So
the plugin holds the tools and their defaults and nothing about any project. The test for any file
in the plugin: would it change if a different project used the plugin? If so, it belongs in the
project's standard.

ROADMAP's "Neutral examples in generic skills" and "Libera content in the review contract" track
what the plugin still carries of one project; "Status" below names what is built.

## What the plugin holds

The tools (skills, agents, hooks, scripts), the review contract every reviewer follows, the bar a
rule passes, and the defaults: how the tools behave where a standard states nothing, and the
default thresholds. A default never describes a project.

## A standard

A standard is one folder, `standards/`, with the same files whatever it covers:

| File | Holds |
|---|---|
| `review-rules.md` | The rules, each with its wording, tier, status, evidence and scope; held candidates below `## Candidates below the criteria` |
| `decisions.md` | The design decisions the code follows |
| `terminology.md` | The vocabulary, when the project keeps one |
| `profile.yaml` | The settings: whatever detection cannot find, and any threshold set differently from the plugin's default |
| `already-checked-by-tools.md` | Asks a configured linter or hook already enforces, so no rule repeats them |
| `templates/<name>/` | The pull request templates a repository's `template` setting names |
| `tracker.md`, `wiki.md` | The project's Jira and Confluence facts the skills use: field IDs, issue types, the ticket format and template, spaces and page IDs |
| `context/` | Pointers to the pages, epics and threads a reader needs, never copies |
| `archive/` | Why a rule or decision changed or left |
| `log/<repo>/` | The revision's records, by repository |

Any of the rules and the decisions makes a standard. A repository with no standard still gets every
skill, on the review contract and what is detected.

A rule's wording lives once, in the ledger. The plugin's session-start hook loads the rules that
apply to the repository into every session, so a session that is not building or reviewing follows
them too; a session without the plugin, and GitHub Copilot, see none. A repository's
`.github/instructions/` keeps what is not a rule: its layout, its commands, its restrictions.

The standard is the folder as checked out, committed or not; uncommitted files are one person's
trial, and a review says so.

### A standard for one repository

The usual case. The standard is the repository's own `standards/`, and nothing in it names another
repository.

### A standard for several repositories

A project whose code spans several repositories keeps one standard for all of them, in one
repository the project chooses, often a private one. That standard adds:

- **A settings file per repository it covers**, `profiles/<repo>.yaml`, holding that repository's
  own settings where detection cannot find them, such as its consumers or its deep paths. The files
  present are the repositories covered.
- **A tag on what applies to only some of them.** A rule or decision carries `repos: [<repo>, ...]`
  when it applies only there; one with no tag applies to every repository covered. A rule's `scope:`
  still narrows it to paths within a repository. A tag naming a repository with no profile file
  fails the lint.

Each repository covered holds one file, `standards/profile.yaml`, with one line naming where its
standard is: `standard: <owner>/<repo>`. That file holds nothing else. A repository whose pointer
names a standard that has no profile file for it is refused.

A change to any rule, decision, term or setting, for one repository or for all, is one pull request
on the standard's repository. The plugin fetches the standard's latest commit with the person's own
git credentials into a cache in the checkout's git directory: at a skill's step, never inside a
hook, which reads the cache as it stands. Nothing is copied into the repositories covered.

When the standard cannot be fetched, the step that needs it stops and says why. A person may choose
to go on with the review contract and what is detected alone, and the review's `standards:` line
then says the standard was not read. An outside contributor to a public repository whose standard
is private is in that position; a posted review on a public repository quotes a rule's wording
rather than linking to the private standard.

A person trying out changes to a standard before it is merged points the plugin at a local checkout
of the standard's repository; the review's `standards:` line marks it, as it marks uncommitted
files.

## How a setting is found

Each setting has one kind. A **project setting** (the ticket key and tracker project, the tracker's
workflow and roles, the internal domains, the attribution wordings, posted text, the identifier
classes) is the same for every repository a standard covers and sits only in `profile.yaml`. A
**repository setting** (the test, coverage and lint commands, the gate patterns, the consumers, the
depth paths, whether it is public) differs between repositories and sits, in a standard for several,
only in `profiles/<repo>.yaml`. A setting in the wrong file is refused. In a standard for one
repository, both kinds sit in `profile.yaml`.

For the repository being worked in, each setting comes from the first of these that gives it:

1. the standard;
2. what the plugin detects in the checkout: the ticket key its history uses, its test and lint
   commands, its pull request template;
3. the plugin's default;
4. otherwise nobody has said: the step that needs the value asks, and onboarding writes the answer
   into the standard.

What a standard states wins over what is detected; detection fills only what the standard leaves
out.

## Onboarding

Onboarding runs in one repository at a time and asks one question before anything else:

> Where do this repository's rules live?
> - Here, in this repository (recommended)
> - In another repository: name it

Naming another repository whose standard does not exist yet starts one there. Then onboarding
surveys the repository, reads the servers, and asks only what detection and the standard do not
already answer: the tracker's workflow roles and the internal domain for a new standard, this
repository's consumers and deep paths for any. It writes the answers to the standard; for a
repository whose standard is elsewhere, it writes the repository's one-line `profile.yaml` and the
standard's `profiles/<repo>.yaml`, the only time both are written. Its last step drafts first rules
from this repository's merged review threads, dropping any the standard already has and, for a standard
elsewhere, tagging every candidate `repos: [<this repository>]`, since its evidence is this
repository's alone. Nothing is written outside `.review/` or committed
without a yes to that write.

## The revision

`revise` proposes rule changes from the evidence of merged pull requests. For a standard covering
several repositories, it counts each rule's findings in every repository the rule reaches, so the
whole project shapes whether a rule stays. It archives every covered repository's records, but
reads only the threads of the repository it runs in, against that repository's code, so new rules
come from that repository alone; ROADMAP.md tracks reading the others'. For a
standard elsewhere it writes into a clone of the standard's repository, and its accepted changes
are one pull request there; for a repository's own standard, they are one pull request in it.

## Decision and rule numbers

A standard numbers its rules `R-nnn` and its decisions `D-nnn`, one series each, whatever it covers.
A rule or decision that moves into a standard from another numbering takes the next free number,
and `archive/` records the old number beside the new.

## Evidence for the revision

Each rule cites the pull requests it fired on, `<repo>#<n>`, beside the ledger, and every count is
derived from the distinct citations, so a harvest run twice counts nothing twice and no reviewer is
named. This replaces the stored review records.

## Worked example: Libera

Libera's standard lives in a private repository of its own, covering libera_utils, libera_rad,
libera_cam and an infrastructure repository, each with a file in `profiles/`. Each of those
repositories holds only `standards/profile.yaml` with `standard: <owner>/<standard repository>`.
libera_utils' rules arrive tagged `repos: [libera_utils]`, since they were written for its code,
and are widened one at a time where the team wants them everywhere; the infrastructure
repository's AWS rules carry a `repos:` tag naming it alone. libera_utils' own decisions take the numbers after the shared ones, D-014
onward. The Jira workflow, the internal domain and the vocabulary are stated once. A library the
project uses, owned elsewhere, keeps its own standard in its own `standards/`.

## Status

- Built: a standard committed or not (#162); decisions with no ledger as a standard (#163); a
  repository's own `profile.yaml` read by `profile.py` (#173); the `standard:` pointer, with a
  standard for several repositories read from `profile.yaml` and `profiles/<repo>.yaml`, a local
  checkout for a trial, and going on without an unreachable standard on the person's choice;
  `repos:` tags, loaded, linted and counted per repository; a rule's wording in its ledger entry,
  loaded into every session by `hooks/rules.sh`; the revision reading and writing the standard
  where it lives, its records under `log/<repo>/`; onboarding asking where the rules live and
  writing the standard or the pointer; and `profile.py --standard`, printing the standard's
  directory. The plugin's team layer is gone: no repository's settings come from the plugin.
- Next: see ROADMAP.
