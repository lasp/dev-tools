"""Tests for scripts/controlled_gate.py and hooks/controlled-gate.sh. Run with `python3 -m unittest discover -s tests`."""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "hooks" / "controlled-gate.sh"
SCRIPT = ROOT / "scripts" / "controlled_gate.py"
LINE = "Controlled: PROJ-9997 — CUI // SP-EXPT"
HELD = ".review/context/PROJ-9997.md"
OTHER = ".review/context/PROJ-9998.md"

# Commands that name a held file, or a directory inside a `.review/` tree holding one: each asks.
READS = [
    f"cat {HELD}",
    f"tail -5 {HELD}",
    f"head -n 5 {HELD}",
    f"head -1 -n 5 {HELD}",
    f"sed -n 2,5p {HELD}",
    f"less {HELD}",
    f"awk 'NR>1' {HELD}",
    f"grep BADGER {HELD}",
    "cat .review/context/*.md",
    "cat .review/**/PROJ-9997.md",
    f"python3 -c \"print(open('{HELD}').read())\"",
    "cd .review/context && cat PROJ-9997.md",
    f"git log -1 && cat {HELD} | head -3",
    f"bash -c 'cat {HELD}'",
    f'echo "$(cat {HELD})"',
    f'git commit -m "$(cat {HELD})"',
    "grep -r BADGER .review",
    "find .review -type f | xargs cat",
    f"cp {HELD} /tmp/x.md",
    f"head -1 {HELD} > /tmp/first.txt",
    f"awk -f{HELD}",
    f"--file={HELD}",
    "ls .review/context | xargs -I{} cat .review/context/{}",
    "find .review -exec cat {} +",
    f"ls .review && cat {HELD}",
    f"ls {HELD} 2>/dev/null; tail -n +2 {HELD}",
    f"echo `cat {HELD}`",
    f"git commit -F {HELD}",
    f"python3 - <<'PY'\nprint(open('{HELD}').read())\nPY",
    f"cat <<'EOF' | bash\ncat {HELD}\nEOF",
    f"ls\ncat {HELD}",
    "cat '.review/context/PROJ-9997.md",
]

# Commands that pass while a file is held: they name no held file, or show none of its text.
ROUTINE = [
    f"head -1 {HELD}",
    f"head -n 1 {HELD}",
    f"head -n1 {HELD}",
    f"head --lines=1 {HELD}",
    f"sed -n 1p {HELD}",
    f"sed 1q {HELD}",
    "ls -la .review/context",
    f"ls {HELD}",
    f"rm {HELD}",
    "mkdir -p .review/onboard",
    "git status",
    "git branch && git status",
    "git log -p",
    "python3 -m unittest discover -s tests",
    "uv run python -m unittest discover -s tests && bash tests/test_where.sh",
    "grep -r BADGER src",
    "source .venv/bin/activate",
    "git commit -m \"$(cat <<'EOF'\nA message\nEOF\n)\"",
    "cat .review/plain.md src/outside.md",
    "ls .review/context/ 2>/dev/null",
    "test -f .review/context.md && echo yes",
    "mkdir -p .review/design/p1 && ls .review",
    "ls .review/*.md",
    "ls .review/context/*.md 2>&1",
    "ls .review | head",
    "find .review -name '*.md'",
    "git status --short .review",
    'git commit -m "note the .review table"',
    "echo .review/context",
]


def make_repo(base, held):
    repo = base
    (repo / ".git").mkdir(parents=True)
    (repo / ".review" / "context").mkdir(parents=True)
    (repo / "src").mkdir()
    first = f"{LINE}\n" if held else ""
    (repo / HELD).write_text(f"{first}# PROJ-9997 · Flag high-gain frames\n\nBADGER-6604 detail\n")
    (repo / OTHER).write_text(("Controlled: PROJ-9998 — ITAR\n" if held else "") + "# PROJ-9998 · x\n")
    (repo / ".review" / "plain.md").write_text("# plain\n")
    (repo / "src" / "outside.md").write_text(f"{LINE}\nnot under .review\n")
    (repo / "src" / "plain-target.md").write_text("plain\n")
    (repo / "src" / "link.md").symlink_to(repo / HELD)
    (repo / ".review" / "out-link.md").symlink_to(repo / "src" / "plain-target.md")
    return repo


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = make_repo(self.tmp / "repo", held=True)
        self.clean = make_repo(self.tmp / "clean", held=False)

    def gate(self, tool, inp, cwd=None, script=True, session="s1", event="pre"):
        payload = json.dumps({"tool_name": tool, "tool_input": inp, "cwd": str(cwd or self.repo),
                              "session_id": session})
        cmd = [sys.executable, str(SCRIPT), event] if script else [str(GATE), event]
        out = subprocess.run(cmd, input=payload, capture_output=True, text=True, check=True).stdout
        return json.loads(out)["hookSpecificOutput"] if out.strip() else None

    def asks(self, tool, inp, **kw):
        d = self.gate(tool, inp, **kw)
        self.assertIsNotNone(d, f"{tool} {inp} passed")
        self.assertEqual(d["permissionDecision"], "ask")
        self.assertNotIn("BADGER", d["permissionDecisionReason"])
        return d["permissionDecisionReason"]

    def passes(self, tool, inp, **kw):
        self.assertIsNone(self.gate(tool, inp, **kw), f"{tool} {inp} was asked about")

    def ran(self, tool, inp, **kw):
        """The call ran, as it does after the person's yes: the post hook sees it."""
        self.assertIsNone(self.gate(tool, inp, event="post", **kw))

    # What asks

    def test_a_read_of_a_held_file_asks_naming_the_item_and_its_warning_only(self):
        reason = self.asks("Read", {"file_path": str(self.repo / HELD)})
        self.assertIn("PROJ-9997", reason)
        self.assertIn(LINE, reason)
        self.assertNotIn("high-gain", reason)

    def test_reading_only_the_first_line_passes(self):
        self.passes("Read", {"file_path": HELD, "limit": 1})
        self.passes("Read", {"file_path": HELD, "offset": 1, "limit": 1})
        self.asks("Read", {"file_path": HELD, "limit": 2})
        self.asks("Read", {"file_path": HELD, "offset": 2, "limit": 1})

    def test_files_not_held_pass(self):
        for path in (".review/plain.md", "src/outside.md", ".review/missing.md", ".review/out-link.md"):
            with self.subTest(path=path):
                self.passes("Read", {"file_path": path})

    def test_a_symlink_to_a_held_file_is_held(self):
        self.asks("Read", {"file_path": "src/link.md"})

    def test_every_editing_tool_asks_on_a_held_file_and_a_write_keeping_its_first_line_passes(self):
        self.asks("Edit", {"file_path": HELD, "old_string": "a", "new_string": "b"})
        self.asks("Write", {"file_path": HELD, "content": "x"})
        self.asks("Write", {"file_path": HELD, "content": "Controlled: OTHER-1 — CUI\nx"})
        self.asks("MultiEdit", {"file_path": HELD, "edits": []})
        self.asks("NotebookEdit", {"notebook_path": HELD, "new_source": "x"})
        self.passes("Write", {"file_path": HELD, "content": f"{LINE}\nthe rewritten body"})
        self.passes("Write", {"file_path": ".review/context/NEW.md", "content": f"{LINE}\nnew"})

    def test_grep_asks_only_when_it_shows_lines_from_a_held_file(self):
        self.asks("Grep", {"pattern": "x", "path": HELD, "output_mode": "content"})
        self.asks("Grep", {"pattern": "x", "path": ".review", "output_mode": "content"})
        self.passes("Grep", {"pattern": "x", "path": ".review"})
        self.passes("Grep", {"pattern": "x", "path": "src", "output_mode": "content"})
        self.passes("Grep", {"pattern": "x", "path": ".review", "output_mode": "content"}, cwd=self.clean)

    def test_a_command_naming_a_held_file_asks(self):
        for command in READS:
            with self.subTest(command=command):
                self.asks("Bash", {"command": command})

    def test_the_same_commands_pass_when_nothing_is_held(self):
        for command in READS:
            with self.subTest(command=command):
                self.passes("Bash", {"command": command}, cwd=self.clean)

    def test_routine_commands_pass_while_a_file_is_held(self):
        for command in ROUTINE:
            with self.subTest(command=command):
                self.passes("Bash", {"command": command})

    def test_a_held_file_in_another_repository_asks_from_a_clean_one(self):
        rel = os.path.relpath(self.repo / HELD, self.clean)
        self.asks("Bash", {"command": f"cat {self.repo / HELD}"}, cwd=self.clean)
        self.asks("Bash", {"command": f"cat {rel}"}, cwd=self.clean)
        self.passes("Bash", {"command": f"head -1 {rel}"}, cwd=self.clean)

    def test_a_path_with_a_space_is_one_word(self):
        spaced = make_repo(self.tmp / "rv repo", held=True)
        for command in (f'cat "{spaced / HELD}"', "cat " + str(spaced / HELD).replace(" ", "\\ "),
                        f"cat '{spaced}'/{HELD}"):
            with self.subTest(command=command):
                self.asks("Bash", {"command": command}, cwd=self.clean)
        self.passes("Bash", {"command": f'head -1 "{spaced / HELD}"'}, cwd=self.clean)

    def test_a_held_file_named_in_another_case_is_held_where_the_file_system_ignores_case(self):
        if not (self.repo / ".REVIEW").exists():
            self.skipTest("this file system tells .REVIEW from .review")
        upper = ".REVIEW/context/PROJ-9997.md"
        self.asks("Read", {"file_path": upper})
        self.asks("Bash", {"command": f"cat {upper}"})

    def test_past_the_walk_limit_only_held_files_found_ask(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import controlled_gate as gate
        many = make_repo(self.tmp / "many", held=False)
        for i in range(6):
            (many / ".review" / f"f{i}.md").write_text("x\n")
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "grep -r x .review"},
                              "cwd": str(many), "session_id": "s1"})
        old = gate.WALK_LIMIT
        gate.WALK_LIMIT = 3
        try:
            self.assertEqual(gate.reads("Bash", {"command": "grep -r x .review"}, str(many)), [])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                gate.pre(payload)
            self.assertEqual(out.getvalue(), "")
            gate.WALK_LIMIT = 100
            (many / ".review" / "held.md").write_text("Controlled: PROJ-1 — CUI\nx\n")
            with contextlib.redirect_stdout(out):
                gate.pre(payload)
            self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"]["permissionDecision"], "ask")
        finally:
            gate.WALK_LIMIT = old

    # Clearance, per item and per session

    def test_once_a_read_ran_later_reads_of_that_item_in_the_session_pass(self):
        self.asks("Read", {"file_path": HELD})
        self.ran("Read", {"file_path": HELD})
        self.passes("Read", {"file_path": HELD})
        self.passes("Bash", {"command": f"cat {HELD}"})
        self.passes("Grep", {"pattern": "x", "path": HELD, "output_mode": "content"})

    def test_a_clearance_covers_only_its_item(self):
        self.ran("Read", {"file_path": HELD})
        self.asks("Read", {"file_path": OTHER})
        reason = self.asks("Bash", {"command": "cat .review/context/*.md"})
        self.assertIn("PROJ-9998", reason)
        self.assertNotIn("PROJ-9997", reason)

    def test_a_call_reading_several_items_names_each_and_clears_each(self):
        reason = self.asks("Bash", {"command": "cat .review/context/*.md"})
        self.assertIn("PROJ-9997", reason)
        self.assertIn("ITAR", reason)
        self.ran("Bash", {"command": "cat .review/context/*.md"})
        self.passes("Read", {"file_path": OTHER})
        self.passes("Read", {"file_path": HELD})

    def test_a_word_that_only_starts_with_review_names_nothing(self):
        self.passes("Bash", {"command": "cat notes.reviewer x.review-old"})

    def test_another_session_asks_again_and_its_clearance_replaces_the_record(self):
        self.ran("Read", {"file_path": HELD})
        self.asks("Read", {"file_path": HELD}, session="s2")
        self.ran("Read", {"file_path": OTHER}, session="s2")
        self.asks("Read", {"file_path": HELD}, session="s1")
        self.passes("Read", {"file_path": OTHER}, session="s2")

    def test_the_session_that_writes_a_controlled_file_is_not_asked_to_read_it(self):
        new = ".review/context/PROJ-9996.md"
        line = "Controlled: PROJ-9996 — CUI"
        self.passes("Write", {"file_path": new, "content": f"{line}\nbody"})
        (self.repo / new).write_text(f"{line}\nbody\n")
        self.ran("Write", {"file_path": new, "content": f"{line}\nbody"})
        self.passes("Read", {"file_path": new})
        self.asks("Read", {"file_path": new}, session="s2")
        self.ran("Write", {"file_path": "src/elsewhere.md", "content": f"{line}\nbody"}, session="s3")
        self.ran("Write", {"file_path": ".review/plain2.md", "content": "no marker"}, session="s3")
        self.asks("Read", {"file_path": new}, session="s3")

    def test_a_first_line_read_clears_nothing(self):
        self.ran("Read", {"file_path": HELD, "limit": 1})
        self.ran("Bash", {"command": f"head -1 {HELD}"})
        self.asks("Read", {"file_path": HELD})

    def test_no_session_id_clears_nothing_and_keeps_the_record(self):
        self.ran("Read", {"file_path": HELD})
        self.ran("Read", {"file_path": OTHER}, session="")
        self.asks("Read", {"file_path": OTHER}, session="")
        self.passes("Read", {"file_path": HELD})

    def test_a_record_that_cannot_be_read_clears_nothing(self):
        record = self.repo / ".review" / "controlled-cleared.json"
        for text in ("not json", "[]", json.dumps({"session_id": "s1", "cleared": "PROJ-9997"})):
            with self.subTest(text=text):
                record.write_text(text)
                self.asks("Read", {"file_path": HELD})

    # A call the check cannot read passes

    def test_an_unreadable_payload_passes(self):
        for payload in ("not json",
                        json.dumps({"tool_name": "Read", "tool_input": {"file_path": 7}, "cwd": str(self.repo)}),
                        json.dumps({"tool_name": "Bash", "tool_input": {"command": ["cat", HELD]}, "cwd": str(self.repo)})):
            with self.subTest(payload=payload):
                for cmd in ([sys.executable, str(SCRIPT), "pre"], [str(GATE), "pre"]):
                    out = subprocess.run(cmd, input=payload, capture_output=True, text=True, check=True).stdout
                    self.assertEqual(out, "")
                out = subprocess.run([str(GATE), "post"], input=payload, capture_output=True, text=True, check=True).stdout
                self.assertEqual(out, "")

    def test_a_crash_or_a_garbled_answer_in_the_script_passes(self):
        for body in ("raise RuntimeError('boom')", "print('not a decision')"):
            with self.subTest(body=body):
                copy = Path(tempfile.mkdtemp(dir=self.tmp))
                (copy / "hooks").mkdir()
                (copy / "scripts").mkdir()
                shutil.copy2(GATE, copy / "hooks" / "controlled-gate.sh")
                (copy / "scripts" / "controlled_gate.py").write_text(body + "\n")
                payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": str(self.repo)})
                out = subprocess.run([str(copy / "hooks" / "controlled-gate.sh"), "pre"], input=payload,
                                     capture_output=True, text=True, check=True).stdout
                self.assertEqual(out, "")

    def test_the_script_runs_alone_with_no_other_script_beside_it(self):
        alone = Path(tempfile.mkdtemp(dir=self.tmp))
        shutil.copy2(SCRIPT, alone / "controlled_gate.py")
        payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": HELD}, "cwd": str(self.repo)})
        out = subprocess.run([sys.executable, "-I", str(alone / "controlled_gate.py"), "pre"], input=payload,
                             capture_output=True, text=True, check=True, cwd=alone).stdout
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_other_tools_pass(self):
        self.passes("Glob", {"pattern": ".review/**"})
        self.passes("WebFetch", {"url": "https://example.invalid/.review"})

    # The shell hook

    def test_the_hook_runs_the_script_both_ways(self):
        self.asks("Read", {"file_path": HELD}, script=False)
        self.passes("Read", {"file_path": ".review/plain.md"}, script=False)
        self.passes("Bash", {"command": "git status"}, script=False)
        self.ran("Read", {"file_path": HELD}, script=False)
        self.passes("Read", {"file_path": HELD}, script=False)

    def test_with_no_python3_every_call_passes(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for tool in ("bash", "dirname"):
            (bin_dir / tool).symlink_to(shutil.which(tool))
        def run(inp, event="pre"):
            payload = json.dumps({"tool_name": "Read", "tool_input": inp, "cwd": str(self.repo)})
            out = subprocess.run([str(bin_dir / "bash"), str(GATE), event], input=payload, capture_output=True,
                                 text=True, env={"PATH": str(bin_dir)}, check=True).stdout
            return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else None
        self.assertIsNone(run({"file_path": HELD}))
        self.assertIsNone(run({"file_path": "src/outside.md"}))
        self.assertIsNone(run({"file_path": ".review/plain.md"}, event="post"))


class Registration(unittest.TestCase):
    def matcher(self, event, mode):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"][event]
        [m] = [h["matcher"] for h in hooks
               if any(c["command"].endswith(f'controlled-gate.sh" {mode}') for c in h["hooks"])]
        return re.compile(f"^({m})$")

    def test_hooks_json_sends_it_every_reading_and_writing_tool_before_and_after(self):
        for event, mode in (("PreToolUse", "pre"), ("PostToolUse", "post")):
            for tool in ["Read", "Grep", "Bash", "Edit", "Write", "MultiEdit", "NotebookEdit"]:
                with self.subTest(event=event, tool=tool):
                    self.assertTrue(self.matcher(event, mode).match(tool))
            self.assertFalse(self.matcher(event, mode).match("Glob"))

    def test_gate_is_executable(self):
        self.assertTrue(os.access(GATE, os.X_OK))


if __name__ == "__main__":
    unittest.main()
