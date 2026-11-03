"""Tests for scripts/profile.py. Run with `python3 -m unittest discover -s tests`."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("profile", ROOT / "scripts" / "profile.py")
profile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(profile)


def run(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = profile.main(list(args))
    return rc, out.getvalue(), err.getvalue()


def run_in(cwd: Path, *args: str) -> tuple[int, str, str]:
    """profile.py run as a command from the working directory `cwd`, whose remotes name the owner."""
    out = subprocess.run([sys.executable, str(ROOT / "scripts/profile.py"), *args], cwd=cwd, capture_output=True, text=True)
    return out.returncode, out.stdout, out.stderr


def checkout(tmp: str, remote: str, files: dict) -> Path:
    """A committed checkout under `tmp` whose origin is `remote`."""
    repo = Path(tmp) / "work"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.org"]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "PROJ-1: start"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "PROJ-2: more"], check=True)
    subprocess.run([*git, "remote", "add", "origin", remote], check=True)
    return repo


def own(tmp: str, text: str, name: str = "x") -> Path:
    """A committed checkout of someone/<name> whose own standards/profile.yaml is `text`."""
    return checkout(tmp, f"git@github.com:someone/{name}.git", {"standards/profile.yaml": text})


# A standard's project settings, as a project records its own workflow, hosts and wordings.
PROJECT = """ticket:
  pattern: 'PROJ-\\d+'
  project: PROJ
posted_text: workflow
jira:
  statuses:
    - {name: New, next: ticket-draft, role: filed}
    - {name: To Do, next: implement-change, role: approved}
    - {name: Upcoming, next: implement-change}
    - {name: Under Development, next: implement-change, role: implementation}
    - {name: In Review, next: nothing}
    - {name: Done, next: nothing, role: finished}
    - {name: Abandoned, next: nothing, role: abandoned}
  pr_statuses: [Under Development, In Review]
internal:
  domains: [internal.example]
  private_repositories:
    - secret
    - other_secret
attribution:
  phrases: [drafted with AI assistance]
surface:
  identifiers: [ProductId]
"""
# A repository's own settings beside the project's, in a standard covering itself alone.
REPOSITORY = """downstream: [alpha, beta]
lint:
  command: 'pre-commit run --files'
  regex: 'pre-commit[[:space:]]+run'
public: true
"""


class Parser(unittest.TestCase):
    def test_the_subset_the_profiles_use(self):
        text = (
            "# a header comment\n"
            "ticket:\n  pattern: 'PROJ-\\d+' # who reads it\n  project: PROJ\n"
            "public: false\n"
            "internal:\n  domains: [example.org, example.net]\n"
            "tests:\n  command: 'pytest -m \"not e2e\" tests/'\n"
            "depth:\n  light:\n    - {glob: 'CHANGELOG.md', brief: documentation}\n  deep: ['a/**', 'b#c']\n"
            "downstream:\n  - alpha\n  - beta\n"
        )
        data = profile.parse(text, "p")
        self.assertEqual(data["ticket"], {"pattern": "PROJ-\\d+", "project": "PROJ"})
        self.assertIs(data["public"], False)
        self.assertEqual(data["internal"], {"domains": ["example.org", "example.net"]})
        self.assertEqual(data["tests"]["command"], 'pytest -m "not e2e" tests/')
        self.assertEqual(data["depth"], {"light": [{"glob": "CHANGELOG.md", "brief": "documentation"}], "deep": ["a/**", "b#c"]})
        self.assertEqual(data["downstream"], ["alpha", "beta"])

    def test_the_committed_profiles_parse(self):
        path = ROOT / "standards/default-profile.yaml"
        profile.check(profile.parse(path.read_text(), path.name), path.name, {**profile.SCHEMA, **profile.PROJECT_SCHEMA})
        profile.parse((ROOT / "standards/profile.example.yaml").read_text(), "profile.example.yaml")


class Resolve(unittest.TestCase):
    def test_a_standard_and_the_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, PROJECT + REPOSITORY)
            self.assertEqual(run_in(repo, "someone/x", "--field", "ticket.pattern"), (0, "PROJ-\\d+\n", ""))
            self.assertEqual(run_in(repo, "someone/x", "--field", "downstream"), (0, "alpha\nbeta\n", ""))
        self.assertEqual(run("someone/no_such_repo", "--field", "lint.command"), (0, "\n", ""))
        self.assertEqual(run("someone/no_such_repo", "--field", "depth.deep"), (0, "", ""))
        self.assertEqual(
            run("someone/no_such_repo", "--field", "depth.light")[1].splitlines(),
            [f'{{"glob": "{g}", "brief": "documentation"}}' for g in ("CHANGELOG.md", "README.md", "docs/**/*.md", "doc/**/*.md")],
        )

    def test_the_source_names_the_standards_file_or_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, REPOSITORY)
            self.assertEqual(run_in(repo, "someone/x", "--field", "source"), (0, "standards/profile.yaml\n", ""))
            self.assertTrue(run_in(repo, "someone/x")[1].startswith("source: standards/profile.yaml\n"))
            (repo / "standards/profile.yaml").write_text("source: elsewhere\n")
            rc, out, err = run_in(repo, "someone/x", "--field", "source")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("unknown key 'source'", err)
        self.assertEqual(run("someone/no_such_repo", "--field", "source"), (0, "none\n", ""))

    def test_a_partial_profile_keeps_the_defaults_it_leaves_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, "gates:\n  tests: 'npm test'\ntests:\n  command: not yet recorded\n")
            got = {line.split(": ", 1)[0]: line.split(": ", 1)[1] for line in run_in(repo, "someone/x")[1].splitlines()}
        self.assertEqual(got["gates.tests"], "npm test")
        self.assertEqual(got["tests.command"], "not yet recorded")
        self.assertEqual(got["lint.regex"], profile.defaults(ROOT, "someone/no_such_repo")["lint"]["regex"])

    def test_field_prints_a_list_one_item_a_line_and_a_section_as_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, REPOSITORY)
            self.assertEqual(run_in(repo, "someone/x", "--field", "downstream")[1], "alpha\nbeta\n")
            self.assertEqual(run_in(repo, "someone/x", "--field", "lint")[1], "lint.command: pre-commit run --files\nlint.regex: pre-commit[[:space:]]+run\n")
            self.assertIn("public: true\n", run_in(repo, "someone/x")[1])

    def test_a_field_under_an_unrecorded_section_is_unrecorded(self):
        self.assertEqual(run("--defaults", "--field", "jira.statuses"), (0, "not yet recorded\n", ""))
        self.assertEqual(run("--defaults", "--field", "jira.roles.finished"), (0, "not yet recorded\n", ""))
        self.assertEqual(run("someone/x", "--field", "gates.flavor")[0], 1)

    def test_an_unknown_field_exits_1(self):
        rc, _, err = run("someone/x", "--field", "ticket.host")
        self.assertEqual((rc, err), (1, "profile.py: no field 'ticket.host'\n"))


class Defaults(unittest.TestCase):
    def test_the_defaults_set_every_key_and_fill_what_a_standard_leaves_out(self):
        self.assertEqual(set(profile.defaults(ROOT)), set(profile.SCHEMA) | set(profile.PROJECT_SCHEMA))
        printed = {line.split(":")[0].split(".")[0] for line in run("someone/no_such_repo")[1].splitlines()}
        self.assertEqual(printed, set(profile.SCHEMA) | {"source"})
        self.assertEqual(run("someone/no_such_repo", "--field", "ticket.pattern"), run("--defaults", "--field", "ticket.pattern"))

    def test_defaults_prints_the_defaults_under_the_standard_with_no_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, PROJECT + REPOSITORY)
            rc, out, err = run_in(repo, "--defaults")
            self.assertEqual((rc, err), (0, ""))
            self.assertNotIn("source:", out)
            statuses = ", ".join(
                f'{{"name": "{n}", "next": "{p}"' + (f', "role": "{r}"' if r else "") + "}"
                for n, p, r in (("New", "ticket-draft", "filed"), ("To Do", "implement-change", "approved"), ("Upcoming", "implement-change", ""),
                                ("Under Development", "implement-change", "implementation"), ("In Review", "nothing", ""),
                                ("Done", "nothing", "finished"), ("Abandoned", "nothing", "abandoned"))
            )
            roles = "".join(f"jira.roles.{r}: {n}\n" for r, n in (("filed", "New"), ("approved", "To Do"), ("implementation", "Under Development"),
                                                                 ("finished", "Done"), ("abandoned", "Abandoned")))
            repository = run_in(repo, "someone/x")[1].replace("source: standards/profile.yaml\n", "")
            self.assertEqual(
                out,
                repository
                + f"jira.statuses: [{statuses}]\njira.pr_statuses: [Under Development, In Review]\n{roles}internal.domains: [internal.example]\n"
                + "internal.private_repositories: [secret, other_secret]\n"
                + "attribution.phrases: [drafted with AI assistance]\nsurface.identifiers: [ProductId]\n",
            )
        self.assertEqual(run("--defaults", "--field", "source")[0], 1)

    def test_a_repository_and_defaults_together_is_refused(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            profile.main(["someone/x", "--defaults"])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            profile.main([])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            profile.main(["--standard", "--defaults"])

    def test_standard_prints_its_own_standards_or_says_it_has_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, REPOSITORY)
            self.assertEqual(run_in(repo, "--standard"), (0, f"{(repo / 'standards').resolve()}\n", ""))
            (repo / "standards/profile.yaml").unlink()
            self.assertEqual(run_in(repo, "--standard"), (0, f"{(repo / 'standards').resolve()}\n", ""))
            (repo / "standards").rmdir()
            rc, out, err = run_in(repo, "--standard")
            self.assertEqual((rc, out), (1, ""))
            self.assertTrue(err.rstrip().endswith("the repository has no standard"), err)
            rc, out, err = run("--standard", "someone/elsewhere")
            self.assertEqual((rc, out), (1, ""))
            self.assertNotIn("has no standard", err)

    def test_the_owner_comes_from_origin_when_the_argument_names_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "work"
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "standards").mkdir()

            def standard(*args):
                rc, out, err = run_in(repo, "--standard", *args)
                return "standards" if rc == 0 else "none"
            self.assertEqual(standard(), "none")
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:someone/x.git"], check=True)
            self.assertEqual(standard(), "standards")
            self.assertEqual(standard("x"), "standards")
            self.assertEqual(standard("someone/x"), "standards")
            self.assertEqual(standard("someone/other_repo"), "none")
            self.assertEqual(standard("elsewhere/x"), "none")
            subprocess.run(["git", "-C", str(repo), "remote", "add", "upstream", "https://github.com/upstream-team/x"], check=True)
            self.assertEqual(standard(), "standards")
            self.assertEqual(standard("upstream-team/x"), "none", "the upstream remote's owner is never the run's")
            subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", "ssh://git@github.com/someone/x.git"], check=True)
            self.assertEqual(standard("someone/x"), "standards")

    def test_a_missing_default_profile_or_a_refused_standard_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, err = run("someone/x", "--root", tmp)
            self.assertEqual((rc, out), (1, ""))
            self.assertIn("standards/default-profile.yaml", err)
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, PROJECT)
            for old, new, says in (
                ("posted_text: workflow\n", "posted_text: workflow\nflavor: blue\n", "unknown key 'flavor'"),
                ("posted_text: workflow\n", "posted_text: workflow\nlint: not yet recorded\n", "leaves out lint (it reads not yet recorded)"),
                ("{name: Done, next: nothing, role: finished}", "{name: Done, next: rest, role: finished}", "jira.statuses should be statuses"),
                ("pr_statuses: [Under Development,", "pr_statuses: [Blocked,", "jira.pr_statuses names Blocked, not in jira.statuses"),
                ("domains: [internal.example]", "domains: not yet recorded", "internal.domains reads not yet recorded"),
                ("pr_statuses: [Under Development, In Review]", "pr_statuses: not yet recorded", "jira.pr_statuses reads not yet recorded"),
                ("    - {name: Abandoned, next: nothing, role: abandoned}\n", "    - {name: Abandoned, next: nothing, role: abandoned}\n    - {name: new, next: nothing}\n", "jira.statuses names new twice"),
                ("{name: Done, next: nothing, role: finished}", "{name: ' Done', next: nothing, role: finished}", "empty or has spaces around it"),
                ("{name: Done, next: nothing, role: finished}", "{name: Done, next: [nothing], role: finished}", "jira.statuses should be statuses"),
                ("{name: Done, next: nothing, role: finished}", "{name: Done, next: nothing, role: closed}", "jira.statuses gives Done the role 'closed', not one of filed, approved, implementation, finished, abandoned"),
                ("{name: Done, next: nothing, role: finished}", "{name: Done, next: nothing}", "gives the role finished to no status; it takes exactly one"),
                ("{name: Abandoned, next: nothing, role: abandoned}", "{name: Abandoned, next: nothing, role: finished}", "gives the role finished to Done, Abandoned; it takes exactly one"),
                ("  pr_statuses:", "  roles: {finished: Done}\n  pr_statuses:", "unknown key 'jira.roles'"),
                ("domains: [internal.example]", "domains: ['https://internal.example']", "not a bare host name"),
                ("domains: [internal.example]", "domains: ['']", "not a bare host name"),
                ("domains: [internal.example]", "domains: ['*.internal.example']", "not a bare host name"),
                ("    - secret\n", "    - someone/secret\n", "not a bare repository name"),
                ("  private_repositories:\n    - secret\n    - other_secret\n", "  private_repositories: not yet recorded\n", "internal.private_repositories reads not yet recorded"),
                ("  phrases: [drafted with AI assistance]\n", "  phrases: not yet recorded\n", "attribution.phrases reads not yet recorded"),
                ("  phrases: [drafted with AI assistance]\n", "  phrases: ['  ']\n", "attribution.phrases has an empty phrase"),
                ("  identifiers: [ProductId]\n", "  identifiers: not yet recorded\n", "surface.identifiers reads not yet recorded"),
                ("  identifiers: [ProductId]\n", "  identifiers: [pkg.ProductId]\n", "not a Python class name"),
                ("surface:\n  identifiers: [ProductId]\n", "surface: not yet recorded\n", "leaves out surface (it reads not yet recorded)"),
            ):
                with self.subTest(says=says):
                    changed = PROJECT.replace(old, new)
                    self.assertNotEqual(changed, PROJECT)
                    (repo / "standards/profile.yaml").write_text(changed)
                    rc, out, err = run_in(repo, "--defaults")
                    self.assertEqual((rc, out), (1, ""))
                    self.assertIn(says, err)

    def test_the_roles_print_with_the_defaults_and_name_one_status_each(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, PROJECT)
            self.assertEqual(run_in(repo, "--defaults", "--field", "jira.roles.finished"), (0, "Done\n", ""))
            self.assertEqual(run_in(repo, "--defaults", "--field", "jira.roles.abandoned"), (0, "Abandoned\n", ""))
            self.assertEqual(
                run_in(repo, "--defaults", "--field", "jira.roles")[1],
                "jira.roles.filed: New\njira.roles.approved: To Do\njira.roles.implementation: Under Development\n"
                "jira.roles.finished: Done\njira.roles.abandoned: Abandoned\n",
            )
            self.assertIn('{"name": "Upcoming", "next": "implement-change"}\n', run_in(repo, "--defaults", "--field", "jira.statuses")[1])
            self.assertEqual(run_in(repo, "--defaults", "--field", "jira.roles.reviewed")[0], 1)
            self.assertNotIn("jira", run_in(repo, "someone/x")[1])

    def test_a_private_repository_is_not_public_whatever_its_profile_leaves_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, PROJECT, "secret")
            self.assertEqual(run_in(repo, "someone/secret", "--field", "public"), (0, "false\n", ""))
            for text, want in (("public: not yet recorded\n", (0, "false\n", "")), ("public: false\n", (0, "false\n", ""))):
                (repo / "standards/profile.yaml").write_text(PROJECT + text)
                self.assertEqual(run_in(repo, "someone/secret", "--field", "public"), want)
            (repo / "standards/profile.yaml").write_text(PROJECT + "public: true\n")
            rc, out, err = run_in(repo, "someone/secret", "--field", "public")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("public is true, but standards/profile.yaml over standards/default-profile.yaml lists the repository as private", err)
        with tempfile.TemporaryDirectory() as tmp:
            repo = own(tmp, PROJECT.replace("    - secret\n", "    - Mixed_Case\n"), "mixed_case")
            self.assertEqual(run_in(repo, "someone/mixed_case", "--field", "public"), (0, "false\n", ""))
        for arg in ("someone/secret.git", "git@github.com:o/secret.git", "someone/a b"):
            with self.subTest(arg=arg):
                rc, out, err = run(arg, "--field", "public")
                self.assertEqual((rc, out), (1, ""))
                self.assertIn("is not a bare repository name", err)


class Refusals(unittest.TestCase):
    def refused(self, text: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, err = run_in(own(tmp, text), "someone/x")
        self.assertEqual((rc, out), (1, ""))
        return err

    def test_an_unknown_key(self):
        self.assertIn("unknown key 'flavor'", self.refused("flavor: blue\n"))
        self.assertIn("unknown key 'tests.shell'", self.refused("tests:\n  shell: bash\n"))
        self.assertIn("unknown key 'tests.runner'", self.refused("tests:\n  runner: pytest-runner\n"))

    def test_a_value_of_the_wrong_shape(self):
        self.assertIn("public should be bool", self.refused("public: yes\n"))
        self.assertIn("depth.light should be light", self.refused("depth:\n  light:\n    - {glob: 'x', brief: true}\n"))
        self.assertIn("posted_text takes plain, workflow", self.refused("posted_text: quiet\n"))
        self.assertIn("depth.light should be light", self.refused("depth:\n  light:\n    - {glob: 'x'}\n"))
        self.assertIn("ticket is a section", self.refused("ticket: PROJ\n"))

    def test_a_template_that_is_not_a_bare_name(self):
        for bad in ("mine/", "../templates/mine", "./mine", ""):
            with self.subTest(template=bad):
                self.assertIn("template is a bare name", self.refused(f"template: '{bad}'\n"))

    def test_a_line_the_parser_does_not_read(self):
        self.assertIn("standards/profile.yaml:2: a line the profile parser does not read", self.refused("public: true\n   odd: indent\n"))
        self.assertIn("public is given twice", self.refused("public: true\npublic: false\n"))
        self.assertIn("tests.command is given twice", self.refused("tests:\n  command: a\n  command: b\n"))

    def test_a_pattern_that_is_not_a_regular_expression(self):
        self.assertIn("ticket.pattern has 'PROJ-(', which is not a regular expression", self.refused("ticket:\n  pattern: 'PROJ-('\n"))
        self.assertIn("depth.light has '[bad', which is not a regular expression", self.refused("depth:\n  light:\n    - {glob: 'x', hunk: '[bad', brief: documentation}\n"))


class Detected(unittest.TestCase):
    """A repository with no standard runs on what its checkout states, over the default profile."""

    FILES = {
        ".pre-commit-config.yaml": "repos:\n  - repo: x\n    hooks:\n      - id: ruff\n",
        "AGENTS.md": "## Testing\n\n```\npytest tests/  # unit tests\n```\n",
    }

    def test_the_checkout_fills_what_it_states_and_the_default_profile_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = checkout(tmp, "git@github.com:someone/probe.git", self.FILES)
            for args in (("someone/probe",), ("probe",)):
                with self.subTest(args=args):
                    rc, out, err = run_in(repo, *args)
                    self.assertEqual(rc, 0, err)
                    values = dict(line.split(": ", 1) for line in out.splitlines())
                    self.assertEqual(values["source"], "none")
                    self.assertEqual(values["ticket.pattern"], "PROJ-\\d+")
                    self.assertEqual(values["tests.command"], "pytest tests/")
                    self.assertEqual(values["lint.command"], "pre-commit run --files")
                    self.assertEqual(values["posted_text"], "plain")
                    self.assertEqual(values["template"], "not yet recorded")
                    self.assertEqual(values["depth.deep"], "[]")
            cached = list((repo / ".git/lasp-dev/detected").glob("*"))
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
            self.assertEqual(len(cached), 1)
            self.assertTrue(cached[0].name.startswith(f"{head}-") and cached[0].suffix == ".yaml")
            self.assertFalse((repo / ".review").exists())
            cached[0].write_text("tests:\n  command: 'pytest -x'\n")
            self.assertEqual(run_in(repo, "someone/probe", "--field", "tests.command"), (0, "pytest -x\n", ""))
            (repo / "AGENTS.md").write_text("## Testing\n\n```\npytest -q tests/  # unit tests\n```\n")
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-qam", "PROJ-3: quiet"], check=True)
            self.assertEqual(run_in(repo, "someone/probe", "--field", "tests.command"), (0, "pytest -q tests/\n", ""))
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
            (cached,) = (repo / ".git/lasp-dev/detected").glob("*")
            self.assertTrue(cached.name.startswith(f"{head}-"))

    def test_a_checkout_with_no_commit_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "empty"
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:someone/empty.git"], check=True)
            rc, out, err = run_in(repo, "someone/empty")
            self.assertEqual((rc, out), (1, ""))
            self.assertIn("has no commit", err)
            self.assertFalse((repo / ".git/lasp-dev").exists())

    def test_a_survey_that_fails_is_refused_and_caches_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = checkout(tmp, "git@github.com:someone/probe.git", self.FILES)
            plugin = Path(tmp) / "plugin"
            (plugin / "standards").mkdir(parents=True)
            shutil.copy(ROOT / "standards/default-profile.yaml", plugin / "standards")
            (plugin / "scripts").mkdir()
            shutil.copy(ROOT / "scripts/profile.py", plugin / "scripts")
            (plugin / "scripts/survey.py").write_text("import sys\nsys.exit('cannot read this checkout')\n")
            out = subprocess.run([sys.executable, str(plugin / "scripts/profile.py"), "someone/probe"], cwd=repo, capture_output=True, text=True)
            self.assertEqual((out.returncode, out.stdout), (1, ""))
            self.assertIn("survey.py could not read", out.stderr)
            self.assertIn("cannot read this checkout", out.stderr)
            self.assertEqual(list((repo / ".git/lasp-dev/detected").iterdir()), [])

    def test_a_survey_left_by_a_stopped_process_goes_once_a_minute_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = checkout(tmp, "git@github.com:someone/probe.git", self.FILES)
            detected = repo / ".git/lasp-dev/detected"
            detected.mkdir(parents=True)
            stale, fresh = detected / "a.yaml.1.tmp", detected / "b.yaml.2.tmp"
            stale.write_text("")
            fresh.write_text("")
            os.utime(stale, (time.time() - 120, time.time() - 120))
            self.assertEqual(run_in(repo, "someone/probe", "--field", "posted_text"), (0, "plain\n", ""))
            self.assertFalse(stale.exists())
            self.assertTrue(fresh.exists())

    def test_a_deepened_shallow_clone_surveys_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = checkout(tmp, "git@github.com:someone/probe.git", self.FILES)
            repo = Path(tmp) / "shallow"
            subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{source}", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", "git@github.com:someone/probe.git"], check=True)
            self.assertEqual(run_in(repo, "someone/probe", "--field", "ticket.pattern")[0], 0)
            (before,) = (repo / ".git/lasp-dev/detected").glob("*.yaml")
            subprocess.run(["git", "-C", str(repo), "fetch", "-q", "--unshallow", f"file://{source}"], check=True)
            self.assertEqual(run_in(repo, "someone/probe", "--field", "ticket.pattern")[0], 0)
            (after,) = (repo / ".git/lasp-dev/detected").glob("*.yaml")
            self.assertNotEqual(before.name, after.name)

    def test_another_repository_reads_no_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = checkout(tmp, "git@github.com:someone/probe.git", self.FILES)
            self.assertEqual(run_in(repo, "someone/other", "--field", "ticket.pattern"), (0, "not yet recorded\n", ""))
            self.assertEqual(run_in(repo, "elsewhere/probe", "--field", "ticket.pattern"), (0, "not yet recorded\n", ""))
            self.assertFalse((repo / ".git/lasp-dev").exists())

    def test_the_defaults_are_the_default_profile_with_no_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = checkout(tmp, "git@github.com:someone/probe.git", self.FILES)
            self.assertEqual(run_in(repo, "--defaults", "--field", "posted_text"), (0, "plain\n", ""))
            self.assertEqual(run_in(repo, "--defaults", "--field", "jira.roles.finished"), (0, "not yet recorded\n", ""))
            self.assertEqual(run_in(repo, "--defaults", "--field", "jira.pr_statuses"), (0, "not yet recorded\n", ""))
            self.assertEqual(run_in(repo, "--defaults", "--field", "internal.domains"), (0, "", ""))
            self.assertEqual(run_in(repo, "--defaults", "--field", "ticket.pattern"), (0, "not yet recorded\n", ""))

    def test_detected_values_the_schema_refuses_stop_the_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = checkout(tmp, "git@github.com:someone/probe.git", self.FILES)
            run_in(repo, "someone/probe")
            (cached,) = (repo / ".git/lasp-dev/detected").glob("*.yaml")
            cached.write_text("flavor: sweet\n")
            rc, out, err = run_in(repo, "someone/probe")
            self.assertEqual((rc, out), (1, ""))
            self.assertIn("unknown key 'flavor'", err)

    def test_the_default_profile_sets_every_key_and_no_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "standards").mkdir()
            text = (ROOT / "standards/default-profile.yaml").read_text()
            (Path(tmp) / "standards/default-profile.yaml").write_text("owners: [someone]\n" + text)
            self.assertIn("unknown key 'owners'", run("someone/x", "--root", tmp)[2])
            (Path(tmp) / "standards/default-profile.yaml").write_text(text.replace("posted_text: plain\n", ""))
            self.assertIn("leaves out posted_text", run("someone/x", "--root", tmp)[2])


class OwnAndElsewhere(unittest.TestCase):
    """A repository reads its standard's settings over what its checkout states: its
    own standards/, or the standard its standards/profile.yaml points at."""

    FILES = {"AGENTS.md": "## Testing\n\n```\npytest tests/  # unit tests\n```\n"}
    OWN = ("tests:\n  command: 'pytest -q'\njira:\n  statuses:\n    - {name: Open, next: ticket-draft, role: filed}\n"
           "    - {name: Ready, next: implement-change, role: approved}\n"
           "    - {name: Under Development, next: implement-change, role: implementation}\n"
           "    - {name: Closed, next: nothing, role: finished}\n    - {name: Dropped, next: nothing, role: abandoned}\n"
           "  pr_statuses: [Under Development]\n")
    PROJECT = ("ticket:\n  pattern: 'FAM-\\d+'\n  project: FAM\nposted_text: workflow\n"
               "attribution:\n  phrases: [drafted by the family's bot]\n")
    MEMBER = "tests:\n  command: 'make test'\n"
    POINTER = {"standards/profile.yaml": "standard: fam/shared\n"}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name)
        self.family = self.parent / "gh/fam/shared.git"
        self.family.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.family)], check=True)
        self.publish(self.PROJECT)
        subprocess.run(["git", "-C", str(self.family), "config", "uploadpack.allowFilter", "true"], check=True)
        gitconfig = self.parent / "gitconfig"
        gitconfig.write_text(f'[url "file://{self.parent}/gh/"]\n\tinsteadOf = git@github.com:\n')
        self.env = {k: v for k, v in os.environ.items() if k != profile.OFFLINE}
        self.env.update({"GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_TERMINAL_PROMPT": "0"})

    def tearDown(self):
        self.tmp.cleanup()

    def publish(self, project: str | None, member: str | None = MEMBER, others: dict | None = None):
        """Commits the standard: its profile.yaml, profiles/member.yaml and any other files, each
        left out when None."""
        standards = self.family / "standards"
        if standards.exists():
            shutil.rmtree(standards)
        standards.mkdir()
        (standards / "decisions.md").write_text("decisions\n")
        for rel, text in {"profile.yaml": project, "profiles/member.yaml": member, **(others or {})}.items():
            if text is not None:
                (standards / rel).parent.mkdir(parents=True, exist_ok=True)
                (standards / rel).write_text(text)
        git = ["git", "-C", str(self.family), "-c", "user.name=t", "-c", "user.email=t@example.org"]
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", "standards"], check=True)

    def sha(self) -> str:
        return subprocess.run(["git", "-C", str(self.family), "log", "-1", "--format=%h"], capture_output=True, text=True).stdout.strip()

    def ask(self, repo: Path, *args: str, env: dict | None = None) -> tuple[int, str, str]:
        p = subprocess.run([sys.executable, str(ROOT / "scripts/profile.py"), *args], cwd=repo, capture_output=True, text=True, env=env or self.env)
        return p.returncode, p.stdout, p.stderr

    def member(self, files: dict, name: str = "member") -> Path:
        """A checkout, its standard fetched when it points at one, as a build or review would."""
        repo = checkout(str(self.parent / name), f"git@github.com:someone/{name}.git", {**self.FILES, **files})
        if "standard:" in files.get("standards/profile.yaml", ""):
            self.fetch(repo)
        return repo

    def fetch(self, repo: Path):
        subprocess.run(["bash", str(ROOT / "scripts/standard.sh")], cwd=repo, env=self.env, check=True, capture_output=True)

    def test_its_own_file_comes_first_and_may_set_a_project_key(self):
        repo = self.member({"standards/profile.yaml": self.OWN})
        rc, out, err = self.ask(repo, "someone/member")
        self.assertEqual(rc, 0, err)
        values = dict(line.split(": ", 1) for line in out.splitlines())
        self.assertEqual(values["source"], "standards/profile.yaml")
        self.assertEqual(values["tests.command"], "pytest -q")
        self.assertEqual(values["ticket.pattern"], "PROJ-\\d+")
        self.assertEqual(values["posted_text"], "plain")
        self.assertEqual(self.ask(repo, "--defaults", "--field", "jira.pr_statuses"), (0, "Under Development\n", ""))
        self.assertEqual(self.ask(repo, "--defaults", "--field", "jira.roles.finished"), (0, "Closed\n", ""))

    def test_an_uncommitted_file_is_read_as_it_stands(self):
        repo = self.member({})
        (repo / "standards").mkdir()
        (repo / "standards/profile.yaml").write_text("posted_text: workflow\n")
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "workflow\n", ""))

    def test_the_standard_elsewhere_wins_over_what_is_detected(self):
        repo = self.member(self.POINTER)
        rc, out, err = self.ask(repo, "someone/member")
        self.assertEqual(rc, 0, err)
        values = dict(line.split(": ", 1) for line in out.splitlines())
        sha = self.sha()
        self.assertEqual(values["source"], f"fam/shared@{sha}:standards/profile.yaml, fam/shared@{sha}:standards/profiles/member.yaml")
        self.assertEqual(values["posted_text"], "workflow")
        self.assertEqual(values["ticket.pattern"], "FAM-\\d+", "the standard wins over the checkout's history")
        self.assertEqual(values["tests.command"], "make test", "the standard wins over the checkout's instructions")
        self.assertEqual(values["coverage.command"], "", "what neither states is the default's")
        self.assertEqual(self.ask(repo, "--defaults", "--field", "attribution.phrases"), (0, "drafted by the family's bot\n", ""))

    def test_standard_prints_the_standard_elsewhere_or_its_own(self):
        repo = self.member(self.POINTER)
        rc, out, err = self.ask(repo, "--standard")
        self.assertEqual(rc, 0, err)
        self.assertTrue((Path(out.strip()) / "decisions.md").is_file())
        self.assertTrue(out.startswith(str(repo.resolve() / ".git/lasp-dev/standard/fam__shared/")), out)
        own = self.member({"standards/profile.yaml": self.OWN}, "other")
        self.assertEqual(self.ask(own, "--standard"), (0, f"{(own / 'standards').resolve()}\n", ""))
        subprocess.run(["git", "-C", str(repo), "config", "lasp-dev.standard", "none"], check=True)
        rc, out, err = self.ask(repo, "--standard")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("fam/shared's standard, not read", err)

    def test_a_fork_with_no_upstream_remote_reads_the_pointed_standard_for_its_name(self):
        repo = self.member(self.POINTER)
        self.assertEqual(subprocess.run(["git", "-C", str(repo), "remote"], capture_output=True, text=True).stdout, "origin\n")
        self.assertEqual(self.ask(repo, "someone/member", "--field", "ticket.pattern"), (0, "FAM-\\d+\n", ""))
        self.assertEqual(self.ask(repo, "someone/member", "--field", "tests.command"), (0, "make test\n", ""))
        self.assertEqual(self.ask(repo, "--defaults", "--field", "attribution.phrases"), (0, "drafted by the family's bot\n", ""))

    def test_standard_refuses_what_the_profile_refuses(self):
        self.publish(self.PROJECT, member=None, others={"profiles/someone_else.yaml": self.MEMBER})
        repo = self.member(self.POINTER)
        rc, out, err = self.ask(repo, "--standard")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("has no profiles/member.yaml, so the standard does not cover member", err)
        own = self.member({"standards/profile.yaml": "flavor: sweet\n"}, "other")
        rc, out, err = self.ask(own, "--standard")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("standards/profile.yaml: unknown key 'flavor'", err)
        self.assertNotIn("has no standard", err)

    def test_the_standard_is_read_as_of_the_last_fetch(self):
        repo = self.member(self.POINTER)
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "workflow\n", ""))
        self.publish(self.PROJECT.replace("posted_text: workflow", "posted_text: plain"))
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "workflow\n", ""))
        self.fetch(repo)
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "plain\n", ""))

    def test_the_standard_is_read_with_no_network(self):
        repo = self.member(self.POINTER)
        shutil.rmtree(self.family)
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "workflow\n", ""))

    def test_the_first_read_in_a_clone_fetches_once(self):
        repo = self.member(self.POINTER)
        shutil.rmtree(repo / ".git/lasp-dev/standard")
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "workflow\n", ""))
        self.publish(self.PROJECT.replace("posted_text: workflow", "posted_text: plain"))
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "workflow\n", ""), "a later read does not fetch")

    def test_offline_as_a_hook_reads_it_never_fetches(self):
        repo = self.member(self.POINTER)
        shutil.rmtree(repo / ".git/lasp-dev/standard")
        rc, out, err = self.ask(repo, "someone/member", env={**self.env, profile.OFFLINE: "1"})
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("has not been fetched in this clone", err)
        self.assertFalse((repo / ".git/lasp-dev/standard").exists())

    def test_a_first_fetch_that_fails_is_refused(self):
        repo = self.member(self.POINTER)
        shutil.rmtree(repo / ".git/lasp-dev/standard")
        shutil.rmtree(self.family)
        for args in (("someone/member",), ("--defaults",)):
            rc, out, err = self.ask(repo, *args)
            self.assertEqual((rc, out), (1, ""))
            self.assertIn("could not fetch", err)

    def test_a_fetch_stopped_before_it_wrote_the_files_is_fetched_again(self):
        repo = self.member(self.POINTER)
        self.publish(self.PROJECT.replace("posted_text: workflow", "posted_text: plain"))
        cache = next((repo / ".git/lasp-dev/standard").glob("*.git"))
        # A run stopped after git fetched the commit, before it wrote the commit's files out.
        subprocess.run(["git", f"--git-dir={cache}", "fetch", "-q", "--filter=blob:none", "standard", "HEAD"], env=self.env, check=True)
        subprocess.run(["git", f"--git-dir={cache}", "update-ref", "-d", "refs/lasp-dev/standards"], check=True)
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "plain\n", ""))

    def test_two_first_reads_at_once_both_answer(self):
        repo = self.member(self.POINTER)
        shutil.rmtree(repo / ".git/lasp-dev/standard")
        runs = [subprocess.Popen(["bash", str(ROOT / "scripts/standard.sh"), "--cached"], cwd=repo, env=self.env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(3)]
        done = [run.communicate() + (run.returncode,) for run in runs]
        self.assertEqual([rc for _, _, rc in done], [0, 0, 0], [err for _, err, _ in done])
        self.assertEqual(len({out for out, _, _ in done}), 1)

    def test_an_empty_cache_directory_is_fetched_into_never_resolved_to_the_member(self):
        repo = self.member(self.POINTER)
        cache = next((repo / ".git/lasp-dev/standard").glob("*.git"))
        shutil.rmtree(cache)
        shutil.rmtree(repo / ".git/lasp-dev/standard/fam__shared")
        cache.mkdir()
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "workflow\n", ""))
        remotes = subprocess.run(["git", "-C", str(repo), "remote"], capture_output=True, text=True).stdout.split()
        self.assertEqual(remotes, ["origin"])

    def refusal(self, repo: Path) -> str:
        rc, out, err = self.ask(repo, "someone/member")
        self.assertEqual((rc, out), (1, ""), err)
        return err

    def test_a_standard_with_no_profiles_covers_only_its_own_repository(self):
        self.publish("posted_text: workflow\ntests:\n  command: 'make test'\n", member=None)
        repo = self.member(self.POINTER)
        self.assertIn("has no profiles/, so the standard covers only its own repository, not member", self.refusal(repo))

    def test_a_repository_the_standard_does_not_cover_is_refused(self):
        self.publish(self.PROJECT, member=None, others={"profiles/someone_else.yaml": self.MEMBER})
        repo = self.member(self.POINTER)
        self.assertIn("has no profiles/member.yaml, so the standard does not cover member", self.refusal(repo))

    def test_a_setting_in_the_wrong_file_is_refused(self):
        self.publish(self.PROJECT + "tests:\n  command: 'make test'\n")
        repo = self.member(self.POINTER)
        self.assertIn("profile.yaml sets tests, which a repository sets", self.refusal(repo))
        self.publish(self.PROJECT, member="posted_text: plain\n")
        self.fetch(repo)
        self.assertIn("profiles/member.yaml sets posted_text, which the project sets", self.refusal(repo))

    def test_its_own_standard_for_several_reads_its_own_profiles_file(self):
        repo = self.member({"standards/profile.yaml": self.PROJECT, "standards/profiles/member.yaml": self.MEMBER})
        rc, out, err = self.ask(repo, "someone/member", "--field", "source")
        self.assertEqual((rc, out), (0, "standards/profile.yaml, standards/profiles/member.yaml\n"), err)
        self.assertEqual(self.ask(repo, "someone/member", "--field", "tests.command"), (0, "make test\n", ""))

    def test_another_repository_the_standard_covers_is_read_through_it(self):
        sibling = "tests:\n  command: 'tox'\n"
        repo = self.member({"standards/profile.yaml": self.PROJECT, "standards/profiles/member.yaml": self.MEMBER,
                            "standards/profiles/sib.yaml": sibling})
        self.assertEqual(self.ask(repo, "someone/sib", "--field", "source"), (0, "standards/profile.yaml, standards/profiles/sib.yaml\n", ""))
        self.assertEqual(self.ask(repo, "someone/sib", "--field", "ticket.pattern"), (0, "FAM-\\d+\n", ""))
        self.assertEqual(self.ask(repo, "someone/sib", "--field", "tests.command"), (0, "tox\n", ""))
        self.publish(self.PROJECT, others={"profiles/sib.yaml": sibling})
        pointed = self.member(self.POINTER, name="pointed")
        self.assertEqual(self.ask(pointed, "someone/sib", "--field", "source"),
                         (0, f"fam/shared@{self.sha()}:standards/profile.yaml, fam/shared@{self.sha()}:standards/profiles/sib.yaml\n", ""))
        self.assertEqual(self.ask(pointed, "someone/sib", "--field", "ticket.pattern"), (0, "FAM-\\d+\n", ""))

    def test_another_repository_the_standard_does_not_cover_reads_as_before(self):
        repo = self.member({"standards/profile.yaml": self.PROJECT, "standards/profiles/member.yaml": self.MEMBER})
        elsewhere = self.ask(self.parent, "someone/stranger", "--field", "ticket.pattern")
        self.assertEqual(self.ask(repo, "someone/stranger", "--field", "ticket.pattern"), elsewhere)
        self.assertNotEqual(elsewhere[1], "FAM-\\d+\n")
        pointed = self.member(self.POINTER, name="pointed")
        self.assertEqual(self.ask(pointed, "someone/stranger", "--field", "ticket.pattern"), elsewhere)

    def test_the_standards_own_repository_reads_the_projects_settings(self):
        repo = self.member({"standards/profile.yaml": self.PROJECT, "standards/profiles/other.yaml": self.MEMBER})
        rc, out, err = self.ask(repo, "someone/member", "--field", "source")
        self.assertEqual((rc, out), (0, "standards/profile.yaml\n"), err)
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "workflow\n", ""))

    def test_a_pointer_holds_nothing_else(self):
        repo = checkout(str(self.parent / "other"), "git@github.com:someone/other.git", {"standards/profile.yaml": "standard: fam/shared\nposted_text: plain\n"})
        rc, out, err = self.ask(repo, "someone/other")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("holds that one line alone", err)
        self.publish(self.PROJECT + "standard: fam/other\n")
        repo = self.member(self.POINTER)
        self.assertIn("names another standard; a pointer is followed one level", self.refusal(repo))

    def test_a_pointer_beside_its_own_decisions_is_refused(self):
        repo = self.member({**self.POINTER, "standards/decisions.md": "own\n"})
        self.assertIn("a repository's standard is in one place", self.refusal(repo))

    def test_a_local_checkout_is_read_as_it_stands_and_named(self):
        repo = self.member(self.POINTER)
        trial = self.parent / "trial"
        subprocess.run(["git", "clone", "-q", "git@github.com:fam/shared.git", str(trial)], env=self.env, check=True)
        (trial / "standards/profile.yaml").write_text(self.PROJECT.replace("posted_text: workflow", "posted_text: plain"))
        subprocess.run(["git", "-C", str(repo), "config", "lasp-dev.standard", str(trial)], check=True)
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text"), (0, "plain\n", ""))
        rc, out, err = self.ask(repo, "someone/member", "--field", "source")
        self.assertIn(f"fam/shared at {trial.resolve()}/standards (local):profile.yaml", out)

    def test_none_reads_without_the_standard_and_says_so(self):
        repo = self.member(self.POINTER)
        shutil.rmtree(self.family)
        subprocess.run(["git", "-C", str(repo), "config", "lasp-dev.standard", "none"], check=True)
        rc, out, err = self.ask(repo, "someone/member")
        self.assertEqual(rc, 0, err)
        values = dict(line.split(": ", 1) for line in out.splitlines())
        self.assertEqual(values["source"], "fam/shared's standard, not read (lasp-dev.standard is none)")
        self.assertEqual(values["tests.command"], "pytest tests/")

    def test_files_the_schema_refuses_are_refused_naming_them(self):
        repo = self.member({"standards/profile.yaml": "flavor: sweet\n"})
        self.assertIn("standards/profile.yaml: unknown key 'flavor'", self.refusal(repo))
        (repo / "standards/profile.yaml").write_text("jira:\n  statuses:\n    - {name: Open, next: nothing}\n")
        self.assertIn("standards/profile.yaml over standards/default-profile.yaml: leaves out jira.pr_statuses", self.refusal(repo))
        (repo / "standards/profile.yaml").write_text("jira:\n  statuses:\n    - {name: Open, next: nothing}\n  pr_statuses: []\n")
        self.assertIn("standards/profile.yaml over standards/default-profile.yaml: jira.statuses gives the role filed to no status", self.refusal(repo))
        self.publish("flavor: sweet\n")
        (repo / "standards/profile.yaml").write_text("standard: fam/shared\n")
        self.fetch(repo)
        err = self.refusal(repo)
        self.assertIn(f"fam/shared@{self.sha()}:standards/profile.yaml: unknown key 'flavor'", err)

    def module(self, repo: Path, code: str) -> str:
        """What `code`, run with profile.py loaded as a module as record.py loads it, prints in `repo`."""
        prelude = (f"import importlib.util; spec = importlib.util.spec_from_file_location('profile', {str(ROOT / 'scripts/profile.py')!r}); "
                   f"profile = importlib.util.module_from_spec(spec); spec.loader.exec_module(profile); from pathlib import Path; ROOT = Path({str(ROOT)!r}); ")
        p = subprocess.run([sys.executable, "-c", prelude + code], cwd=repo, capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_the_scripts_read_the_standards_values(self):
        repo = self.member({"standards/profile.yaml": self.OWN})
        self.assertEqual(self.module(repo, "print(profile.defaults(ROOT)['jira']['pr_statuses'])"), "['Under Development']\n")
        self.assertEqual(self.module(repo, "print(profile.resolve('someone/member', ROOT)['tests']['command'])"), "pytest -q\n")
        repo = checkout(str(self.parent / "pointing"), "git@github.com:someone/member.git", self.POINTER)
        self.fetch(repo)
        self.assertIn("drafted by the family's bot", self.module(repo, "print(profile.defaults(ROOT)['attribution']['phrases'])"))

    def test_a_hook_never_fetches(self):
        repo = self.member(self.POINTER)
        shutil.rmtree(repo / ".git/lasp-dev/standard")
        (repo / ".review").mkdir()
        p = subprocess.run(["bash", str(ROOT / "hooks/where.sh")], input=json.dumps({"cwd": str(repo), "session_id": "s"}),
                           cwd=repo, capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("has not been fetched in this clone", p.stdout + p.stderr)
        self.assertFalse((repo / ".git/lasp-dev/standard").exists())

    def test_a_default_branch_whose_newest_change_removed_the_standard_is_refused(self):
        repo = self.member(self.POINTER)
        git = ["git", "-C", str(self.family), "-c", "user.name=t", "-c", "user.email=t@example.org"]
        subprocess.run([*git, "rm", "-rq", "standards"], check=True)
        subprocess.run([*git, "commit", "-qm", "no standard"], check=True)
        p = subprocess.run(["bash", str(ROOT / "scripts/standard.sh")], cwd=repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("fam/shared has no standards/ on its default branch", p.stderr)

    def test_offline_only_when_set_to_1(self):
        repo = self.member(self.POINTER)
        shutil.rmtree(repo / ".git/lasp-dev/standard")
        self.assertEqual(self.ask(repo, "someone/member", "--field", "posted_text", env={**self.env, profile.OFFLINE: "true"}), (0, "workflow\n", ""))

    # Two profiles/ files differing only in case are refused too; macOS's default filesystem
    # cannot hold both, so that refusal has no test here.

    def test_a_local_checkout_that_is_not_absolute_or_has_no_standard_is_refused(self):
        repo = self.member(self.POINTER)
        (self.parent / "empty").mkdir()
        for value, says in (("trial", "not an absolute path"), (str(self.parent / "empty"), "has no standards/")):
            subprocess.run(["git", "-C", str(repo), "config", "lasp-dev.standard", value], check=True)
            self.assertIn(says, self.refusal(repo))

    def test_a_replaced_commits_files_stay_ten_minutes_after_it_is_replaced(self):
        repo = self.member(self.POINTER)
        base = repo / ".git/lasp-dev/standard/fam__shared"
        (old,) = list(base.iterdir())
        hour_ago = time.time() - 3600
        os.utime(old, (hour_ago, hour_ago))
        self.publish(self.PROJECT.replace("posted_text: workflow", "posted_text: plain"))
        self.fetch(repo)
        self.assertEqual(len(list(base.iterdir())), 2, "the replaced commit's files are kept for a read already on them")
        os.utime(old, (hour_ago, hour_ago))
        self.fetch(repo)
        self.assertEqual([d.name for d in base.iterdir()], [subprocess.run(["git", "-C", str(self.family), "log", "-1", "--format=%H"],
                                                                         capture_output=True, text=True).stdout.strip()])

    def test_redaction_refuses_a_standard_not_read(self):
        repo = self.member(self.POINTER)
        subprocess.run(["git", "-C", str(repo), "config", "lasp-dev.standard", "none"], check=True)
        p = subprocess.run([sys.executable, str(ROOT / "scripts/transcript_excerpt.py"), "--stdin"], input="x\n", cwd=repo,
                           capture_output=True, text=True, env=self.env)
        self.assertEqual((p.returncode, p.stdout), (1, ""))
        self.assertIn("internal links cannot be redacted: fam/shared's standard, not read", p.stderr)

    def test_its_own_standard_for_several_refuses_a_setting_in_the_wrong_file(self):
        repo = self.member({"standards/profile.yaml": self.PROJECT + self.MEMBER, "standards/profiles/member.yaml": "public: false\n"})
        self.assertIn("standards/profile.yaml sets tests, which a repository sets", self.refusal(repo))

    def test_once_keeps_an_error_as_it_keeps_a_value(self):
        calls = []

        def flaky(root):
            calls.append(root)
            if len(calls) == 1:
                raise profile.ProfileError("the first read failed")
            return "read"

        ask = profile.once(flaky)
        for _ in range(2):
            with self.assertRaisesRegex(profile.ProfileError, "the first read failed"):
                ask(Path("/a"))
        self.assertEqual(ask(Path("/b")), "read")
        self.assertEqual(calls, [Path("/a"), Path("/b")])


if __name__ == "__main__":
    unittest.main()
