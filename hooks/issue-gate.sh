#!/usr/bin/env bash
# PreToolUse on a GitHub server's issue_write and add_issue_comment, whatever the server is named.
# It only ever allows: a call the main session makes is allowed when .review/github-approval.json at
# the repository's top level lists that tool with that target, so a write plan's calls do not
# prompt one by one. The skill writes the record at the person's yes to the plan and removes it
# when the plan finishes or stops (skills/using-github/issues.md). The record is
#   {"session": "<session_id>", "t": <epoch seconds>, "items": [{"tool": "<tool>", "target": "<target>"}]}
# the target being "<owner>/<repo>" for an issue_write create and "<owner>/<repo>#<n>" for an
# issue_write update and for add_issue_comment. Every other call gets no decision, and the person's
# own permissions apply as they would without the hook: a record from another session, older than
# APPROVAL_TTL seconds, dated in the future, not in that shape, or not listing the call; a call from
# a subagent; a create that sets a parent or issue fields, or a comment that is a reaction, which no
# plan holds; input it cannot read; and any call when jq is missing. So a call outside a plan, such
# as skill-feedback's own create, prompts exactly as it did before the hook.
set -u

APPROVAL_TTL=1800

command -v jq >/dev/null || exit 0
input=$(cat)
tool=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)
op=${tool##*__}
case "$op" in
  issue_write|add_issue_comment) ;;
  *) exit 0 ;;
esac
[ -n "$(printf '%s' "$input" | jq -r '.agent_id // empty' 2>/dev/null)" ] && exit 0
# The record sits at the repository's top level, found from the payload's cwd, so a session
# working in a subdirectory reads the same one.
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
cwd=${cwd:-$PWD}
top=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || top=$cwd
record="$top/.review/github-approval.json"
target=$(printf '%s' "$input" | jq -r --arg op "$op" '.tool_input as $i
  | def repo: if ($i.owner | type) == "string" and ($i.repo | type) == "string" and ($i.owner | length) > 0 and ($i.repo | length) > 0
      then "\($i.owner)/\($i.repo)" else empty end;
    def number: if ($i.issue_number | type) == "number" and $i.issue_number >= 1 and ($i.issue_number | floor) == $i.issue_number
      then $i.issue_number | tostring else empty end;
  if ($i | type) != "object" then empty
  elif $op == "add_issue_comment" then (if $i.reaction == null and $i.comment_id == null then "\(repo)#\(number)" else empty end)
  elif $i.method == "create" then (if $i.parent_issue_number == null and $i.issue_fields == null then repo else empty end)
  elif $i.method == "update" then "\(repo)#\(number)"
  else empty end' 2>/dev/null)
session=$(printf '%s' "$input" | jq -r '.session_id | strings' 2>/dev/null)
if [ -n "$target" ] && [ -n "$session" ] && [ -f "$record" ] \
  && jq -e -s --arg s "$session" --arg op "$op" --arg target "$target" \
    --argjson now "$(date +%s)" --argjson ttl "$APPROVAL_TTL" \
    'length == 1 and (.[0] | .session == $s and (.t | type) == "number"
     and $now - .t >= 0 and $now - .t < $ttl and (.items | type) == "array"
     and all(.items[]; type == "object" and (.tool | type) == "string" and (.target | type) == "string")
     and any(.items[]; .tool == $op and .target == $target))' "$record" >/dev/null 2>&1; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"%s is an item of the write plan you approved."}}\n' "$op"
fi
exit 0
