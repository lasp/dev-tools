#!/usr/bin/env bash
# PreToolUse on Bash and on the GitHub and Atlassian servers' tools, whatever the servers are named.
# scripts/secret_scan.py decides: a `git commit` or a `gh` write whose content holds what looks like
# a credential, or a server write whose input holds one, is denied, naming where and what kind but
# never the value; a call it cannot scan is asked about; every other call passes. With no python3,
# a command that mentions a commit or `gh`, and every server call but a read, are asked about,
# since nothing checked them.
set -u
command -v python3 >/dev/null 2>&1 || {
  input=$(cat)
  tool=""
  if [[ $input =~ \"tool_name\"[[:space:]]*:[[:space:]]*\"([^\"]*)\" ]]; then tool=${BASH_REMATCH[1]}; fi
  case "$tool" in
    Bash) case "$input" in *commit*|*[\"\ \;\&\|\(]gh\ *) ;; *) exit 0 ;; esac ;;
    mcp__*__jira_get_*|mcp__*__jira_search*|mcp__*__jira_list_*|mcp__*__jira_check_*|mcp__*__jira_download_*|mcp__*__jira_batch_get_*) exit 0 ;;
    mcp__*__confluence_get_*|mcp__*__confluence_search*|mcp__*__confluence_list_*|mcp__*__confluence_check_*|mcp__*__confluence_download_*) exit 0 ;;
    mcp__*__get_*|mcp__*__list_*|mcp__*__search_*|mcp__*_read|mcp__*__run_secret_scanning) exit 0 ;;
  esac
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"python3 is not installed, so the secret scan could not run. Allow this only if you know it carries no credential."}}'
  exit 0
}
exec python3 "$(dirname "$0")/../scripts/secret_scan.py" hook
