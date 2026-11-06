#!/usr/bin/env python3
"""Check a revision's clusters of guidance and print each with its people, pull requests and quotes.

The driver groups the guidance tally's lines by the principle they state, across pull requests
and in whatever words (`skills/revise/harvest.md`, "Clusters"), and writes the grouping as JSON
(`docs/contracts.md`, "The guidance clusters"):

    {"clusters": [{"id": "C1", "kind": "<its destination>", "principle": "<one sentence>", "items": ["s1-0", ...],
                   "notes": ["<other evidence, one line each>", ...],
                   "held": "<a held candidate's title in the ledger>" | null}, ...]}

Given that file with --clusters, the tally's printout with --tally (what `guidance_tally.py`
printed, saved to a file), for a standard covering several repositories each other repository's
tally with --tally-from <repo>=<file>, its keys read `<repo>:s<n>-<i>` and its pull requests
`<repo>/pr-NNNN`, as a note and a `prs:` line name them too, with this repository's name in --repo,
a `prs:` entry `<--repo>/pr-NNNN` read as this repository's and a note naming any other refused, and, when a cluster names a held candidate, the ledger with --ledger,
this script refuses, one `refused · <where> · <why>` line per fault and exit 1:

- a tally whose closing `items:` line is missing or counts its words otherwise than its lines, or a
  line with too few cells;
- a cluster without exactly the keys above, an `id` not `C<n>` or given twice, a `kind` that is not
  one of the guidance items' kinds or, in a cluster with tally lines, the kind of none of its
  people's lines, its `admit` and `hold` lines, or of none of its lines when it has only `support`,
  a blank principle,
  a note not `pr-NNNN · <login> · <human|ai-drafted|bot> · <text>`, an analyst's ask, or
  `pasted <file> · <name> · <text>`, a pasted note, or neither an item nor a note;
- a key that is not one of the tally's `admit`, `hold` or `support` lines, or one in two clusters,
  and any such line in no cluster: every line joins exactly one, a cluster of one included;
- a `held` title the ledger's `## Candidates below the criteria` section does not hold, as a
  heading or as the bold title a bullet opens with, a trailing full stop aside, or one given with
  no --ledger.

Otherwise it prints, per cluster in the file's order, `cluster · <id> · <kind> · admit <n> · hold <n> ·
support <n> · prs <n> · people <n> · <principle>`, its kind the destination `harvest.md`'s
"Destinations" sends it to. `admit` counts its `admit` lines of that kind alone, since only those
admit it, and its notes that carry a nomination the extractor took nothing from; an `admit` line of
another kind counts under `hold`. Each tally `nominated` line `not extracted` must be such a note,
`pr-NNNN · <login> · human · nominated <comment id>: <its text>`, in exactly one cluster, and every
such note a `not extracted` line, or it is refused, so no nomination is dropped or invented. Its pull requests are those a person asked on, of
its `admit` and `hold` lines and its `human` notes, which the Recurring ask Dial counts, and its
people the authors of those and of its pasted notes, an agent's or a bot's words never counting
for either, then `prs · <id> · pr-NNNN, ...`, `people ·
<id> · <login>, ...`, with --repo `repos · <id> · <repo>, ...`, the repositories its pull
requests are in, `priority · <id> · <low|medium|high> · <n> pull request(s)`, at the
Recurring ask Dial's counts in `standards/dials.md`, of its pull requests and, when it has
people, those its continued held candidate's `prs:` line names, accumulated across revisions, and
those of its `support` lines, an agent's finding the author changed as asked, then `asked · <id> ·
pr-NNNN, ...` or `none`, the pull requests it counted, each `<repo>/pr-NNNN` with --repo,
which `apply` carries into the candidate's `prs:` line, `held · <id> · <title>` when it joins one, `note · <id> · <note>` for each
note, and up to three `said · <id> ·
"<quote>" — <author>, <url>` lines: its people's words before an agent's, `admit` before `hold`,
each from a pull request and a person not yet quoted while one is left, then the rest in that
order. `prs · <id> · none` and `people · <id> · none` when it has none. A note's pull request is
`pr-` and at least four digits, as the tally prints it.
A last line reads `clusters: <n> · lines: <n>`. Exits 0. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORDS = ("admit", "hold", "support")
HELD = "## Candidates below the criteria"
KEYS = {"id", "kind", "principle", "items", "notes", "held"}
DIALS = Path(__file__).resolve().parents[1] / "standards" / "dials.md"
PRIORITY = re.compile(r"^\| Recurring ask \|.*?(\d+) low, (\d+) medium, (\d+) or more high", re.M)
KINDS = ("rule", "agent-guidance", "data-convention", "process", "decision", "tool-config", "exemplar",
         "review-calibration", "open-question")


class Refused(Exception):
    """Input the clusters cannot be checked against."""


def tally_lines(text: str, repo: str = "") -> dict[str, dict]:
    """The tally's clustered lines by key: word, pr, author, url and quote, each read by its
    place, the quote last, so a `·` in it splits nothing. Refused unless its last line counts what
    it lists."""
    out, counts, summary = {}, {w: 0 for w in (*WORDS, "covered")}, None
    for line in text.splitlines():
        cells = line.split(" · ")
        if cells[0] in counts:
            url_at = 6 if cells[0] == "support" else 7
            if len(cells) <= url_at + 1:
                raise Refused(f"a tally line with too few cells: {line[:80]}")
            counts[cells[0]] += 1
            if cells[0] != "covered":
                out[f"{repo}:{cells[1]}" if repo else cells[1]] = {
                    "word": cells[0], "pr": f"{repo}/{cells[2]}" if repo else cells[2], "author": cells[4], "kind": cells[5], "url": cells[url_at],
                                 "quote": " · ".join(cells[url_at + 1:])}
        elif line.startswith("items: "):
            summary = dict(re.findall(r"(\w+): (\d+)", line))
    if summary is None:
        raise Refused("the tally has no closing `items:` line, so it may be cut short")
    gone = [w for w, n in counts.items() if int(summary.get(w, -1)) != n]
    if gone:
        raise Refused(f"the tally's closing line counts {', '.join(gone)} otherwise than its lines")
    return out


PR = r"(?:[\w.-]+/)?pr-\d{4,}"
NOTE = re.compile(rf"({PR}) · (\S+) · (human|ai-drafted|bot) · \S.*|pasted (\S+) · ([^·]+?) · \S.*")
NOMINATED = re.compile(rf"({PR}) · \S+ · human · nominated (\d+): (\S.*)")


def unextracted(text: str, repo: str = "") -> set[tuple[str, str, str]]:
    """The tally's nominations no item was taken from, as (pr-NNNN, comment id, text)."""
    out = set()
    for line in text.splitlines():
        cells = line.split(" · ")
        if cells[0] == "nominated" and len(cells) >= 7 and cells[4] == "not extracted":
            out.add((f"{repo}/{cells[1]}" if repo else cells[1], cells[2], " · ".join(cells[6:])))
    return out


def held_titles(ledger: str) -> dict[str, set[str]]:
    """The ledger's held candidates by title, each with the pull requests its `prs:` line names, the
    ones its people asked on (`docs/contracts.md`, "The ledger's held-candidates heading"): each
    `### ` heading under the line `## Candidates below the criteria`, and each bullet there at the
    line's start that opens with a bold title, `- **<title>**`, not a label ending `:`, a trailing
    full stop left off either. A `pr-NNNN` anywhere else in a candidate counts for nothing."""
    lines = ledger.splitlines()
    at = next((i for i, line in enumerate(lines) if line.rstrip() == HELD), None)
    if at is None:
        return {}
    out: dict[str, set[str]] = {}
    title = None
    for line in lines[at + 1:]:
        m = re.match(r"### (.+)", line) or re.match(r"[-*] \*\*([^*]*[^*:])\*\*", line)
        if m:
            title = m[1].strip().rstrip(".")
            out.setdefault(title, set())
        prs = re.match(r"\s*(?:[-*] )?prs: (.*)", line)
        if title is not None and prs:
            out[title] |= {f"{r}pr-{int(n):04d}" for r, n in re.findall(r"(?<![\w.-])((?:[\w.-]+/)?)pr-(\d+)\b", prs[1])}
    return out


def priorities() -> tuple[int, int, int]:
    """The Recurring ask Dial's pull request counts for low, medium and high priority."""
    m = PRIORITY.search(DIALS.read_text() if DIALS.is_file() else "")
    if not m:
        raise Refused(f"{DIALS} has no Recurring ask Dial reading `<n> low, <n> medium, <n> or more high`")
    return int(m[1]), int(m[2]), int(m[3])


def norm(pr: str) -> str:
    """A pull request as the tally names it: `pr-` and four digits at least, after any `<repo>/`."""
    repo, _, number = pr.rpartition("/")
    return f"{repo + '/' if repo else ''}pr-{int(number[3:]):04d}"


def check(clusters, lines: dict[str, dict], headings: dict[str, set[str]] | None,
          nominations: set[tuple[str, str, str]] = frozenset(), others: frozenset = frozenset(),
          this: str | None = None) -> list[str]:
    if not isinstance(clusters, dict) or set(clusters) != {"clusters"} or not isinstance(clusters["clusters"], list):
        return ["refused · clusters · not an object with a clusters list"]
    faults, seen, ids = [], {}, set()
    for n, c in enumerate(clusters["clusters"]):
        where = f"cluster {n}"
        if not isinstance(c, dict) or set(c) != KEYS:
            faults.append(f"refused · {where} · keys {sorted(c) if isinstance(c, dict) else c!r}, not {sorted(KEYS)}")
            continue
        where = f"cluster {c['id']!r}"
        if not isinstance(c["id"], str) or not re.fullmatch(r"C\d+", c["id"]) or c["id"] in ids:
            faults.append(f"refused · {where} · an id not C<n>, or given twice")
            continue
        ids.add(c["id"])
        if not isinstance(c["items"], list) or not all(isinstance(k, str) for k in c["items"]) \
                or not (c["held"] is None or isinstance(c["held"], str)):
            faults.append(f"refused · {where} · items not a list of keys, or held neither a title nor null")
            continue
        if not isinstance(c["principle"], str) or not c["principle"].strip():
            faults.append(f"refused · {where} · no principle")
        if c["kind"] not in KINDS:
            faults.append(f"refused · {where} · kind {c['kind']!r}, not one of {', '.join(KINDS)}")
        elif c["items"] and all(k in lines for k in c["items"]) and c["kind"] not in (
                {lines[k]["kind"] for k in c["items"] if lines[k]["word"] != "support"}
                or {lines[k]["kind"] for k in c["items"]}):
            faults.append(f"refused · {where} · kind {c['kind']}, which none of its lines is")
        notes_ok = isinstance(c["notes"], list) and all(isinstance(n, str) and NOTE.fullmatch(n) for n in c["notes"])
        if not notes_ok:
            faults.append(f"refused · {where} · notes are not each `pr-NNNN · <login> · <human|ai-drafted|bot> · "
                          f"<text>` or `pasted <file> · <name> · <text>`")
        if notes_ok:
            stray = sorted({m[1].split("/")[0] for m in map(NOTE.fullmatch, c["notes"]) if m[1] and "/" in m[1]} - others - {this})
            if stray:
                faults.append(f"refused · {where} · a note names {', '.join(stray)}, no repository given with --tally-from")
        if not isinstance(c["items"], list) or not (c["items"] or (notes_ok and c["notes"])):
            faults.append(f"refused · {where} · neither an item nor a note")
            continue
        for key in c["items"]:
            if key not in lines:
                faults.append(f"refused · {where} · {key!r} is no admit, hold or support line of the tally")
            elif key in seen:
                faults.append(f"refused · {where} · {key} is also in {seen[key]}")
            else:
                seen[key] = c["id"]
        if c["held"] is not None:
            if headings is None:
                faults.append(f"refused · {where} · joins a held candidate, and no --ledger was given")
            elif c["held"].rstrip(".") not in headings:
                faults.append(f"refused · {where} · no held candidate headed {c['held']!r} in the ledger")
    faults += [f"refused · {key} · in no cluster" for key in lines if key not in seen]
    noted = [(m[1], m[2], m[3]) for c in clusters["clusters"] if isinstance(c, dict) and isinstance(c.get("notes"), list)
             for m in (NOMINATED.fullmatch(n) for n in c["notes"] if isinstance(n, str)) if m]
    faults += [f"refused · nominated {cid} in {pr} · not extracted, and a note in {noted.count((pr, cid, t)) or 'no'} cluster"
               f"{'s' if noted.count((pr, cid, t)) > 1 else ''}, not one: {t}"
               for pr, cid, t in sorted(nominations) if noted.count((pr, cid, t)) != 1]
    faults += [f"refused · nominated {cid} in {pr} · a note no `not extracted` tally line names: {t}"
               for pr, cid, t in sorted(set(noted) - set(nominations))]
    return faults


def quotes(keys: list[str], lines: dict[str, dict]) -> list[dict]:
    rank = sorted(keys, key=lambda k: (lines[k]["word"] == "support", lines[k]["word"] != "admit"))
    chosen, prs, people = [], set(), set()
    for k in rank:
        if len(chosen) == 3:
            break
        if lines[k]["pr"] not in prs and lines[k]["author"] not in people:
            chosen.append(k)
            prs.add(lines[k]["pr"])
            people.add(lines[k]["author"])
    for k in rank:
        if len(chosen) < 3 and k not in chosen:
            chosen.append(k)
    return [lines[k] for k in chosen]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--clusters", type=Path, required=True)
    p.add_argument("--tally", type=Path, required=True)
    p.add_argument("--tally-from", action="append", default=[], metavar="REPO=FILE",
                   help="another covered repository's tally; repeatable")
    p.add_argument("--repo", help="this repository's name, needed with --tally-from")
    p.add_argument("--ledger", type=Path)
    args = p.parse_args(argv)
    try:
        clusters = json.loads(args.clusters.read_text())
        tally = args.tally.read_text()
        lines, nominations = tally_lines(tally), unextracted(tally)
        if args.tally_from and not args.repo:
            raise Refused("--tally-from needs --repo, this repository's name")
        for given in args.tally_from:
            repo, _, path = given.partition("=")
            if not re.fullmatch(r"[\w.-]+", repo) or not path or repo == args.repo:
                raise Refused(f"--tally-from {given!r} is not <another repository>=<its tally>")
            other = Path(path).read_text()
            lines.update(tally_lines(other, repo))
            nominations |= unextracted(other, repo)
        headings = held_titles(args.ledger.read_text()) if args.ledger else None
        _, medium, high = priorities()
    except (OSError, json.JSONDecodeError, Refused) as e:
        print(f"refused · input · {e}")
        return 1
    others = frozenset(given.partition("=")[0] for given in args.tally_from)
    if headings and args.repo:
        headings = {t: {p[len(args.repo) + 1:] if p.startswith(args.repo + "/") else p for p in prs}
                    for t, prs in headings.items()}
    if args.repo:
        clusters = {**clusters, "clusters": [
            {**c, "notes": [n.replace(f"{args.repo}/pr-", "pr-", 1) if n.startswith(f"{args.repo}/pr-") else n for n in c["notes"]]}
            if isinstance(c, dict) and isinstance(c.get("notes"), list) else c for c in clusters["clusters"]]} \
            if isinstance(clusters, dict) and isinstance(clusters.get("clusters"), list) else clusters
    faults = check(clusters, lines, headings, nominations, others, args.repo)
    if faults:
        print("\n".join(faults))
        return 1
    for c in clusters["clusters"]:
        keys = c["items"]
        admits = [k for k in keys if lines[k]["word"] == "admit" and lines[k]["kind"] == c["kind"]]
        noted = [n for n in c["notes"] if NOMINATED.fullmatch(n)]
        count = {"admit": len(admits) + len(noted), "hold": sum(lines[k]["word"] in WORDS[:2] for k in keys) - len(admits),
                 "support": sum(lines[k]["word"] == "support" for k in keys)}
        notes = [NOTE.fullmatch(n) for n in c["notes"]]
        prs = sorted({lines[k]["pr"] for k in keys if lines[k]["word"] != "support"}
                     | {norm(m[1]) for m in notes if m[3] == "human"})
        people = sorted({lines[k]["author"] for k in keys if lines[k]["word"] != "support"}
                        | {m[2] for m in notes if m[3] == "human"} | {m[5].strip() for m in notes if m[4]})
        print(f"cluster · {c['id']} · {c['kind']} · " + " · ".join(f"{w} {n}" for w, n in count.items())
              + f" · prs {len(prs)} · people {len(people)} · {c['principle']}")
        print(f"prs · {c['id']} · {', '.join(prs) or 'none'}")
        if args.repo:
            repos = sorted({pr.split("/")[0] if "/" in pr else args.repo for pr in prs})
            print(f"repos · {c['id']} · {', '.join(repos) or 'none'}")
        print(f"people · {c['id']} · {', '.join(people) or 'none'}")
        earlier = headings[c["held"].rstrip(".")] if c["held"] and people else set()
        asked = set(prs) | earlier | ({lines[k]["pr"] for k in keys if lines[k]["word"] == "support"} if people else set())
        level = "high" if len(asked) >= high else "medium" if len(asked) >= medium else "low"
        print(f"priority · {c['id']} · {level} · {len(asked)} pull request{'' if len(asked) == 1 else 's'}")
        qualified = sorted(p if "/" in p or not args.repo else f"{args.repo}/{p}" for p in asked)
        print(f"asked · {c['id']} · {', '.join(qualified) or 'none'}")
        if c["held"]:
            print(f"held · {c['id']} · {c['held']}")
        for note in c["notes"]:
            print(f"note · {c['id']} · {note}")
        for q in quotes(keys, lines):
            print(f'said · {c["id"]} · "{q["quote"]}" — {q["author"]}, {q["url"]}')
    print(f"clusters: {len(clusters['clusters'])} · lines: {len(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
