# Agent guidance

### A-001 · No compatibility shims before the code has users

_2026-10 · seen 2026-10_
habit: keeps the old name working beside a renamed function, with an alias or a deprecation warning
> Rename outright and update the callers. Nothing outside this repository calls widgets yet, so an alias for the old name is dead code.
said: "nobody calls the old name; drop the alias" — a-reviewer, https://example.com/widgets/pull/12#discussion_r1
