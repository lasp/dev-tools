# Mapping the consumers of a curryer or libera_utils change

How to map consumers is `<plugin root>/skills/downstream/consumers.md`; this file adds what is
particular to curryer and libera_utils.

## 1. The consumers

libera_utils keeps its consumers in its profile's `downstream`, in its standard's
`profiles/libera_utils.yaml`. curryer has no profile, so its list is this table's.

| Upstream | Consumers |
| --- | --- |
| curryer | libera_utils, libera_rad, libera_cam, libera_analysis, CSDS |

CSDS consumes only curryer. libera_cdk's lambda subpackage imports libera_utils. CSDS is not on
GitHub; read it only from a clone.

## 2. The use sites

libera_rad, libera_cam and libera_analysis mostly use curryer through libera_utils, so follow a
curryer change one step through the libera_utils functions they call. When this repository is
curryer, over a written diff, `downstream check` step 4 does this by launching one `ticket-investigator` per consumer, in one
message, fresh: its goal "find what calls the libera_utils functions that call these names", the
surface lines as its claims, and no synonyms.

## 3. The pin

The packages are `lasp-curryer` and `libera-utils`. libera_analysis has no top-level pin; each
package under `src/python/` declares its own. libera_cdk's top-level `libera_utils = "*"` defers
to the pin in `subpackages/lambda/pyproject.toml`; read that one.

## 4. CSDS

A hit in CSDS on `curryer.correction.*` is production-sensitive: say so first, and propose an
additive or back-compatible change.

## 5. The verdict

When the change looks generic enough to belong in curryer, or mission-specific enough to belong
downstream, say so, by the test in `../SKILL.md`.

GitHub reads, such as an open curryer pull request in step 1 of the porting loop, go through the
server `skills/using-github/SKILL.md` picks for the repository's owner.
