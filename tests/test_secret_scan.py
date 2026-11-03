"""Tests for scripts/secret_scan.py and hooks/secret-gate.sh. Run with `python3 -m unittest discover -s tests`.

Every credential below is assembled at run time from pieces, so this file holds none for the scan,
gitleaks or a push protection to find.
"""

import collections
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "hooks" / "secret-gate.sh"

_spec = importlib.util.spec_from_file_location("secret_scan", ROOT / "scripts" / "secret_scan.py")
secret_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(secret_scan)

A36 = "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC2eF4hJ6"
SECRETS = {
    "private key": "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
    "AWS access key ID": "AK" + "IA" + "Q3EGRCJ5ZT7N2WXK",
    "GitHub token": "gh" + "p_" + A36,
    "GitHub fine-grained token": "github" + "_pat_" + "11ABCDEFG0" + "x9Y8z7W6v5" * 7,
    "GitLab token": "gl" + "pat-" + "aB3dE5gH7jK9mN1pQ3sT",
    "Slack token": "xo" + "xb-" + "1234567890-abcdefghij",
    "Slack webhook": "https://hooks.slack.com/services/" + "T0123ABCD/B0123ABCD/" + "aB3dE5gH7jK9mN1pQ3sT",
    "Atlassian API token": "ATA" + "TT3" + "xFfGF0" + "aB3dE5gH7j" * 16,
    "Anthropic API key": "sk-" + "ant-" + "api03-" + "aB3dE5gH7j" * 5,
    "Google API key": "AI" + "za" + "SyD3dE5gH7jK9mN1pQ3sT5vW7yZ9bC2eF4h",
    "JSON web token": "ey" + "JhbGciOiJIUzI1NiJ9." + "ey" + "JzdWIiOiIxMjM0NTY3ODkwIn0." + "SflKxwRJSMeKKF2QT4fw",
    "token assignment": "JIRA_" + "PERSONAL_TOKEN=" + "Nz" + "QxMjM0NTY3ODkwOkFiY2RlZmdoaWpr",
    "AWS secret access key": "AWS_SECRET_" + "ACCESS_KEY = " + "wJalrXUtnFEMI/K7MDENG/bPxRfiCY1234567890",
    "bearer token": "Authorization: " + "Bearer " + "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC2eF4hJ6",
}
TOKEN = SECRETS["GitHub token"]

LOOK_ALIKES = [
    "the AWS docs use " + "AK" + "IA" + "IOSFODNN7EXAMPLE",
    "a branch named ghp_fix and a function gh" + "p_token_name",
    '"JIRA_' + 'PERSONAL_TOKEN": "${JIRA_TOKEN}"',
    "export JIRA_" + "TOKEN=<Jira token>",
    "JIRA_" + "API_TOKEN=your-token-goes-here-please",
    "Authorization: " + "Bearer ${GITHUB_MCP_TOKEN}",
    "-----BEGIN " + "PUBLIC KEY-----",
    "ey" + "J is how a JWT starts, eyJ.eyJ.sig is too short",
    "glpat-short",
    "an allowed fixture " + TOKEN + "  # gitleaks:allow",
]

# A scenario pack in a directory of its own under sandbox/ plants its own fakes, counted by that
# pack's own test; every other fake the repository plants carries `gitleaks:allow`.
PACKS = tuple(f"{d.relative_to(ROOT)}/" for d in sorted((ROOT / "sandbox").iterdir()) if (d / "scenarios.yaml").is_file())


def planted(paths):
    """(path, kind) for each credential the scan finds in these tracked files, counted."""
    return dict(collections.Counter(
        (p, f.rsplit(": ", 1)[1]) for p in paths if (ROOT / p).is_file() and not (ROOT / p).is_symlink()
        for f in secret_scan.scan_file(str(ROOT / p), p)))


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def run_gate(payload, env=None):
    r = subprocess.run(["bash", str(GATE)], input=payload, capture_output=True, text=True, check=True, env=env)
    return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None


def new_repo():
    repo = Path(tempfile.mkdtemp())
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "a.py").write_text("x = 1\n")
    (repo / "b.py").write_text("y = 1\n")
    git(repo, "add", "a.py", "b.py")
    git(repo, "commit", "-q", "-m", "one")
    return repo


class Patterns(unittest.TestCase):
    def test_each_form_is_found_by_its_kind(self):
        for kind, secret in SECRETS.items():
            with self.subTest(kind=kind):
                self.assertEqual(secret_scan.scan_text("x " + secret, "f"), [f"f:1: {kind}"])

    def test_look_alikes_are_not(self):
        for text in LOOK_ALIKES:
            with self.subTest(text=text):
                self.assertEqual(secret_scan.scan_text(text, "f"), [])

    def test_the_repository_holds_only_its_known_fakes(self):
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(planted(p for p in files if not p.startswith(PACKS)), {})

    def test_each_scenario_pack_has_a_test_counting_its_fakes(self):
        tests = [t.read_text() for t in (ROOT / "tests").glob("test_*.py") if t.name != "test_secret_scan.py"]
        for pack in PACKS:
            with self.subTest(pack=pack):
                self.assertTrue(any("planted(" in t and f'"{pack}"' in t for t in tests), pack)


class Diff(unittest.TestCase):
    def test_an_added_line_that_looks_like_a_header_is_content(self):
        diff = ("diff --git a/x.txt b/x.txt\n--- a/x.txt\n+++ b/x.txt\n@@ -0,0 +1,3 @@\n"
                "+++ header-looking line\n+++ /dev/null\n+" + TOKEN + "\n")
        self.assertEqual(secret_scan.scan_diff(diff), ["x.txt:3: GitHub token"])

    def test_a_deleted_file_adds_nothing(self):
        diff = "diff --git a/x b/x\ndeleted file mode 100644\n--- a/x\n+++ /dev/null\n@@ -1 +0,0 @@\n-" + TOKEN + "\n"
        self.assertEqual(secret_scan.scan_diff(diff), [])


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def cli(self, *args, cwd=None):
        return subprocess.run(["python3", str(ROOT / "scripts" / "secret_scan.py"), *args],
                              cwd=cwd, capture_output=True, text=True)

    def test_finding_names_line_and_kind_never_the_value(self):
        f = self.tmp / "a.txt"
        f.write_text("one\ntoken " + TOKEN + "\n")
        r = self.cli("files", str(f))
        self.assertEqual((r.returncode, r.stdout), (1, f"{f}:2: GitHub token\n"))
        self.assertNotIn(A36, r.stdout + r.stderr)

    def test_clean_file_exits_zero(self):
        f = self.tmp / "a.txt"
        f.write_text("nothing here\n")
        self.assertEqual(self.cli("files", str(f)).returncode, 0)

    def test_binary_file_is_skipped(self):
        f = self.tmp / "a.bin"
        f.write_bytes(b"\0" + TOKEN.encode())
        self.assertEqual(self.cli("files", str(f)).returncode, 0)

    def test_unreadable_file_exits_two(self):
        r = self.cli("files", str(self.tmp / "missing"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot read", r.stderr)

    def test_diff_outside_a_repository_exits_two_in_one_line(self):
        r = self.cli("diff", cwd=self.tmp)
        self.assertEqual(r.returncode, 2)
        self.assertIn("is not in a git repository", r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_unknown_mode_exits_two(self):
        self.assertEqual(self.cli("everything").returncode, 2)


class Commit(unittest.TestCase):
    def setUp(self):
        self.repo = new_repo()
        self.addCleanup(shutil.rmtree, self.repo)

    def bash(self, command, cwd=None):
        return run_gate(json.dumps({"tool_name": "Bash", "tool_input": {"command": command},
                                    "cwd": str(cwd or self.repo)}))

    def stage(self, text, name="a.py", repo=None):
        repo = repo or self.repo
        (repo / name).write_text(text)
        git(repo, "add", name)

    def assertDenied(self, out, *parts):
        self.assertEqual(out and out["permissionDecision"], "deny", out)
        for part in parts:
            self.assertIn(part, out["permissionDecisionReason"])
        self.assertNotIn(A36, out["permissionDecisionReason"])

    def test_clean_commit_passes(self):
        self.stage("x = 2\n")
        self.assertIsNone(self.bash("git commit -m two"))

    def test_staged_secret_is_denied_at_its_line(self):
        self.stage("x = 1\ntoken = '" + TOKEN + "'\n")
        self.assertDenied(self.bash("git commit -m two"), "a.py:2: GitHub token (staged)")

    def test_unstaged_change_counts_only_when_the_commit_takes_it(self):
        (self.repo / "a.py").write_text(SECRETS["private key"] + "\n")
        self.assertIsNone(self.bash("git commit -m two"))
        self.assertDenied(self.bash("git commit -am two"), "a.py:1: private key (working tree")
        self.assertDenied(self.bash("git commit -m two a.py"), "a.py:1")
        self.assertIsNone(self.bash("git commit -m two b.py"))

    def test_untracked_file_counts_only_when_an_add_names_it(self):
        (self.repo / "new.env").write_text(SECRETS["token assignment"] + "\n")
        (self.repo / "c.py").write_text("z = 1\n")
        self.assertIsNone(self.bash("git commit -m two"))
        self.assertIsNone(self.bash("git add c.py && git commit -m two"))
        for add in ("git add new.env", "git add -A", "git add .", "git add --all"):
            with self.subTest(add=add):
                self.assertDenied(self.bash(f"{add} && git commit -m two"), "new.env:1: token assignment (untracked")
        self.assertIsNone(self.bash("git add -u && git commit -m two"))

    def test_add_force_takes_an_ignored_file(self):
        (self.repo / ".gitignore").write_text(".env\n")
        (self.repo / ".env").write_text(SECRETS["token assignment"] + "\n")
        self.assertIsNone(self.bash("git add -A && git commit -m two"))
        self.assertDenied(self.bash("git add -f .env && git commit -m two"), ".env:1")

    def test_removed_line_is_not_a_finding(self):
        self.stage("t = '" + TOKEN + "'  # gitleaks:allow\n")
        git(self.repo, "commit", "-q", "-m", "two")
        self.stage("x = 1\n")
        self.assertIsNone(self.bash("git commit -m three"))

    def test_commands_that_do_not_commit_are_not_scanned(self):
        self.stage(TOKEN + "\n")
        for command in ("git status", "git log --grep commit", "git show HEAD -- commit.py",
                        "git checkout -b fix/commit-gate", "git commit --dry-run -m x", "echo commit"):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command))

    def test_the_message_is_scanned(self):
        self.assertDenied(self.bash(f"git commit --allow-empty -m 'add {TOKEN}'"), "command:1: GitHub token (command text)")
        self.assertDenied(self.bash(f"git commit --allow-empty -F - <<'MSG'\nsubject\n\n{TOKEN}\nMSG"), "command:4")
        (self.repo / "msg.txt").write_text("subject\n" + TOKEN + "\n")
        self.assertDenied(self.bash("git commit --allow-empty -F msg.txt"), "msg.txt:2: GitHub token (message file)")

    def test_a_file_the_command_writes_from_its_own_text_is_read_as_that_text(self):
        for command in ("M=$(mktemp) && cat > \"$M\" <<'EOF'\nsubject\nEOF\ngit commit --allow-empty -F \"$M\"",
                        "cat >\"${M}\" <<EOF\nsubject\nEOF\ngit commit --allow-empty -F \"$M\"",
                        "printf 'subject\\n' > $M; git commit --allow-empty -F $M",
                        "printf 'subject\\n' >| $M; git commit --allow-empty -F $M"):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command))
        self.assertDenied(self.bash(f"cat > \"$M\" <<'EOF'\n{TOKEN}\nEOF\ngit commit --allow-empty -F \"$M\""),
                          "(command text)")
        for command in ("cat > \"$M\" <<EOF\n$BODY\nEOF\ngit commit --allow-empty -F \"$M\"",
                        "cat notes.txt > $M; git commit --allow-empty -F $M",
                        "echo \"$BODY\" > $M; git commit --allow-empty -F $M",
                        "echo a > $M; cat notes.txt >> $M; git commit --allow-empty -F $M",
                        "git log -1 2> $M; git commit --allow-empty -F $M",
                        "cat > \"$M\" <<'EOF'\nx\nEOF\ngh auth token | tee -a \"$M\" && git commit --allow-empty -F \"$M\"",
                        "cat > \"$M\" <<'EOF' < notes.txt\nx\nEOF\ngit commit --allow-empty -F \"$M\"",
                        "echo \"<<\"; cat <<EOF > \"$M\"\n$BODY\nEOF\ngit commit --allow-empty -F \"$M\"",
                        "echo \">\"; cat notes.txt > $M; git commit --allow-empty -F $M",
                        "git commit --allow-empty -F \"$M\"; cat > \"$M\" <<'EOF'\nx\nEOF",
                        "M=a; cat > \"$M\" <<'EOF'\nx\nEOF\nM=notes.txt; git commit --allow-empty -F \"$M\""):
            with self.subTest(command=command):
                out = self.bash(command)
                self.assertEqual(out["permissionDecision"], "ask")
                self.assertIn("cannot tell which file", out["permissionDecisionReason"])

    def test_the_repository_is_the_one_the_command_names(self):
        other = new_repo()
        self.addCleanup(shutil.rmtree, other)
        self.stage(TOKEN + "\n", repo=other)
        for command in (f"git -C {other} commit -m x", f"cd {other} && git commit -m x",
                        f"git --git-dir={other}/.git --work-tree={other} commit -m x",
                        f'bash -c "cd {other} && git commit -m x"', f"cd {other}\ngit commit -m x"):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "a.py:1")
        self.assertIsNone(self.bash(f"git -C {self.repo} commit -m x", cwd=other.parent))
        self.assertIsNone(self.bash("git commit -m x"))
        self.assertDenied(self.bash(f"git -C {other.parent} -C {other.name} commit -m x"), "a.py:1")

    def test_a_repository_it_cannot_resolve_is_asked_about(self):
        for command in ('cd "$TARGET" && git commit -m x', "GIT_DIR=/x/.git git commit -m x", "popd; git commit -m x"):
            with self.subTest(command=command):
                out = self.bash(command)
                self.assertEqual(out["permissionDecision"], "ask")
                self.assertIn("cannot tell which repository", out["permissionDecisionReason"])

    def test_a_variable_the_command_sets_to_a_path_is_followed(self):
        other = new_repo()
        self.addCleanup(shutil.rmtree, other)
        notes = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, notes)
        (notes / "clean.txt").write_text("subject\n")
        (notes / "leak.txt").write_text("subject\n" + TOKEN + "\n")
        for command in (f"S={notes}\ngit merge -S x 2>&1 | tail -3; git commit --allow-empty -F $S/clean.txt",
                        f'S={notes} && P="$S" && git commit --allow-empty -F "${{P}}/clean.txt"',
                        f"printf 'subject\\n' > {notes}/new.txt; git commit --allow-empty -F {notes}/new.txt",
                        f"export S={notes}; git commit --allow-empty -F $S/clean.txt"):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command))
        for command in (f"S={notes}; git commit --allow-empty -F $S/leak.txt",
                        f"S={notes}; git log -1 --format='%h %s'; git commit --allow-empty -F $S/leak.txt",
                        f"S={notes}; git commit --allow-empty -F $S/leak.txt; for f in a; do echo $S; done"):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "leak.txt:2: GitHub token (message file)")
        self.stage(TOKEN + "\n", repo=other)
        for command in (f"C={other}; git -C $C add a.py && git -C $C commit -q -F - <<'MSG'\nx\nMSG",
                        f"T={other} && cd $T && git commit -m x"):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "a.py:1")

    def test_a_variable_set_more_than_once_or_not_to_a_literal_is_not_followed(self):
        for command in ("S=$(mktemp -d); git commit --allow-empty -F $S/m.txt",
                        "S=/a; S=/b; git commit --allow-empty -F $S/m.txt",
                        "P=$UNSET/x; git commit --allow-empty -F $P",
                        "(S=/tmp); git commit --allow-empty -F $S/m.txt",
                        "S=/a; declare S=/b; git commit --allow-empty -F $S/m.txt",
                        "S=/a; read S < f; git commit --allow-empty -F $S/m.txt",
                        "S=/a; printf -v S /b; git commit --allow-empty -F $S/m.txt",
                        "S=/a; unset S; git commit --allow-empty -F $S/m.txt",
                        "S=/a; S+=/b; git commit --allow-empty -F $S/m.txt",
                        "S=/a; eval 'S=/b'; git commit --allow-empty -F $S/m.txt",
                        "S=/a; for d in x; do git commit --allow-empty -F $S/m.txt; done",
                        "S=/a; f() { echo; }; git commit --allow-empty -F $S/m.txt",
                        "S=/a; command source ./env.sh; git commit --allow-empty -F $S/m.txt",
                        "S=/a; time . ./env.sh; git commit --allow-empty -F $S/m.txt",
                        "S=/a; X=S; builtin eval \"$X=/b\"; git commit --allow-empty -F $S/m.txt",
                        "S=/a; X=S; declare \"$X=/b\"; git commit --allow-empty -F $S/m.txt",
                        "S='/a/m.txt -a'; git commit --allow-empty -F $S",
                        "S=/a/m[.]txt; git commit --allow-empty -F $S",
                        '"S"=/a; git commit --allow-empty -F $S/m.txt',
                        "\\S=/a; git commit --allow-empty -F $S/m.txt",
                        "$(true)S=/a; git commit --allow-empty -F $S/m.txt",
                        "S=/a; S[0]=/b; git commit --allow-empty -F $S/m.txt",
                        "PWD=/a; git commit --allow-empty -F $PWD/m.txt",
                        "_=/a; true x; git commit --allow-empty -F $_/m.txt",
                        "S=/a; printf -vS /b; git commit --allow-empty -F $S/m.txt",
                        "S=/a; read < f; git commit --allow-empty -F $S/m.txt",
                        "IFS=:; S=/a; git commit --allow-empty -F $S/m.txt",
                        "S='~'; git commit --allow-empty -F $S/m.txt",
                        '[ -n "$S" ] || S=/a; git commit --allow-empty -F $S/m.txt',
                        "S=/a | true; git commit --allow-empty -F $S/m.txt",
                        "S=/a & git commit --allow-empty -F $S/m.txt",
                        "S=/a; git commit --allow-empty -F '$S/m.txt'",
                        "S=/a; git commit --allow-empty -F \\$S/m.txt",
                        "S=/a; bash -c 'git commit --allow-empty -F $S/m.txt'",
                        "M=/a/m.txt; cat > $M <<EOF\n$(cat x)\nEOF\ngit commit --allow-empty -F $M",
                        "S=/" + "a" * 5000 + "; git commit --allow-empty -F $S/m.txt"):
            with self.subTest(command=command[:80]):
                out = self.bash(command)
                self.assertEqual(out["permissionDecision"], "ask")
                self.assertIn("cannot tell which file", out["permissionDecisionReason"])
        out = self.bash("cd() ( : ); C=/a; cd $C; git commit -m x")
        self.assertIn("cannot tell which repository", out["permissionDecisionReason"])
        out = self.bash("export GIT_DIR=/x/.git; git commit -m x")
        self.assertIn("cannot tell which repository", out["permissionDecisionReason"])

    def test_a_file_a_variable_names_is_not_followed_when_the_command_writes_a_file(self):
        for command in ("S=/a; git diff > $S/p.patch; git commit --allow-empty -F $S/m.txt",
                        "S=/a; cat x > $S/m.txt; git commit --allow-empty --file=$S/m.txt",
                        "S=/a; cat x > $S/m.txt; git commit --allow-empty -F$S/m.txt",
                        "S=/a; (cd $S && cat x > m.txt); git commit --allow-empty -F $S/m.txt",
                        "S=/a; cat x > $S//m.txt; git commit --allow-empty -F $S/m.txt",
                        "S=/a; echo hi > 1; git commit --allow-empty -F $S/m.txt",
                        "S=/a; echo hi &>1; git commit --allow-empty -F $S/m.txt",
                        'S=/a; bash -c "cat x > m"; git commit --allow-empty -F $S/m.txt',
                        'S=/a; : "$(cat x > m)"; git commit --allow-empty -F $S/m.txt'):
            with self.subTest(command=command):
                out = self.bash(command)
                self.assertEqual(out["permissionDecision"], "ask")
                self.assertIn("cannot tell which file", out["permissionDecisionReason"])
        self.assertIsNone(self.bash("S=/a; git log 2>&1 >/dev/null; git commit --allow-empty -F $S/m.txt"))

    def test_a_message_file_is_read_when_a_write_to_it_may_not_run(self):
        (self.repo / "m.txt").write_text("subject\n" + TOKEN + "\n")
        for command in ("set -o noclobber; echo x > m.txt; git commit --allow-empty -F m.txt",
                        "false && echo x > m.txt; git commit --allow-empty -F m.txt"):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "m.txt:2")

    def test_an_alias_for_commit_counts(self):
        git(self.repo, "config", "alias.ci", "commit -v")
        git(self.repo, "config", "alias.sci", "!git commit")
        self.stage(TOKEN + "\n")
        self.assertDenied(self.bash("git ci -m x"), "a.py:1")
        self.assertEqual(self.bash("git sci -m x")["permissionDecision"], "ask")

    def test_an_unreadable_command_is_asked_about_only_when_it_may_commit(self):
        self.assertEqual(self.bash("git commit -m 'unclosed")["permissionDecision"], "ask")
        self.assertIsNone(self.bash("echo 'unclosed"))

    def test_outside_a_repository_is_asked_about_in_a_line(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        out = self.bash("git commit -m two", cwd=tmp)
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("is not in a git repository", out["permissionDecisionReason"])
        self.assertLess(len(out["permissionDecisionReason"]), 400)

    def test_a_comment_hides_no_command(self):
        self.stage(TOKEN + "\n")
        for command in ("# stage and commit\ngit add a.py\ngit commit -m x",
                        "# don't forget\ngit add a.py\ngit commit -m x",
                        "cd .  # here\ngit commit -m x",
                        "git log -1 --format=%h#%s && git commit -m x"):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "a.py:1")

    def test_a_commented_clean_commit_passes(self):
        self.stage("x = 2\n")
        self.assertIsNone(self.bash("# record the fix\ngit add a.py\ngit commit -m fix#12"))

    def test_a_heredoc_starts_only_outside_quotes_and_arithmetic(self):
        self.stage(TOKEN + "\n")
        for command in ('echo "see <<EOF"\ngit commit -m x', "echo $((1<<n))\ngit commit -m x",
                        "((n = 1<<2))\ngit commit -m x"):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "a.py:1")

    def test_the_usual_commit_form(self):
        command = ("git add a.py && git commit -m \"$(cat <<'EOF'\nFix the \"gate\", don't stop\n\n{}"
                   "Co-Authored-By: someone\nEOF\n)\"")
        self.stage("x = 2\n")
        self.assertIsNone(self.bash(command.format("")))
        self.assertDenied(self.bash(command.format(TOKEN + "\n")), "command:4: GitHub token (command text)")
        self.stage(TOKEN + "\n")
        self.assertDenied(self.bash(command.format("")), "a.py:1")

    def test_a_cd_inside_a_subshell_holds_only_there(self):
        other = new_repo()
        self.addCleanup(shutil.rmtree, other)
        self.stage(TOKEN + "\n")
        self.assertDenied(self.bash(f"(cd {other} && git status); git commit -m x"), "a.py:1")
        self.assertIsNone(self.bash(f"(cd {other} && git commit -m x)"))

    def test_wrappers_and_inline_aliases_are_followed(self):
        self.stage(TOKEN + "\n")
        for command in ("bash -lc 'git commit -m x'", "timeout -s KILL 30 git commit -m x",
                        "nice -n 5 git commit -m x", "nohup git commit -m x", "echo a.py | xargs git commit -m x",
                        "git -c alias.x=commit x -m y"):
            with self.subTest(command=command):
                self.assertDenied(self.bash(command), "a.py:1")

    def test_files_xargs_adds_are_scanned(self):
        (self.repo / "b.py").write_text(TOKEN + "\n")
        self.assertDenied(self.bash("ls b.py | xargs git add && git commit -m x"), "b.py:1")

    def test_an_ansi_c_quoted_message_is_read(self):
        self.stage("x = 2\n")
        self.assertIsNone(self.bash("git commit -m $'it\\'s fixed'"))

    def test_a_budget_spent_on_an_alias_lookup_is_not_taken_for_no_alias(self):
        with self.assertRaises(secret_scan.BudgetSpent):
            secret_scan.alias_of((str(self.repo), ()), "ci", secret_scan.Budget(seconds=0))

    def test_a_long_diff_checks_the_clock_by_size(self):
        class Counting(secret_scan.Budget):
            calls = 0

            def remaining(self):
                Counting.calls += 1
                return super().remaining()

        diff = "diff --git a/d b/d\n+++ b/d\n@@ -0,0 +1,5 @@\n" + ("+" + "x" * 200_000 + "\n") * 5
        secret_scan.scan_diff(diff, budget=Counting())
        self.assertGreaterEqual(Counting.calls, 2)

    def hook_with(self, budget):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            secret_scan.hook(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
                                         "cwd": str(self.repo)}), budget)
        return json.loads(out.getvalue())["hookSpecificOutput"]

    def test_a_scan_past_its_budget_is_asked_about(self):
        self.stage("x = 2\n" * 50)
        out = self.hook_with(secret_scan.Budget(size=10))
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("more text than the scan can check", out["permissionDecisionReason"])
        out = self.hook_with(secret_scan.Budget(seconds=0))
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("ran out of time", out["permissionDecisionReason"])


class Gh(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "body.md").write_text("Notes\n" + TOKEN + "\n")
        (self.tmp / "clean.md").write_text("Notes\n")

    def bash(self, command):
        return run_gate(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.tmp)}))

    def test_a_write_with_a_secret_is_denied(self):
        for command, where in ((f"gh pr comment 1 --body 'see {TOKEN}'", "command:1"),
                               ("gh issue create --title t --body-file body.md", "body.md:2"),
                               ("gh -R o/r pr create --title t -F body.md", "body.md:2"),
                               ("gh api repos/o/r/issues -F body=@body.md -f title=t", "body.md:2"),
                               ("gh api repos/o/r/issues --input body.md", "body.md:2"),
                               ("gh gist create --desc 'my notes' clean.md body.md", "body.md:2")):
            with self.subTest(command=command):
                out = self.bash(command)
                self.assertEqual(out["permissionDecision"], "deny")
                self.assertIn(where, out["permissionDecisionReason"])
                self.assertNotIn(A36, out["permissionDecisionReason"])

    def test_comments_and_hashes_hide_no_write(self):
        for command in (f"# post the summary\ngh pr comment 1 --body 'see {TOKEN}'",
                        f"git log -1 --format=%h#%s && gh pr comment 1 --body 'see {TOKEN}'"):
            with self.subTest(command=command):
                self.assertEqual(self.bash(command)["permissionDecision"], "deny")

    def test_close_reopen_and_repository_writes_are_scanned(self):
        for command in (f"gh issue close 5 -c 'see {TOKEN}'", f"gh pr close 5 --comment 'see {TOKEN}'",
                        f"gh pr reopen 5 --comment 'see {TOKEN}'", f"gh repo edit --description '{TOKEN}'"):
            with self.subTest(command=command):
                self.assertEqual(self.bash(command)["permissionDecision"], "deny")

    def test_a_file_it_cannot_resolve_is_asked_about(self):
        out = self.bash('gh pr comment 1 --body-file "$NOTES"')
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("cannot tell which file", out["permissionDecisionReason"])

    def test_a_body_file_in_a_variable_the_command_sets_is_read(self):
        (self.tmp / "leak.md").write_text(TOKEN + "\n")
        self.assertEqual(self.bash(f"S={self.tmp}; gh pr comment 1 --body-file $S/leak.md")["permissionDecision"],
                         "deny")
        for command in ("S=/a; cat x > $S/m.md; gh pr comment 1 --body-file=$S/m.md",
                        "S=/a; cat x > $S/m.md; gh api repos/o/r/issues -F body=@$S/m.md"):
            with self.subTest(command=command):
                self.assertIn("cannot tell which file", self.bash(command)["permissionDecisionReason"])

    def test_a_body_file_the_command_writes_from_its_own_text_passes(self):
        self.assertIsNone(self.bash('echo body > "$NOTES" && gh pr comment 1 --body-file "$NOTES"'))
        out = self.bash('echo "$X" > "$NOTES" && gh pr comment 1 --body-file "$NOTES"')
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("cannot tell which file", out["permissionDecisionReason"])

    def test_an_unreadable_command_is_asked_about_only_when_it_may_write(self):
        self.assertEqual(self.bash("gh pr comment 1 --body 'unclosed")["permissionDecision"], "ask")
        self.assertIsNone(self.bash("gh pr view 1; echo 'unclosed"))

    def test_reads_and_clean_writes_pass(self):
        for command in ("gh pr view 1", "gh api repos/o/r/pulls", f"gh pr list --search {TOKEN}",
                        "gh pr comment 1 --body-file clean.md", "gh pr comment 1 --body-file missing.md"):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command))


class Writes(unittest.TestCase):
    def call(self, tool, tool_input):
        return run_gate(json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": "/"}))

    def test_github_write_with_a_secret_is_denied_by_field(self):
        out = self.call("mcp__github-x__push_files",
                        {"files": [{"path": "a", "content": "ok"}, {"path": "b", "content": "k\n" + SECRETS["Slack token"]}]})
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("files[1].content:2: Slack token", out["permissionDecisionReason"])

    def test_every_github_tool_but_a_read_is_scanned(self):
        body = {"commit_message": TOKEN, "body": TOKEN}
        for tool in ("mcp__github-example__merge_pull_request", "mcp__github__create_gist",
                     "mcp__github-ehlmann__a_tool_a_later_server_adds"):
            with self.subTest(tool=tool):
                self.assertEqual(self.call(tool, body)["permissionDecision"], "deny")
        for tool in ("mcp__github__get_file_contents", "mcp__github-example__pull_request_read",
                     "mcp__github__search_code", "mcp__github__list_issues", "mcp__github__run_secret_scanning",
                     "mcp__other__create_thing"):
            with self.subTest(tool=tool):
                self.assertIsNone(self.call(tool, body))

    def test_clean_github_write_passes(self):
        self.assertIsNone(self.call("mcp__github-x__add_issue_comment", {"body": "Looks good."}))

    def test_atlassian_write_is_scanned_and_read_is_not(self):
        body = {"issue_key": "X-1", "comment": SECRETS["AWS access key ID"]}
        self.assertEqual(self.call("mcp__atl__jira_add_comment", body)["permissionDecision"], "deny")
        self.assertIsNone(self.call("mcp__atl__jira_get_issue", body))

    def test_unparsable_payload_is_asked_about(self):
        self.assertEqual(run_gate("not json")["permissionDecision"], "ask")


class NoPython(unittest.TestCase):
    """The gate on a machine with no python3: it asks about what it would have scanned."""

    def setUp(self):
        self.bin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.bin)
        for tool in ("bash", "cat", "dirname"):
            os.symlink(shutil.which(tool), self.bin / tool)

    def gate(self, tool, tool_input):
        payload = json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": "/"})
        r = subprocess.run([shutil.which("bash"), str(GATE)], input=payload, capture_output=True, text=True,
                           check=True, env={"PATH": str(self.bin)})
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else None

    def test_it_asks_about_commits_posts_and_writes(self):
        self.assertEqual(self.gate("Bash", {"command": "git commit -m x"}), "ask")
        self.assertEqual(self.gate("Bash", {"command": "gh pr comment 1 --body x"}), "ask")
        self.assertEqual(self.gate("mcp__github-example__add_issue_comment", {"body": "x"}), "ask")
        self.assertEqual(self.gate("mcp__atl__jira_add_comment", {"comment": "x"}), "ask")

    def test_it_lets_the_rest_through(self):
        self.assertIsNone(self.gate("Bash", {"command": "git status"}))
        self.assertIsNone(self.gate("mcp__atl__jira_get_issue", {"issue_key": "X-1"}))
        self.assertIsNone(self.gate("mcp__github__get_me", {}))
        self.assertIsNone(self.gate("mcp__github__pull_request_read", {}))


class Registration(unittest.TestCase):
    def matcher(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]["PreToolUse"]
        [m] = [h["matcher"] for h in hooks if any("secret-gate" in c["command"] for c in h["hooks"])]
        return re.compile(f"^({m})$")

    def test_hooks_json_sends_it_bash_and_every_server_tool(self):
        m = self.matcher()
        for tool in ["Bash", "mcp__atl__jira_add_comment", "mcp__atl__confluence_update_page",
                     "mcp__github-example__merge_pull_request", "mcp__github__a_tool_a_later_server_adds"]:
            with self.subTest(tool=tool):
                self.assertTrue(m.match(tool))

    def test_hooks_json_spares_other_servers(self):
        self.assertFalse(self.matcher().match("mcp__spicedocs__get_page"))

    def test_gate_is_executable(self):
        self.assertTrue(os.access(GATE, os.X_OK))


if __name__ == "__main__":
    unittest.main()
