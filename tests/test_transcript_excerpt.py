"""Tests for scripts/transcript_excerpt.py. Run with `python3 -m unittest discover -s tests`."""

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
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "feedback-transcript.jsonl"
DEFAULT = (ROOT / "standards" / "default-profile.yaml").read_text()

# The module reads the internal domains once, at import, from the working directory's standard: a
# checkout whose standard names `internal.example`.
_HERE = Path(tempfile.mkdtemp())
subprocess.run(["git", "init", "-q", str(_HERE)], check=True)
subprocess.run(["git", "-C", str(_HERE), "remote", "add", "origin", "git@github.com:someone/thing.git"], check=True)
(_HERE / "standards").mkdir()
(_HERE / "standards/profile.yaml").write_text("internal:\n  domains: [internal.example]\n  private_repositories: []\n")
_cwd = os.getcwd()
os.chdir(_HERE)
try:
    _spec = importlib.util.spec_from_file_location("transcript_excerpt", ROOT / "scripts" / "transcript_excerpt.py")
    excerpt = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(excerpt)
finally:
    os.chdir(_cwd)
    shutil.rmtree(_HERE)


def write_transcript(directory, *entries):
    path = Path(directory) / "t.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return path


def person(text):
    return {"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": text}}


def claude(*blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def ask(questions):
    return {"type": "tool_use", "id": "q", "name": "AskUserQuestion", "input": {"questions": questions}}


def answer(result):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q", "content": "x"}]},
            "toolUseResult": result}


def run(*argv, env=None):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, env or {}, clear=False), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = excerpt.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Turns(unittest.TestCase):
    def test_last_turns_are_kept(self):
        code, out, err = run("--file", str(FIXTURE), "--turns", "2")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("--- Turn"), 2)
        self.assertIn("Person: ! make check", out)
        self.assertIn("Person: /lasp-dev:skill-feedback ticket-draft: too long", out)
        self.assertNotIn("Third question", out)
        self.assertIn("turns: 2 of 2 requested", err)

    def test_fewer_turns_than_asked_prints_all(self):
        code, out, err = run("--file", str(FIXTURE))
        self.assertEqual(code, 0)
        self.assertEqual(out.count("--- Turn"), 6)
        self.assertIn("turns: 6 of 10 requested", err)
        self.assertNotIn("Before any message", out)

    def test_queued_message_starts_a_turn(self):
        out = run("--file", str(FIXTURE))[1]
        self.assertIn("--- Turn 3 ---\n\nPerson: Typed while Claude worked.\n\nClaude: Noted.", out)

    def test_before_skill_ends_before_the_turn_that_started_it(self):
        code, out, _ = run("--file", str(FIXTURE), "--turns", "2", "--before-skill", "skill-feedback")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("--- Turn"), 2)
        self.assertIn("Third question.", out)
        self.assertIn("! make check", out)
        self.assertNotIn("feedback", out)

    def test_before_skill_matches_a_skill_tool_call(self):
        out = run("--file", str(FIXTURE), "--before-skill", "lasp-dev:commit")[1]
        self.assertEqual(out.count("--- Turn"), 1)
        self.assertIn("First question", out)

    def test_before_skill_matches_feedback_started_by_the_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(
                tmp,
                person("Draft the ticket."),
                claude({"type": "text", "text": "Drafted."}),
                person("That ticket is too long; file feedback."),
                claude({"type": "tool_use", "id": "s", "name": "Skill", "input": {"skill": "lasp-dev:skill-feedback"}}),
                {"type": "user", "isMeta": True, "message": {"role": "user", "content": [{"type": "text", "text": "SKILL-BODY"}]}},
            )
            code, out, _ = run("--file", str(path), "--before-skill", "skill-feedback")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("--- Turn"), 1)
        self.assertIn("Person: Draft the ticket.", out)
        self.assertNotIn("too long", out)

    def test_fixture_writes_typed_commands_as_claude_code_does(self):
        commands = [json.loads(line) for line in FIXTURE.read_text().splitlines() if "<command-name>" in line]
        self.assertEqual(len(commands), 2)
        for entry in commands:
            self.assertNotIn("origin", entry)
            self.assertNotIn("isMeta", entry)


class Rendering(unittest.TestCase):
    def setUp(self):
        self.out = run("--file", str(FIXTURE))[1]

    def test_tool_calls_render_as_names_only(self):
        self.assertIn("Tools: Bash x2, Read", self.out)
        self.assertIn("Tools: Agent (pr-reader), Skill (lasp-dev:commit)", self.out)

    def test_slash_command_renders_as_typed(self):
        self.assertIn("Person: /lasp-dev:work PROJ-1", self.out)

    def test_shell_command_renders_as_typed_and_its_output_is_dropped(self):
        self.assertIn("--- Turn 5 ---\n\nPerson: ! make check\n\n--- Turn 6 ---", self.out)

    def test_ask_user_question_keeps_the_questions_and_answers(self):
        self.assertIn(
            "Claude asked:\n1. Which way?\n2. Push now?\n\nPerson answered:\n"
            "1. The short way (Recommended) (note: see <internal link>)\n"
            "2. Only after the token=<redacted> check",
            self.out,
        )

    def test_declined_question_says_so(self):
        self.assertIn("Claude asked: Proceed?\n\nPerson answered: none; the question was declined", self.out)

    def test_question_that_failed_to_show_is_not_called_declined(self):
        self.assertEqual(
            excerpt.answers_of(["Proceed?"], "Error: No such tool available: AskUserQuestion"),
            "none; the question was not shown (a tool error)",
        )
        self.assertEqual(
            excerpt.answers_of(["Proceed?"], "Error: The user doesn't want to proceed with this tool use."),
            "none; the question was declined",
        )

    def test_excerpt_is_one_fenced_text_block(self):
        self.assertTrue(self.out.startswith("```text\n--- Turn 1 ---\n"))
        self.assertTrue(self.out.endswith("\n```\n"))
        self.assertEqual(self.out.count("```"), 2)

    def test_fence_outruns_backticks_in_the_excerpt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, person("Show me."), claude({"type": "text", "text": "````md\n@someone #87\n````"}))
            out = run("--file", str(path))[1]
        self.assertTrue(out.startswith("`````text\n"))
        self.assertTrue(out.endswith("\n`````\n"))

    def test_everything_but_person_and_claude_text_is_dropped(self):
        for body in (
            "TOOL-INPUT-BODY", "TOOL-RESULT-BODY", "THINKING-BODY", "ATTACHMENT-BODY", "HOOK-BODY",
            "SKILL-BODY", "AGENT-PROMPT-BODY", "PEER-BODY", "TASK-BODY", "SIDECHAIN-BODY",
            "REMINDER-BODY", "QUESTION-BODY", "command-message", "OPTION-BODY", "ANSWER-RESULT-BODY",
            "DECLINE-RESULT-BODY", "BASH-STDOUT-BODY", "BASH-STDERR-BODY", "bash-input",
        ):
            with self.subTest(body=body):
                self.assertNotIn(body, self.out)


class Redaction(unittest.TestCase):
    # Built at run time so no secret scanner reads a token-shaped literal in this file.
    CASES = (
        ("github-token", "push with " + "gh" + "p_" + "A1b2" * 9 + " now", "A1b2A1b2"),
        ("github-token", "pat " + "github" + "_pat_" + "11AB" * 8 + "_xyz", "11AB11AB"),
        ("atlassian-token", "key " + "ATA" + "TT" + "3xFfGF0" * 4, "3xFfGF0"),
        ("aws-key", "id " + "AK" + "IA" + "IOSFODNN7EXAMPLE", "IOSFODNN7EXAMPLE"),
        ("aws-key", "id " + "AS" + "IA" + "IOSFODNN7EXAMPLE", "IOSFODNN7EXAMPLE"),
        ("slack-token", "hook " + "xo" + "xb-" + "1234-5678-abcdef", "1234-5678-abcdef"),
        ("gitlab-token", "token " + "gl" + "pat-" + "x1Y2" * 5, "x1Y2x1Y2"),
        ("bearer", "Authorization: Bearer abc.def-ghi_jkl", "abc.def-ghi_jkl"),
        ("basic-auth", "Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpw"),
        ("url-credentials", "git push https://user:hunter22@github.com/example-org/x.git", "hunter22"),
        ("curl-user", "curl -u user:hunter22 https://example.org/api", "hunter22"),  # gitleaks:allow
        ("private-key", "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", "MIIEow"),  # gitleaks:allow
        ("assignment", "password=hunter22", "hunter22"),
        ("assignment", 'export API_TOKEN="s3cr3tvalue"', "s3cr3tvalue"),
        ("assignment", "client_secret: shhh-value", "shhh-value"),
        ("assignment", 'password: "correct horse battery staple"', "horse"),
        ("internal-link", "see https://jira.internal.example/browse/PROJ-1 here", "jira.internal"),
        ("internal-link", "the board at internal.example/tracker/browse/PROJ-2", "tracker"),
        ("internal-link", "page wiki.internal.example/display/SPACE", "wiki"),
        ("internal-link", "git clone " + "git" + "@gitlab.internal.example:team/tool.git", "tool"),
        ("internal-link", "! ssh someone@proc1.internal.example", "proc1"),
        ("internal-link", "scp f.nc user@web.internal.example:/data/in", "/data"),
        ("internal-link", "write to someone@internal.example", "example"),
        ("home", "opened /home/someone/repo/file.py", "/home/someone"),
        ("home", "opened /HOME/Someone/repo/file.py", "Someone"),
        ("home", "in ~/.claude/projects/-home-someone-repos-x/a.jsonl", "someone"),
        ("home", "scratch at /private/tmp/claude-1/-Home-Someone-repos-x/scratch", "Someone"),
        ("assignment", "**Password:** hunter22", "hunter22"),
        ("assignment", "*Secret*: abc123def", "abc123def"),
        ("assignment", "- **GH_TOKEN**: ghx_abc123def456", "abc123def456"),
        ("assignment", "**Password:** 'correct horse battery staple'", "horse"),
        ("assignment", "the token: abc123def", "abc123def"),
        ("assignment", "PRIVATE_KEY=MIIEowIBAAKCAQEA", "MIIEow"),
        ("assignment", "PASSPHRASE=open-sesame-1", "sesame"),
        ("assignment", "DefaultEndpointsProtocol=https;AccountKey=Zm9vYmFy+abc==;", "Zm9vYmFy"),  # gitleaks:allow
        ("assignment", "ACCOUNTKEY=Zm9vYmFy", "Zm9vYmFy"),
        ("assignment", "CLIENT_SECRET=s3cr3t-value", "s3cr3t"),
        ("assignment", "ACCESS_KEY=wJalrXUtnFEMI", "wJalrXUtnFEMI"),
        ("private-key", "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk\nand the rest", "b3BlbnNzaC1rZXk"),  # gitleaks:allow
        ("private-key", "-----BEGIN PGP PRIVATE KEY BLOCK-----\nlQOYBF\n-----END PGP PRIVATE KEY BLOCK-----", "lQOYBF"),  # gitleaks:allow
        ("anthropic-key", "key " + "sk-" + "ant-api03-" + "Ab1_" * 10, "Ab1_Ab1_"),
        ("openai-key", "key " + "sk-" + "proj-" + "Ab1x" * 10, "Ab1xAb1x"),
        ("openai-key", "key " + "sk-" + "Ab1x" * 10, "Ab1xAb1x"),
        ("jwt", "token " + "eyJ" + "hbGciOiJIUzI1NiJ9." + "eyJ" + "zdWIiOiIxIn0.c2lnbmF0dXJl", "c2lnbmF0dXJl"),
        ("google-key", "key " + "AI" + "za" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q", "SyA1b2C3"),
        ("npm-token", "npm " + "npm" + "_" + "a1B2" * 9, "a1B2a1B2"),
        ("pypi-token", "pypi " + "pypi" + "-" + "AgEIcHlwaS5vcmc" * 4, "AgEIcHlwaS5vcmc"),
        ("huggingface-token", "hf " + "hf" + "_" + "aB3d" * 9, "aB3daB3d"),
        ("stripe-key", "stripe " + "sk" + "_live_" + "4eC3" * 6, "4eC34eC3"),
        ("stripe-key", "stripe " + "rk" + "_live_" + "4eC3" * 6, "4eC34eC3"),
        ("slack-webhook", "post to https://hooks.slack.com/services/" + "T000/B000/XXXXsecretXXXX", "XXXXsecretXXXX"),
        ("password-flag", "app --password hunter22 --verbose", "hunter22"),
        ("password-flag", "app --password=hunter22", "hunter22"),
        ("password-flag", "mysql -u root -phunter22 db", "hunter22"),
        ("password-flag", "sshpass -p hunter22 ssh host", "hunter22"),
        ("auth-header", "Authorization: token " + "0123abcd" * 5, "0123abcd"),
        ("auth-header", "-H 'Authorization: Token 9f8e7d6c5b4a'", "9f8e7d6c5b4a"),  # gitleaks:allow
        ("auth-header", '{"Authorization": "token 9f8e7d6c5b4a"}', "9f8e7d6c5b4a"),
        ("auth-header", "-H 'Cookie: session=abc123; csrftoken=def456'", "def456"),
        ("url-credentials", "postgres://user:p@ss@db.example.org/x", "ss@db"),
        ("url-credentials", "redis://:hunter22@host:6379", "hunter22"),
        ("assignment", "- `DB_PASSWORD`: hunter22", "hunter22"),
        ("assignment", "- `GITHUB_TOKEN`: `abc123def456`", "abc123def456"),
        ("assignment", "DB_PASS=hunter22", "hunter22"),
        ("assignment", "pwd=hunter22", "hunter22"),
        ("assignment", "PGPASS=hunter22", "hunter22"),
        ("assignment", "db-pwd: hunter22", "hunter22"),
        ("assignment", "password=b'correct horse'", "horse"),
        ("assignment", 'token=rb"correct horse"', "horse"),
        ("slack-webhook", "post to https://hooks.slack.com/workflows/" + "T000/A000/123/abcSecret", "abcSecret"),
        ("slack-webhook", "post to https://hooks.slack.com/triggers/" + "T000/A000/123/abcSecret", "abcSecret"),
        ("auth-header", "  - Cookie: session=abc123secret", "abc123secret"),
        ("auth-header", "curl --header Authorization:abc123secret https://example.org", "abc123secret"),
        ("private-key", "`-----BEGIN OPENSSH PRIVATE KEY-----` b3BlbnNzaC1rZXk\nThe next step.", "b3BlbnNzaC1rZXk"),  # gitleaks:allow
    )

    def redact(self, text):
        counts = dict.fromkeys([kind for kind, _, _ in excerpt.REDACTIONS] + ["home"], 0)
        return excerpt.redact(text, counts, "/home/someone"), counts

    def test_each_kind_is_removed_and_counted(self):
        for kind, text, secret in self.CASES:
            with self.subTest(kind=kind, text=text):
                out, counts = self.redact(text)
                self.assertNotIn(secret, out)
                self.assertEqual(counts[kind], 1)
                self.assertEqual(sum(counts.values()), 1, counts)

    def test_replacements(self):
        self.assertEqual(self.redact("password=hunter22")[0], "password=<redacted>")
        self.assertEqual(self.redact("Bearer abcdefghij")[0], "Bearer <redacted>")
        self.assertEqual(self.redact("at https://jira.internal.example/x.")[0], "at <internal link>.")
        self.assertEqual(self.redact("in /home/someone/repo")[0], "in ~/repo")
        self.assertEqual(self.redact('password: "correct horse battery staple" ok')[0], "password: <redacted> ok")
        self.assertEqual(self.redact("git" + "@gitlab.internal.example:team/tool.git")[0], "git" + "@<internal link>")
        self.assertEqual(self.redact("https://user:hunter22@github.com/x")[0], "https://<redacted>@github.com/x")
        self.assertEqual(self.redact("curl -u user:hunter22 https://example.org")[0], "curl -u <redacted> https://example.org")  # gitleaks:allow
        self.assertEqual(self.redact("**Password:** hunter22")[0], "**Password:** <redacted>")
        self.assertEqual(self.redact("postgres://user:p@ss@db.example.org/x")[0], "postgres://<redacted>@db.example.org/x")
        self.assertEqual(self.redact("in /private/tmp/c/-home-someone-repos-x/s")[0], "in /private/tmp/c/-~-repos-x/s")
        self.assertEqual(self.redact("-----BEGIN RSA PRIVATE KEY-----\nMIIE\nmore")[0], "<redacted>")  # gitleaks:allow
        self.assertEqual(self.redact("-H 'Authorization: token abc123def'")[0], "-H 'Authorization: token <redacted>'")
        self.assertEqual(self.redact("POST https://hooks.slack.com/services/T0/B0/xyz")[0], "POST https://hooks.slack.com/services/<redacted>")
        self.assertEqual(self.redact("- `DB_PASSWORD`: hunter22")[0], "- `DB_PASSWORD`: <redacted>")
        self.assertEqual(self.redact("redis://:hunter22@host:6379")[0], "redis://<redacted>@host:6379")
        self.assertEqual(self.redact("password=b'correct horse' ok")[0], "password=<redacted> ok")
        self.assertEqual(self.redact("  - Cookie: session=abc123")[0], "  - Cookie: <redacted>")

    def test_private_key_with_no_end_takes_only_the_key_lines(self):
        self.assertEqual(
            self.redact("`-----BEGIN OPENSSH PRIVATE KEY-----` is the first line of a key.\nThe next step is to run the tests.")[0],  # gitleaks:allow
            "`<redacted>\nThe next step is to run the tests.",
        )
        self.assertEqual(
            self.redact("-----BEGIN RSA PRIVATE KEY-----\nProc-Type: 4,ENCRYPTED\n\nMIIEow\nb3Bl==\n\nThe key ends there.")[0],  # gitleaks:allow
            "<redacted>\n\nThe key ends there.",
        )

    def test_dashed_home_replaces_underscores_too(self):
        counts = dict.fromkeys([kind for kind, _, _ in excerpt.REDACTIONS] + ["home"], 0)
        out = excerpt.redact("projects/-Users-some-one-repos-x", counts, "/Users/some_one")
        self.assertEqual(out, "projects/-~-repos-x")
        self.assertEqual(counts["home"], 1)

    def test_dashed_home_replaces_every_character_but_letters_and_digits(self):
        counts = dict.fromkeys([kind for kind, _, _ in excerpt.REDACTIONS] + ["home"], 0)
        out = excerpt.redact("projects/-home-john-corp-com-repo", counts, "/home/john@corp.com")
        self.assertEqual(out, "projects/-~-repo")
        self.assertEqual(counts["home"], 1)

    def test_dashed_home_starts_at_a_name_boundary(self):
        for text in ("pip install --root /opt/x", "cert-root-ca", "my-root"):
            with self.subTest(text=text):
                counts = dict.fromkeys([kind for kind, _, _ in excerpt.REDACTIONS] + ["home"], 0)
                self.assertEqual(excerpt.redact(text, counts, "/root"), text)
                self.assertEqual(counts["home"], 0)

    def test_long_run_of_word_characters_redacts_quickly(self):
        line = ("A1b2_C3d4-" * 20000) + " password=hunter22"
        start = time.perf_counter()
        out, counts = self.redact(line)
        self.assertLess(time.perf_counter() - start, 2)
        self.assertTrue(out.endswith(" password=<redacted>"))
        self.assertEqual(counts["assignment"], 1)

    def test_token_in_an_assignment_counts_once(self):
        out, counts = self.redact("token=" + "gh" + "o_" + "x" * 30)
        self.assertEqual(out, "token=<redacted>")
        self.assertEqual(counts["github-token"], 1)
        self.assertEqual(counts["assignment"], 0)

    def test_what_is_left_alone(self):
        for text in (
            "/home/someoneelse/repo",
            "Basic functionality of the tool",
            "the host: it failed",
            "about 3,900 tokens of descriptions",
            "https://github.com/example-org/widgets",
            "max_tokens: 4096",
            "set MAX_TOKENS=4096 and input_tokens: 120",
            "-home-someoneelse-repos",
            "mysql -u root -p mydb",
            "docker login --password-stdin",
            "psql -h db -p 5432",
            "Authorization: Bearer <redacted>",
            "The Authorization: header was missing on the retry path; see client.py:88",
            "I checked the Cookie: header handling in auth.py. Fix: use time.monotonic.",
            "**Authorization:** required for every call",
            "the bypass: on, the compass: north, pass_file: x",
        ):
            with self.subTest(text=text):
                out, counts = self.redact(text)
                self.assertEqual(out, text)
                self.assertEqual(sum(counts.values()), 0)

    def test_counts_reach_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text('{"type": "user", "origin": {"kind": "human"}, "message": {"content": "password=hunter22"}}\n')
            code, out, err = run("--file", str(path))
        self.assertEqual(code, 0)
        self.assertIn("password=<redacted>", out)
        self.assertIn("assignment 1", err)
        self.assertIn("github-token 0", err)


class MaxChars(unittest.TestCase):
    def test_characters_reach_stderr(self):
        code, out, err = run("--file", str(FIXTURE))
        self.assertEqual(code, 0)
        self.assertIn(f"characters: {len(out)}", err)

    def test_oldest_turns_are_dropped_to_fit(self):
        full = run("--file", str(FIXTURE))[1]
        last_two = run("--file", str(FIXTURE), "--turns", "2")[1]
        last_three = run("--file", str(FIXTURE), "--turns", "3")[1]
        limit = len(last_three) - 1
        code, out, err = run("--file", str(FIXTURE), "--max-chars", str(limit))
        self.assertEqual(code, 0)
        self.assertLess(len(last_two), limit)
        self.assertLess(limit, len(full))
        self.assertEqual(out, last_two)
        self.assertIn("turns: 2 of 10 requested, 4 oldest dropped to fit --max-chars", err)
        self.assertIn(f"characters: {len(out)}", err)

    def test_a_fitting_excerpt_drops_nothing(self):
        full = run("--file", str(FIXTURE))[1]
        code, out, err = run("--file", str(FIXTURE), "--max-chars", str(len(full)))
        self.assertEqual(code, 0)
        self.assertEqual(out, full)
        self.assertIn("turns: 6 of 10 requested\n", err)

    def test_redactions_count_only_the_kept_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, person("password=hunter22 " + "x" * 200), person("Short."))
            code, out, err = run("--file", str(path), "--max-chars", "100")
        self.assertEqual(code, 0)
        self.assertNotIn("hunter22", out)
        self.assertIn("assignment 0", err)


class Stdin(unittest.TestCase):
    def test_redacts_the_text_on_stdin(self):
        text = "It failed at https://jira.internal.example/browse/PROJ-3 with password=hunter22.\nThe rest stays."
        with mock.patch("sys.stdin", io.StringIO(text)):
            code, out, err = run("--stdin")
        self.assertEqual(code, 0)
        self.assertEqual(out, "It failed at <internal link> with password=<redacted>.\nThe rest stays.")
        self.assertIn("internal-link 1", err)
        self.assertIn("assignment 1", err)
        self.assertNotIn("turns:", err)

    def test_stdin_takes_no_transcript(self):
        with mock.patch("sys.stdin", io.StringIO("x")), self.assertRaises(SystemExit) as raised:
            run("--stdin", "--file", str(FIXTURE))
        self.assertEqual(raised.exception.code, 2)

    def test_stdin_takes_no_max_chars(self):
        err = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO("x")), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as raised:
            excerpt.main(["--stdin", "--max-chars", "100"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("takes no --file, --before-skill or --max-chars", err.getvalue())


class Failures(unittest.TestCase):
    def setUp(self):
        self.config = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.config)

    def place(self, project, session="sess-1"):
        path = self.config / "projects" / project / f"{session}.jsonl"
        path.parent.mkdir(parents=True)
        shutil.copy(FIXTURE, path)
        return path

    def env(self, session="sess-1"):
        return {"CLAUDE_CONFIG_DIR": str(self.config), "CLAUDE_CODE_SESSION_ID": session}

    def test_finds_the_session_by_id(self):
        self.place("-repo")
        code, out, _ = run("--turns", "1", env=self.env())
        self.assertEqual(code, 0)
        self.assertIn("/lasp-dev:skill-feedback", out)

    def test_no_transcript_for_the_session(self):
        self.place("-repo", session="other")
        code, out, err = run(env=self.env())
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("no transcript for session sess-1", err)

    def test_two_transcripts_for_the_session(self):
        self.place("-repo-a")
        self.place("-repo-b")
        code, out, err = run(env=self.env())
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("2 transcripts for session sess-1", err)
        self.assertIn("--file", err)

    def test_no_session_id(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config)}):
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            code, _, err = run()
        self.assertEqual(code, 1)
        self.assertIn("CLAUDE_CODE_SESSION_ID is not set", err)

    def test_file_that_cannot_be_read(self):
        code, out, err = run("--file", str(self.config / "missing.jsonl"))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("cannot read", err)

    def test_questions_that_are_not_a_list(self):
        path = write_transcript(self.config, person("Go."), claude(ask("Which?")))
        code, out, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("questions are not a list of questions: a string that is not JSON", err)

    def test_questions_as_a_json_string(self):
        questions = json.dumps([{"question": "Which?"}])
        path = write_transcript(self.config, person("Go."), claude(ask(questions)), answer({"answers": {"Which?": "Yes"}}))
        code, out, _ = run("--file", str(path))
        self.assertEqual(code, 0)
        self.assertIn("Claude asked: Which?\n\nPerson answered: Yes", out)

    def test_questions_as_a_json_string_that_is_not_a_list(self):
        path = write_transcript(self.config, person("Go."), claude(ask(json.dumps({"question": "Which?"}))))
        code, out, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("questions are not a list", err)

    def test_result_record_without_answers(self):
        path = write_transcript(self.config, person("Go."), claude(ask([{"question": "Which?"}])), answer({"questions": []}))
        code, out, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("has no answers record", err)

    def test_answers_keyed_another_way(self):
        path = write_transcript(self.config, person("Go."), claude(ask([{"question": "Which?"}])), answer({"answers": {"0": "Yes"}}))
        code, out, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("no answer for the question 'Which?'", err)

    def test_annotations_that_are_not_a_record(self):
        result = {"answers": {"Which?": "Yes"}, "annotations": [{"notes": "x"}]}
        path = write_transcript(self.config, person("Go."), claude(ask([{"question": "Which?"}])), answer(result))
        code, out, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("annotations are not a record: list", err)

    def test_line_that_is_not_an_object(self):
        path = self.place("-repo")
        path.write_text(path.read_text() + "[1, 2]\n")
        code, out, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn(":33 is not a JSON object", err)

    def test_file_that_is_not_utf8(self):
        path = self.config / "latin1.jsonl"
        path.write_bytes(b'{"type": "user", "origin": {"kind": "human"}, "message": {"content": "\xff"}}\n')
        code, out, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("is not UTF-8", err)

    def test_newest_turn_over_max_chars(self):
        code, out, err = run("--file", str(FIXTURE), "--max-chars", "20")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("the newest turn alone is", err)
        self.assertIn("over --max-chars 20", err)

    def test_line_that_is_not_json(self):
        path = self.place("-repo")
        path.write_text(path.read_text() + "{not json\n")
        code, _, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertIn("is not JSON", err)

    def test_a_line_separator_inside_a_string_is_not_a_line_break(self):
        # JSON leaves U+2028 and U+0085 raw in a string, as in a binary file a tool read.
        path = self.config / "separators.jsonl"
        path.write_text(json.dumps(person("before\u2028after\x85end"), ensure_ascii=False) + "\n", encoding="utf-8")
        self.assertEqual(excerpt.read_entries(path)[0]["message"]["content"], "before\u2028after\x85end")

    def test_no_message_from_the_person(self):
        path = self.config / "empty.jsonl"
        path.write_text('{"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}\n')
        code, _, err = run("--file", str(path))
        self.assertEqual(code, 1)
        self.assertIn("no message from the person", err)

    def test_turns_below_one(self):
        code, _, err = run("--file", str(FIXTURE), "--turns", "0")
        self.assertEqual(code, 1)
        self.assertIn("--turns must be 1 or more", err)

    def test_skill_never_started(self):
        code, _, err = run("--file", str(FIXTURE), "--before-skill", "pr-review")
        self.assertEqual(code, 1)
        self.assertIn("never started skill 'pr-review'", err)


class InternalDomains(unittest.TestCase):
    """The internal domains are the default profile's and the working directory's standard's
    together, and without one that can be read nothing is printed."""

    def run_copy(self, text: str, default: str | None = DEFAULT, cwd: Path | None = None) -> tuple[int, str, str]:
        plugin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plugin)
        (plugin / "scripts").mkdir()
        for name in ("transcript_excerpt.py", "profile.py", "standard.sh"):
            shutil.copy(ROOT / "scripts" / name, plugin / "scripts")
        if default is not None:
            (plugin / "standards").mkdir()
            (plugin / "standards/default-profile.yaml").write_text(default)
        p = subprocess.run([sys.executable, str(plugin / "scripts/transcript_excerpt.py"), "--stdin"], input=text, capture_output=True, text=True,
                           cwd=cwd or plugin)
        return p.returncode, p.stdout, p.stderr

    def own_checkout(self, profile: str) -> Path:
        """A checkout whose own standards/profile.yaml is `profile`."""
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:someone/thing.git"], check=True)
        (repo / "standards").mkdir()
        (repo / "standards/profile.yaml").write_text(profile)
        return repo

    def domains(self, listed: str) -> Path:
        return self.own_checkout(f"internal:\n  domains: {listed}\n  private_repositories: []\n")

    def test_each_domain_of_the_standard_is_redacted(self):
        repo = self.domains("[internal.example, intra.example.org]")
        rc, out, _ = self.run_copy("see https://wiki.intra.example.org/x and jira.internal.example/y, not example.org\n", cwd=repo)
        self.assertEqual((rc, out), (0, "see <internal link> and <internal link>, not example.org\n"))

    def test_a_standard_with_no_domains_redacts_no_link(self):
        rc, out, err = self.run_copy("see jira.internal.example/y\n", cwd=self.domains("[]"))
        self.assertEqual((rc, out), (0, "see jira.internal.example/y\n"))
        self.assertIn("internal-link 0", err)

    def test_a_domain_that_ends_another_does_not_leak_its_path(self):
        rc, out, _ = self.run_copy("see https://wiki.corp.com.au/secret/path and corp.com/x\n", cwd=self.domains("[corp.com, corp.com.au]"))
        self.assertEqual((rc, out), (0, "see <internal link> and <internal link>\n"))

    def test_unrecorded_domains_print_nothing(self):
        rc, out, err = self.run_copy("see https://jira.internal.example/x\n", cwd=self.domains("not yet recorded"))
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("internal links cannot be redacted", err)

    def test_the_default_profiles_domains_are_redacted_beside_the_standards(self):
        default = DEFAULT.replace("  domains: []", "  domains: [internal.example]")
        rc, out, _ = self.run_copy("see https://jira.internal.example/x\n", default)
        self.assertEqual((rc, out), (0, "see <internal link>\n"))
        rc, out, _ = self.run_copy("see https://jira.internal.example/x\n")
        self.assertEqual((rc, out), (0, "see https://jira.internal.example/x\n"))
        repo = self.domains("[intra.example.org]")
        rc, out, err = self.run_copy("see https://wiki.intra.example.org/x and jira.internal.example/y\n", default, repo)
        self.assertEqual((rc, out), (0, "see <internal link> and <internal link>\n"), err)

    def test_a_standard_not_read_prints_nothing(self):
        repo = self.own_checkout("standard: someone/std\n")
        subprocess.run(["git", "-C", str(repo), "config", "lasp-dev.standard", "none"], check=True)
        rc, out, err = self.run_copy("see https://jira.internal.example/x\n", cwd=repo)
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("internal links cannot be redacted", err)

    def test_without_the_default_profile_nothing_is_printed(self):
        rc, out, err = self.run_copy("see https://jira.internal.example/x\n", None, self.domains("[internal.example]"))
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("internal links cannot be redacted", err)

if __name__ == "__main__":
    unittest.main()
