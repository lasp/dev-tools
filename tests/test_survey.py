"""Tests for scripts/survey.py: what it finds in a repository's own files, and how it compares."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "survey.py"
SCRATCH = tempfile.TemporaryDirectory()


def tearDownModule():
    SCRATCH.cleanup()


def scratch() -> Path:
    return Path(tempfile.mkdtemp(dir=SCRATCH.name))


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_repo(files: dict, remote, branches=(), subjects=("Initial commit",), remote_branches=()) -> Path:
    repo = scratch()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.org")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "commit.gpgsign", "false")
    if remote:
        git(repo, "remote", "add", "origin", remote)
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
    git(repo, "add", "-A")
    for subject in subjects:
        git(repo, "commit", "-q", "--allow-empty", "-m", subject)
    for name in branches:
        git(repo, "branch", name)
    for name in remote_branches:
        git(repo, "update-ref", f"refs/remotes/origin/{name}", "HEAD")
    return repo


def run(repo: Path, *args: str, cwd: Path = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo), *args], capture_output=True, text=True, cwd=cwd)


def rows(repo: Path, standard: str = None) -> dict:
    """The rows for `repo`; with `standard`, written as the checkout's own standards/profile.yaml and
    surveyed from inside the checkout, where profile.py reads its standard."""
    if standard is not None:
        (repo / "standards").mkdir(exist_ok=True)
        (repo / "standards/profile.yaml").write_text(standard)
    out = run(repo, "--json", cwd=repo if standard is not None else None)
    assert out.returncode == 0, out.stderr
    return {r["family"]: r for r in json.loads(out.stdout)}


WORKFLOW = """name: tests
jobs:
  test:
    steps:
      - run: pip install -e .
      - name: Smoke
        run: poetry run pytest --version
      - name: Run tests
        run: |
          poetry run pytest \\
            -m "not slow" tests/
      - name: Coverage
        run: uv run pytest --cov=sample tests/
"""

PYPROJECT = """[project]
name = "sample"

[tool.pytest.ini_options]
markers = [
    "slow: a slow test",
    "network: needs the network",
]
testpaths = ["tests"]
"""

CONTRIBUTING = """# Contributing

## Commit messages

Start the subject with the ticket key. SECRET-BODY-TEXT-1234 never reaches the survey.

## Branch names

## Merging and rebasing
"""


class GenericRepository(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = make_repo(
            {
                ".github/pull_request_template.md": "## Summary\n\n## Testing\n",
                ".github/ISSUE_TEMPLATE/bug.md": "bug\n",
                "CONTRIBUTING.md": CONTRIBUTING,
                ".github/CODEOWNERS": "# owners\n* @someone\n/docs @writer\n",
                ".github/workflows/tests.yml": WORKFLOW,
                ".pre-commit-config.yaml": "repos:\n  - repo: x\n    hooks:\n      - id: ruff\n      - id: gitleaks\n",
                "pyproject.toml": PYPROJECT,
                "docs/testing.md": "# Testing\n",
                "AGENTS.md": "agents\n",
                "docs/adr/0001-use-x.md": "# ADR\n",
                "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n",
            },
            "git@github.com:example-org/sample_repo.git",
            branches=("feature/PROJ-12-thing", "PROJ-7-other", "main-fix"),
            subjects=("PROJ-1: start", "PROJ-2: more", "tidy"),
        )
        cls.rows = rows(cls.repo)

    def test_each_family_is_found_where_the_repository_keeps_it(self):
        found = {k: r["found_in"] for k, r in self.rows.items()}
        self.assertEqual(found["remote"], "git")
        self.assertEqual(found["pull request template"], ".github/pull_request_template.md")
        self.assertEqual(found["issue templates"], ".github/ISSUE_TEMPLATE/")
        self.assertEqual(found["commit style"], "CONTRIBUTING.md#Commit messages")
        self.assertEqual(found["branch naming"], "CONTRIBUTING.md#Branch names")
        self.assertEqual(found["merge strategy"], "CONTRIBUTING.md#Merging and rebasing")
        self.assertEqual(found["code owners"], ".github/CODEOWNERS")
        self.assertEqual(found["testing doc"], "docs/testing.md")
        self.assertEqual(found["agent instructions"], "AGENTS.md")
        self.assertEqual(found["decision records"], "docs/adr/")
        self.assertEqual(found["ticket key"], "history")
        self.assertEqual(found["review rules"], "none")

    def test_a_standard_pointer_is_the_review_rules_row(self):
        repo = make_repo({"standards/profile.yaml": "standard: example-org/standards\n"}, "git@github.com:example-org/member.git")
        row = rows(repo)["review rules"]
        self.assertEqual((row["found_in"], row["value"]), ("standards/profile.yaml", "those of example-org/standards"))

    def test_a_template_its_own_standard_names_and_does_not_hold_differs_rather_than_failing(self):
        repo = make_repo({"standards/profile.yaml": "template: mine\n", ".github/pull_request_template.md": "x\n"}, "git@github.com:example-org/own.git")
        out = subprocess.run([sys.executable, str(SCRIPT), "--json"], cwd=repo, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        row = next(r for r in json.loads(out.stdout) if r["family"] == "pull request template")
        self.assertEqual((row["plugin_today"], row["match"]), ("mine", "differs"))

    def test_a_template_its_own_standard_holds_is_the_same_and_named(self):
        repo = make_repo({"standards/profile.yaml": "template: mine\n", "standards/templates/mine/PULL_REQUEST_TEMPLATE.md": "## Why\n",
                          ".github/PULL_REQUEST_TEMPLATE.md": "## Why\n"}, "git@github.com:example-org/own.git")
        out = subprocess.run([sys.executable, str(SCRIPT), "--json"], cwd=repo, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        row = next(r for r in json.loads(out.stdout) if r["family"] == "pull request template")
        self.assertEqual((row["plugin_today"], row["match"]), ("mine", "same"))
        cand = scratch() / "profile.yaml"
        out = run(repo, "--profile", str(cand), cwd=repo)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("template: 'mine'\n", cand.read_text())

    def test_a_template_is_named_as_the_repository_spells_it(self):
        repo = make_repo({".github/PULL_REQUEST_TEMPLATE.md": "x\n"}, "git@github.com:example-org/caps.git")
        self.assertEqual(rows(repo)["pull request template"]["found_in"], ".github/PULL_REQUEST_TEMPLATE.md")

    def test_values_are_short_facts(self):
        value = {k: r["value"] for k, r in self.rows.items()}
        self.assertEqual(value["remote"], "example-org/sample_repo")
        self.assertEqual(value["code owners"], "2 rules")
        self.assertEqual(value["test command"], 'pytest -m "not slow" tests/')
        self.assertEqual(value["coverage command"], "pytest --cov=sample tests/")
        self.assertEqual(value["secret scanning"], "gitleaks")
        self.assertEqual(value["package"], "sample")
        self.assertEqual(value["pytest settings"], 'markers: slow, network; testpaths: ["tests"]')
        self.assertEqual(value["changelog"], "Keep a Changelog, [Unreleased]")
        self.assertEqual(value["ticket project"], "PROJ")
        self.assertEqual(value["commit habit"], "2 of 3 subjects open with a ticket key")

    def test_a_repository_no_team_serves_is_compared_with_the_default_profile(self):
        row = self.rows["lint gate"]
        self.assertEqual(row["plugin_source"], "standards/default-profile.yaml")
        self.assertEqual(self.rows["ticket key"]["match"], "repository only")
        self.assertEqual(self.rows["remote"]["match"], "-")

    def test_the_lint_gate_the_default_profile_leaves_empty_is_the_repositorys_alone(self):
        self.assertEqual(self.rows["lint gate"]["match"], "repository only")
        self.assertEqual(self.rows["lint gate"]["value"], "pre-commit, 2 hooks")

    def test_file_contents_never_reach_the_output(self):
        out = run(self.repo)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("SECRET-BODY-TEXT-1234", out.stdout)
        self.assertNotIn("SECRET-BODY-TEXT-1234", run(self.repo, "--json").stdout)

    def test_the_table_has_its_fixed_header_and_one_row_per_family(self):
        lines = run(self.repo).stdout.splitlines()
        self.assertRegex(lines[0], r"^survey: example-org/sample_repo · \d+ families · \d+ from the repository$")
        self.assertEqual(lines[1], "family | found in | value | plugin today | match")
        self.assertEqual(len(lines) - 2, len(self.rows))
        self.assertTrue(all(line.count(" | ") == 4 for line in lines[1:]))


class TicketKeys(unittest.TestCase):
    def test_look_alike_keys_name_no_project(self):
        repo = make_repo({}, "git@github.com:example-org/k.git",
                         subjects=("Support UTF-8 filenames", "Bump SHA-256 helper", "Fix CVE-2024-1 and CVE-2023-2"))
        row = rows(repo)["ticket project"]
        self.assertEqual((row["found_in"], row["value"]), ("none", "-"))

    def test_a_key_seen_once_in_a_subject_alone_is_not_enough(self):
        repo = make_repo({}, "git@github.com:example-org/k.git", subjects=("ABC-12: a thing",))
        self.assertEqual(rows(repo)["ticket project"]["value"], "-")

    def test_two_subjects_opening_with_the_key_name_the_project(self):
        repo = make_repo({}, "git@github.com:example-org/k.git", subjects=("ABC-1: one", "ABC-2: two"))
        self.assertEqual(rows(repo)["ticket project"]["value"], "ABC")

    def test_designators_inside_a_subject_name_no_project(self):
        repo = make_repo({}, "git@github.com:example-org/k.git", branches=("feature/PROJ-808-per-pixel",),
                         subjects=("Per-pixel geometry for NOAA-21", "Compare with NOAA-20 VIIRS"))
        self.assertEqual(rows(repo)["ticket project"]["value"], "PROJ")

    def test_one_designator_opening_a_subject_is_not_enough(self):
        repo = make_repo({}, "git@github.com:example-org/k.git",
                         subjects=("Calibrate against TSIS-1", "TSIS-2 overlap with the radiometer"))
        self.assertEqual(rows(repo)["ticket project"]["value"], "-")

    def test_the_commit_habit_counts_only_the_chosen_key(self):
        repo = make_repo({}, "git@github.com:example-org/k.git", branches=("PROJ-808-x",),
                         subjects=("NOAA-21 time fix", "PROJ-808: per pixel", "tidy"))
        self.assertEqual(rows(repo)["commit habit"]["value"], "1 of 3 subjects open with a ticket key")

    def test_keys_seen_about_as_often_name_no_project(self):
        repo = make_repo({}, "git@github.com:example-org/k.git", remote_branches=("MM-104-a", "MM-106-b"),
                         subjects=("PROJ-780 angles", "PROJ-739 boresight", "tidy"))
        self.assertEqual(rows(repo)["ticket project"]["value"], "-")
        repo = make_repo({}, "git@github.com:example-org/k.git", branches=("ZED-1-a", "ABC-2-b"))
        self.assertEqual(rows(repo)["ticket project"]["value"], "-")

    def test_a_key_seen_twice_as_often_as_any_other_names_the_project(self):
        repo = make_repo({}, "git@github.com:example-org/k.git", remote_branches=("MM-104-a",),
                         subjects=("PROJ-1 a", "PROJ-2 b"))
        self.assertEqual(rows(repo)["ticket project"]["value"], "PROJ")

    def test_a_dated_branch_names_no_project(self):
        repo = make_repo({}, "git@github.com:example-org/k.git", branches=("onboard/WISER-2026-10-29",),
                         subjects=("WISER-2026-10-29 release",))
        self.assertEqual(rows(repo)["ticket project"]["value"], "-")
        repo = make_repo({}, "git@github.com:example-org/k.git", branches=("PROJ-12-3d-view",))
        self.assertEqual(rows(repo)["ticket project"]["value"], "PROJ")

    def test_the_history_implies_the_profiles_pattern_and_misses_stay_counted(self):
        repo = make_repo({}, "git@github.com:example-org/probe.git", subjects=("PROJ-1: a", "PROJ-2: b"),
                         branches=("proj-1-a", "proj-2-b"), remote_branches=("proj-1-a", "HEAD"))
        row = rows(repo, "ticket:\n  pattern: 'PROJ-\\d+'\n  project: PROJ\n")["ticket key"]
        self.assertEqual(row["value"], "PROJ-<n>; branches: 0 of 3 as where.sh, 2 any case")
        self.assertEqual(row["match"], "same")

    def test_a_profile_pattern_for_another_key_differs(self):
        repo = make_repo({}, "git@github.com:example-org/probe.git", branches=("PROJ-1-a", "PROJ-2-b"))
        self.assertEqual(rows(repo, "ticket:\n  pattern: 'OTHER-\\d+'\n  project: OTHER\n")["ticket key"]["match"], "differs")

    def test_branches_the_pattern_matches_agree(self):
        repo = make_repo({}, "git@github.com:example-org/probe.git", branches=("feature/PROJ-1-a", "PROJ-2-b"))
        self.assertEqual(rows(repo, "ticket:\n  pattern: 'PROJ-\\d+'\n  project: PROJ\n")["ticket key"]["match"], "same")


class IssueKeys(unittest.TestCase):
    """The `issue key` row: GitHub issue keys where convention puts one, and the pattern they imply."""

    def issue_row(self, **history) -> dict:
        return rows(make_repo({}, "git@github.com:example-org/k.git", **history))["issue key"]

    def test_numbered_branches_imply_where_shs_default(self):
        row = self.issue_row(branches=("12-empty-inventory", "feature/14-low-stock", "issue-9-by-part", "issue-15"))
        self.assertEqual((row["found_in"], row["key"], row["match"]), ("history", None, "-"))
        self.assertEqual(row["value"], r"branches: <n>-words 2, issue-<n> 2 of 5; subjects: 0 of 1; pattern (issue-)?\d+")

    def test_gh_branches_alone_imply_their_own_pattern_and_name_no_jira_project(self):
        found = rows(make_repo({}, "git@github.com:example-org/k.git", branches=("GH-12-x", "gh-14-y"), subjects=("GH-12: a", "GH-14: b")))
        self.assertEqual(found["issue key"]["value"], r"branches: GH-<n> 2 of 3; subjects: 2 of 2; pattern GH-\d+")
        self.assertEqual((found["ticket project"]["value"], found["ticket key"]["found_in"]), ("-", "none"))

    def test_a_number_before_an_underscore_is_an_issue_key_as_in_where_sh(self):
        self.assertEqual(self.issue_row(branches=("12_empty-inventory",))["found_in"], "history")

    def test_gh_beside_another_form_is_mixed(self):
        self.assertTrue(self.issue_row(branches=("GH-12-x", "14-y")).get("value").endswith("pattern mixed"))

    def test_subjects_alone_imply_no_pattern(self):
        row = self.issue_row(subjects=("#12: guard an empty inventory", "[#14] low stock", "Count widgets by part (#15)"))
        self.assertEqual(row["value"], "branches: none of 1; subjects: 2 of 3; pattern none")

    def test_dates_and_versions_are_no_issue_keys(self):
        row = self.issue_row(branches=("2026-10-29-notes", "onboard/widgets-2026-11-01", "release/1.2", "v3-fix", "release/1-2"),
                             subjects=("#2026-10-29 notes", "Bump to 1.2"))
        self.assertEqual((row["found_in"], row["value"]), ("none", "-"))

    def test_jira_keys_are_no_issue_keys(self):
        found = rows(make_repo({}, "git@github.com:example-org/k.git", branches=("PROJ-42-csv",), subjects=("PROJ-42: csv",)))
        self.assertEqual((found["issue key"]["found_in"], found["ticket project"]["value"]), ("none", "PROJ"))


class Guides(unittest.TestCase):
    def test_headings_are_read_by_word_and_never_from_code(self):
        guide = ("# Guide\n\n## Pre-commit hooks\n\n## Emerging practices\n\n```bash\n# create a branch for your work\n```\n\n"
                 "## Review | approval\n")
        found = rows(make_repo({"CONTRIBUTING.md": guide}, "git@github.com:example-org/g.git"))
        self.assertEqual(found["commit style"]["found_in"], "none")
        self.assertEqual(found["merge strategy"]["found_in"], "none")
        self.assertEqual(found["branch naming"]["found_in"], "none")

    def test_a_heading_holding_a_bar_keeps_the_table_whole(self):
        repo = make_repo({"CONTRIBUTING.md": "## Commits | style\n"}, "git@github.com:example-org/g.git")
        self.assertEqual(rows(repo)["commit style"]["found_in"], "CONTRIBUTING.md#Commits / style")
        self.assertTrue(all(line.count(" | ") == 4 for line in run(repo).stdout.splitlines()[1:]))

    def test_a_restructuredtext_guide_is_found_with_its_titles(self):
        guide = "Contributing\n============\n\nBranch names\n------------\n\ntext\n"
        found = rows(make_repo({"CONTRIBUTING.rst": guide}, "git@github.com:example-org/g.git"))
        self.assertEqual(found["contributing guide"]["found_in"], "CONTRIBUTING.rst")
        self.assertEqual(found["branch naming"]["found_in"], "CONTRIBUTING.rst#Branch names")

    def test_code_owners_are_read_where_github_reads_them_first(self):
        repo = make_repo({"CODEOWNERS": "* @a\n", ".github/CODEOWNERS": "* @b\n/x @c\n"}, "git@github.com:example-org/o.git")
        self.assertEqual(rows(repo)["code owners"]["found_in"], ".github/CODEOWNERS")

    def test_a_changelog_under_doc_is_found(self):
        repo = make_repo({"doc/changelog.md": "# Changelog\n\n## [Unreleased]\n"}, "git@github.com:example-org/d.git")
        found = rows(repo)
        self.assertEqual(found["changelog"]["found_in"], "doc/changelog.md")
        self.assertEqual(found["changelog"]["value"], "Keep a Changelog, [Unreleased]")

    def test_a_sphinx_changelog_is_found(self):
        repo = make_repo({"docs/source/changelog.md": "# Changelog\n"}, "git@github.com:example-org/d.git")
        self.assertEqual(rows(repo)["changelog"]["found_in"], "docs/source/changelog.md")

    def test_a_changelog_at_the_top_comes_before_one_under_docs(self):
        repo = make_repo({"CHANGELOG.md": "# Changelog\n", "docs/changelog.md": "## [Unreleased]\n"}, "git@github.com:example-org/e.git")
        self.assertEqual(rows(repo)["changelog"]["found_in"], "CHANGELOG.md")

    def test_names_are_matched_exactly_whatever_the_file_system(self):
        repo = make_repo({"agents.md": "x\n", "changelog.md": "## [Unreleased]\n"}, "git@github.com:example-org/c.git")
        found = rows(repo)
        self.assertEqual(found["agent instructions"]["found_in"], "none")
        self.assertEqual(found["changelog"]["found_in"], "none")


FORMS = """jobs:
  a:
    steps:
      - name: Install
        run: make install && poetry run python -m pytest tests/
      - name: Coverage
        run: >
          coverage run -m pytest
          tests/
        env:
          PYTHONWARNINGS: error
  b:
    steps:
      - run: uv run --frozen pytest -q
"""


class Commands(unittest.TestCase):
    def test_each_ci_form_of_a_pytest_command_is_read(self):
        found = rows(make_repo({".github/workflows/ci.yml": FORMS}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest tests/")
        self.assertEqual(found["coverage command"]["value"], "pytest tests/")
        self.assertNotIn("PYTHONWARNINGS", json.dumps(found))

    def test_a_folded_block_keeps_its_options(self):
        flow = "jobs:\n  a:\n    steps:\n      - run: >\n          pytest\n          --cov=pkg\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["coverage command"]["value"], "pytest --cov=pkg")
        self.assertEqual(found["test command"]["value"], "-")

    def test_an_integration_workflow_is_passed_over_for_the_main_suite(self):
        files = {".github/workflows/_integration.yml": "jobs:\n  a:\n    steps:\n      - run: pytest tests/integration\n",
                 ".github/workflows/unit.yml": "jobs:\n  a:\n    steps:\n      - run: pytest tests/unit\n"}
        found = rows(make_repo(files, "git@github.com:example-org/f.git"))
        self.assertEqual((found["test command"]["found_in"], found["test command"]["value"]),
                         (".github/workflows/unit.yml", "pytest tests/unit"))

    def test_operators_inside_quotes_do_not_split_a_command(self):
        flow = "jobs:\n  a:\n    steps:\n      - run: pytest -k 'a && b' tests/\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest -k 'a && b' tests/")

    def test_a_command_run_through_a_shell_or_xvfb_is_read_as_what_it_runs(self):
        flow = "jobs:\n  a:\n    steps:\n      - run: xvfb-run -a bash -lc 'make generated && cd src/tests && pytest -s .'\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "cd src/tests && pytest -s .")
        flow = "jobs:\n  a:\n    steps:\n      - run: xvfb-run --auto-servernum pytest tests/\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest tests/")
        flow = "jobs:\n  a:\n    steps:\n      - run: xvfb-run -a -s \"-screen 0 1024x768x24\" pytest tests/\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest tests/")

    def test_a_working_directory_is_where_the_step_runs(self):
        flow = ("defaults:\n  run:\n    working-directory: top\njobs:\n  a:\n    defaults:\n      run:\n"
                "        working-directory: radiometers\n        shell: bash\n    steps:\n"
                "      - run: poetry run pytest -m \"\" -v\n"
                "      - name: Coverage\n        run: pytest --cov=pkg\n        working-directory: \"sub/dir\"\n"
                "  b:\n    steps:\n      - run: cd x && pytest b/\n")
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], 'cd radiometers && pytest -m "" -v')
        self.assertEqual(found["coverage command"]["value"], "cd sub/dir && pytest --cov=pkg")
        one = "jobs:\n  b:\n    steps:\n      - run: |\n          cd x\n          pytest b/\n"
        found = rows(make_repo({".github/workflows/ci.yml": "defaults:\n  run:\n    working-directory: top\n" + one},
                               "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "cd top/x && pytest b/")

    def test_a_jobs_default_stays_in_its_job_and_outranks_the_workflows_wherever_written(self):
        flow = ("jobs:\n  a:\n# a note at column 0\n    defaults:\n      run:\n        working-directory: adir\n"
                "        shell: bash\n    steps:\n      - run: echo a\n  b:\n    steps:\n      - run: pytest tests\n")
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest tests")
        flow = ("jobs:\n  a:\n    defaults:\n      run:\n        working-directory: jobdir\n    steps:\n"
                "      - run: pytest tests\ndefaults:\n  run:\n    working-directory: top\n")
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "cd jobdir && pytest tests")

    def test_a_working_directory_no_shell_can_name_reads_with_no_cd(self):
        flow = ("defaults:\n  run:\n    shell: bash\njobs:\n  a:\n    steps:\n      - uses: x/y@v1\n        with:\n"
                "          working-directory: elsewhere\n      - run: pytest a/\n        working-directory: ${{ matrix.dir }}\n"
                "      - run: pytest --cov=p\n        working-directory: ./\n"
                "      - run: cd .. && pytest --cov=q\n        working-directory: sub\n"
                "      - run: pytest c/\n        working-directory: \"my dir\"\n")
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest a/")
        self.assertEqual(found["coverage command"]["value"], "pytest --cov=p")

    def test_a_linter_command_is_the_lint_gate_without_a_pre_commit_file(self):
        tox = "[testenv]\ncommands = pytest tests\n\n[testenv:lint]\ncommands =\n    ruff format src\n    ruff check src tests\n"
        found = rows(make_repo({"tox.ini": tox}, "git@github.com:example-org/f.git"))
        self.assertEqual((found["lint gate"]["found_in"], found["lint gate"]["value"]), ("tox.ini", "ruff check src tests"))
        flow = ("jobs:\n  a:\n    steps:\n      - run: ruff check --fix .\n      - run: ruff check --fix-only .\n"
                "      - run: uv run flake8 src\n")
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["lint gate"]["value"], "flake8 src")
        found = rows(make_repo({".github/workflows/ci.yml": flow, ".pre-commit-config.yaml": "repos: []\n"},
                               "git@github.com:example-org/f.git"))
        self.assertEqual(found["lint gate"]["found_in"], ".pre-commit-config.yaml")
        tox_repo = make_repo({"tox.ini": tox}, "git@github.com:example-org/probe.git")
        self.assertEqual(rows(tox_repo, "lint:\n  command: 'ruff check src tests'\n")["lint gate"]["match"], "same")
        self.assertEqual(rows(tox_repo, "lint:\n  command: 'flake8 src'\n")["lint gate"]["match"], "differs")
        cand = scratch() / "profile.yaml"
        self.assertEqual(run(tox_repo, "--profile", str(cand)).returncode, 0)
        sources = json.loads(cand.with_name("profile.sources.json").read_text())["keys"]
        self.assertIn("command: 'ruff check src tests'", cand.read_text())
        self.assertIn("regex: 'ruff[[:space:]]+check'", cand.read_text())
        self.assertEqual((sources["lint.command"]["source"], sources["lint.regex"]["source"]), ("tox.ini", "tox.ini (inferred)"))

    def test_tox_commands_are_read_by_section(self):
        tox = ("[tox]\nenvlist = py310, lint\n\n[testenv:integration]\ncommands = pytest tests/integration\n\n"
               "[testenv]\nextras = test\ncommands =\n    pytest {posargs:tests}\n    pytest --cov=pkg {posargs}\n\n"
               "[testenv:lint]\ncommands = ruff check src\n")
        found = rows(make_repo({"tox.ini": tox}, "git@github.com:example-org/f.git"))
        self.assertEqual((found["test command"]["found_in"], found["test command"]["value"]), ("tox.ini", "pytest tests"))
        self.assertEqual(found["coverage command"]["value"], "pytest --cov=pkg")
        tox = ("[testenv]\ncommands =\n    # the suite\n    py310: {envpython} -m pytest --cov=pkg \\\n        {posargs}\n"
               "    - pytest {posargs:{toxinidir}/tests}  # unit\n")
        found = rows(make_repo({"tox.ini": tox}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest tests")
        self.assertEqual(found["coverage command"]["value"], "pytest --cov=pkg")

    def test_a_directory_changed_into_stays_with_its_command(self):
        flow = "jobs:\n  a:\n    steps:\n      - run: make generated && cd src/tests && pytest -s .\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "cd src/tests && pytest -s .")

    def test_runner_options_that_take_a_value_are_removed_with_it(self):
        flow = ("jobs:\n  a:\n    steps:\n      - run: uv run --python ${{ matrix.python-version }} pytest tests/\n"
                "      - run: uv run --with pytest-cov pytest --cov=pkg tests/\n")
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest tests/")
        self.assertEqual(found["coverage command"]["value"], "pytest --cov=pkg tests/")

    def test_an_excluded_path_does_not_make_the_main_suite_a_side_suite(self):
        files = {".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: pytest --ignore=tests/integration tests/\n",
                 ".github/workflows/docs.yml": "jobs:\n  a:\n    steps:\n      - run: python -m pytest --doctest-modules src/pkg\n"}
        found = rows(make_repo(files, "git@github.com:example-org/f.git"))
        self.assertEqual((found["test command"]["found_in"], found["test command"]["value"]),
                         (".github/workflows/ci.yml", "pytest --ignore=tests/integration tests/"))

    def test_a_folded_block_keeps_a_blank_line_as_a_break(self):
        flow = "jobs:\n  a:\n    steps:\n      - run: >\n          echo a\n\n          pytest tests/\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/f.git"))
        self.assertEqual(found["test command"]["value"], "pytest tests/")

    def test_quoting_and_runners_do_not_count_and_a_real_difference_does(self):
        standard = ("tests:\n  command: \"poetry run pytest -m 'not e2e' tests/\"\n"
                    "coverage:\n  command: 'pytest --cov=other tests/'\n")
        flow = "jobs:\n  a:\n    steps:\n      - run: pytest -m \"not e2e\" tests/\n      - run: pytest --cov=pkg tests/\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/probe.git"), standard)
        self.assertEqual(found["test command"]["match"], "same")
        self.assertEqual(found["coverage command"]["match"], "differs")

    def test_a_key_the_repository_holds_and_the_plugin_leaves_empty_is_repository_only(self):
        flow = "jobs:\n  a:\n    steps:\n      - run: pytest tests/\n"
        found = rows(make_repo({".github/workflows/ci.yml": flow}, "git@github.com:example-org/probe.git"), "")
        self.assertEqual(found["test command"]["match"], "repository only")

    def test_a_template_identical_to_the_plugins_is_the_same(self):
        standard = make_repo({"standards/profile.yaml": "ticket:\n  pattern: 'PROJ-\\d+'\n  project: PROJ\n",
                              "standards/profiles/probe.yaml": "template: mine\n",
                              "standards/templates/mine/PULL_REQUEST_TEMPLATE.md": "## Summary\n"}, "git@github.com:example-org/standard.git")
        repo = make_repo({".github/pull_request_template.md": "## Summary\n"}, "git@github.com:example-org/probe.git")
        git(repo, "config", "lasp-dev.standard", str(standard))
        found = rows(repo, "standard: example-org/standard\n")
        row = found["pull request template"]
        self.assertEqual((row["match"], row["plugin_source"]), ("same", f"example-org/standard at {standard.resolve()}/standards (local):profiles/probe.yaml"))
        self.assertEqual(found["ticket key"]["plugin_source"], f"example-org/standard at {standard.resolve()}/standards (local):profile.yaml")


class Settings(unittest.TestCase):
    def test_only_the_markers_list_names_markers_and_single_quotes_are_read(self):
        text = ("[project]\nname = 'single'\n\n[tool.pytest.ini_options]\nfilterwarnings = [\n"
                "    \"ignore::DeprecationWarning\",\n]\nmarkers = ['slow: x', \"net: y\"]\n")
        found = rows(make_repo({"pyproject.toml": text}, "git@github.com:example-org/p.git"))
        self.assertEqual(found["package"]["value"], "single")
        self.assertEqual(found["pytest settings"]["value"], "markers: slow, net")

    def test_import_names_come_from_the_packages_tables_then_its_layout_then_its_name(self):
        name = "[project]\nname = 'lasp-curryer'\n"
        cases = [
            ({"pyproject.toml": name, "curryer/__init__.py": "", "tests/__init__.py": ""}, "git (inferred)", "curryer"),
            ({"pyproject.toml": name, "src/curryer/__init__.py": "", "src/curryer/io/__init__.py": "",
              "tools/__init__.py": ""}, "git (inferred)", "curryer"),
            ({"pyproject.toml": name + "\n[tool.setuptools]\npackages = [\"curryer\", \"curryer.io\"]\nzip-safe = false\n",
              "other/__init__.py": ""}, "pyproject.toml", "curryer"),
            ({"pyproject.toml": "[tool.poetry]\nname = 'lasp-curryer'\npackages = [\n  { include = \"curryer\", from = \"src\","
                                " format = [\"sdist\"] },\n  { include = \"spice\" },\n]\n"}, "pyproject.toml", "curryer, spice"),
            ({"pyproject.toml": name}, "pyproject.toml (inferred)", "lasp_curryer"),
            ({"pyproject.toml": name + "\n[tool.setuptools]\npackages = {find = {where = [\"src\"]}}\n",
              "src/curryer/__init__.py": "", "src/tests/__init__.py": ""}, "git (inferred)", "curryer"),
            ({"pyproject.toml": name, "curryer/__init__.py": "", "tools/__init__.py": "", "scripts/__init__.py": ""},
             "git (inferred)", "curryer"),
            ({"pyproject.toml": name, "tools/__init__.py": ""}, "git (inferred)", "tools"),
            ({"pyproject.toml": name + "\n[tool.setuptools]\npackages = ['lasp.curryer', 'lasp.curryer.io']\n",
              "src/lasp/curryer/__init__.py": "", "src/lasp/curryer/io/__init__.py": ""}, "pyproject.toml", "lasp.curryer"),
        ]
        for files, where, value in cases:
            with self.subTest(files=sorted(files)):
                row = rows(make_repo(files, "git@github.com:example-org/curryer.git"))["import names"]
                self.assertEqual((row["found_in"], row["value"], row["conflict"]), (where, value, False))

    def test_import_names_several_packages_none_named_for_the_distribution_are_a_conflict(self):
        files = {"pyproject.toml": "[project]\nname = 'lasp-curryer'\n", "tools/__init__.py": "", "scripts/__init__.py": ""}
        row = rows(make_repo(files, "git@github.com:example-org/curryer.git"))["import names"]
        self.assertEqual((row["found_in"], row["value"], row["conflict"]), ("git (inferred)", "scripts, tools", True))

    def test_import_names_two_tables_disagree_on_are_a_conflict(self):
        text = ("[project]\nname = 'lasp-curryer'\n\n[tool.setuptools]\npackages = ['curryer']\n\n"
                "[tool.poetry]\npackages = [{ include = 'spice' }]\n")
        row = rows(make_repo({"pyproject.toml": text}, "git@github.com:example-org/curryer.git"))["import names"]
        self.assertEqual((row["value"], row["conflict"], row["match"]), ("curryer, spice", True, "-"))

    def test_merge_commits_are_not_counted_as_habit(self):
        repo = make_repo({}, "git@github.com:example-org/m.git", subjects=("ABC-1: one", "ABC-2: two"))
        git(repo, "checkout", "-q", "-b", "side")
        git(repo, "commit", "-q", "--allow-empty", "-m", "ABC-3: three")
        git(repo, "checkout", "-q", "main")
        git(repo, "commit", "-q", "--allow-empty", "-m", "ABC-4: four")
        git(repo, "merge", "-q", "--no-ff", "-m", "Merge branch side", "side")
        self.assertEqual(rows(repo)["commit habit"]["value"], "4 of 4 subjects open with a ticket key")

    def test_the_default_branch_is_labelled_as_the_local_origin_head(self):
        repo = make_repo({}, "git@github.com:example-org/d.git", remote_branches=("main",))
        git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        self.assertEqual(rows(repo)["default branch"]["value"], "main (local origin/HEAD)")


class WidgetsRoundTrip(unittest.TestCase):
    """A mirror of the files a real repository keeps that its profile's keys could come from, their
    command lines as its main branch has them, under the name widgets, compared with its profile's
    values kept as the mirror's own standard."""

    PROFILE = ("ticket:\n  pattern: 'PROJ-\\d+'\n  project: PROJ\ntemplate: widgets\n"
               "tests:\n  command: 'pytest -m \"not e2e\" tests/'\n"
               "coverage:\n  command: 'pytest --cov=widgets -m \"not e2e\" tests/'\n"
               "lint:\n  command: 'pre-commit run --files'\n  regex: 'pre-commit[[:space:]]+run'\n")

    @classmethod
    def setUpClass(cls):
        flow = (
            "jobs:\n  t:\n    steps:\n      - name: Run tests\n        run: |\n"
            "          poetry run pytest \\\n            --cov=widgets \\\n            --cov-report=html:htmlcov\n"
        )
        cls.rows = rows(make_repo(
            {
                ".github/workflows/_run-tests.yml": flow,
                ".pre-commit-config.yaml": "repos:\n  - repo: x\n    hooks:\n      - id: detect-private-key\n      - id: ruff-check\n",
                "pyproject.toml": '[project]\nname = "widgets"\n\n[tool.pytest.ini_options]\nmarkers = [\n    "integration: x"\n]\n',
                "doc/source/developer-docs/testing.md": (
                    "# Testing\n\nTesting is run with `pytest`. To run all tests, make sure the dev dependencies are "
                    "installed and run:\n\n```bash\n# Run all unit and integration tests\npytest tests\n```\n\n"
                    "This allows you to selectively exclude running integration tests with\n\n"
                    "```\npytest -m \"not integration\" tests\n```\n\n## Generating Coverage and Test Reports\n\n"
                    "```bash\n# Create coverage data (stored in .coverage)\npytest --cov=widgets --junit-xml=junit.xml\n"
                    "# Generate interactive HTML coverage report\npytest --cov-report=html:coverage_report --cov=widgets\n"
                    "```\n"),
                "doc/source/developer-docs/git.md": "# Git Usage\n\n### Suggested Commit Message Formatting\n\n"
                                                    "## Reasons for Rebasing\n\n## Release Branches\n",
                ".github/instructions/widgets.instructions.md": (
                    "## Testing\n\n- **Framework**: pytest. Unit tests in `tests/`; integration tests marked\n"
                    "  `@pytest.mark.integration` and in `tests/integration/`.\n"
                    "- **Run unit tests**: `pytest -m \"not integration\" tests/`\n"
                    "- **Run with coverage**: `pytest --cov=widgets tests/`\n"),
            },
            "git@github.com:example-team/mirror.git",
            branches=("PROJ-830-report", "PROJ-794-fmatch", "proj-775-retention", "copilot/fix"),
        ), cls.PROFILE)

    def test_what_the_repository_could_have_supplied(self):
        match = {k: r["match"] for k, r in self.rows.items() if r["key"]}
        self.assertEqual(match, {
            "pull request template": "plugin only",
            "test command": "differs",
            "test command (also)": "differs",
            "coverage command": "differs",
            "coverage command (also)": "differs",
            "lint gate": "inferred",
            "ticket key": "same",
            "ticket project": "same",
        })
        self.assertEqual(self.rows["test command (also)"]["value"], 'pytest -m "not integration" tests')
        self.assertFalse(self.rows["test command"]["conflict"])
        self.assertTrue(self.rows["coverage command"]["conflict"])
        self.assertEqual(self.rows["lint gate"]["plugin_source"], "standards/profile.yaml")


def prose(files: dict) -> dict:
    return rows(make_repo(files, "git@github.com:example-org/p.git"))


class ProseCommands(unittest.TestCase):
    """Test and coverage commands from the files a maintainer writes, before CI."""

    CI = {".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: pytest tests/\n"}

    def test_an_instruction_files_labeled_command_comes_before_ci(self):
        found = prose({**self.CI, "AGENTS.md": '- **Run unit tests**: `pytest -m "not integration" tests/`\n'})
        self.assertEqual(found["test command"]["found_in"], "AGENTS.md")
        self.assertEqual(found["test command"]["value"], 'pytest -m "not integration" tests/')
        self.assertEqual(found["test command (also)"]["found_in"], ".github/workflows/ci.yml")
        self.assertEqual(found["test command (also)"]["value"], "pytest tests/")
        self.assertTrue(found["test command"]["conflict"])
        self.assertTrue(found["test command (also)"]["conflict"])
        self.assertEqual(found["test command"]["match"], "repository only")

    def test_sources_that_agree_are_no_conflict(self):
        found = prose({**self.CI, "AGENTS.md": "- **Run unit tests**: `poetry run pytest tests/`\n"})
        self.assertEqual(found["test command"]["match"], "repository only")
        self.assertEqual(found["test command (also)"]["found_in"], ".github/workflows/ci.yml")

    def test_a_fenced_block_is_read_by_its_comments_and_passes_over_extra_suites_and_single_tests(self):
        guide = ("## Tests\n\n```bash\n$ pytest --run-extra   # include slow/integration tests\n"
                 "pytest tests/a.py::T::t   # single test\npytest   # fast tests only\n```\n")
        found = prose({".github/instructions/x.instructions.md": guide})
        self.assertEqual(found["test command"]["found_in"], ".github/instructions/x.instructions.md")
        self.assertEqual(found["test command"]["value"], "pytest")
        self.assertNotIn("test command (also)", found)

    def test_the_testing_doc_is_read_when_no_instruction_file_gives_one(self):
        doc = ("# Testing\n\nExclude the integration tests with:\n\n```\npytest -m \"not integration\" "
               "tests\n```\n")
        found = prose({**self.CI, "docs/testing.md": doc})
        self.assertEqual(found["test command"]["found_in"], "docs/testing.md")
        self.assertEqual(found["test command"]["value"], 'pytest -m "not integration" tests')

    def test_a_unit_label_comes_first_and_a_runner_and_continuation_are_read(self):
        guide = ("- **Run all tests**:\n  ```bash\n  poetry run pytest \\\n    tests/\n  ```\n"
                 "- **Run unit tests only**:\n  ```bash\n  poetry run pytest -m 'not slow' tests/unit\n  ```\n")
        found = prose({"CLAUDE.md": guide})
        self.assertEqual(found["test command"]["value"], "pytest -m 'not slow' tests/unit")

    def test_a_tool_mentioned_in_prose_is_no_command(self):
        found = prose({"AGENTS.md": "- **Framework**: `pytest` with plugins.\nTesting is run with `pytest -q` here.\n"
                                    "- **Testing**: `pytest` with coverage reporting\n"})
        self.assertEqual(found["test command"]["found_in"], "none")

    def test_a_coverage_only_source_gives_the_coverage_command_and_ci_the_test_command(self):
        found = prose({**self.CI, "AGENTS.md": "- **Run unit tests**: `poetry run pytest tests/unit --cov=pkg`\n"})
        self.assertEqual(found["coverage command"]["found_in"], "AGENTS.md")
        self.assertEqual(found["coverage command"]["value"], "pytest tests/unit --cov=pkg")
        self.assertEqual(found["test command"]["found_in"], ".github/workflows/ci.yml")

    def test_a_label_naming_a_suite_it_deselects_keeps_the_command(self):
        doc = "# Testing\n\n- **Without integration tests**: `pytest -m \"not integration\" tests`\n"
        found = prose({"docs/testing.md": doc})
        self.assertEqual(found["test command"]["value"], 'pytest -m "not integration" tests')

    def test_a_documents_text_never_reaches_the_output(self):
        guide = "SECRET-PROSE-4471 explains it.\n\n- **Run unit tests**: `pytest tests/`\n"
        out = run(make_repo({"AGENTS.md": guide}, "git@github.com:example-org/p.git"), "--json")
        self.assertNotIn("SECRET-PROSE-4471", out.stdout)


class GitDoc(unittest.TestCase):
    def test_a_developer_git_doc_gives_the_conventions_a_missing_guide_does_not(self):
        doc = "# Git Usage\n\n### Suggested Commit Message Formatting\n\n## Reasons for Rebasing\n\n## Release Branches\n"
        found = prose({"doc/source/developer-docs/git.md": doc})
        self.assertTrue(found["commit style"]["found_in"].startswith("doc/source/developer-docs/git.md#Suggested"))
        self.assertEqual(found["commit style"]["value"], "Suggested Commit Message Formatting")
        self.assertEqual(found["merge strategy"]["value"], "Reasons for Rebasing")
        self.assertEqual(found["branch naming"]["value"], "Release Branches")

    def test_the_contributing_guide_comes_first_and_the_git_doc_fills_its_gaps(self):
        found = prose({"CONTRIBUTING.md": "# Contributing\n\n## Commit messages\n",
                       "docs/git-workflow.md": "# Git\n\n## Commits\n\n## Squashing\n"})
        self.assertEqual(found["commit style"]["found_in"], "CONTRIBUTING.md#Commit messages")
        self.assertEqual(found["merge strategy"]["found_in"], "docs/git-workflow.md#Squashing")


class CommittedOnly(unittest.TestCase):
    """Only what the commit holds is read; what the checkout holds besides is named and left alone."""

    def test_an_uncommitted_file_is_named_and_never_read(self):
        repo = make_repo({"README.md": "x\n"}, "git@github.com:example-org/u.git")
        (repo / "AGENTS.md").write_text("- **Run unit tests**: `pytest tests/`\n")
        (repo / ".git/info/exclude").write_text("CLAUDE.md\n")
        (repo / "CLAUDE.md").write_text("- **Run unit tests**: `pytest -x`\n")
        found = rows(repo)
        self.assertEqual(found["test command"]["found_in"], "none")
        self.assertEqual(found["agent instructions"]["found_in"], "none")
        self.assertEqual(found["not committed"]["value"], "2 files, not read: AGENTS.md, CLAUDE.md")

    def test_another_commit_is_read_with_ref(self):
        repo = make_repo({"AGENTS.md": "- **Run unit tests**: `pytest tests/`\n"}, "git@github.com:example-org/r.git")
        git(repo, "checkout", "-q", "-b", "feature")
        git(repo, "rm", "-q", "AGENTS.md")
        git(repo, "commit", "-q", "-m", "drop")
        self.assertEqual(rows(repo)["test command"]["found_in"], "none")
        out = run(repo, "--json", "--ref", "main")
        found = {r["family"]: r for r in json.loads(out.stdout)}
        self.assertEqual(found["test command"]["found_in"], "AGENTS.md")

    def test_a_ref_that_is_no_commit_exits_1(self):
        out = run(make_repo({}, None), "--ref", "nope")
        self.assertEqual(out.returncode, 1)
        self.assertIn("nope names no commit", out.stderr)


class OtherHosts(unittest.TestCase):
    def test_gitlab_templates_and_ci_are_read(self):
        found = prose({
            ".gitlab/merge_request_templates/Default.md": "## Summary\n",
            ".gitlab/issue_templates/bug.md": "bug\n",
            ".gitlab-ci.yml": 'test:\n  script:\n    - pip install .\n    - "pytest -m \'not slow\' tests/"\n',
        })
        self.assertEqual(found["pull request template"]["found_in"], ".gitlab/merge_request_templates/Default.md")
        self.assertEqual(found["issue templates"]["value"], "1 files")
        self.assertEqual(found["test command"]["found_in"], ".gitlab-ci.yml")
        self.assertEqual(found["test command"]["value"], "pytest -m 'not slow' tests/")
        self.assertEqual(found["CI workflows"]["found_in"], ".gitlab-ci.yml")

    def test_a_codebuild_spec_is_read(self):
        spec = "version: 0.2\nphases:\n  build:\n    commands:\n      - |\n        python -m pytest \\\n          tests/unit\n"
        found = prose({"buildspec.yml": spec})
        self.assertEqual(found["test command"]["found_in"], "buildspec.yml")
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")

    def test_a_developer_docs_testing_section_gives_the_command(self):
        doc = ("# Developers\n\n## Building the docs\n\n```\npytest --doctest-modules src\n```\n\n"
               "## Testing\n\n```\npytest tests\n```\n\n## Releasing\n\n```\npytest --version\n```\n")
        found = prose({"docs/source/developers.md": doc})
        self.assertEqual(found["test command"]["found_in"], "docs/source/developers.md")
        self.assertEqual(found["test command"]["value"], "pytest tests")
        self.assertNotIn("test command (also)", found)


class CiItems(unittest.TestCase):
    """Only a CI file's script items are commands, read as YAML reads them."""

    def test_stage_and_needs_lists_are_no_commands(self):
        ci = ("stages:\n  - lint\n  - pytest\nunit:\n  stage: pytest\n  needs:\n    - pytest\n  tags:\n    - pytest\n"
              "  script:\n    - pip install .\n    - pytest -m \"not integration\" tests/\n")
        found = prose({".gitlab-ci.yml": ci, "AGENTS.md": '- **Run unit tests**: `pytest -m "not integration" tests/`\n'})
        self.assertEqual(found["test command (also)"]["value"], 'pytest -m "not integration" tests/')
        self.assertFalse(found["test command"]["conflict"])

    def test_a_plain_items_comment_is_dropped_and_a_quoted_one_unescaped(self):
        found = prose({".gitlab-ci.yml": "unit:\n  script:\n    - pytest tests/unit  # fast suite only\n"})
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")
        found = prose({"buildspec.yml": 'phases:\n  build:\n    commands:\n      - "pytest -k \\"not slow\\" tests/"\n'})
        self.assertEqual(found["test command"]["value"], 'pytest -k "not slow" tests/')

    def test_a_flow_list_and_a_continued_plain_item_are_read(self):
        found = prose({".gitlab-ci.yml": "unit:\n  script: [pip install ., 'pytest tests/unit']\n"})
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")
        found = prose({".gitlab-ci.yml": "unit:\n  script:\n    - pytest\n      tests/unit\n"})
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")

    def test_a_comment_after_the_key_keeps_its_list(self):
        found = prose({".gitlab-ci.yml": "unit:\n  script:  # run the suite\n    - pytest tests/unit\n"})
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")
        found = prose({"buildspec.yml": "phases:\n  build:\n    commands: # tests\n      - pytest tests/unit\n"})
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")

    def test_an_anchor_after_the_key_keeps_its_list_and_an_alias_or_tag_is_no_command(self):
        ci = ("unit:\n  script: &unit\n    - pytest tests/unit\nagain:\n  script: *unit\n"
              "more:\n  script: !reference [.setup, script]\n")
        found = prose({".gitlab-ci.yml": ci})
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")
        self.assertNotIn("test command (also)", found)

    def test_a_block_keeps_its_blank_lines_and_drops_comments(self):
        ci = "unit:\n  script:\n    - |\n      pip install .\n\n      pytest tests/unit  # unit\n"
        self.assertEqual(prose({".gitlab-ci.yml": ci})["test command"]["value"], "pytest tests/unit")
        ci = "unit:\n  script: |\n    pip install .\n\n    pytest tests/unit  # unit\n"
        self.assertEqual(prose({".gitlab-ci.yml": ci})["test command"]["value"], "pytest tests/unit")

    def test_a_cd_item_stays_in_front_of_the_commands_after_it(self):
        spec = ("version: 0.2\nphases:\n  build:\n    commands:\n      - cd ./src\n"
                "      - pytest --ignore=test_data -k 'test_'\n")
        found = prose({"buildspec.yml": spec})
        self.assertEqual(found["test command"]["value"], "cd ./src && pytest --ignore=test_data -k 'test_'")
        flow = "jobs:\n  a:\n    steps:\n      - run: |\n          cd src\n          pytest tests/unit\n"
        self.assertEqual(prose({".github/workflows/ci.yml": flow})["test command"]["value"], "cd src && pytest tests/unit")

    def test_a_dangling_continuation_is_dropped(self):
        flow = "jobs:\n  a:\n    steps:\n      - run: |\n          pytest tests/unit \\\n"
        found = prose({".github/workflows/ci.yml": flow})
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")


class Conflicts(unittest.TestCase):
    """A family whose sources disagree is marked on every row; each row still compares with the key."""

    FILES = {"AGENTS.md": "- **Run unit tests**: `pytest tests/unit`\n",
             ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: pytest tests/\n"}

    def surveyed(self, command: str) -> dict:
        return rows(make_repo(self.FILES, "git@github.com:example-org/probe.git"), f"tests:\n  command: '{command}'\n")

    def test_the_plugin_matching_the_first_source(self):
        found = self.surveyed("pytest tests/unit")
        self.assertEqual((found["test command"]["match"], found["test command (also)"]["match"]), ("same", "differs"))
        self.assertTrue(found["test command"]["conflict"] and found["test command (also)"]["conflict"])

    def test_the_plugin_matching_a_later_source(self):
        found = self.surveyed("pytest tests/")
        self.assertEqual((found["test command"]["match"], found["test command (also)"]["match"]), ("differs", "same"))

    def test_the_table_marks_every_row_of_the_group(self):
        repo = make_repo(self.FILES, "git@github.com:example-org/probe.git")
        (repo / "standards").mkdir()
        (repo / "standards/profile.yaml").write_text("tests:\n  command: 'pytest tests/'\n")
        lines = run(repo, cwd=repo).stdout.splitlines()
        marks = [l.rsplit(" | ", 1)[1] for l in lines if l.startswith("test command")]
        self.assertEqual(marks, ["conflict; differs", "conflict; same"])

    def test_a_trailing_slash_alone_is_no_conflict(self):
        found = prose({"AGENTS.md": '- **Run unit tests**: `pytest -m "not integration" tests/`\n',
                       "docs/testing.md": '# Testing\n\n```\npytest -m "not integration" tests\n```\n'})
        self.assertFalse(found["test command"]["conflict"])

    def test_option_order_alone_is_no_conflict(self):
        found = prose({"AGENTS.md": '- **Run unit tests**: `pytest -m "not e2e" --cov=pkg tests/`\n',
                       ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: pytest --cov=pkg -m 'not e2e' tests/\n"})
        self.assertFalse(found["coverage command"]["conflict"])

    def test_a_repeated_option_keeps_the_order_of_its_values(self):
        found = prose({"AGENTS.md": '- **Run unit tests**: `pytest -m a -m b tests/`\n',
                       ".github/workflows/ci.yml": "jobs:\n  a:\n    steps:\n      - run: pytest -m b -m a tests/\n"})
        self.assertTrue(found["test command"]["conflict"])

    def test_a_command_deselecting_a_side_suite_ranks_with_unit_ones(self):
        doc = ("# Testing\n\nTo run all tests:\n\n```\npytest tests\n```\n\n"
               "Exclude integration tests with:\n\n```\npytest -m \"not integration\" tests\n```\n")
        self.assertEqual(prose({"docs/testing.md": doc})["test command"]["value"], 'pytest -m "not integration" tests')

    def test_a_comment_line_labels_the_command_under_it(self):
        guide = "## Tests\n\n```\n# Run everything\npytest tests\n# Run unit tests\npytest tests/unit\n```\n"
        self.assertEqual(prose({"AGENTS.md": guide})["test command"]["value"], "pytest tests/unit")

    def test_a_fenced_comment_is_no_heading_in_a_developer_doc(self):
        doc = ("# Developers\n\n## Testing\n\n```bash\n# install the dev extras first\npip install -e .\n"
               "pytest tests/unit\n```\n")
        found = prose({"docs/developers.md": doc})
        self.assertEqual(found["test command"]["found_in"], "docs/developers.md")
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")


class Symlinks(unittest.TestCase):
    def test_a_link_within_the_commit_is_read_as_its_target(self):
        repo = make_repo({"docs/agents.md": "- **Run unit tests**: `pytest tests/unit`\n"}, "git@github.com:example-org/s.git")
        (repo / "AGENTS.md").symlink_to("docs/agents.md")
        git(repo, "add", "AGENTS.md")
        git(repo, "commit", "-q", "-m", "link")
        found = rows(repo)
        self.assertEqual(found["test command"]["found_in"], "AGENTS.md")
        self.assertEqual(found["test command"]["value"], "pytest tests/unit")
        self.assertEqual(found["symlinks not followed"]["found_in"], "none")

    def test_a_link_out_of_the_commit_is_listed_and_not_read(self):
        repo = make_repo({"README.md": "x\n"}, "git@github.com:example-org/s.git")
        (repo / "CLAUDE.md").symlink_to("../elsewhere/CLAUDE.md")
        git(repo, "add", "CLAUDE.md")
        git(repo, "commit", "-q", "-m", "link")
        found = rows(repo)
        self.assertEqual(found["symlinks not followed"]["value"], "1 links, not read: CLAUDE.md -> ../elsewhere/CLAUDE.md")
        self.assertEqual(found["test command"]["found_in"], "none")


    def committed_links(self, links: dict) -> dict:
        repo = make_repo({"README.md": "x\n", "docs/real.md": "## Commits\n"}, "git@github.com:example-org/s.git")
        for path, target in links.items():
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).symlink_to(target)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "links")
        return rows(repo)

    def test_a_link_that_cannot_be_followed_counts_as_not_held(self):
        chain = {f"c{i}": f"c{i + 1}" for i in range(1, 12)}
        found = self.committed_links({"CONTRIBUTING.md": "../outside.md", "TESTING.md": "c1",
                                      ".github/copilot-instructions.md": "/etc/passwd", "AGENTS.md": "docs", **chain})
        self.assertEqual(found["contributing guide"]["found_in"], "none")
        self.assertEqual(found["testing doc"]["found_in"], "none")
        self.assertEqual(found["agent instructions"]["found_in"], "none")
        value = found["symlinks not followed"]["value"]
        for link in ("CONTRIBUTING.md -> ../outside.md", "TESTING.md -> c1",
                     ".github/copilot-instructions.md -> /etc/passwd", "AGENTS.md -> docs"):
            self.assertIn(link, value)
        self.assertTrue(value.startswith("4 links, not read: "))

    def test_a_chain_within_the_limit_is_followed(self):
        chain = {f"c{i}": f"c{i + 1}" for i in range(1, 7)}
        chain["c7"] = "docs/real.md"
        found = self.committed_links({"CONTRIBUTING.md": "c1", **chain})
        self.assertEqual(found["commit style"]["value"], "Commits")
        self.assertEqual(found["symlinks not followed"]["found_in"], "none")


class History(unittest.TestCase):
    def test_a_ref_named_like_a_path_still_reads_its_history(self):
        repo = make_repo({"docs/x.md": "x\n"}, "git@github.com:example-org/h.git", subjects=("ABC-1 one", "ABC-2 two"))
        git(repo, "branch", "docs")
        out = run(repo, "--json", "--ref", "docs")
        self.assertEqual(out.returncode, 0, out.stderr)
        found = {r["family"]: r for r in json.loads(out.stdout)}
        self.assertEqual(found["ticket project"]["value"], "ABC")

    def test_an_edited_tracked_file_is_read_as_committed(self):
        repo = make_repo({"AGENTS.md": "- **Run unit tests**: `pytest tests/`\n"}, "git@github.com:example-org/e.git")
        (repo / "AGENTS.md").write_text("- **Run unit tests**: `pytest -x`\n")
        self.assertEqual(rows(repo)["test command"]["value"], "pytest tests/")

    def test_the_header_counts_families_only(self):
        repo = make_repo(Conflicts.FILES, "git@github.com:example-org/probe.git")
        lines = run(repo).stdout.splitlines()
        families = [l for l in lines[2:] if not l.split(" | ")[0].endswith("(also)")
                    and l.split(" | ")[0] not in ("not committed", "symlinks not followed")]
        self.assertIn(f" · {len(families)} families · ", lines[0])


class Failures(unittest.TestCase):
    def test_outside_a_checkout_it_exits_1_naming_the_cause(self):
        out = run(scratch())
        self.assertEqual(out.returncode, 1)
        self.assertIn("is not inside a git checkout", out.stderr)
        self.assertEqual(out.stdout, "")

    def test_a_refused_profile_exits_1_naming_the_cause(self):
        repo = make_repo({"standards/profile.yaml": "ticket: [X]\n"}, "git@github.com:example-org/bad.git")
        out = run(repo, cwd=repo)
        self.assertEqual(out.returncode, 1)
        self.assertRegex(out.stderr, r"^survey\.py: .*standards/profile\.yaml")

    def test_a_checkout_with_no_remote_says_so_and_compares_with_the_default_profile(self):
        repo = make_repo({}, None)
        out = run(repo, cwd=repo)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertRegex(out.stdout.splitlines()[0], r"^survey: no remote · ")
        self.assertIn("(standards/default-profile.yaml)", out.stdout)


if __name__ == "__main__":
    unittest.main()
