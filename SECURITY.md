# Security

Report a vulnerability privately, through this repository's **Security** tab ("Report a
vulnerability"), not in a public issue. Say what is affected (a skill, agent, hook or script), how
to reproduce it, and what it exposes or allows.

Kinds of report that matter most here:

- a way past a gate: a push, a post, a commit or a Jira or Confluence write that happens without
  the person's yes, or past `hooks/atlassian-gate.sh`, `hooks/secret-gate.sh` or
  `hooks/controlled-gate.sh` (a call the secret scan or the controlled-file check cannot read
  passing is by design, not a vulnerability: the README's "Permissions" says what each reads);
- a secret, credential or internal link that reaches a pull request, an issue or a page despite the
  redaction in `scripts/transcript_excerpt.py`;
- a script that runs or writes outside the checkout it was given.

The plugin never needs a credential of its own; the GitHub and Atlassian servers it calls use the
person's own tokens, which no file here holds.
