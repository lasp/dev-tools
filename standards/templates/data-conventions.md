# Data conventions

Facts about this project's inputs and products that code must respect, each with the document or
the person that owns it: fill values, frames, units, attribute and filename conventions. Every
build and review loads this file with the rules. A convention changes only through its owner. What belongs here is the plugin's
`docs/standards.md`, "Agent guidance and data conventions"; the plugin's `scripts/entries_lint.py`
checks the form. Copy this file into the standard's folder as `data-conventions.md` and add entries below.

```markdown
### F-001 · <the fact, in a few words>

_<YYYY-MM admitted>_
> <the fact, as code must respect it>
source: <the document, its version and section; or the data's owner>
said: "<a person's words, at most 40, when one stated it>" — <login>, <comment URL>
```
