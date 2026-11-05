#!/usr/bin/env python3
"""Count verdicts per rule over a log/ directory of review records, for revise step 1.

Per rule: firings, agrees, disagrees, discusses, unanswered findings (unanswered and unparsed
together), unlabeled findings (`severity: unparsed`, whose severity label the record could not
read, so whose replies were never read), open contests (verdict `contested`), settled contests
(`contested: true` beside a verdict), and the corrections the `correction-*.yaml` records name
and the notes the `note-*.yaml` records name, both a count, never evidence. Firings count every
finding, an unlabeled one included; the unanswered, unlabeled and open-contest columns never
enter a rate, and the unanswered share is over the firings less the unlabeled. A rule is the citation a
finding key starts with: `R-012`, `D-008@my_repo`, `term/T-010`; any other key counts under
its first segment (`ticket`, `other`, `test`). The older verdict words in `pr-0066.yaml` map to
the current three: accepted to agree, declined to disagree, escalated to discuss.

A `distinct-prs-agreed` column counts the distinct records, one per pull request, in which a
finding citing the rule was answered agree, whoever wrote the pull request or the reply.

`--ledger <review-rules.md>` gives one row per `### R-NNN` heading in the repository's ledger,
or with `--repo <name>` per rule that applies to that repository, its `repos:` line naming it or
absent, zeros included, with its `status` and `since` read from its status line (`tier: … · status: … ·
since: …`, bold allowed around the status); a cited key the ledger does not hold, such as a
decision, a term or a `test/` key, still gets a row, its status `-`. A heading with no status
line is an error. With `--ledger` a third table, "expiry", gives each ledger rule its
`last-fired`, the `merged:` day of the newest record whose findings or `inner.fired` cite it;
`checked-since-admitted`, the checked records merged on or after the first day of its `since:`
month; and `checked-since-fired`, the checked records merged after `last-fired`, or since
admission when it never fired. A record is checked when the rules were run on its pull request: it
has a findings review (`standards_sha:` other than `none`), a build (`inner:` other than `none`),
or a finding that cites a rule. A pull request nothing checked could not have fired a rule, so it
ages none. A `since:` that is not `YYYY-MM` or `YYYY-MM-DD` is an error.

A record is placed in time by its `merged:` line, the day its pull request merged; `date:` is
its first review and places nothing. `--since YYYY-MM-DD` prints two tables, "since <date>" over
the records merged on or after it and the corrections and notes whose `date:` is on or after it,
then "all records". A record whose `contract:` is 3 or more, or that has a `merged:` line, must
read `merged: YYYY-MM-DD`, or it is an error. A record with no `merged:` line and a lower
contract, or none, predates the field. The harvest rewrites every record merged in a window at
the current contract, so such a record merged before any window the revision reads: it is left
out of the window table and of the expiry counts, named on a line of its own whenever either is
printed, and counted in "all records". A correction with no `date:`, `ids:`, `kind:`, `source:`, `by:` or `clause:`, or a note
with no `date:`, `ids:`, `kind:` or `by:`, is an error whatever its date.

Pull request numbers on stdin, one per line, are the merged pull requests the window should
have records for; the ones with no `pr-NNNN.yaml` are listed, and one whose record predates
`merged:` is an error, since the harvest should have rewritten it. Stdlib only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

WORDS = {"agree": "agree", "accepted": "agree", "disagree": "disagree", "declined": "disagree"}
WORDS |= {"discuss": "discuss", "escalated": "discuss"}
WORDS |= {"unanswered": "unanswered", "unparsed": "unanswered", "contested": "open-contest"}
COLUMNS = (
    "firings", "agree", "disagree", "discuss", "unanswered", "unlabeled", "open-contest", "contested", "distinct-prs-agreed",
    "corrections", "notes",
)


def rule_of(key: str) -> str:
    m = re.match(r"(R-\d+|D-\d+(?:@[\w-]+)?|term/T-\d+)", key)
    return m.group(1) if m else key.split("/")[0]


def findings(text: str, name: str) -> list[dict]:
    """The findings section's items, each as its key, verdict and contested flag; a finding with
    `severity: unparsed` has the verdict `unlabeled`, whatever its verdict line says."""
    m = re.search(r"^findings:(.*?)(?=^\w|\Z)", text, re.M | re.S)
    if not m:
        return []
    # A finding starts at the first item's indent; a deeper `- ` is a list inside one, as a
    # contested finding's `lines:`.
    first = re.search(r"^( *)- ", m.group(1), re.M)
    if not first:
        return []
    items = []
    for item in re.split(rf"^{first.group(1)}- ", m.group(1), flags=re.M)[1:]:
        key = re.search(r"\bkey:\s*\"?([^,\s}\"]+)", item)
        verdict = re.search(r"\bverdict:\s*(\w+)", item)
        if not key or not verdict or verdict.group(1) not in WORDS:
            raise ValueError(f"{name}: a finding without a readable key and verdict: {item.strip()[:80]}")
        unlabeled = bool(re.search(r"^\s*severity:\s*unparsed\s*$", item, re.M))
        items.append(
            {
                "rule": rule_of(key.group(1)),
                "verdict": "unlabeled" if unlabeled else WORDS[verdict.group(1)],
                # A settled contest; an open one is its verdict, counted under open-contest.
                # Quoted text, such as a judged verdict's basis, is no field.
                "contested": WORDS[verdict.group(1)] != "open-contest"
                and bool(re.search(r"\bcontested:\s*true\b", re.sub(r'"(?:[^"\\]|\\.)*"', '""', item))),
            }
        )
    return items


# The record contract that added `merged:`.
MERGED_CONTRACT = 3


def dated(text: str, name: str, since: datetime.date | None) -> bool:
    """Whether a correction or note falls in the window: always without one, else by its `date:`."""
    if since is None:
        return True
    m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})\s*$", text, re.M)
    if not m:
        raise ValueError(f"{name}: no 'date: YYYY-MM-DD' line, so --since cannot place it")
    return datetime.date.fromisoformat(m.group(1)) >= since


def merged_on(text: str, name: str) -> datetime.date | None:
    """A record's `merged:` day, or None for a record that predates the field."""
    m = re.search(r"^merged:\s*(\d{4}-\d{2}-\d{2})\s*$", text, re.M)
    if m:
        return datetime.date.fromisoformat(m.group(1))
    contract = re.search(r"^contract:\s*(\d+)", text, re.M)
    if re.search(r"^merged:", text, re.M) or (contract and int(contract.group(1)) >= MERGED_CONTRACT):
        raise ValueError(f"{name}: no 'merged: YYYY-MM-DD' line, which a record of contract {MERGED_CONTRACT} or later carries")
    return None


def records(log: Path) -> list[tuple[Path, str, datetime.date | None]]:
    """Each `pr-NNNN.yaml` with its text and its `merged:` day."""
    return [(path, text, merged_on(text, path.name)) for path in sorted(log.glob("pr-*.yaml")) for text in [path.read_text()]]


def unplaced(log: Path) -> list[str]:
    """The records that predate `merged:`, which no window or expiry count places."""
    return [path.name for path, _, day in records(log) if day is None]


def fired(text: str) -> set[str]:
    """The rules a record's `inner.fired` names, the build's own firings."""
    m = re.search(r"^  fired:\s*(\[.*\])\s*$", text, re.M)
    return {rule_of(entry) for entry in json.loads(m.group(1))} if m else set()


def count(log: Path, since: datetime.date | None = None) -> dict[str, Counter]:
    table: dict[str, Counter] = defaultdict(Counter)
    agreed: dict[str, set[str]] = defaultdict(set)
    for path, text, day in records(log):
        if since is not None and (day is None or day < since):
            continue
        for f in findings(text, path.name):
            row = table[f["rule"]]
            row["firings"] += 1
            row[f["verdict"]] += 1
            row["contested"] += f["contested"]
            if f["verdict"] == "agree":
                agreed[f["rule"]].add(path.name)
    for rule, prs in agreed.items():
        table[rule]["distinct-prs-agreed"] = len(prs)
    required = {"correction-*.yaml": ("date", "kind", "source", "by", "clause"), "note-*.yaml": ("date", "kind", "by")}
    for pattern, column in (("correction-*.yaml", "corrections"), ("note-*.yaml", "notes")):
        for path in sorted(log.glob(pattern)):
            text = path.read_text()
            m = re.search(r"^ids:\s*\[(.*?)\]", text, re.M)
            if not m or not m.group(1).strip():
                raise ValueError(f"{path.name}: no 'ids: [...]' line")
            for field in required[pattern]:
                if not re.search(rf"^{field}:\s*\S", text, re.M):
                    raise ValueError(f"{path.name}: no '{field}:' line")
            if not dated(text, path.name, since):
                continue
            for rule in {rule_of(i.strip()) for i in m.group(1).split(",")}:
                table[rule][column] += 1
    return table


def missing(log: Path, merged: list[int]) -> list[int]:
    return [n for n in merged if not (log / f"pr-{n:04d}.yaml").exists()]


def entries(path: Path) -> dict[str, dict]:
    """Each `### R-NNN` block of the ledger at `path`, as `parse_entries` reads it."""
    return parse_entries(path.read_text(), path.name)


def unfenced(text: str) -> str:
    """`text` with every line inside a code fence, its fence lines included, blanked to spaces of
    the same length, so a heading or a field line shown in an example is never read as one and
    every offset still points into `text`. A fence closes on a line opening with its own
    character, as long as its opener or longer."""
    out, fence = [], None
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        m = re.match(r"(`{3,}|~{3,})", body)
        if fence is None and m:
            fence = m.group(1)
        elif fence is not None and m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
            fence = None
        elif fence is None:
            out.append(line)
            continue
        out.append(" " * len(body) + line[len(body):])
    return "".join(out)


def parse_entries(text: str, name: str) -> dict[str, dict]:
    """Each `### R-NNN` block of a ledger's text: its `title`, `tier` and `status` (bold stripped), `since`, `evidence` (the
    status line's text after `evidence:`), `text` (the block whole) and, when present, `scope`,
    `example` and `repos`, from the lines that open with them. A block ends at the next heading of level one
    to three, so a ledger's other sections never join its last rule. A block with no status line
    is refused."""
    out = {}
    for m in re.finditer(r"^### (R-\d+)\b[ \t]*(?:·[ \t]*)?([^\n]*)\n(.*?)(?=^#{1,3} |\Z)", unfenced(text), re.M | re.S):
        rid, title, body = m.group(1), m.group(2).strip(), m.group(3)
        status = re.search(r"\bstatus:\s*\**([\w-]+)\**", body)
        if not status:
            raise ValueError(f"{name}: {rid} has no status line")
        since = re.search(r"\bsince:\s*([\d-]+)", body)
        tier = re.search(r"\btier:\s*\**([^\s·*]+)\**", body)
        evidence = re.search(r"\bevidence:\s*([^\n]*)", body)
        entry = {
            "title": title,
            "tier": tier.group(1) if tier else "-",
            "status": status.group(1),
            "since": since.group(1) if since else "-",
            "evidence": evidence.group(1).strip() if evidence else "",
            "text": text[m.start() : m.end()],
        }
        for field in ("scope", "example", "repos"):
            line = re.search(rf"^{field}:[ \t]*(\S.*?)[ \t]*$", body, re.M)
            if line:
                entry[field] = line.group(1)
        out[rid] = entry
    return out


def repos(line: str) -> list[str] | None:
    """The repository names of a `repos:` line, `[<repo>, ...]`, lowercased; None when it is not
    one non-empty flow list of bare names."""
    m = re.fullmatch(r"\[([^\]]*)\]", line.strip())
    names = [n.strip().strip("'\"").lower() for n in m.group(1).split(",")] if m else []
    return names if names and all(re.fullmatch(r"[\w.-]+", n) for n in names) else None


def applies(entry: dict, repo: str | None) -> bool:
    """Whether a rule applies to `repo`: always with no `repos:` line or no repository given;
    otherwise when its line names it. A line that is not a list of names is refused."""
    if repo is None or "repos" not in entry:
        return True
    names = repos(entry["repos"])
    if names is None:
        raise ValueError(f"repos: {entry['repos']!r} is not a list of repository names such as [my_repo]")
    return repo.lower() in names


def ledger(path: Path, repo: str | None = None) -> dict[str, tuple[str, str]]:
    """Each `### R-NNN` heading's status and since, from its status line; with `repo`, only the
    rules that apply to it."""
    return {rid: (e["status"], e["since"]) for rid, e in entries(path).items() if applies(e, repo)}


def admitted(rule: str, since: str) -> datetime.date | None:
    """The first day of a ledger `since:` month, or the day itself; None for a rule with none."""
    if since == "-":
        return None
    try:
        return datetime.date.fromisoformat(since + "-01" if len(since) == 7 else since)
    except ValueError:
        raise ValueError(f"{rule}: since: {since!r} is not YYYY-MM or YYYY-MM-DD") from None


def checked(text: str) -> bool:
    """Whether the rules were run on a record's pull request: a findings review or a build."""
    return not (re.search(r"^standards_sha:\s*none\s*$", text, re.M) and re.search(r"^inner:\s*none\s*$", text, re.M))


def expiry(log: Path, rules: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str, str]]:
    """Each ledger rule's last-fired day, checked records since its admission and since it last fired."""
    placed = []
    for path, text, day in records(log):
        cited = {f["rule"] for f in findings(text, path.name)} | fired(text)
        if day and (checked(text) or cited):
            placed.append((day, cited))
    out = {}
    for rule, (_, since) in rules.items():
        start = admitted(rule, since)
        last = max((day for day, cited in placed if rule in cited), default=None)
        since_admitted = str(sum(day >= start for day, _ in placed)) if start else "-"
        since_fired = str(sum(day > last for day, _ in placed)) if last else since_admitted
        out[rule] = (last.isoformat() if last else "-", since_admitted, since_fired)
    return out


def aligned(rows: list[tuple[str, ...]]) -> str:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip() for row in rows)


def render(table: dict[str, Counter], rules: dict[str, tuple[str, str]] | None = None) -> str:
    head = ("rule", "status", "since", *COLUMNS) if rules is not None else ("rule", *COLUMNS)
    rows = [head]
    for r in sorted(set(table) | set(rules or {})):
        cells = [str(table.get(r, Counter())[c]) for c in COLUMNS]
        rows.append((r, *(rules.get(r, ("-", "-")) if rules is not None else ()), *cells))
    return aligned(rows)


def render_expiry(ages: dict[str, tuple[str, str, str]], rules: dict[str, tuple[str, str]]) -> str:
    head = ("rule", "status", "since", "last-fired", "checked-since-admitted", "checked-since-fired")
    return aligned([head, *((r, *rules[r], *ages[r]) for r in sorted(rules))])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("log", type=Path, help="a standards/<repo>/log/ directory of records")
    p.add_argument("--ledger", type=Path, help="the repository's standards/review-rules.md")
    p.add_argument("--repo", help="with --ledger, only the rules whose repos: line names this repository, or that have none")
    p.add_argument("--since", type=datetime.date.fromisoformat, help="YYYY-MM-DD: also count the records on or after it")
    args = p.parse_args(argv)
    if args.repo and not args.ledger:
        p.error("--repo names whose rules to keep, so it takes --ledger")
    if not args.log.is_dir():
        print(f"ratchet_counts.py: {args.log} is not a directory", file=sys.stderr)
        return 1
    merged = None if sys.stdin.isatty() else [int(n) for n in sys.stdin.read().split()]
    try:
        rules = ledger(args.ledger, args.repo) if args.ledger else None
        old = unplaced(args.log)
        stale = [name for name in old if merged and int(re.search(r"\d+", name).group()) in merged]
        if stale:
            raise ValueError(f"{', '.join(stale)}: merged in the window but predates 'merged:'; the harvest did not rewrite it")
        if args.since:
            print(f"since {args.since.isoformat()}\n{render(count(args.log, args.since), rules)}\n")
        if args.since or rules is not None:
            print(f"records with no merged: line, in no window or expiry count: {', '.join(old) or 'none'}\n")
        if args.since:
            print("all records")
        print(render(count(args.log), rules))
        if rules is not None:
            print(f"\nexpiry\n{render_expiry(expiry(args.log, rules), rules)}")
    except (ValueError, OSError) as e:
        print(f"ratchet_counts.py: {e}", file=sys.stderr)
        return 1
    if merged is not None:
        gone = missing(args.log, merged)
        print(f"\nrecords missing for merged pull requests: {', '.join(f'#{n}' for n in gone) or 'none'} ({len(gone)} of {len(merged)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
