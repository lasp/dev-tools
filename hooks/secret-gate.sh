#!/usr/bin/env bash
# PreToolUse on Bash and on every server's tools, since a server's kind is not in its name.
# scripts/secret_scan.py decides: a `git commit` or a `gh` write whose content holds what looks like
# a credential, or a server write whose input holds one, is denied, naming where and what kind but
# never the value; every other call passes, one the scan cannot read included. With no python3,
# nothing is scanned and every call passes.
set -u
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 "$(dirname "$0")/../scripts/secret_scan.py" hook
