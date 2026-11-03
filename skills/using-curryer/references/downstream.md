# Mapping the consumers of a change

Read-only. For a curryer symbol or module, or a libera_utils one, find who imports it, which of
their tests exercise it, and how soon a change would reach them.

## 1. The consumers

Each upstream's consumers have one home. A repository with a profile keeps them in the profile's
`downstream`, which the code reads (`python3 "<plugin root>/scripts/profile.py"
<owner/repo> --field downstream`, run in that repository's checkout); curryer has no profile, so
its list is this table's. Everything else that names them points here or agrees.

| Upstream | Consumers |
| --- | --- |
| curryer | libera_utils, libera_rad, libera_cam, libera_analysis, CSDS |
| libera_utils | its profile's `downstream`, in its standard's `profiles/libera_utils.yaml` |

CSDS consumes only curryer. libera_cdk's lambda subpackage imports libera_utils. A repository
whose profile reads `not yet recorded` and that has no row here has no recorded consumers: say
so, never guess.

Read each consumer cloned beside this repository (`$(git rev-parse --show-toplevel)/../<repo>`).
A consumer not cloned there is named as unread, never guessed. CSDS is not on GitHub; read it
only from a clone.

## 2. The use sites

Before the change is written, search each consumer for the symbol: the import forms, attribute
access, and string references such as a config key or a CLI option. libera_rad, libera_cam and
libera_analysis mostly use curryer through libera_utils, so follow a curryer change one step
through the libera_utils functions they call. Report each hit as `repo/path:line` with the
enclosing function or class, and the test modules that cover it. Over a written diff,
`/lasp-dev:downstream check` does this and runs the consumers' lanes.

## 3. The pin

Read each consumer's actual dependency, from its `pyproject.toml` and from the environment it
runs in (`pip show lasp-curryer`, `pip show libera-utils`), never from memory:

- **A released range** (`lasp-curryer >= 0.5.2, <1.0`): the break lands at the first release
  inside the range, with no change on the consumer's side.
- **An exact pin** (`libera-utils == 5.10.11`): the break lands when the consumer bumps.
- **A commit pin** (`@ git+https://...@<sha>`): the break lands when the pin moves.
- **An editable or branch install:** the break is immediate.

libera_analysis has no top-level pin; each package under `src/python/` declares its own.
libera_cdk's top-level `libera_utils = "*"` defers to the pin in `subpackages/lambda/pyproject.toml`;
read that one.

## 4. CSDS

A hit in CSDS on `curryer.correction.*` is production-sensitive: say so first, and propose an
additive or back-compatible change.

## 5. The verdict

Per consumer: breaking or not, and when, from the pin, as `downstream check` step 7 words it.
Then the order the changes land in, upstream first, and the consumer tests that must pass. When the change looks generic enough to
belong in curryer, or mission-specific enough to belong downstream, say so, by the test in
`../SKILL.md`.

GitHub reads, such as an open curryer pull request in step 1 of the porting loop, go through the
server `skills/using-github/SKILL.md` picks for the repository's owner.
