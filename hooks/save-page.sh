#!/usr/bin/env bash
# PostToolUse on the GitHub server's pull_request_read: scripts/save_page.py writes the result, as
# the server returned it, under .review/pages/ and names the file for the caller to copy into its
# thread dump, since a result kept in the model's context has no file and a page written out by
# hand drops or changes text. With no python3 nothing is saved, and pr-reader, finding no file
# named, stops rather than write the page itself.
set -u
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 "$(dirname "$0")/../scripts/save_page.py"
