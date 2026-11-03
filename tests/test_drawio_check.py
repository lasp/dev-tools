"""Tests for scripts/drawio_check.py, the check on a diagram before it is pasted. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("drawio_check", ROOT / "scripts" / "drawio_check.py")
drawio_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drawio_check)

ROOT_CELLS = '<mxCell id="0"/><mxCell id="1" parent="0"/>'


def vertex(cid, x, y, label="Box", style="rounded=1;whiteSpace=wrap;html=1;", parent="1"):
    return (
        f'<mxCell id="{cid}" value="{label}" style="{style}" vertex="1" parent="{parent}">'
        f'<mxGeometry x="{x}" y="{y}" width="160" height="60" as="geometry"/></mxCell>'
    )


def edge(cid, source, target, label="data"):
    return (
        f'<mxCell id="{cid}" value="{label}" style="edgeStyle=orthogonalEdgeStyle;html=1;" edge="1" '
        f'parent="1" source="{source}" target="{target}"><mxGeometry relative="1" as="geometry"/></mxCell>'
    )


def mxfile(*cells, root=ROOT_CELLS):
    return (
        '<mxfile host="drawio"><diagram name="Context" id="ctx"><mxGraphModel grid="1" gridSize="10">'
        f"<root>{root}{''.join(cells)}</root></mxGraphModel></diagram></mxfile>"
    )


class DrawioCheck(unittest.TestCase):
    def run_on(self, text):
        path = Path(tempfile.mkdtemp()) / "d.drawio"
        path.write_text(text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = drawio_check.main([str(path)])
        return rc, out.getvalue()

    def test_a_clean_diagram_passes_with_its_summary(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0), vertex("b", 240, 0), edge("e", "a", "b")))
        self.assertEqual(rc, 0, out)
        self.assertIn("Context: 2 vertices, 1 edges, 400 x 60", out)

    def test_a_bare_graph_model_passes(self):
        rc, out = self.run_on(f"<mxGraphModel><root>{ROOT_CELLS}{vertex('a', 0, 0)}</root></mxGraphModel>")
        self.assertEqual(rc, 0, out)

    def test_malformed_xml_fails(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0, label="R&D")))
        self.assertEqual(rc, 1)
        self.assertIn("not well-formed XML", out)

    def test_compressed_page_fails(self):
        rc, out = self.run_on('<mxfile><diagram name="Context">7VZNb9swDP01Pq6ILafLjk3abhgwYEAP</diagram></mxfile>')
        self.assertEqual(rc, 1)
        self.assertIn("compressed text", out)

    def test_missing_root_cells_fail(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0, parent="0"), root='<mxCell id="0"/>'))
        self.assertEqual(rc, 1)
        self.assertIn("root cells are missing", out)

    def test_duplicate_id_fails(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0), vertex("a", 300, 0)))
        self.assertEqual(rc, 1)
        self.assertIn("id 'a' is used twice", out)

    def test_dangling_edge_end_fails(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0), edge("e", "a", "gone")))
        self.assertEqual(rc, 1)
        self.assertIn("target 'gone', which is not a cell", out)

    def test_edge_to_an_edge_fails(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0), vertex("b", 240, 0), edge("e", "a", "b"), edge("f", "a", "e")))
        self.assertEqual(rc, 1)
        self.assertIn("target 'e', which is not a vertex", out)

    def test_unknown_parent_fails(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0, parent="nowhere")))
        self.assertEqual(rc, 1)
        self.assertIn("names parent 'nowhere'", out)

    def test_vertex_without_size_fails(self):
        cell = '<mxCell id="a" value="A" vertex="1" parent="1"><mxGeometry x="0" y="0" as="geometry"/></mxCell>'
        rc, out = self.run_on(mxfile(cell))
        self.assertEqual(rc, 1)
        self.assertIn("no geometry with a positive width and height", out)

    def test_overlapping_boxes_fail(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0), vertex("b", 100, 20)))
        self.assertEqual(rc, 1)
        self.assertIn("vertices 'a' and 'b' overlap", out)

    def test_a_box_inside_a_container_or_under_a_label_does_not_overlap(self):
        boundary = vertex("sys", 0, 0, label="System", style="swimlane;container=1;")
        label = vertex("t", 10, 10, label="Note", style="text;html=1;")
        rc, out = self.run_on(mxfile(boundary, vertex("a", 20, 30, parent="sys"), vertex("b", 0, 0), label))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("overlap", out)

    def test_overlapping_containers_fail(self):
        lane_a = vertex("la", 0, 0, label="Author", style="swimlane;")
        lane_b = vertex("lb", 0, 30, label="Reviewer", style="swimlane;")
        rc, out = self.run_on(mxfile(lane_a, lane_b))
        self.assertEqual(rc, 1)
        self.assertIn("vertices 'la' and 'lb' overlap", out)

    def test_an_edge_label_child_passes(self):
        label = (
            '<mxCell id="lbl" value="data" style="edgeLabel;html=1;" vertex="1" connectable="0" parent="e">'
            '<mxGeometry x="-0.2" relative="1" as="geometry"><mxPoint as="offset"/></mxGeometry></mxCell>'
        )
        rc, out = self.run_on(mxfile(vertex("a", 0, 0), vertex("b", 240, 0), edge("e", "a", "b"), label))
        self.assertEqual(rc, 0, out)
        self.assertIn("Context: 2 vertices, 1 edges", out)

    def test_an_edge_with_no_end_fails(self):
        cell = '<mxCell id="e" edge="1" parent="1" source="a"><mxGeometry relative="1" as="geometry"/></mxCell>'
        rc, out = self.run_on(mxfile(vertex("a", 0, 0), cell))
        self.assertEqual(rc, 1)
        self.assertIn("edge 'e' has no target and no targetPoint", out)

    def test_an_edge_end_at_a_point_passes(self):
        cell = (
            '<mxCell id="e" edge="1" parent="1" source="a"><mxGeometry relative="1" as="geometry">'
            '<mxPoint x="400" y="30" as="targetPoint"/></mxGeometry></mxCell>'
        )
        rc, out = self.run_on(mxfile(vertex("a", 0, 0), cell))
        self.assertEqual(rc, 0, out)

    def test_a_file_with_no_model_fails(self):
        rc, out = self.run_on("<mxfile/>")
        self.assertEqual(rc, 1)
        self.assertIn("no <mxGraphModel> and no <diagram>", out)

    def test_an_unreadable_file_exits_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(drawio_check.main([str(Path(tempfile.mkdtemp()) / "missing.drawio")]), 2)
            path = Path(tempfile.mkdtemp()) / "d.drawio"
            path.write_bytes(mxfile(vertex("a", 0, 0)).encode("utf-16"))
            self.assertEqual(drawio_check.main([str(path)]), 2)
            self.assertEqual(drawio_check.main([]), 2)
        self.assertIn("cannot read", err.getvalue())

    def test_an_empty_label_is_a_warning_not_a_failure(self):
        rc, out = self.run_on(mxfile(vertex("a", 0, 0, label="")))
        self.assertEqual(rc, 0, out)
        self.assertIn("warning: vertex 'a' has no label", out)

    def test_a_user_object_carries_the_label(self):
        obj = (
            '<UserObject label="Ingest" id="u"><mxCell style="rounded=1;" vertex="1" parent="1">'
            '<mxGeometry x="0" y="0" width="160" height="60" as="geometry"/></mxCell></UserObject>'
        )
        rc, out = self.run_on(mxfile(obj, vertex("b", 240, 0), edge("e", "u", "b")))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("warning", out)


if __name__ == "__main__":
    unittest.main()
