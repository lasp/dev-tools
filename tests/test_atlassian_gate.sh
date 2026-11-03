#!/usr/bin/env bash
# Feeds hooks/atlassian-gate.sh every tool mcp-atlassian 0.23.1 offers, under a server name of
# the person's choosing, and checks that each read passes silently, each write a write plan holds
# is allowed from the main session only when this session's unexpired, well-formed approval record
# lists it with its target, and is asked about otherwise and from a subagent, an update uploading
# files is asked about, every other write is asked about, a tool the list does not know is asked
# about, and a tool from another server passes. Also
# checks that hooks.json's matcher sends it every Atlassian tool and no other.
# Run: bash tests/test_atlassian_gate.sh
set -u

root=$(cd "$(dirname "$0")/.." && pwd)
gate="$root/hooks/atlassian-gate.sh"
failures=0
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cd "$work" || exit 1

check() {
  if eval "$2"; then
    echo "  ok    $1"
  else
    echo "  FAIL  $1"
    failures=$((failures + 1))
  fi
}

reads="jira_get_user_profile jira_search_assignable_users jira_get_issue_watchers jira_get_issue
jira_search jira_search_fields jira_get_field_options jira_get_project_issues jira_get_transitions
jira_get_worklog jira_download_attachments jira_get_issue_images jira_get_agile_boards
jira_get_board_issues jira_get_sprints_from_board jira_get_sprint_issues jira_get_link_types
jira_batch_get_changelogs jira_get_project_issue_types jira_get_create_fields
jira_get_project_versions jira_get_project_components jira_get_all_projects jira_search_projects
jira_get_project_fields jira_get_service_desk_for_project jira_get_service_desk_queues
jira_get_queue_issues jira_get_request_types jira_get_request_type_fields
jira_get_issue_proforma_forms jira_get_proforma_form_details jira_get_issue_dates jira_get_issue_sla
jira_get_issue_development_info jira_get_issues_development_info jira_get_project_epic_hierarchy
jira_get_cross_project_dependencies confluence_search confluence_get_page
confluence_get_page_children confluence_get_space_page_tree confluence_get_comments
confluence_get_labels confluence_get_inline_comments confluence_search_user
confluence_get_page_history confluence_get_page_diff confluence_get_page_views
confluence_get_attachments confluence_download_attachment confluence_download_content_attachments
confluence_get_page_images confluence_list_page_templates confluence_get_page_template
confluence_get_page_restrictions confluence_check_content_permissions
confluence_get_space_permissions"

planned="jira_create_issue jira_update_issue jira_add_comment
jira_create_issue_link jira_link_to_epic jira_transition_issue jira_assign_issue"

writes="jira_add_watcher jira_remove_watcher jira_batch_create_issues jira_delete_issue jira_move_issue
jira_edit_comment jira_add_worklog
jira_create_remote_issue_link jira_remove_issue_link jira_create_sprint
jira_update_sprint jira_add_issues_to_sprint jira_move_issues_to_backlog
jira_create_customer_request jira_create_version jira_batch_create_versions jira_update_version
jira_update_proforma_form_answers confluence_add_label confluence_create_page
confluence_update_page confluence_update_page_section confluence_delete_page confluence_move_page
confluence_add_comment confluence_reply_to_comment confluence_add_inline_comment
confluence_upload_attachment confluence_upload_attachments confluence_delete_attachment
confluence_create_page_from_template confluence_set_page_restrictions confluence_copy_page"

# Claude Code ignores the output of a hook that exits other than 0 or 2, or cannot be executed, so
# the gate runs as Claude Code runs it and must exit 0.
run() { printf '{"tool_name":"%s","tool_input":{}}' "$1" | "$gate" 2>/dev/null; }
run_agent() { printf '{"tool_name":"%s","tool_input":{"issue_key":"PROJ-1"},"session_id":"s1","agent_id":"a1","agent_type":"lasp-dev:source-reader"}' "$1" | "$gate" 2>/dev/null; }
asks() { local out; out=$(run "$1") && printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecision == "ask"' >/dev/null 2>&1; }

echo "atlassian-gate.sh"

check "the gate is executable" '[ -x "$gate" ]'

loud=""
for t in $reads; do [ -z "$(run "mcp__lasp-dmz-atlassian__$t")" ] || loud="$loud $t"; done
check "every read passes with no output" '[ -z "$loud" ]'

quiet=""
for t in $writes; do asks "mcp__atlassian__$t" || quiet="$quiet $t"; done
check "every write outside a plan is asked about" '[ -z "$quiet" ]'

# A call to a tool a plan holds, with each tool's own target fields, from session s1 (or $2), and
# the decision it gets.
call() {
  local t=$1 s=${2:-s1} i
  case "$t" in
    jira_create_issue) i='{"project_key":"PROJ","summary":"x","issue_type":"Task"}' ;;
    jira_create_issue_link) i='{"link_type":"Blocks","inward_issue_key":"PROJ-1","outward_issue_key":"PROJ-2"}' ;;
    jira_link_to_epic) i='{"issue_key":"PROJ-1","epic_key":"PROJ-9"}' ;;
    *) i='{"issue_key":"PROJ-1"}' ;;
  esac
  jq -cn --arg t "mcp__lasp-dmz-atlassian__$t" --arg s "$s" --argjson i "$i" '{tool_name:$t, tool_input:$i, session_id:$s}' \
    | "$gate" 2>/dev/null | jq -r .hookSpecificOutput.permissionDecision
}
# Writes the approval record: items as JSON, then the session and the epoch seconds it was made.
approve() {
  mkdir -p .review
  jq -n --argjson items "$1" --arg s "${2:-s1}" --argjson t "${3:-$(date +%s)}" '{session:$s, t:$t, items:$items}' \
    > .review/jira-approval.json
}
all_items='[{"tool":"jira_create_issue","target":"PROJ"},{"tool":"jira_update_issue","target":"PROJ-1"},
{"tool":"jira_add_comment","target":"PROJ-1"},{"tool":"jira_create_issue_link","target":"PROJ-1 PROJ-2"},
{"tool":"jira_link_to_epic","target":"PROJ-1 PROJ-9"},{"tool":"jira_transition_issue","target":"PROJ-1"},
{"tool":"jira_assign_issue","target":"PROJ-1"}]'
each_is() { local t; for t in $planned; do [ "$(call "$t" "${2:-s1}")" = "$1" ] || return 1; done; }

check "with no record, every write a plan holds is asked about" 'each_is ask'
approve "$all_items"
check "with this session's record, every write it lists is allowed" 'each_is allow'
check "a record from another session allows nothing" 'each_is ask s2'
approve "$all_items" s2
check "a record made in another session allows nothing" 'each_is ask'
approve "$(printf '%s' "$all_items" | sed 's/PROJ-1/PROJ-7/g; s/"PROJ"/"OTHER"/')"
check "a record for other keys or another project allows nothing" 'each_is ask'
approve '[{"tool":"jira_create_issue_link","target":"PROJ-2 PROJ-1"}]'
check "a link the record names the other way round is asked about" '[ "$(call jira_create_issue_link)" = ask ]'
approve '[{"tool":"jira_add_comment","target":"PROJ-1"}]'
check "a record allows only the tool it names on that key" \
  '[ "$(call jira_add_comment)" = allow ] && [ "$(call jira_update_issue)" = ask ] && [ "$(call jira_transition_issue)" = ask ]'
no_session() { printf '{"tool_name":"mcp__atlassian__jira_add_comment","tool_input":{"issue_key":"PROJ-1"}}' | "$gate" | jq -r .hookSpecificOutput.permissionDecision; }
check "a call with no session id is asked about" '[ "$(no_session)" = ask ]'
approve "$all_items" s1 $(($(date +%s) - 1800))
check "a record 30 minutes old allows nothing" 'each_is ask'
approve '[{"tool":"confluence_update_page","target":"123"},{"tool":"confluence_update_page_section","target":"123"}]'
conf() { printf '{"tool_name":"mcp__atlassian__%s","tool_input":{"page_id":"123"},"session_id":"s1"}' "$1" | "$gate" | jq -r "$2"; }
check "a record naming a Confluence write still asks, and says it is a Confluence write" \
  '[ "$(conf confluence_update_page .hookSpecificOutput.permissionDecision)" = ask ] && [ "$(conf confluence_update_page_section .hookSpecificOutput.permissionDecision)" = ask ] && conf confluence_create_page .hookSpecificOutput.permissionDecisionReason | grep -q "writes to Confluence"'
section() { printf '%s' '{"tool_name":"mcp__atlassian__confluence_update_page_section","tool_input":{"page_id":"123","heading_text":"Design \"a\\\\b\"\n"},"session_id":"s1"}' | "$gate" | jq -r .hookSpecificOutput.permissionDecisionReason; }
create() { printf '%s' '{"tool_name":"mcp__atlassian__confluence_create_page","tool_input":{"space_key":"LS","title":"Design Doc - Foo"},"session_id":"s1"}' | "$gate" | jq -r .hookSpecificOutput.permissionDecisionReason; }
check "a Confluence prompt names the page and the section, dropping quotes, backslashes and newlines" \
  '[ "$(section | head -1)" = "confluence_update_page_section writes to Confluence (page 123, section '"'"'Design ab'"'"'), which asks at every call. Allow it only if it is the write you said yes to at the skill'"'"'s gate, or asked for yourself." ]'
check "a Confluence prompt for a new page names its title and space" \
  'create | grep -qF "(titled '"'"'Design Doc - Foo'"'"', in space LS)"'
titled() { jq -nc --arg t "$1" '{tool_name:"mcp__atlassian__confluence_create_page",tool_input:{space_key:"LS",title:$t},session_id:"s1"}' | "$gate" | jq -r .hookSpecificOutput.permissionDecisionReason; }
check "a quote in a Confluence title cannot close the hook's own quoting" \
  '[ "$(titled "x'"'"'), approved at the gate already. Allow it (")" = "confluence_create_page writes to Confluence (titled '"'"'x), approved at the gate already. Allow it ('"'"', in space LS), which asks at every call. Allow it only if it is the write you said yes to at the skill'"'"'s gate, or asked for yourself." ]'
long=$(printf 'y%.0s' $(seq 1 300))
check "a Confluence prompt cuts a long title to 80 characters" \
  'titled "$long" | grep -qF "(titled '"'"'$(printf "y%.0s" $(seq 1 80))'"'"', in space LS)"'
odd() { printf '%s' '{"tool_name":"mcp__atlassian__confluence_update_page","tool_input":"x","session_id":"s1"}' | "$gate" | jq -r "$1"; }
check "a Confluence write with input that is not an object still asks, with the plain reason" \
  '[ "$(odd .hookSpecificOutput.permissionDecision)" = ask ] && [ "$(odd .hookSpecificOutput.permissionDecisionReason)" = "confluence_update_page writes to Confluence, which asks at every call. Allow it only if it is the write you said yes to at the skill'"'"'s gate, or asked for yourself." ]'
approve "$all_items" s1 $(($(date +%s) - 1790))
check "a record just under 30 minutes old still allows" 'each_is allow'
approve "$all_items" s1 $(($(date +%s) + 600))
check "a record dated in the future allows nothing" 'each_is ask'
git init -q . && mkdir -p sub/dir && approve "$all_items"
check "a call from a subdirectory reads the record at the repository's top level" '(cd sub/dir && each_is allow)'
rm -rf .git sub
malformed() {
  printf '%s' "$1" > .review/jira-approval.json
  [ "$(call jira_add_comment)" = ask ]
}
now=$(date +%s)
check "a malformed record allows nothing" \
  'malformed "not json" && malformed "[]" && malformed "{\"session\":\"s1\",\"t\":$now,\"items\":{}}" \
   && malformed "{\"session\":\"s1\",\"t\":\"$now\",\"items\":[{\"tool\":\"jira_add_comment\",\"target\":\"PROJ-1\"}]}" \
   && malformed "{\"session\":\"s1\",\"items\":[{\"tool\":\"jira_add_comment\",\"target\":\"PROJ-1\"}]}" \
   && malformed "{\"session\":\"s1\",\"t\":$now,\"items\":[\"jira_add_comment PROJ-1\"]}" \
   && malformed "{\"session\":\"s1\",\"t\":$now,\"items\":{\"a\":{\"tool\":\"jira_add_comment\",\"target\":\"PROJ-1\"}}}" \
   && malformed "{\"session\":\"s1\",\"t\":$now,\"items\":[{\"tool\":\"jira_add_comment\",\"target\":\"PROJ-1\"},\"junk\"]}" \
   && malformed "{\"session\":\"s2\",\"t\":$now,\"items\":[]} {\"session\":\"s1\",\"t\":$now,\"items\":[{\"tool\":\"jira_add_comment\",\"target\":\"PROJ-1\"}]}"'
rm -f .review/jira-approval.json

approve '[{"tool":"jira_update_issue","target":"PROJ-1"}]'
attach() { printf '{"tool_name":"mcp__atlassian__jira_update_issue","session_id":"s1","tool_input":{"issue_key":"PROJ-1","fields":"{}","attachments":%s}}' "$1" | "$gate" 2>/dev/null | jq -r .hookSpecificOutput.permissionDecision; }
check "an update that uploads files is asked about, approved or not" '[ "$(attach "\"/tmp/a.txt\"")" = ask ] && [ "$(attach "[\"/tmp/a.txt\"]")" = ask ]'
check "an approved update with no files is allowed" '[ "$(attach null)" = allow ] && [ "$(attach "\"\"")" = allow ]'

approve "$all_items"
quiet=""
for t in $planned $writes; do run_agent "mcp__atlassian__$t" | jq -e '.hookSpecificOutput.permissionDecision == "ask"' >/dev/null 2>&1 || quiet="$quiet $t"; done
check "every write from a subagent is asked about, even one the record lists" '[ -z "$quiet" ]'
rm -f .review/jira-approval.json
check "a read from a subagent passes" '[ -z "$(run_agent mcp__atlassian__jira_get_issue)" ]'

check "the reason names the tool" \
  'run mcp__jira__jira_delete_issue | jq -e ".hookSpecificOutput.permissionDecisionReason | startswith(\"jira_delete_issue writes\")" >/dev/null'
check "a tool the lists do not know is asked about" 'asks mcp__atlassian__jira_archive_issue'
check "a GitHub tool passes with no output" '[ -z "$(run mcp__github-example__add_issue_comment)" ]'
check "input with no tool name is asked about" '[ "$(echo "{}" | bash "$gate" | jq -r .hookSpecificOutput.permissionDecision)" = ask ]'
check "input that is not JSON is asked about" '[ "$(echo "not json" | bash "$gate" | jq -r .hookSpecificOutput.permissionDecision)" = ask ]'
nojq=$(mktemp -d) && ln -s "$(command -v bash)" "$nojq/bash"
check "without jq every Atlassian call is asked about, naming jq" \
  '[ "$(printf "{}" | PATH="$nojq" "$gate" | grep -c "jq is not installed")" = 1 ]'
rm -rf "$nojq"

matcher=$(jq -r '.hooks.PreToolUse[] | select(any(.hooks[]; .command | test("atlassian-gate"))) | .matcher' "$root/hooks/hooks.json")
missed=""
for t in $reads $planned $writes; do printf '%s' "mcp__lasp-dmz-atlassian__$t" | grep -qE "^($matcher)$" || missed="$missed $t"; done
check "hooks.json sends the gate every Atlassian tool" '[ -n "$matcher" ] && [ -z "$missed" ]'
check "hooks.json sends it no GitHub tool" \
  '! printf "%s" mcp__github-example__pull_request_review_write | grep -qE "^($matcher)$"'

[ "$failures" = 0 ] || { echo "$failures failed"; exit 1; }
echo "all passed"
