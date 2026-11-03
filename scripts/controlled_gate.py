#!/usr/bin/env python3
"""Ask the person before a tool reads past the first line of a `.review/` file marked controlled.

    controlled_gate.py pre     read a PreToolUse payload on stdin and print the decision
    controlled_gate.py post    read a PostToolUse payload on stdin and record what it cleared

skills/writing/references/short.md, "Controlled content", owns the rule: a file under `.review/`
written from an item that warns it is controlled opens with `Controlled: <key or ID> — <the
warning>`, and nothing past that line is read until the person clears the item. A model can miss
the rule; this hook makes the stop one the person sees. It asks through Claude Code's own
permission prompt, naming the item and its warning, so the person, not the model, opens the file.

A file is held when a component of its path, as named or as resolved through symlinks, is
`.review` (in any case, since macOS opens `.REVIEW` as `.review`), and its first line starts with
`Controlled:`. A call reads one when:
- Read, Edit, MultiEdit or NotebookEdit names it; a Read of the first line alone (`limit` 1 from
  the start) does not, nor does a Write whose content opens with the file's own first line;
- Grep in `content` mode names it, or a directory inside a `.review/` tree holding one;
- a Bash command names it, or a directory inside a `.review/` tree holding one, as a word,
  after `=`, glued to a one-letter option, or inside a word such as a `-c` script, in one of its
  simple commands (split at `&&`, `||`, `;`, `|`, `&`, parentheses and newlines, words as the shell
  quotes them) that may show a file's text. A simple command shows none when it is in QUIET (`ls`,
  `rm`, `echo` and the like), `find` with no `-exec`, `git status`, a `git commit` with no `-F`,
  `-C` or template, or an exact first-line read (`head -1 F`, `head -n 1 F`, `head -n1 F`,
  `head --lines=1 F`, `sed -n 1p F`, `sed 1q F`), and has no command substitution and no
  redirect but to /dev/null or another descriptor; in a pipeline with `xargs`, every command may.

Clearance is per item, per session. When such a call has run, which it does only after the
person's yes, `post` records its items in `controlled-cleared.json` in that `.review/` tree under
the session's id, and `pre` lets later calls in the same session that read only those items
through. A Write of a `.review/` file whose content opens with a `Controlled:` line records its
item too, since only a session already holding the item's text writes that line. Another
session's id replaces the record, so a new session asks again.

It is a stop for a mistake, not a lock: a path built from a variable, a program that opens a path
the command does not name, and a recursive read from above `.review/` are not seen, and the record
is a file the session could write.

`pre` and `post` always exit 0. `pre` prints `ask` naming the held file and its first line, which
holds only the key and the warning, or `ask` when the payload cannot be read; otherwise nothing,
which lets the call through. hooks/controlled-gate.sh asks when `pre` fails or prints something it
cannot read.
"""
import glob
import itertools
import json
import os
import re
import shlex
import sys

MARK = "Controlled:"
RECORD = "controlled-cleared.json"
WALK_LIMIT = 5000     # files looked at under one `.review/` before the check counts it as holding one
GLOB_LIMIT = 500      # paths one glob may expand to before the check asks
FIRST_LINE = (["-1"], ["-n", "1"], ["-n1"], ["--lines=1"])
QUIET = {"ls", "stat", "test", "du", "mkdir", "rmdir", "rm", "touch", "mv", "realpath", "echo",
         "printf", "pwd", "true", "false", "which", "basename", "dirname"}  # show no file's text
OPERATORS = {"&&", "||", ";", ";;", "|", "|&", "&", "(", ")", "\n"}
REVIEW_PATH = re.compile(r"(?:[\w.~/+-]*/)?\.review(?:/[^\s'\"`;|&<>()]*)?(?![\w.-])", re.IGNORECASE)
TOO_MANY = "too many to check"


def decide(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "ask",
                                             "permissionDecisionReason": reason}}))


def review_root(path):
    """The `.review` directory a path sits under, as named, or None."""
    parts = os.path.abspath(path).split(os.sep)
    lower = [part.lower() for part in parts]
    return os.sep.join(parts[:lower.index(".review") + 1]) if ".review" in lower else None


def first_line(path):
    """The held file's first line, or None when `path` is not a held file."""
    real = os.path.realpath(path)
    if not review_root(path) and not review_root(real):
        return None
    if not os.path.isfile(real):
        return None
    try:
        with open(real, "rb") as f:
            head = f.read(512).split(b"\n", 1)[0]
    except OSError:
        return None
    line = head.decode("utf-8", "replace").lstrip("﻿").rstrip("\r")
    return line[:200] if line.startswith(MARK) else None


def item_of(line):
    return line[len(MARK):].strip().split(" — ")[0].split(" - ")[0].strip() or line


def held_under(directory):
    """The held files under a directory inside a `.review/` tree, as (path, first line)."""
    found, seen = [], 0
    for root, _, names in os.walk(directory):
        for name in names:
            seen += 1
            if seen > WALK_LIMIT:
                return found + [(directory, TOO_MANY)]
            path = os.path.join(root, name)
            line = first_line(path)
            if line:
                found.append((path, line))
    return found


def segments(command):
    """The simple commands in a shell command line, each as (words, redirects, piped to xargs), or
    None when the line cannot be split."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace, lexer.whitespace_split, lexer.commenters = " \t\r", True, ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    out, words, redirects, i = [], [], [], 0
    while i < len(tokens):
        token = tokens[i]
        if token in OPERATORS:
            out.append((words, redirects, token))
            words, redirects = [], []
        elif set(token) <= set("<>&|") and set(token) & set("<>"):
            if words and words[-1].isdigit():
                words.pop()
            redirects.append((token, tokens[i + 1] if i + 1 < len(tokens) else ""))
            i += 1
        else:
            words.append(token)
        i += 1
    out.append((words, redirects, ""))
    result, pipeline = [], []
    for words, redirects, sep in out:
        pipeline.append((words, redirects))
        if sep not in ("|", "|&"):
            xargs = any(w[:1] == ["xargs"] for w, _ in pipeline)
            result += [(w, r, xargs) for w, r in pipeline if w or r]
            pipeline = []
    return result


def quiet(words, redirects):
    """Whether a simple command shows no file's text: a QUIET command, `find` with no `-exec`,
    `git status`, `git commit -m`, or an exact first-line read, with no command substitution and no
    redirect but to /dev/null or another descriptor."""
    if any(op not in (">", ">>", "&>", ">|", ">&") or not (target == "/dev/null" or target.isdigit())
           for op, target in redirects):
        return False
    if not words or any("$(" in w or "`" in w or "<(" in w for w in words):
        return not words
    name, args = words[0], words[1:]
    if name in QUIET:
        return True
    if name == "find":
        return not any(a.startswith(("-exec", "-ok", "-fprint", "-fls", "-delete")) for a in args)
    if name == "git":
        while len(args) > 1 and args[0] == "-C":
            args = args[2:]
        if args[:1] == ["status"]:
            return True
        if args[:1] == ["commit"]:
            return not any(a.startswith(("-F", "--file", "-C", "-c", "--reuse", "--reedit", "-t", "--template"))
                           for a in args[1:])
        return False
    return len(words) > 1 and ((name == "head" and words[1:-1] in FIRST_LINE)
                               or (name == "sed" and words[1:-1] in (["-n", "1p"], ["1q"])))


def candidates(word):
    """The paths a command word may name: itself, its value after `=`, and the rest of a word glued
    to a one-letter option (`-fX` names X)."""
    found = {word}
    if "=" in word:
        found.add(word.split("=", 1)[1])
    if re.match(r"-[A-Za-z]", word) and len(word) > 2:
        found.add(word[2:])
    return found


def named(path):
    """The held files a named path is, or holds when it is a directory inside `.review/`."""
    line = first_line(path)
    if line:
        return [(path, line)]
    if os.path.isdir(path) and (review_root(path) or review_root(os.path.realpath(path))):
        return held_under(path)
    return []


def paths_named(word, cwd):
    """The paths a word may name, a glob expanded, or None when a glob expands past GLOB_LIMIT."""
    found = []
    for value in candidates(word) | {m.group(0) for m in REVIEW_PATH.finditer(word)}:
        if not value or "$" in value:
            continue
        path = os.path.join(cwd, os.path.expanduser(value))
        if re.search(r"[*?[]", value):
            paths = list(itertools.islice(glob.iglob(path, recursive=True), GLOB_LIMIT + 1))
            if len(paths) > GLOB_LIMIT:
                return None
            found += paths
        else:
            found.append(os.path.normpath(path))
    return found


def bash_reads(command, cwd):
    parts = segments(command)
    if parts is None:
        words = [m.group(0) for m in REVIEW_PATH.finditer(command)]
    else:
        words = [w for ws, rs, xargs in parts if xargs or not quiet(ws, rs) for w in ws + [t for _, t in rs]]
    found = {}
    for word in words:
        paths = paths_named(word, cwd)
        if paths is None:
            return [(os.path.join(cwd, word), TOO_MANY)]
        for path in paths:
            for held, line in named(path):
                found.setdefault(os.path.realpath(held), (held, line))
    return list(found.values())


def reads(tool, inp, cwd):
    """The held files a tool call reads, as (path, first line)."""
    if tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        target = inp.get("file_path") or inp.get("notebook_path") or ""
        line = first_line(os.path.join(cwd, target)) if target else None
        if not line:
            return []
        if tool == "Read" and inp.get("limit") == 1 and inp.get("offset") in (None, 0, 1):
            return []
        if tool == "Write" and isinstance(inp.get("content"), str):
            if inp["content"].split("\n", 1)[0].rstrip("\r").lstrip("﻿") == line:
                return []
        return [(os.path.join(cwd, target), line)]
    if tool == "Grep" and inp.get("output_mode") == "content":
        return named(os.path.normpath(os.path.join(cwd, inp.get("path") or ".")))
    if tool == "Bash":
        return bash_reads(inp.get("command") or "", cwd)
    return []


def record_path(path):
    root = review_root(path) or review_root(os.path.realpath(path))
    return os.path.join(root, RECORD) if root else None


def cleared(path, session):
    try:
        with open(record_path(path)) as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return set()
    if not isinstance(data, dict) or data.get("session_id") != session or not session:
        return set()
    return {k for k in data.get("cleared") or [] if isinstance(k, str)}


def record(found, session):
    by_file = {}
    for path, line in found:
        if line != TOO_MANY and record_path(path):
            by_file.setdefault(record_path(path), set()).add(item_of(line))
    for target, items in by_file.items():
        keys = sorted(cleared(target, session) | items)
        try:
            with open(target, "w") as f:
                json.dump({"session_id": session, "cleared": keys}, f)
        except OSError:
            pass


def reason(found, cwd):
    for path, line in found:
        if line == TOO_MANY:
            return (f"{path} holds more files than the controlled-file check can look at, so it "
                    "cannot tell whether one opens with Controlled:. Allow this only if it reads no "
                    "such file.")
    lines = sorted({line for _, line in found})
    items = ", ".join(item_of(line) for line in lines)
    shown = "; ".join(f"{os.path.relpath(path, cwd) if cwd else path} opens with \"{line}\""
                      for path, line in found[:3])
    more = f", and {len(found) - 3} more" if len(found) > 3 else ""
    return (f"This call reads what is written from {items}, marked controlled: {shown}{more}. Under "
            f"short.md's \"Controlled content\", nothing past that line is read until you clear it. "
            f"Allow this only if you want Claude to read {items}; once allowed, later reads of it in "
            "this session do not ask again.")


def payload(text):
    data = json.loads(text)
    tool, inp = data.get("tool_name") or "", data.get("tool_input") or {}
    cwd = data.get("cwd") or os.getcwd()
    if not isinstance(inp, dict) or not isinstance(cwd, str):
        raise ValueError
    for key in ("file_path", "notebook_path", "path", "command"):
        if key in inp and not isinstance(inp[key], str):
            raise ValueError
    return tool, inp, cwd, str(data.get("session_id") or "")


def pre(text):
    try:
        tool, inp, cwd, session = payload(text)
    except (ValueError, AttributeError):
        decide("The tool call could not be read, so the controlled-file check could not run.")
        return
    found = [(path, line) for path, line in reads(tool, inp, cwd)
             if line == TOO_MANY or item_of(line) not in cleared(path, session)]
    if found:
        decide(reason(found, cwd))


def post(text):
    try:
        tool, inp, cwd, session = payload(text)
    except (ValueError, AttributeError):
        return
    if not session:
        return
    found = reads(tool, inp, cwd)
    content = inp.get("content")
    if tool == "Write" and isinstance(content, str) and inp.get("file_path"):
        line = content.split("\n", 1)[0].rstrip("\r").lstrip("\ufeff")
        if line.startswith(MARK):
            found.append((os.path.join(cwd, inp["file_path"]), line[:200]))
    record(found, session)


def main(argv):
    if argv[1:] not in (["pre"], ["post"]):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    (pre if argv[1] == "pre" else post)(sys.stdin.read())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
