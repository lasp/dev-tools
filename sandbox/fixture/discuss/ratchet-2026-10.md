window: 2026-10-01..2026-10-31

# Standards revision · widgets · 2026-10

## Head
standard: this repository's standards/
records: 1 harvested · 0 missing · 0 baseline
guidance: 6 comments · 5 items · 4 general, 1 pr-specific · general by kind: rule 2, data-convention 1, process 1

## Proposals
### Rules
- [ ] R-004 · A reader fails loudly on input it cannot use · single statement · pr-0007 · C1
  said: "In general, a reader should fail loudly on input it cannot use" — alice, https://github.com/example/widgets/pull/7#discussion_r101
  Recommended: accept — a person's general statement, changed as asked
  Mark: yes, but word it "raises on input it cannot use", not "fails loudly"; nobody can test "loudly" — erin
### Data conventions
- [ ] F-001 · change · a count of -1 is also the fill value in the parts CSV, not only the inventory CSV · owner: the warehouse service's export specification · pr-0007
  Recommended: escalate: the warehouse service's export specification, section 3
  entry:
    ### F-001 · A count of -1 means not counted

    _2026-10_
    > In an inventory or parts CSV, a count of -1 is the fill value for a part not counted that day. Never sum it or treat it as zero.
    source: the warehouse service's export specification, section 3
  Mark: makes sense to me, the parts export works the same way — bob
- [ ] F-002 · A column's name carries its units · source: carol · pr-0007 · C2
  said: "Units go in the column name so nobody has to guess them." — carol, https://github.com/example/widgets/pull/7#discussion_r104
  Recommended: accept
  Mark:
### Decisions
- [ ] D-001 · A pull request description opens with its ticket key · process · pr-0007, pr-0009 · C3
  said: "put the ticket key on the first line of the description, the release notes are built from it." — dana, https://github.com/example/widgets/pull/7#pullrequestreview-105
  Recommended: accept
  Mark: dana: yes. erin: the release-notes job is being retired next month, so this may not matter by then.
