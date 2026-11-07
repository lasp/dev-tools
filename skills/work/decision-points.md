# Decision points

How every skill in this plugin stops for the person, and how it writes a file so that it does
not stop them where it did not mean to. A skill's own text says what it asks at a point and what
it recommends; this file says how the asking is shaped and how a file is written, so each is said
once.

## The shape

1. **Where things stand**, in a line or two before the question: what was done, what was found,
   in the person's terms. No internal names: a script's row or column names, a file's section
   names and step numbers reach the person only when they need them to find something.
2. **What bears on it.** The evidence for each option, short, and the recommendation with its
   reason. Research first; a question whose answer is in the code, the ticket or a file already
   read is not asked. An item that warns it is controlled is the exception: the question names it
   and its warning and describes nothing of it (`skills/writing/references/short.md`, "Controlled
   content").
3. **One `AskUserQuestion` widget**, at most four options so "Other" stays visible. A question
   about what to do next offers:
   - the step the skill would take next, first, its label ending `(Recommended)`;
   - the other steps that make sense from here;
   - a way to stop, saying what is kept;
   - `Let's discuss`, when the choice is consequential or the answer may depend on something the
     person has not been told.

   When more steps make sense than fit beside the stop, the question names the rest, and the
   person picks one through "Other". A question that asks for an answer rather than a next step,
   such as an open question or a thread's disposition, offers the answers, the recommended one
   first, and needs no stop of its own. A point with no recommendation says why in the question,
   and marks none.
4. **One widget per point.** Questions that arise at the same point go in one widget rather than
   one after another; past four, in as few widgets of four as they need. A yes that would follow
   straight after another yes is asked with it: as a second question in the widget, or as one
   option that names both actions, such as "Commit and push".

## Writing a file

A file whose content the skill composes or copies, such as a ticket's text, a context page, a
plan or a review, is written with the Write tool, which makes any missing directory, and changed
with Edit; its content never goes through Bash as a heredoc, `echo` or `printf`. That text holds
Jira markup, code, `{{`, `$`, backticks and quotes, which Claude Code cannot read safely inside a
command, so the command goes to the permission rules: a prompt in a person's session, a denial in
the sandbox. The Write tool refuses to overwrite a file this session has not read: to replace
one, remove it first with `rm -f <path>`, a plain command, then write it.

Bash runs scripts and git, and these stay commands: a script's output redirected to a file, such
as `bash standard_file.sh > .review/standard.md.tmp`; `commit`'s message handed to git with `git
commit -F - <<'MSG'`; and `write-plan.md`'s `jq` approval record, which holds only fixed-form
items, tool names and keys.

## What does not change

- **Gates.** Anything hard to undo, a post, a push, a commit, a write to Jira or Confluence or a
  GitHub issue write, waits for a yes to exactly what it does: a request the person typed that
  names it, or an answer to a question or option that names it. A gate may share a widget with
  other questions at the same point; it is never implied by an answer to something else, nor by a
  standing answer that does not name it, such as "take the recommended answer on every
  question", whether it came before the gate was asked or after: show the gate, or show it again,
  and ask it. A yes given in advance that names the gate, such as "commit this to main", is one.
- **The text is shown with the gate.** A gate that posts or writes text, a review, a comment, a
  reply, a pull request body, a Jira description or comment, a Confluence page or section, shows
  that text as it will be sent in the message that asks, never by pointing to "above", an earlier
  turn or a tool's output, which the person does not see. Text up to about a screen is shown
  whole. Longer text is written to a file under `.review/` first and the question names the file
  as a link the person can open, with a line or two inline on what it holds and what changed;
  every text the gate covers is in the message or in a file it names. A gate that approves a
  plan names the file holding the whole plan as a link, written before the question is asked, with
  the plan's summary inline.
- **The person decides.** A recommendation is never taken for them, and nothing proceeds on
  silence. They may skip, repeat or reorder a step, unless a script needs its output or the skill
  names the step as a gate that holds, as `design-doc`'s frame does.
- **The widget is the default, not a requirement.** A reply typed in chat is an answer. Where
  `AskUserQuestion` is not available, ask the same options as a numbered list in prose, the
  recommended one marked, and wait for the reply.
- **A rejected widget** means: ask the same thing in prose. It is not an answer.
- **Free text** in "Other" is the answer; act on it, or ask what it means.
