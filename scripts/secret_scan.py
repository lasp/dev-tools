#!/usr/bin/env python3
"""Find credentials in text a commit or a post would carry, by a fixed list of forms.

    secret_scan.py files <path>...   scan files
    secret_scan.py diff              scan the lines `git diff --cached` and `git diff` add in the
                                     current directory's repository
    secret_scan.py hook              read a PreToolUse payload on stdin and print the decision

A finding prints as `<where>:<line>: <kind>`; the matched value is never printed. The forms are
ones a credential takes and ordinary text does not, so a hit is worth stopping for: no entropy
guess. A value ending in EXAMPLE, the form AWS's documentation uses, is not a finding, and neither
is a line carrying `gitleaks:allow`, the marker gitleaks, run by this repository's pre-commit
configuration, also honors. scripts/transcript_excerpt.py's list is wider on purpose: it redacts
text that is shown, where a miss costs more than a false hit; here a false hit stops a commit.

What the hook scans:
- A Bash command that runs `git commit`, found by parsing the command: comments, quotes, `$( )`
  and heredoc bodies are read as the shell reads them; the repository is the one `cd`, `git -C`,
  `--git-dir` and `--work-tree` name, a `cd` inside `( )` holding only there; a variable the command
  sets once to a literal value, as `S=/tmp/x; git commit -F $S/msg`, is read as that value where
  `plan` says; `bash -c`, `timeout`,
  `nice`, `nohup` and `xargs` are followed; and an alias whose first word is `commit` counts, a
  `-c alias.<name>=` one included. It scans the staged changes; the unstaged changes to tracked files when the commit takes
  `-a`, `--patch` or paths, or a `git add` in the same command stages them; the untracked files a
  `git add` in the same command names, with ignored ones when it takes `-f`; the command's own text,
  which holds a `-m` message or a heredoc; and a `-F <file>` message file.
- A Bash command led by `gh` that writes (an issue or pull request created, edited, commented
  on, reviewed, merged, closed or reopened; a gist, release or repository created or edited; or
  `gh api` with fields or a body): the command's text and the
  files it sends (`--body-file`, `--notes-file`, `-F`, `--input`, `field=@file`, a gist's files).
- Any tool of a GitHub server (a server whose name holds `github`) but a read, and any Jira or
  Confluence tool but a read: every string in the call's input, named by its field.

Untracked files over 1 MB are taken for data and skipped. The scan stops at its own budget, well
inside the hook's 5 s timeout, since a hook that times out lets the call through; past it, the
hook asks.

Exit codes, for `files` and `diff`: 0 nothing found, 1 a finding, 2 the scan could not run (a file
unreadable, git failing). `hook` always exits 0 and decides in its output:
- `deny` when what the call would carry holds a finding, naming where and what kind;
- `ask` when it cannot scan (input it cannot parse, a repository it cannot resolve, git failing,
  the budget spent), saying so, so a broken scan stops for the person rather than passing a call
  nobody checked;
- nothing, which lets the call through, for any other call.
"""
import collections
import json
import os
import re
import shlex
import subprocess
import sys
import time

PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----")),
    ("AWS access key ID", re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{16,}")),
    ("Atlassian API token", re.compile(r"\bATATT3[A-Za-z0-9_\-=]{150,}")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[a-z]+\d*-[A-Za-z0-9_\-]{40,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("JSON web token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    # A token or secret assigned to a variable these servers and clouds name, or sent as a bearer
    # header. The value must hold a letter and a digit, so a placeholder such as
    # `your-token-goes-here` or a reference such as `${JIRA_TOKEN}` is not a finding.
    ("token assignment", re.compile(
        r"\b(?:JIRA|CONFLUENCE|ATLASSIAN|GITHUB|GH|GITLAB|SLACK|ANTHROPIC|OPENAI)_[A-Z_]*(?:TOKEN|KEY|SECRET|PASSWORD)\b"
        r"[\"']?\s*[=:]\s*[\"']?(?=[A-Za-z0-9+/_\-.=]*[0-9])(?=[A-Za-z0-9+/_\-.=]*[A-Za-z])[A-Za-z0-9+/_\-.=]{20,}")),
    ("AWS secret access key", re.compile(
        r"\bAWS_SECRET_ACCESS_KEY\b[\"']?\s*[=:]\s*[\"']?(?=[A-Za-z0-9+/]*[0-9])[A-Za-z0-9+/]{40}\b")),
    ("bearer token", re.compile(
        r"\bBearer\s+(?=[A-Za-z0-9._~+/\-]*[0-9])(?=[A-Za-z0-9._~+/\-]*[A-Za-z])[A-Za-z0-9._~+/\-]{30,}=*")),
]

# A tool of a GitHub or Atlassian server that only reads; every other tool of theirs is a write.
GITHUB_READ = re.compile(r"(?:get_|list_|search_)|.*_read$|run_secret_scanning$")
ATLASSIAN_READ = re.compile(r"(?:jira|confluence)_(?:get_|search|list_|check_|download_|batch_get_)")

UNTRACKED_LIMIT = 1_000_000  # bytes; a larger untracked file is data, not something typed
BUDGET_SECONDS = 2.5         # the hook's timeout is 5 s, and a timed-out hook lets the call through
BUDGET_BYTES = 16_000_000    # of text scanned in one call

# git's own commands, which are never aliases; any other word is looked up as an alias.
GIT_COMMANDS = set("""add am apply archive bisect blame branch cat-file checkout cherry-pick
clean clone commit config describe diff fetch for-each-ref format-patch fsck gc grep help init
log ls-files ls-remote merge mv notes pull push rebase reflog remote reset restore rev-list
rev-parse revert rm shortlog show show-ref stash status submodule switch symbolic-ref tag
update-index version worktree""".split())
GIT_GLOBAL_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--exec-path"}
COMMIT_SHORT_WITH_ARG = set("mFcCt")
COMMIT_LONG_WITH_ARG = {"--message", "--file", "--author", "--date", "--reuse-message", "--reedit-message",
                        "--fixup", "--squash", "--template", "--cleanup", "--trailer", "--pathspec-from-file"}
ADD_LONG_WITH_ARG = {"--chmod", "--pathspec-from-file"}
SHELL_WORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "time", "nohup",
               "command", "exec", "builtin"}
TIMEOUT_WITH_ARG = {"-s", "--signal", "-k", "--kill-after"}
XARGS_WITH_ARG = {"-I", "-n", "-L", "-P", "-d", "-E", "-s", "-a", "--max-args", "--max-lines", "--max-procs",
                  "--delimiter", "--eof", "--max-chars", "--arg-file", "--replace"}
GH_WRITES = {("issue", "create"), ("issue", "comment"), ("issue", "edit"), ("issue", "close"),
             ("issue", "reopen"), ("pr", "create"), ("pr", "comment"), ("pr", "edit"), ("pr", "review"),
             ("pr", "merge"), ("pr", "close"), ("pr", "reopen"), ("gist", "create"), ("gist", "edit"),
             ("release", "create"), ("release", "edit"), ("repo", "create"), ("repo", "edit")}
# A command that may be a gh write, read from its text when the command cannot be split.
GH_WRITE_TEXT = re.compile(r"\bgh\s+(?:(?:-R|--repo)[\s=]\S+\s+)?(?:api\b|"
                           + "|".join(rf"{a}\s+{b}\b" for a, b in sorted(GH_WRITES)) + ")")


class ScanError(Exception):
    pass


class BudgetSpent(ScanError):
    pass


class Budget:
    """The time and bytes one call may spend; a scan past either stops with a ScanError."""

    def __init__(self, seconds=None, size=None):
        self.deadline = time.monotonic() + (BUDGET_SECONDS if seconds is None else seconds)
        self.left = BUDGET_BYTES if size is None else size

    def remaining(self):
        r = self.deadline - time.monotonic()
        if r <= 0:
            raise BudgetSpent("the scan ran out of time before it finished")
        return r

    def spend(self, n):
        self.left -= n
        if self.left < 0:
            raise BudgetSpent("there is more text than the scan can check in time")
        self.remaining()


def scan_text(text, where, first_line=1):
    """Each finding in `text` as `<where>:<line>: <kind>`, the first line numbered `first_line`."""
    found = []
    for n, line in enumerate(text.splitlines(), first_line):
        if "gitleaks:allow" in line:
            continue
        for kind, pattern in PATTERNS:
            if any(not m.group(0).endswith("EXAMPLE") for m in pattern.finditer(line)):
                found.append(f"{where}:{n}: {kind}")
    return found


def scan_file(path, where=None, budget=None):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ScanError(f"cannot read {path}: {e.strerror}") from None
    if budget:
        budget.spend(len(data))
    if b"\0" in data:
        return []
    return scan_text(data.decode("utf-8", "replace"), where or path)


def git(repo, *args, budget=None):
    """Run git in `repo`, a (directory, global options) pair; its stdout, or a ScanError naming
    the first line of what git said."""
    cwd, opts = repo
    try:
        r = subprocess.run(["git", *opts, *args], cwd=cwd, capture_output=True, text=True, errors="replace",
                           timeout=budget.remaining() if budget else None)
    except subprocess.TimeoutExpired:
        raise BudgetSpent("the scan ran out of time before it finished") from None
    except OSError as e:
        raise ScanError(f"cannot run git in {cwd}: {e.strerror}") from None
    if r.returncode:
        first = (r.stderr.strip().splitlines() or [f"exit {r.returncode}"])[0]
        raise ScanError(f"git {args[0]} failed: {first}")
    if budget:
        budget.spend(len(r.stdout))
    return r.stdout


def scan_diff(diff, tag="", budget=None):
    """The findings in the lines a unified diff with no context adds, at their new line numbers.
    A file's `---` and `+++` lines are headers only between its `diff --git` line and its first
    hunk, so an added line that starts `++ ` is content."""
    found, path, n, header, seen = [], None, 0, False, 0
    for line in diff.splitlines():
        seen += len(line) + 1
        if budget and seen >= 262144:
            budget.remaining()
            seen = 0
        if line.startswith("diff --git "):
            path, header = None, True
        elif header and line.startswith("+++ "):
            # A path git quotes, for a character it escapes, keeps its quotes: it still names the file.
            name = line[4:].strip('"')
            path = None if name == "/dev/null" else name[2:] if name.startswith("b/") else name
        elif line.startswith("@@"):
            header = False
            m = re.match(r"@@ -\S+ \+(\d+)", line)
            n = int(m.group(1)) if m else 0
        elif not header and line.startswith("+") and path:
            found += [f + tag for f in scan_text(line[1:], path, n)]
            n += 1
    return found


DIFF_OPTS = ("-U0", "--no-color", "--no-ext-diff", "--no-renames")


def check_repository(repo, budget):
    try:
        git(repo, "rev-parse", "--is-inside-work-tree", budget=budget)
    except BudgetSpent:
        raise
    except ScanError:
        raise ScanError(f"{repo[0]} is not in a git repository the scan can read") from None


def scan_staged(repo, budget):
    return scan_diff(git(repo, "-c", "core.quotePath=false", "diff", "--cached", *DIFF_OPTS, budget=budget),
                     " (staged)", budget)


def scan_unstaged(repo, paths, budget, tag=" (working tree, this command stages it)"):
    """The unstaged changes to tracked files, all of them when `paths` is None."""
    extra = ["--", *paths] if paths is not None else []
    return scan_diff(git(repo, "-c", "core.quotePath=false", "diff", *DIFF_OPTS, *extra, budget=budget), tag, budget)


def scan_existing(cwd, name, budget, own=frozenset()):
    """The findings in a file a command names, or none when it is `-` or does not exist, since the
    command then reads stdin, which is in the command's own text, or fails. A name the scan cannot
    resolve has none when it is in `own`, the files `written_here` finds."""
    if name in ("", "-"):
        return []
    path = resolve(cwd, name)
    if path is UNRESOLVED:
        if norm_name(name) in own:
            return []
        raise ScanError(f"the scan cannot tell which file `{name}` is")
    return scan_file(path, name, budget) if os.path.exists(path) else []


def scan_untracked(repo, paths, ignored, budget):
    """The untracked files under `paths` (all, when None), ignored ones too when `ignored`."""
    top = git(repo, "rev-parse", "--show-toplevel", budget=budget).strip()
    args = ["ls-files", "--others", "--full-name", "-z"]
    if not ignored:
        args.append("--exclude-standard")
    if paths is not None:
        args += ["--", *paths]
    found = []
    for rel in git(repo, *args, budget=budget).split("\0"):
        if rel:
            path = os.path.join(top, rel)
            if os.path.isfile(path) and os.path.getsize(path) <= UNTRACKED_LIMIT:
                found += [f + " (untracked, this command adds it)" for f in scan_file(path, rel, budget)]
    return found


# --- Reading a shell command ---------------------------------------------------------------------

HEREDOC = re.compile(r"<<(-?)[ \t]*(?:'([^'\n]*)'|\"([^\"\n]*)\"|\\?([^\s;&|()<>'\"]+))")
WORD_START = set(" \t\n;&|()")


def ansi_c(command, i):
    """The `$'...'` word starting at `i` as a double-quoted word shlex can read, and the index past
    it; None when it does not close."""
    out, j = [], i + 2
    while j < len(command):
        c = command[j]
        if c == "'":
            text = "".join(out)
            return '"' + re.sub(r'(["\\$`])', r"\\\1", text) + '"', j + 1
        if c == "\\" and j + 1 < len(command):
            out.append({"n": "\n", "t": "\t"}.get(command[j + 1], command[j + 1]))
            j += 2
            continue
        out.append(c)
        j += 1
    return None


def prepare(command, docs=None):
    """The command as shlex can split it, read as the shell reads it: a comment dropped to the end
    of its line, heredoc bodies dropped, a backslash-newline joined, each newline between commands
    as `;`, and `$'...'` as a double-quoted word. Quotes, `$( )` and `$(( ))` are followed, so a
    `#`, `<<` or newline inside one is text. `docs`, when given, gets one entry per heredoc in
    order: whether its body expands anything."""
    out, stack, pending, i, n = [], [], [], 0, len(command)
    while i < n:
        ch = command[i]
        top = stack[-1][0] if stack else None
        if top == "'":
            out.append(ch)
            if ch == "'":
                stack.pop()
            i += 1
            continue
        if ch == "\\":
            if command.startswith("\n", i + 1):
                i += 2
            else:
                out.append(command[i:i + 2])
                i += 2
            continue
        if top == '"':
            if ch == '"':
                stack.pop()
            elif command.startswith("$((", i):
                stack.append(["((", 0])
                out.append("$((")
                i += 3
                continue
            elif command.startswith("$(", i):
                stack.append(["$(", 0])
                out.append("$(")
                i += 2
                continue
            out.append(ch)
            i += 1
            continue
        if top == "((":
            if ch == ")" and stack[-1][1] == 0 and command.startswith("))", i):
                stack.pop()
                out.append("))")
                i += 2
                continue
            stack[-1][1] += {"(": 1, ")": -1}.get(ch, 0)
            out.append(ch)
            i += 1
            continue
        # A command: the top level, or inside $( ).
        at_word = i == 0 or command[i - 1] in WORD_START
        if ch in "'\"":
            stack.append([ch, 0])
        elif command.startswith("$'", i) and ansi_c(command, i):
            word, i = ansi_c(command, i)
            out.append(word)
            continue
        elif command.startswith("$((", i) or (at_word and command.startswith("((", i)):
            k = 3 if ch == "$" else 2
            stack.append(["((", 0])
            out.append(command[i:i + k])
            i += k
            continue
        elif command.startswith("$(", i):
            stack.append(["$(", 0])
            out.append("$(")
            i += 2
            continue
        elif top == "$(" and ch in "()":
            if ch == "(":
                stack[-1][1] += 1
            elif stack[-1][1]:
                stack[-1][1] -= 1
            else:
                stack.pop()
        elif ch == "#" and at_word:
            j = command.find("\n", i)
            i = n if j < 0 else j
            continue
        elif command.startswith("<<", i) and not command.startswith("<<<", i):
            m = HEREDOC.match(command, i)
            if m:
                delim = next(g for g in m.group(2, 3, 4) if g is not None)
                quoted = m.group(4) is None or command[m.start(4) - 1] == "\\"
                pending.append((delim, bool(m.group(1)), quoted))
                out.append(m.group(0))
                i = m.end()
                continue
        elif ch == "\n":
            out.append(";" if not stack else "\n")
            i += 1
            while pending:
                delim, dash, quoted = pending.pop(0)
                expands = False
                while i < n:
                    j = command.find("\n", i)
                    line, i = (command[i:], n) if j < 0 else (command[i:j], j + 1)
                    if (line.lstrip("\t") if dash else line) == delim:
                        break
                    expands = expands or (not quoted and bool(re.search(r"[$`\\]", line)))
                if docs is not None:
                    docs.append(expands)
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def segments(command, seps=None, targets=None):
    """The simple commands in a shell command, each a list of words, with redirections dropped, and
    "(" and ")" where a subshell opens and closes. `seps`, when given, gets one entry per entry
    returned: for a simple command, the operators before and after it, such as `&&` or `|`, with ""
    at either end or at a parenthesis; None for a parenthesis. `targets`, when given, gets an
    (operator, target) pair for each `>` redirection. Raises ValueError when the command cannot be split, an unclosed quote for one."""
    lexer = shlex.shlex(prepare(command), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    segs, cur, skip, before = [], [], False, ""
    seps = [] if seps is None else seps
    targets = [] if targets is None else targets
    for tok in lexer:
        if skip:
            if ">" in skip:
                targets.append((skip, norm_name(tok)))
            skip = False
            continue
        if tok and set(tok) <= set("();<>|&"):
            if "<" in tok or ">" in tok:
                if cur and cur[-1].isdigit():
                    cur.pop()
                skip = (not tok.endswith("&") or tok in ("<&", ">&")) and tok
                continue
            op = tok.strip("()")
            for c in tok:
                if cur:
                    segs.append(cur)
                    seps.append((before, op))
                cur = []
                if c in "()":
                    segs.append(c)
                    seps.append(None)
            before = op
            continue
        cur.append(tok)
    if cur:
        segs.append(cur)
        seps.append((before, ""))
    return segs


def norm_name(word):
    return re.sub(r"\$\{(\w+)\}", r"$\1", word)


def written_here(command):
    """The files `command` writes with `>` from its own text alone, as `cat > "$M" <<'EOF'`: a bare
    `cat` whose only input is a heredoc that expands nothing, or `echo` or `printf` whose words
    expand nothing. The scan reads that text as the command's, so it has seen all such a file
    holds. A name is left out when the command names it anywhere else, other than as the file a
    `-F`, `--file`, `--body-file`, `--notes-file` or `--input` reads, when that is before its write,
    or when it is a variable the command assigns more than once. A shell function or alias that
    shadows `cat`, `echo` or `printf` is not followed."""
    heredocs = []
    lexer = shlex.shlex(prepare(command, heredocs), posix=False, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        raw = list(lexer)
        tokens = [t if set(t) <= set("();<>|&") else "".join(shlex.split(t)) for t in raw]
    except ValueError:
        return frozenset()
    safe, unsafe, first_write = set(), set(), {}
    words, writes, inputs, op, k = [], [], [], None, 0

    def close():
        name = list(words)
        while name and re.match(r"[A-Za-z_][A-Za-z0-9_]*=", name[0]):
            name.pop(0)
        ok = (name[:1] in (["echo"], ["printf"]) and not any(re.search(r"[$`]", w) for w in name[1:])) or (
            name in (["cat"], ["cat", "-"]) and inputs == [False])
        for o, target, at in writes:
            (safe if ok and o in (">", ">|") else unsafe).add(target)
            first_write.setdefault(target, at)

    targets = set()
    for at, tok in enumerate(tokens):
        if op:
            if op == "<<":
                inputs.append(heredocs[k] if k < len(heredocs) else True)
                k += 1
            elif "<" in op:
                inputs.append(True)
            else:
                writes.append((op, norm_name(tok), at))
                targets.add(at)
            op = None
            continue
        if raw[at] and set(raw[at]) <= set("();<>|&"):
            if "<" in tok or ">" in tok:
                if words and words[-1].isdigit():
                    tok = words.pop() + tok
                op = tok if not tok.endswith("&") or tok in ("<&", ">&") else None
                continue
            close()
            words, writes, inputs = [], [], []
            continue
        words.append(tok)
    close()
    if k != len(heredocs):
        return frozenset()
    readers = {"-F", "--file", "--body-file", "--notes-file", "--input"}
    for name in safe - unsafe:
        var = name[1:] if re.fullmatch(r"\$\w+", name) else None
        assigned = sum(1 for t in tokens if var and t.startswith(var + "="))
        for at, tok in enumerate(tokens):
            if at in targets or name not in norm_name(tok):
                continue
            if norm_name(tok) != name or at == 0 or tokens[at - 1] not in readers or at < first_write[name]:
                unsafe.add(name)
        if assigned > 1:
            unsafe.add(name)
    return frozenset(safe - unsafe)


UNRESOLVED = None


def resolve(cwd, path):
    if cwd is UNRESOLVED or re.search(r"[$`*?]", path) or path == "-":
        return UNRESOLVED
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))


def unwrap(words):
    """The command `timeout`, `nice`, `nohup` or `xargs` runs, and whether `xargs` runs it, so its
    arguments are not all in the command."""
    via_xargs = False
    while words:
        name = os.path.basename(words[0])
        if name == "nohup":
            words = words[1:]
        elif name == "nice":
            words = words[1:]
            if words[:1] == ["-n"]:
                words = words[2:]
            elif words and re.fullmatch(r"-n?-?\d+|--adjustment=\S+", words[0]):
                words = words[1:]
        elif name in ("timeout", "xargs"):
            with_arg = TIMEOUT_WITH_ARG if name == "timeout" else XARGS_WITH_ARG
            words = words[1:]
            while words and words[0].startswith("-") and words[0] != "-":
                w = words.pop(0)
                if w == "--":
                    break
                if w in with_arg and words:
                    words.pop(0)
            if name == "timeout":
                words = words[1:]
            else:
                via_xargs = True
        else:
            break
    return words, via_xargs


ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.S)
VARIABLE = re.compile(r"\$(?:\{(\w+)\}|(\w+))")


def assignments(words):
    """The (name, value) pairs of a segment that only sets variables, as `S=/tmp/x` or
    `export S=/tmp/x`, or None for any other segment."""
    if words[:1] == ["export"]:
        words = words[1:]
    pairs = [ASSIGNMENT.fullmatch(w) for w in words]
    return [m.groups() for m in pairs] if words and all(pairs) else None


def expand(word, shellvars):
    """`word` with each `$NAME` or `${NAME}` the command set to a literal value replaced by it, or
    as written when that would be longer than LITERAL_LIMIT."""
    full = VARIABLE.sub(lambda m: shellvars.get(m.group(1) or m.group(2)) or m.group(0), word)
    return word if len(full) > LITERAL_LIMIT else full


def quoted_refs(text):
    """The names a `$` refers to inside single quotes or after a backslash, which the shell leaves
    as written."""
    names, quote, i = set(), None, 0
    while i < len(text):
        ch = text[i]
        if quote == "'":
            if ch == "'":
                quote = None
            elif ch == "$" and VARIABLE.match(text, i):
                m = VARIABLE.match(text, i)
                names.add(m.group(1) or m.group(2))
        elif ch == "\\":
            m = VARIABLE.match(text, i + 1)
            if m:
                names.add(m.group(1) or m.group(2))
            i += 1
        elif ch == "'" and quote is None:
            quote = "'"
        elif ch == '"':
            quote = None if quote == '"' else '"'
        i += 1
    return names


# A segment led by one of these may skip, repeat or make an assignment in a way plan does not
# follow, so plan expands nothing from there on.
CONTROL = {"if", "then", "else", "elif", "do", "while", "until", "for", "case", "select", "{", "!",
           "function", "eval", "source", ".", "trap"}
# A builtin that may set a variable by a name it is given or makes at run time, as `read S`,
# `declare -n R=S` or `printf -vS`; a command that runs one follows no variable.
NAMING = {"declare", "typeset", "local", "readonly", "read", "mapfile", "readarray", "unset", "let",
          "getopts"}
# The names the shell sets or reads itself, which an assignment does not hold.
SPECIAL = {"PWD", "OLDPWD", "REPLY", "OPTARG", "OPTIND", "MAPFILE", "IFS", "HOME", "PATH", "CDPATH",
           "RANDOM", "SECONDS", "LINENO", "PPID", "UID", "EUID", "SHLVL", "PIPESTATUS", "FUNCNAME",
           "GROUPS", "HISTCMD", "SRANDOM", "EPOCHSECONDS", "EPOCHREALTIME", "COLUMNS", "LINES",
           "argv", "path", "cdpath", "fpath", "status", "pipestatus", "match", "MATCH", "reply"}
LITERAL_LIMIT = 4096


def command_word(words):
    """The command a segment runs, past its assignments and the words that run another command."""
    i = 0
    while i < len(words) and (ASSIGNMENT.fullmatch(words[i]) or words[i] in SHELL_WORDS):
        i += 1
    return os.path.basename(words[i]) if i < len(words) else ""


def followable(command, segs, seps):
    """The variables plan expands. Each is set exactly once, by a segment of its own that runs
    whenever the `&&` chain it is in gets that far: after the start, `;`, `&&` or `(`, and not
    piped or sent to the background, and written unquoted. None is bound any other way (`for`,
    `S+=`, `S[0]=`, a prefix `S=x cmd`), is a name the shell sets itself, or is written inside
    single quotes or after a backslash. A command that defines a function, binds IFS, runs a NAMING
    builtin, `printf -v` or an `export` of a name it makes at run time follows none."""
    text = prepare(command)
    if re.search(r"\bIFS\b", command) or re.search(r"\w\s*\(\s*\)", text):
        return set()
    names, bindings = set(), collections.Counter()
    for words, sep in zip(segs, seps):
        if sep is None:
            continue
        cmd = command_word(words)
        if cmd in NAMING or (cmd == "printf" and any(w.startswith("-v") for w in words)) or (
                cmd == "export" and any(re.search(r"[$`]", w.split("=", 1)[0]) for w in words)):
            return set()
        if sep[0] in ("", ";", "&&") and sep[1] in ("", ";", "&&", "||"):
            names.update(n for n, _ in assignments(words) or [])
        for w in words:
            bound = set(re.findall(r"(?<![\w$])([A-Za-z_]\w*)(?:\[[^]]*\])?\+?=", w))
            bound.update(re.findall(r"^([A-Za-z_]\w*)$", w))
            bindings.update(bound)
    return {n for n in names if bindings[n] == 1 and n not in SPECIAL and re.match(r"[A-Za-z]", n)
            and not re.match(r"BASH|ZSH", n) and re.search(rf"(?:^|[\s;&|(]){n}=", text)} - quoted_refs(text)


def plan(command, cwd, budget, depth=0):
    """What a shell command does that the scan reads: [("git", dir, env, words, via_xargs),
    ("gh", dir, words)], in order, following `cd`, a subshell's own `cd`, `bash -c` and the
    commands `timeout`, `nice`, `nohup` and `xargs` run. A variable `followable` names, set to a
    value that is literal once the variables before it are expanded, is expanded after it in a
    `cd` and in git's options before its subcommand. In the other git and gh words, which name the
    files a commit or post reads, it is expanded only when no `>` in the command writes a file,
    since a file the command writes is judged by its name as written; any other variable is left
    as written."""
    steps, saved, shellvars, git_env, seps, targets = [], [], {}, {}, [], []
    segs = segments(command, seps, targets)
    follow = followable(command, segs, seps)
    files = all(t in ("-", "/dev/null", "/dev/stdout", "/dev/stderr") or (op == ">&" and t.isdigit())
                for op, t in targets) and not any(
        ">" in w and (re.search(r"\$\(|`", w) or command_word(seg) in ("bash", "sh", "zsh"))
        for seg in segs if seg not in ("(", ")") for w in seg)

    def args(words):
        if files:
            return [expand(w, shellvars) for w in words]
        out, i = [], 0
        while i < len(words) and words[i].startswith("-"):
            out.append(expand(words[i], shellvars))
            if words[i] in GIT_GLOBAL_WITH_ARG and i + 1 < len(words):
                i += 1
                out.append(expand(words[i], shellvars))
            i += 1
        return out + words[i:]

    for words in segs:
        if words == "(":
            saved.append((cwd, dict(shellvars)))
            continue
        if words == ")":
            cwd, shellvars = saved.pop() if saved else (cwd, shellvars)
            continue
        if words[0] in CONTROL:
            follow, shellvars = set(), {}
        pairs = assignments(words)
        if pairs is not None:
            for name, value in pairs:
                if name.startswith("GIT_"):
                    git_env[name] = value
                if name in follow:
                    value = expand(value, shellvars)
                    literal = len(value) <= LITERAL_LIMIT and re.fullmatch(r"/[\w./+-]*", value)
                    shellvars[name] = value if literal else None
            continue
        env = dict(git_env)
        while words and (re.match(r"[A-Za-z_][A-Za-z0-9_]*=", words[0]) or words[0] in SHELL_WORDS):
            if "=" in words[0] and words[0] not in SHELL_WORDS:
                k, v = words[0].split("=", 1)
                env[k] = v
            words = words[1:]
        if words and words[0] == "env":
            words = words[1:]
            while words and (words[0].startswith("-") or "=" in words[0]):
                if "=" in words[0] and not words[0].startswith("-"):
                    k, v = words[0].split("=", 1)
                    env[k] = v
                words = words[1:]
        words, via_xargs = unwrap(words)
        if not words:
            continue
        name = os.path.basename(words[0])
        if name in CONTROL:
            follow, shellvars = set(), {}
        inner = next((i for i, w in enumerate(words[1:-1], 1) if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", w)), None)
        if name in ("cd", "pushd"):
            target = expand(words[1], shellvars) if len(words) > 1 else "~"
            cwd = resolve(cwd, target)
        elif name == "popd":
            cwd = UNRESOLVED
        elif name in ("bash", "sh", "zsh") and inner and depth < 3:
            steps += plan(words[inner + 1], cwd, budget, depth + 1)
        elif name == "git":
            steps.append(("git", cwd, env, args(words[1:]), via_xargs))
        elif name == "gh":
            steps.append(("gh", cwd, [expand(w, shellvars) for w in words[1:]] if files else words[1:]))
    return steps


def git_call(cwd, env, args):
    """The repository a git call acts in, as a (directory, global options) pair or None when it
    cannot be resolved, its subcommand and arguments, and the settings its `-c` options make."""
    opts, config = [], {}
    if cwd is UNRESOLVED or any(k in env for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")):
        cwd = UNRESOLVED
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        name, eq, value = a.partition("=")
        if name in GIT_GLOBAL_WITH_ARG and not eq and a != "--exec-path":
            if i + 1 >= len(args):
                return None, None, [], config
            value, i = args[i + 1], i + 1
        if name == "-C":
            cwd = resolve(cwd, value)
        elif name == "-c" and "=" in value:
            k, v = value.split("=", 1)
            config[k.lower()] = v
        elif name in ("--git-dir", "--work-tree"):
            path = resolve(cwd, value) if cwd is not UNRESOLVED else UNRESOLVED
            if path is UNRESOLVED:
                cwd = UNRESOLVED
            else:
                opts.append(f"{name}={path}")
        i += 1
    if i >= len(args):
        return None, None, [], config
    repo = None if cwd is UNRESOLVED else (cwd, tuple(opts))
    return repo, args[i], args[i + 1:], config


def alias_of(repo, sub, budget, config=None):
    """What `git <sub>` runs when `sub` is an alias, set by a `-c` option or in the repository's
    configuration: its words, ["!"] for a shell alias, or None."""
    if sub in GIT_COMMANDS:
        return None
    value = (config or {}).get(f"alias.{sub}".lower())
    if value is None:
        if repo is None:
            return None
        try:
            value = git(repo, "config", "--get", f"alias.{sub}", budget=budget).strip()
        except BudgetSpent:
            raise
        except ScanError:
            return None
    if value.startswith("!"):
        return ["!"] + value[1:].split()
    try:
        return shlex.split(value)
    except ValueError:
        return ["!"]


def commit_scope(args):
    """What a `git commit` with these arguments takes beyond the staged changes: (None, files)
    when it takes no unstaged change, ("all", files) for -a or --patch, or (paths, files) for a
    commit naming paths; `files` are its -F message files. Returns None for a dry run."""
    unstaged, paths, files, i = None, [], [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            paths += args[i + 1:]
            break
        if a.startswith("--"):
            name, eq, value = a.partition("=")
            if name == "--dry-run":
                return None
            if name in ("--all", "--patch", "--interactive", "--pathspec-from-file"):
                unstaged = "all"
            if name in COMMIT_LONG_WITH_ARG and not eq and i + 1 < len(args):
                value, i = args[i + 1], i + 1
            if name == "--file":
                files.append(value)
        elif a.startswith("-") and len(a) > 1:
            for j, c in enumerate(a[1:], 1):
                if c in ("a", "p"):
                    unstaged = "all"
                if c in COMMIT_SHORT_WITH_ARG:
                    value = a[j + 1:]
                    if not value and i + 1 < len(args):
                        value, i = args[i + 1], i + 1
                    if c == "F":
                        files.append(value)
                    break
                if c in ("S", "u"):
                    break
        else:
            paths.append(a)
        i += 1
    if unstaged is None and paths:
        unstaged = paths
    return unstaged, files


def add_scope(args):
    """What a `git add` with these arguments stages: (paths or None for all, takes untracked,
    takes ignored), or None when it stages nothing the scan reads."""
    paths, everything, update, force, i = [], False, False, False, 0
    while i < len(args):
        a = args[i]
        if a == "--":
            paths += args[i + 1:]
            break
        if a.startswith("--"):
            name, eq, _ = a.partition("=")
            if name == "--dry-run":
                return None
            everything |= name in ("--all", "--no-ignore-removal", "--pathspec-from-file")
            update |= name == "--update"
            force |= name == "--force"
            if name in ADD_LONG_WITH_ARG and not eq:
                i += 1
        elif a.startswith("-") and len(a) > 1:
            if "n" in a:
                return None
            everything |= "A" in a
            update |= "u" in a
            force |= "f" in a
        else:
            paths.append(a)
        i += 1
    if paths:
        return paths, not update, force
    if everything:
        return None, True, force
    if update:
        return None, False, force
    return None


def scan_commit(command, cwd, budget):
    """The findings in what the git commits in `command` would carry, or None when it runs no
    commit. Raises ScanError when a commit's repository cannot be resolved or read."""
    steps = plan(command, cwd, budget)
    commits, adds = [], []
    for step in steps:
        if step[0] != "git":
            continue
        _, at, env, args, via_xargs = step
        repo, sub, rest, config = git_call(at, env, args)
        if sub is None:
            continue
        alias = alias_of(repo, sub, budget, config)
        if alias and alias[0] == "!":
            if "commit" in alias:
                raise ScanError(f"`git {sub}` is a shell alias that commits, which the scan cannot follow")
            continue
        if alias:
            sub, rest = alias[0], alias[1:] + rest
        if sub == "commit":
            if repo is None:
                raise ScanError("the scan cannot tell which repository this commit is in")
            commits.append((repo, rest + ["-a"] if via_xargs else rest))
        elif sub == "add":
            # The paths xargs passes are not in the command, so the add may take any file.
            adds.append((repo, rest + ["-A"] if via_xargs else rest))
    if not commits:
        return None
    if any(repo is None for repo, _ in adds):
        raise ScanError("the scan cannot tell which repository a `git add` in this command is in")
    found = [f + " (command text)" for f in scan_text(command, "command")]
    own = written_here(command)
    for repo, rest in commits:
        scope = commit_scope(rest)
        if scope is None:
            continue
        unstaged, files = scope
        check_repository(repo, budget)
        found += scan_staged(repo, budget)
        if unstaged is not None:
            found += scan_unstaged(repo, None if unstaged == "all" else unstaged, budget)
        for f in files:
            found += [x + " (message file)" for x in scan_existing(repo[0], f, budget, own)]
    for repo, rest in adds:
        scope = add_scope(rest)
        if scope is None:
            continue
        paths, untracked, ignored = scope
        check_repository(repo, budget)
        found += scan_unstaged(repo, paths, budget)
        if untracked:
            found += scan_untracked(repo, paths, ignored, budget)
    return sorted(set(found))


def gh_words(args):
    """The subcommand words of a `gh` call, `pr create` for `gh -R o/r pr create --title x`."""
    words, i = [], 0
    while i < len(args) and len(words) < 2:
        if args[i] in ("-R", "--repo"):
            i += 1
        elif not args[i].startswith("-"):
            words.append(args[i])
        i += 1
    return tuple(words)


def gh_files(args, api):
    """The files a `gh` write sends: --body-file, --notes-file, --input, a `field=@file` value of
    `gh api`'s -F or --field, -F <file> elsewhere, and a gist's files."""
    files, i = [], 0
    while i < len(args):
        a = args[i]
        name, eq, value = a.partition("=")
        if name in ("--body-file", "--notes-file", "--input", "-F", "--field") or re.match(r"-F.", a):
            if re.match(r"-F.", a):
                value = a[2:]
            elif not eq and i + 1 < len(args):
                value, i = args[i + 1], i + 1
            if name in ("--body-file", "--notes-file", "--input"):
                files.append(value)
            elif "=@" in value:
                files.append(value.split("=@", 1)[1])
            elif not api and name != "--field":
                files.append(value)
        i += 1
    if gh_words(args) == ("gist", "create"):
        rest, i = [], 0
        while i < len(args):
            if args[i] in ("-d", "--desc", "-f", "--filename"):
                i += 1
            elif not args[i].startswith("-") or args[i] == "-":
                rest.append(args[i])
            i += 1
        files += rest[2:]
    return files


def scan_gh(command, cwd, budget):
    """The findings in what the `gh` writes in `command` would send, or None when it sends none."""
    found, writes = [], False
    own = written_here(command)
    for step in plan(command, cwd, budget):
        if step[0] != "gh":
            continue
        _, at, args = step
        api = gh_words(args)[:1] == ("api",)
        if api:
            sends = any(a.split("=", 1)[0] in ("-f", "-F", "--field", "--raw-field", "--input")
                        or re.match(r"-[fF].", a) for a in args)
            method = next((args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-X", "--method")), "")
            if not sends and method.upper() not in ("POST", "PATCH", "PUT"):
                continue
        elif gh_words(args) not in GH_WRITES:
            continue
        writes = True
        for f in gh_files(args, api):
            found += [x + " (file the command sends)" for x in scan_existing(at, f, budget, own)]
    if not writes:
        return None
    found += [f + " (command text)" for f in scan_text(command, "command")]
    return sorted(set(found))


# --- The hook ------------------------------------------------------------------------------------

def strings(value, path=""):
    """Each string in a tool's input with the path to it, such as `files[0].content`."""
    if isinstance(value, str):
        yield path or "input", value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from strings(v, f"{path}[{i}]")


def decide(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}}))


def is_write(tool):
    if not tool.startswith("mcp__") or "__" not in tool[5:]:
        return False
    server, op = tool[5:].rsplit("__", 1)
    if re.match(r"(?:jira|confluence)_", op):
        return not ATLASSIAN_READ.match(op)
    return "github" in server.lower() and not GITHUB_READ.match(op)


def hook(payload, budget=None):
    budget = budget or Budget()
    try:
        event = json.loads(payload)
        tool = event["tool_name"]
        tool_input = event.get("tool_input") or {}
    except (ValueError, KeyError, TypeError):
        decide("ask", "The secret scan could not read this call, so nothing was checked for credentials. "
                      "Allow it only if you know it carries none.")
        return
    if tool == "Bash":
        command = tool_input.get("command", "")
        if not isinstance(command, str):
            return
        cwd = event.get("cwd") or os.getcwd()
        try:
            commit = scan_commit(command, cwd, budget)
            sent = scan_gh(command, cwd, budget)
        except ValueError:
            if re.search(r"\bgit\b[\s\S]*\bcommit\b", command) or GH_WRITE_TEXT.search(command):
                decide("ask", "The secret scan could not read this command (an unclosed quote, perhaps), "
                              "so a commit or post in it was not checked for credentials. Allow it only "
                              "if you know it carries none.")
            return
        except ScanError as e:
            decide("ask", f"The secret scan could not check this command: {e}. "
                          "Allow it only if you know it carries no credential.")
            return
        if commit is None and sent is None:
            return
        found = (commit or []) + (sent or [])
        what = "This command"
    elif is_write(tool):
        op = tool.rsplit("__", 1)[-1]
        try:
            found = []
            for where, text in strings(tool_input):
                budget.spend(len(text))
                found += scan_text(text, where)
        except ScanError as e:
            decide("ask", f"The secret scan could not check this {op} call: {e}. "
                          "Allow it only if you know it carries no credential.")
            return
        what = f"This {op} call"
    else:
        return
    if found:
        listed = "; ".join(found[:10]) + (f"; and {len(found) - 10} more" if len(found) > 10 else "")
        decide("deny", f"{what} would carry what looks like a credential: {listed}. Remove it, and "
                       "rotate it if it was ever pushed or posted. If it is not a credential, the "
                       "person can commit or post it outside Claude.")


def main(argv):
    if not argv or argv[0] not in ("files", "diff", "hook"):
        print(__doc__, file=sys.stderr)
        return 2
    if argv[0] == "hook":
        hook(sys.stdin.read())
        return 0
    try:
        if argv[0] == "files":
            found = [f for p in argv[1:] for f in scan_file(p)]
        else:
            repo = (os.getcwd(), ())
            check_repository(repo, None)
            found = sorted(set(scan_staged(repo, None) + scan_unstaged(repo, None, None, " (unstaged)")))
    except ScanError as e:
        print(f"secret_scan: {e}", file=sys.stderr)
        return 2
    for f in found:
        print(f)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
