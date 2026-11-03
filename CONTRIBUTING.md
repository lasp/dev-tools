# Contributing

The README's "Changing the tooling" section is the guide: how a skill, agent or hook is changed,
the evidence a change carries (its `Origin:`, `Sandbox:` and `Canary:` lines) and the sandbox that
measures it. `.claude/CLAUDE.md` holds the conventions every skill and agent follows.

- **A complaint about a skill** starts as a `skill-feedback` issue: run
  `/lasp-dev:skill-feedback` in the session where it went wrong, or open one with the
  "Skill feedback" template.
- **Before a pull request**, run the checks CI runs:
  `uv run python -m unittest discover -s tests`, the four `tests/*.sh`, and
  `uv run python scripts/check_static.py`.
- **Security issues** go through `SECURITY.md`, not a public issue.
