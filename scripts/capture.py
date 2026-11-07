#!/usr/bin/env python3
"""Keep each merged pull request's harvest in the standard's log, and restore a window of it.

`revise capture` harvests the window's merged pull requests between revisions, so that `prepare`
reads them from the log instead of harvesting a month at once (`docs/contracts.md`, "The
capture"). Each capture harvests the whole window again, one `pr-reader`, so a record and its
comment list take the replies posted since; the analysts and the extractor run only on the pull
requests `pending` names. Three commands:

`pending --log <log> --threads <dir>` prints `pr-NNNN` for each dump under --threads whose
`comment-list.json` differs from its capture's, or that has no capture with `items.json`: a pull
request new to the log, or one with comments since it was read.

`store --log <log> --report <file> --threads <dir> --from <day> --through <day> [--slices <slice>
...] [--not-read <n> ...] [--analysis <dir>]` files one capture run. The report is `pr-reader`'s
harvest block, saved to a file: its `merged: <n>` line must count its `pr-NNNN · created <day> ·
merged <day> · ...` lines, each of which is one pull request, and each gets `<log>/capture/pr-
NNNN/`, replaced: `harvest.txt`, its report line; from its dump under --threads, each of DUMP that
is there; `items.json`, its guidance items as a slice of one pull request; and `analysis.md`, its
`thread-analyst` block. A pull request `pending` names takes its block from `<analysis>/pr-NNNN.md`,
none when that is not there, and its items from the run's --slices, held first to
`guidance_check.py` with those pull requests' comment lists, every refusal printed and nothing
written; one --not-read names, from a slice the check still refused, gets no `items.json`. Any other
keeps the `items.json` and `analysis.md` its capture had. Then `<from> <through>` is appended to `<log>/capture/covered.txt`,
the days the harvest searched. Prints `captured pr-NNNN · items <n> | items kept <n> | not read[ ·
analysis[ kept]]` per pull request and `covered <from>..<through>`.

`load --log <log> --since <day> --through <day> --out <dir> --guidance <dir> [--merges <file>]`
restores the pull requests captured as merged from --since through --through: removes, then writes,
`<out>/threads/pr-NNNN/` with the DUMP files and `comment-list.json`, `<out>/records/pr-NNNN.yaml`
from `<log>/pr-NNNN.yaml`, `<out>/analysis/pr-NNNN.md`, and in --guidance, also emptied first, one
`slice-<n>.json` per pull request with items, n from 1 in number order. It prints the harvest
block `pr-reader` would have, `## harvest — <log> since <day>`, its count line and its pull
requests' lines, then `not read · pr-NNNN` for each with a comment list and no items. It refuses,
exit 2, writing nothing, with one line each: `uncovered · <from> · <to>` for days from --since
through --through no `covered.txt` line covers; `uncaptured · pr-NNNN · <day>` for a pull request
--merges (`window_merges.py`'s printout) lists as merged in those days that no capture holds,
whatever day its capture names; `failed · pr-NNNN · <day>` for a capture whose line is neither a
`record` nor `no review`, such as a fetch that failed; and `missing · pr-NNNN · <day>` for one whose
line says `record` and whose log has none. A log not yet made, before a repository's first capture,
holds no capture.

All exit 1 with the reason for an input that cannot be read: a day not YYYY-MM-DD, --from after
--through, a report whose count line is missing or miscounts, a `pr-` line not of the form, a pull
request named twice, for `store` a log directory that does not exist or a --not-read pull request
`pending` does not name, or a capture whose
`harvest.txt` is not a report line. Stdlib only.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import importlib.util
import io
import json
import re
import shutil
import sys
from pathlib import Path

LINE = re.compile(r"^pr-(\d{4,}) · created (\d{4}-\d{2}-\d{2}) · merged (\d{4}-\d{2}-\d{2}) · .+$")
COUNT = re.compile(r"^merged: (\d+); records written: \d+; labels unparsed: \d+$")
UNPARSED = re.compile(r" · record · (\d+) label\(s\) unparsed")
SETTLED = re.compile(r" · (record|no review)( · |$)")
MERGE = re.compile(r"^pr-(\d+) [0-9a-f]{40} (\d{4}-\d{2}-\d{2})\b")
DUMP = ("pr.json", "body.md", "comments.json", "reviews.json", "issue-comments.json", "judged.json")


class Refused(Exception):
    """An input the capture cannot be read from."""


def day(text: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(text)
    except ValueError as e:
        raise Refused(f"{text!r} is not a day, YYYY-MM-DD") from e


def report_lines(text: str) -> dict[int, str]:
    """The report's pull request lines by number, refused unless its count line counts them."""
    out: dict[int, str] = {}
    count = None
    for raw in text.splitlines():
        line = raw.strip()
        if COUNT.match(line):
            count = int(COUNT.match(line)[1])
        elif line.startswith("pr-"):
            m = LINE.match(line)
            if not m:
                raise Refused(f"a report line not `pr-NNNN · created <day> · merged <day> · ...`: {line[:80]}")
            if int(m[1]) in out:
                raise Refused(f"the report names pr-{m[1]} twice")
            out[int(m[1])] = line
    if count is None:
        raise Refused("the report has no `merged: <n>; records written: <n>; labels unparsed: <n>` line")
    if count != len(out):
        raise Refused(f"the report's count line says {count} merged and it lists {len(out)}")
    return out


def load_check():
    spec = importlib.util.spec_from_file_location("guidance_check", Path(__file__).with_name("guidance_check.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pending(log: Path, threads: Path) -> list[int]:
    """The dumps whose comment list is new to the log or changed since it was captured."""
    out = []
    for dump in sorted(threads.glob("pr-*")):
        new = dump / "comment-list.json"
        kept = log / "capture" / dump.name
        if new.is_file() and not ((kept / "items.json").is_file() and (kept / "comment-list.json").is_file()
                                  and json.loads((kept / "comment-list.json").read_text()) == json.loads(new.read_text())):
            out.append(int(dump.name[3:]))
    return out


def store(args) -> int:
    start, end = day(args.start), day(args.through)
    if start > end:
        raise Refused(f"--from {start} is after --through {end}")
    if not args.log.is_dir():
        raise Refused(f"{args.log} is not a directory: archive the records first, which makes it")
    prs = report_lines(args.report.read_text())
    unread = set(args.not_read)
    named = [n for n in pending(args.log, args.threads) if n in prs]
    stray = sorted(unread - set(named))
    if stray:
        raise Refused(f"--not-read names {', '.join(f'pr-{n:04d}' for n in stray)}, which `pending` does not")
    fresh = [n for n in named if n not in unread]
    lists = [args.threads / f"pr-{n:04d}" / "comment-list.json" for n in fresh]
    items: dict[int, list] = {n: [] for n in fresh}
    if lists or args.slices:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = load_check().main([*map(str, args.slices), "--comments", *map(str, lists)]) if args.slices else 1
        if code != 0:
            print(out.getvalue() or f"refused · --slices · none given for {', '.join(f'pr-{n:04d}' for n in fresh)}\n", end="")
            return 1
        for path in args.slices:
            for it in json.loads(path.read_text())["items"]:
                items[it["pr"]].append(it)
    root = args.log / "capture"
    root.mkdir(exist_ok=True)
    for n, line in sorted(prs.items()):
        dest, dump = root / f"pr-{n:04d}", args.threads / f"pr-{n:04d}"
        kept = {f: (dest / f).read_text() for f in ("items.json", "analysis.md") if (dest / f).is_file()}
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir()
        (dest / "harvest.txt").write_text(line + "\n")
        for f in (*DUMP, "comment-list.json"):
            if (dump / f).is_file():
                shutil.copyfile(dump / f, dest / f)
        said = ""
        if n in items:
            read = len(json.loads((dump / "comment-list.json").read_text())["comments"])
            (dest / "items.json").write_text(json.dumps({"prs": [n], "comments_read": read, "items": items[n]},
                                                        ensure_ascii=False, indent=1) + "\n")
            said = f" · items {len(items[n])}"
        elif n in unread:
            said = " · not read"
        elif "items.json" in kept and (dest / "comment-list.json").is_file():
            (dest / "items.json").write_text(kept["items.json"])
            said = f" · items kept {len(json.loads(kept['items.json'])['items'])}"
        block = args.analysis / f"pr-{n:04d}.md" if args.analysis and n in named else None
        if block and block.is_file():
            shutil.copyfile(block, dest / "analysis.md")
            said += " · analysis"
        elif n not in named and "analysis.md" in kept:
            (dest / "analysis.md").write_text(kept["analysis.md"])
            said += " · analysis kept"
        print(f"captured pr-{n:04d}{said}")
    with (root / "covered.txt").open("a") as f:
        f.write(f"{start} {end}\n")
    print(f"covered {start}..{end}")
    return 0


def covered(root: Path) -> list[tuple[datetime.date, datetime.date]]:
    path = root / "covered.txt"
    spans = []
    for line in (path.read_text().splitlines() if path.is_file() else []):
        if line.strip():
            if len(line.split()) != 2:
                raise Refused(f"{path}: {line!r} is not `<from> <through>`")
            a, b = map(day, line.split())
            spans.append((a, b))
    return sorted(spans)


def gaps(spans, start: datetime.date, end: datetime.date) -> list[tuple[datetime.date, datetime.date]]:
    """The runs of days from start through end that no span covers."""
    out, at = [], start
    for a, b in spans:
        if b < at:
            continue
        if a > at:
            out.append((at, min(end, a - datetime.timedelta(days=1))))
        at = max(at, b + datetime.timedelta(days=1))
        if at > end:
            break
    if at <= end:
        out.append((at, end))
    return [g for g in out if g[0] <= g[1]]


def load(args) -> int:
    start, end = day(args.since), day(args.through)
    if start > end:
        raise Refused(f"--since {start} is after --through {end}")
    root = args.log / "capture"
    held: dict[int, tuple[str, datetime.date, Path]] = {}
    for dest in sorted(root.glob("pr-*")) if root.is_dir() else []:
        line = (dest / "harvest.txt").read_text().strip() if (dest / "harvest.txt").is_file() else ""
        m = LINE.match(line)
        if not m:
            raise Refused(f"{dest / 'harvest.txt'} is not a harvest report line")
        held[int(m[1])] = (line, day(m[3]), dest)
    captured = {n: v for n, v in held.items() if start <= v[1] <= end}
    faults = [f"uncovered · {a} · {b}" for a, b in gaps(covered(root), start, end)]
    if args.merges:
        for m in map(MERGE.match, args.merges.read_text().splitlines()):
            if m and start <= day(m[2]) <= end and int(m[1]) not in held:
                faults.append(f"uncaptured · pr-{int(m[1]):04d} · {m[2]}")
    for n, (line, merged, _) in sorted(captured.items()):
        if not SETTLED.search(line):
            faults.append(f"failed · pr-{n:04d} · {merged}")
        elif " · record" in line and not (args.log / f"pr-{n:04d}.yaml").is_file():
            faults.append(f"missing · pr-{n:04d} · {merged}")
    if faults:
        print("\n".join(faults))
        return 2
    for sub in ("threads", "records", "analysis"):
        shutil.rmtree(args.out / sub, ignore_errors=True)
        (args.out / sub).mkdir(parents=True)
    shutil.rmtree(args.guidance, ignore_errors=True)
    args.guidance.mkdir(parents=True)
    slices, unread = 0, []
    for n, (line, _, dest) in sorted(captured.items()):
        name = f"pr-{n:04d}"
        (args.out / "threads" / name).mkdir()
        for f in (*DUMP, "comment-list.json"):
            if (dest / f).is_file():
                shutil.copyfile(dest / f, args.out / "threads" / name / f)
        if (args.log / f"{name}.yaml").is_file():
            shutil.copyfile(args.log / f"{name}.yaml", args.out / "records" / f"{name}.yaml")
        if (dest / "analysis.md").is_file():
            shutil.copyfile(dest / "analysis.md", args.out / "analysis" / f"{name}.md")
        if (dest / "items.json").is_file():
            slices += 1
            shutil.copyfile(dest / "items.json", args.guidance / f"slice-{slices}.json")
        elif (dest / "comment-list.json").is_file():
            unread.append(name)
    lines = [captured[n][0] for n in sorted(captured)]
    unparsed = sum(int(m[1]) for m in map(UNPARSED.search, lines) if m)
    print(f"## harvest — {args.log} since {start}")
    print(f"merged: {len(lines)}; records written: {sum(' · record' in x for x in lines)}; labels unparsed: {unparsed}")
    print("\n".join([*lines, *(f"not read · {name}" for name in unread)]))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("pending")
    q.add_argument("--log", type=Path, required=True)
    q.add_argument("--threads", type=Path, required=True)
    s = sub.add_parser("store")
    s.add_argument("--log", type=Path, required=True)
    s.add_argument("--report", type=Path, required=True)
    s.add_argument("--threads", type=Path, required=True)
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--through", required=True)
    s.add_argument("--slices", type=Path, nargs="*", default=[])
    s.add_argument("--not-read", type=int, nargs="*", default=[])
    s.add_argument("--analysis", type=Path)
    r = sub.add_parser("load")
    r.add_argument("--log", type=Path, required=True)
    r.add_argument("--since", required=True)
    r.add_argument("--through", required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--guidance", type=Path, required=True)
    r.add_argument("--merges", type=Path)
    args = p.parse_args(argv)
    try:
        if args.command == "pending":
            print("\n".join(f"pr-{n:04d}" for n in pending(args.log, args.threads)))
            return 0
        return store(args) if args.command == "store" else load(args)
    except (Refused, OSError, json.JSONDecodeError) as e:
        print(f"capture.py: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
