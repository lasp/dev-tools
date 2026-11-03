#!/usr/bin/env python3
"""Check a draw.io diagram file before a person pastes it into the draw.io editor.

    python3 drawio_check.py <file.drawio>

The `drawio` skill writes a diagram as uncompressed XML: an `<mxfile>` holding one or more
`<diagram>` pages, each an `<mxGraphModel>`, or a bare `<mxGraphModel>`. The draw.io editor
accepts XML that is broken in ways it does not report: an edge whose end is missing draws nowhere,
two cells with one id lose one of them, and a box placed on another hides it. So each failure
here is printed as `drawio_check: <page>: <what>`:

- the file is not well-formed XML, or holds no `<mxGraphModel>`, or a page is compressed text
  rather than XML, which no person can review;
- a page lacks the two root cells, id `0` and id `1` with parent `0`;
- an id is used twice, or a cell names a parent that is not a cell;
- an edge names a `source` or `target` that is not a vertex, or has an end with neither a
  terminal nor a `sourcePoint` or `targetPoint` in its geometry;
- a vertex has no `<mxGeometry>`, or one with no positive width and height, unless it is an
  edge's label (its parent is an edge), which draw.io places relative to the edge;
- two vertices with the same parent overlap, unless one is a text label (`text` in its style) or
  exactly one is a container (`container=1`, `swimlane` or `group` in its style), since a box drawn
  on another hides it; two overlapping containers, such as two lanes, fail.

A vertex with an empty label is a warning, printed as `drawio_check: <page>: warning: <what>`,
since a shape such as a legend swatch may have none. On success it prints, per page, its name,
vertices, edges and the size of the drawing. Exit 0 with no failure, 1 otherwise, 2 for a file
that cannot be read. Stdlib only.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def pages(root: ET.Element) -> list[tuple[str, ET.Element | None]]:
    """Each page's name and its mxGraphModel, None for a page that holds no XML model."""
    if root.tag == "mxGraphModel":
        return [("diagram", root)]
    found = []
    for i, diagram in enumerate(root.iter("diagram"), 1):
        found.append((diagram.get("name") or f"page {i}", diagram.find("mxGraphModel")))
    return found


def box(cell: ET.Element) -> tuple[float, float, float, float] | None:
    geo = cell.find("mxGeometry")
    if geo is None:
        return None
    try:
        x, y = float(geo.get("x", 0)), float(geo.get("y", 0))
        w, h = float(geo.get("width", 0)), float(geo.get("height", 0))
    except ValueError:
        return None
    return x, y, w, h


def check_model(name: str, model: ET.Element) -> tuple[list[str], list[str], str]:
    failures, warnings = [], []
    root = model.find("root")
    cells = list(root) if root is not None else []
    ids: dict[str, ET.Element] = {}
    for cell in cells:
        cid = cell.get("id")
        if cid is None:
            failures.append(f"a <{cell.tag}> has no id")
        elif cid in ids:
            failures.append(f"id {cid!r} is used twice")
        else:
            ids[cid] = cell
    if "0" not in ids or ids.get("1") is None or ids["1"].get("parent") != "0":
        failures.append('the root cells are missing: <mxCell id="0"/> and <mxCell id="1" parent="0"/>')
    # A styled shape such as <UserObject> or <object> wraps its mxCell and carries the id and label.
    def inner(cell: ET.Element) -> ET.Element:
        return cell if cell.tag == "mxCell" else (cell.find("mxCell") if cell.find("mxCell") is not None else cell)

    vertices, edges = {}, 0
    for cid, cell in ids.items():
        mx = inner(cell)
        parent = mx.get("parent")
        if cid != "0" and parent not in ids:
            failures.append(f"{cid!r} names parent {parent!r}, which is not a cell")
        if mx.get("edge") == "1":
            edges += 1
            geo = mx.find("mxGeometry")
            for end in ("source", "target"):
                ref = mx.get(end)
                if ref is None:
                    if geo is None or geo.find(f"mxPoint[@as='{end}Point']") is None:
                        failures.append(f"edge {cid!r} has no {end} and no {end}Point")
                elif ref not in ids:
                    failures.append(f"edge {cid!r} has {end} {ref!r}, which is not a cell")
                elif inner(ids[ref]).get("vertex") != "1":
                    failures.append(f"edge {cid!r} has {end} {ref!r}, which is not a vertex")
        elif mx.get("vertex") == "1":
            if parent in ids and inner(ids[parent]).get("edge") == "1":
                continue
            b = box(mx)
            if b is None or b[2] <= 0 or b[3] <= 0:
                failures.append(f"vertex {cid!r} has no geometry with a positive width and height")
                continue
            vertices[cid] = (mx, b)
            label = cell.get("label") if cell is not mx else mx.get("value")
            if not (label or "").strip():
                warnings.append(f"vertex {cid!r} has no label")

    def container(mx: ET.Element) -> bool:
        style = mx.get("style") or ""
        return "container=1" in style or "swimlane" in style or style.startswith("group")

    def text(mx: ET.Element) -> bool:
        return (mx.get("style") or "").split(";")[0] == "text"

    items = sorted(vertices.items())
    for i, (a, (ma, (ax, ay, aw, ah))) in enumerate(items):
        for b, (mb, (bx, by, bw, bh)) in items[i + 1 :]:
            if ma.get("parent") != mb.get("parent") or container(ma) != container(mb) or text(ma) or text(mb):
                continue
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                failures.append(f"vertices {a!r} and {b!r} overlap")

    top = [b for _, (mx, b) in vertices.items() if mx.get("parent") == "1"]
    size = ""
    if top:
        width = max(x + w for x, _, w, _ in top) - min(x for x, _, _, _ in top)
        height = max(y + h for _, y, _, h in top) - min(y for _, y, _, _ in top)
        size = f", {width:g} x {height:g}"
    return failures, warnings, f"{name}: {len(vertices)} vertices, {edges} edges{size}"


def check(path: Path) -> tuple[list[str], list[str], list[str]]:
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except ET.ParseError as e:
        return [f"{path.name}: not well-formed XML: {e}"], [], []
    failures, warnings, summary = [], [], []
    found = pages(root)
    if not found:
        return [f"{path.name}: no <mxGraphModel> and no <diagram>"], [], []
    for name, model in found:
        if model is None:
            failures.append(f"{name}: the page is compressed text, not XML; write it uncompressed")
            continue
        f, w, s = check_model(name, model)
        failures += [f"{name}: {x}" for x in f]
        warnings += [f"{name}: warning: {x}" for x in w]
        summary.append(s)
    return failures, warnings, summary


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: drawio_check.py <file.drawio>", file=sys.stderr)
        return 2
    path = Path(args[0])
    try:
        path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"drawio_check: cannot read {path}: {e}", file=sys.stderr)
        return 2
    failures, warnings, summary = check(path)
    for line in failures + warnings:
        print(f"drawio_check: {line}")
    for line in summary:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
