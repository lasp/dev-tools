#!/usr/bin/env bash
# Runs once, when the container is created — not on restart or attach.
#
# Syncs the Python environment with uv (pyproject.toml), makes sure jq is present, and
# installs the Claude Code CLI and registers this checkout as the plugin
# marketplace. MCP servers are not this repo's concern; they persist in
# $CLAUDE_CONFIG_DIR, which lives on the workspace mount.
#
# Nothing here aborts container creation: a failed install is worth a loud
# message, not an unusable container.
set -uo pipefail

# Signing is opt in per container: the host gitconfig carries the key but leaves
# commit.gpgsign off. Local scope is the point — do not promote it to --global.
git config commit.gpgsign true ||
    echo "post-create: could not enable commit signing." >&2

# The native installer drops a standalone binary in ~/.local/bin as the current
# user — no Node, no root-owned npm prefix, so `claude update` works without
# sudo. Never run it under sudo; it would install into root's home instead.
#
# It may warn that ~/.local/bin is not on PATH. Ignore it: postCreate runs a
# bare shell, but /etc/zsh/zshrc and ~/.profile in the base image both add that
# directory, so `claude` resolves in a real shell.
if command -v claude >/dev/null 2>&1; then
    echo "post-create: claude already present ($(claude --version 2>/dev/null))"
elif curl -fsSL https://claude.ai/install.sh | bash -s stable; then
    echo "post-create: Claude Code installed to ~/.local/bin"
else
    echo "post-create: Claude Code install failed. Install it by hand with:" >&2
    echo "post-create:   curl -fsSL https://claude.ai/install.sh | bash -s stable" >&2
fi

# The installer put claude in ~/.local/bin, which a bare postCreate shell does
# not have on PATH yet.
export PATH="$HOME/.local/bin:$PATH"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Python for the scripts, tests and checks comes from uv: the version in .python-version, plus the
# dev group (pyyaml, codespell). devcontainer.json puts .venv/bin first on PATH.
(cd "$REPO" && uv sync) ||
    echo "post-create: uv sync failed; run it by hand in $REPO." >&2

# The hooks and the session-start line need jq; the base image may not have it.
command -v jq >/dev/null 2>&1 ||
    { sudo apt-get update -qq && sudo apt-get install -y -qq jq; } >/dev/null 2>&1 ||
    echo "post-create: jq is missing and did not install; the build hooks record nothing without it." >&2

# This repo develops the plugin it ships, so it registers the checkout itself as
# the marketplace. A marketplace added from a local directory loads its plugins
# in place, so an edit is live in the next session or after `/reload-plugins`.
# Both commands are no-ops once done.
if command -v claude >/dev/null 2>&1; then
    claude plugin marketplace add "$REPO" &&
        claude plugin install lasp-dev@lasp-dev-tools ||
        echo "post-create: the lasp-dev plugin did not install; see above." >&2
fi
