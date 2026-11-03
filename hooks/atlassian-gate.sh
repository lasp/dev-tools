#!/usr/bin/env bash
# PreToolUse on the Atlassian server's tools, whatever the server is named. A read passes. A Jira
# write of a kind a write plan holds, made by the main session, is allowed only when
# .review/jira-approval.json at the repository's top level lists that tool with that target: the skill writes it at the person's
# yes to the plan and removes it when the plan finishes or stops (skills/using-jira/write-plan.md),
# so asking again at each of a dozen calls adds no check. The record is
#   {"session": "<session_id>", "t": <epoch seconds>, "items": [{"tool": "<tool>", "target": "<target>"}]}
# the target being the project_key for jira_create_issue, "<inward_issue_key> <outward_issue_key>"
# for jira_create_issue_link, "<issue_key> <epic_key>" for jira_link_to_epic, and the issue_key for
# the rest. A record from another session, older than APPROVAL_TTL seconds, dated in the future,
# not in that shape, or not listing the call allows nothing, and the call is asked about: an ask
# prompts in auto mode too, where passing silently would leave the call to the classifier. An ask
# or deny rule in the person's settings still applies over the allow. Every other call waits for a
# yes: any Confluence write, a Jira write that deletes, removes, moves or overwrites a comment, an
# update that uploads local files, a tool the plan does not use, and any write a subagent makes,
# which never writes.
#
# A read is a tool whose name, after its jira_ or confluence_ prefix, opens with get_, search,
# list_, check_, download_ or batch_get_. A tool a later server version adds counts as a write
# outside the plan. Input it cannot read, or any call when jq is missing, is asked about too.
set -u

APPROVAL_TTL=1800

decide() {
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"%s","permissionDecisionReason":"%s"}}\n' "$1" "$2"
}
ask() { decide ask "$1"; }

command -v jq >/dev/null || { ask "jq is not installed, so the Atlassian gate cannot tell a read from a write. Allow it only if you know the call writes nothing."; exit 0; }
input=$(cat)
# The record sits at the repository's top level, found from the payload's cwd, so a session
# working in a subdirectory reads the same one.
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
cwd=${cwd:-$PWD}
top=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || top=$cwd
record="$top/.review/jira-approval.json"
tool=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)
agent=$(printf '%s' "$input" | jq -r '.agent_id // empty' 2>/dev/null)
op=${tool##*__}
case "$op" in
  jira_*|confluence_*) ;;
  "") ask "The Atlassian gate could not read the tool name. Allow it only if you know the call writes nothing."; exit 0 ;;
  *) exit 0 ;;
esac
case "${op#*_}" in
  get_*|search*|list_*|check_*|download_*|batch_get_*) exit 0 ;;
esac
[ -n "$agent" ] && { ask "$op writes to Jira or Confluence from a subagent, and a subagent never writes. Deny it unless you asked for this call yourself."; exit 0; }
attached=$(printf '%s' "$input" | jq -r '.tool_input.attachments // empty | tostring' 2>/dev/null)
case "$attached" in
  ""|"[]") ;;
  *) ask "$op uploads local files to Jira, which no write plan does. Allow it only if you asked for exactly this."; exit 0 ;;
esac
case "$op" in
  jira_create_issue|jira_update_issue|jira_add_comment|jira_create_issue_link|jira_link_to_epic|jira_transition_issue|jira_assign_issue)
    target=$(printf '%s' "$input" | jq -r --arg op "$op" '.tool_input as $i
      | if $op == "jira_create_issue" then [$i.project_key]
        elif $op == "jira_create_issue_link" then [$i.inward_issue_key, $i.outward_issue_key]
        elif $op == "jira_link_to_epic" then [$i.issue_key, $i.epic_key]
        else [$i.issue_key] end
      | if all(type == "string" and length > 0) then join(" ") else empty end' 2>/dev/null)
    session=$(printf '%s' "$input" | jq -r '.session_id | strings' 2>/dev/null)
    if [ -n "$target" ] && [ -n "$session" ] && [ -f "$record" ] \
      && jq -e -s --arg s "$session" --arg op "$op" --arg target "$target" \
        --argjson now "$(date +%s)" --argjson ttl "$APPROVAL_TTL" \
        'length == 1 and (.[0] | .session == $s and (.t | type) == "number"
         and $now - .t >= 0 and $now - .t < $ttl and (.items | type) == "array"
         and all(.items[]; type == "object" and (.tool | type) == "string" and (.target | type) == "string")
         and any(.items[]; .tool == $op and .target == $target))' "$record" >/dev/null 2>&1; then
      decide allow "$op is an item of the write plan you approved."
    else
      ask "$op is not an item of a write plan you approved in this session: $record does not list it with this target. Allow it only if you asked for exactly this."
    fi
    exit 0 ;;
esac
case "$op" in
  confluence_*)
    # What the call writes, as the person saw it at the skill's gate: the page and, for a section
    # write, its heading. Each value is cut to 80 characters and loses its quotes, backslashes and
    # control characters, since the reason is printed inside a JSON string and a value the model
    # chose must not read as the hook's own words.
    what=$(printf '%s' "$input" | jq -r 'def v: tostring | gsub("[\"'\''\\\\[:cntrl:]]"; "") | .[0:80];
      .tool_input as $i | ($i | type) as $t
      | if $t != "object" then empty else
        [ (if $i.page_id then "page \($i.page_id | v)" else empty end),
          (if $i.title then "titled '\''\($i.title | v)'\''" else empty end),
          (if $i.heading_text then "section '\''\($i.heading_text | v)'\''" else empty end),
          (if $i.space_key and ($i.page_id | not) then "in space \($i.space_key | v)" else empty end) ]
        | join(", ") end' 2>/dev/null)
    ask "$op writes to Confluence${what:+ ($what)}, which asks at every call. Allow it only if it is the write you said yes to at the skill's gate, or asked for yourself." ;;
  *) ask "$op writes to Jira outside a write plan. Allow it only if you asked for exactly this." ;;
esac
