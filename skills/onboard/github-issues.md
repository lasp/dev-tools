# GitHub Issues' settings

Read by onboard's step 4 for a new standard whose tickets are GitHub issues: step 2 found GitHub
Issues, or the person chose it where the evidence was mixed. These questions go in step 4's widget
beside its others, each with what bears on it and a recommendation, and none writes outside
`.review/onboard/`.

- **The workflow, from the labels.** An issue's own state already says most of where it stands:
  an open one is filed, one closed as completed is finished, and one closed as not planned is
  abandoned. A label marks a step between. For each label step 2 found that marks a step of the
  work, rather than a kind of issue such as `bug` or `enhancement`, ask the phase an open issue
  carrying it goes to, `ticket-draft`, `implement-change` or `nothing`, and, where one fits, the
  role a generic skill names it by, `filed`, `approved`, `implementation`, `finished` or
  `abandoned`, each role on at most one label. A role with no fitting label stays unmapped, and
  the issue's state stands for it. A label that sorts issues by kind is not mapped, so an open
  issue carrying only such labels goes to `ticket-draft`, as one with none does. Recommend from
  the label names and their open and closed counts, such as `ready` for approved and `in progress`
  for implementation, both going to `implement-change`. A label the person names that the sample
  missed is checked first, as step 2 says. Nothing creates or renames a label.
- **The labels at which a pull request may be open**, each one of the mapped labels: recommend
  the implementation label when one is mapped, and none otherwise.
- **Where the issues live**, asked only when step 2 proposed another repository: recommend it,
  with the references that name it as the evidence. Otherwise the issues are this repository's and
  nothing is asked.
- **How a branch names its issue**, which `work` and the session-start line read to tell which
  issue a branch is for, from the `issue key` row's pattern:
  - `(issue-)?\d+` or `none`: with no pattern recorded, the plugin reads `59-words`,
    `issue-59-words` and `feature/59-words` as issue 59, so this is not asked, and the table says
    the branches follow the default;
  - `GH-\d+`: ask, recommending recording it, since with none recorded no `GH-<n>` branch names
    its issue;
  - `mixed`: the branch names follow more than one form, so the history leaves the pattern open:
    ask, with each form's count from the row. Offer a pattern covering every form seen, such as
    `(GH-|issue-)?\d+` (Recommended: no branch then goes unread), the most used form's own
    pattern, or **Let's discuss**. Whichever the person picks, the default included, is recorded.

Write the answers to `.review/onboard/project.yaml` with the Write tool, never into
`answers.json`, whose keys are the survey's, and never as `jira:`:

```yaml
issue_tracker:
  kind: github
  statuses:
    - {name: ready, next: implement-change, role: approved}
    - {name: in progress, next: implement-change, role: implementation}
  pr_statuses: [in progress]
internal:
  domains: []
  private_repositories: []
```

Each status is `{name, next, role}`, with the role only where one was given, and `statuses: []`
when no label is mapped. `location: <owner>/<repo>` goes under `kind` only when the issues are
another repository's; with none, the plugin reads the issues as this repository's, and `none` is
never written, since the standard refuses it. A recorded pattern adds `ticket:` with `pattern:`,
in single quotes. `internal.domains` holds the hosts no posted text may name, from the hosts the
servers use, as for Jira, and is `[]` when they name none of the project's own.
