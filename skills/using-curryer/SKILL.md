---
name: using-curryer
description: >
  Who consumes curryer and libera_utils, where a change breaks, and whether code belongs in
  curryer. Applies to any change to a curryer public API, to SPICE, frame, kernel or time code in
  curryer or a repository that depends on it, or to a libera_utils interface.
user-invocable: false
metadata:
  author: lasp-dev
  version: 1.0.6
---

## The constellation

```
curryer ──> libera_utils ──> libera_rad, libera_cam, libera_analysis, libera_cdk
        │                    (libera_rad, libera_cam and libera_analysis also use curryer.compute, thinly)
        └─> CSDS             (a heavy consumer of curryer.correction.*, running in production; only curryer)
```

The lists themselves are `references/downstream.md` section 1's; this picture agrees with them.

D-006 in `<standard>/decisions.md`, `<standard>` being the directory `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/profile.py" --standard`
prints for the checkout the session is in, is the project's decision: curryer is upstream, the upstream change
lands first, and a change to a curryer public API has its consumers mapped before it is written.
It is read only where the checkout's standard holds it: when `--standard` exits 1 ending "the
repository has no standard", or the standard has no D-006, say in one line that the decision was
not read and go on with this file; any other exit 1 is a refusal, shown to the person, and the
decision is not read.
`references/downstream.md` adds curryer's particulars to `downstream`'s method for mapping them. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there.

## The blast radius

A change breaks where its consumers import it:

- `curryer.correction.*` reaches CSDS, which imports across the whole package. CSDS runs in production, so a change there is
  additive or back-compatible, and coordinated with CSDS before it lands.
- `curryer.compute.*`, `curryer.spicierpy` and the top-level exports reach libera_utils, and
  through it libera_utils' consumers.
- A libera_utils public name, `DataProductIdentifier` or `ProcessingStepIdentifier` member,
  product-definition variable or attribute, or CLI option reaches libera_utils' consumers:
  the three algorithm repositories, and libera_cdk, whose infrastructure reads the processing
  step names.

When the break lands depends on the consumer's pin, which
`${CLAUDE_PLUGIN_ROOT}/skills/downstream/consumers.md` section 3 reads, with
`references/downstream.md`'s packages: a
released range breaks at the release that falls inside it; a commit pin or an editable install
breaks when the pin moves, or at once.
As read on 2026-10-03: libera_utils and libera_rad pin `lasp-curryer >= 0.5.2, <1.0`, libera_rad
pins `libera-utils == 5.10.11`, and libera_cam pins both to a commit. Read them again before
relying on them.

The Libera repositories are in building mode until launch and freer to change shape. CSDS is
not.

## Does it belong in curryer or downstream?

**curryer**, when all of these hold: it depends only on SPICE, time, geometry or generic
geospatial physics; it hard-codes no instrument identity, mission frame or kernel name,
calibration parameter or product schema; and it would plausibly serve another mission (TSIS,
CLARREO, CTIM), not only Libera.

**Downstream**, when it encodes instrument constants, frame or kernel names, mission epochs
beyond curryer's registry, product or file-format schemas, or mission business logic.

**Split**, when it is both: a generic core with an extension point in curryer, and the mission
glue downstream (a geolocation routine in curryer that takes frame names; Libera passes its own).
Say in one sentence why the seam earns its place.

`references/capability-map.md` lists what curryer already provides, so downstream code does not
reimplement it, and the SPICE mistakes a review catches.

## Porting: downstream to curryer, then rewire

1. **Audit first.** Look for an open curryer branch or pull request doing the same thing; the
   repositories are developed in parallel.
2. Land the generic core in curryer with its tests, and release it.
3. Rewire the downstream repository to import it from curryer and delete the local copy, with a
   thin shim only while the change moves through.
4. Never patch a downstream repository around a missing upstream fix.
