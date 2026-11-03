---
name: commit
description: >
  Decides what in the working tree belongs in a commit, writes the message as Conventional
  Commits or in the style the person or repository asks for, and commits locally; never pushes. Use when asked to "commit this", "commit my
  changes" or "write a commit message".
metadata:
  author: llm-tooling
  version: 6.2.0
---

# Commit

Decide what belongs in the commit, write the message, commit. Invoking this skill is the authorization to commit — do not ask again unless a rule below says to; a question it asks follows `${CLAUDE_PLUGIN_ROOT}/skills/work/decision-points.md`. The plugin root is `${CLAUDE_PLUGIN_ROOT}`: a path written `<plugin root>/…` in a file this skill reads starts there. A request for only a message ("write a commit message") gets the message, shown and not committed.

## What Goes In

Survey the whole tree: `git status -sb`, `git diff`, `git diff --cached`, `git ls-files --others --exclude-standard`. Staging is a signal about intent, not the definition of the commit. If the tree is clean, say so and stop.

**Start from what this session did.** The files you created or edited for the user's request are the commit; anything else is a question. With no session context, describe the groupings the tree suggests and let the user pick.

Never commit, even when staged:

- Anything under `.review/`, the plugin's working state, and review or planning artifacts
  elsewhere: `pr-*-review.md`, fix plans, scratch notes.
- Credentials and private configuration — `.env`, keys, tokens.
- Build output, caches, editor and OS files.

Say which paths you excluded and why.

Ask when the answer is not obvious: unrelated units of work in one tree, a file that could be artifact or deliverable, a staged subset that overlaps unstaged edits to the same files. On a split, commit each group through the steps below, in the order the person gives, and report each SHA.

Stage by naming paths — never `git add -A`, `git add .`, or a bare `git add -u`. A deletion stages with `git add <deleted-path>`, or `git rm <path>` if the file is still on disk; a rename stages as both paths. Check `git diff --cached --stat` against your list before writing the message.

## Obvious Breakage

Commit what you believe works, without auditing: no test runs, no reading files this session never touched. One `grep` for a name you renamed or deleted is in scope; a wider review is not.

Stop before committing if you already know the commit breaks something — a reference you saw go stale, a caller you noticed. Name what breaks and where, then let the user fix it first, approve the breakage, or split the commit. **Committing known breakage takes explicit approval**; silence or an ambiguous answer means no. A suspicion is not enough to hold a commit — mention it and commit.

## When Not to Commit

Draft the message and hand it over instead of committing when the repository's loaded instructions (`CLAUDE.md` and what it imports, `AGENTS.md`) forbid an agent to commit even when asked (a rule against unsolicited commits only is met by this invocation), when a merge, rebase, cherry-pick, or bisect is in progress, or when HEAD is detached. Say which condition applies and what they can run themselves. On the default branch, ask first and offer to branch — unless the person or the repository's instructions say it commits to its default branch, in which case commit and say you did.

## Message

**Write [Conventional Commits](https://www.conventionalcommits.org/) by default**, and any
other style the person or the repository asks for instead. A requested style wins wherever it is
written: this session, `CLAUDE.local.md`, the repository's `CLAUDE.md` and what it imports,
`AGENTS.md`, `CONTRIBUTING.md`, or a git page in its developer docs, and the person's
`~/.claude/CLAUDE.md`. Where two disagree, the session wins, then `CLAUDE.local.md`, then the
repository's files, then `~/.claude/CLAUDE.md`. A format a file writes down counts as asked for,
even one it calls suggested or preferred; a file that says there is no standard and shows no
format asks for nothing. A requested style is followed as written, such as a ticket key prefix
(`PROJ-42: load an inventory from CSV`) or plain imperative subjects. Recent
history, `git log --oneline -20` on the default branch, is a habit, not a request: on its own it
does not replace the default, though a scope the history uses for the same area is a good scope
to reuse. A request to keep the history consistent, or to match the existing commits, is a
request for the style that history shows; a history too mixed to read gets the default.
Say which style you followed and where it was asked for, or that it is the default.

The default subject is `<type>(<scope>): <description>`: a type of `feat`, `fix`, `docs`,
`refactor`, `test`, `build`, `ci`, `perf`, `style` or `chore`; a scope only when one area of
the code clearly owns the change; a description in the imperative, lower case, with no closing
period. A breaking change adds `!` after the type or scope and a `BREAKING CHANGE:` footer
saying what breaks.

```
<subject in the chosen style, imperative, under 72 characters>

<body>
```

A suffix the host adds at merge, such as GitHub's `(#NN)`, is not part of the subject you
write. End with the `Co-Authored-By` trailer this session's attribution supplies (D-013), unless
the person or the repository's instructions say to add no attribution; add none it does not supply.

Body bullets wrap at 72 characters, one concrete change each, most significant first, worded as `${CLAUDE_SKILL_DIR}/../writing/references/short.md` sets out, and says nothing the diff does not show. Skip whitespace and import churn. A small change needs no body. Before a Jira or Confluence link goes in the message, the person's included, read `short.md`'s "Links and public repositories" and follow it.

A message that carries text from a cleared controlled item is shown, naming the item and its warning, and committed only on the person's yes (`short.md`'s "Controlled content").

Describe what the diff shows. Give a reason only when the person stated one: this session, the approved plan file or the ticket's context page; never reconstruct intent from the code.

## Commit

Show the message, then:

```bash
git commit -F - <<'MSG'
<message>
MSG
```

Use `-F`, never `-m`.

Report the short SHA and branch, and end by saying that nothing was pushed. **Never push**, and never amend unless asked for an amend by name.

If the commit fails, the run ends there. Report what happened, leave the message on screen, and tell the user to re-run `/lasp-dev:commit` once they have looked at the state. Never retry with `--no-verify` — the hook is the repo objecting. If a hook reformatted files, show what it rewrote.
