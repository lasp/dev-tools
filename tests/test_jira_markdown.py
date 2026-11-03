"""Tests for scripts/jira_markdown.py and its copy of mcp-atlassian's converter,
scripts/jira_markup.py. Run with `python3 -m unittest discover -s tests`.

The copy is checked against mcp-atlassian 0.23.1 itself through `uvx --offline`, skipped where uv
has not cached that package, as CI's step before the tests does.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS / "jira_markdown.py"
UVX = ["uvx", "--offline", "--from", "mcp-atlassian@0.23.1", "python"]
sys.path.insert(0, str(SCRIPTS))

from jira_markup import JiraPreprocessor  # noqa: E402

SAMPLES = [
    "h1. Context\n*Touches:* {{widget_utils.io}} and [the page|https://example.com/page]\n",
    "h2. Acceptance Criteria\n# an input: the result\n# another\n* a bullet\n** nested\n",
    "{code:python}\nx = 1\n\ny = 2\n{code}\n{noformat}\nraw *text*\n{noformat}\n",
    "_italic_ -struck- +under+ ^sup^ ~sub~ ??cite?? {color:red}red{color}\n",
    "||a||b||\n|1|2|\nbq. quoted\n{quote}\nmore\n{quote}\n{panel:title=Note}\nbody\n{panel}\n",
    "See https://github.com/example-org/widget_utils/pull/58 and widget_utils keeps it.\n",
]
PACKAGE = (
    "import json, sys\n"
    "from mcp_atlassian.preprocessing.jira import JiraPreprocessor\n"
    "p = JiraPreprocessor(base_url='https://jira.invalid')\n"
    "print(json.dumps([[p.jira_to_markdown(t), p.markdown_to_jira(p.jira_to_markdown(t))] for t in json.load(sys.stdin)]))\n"
)


def run(text: str, *args: str) -> subprocess.CompletedProcess:
    """Runs the script with `-S`, so no installed package is on its path."""
    return subprocess.run([sys.executable, "-S", str(SCRIPT), *args], input=text, capture_output=True, text=True)


def to_wiki(markdown: str) -> str:
    return JiraPreprocessor().markdown_to_jira(markdown)


def server_package() -> bool:
    if not shutil.which("uvx"):
        return False
    return subprocess.run([*UVX, "-c", "import mcp_atlassian"], capture_output=True).returncode == 0


@unittest.skipUnless(server_package(), "uvx has no cached mcp-atlassian 0.23.1")
class TheCopyConvertsAsThePackageDoes(unittest.TestCase):
    def test_each_sample_converts_both_ways_as_the_package_does(self):
        out = subprocess.run([*UVX, "-c", PACKAGE], input=json.dumps(SAMPLES), capture_output=True, text=True, check=True)
        converted = json.loads(out.stdout)
        self.assertEqual(len(converted), len(SAMPLES))
        copy = JiraPreprocessor()
        for text, (markdown, wiki) in zip(SAMPLES, converted):
            with self.subTest(text=text):
                self.assertEqual(copy.jira_to_markdown(text), markdown)
                self.assertEqual(copy.markdown_to_jira(markdown), wiki)


class TheScript(unittest.TestCase):
    def test_the_ticket_format_converts_and_comes_back_as_written(self):
        wiki = (
            "h2. Context\n"
            "The *writer* fills {{production_time}}.\n"
            "* a bullet\n"
            "# AC-1 a numbered criterion\n"
            "[the page|https://example.com/page]\n"
        )
        result = run(wiki)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## Context", result.stdout)
        self.assertIn("**writer**", result.stdout)
        self.assertIn("1. AC-1 a numbered criterion", result.stdout)

    def test_what_jira_does_not_show_is_not_compared(self):
        # Blank lines, trailing spaces and the escape the server adds to an underscore.
        result = run("h2. Context  \n\n\nwidget_utils keeps it.\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_line_stored_differently_is_listed_and_the_markdown_still_printed(self):
        result = run("h2. Context\n - first dash bullet\n - second dash bullet\n")
        self.assertEqual(result.returncode, 3)
        self.assertIn("- - first dash bullet", result.stderr)
        self.assertIn("- - second dash bullet", result.stderr)
        self.assertIn("## Context", result.stdout)

    def test_a_blank_line_inside_a_code_block_is_compared(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt") as stored:
            stored.write("{code}\nx = 1\n\n{code}\n")
            stored.flush()
            result = run("{code}\nx = 1\n{code}\n", "--stored", stored.name)
        self.assertEqual(result.returncode, 3)
        self.assertIn("+\n", result.stderr + "\n")

    def test_a_code_block_survives_repeated_round_trips_unchanged(self):
        wiki = "a\n{code:python}\nx = 1\n\ny = 2\n{code}\nb\n"
        text = wiki
        for _ in range(3):
            result = run(text)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = to_wiki(result.stdout)
        self.assertEqual(text.strip(), wiki.strip())

    def test_a_backslash_inside_a_bare_url_is_compared(self):
        # The server escapes the underscore in a bare URL, and the link Jira builds may keep it.
        result = run("See https://github.com/example-org/widget_utils/pull/58 for it.\n")
        self.assertEqual(result.returncode, 3)
        self.assertIn("widget\\_utils", result.stderr)

    def test_stored_matches_what_the_server_stored_from_the_markdown_sent(self):
        wiki = "h2. Context\nwidget_utils keeps {{production_time}}.\n# AC-1 a criterion\n"
        sent = run(wiki).stdout
        with tempfile.NamedTemporaryFile("w", suffix=".txt", newline="") as stored:
            stored.write(to_wiki(sent).replace("\n", "\r\n"))
            stored.flush()
            result = run(wiki, "--stored", stored.name)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stored_compares_with_the_text_a_write_stored(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt") as stored:
            stored.write("h2. Context\nSomething else.\n")
            stored.flush()
            result = run("h2. Context\nThe text shown.\n", "--stored", stored.name)
        self.assertEqual(result.returncode, 3)
        self.assertIn("-The text shown.", result.stderr)
        self.assertIn("+Something else.", result.stderr)


if __name__ == "__main__":
    unittest.main()
