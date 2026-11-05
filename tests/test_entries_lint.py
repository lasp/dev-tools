"""Tests for scripts/entries_lint.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("entries_lint", ROOT / "scripts" / "entries_lint.py")
entries_lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entries_lint)

GUIDANCE = """\
# Agent guidance

Habits agents should not repeat.

```markdown
### A-099 · An example in a fence
```

### A-001 · Fix the environment, not the import
repos: [widgets]

_2026-09 · seen 2026-11_
habit: guards the import of a dependency the image lacks
> Install a missing dependency where the code runs.
> Never guard or mock its import.
said: "put libnetcdf in the image, not a fake" — alice, https://github.com/o/r/pull/1#discussion_r1
said: "same again" — bob, https://github.com/o/r/pull/2#discussion_r2

### A-002 · No compatibility shims before a product has users

_2026-10 · seen 2026-10_
habit: keeps an old signature working beside the new one
> Change the signature; nothing calls the old one yet.
said: "nobody uses this yet" — carol, https://github.com/o/r/pull/3#discussion_r3
"""

CONVENTIONS = """\
# Data conventions

### F-001 · Fill values differ by field

_2026-10_
> Read each field's fill value from its attributes; never assume one.
source: the product's interface document, version 2, section 4

### F-002 · Positions are inertial

_2026-11_
> A position is in the inertial frame, not Earth-fixed.
source: the geolocation lead
said: "this is J2000, not ITRF" — dave, https://github.com/o/r/pull/4#discussion_r4
"""


class Lint(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def run_lint(self, **files: str) -> tuple[int, list[str]]:
        paths = []
        for name, text in files.items():
            path = self.dir / (name[:-3].replace("_", "-") + ".md")
            path.write_text(text)
            paths.append(str(path))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = entries_lint.main(paths)
        return code, out.getvalue().splitlines()

    def test_well_formed_files_pass_and_count_their_entries(self):
        code, lines = self.run_lint(agent_guidance_md=GUIDANCE, data_conventions_md=CONVENTIONS)
        self.assertEqual(code, 0, lines)
        self.assertEqual([x.rsplit(" · ", 1)[1] for x in lines], ["2 entries", "2 entries"])

    def test_the_plugins_templates_pass(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = entries_lint.main([str(ROOT / "standards" / "templates" / f) for f in ("agent-guidance.md", "data-conventions.md")])
        self.assertEqual(code, 0, out.getvalue())

    def test_refuses_an_agent_guidance_entry_out_of_form(self):
        cases = {
            "a heading not `### A-NNN · <title>`": GUIDANCE.replace("### A-002 ·", "### F-002 ·"),
            "A-001 given twice or out of order": GUIDANCE.replace("A-002 ·", "A-001 ·"),
            "no `_YYYY-MM · seen YYYY-MM_` line first": GUIDANCE.replace("_2026-10 · seen 2026-10_", "_2026-10_"),
            "seen 2026-08, before it was admitted in 2026-09": GUIDANCE.replace("seen 2026-11", "seen 2026-08"),
            "no `> ` line": GUIDANCE.replace("> Change the signature; nothing calls the old one yet.\n", ""),
            "not exactly one `habit:` line": GUIDANCE.replace("habit: keeps an old", "said: x\nhabit: keeps an old").replace(
                "habit: guards the import", "habit: one\nhabit: guards the import"),
            "a `source:` line, which belongs in the other file": GUIDANCE.replace("habit: keeps", "source: a doc\nhabit: keeps"),
            "a `said:` line not `said:": GUIDANCE.replace("— carol, https://", "— carol https://"),
            "no `said:` line: agent guidance quotes a person": GUIDANCE.replace(
                'said: "nobody uses this yet" — carol, https://github.com/o/r/pull/3#discussion_r3\n', ""),
            "a second `repos:` line": GUIDANCE.replace("repos: [widgets]\n", "repos: [widgets]\nrepos: [gadgets]\n"),
        }
        for why, text in cases.items():
            with self.subTest(why=why):
                code, lines = self.run_lint(agent_guidance_md=text)
                self.assertEqual(code, 1)
                self.assertIn(why, "\n".join(lines))

    def test_refuses_a_data_convention_out_of_form(self):
        cases = {
            "not exactly one `source:` line": CONVENTIONS.replace("source: the geolocation lead\n", ""),
            "a `habit:` line, which belongs in the other file": CONVENTIONS.replace("source: the geo", "habit: x\nsource: the geo"),
            "no `_YYYY-MM_` line first": CONVENTIONS.replace("_2026-11_", "_2026-11 · seen 2026-11_"),
            "a heading not `### F-NNN · <title>`": CONVENTIONS + "\n## Notes\n\nprose\n",
        }
        for why, text in cases.items():
            with self.subTest(why=why):
                code, lines = self.run_lint(data_conventions_md=text)
                self.assertEqual(code, 1)
                self.assertIn(why, "\n".join(lines))

    def test_reports_every_fault_and_refuses_a_file_of_another_name(self):
        text = GUIDANCE.replace("habit: guards the import of a dependency the image lacks\n", "").replace("_2026-10 · seen 2026-10_", "")
        code, lines = self.run_lint(agent_guidance_md=text, notes_md="# Notes\n")
        self.assertEqual(code, 1)
        self.assertEqual(len(lines), 3, lines)
        self.assertTrue(lines[-1].endswith("not agent-guidance.md or data-conventions.md"))


if __name__ == "__main__":
    unittest.main()
