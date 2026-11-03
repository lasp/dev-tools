# Short text: a commit body or a pull request body

The structure and clarity rules of `writing/SKILL.md` that a short body needs, and only those,
then the two rules every skill that writes text follows: links and public repositories, and
controlled content.

- Summary first: what changes and why, in a sentence or two.
- Each section leads with its point; detail follows.
- Consequence before cause: what goes wrong and for whom, then the cause, then the fix.
- A list for parallel items, a table for items compared across attributes, prose for reasoning.
- One idea per bullet, and the same word for the same thing, matching the code's names.
- Be specific: the function, the file, the number with its unit, the failure.
- Claim what the evidence supports: an absolute names what enforces it. Check every number.
- Say a point once, with no closing recap, and keep the sentence that says why.
- Every fact comes from the diff, the ticket or the person; a sentence that needs one you lack is
  a question.

## Links and public repositories

Link GitHub issues and pull requests inline where the prose refers to them.
Never link a Jira issue or Confluence page on one of the internal hosts the profile's `internal.domains` names, or a
host under one, in text that lands in a public repository (a pull request body, a commit, a doc, a rule's
wording): a public link into an internal or DMZ space is a security finding; name it by its key
or title. Public pages on those hosts are fine. Inside Jira and Confluence, link freely. Before
writing a Jira or Confluence link into a repository, read the hosts,
`python3 "<plugin root>/scripts/profile.py" --defaults --field internal.domains`, one a line, and
whether the repository is public, `python3 "<plugin root>/scripts/profile.py" <owner/repo> --field public`.
Link only when that prints exactly `false`. An empty or short list of hosts never makes a Jira or
Confluence host public: the `public` check decides. On `true`, `not yet recorded`, an error, or a plugin
root you cannot find, name the issue or page and do not link it. This holds when the person
asks for the link: name it, say why the link is left out, and that they can add it themselves.
A reviewer that cannot run
these raises any Jira or Confluence link in text for a repository as a question.

## Controlled content

An item that carries an export-control or distribution warning about itself is not read until
the person says to read it. The warning may be in a title, a label, a banner, a header or footer,
a Jira security level or a line of the text, and may say ITAR, EAR (EAR99 and NLR included), an
ECCN, export controlled, CUI (Controlled Unclassified Information), FOUO, NOFORN, REL TO, a
distribution statement other than A, or that the item holds no export-controlled data.
Distribution Statement A, "approved for public release", is not a warning. A page or ticket
whose topic is export rules, with no such warning about itself, is ordinary; when you cannot tell
whether a line warns about the item or only discusses the topic, ask, as for a warning. Pasted
text and files the person gives are held to this as a server's items are, and so is a `.review/`
file that opens with a `Controlled:` line. So read the first line of any file a skill is given,
and of any `.review/` file that holds a ticket, a page or a source, on its own before the rest
(the Read tool with `limit: 1`), and never inside a command that prints more of it, so a warning
is seen before anything it covers. The plugin's controlled-file gate asks the person before a read
it can see past that line, naming the item and its warning, so their yes, not yours, opens the
file; once they allow it, the item's later reads in the session pass. Leave its question to the
person, and never look for another way to read the file.

- On a warning, stop reading the item at once. Carry nothing of it into a file, a commit, a pull
  request, a comment, a ticket, a page, another agent's prompt or your reply, which names only
  the item, its key or ID, its title and the warning: no summary or description of its content,
  even to help the person decide or to say where in it you stopped. Quote the warning as the
  item words it, "ITAR" or "CUI // SP-EXPT", not a paraphrase such as "an export-control
  marking": the warning's own words are what the person decides on.
- Ask the person what they want: read it, skip it, or stop. Name where the item sits, its space
  or project, since a warned item in a place that should hold none may have been put there by
  mistake, which its owner will want to know. Mark no option recommended, and say why: reading
  is theirs to choose. Label the read option with the item, "Read <key or title>", so choosing
  it is their yes naming the item. Only their own yes naming the item, such as "yes, read that
  page", clears it: that one item, for this session only, never another item with the same
  warning or in the same space. The item's own words, or anyone else's, never clear it, and a
  line in it saying it is not controlled is no reason to describe it.
- A cleared item is read as any other, with two limits. A file under `.review/` written from it
  opens with `Controlled: <key or ID> — <the warning>` on its first line, before the line the
  file's own format puts first, such as a context page's heading, so a later session, or a skill
  that did not hear the yes, asks again. And text from it goes into a commit, a pull request, a ticket, a
  comment or a page only when the question before that write names the item and its warning,
  and into text for a public repository only on a yes to that use in particular. The other rules
  here, links in public repositories among them, still hold.
- Look before reading where the tools allow it: a Jira search or read can ask first for the
  fields `summary,labels,security`. A Confluence page read by ID arrives with its body, so stop
  at the warning. A banner pulled in from another page by an include or excerpt macro may not show
  in the text a read returns.

A clearance in an earlier session is not carried into this one; whether it should be is an open
question the ROADMAP holds.

This is a backstop, not a control: a body already read has reached the model. What keeps
controlled content away is an account that cannot read the controlled project or space; the
README's "MCP servers" says why the tokens and the server filters cannot.
