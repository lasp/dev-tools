#!/usr/bin/env python3
"""Print the last turns of a Claude Code session as plain text, with secrets and internal links removed.

The session is the JSONL transcript Claude Code writes for it: with `--file`, that file; otherwise
`projects/*/<CLAUDE_CODE_SESSION_ID>.jsonl` under `$CLAUDE_CONFIG_DIR`, or `~/.claude` when that
is unset. A turn is one message from the person and everything up to their next one. A message
from the person is a user entry whose `origin.kind` is `human`, a `queued_command` attachment
with that origin, typed while Claude was working, a typed slash command, an entry holding
`<command-name>`, or a `!` shell command, an entry holding `<bash-input>`. Claude Code writes the
last two with no `origin` (some versions mark a typed command `human`), and the skill body a
typed command expands to is a separate `isMeta` entry, dropped. A slash command is shown as the
command and its arguments, and a shell command as `! <command>`; its output is dropped. Of
everything else the excerpt keeps Claude's visible text and, for each tool call, the tool's name
alone, with the skill's name for a `Skill` call and the agent type for an `Agent` call.
`AskUserQuestion` is the one exception: its questions are kept, and the person's answers, with
any notes, from its result. A result Claude Code records as rejected (`User rejected tool use`,
or one saying the user doesn't want to proceed) shows the question as declined, and any other
error result as not shown. Other tool inputs and results, thinking, system reminders, hook
output, attachments, sidechain entries and the messages the harness sends as the user are
dropped.

`--turns N` keeps the last N turns (default 10); a session with fewer prints all it has. With
`--before-skill NAME`, the turns end before the last one in which skill NAME started, typed as
`/NAME` or `/<plugin>:NAME`, or called through the `Skill` tool, so the run asking for the excerpt
is not part of it. With `--max-chars N`, the oldest of those turns are dropped until the printed
excerpt, fence included, is N characters or fewer.

Before printing, each kept text is redacted, in this order: PEM and PGP private-key blocks, to
their END line or, with none, the rest of the BEGIN line and the base64, `Name: value` and blank
lines after it; GitHub, GitLab, Atlassian, AWS, Slack, Anthropic, OpenAI, Stripe, Google, npm,
PyPI and Hugging Face tokens, Slack webhook, workflow and trigger paths and JWTs; `Bearer` and
`Basic` credentials; an `Authorization:` or `Cookie:` header's value, a `token` scheme word kept,
where the header starts a line (after any indent or list marker) or follows a quote, `-H` or
`--header`; a URL's `user:password@`, the user possibly empty, to the last `@` before the host;
`curl -u user:password`; the value after `--password`, `mysql -p` and `sshpass -p`; `password=`,
`token=`, `secret=`, `api_key=`, `passphrase=`, `private_key=`, `account_key=` and `access_key=`
style assignments, and those whose key is `pass` or `pwd`, ends in `_pass`, `-pass`, `_pwd` or
`-pwd`, or is `pgpass` (`:` as well as `=`, the key in markdown emphasis, a code span or neither;
the key is kept, and a quoted value, with any one- or two-letter string prefix such as `b` or `r`,
is removed to its closing quote), but not a key ending in `tokens`, a count, and a bare `token:`
in prose loses the word after it, since a short token cannot be told from a word; any host under
the internal domains of the working directory's repository's standard and of the default
profile (`internal.domains`), with what follows it as a URL or an scp path, wherever it
sits, after an `@` included (as `<internal link>`), and a profile that cannot be read exits 1
before anything is printed; those are the only internal hosts it knows, so another project's hosts
pass through, and the person's preview of the excerpt is the check for them; and the person's home directory, in any case (as `~`), and in
Claude Code's dashed directory names, such as `-Users-name-repos-x` (as `-~`). Prints the excerpt to stdout inside one fenced `text` block, its
fence longer than any run of backticks in it, so GitHub neither renders it nor turns an `@login`
or `#n` in it into a mention or a link; to stderr, one line counting the turns and any dropped to
fit `--max-chars`, one with the excerpt's length in characters, and one counting each redaction
kind in the kept turns, zeros included. With `--stdin`, no transcript is read: the text on stdin
is redacted the same way and printed as it is, unfenced, with the redaction line on stderr.

Exits 1 with the reason on stderr when no session id is set and no `--file` is given, when no
transcript or more than one matches the session id, when the file cannot be read, is not UTF-8
or holds a line that is not a JSON object, when it holds no message from the person, when
`--turns` is below 1, when `--before-skill` names a skill the session never started, when the
newest turn alone is longer than `--max-chars`, and when an `AskUserQuestion` call's questions are
not a list of questions, nor a JSON string that parses to one, or its result is neither an error string nor a record with an answer to
each question under `answers` and, if present, a record of `annotations`, since either means
Claude Code changed the shape this script reads. Exits 2 when `--stdin` is given with `--file`,
`--before-skill` or `--max-chars`. Stdlib only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def internal_domains() -> list[str]:
    """The default profile's and the working directory's standard's internal domains together, and
    no other project's: a host only another standard names is not redacted. A file that cannot be
    read, or a standard not read, stops the script rather than letting an internal link through
    unredacted."""
    spec = importlib.util.spec_from_file_location("profile", ROOT / "scripts" / "profile.py")
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    try:
        values, sources, _ = profile.local(None, profile.owners(None))
        unread = [s for s in sources if s.endswith(profile.UNREAD)]
        if unread:
            raise profile.ProfileError(f"{unread[0]}, so its internal domains are not known")
        default = ROOT / profile.DEFAULT_PROFILE
        found = [(str(default), profile.parse(default.read_text(), str(default)))]
        if "internal" in values:
            found.append((" over ".join(sources), values))
        domains: set[str] = set()
        for name, data in found:
            section = data.get("internal")
            listed = section.get("domains") if isinstance(section, dict) else None
            if not isinstance(listed, list) or not all(isinstance(d, str) for d in listed):
                raise profile.ProfileError(f"{name}: internal.domains is {listed!r}, not a list")
            domains.update(listed)
        return sorted(domains)
    except (profile.ProfileError, OSError) as e:
        sys.exit(f"transcript_excerpt.py: internal links cannot be redacted: {e}")


# Any host under one of them, the longest first so one domain that ends another is tried whole;
# with none, a pattern that matches nothing.
DOMAINS = "|".join(re.escape(d) for d in sorted(internal_domains(), key=len, reverse=True)) or "(?!)"

DEFAULT_TURNS = 10
REDACTED = "<redacted>"
INTERNAL = "<internal link>"
REDACTIONS = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----(?:(?:(?!-----BEGIN ).)*?-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----"
            r"|[^\n]*(?:(?:\n[ \t]*)*\n(?:[A-Za-z0-9+/=]+|[\w-]+: [^\n]*)(?=\n|\Z))*)",
            re.S,
        ),
        REDACTED,
    ),
    ("github-token", re.compile(r"\b(?:gh[oprsu]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), REDACTED),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"), REDACTED),
    ("atlassian-token", re.compile(r"\bATATT[A-Za-z0-9_=-]{20,}"), REDACTED),
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), REDACTED),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), REDACTED),
    ("slack-webhook", re.compile(r"(\bhooks\.slack\.com/(?:services|workflows|triggers)/)[A-Za-z0-9/_-]+"), r"\g<1>" + REDACTED),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), REDACTED),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), REDACTED),
    ("stripe-key", re.compile(r"\b[rs]k_live_[A-Za-z0-9]{20,}"), REDACTED),
    ("google-key", re.compile(r"\bAIza[A-Za-z0-9_-]{35}"), REDACTED),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}"), REDACTED),
    ("pypi-token", re.compile(r"\bpypi-[A-Za-z0-9_-]{50,}"), REDACTED),
    ("huggingface-token", re.compile(r"\bhf_[A-Za-z0-9]{30,}"), REDACTED),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"), REDACTED),
    ("bearer", re.compile(r"\b(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.I), r"\g<1>" + REDACTED),
    ("basic-auth", re.compile(r"\b(Basic\s+)(?=[A-Za-z0-9+/]*[0-9+/=])[A-Za-z0-9+/]{8,}={0,2}"), r"\g<1>" + REDACTED),
    # The header starts a line, after any indent or list marker, or follows a quote, `-H` or `--header`.
    # The rest of its value is taken, to a quote or the line's end; a `token` scheme word is kept.
    (
        "auth-header",
        re.compile(
            r"""(?im)((?:^[ \t]*(?:[-*+>][ \t]+|\d+[.)][ \t]+)?|["']|(?<!\S)(?:-H|--header)(?:\s+|=))"""
            r"""(?:(?:proxy-)?authorization|(?:set-)?cookie)["']?\s*:\s*["']?(?!(?:bearer|basic)\s+<)(?:token\s+)?)"""
            r"""(?![<\s])[^\n"'<]*[^\s"'<]"""
        ),
        r"\g<1>" + REDACTED,
    ),
    ("url-credentials", re.compile(r"(?<=://)[^/\s:@]*:[^/\s]+(?=@)"), REDACTED),
    ("curl-user", re.compile(r"""((?:^|\s)(?:-u|--user)(?:\s+|=))(["']?)[^\s:"'<]+:[^\s"']+\2"""), r"\g<1>" + REDACTED),
    # MySQL's `-p<password>` is attached; a bare `-p` prompts. psql's `-p` is the port, so it is left alone.
    (
        "password-flag",
        re.compile(
            r"""((?:\b(?:mysql\w*|mariadb\w*)\b[^\n|;&]*?\s-p|\bsshpass\b[^\n|;&]*?\s-p\s*|(?:^|\s)--(?:password|passwd|passphrase)(?:\s+|=)))"""
            r"""(?:"[^"\n]*"|'[^'\n]*'|(?![<\s])\S+)"""
        ),
        r"\g<1>" + REDACTED,
    ),
    # A key may sit in markdown emphasis or a code span. A key ending in `tokens` is a count. A `token:`
    # in prose loses the word after it too, since a short token cannot be told from a word. The runs
    # around the keyword are bounded, so a long run of word characters takes linear time.
    (
        "assignment",
        re.compile(
            r"""(?i)\b((?:[\w-]{0,40}?(?:password|passwd|passphrase|token|secret|api[_-]?key|private[_-]?key|account[_-]?key|access[_-]?key)"""
            r"""[\w-]{0,40}(?<!tokens)|(?:[\w-]{0,40}?[_-]|pg)?(?:pass|pwd))[*_`]{0,3}["']?\s*[=:]\s*(?:[*_`]{1,3}\s*)?)"""
            r"""(?:(?:[bfru]{1,2})?(?:"(?!<)[^"\n]+"|'(?!<)[^'\n]+')|(?![<\s"'])[^\s"'&,;]*[^\s"'&,;.:!?)])"""
        ),
        r"\g<1>" + REDACTED,
    ),
    (
        "internal-link",
        re.compile(
            r"(?<![\w.-])(?:https?://)?(?:[\w-]+\.)*(?:" + DOMAINS + r")(?![\w-])(?::\d+)?"
            r"(?:/(?:[^\s)\]>\"'`]*[^\s)\]>\"'`.,;:!?])?|:(?=[\w~/])[^\s)\]>\"'`]*[^\s)\]>\"'`.,;:!?])?",
            re.I,
        ),
        INTERNAL,
    ),
)
SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
COMMAND_NAME = re.compile(r"<command-name>(.*?)</command-name>", re.S)
COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
LABELS = {"person": "Person:", "claude": "Claude:", "asked": "Claude asked:", "answered": "Person answered:"}
BASH_INPUT = re.compile(r"<bash-input>(.*?)</bash-input>", re.S)
BASH_OUTPUT = re.compile(r"<bash-(?:stdout|stderr)>.*?</bash-(?:stdout|stderr)>", re.S)


class ExcerptError(Exception):
    pass


def find_transcript(session_id: str | None, config_dir: Path) -> Path:
    """The one transcript named `<session_id>.jsonl` under `config_dir/projects/*/`."""
    if not session_id:
        raise ExcerptError("CLAUDE_CODE_SESSION_ID is not set; give the transcript with --file")
    matches = sorted((config_dir / "projects").glob(f"*/{session_id}.jsonl"))
    if not matches:
        raise ExcerptError(f"no transcript for session {session_id} under {config_dir / 'projects'}")
    if len(matches) > 1:
        listed = ", ".join(str(m) for m in matches)
        raise ExcerptError(f"{len(matches)} transcripts for session {session_id}: {listed}; give one with --file")
    return matches[0]


def read_entries(path: Path) -> list[dict]:
    try:
        # Newlines only: str.splitlines also splits on characters JSON leaves raw inside a string,
        # such as U+2028 among the bytes of a binary file a tool read.
        lines = path.read_text(encoding="utf-8").split("\n")
    except OSError as e:
        raise ExcerptError(f"cannot read {path}: {e.strerror}") from e
    except UnicodeDecodeError as e:
        raise ExcerptError(f"{path} is not UTF-8: byte {e.start} {e.reason}") from e
    entries = []
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            raise ExcerptError(f"{path}:{n} is not JSON: {e.msg}") from e
        if not isinstance(entry, dict):
            raise ExcerptError(f"{path}:{n} is not a JSON object")
        entries.append(entry)
    return entries


def text_of(content) -> str:
    """The text of a message's content, a string or a list of blocks, system reminders removed."""
    if isinstance(content, str):
        text = content
    else:
        text = "\n\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")
    return SYSTEM_REMINDER.sub("", text).strip()


def person_text(text: str) -> str:
    """A typed slash command as `/name args`, a shell command as `! command`; anything else as written."""
    shell = BASH_INPUT.search(text)
    if shell:
        return f"! {shell.group(1).strip()}"
    name = COMMAND_NAME.search(text)
    if not name:
        return BASH_OUTPUT.sub("", text).strip()
    args = COMMAND_ARGS.search(text)
    return f"{name.group(1).strip()} {args.group(1).strip() if args else ''}".strip()


def numbered(items: list[str]) -> str:
    return items[0] if len(items) == 1 else "\n" + "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))


def answers_of(questions: list[str], result) -> str:
    """The person's answer to each question, in the questions' order, with any notes; for a string
    result, which Claude Code writes for an error, whether the person declined."""
    if isinstance(result, str):
        declined = result.startswith("User rejected") or "doesn't want to proceed" in result
        return "none; the question was declined" if declined else "none; the question was not shown (a tool error)"
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise ExcerptError(f"an AskUserQuestion result has no answers record: {type(result).__name__}")
    answers = result["answers"]
    notes = result.get("annotations", {})
    if not isinstance(notes, dict):
        raise ExcerptError(f"an AskUserQuestion result's annotations are not a record: {type(notes).__name__}")
    out = []
    for q in questions:
        if q not in answers:
            raise ExcerptError(f"an AskUserQuestion result has no answer for the question {q!r}")
        answer = str(answers[q])
        note = (notes.get(q) or {}).get("notes") if isinstance(notes.get(q), dict) else None
        out.append(f"{answer} (note: {note})" if note else answer)
    return numbered(out)


def tool_label(block: dict) -> str:
    name = block.get("name", "?")
    tool_input = block.get("input") or {}
    detail = tool_input.get("skill") if name == "Skill" else tool_input.get("subagent_type") if name in ("Agent", "Task") else None
    return f"{name} ({detail})" if detail else name


def skill_matches(started: str, skill: str) -> bool:
    started = started.lstrip("/").split()[0] if started.strip() else ""
    return started == skill or started.rsplit(":", 1)[-1] == skill


def events(entries: list[dict]) -> list[tuple[str, str]]:
    """The session as (kind, value) pairs in order: `person`, `claude` text, `tool` label, `asked`
    and `answered` for `AskUserQuestion`, and `skill` started."""
    out: list[tuple[str, str]] = []
    asked: dict[str, list[str]] = {}
    for e in entries:
        if e.get("isSidechain") or e.get("isMeta"):
            continue
        kind = e.get("type")
        content = (e.get("message") or {}).get("content")
        if kind == "user" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id") in asked:
                    out.append(("answered", answers_of(asked.pop(block["tool_use_id"]), e.get("toolUseResult"))))
        origin = (e.get("origin") or {}).get("kind")
        typed = origin is None and (BASH_INPUT.search(text_of(content)) or COMMAND_NAME.search(text_of(content)))
        if kind == "user" and (origin == "human" or typed):
            text = text_of(content)
            if text and person_text(text):
                out.append(("person", person_text(text)))
                if COMMAND_NAME.search(text):
                    out.append(("skill", person_text(text)))
        elif kind == "attachment":
            att = e.get("attachment") or {}
            if att.get("type") == "queued_command" and (att.get("origin") or {}).get("kind") == "human":
                text = text_of(att.get("prompt"))
                if text:
                    out.append(("person", person_text(text)))
        elif kind == "assistant":
            for block in (e.get("message") or {}).get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text", "").strip():
                    out.append(("claude", block["text"].strip()))
                elif block.get("type") == "tool_use" and block.get("name") == "AskUserQuestion":
                    raw = (block.get("input") or {}).get("questions")
                    if isinstance(raw, str):
                        try:
                            raw = json.loads(raw)
                        except json.JSONDecodeError as e:
                            raise ExcerptError(f"an AskUserQuestion call's questions are not a list of questions: a string that is not JSON ({e.msg})") from e
                    if not isinstance(raw, list) or not raw or not all(isinstance(q, dict) for q in raw):
                        raise ExcerptError("an AskUserQuestion call's questions are not a list of questions")
                    questions = [str(q.get("question", "")) for q in raw]
                    asked[block.get("id", "")] = questions
                    out.append(("asked", numbered(questions)))
                elif block.get("type") == "tool_use":
                    out.append(("tool", tool_label(block)))
                    if block.get("name") == "Skill":
                        out.append(("skill", str((block.get("input") or {}).get("skill", ""))))
    return out


def turns_of(evs: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    """Split at each message from the person; what comes before the first is dropped."""
    turns: list[list[tuple[str, str]]] = []
    for ev in evs:
        if ev[0] == "person":
            turns.append([ev])
        elif turns:
            turns[-1].append(ev)
    return turns


def select(turns: list[list[tuple[str, str]]], count: int, before_skill: str | None) -> list[list[tuple[str, str]]]:
    if count < 1:
        raise ExcerptError(f"--turns must be 1 or more, not {count}")
    if before_skill:
        starts = [i for i, t in enumerate(turns) if any(k == "skill" and skill_matches(v, before_skill) for k, v in t)]
        if not starts:
            raise ExcerptError(f"the session never started skill {before_skill!r}")
        turns = turns[: starts[-1]]
    return turns[-count:]


def redact(text: str, counts: dict[str, int], home: str) -> str:
    for kind, pattern, replacement in REDACTIONS:
        text, n = pattern.subn(replacement, text)
        counts[kind] += n
    if home and home != "/":
        home = home.rstrip("/")
        text, n = re.subn(re.escape(home) + r"(?![\w.-])", "~", text, flags=re.I)
        counts["home"] += n
        # Claude Code's project and scratchpad directory names: the path with each character that is not
        # a letter or digit as `-`.
        dashed = re.escape(re.sub(r"[^A-Za-z0-9]", "-", home))
        text, n = re.subn(r"(?<![A-Za-z0-9-])" + dashed + r"(?![A-Za-z0-9])", "-~", text, flags=re.I)
        counts["home"] += n
    return text


def render(turns: list[list[tuple[str, str]]], counts: dict[str, int], home: str) -> str:
    parts = []
    for i, turn in enumerate(turns, 1):
        lines = [f"--- Turn {i} ---"]
        tools: list[str] = []
        for kind, value in turn + [("end", "")]:
            if kind not in ("tool", "skill") and tools:
                runs = []
                for name in tools:
                    if runs and runs[-1][0] == name:
                        runs[-1][1] += 1
                    else:
                        runs.append([name, 1])
                lines.append("Tools: " + ", ".join(n if c == 1 else f"{n} x{c}" for n, c in runs))
                tools = []
            if kind in LABELS:
                text = redact(value, counts, home)
                lines.append(LABELS[kind] + (text if text.startswith("\n") else " " + text))
            elif kind == "tool":
                tools.append(value)
        parts.append("\n\n".join(lines))
    body = "\n\n".join(parts)
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", body)), default=0))
    return f"{fence}text\n{body}\n{fence}\n"


def fit(turns: list[list[tuple[str, str]]], counts: dict[str, int], home: str, max_chars: int | None) -> tuple[str, int]:
    """The excerpt of the newest turns that fit in `max_chars`, and how many of the oldest were dropped;
    `counts` holds the redactions in the kept turns alone."""
    for dropped in range(max(len(turns), 1)):
        for kind in counts:
            counts[kind] = 0
        out = render(turns[dropped:], counts, home)
        if max_chars is None or len(out) <= max_chars:
            return out, dropped
    raise ExcerptError(f"the newest turn alone is {len(out)} characters, over --max-chars {max_chars}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", type=Path, help="the transcript, instead of finding this session's")
    parser.add_argument("--turns", type=int, default=DEFAULT_TURNS, help=f"how many turns to keep (default {DEFAULT_TURNS})")
    parser.add_argument("--before-skill", metavar="NAME", help="end before the last turn in which this skill started")
    parser.add_argument("--max-chars", type=int, metavar="N", help="drop the oldest turns until the excerpt is N characters or fewer")
    parser.add_argument("--stdin", action="store_true", help="redact the text on stdin instead of reading a transcript")
    args = parser.parse_args(argv)
    counts = {kind: 0 for kind, _, _ in REDACTIONS}
    counts["home"] = 0
    if args.stdin:
        if args.file or args.before_skill or args.max_chars is not None:
            parser.error("--stdin reads no transcript, so it takes no --file, --before-skill or --max-chars")
        sys.stdout.write(redact(sys.stdin.read(), counts, str(Path.home())))
        print("redactions: " + ", ".join(f"{k} {n}" for k, n in counts.items()), file=sys.stderr)
        return 0
    try:
        if args.file:
            path = args.file
        else:
            config = os.environ.get("CLAUDE_CONFIG_DIR")
            path = find_transcript(os.environ.get("CLAUDE_CODE_SESSION_ID"), Path(config) if config else Path.home() / ".claude")
        turns = turns_of(events(read_entries(path)))
        if not turns:
            raise ExcerptError(f"{path} holds no message from the person")
        kept = select(turns, args.turns, args.before_skill)
        out, dropped = fit(kept, counts, str(Path.home()), args.max_chars)
    except ExcerptError as e:
        print(f"transcript_excerpt.py: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(out)
    fitted = f", {dropped} oldest dropped to fit --max-chars {args.max_chars}" if dropped else ""
    print(f"turns: {len(kept) - dropped} of {args.turns} requested{fitted}", file=sys.stderr)
    print(f"characters: {len(out)}", file=sys.stderr)
    print("redactions: " + ", ".join(f"{k} {n}" for k, n in counts.items()), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
