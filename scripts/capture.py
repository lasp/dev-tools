#!/usr/bin/env python3
"""Keep each merged pull request's harvest in the standard's log, and restore a window of it.

`revise capture` harvests merged pull requests as they merge, so that `prepare` reads them from the
log instead of harvesting a month at once (`docs/contracts.md`, "The capture"). Two commands:

`store --log <log> --report <file> --threads <dir> --from <day> --through <day> [--slices <slice>
...] [--analysis <dir>]` files one capture run. The report is `pr-reader`'s harvest block, saved to
a file; each of its `pr-NNNN · created <day> · merged <day> · ...` lines is one pull request, and
each gets `<log>/capture/pr-NNNN/`, replaced whole: `harvest.txt`, its report line; `pr.json` and
`comment-list.json`, from its dump under --threads when there; `items.json`, its guidance items
as a slice of one pull request, cut from the run's --slices; and `analysis.md`, its
`thread-analyst` block, from `<analysis>/pr-NNNN.md` when there. The slices are first held to
`guidance_check.py` with the listed pull requests' comment lists, and every refusal it prints is
printed and nothing is written. Then `<from> <through>` is appended to `<log>/capture/covered.txt`,
the days the harvest searched. Prints `captured pr-NNNN · items <n>[ · analysis]` per pull request
and `covered <from>..<through>`.

`load --log <log> --since <day> --through <day> --out <dir> --guidance <dir> [--merges <file>]`
restores the pull requests captured as merged from --since through --through: removes, then writes,
`<out>/threads/pr-NNNN/` with `pr.json` and `comment-list.json`, `<out>/records/pr-NNNN.yaml` from
`<log>/pr-NNNN.yaml`, `<out>/analysis/pr-NNNN.md`, and in --guidance, also emptied first, one
`slice-<n>.json` per pull request with items, n from 1 in number order; then prints the harvest
block `pr-reader` would have, `## harvest — <log> since <day>`, its count line and its pull
requests' lines. It refuses, exit 2, writing nothing, with one line each: `uncovered · <from> ·
<to>` for days from --since through --through no `covered.txt` line covers, `uncaptured · pr-NNNN`
for a pull request --merges (`window_merges.py`'s printout) lists as merged in those days with no
capture, and `missing · pr-NNNN · record` for a capture whose line says `record` and whose log has
none.

Both exit 1 with the reason for an input that cannot be read: a day not YYYY-MM-DD, --from after
--through, a report line naming a pull request twice, a log directory that does not exist, or a
capture whose `harvest.txt` is not a report line. Stdlib only.
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
UNPARSED = re.compile(r" · record · (\d+) label\(s\) unparsed")
MERGE = re.compile(r"^pr-(\d+) [0-9a-f]{40} (\d{4}-\d{2}-\d{2})\b")


class Refused(Exception):
    """An input the capture cannot be read from."""


def day(text: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(text)
    except ValueError as e:
        raise Refused(f"{text!r} is not a day, YYYY-MM-DD") from e


def report_lines(text: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for line in text.splitlines():
        m = LINE.match(line.strip())
        if m:
            if int(m[1]) in out:
                raise Refused(f"the report names pr-{m[1]} twice")
            out[int(m[1])] = line.strip()
    return out


def load_check():
    spec = importlib.util.spec_from_file_location("guidance_check", Path(__file__).with_name("guidance_check.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def store(args) -> int:
    start, end = day(args.start), day(args.through)
    if start > end:
        raise Refused(f"--from {start} is after --through {end}")
    if not args.log.is_dir():
        raise Refused(f"{args.log} is not a directory: archive the records first, which makes it")
    prs = report_lines(args.report.read_text())
    lists = {n: args.threads / f"pr-{n:04d}" / "comment-list.json" for n in prs}
    lists = {n: p for n, p in lists.items() if p.is_file()}
    items: dict[int, list] = {n: [] for n in lists}
    if lists:
        if not args.slices:
            raise Refused("the harvest has comment lists and no --slices: run the guidance extraction first")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = load_check().main([*map(str, args.slices), "--comments", *map(str, lists.values())])
        if code != 0:
            print(out.getvalue(), end="")
            return 1
        for path in args.slices:
            for it in json.loads(path.read_text())["items"]:
                items[it["pr"]].append(it)
    root = args.log / "capture"
    root.mkdir(exist_ok=True)
    for n, line in sorted(prs.items()):
        dest = root / f"pr-{n:04d}"
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir()
        (dest / "harvest.txt").write_text(line + "\n")
        dump = args.threads / f"pr-{n:04d}"
        if (dump / "pr.json").is_file():
            shutil.copyfile(dump / "pr.json", dest / "pr.json")
        said = ""
        if n in lists:
            shutil.copyfile(lists[n], dest / "comment-list.json")
            read = len(json.loads(lists[n].read_text())["comments"])
            (dest / "items.json").write_text(json.dumps({"prs": [n], "comments_read": read, "items": items[n]},
                                                        ensure_ascii=False, indent=1) + "\n")
            said = f" · items {len(items[n])}"
        block = args.analysis / f"pr-{n:04d}.md" if args.analysis else None
        if block and block.is_file():
            shutil.copyfile(block, dest / "analysis.md")
            said += " · analysis"
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
    if not args.log.is_dir():
        raise Refused(f"{args.log} is not a directory")
    captured: dict[int, tuple[str, Path]] = {}
    for dest in sorted(root.glob("pr-*")) if root.is_dir() else []:
        line = (dest / "harvest.txt").read_text().strip() if (dest / "harvest.txt").is_file() else ""
        m = LINE.match(line)
        if not m:
            raise Refused(f"{dest / 'harvest.txt'} is not a harvest report line")
        if start <= day(m[3]) <= end:
            captured[int(m[1])] = (line, dest)
    faults = [f"uncovered · {a} · {b}" for a, b in gaps(covered(root), start, end)]
    if args.merges:
        for m in map(MERGE.match, args.merges.read_text().splitlines()):
            if m and start <= day(m[2]) <= end and int(m[1]) not in captured:
                faults.append(f"uncaptured · pr-{int(m[1]):04d}")
    faults += [f"missing · pr-{n:04d} · record" for n, (line, _) in sorted(captured.items())
               if " · record" in line and not (args.log / f"pr-{n:04d}.yaml").is_file()]
    if faults:
        print("\n".join(faults))
        return 2
    for sub in ("threads", "records", "analysis"):
        shutil.rmtree(args.out / sub, ignore_errors=True)
        (args.out / sub).mkdir(parents=True)
    shutil.rmtree(args.guidance, ignore_errors=True)
    args.guidance.mkdir(parents=True)
    slices = 0
    for n, (line, dest) in sorted(captured.items()):
        name = f"pr-{n:04d}"
        (args.out / "threads" / name).mkdir()
        for f in ("pr.json", "comment-list.json"):
            if (dest / f).is_file():
                shutil.copyfile(dest / f, args.out / "threads" / name / f)
        if (args.log / f"{name}.yaml").is_file():
            shutil.copyfile(args.log / f"{name}.yaml", args.out / "records" / f"{name}.yaml")
        if (dest / "analysis.md").is_file():
            shutil.copyfile(dest / "analysis.md", args.out / "analysis" / f"{name}.md")
        if (dest / "items.json").is_file():
            slices += 1
            shutil.copyfile(dest / "items.json", args.guidance / f"slice-{slices}.json")
    lines = [line for line, _ in (captured[n] for n in sorted(captured))]
    unparsed = sum(int(m[1]) for m in map(UNPARSED.search, lines) if m)
    print(f"## harvest — {args.log} since {start}")
    print(f"merged: {len(lines)}; records written: {sum(' · record' in x for x in lines)}; labels unparsed: {unparsed}")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("store")
    s.add_argument("--log", type=Path, required=True)
    s.add_argument("--report", type=Path, required=True)
    s.add_argument("--threads", type=Path, required=True)
    s.add_argument("--from", dest="start", required=True)
    s.add_argument("--through", required=True)
    s.add_argument("--slices", type=Path, nargs="*", default=[])
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
        return store(args) if args.command == "store" else load(args)
    except (Refused, OSError, json.JSONDecodeError, ValueError) as e:
        print(f"capture.py: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
