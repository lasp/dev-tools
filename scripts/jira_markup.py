"""Jira wiki markup to and from Markdown, as mcp-atlassian 0.23.1 converts it on a write.

Copied from mcp-atlassian 0.23.1 (https://github.com/sooperset/mcp-atlassian),
`mcp_atlassian/preprocessing/jira.py` and the two block helpers of `preprocessing/base.py`, so the
conversion runs on the standard library alone. Left out: the class's base, `clean_jira_text`,
and the methods that resolve mentions and smart links; the constructor keeps only
`disable_translation`. The rest is as published.
`tests/test_jira_markdown.py` checks that it converts as the package does.
"""

# MIT License
#
# Copyright (c) 2024 Hyeonsoo Lee
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import re
from collections.abc import Callable

def _extract_blocks(
    text: str,
    pattern: str,
    transform_fn: Callable[[re.Match[str]], str],
    storage: list[str],
    prefix: str,
    flags: int = 0,
) -> str:
    """Extract blocks matching pattern, transform, store, and replace with placeholders.

    Args:
        text: Input text to process.
        pattern: Regex pattern to match blocks.
        transform_fn: Function to transform the match into the target format.
        storage: List to store transformed blocks.
        prefix: Placeholder prefix (e.g., "CODEBLOCK").
        flags: Regex flags to pass to ``re.sub``.

    Returns:
        Text with blocks replaced by placeholders.
    """

    def _replacer(match: re.Match[str]) -> str:
        transformed = transform_fn(match)
        placeholder = f"\x00{prefix}{len(storage)}\x00"
        storage.append(transformed)
        return placeholder

    return re.sub(pattern, _replacer, text, flags=flags)


def _restore_blocks(text: str, storage: list[str], prefix: str) -> str:
    """Restore blocks from placeholders.

    Replaces in reverse order (highest index first) to avoid
    index collisions when placeholder text contains digits.

    Args:
        text: Text with placeholders.
        storage: List of stored blocks.
        prefix: Placeholder prefix used during extraction.

    Returns:
        Text with placeholders replaced by stored blocks.
    """
    for i in range(len(storage) - 1, -1, -1):
        text = text.replace(f"\x00{prefix}{i}\x00", storage[i])
    return text


def _convert_panel(params: str | None, content: str) -> str:
    """Convert a Jira {panel} block to markdown."""
    title = ""
    if params:
        title_match = re.search(r"title=([^|}]+)", params)
        if title_match:
            title = title_match.group(1).strip()
    content = content.strip()
    if title:
        return f"\n**{title}**\n{content}\n"
    return f"\n{content}\n"



class JiraPreprocessor:
    """Handles text preprocessing for Jira content."""

    # Step 1: Valid JIRA languages (official list)
    # Source: https://jira.atlassian.com/browse/JRASERVER-21067 (JIRA 7.5.0+)
    # and JIRA v9.12.12 release notes
    # Official documentation: https://jira.atlassian.com/secure/WikiRendererHelpAction.jspa
    VALID_JIRA_LANGUAGES = {
        # Core languages from JIRA 7.5.0+
        "actionscript",
        "actionscript3",
        "ada",
        "applescript",
        "bash",
        "sh",  # alias for bash
        "c",
        "c#",
        "csharp",  # alias for c#
        "cs",  # alias for c#
        "c++",
        "cpp",  # alias for c++
        "css",
        "sass",  # CSS preprocessor
        "less",  # CSS preprocessor
        "coldfusion",
        "delphi",
        "diff",
        "patch",  # alias for diff
        "erlang",
        "erl",  # alias for erlang
        "go",
        "groovy",
        "haskell",
        "html",
        "xml",
        "java",
        "javafx",
        "javascript",
        "js",  # alias for javascript
        "json",
        "lua",
        "nyan",
        "objc",
        "objective-c",  # alias for objc
        "perl",
        "php",
        "powershell",
        "ps1",  # alias for powershell
        "python",
        "py",  # alias for python
        "r",
        "rainbow",
        "ruby",
        "rb",  # alias for ruby
        "scala",
        "sql",
        "swift",
        "visualbasic",
        "vb",  # alias for visualbasic
        "yaml",
        "yml",  # alias for yaml
        "none",  # plain text, no highlighting
    }

    # Step 2: Mapping for unsupported languages to closest valid JIRA alternative
    # Only map to actual JIRA languages; unmapped languages will return None → {code}
    LANGUAGE_MAPPING = {
        # Dockerfile → bash (similar shell syntax)
        "dockerfile": "bash",
        "docker": "bash",
        # TypeScript → javascript
        "typescript": "javascript",
        "ts": "javascript",
        "tsx": "javascript",
        # JSX/React → javascript
        "jsx": "javascript",
        # Kotlin → java (JVM-based language)
        "kotlin": "java",
        "kt": "java",
        # Build files → bash
        "makefile": "bash",
        "make": "bash",
        "cmake": "bash",
    }

    def __init__(self, disable_translation: bool = False) -> None:
        self.disable_translation = disable_translation

    def jira_to_markdown(self, input_text: str) -> str:
        """
        Convert Jira markup to Markdown format.

        Args:
            input_text: Text in Jira markup format

        Returns:
            Text in Markdown format (or original text if translation disabled)
        """
        if not input_text:
            return ""

        if self.disable_translation:
            return input_text

        output = input_text

        # Protect code/noformat/inline-code blocks from downstream
        # transformations by replacing them with placeholders.
        #
        # Trade-off: when {quote} wraps a {code} block, the code
        # content is extracted *before* the {quote} handler runs.
        # The {quote} handler prefixes each remaining line with
        # "> " but cannot reach inside the already-extracted block.
        # After restoration the opening fence line may carry "> "
        # while inner code lines do not, breaking blockquote
        # continuity.  This is intentional: protecting code content
        # from markup corruption is more important than preserving
        # blockquote indentation around code fences.
        code_blocks: list[str] = []
        inline_codes: list[str] = []

        def _jira_code_to_md(match: re.Match[str]) -> str:
            lang = match.group(1) or ""
            content = match.group(2)
            return f"```{lang}\n{content}\n```"

        output = _extract_blocks(
            output,
            r"\{code(?::([a-z]+))?\}([\s\S]*?)\{code\}",
            _jira_code_to_md,
            code_blocks,
            "CODEBLOCK",
            flags=re.MULTILINE,
        )
        output = _extract_blocks(
            output,
            r"\{noformat\}([\s\S]*?)\{noformat\}",
            lambda m: f"```\n{m.group(1)}\n```",
            code_blocks,
            "CODEBLOCK",
        )
        output = _extract_blocks(
            output,
            r"\{\{([^}]+)\}\}",
            lambda m: f"`{m.group(1)}`",
            inline_codes,
            "INLINECODE",
        )

        # Block quotes
        output = re.sub(r"^bq\.(.*?)$", r"> \1\n", output, flags=re.MULTILINE)

        # Text formatting (bold, italic)
        output = re.sub(
            r"([*_])(.*?)\1",
            lambda match: (
                ("**" if match.group(1) == "*" else "*")
                + match.group(2)
                + ("**" if match.group(1) == "*" else "*")
            ),
            output,
        )

        # Multi-level numbered list
        output = re.sub(
            r"^((?:#|-|\+|\*)+) (.*)$",
            lambda match: self._convert_jira_list_to_markdown(match),
            output,
            flags=re.MULTILINE,
        )

        # Headers
        output = re.sub(
            r"^h([0-6])\.(.*)$",
            lambda match: "#" * int(match.group(1)) + match.group(2),
            output,
            flags=re.MULTILINE,
        )

        # Citation (non-overlapping alternation to avoid catastrophic backtracking)
        output = re.sub(
            r"\?\?([^?]+(?:\?[^?]+)*)\?\?",
            r"<cite>\1</cite>",
            output,
        )

        # Inserted text
        output = re.sub(r"\+([^+]*)\+", r"<ins>\1</ins>", output)

        # Superscript
        output = re.sub(r"\^([^^]*)\^", r"<sup>\1</sup>", output)

        # Subscript
        output = re.sub(r"~([^~]*)~", r"<sub>\1</sub>", output)

        # Strikethrough
        output = re.sub(r"-([^-]*)-", r"-\1-", output)

        # Quote blocks
        output = re.sub(
            r"\{quote\}([\s\S]*)\{quote\}",
            lambda match: "\n".join(
                [f"> {line}" for line in match.group(1).split("\n")]
            ),
            output,
            flags=re.MULTILINE,
        )

        # Panel blocks - extract content, optionally show title as bold
        output = re.sub(
            r"\{panel(?::([^}]*))?\}([\s\S]*?)\{panel\}",
            lambda match: _convert_panel(match.group(1), match.group(2)),
            output,
            flags=re.MULTILINE,
        )

        # Images with alt text
        output = re.sub(
            r"!([^|\n\s]+)\|([^\n!]*)alt=([^\n!\,]+?)"
            r"(,([^\n!]*))?!",
            r"![\3](\1)",
            output,
        )

        # Images with other parameters (ignore them)
        output = re.sub(r"!([^|\n\s]+)\|([^\n!]*)!", r"![](\1)", output)

        # Images without parameters
        output = re.sub(r"!([^\n\s!]+)!", r"![](\1)", output)

        # Links
        output = re.sub(r"\[([^|]+)\|(.+?)\]", r"[\1](\2)", output)
        output = re.sub(r"\[(.+?)\]([^\(])", r"\1\2", output)

        # Colored text
        output = re.sub(
            r"\{color:([^}]+)\}([\s\S]*?)\{color\}",
            r"<span style=\"color:\1\">\2</span>",
            output,
            flags=re.MULTILINE,
        )

        # Convert Jira table headers (||) to markdown table format
        lines = output.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            if "||" in line:
                # Replace Jira table headers
                lines[i] = lines[i].replace("||", "|")

                # Add a separator line for markdown tables
                header_cells = lines[i].count("|") - 1
                if header_cells > 0:
                    separator_line = "|" + "---|" * header_cells
                    lines.insert(i + 1, separator_line)
                    i += 1

            i += 1

        # Rejoin the lines
        output = "\n".join(lines)

        # Restore code/noformat blocks and inline code
        output = _restore_blocks(output, code_blocks, "CODEBLOCK")
        output = _restore_blocks(output, inline_codes, "INLINECODE")

        return output

    def _normalize_code_language(self, lang: str | None) -> str | None:
        """
        Normalize and map markdown code language to JIRA-supported language.

        Step 3: Default handling - unmapped languages return None for plain {code}

        Args:
            lang: Language identifier from markdown code block

        Returns:
            Valid JIRA language string, or None for plain {code} block
        """
        if not lang:
            return None

        lang_lower = lang.lower()

        # Step 1: Check if already valid JIRA language
        if lang_lower in self.VALID_JIRA_LANGUAGES:
            return lang_lower

        # Step 2: Check language mapping
        if lang_lower in self.LANGUAGE_MAPPING:
            return self.LANGUAGE_MAPPING[lang_lower]

        # Step 3: Default - unmapped language returns None for plain {code}
        return None

    def markdown_to_jira(self, input_text: str) -> str:
        """
        Convert Markdown syntax to Jira markup syntax.

        Args:
            input_text: Text in Markdown format

        Returns:
            Text in Jira markup format (or original text if translation disabled)
        """
        if not input_text:
            return ""

        if self.disable_translation:
            return input_text

        code_blocks: list[str] = []
        inline_codes: list[str] = []

        def _md_code_to_jira(match: re.Match[str]) -> str:
            syntax = match.group(1) or ""
            content = match.group(2)
            jira_lang = self._normalize_code_language(syntax)
            code = "{code"
            if jira_lang:
                code += ":" + jira_lang
            code += "}" + content + "{code}"
            return code

        def _md_inline_to_jira(
            match: re.Match[str],
        ) -> str:
            return "{{" + match.group(1) + "}}"

        # Extract code blocks and inline code before
        # any other transformations.
        output = _extract_blocks(
            input_text,
            r"```(\w*)\n([\s\S]+?)```",
            _md_code_to_jira,
            code_blocks,
            "CODEBLOCK",
        )
        output = _extract_blocks(
            output,
            r"`([^`]+)`",
            _md_inline_to_jira,
            inline_codes,
            "INLINECODE",
        )

        # Headers with = or - underlines
        output = re.sub(
            r"^(.*?)\n([=-])+$",
            lambda match: f"h{1 if match.group(2)[0] == '=' else 2}. {match.group(1)}",
            output,
            flags=re.MULTILINE,
        )

        # Headers with # prefix - require space after #
        # to distinguish from Jira lists (issue #786)
        output = re.sub(
            r"^([#]+) (.*)$",
            lambda match: f"h{len(match.group(1))}. " + match.group(2),
            output,
            flags=re.MULTILINE,
        )

        markdown_url_targets: list[str] = []

        def store_markdown_url_target(target: str) -> str:
            placeholder = f"\x00MARKDOWNURL{len(markdown_url_targets)}\x00"
            markdown_url_targets.append(target)
            return placeholder

        def protect_markdown_link_target(match: re.Match[str]) -> str:
            return (
                match.group(1)
                + store_markdown_url_target(match.group(2))
                + match.group(3)
            )

        def protect_markdown_autolink_target(match: re.Match[str]) -> str:
            return "<" + store_markdown_url_target(match.group(1)) + ">"

        output = re.sub(
            r"(!?\[[^\]\n]*\]\()([^)]+)(\))",
            protect_markdown_link_target,
            output,
        )
        output = re.sub(
            r"<((?:[A-Za-z][A-Za-z0-9+.-]*:[^>\s]+|[^<>\s@]+@[^<>\s@]+))>",
            protect_markdown_autolink_target,
            output,
        )

        # Bold and italic - skip lines starting with
        # asterisks+space (Jira list syntax, issue #786)
        def escape_intraword_underscore_runs(match: re.Match[str]) -> str:
            return r"\_" * len(match.group(0))

        def convert_bold_italic_line(line: str) -> str:
            # CommonMark treats underscores between two word characters as
            # literal text, not emphasis. The Jira wiki renderer does not:
            # it italicizes any ``_word_`` span, so identifiers such as
            # snake_case, customfield_10101 or foo_bar_baz would render with
            # spurious italics (and adjacent identifiers can pair into a
            # cross-token italic span). Escape intraword underscore runs as
            # ``\_`` so Jira renders them literally; genuine word-boundary
            # ``_emphasis_``/``__strong__`` is left intact for conversion below.
            line = re.sub(
                r"(?<=[^\W_])_+(?=[^\W_])",
                escape_intraword_underscore_runs,
                line,
            )
            if re.match(r"^[*_]+\s", line):
                return line
            return re.sub(
                r"([*_]+)(.*?)\1",
                lambda m: (
                    ("_" if len(m.group(1)) == 1 else "*")
                    + m.group(2)
                    + ("_" if len(m.group(1)) == 1 else "*")
                ),
                line,
            )

        lines = output.split("\n")
        output = "\n".join(convert_bold_italic_line(line) for line in lines)
        output = _restore_blocks(output, markdown_url_targets, "MARKDOWNURL")

        # Multi-level bulleted list
        def bulleted_list_fn(match: re.Match[str]) -> str:
            ident = len(match.group(1)) if match.group(1) else 0
            level = ident // 2 + 1
            return str("*" * level + " " + match.group(2))

        output = re.sub(
            r"^(\s+)?[-+*] (.*)$",
            bulleted_list_fn,
            output,
            flags=re.MULTILINE,
        )

        # Multi-level numbered list
        def numbered_list_fn(
            match: re.Match[str],
        ) -> str:
            ident = len(match.group(1)) if match.group(1) else 0
            level = ident // 2 + 1
            return str("#" * level + " " + match.group(2))

        output = re.sub(
            r"^(\s+)?\d+\. (.*)$",
            numbered_list_fn,
            output,
            flags=re.MULTILINE,
        )

        # HTML formatting tags to Jira markup
        tag_map = {
            "cite": "??",
            "del": "-",
            "ins": "+",
            "sup": "^",
            "sub": "~",
        }

        for tag, replacement in tag_map.items():
            output = re.sub(
                rf"<{tag}>(.*?)<\/{tag}>",
                rf"{replacement}\1{replacement}",
                output,
            )

        # Colored text
        output = re.sub(
            r"<span style=\"color:(#[^\"]+)\">"
            r"([\s\S]*?)</span>",
            r"{color:\1}\2{color}",
            output,
            flags=re.MULTILINE,
        )

        # Strikethrough
        output = re.sub(r"~~(.*?)~~", r"-\1-", output)

        # Images without alt text
        output = re.sub(r"!\[\]\(([^)\n\s]+)\)", r"!\1!", output)

        # Images with alt text
        output = re.sub(
            r"!\[([^\]\n]+)\]\(([^)\n\s]+)\)",
            r"!\2|alt=\1!",
            output,
        )

        # Links
        output = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\1|\2]", output)
        output = re.sub(r"<([^>]+)>", r"[\1]", output)

        # Convert markdown tables to Jira table format
        # Issue #1343: parse full table blocks (header + separator + data rows),
        # strip whitespace from each cell, convert header to ||cell|| and data
        # rows to |cell|.
        lines = output.split("\n")
        i = 0
        while i < len(lines):
            # Look for a header row followed by a markdown separator line
            if (
                i < len(lines) - 1
                and re.match(r"^\|[-\s|:]+\|$", lines[i + 1])
                and re.match(r"^\|.*\|$", lines[i])
            ):
                # Header row
                header_cells = [cell.strip() for cell in lines[i].split("|")[1:-1]]
                lines[i] = "||" + "||".join(header_cells) + "||"
                lines.pop(i + 1)  # drop separator

                # Consume data rows while they look like table rows
                while i < len(lines) and re.match(
                    r"^\|.*\|$", lines[i + 1] if i + 1 < len(lines) else ""
                ):
                    data_cells = [
                        cell.strip() for cell in lines[i + 1].split("|")[1:-1]
                    ]
                    lines[i + 1] = "|" + "|".join(data_cells) + "|"
                    i += 1
            i += 1

        # Rejoin the lines
        output = "\n".join(lines)

        # Restore code blocks and inline code
        output = _restore_blocks(output, code_blocks, "CODEBLOCK")
        output = _restore_blocks(output, inline_codes, "INLINECODE")

        return output

    def _convert_jira_list_to_markdown(self, match: re.Match) -> str:
        """
        Helper method to convert Jira lists to Markdown format.

        Args:
            match: Regex match object containing the Jira list markup

        Returns:
            Markdown-formatted list item
        """
        jira_bullets = match.group(1)
        content = match.group(2)

        # Calculate indentation level based on number of symbols
        indent_level = len(jira_bullets) - 1
        indent = " " * (indent_level * 2)

        # Determine the marker based on the last character
        last_char = jira_bullets[-1]
        prefix = "1." if last_char == "#" else "-"

        return f"{indent}{prefix} {content}"
