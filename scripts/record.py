#!/usr/bin/env python3
"""Write a pull request's review record from its review threads, reviews and body.

Implements `skills/pr-review/SKILL.md`, "Whose reply counts". Inputs are the GitHub MCP
server's `pull_request_read` results, saved as JSON: `get` (--pr), `get_reviews` (--reviews) and
`get_review_comments` (--comments), and `get_comments` (--issue-comments), the conversation
comments, and the pull request body (--body). Output is block YAML in
the shape of `tests/fixtures/pr-0042/expected.yaml`.

The record is the harvest's working form: the pull request's threads are the record, and
`revise` regenerates this file from them at each revision; nothing writes it at review
time. The ticket is the key on the body's `Ticket:` line, in the ticket key pattern of the
repository's profile (`scripts/profile.py`), or on a GitHub tracker the issue's `#<n>`, recorded
as its number, or `none`; a body with a `Ticket:` line under a
profile that profile.py refuses, or one whose pattern reads `not yet recorded`, or a body with
more than one `Ticket:` line, is refused. A
ticket in several pull requests gives `stack:` from that line's `part k of n · base: <branch>`
and `claims:` from the `Claims:` line, each `none` when absent. The build, plan, gates and tokens
are the lines of the body's Already checked block, which must carry them; its optional `Depth:` line,
one of light, standard or deep, becomes `inner.depth`, `none` when absent, its `Reopened:`
lines, one per reopened thread, the list `inner.reopened`, and its optional
`Rules checked:` and `Declined:` lines become `inner.fired` and `inner.declined`, the build's own
findings, empty when a line is absent or reads `none`, each entry opening with a finding key's
citation; its optional `Nominated:` and `Procedure:` lines, the corrections a person made at the
plan and diff gates, become `inner.nominated` and `inner.procedure`, split on `;` and needing no citation;
its optional `Reproduced:` line becomes `inner.reproduced`, `none` when absent or `none`, and its optional
`Ripple: predicted <a, b or none> · verified <a or none> · breaks <a or none>` line becomes
`inner.ripple`, three lists, `none` when absent; a body with no block was not built,
and its record carries `build: none`, `plan: none` and `inner: none`. With no --standards-sha,
the sha is the latest findings review's `standards: <sha>` line, which reads `none` for a
repository with no standard and ends ` + uncommitted`, kept, when the review ran on uncommitted
standards. A record is of a merged pull request: `date:` is the day of its
first review, the first findings review's, and `merged:` the UTC day it merged, from `merged_at`,
which an unmerged pull request lacks and is refused for. A reviewer is a person other than the
pull request's author; a findings review makes a record whoever posted it, since the person who
ran the review approved every finding in it. A pull request with no findings review still gets a record when a
reviewer said something, in a review thread, a review summary or a conversation comment, or the
author opened a thread in their own words: its head is the merge or head sha, its date the day of
the first of those, its standards sha `none`, and it has no findings. A finding is a thread whose first comment opens on one of the four severity lines and
carries the review's attribution line; one with a `Standard` block and a citation goes under
`findings:`, and one without, or with a legacy `other` key, under `threads:` with `by: review`,
its severity and its verdict read as a finding's. Every other thread, a person's or a bot's, is
listed under `threads:` as a pointer, with the author's verdict from the first of their replies
in it that starts with one of the three words, or the judgment of one with none, a Discuss settled
by their next Agree or Disagree, `unanswered` when the author has not replied, on a thread
someone else opened or one they opened in their own words, `unparsed` when their replies there
carry no word and no judgment reads them, and `none` on a thread the author opened with an
AI-drafted comment. A reply's last line, when it carries the 🤖 and
`AI-assisted` and is not the only line, is its attribution and no part of its reason or answer.
Every review that is not a findings review and whose body is not blank is listed under
`reviews:`, and every conversation comment under `comments:`, each a pointer with who wrote it,
its authorship, its date and its first line that is not quoted; a bot's or the author's are
listed too, and their `by:` beside the record's `author:` says whose they are. Neither carries a verdict: a review body or a
conversation comment is not a thread, the author's reply to it has no fixed place, and
`thread-analyst` reads what came of it.
The unanswered, unparsed and contested findings, and the unparsed people's threads, are printed
on stderr, and recorded with that verdict. A finding whose Standard block has no readable key is
named on stderr; --state lists it with the key `-` and its verdict, and a record of its pull
request is refused. A finding with a Standard block whose first line is not one of the four
severity lines is recorded, where its key places it, with `severity: unparsed`, `verdict:
unparsed` and `line:`, that first line, its replies unread, since its severity decides how they
read; it is printed on stderr as `unparsed label:`, the last line counts such labels, --undecided
does not list it and --state refuses it.

A verdict is read from its word first. --undecided prints, as JSON, the threads the words leave
open (a finding unparsed, held by a reasonless Disagree or still in discussion, a person's thread
the author answered without one or whose Discuss no word of theirs has settled) with the replies a judgment may read, and writes nothing.
`pr-reader` judges them and writes the judgments, which --judged reads: each reads one wordless
reply as though it opened with the judged word, so it settles, opens a discussion and contests as
a word would, and the entry it decides carries `judged: true` and the judge's `basis:`, and
`done: true` when the reply says the change was made. A judgment on anything --undecided does not
list, so on any reply with a word, is refused: a judgment never overrides a word.

Input the script does not support, such as an Already checked block missing one of its lines, a
labeled line with nothing after its label, a pull request with no `merged_at` or no author's login,
one with no findings review and nothing a reviewer said, a thread without GitHub's `is_resolved`
and `is_outdated` flags, a person's reply with an empty body, a review summary in a state other
than approved, changes requested, commented or dismissed or missing its login, date or commit, a
conversation comment missing its id, login, body or date, a review or comment id given twice, a
review with no `html_url` or one on a repository other than --repo, or an input file that is not
JSON, exits 1 with the reason; nothing is guessed. Stdlib only, so the
plugin needs no environment.

A record's first line is `contract: 13` and the --state printout's `contract: 6`: the version
of each interface as `docs/contracts.md` defines it.

With --state it writes nothing and prints where the pull request stands: the head, then
`draft: true|false` and `state: open|merged|closed` from the `get` result's `draft`, `merged` and
`state` fields, which a pull request without them is refused for, `author: <login>`, who opened
it, then the body's
`Ticket:` line and the block's `Build:` line, each findings review with its `standards:` sha when it has one, and one row per review thread with its verdict
under "Whose reply counts": agree, disagree, discuss, unanswered or unparsed, or answered for a
question, read from its word or, given --judged, the judgment. Contested means a second person's verdict differs and the author has not settled it.
A pull request with no findings review is supported there; an uncited finding's key is `-`; a
thread that is not a finding is
listed with its opener, its resolved flag, the author's verdict, `unanswered`, `unparsed` or `none`, and its outdated flag
in the key, severity, verdict and proposed columns. The tenth column, after the verdict, is the text
after the verdict word on the verdict reply's first line, or on a Disagree its whole reason on one
line, as the record keeps it, a judged reply's first line or reason, empty when there is none; the
last, judged, is `no`, `yes, <login>: <basis>` (`yes, <login>, done: <basis>` when the reply says
the change was made), or `unclear: <basis>`; a `|` in any column is printed `\\|`, so
a row splits on ` | ` into its eleven columns. Replies after counts the replies after the verdict reply, for a finding's thread
and a person's alike, and every reply on a person's thread with no verdict; on a `discuss` row,
only the replies after the pull request author's last one, so the author's own answer in the
discussion leaves it at 0. --out is refused, --standards-sha is
ignored, and --issue-comments is required but not read.
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERDICTS = ("disagree", "discuss", "agree")
LABEL = re.compile(r"\*\*(Must fix before merge|Should fix|Suggestion|Question)\*\*\s*[—-]\s*(.+)")
# The attribution line opens with either wording: the current one, and the one comments posted before
# the AI assistance level carry.
ATTRIBUTIONS = ("AI-assisted comment, posted by @", "AI-assisted comment, reviewed and approved by @")
# Signs, beside the attribution line and a standard's `attribution.phrases`, that a comment was
# drafted by an agent, as docs/contracts.md "Authorship" lists them. Each is matched against the
# first and the last of the comment's own lines, where an agent signs, lowercased and with its code
# spans removed, and each has a signature's shape, so a person's sentence about one does not match.
AI_SIGNATURES = tuple(
    re.compile(p)
    for p in (
        r"^[^a-z0-9]*🤖.*(?<![a-z])ai-assisted(?![a-z])|(?<![a-z])ai-assisted(?![a-z]).*🤖[^a-z0-9]*$",
        r"(?<![a-z])ai assistance level: *[1-5]/5( *\([^)]*\))?[^a-z0-9?]*$",
        r"^[\W_]+(this )?(comment|reply|review|summary) (was |is )?(generated|drafted|written) (by|with) (claude|copilot|an? (ai|llm))(?![a-z])[^?]*$",
        r"^[^a-z0-9]*🤖[^a-z0-9]*generated (by|with)(?![a-z])",
        r"^[\W_]*generated (by|with) (\[claude code\]\([^)]*\)|claude code)[^a-z0-9]*$",
        r"^co-authored-by: *claude(?![a-z])",
    )
)
SEVERITIES = {"must fix before merge": "must-fix", "should fix": "should-fix", "suggestion": "suggestion", "question": "question"}
# The versions of the --state printout and of the record, as docs/contracts.md defines them.
CONTRACT = 6
RECORD_CONTRACT = 13
# What a judgment may say a reply means, as docs/contracts.md "The judgments" defines it.
JUDGED = (*VERDICTS, "answered", "unclear")
# The Already checked lines a built pull request's body must carry; pr-create's body.md writes them.
BUILD, PLAN, GATES, TOKENS = REQUIRED_LINES = ("Build:", "Plan:", "Gates:", "Tokens since the build started:")
# The optional Already checked lines read into the record: the build's firings and declines.
RULES_CHECKED, DECLINED = OPTIONAL_LINES = ("Rules checked:", "Declined:")
# The optional Already checked lines that carry the corrections a person made at the gates.
NOMINATED, PROCEDURE = "Nominated:", "Procedure:"
# The build's review depth, the Already checked block's optional `Depth:` line.
DEPTH, DEPTHS = "Depth:", ("light", "standard", "deep")
# The citations a finding key starts with, as standards/review-contract.md "Citation" lists them.
CITATION = re.compile(r"(R-\d+|D-\d+(@[\w-]+)?|(ticket|term|test|helper)/)")
# Review bots that post under a plain login in the MCP server's thread output.
BOT_LOGINS = {"copilot-pull-request-reviewer", "copilot", "github-actions"}


class Unsupported(Exception):
    """Input the script will not interpret."""


def load_profile():
    spec = importlib.util.spec_from_file_location("profile", Path(__file__).with_name("profile.py"))
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    return profile


@functools.lru_cache(maxsize=None)
def project_phrases() -> tuple[str, ...]:
    """The working directory's repository's `attribution.phrases`, from its standard over the
    default profile, lowercased: the wordings beside the review's attribution line that
    mark a comment as AI-drafted. Raises Unsupported when the profile is refused, since then no
    comment's authorship can be told."""
    profile = load_profile()
    try:
        return tuple(sorted({p.lower() for p in profile.defaults(ROOT)["attribution"]["phrases"]}))
    except (profile.ProfileError, OSError) as e:
        raise Unsupported(f"the repository's standard, or the default profile, is refused: {e}") from e


def ticket_pattern(repo: str) -> str:
    """The ticket key pattern of the repository's profile under ROOT."""
    profile = load_profile()
    try:
        ticket = profile.resolve(repo, ROOT)["ticket"]
    except profile.ProfileError as e:
        raise Unsupported(f"the profile is refused: {e}") from e
    if ticket == profile.NOT_RECORDED or ticket["pattern"] == profile.NOT_RECORDED:
        raise Unsupported(f"the profile for {repo} has no ticket.pattern recorded")
    return ticket["pattern"]


def ticket_key(repo: str, line: str) -> str:
    """The ticket the body's `Ticket:` line names, or `none`, as profile.py's `ticket_named` reads
    it: on a GitHub tracker the issue's number, whatever the pattern; otherwise the key in the
    profile's pattern. A line that names the wrong tracker's key is refused."""
    profile = load_profile()
    try:
        tracker = profile.defaults(ROOT, repo)["issue_tracker"]
    except (profile.ProfileError, OSError) as e:
        raise Unsupported(f"the profile is refused: {e}") from e
    github = tracker != profile.NOT_RECORDED and tracker["kind"] == "github"
    try:
        t = profile.ticket_named(line, tracker, "" if github else ticket_pattern(repo))
    except ValueError as e:
        raise Unsupported(str(e)) from e
    return t or "none"


def is_bot(login: str) -> bool:
    return login.endswith("[bot]") or login.lower() in BOT_LOGINS


def reviewer(login: str, pr_author: str) -> bool:
    """A reviewer: a person other than the pull request's author. A record exists when a reviewer
    said something, or when the author opened a thread in their own words."""
    return not is_bot(login) and login != pr_author


def answerable(opener: dict, pr_author: str) -> bool:
    """Whether a thread that is not a finding waits on the author's answer: one anyone else
    opened, and one the author opened in their own words, since the author reviewing their own
    pull request is a reviewer like any other. Only one the author opened with an AI-drafted
    comment does not."""
    return opener["author"] != pr_author or authorship_of(opener) == "human"


CODE_SPAN = re.compile(r"`[^`]*`")
FENCE = re.compile(r"^(`{3,}|~{3,})")


def own_lines(body: str) -> list[str]:
    """A comment's own lines, stripped and not blank: without the lines that open `>`, which quote
    someone else, and without fenced code blocks, which show text rather than sign the comment. A
    fence closes on a line of the same character, at least as long, and nothing else after it."""
    out, fence = [], None
    for line in body.splitlines():
        s = line.strip()
        m = FENCE.match(s)
        if fence is None and m:
            fence = m[1]
        elif fence is not None:
            if m and m[1][0] == fence[0] and len(m[1]) >= len(fence) and not s[len(m[1]):].strip():
                fence = None
        elif s and not s.startswith(">"):
            out.append(s)
    return out


def authorship_of(comment: dict) -> str:
    """Who wrote a comment: `bot` for a bot's login; `ai-drafted` when it carries the review's
    attribution line or one of the standard's `attribution.phrases` in its own lines (`own_lines`),
    or one of AI_SIGNATURES on the first or the last of them, case aside; `human` otherwise, so a
    comment with no sign is a person's. Read per comment, so a person's reply in a thread an agent
    opened is `human`. The one definition of AI-drafted that the record and thread-analyst
    share."""
    if is_bot(comment["author"]):
        return "bot"
    lines = own_lines(comment["body"].lower())
    body = "\n".join(lines)
    if any(a.lower() in body for a in ATTRIBUTIONS) or any(p in body for p in project_phrases()):
        return "ai-drafted"
    if any(sig.search(CODE_SPAN.sub("", line)) for sig in AI_SIGNATURES for line in {*lines[:1], *lines[-1:]}):
        return "ai-drafted"
    return "human"


def q(text: str) -> str:
    """A YAML double-quoted scalar; JSON string syntax is valid YAML."""
    return json.dumps(text, ensure_ascii=False)


def when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def unsigned(body: str) -> str:
    """A reply without its attribution line: the last line of a reply of more than one, when it
    carries the 🤖 and the words `AI-assisted`, which comment-style keeps however a reply's line is
    worded."""
    lines = body.strip().splitlines()
    if len(lines) > 1 and "🤖" in lines[-1] and "AI-assisted" in lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def verdict_of(body: str) -> tuple[str | None, str]:
    """The verdict word the first line starts with, read leniently, `Agreed` and `Disagreed`
    included, and the text after it, without the reply's attribution line."""
    m = re.match(r"[\s*_>`\"']*(" + "|".join(VERDICTS) + r")d?\b[\s*_]*[.,:;!\-—–]*[ \t]*(.*)", unsigned(body), re.I | re.S)
    return (m.group(1).lower(), m.group(2).strip()) if m else (None, "")


def after_verdict(body: str) -> str:
    """The text after a reply's verdict word, on one line: a Disagree's whole reason, as the record
    keeps it, or the rest of the first line on an Agree or a Discuss, such as "in a follow-up
    (PROJ-900)"; empty when there is none."""
    word, rest = verdict_of(body)
    return " ".join(rest.split()) if word == "disagree" else verdict_of(first_line(body))[1]


def findings_reviews(reviews: list[dict]) -> list[tuple[dict, str]]:
    """The reviews `pr-review` posted, each with the sha on its `reviewed:` line, oldest first: in
    any of the three verdicts the person may choose (COMMENTED, APPROVED, CHANGES_REQUESTED), or
    DISMISSED, since a dismissal withdraws the verdict, not the findings or the head they reviewed;
    the body's first line is `## Review`, or `## Standards review` as earlier ones were, and
    the body carries the attribution line. Any other review, such as a person's headed
    `## Review notes` or one with no attribution, is a person's review. Raises Unsupported for one
    that has the heading and the attribution but no `reviewed:` line or no `submitted_at`, which is
    broken output."""
    found = []
    for r in reviews:
        body = (r.get("body") or "").lstrip()
        heading = re.fullmatch(r"## (Review|Standards review)[ \t]*", body.split("\n", 1)[0].rstrip("\r"))
        if r.get("state") not in REVIEW_STATES or not heading or not any(a in body for a in ATTRIBUTIONS):
            continue
        m = re.search(r"^reviewed: ([0-9a-f]{7,40})\s*$", body, re.M)
        if not m:
            raise Unsupported(f"findings review {r.get('id')} has no 'reviewed: <sha>' line")
        if not r.get("submitted_at"):
            raise Unsupported(f"findings review {r.get('id')} has no 'submitted_at'")
        found.append((r, m.group(1)))
    return sorted(found, key=lambda x: when(x[0]["submitted_at"]))


def standards_line(review: dict) -> str | None:
    """The sha on a findings review's `standards:` line, or `none`, which pr-review posts for a
    repository with no standard, kept with its ` + uncommitted` suffix when the review ran on
    uncommitted standards; None when the review has no such line."""
    m = re.search(r"^standards: ((?:[0-9a-f]{7,40}|none)(?: \+ uncommitted)?)\s*$", review.get("body") or "", re.M)
    return m.group(1) if m else None


def parse_finding(thread: dict) -> dict | None:
    """The finding a thread's first comment carries, or None for a thread that is not one. A
    finding with a Standard block whose first line is not one of the four severity lines has the
    severity `unparsed` and that line as its `label`. A reply from a person with an empty body is
    refused: it has no first line to read a verdict from."""
    for c in thread["comments"][1:]:
        if not is_bot(c["author"]) and not c["body"].strip():
            raise Unsupported(f"thread {thread['id']} has a reply by {c['author']} with an empty body")
    first = thread["comments"][0]
    standard = "<summary>Standard</summary>" in first["body"]
    m = LABEL.match(first["body"])
    if standard and not any(a in first["body"] for a in ATTRIBUTIONS):
        raise Unsupported(f"thread {thread['id']} is a finding with no attribution line")
    # Without a Standard block or a severity line, and the review's attribution, it is a person's or a bot's thread.
    if not (m or standard) or not any(a in first["body"] for a in ATTRIBUTIONS):
        return None
    key, unreadable = None, False
    if standard:
        block = first["body"].split("<summary>Standard</summary>", 1)[1].split("</details>", 1)[0]
        # The key in backticks, or bare to the line's end; a bare key is a citation, or the legacy
        # `other/`, with the `::` every key in the review contract holds.
        k = re.search(r"^key: (?:`([^`]+)`|(.*)$)", block, re.M)
        quoted, bare = (k.group(1), (k.group(2) or "").strip()) if k else (None, "")
        readable = (CITATION.match(bare) or bare.startswith("other/")) and "::" in bare and not re.search(r"[`*]", bare)
        cited = quoted or (bare if readable else None)
        if cited:
            # `other` was the citation of an uncited finding before the contract dropped it.
            key = None if cited.startswith("other/") else cited
        else:
            unreadable = True
            print(f"record.py: thread {thread['id']} has a Standard block with no readable 'key:' line", file=sys.stderr)
    # A finding with no line is a file-level comment, recorded at its path alone.
    line = first.get("original_line") or first.get("line")
    return {
        "thread": thread["id"],
        "severity": SEVERITIES[m.group(1).lower()] if m else "unparsed",
        "title": m.group(2).strip() if m else first_line(first["body"]),
        "label": None if m else first_line(first["body"]),
        "key": key,
        "unreadable": unreadable,
        "at": f"{first['path']}:{line}" if line is not None else first["path"],
        "created": when(first["created_at"]),
        "replies": [c for c in thread["comments"][1:] if not is_bot(c["author"])],
    }


def pointer(thread: dict, pr_author: str, finding: dict | None = None, judgment: dict | None = None) -> dict:
    """A thread that is not a cited finding, as the record points to it: who opened it, where,
    GitHub's resolved and outdated flags, the replies from people, and its verdict. An uncited
    finding is opened `by: review` and its verdict is read as a finding's. Otherwise the verdict is
    the pull request author's: the word that opens their first reply to carry one, or the
    judgment of a reply of theirs with none, and a Discuss is settled by their next Agree or
    Disagree, word or judged; with no reply from the author it is `unanswered`, author replies
    that neither a word nor a judgment reads are `unparsed`, and a thread the author opened with
    an AI-drafted comment is `none`. A thread the author opened in their own words waits on
    their answer like anyone's. No other reply, reaction or flag is a verdict."""
    first = thread["comments"][0]
    for flag in ("is_resolved", "is_outdated"):
        if flag not in thread:
            raise Unsupported(f"thread {thread['id']} has no '{flag}' flag")
    line = first.get("original_line") or first.get("line")
    people = [c for c in thread["comments"][1:] if not is_bot(c["author"])]
    line_of = ""
    if finding is not None:
        adjudicate(finding, pr_author, judgment)
        word = {"answered": finding.get("verdict", "answered")}.get(finding["state"], finding["state"])
        rest, by = finding.get("reason", ""), "review"
        at = finding["decided"] if finding["replies"] and finding["state"] != "unanswered" and finding["severity"] != "unparsed" else None
        judged = finding.get("judged")
    else:
        own = [i for i, c in enumerate(people) if c["author"] == pr_author]
        words = {i: word_at(people, i, judgment) for i in own}
        at, word, rest = next(((i, *words[i]) for i in own if words[i][0]), (None, None, ""))
        # A Discuss stays open until the author's next Agree or Disagree, word or judged.
        if word == "discuss":
            at, word, rest = next(((i, *words[i]) for i in own if i > at and words[i][0] in ("agree", "disagree")), (at, word, rest))
        # A question the author answered in their own words.
        if word is None and judgment and judgment["verdict"] == "answered":
            at, word, rest = judgment["reply"], "answered", ""
        if not own and answerable(first, pr_author):
            word = "unanswered"
        elif own and word is None and answerable(first, pr_author):
            word, line_of = "unparsed", first_line(unsigned(people[own[0]]["body"]))
        judged = judgment if judgment and judgment["verdict"] != "unclear" and at == judgment["reply"] else None
        by = "bot" if is_bot(first["author"]) else first["author"]
    unclear = judgment["basis"] if judgment and judgment["verdict"] == "unclear" else ""
    return {
        "thread": thread["id"],
        "by": by,
        "severity": finding["severity"] if finding else None,
        "at": f"{first['path']}:{line}" if line is not None else first["path"],
        "created": when(first["created_at"]),
        "authorship": authorship_of(first),
        "resolved": thread["is_resolved"],
        "outdated": thread["is_outdated"],
        "replies": len(people),
        # The replies after the verdict reply; every reply when there is no verdict.
        "replies_after": len(people) - 1 - at if at is not None else len(people),
        "after": (after_judged(people[at]["body"], judged) if judged else after_verdict(people[at]["body"])) if at is not None else "",
        "verdict": word or "none",
        "line": finding.get("line", "") if finding is not None else line_of,
        "judged": judged,
        "unclear": unclear,
        "reason": rest if word == "disagree" else "",
        # An uncited question's answer, as adjudicate keeps it for a cited one.
        "answer": finding.get("answer", "") if finding is not None else "",
        "headline": first_line(first["body"]),
    }


def word_at(replies: list[dict], i: int, judgment: dict | None) -> tuple[str | None, str]:
    """Reply i's verdict and the text after it: its word, or, for the one reply a judgment names,
    the judged verdict and reason, as though it opened with the word. A reply with neither reads
    (None, "")."""
    word = verdict_of(replies[i]["body"])
    if word[0] or not judgment or judgment["reply"] != i or judgment["verdict"] not in VERDICTS:
        return word
    return judgment["verdict"], judgment["reason"]


def adjudicate(f: dict, pr_author: str, judgment: dict | None = None) -> dict:
    """Apply "Whose reply counts" to one finding; sets f['state'] and the verdict fields. A
    judgment reads one wordless reply as though it opened with the judged word, so the open and
    Discuss settlements and the rival check run on it as on a word; when it decides the thread,
    f['judged'] holds it, and an unclear judgment's basis is f['unclear']."""
    replies = f["replies"]
    # With no severity nothing settles it: whether a Disagree needs a reason, or a reply is an answer, is unknown.
    if f["severity"] == "unparsed":
        f["state"], f["line"] = "unparsed", f["label"]
        return f
    if judgment and judgment["verdict"] == "unclear":
        f["unclear"] = judgment["basis"]
    if not replies:
        f["state"] = "unanswered"
        return f
    f["decided"] = 0
    if f["severity"] == "question":
        f["state"], f["answer"], f["adjudicator"] = "answered", unsigned(replies[0]["body"]), replies[0]["author"]
        return f
    first = replies[0]
    word, rest = word_at(replies, 0, judgment)

    def reasonless(w: str | None, r: str) -> bool:
        return w == "disagree" and not r and f["severity"] in ("must-fix", "should-fix")

    def settles(w: str | None, r: str) -> bool:
        """An Agree, or a Disagree with the reason its severity needs."""
        return w == "agree" or (w == "disagree" and not reasonless(w, r))

    def settle_after(i: int) -> tuple[int, str, str] | None:
        """The first reply after reply i that settles the finding, whoever wrote it."""
        return next(
            ((j, *word_at(replies, j, judgment)) for j in range(i + 1, len(replies)) if settles(*word_at(replies, j, judgment))),
            None,
        )

    def held_open(i: int) -> tuple[int, str, str] | None:
        """Reply i, with no verdict word or a must-fix or should-fix Disagree with no reason, is open
        like Discuss: the next Agree, or Disagree with its reason, settles it, whoever writes it,
        and a judged Discuss after it opens the discussion. With neither, the finding is recorded
        open at reply i and None is returned."""
        settle = settle_after(i)
        if settle is None and judgment and judgment["verdict"] == "discuss" and judgment["reply"] > i:
            settle = judgment["reply"], "discuss", ""
        if settle is None:
            f["decided"] = i
            if word_at(replies, i, judgment)[0] is None:
                f["state"], f["line"] = "unparsed", replies[i]["body"].strip().splitlines()[0]
            else:
                f["state"], f["why"] = "unanswered", "disagree with no reason"
        return settle

    # An open first reply's settling reply opens the finding instead, and its author is the
    # adjudicator. Nothing before it contests it.
    opened = 0
    if word is None or reasonless(word, rest):
        settle = held_open(0)
        if settle is None:
            return f
        f["decided"], word, rest = settle
        opened = f["decided"]
        first = replies[opened]
    f["adjudicator"] = first["author"]
    f["word"] = word
    verdict, reason = word, rest
    # Discuss is open until a later Agree, or Disagree with its reason, in the thread settles it.
    if verdict == "discuss" and (settle := settle_after(f["decided"])):
        f["decided"], verdict, reason = settle
    # The author's first Agree, or Disagree with its reason, from the opening reply on.
    by_author = next(
        (i for i in range(opened, len(replies)) if replies[i]["author"] == pr_author and settles(*word_at(replies, i, judgment))),
        None,
    )
    # Before it, a second person's first verdict, differing from the settled one, contests it. The
    # author's reply is never a rival, nor is the reply that settled a Discuss, and a reasonless
    # must-fix or should-fix Disagree settles nothing, so it contests nothing either.
    rival = next(
        (
            i
            for i in range(opened + 1, len(replies) if by_author is None else by_author)
            if i != f["decided"]
            and replies[i]["author"] not in (first["author"], pr_author)
            and word_at(replies, i, judgment)[0]
            and not reasonless(*word_at(replies, i, judgment))
        ),
        None,
    )
    if rival is not None and word_at(replies, rival, judgment)[0] != verdict:
        f["contested"] = [f"{c['author']}: {c['body'].strip().splitlines()[0]}" for c in (first, replies[rival])]
    # The author's settling reply decides, over every reply before it and any contest. Without
    # one, a contest stands until they settle it; otherwise their first reply after someone else's
    # Agree or Disagree, a Discuss, a reasonless Disagree or one with no word, reopens the finding
    # as the same reply would open it first.
    mine = next((i for i in range(f["decided"] + 1, len(replies)) if replies[i]["author"] == pr_author), None)
    if by_author is not None:
        f["decided"] = by_author
        verdict, reason = word_at(replies, by_author, judgment)
    elif "contested" in f:
        f["state"] = "contested"
        return f
    elif mine is not None and verdict != "discuss":
        if word_at(replies, mine, judgment)[0] == "discuss":
            settle = settle_after(mine) or (mine, "discuss", "")
        elif (settle := held_open(mine)) is None:
            return f
        f["decided"], verdict, reason = settle
    # The adjudicator is whoever wrote the reply that settled it, which a later reply may be.
    f["state"], f["verdict"], f["adjudicator"] = "answered", verdict, replies[f["decided"]]["author"]
    if verdict == "disagree" and reason:
        f["reason"] = reason
    if judgment and judgment["reply"] == f["decided"] and not verdict_of(replies[f["decided"]]["body"])[0]:
        f["judged"] = judgment
    return f


def eligible(replies: list[dict], may_decide) -> list[int]:
    """The replies a judgment may read: those from someone who may decide the thread, after the
    last of theirs with a verdict word, which leaves every one of them wordless."""
    last = max((i for i, c in enumerate(replies) if may_decide(c) and verdict_of(c["body"])[0]), default=-1)
    return [i for i in range(last + 1, len(replies)) if may_decide(replies[i])]


def undecided(threads: list[dict], pr_author: str) -> list[dict]:
    """The threads whose words leave the verdict open, for pr-reader to judge: a finding that is
    unparsed, held by a Disagree with no reason, or still in discussion, and a person's thread the
    author answered with no word, or whose Discuss no word of theirs has settled. Each lists the
    thread's replies from people, unsigned, and which of them a judgment may read: on a finding
    any person's wordless reply after the last word, on a person's thread the author's. A
    question, a thread read from its words, and one with nothing eligible are not listed."""
    out = []
    for th in threads:
        f = parse_finding(th)
        first = th["comments"][0]
        people = [c for c in th["comments"][1:] if not is_bot(c["author"])]
        if f is not None:
            if f["severity"] in ("question", "unparsed"):
                continue
            adjudicate(f, pr_author)
            open_ = f["state"] == "unparsed" or f.get("why") == "disagree with no reason" or (
                f["state"] == "answered" and f["verdict"] == "discuss"
            )
            may = eligible(people, lambda c: True) if open_ else []
        else:
            t = pointer(th, pr_author)
            open_ = t["verdict"] in ("unparsed", "discuss") and answerable(first, pr_author)
            may = eligible(people, lambda c: c["author"] == pr_author) if open_ else []
        if not may:
            continue
        out.append(
            {
                "thread": th["id"],
                "kind": "finding" if f is not None else "thread",
                # What the words read: an `answered` judgment fits only a thread they leave unparsed.
                "read": f["state"] if f is not None else t["verdict"],
                "severity": f["severity"] if f is not None else None,
                "opener": {"author": first["author"], "body": unsigned(first["body"])},
                "replies": [{"index": i, "author": c["author"], "body": unsigned(c["body"])} for i, c in enumerate(people)],
                "eligible": may,
            }
        )
    return out


def read_judged(data: object, open_: list[dict]) -> dict[str, dict]:
    """pr-reader's judgments, by thread, checked against the threads `undecided` lists: refuses a
    thread or reply it does not list, a thread judged twice, a verdict outside JUDGED, `answered`
    on a finding or on a thread the author's word opened a discussion on, `done` on anything but an agree, a basis that is not one non-empty line, and a
    reason that is not in the reply's own words."""
    if not isinstance(data, list):
        raise Unsupported("the judgments are not a JSON list")
    listed = {u["thread"]: u for u in open_}
    out: dict[str, dict] = {}
    for j in data:
        if not isinstance(j, dict) or not isinstance(j.get("thread"), str):
            raise Unsupported(f"a judgment with no thread: {j!r}")
        t = j["thread"]
        if t not in listed:
            raise Unsupported(f"judgment on {t}, which its words already read or which has nothing to judge; a judgment never overrides a word")
        if t in out:
            raise Unsupported(f"{t} is judged twice")
        verdict, reply, reason, basis = j.get("verdict"), j.get("reply"), j.get("reason") or "", j.get("basis")
        if verdict not in JUDGED:
            raise Unsupported(f"{t}: the verdict {verdict!r} is not one of {', '.join(JUDGED)}")
        if verdict == "answered" and listed[t]["kind"] == "finding":
            raise Unsupported(f"{t}: a finding is agreed, disagreed or discussed, not answered")
        if verdict == "answered" and listed[t]["read"] != "unparsed":
            raise Unsupported(f"{t}: the author's word already opened a discussion, which an answer does not settle")
        if verdict == "unclear":
            reply = None
        elif reply not in listed[t]["eligible"]:
            raise Unsupported(f"{t}: reply {reply!r} is not one a judgment may read there")
        if not isinstance(basis, str) or not basis.strip() or "\n" in basis.strip():
            raise Unsupported(f"{t}: the basis is not one non-empty line")
        if j.get("done") and verdict != "agree":
            raise Unsupported(f"{t}: done is for an agree")
        if reason and reply is None:
            raise Unsupported(f"{t}: an unclear judgment has no reason")
        if reason and " ".join(reason.split()) not in " ".join(listed[t]["replies"][reply]["body"].split()):
            raise Unsupported(f"{t}: the reason is not in the reply's own words")
        out[t] = {"reply": reply, "verdict": verdict, "reason": " ".join(reason.split()), "done": bool(j.get("done")), "basis": basis.strip()}
    return out


def after_judged(body: str, judgment: dict) -> str:
    """The after-the-verdict text for a judged reply: a Disagree's reason, else the reply's first
    line, so a commit or a follow-up it names still routes."""
    return judgment["reason"] if judgment["verdict"] == "disagree" else " ".join(first_line(unsigned(body)).split())


def labeled(text: str, label: str) -> str | None:
    """The value on the first line that opens with `label`, or None when no line does. A line with
    nothing after its label is refused rather than read as absent."""
    m = re.search(rf"^{re.escape(label)}[ \t]*(.*?)[ \t]*$", text, re.M)
    if m and not m.group(1):
        raise Unsupported(f"the '{label}' line is empty")
    return m.group(1) if m else None


def body_line(body: str, label: str) -> str:
    value = labeled(body, label)
    if value is None:
        raise Unsupported(f"the Already checked block has no '{label}' line")
    return value


def entries(block: str, label: str, sep: str, cited: bool = True) -> list[str]:
    """An optional Already checked line's entries, split on `sep`; none for a line that is absent
    or reads `none`. When `cited`, an entry that does not open with a finding key's citation is
    refused."""
    value = labeled(block, label)
    if value is None or value.lower() == "none":
        return []
    found = [e.strip() for e in re.split(sep, value) if e.strip()]
    for e in found:
        if cited and not CITATION.match(e):
            raise Unsupported(f"the '{label}' line has {e!r}, which does not open with a finding key")
    return found


def ticket_line(body: str) -> str | None:
    """The value of the body's one `Ticket:` line, or None. A second one is refused: the first
    would be read for the ticket and its part, and the other ignored."""
    found = len(re.findall(r"^Ticket:", body, re.M))
    if found > 1:
        raise Unsupported(f"the body has {found} 'Ticket:' lines, not one")
    return labeled(body, "Ticket:")


def reproduced(block: str) -> str:
    """The Already checked block's `Reproduced:` line, whole, or `none` when the line is absent or
    reads `none`, so `revise` tells a defect fix by a value other than `none`."""
    value = labeled(block, "Reproduced:")
    return q(value) if value and value.lower() != "none" else "none"


def ripple(block: str) -> str:
    """The Already checked block's `Ripple:` line as a flow map of three lists, or `none`. Each of
    its three slots names consumers or reads `none`; an empty slot is refused."""
    value = labeled(block, "Ripple:")
    if value is None:
        return "none"
    parts = re.fullmatch(r"predicted (.+?) · verified (.+?) · breaks (.+)", value)
    if not parts:
        raise Unsupported(f"a Ripple: line not as body.md gives it: {value!r}")
    lists = []
    for slot in parts.groups():
        named = [c.strip() for c in slot.split(",")]
        if named == ["none"]:
            lists.append([])
        elif all(named) and "none" not in named:
            lists.append([q(c) for c in named])
        else:
            raise Unsupported(f"a Ripple: slot that is neither consumers nor `none`: {slot!r}")
    return "{" + ", ".join(f"{k}: [{', '.join(v)}]" for k, v in zip(("predicted", "verified", "breaks"), lists)) + "}"


BLOCK = re.compile(r"<details><summary>Already checked</summary>(.*?)</details>", re.S)


def already_checked(body: str) -> str | None:
    """The body's Already checked block, which the build writes, or None for a change not built."""
    m = BLOCK.search(body)
    return m.group(1) if m else None


def body_line_or_none(body: str, *labels: str) -> str:
    """The first of the labeled lines the body has, label included, or 'none'."""
    for label in labels:
        value = labeled(body, label)
        if value is not None:
            return f"{label} {value}"
    return "none"


REVIEW_STATES = {"APPROVED": "approved", "CHANGES_REQUESTED": "changes_requested", "COMMENTED": "commented", "DISMISSED": "dismissed"}


def spoken(reviews: list, issue_comments: list) -> tuple[list[dict], list[dict]]:
    """The reviews that are not findings reviews and whose body is not blank, and the conversation
    comments, each checked. Raises Unsupported for reviews that are not one list of objects, for a
    review with no id or a body that is not
    text, for two reviews or two comments with one id, for conversation comments that are not one
    list of objects, for a listed review in a state `REVIEW_STATES` does not hold or missing its
    user login, submission date or commit, and for a comment missing its id, user login, body or
    creation date, or with a body that is not text."""
    if not isinstance(reviews, list) or not all(isinstance(r, dict) for r in reviews):
        raise Unsupported("--reviews is not one list of review objects, every page's items in it")
    seen: dict = {}
    for i, r in enumerate(reviews, 1):
        if "id" not in r:
            raise Unsupported(f"review {i} has no 'id'")
        if r["id"] in seen:
            raise Unsupported(f"reviews {seen[r['id']]} and {i} are both review {r['id']}")
        seen[r["id"]] = i
        if r.get("body") is not None and not isinstance(r["body"], str):
            raise Unsupported(f"review {r.get('id')} has a body that is not text")
    findings = {id(r) for r, _ in findings_reviews(reviews)}
    listed = []
    for r in reviews:
        if id(r) in findings or not (r.get("body") or "").strip():
            continue
        if r.get("state") not in REVIEW_STATES:
            raise Unsupported(f"review {r.get('id')} has the state {r.get('state')!r}, not one of {', '.join(REVIEW_STATES)}")
        for field in ("user", "submitted_at", "commit_id"):
            if not r.get(field) or (field == "user" and not (isinstance(r["user"], dict) and r["user"].get("login"))):
                raise Unsupported(f"review {r.get('id')} has no '{field if field != 'user' else 'user.login'}'")
        listed.append(r)
    if not isinstance(issue_comments, list) or not all(isinstance(c, dict) for c in issue_comments):
        raise Unsupported("--issue-comments is not one list of comment objects, every page's items in it")
    seen = {}
    for i, c in enumerate(issue_comments, 1):
        for field in ("id", "user", "body", "created_at"):
            given = c.get(field)
            if field == "user":
                given = given.get("login") if isinstance(given, dict) else None
            if field not in c or (field != "body" and given in (None, "")):
                raise Unsupported(f"conversation comment {i} has no '{field if field != 'user' else 'user.login'}'")
        if not isinstance(c["body"], str):
            raise Unsupported(f"conversation comment {i} has a body that is not text")
        if c["id"] in seen:
            raise Unsupported(f"conversation comments {seen[c['id']]} and {i} are both comment {c['id']}")
        seen[c["id"]] = i
    return listed, issue_comments


def conversation(listed: list, issue_comments: list) -> list[str]:
    """The `reviews:` and `comments:` pointer sections, from `spoken`, oldest first."""
    out = ["reviews:" if listed else "reviews: []"]
    for r in sorted(listed, key=lambda r: when(r["submitted_at"])):
        login = r["user"]["login"]
        out += [
            f"  - review: {r['id']}",
            f"    by: {'bot' if is_bot(login) else login}",
            f"    authorship: {authorship_of({'author': login, 'body': r['body']})}",
            f"    state: {REVIEW_STATES[r['state']]}",
            f"    submitted: {when(r['submitted_at']).astimezone().date().isoformat()}",
            f"    commit: {r['commit_id'][:7]}",
            f"    headline: {q(headline(r['body']))}",
        ]
    out.append("comments:" if issue_comments else "comments: []")
    for c in sorted(issue_comments, key=lambda c: when(c["created_at"])):
        login = c["user"]["login"]
        out += [
            f"  - comment: {c['id']}",
            f"    by: {'bot' if is_bot(login) else login}",
            f"    authorship: {authorship_of({'author': login, 'body': c['body']})}",
            f"    posted: {when(c['created_at']).astimezone().date().isoformat()}",
            f"    headline: {q(headline(c['body']))}",
        ]
    return out


def headline(body: str) -> str:
    """A review body's or a conversation comment's first line of its own: not blank and not a
    quoted line, one that opens `>`; empty when it has none."""
    return next((line.strip() for line in body.splitlines() if line.strip() and not line.lstrip().startswith(">")), "")


def first_line(body: str) -> str:
    return body.strip().splitlines()[0] if body.strip() else ""


def since_author(replies: list[dict], author: str) -> int:
    """The replies after the last one `author` wrote, or all of them when they wrote none."""
    own = [i for i, r in enumerate(replies) if r["author"] == author]
    return len(replies) - 1 - own[-1] if own else len(replies)


def on_repo(review: dict, repo: str) -> None:
    """Raises Unsupported for a review with no `html_url`, or one whose URL's owner/name is not
    `repo`, compared without case as GitHub compares them."""
    url = review.get("html_url")
    if not isinstance(url, str) or not url:
        raise Unsupported(f"review {review.get('id')} has no 'html_url'")
    on = re.match(r"https?://[^/]+/([^/]+/[^/?#]+)", url)
    if not on or on.group(1).lower() != repo.lower():
        raise Unsupported(f"review {review.get('id')} is not on {repo}")


def judged_cell(judged: dict | None, by: str, unclear: str) -> str:
    """The state row's last column: how the verdict was read."""
    if judged:
        return f"yes, {by}{', done' if judged['done'] else ''}: {judged['basis']}"
    return f"unclear: {unclear}" if unclear else "no"


def state(pr: dict, reviews: list, threads: list, body: str, repo: str, judged: dict | None = None) -> list[str]:
    """Where the pull request stands, as plain text: the --state printout."""
    judged = judged or {}
    body = body.replace("\r\n", "\n")
    for r in reviews:
        on_repo(r, repo)
    for field in ("draft", "state", "merged"):
        if field not in pr:
            raise Unsupported(f"the pull request has no '{field}' field")
    out = [
        f"contract: {CONTRACT}",
        f"head: {pr['head']['sha']}",
        f"draft: {str(pr['draft']).lower()}",
        f"state: {'merged' if pr['merged'] else pr['state']}",
        f"author: {pr['user']['login']}",
        f"ticket: {'Ticket: ' + ticket_line(body) if ticket_line(body) else 'none'}",
        f"build: {body_line_or_none(already_checked(body) or '', BUILD)}",
    ]
    reviewed = findings_reviews(reviews)
    out += [
        f"findings review: {r['id']} reviewed: {sha}" + (f" standards: {standards_line(r)}" if standards_line(r) else "")
        for r, sha in reviewed
    ] or ["findings review: none"]
    out.append(f"threads: {len(threads)}")
    out.append(
        "id | key, or opener | severity, or resolved | headline | path:line | verdict | contested | replies after"
        " | proposed, or outdated | after the verdict | judged"
    )
    for th in threads:
        f = parse_finding(th)
        if f is None:
            t = pointer(th, pr["user"]["login"], judgment=judged.get(th["id"]))
            if t["verdict"] == "discuss":
                t["replies_after"] = since_author([c for c in th["comments"][1:] if not is_bot(c["author"])], pr["user"]["login"])
            row = [
                t["thread"], t["by"], str(t["resolved"]).lower(), t["headline"], t["at"], t["verdict"], "no",
                str(t["replies_after"]), str(t["outdated"]).lower(), t["after"],
                judged_cell(t["judged"], pr["user"]["login"], t["unclear"]),
            ]
        elif f["severity"] == "unparsed":
            raise Unsupported(f"thread {th['id']} is a finding with the label {f['label']!r}, not one of the four")
        else:
            adjudicate(f, pr["user"]["login"], judged.get(th["id"]))
            verdict = {"answered": f.get("verdict", "answered"), "contested": f.get("word")}.get(f["state"], f["state"])
            after = len(f["replies"]) - 1 - f["decided"] if f["replies"] else 0
            if verdict == "discuss":
                after = since_author(f["replies"][f["decided"] + 1 :], pr["user"]["login"])
            proposed = re.search(r"^Proposed:.*$", th["comments"][0]["body"], re.M)
            settled = f["replies"] and f["state"] in ("answered", "contested") and f["severity"] != "question"
            row = [
                f["thread"], f["key"] or "-", f["severity"], f["title"], f["at"], verdict,
                "yes" if f["state"] == "contested" else "no", str(after), proposed.group(0).strip() if proposed else "none",
                (after_judged(f["replies"][f["decided"]]["body"], f["judged"]) if f.get("judged") else after_verdict(f["replies"][f["decided"]]["body"]))
                if settled
                else "",
                judged_cell(f.get("judged"), f.get("adjudicator", ""), f.get("unclear", "")),
            ]
        # A `|` in free text is escaped, so a row splits on " | " into exactly its eleven columns.
        out.append(" | ".join(c.replace("|", "\\|") for c in row))
    return out


def build(
    pr: dict,
    reviews: list,
    threads: list,
    body: str,
    repo: str,
    standards_sha: str | None,
    *,
    issue_comments: list,
    judged: dict | None = None,
) -> tuple[list[str], list[str]]:
    body = body.replace("\r\n", "\n")
    judged = judged or {}
    listed, issue_comments = spoken(reviews, issue_comments)
    for r in reviews:
        on_repo(r, repo)
    block = already_checked(body)
    if block is None:
        built = ["build: none", "plan: none", "inner: none"]
    else:
        value = {label: body_line(block, label) for label in REQUIRED_LINES}
        depth = labeled(block, DEPTH)
        reopened = re.findall(r"^Reopened:[ \t]*(.*?)[ \t]*$", block, re.M)
        if not all(reopened):
            raise Unsupported("a 'Reopened:' line is empty")
        if depth is not None and depth not in DEPTHS:
            raise Unsupported(f"the '{DEPTH}' line has {depth!r}, not one of {', '.join(DEPTHS)}")
        built = [
            f"build: {q(value[BUILD])}",
            f"plan: {q(value[PLAN])}",
            "inner:",
            f"  gates: {q(value[GATES])}",
            f"  tokens: {q(value[TOKENS])}",
            f"  depth: {q(depth) if depth else 'none'}",
            f"  reopened: [{', '.join(q(r) for r in reopened)}]",
            f"  fired: [{', '.join(q(e) for e in entries(block, RULES_CHECKED, r'[,;]'))}]",
            f"  declined: [{', '.join(q(e) for e in entries(block, DECLINED, ';'))}]",
            f"  nominated: [{', '.join(q(e) for e in entries(block, NOMINATED, ';', cited=False))}]",
            f"  procedure: [{', '.join(q(e) for e in entries(block, PROCEDURE, ';', cited=False))}]",
            f"  reproduced: {reproduced(block)}",
            f"  ripple: {ripple(block)}",
        ]
    line = ticket_line(body)
    ticket = ticket_key(repo, line) if line else "none"
    # A ticket in several pull requests: this one's part, and the criteria it claims.
    part = re.search(r"· part (\d+) of (\d+) · base: (\S+)", line) if line else None
    stack = f"{{part: {part.group(1)}, of: {part.group(2)}, base: {q(part.group(3))}}}" if part else "none"
    claims = labeled(body, "Claims:")
    claimed = "[" + ", ".join(q(c.strip()) for c in claims.split(",") if c.strip()) + "]" if claims else "none"
    author = pr["user"]["login"]

    reviewed = findings_reviews(reviews)
    parsed = [(th, parse_finding(th)) for th in threads]
    # The record feeds the counts: a finding whose key cannot be read would drop its rule's firing.
    for th, f in parsed:
        if f and f["unreadable"]:
            raise Unsupported(f"thread {th['id']} is a finding with no readable 'key:' line")
    findings = [f for _, f in parsed if f and f["key"]]
    for f in findings:
        adjudicate(f, author, judged.get(f["thread"]))
        # The findings review a thread belongs to is the first one submitted after it was opened.
        f["review"] = next(
            (i for i, (r, _) in enumerate(reviewed) if when(r["submitted_at"]) >= f["created"]),
            len(reviewed) - 1,
        )

    if not pr.get("merged_at"):
        raise Unsupported("no 'merged_at' on the pull request: a record is of a merged pull request")
    # The UTC day, as the harvest's `merged:>=<date>` search qualifier compares it.
    merged = when(pr["merged_at"]).astimezone(timezone.utc).date().isoformat()
    if reviewed:
        if standards_sha is None:
            standards_sha = next((s for s in reversed([standards_line(r) for r, _ in reviewed]) if s), None)
        if standards_sha is None:
            raise Unsupported("no --standards-sha and no 'standards: <sha>' line in a findings review")
        head, date = reviewed[-1][1], when(reviewed[0][0]["submitted_at"])
    else:
        # With no findings review, the first review is the first thing a reviewer said.
        said = [c["created_at"] for th in threads for c in th["comments"] if reviewer(c["author"], author)]
        said += [r["submitted_at"] for r in listed if reviewer(r["user"]["login"], author)]
        said += [c["created_at"] for c in issue_comments if reviewer(c["user"]["login"], author)]
        # The author's own review: a thread they opened in their own words.
        said += [th["comments"][0]["created_at"] for th, f in parsed if f is None and th["comments"][0]["author"] == author and answerable(th["comments"][0], author)]
        if not said:
            raise Unsupported(
                "no findings review, no thread the author opened in their own words and nothing a reviewer said"
                " in a thread, a review summary or a conversation comment: nothing was reviewed"
            )
        standards_sha = standards_sha or "none"
        head = pr.get("merge_commit_sha") or pr["head"]["sha"]
        date = min(when(s) for s in said)
    date = date.astimezone().date().isoformat()
    pointers = sorted((pointer(th, author, f, judged.get(th["id"])) for th, f in parsed if not (f and f["key"])), key=lambda t: t["created"])

    answered = [f for f in findings if f["state"] == "answered"]
    # A Discuss is open, so its author settled nothing.
    adjudicators = list(dict.fromkeys(f["adjudicator"] for f in answered if f.get("verdict") != "discuss"))

    out = [
        f"contract: {RECORD_CONTRACT}",
        f"pr: {pr['number']}",
        f"ticket: {ticket}",
        f"stack: {stack}",
        f"claims: {claimed}",
        f"branch: {pr['head']['ref']}",
        f"head: {head[:7]}",
        f"date: {date}",
        f"merged: {merged}",
        f"standards_sha: {standards_sha}",
        # The repository whose profile the review ran under, by name.
        f"profile: {repo.rstrip('/').split('/')[-1]}",
        f"adjudicated_by: {', '.join(adjudicators) or 'none'}",
        *built,
        f"author: {author}",
    ]

    # A round is a delta: the findings of the reviews since the previous round's, not every
    # earlier review again.
    rounds, since = [], 0
    for i in range(1, len(reviewed)):
        if reviewed[i][1] == reviewed[i - 1][1]:
            continue
        sent = [f for f in answered if since <= f["review"] < i and f["severity"] != "question"]
        since = i
        rounds.append(
            [
                f"  - round: {len(rounds) + 1}",
                f"    commits: {reviewed[i - 1][1][:7]}..{reviewed[i][1][:7]}",
                f"    sent_back_by: [{', '.join(f['key'] for f in sent if f['verdict'] == 'agree')}]",
                f"    applied: {sum(f['verdict'] == 'agree' for f in sent)}",
                f"    declined: {sum(f['verdict'] == 'disagree' for f in sent)}",
            ]
        )
    out.append("rework_rounds:" if rounds else "rework_rounds: []")
    for r in rounds:
        out.extend(r)

    # Every cited finding is recorded, settled or not, so a rule nobody answers shows as unanswered
    # firings rather than fewer firings.
    recorded = [f for f in findings if f["severity"] != "question"]
    out.append("findings:" if recorded else "findings: []")
    for f in recorded:
        out += [
            f"  - key: {q(f['key'])}",
            f"    severity: {f['severity']}",
            f"    at: {q(f['at'])}",
            f"    thread: {f['thread']}",
            f"    verdict: {f['verdict'] if f['state'] == 'answered' else f['state']}",
        ]
        out += judged_lines(f.get("judged"), f.get("unclear", ""))
        if f["state"] == "unparsed":
            out.append(f"    line: {q(f['line'])}")
        if "reason" in f:
            out.append(f"    reason: {q(f['reason'])}")
        if "why" in f:
            out.append(f"    why: {q(f['why'])}")
        if f["state"] == "answered" and f["verdict"] != "discuss":
            out.append(f"    by: {f['adjudicator']}")
        if "contested" in f:
            out.append("    contested: true")
            out.append("    lines:")
            out += [f"      - {q(line)}" for line in f["contested"]]

    asked = [f for f in findings if f["severity"] == "question"]
    out.append("questions:" if asked else "questions: []")
    for f in asked:
        out += [
            f"  - q: {q(f['title'])}",
            f"    key: {q(f['key'])}",
            f"    at: {q(f['at'])}",
            f"    thread: {f['thread']}",
            f"    a: {q(f['answer'])}" if f["state"] == "answered" else "    unanswered: true",
        ]

    out.append("threads:" if pointers else "threads: []")
    for t in pointers:
        out += [
            f"  - thread: {t['thread']}",
            f"    by: {t['by']}",
            f"    authorship: {t['authorship']}",
            *([f"    severity: {t['severity']}"] if t["severity"] else []),
            f"    at: {q(t['at'])}",
            f"    opened: {t['created'].astimezone().date().isoformat()}",
            f"    resolved: {str(t['resolved']).lower()}",
            f"    outdated: {str(t['outdated']).lower()}",
            f"    replies: {t['replies']}",
            f"    verdict: {t['verdict']}",
            *judged_lines(t["judged"], t["unclear"]),
        ]
        if t["verdict"] == "unparsed":
            out.append(f"    line: {q(t['line'])}")
        if t["reason"]:
            out.append(f"    reason: {q(t['reason'])}")
        if t["answer"]:
            out.append(f"    a: {q(t['answer'])}")

    out += conversation(listed, issue_comments)

    report = []
    for f in findings:
        if f["state"] == "answered":
            continue
        detail = {"unparsed": f"first line: {f.get('line', '')}", "unanswered": f.get("why", "no reply from a person")}
        detail["contested"] = " | ".join(f.get("contested", []))
        said = "unparsed label" if f["severity"] == "unparsed" else f["state"]
        report.append(f"{said}: {f['thread']} {f['key']} ({detail[f['state']]})")
    report += [
        f"unparsed{' label' if t['severity'] == 'unparsed' else ''}: {t['thread']} (first line: {t['line']})"
        for t in pointers
        if t["verdict"] == "unparsed"
    ]
    return out, report


def judged_lines(judged: dict | None, unclear: str) -> list[str]:
    """A record entry's lines saying its verdict was judged from a reply's words, or could not be."""
    if judged:
        return ["    judged: true", f"    basis: {q(judged['basis'])}", *(["    done: true"] if judged["done"] else [])]
    return [f"    basis: {q(unclear)}"] if unclear else []


def read_text(path: Path) -> str:
    """A dump file's text; Unsupported, naming the file, when it cannot be read."""
    try:
        return path.read_text()
    except OSError as e:
        raise Unsupported(f"{path} cannot be read: {e.strerror}") from e


def read_json(path: Path):
    """A dump file's JSON; Unsupported, naming the file, when it cannot be read or is not JSON."""
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as e:
        raise Unsupported(f"{path} is not JSON: {e}") from e


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pr", type=Path, required=True, help="pull_request_read get, as JSON")
    p.add_argument("--reviews", type=Path, required=True, help="pull_request_read get_reviews, as JSON")
    p.add_argument("--comments", type=Path, required=True, help="pull_request_read get_review_comments, as JSON")
    p.add_argument("--issue-comments", type=Path, required=True, help="pull_request_read get_comments, the conversation comments, as JSON")
    p.add_argument("--body", type=Path, required=True, help="the pull request body")
    p.add_argument("--repo", required=True, help="owner/name, checked against the reviews")
    p.add_argument("--out", type=Path, help="the record to write; refused with --state")
    p.add_argument("--state", action="store_true", help="print where the pull request stands and write nothing")
    p.add_argument("--standards-sha", help="the standards/ sha the reviewer ran against")
    p.add_argument("--undecided", action="store_true", help="print, as JSON, the threads the words leave open, and write nothing")
    p.add_argument("--judged", type=Path, help="pr-reader's judgments of the --undecided threads, as JSON")
    args = p.parse_args(argv)
    if args.undecided and (args.state or args.out or args.judged):
        p.error("--undecided is refused with --state, --out and --judged")
    if args.undecided:
        args.state = True
    elif args.state and args.out:
        p.error("--out is refused with --state, which writes nothing")
    if not args.state and not args.out:
        p.error("--out is required unless --state is given")

    try:
        comments = read_json(args.comments)
        threads = comments["review_threads"] if isinstance(comments, dict) else comments
        given = read_json(args.pr).get("user")
        author = given.get("login") if isinstance(given, dict) else None
        if not author:
            raise Unsupported("the pull request has no 'user.login'")
        if args.undecided:
            print(json.dumps(undecided(threads, author), indent=1))
            return 0
        judged = read_judged(read_json(args.judged), undecided(threads, author)) if args.judged else None
        if args.state:
            lines = state(
                read_json(args.pr),
                read_json(args.reviews),
                threads,
                read_text(args.body),
                args.repo,
                judged,
            )
            print("\n".join(lines))
            return 0
        lines, report = build(
            read_json(args.pr),
            read_json(args.reviews),
            threads,
            read_text(args.body),
            args.repo,
            args.standards_sha,
            issue_comments=read_json(args.issue_comments),
            judged=judged,
        )
    except Unsupported as e:
        print(f"record.py: {e}", file=sys.stderr)
        return 1
    args.out.write_text("\n".join(lines) + "\n")
    for line in report:
        print(line, file=sys.stderr)
    labels = sum(line.startswith("unparsed label: ") for line in report)
    print(f"wrote {args.out}: {len(report)} finding(s) unsettled, {labels} label(s) unparsed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
