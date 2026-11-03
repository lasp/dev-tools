# The plugin's standards

What every project's standard is held to, shipped with the plugin: how every reviewer behaves
(`review-contract.md`), the bar a rule meets (`rule-bar.md`), the thresholds the revision and the
planning skills apply (`dials.md`) and the default profile (`default-profile.yaml`, with
`profile.example.yaml` as its template). A project's own standard holds the rest: its vocabulary,
its decisions, `context/`, `archive/`, each repository's rules and each repository's records. That
standard is the directory `scripts/profile.py --standard` prints, a repository's own `standards/`
or the shared standard its `standard:` pointer names (`docs/standards.md`).

A directory here named for a repository, where one remains, holds that repository's records and
harvest from before its project's standard existed. They move to that standard, and the plugin's
published tree leaves the directory out.

**When a standard and an authoritative source disagree, the source wins;** run
`/lasp-dev:revise correct` to fix the standard. Everything in a standard is a description of
what a team decided, and a description can be out of date. The authoritative sources are the code,
the Confluence pages and Jira issues named in `context/`, and the people who made the decisions.

## What lives here, and what does not

| Here, in the plugin | In the project's standard | In each repository |
| --- | --- | --- |
| `review-contract.md` — how every reviewer behaves, one copy for every repository | `terminology.md` — one vocabulary across the project's repositories | `standards/review-rules.md` — the ledger of rules about that repository's own code, each entry holding its wording as `> ` lines, when the repository keeps its own standard |
| `rule-bar.md` — the gates a rule passes before it is admitted | `decisions.md` — decisions that constrain more than one repository | `standards/decisions.md` — decisions local to it |
| `dials.md` — every threshold the revision applies | `context/` — one entry per Confluence page, Jira epic or PR thread | `standards/profile.yaml` — its settings, or the one-line `standard:` pointer |
| `default-profile.yaml` — how the tools operate, under every repository's settings | `archive/` — why a rule existed, kept after the rule stops existing | `.github/PULL_REQUEST_TEMPLATE.md`, which `/lasp-dev:quickstart` checks against the standard's `templates/<name>/PULL_REQUEST_TEMPLATE.md` |
| — | `<repo>/log/` — each repository's review records, revision reports and corrections (`docs/contracts.md`, "The record") | — |

A rule is loaded on every reviewer run and has to earn that
place, so a rule about one repository's file naming would be dead weight in
another. A term is a few words and the damage from a missing one is a ticket that
says "footprint" where the code says "field of view", so the vocabulary is worth loading
everywhere. Procedure changes should reach every repository at once; rules should not.

## How a repository consumes this

These files are plain markdown and YAML, read, never imported. They ship inside the `lasp-dev`
plugin, which installs once per machine and applies to every repository, and are read at the
commit the plugin was installed from. Three of the plugin's skills (`work`, `onboard`, whose last
step drafts the first rules, and `revise` with its `correct` mode) and its build hooks maintain a
project's standard, and the forked `pr-review`, `implement-change` and `pr-create` follow it. The
repository's top-level `README.md`, "Install", walks through the install.

A project's standard changes through a pull request on its own repository: `revise`, in each of its
modes, runs in the code repository, clones the standard's repository into a temporary directory and
commits there, then asks before pushing the branch and opening its pull request. The revision
archives there the records it rebuilds from each merged pull request's threads. What lives here
changes through a pull request on the plugin and reaches each machine at its next update.

## Profiles

A profile, a repository's settings in its standard (its own `standards/profile.yaml`, or
`profiles/<repo>.yaml` in a standard for several repositories), holds the facts about one
repository that the hooks, scripts and skills
would otherwise hard-code: its ticket key pattern and Jira project, whether it is public, its
pull request template, the repositories a change ripples into, the
test, coverage and lint commands the review wave passes to its reviewers, the patterns that count
a lint, types or tests command as a gate, its GitHub server, how much of the workflow a posted review names, and the paths that set a build's depth.
`scripts/profile.py <owner/repo>` resolves it: the standard's settings, from the repository's own
`standards/profile.yaml` or the standard its `standard:` pointer names (`docs/standards.md`), over
what `survey.py` detects in its checkout, then `default-profile.yaml`, which holds how the tools
operate and nothing a repository states, and it names the files it read, or none
(`docs/contracts.md`, "The profile"). A repository with no standard needs no file: its values are
what is detected and the default profile's.
`profile.example.yaml` is the template, and a value nobody has looked up reads `not yet recorded`.

## Dials

The thresholds the revision and the planning skills apply are in `standards/dials.md`.

## Numbering

`T-nnn` and `D-nnn` numbers are permanent. A retired entry keeps its number and is marked
retired; numbers are never reused. A corrected entry, one the corpus had misread from its source,
keeps its number too. A corrected decision's italic source line records the correction,
`corrected <date>: <what was misread>`; a corrected term's record is its
`<repo>/log/correction-<date>-<id>.yaml`, and its row carries no note. A repository's own
decisions are numbered separately, in its `standards/decisions.md`, and cited with the
repository: `widgets/D-004` in prose, and `D-004@widgets` in a finding key, whose
citation cannot contain a `/`.
