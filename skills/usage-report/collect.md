# Collecting the reports

`/lasp-dev:usage-report collect` is the maintainer's side: it merges the reports people sent, the
issues titled `usage-report: …` on the plugin's repository and any report files given, into one
table. A report is found by that title, never by the `usage-report` label, which GitHub drops when
the sender has no push access. It reads GitHub and the files, writes only inside a run directory
of its own under the temporary directory, and posts nothing. `<plugin root>` is the plugin root `SKILL.md` names.

After `collect`, `since YYYY-MM-DD` reads only the issues created on or after that date; every
other argument is the path of a report file, a report as `usage-report file` writes it.

## 1. The run directory

```bash
mktemp -d "${TMPDIR:-/tmp}/usage-report.XXXXXX"
```

Write the path it prints in full wherever `<run>` stands below.

## 2. The issues

The plugin's repository is the `homepage` in `<plugin root>/.claude-plugin/plugin.json`,
`https://github.com/<owner>/<repo>`. Resolve the GitHub read tools as
`<plugin root>/skills/using-github/SKILL.md` says; collecting writes nothing to GitHub, so no
write tool is resolved.

`list_issues` on `<owner>/<repo>` with `orderBy: CREATED_AT`, `direction: DESC`, `fields:
["number", "title", "user", "created_at"]`, `perPage: 100` and no `state` or `labels`, so closed
and unlabeled issues count too, paging with `after` until none is left, 3 pages are read, or, with
`since`, an issue created before that date. Of the issues whose title begins `usage-report:`, keep
the 5 newest. A body is typically about 20 KB, 60 KB at most, and passes through the conversation
twice, read and then written, so 5 is what one run reads; past it, say how many reports were left
out, by their numbers, that `collect since <date>` narrows the run to newer ones, and that
`collect with gh` reads up to 50.

For each issue kept, newest first: `issue_read` with method `get`, then write its `body` to
`<run>/issue-<number>.md` with the Write tool, exactly as it came: no character changed, added or
dropped. A slip is not repaired by hand: the digest in the body catches it at step 4, and the
issue is named there as refused. Claude Code may ask the person before each write, the run
directory being outside the working directory; before the first read, say so, and that
`collect with gh` writes the bodies without those questions.

On `gh`, when the person has said so, the bodies never pass through the conversation, so the 50
newest are kept, `since` applied as above:

```bash
gh issue list --repo <owner>/<repo> --search 'in:title "usage-report:" sort:created-desc' --state all --limit 300 --json number,title,author,createdAt --jq '[.[] | select(.title | startswith("usage-report:"))]'
gh issue view <number> --repo <owner>/<repo> --json body --jq .body > <run>/issue-<number>.md
```

A `plugin.json` with no GitHub `homepage`, no GitHub server, or a call that fails, is said as
`<plugin root>/skills/work/servers.md` sets out, the issues being what is lost: with report files
given, the run goes on with them alone; with none, it stops and offers `gh`.

## 3. The report files

Each path given must exist (`test -f <path>`); a missing one is named, and the run goes on without
it. The files are read where they are, never copied. A file carries no sender, so ask in one
question, naming each file, who sent it: their GitHub login, so a report they also filed as an
issue is found as a duplicate, or any name, the same one for each of a person's files. There is no
recommendation, since only the person knows; the answer is typed.

## 4. Merge

```bash
python3 "<plugin root>/scripts/usage_merge.py" --out <run>/merged.json --report <login> <run>/issue-<number>.md --report <sender> <path>
```

with one `--report` per issue, its author's login from step 2, and one per file, its sender from
step 3. The logins and paths are only arguments: the merged result holds the count of reports and
of distinct senders, never who they are.

Exit 1 writes nothing and prints one line per refused report, naming its file, then a count. Then:

- a report refused on its own (not a report, a digest that does not match, another schema, a
  field not in the report's shape): leave it out;
- `the same report as`: leave out the file the line opens with, and keep the one it names;
- `by the same author as`: two reports of one sender cover some of the same days. Ask which to
  keep: the one whose window ends later is recommended, since a sender who reports days again most
  likely meant the later report to stand; the other, both left out and `Let's discuss` are the
  other options.

Run the merge again without what was left out, until it exits 0 or no report is left; with none
left, say so and stop.

## 5. The table

One message:

1. **What was read**: the issues read, of how many listed, and the files; then each report left
   out, by issue number or path, with the reason as the script gave it.
2. **The merged table**: what step 4 printed, in a fenced `text` block, line for line: no
   heading, table or summary in its place, since the maintainer reads these numbers as the script
   wrote them.
3. **The whole result**: `<run>/merged.json` as a link. It keeps what the table leaves out: each
   report's medians beside its run count, since medians from different reports cannot be
   combined into one, the questions by header, the transitions, scripts, hooks and denials, and
   the notes.

Nothing is asked; collecting ends here.
