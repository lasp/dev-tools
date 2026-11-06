# Contributing

The README's "Changing the tooling" section is the guide: how a skill, agent or hook is changed,
the evidence a change carries (its `Origin:`, `Sandbox:` and `Canary:` lines) and the sandbox that
measures it. `.claude/CLAUDE.md` holds the conventions every skill and agent follows.

- **A complaint about a skill** starts as a `skill-feedback` issue: run
  `/lasp-dev:skill-feedback` in the session where it went wrong, or open one with the
  "Skill feedback" template.
- **Before a pull request**, run the checks CI runs:
  `uv run python -m unittest discover -s tests`, the five `tests/*.sh`, and
  `uv run python scripts/check_static.py`.
- **Security issues** go through `SECURITY.md`, not a public issue.

## Adding a skill

A skill here works on any project: what differs between teams is read from the repository or its
standard at run time, never written into the skill. Each step names where its rule lives.

1. **Write `skills/<name>/SKILL.md`**, with its templates and support files in the same directory.
   The `name` is the slash command, so pick it once; a rename updates every reference.
   Frontmatter keys, the `description:` rules and when a skill is hidden from the `/` menu are in
   `.claude/CLAUDE.md` "Conventions".
2. **Hold it to "How a skill behaves"** in `.claude/CLAUDE.md`: it works from whatever exists,
   researches before it asks, lets the person steer at each decision point
   (`skills/work/decision-points.md` sets the shape), and stops before anything hard to undo.
3. **Name no project.** No team, repository, Jira project or domain goes into the skill; read it
   from the profile or the standard. `scripts/check_static.py`'s coupling check fails a new match
   of the names listed in `scripts/coupling.json`; it does not catch any other name.
4. **Use `${CLAUDE_PLUGIN_ROOT}` only in `SKILL.md`.** A support file writes `<plugin root>/…` and
   the skill says once what that is; the same holds for `<standard>/…`. `.claude/CLAUDE.md`
   "Conventions" has the rule and `check_static.py`'s `plugin-vars` check enforces it.
5. **Link it for Copilot**: a symlink `.github/skills/<name>` to `../../skills/<name>` (an agent:
   `.github/agents/<name>.agent.md`). `check_static.py`'s `copilot-links` check fails a missing or
   misdirected link.
6. **Add its row** to the skills table in README "What is included", and to the one-line list
   above it; a skill marked `user-invocable: false` gets a `hidden` row and no line.
   `check_static.py`'s `readme-skills` check fails a missing row or line and a wrong Started value.
7. **Run the checks** in "Before a pull request" above, one after another.
8. **Try it in the sandbox** before review: a scenario in `sandbox/`, run beside the current
   plugin ([`sandbox/README.md`](sandbox/README.md)). A skill a person types needs a
   `trigger-<name>` scenario in `sandbox/triggers/scenarios.yaml`, a request in plain words, and
   its id in `sandbox/triggers/coverage.yaml`, or `TriggerPack` in `tests/test_sandbox.py` fails;
   a skill with `user-invocable: false` or `disable-model-invocation: true` needs none.
9. **Fill the pull request's `Origin:`, `Sandbox:` and `Canary:` lines**, as README "Changing the
   tooling" says, and set the skill's `metadata.version`.

A file one skill writes and another reads is a contract, with a version and a test that pins it:
README "Changing the tooling" says how a change to one is made.
