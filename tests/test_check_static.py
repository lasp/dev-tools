"""Tests for scripts/check_static.py. Run with `python3 -m unittest discover -s tests`.

Each test builds a small plugin tree in a temporary directory: one skill, one agent, their
Copilot links, a README with a skills table and a `.review/` table, and the real `record.py` and
record fixtures for the round trip, with a stub `ratchet_counts.py` standing in so the result
does not depend on the real counter.
"""

import contextlib
import importlib.util
import io
import json
import re
import shutil
import sys
import tempfile
import types
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("check_static", ROOT / "scripts" / "check_static.py")
check_static = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_static)

SKILL = """---
name: alpha
description: >
  Does one thing.
argument-hint: "[x]"
metadata:
  author: dev-tools
---

Run `alpha-reader` and then `/lasp-dev:alpha`. Read `${CLAUDE_SKILL_DIR}/notes.md`.
Run `python3 scripts/record.py --state`. Write `.review/alpha/<ticket>.md`.
"""
AGENT = """---
name: alpha-reader
description: Reads for alpha.
disallowedTools:
  - Edit
skills:
  - lasp-dev:alpha
model: sonnet
---

Runs `${CLAUDE_PLUGIN_ROOT}/scripts/record.py`.
"""
README = """# Plugin

## What is included

- `alpha`: does one thing.

| Group | Skill | Started | Use it to |
| --- | --- | --- | --- |
| Entry point | `alpha` | typed or asked | Do one thing |

## Layout

| File in `.review/` | Written by | Read by | Cleared when |
| --- | --- | --- | --- |
| `alpha/<ticket>.md` | `alpha` | The person | Never |
"""
# Counts the findings the way the records are written, so the round trip passes.
GOOD_COUNTS = '''import re
from collections import Counter, defaultdict
def count(log, since=None):
    table = defaultdict(Counter)
    for p in sorted(log.glob("pr-*.yaml")):
        section = p.read_text().split("\\nfindings:", 1)[1].split("\\nquestions:", 1)[0]
        for item in re.split(r"^  - ", section, flags=re.M)[1:]:
            row = table[re.search(r"key: (\\S+)", item).group(1).split("/")[0]]
            row["firings"] += 1
            v = re.search(r"verdict: (\\w+)", item).group(1)
            v = {"unparsed": "unanswered", "contested": "open-contest"}.get(v, v)
            row[v] += 1
            row["contested"] += "\\n    contested: true" in item and v != "open-contest"
    return table
'''


class StaticCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "skills/alpha").mkdir(parents=True)
        (self.tmp / "skills/alpha/SKILL.md").write_text(SKILL)
        (self.tmp / "skills/alpha/notes.md").write_text("notes\n")
        (self.tmp / "agents").mkdir()
        (self.tmp / "agents/alpha-reader.md").write_text(AGENT)
        (self.tmp / "README.md").write_text(README)
        (self.tmp / ".github/skills").mkdir(parents=True)
        (self.tmp / ".github/skills/alpha").symlink_to("../../skills/alpha")
        (self.tmp / ".github/agents").mkdir()
        (self.tmp / ".github/agents/alpha-reader.agent.md").symlink_to("../../agents/alpha-reader.md")
        (self.tmp / ".claude-plugin").mkdir()
        (self.tmp / ".claude-plugin/plugin.json").write_text('{"name": "lasp-dev"}\n')
        (self.tmp / "scripts").mkdir()
        shutil.copy(ROOT / "scripts/record.py", self.tmp / "scripts/record.py")
        # record.py reads the attribution phrases through profile.py.
        shutil.copy(ROOT / "scripts/profile.py", self.tmp / "scripts/profile.py")
        (self.tmp / "standards").mkdir()
        shutil.copy(ROOT / "standards/default-profile.yaml", self.tmp / "standards/default-profile.yaml")
        (self.tmp / "scripts/ratchet_counts.py").write_text(GOOD_COUNTS)
        shutil.copytree(ROOT / "tests", self.tmp / "tests", ignore=shutil.ignore_patterns("__pycache__", "live"))

    def failures(self, *checks: str) -> list[str]:
        plugin = check_static.Plugin(self.tmp)
        for name in checks:
            getattr(plugin, f"check_{name}")()
        return plugin.failures

    def edit(self, rel: str, old: str, new: str) -> None:
        path = self.tmp / rel
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new))

    def test_a_consistent_tree_passes_every_check(self):
        checks = ("frontmatter", "references", "plugin_vars", "review_map", "copilot_links", "readme_skills", "round_trip")
        self.assertEqual(self.failures(*checks), [])

    def test_frontmatter_names_keys_models_and_skills(self):
        self.edit("skills/alpha/SKILL.md", "name: alpha\n", "name: beta\nwhen: always\n")
        self.edit("agents/alpha-reader.md", "model: sonnet", "model: gpt")
        self.edit("agents/alpha-reader.md", "  - lasp-dev:alpha\n", "  - lasp-dev:gamma\n  - alpha\n")
        self.edit("agents/alpha-reader.md", "  - Edit\n", "  - Edti\n")
        got = self.failures("frontmatter")
        self.assertIn("frontmatter: skills/alpha/SKILL.md: unknown key 'when'", got)
        self.assertIn("frontmatter: skills/alpha/SKILL.md: name 'beta' is not the directory name 'alpha'", got)
        self.assertTrue(any("model 'gpt'" in f for f in got))
        self.assertTrue(any("skills names 'lasp-dev:gamma', which is not a skill here" in f for f in got))
        self.assertTrue(any("skills names 'alpha'; write it lasp-dev:<skill>" in f for f in got))
        self.assertTrue(any("unknown tool 'Edti'" in f for f in got))

    def test_the_plugin_name_comes_from_the_manifest(self):
        (self.tmp / ".claude-plugin/plugin.json").write_text('{"name": "lasp-tools"}\n')
        self.assertIn(
            "frontmatter: agents/alpha-reader.md: skills names 'lasp-dev:alpha'; write it lasp-tools:<skill>",
            self.failures("frontmatter"),
        )

    def test_a_missing_frontmatter_block_or_description_fails(self):
        (self.tmp / "agents/alpha-reader.md").write_text("# no frontmatter\n")
        self.edit("skills/alpha/SKILL.md", "  Does one thing.\n", "")
        got = self.failures("frontmatter")
        self.assertIn("frontmatter: agents/alpha-reader.md: no frontmatter block", got)
        self.assertIn("frontmatter: skills/alpha/SKILL.md: empty description", got)

    def test_references_resolve_skills_paths_agents_and_flags(self):
        self.edit("skills/alpha/SKILL.md", "/lasp-dev:alpha", "/lasp-dev:omega")
        self.edit("skills/alpha/SKILL.md", "notes.md", "nodes.md")
        self.edit("skills/alpha/SKILL.md", "`alpha-reader`", "`alpha-planner`")
        self.edit("skills/alpha/SKILL.md", "--state", "--stat")
        self.edit("agents/alpha-reader.md", "scripts/record.py", "scripts/recorder.py")
        got = self.failures("references")
        self.assertIn("references: skills/alpha/SKILL.md: /lasp-dev:omega is not a skill", got)
        self.assertIn("references: skills/alpha/SKILL.md: ${CLAUDE_SKILL_DIR}/nodes.md does not exist", got)
        self.assertIn("references: skills/alpha/SKILL.md: alpha-planner reads as an agent, and there is no agents/alpha-planner.md", got)
        self.assertIn("references: skills/alpha/SKILL.md: record.py has no --stat", got)
        self.assertIn("references: agents/alpha-reader.md: ${CLAUDE_PLUGIN_ROOT}/scripts/recorder.py does not exist", got)

    def test_a_plugin_variable_in_a_support_file_fails_plugin_vars(self):
        (self.tmp / "skills/alpha/notes.md").write_text('Run `"${CLAUDE_PLUGIN_ROOT}/scripts/record.py"`, then `${CLAUDE_SKILL_DIR}/x.md`.\n')
        self.assertEqual(
            self.failures("plugin_vars"),
            [
                "plugin-vars: skills/alpha/notes.md: ${CLAUDE_PLUGIN_ROOT} is expanded only in a SKILL.md or an agent",
                "plugin-vars: skills/alpha/notes.md: ${CLAUDE_SKILL_DIR} is expanded only in a SKILL.md or an agent",
            ],
        )

    def test_a_plugin_root_path_that_does_not_exist_fails_plugin_vars(self):
        (self.tmp / "skills/alpha/notes.md").write_text("Run `<plugin root>/scripts/record.py`, then `<plugin root>/scripts/nope.py`.\n")
        self.assertEqual(self.failures("plugin_vars"), ["plugin-vars: skills/alpha/notes.md: <plugin root>/scripts/nope.py does not exist"])

    def test_a_bot_login_is_not_read_as_an_agent(self):
        self.edit("skills/alpha/SKILL.md", "`alpha-reader`", "`copilot-pull-request-reviewer`")
        self.assertEqual(self.failures("references"), [])

    def test_a_review_path_with_no_row_fails(self):
        self.edit("skills/alpha/SKILL.md", ".review/alpha/<ticket>.md", ".review/beta.md")
        self.assertEqual(
            self.failures("review_map"),
            ["review-map: skills/alpha/SKILL.md: .review/beta.md has no row in the README's `.review/` table"],
        )

    def test_a_directory_or_shell_prefix_of_a_row_matches(self):
        self.edit("skills/alpha/SKILL.md", ".review/alpha/<ticket>.md", ".review/alpha and .review/alpha/${t}.md")
        self.assertEqual(self.failures("review_map"), [])

    def test_a_missing_wrong_or_stray_copilot_link_fails(self):
        (self.tmp / ".github/skills/alpha").unlink()
        (self.tmp / ".github/agents/alpha-reader.agent.md").unlink()
        (self.tmp / ".github/agents/alpha-reader.agent.md").symlink_to("../../skills/alpha/SKILL.md")
        (self.tmp / ".github/skills/gone").symlink_to("../../skills/gone")
        self.assertEqual(
            self.failures("copilot_links"),
            [
                "copilot-links: .github/skills/alpha: is not a symlink to ../../skills/alpha",
                "copilot-links: .github/agents/alpha-reader.agent.md: links to ../../skills/alpha/SKILL.md, not ../../agents/alpha-reader.md",
                "copilot-links: .github/skills/gone: names no skill or agent",
            ],
        )

    def test_a_copy_in_place_of_a_link_fails(self):
        (self.tmp / ".github/skills/alpha").unlink()
        shutil.copytree(self.tmp / "skills/alpha", self.tmp / ".github/skills/alpha")
        self.assertEqual(self.failures("copilot_links"), ["copilot-links: .github/skills/alpha: is not a symlink to ../../skills/alpha"])

    def test_a_typed_skill_missing_from_the_table_or_the_list_fails(self):
        (self.tmp / "skills/gamma").mkdir()
        (self.tmp / "skills/gamma/SKILL.md").write_text(SKILL.replace("name: alpha", "name: gamma"))
        self.edit("README.md", "- `alpha`: does one thing.\n", "")
        self.assertEqual(
            self.failures("readme_skills"),
            [
                "readme-skills: README.md: `alpha` is not in the list above the skills table",
                "readme-skills: README.md: `gamma` has no row in the skills table",
                "readme-skills: README.md: `gamma` is not in the list above the skills table",
            ],
        )

    def test_a_hidden_skill_needs_no_line_and_a_name_that_is_no_skill_fails(self):
        (self.tmp / "skills/beta").mkdir()
        (self.tmp / "skills/beta/SKILL.md").write_text(SKILL.replace("name: alpha", "name: beta\nuser-invocable: false"))
        self.edit("README.md", "| Do one thing |\n", "| Do one thing |\n| | `beta` | hidden | Load |\n| | `delta` | typed only | Gone |\n")
        self.assertEqual(self.failures("readme_skills"), ["readme-skills: README.md: `delta` is not a skill"])

    def test_the_table_and_the_list_disagree_on_what_is_typed(self):
        (self.tmp / "skills/beta").mkdir()
        (self.tmp / "skills/beta/SKILL.md").write_text(SKILL.replace("name: alpha", "name: beta\nuser-invocable: false"))
        self.edit("README.md", "| `alpha` | typed or asked |", "| `alpha` | hidden |")
        self.edit("README.md", "| Do one thing |\n", "| Do one thing |\n| | `beta` | typed only | Load |\n")
        self.assertEqual(
            self.failures("readme_skills"),
            [
                "readme-skills: README.md: `beta` is typed in the skills table and not in the list above it",
                "readme-skills: README.md: `alpha` is in the list above the skills table and not typed in it",
            ],
        )

    def test_a_readme_with_no_skills_table_fails(self):
        self.edit("README.md", "| Group | Skill |", "| Group | Name |")
        self.assertEqual(self.failures("readme_skills"), ['readme-skills: README.md: "What is included" has no skills table'])

    def test_a_counter_that_cannot_read_a_record_fails_the_round_trip(self):
        (self.tmp / "scripts/ratchet_counts.py").write_text("def count(log, since=None):\n    raise ValueError('no key')\n")
        self.assertEqual(
            self.failures("round_trip"),
            ["round-trip: scripts/ratchet_counts.py: cannot read record.py's output: no key"],
        )

    def test_a_counter_that_miscounts_fails_the_round_trip(self):
        (self.tmp / "scripts/ratchet_counts.py").write_text("def count(log, since=None):\n    return {}\n")
        got = self.failures("round_trip")
        self.assertEqual(len(got), 1)
        self.assertIn("counted {'firings': 0", got[0])

    def test_the_round_trip_builds_from_its_own_trees_fixtures_whatever_is_already_imported(self):
        stale = types.ModuleType("test_record")
        with unittest.mock.patch.dict(sys.modules, {"test_record": stale}):
            self.assertEqual(self.failures("round_trip"), [])


class CouplingCheck(unittest.TestCase):
    """The coupling count, on a tree whose mission is `acme`: one mention in a generic file, and
    more in an excluded skill and in the baseline itself."""

    BASELINE = {
        "counts": {"skills/alpha/notes.md": 1},
        "mission": {"skills/beta/": "acme's own skill"},
        "patterns": {r"\bacme\b": "the mission"},
    }

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for rel, text in (("skills/alpha/notes.md", "Ask acme.\nAsk anyone.\n"), ("skills/beta/SKILL.md", "acme\n"),
                          (".claude-plugin/plugin.json", '{"name": "acme-tools"}\n')):
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / rel).write_text(text)
        (self.tmp / "scripts").mkdir()
        self.baseline = self.tmp / "scripts/coupling.json"
        self.baseline.write_text(json.dumps(self.BASELINE, indent=2, sort_keys=True) + "\n")

    def run_plugin(self, method: str) -> list[str]:
        plugin = check_static.Plugin(self.tmp)
        getattr(plugin, method)()
        return plugin.failures

    def test_the_baseline_as_written_passes(self):
        self.assertEqual(self.run_plugin("check_coupling"), [])

    def test_a_new_mention_fails_in_a_counted_file_and_a_new_one(self):
        (self.tmp / "skills/alpha/notes.md").write_text("Ask acme.\nAsk acme again.\n")
        (self.tmp / "agents").mkdir()
        (self.tmp / "agents/alpha-reader.md").write_text("Reads acme.\n")
        self.assertEqual(
            self.run_plugin("check_coupling"),
            [
                "coupling: agents/alpha-reader.md: 1 mention(s), 0 in scripts/coupling.json: "
                "remove the new mention; if it moved, move its old entry by hand; "
                "if it is mission content, add its path to `mission` with why",
                "coupling: skills/alpha/notes.md: 2 mention(s), 1 in scripts/coupling.json: remove the new mention",
            ],
        )

    def test_an_excluded_path_is_not_counted(self):
        (self.tmp / "skills/beta/SKILL.md").write_text("acme\nacme\n")
        (self.tmp / "skills/beta/notes.md").write_text("acme\n")
        (self.tmp / "skills/beta/refs").mkdir()
        (self.tmp / "skills/beta/refs/README.md").write_text("acme\n")
        self.assertEqual(self.run_plugin("check_coupling"), [])

    def test_the_readme_directly_in_an_excluded_directory_is_counted(self):
        (self.tmp / "skills/beta/README.md").write_text("Each entry names acme.\n")
        self.assertEqual(
            [f.split(": remove")[0] for f in self.run_plugin("check_coupling")],
            ["coupling: skills/beta/README.md: 1 mention(s), 0 in scripts/coupling.json"],
        )

    def test_each_mention_counts_however_the_lines_wrap(self):
        self.baseline.write_text(json.dumps({**self.BASELINE, "counts": {"skills/alpha/notes.md": 2}}))
        for text, failures in (
            ("Ask acme or acme.\n", []),
            ("Ask acme\nor acme.\n", []),
            ("Ask acme, acme or acme.\n", ["coupling: skills/alpha/notes.md: 3 mention(s), 2 in scripts/coupling.json: remove the new mention"]),
        ):
            with self.subTest(text):
                (self.tmp / "skills/alpha/notes.md").write_text(text)
                self.assertEqual(self.run_plugin("check_coupling"), failures)

    def test_a_lowered_count_fails_as_stale_until_the_update_lowers_the_baseline(self):
        (self.tmp / "skills/alpha/notes.md").write_text("Ask anyone.\n")
        self.assertEqual(
            self.run_plugin("check_coupling"),
            [
                "coupling: skills/alpha/notes.md: 0 mention(s), 1 in scripts/coupling.json: "
                "lower it with `python3 scripts/check_static.py --update-coupling`"
            ],
        )
        self.assertEqual(self.run_plugin("update_coupling"), [])
        self.assertEqual(self.run_plugin("check_coupling"), [])

    def test_the_update_writes_the_baseline(self):
        (self.tmp / "skills/alpha/notes.md").write_text("Ask anyone.\n")
        (self.tmp / "skills/alpha/SKILL.md").write_text("acme\n")
        self.baseline.write_text(json.dumps({**self.BASELINE, "counts": {"skills/alpha/notes.md": 1, "skills/alpha/SKILL.md": 1}}))
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(check_static.main(["--root", str(self.tmp), "--update-coupling"]), 0)
        want = {**self.BASELINE, "counts": {"skills/alpha/SKILL.md": 1}}
        self.assertEqual(self.baseline.read_text(), json.dumps(want, indent=2, sort_keys=True) + "\n")
        self.assertIn("coupling: 1 mention(s) in the generic files", err.getvalue())

    def test_the_update_refuses_a_raise_and_writes_nothing(self):
        (self.tmp / "skills/alpha/notes.md").write_text("Ask acme.\nAsk acme again.\n")
        (self.tmp / "agents").mkdir()
        (self.tmp / "agents/alpha-reader.md").write_text("Reads acme.\n")
        before = self.baseline.read_text()
        self.assertEqual(
            self.run_plugin("update_coupling"),
            [
                "coupling: agents/alpha-reader.md: 1 mention(s), 0 in scripts/coupling.json: the update only lowers a count; "
                "if it moved, move its old entry by hand; if it is mission content, add its path to `mission` with why",
                "coupling: skills/alpha/notes.md: 2 mention(s), 1 in scripts/coupling.json: the update only lowers a count",
            ],
        )
        self.assertEqual(self.baseline.read_text(), before)

    def test_a_moved_file_names_the_entry_to_move(self):
        (self.tmp / "skills/alpha/notes.md").rename(self.tmp / "skills/alpha/guide.md")
        moved = "coupling: skills/alpha/guide.md: 1 mention(s), 0 in scripts/coupling.json: "
        hint = "if it moved from skills/alpha/notes.md, move that entry by hand"
        self.assertEqual(
            self.run_plugin("check_coupling"),
            [
                f"{moved}remove the new mention; {hint}; if it is mission content, add its path to `mission` with why",
                "coupling: skills/alpha/notes.md: 0 mention(s), 1 in scripts/coupling.json: "
                "lower it with `python3 scripts/check_static.py --update-coupling`",
            ],
        )
        self.assertEqual(
            self.run_plugin("update_coupling"),
            [f"{moved}the update only lowers a count; {hint}; if it is mission content, add its path to `mission` with why"],
        )

    def test_a_baseline_missing_a_key_fails(self):
        self.baseline.write_text(json.dumps({"counts": {}, "patterns": {}}))
        self.assertEqual(
            self.run_plugin("check_coupling"),
            ["coupling: scripts/coupling.json: the baseline is not an object of three objects, counts, mission and patterns"],
        )

    def test_a_malformed_baseline_fails(self):
        for name, text, why in (
            ("not JSON", "{", "cannot read the baseline: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"),
            ("a zero count", json.dumps({**self.BASELINE, "counts": {"skills/alpha/notes.md": 0}}), "a count is not a positive integer"),
            ("a string count", json.dumps({**self.BASELINE, "counts": {"skills/alpha/notes.md": "1"}}), "a count is not a positive integer"),
            (
                "a bad pattern",
                json.dumps({**self.BASELINE, "patterns": {"(": "unclosed"}}),
                "a pattern is not a regular expression: missing ), unterminated subpattern at position 0",
            ),
        ):
            with self.subTest(name):
                self.baseline.write_text(text)
                self.assertEqual(self.run_plugin("check_coupling"), [f"coupling: scripts/coupling.json: {why}"])

    def test_a_mission_path_must_exist_and_a_directory_must_end_in_a_slash(self):
        slash = "write a directory with a trailing / and a file without"
        for name, entry, why in (
            ("missing", "skills/gone/", "does not exist: remove its entry"),
            ("no trailing slash", "skills/beta", f"is a directory: {slash}"),
            ("a file with a slash", "skills/alpha/notes.md/", f"is a file: {slash}"),
        ):
            with self.subTest(name):
                self.baseline.write_text(json.dumps({**self.BASELINE, "mission": {entry: "excluded"}}))
                self.assertEqual(self.run_plugin("check_coupling"), [f"coupling: scripts/coupling.json: mission's {entry} {why}"])
        with self.subTest("under another mission directory"):
            self.baseline.write_text(json.dumps({**self.BASELINE, "mission": {"skills/beta/": "x", "skills/beta/SKILL.md": "x"}}))
            self.assertEqual(
                self.run_plugin("check_coupling"),
                ["coupling: scripts/coupling.json: mission's skills/beta/SKILL.md is under mission's skills/beta/: remove it"],
            )

    def test_the_real_patterns_count_the_mission_and_not_the_plugin_name(self):
        patterns = [re.compile(p) for p in json.loads((ROOT / "scripts/coupling.json").read_text())["patterns"]]
        for line, mentions in (
            ("LASP-Libera/libera_utils", 2),
            ("implementation-plan-libsdc-830.md", 1),
            ("a csds reader", 1),
            ("the year plan, page 87654321.", 1),
            ("libera.example.net/wiki/spaces/LIBERA/pages/87654321", 3),
            ("libera_12345678", 1),
            ("run /lasp-dev:work", 0),
            ("install lasp-dev@lasp-dev-tools", 0),
            ("deliberately", 0),
            ("v1.12345678", 0),
            ("12345678.9", 0),
        ):
            with self.subTest(line):
                self.assertEqual(sum(len(rx.findall(line)) for rx in patterns), mentions)


class ContractChecks(unittest.TestCase):
    """The contract, body and sections checks, each on a copy of this plugin with one mutation."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for d in ("skills", "agents", "scripts", "standards", "hooks"):
            shutil.copytree(ROOT / d, self.tmp / d, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "docs", self.tmp / "docs")
        shutil.copytree(ROOT / ".claude-plugin", self.tmp / ".claude-plugin")
        shutil.copytree(ROOT / ".github", self.tmp / ".github", symlinks=True)
        shutil.copytree(ROOT / "tests", self.tmp / "tests", ignore=shutil.ignore_patterns("__pycache__", "live"))
        shutil.copytree(ROOT / "sandbox", self.tmp / "sandbox", ignore=shutil.ignore_patterns("__pycache__"))
        for f in ("GUIDE.md", "README.md", "ROADMAP.md", ".claude/CLAUDE.md"):
            (self.tmp / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / f, self.tmp / f)

    def failures(self, check: str) -> list[str]:
        plugin = check_static.Plugin(self.tmp)
        getattr(plugin, f"check_{check}")()
        return plugin.failures

    def edit(self, rel: str, old: str, new: str) -> None:
        path = self.tmp / rel
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_the_plugin_as_it_stands_passes(self):
        for check in ("contract", "body", "sections", "paths", "dials", "contracts", "profiles", "plugin_vars", "coupling", "copilot_links", "readme_skills"):
            self.assertEqual(self.failures(check), [], check)

    def test_a_plan_line_missing_from_body_md_fails_body(self):
        self.edit("skills/pr-create/body.md", "Plan: ", "Approved: ")
        self.assertEqual(
            self.failures("body"),
            ["body: skills/pr-create/body.md: the Already checked block has no 'Plan:' line, which record.py requires"],
        )

    def test_a_renamed_optional_line_in_body_md_fails_body(self):
        for label, renamed in (("Rules checked: ", "Rules fired: "), ("Declined: ", "Left: ")):
            with self.subTest(label=label):
                self.edit("skills/pr-create/body.md", label, renamed)
                self.assertEqual(
                    self.failures("body"),
                    [f"body: skills/pr-create/body.md: the Already checked block has no {label.strip()!r} line, which record.py reads"],
                )
                self.edit("skills/pr-create/body.md", renamed, label)

    def test_a_renamed_summary_heading_fails_contract(self):
        self.edit("skills/pr-review/SKILL.md", "## Review\nreviewed:", "## Code review\nreviewed:")
        self.assertEqual(
            self.failures("contract"),
            ['contract: skills/pr-review/SKILL.md: "The review" has no summary block or no Should fix comment block'],
        )
        self.edit("skills/pr-review/SKILL.md", "## Code review\nreviewed:", "## Review\nreviewed at:")
        got = self.failures("contract")
        self.assertTrue(any("does not read the summary as a findings review" in f for f in got), got)

    def test_a_contract_pinned_by_a_missing_test_fails_contracts(self):
        self.edit("docs/contracts.md", "test_reproduces_the_committed_record", "test_that_does_not_exist")
        self.assertEqual(
            self.failures("contracts"),
            ['contracts: docs/contracts.md: "The record" is pinned by tests/test_record.py::test_that_does_not_exist, which does not exist'],
        )

    def test_a_finding_comment_the_parser_reads_differently_fails_contract(self):
        self.edit("skills/pr-review/SKILL.md", "**Should fix** — a predicate", "**Should fix** — the predicate")
        got = self.failures("contract")
        self.assertTrue(any("reads the finding comment as" in f for f in got), got)

    def test_a_severity_example_without_its_dash_fails_contract(self):
        self.edit("skills/pr-review/comment-style.md", "**Must fix before merge** — expired", "**Must fix before merge**: expired")
        self.assertEqual(
            self.failures("contract"),
            ["contract: skills/pr-review/comment-style.md: the Severity Line example does not match record.py's LABEL"],
        )

    def test_a_contract_with_no_pin_fails_contracts(self):
        self.edit("docs/contracts.md", "Pinned by: tests/test_record.py::test_reproduces_the_committed_record", "")
        self.assertEqual(self.failures("contracts"), ['contracts: docs/contracts.md: "The record" has no Pinned by: line'])

    def test_a_sibling_skill_path_resolves_and_a_heading_inside_a_fence_does_not_count(self):
        self.edit("skills/pr-fix/SKILL.md", "`pr-review`'s \"Whose reply counts\"", "`${CLAUDE_SKILL_DIR}/../work/SKILL.md`'s \"Fenced heading\"")
        self.edit("skills/work/SKILL.md", "## Never\n", "```\n# Fenced heading\n```\n\n## Never\n")
        self.assertEqual(
            self.failures("sections"),
            ['sections: skills/pr-fix/SKILL.md: `work` "Fenced heading" is not a heading in skills/work/SKILL.md'],
        )

    def test_a_standard_path_with_no_word_on_where_the_directory_is_fails_plugin_vars(self):
        self.edit("skills/pr-create/standard-repo.md", "`<standard>/templates/<name>/PULL_REQUEST_TEMPLATE.md`, `<standard>` being what\n`python3 \"<plugin root>/scripts/profile.py\" --standard` prints. When either exits 1",
                  "`<standard>/templates/<name>/PULL_REQUEST_TEMPLATE.md`. When either exits 1")
        self.assertEqual(self.failures("plugin_vars"),
                         ["plugin-vars: skills/pr-create/standard-repo.md: writes <standard>/ and does not say it is what profile.py --standard prints"])

    def test_a_default_profile_the_resolver_refuses_fails_profiles(self):
        self.edit("standards/default-profile.yaml", "  phrases: []\n", "")
        self.assertEqual(self.failures("profiles"),
                         ["profiles: standards/default-profile.yaml: standards/default-profile.yaml: leaves out attribution.phrases; the default profile sets every key, and a standard sets a section whole"])

    def test_a_default_profile_naming_a_missing_brief_fails_profiles(self):
        self.edit("standards/default-profile.yaml", "{glob: 'CHANGELOG.md', brief: documentation}", "{glob: 'CHANGELOG.md', brief: docs}")
        self.assertEqual(self.failures("profiles"),
                         ["profiles: standards/default-profile.yaml: depth.light names the brief 'docs', not a file in skills/implement-change/reviews/"])

    def test_an_example_profile_missing_a_key_fails_profiles(self):
        self.edit("standards/profile.example.yaml", "github_server:", "server:")
        self.assertEqual(
            self.failures("profiles"),
            ["profiles: standards/profile.example.yaml: its keys differ from profile.py's: ['github_server', 'server']"],
        )

    def test_a_reference_to_a_missing_section_fails_sections(self):
        self.edit("skills/pr-fix/SKILL.md", "`pr-review`'s \"Whose reply counts\"", "`pr-review`'s \"Whose word counts\"")
        self.assertEqual(
            self.failures("sections"),
            ['sections: skills/pr-fix/SKILL.md: `pr-review` "Whose word counts" is not a heading in skills/pr-review/SKILL.md'],
        )

    def test_a_path_the_documents_name_that_does_not_exist_fails_paths(self):
        self.edit("standards/README.md", "`standards/decisions.md` — decisions local to it", "`standards/test-lanes.md` — decisions local to it")
        self.assertEqual(self.failures("paths"), ["paths: standards/README.md: `standards/test-lanes.md` does not exist"])

    def test_a_reference_to_a_missing_roadmap_section_fails_sections(self):
        self.edit("standards/README.md", "## Dials\n\n", "## Dials\n\nSee `ROADMAP.md` \"Nope\".\n\n")
        self.assertEqual(
            self.failures("sections"),
            ['sections: standards/README.md: `ROADMAP.md` "Nope" is not a heading in ROADMAP.md'],
        )

    def test_a_readme_named_in_words_resolves_its_section(self):
        self.edit("GUIDE.md", "the README's \"MCP servers\"", "the README's \"Nope\"")
        self.edit("docs/design.md", "The corpus README, \"What lives here, and what does not\"", "The corpus README, \"Nope\"")
        self.assertEqual(
            self.failures("sections"),
            [
                'sections: GUIDE.md: `README.md` "Nope" is not a heading in README.md',
                'sections: docs/design.md: `standards/README.md` "Nope" is not a heading in standards/README.md',
            ],
        )

    def test_a_plugin_path_a_markdown_path_and_the_corpus_readmes_form_resolve_their_sections(self):
        self.edit("skills/ticket-draft/SKILL.md", "`standards/dials.md`), propose", "`${CLAUDE_PLUGIN_ROOT}/standards/dials.md` \"Nope\"), propose")
        self.edit("GUIDE.md", "## Glossary\n", "## Glossary\n\nSee `skills/revise/outline.md` \"Nope\" and the corpus README's \"Nope\".\n")
        self.assertEqual(
            self.failures("sections"),
            [
                'sections: GUIDE.md: `skills/revise/outline.md` "Nope" is not a heading in skills/revise/outline.md',
                'sections: GUIDE.md: `standards/README.md` "Nope" is not a heading in standards/README.md',
                'sections: skills/ticket-draft/SKILL.md: `standards/dials.md` "Nope" is not a heading in standards/dials.md',
            ],
        )

    def test_a_skill_relative_path_and_a_summary_label_resolve(self):
        (self.tmp / "skills/pr-create/notes.md").write_text("<details><summary>Kept</summary></details>\n")
        self.edit("skills/pr-create/SKILL.md", "## ", "See `${CLAUDE_SKILL_DIR}/notes.md` \"Kept\" and `notes.md` \"Gone\".\n\n## ")
        self.assertEqual(
            self.failures("sections"),
            ['sections: skills/pr-create/SKILL.md: `skills/pr-create/notes.md` "Gone" is not a heading in skills/pr-create/notes.md'],
        )

    def test_a_link_to_a_missing_file_or_heading_fails_paths(self):
        self.edit("README.md", "](docs/design.md)", "](docs/nope.md)")
        self.edit("README.md", "](GUIDE.md#glossary)", "](GUIDE.md#nope)")
        self.edit("docs/design.md", "**Where this departs from the design document.**", "**Where this departs from the design document.** [x](contracts.md#nope)")
        self.assertEqual(
            self.failures("paths"),
            [
                "paths: README.md: the link (GUIDE.md#nope) names no heading of GUIDE.md",
                "paths: README.md: the link (docs/nope.md) names a file that does not exist",
                "paths: docs/design.md: the link (contracts.md#nope) names no heading of docs/contracts.md",
            ],
        )

    def test_a_dials_row_counts_as_a_section(self):
        self.edit("GUIDE.md", "## Glossary\n", "## Glossary\n\nSee `standards/dials.md` \"Established\" and `standards/dials.md` \"Deep review\".\n")
        self.assertEqual(self.failures("sections"), [])

    def test_a_link_inside_code_is_not_read_and_a_repeated_heading_takes_its_suffix(self):
        self.edit("GUIDE.md", "## Glossary\n", "## Glossary\n\n```\nx[0](nope)\n```\n\nInline `[a](nope.md)`; [twice](README.md#glossary-1).\n\n## Glossary\n")
        self.assertEqual(self.failures("paths"), ["paths: GUIDE.md: the link (README.md#glossary-1) names no heading of README.md"])
        self.edit("README.md", "## Layout\n", "## Glossary\n\n## Glossary\n\n## Layout\n")
        self.assertEqual(self.failures("paths"), [])

    def test_a_dial_that_is_not_a_row_fails_dials(self):
        self.edit("docs/design.md", "the Provisional expiry, Established expiry and Low agree rate Dials", "the Provisional expiry, Late expiry and Low agree rate Dials")
        self.edit("GUIDE.md", "the Admission Dial", "the Admission or Nope Dial")
        self.edit("skills/ticket-draft/SKILL.md", '"Split before starting" threshold', '"Split first" threshold')
        self.assertEqual(
            self.failures("dials"),
            [
                'dials: GUIDE.md: "Nope" is not a row of standards/dials.md',
                'dials: docs/design.md: "Late expiry" is not a row of standards/dials.md',
                'dials: skills/ticket-draft/SKILL.md: "Split first" is not a row of standards/dials.md',
            ],
        )

    def test_an_adopting_repository_path_and_a_placeholder_pass_paths(self):
        self.edit("standards/README.md", "## Dials\n\n", "## Dials\n\nSee `standards/review-rules.md` and `standards/<repo>/x.md`.\n\n")
        self.assertEqual(self.failures("paths"), [])

    def test_a_fixture_the_lint_no_longer_passes_fails_rule_bar(self):
        self.edit("tests/fixtures/rule-bar/loader.py", "def load(path: Path)", "def load(path)")
        got = self.failures("rule_bar")
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith('rule-bar: scripts/rule_lint.py: the fixture fails: anchors: R-001: "path: Path" is not in load in pkg/loader.py'))

    def test_a_standards_skill_that_drops_the_bar_fails_rule_bar(self):
        path = self.tmp / "skills/revise/SKILL.md"
        path.write_text(path.read_text().replace("rule-bar.md", "the bar"))
        self.assertEqual(self.failures("rule_bar"), ["rule-bar: skills/revise/SKILL.md: does not name rule-bar.md"])

    def test_a_reader_that_drops_the_conversation_comments_fails_contract(self):
        self.edit("agents/pr-reader.md", "`issue-comments.json` and `body.md` beside them", "the conversation and `body.md` beside them")
        self.assertEqual(self.failures("contract"), ['contract: agents/pr-reader.md: "The dump" does not name `issue-comments.json`'])


if __name__ == "__main__":
    unittest.main()
