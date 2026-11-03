# Prose standards

The word lists are not ban lists. Each entry is usually decoration and occasionally the exact
word. Apply the truth test: does the word carry information a plainer word would lose? If it
does, keep it. The same holds, more loosely, for the phrases and structures further down: they
are almost always filler, and the rare sentence where one is the plain statement of what is
meant keeps it.

## Flagged words with a legitimate use

| Word | The true use | The decoration |
| --- | --- | --- |
| robust | Statistical: robust to outliers, a robust estimator | "a robust pipeline" |
| seamless | Literally no seam: SPK segments that abut with no gap | "seamless integration" |
| harness | A physical harness | "harness the power of" |
| navigate | Spacecraft navigation, a nav solution | "navigate the complexity of" |
| landscape | Terrain | "the current landscape" |
| unpack | A tuple, an archive | "unpack the implications" |
| pivotal | A real pivot: a gimbal axis | "a pivotal moment" |
| underscore | The character `_` | "this underscores the need for" |
| comprehensive | A checkable claim the text then substantiates | "a comprehensive guide" |
| nuanced, intricate | The nuance or the parts are stated next | empty praise |
| leverage | Financial or mechanical leverage | any use meaning "use" |
| key | A dict key, a lookup key, a cryptographic key | "key features" |
| critical | A critical angle, point or path | "critical to success" |
| powerful | Optical power, the power of a statistical test | "a powerful tool" |
| at scale | A stated scale: 10^6 footprints per granule | "works at scale" |
| production-ready | The production system is named, with how long it has run there | a label on untested code |

## Words that are almost always marketing

delve, bolster, foster, shed light on, pave the way, groundbreaking, cutting-edge,
transformative, game-changing, innovative, holistic, testament, realm, utilize, streamline,
empower, elevate, unlock, supercharge, revolutionize, world-class, best-in-class, blazing fast,
move the needle, level up. Each hides what the code does; say what it does instead.

## Phrases that stand in for a point

- "In today's [fast-paced / rapidly evolving] world..."
- "It's important to note that..." / "It's worth noting that..."
- "One of the most [important / significant]..."
- "When it comes to..." / "At its core..." / "At the end of the day..."
- "This is where X comes in" / "Let's break it down"
- "Plays a crucial role in..." / "It cannot be overstated..."
- "...highlighting the need for..." / "...marking a significant shift in..."
- Participle tails that append an unstated benefit: "..., ensuring consistency", "..., making it
  easy to..."
- "Additionally," / "Furthermore," / "Moreover," opening paragraph after paragraph
- "A wide range of..." / "Various..." in place of the actual list
- "In summary," / "Overall," before a restatement

Each announces that something matters instead of showing why. Delete the announcement; if no
reason is left standing, the sentence had nothing in it.

## Structures that usually imitate a point

- "It's not just X, it's Y" / "Not only X, but Y" / "This isn't about X. It's about Y."
- "No X. No Y. Just Z."
- Signposting: "Let's explore", "In this section we will".
- The scene-setting opener and the recap close.
- A list of labeled items that are not parallel, or a paragraph cut into bullets. A list whose
  items really are parallel, each with a label a reader scans for, is structure and stays.

Keep one of these only where it is the plain statement of what is meant, such as a real
contrast between two things the reader might confuse.

## Pitch register

The voice of a launch post. Technical readers discount everything written in it.

- The rhetorical question answered in the next line: "So why does this matter? Because..."
- The reveal: "The result? Zero reloads." / "Enter the InventoryLoader."
- "Here's the thing" / "Spoiler:" / "Imagine..." / "Tired of...?"
- A triad for cadence when the text supports one of the three
- A one-sentence paragraph used as a punchline; exclamation marks

## Overclaiming

A claim stronger than the evidence is a defect in a science pipeline, not a matter of tone. The
words that usually carry it: ensures, guarantees, eliminates, always, never, all, every, fully,
completely, effortlessly, the only. Intensifiers do it quietly: truly, extremely, highly, vital,
essential. "Simply", "just" and "easily" overclaim on the reader's behalf.

"Always" is right when something enforces it, and then the sentence names the enforcer. Without
one, state the mechanism and its scope.

The opposite failure is the stacked hedge, "may potentially help to somewhat reduce": one
qualifier, on the part that is uncertain, with the reason. Where the behavior is known, state it
without "may".

## Worked rewrites

Each rewrite keeps every fact of the original.

**A ticket's The code today that opens with the mechanism** (the ticket behind o/r#42):

> `load_rows` reads a CSV file with `csv.reader`, rejects a duplicate `id` when `strict` is
> True, and returns the rows keyed by their `id` column. A row can have fewer or more fields
> than the header. Today nothing looks at a row's width.

> Nothing in `load_rows` checks whether a row has as many fields as the header, so we cannot
> tell whether files ever arrive with short or long rows. The loader reads the file with
> `csv.reader`, rejects a duplicate `id` when `strict` is True, and keys the rows by their `id`
> column.

The problem and who cannot see it come first; the mechanism is the same three facts, after.

**A Summary line carrying the whole design** (o/r#42):

> Problem: a row can have fewer or more fields than the header, and a row is one parsed record,
> which spans several lines of the file when a quoted field holds a line break. Nothing looked
> at row width, so we could not tell whether or how often that happens; a `TODO` sat at the
> width check.

> Problem: a row can have fewer or more fields than the header, and nothing checked it, so we
> could not tell whether or how often that happens.

The line keeps its claim; the definition of a row and the TODO move to "What changed",
where a reader looking for them will look.

**A README paragraph that sets a scene:**

> In today's world of ever-growing satellite data volumes, keeping processing pipelines reliable
> is more important than ever. This repository provides tools that help.

> `widgets` reads part inventories from CSV files and totals the widgets by part number.

What the repository does, for whom, in the first sentence; the scene added nothing.

**Overclaiming:**

> The new check ensures kernel paths are always valid and completely eliminates path-length
> errors.

> `validate_path_length` raises before a kernel is furnished if its path exceeds SPICE's
> 80-character limit, so an over-long path stops the run at load time instead of failing inside
> `furnsh`. It does not shorten paths.

**Cause first instead of consequence first:**

> `boresight_offset_angles` defaulted `reference_vector` to +X instead of reading
> `INS<id>_FOV_REF_VECTOR`. This PR reads it from the kernel.

> Boresight azimuth offsets were measured from the wrong origin for any instrument whose IK
> declares a reference vector other than +X. Every IK in the repository declares `(1 0 0)`, so
> no current product changes. The cause was that `boresight_offset_angles` defaulted the origin
> to +X. `instrument_fov` now returns the kernel's reference vector and the provider passes it
> through.

**The flagged word that passes:**

> The SPK segments abut exactly at the boundary, so interpolation across it is seamless.

There is literally no seam, and "smooth" would claim a different property. Flagged does not mean
wrong.

## Over-correction

Cutting decoration should leave prose, not a telegram: every sentence the same length, no
connective words, a page that reads like assembly instructions. Keep the sentence that explains
why one fact follows from another, and keep the domain vocabulary, which is precision rather than
decoration.
