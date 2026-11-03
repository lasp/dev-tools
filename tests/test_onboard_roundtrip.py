"""Tests for survey.py --profile, the candidate profile, and sandbox/onboard_roundtrip.py, its score."""

import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_survey import git, make_repo, run, scratch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / "sandbox" / "onboard_roundtrip.py"


# The project's settings every repository the test standard covers shares.
PROJECT = """ticket:
  pattern: 'PROJ-\\d+'
  project: PROJ
posted_text: workflow
github_server: ''
jira:
  statuses:
    - {name: New, next: ticket-draft, role: filed}
    - {name: To Do, next: implement-change, role: approved}
    - {name: Under Development, next: implement-change, role: implementation}
    - {name: Done, next: nothing, role: finished}
    - {name: Abandoned, next: nothing, role: abandoned}
  pr_statuses: [Under Development]
internal:
  domains: [internal.example]
  private_repositories: [secret]
attribution:
  phrases: [drafted with AI assistance]
surface:
  identifiers: [ProductId]
"""


def blocks(text: str) -> dict[str, str]:
    """Each top-level key of a profile's text with its lines, comments dropped."""
    found: dict[str, str] = {}
    key = None
    for line in text.splitlines(keepends=True):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            key = line.split(":", 1)[0]
            found[key] = ""
        found[key] += line
    return found


def plugin_root(profile: str = "", repo: str = "probe", template: str = "") -> Path:
    """A local checkout of example-org/standard, a standard for several repositories: PROJECT with
    `profile`'s project settings over it in its profile.yaml, the rest of `profile` as
    profiles/<repo>.yaml and, when given, `template` as its pull request template `mine`."""
    given = blocks(profile)
    project = {**blocks(PROJECT), **{k: v for k, v in given.items() if k in PROJECT_KEYS}}
    files = {"standards/profile.yaml": "".join(project.values()),
             f"standards/profiles/{repo}.yaml": "".join(v for k, v in given.items() if k not in PROJECT_KEYS)}
    if template:
        files["standards/templates/mine/PULL_REQUEST_TEMPLATE.md"] = template
    return make_repo(files, "git@github.com:example-org/standard.git")


def point(repo: Path, standard: Path) -> Path:
    """`repo` with its standard elsewhere, read from the local checkout `standard`."""
    (repo / "standards").mkdir(exist_ok=True)
    (repo / "standards/profile.yaml").write_text("standard: example-org/standard\n")
    git(repo, "config", "lasp-dev.standard", str(standard))
    return repo


def survey_in(repo: Path, standard: Path, *args: str) -> subprocess.CompletedProcess:
    """survey.py run from inside `repo`, pointed at `standard`."""
    return run(point(repo, standard), *args, cwd=repo)


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile, survey = load("profile"), load("survey")
NR = profile.NOT_RECORDED
PROJECT_KEYS = profile.PROJECT_KEYS

TEMPLATE = "## Why\n\n## What changes\n"
PLUGIN_PROFILE = """ticket:
  pattern: 'PROJ-\\d+'
  project: PROJ
template: mine
downstream: [alpha, beta]
tests:
  command: 'pytest tests/'
coverage:
  command: 'pytest --cov=probe tests/'
depth:
  deep: ['src/core/**', 'data/**']
public: true
lint:
  command: 'pre-commit run --files'
  regex: 'pre-commit[[:space:]]+run'
types:
  regex: '(mypy|pyright)'
gates:
  tests: pytest
"""
FILES = {
    ".github/pull_request_template.md": TEMPLATE,
    "CLAUDE.md": "- **Run unit tests**: `pytest -m \"not slow\" tests/`\n- **Coverage**: `pytest --cov=probe tests/`\n"
                 "@docs/extra.md\nNot an import: `@docs/code.md`, nor mail@example.org.\n```\n@docs/code.md\n```\n",
    "docs/extra.md": "More notes. @nested.md\n",
    "docs/nested.md": "Nested.\n",
    "docs/code.md": "Code.\n",
    ".github/workflows/t.yml": "jobs:\n  t:\n    steps:\n      - run: pytest --cov=probe --cov-report=html tests/\n",
    ".pre-commit-config.yaml": "repos:\n  - repo: x\n    hooks:\n      - id: ruff\n",
}
SESSION = ["CLAUDE.md", "docs/extra.md", "docs/nested.md"]


def candidate_of(repo: Path, root: Path, *args: str) -> Path:
    path = scratch() / "onboard" / "profile.yaml"
    out = survey_in(repo, root, "--profile", str(path), *args)
    assert out.returncode == 0, out.stderr
    return path


def candidate_of_own(repo: Path) -> Path:
    """The candidate for `repo`, surveyed from inside it with its own standard."""
    path = scratch() / "onboard" / "profile.yaml"
    out = run(repo, "--profile", str(path), cwd=repo)
    assert out.returncode == 0, out.stderr
    return path


def score(candidate: Path, root: Path, *args: str, repo: str = "example-org/probe") -> subprocess.CompletedProcess:
    """The scorer run from a checkout of `repo` pointed at the standard `root`."""
    here = scratch()
    git(here, "init", "-q")
    git(here, "remote", "add", "origin", f"git@github.com:{repo}.git")
    return subprocess.run([sys.executable, str(SCORER), str(candidate), *args], cwd=point(here, root),
                          capture_output=True, text=True)


def scored(candidate: Path, root: Path, *args: str, repo: str = "example-org/probe") -> dict:
    out = score(candidate, root, "--json", *args, repo=repo)
    assert out.returncode == 0, out.stderr
    return {r["key"]: r for r in json.loads(out.stdout)}


def copy(path: Path, edit_profile=None, edit_sources=None) -> Path:
    """A copy of a candidate and its sources, each edited."""
    new = scratch() / "profile.yaml"
    text = path.read_text()
    new.write_text(edit_profile(text) if edit_profile else text)
    sources = json.loads(path.with_name("profile.sources.json").read_text())
    if edit_sources:
        edit_sources(sources)
    new.with_name("profile.sources.json").write_text(json.dumps(sources))
    return new


def proposed(key: str):
    """A sources edit for a value a test proposes: its source, listed in files."""
    def edit(sources: dict) -> None:
        sources["keys"][key]["source"] = "proposed"
        sources["files"]["proposed"] = {"loads": "script", "chars": 0}
    return edit


def replaced(old: str, new: str):
    def edit(text: str) -> str:
        assert old in text, old
        return text.replace(old, new)
    return edit


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = plugin_root(PLUGIN_PROFILE, "probe", TEMPLATE)
        cls.repo = make_repo(FILES, "git@github.com:example-org/probe.git", branches=("PROJ-1-start",),
                             subjects=("PROJ-2: one", "PROJ-3: two"))
        cls.path = candidate_of(cls.repo, cls.root, "--public", "true")
        cls.sources = json.loads(cls.path.with_name("profile.sources.json").read_text())


class Candidate(Fixture):
    def test_the_candidate_is_a_profile_the_schema_takes_with_every_key(self):
        data = profile.parse(self.path.read_text(), "candidate")
        profile.check(data, "candidate")
        self.assertEqual(set(data), set(profile.SCHEMA))
        self.assertEqual(data["downstream"], NR)
        self.assertEqual(data["depth"], {"light": [{"glob": "docs/**/*.md", "brief": "documentation"}], "deep": NR})

    def test_values_it_can_fill_and_where_each_came_from(self):
        data, keys = profile.parse(self.path.read_text(), "candidate"), self.sources["keys"]
        self.assertEqual(data["ticket"], {"pattern": "PROJ-\\d+", "project": "PROJ"})
        self.assertEqual(data["template"], "mine")
        self.assertIs(data["public"], True)
        self.assertEqual(data["tests"]["command"], 'pytest -m "not slow" tests/')
        self.assertEqual(data["lint"]["command"], "pre-commit run --files")
        self.assertEqual(keys["template"]["source"], ".github/pull_request_template.md")
        self.assertEqual(keys["tests.command"]["source"], "CLAUDE.md")
        self.assertEqual(keys["public"]["source"], "GitHub")
        self.assertEqual(keys["ticket.project"]["source"], "history")
        self.assertEqual(self.sources["repo"], "example-org/probe")

    def test_sources_that_disagree_leave_the_key_unrecorded_and_list_each(self):
        data, cov = profile.parse(self.path.read_text(), "candidate"), self.sources["keys"]["coverage.command"]
        self.assertEqual(data["coverage"]["command"], NR)
        self.assertTrue(cov["conflict"])
        self.assertEqual([s["source"] for s in cov["seen"]], ["CLAUDE.md", ".github/workflows/t.yml"])

    def test_a_template_no_standard_template_matches_is_left_unrecorded_and_said_to_be_held(self):
        root = plugin_root(PLUGIN_PROFILE, "probe")
        path = candidate_of(make_repo(FILES, "git@github.com:example-org/probe.git"), root)
        data = profile.parse(path.read_text(), "candidate")
        self.assertEqual(data["template"], NR)
        self.assertEqual(data["public"], NR)
        self.assertEqual(scored(path, root)["template"]["note"],
                         ".github/pull_request_template.md is held, matching no template of the standard")

    def test_commands_are_kept_as_the_repository_writes_them(self):
        repo = make_repo({"CLAUDE.md": "- **Run unit tests**: `uv run pytest -k \"unit|fast\"  tests/`\n",
                          ".github/workflows/t.yml": "jobs:\n  t:\n    steps:\n      - run: pytest --cov=p tests/ | tee log\n"},
                         "git@github.com:example-org/probe.git")
        root = plugin_root("tests:\n  command: 'pytest -k \"unit|fast\" tests/'\ncoverage:\n  command: 'pytest --cov=p tests/ | tee log'\n",
                           "probe")
        path = candidate_of(repo, root)
        data = profile.parse(path.read_text(), "candidate")
        self.assertEqual(data["tests"]["command"], 'uv run pytest -k "unit|fast"  tests/')
        self.assertEqual(data["coverage"]["command"], "pytest --cov=p tests/ | tee log")
        seen = json.loads(path.with_name("profile.sources.json").read_text())["keys"]["coverage.command"]["seen"]
        self.assertEqual(seen, [{"source": ".github/workflows/t.yml", "value": "pytest --cov=p tests/ | tee log"}])
        rows = scored(path, root)
        self.assertEqual((rows["tests.command"]["cls"], rows["tests.command"]["note"]), ("match", ""))
        self.assertEqual(rows["coverage.command"]["cls"], "match")

    def test_the_files_every_session_loads_follow_imports_outside_code(self):
        start = self.sources["session_start"]
        self.assertEqual(start["files"], SESSION)
        self.assertEqual(start["chars"], sum(len(FILES[p]) for p in SESSION))
        self.assertEqual(self.sources["files"]["CLAUDE.md"]["loads"], "always")
        self.assertEqual(self.sources["files"][".github/workflows/t.yml"]["loads"], "script")

    def test_unscoped_rules_load_and_a_scoped_rules_imports_load(self):
        repo = make_repo({".claude/rules/all.md": "Every session.\n",
                          ".claude/rules/py.md": "---\npaths: ['**/*.py']\n---\nSee @../../docs/c.md\n",
                          "docs/c.md": "Imported by a scoped rule.\n"},
                         "git@github.com:example-org/probe.git")
        start = json.loads(candidate_of(repo, self.root).with_name("profile.sources.json").read_text())["session_start"]
        self.assertEqual(start["files"], [".claude/rules/all.md", "docs/c.md"])

    def test_imports_stop_five_hops_deep(self):
        chain = {"CLAUDE.md": "@h1.md\n", **{f"h{i}.md": f"@h{i + 1}.md\n" for i in range(1, 7)}}
        repo = make_repo(chain, "git@github.com:example-org/probe.git")
        start = json.loads(candidate_of(repo, self.root).with_name("profile.sources.json").read_text())["session_start"]
        self.assertEqual(start["files"], ["CLAUDE.md", "h1.md", "h2.md", "h3.md", "h4.md", "h5.md"])

    def test_how_a_file_reaches_the_model(self):
        self.assertEqual(survey.loads("CLAUDE.md", ["CLAUDE.md"]), "always")
        self.assertEqual(survey.loads(".github/instructions/a.instructions.md", ["CLAUDE.md"]), "on demand")
        self.assertEqual(survey.loads("docs/testing.md", []), "on demand")
        self.assertEqual(survey.loads(".pre-commit-config.yaml (inferred)", []), "script")
        self.assertEqual(survey.loads(".github/workflows/ci.yml", []), "script")
        self.assertEqual(survey.loads("history", []), "script")

    def test_a_drop_in_profile_leaves_unfilled_keys_to_the_project_and_the_default_profile(self):
        path = scratch() / "drop-in.yaml"
        self.assertEqual(survey_in(self.repo, self.root, "--drop-in", str(path)).returncode, 0)
        self.assertNotIn(NR, path.read_text())
        repo = point(make_repo({}, "git@github.com:example-org/probe.git"), plugin_root(path.read_text(), "probe", TEMPLATE))

        def field(name: str) -> str:
            out = subprocess.run([sys.executable, str(ROOT / "scripts/profile.py"), "example-org/probe", "--field", name],
                                 cwd=repo, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            return out.stdout
        default = profile.parse((ROOT / profile.DEFAULT_PROFILE).read_text(), "default")
        self.assertEqual(field("ticket.project"), "PROJ\n")
        self.assertEqual(field("posted_text"), "workflow\n")
        self.assertEqual(field("coverage.command"), default["coverage"]["command"] + "\n")
        self.assertEqual(field("depth.deep"), "")


REMOTE = "git@github.com:example-org/probe.git"


def values_of(repo: Path, root: Path, *args: str) -> tuple[dict, dict]:
    path = candidate_of(repo, root, *args)
    return profile.parse(path.read_text(), "candidate"), json.loads(path.with_name("profile.sources.json").read_text())["keys"]


def sibling(parent: Path, name: str, files: dict, remote: str) -> None:
    shutil.move(str(make_repo(files, remote)), str(parent / name))


class Detectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = plugin_root()

    def test_a_gate_pattern_keeps_the_program_and_a_subcommand(self):
        self.assertEqual(survey.gate_pattern("pre-commit run --files"), "pre-commit[[:space:]]+run")
        self.assertEqual(survey.gate_pattern("poetry run pytest tests/unit"), "pytest")
        self.assertEqual(survey.gate_pattern("cd sub && uv run pytest -x"), "pytest")
        self.assertEqual(survey.gate_pattern("python -m pytest tests"), "pytest")
        self.assertEqual(survey.gate_pattern("make test"), "make[[:space:]]+test")
        self.assertEqual(survey.gate_pattern("npm run test"), "npm[[:space:]]+run[[:space:]]+test")
        self.assertEqual(survey.gate_pattern("PYTHONPATH=. pytest tests"), "pytest")
        self.assertEqual(survey.gate_pattern("env X=1 Y=2 pytest"), "pytest")
        self.assertEqual(survey.gate_pattern("py.test tests"), r"py\.test")
        self.assertEqual(survey.gate_pattern("poetry run pytest -x"), "pytest")
        self.assertEqual(survey.gate_pattern("X=1 uv run pre-commit run --all-files"), "pre-commit[[:space:]]+run")
        self.assertEqual(survey.gate_pattern("make generated && cd src/tests && pytest -s ."), "pytest")
        self.assertEqual(survey.gate_pattern("xvfb-run -a bash -lc 'cd src/tests && pytest -s .'"), "pytest")
        self.assertEqual(survey.gate_pattern("pytest tests; make docs"), "pytest")
        self.assertEqual(survey.gate_pattern("pre-commit run --all-files && git diff --exit-code"), "pre-commit[[:space:]]+run")
        self.assertEqual(survey.gate_pattern("coverage run -m pytest && coverage report"), "pytest")
        self.assertEqual(survey.gate_pattern("pytest || true"), "pytest")
        self.assertEqual(survey.gate_pattern("py.test a && echo done"), r"py\.test")
        self.assertEqual(survey.gate_pattern("make build && make install"), "")
        self.assertEqual(survey.gate_pattern("pytest tests && mypy src"), "")
        self.assertEqual(survey.one_gate(["pytest && ruff check ."]), "")
        self.assertEqual(survey.one_gate(["pytest tests", "coverage run -m pytest && coverage report"]), "pytest")
        self.assertEqual(survey.gate_pattern("xvfb-run -a -s '-screen 0 1024x768x24' pytest tests"), "pytest")
        self.assertEqual(survey.wrapped('bash -c "pytest -k \\"a b\\""'), 'pytest -k "a b"')
        self.assertEqual(survey.gate_pattern('cd "a b" && pytest'), "pytest")
        for nothing in ("make -C sub test", "tox -e py", "./run.sh", "bash -c pytest", "sudo pytest", "",
                        "poetry run test", "hatch run test", "pdm run lint", "env -i pytest", "env -u X pytest",
                        "test -f CHANGELOG.md", "echo pytest", "[ -f x ]"):
            with self.subTest(command=nothing):
                self.assertEqual(survey.gate_pattern(nothing), "")

    def test_one_gate_only_when_every_command_shares_it(self):
        self.assertEqual(survey.one_gate(["pytest a", "cd s && uv run pytest b"]), "pytest")
        self.assertEqual(survey.one_gate(["pytest a", "tox -e py"]), "")
        self.assertEqual(survey.one_gate(["pytest a", "tox run"]), "")
        self.assertEqual(survey.one_gate([]), "")

    def test_gate_patterns_come_from_the_lint_and_test_commands(self):
        data, keys = values_of(make_repo(FILES, REMOTE), self.root)
        self.assertEqual((data["lint"]["regex"], keys["lint.regex"]["source"]),
                         ("pre-commit[[:space:]]+run", ".pre-commit-config.yaml (inferred)"))
        self.assertEqual((data["gates"]["tests"], keys["gates.tests"]["source"]), ("pytest", "CLAUDE.md (inferred)"))

    def test_type_checkers_from_a_hook_or_pyproject(self):
        hook = {".pre-commit-config.yaml": "repos:\n  - repo: x\n    hooks:\n      - id: mypy\n"}
        data, keys = values_of(make_repo(hook, REMOTE), self.root)
        self.assertEqual((data["types"]["regex"], keys["types.regex"]["source"]), ("mypy", ".pre-commit-config.yaml (inferred)"))
        both = {"pyproject.toml": "[project]\nname = 'p'\n\n[tool.pyright]\nstrict = []\n\n[tool.mypy]\nstrict = true\n"}
        self.assertEqual(values_of(make_repo(both, REMOTE), self.root)[0]["types"]["regex"], "(mypy|pyright)")
        listed = {"pyproject.toml": "[project]\nname = 'p'\ndependencies = [\n  \"mypy>=1\",\n]\n"}
        self.assertEqual(values_of(make_repo(listed, REMOTE), self.root)[0]["types"]["regex"], "mypy")

    def test_a_package_or_marker_named_like_a_checker_is_none(self):
        stubs = {"pyproject.toml": "[project]\nname = 'p'\ndependencies = [\n  \"mypy-boto3-s3>=1.28\",\n  'mypy-extensions',\n]\n"
                                   "mypy-boto3-ec2 = '*'\n\n[tool.pytest.ini_options]\nmarkers = [\n  \"mypy: a marker\",\n]\n"}
        data, keys = values_of(make_repo(stubs, REMOTE), self.root)
        self.assertEqual((data["types"]["regex"], keys["types.regex"]["source"]), (NR, None))

    def test_no_signal_leaves_every_detected_key_unrecorded(self):
        quiet = {"README.txt": "x\n", "pyproject.toml": "[project]\nname = 'p'\n# no mypy here\n",
                 "tests/test_manifest.py": "x\n", "docs/calibration.txt": "x\n"}
        data, keys = values_of(make_repo(quiet, REMOTE), self.root)
        for key in ("lint.regex", "types.regex", "gates.tests", "depth.light", "depth.deep", "downstream"):
            with self.subTest(key=key):
                top, _, sub = key.partition(".")
                self.assertEqual(data[top][sub] if sub else data[top], NR)
                self.assertIsNone(keys[key]["source"])

    def test_light_paths_by_rule(self):
        files = {"CHANGELOG.md": "x\n", "README.md": "x\n", "docs/a.md": "x\n", "docs/b.rst": "x\n",
                 "pyproject.toml": "[project]\nname = 'p'\nversion = '1.0'\n"}
        data, keys = values_of(make_repo(files, REMOTE), self.root)
        self.assertEqual(data["depth"]["light"], [
            {"glob": "CHANGELOG.md", "brief": "documentation"}, {"glob": "README.md", "brief": "documentation"},
            {"glob": "docs/**/*.md", "brief": "documentation"}, {"glob": "docs/**/*.rst", "brief": "documentation"},
            {"glob": "pyproject.toml", "hunk": "^version =", "brief": "documentation"}])
        self.assertEqual(keys["depth.light"]["source"], "git (inferred)")

    def test_deep_paths_by_rule_outside_tests_and_docs(self):
        files = {"pkg/data/x.csv": "x\n", "pkg/calibration/a.py": "x\n", "pkg/calibration/b.py": "x\n",
                 "pkg/cli/manifest.py": "x\n", "pkg/io/manifest.py": "x\n", "pkg/io/product_definition.py": "x\n",
                 "pkg/io/reader.py": "x\n", "pkg/io/test_schema.py": "x\n", "pkg/io/mock_kernel.py": "x\n",
                 "tests/test_manifest.py": "x\n", "tests/data/y.csv": "x\n", "docs/schema.py": "x\n",
                 "pkg/data/kernel_list.py": "x\n", "src/geolocation_utils.py": "x\n"}
        data, keys = values_of(make_repo(files, REMOTE), self.root)
        self.assertEqual(data["depth"]["deep"], ["pkg/calibration/**", "pkg/data/**", "**/manifest*",
                                                 "pkg/io/product_definition*", "src/geolocation_utils*"])
        self.assertEqual(keys["depth.deep"]["source"], "git (inferred)")

    def test_downstream_from_checkouts_that_import_or_depend_on_the_package(self):
        repo = make_repo({"pyproject.toml": "[project]\nname = 'probe-kit'\n"}, REMOTE)
        parent = scratch()
        sibling(parent, "a", {"x.py": "import os\nfrom probe_kit.io import read\n", "y.py": "    import probe_kit\n"},
                "git@github.com:example-org/user_a.git")
        sibling(parent, "b", {"pyproject.toml": "[project]\ndependencies = ['probe-kit>=1']\n"},
                "git@github.com:example-org/user_b.git")
        sibling(parent, "b-copy", {"pyproject.toml": "[project]\ndependencies = ['probe_kit']\n"},
                "https://github.com/example-org/user_b")
        sibling(parent, "c", {"z.py": "import probe_kitchen\n# probe_kit in prose\n"}, "git@github.com:example-org/unrelated.git")
        sibling(parent, "self", {"w.py": "import probe_kit\n"}, REMOTE)
        sibling(parent, "fork", {"w.py": "import probe_kit\n"}, "git@github.com:someone/probe.git")
        path = candidate_of(repo, self.root, "--downstream-from", str(parent))
        data, sources = profile.parse(path.read_text(), "c"), json.loads(path.with_name("profile.sources.json").read_text())
        keys = sources["keys"]
        self.assertEqual(data["downstream"], ["user_a", "user_b"])
        self.assertEqual(sources["files"]["clones (search)"], {"loads": "script", "chars": 0})
        self.assertEqual(keys["downstream"]["source"], "clones (search)")
        self.assertEqual(keys["downstream"]["seen"], [{"source": "clones (search)", "value": "user_a: 2 files"},
                                                      {"source": "clones (search)", "value": "user_b: 1 files"}])

    def test_downstream_from_the_skills_search_and_a_bad_file_fails(self):
        found = scratch() / "downstream.json"
        found.write_text(json.dumps([{"repo": "beta", "evidence": 3}, {"repo": "alpha", "evidence": 9},
                                     {"repo": "Probe", "evidence": 40}]))
        repo = make_repo(FILES, REMOTE)
        root = plugin_root(PLUGIN_PROFILE, "probe", TEMPLATE)
        path = candidate_of(repo, root, "--downstream-from", str(found))
        self.assertEqual(profile.parse(path.read_text(), "c")["downstream"], ["alpha", "beta"])
        row = scored(path, root)["downstream"]
        self.assertEqual((row["cls"], row["covers"], row["tier"], row["loads"]), ("match", True, "derived", "script"))
        for bad in ([{"repo": "a/b", "evidence": 1}], [{"repo": "a", "evidence": 0}], {"repo": "a"},
                    [{"repo": "a", "evidence": True}]):
            with self.subTest(bad=bad):
                found.write_text(json.dumps(bad))
                out = survey_in(repo, self.root, "--profile", str(scratch() / "p.yaml"), "--downstream-from", str(found))
                self.assertEqual(out.returncode, 1)
                self.assertIn("not a list of", out.stderr)
        found.write_text("[not json")
        out = survey_in(repo, self.root, "--profile", str(scratch() / "p.yaml"), "--downstream-from", str(found))
        self.assertEqual((out.returncode, str(found) in out.stderr), (1, True))
        out = survey_in(repo, self.root, "--profile", str(scratch() / "p.yaml"), "--downstream-from", "/nowhere/at/all")
        self.assertEqual(out.returncode, 1)
        self.assertIn("neither a file nor a directory", out.stderr)

    def test_a_search_git_cannot_run_stops_the_survey(self):
        with self.assertRaises(OSError):
            survey.grep(scratch(), "x", "HEAD", "*.py")
        self.assertEqual(survey.grep(make_repo({"a.py": "y\n"}, REMOTE), "nothing-here", "HEAD", "*.py"), set())

    def test_a_drop_in_leaves_proposals_out_unless_the_person_confirmed_them(self):
        files = {**FILES, "pkg/io/manifest.py": "x\n", "pkg/io/product_definition.py": "x\n"}
        repo, root = make_repo(files, REMOTE), plugin_root(PLUGIN_PROFILE, "probe", TEMPLATE)
        drop = scratch() / "drop.yaml"
        self.assertEqual(survey_in(repo, root, "--drop-in", str(drop)).returncode, 0)
        self.assertNotIn("depth", profile.parse(drop.read_text(), "d"))
        answers = scratch() / "answers.json"
        answers.write_text(json.dumps({"depth.deep": {"how": "confirmed", "value": ["pkg/io/manifest*"]},
                                       "downstream": {"how": "asked", "value": ["alpha"]},
                                       "posted_text": {"how": "asked", "value": "plain"},
                                       "coverage.command": {"how": "asked", "value": "pytest --cov=pkg tests/"}}))
        self.assertEqual(survey_in(repo, root, "--drop-in", str(drop), "--answers", str(answers)).returncode, 0)
        data = profile.parse(drop.read_text(), "d")
        self.assertEqual((data["depth"], data["downstream"]), ({"deep": ["pkg/io/manifest*"]}, ["alpha"]))
        self.assertEqual((data["posted_text"], data["coverage"]), ("plain", {"command": "pytest --cov=pkg tests/"}))
        answers.write_text(json.dumps({"lint.command": {"how": "asked", "value": "ruff check"},
                                       "tests.command": {"how": "asked", "value": "tox -e py"},
                                       "coverage.command": {"how": "asked", "value": "not yet recorded"}}))
        self.assertEqual(survey_in(repo, root, "--drop-in", str(drop), "--answers", str(answers)).returncode, 0)
        data = profile.parse(drop.read_text(), "d")
        self.assertEqual((data["lint"], data["tests"]), ({"command": "ruff check", "regex": "ruff[[:space:]]+check"}, {"command": "tox -e py"}))
        self.assertNotIn("coverage", data)
        self.assertEqual(data["gates"], {"tests": ""})
        cand = scratch() / "cand.yaml"
        self.assertEqual(survey_in(repo, root, "--profile", str(cand)).returncode, 0)
        flat = {f"{k}.{s}" if isinstance(v, dict) else k: x for k, v in profile.parse(cand.read_text(), "c").items()
                for s, x in (v.items() if isinstance(v, dict) else [(None, v)])}
        filled = next(k for k, v in flat.items() if v != profile.NOT_RECORDED and k not in survey.PROPOSALS)
        unfilled = next(k for k, v in flat.items() if v == profile.NOT_RECORDED and k not in survey.PROPOSALS
                        and k in ("ticket.project", "lint.command", "tests.command", "coverage.command", "types.regex"))
        answers.write_text(json.dumps({filled: {"how": "confirmed", "value": flat[filled]}}))
        self.assertEqual(survey_in(repo, root, "--drop-in", str(drop), "--answers", str(answers)).returncode, 0)
        top, _, sub = filled.partition(".")
        got = profile.parse(drop.read_text(), "d")
        self.assertEqual(got[top][sub] if sub else got[top], flat[filled])
        answers.write_text(json.dumps({unfilled: {"how": "confirmed", "value": profile.NOT_RECORDED}}))
        out = survey_in(repo, root, "--drop-in", str(drop), "--answers", str(answers))
        self.assertEqual(out.returncode, 1)
        self.assertIn("not the candidate's", out.stderr)
        answers.write_text(json.dumps({"tests.command": {"how": "asked", "value": "pytest -x tests/"},
                                       "gates.tests": {"how": "asked", "value": "nox"}}))
        self.assertEqual(survey_in(repo, root, "--drop-in", str(drop), "--answers", str(answers)).returncode, 0)
        self.assertEqual(profile.parse(drop.read_text(), "d")["gates"], {"tests": "nox"})
        answers.write_text(json.dumps({"tests.command": {"how": "asked", "value": "pytest -x tests/"}}))
        self.assertEqual(survey_in(repo, root, "--drop-in", str(drop), "--answers", str(answers)).returncode, 0)
        self.assertEqual(profile.parse(drop.read_text(), "d")["gates"], {"tests": "pytest"})
        bad = [({"tests.command": {"how": "confirmed", "value": "pytest elsewhere/"}}, "not the candidate's"),
               ({"depth.deep": {"how": "confirmed", "value": ["elsewhere/**"]}}, "not part of the proposal"),
               ({"downstream": {"how": "confirmed", "value": ["alpha"]}}, "not part of the proposal"),
               ({"depth.deep": {"how": "asked", "value": "pkg/**"}}, "depth.deep should be list"),
               ({"downstreams": {"how": "asked", "value": ["alpha"]}}, "'downstreams' is no profile key"),
               ({"posted_text": {"how": "asked"}}, "posted_text needs how"),
               ({"posted_text": {"how": "asked", "value": "loud"}}, "posted_text takes"),
               (["not", "an", "object"], "not a JSON object")]
        for data, says in bad:
            with self.subTest(says=says):
                answers.write_text(json.dumps(data))
                fresh = scratch() / "drop.yaml"
                out = survey_in(repo, root, "--drop-in", str(fresh), "--answers", str(answers))
                self.assertEqual(out.returncode, 1)
                self.assertIn(says, out.stderr)
                self.assertFalse(fresh.exists())
        answers.write_text("{not json")
        out = survey_in(repo, root, "--drop-in", str(scratch() / "d.yaml"), "--answers", str(answers))
        self.assertEqual((out.returncode, str(answers) in out.stderr), (1, True))
        prof = scratch() / "p.yaml"
        out = survey_in(repo, root, "--profile", str(prof), "--answers", str(answers))
        self.assertEqual(out.returncode, 2)
        self.assertIn("--answers goes with --drop-in", out.stderr)
        self.assertFalse(prof.exists())


class Score(Fixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows = scored(cls.path, cls.root)

    def test_each_key_is_classed(self):
        cls = {k: r["cls"] for k, r in self.rows.items()}
        self.assertEqual(cls["ticket.pattern"], "match")
        self.assertEqual(cls["template"], "match")
        self.assertEqual(cls["lint.command"], "match")
        self.assertEqual(cls["tests.command"], "differs")
        self.assertEqual(cls["coverage.command"], "conflict")
        self.assertEqual(cls["posted_text"], "project default")
        self.assertEqual(cls["depth.deep"], "missing")
        self.assertEqual(len(self.rows), 15)

    def test_a_value_no_repository_file_states_is_marked_likely_stale(self):
        self.assertIn("likely stale", self.rows["tests.command"]["note"])

    def test_a_value_the_repository_does_not_set_is_never_called_stale(self):
        root = plugin_root("ticket:\n  project: PROJ\n", "probe", TEMPLATE)
        row = scored(self.path, root)["tests.command"]
        self.assertEqual((row["cls"], row["note"]), ("differs", ""))

    def test_a_conflict_says_which_file_states_the_plugins_value(self):
        self.assertEqual(self.rows["coverage.command"]["note"], "CLAUDE.md states the plugin's value")

    def test_a_conflict_when_the_plugins_value_is_none_of_them(self):
        root = plugin_root("ticket:\n  project: PROJ\n", "probe", TEMPLATE)
        self.assertEqual(scored(self.path, root)["coverage.command"]["note"], "the plugin's value is none of them")

    def test_a_differing_value_a_file_states_is_named(self):
        path = copy(self.path, replaced("command: 'pytest -m \"not slow\" tests/'", "command: 'pytest x/'"),
                    lambda s: (s["keys"]["tests.command"]["seen"].append({"source": "docs/t.md", "value": "pytest tests/"}),
                               s["files"].__setitem__("docs/t.md", {"loads": "on demand", "chars": 20})))
        row = scored(path, self.root)["tests.command"]
        self.assertEqual((row["cls"], row["note"]), ("differs", "docs/t.md states the plugin's value"))

    def test_commands_compare_without_their_runner_or_a_trailing_slash(self):
        root = plugin_root("tests:\n  command: 'uv run pytest -m \"not slow\" tests'\n", "probe", TEMPLATE)
        self.assertEqual(scored(self.path, root)["tests.command"]["cls"], "match")

    def test_an_unrecorded_key_the_project_gives_is_a_project_default(self):
        row = self.rows["posted_text"]
        self.assertEqual((row["cls"], row["note"]),
                         ("project default", "what the plugin resolves without the repository's own settings, which a drop-in keeps"))
        self.assertTrue(row["plugin_source"].endswith(":profile.yaml"), row["plugin_source"])

    def test_a_project_default_is_what_the_repository_resolves_to_without_its_own_settings(self):
        root = plugin_root("public: false\n", "secret")
        repo = make_repo({"README.md": "x\n"}, "git@github.com:example-org/secret.git")
        row = scored(candidate_of(repo, root), root, repo="example-org/secret")["public"]
        self.assertEqual((row["cls"], row["plugin"]), ("project default", False))
        root = plugin_root("public: false\n", "probe")
        self.assertEqual(scored(candidate_of(make_repo({"README.md": "x\n"}, REMOTE), root), root)["public"]["cls"], "missing")

    def test_an_unrecorded_key_the_project_does_not_give_is_missing(self):
        for key in ("depth.deep", "downstream"):
            row = self.rows[key]
            self.assertEqual((row["cls"], row["note"]), ("missing", ""), key)

    def test_a_standard_of_its_own_in_one_file_is_all_the_repositorys_own(self):
        repo = make_repo(FILES, "git@github.com:example-org/probe.git")
        (repo / "standards").mkdir()
        (repo / "standards/profile.yaml").write_text("posted_text: workflow\ntests:\n  command: 'pytest tests/'\n")
        path = candidate_of_own(repo)
        out = subprocess.run([sys.executable, str(SCORER), str(path), "--json"], cwd=repo, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = {r["key"]: r for r in json.loads(out.stdout)}
        self.assertEqual((rows["posted_text"]["cls"], rows["posted_text"]["plugin_source"]), ("missing", "standards/profile.yaml"))
        self.assertEqual(rows["tests.command"]["plugin_source"], "standards/profile.yaml")
        self.assertEqual(rows["github_server"]["plugin_source"], "standards/default-profile.yaml")

    def test_an_inferred_value_is_derived_and_says_from_what(self):
        row = self.rows["lint.command"]
        self.assertEqual((row["tier"], row["note"]), ("derived", "inferred from .pre-commit-config.yaml"))

    def test_each_tier(self):
        tier = {k: r["tier"] for k, r in self.rows.items()}
        self.assertEqual(tier["ticket.project"], "derived")
        self.assertEqual(tier["public"], "derived")
        self.assertEqual(tier["tests.command"], "agent file")
        self.assertEqual(tier["template"], "human file")
        self.assertEqual(tier["coverage.command"], "agent file, human file")
        self.assertEqual(tier["posted_text"], "plugin store")
        answers = scratch() / "answers.json"
        answers.write_text(json.dumps({"downstream": {"how": "asked", "value": ["alpha", "beta"]}}))
        self.assertEqual(scored(self.path, self.root, "--answers", str(answers))["downstream"]["tier"], "person")

    def test_the_table_counts_tiers_once_each_and_the_session_start(self):
        out = score(self.path, self.root)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("tiers: derived 7 · agent file 2 · human file 1 · plugin store 5", out.stdout)
        chars = sum(len(FILES[p]) for p in SESSION)
        self.assertIn(f"session start: ~{chars // 4} tokens (characters / 4) from {', '.join(SESSION)}", out.stdout)

    def test_how_each_fact_loads(self):
        loads = {k: r["loads"] for k, r in self.rows.items()}
        self.assertEqual(loads["tests.command"], f"always ~{len(FILES['CLAUDE.md']) // 4} tok")
        self.assertEqual(loads["coverage.command"], f"always ~{len(FILES['CLAUDE.md']) // 4} tok, script")
        self.assertEqual(loads["template"], "script")
        self.assertEqual(loads["posted_text"], "script")

    def test_a_fact_from_a_file_no_session_loads_is_on_demand(self):
        doc = "- **Run unit tests**: `pytest tests/`\n"
        repo = make_repo({"docs/testing.md": doc}, "git@github.com:example-org/probe.git")
        row = scored(candidate_of(repo, self.root), self.root)["tests.command"]
        self.assertEqual((row["tier"], row["loads"]), ("human file", f"on demand ~{len(doc) // 4} tok"))

    def test_lists_compare_as_sets_and_a_proposal_covers_the_plugins(self):
        path = copy(self.path, replaced("downstream: not yet recorded", "downstream: ['beta', 'alpha']"), proposed("downstream"))
        row = scored(path, self.root)["downstream"]
        self.assertEqual((row["cls"], row["covers"]), ("match", True))
        path = copy(self.path, replaced("  deep: not yet recorded", "  deep: ['data/**', 'src/core/**', 'extra/**']"),
                    proposed("depth.deep"))
        row = scored(path, self.root)["depth.deep"]
        self.assertEqual((row["cls"], row["covers"]), ("differs", True))
        self.assertEqual(row["note"], "covers the plugin's, with 1 more for the person to trim")
        path = copy(self.path, replaced("  deep: not yet recorded", "  deep: ['src/core/**']"),
                    proposed("depth.deep"))
        row = scored(path, self.root)["depth.deep"]
        self.assertEqual((row["covers"], row["note"]), (False, "leaves out 1 of the plugin's values"))

    def test_answers_asked_and_confirmed(self):
        path = copy(self.path, replaced("  deep: not yet recorded", "  deep: ['data/**', 'src/core/**', 'extra/**']"),
                    proposed("depth.deep"))
        answers = scratch() / "answers.json"
        answers.write_text(json.dumps({"depth.deep": {"how": "confirmed", "value": ["src/core/**", "data/**"]},
                                       "posted_text": {"how": "asked", "value": "plain"}}))
        rows = scored(path, self.root, "--answers", str(answers))
        self.assertEqual((rows["depth.deep"]["cls"], rows["depth.deep"]["covers"]), ("confirmed", True))
        self.assertEqual(rows["depth.deep"]["note"], "the plugin's value")
        self.assertEqual((rows["posted_text"]["cls"], rows["posted_text"]["note"]), ("asked", "not the plugin's value"))

    def test_the_plugin_source_of_a_section_the_profile_leaves_unrecorded(self):
        root = plugin_root(PLUGIN_PROFILE + "lint:\n  command: not yet recorded\n  regex: not yet recorded\ntypes:\n  regex: not yet recorded\n",
                           "probe", TEMPLATE)
        rows = scored(self.path, root)
        self.assertTrue(rows["types.regex"]["plugin_source"].endswith("profiles/probe.yaml"))
        self.assertEqual((rows["types.regex"]["note"], rows["types.regex"]["tier"]), ("the plugin records none either", "-"))
        self.assertEqual((rows["lint.regex"]["cls"], rows["lint.regex"]["note"]), ("differs", "the plugin records none"))
        self.assertEqual(rows["lint.command"]["note"], "the plugin records none")
        self.assertTrue(rows["tests.command"]["plugin_source"].endswith("profiles/probe.yaml"))

    def test_a_mismatch_never_fails_the_report(self):
        self.assertEqual(score(self.path, self.root).returncode, 0)


class Malformed(Fixture):
    def refused(self, path: Path, *args: str, says: str) -> None:
        out = score(path, self.root, *args)
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn(says, out.stderr)
        self.assertNotIn("Traceback", out.stderr)

    def answers(self, data) -> Path:
        path = scratch() / "answers.json"
        path.write_text(json.dumps(data))
        return path

    def test_a_confirmed_value_outside_the_proposal_fails(self):
        self.refused(self.path, "--answers", str(self.answers({"downstream": {"how": "confirmed", "value": ["alpha"]}})),
                     says="not the candidate's")
        path = copy(self.path, replaced("  deep: not yet recorded", "  deep: ['src/core/**']"),
                    proposed("depth.deep"))
        answers = self.answers({"depth.deep": {"how": "confirmed", "value": ["src/core/**", "data/**"]}})
        self.refused(path, "--answers", str(answers), says="not the candidate's")

    def test_an_answer_for_no_key_or_without_how_fails(self):
        self.refused(self.path, "--answers", str(self.answers({"nope": {"how": "asked", "value": "x"}})), says="no profile key")
        self.refused(self.path, "--answers", str(self.answers({"posted_text": {"value": "plain"}})), says="needs how")
        self.refused(self.path, "--answers", str(self.answers({"posted_text": {"how": "asked", "value": "loud"}})),
                     says="posted_text takes")

    def test_a_candidate_the_schema_refuses_or_that_leaves_a_key_out_fails(self):
        self.refused(copy(self.path, lambda t: t + "flavor: plain\n"), says="unknown key 'flavor'")
        self.refused(copy(self.path, replaced("posted_text: not yet recorded\n", "")), says="leaves out posted_text")
        whole = replaced("types:\n  regex: not yet recorded\n", "types: not yet recorded\n")
        self.refused(copy(self.path, whole), says="leaves out types.regex")

    def test_a_missing_or_unreadable_sources_file_fails(self):
        path = copy(self.path)
        path.with_name("profile.sources.json").write_text("{not json")
        self.refused(path, says="profile.sources.json")
        path.with_name("profile.sources.json").unlink()
        self.refused(path, says="profile.sources.json")

    def test_a_sources_file_that_does_not_fit_the_candidate_fails(self):
        cases = [
            (lambda s: s.pop("repo"), "needs repo"),
            (lambda s: s["keys"].pop("posted_text"), "posted_text is not or is left out"),
            (lambda s: s["keys"].__setitem__("flavor", {"source": None, "conflict": False, "seen": []}), "flavor is not"),
            (lambda s: s["keys"]["posted_text"].pop("conflict"), "posted_text needs source"),
            (lambda s: s["keys"]["posted_text"].update(seen=[{"value": 1}]), "posted_text needs source"),
            (lambda s: s["keys"]["ticket.project"].update(conflict=True), "ticket.project's sources disagree"),
            (lambda s: s["keys"]["ticket.project"].update(source=None), "ticket.project reads 'PROJ'"),
            (lambda s: s["keys"]["posted_text"].update(source="CLAUDE.md"), "posted_text reads 'not yet recorded'"),
            (lambda s: s["files"]["CLAUDE.md"].update(loads="sometimes"), "files.CLAUDE.md needs loads"),
            (lambda s: s["session_start"].pop("chars"), "session_start needs files"),
            (lambda s: s["session_start"].update(files=[1, 2]), "session_start needs files"),
            (lambda s: s["session_start"].update(files=["nowhere.md"]), "session_start needs files"),
            (lambda s: s["session_start"].update(chars=s["session_start"]["chars"] + 1), "session_start.chars is"),
            (lambda s: s["files"].pop("history"), "history is a source with no entry in files"),
            (lambda s: s["files"].pop(".github/workflows/t.yml"), ".github/workflows/t.yml is a source with no entry"),
            (lambda s: s["keys"]["coverage.command"]["seen"].pop(), "coverage.command's sources disagree, but it lists 1"),
        ]
        for edit, says in cases:
            with self.subTest(says=says):
                self.refused(copy(self.path, edit_sources=edit), says=says)


if __name__ == "__main__":
    unittest.main()
