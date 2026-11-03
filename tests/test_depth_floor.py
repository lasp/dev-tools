"""Tests for scripts/depth_floor.py, on scratch repositories. Run with `python3 -m unittest discover -s tests`."""

import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("depth_floor", ROOT / "scripts" / "depth_floor.py")
depth_floor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(depth_floor)

DEPTH = {
    "light": [
        {"glob": "CHANGELOG.md", "brief": "documentation"},
        {"glob": "doc/**/*.md", "brief": "documentation"},
        {"glob": "pyproject.toml", "hunk": "^version =", "brief": "documentation"},
    ],
    "deep": ["pkg/io/product_definition*", "**/manifest*"],
}


class Floor(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmp)
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", *args], check=True)
        self.write("pyproject.toml", '[project]\nname = "x"\nversion = "1.0.0"\n')
        self.write("pkg/a.py", "x = 1\n")
        self.write("CHANGELOG.md", "# Changes\n")
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "init"], check=True)

    def write(self, rel: str, text: str) -> None:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_a_changelog_and_a_version_bump_are_light(self):
        self.write("CHANGELOG.md", "# Changes\n\n- one\n")
        self.write("pyproject.toml", '[project]\nname = "x"\nversion = "1.0.1"\n')
        self.write("doc/source/new.md", "words\n")
        self.assertEqual(depth_floor.floor("main", DEPTH, None), ("light", "every changed path is on the light allowlist", ["documentation"]))

    def test_another_hunk_in_pyproject_is_standard(self):
        self.write("pyproject.toml", '[project]\nname = "y"\nversion = "1.0.1"\n')
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[:2], ("standard", "pyproject.toml is not on the light allowlist"))

    def test_code_is_standard_and_no_change_is_standard(self):
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[:2], ("standard", "no change against the base"))
        self.write("pkg/a.py", "x = 2\n")
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[:2], ("standard", "pkg/a.py is not on the light allowlist"))

    def test_a_deep_glob_or_an_altered_public_signature_is_deep(self):
        self.write("pkg/sub/manifest.json", "{}\n")
        self.assertEqual(
            depth_floor.floor("main", DEPTH, None)[:2],
            ("deep", "pkg/sub/manifest.json (untracked: part of the change?) matches the deep glob **/manifest*"),
        )
        os.remove("pkg/sub/manifest.json")
        # Outside the repository, as .review/ is ignored in one.
        plan = Path(tempfile.mkdtemp()) / "plan.md"
        self.addCleanup(subprocess.run, ["rm", "-rf", str(plan.parent)])
        plan.write_text("# Plan\n\n### Signatures\n\n- `pkg.a.read(path: Path)` · altered · public\n\n### Steps\n")
        self.write("CHANGELOG.md", "# Changes\n\n- one\n")
        self.assertEqual(depth_floor.floor("main", DEPTH, plan)[0], "deep")
        plan.write_text("# Plan\n\n### Signatures\n\n- `pkg.a._helper()` · added · private\n")
        self.assertEqual(depth_floor.floor("main", DEPTH, plan)[0], "light")
        plan.write_text("# Plan\n\n### Signatures\n\nnone: no public signature is altered or removed\n")
        self.assertEqual(depth_floor.floor("main", DEPTH, plan)[0], "light")

    def test_a_plan_whose_signatures_cannot_be_read_is_refused(self):
        plan = Path(tempfile.mkdtemp()) / "plan.md"
        self.addCleanup(subprocess.run, ["rm", "-rf", str(plan.parent)])
        for text, why in (
            ("# Plan\n\n### Steps\n", "no ### Signatures section"),
            ("# Plan\n\n## Signatures\n\n- `pkg.a.read()` · altered · public\n", "no ### Signatures section"),
            ("# Plan\n\n### Signatures\n\n### Steps\n", "section is empty"),
            ("# Plan\n\n### Signatures\n\n- `pkg.a.read()` - altered - public\n", "not in the template's shape"),
            ("# Plan\n\n### Signatures\n\nNote: only a note\n", "section is empty"),
            ("# Plan\n\n### Signatures\n\n- ``pkg.a.read()` · altered · public\n", "not in the template's shape"),
            ("# Plan\n\n### Signatures\n\nNote: `pkg.a.read(x)` · altered · public\nnone\n", "inside a note"),
            ("# Plan\n\n### Signatures\n\n| `pkg.a.read()` | altered | public |\n", "not in the template's shape"),
        ):
            plan.write_text(text)
            with self.assertRaisesRegex(RuntimeError, why):
                depth_floor.floor("main", DEPTH, plan)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(depth_floor.main(["main", "--repo", "o/no_such_repo", "--signatures", str(plan)]), 1)
        self.assertIn("not in the template's shape", err.getvalue())
        self.assertIn("each line is `none`, `Note: <text>`, or", err.getvalue())

    def test_a_note_a_behavior_change_and_doubled_backticks_are_read(self):
        plan = Path(tempfile.mkdtemp()) / "plan.md"
        self.addCleanup(subprocess.run, ["rm", "-rf", str(plan.parent)])
        self.write("CHANGELOG.md", "# Changes\n\n- one\n")
        for text, level in (
            ("### Signatures\n\n- `pkg.a.read(path)` · behavior · public\n", "light"),
            ("### Signatures\n\nNote: `start` keeps its arguments\n- `pkg.a.read()` · behavior · public\n", "light"),
            ("### Signatures\n\n- Note: the hook modes below are its interface\n- ``build-record.sh take`` · added · public\n", "light"),
            ("### Signatures\n\nNote: only a note\nnone\n", "light"),
            ("### Signatures\n\n- ``a `b` c`` · altered · public\n", "deep"),
        ):
            plan.write_text(f"# Plan\n\n{text}")
            self.assertEqual(depth_floor.floor("main", DEPTH, plan)[0], level, text)

    def test_a_tracked_path_is_named_without_the_untracked_question(self):
        self.write("pkg/a.py", "x = 2\n")
        self.write("notes.md", "scratch\n")
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[:2], ("standard", "notes.md (untracked: part of the change?) is not on the light allowlist"))
        os.remove("notes.md")
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[:2], ("standard", "pkg/a.py is not on the light allowlist"))

    def test_a_file_moved_out_of_a_deep_path_is_still_deep(self):
        self.write("pkg/io/product_definition.yaml", "a: 1\n")
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "add"], check=True)
        subprocess.run(["git", "mv", "pkg/io/product_definition.yaml", "elsewhere.yaml"], check=True)
        self.assertEqual(depth_floor.floor("HEAD", DEPTH, None)[0], "deep")

    def test_a_base_that_moved_on_adds_none_of_its_changes(self):
        subprocess.run(["git", "switch", "-qc", "topic"], check=True)
        self.write("CHANGELOG.md", "# Changes\n\n- one\n")
        subprocess.run(["git", "commit", "-qam", "log"], check=True)
        subprocess.run(["git", "switch", "-q", "main"], check=True)
        self.write("pkg/sub/manifest.json", "{}\n")
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "manifest"], check=True)
        subprocess.run(["git", "switch", "-q", "topic"], check=True)
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[0], "light")

    def test_an_unrecorded_allowlist_and_an_untracked_hunk_file_are_not_light(self):
        self.write("CHANGELOG.md", "# Changes\n\n- one\n")
        self.assertEqual(depth_floor.floor("main", {"light": "not yet recorded", "deep": "not yet recorded"}, None)[0], "standard")
        os.remove("CHANGELOG.md")
        subprocess.run(["git", "checkout", "-q", "--", "CHANGELOG.md"], check=True)
        self.write("sub/pyproject.toml", 'version = "2"\n')
        depth = {"light": [{"glob": "**/pyproject.toml", "hunk": "^version =", "brief": "documentation"}], "deep": []}
        self.assertEqual(depth_floor.floor("main", depth, None)[0], "standard")

    def test_given_paths_are_judged_without_a_diff_and_a_hunk_entry_matches_provisionally(self):
        self.assertEqual(depth_floor.floor("main", DEPTH, None, ["CHANGELOG.md", "doc/a.md"])[:2], ("light", "every changed path is on the light allowlist"))
        self.assertEqual(
            depth_floor.floor("main", DEPTH, None, ["pyproject.toml"]),
            ("light", "every changed path is on the light allowlist; provisionally for pyproject.toml, whose hunk pattern the run over the diff checks", ["documentation"]),
        )
        self.assertEqual(depth_floor.floor("main", DEPTH, None, ["pyproject.toml", "pkg/a.py"])[0], "standard")
        self.assertEqual(depth_floor.floor("main", DEPTH, None, ["pkg/io/product_definition.py"])[0], "deep")

    def test_a_dependency_change_is_standard_whatever_the_diff_configuration(self):
        self.write("pyproject.toml", '[project]\nname = "x"\nversion = "1.0.0"\ndependencies = ["numpy>=2"]\n')
        driver = self.tmp.parent / f"{self.tmp.name}-difft"
        driver.write_text("#!/bin/sh\necho 'version = changed'\n")
        driver.chmod(0o755)
        self.addCleanup(driver.unlink)
        for key, value in (("diff.external", str(driver)), ("color.diff", "always"), ("diff.relative", "true")):
            subprocess.run(["git", "config", key, value], check=True)
            self.assertEqual(depth_floor.floor("main", DEPTH, None)[:2], ("standard", "pyproject.toml is not on the light allowlist"), key)

    def test_a_removed_line_that_starts_like_a_header_is_a_changed_line(self):
        self.write("pyproject.toml", '[project]\nname = "x"\nversion = "1.0.0"\nargs = """\n--strict\n"""\n')
        subprocess.run(["git", "commit", "-qam", "args"], check=True)
        self.write("pyproject.toml", '[project]\nname = "x"\nversion = "1.0.1"\nargs = """\n"""\n')
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[:2], ("standard", "pyproject.toml is not on the light allowlist"))

    def test_a_hunk_path_with_glob_characters_reads_only_its_own_lines(self):
        depth = {"light": [{"glob": "*.toml", "hunk": "^version =", "brief": "documentation"}], "deep": []}
        self.write("v[12].toml", 'version = "1"\n')
        self.write("v1.toml", 'version = "1"\n')
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "tomls"], check=True)
        self.write("v[12].toml", 'version = "2"\n')
        self.assertEqual(depth_floor.floor("main", depth, None)[0], "light")
        self.write("v1.toml", 'name = "y"\n')
        self.assertEqual(depth_floor.changed_lines(str(self.tmp), "main", "v[12].toml"), ['version = "1"', 'version = "2"'])

    def test_a_change_with_no_changed_lines_never_matches_a_hunk_entry(self):
        os.chmod("pyproject.toml", 0o755)
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[:2], ("standard", "pyproject.toml is not on the light allowlist"))

    def test_a_non_ascii_path_and_a_subdirectory_are_judged_from_the_top_level(self):
        self.write("pkg/io/product_definition_café.yaml", "a: 1\n")
        self.assertEqual(
            depth_floor.floor("main", DEPTH, None)[:2],
            ("deep", "pkg/io/product_definition_café.yaml (untracked: part of the change?) matches the deep glob pkg/io/product_definition*"),
        )
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "add"], check=True)
        self.write("pkg/io/product_definition_café.yaml", "a: 2\n")
        os.chdir("pkg")
        self.assertEqual(depth_floor.floor("main", DEPTH, None)[0], "deep")
        subprocess.run(["git", "checkout", "-q", "--", "io/product_definition_café.yaml"], check=True)
        self.write("pkg/io/product_definition.py", "x = 1\n")
        self.assertEqual(
            depth_floor.floor("main", DEPTH, None)[:2],
            ("deep", "pkg/io/product_definition.py (untracked: part of the change?) matches the deep glob pkg/io/product_definition*"),
        )

    def test_an_unrecorded_allowlist_means_nothing_is_light(self):
        self.write("CHANGELOG.md", "# Changes\n\n- one\n")
        self.assertEqual(depth_floor.floor("main", {"light": [], "deep": []}, None)[0], "standard")

    def test_with_no_profile_documentation_is_light_and_agent_instructions_are_not(self):
        default = depth_floor.load_profile().resolve("o/no_such_repo", ROOT)["depth"]
        self.write("CHANGELOG.md", "# Changes\n\n- one\n")
        self.write("README.md", "# x\n")
        self.write("docs/guide.md", "words\n")
        self.write("doc/source/a/b.md", "words\n")
        self.assertEqual(depth_floor.floor("main", default, None), ("light", "every changed path is on the light allowlist", ["documentation"]))
        for path in ("skills/x/SKILL.md", "agents/a.md", "CLAUDE.md", "AGENTS.md", ".github/instructions/x.instructions.md", "pkg/README.md", "docs/conf.py"):
            self.write(path, "words\n")
            self.assertEqual(depth_floor.floor("main", default, None)[:2], ("standard", f"{path} (untracked: part of the change?) is not on the light allowlist"))
            os.remove(path)
        deep = dict(default, deep=["**/manifest*"])
        self.write("docs/manifest.md", "words\n")
        self.assertEqual(depth_floor.floor("main", deep, None)[0], "deep")

    def test_the_reason_names_the_default_allowlist_when_the_profile_sets_none(self):
        self.write("CHANGELOG.md", "# Changes\n\n- one\n")

        def reason(repo: str) -> str:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(depth_floor.main(["main", "--repo", repo]), 0)
            return out.getvalue().splitlines()[1]

        self.assertEqual(reason("o/no_such_repo"), "reason: every changed path is on the default light allowlist")
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:someone/x.git"], check=True)
        self.write("standards/profile.yaml", "depth:\n  deep: ['**/manifest*']\n")
        subprocess.run(["git", "add", "standards"], check=True)
        subprocess.run(["git", "commit", "-qm", "standard"], check=True)
        self.assertEqual(reason("someone/x"), "reason: every changed path is on the default light allowlist")
        self.write("standards/profile.yaml", "depth:\n  light:\n    - {glob: 'CHANGELOG.md', brief: documentation}\n"
                                             "    - {glob: 'standards/*', brief: documentation}\n")
        self.assertEqual(reason("someone/x"), "reason: every changed path is on the light allowlist")
        self.write("pkg/a.py", "x = 2\n")
        self.write("standards/profile.yaml", "depth:\n  deep: ['**/manifest*']\n")
        self.assertEqual(reason("someone/x"), "reason: pkg/a.py is not on the default light allowlist")

    def test_main_prints_the_level_and_reason_and_refuses_a_bad_base(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(depth_floor.main(["main", "--repo", "o/no_such_repo"]), 0)
        self.assertEqual(out.getvalue(), "depth: standard\nreason: no change against the base\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(depth_floor.main(["no-such-base", "--repo", "o/no_such_repo"]), 1)
        self.assertIn("depth_floor.py: git merge-base no-such-base HEAD", err.getvalue())

    def test_globs(self):
        self.assertTrue(depth_floor.glob_regex("doc/**/*.md").match("doc/a/b/c.md"))
        self.assertTrue(depth_floor.glob_regex("doc/**/*.md").match("doc/c.md"))
        self.assertFalse(depth_floor.glob_regex("*.md").match("doc/c.md"))
        self.assertTrue(depth_floor.glob_regex("widgets/data/**").match("widgets/data/x/y.csv"))


if __name__ == "__main__":
    unittest.main()
