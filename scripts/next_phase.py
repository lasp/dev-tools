#!/usr/bin/env python3
"""Say which phase `work` runs next, from the local facts and, when there is one, the pull request.

Reads `hooks/where.sh --fields` (--fields) and, when given, `pr-reader`'s `state` block (--state):
`record.py --state`'s printout under a `## pr-NNNN — state` heading, or `pull request: none`, which
means the branch never had a pull request in any state; and, when given, the pull request's local
review, `.review/pr-<n>-review-submission.md` (--local-review), whose `Head: <sha>` and `Posting:
undecided | declined | posted <url>` lines say whether `pr-review` reviewed the current head here
and what the person chose to do with it. Prints `phase: <skill, or nothing>`,
`argument: <ticket, pull request, or empty>`, `why: <the row>`, `lock: <the skill a live
.review/lock names, or none; a lock untouched for four hours is stale and none>`, then the three lines `work` says. The lock line names a skill only when the
phase is implement-change or pr-fix, the two that take the lock; any other phase runs regardless
of it. The first row that matches decides:

| Row | Phase |
| --- | --- |
| reopened: on the ticket's branch, or a branch with no ticket, its reopened file names a thread, or a `session-<pr>-<n>` reopen decided in a session on this pull request, the plan has no `## Revision` section, its redesign, for it, or one with no `Approved by:` line in its section, or the redesign's build has not passed: no outcome naming every reopened thread on its `Reopened:` lines, or a dirty tree | implement-change |
| reopened-body: the redesign's build passed and the ticket's pull request is open | pr-create, to put the `Reopened:` lines in its description |
| pr-closed: this part is merged or closed, and the stack's merged parts claim every criterion | nothing: the ticket is done (the pr-closed row's why) |
| open-part: this part is merged or closed, and another part of the stack is open | nothing here: `work` takes up that pull request |
| next-part: this part is merged or closed, and the plan has a part no pull request carries yet | implement-change, for the next part |
| unclaimed: every part is merged and a criterion is claimed by none | nothing |
| pr-closed: the pull request is merged or closed | nothing: a merged one is harvested at the monthly revision |
| review-unposted: no findings review names the current head, and the local review of it is still `Posting: undecided` | pr-review, to ask whether to post it |
| pr-review: no findings review names the current head, and no local review of it reads `Posting: declined`, unless `--me` is the pull request's author and a findings review names an earlier head, or a thread someone else opened, a person's or a bot's, has its answer: the author answered that review, and the threads decide, except while a built reopen's thread awaits its fixed reply, when the author reviews the new design too; `--reviewed-this-loop` on a non-draft skips to reviewers-first | pr-review |
| reviewers-first: `--reviewed-this-loop`, and the pull request is not a draft | nothing: reviewers answer first |
| walk: a thread whose verdict is unanswered or unparsed (a reply neither its words nor pr-reader's judgment reads, on a finding or a person's thread), or contested, or a discuss with a reply after it | pr-fix, walking them |
| fix: a thread agreed with 0 replies after, whose text after the verdict names no commit and no follow-up and carries no response in a form `docs/contracts.md`'s "The agreed reply" names, and whose judged reply does not say the change was made | pr-fix |
| follow-up: a thread agreed in a follow-up, with 0 replies after and no such response | pr-fix, for the follow-up reply |
| mark-ready: a draft, every thread answered | nothing: mark it ready for review; a fix taken as made from a judged reply is named, to confirm |
| answered: every thread answered | nothing: the merge is a person's; discuss threads, and a fix taken as made from a judged reply, are named |
| elsewhere: the ticket's context page names other branches, not this one | nothing: switch to its branch |
| unfiled: no key, and the fields' `slug=` names a ticket `ticket-draft` drafted that is not filed | nothing: file its `.jira.txt`, on a GitHub tracker its `.issue.md`, or have `ticket-draft <slug>` file it or take its key |
| ticket-draft: no context page, the ticket in a status whose `next` is ticket-draft, or unknown, or no key; or an open GitHub issue with no mapped label | ticket-draft |
| ticket-to-do: no context page, the ticket in a status whose `next` is implement-change (`--ticket-status`, or an open GitHub issue's mapped label) and no pull request | implement-change |
| ticket-closed: no context page, the ticket in a status whose `next` is nothing, or a closed GitHub issue, and no pull request | nothing |
| plan: a context page and no plan file, or one with no `Approved by:` line, a draft | implement-change, at its plan review |
| build: an approved plan and no outcome for this branch | implement-change, resuming |
| diff-gate: an outcome and a dirty tree | implement-change, at its diff gate |
| build-stopped: an outcome other than `Build: passed`, no pull request | nothing: retry, open anyway, or discuss |
| pr-create: an outcome, no pull request | pr-create |

`--me` is the login of the person running `work`; the state block's `author:` line is checked against it, and without it the pr-review row is the one a reviewer gets. A pull request's rows decide before the local ones; with `--pr`, the pull request must be the
fields' ticket's, `where.sh --fields --ticket <its key>`. While this part's pull request is open,
a row that waits on other people (reviewers-first, mark-ready, answered) becomes next-part when
the plan has a part no pull request carries yet, since parts are built while earlier ones are in
review. A ticket in several pull requests passes `--stack`, a file with one line per pull
request, `#<n> <open|merged|closed> <branch> <claimed criteria, comma-separated>`, and
`--criteria`, the ticket's Acceptance Criteria: the first line `work` says lists the stack, the
fields' `part=` (`k of n`) gives the plan's part count, and the ticket is done only when every
criterion is claimed by a merged pull request. A ticket with no context page here and a status in the
`issue_tracker.pr_statuses` of the repository's standard, or the default profile, needs the state
block, since its pull request may exist elsewhere. A missing, unreadable or contradictory input
exits 1 with the reason, as do statuses (the profile's `issue_tracker`) that cannot be read when the
status is needed. Where no workflow is recorded, every status routes to ticket-draft, as with no
status read, and the reason names the status and that no workflow is recorded.

On a GitHub tracker the ticket is an issue, its key the number, which the first line writes `#<n>`.
Its status is `--issue-state open|closed` and a `--label` for each of its labels: a closed issue is
ticket-closed, an open one with no label the profile's `issue_tracker.statuses` maps is ticket-draft,
and one with a mapped label goes to that label's `next`; an issue with two mapped labels exits 1, as
do `--ticket-status` on a GitHub tracker, `--issue-state` on any other, and `--label` without
`--issue-state`. A label the profile does not map is not a status and is passed over.
Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCAL_FIELDS = ("ticket", "branch", "context", "plan", "base", "outcome", "outcome_reopened", "build_branch", "dirty", "lock", "part", "reopened", "slug", "elsewhere")
# The phases that take .review/lock.
LOCKING = ("implement-change", "pr-fix")
# An Agree whose text after the word names the commit that made the change, or a later change: a
# sha of letters and digits anywhere, or any sha after "fixed in", as pr-fix's reply writes it.
COMMIT = re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b|(?i:\bfixed in [0-9a-f]{7,40}\b)")
FOLLOW_UP = re.compile(r"\bfollow[- ]?up\b|\blater pull request\b", re.I)
# An Agree whose reply carries the response to a thread answered without a commit, as pr-fix's one
# reply writes it and docs/contracts.md "The agreed reply" names it.
REPLIED = re.compile(r"(?:reply only|follow-up in \S+|moved to \S+): +\S", re.I)


# A column separator: record.py prints a `|` inside a column as `\|`, and a column, such as the
# one after the verdict, may be empty.
ROW = re.compile(r" \|(?: |$)")
VERDICTS = ("unanswered", "unparsed", "agree", "disagree", "discuss", "answered", "contested", "none")


class Refused(Exception):
    """An input this script does not read."""


def workflow() -> tuple[str, dict[str, str], tuple[str, ...]] | None:
    """The tracker's kind, `jira` or `github`; its statuses, Jira statuses or GitHub labels,
    lowercased, each with where a ticket with no context page here goes; and the statuses at which
    its pull request may exist with no local page, which work reads first; from the repository's
    standard over the default profile, whose refusal is this script's. None when no workflow is
    recorded."""
    spec = importlib.util.spec_from_file_location("profile", ROOT / "scripts" / "profile.py")
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    try:
        tracker = profile.defaults(ROOT)["issue_tracker"]
    except (profile.ProfileError, OSError) as e:
        raise Refused(f"the tracker's statuses could not be read: {e}") from e
    if tracker == profile.NOT_RECORDED:
        return None
    return tracker["kind"], {s["name"].lower(): s["next"] for s in tracker["statuses"]}, tuple(s.lower() for s in tracker["pr_statuses"])


def shown(ticket: str) -> str:
    """The ticket as people see it: a GitHub issue's number as `#<n>`, a Jira key as it is."""
    return f"#{ticket}" if ticket.isdigit() else ticket


def read_local_review(text: str) -> dict | None:
    """A local review's head and the person's posting choice: `undecided`, `declined` or `posted`.
    None for a file `pr-review` wrote before it recorded the choice, with a `Head:` line and no
    `Posting:` line, which routes as no local review. Raises Refused for a file with no `Head:`
    line, or a `Posting:` line holding another value."""
    head = re.search(r"^Head: ([0-9a-f]{7,40})\s*$", text, re.M)
    if not head:
        raise Refused("the local review has no 'Head: <sha>' line")
    posting = re.search(r"^Posting: *(\S*)", text, re.M)
    if not posting:
        return None
    if posting.group(1) not in ("undecided", "declined", "posted"):
        raise Refused("the local review's Posting: line is not 'undecided', 'declined' or 'posted <url>'")
    return {"head": head.group(1), "posting": posting.group(1)}


def same(a: str, b: str) -> bool:
    """Two shas, either abbreviated, name one commit."""
    return a.startswith(b) or b.startswith(a)


def read_fields(text: str) -> dict:
    fields = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k.strip()] = v.strip()
    missing = [k for k in LOCAL_FIELDS if k not in fields]
    if missing:
        raise Refused(f"the fields have no {', '.join(missing)}")
    if fields["part"] and not re.fullmatch(r"\d+ of \d+", fields["part"]):
        raise Refused(f"the fields' part is {fields['part']!r}, not 'k of n'")
    if fields["slug"] and (fields["ticket"] or fields["context"]):
        raise Refused(f"the fields' slug {fields['slug']!r} comes with a ticket or a context page")
    return fields


def read_state(text: str) -> dict:
    """The state block: its pull request number, head, draft, state, author, ticket, findings reviews and rows."""
    if re.search(r"^pull request: none\s*$", text, re.M):
        return {"open": False, "none": True}
    number = re.search(r"^## pr-0*(\d+) — state", text, re.M)
    head = re.search(r"^head: ([0-9a-f]{7,40})\s*$", text, re.M)
    draft = re.search(r"^draft: (true|false)\s*$", text, re.M)
    state = re.search(r"^state: (open|merged|closed)\s*$", text, re.M)
    author = re.search(r"^author: (\S+)\s*$", text, re.M)
    if not (number and head and draft and state and author):
        raise Refused("the state block has no '## pr-NNNN — state' heading, head:, draft:, state: or author: line")
    if not re.search(r"^contract: 6\s*$", text, re.M):
        raise Refused("the state block is not contract 6")
    # The first ticket key on the body's Ticket: line, as record.py reads it, a link included: a
    # Jira key, or a GitHub issue's `#<n>`, read as its number.
    line = re.search(r"^ticket: Ticket:(.*)$", text, re.M)
    key = re.search(r"\b([A-Z][A-Z0-9_]*-\d+)\b|(?<![\w&])#(\d+)\b", line.group(1)) if line else None
    ticket = (key.group(1) or key.group(2)) if key else ""
    reviewed = re.findall(r"^findings review: \S+ reviewed: ([0-9a-f]{7,40})", text, re.M)
    rows = []
    table = text.split("\nid | ", 1)
    if len(table) == 2:
        for line in table[1].splitlines()[1:]:
            # pr-reader adds this line after the table when record.py refused its judgments.
            if not line.strip() or line.startswith("judgments refused: "):
                continue
            cells = [c.replace("\\|", "|") for c in ROW.split(line)]
            if (
                len(cells) != 11
                or cells[5] not in VERDICTS
                or cells[6] not in ("yes", "no")
                or not cells[7].isdigit()
                or not re.match(r"no$|yes, |unclear: ", cells[10])
            ):
                raise Refused(f"a state row this script does not read: {line[:80]!r}")
            # A judged reply that says the change was made counts as one naming its commit.
            done = bool(re.match(r"yes, [^:,]+, done:", cells[10]))
            # A thread that is not a finding has its resolved state, not a severity, and its opener.
            by = cells[1] if cells[2] in ("true", "false") else ""
            rows.append({"id": cells[0], "by": by, "verdict": cells[5], "contested": cells[6], "after": int(cells[7]), "text": cells[9], "done": done})
    return {
        "open": state.group(1) == "open",
        "none": False,
        "number": number.group(1),
        "head": head.group(1),
        "draft": draft.group(1) == "true",
        "state": state.group(1),
        "author": author.group(1),
        "ticket": ticket,
        "reviewed": reviewed,
        "rows": rows,
    }


def read_stack(text: str) -> list[dict]:
    stack = []
    for line in text.splitlines():
        m = re.match(r"#(\d+)\s+(open|merged|closed)\s+(\S+)\s*(.*)$", line.strip())
        if not m:
            if line.strip():
                raise Refused(f"a stack line this script does not read: {line.strip()!r}")
            continue
        stack.append({"number": m.group(1), "state": m.group(2), "branch": m.group(3), "claims": {c.strip() for c in m.group(4).split(",") if c.strip()}})
    return stack


def claimed(stack: list[dict], *states: str) -> set[str]:
    """The criteria the stack's pull requests in these states claim."""
    return set().union(*(s["claims"] for s in stack if s["state"] in states))


def row(phase: str, argument: str, why: str, say: str) -> dict:
    return {"phase": phase, "argument": argument, "why": why, "say": say}


def issue_row(ticket: str, state: str, labels: list[str], statuses: dict[str, str], pr_statuses: tuple[str, ...], pr: dict | None) -> dict:
    """The row for a GitHub issue with no context page here, from its state and the labels the
    profile maps: a closed issue is past the build, an open one with no mapped label is filed, and
    one with a mapped label goes where that label says. Two mapped labels are refused."""
    n = shown(ticket)
    if state == "closed":
        return row("nothing", ticket, "ticket-closed", f"{n} is closed")
    mapped = [label for label in labels if label.strip().lower() in statuses]
    if len(mapped) > 1:
        raise Refused(f"{n} carries {', '.join(mapped)}, {len(mapped)} of the labels the profile's issue_tracker maps; it takes at most one")
    if not mapped:
        return row("ticket-draft", ticket, "ticket-draft", f"no context page; {n} is open with no status label")
    label = mapped[0].strip()
    if label.lower() in pr_statuses and pr is None:
        raise Refused(f"{n} is labeled {label}: pass the state block of its pull request, or pull request: none")
    phase = statuses[label.lower()]
    if phase == "implement-change":
        return row("implement-change", ticket, "ticket-to-do", f"{n} is labeled {label}, with no context page here")
    if phase == "nothing":
        return row("nothing", ticket, "ticket-closed", f"{n} is labeled {label}")
    return row("ticket-draft", ticket, "ticket-draft", f"no context page; {n} is labeled {label}")


def decide(
    fields: dict, pr: dict | None, ticket_status: str, reviewed_this_loop: bool, pr_given: str,
    stack: list[dict] | None = None, criteria: list[str] | None = None,
    local_review: dict | None = None, me: str = "", issue_state: str = "", labels: list[str] | None = None,
) -> dict:
    """The row that matches, as phase, argument and why."""
    ticket = fields["ticket"]
    given_stack = stack is not None
    stack = stack or []
    criteria = criteria or []
    has_pr = pr is not None and not pr["none"]
    if pr_given and not has_pr:
        raise Refused(f"--pr {pr_given} needs that pull request's state block")
    if has_pr and pr_given and pr["ticket"] != ticket:
        if pr["ticket"]:
            raise Refused(f"the fields are {shown(ticket) or 'no ticket'}'s, but #{pr['number']} is {shown(pr['ticket'])}'s: pass where.sh --fields --ticket {pr['ticket']}")
        # A pull request that names no ticket: this working tree's ticket facts, its stack among
        # them, are not its.
        fields = dict(fields, ticket="", reopened="", part="", elsewhere="")
        ticket, given_stack, stack, criteria = "", False, [], []
    if given_stack != bool(fields["part"]):
        raise Refused("a ticket in parts, the fields' part=, needs --stack, and --stack needs part=")
    own = next((s for s in stack if s["branch"] == fields["branch"]), None)
    if own and not has_pr:
        raise Refused(f"the stack names #{own['number']} for {fields['branch']}, but the state block has no pull request")
    parts = int(fields["part"].split(" of ")[1]) if fields["part"] else 0
    built = [s for s in stack if s["state"] != "closed"]
    unclaimed = [c for c in criteria if c not in claimed(stack, "open", "merged")]
    left = f"; {', '.join(unclaimed)} claimed by no open or merged part" if unclaimed else ""
    next_part = f"{parts - len(built)} of the plan's {parts} parts without an open or merged pull request{left}" if len(built) < parts else ""

    # A reopen is built and put in the pull request's description before its threads are worked.
    reopened = fields["reopened"].split()
    if has_pr:
        # A thread is one pull request's: another part's reopen is not this one's. A reopen decided
        # in a session, `session-<pr>-<n>`, has no thread and names the pull request it was decided on.
        reopened = [t for t in reopened if t in {r["id"] for r in pr["rows"]} or re.fullmatch(rf"session-{pr['number']}-\d+", t)]
    elif stack:
        # Before this part has a pull request, a session reopen decided on another part's is that part's.
        others = {s["number"] for s in stack}
        reopened = [t for t in reopened if not (m := re.fullmatch(r"session-(\d+)-\d+", t)) or m.group(1) not in others]
    if reopened and not fields["elsewhere"] and (not has_pr or pr["open"]):
        plan = Path(fields["plan"])
        text = plan.read_text() if plan.is_file() else ""
        sections = {t: re.search(rf"^## Revision \d+ — {re.escape(t)}(?=\s|$)(.*?)(?=^## |\Z)", text, re.M | re.S) for t in reopened}
        unrevised = [t for t, m in sections.items() if not m]
        if unrevised:
            return row("implement-change", ticket, "reopened", f"review reopened the design in {', '.join(unrevised)}")
        # A redesign is approved when its own `## Revision` section carries an `Approved by:` line.
        drafted = [t for t, m in sections.items() if not re.search(r"^Approved by: \S", m.group(1), re.M)]
        if drafted:
            return row("implement-change", ticket, "reopened", f"the redesign for {', '.join(drafted)} is drafted, not yet approved")
        # An outcome from before the redesign names none of its threads.
        unbuilt = [t for t in reopened if t not in fields["outcome_reopened"].split()]
        if not fields["outcome"] or unbuilt or fields["dirty"] == "true":
            return row("implement-change", ticket, "reopened", "the redesign's build has not finished")
        if fields["outcome"].strip() != "Build: passed":
            return row("nothing", ticket, "build-stopped", fields["outcome"].strip())
        if has_pr:
            return row("pr-create", ticket, "reopened-body", f"the redesign is built; #{pr['number']}'s description lacks {', '.join(reopened)}")

    if has_pr:
        n = pr["number"]
        if not pr["open"]:
            merged_claims = claimed(stack, "merged")
            if stack and criteria and all(c in merged_claims for c in criteria):
                return row("nothing", n, "pr-closed", f"pull request #{n} is {pr['state']}; every criterion is covered: the ticket is done")
            if stack:
                waiting = [s for s in stack if s["state"] == "open"]
                if waiting:
                    return row("nothing", waiting[0]["number"], "open-part", f"#{n} is {pr['state']}; #{waiting[0]['number']} is open{left}")
                if next_part:
                    return row("implement-change", ticket, "next-part", f"#{n} is {pr['state']}; {next_part}")
                if unclaimed:
                    return row("nothing", n, "unclaimed", f"the plan's {parts} parts leave {', '.join(unclaimed)} unclaimed")
            return row("nothing", n, "pr-closed", f"pull request #{n} is {pr['state']}")
        # The author who answered a findings review and pushed goes on from the threads; a reviewer
        # reviews the new head. A built reopen is reviewed again, by the author too, until its thread
        # is answered as fixed. GitHub logins are case-insensitive.
        reopen_pending = any(
            r["id"] in fields["outcome_reopened"].split() and r["verdict"] == "agree" and r["after"] == 0 and not r["done"] and not COMMIT.search(r["text"])
            for r in pr["rows"]
        )
        # A review by people or a bot counts once a thread someone else opened has its answer.
        answered_others = any(r["by"] and r["by"].lower() != pr["author"].lower() and r["verdict"] != "unanswered" for r in pr["rows"])
        answered_by_author = (bool(pr["reviewed"]) or answered_others) and me.lower() == pr["author"].lower() and not reopen_pending
        if not any(same(pr["head"], s) for s in pr["reviewed"]):
            # A review kept here, not posted, is the person's choice, the author's too: it routes on
            # once they made it.
            local = local_review if local_review and same(pr["head"], local_review["head"]) else None
            if local and local["posting"] == "undecided":
                return row("pr-review", n, "review-unposted", "a review of the current head is kept here; whether to post it is undecided")
            posted_here = reviewed_this_loop and not pr["draft"]
            if not answered_by_author and not posted_here and (not local or local["posting"] != "declined"):
                return row("pr-review", n, "pr-review", "no review of the current head")
        waits = None
        if reviewed_this_loop and not pr["draft"]:
            waits = row("nothing", n, "reviewers-first", "the review is posted; reviewers answer first")
        else:
            walk = [r for r in pr["rows"] if r["verdict"] in ("unanswered", "unparsed") or r["contested"] == "yes"]
            walk += [r for r in pr["rows"] if r["verdict"] == "discuss" and r["after"] > 0 and r["contested"] != "yes"]
            if walk:
                return row("pr-fix", n, "walk", f"{len(walk)} thread(s) to answer")
            agreed = [
                r for r in pr["rows"]
                if r["verdict"] == "agree" and r["after"] == 0 and not r["done"] and not COMMIT.search(r["text"]) and not REPLIED.match(r["text"])
            ]
            later = [r for r in agreed if FOLLOW_UP.search(r["text"])]
            if len(agreed) > len(later):
                return row("pr-fix", n, "fix", f"{len(agreed) - len(later)} agreed thread(s) to fix")
            if later:
                return row("pr-fix", n, "follow-up", f"{len(later)} agreed in a follow-up, to reply to")
            judged_done = [r["id"] for r in pr["rows"] if r["verdict"] == "agree" and r["after"] == 0 and r["done"] and not COMMIT.search(r["text"])]
            confirm = f"; fix taken as made from a judged reply, to confirm: {', '.join(judged_done)}" if judged_done else ""
            if pr["draft"]:
                waits = row("nothing", n, "mark-ready", "every thread answered, still a draft" + confirm)
            else:
                discuss = [r["id"] for r in pr["rows"] if r["verdict"] == "discuss"]
                waits = row("nothing", n, "answered", "every thread answered" + (f"; still in discussion: {', '.join(discuss)}" if discuss else "") + confirm)
        if next_part:
            return row("implement-change", ticket, "next-part", f"#{n}: {waits['say']}; {next_part}")
        return waits

    if fields["elsewhere"]:
        return row("nothing", ticket, "elsewhere", f"built on {fields['elsewhere']}, not here")
    if fields["slug"]:
        known = workflow()
        return {**row("nothing", fields["slug"], "unfiled", f"drafted as {fields['slug']}, not filed"),
                "paste": "issue.md" if known and known[0] == "github" else "jira.txt"}
    if not fields["context"]:
        status = ticket_status.strip().lower()
        known = workflow() if ticket and (status or issue_state) else None
        if ticket and issue_state and (not known or known[0] != "github"):
            raise Refused("--issue-state is a GitHub tracker's, and the profile's issue_tracker records no GitHub tracker")
        if known and known[0] == "github":
            if status:
                raise Refused("a GitHub tracker's status is --issue-state with a --label per label, not --ticket-status")
            return issue_row(ticket, issue_state, labels or [], known[1], known[2], pr)
        if known:
            _, statuses, pr_statuses = known
            if status not in statuses:
                raise Refused(f"the ticket status {ticket_status!r} is not one of the statuses the profile's issue_tracker names")
            if status in pr_statuses and pr is None:
                raise Refused(f"{ticket} is {ticket_status}: pass the state block of its pull request, or pull request: none")
            if statuses[status] == "implement-change":
                return row("implement-change", ticket, "ticket-to-do", f"{ticket} is {ticket_status}, with no context page here")
            if statuses[status] == "nothing":
                return row("nothing", ticket, "ticket-closed", f"{ticket} is {ticket_status}")
        if ticket and status and not known:
            return row("ticket-draft", ticket, "ticket-draft", f"no context page; {ticket} is {ticket_status}, and no workflow is recorded")
        return row("ticket-draft", ticket, "ticket-draft", "no context page")
    if not Path(fields["plan"]).is_file():
        return row("implement-change", ticket, "plan", "no plan yet")
    if not re.search(r"^Approved by: \S", Path(fields["plan"]).read_text(), re.M):
        return row("implement-change", ticket, "plan", "the plan is drafted, not yet approved")
    if not fields["outcome"]:
        return row("implement-change", ticket, "build", "the plan is approved; the build has not finished")
    if fields["dirty"] == "true":
        return row("implement-change", ticket, "diff-gate", "the build finished with uncommitted changes")
    if fields["outcome"].strip() != "Build: passed":
        return row("nothing", ticket, "build-stopped", fields["outcome"].strip())
    return row("pr-create", ticket, "pr-create", "built, no pull request")


# What the phase will ask the person, for work's third line.
ASKS = {
    "ticket-draft": "questions about the ticket, then a yes to the draft.",
    "implement-change": "the plan, the diff, and whether to open a pull request; it runs unattended between them.",
    "pr-create": "a yes to the description.",
    "pr-review": "whether to draft comments, then whether to post them; nothing posts without your yes.",
    "pr-fix": "agree, disagree or discuss on each thread, then the plan, the diff, the push and any reply.",
}
NEXT = {
    "pr-closed": "Nothing: a merged pull request's threads are harvested at the monthly revision.",
    "open-part": "Next: work takes up that open part.",
    "unclaimed": "Nothing: add a part to the plan, or settle the criterion on the ticket.",
    "elsewhere": "Nothing here: switch to the ticket's branch and run work again.",
    "reviewers-first": "Nothing: reviewers answer on GitHub first.",
    "mark-ready": "Nothing: mark it ready for review on GitHub, then run work again after reviewers answer.",
    "answered": "Nothing: settle any discuss thread by saying whether you agree; the merge is a person's.",
    "build-stopped": "Nothing yet: retry the build, open the pull request anyway, or discuss.",
    "ticket-closed": "Nothing: the ticket is past the build; open it in the tracker to see why.",
    "unfiled": "Nothing: file `.review/context/{argument}.{paste}` in the tracker, or have `/lasp-dev:ticket-draft {argument}` file it; "
    "give it the key to rename the page, then run `/lasp-dev:work <key>`.",
}


def lines(ticket: str, d: dict, stack: list[dict] | None = None) -> list[str]:
    # An argument of digits is a pull request's number, except a GitHub issue's own, the ticket.
    listed = "stack: " + ", ".join(f"#{s['number']} {s['state']}" for s in stack) if stack and len(stack) > 1 else ""
    head = " · ".join(
        p for p in (shown(ticket) or "no ticket", listed, f"pull request #{d['argument']}" if d["argument"].isdigit() and d["argument"] != ticket else "", d["say"]) if p
    )
    if d["phase"] == "nothing":
        return [head, NEXT[d["why"]].format(argument=d["argument"], paste=d.get("paste")), "It will ask you: nothing."]
    return [head, f"Next: {d['phase']}.", f"It will ask you: {ASKS[d['phase']]}"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fields", type=Path, required=True, help="hooks/where.sh --fields, saved to a file")
    p.add_argument("--state", type=Path, help="pr-reader's state block, saved to a file")
    p.add_argument("--pr", default="", help="the pull request work was given")
    p.add_argument("--ticket-status", default="", help="the ticket's Jira status, when it has no context page here")
    p.add_argument("--issue-state", choices=("open", "closed"), default="", help="a GitHub issue's state, when it has no context page here")
    p.add_argument("--label", action="append", default=[], help="one of that issue's labels; once per label")
    p.add_argument("--reviewed-this-loop", action="store_true", help="pr-review posted in this invocation of work")
    p.add_argument("--stack", type=Path, help="the ticket's pull requests, one `#<n> <state> <branch> <claims>` per line")
    p.add_argument("--criteria", default="", help="the ticket's Acceptance Criteria, such as AC-1,AC-2")
    p.add_argument("--local-review", type=Path, help="the pull request's .review/pr-<n>-review-submission.md, when it exists")
    p.add_argument("--me", default="", help="the GitHub login of the person running work")
    args = p.parse_args(argv)
    try:
        fields = read_fields(args.fields.read_text())
        pr = read_state(args.state.read_text()) if args.state else None
        stack = read_stack(args.stack.read_text()) if args.stack else None
        criteria = [c.strip() for c in args.criteria.split(",") if c.strip()]
        local = read_local_review(args.local_review.read_text()) if args.local_review else None
        if args.label and not args.issue_state:
            raise Refused("--label needs --issue-state")
        d = decide(fields, pr, args.ticket_status, args.reviewed_this_loop, args.pr, stack, criteria, local, args.me, args.issue_state, args.label)
    except (Refused, OSError) as e:
        print(f"next_phase.py: {e}", file=sys.stderr)
        return 1
    # Under --pr the first line names the pull request's ticket, which decide() checked.
    ticket = pr["ticket"] if args.pr else fields["ticket"]
    lock = fields["lock"] if d["phase"] in LOCKING and fields["lock"] else "none"
    print(f"phase: {d['phase']}\nargument: {d['argument']}\nwhy: {d['why']}\nlock: {lock}")
    print("\n".join(lines(ticket, d, stack)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
