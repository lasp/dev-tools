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
from unittest import mock

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


def hook_output(event, budget):
    """What the hook prints for this event, run in this process on this budget."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        secret_scan.hook(json.dumps(event), budget)
    return out.getvalue()


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

    def assertPassesUnread(self, command, reason, cwd=None):
        """The scan cannot read this command, for this reason, and the gate lets it through."""
        self.assertIsNone(self.bash(command, cwd))
        with self.assertRaisesRegex(secret_scan.ScanError, reason):
            secret_scan.scan_commit(command, str(cwd or self.repo), secret_scan.Budget(), [])

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
                self.assertPassesUnread(command, "cannot tell which file")

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

    def test_a_repository_it_cannot_resolve_passes(self):
        self.stage(TOKEN + "\n")
        for command in ('cd "$TARGET" && git commit -m x', "GIT_DIR=/x/.git git commit -m x", "popd; git commit -m x"):
            with self.subTest(command=command):
                self.assertPassesUnread(command, "cannot tell which repository")

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
                self.assertPassesUnread(command, "cannot tell which file")
        self.assertPassesUnread("cd() ( : ); C=/a; cd $C; git commit -m x", "cannot tell which repository")
        self.assertPassesUnread("export GIT_DIR=/x/.git; git commit -m x", "cannot tell which repository")

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
                self.assertPassesUnread(command, "cannot tell which file")
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
        self.assertPassesUnread("git sci -m x", "shell alias that commits")

    def test_a_command_it_cannot_split_is_judged_on_its_text(self):
        self.stage(TOKEN + "\n")
        for command in ("git commit -m 'unclosed", "echo 'unclosed",
                        f'echo "$(echo "it\'s")" {TOKEN}; git log --grep commit'):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command))
        for command in (f"git commit -m '{TOKEN}", f'git commit -m "a $(echo "b\'c") {TOKEN}"',
                        f'git commit -m "`echo "\'"` {TOKEN}"'):
            with self.subTest(command=command):
                with self.assertRaises(ValueError):
                    secret_scan.scan_commit(command, str(self.repo), secret_scan.Budget(), [])
                self.assertDenied(self.bash(command), "(command text)")
        self.assertDenied(self.bash("git commit -m 'closed'"), "a.py:1")

    def test_outside_a_repository_passes(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        self.assertPassesUnread("git commit -m two", "is not in a git repository", cwd=tmp)

    def test_a_finding_before_the_scan_stops_is_denied(self):
        self.stage(TOKEN + "\n")
        self.assertDenied(self.bash('git commit -m x && cd "$D" && git commit -m y'), "a.py:1")
        self.assertDenied(self.bash('(cd "$D" && git commit -m y); git commit -m x'), "a.py:1")
        self.assertDenied(self.bash('(cd "$D" && git add .); git commit -m x'), "a.py:1")
        self.stage("x = 2\n")
        self.assertDenied(self.bash(f'cd "$D" && git commit -m "{TOKEN}"'), "(command text)")
        git(self.repo, "config", "alias.sci", "!git commit")
        self.assertDenied(self.bash(f'git sci -m "{TOKEN}"'), "(command text)")

    def test_a_finding_before_the_budget_is_spent_is_denied(self):
        self.stage(TOKEN + "\n")
        event = {"tool_name": "Bash", "tool_input": {"command": "git commit -a -m x"}, "cwd": str(self.repo)}
        with mock.patch.object(secret_scan, "scan_unstaged", side_effect=secret_scan.BudgetSpent("spent")):
            out = json.loads(hook_output(event, secret_scan.Budget()))["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("a.py:1", out["permissionDecisionReason"])

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

    def test_a_scan_past_its_budget_passes(self):
        self.stage(TOKEN + "\n" + "x = 2\n" * 50)
        for budget in (secret_scan.Budget(size=10), secret_scan.Budget(seconds=0)):
            with self.subTest(budget=vars(budget)):
                self.assertEqual(hook_output({"tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
                                              "cwd": str(self.repo)}, budget), "")


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

    def assertPassesUnread(self, command, reason):
        """The scan cannot read this command, for this reason, and the gate lets it through."""
        self.assertIsNone(self.bash(command))
        with self.assertRaisesRegex(secret_scan.ScanError, reason):
            secret_scan.scan_gh(command, str(self.tmp), secret_scan.Budget(), [])

    def test_a_file_it_cannot_resolve_passes(self):
        self.assertPassesUnread('gh pr comment 1 --body-file "$NOTES"', "cannot tell which file")

    def test_a_body_file_in_a_variable_the_command_sets_is_read(self):
        (self.tmp / "leak.md").write_text(TOKEN + "\n")
        self.assertEqual(self.bash(f"S={self.tmp}; gh pr comment 1 --body-file $S/leak.md")["permissionDecision"],
                         "deny")
        for command in ("S=/a; cat x > $S/m.md; gh pr comment 1 --body-file=$S/m.md",
                        "S=/a; cat x > $S/m.md; gh api repos/o/r/issues -F body=@$S/m.md"):
            with self.subTest(command=command):
                self.assertPassesUnread(command, "cannot tell which file")

    def test_a_body_file_the_command_writes_from_its_own_text_passes(self):
        self.assertIsNone(self.bash('echo body > "$NOTES" && gh pr comment 1 --body-file "$NOTES"'))
        self.assertPassesUnread('echo "$X" > "$NOTES" && gh pr comment 1 --body-file "$NOTES"',
                                "cannot tell which file")

    def test_a_command_it_cannot_split_is_judged_on_its_text(self):
        for command in ("gh pr comment 1 --body 'unclosed", "gh pr view 1; echo 'unclosed",
                        f"gh pr view 1; echo '{TOKEN}"):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command))
        for command in (f"gh pr comment 1 --body '{TOKEN}", f'gh pr comment 1 --body "a $(echo "b\'c") {TOKEN}"'):
            with self.subTest(command=command):
                self.assertEqual(self.bash(command)["permissionDecision"], "deny")

    def test_a_finding_before_the_scan_stops_is_denied(self):
        for command in ('gh pr create --title t --body-file body.md && gh issue create --title t --body-file "$X"',
                        'gh issue create --title t --body-file "$X" && gh pr create --title t --body-file body.md',
                        "GIT_DIR=/x/.git git commit -m x; gh pr comment 1 --body-file body.md"):
            with self.subTest(command=command):
                out = self.bash(command)
                self.assertEqual(out and out["permissionDecision"], "deny", out)
                self.assertIn("body.md:2", out["permissionDecisionReason"])

    def test_reads_and_clean_writes_pass(self):
        for command in ("gh pr view 1", "gh api repos/o/r/pulls", f"gh pr list --search {TOKEN}",
                        "gh pr comment 1 --body-file clean.md", "gh pr comment 1 --body-file missing.md"):
            with self.subTest(command=command):
                self.assertIsNone(self.bash(command))


class Writes(unittest.TestCase):
    """A server's kind comes from its configuration in `.mcp.json` or `.claude.json`, here in a
    project directory and a config directory of the test's own."""

    def setUp(self):
        self.project = Path(tempfile.mkdtemp()).resolve()
        self.config = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project)
        self.addCleanup(shutil.rmtree, self.config)
        self.servers({"other": {"command": "other-mcp"}})

    def servers(self, servers):
        (self.project / ".mcp.json").write_text(json.dumps({"mcpServers": servers}))

    def call(self, tool, tool_input, cwd=None, project_dir=None):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        env["CLAUDE_CONFIG_DIR"] = str(self.config)
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)
        return run_gate(json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd or self.project)}),
                        env=env)

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

    def test_a_github_server_is_told_by_what_it_is_or_by_its_name(self):
        body = {"body": TOKEN}
        self.servers({"corp-code": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"},
                      "gh": {"command": "docker", "args": ["run", "-i", "ghcr.io/github/github-mcp-server"]},
                      "npx-code": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"]},
                      "hub": {"command": "docker", "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                                                            "mcp/github"]},
                      "hub-tagged": {"command": "docker", "args": ["run", "-i", "mcp/github:latest"]},
                      "hub-registry": {"command": "docker", "args": ["run", "-i", "docker.io/mcp/github"]},
                      "hub-digest": {"command": "docker", "args": ["run", "-i", "mcp/github@sha256:" + "0" * 64]},
                      "remote": {"command": "npx", "args": ["-y", "mcp-remote", "HTTPS://api.githubcopilot.com/mcp/"]},
                      "ghe": {"type": "http", "url": "https://copilot-api.corp.ghe.com/mcp/"},
                      "github-mirror": {"type": "http", "url": "https://code.example.org/mcp"},
                      "github": {"command": "an-unrecognized-binary"}})
        for tool in ("mcp__corp-code__add_issue_comment", "mcp__gh__create_pull_request",
                     "mcp__npx-code__create_issue", "mcp__hub__create_issue", "mcp__hub-tagged__create_issue",
                     "mcp__hub-registry__create_issue", "mcp__hub-digest__create_issue",
                     "mcp__remote__create_issue", "mcp__ghe__add_issue_comment",
                     "mcp__github-mirror__add_issue_comment", "mcp__github__push_files"):
            with self.subTest(tool=tool):
                self.assertEqual(self.call(tool, body)["permissionDecision"], "deny")

    def test_a_variable_outside_the_fields_that_tell_the_kind_does_not_hide_it(self):
        self.servers({"hosted": {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
                                 "headers": {"Authorization": "Bearer ${GITHUB_PAT}"}},
                      "local": {"command": "docker", "args": ["run", "-i", "ghcr.io/github/github-mcp-server"],
                                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PAT}"}},
                      "in-args": {"command": "docker", "args": ["run", "-i", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN=${GH_PAT}",
                                                                "ghcr.io/github/github-mcp-server"]}})
        for tool in ("mcp__hosted__add_issue_comment", "mcp__local__add_issue_comment", "mcp__in-args__add_issue_comment"):
            with self.subTest(tool=tool):
                self.assertEqual(self.call(tool, {"body": TOKEN})["permissionDecision"], "deny")

    def test_atlassian_s_hosted_server_is_atlassian_s(self):
        self.servers({"rovo": {"type": "http", "url": "https://mcp.atlassian.com/v1/sse"}})
        self.assertEqual(self.call("mcp__rovo__addCommentToJiraIssue", {"body": TOKEN})["permissionDecision"], "deny")

    def test_a_key_is_matched_as_claude_code_names_its_tools(self):
        self.servers({"corp.code host": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"}})
        self.assertEqual(self.call("mcp__corp_code_host__add_issue_comment", {"body": TOKEN})["permissionDecision"],
                         "deny")

    def test_the_local_scope_wins_over_the_project_and_user_scopes(self):
        elsewhere = {"type": "http", "url": "https://code.example.org/mcp"}
        self.servers({"code": elsewhere})
        (self.config / ".claude.json").write_text(json.dumps({
            "mcpServers": {"code": elsewhere},
            "projects": {str(self.project): {"mcpServers": {
                "code": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"}}}}}))
        self.assertEqual(self.call("mcp__code__add_issue_comment", {"body": TOKEN})["permissionDecision"], "deny")

    def test_a_server_found_only_in_the_user_scope_or_a_parent_is_read(self):
        (self.config / ".claude.json").write_text(json.dumps({"mcpServers": {
            "user-code": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"}}}))
        self.assertEqual(self.call("mcp__user-code__add_issue_comment", {"body": TOKEN})["permissionDecision"], "deny")
        self.servers({"up": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"},
                      "other": {"command": "other-mcp"}})
        self.project = self.project / "sub" / "dir"
        self.project.mkdir(parents=True)
        self.assertEqual(self.call("mcp__up__add_issue_comment", {"body": TOKEN})["permissionDecision"], "deny")
        self.assertIsNone(self.call("mcp__other__create_thing", {"body": TOKEN}))

    def test_a_server_of_unknown_kind_passes(self):
        body = {"body": TOKEN}
        self.servers({"vars": {"type": "http", "url": "${CODE_MCP_URL}"}})
        for tool in ("mcp__unconfigured__add_comment", "mcp__vars__add_comment"):
            with self.subTest(tool=tool):
                self.assertIsNone(self.call(tool, body))
        deep = '{"mcpServers": ' + '{"x": ' * 100000 + "1" + "}" * 100001
        for malformed in ("{not json", json.dumps({"mcpServers": {"other": ["not", "a", "server"]}}),
                          json.dumps({"mcpServers": ["other"]}), json.dumps({"mcpServers": {"other": {"args": 5}}}),
                          json.dumps({"mcpServers": {"other": {"command": "x", "args": [["nested"]]}}}), deep):
            with self.subTest(malformed=malformed[:60]):
                (self.project / ".mcp.json").write_text(malformed)
                self.assertIsNone(self.call("mcp__other__create_thing", body))
                self.assertEqual(self.call("mcp__github__create_thing", body)["permissionDecision"], "deny")

    def test_the_lookup_starts_at_the_project_directory_not_the_session_cwd(self):
        elsewhere = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, elsewhere)
        (self.config / ".claude.json").write_text(json.dumps({"projects": {str(self.project): {"mcpServers": {
            "local-code": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"}}}}}))
        self.servers({"code": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"}})
        for tool in ("mcp__local-code__add_issue_comment", "mcp__code__add_issue_comment"):
            with self.subTest(tool=tool):
                out = self.call(tool, {"body": TOKEN}, cwd=elsewhere, project_dir=self.project)
                self.assertEqual(out["permissionDecision"], "deny")
                self.assertIsNone(self.call(tool, {"body": TOKEN}, cwd=elsewhere))

    def test_clean_github_write_passes(self):
        self.assertIsNone(self.call("mcp__github-x__add_issue_comment", {"body": "Looks good."}))

    def test_atlassian_write_is_scanned_and_read_is_not(self):
        body = {"issue_key": "X-1", "comment": SECRETS["AWS access key ID"]}
        self.assertEqual(self.call("mcp__atl__jira_add_comment", body)["permissionDecision"], "deny")
        self.assertIsNone(self.call("mcp__atl__jira_get_issue", body))

    def test_unparsable_payload_passes(self):
        self.assertIsNone(run_gate("not json"))

    def test_a_finding_before_the_budget_is_spent_is_still_denied(self):
        event = {"tool_name": "mcp__github__add_issue_comment", "cwd": "/",
                 "tool_input": {"a": "see " + TOKEN, "b": "x" * 100}}
        out = json.loads(hook_output(event, secret_scan.Budget(size=len(event["tool_input"]["a"]) + 10)))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("a:1: GitHub token", out["hookSpecificOutput"]["permissionDecisionReason"])
        event["tool_input"] = {"a": "x" * 100, "b": "see " + TOKEN}
        self.assertEqual(hook_output(event, secret_scan.Budget(size=10)), "")


class NoPython(unittest.TestCase):
    """The gate on a machine with no python3: nothing is scanned, so every call passes."""

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

    def test_every_call_passes(self):
        self.assertIsNone(self.gate("Bash", {"command": f"git commit -m '{TOKEN}'"}))
        self.assertIsNone(self.gate("Bash", {"command": "gh pr comment 1 --body x"}))
        self.assertIsNone(self.gate("mcp__github-example__add_issue_comment", {"body": TOKEN}))
        self.assertIsNone(self.gate("mcp__atl__jira_add_comment", {"comment": "x"}))
        self.assertIsNone(self.gate("Bash", {"command": "git status"}))
        self.assertIsNone(self.gate("mcp__atl__jira_get_issue", {"issue_key": "X-1"}))
        self.assertIsNone(self.gate("mcp__github__get_me", {}))
        self.assertIsNone(self.gate("mcp__github__pull_request_read", {}))
        self.assertIsNone(self.gate("mcp__claude-in-chrome__navigate", {"url": "x"}))
        self.assertIsNone(self.gate("mcp__corp-code__add_issue_comment", {"body": "x"}))


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

    def test_hooks_json_sends_it_a_server_whatever_its_name(self):
        self.assertTrue(self.matcher().match("mcp__corp-code__create_pull_request"))

    def test_gate_is_executable(self):
        self.assertTrue(os.access(GATE, os.X_OK))


if __name__ == "__main__":
    unittest.main()
