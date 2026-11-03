"""Convert Jira wiki markup to the Markdown the Atlassian MCP server's write tools take.

The conversion is mcp-atlassian 0.23.1's, copied into `jira_markup.py` beside this script, so the
standard library runs it:

    python3 scripts/jira_markdown.py < text.txt
    python3 scripts/jira_markdown.py --stored stored.txt < text.txt

Reads wiki markup on stdin and prints its Markdown on stdout. Then compares the input with what
Jira would store from that Markdown, or with `--stored`, with the text a write stored. Exits 0
when they match; 3 when they differ, listing each differing line on stderr, the Markdown still
printed. A server of another version may store a text differently from what this says, which the
read-back with `--stored` shows. Outside `{code}` and
`{noformat}` blocks, blank lines, trailing spaces and a backslash escaping punctuation, which
Jira does not show, are not compared; a backslash inside a bare URL is, since the link Jira
builds from it may keep it.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

from jira_markup import JiraPreprocessor

FENCE = re.compile(r"^\s*```")
URL = re.compile(r"(https?://\S+)")
ESCAPE = re.compile(r"\\([^A-Za-z0-9\s])")
BLOCK = re.compile(r"\{(code|noformat)[^}]*\}")


def lines(text: str) -> list[str]:
    """The lines a reader sees: those inside a code block as they are, the rest normalized."""
    seen, in_block = [], False
    for line in text.splitlines():
        line = line.rstrip()
        marks = len(BLOCK.findall(line))
        if in_block or marks:
            seen.append(line)
        elif line.strip():
            seen.append("".join(p if URL.fullmatch(p) else ESCAPE.sub(r"\1", p) for p in URL.split(line)))
        in_block ^= marks % 2 == 1
    return seen


def tidy(markdown: str) -> str:
    """One blank line after an opening fence and none before a closing one.

    The server's Markdown-to-wiki conversion drops the first line break inside a code block, and
    its wiki-to-Markdown conversion adds a blank line before the closing fence, which would grow
    by one at every round trip.
    """
    out, in_fence = [], False
    for line in markdown.splitlines():
        if FENCE.match(line):
            if in_fence:
                while out and not out[-1].strip():
                    out.pop()
                out.append(line)
            else:
                out += [line, ""]
            in_fence = not in_fence
        elif in_fence and not line.strip() and FENCE.match(out[-2]) and out[-1] == "":
            continue
        else:
            out.append(line)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stored", type=Path, help="the wiki markup a write stored, to compare with")
    args = parser.parse_args(argv)
    wiki = sys.stdin.read()
    convert = JiraPreprocessor()
    markdown = tidy(convert.jira_to_markdown(wiki))
    stored = args.stored.read_text() if args.stored else convert.markdown_to_jira(markdown)
    print(markdown)
    diff = list(difflib.unified_diff(lines(wiki), lines(stored), "shown", "stored", n=0, lineterm=""))
    if diff:
        print("jira_markdown: Jira would not store the text as shown:", *diff, sep="\n", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
