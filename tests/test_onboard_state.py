"""Tests for scripts/onboard_state.py, scripts/review_dir.sh's directory argument and survey.py's
`--standard none`: what onboarding's first step reads in one command."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "scripts" / "onboard_state.py"
SCRATCH = tempfile.TemporaryDirectory()


def tearDownModule():
    SCRATCH.cleanup()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def make_repo(files: dict, remote: str = "git@github.com:example-org/probe.git") -> Path:
    repo = Path(tempfile.mkdtemp(dir=SCRATCH.name)).resolve()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "remote", "add", "origin", remote)
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@example.org", "-c", "user.name=t", "-c", "commit.gpgsign=false",
        "commit", "-q", "--allow-empty", "-m", "init")
    return repo


def state(where: Path) -> dict:
    out = subprocess.run([sys.executable, str(STATE), "--repo", str(where)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(line.split(": ", 1) for line in out.stdout.splitlines() if not line.startswith("clone: ")) | {
        "clones": [line[len("clone: "):] for line in out.stdout.splitlines() if line.startswith("clone: ")]}


class State(unittest.TestCase):
    def test_a_plain_checkout_clones_into_itself(self):
        repo = make_repo({"README.md": "x\n"})
        s = state(repo)
        self.assertEqual(s["clone directory"], f"{repo}/.review/onboard/clone")
        self.assertEqual(s["clone directory note"], "none")
        self.assertEqual((s["own standard"], s["pointer"], s["standard setting"]), ("none", "none", "unset"))

    def test_a_linked_working_tree_clones_into_the_main_one_and_says_add_dir(self):
        repo = make_repo({"README.md": "x\n"})
        linked = Path(tempfile.mkdtemp(dir=SCRATCH.name)).resolve() / "wt"
        git(repo, "worktree", "add", "-q", "-b", "side", str(linked))
        s = state(linked)
        self.assertEqual(s["clone directory"], f"{repo}/.review/onboard/clone")
        self.assertIn(f"/add-dir {repo}", s["clone directory note"])

    def test_a_separate_git_directory_clones_into_this_working_tree(self):
        repo = make_repo({})
        tree = Path(tempfile.mkdtemp(dir=SCRATCH.name)).resolve()
        gitdir = Path(tempfile.mkdtemp(dir=SCRATCH.name)).resolve() / "g.git"
        subprocess.run(["git", "clone", "-q", "--separate-git-dir", str(gitdir), str(repo), str(tree / "c")], check=True)
        s = state(tree / "c")
        self.assertEqual(s["clone directory"], f"{tree / 'c'}/.review/onboard/clone")
        self.assertIn("clone of its own", s["clone directory note"])

    def test_a_pointer_is_named_and_an_uncommitted_one_marked(self):
        repo = make_repo({"standards/profile.yaml": "standard: example-org/std\n"})
        self.assertEqual(state(repo)["pointer"], "example-org/std")
        self.assertEqual(state(repo)["own standard"], "none")
        (repo / "standards/profile.yaml").write_text("standard: example-org/std\npublic: true\n")
        self.assertEqual(state(repo)["pointer"], "example-org/std")
        (repo / "standards/profile.yaml").write_text("standard: example-org/other\n")
        self.assertEqual(state(repo)["pointer"], "example-org/other (uncommitted)")

    def test_an_own_standard_lists_its_files(self):
        repo = make_repo({"standards/review-rules.md": "# Rules\n", "standards/profile.yaml": "public: true\n"})
        self.assertEqual(state(repo)["own standard"], "standards/review-rules.md, standards/profile.yaml")

    def test_the_setting_and_existing_clones_are_described(self):
        repo = make_repo({})
        clone = repo / ".review/onboard/clone/example-org__std"
        clone.mkdir(parents=True)
        git(clone, "init", "-q", "-b", "main")
        git(clone, "remote", "add", "origin", "git@github.com:example-org/std.git")
        git(clone, "-c", "user.email=t@example.org", "-c", "user.name=t", "-c", "commit.gpgsign=false",
            "commit", "-q", "--allow-empty", "-m", "local")
        git(repo, "config", "lasp-dev.standard", str(clone))
        s = state(repo)
        self.assertEqual(s["standard setting clone"], f"{clone}, origin example-org/std")
        self.assertEqual(s["clones"], ["example-org__std, origin example-org/std, branch main, 1 commits its origin does not hold"])
        (repo / ".review/onboard/clone/leftover").mkdir()
        self.assertIn("leftover, not a git checkout", state(repo)["clones"])
        (repo / ".review/onboard/clone/broken").mkdir()
        (repo / ".review/onboard/clone/broken/.git").write_text("gitdir: /nonexistent\n")
        self.assertIn("broken, not a git checkout", state(repo)["clones"])
        git(repo, "config", "lasp-dev.standard", str(repo / ".review/onboard/clone/broken"))
        self.assertEqual(state(repo)["standard setting clone"], f"{repo / '.review/onboard/clone/broken'}, not a git checkout")
        git(repo, "config", "lasp-dev.standard", str(repo / "gone"))
        self.assertEqual(state(repo)["standard setting clone"], f"{repo / 'gone'}, missing")

    def test_outside_a_checkout_it_exits_1(self):
        out = subprocess.run([sys.executable, str(STATE), "--repo", tempfile.mkdtemp(dir=SCRATCH.name)],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("not inside a git checkout", out.stderr)


class ReviewDir(unittest.TestCase):
    def test_a_directory_argument_is_where_review_is_made_and_ignored(self):
        repo = make_repo({})
        out = subprocess.run(["bash", str(ROOT / "scripts/review_dir.sh"), str(repo)], capture_output=True, text=True,
                             cwd=SCRATCH.name)
        self.assertEqual(out.returncode, 0)
        self.assertTrue((repo / ".review").is_dir())
        self.assertIn(".review/", (repo / ".git/info/exclude").read_text())

    def test_a_directory_it_cannot_enter_creates_nothing(self):
        out = subprocess.run(["bash", str(ROOT / "scripts/review_dir.sh"), str(Path(SCRATCH.name) / "absent")],
                             capture_output=True, text=True, cwd=SCRATCH.name)
        self.assertEqual((out.returncode, out.stdout), (0, ""))
        self.assertFalse((Path(SCRATCH.name) / ".review").exists())


class SurveyStandardNone(unittest.TestCase):
    def test_a_standard_that_does_not_cover_the_repository_is_set_aside(self):
        repo = make_repo({"standards/profile.yaml": "standard: example-org/std\n"})
        std = make_repo({"standards/profiles/other.yaml": "public: true\n", "standards/decisions.md": "# Decisions\n"},
                        remote="git@github.com:example-org/std.git")
        git(repo, "config", "lasp-dev.standard", str(std))
        survey = [sys.executable, str(ROOT / "scripts/survey.py")]
        refused = subprocess.run(survey, capture_output=True, text=True, cwd=repo)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("does not cover", refused.stderr)
        out = subprocess.run(survey + ["--standard", "none"], capture_output=True, text=True, cwd=repo)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("(standards/default-profile.yaml)", out.stdout)
        env = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="lasp-dev.standard", GIT_CONFIG_VALUE_0=str(std))
        out = subprocess.run(survey + ["--standard", "none"], capture_output=True, text=True, cwd=repo, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        env["GIT_CONFIG_COUNT"] = "x"
        out = subprocess.run(survey + ["--standard", "none"], capture_output=True, text=True, cwd=repo, env=env)
        self.assertEqual(out.returncode, 1)
        self.assertIn("survey.py: GIT_CONFIG_COUNT", out.stderr)


if __name__ == "__main__":
    unittest.main()
