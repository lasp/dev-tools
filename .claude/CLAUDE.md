# dev-tools: contributor notes

This repository is the `lasp-dev` Claude Code plugin. `.github/skills` and `.github/agents` link its skills and agents for Copilot.

## How a skill behaves

Every skill, agent and hook is held to these; a change that breaks one says why.

- **It works from whatever exists.** Files an earlier skill wrote, such as a context page, a plan
  or a build outcome, add context. Their absence never stops a skill that does not need them, and
  their presence never takes over a request for other work. A skill stops only at the step that
  needs a missing server or file, and says what it skipped; for a server, in the words
  `skills/work/servers.md` sets.
- **It researches before it asks.** A decision put to the person comes with what bears on it, a
  recommendation and the evidence for it; the person decides.
- **The person steers.** At each natural decision point a skill says where things stand and asks
  what the person wants to do: the step it would take next, marked recommended, and the other
  things that make sense from there, stopping included. A sequence is the default route, not a
  track: a step is skipped, repeated or taken out of order when the person says so, unless a
  script needs its output. Gates stay before anything hard to undo: a post, a push, a commit, a
  write to Jira or Confluence. How a decision point is shaped at run time, and how a skill writes a
  file, is `skills/work/decision-points.md`, which every skill that asks the person cites.
- **Exact wording only where a script parses it.** A line a script reads keeps its fixed form,
  named in `docs/contracts.md`; prose a person reads follows `skills/writing/`, not a template.
- **Effort scales with the change.** The plan, the review and the description are sized to what
  changed. The planner and its reviewer look for the smallest change that meets every
  criterion, and a later review round reruns the implementation reviewer and only the focuses that still
  have a blocking finding, and the tests reviewer when a fix changed a test.

## Conventions

- Skills live under `skills/<skill-name>/SKILL.md` and agents under `agents/<agent-name>.md`.
  The repository root is the `lasp-dev` plugin.
- `.github/skills` and `.github/agents` hold symlinks into those directories for Copilot. Add
  one for every new skill (`.github/skills/<name>`) or agent (`.github/agents/<name>.agent.md`).
- The general skills and agents forked from medley56/llm-tooling at the commit in `UPSTREAM`
  (README "Changing the tooling").
- The standards workflow is three skills, `skills/work`, `skills/onboard`, whose last step
  drafts a repository's first rules, and `skills/revise`, whose `correct` mode fixes a misreading between revisions, with `hooks/` and the `standards/`
  corpus, including the one review contract every adopted repository uses,
  `standards/review-contract.md`; the forked `skills/pr-review`, `skills/implement-change` and
  `skills/pr-create` follow the standard where a repository has one. Its skills use the planning, build and review agents rather than copying
  them, and pass them the standard's paths.
- `skills/test-suite-review` judges test changes for any repository, reading the lanes,
  fixtures and mocking libraries from the repository it runs in.
- A page a person reads to learn something, as `architecture-doc` and `process-doc` write, reads
  as `skills/writing/references/page.md` sets; their `revise` modes read a page and choose the
  write as `using-confluence`'s "Revising a page" says.
- `skills/drawio` draws a diagram as draw.io XML for any skill or person, checked by
  `scripts/drawio_check.py`. No tool uploads a diagram's attachment, so a person places a new one
  in the page; a page write keeps an existing one by carrying its macro, as `using-confluence`'s
  "Macros and mentions" says.
- The Atlassian skills are `skills/using-confluence`, `skills/using-jira`, `skills/ticket-draft`,
  `skills/ticket-audit`, `skills/design-doc`, `skills/architecture-doc` and `skills/process-doc`.
  The Atlassian MCP server may run read-write. A skill writes to Jira only through a write plan the person approved, as `using-jira`'s "Writing
  to Jira" and `skills/using-jira/write-plan.md` set out, and hands over what the plan does not
  write to paste: `ticket-draft` at step 8, and `ticket-audit` at Apply. It writes to Confluence
  only at `design-doc`'s publish step and its `revise` mode, and `architecture-doc`'s and
  `process-doc`'s publish steps and `revise` modes, each on the person's yes, as `using-confluence`'s "Writing to Confluence" sets out, and otherwise hands the page over to
  paste. `hooks/atlassian-gate.sh` allows a Jira write from the main session only when the
  approval record the plan writes at the person's yes, `.review/jira-approval.json`, lists that
  tool on that target for this session, and asks before every other Atlassian call that is not a
  read, every Confluence write included.
- A rule's wording lives once, in its ledger entry's `> ` lines, and `hooks/rules.sh` loads the
  rules that apply to the repository into every session; Copilot does not see them. A ledger whose
  wording is still in `.github/instructions/*.instructions.md` links it from each entry until its
  standard moves. Do not add `.claude/rules/` files to scope rules by path: as of Claude Code 2.1.283, an `@`
  import inside a `.claude/rules/*.md` file resolves but its target loads at session start
  regardless of `paths:`, and the scoped file itself later attaches with the raw import line
  unexpanded. Only inline text in a `.claude/rules/` file is scoped, and that would be a
  second copy Copilot cannot read. (Verified from session transcripts.)
- A skill is hidden from the `/` menu (`user-invocable: false`) only when nobody would type it on
  purpose; being called by other skills is not enough, so `commit` and `test-suite-review` stay
  visible.
- Keep YAML frontmatter minimal and portable between GitHub Copilot and Claude Code.
- A `description:` says what only that skill or agent does, the phrases a person types for it,
  and "Not for" where a sibling or a built-in could be taken for it; an agent no person runs opens
  "Run by …; not for direct use". A section only one path reads lives in a file in the skill's
  directory, named on a line that says when to read it (`docs/design.md`).
- Keep templates and support files inside the owning skill directory.
- Claude Code expands `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_SKILL_DIR}` only in a `SKILL.md` or an
  agent's body, not in a file read later. A support file writes `<plugin root>/…`, and every skill
  that reads it says once that the plugin root is `${CLAUDE_PLUGIN_ROOT}`; `check_static.py`'s
  `plugin-vars` check fails a variable anywhere else. A file that writes `<standard>/…` says once
  that `<standard>` is the directory `profile.py --standard` prints, and `plugin-vars` fails one
  that does not. `--standard` prints the repository's standard, the fetched one its pointer names
  or its own `standards/`, and with neither exits 1, its message ending "the repository has no
  standard", so such a file says what it does without one; any other exit 1, such as a standard
  that does not cover the repository or that the schema refuses, is a refusal the file treats as a
  failed read, never as no standard. Outside a covered repository, `using-jira` and
  `using-confluence` say so and ask which project's standard to read, or go on with what the
  person pastes.
- A skill's `name` is its slash command, so renames must update all cross-references.
- Sub-agents must return decisions for the caller to ask; they cannot interactively prompt users.
- Anything that can be done more than one way gets a default and an alternative: the skill names
  its default and takes the person's alternative. GitHub goes through the MCP server by default
  and the `gh` CLI when the person says so; a ticket or page comes from the server by default and
  from pasted text or a file when the person gives it. The gates hold on every path: a yes before
  anything posts, pushes or is written to Jira or Confluence.
- Prose a skill composes for another person on a pull request, or a page `design-doc`,
  `architecture-doc` or `process-doc` publishes, carries an AI assistance level, set by the person; `skills/pr-review/comment-style.md`,
  "AI assistance level", owns the scale and its place, and `scripts/record.py` parses the comment
  attribution line.
- A review thread's disposition is the record's verdict in every skill: agree, disagree or
  discuss, and answer for a question, with move and reopen only on an agreed thread. How a reply
  is read is `pr-review`'s "Whose reply counts", how a decision is posted or kept local is
  `pr-fix`'s "5. Disposition the Threads", and the local review file `scripts/next_phase.py`
  reads is `docs/contracts.md`'s "The local review".
- Updating the plugin is the person's to arrange: the README names the ways and recommends none,
  and no skill, hook, session-start line or quickstart check performs an update or says one is
  due. The plugin carries no `version` and is keyed by commit.
- Each fact has one owning document; the others link to it. `README.md` is the reference: install,
  the servers, models, the layout and the `.review/` map, the skill and agent tables, adoption
  and changing the tooling. `GUIDE.md` says how to use the workflow, `docs/design.md` why it is
  built this way, and `docs/contracts.md` what scripts parse. A skill or agent owns its run-time
  rule, and a document that mentions the rule links there. A change updates the document that
  owns each fact it changes, and this file when a convention here changes. Quickstart cites README headings by name ("Install",
  "MCP servers", "Models", "Your responsibility", "Layout", "How the corpus grows"), quickstart and "MCP servers" cite
  Install's steps by number, and `scripts/check_static.py` parses the `.review/` table by its
  header row, so rename or renumber any of them only with those citations.
- The Python environment is uv's (`pyproject.toml`, `.python-version`; the devcontainer and CI run
  `uv sync`). The dev tools' pins live in `pyproject.toml` only; `uv.lock` is not committed.
- Before a pull request: `uv run python -m unittest discover -s tests`, the four
  `tests/*.sh`, and `uv run python scripts/check_static.py`, so the tests use the project's
  environment outside the devcontainer too; CI also runs codespell, `claude plugin validate .`, and the unit tests and `check_static.py`
  on Python 3.9, the README's floor.
  A change to what a skill, agent or hook does fills the description's `Origin:`, `Sandbox:` and
  `Canary:` lines, as the README's "Changing the tooling" says; a `skill-feedback` issue is where
  a complaint about a skill starts.
- `ROADMAP.md` holds deferred and planned work. An item leaves it when it lands, and a change that
  defers or lands one updates it in the same change.
