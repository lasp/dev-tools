#!/usr/bin/env python3
"""Save each GitHub `pull_request_read` result to a file as the server returned it, for pr-reader's dump.

Run by `hooks/save-page.sh` after every `pull_request_read` call, the main session's or an
agent's. A result the harness keeps in the model's context has no file to copy, and a page a model
writes out by hand drops or changes text, so this hook writes it: the `tool_response` string,
byte for byte, under `.review/pages/<owner>-<repo>/pr-NNNN/` at the top level of the git repository
the session's cwd is in, as the other hooks find `.review/`, after `review_dir.sh` has made sure git
ignores `.review/`. Outside a git repository it saves nothing. A page is named as `thread_dump.py`
reads a dump's `pages/`:

- `get` writes `get.json`;
- `get_reviews` and `get_comments` write `<method>-<page>.json`, the call's `page`, 1 when none;
- `get_review_comments` writes `get_review_comments-<n>.json`: 1 for a call with no `after`, else
  one more than the saved page whose `pageInfo.endCursor` is that `after`.

Each write replaces the file of that name and removes nothing else: the calls of one dump run in
parallel, so a hook that cleared the folder could remove a sibling's page, and the caller copies
only the files these notes name, so an older page left beside them is never read.

Other methods are left alone. On a save it prints the hook's `additionalContext`, `saved
<method> as <path>`, the absolute path, so the caller copies that file from any directory. When it cannot
save (an `after` no saved page ends with, a response that is not text, a write that fails) it
prints `not saved: <method>: <reason>` instead, so the caller stops rather than write the page
itself. Exits 0 either way, since a PostToolUse hook cannot undo the call. Stdlib only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

METHODS = ("get", "get_reviews", "get_review_comments", "get_comments")


class NotSaved(Exception):
    """The result cannot be written as a numbered page."""


def response_text(response) -> str:
    if isinstance(response, str):
        return response
    raise NotSaved(f"the response is a {type(response).__name__}, not text")


def top_level(cwd: str) -> Path:
    out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if out.returncode:
        raise NotSaved(f"{cwd} is not in a git repository")
    top = Path(out.stdout.strip())
    subprocess.run(["bash", str(Path(__file__).with_name("review_dir.sh"))], cwd=top, capture_output=True)
    return top


def review_comments_page(folder: Path, after: str | None) -> int:
    if not after:
        return 1
    for page in folder.glob("get_review_comments-*.json"):
        try:
            cursor = json.loads(page.read_text())["pageInfo"]["endCursor"]
        except (ValueError, KeyError, TypeError):
            continue
        if cursor == after:
            return int(re.search(r"-(\d+)\.json$", page.name).group(1)) + 1
    raise NotSaved(f"no saved page ends at the cursor {after}")


def save(event: dict) -> str | None:
    args = event.get("tool_input") or {}
    method = args.get("method")
    if method not in METHODS:
        return None
    try:
        owner, repo, number = args["owner"], args["repo"], int(args["pullNumber"])
        text = response_text(event.get("tool_response"))
        folder = top_level(event["cwd"]) / ".review" / "pages" / f"{owner}-{repo}" / f"pr-{number:04d}"
        folder.mkdir(parents=True, exist_ok=True)
        if method == "get":
            name = "get.json"
        elif method == "get_review_comments":
            name = f"get_review_comments-{review_comments_page(folder, args.get('after'))}.json"
        else:
            name = f"{method}-{int(args.get('page') or 1)}.json"
        (folder / name).write_text(text)
        return f"saved {method} as {folder / name}"
    except NotSaved as e:
        return f"not saved: {method}: {e}"
    except (KeyError, ValueError, TypeError, OSError) as e:
        return f"not saved: {method}: {type(e).__name__}: {e}"


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    note = save(event) if isinstance(event, dict) else None
    if note:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": note}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
