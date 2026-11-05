# Agent guidance

Habits coding agents fall into here and should not repeat, each in a reviewer's words. Every build
and review loads this file with the rules. An entry guides whoever writes the code, and a review
that meets the habit again raises a suggestion keyed `agent/A-nnn`. What belongs here, and when an entry retires, is the plugin's
`docs/standards.md`, "Agent guidance and data conventions"; `scripts/entries_lint.py` checks the
form. Copy this file into the standard's folder as `agent-guidance.md` and add entries below.

```markdown
### A-001 · <what to do, in a few words>

_<YYYY-MM admitted> · seen <YYYY-MM last seen>_
habit: <what agents do here that a reviewer had to undo>
> <what to do instead: the instruction an agent reads>
said: "<the reviewer's words, at most 40>" — <login>, <comment URL>
```
