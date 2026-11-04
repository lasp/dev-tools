# Mapping the consumers of a change

Read-only. For a public name of this repository, find who imports it, which of their tests
exercise it, and how soon a change would reach them. `check` follows these steps over a written
diff, and its step 2 resolves a repository's list for the other skills.

## 1. The consumers

A repository's consumers are its profile's `downstream`, which the code reads
(`python3 "<plugin root>/scripts/profile.py" <owner/repo> --field downstream`, run in that
repository's checkout). Where it reads
`not yet recorded`, the repository has no recorded consumers: say so, never guess. `onboard`
proposes the list from a code search, for the person to trim.

Read each consumer cloned beside this repository (`$(git rev-parse --show-toplevel)/../<repo>`).
A consumer not cloned there is named as unread, never guessed.

## 2. The use sites

Before the change is written, search each consumer for the name: the import forms, attribute
access, and string references such as a config key or a CLI option. Report each hit as
`repo/path:line` with the enclosing function or class, and the test modules that cover it.

## 3. The pin

Read each consumer's actual dependency on this repository, from its dependency files
(`pyproject.toml`, `requirements*.txt`, `package.json`, `Cargo.toml` and the like, in each
package where it declares its own) and from the environment it runs in (`pip show <package>` or
the ecosystem's equivalent), never from memory:

- **A released range** (`>= 0.5.2, <1.0`): the break lands at the first release inside the
  range, with no change on the consumer's side.
- **An exact pin** (`== 5.10.11`): the break lands when the consumer bumps.
- **A commit pin** (`@ git+https://...@<sha>`): the break lands when the pin moves.
- **An editable or branch install:** the break is immediate.

## 4. The verdict

Per consumer: breaking or not, and when, from the pin, as `downstream check` step 7 words it.
Then the order the changes land in, upstream first, and the consumer tests that must pass.
