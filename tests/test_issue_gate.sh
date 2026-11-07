#!/usr/bin/env bash
# Feeds hooks/issue-gate.sh github-mcp-server's issue_write and add_issue_comment, under a server
# name of the person's choosing, and checks that a call this session's unexpired, well-formed
# approval record lists with its target is allowed, and that every other call gets no decision:
# no record, an unlisted target or tool, another session, a stale, future or malformed record, a
# subagent's call, a create of another title, a call carrying an argument no plan sends, input it
# cannot read, and any call without jq. Also checks that hooks.json's matcher sends it those two tools and no other.
# Run: bash tests/test_issue_gate.sh
set -u

root=$(cd "$(dirname "$0")/.." && pwd)
gate="$root/hooks/issue-gate.sh"
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

# The decision for a call of $1 with input $2, from session $3 (default s1): allow, or none when
# the gate printed nothing. Anything else, a non-zero exit included, is printed as it came.
decision() {
  local out
  jq -e . >/dev/null 2>&1 <<<"$2" || { echo "bad test input"; return; }
  out=$(jq -cn --arg t "mcp__github-example__$1" --argjson i "$2" --arg s "${3:-s1}" '{tool_name:$t, tool_input:$i, session_id:$s}' | "$gate" 2>/dev/null) \
    || { echo "exit $?"; return; }
  [ -z "$out" ] && { echo none; return; }
  printf '%s' "$out" | jq -r .hookSpecificOutput.permissionDecision 2>/dev/null || printf '%s' "$out"
}
create='{"method":"create","owner":"example","repo":"widgets","title":"Refuse a negative count","body":"b","labels":["ready"]}'
update='{"method":"update","owner":"example","repo":"widgets","issue_number":12,"title":"t","body":"b","labels":["ready"],"state":"closed","state_reason":"duplicate","duplicate_of":9}'
comment='{"owner":"example","repo":"widgets","issue_number":12,"body":"c"}'
# Writes the approval record: items as JSON, then the session and the epoch seconds it was made.
approve() {
  mkdir -p .review
  jq -n --argjson items "$1" --arg s "${2:-s1}" --argjson t "${3:-$(date +%s)}" '{session:$s, t:$t, items:$items}' \
    > .review/github-approval.json
}
all_items='[{"tool":"issue_write","target":"example/widgets Refuse a negative count"},{"tool":"issue_write","target":"example/widgets#12"},
{"tool":"add_issue_comment","target":"example/widgets#12"}]'
each_is() {
  [ "$(decision issue_write "$create" "${2:-s1}")" = "$1" ] && [ "$(decision issue_write "$update" "${2:-s1}")" = "$1" ] \
    && [ "$(decision add_issue_comment "$comment" "${2:-s1}")" = "$1" ]
}

echo "issue-gate.sh"

check "the gate is executable" '[ -x "$gate" ]'
check "with no record, no call gets a decision" 'each_is none'
approve "$all_items"
check "with this session's record, a listed create, update and comment are allowed" 'each_is allow'
check "the reason names the tool" \
  'jq -cn --argjson i "$create" "{tool_name:\"mcp__gh__issue_write\", tool_input:\$i, session_id:\"s1\"}" | "$gate" | jq -e ".hookSpecificOutput.permissionDecisionReason == \"issue_write is an item of the write plan you approved.\"" >/dev/null'
check "a call from another session gets no decision" 'each_is none s2'
approve "$all_items" s2
check "a record made in another session allows nothing" 'each_is none'
approve "$(printf '%s' "$all_items" | sed 's/#12/#13/g; s/"example\/widgets Refuse/"example\/other Refuse/')"
check "a record for another issue or repository allows nothing" 'each_is none'
approve '[{"tool":"issue_write","target":"example/widgets Refuse a negative count"}]'
check "a create's record does not allow an update of an issue in that repository" \
  '[ "$(decision issue_write "$create")" = allow ] && [ "$(decision issue_write "$update")" = none ]'
other_title=$(printf '%s' "$create" | jq -c '.title = "Refuse a negative count in by_part"')
feedback='{"method":"create","owner":"example","repo":"widgets","title":"ticket-draft: wrote 900 words for a one-line fix","body":"b","labels":["skill-feedback"]}'
no_title=$(printf '%s' "$create" | jq -c 'del(.title)')
check "a create's record allows that title only: another create, skill-feedback's in this session included, gets no decision" \
  '[ "$(decision issue_write "$other_title")" = none ] && [ "$(decision issue_write "$feedback")" = none ] && [ "$(decision issue_write "$no_title")" = none ]'
approve '[{"tool":"issue_write","target":"example/widgets"}]'
check "a create's target without its title allows no create" '[ "$(decision issue_write "$create")" = none ]'
# The record as issues.md builds it: the items written to a file, read by jq with --slurpfile.
quoted=$(printf '%s' "$create" | jq -c '.title = "Don'"'"'t count a \"negative\" part"')
jq -n --argjson c "$quoted" '[{tool: "issue_write", target: "example/widgets \($c.title)"}]' > .review/github-approval-items.json
jq -n --arg s s1 --argjson t "$(date +%s)" --slurpfile items .review/github-approval-items.json \
  '{session: $s, t: $t, items: $items[0]}' > .review/github-approval.json
check "a title holding an apostrophe and double quotes, recorded from the items file, allows that create" \
  '[ "$(decision issue_write "$quoted")" = allow ] && [ "$(decision issue_write "$create")" = none ]'
newline=$(printf '%s' "$create" | jq -c '.title = "Refuse a negative count\n"')
approve '[{"tool":"issue_write","target":"example/widgets Refuse a negative count"}]'
check "a target is compared byte for byte: a title with a trailing newline does not match one without" \
  '[ "$(decision issue_write "$newline")" = none ] && [ "$(decision issue_write "$create")" = allow ]'
rm -f .review/github-approval-items.json
approve '[{"tool":"add_issue_comment","target":"example/widgets#12"}]'
check "a record allows only the tool it names on that target" \
  '[ "$(decision add_issue_comment "$comment")" = allow ] && [ "$(decision issue_write "$update")" = none ]'
approve '[{"tool":"issue_write","target":"example/widgets#12"}]'
check "an update's record does not allow a comment on the issue" '[ "$(decision add_issue_comment "$comment")" = none ]'
approve "$all_items"
with_parent=$(printf '%s' "$create" | jq -c '. + {parent_issue_number: 3}')
with_fields=$(printf '%s' "$create" | jq -c '. + {issue_fields: [{field_name: "Estimate", value: 3}]}')
check "a create naming a parent or issue fields gets no decision, though the record lists the create" \
  '[ "$(decision issue_write "$with_parent")" = none ] && [ "$(decision issue_write "$with_fields")" = none ]'
extra() { printf '%s' "$1" | jq -c ". + {$2}"; }
check "a create carrying assignees, a milestone or a type gets no decision" \
  '[ "$(decision issue_write "$(extra "$create" "assignees: [\"bob\"]")")" = none ] && [ "$(decision issue_write "$(extra "$create" "milestone: 2")")" = none ] \
   && [ "$(decision issue_write "$(extra "$create" "type: \"Bug\"")")" = none ]'
check "an update carrying assignees, a milestone or a type gets no decision" \
  '[ "$(decision issue_write "$(extra "$update" "assignees: [\"bob\"]")")" = none ] && [ "$(decision issue_write "$(extra "$update" "milestone: 2")")" = none ] \
   && [ "$(decision issue_write "$(extra "$update" "type: null")")" = none ]'
check "a comment carrying assignees, a milestone or a type gets no decision" \
  '[ "$(decision add_issue_comment "$(extra "$comment" "assignees: [\"bob\"]")")" = none ] && [ "$(decision add_issue_comment "$(extra "$comment" "milestone: 2")")" = none ] \
   && [ "$(decision add_issue_comment "$(extra "$comment" "type: \"Bug\"")")" = none ]'
check "a create carrying an update's arguments gets no decision" '[ "$(decision issue_write "$(extra "$create" "state: \"closed\"")")" = none ]'
reaction=$(printf '%s' "$comment" | jq -c 'del(.body) + {reaction: "+1"}')
on_comment=$(printf '%s' "$comment" | jq -c '. + {comment_id: 5}')
check "a reaction gets no decision, though the record lists a comment on the issue" \
  '[ "$(decision add_issue_comment "$reaction")" = none ] && [ "$(decision add_issue_comment "$on_comment")" = none ]'
no_method=$(printf '%s' "$create" | jq -c 'del(.method)')
other_method=$(printf '%s' "$create" | jq -c '.method = "delete"')
no_number=$(printf '%s' "$update" | jq -c 'del(.issue_number)')
text_number=$(printf '%s' "$update" | jq -c '.issue_number = "12"')
part_number=$(printf '%s' "$update" | jq -c '.issue_number = 12.5')
no_owner=$(printf '%s' "$comment" | jq -c 'del(.owner)')
check "a call naming no method, another method, no repository or no whole number gets no decision" \
  '[ "$(decision issue_write "$no_method")" = none ] && [ "$(decision issue_write "$other_method")" = none ] \
   && [ "$(decision issue_write "$no_number")" = none ] && [ "$(decision issue_write "$text_number")" = none ] \
   && [ "$(decision issue_write "$part_number")" = none ] && [ "$(decision issue_write "\"x\"")" = none ] \
   && [ "$(decision add_issue_comment "$no_owner")" = none ]'
no_session() { printf '%s' "{\"tool_name\":\"mcp__gh__issue_write\",\"tool_input\":$create}" | "$gate"; }
check "a call with no session id gets no decision" '[ -z "$(no_session)" ]'
approve "$all_items" s1 $(($(date +%s) - 1800))
check "a record 30 minutes old allows nothing" 'each_is none'
approve "$all_items" s1 $(($(date +%s) - 1790))
check "a record just under 30 minutes old still allows" 'each_is allow'
approve "$all_items" s1 $(($(date +%s) + 600))
check "a record dated in the future allows nothing" 'each_is none'
git init -q . && mkdir -p sub/dir && approve "$all_items"
check "a call from a subdirectory reads the record at the repository's top level" '(cd sub/dir && each_is allow)'
rm -rf .git sub
malformed() {
  printf '%s' "$1" > .review/github-approval.json
  [ "$(decision add_issue_comment "$comment")" = none ]
}
now=$(date +%s)
check "a malformed record allows nothing" \
  'malformed "not json" && malformed "[]" && malformed "{\"session\":\"s1\",\"t\":$now,\"items\":{}}" \
   && malformed "{\"session\":\"s1\",\"t\":\"$now\",\"items\":[{\"tool\":\"add_issue_comment\",\"target\":\"example/widgets#12\"}]}" \
   && malformed "{\"session\":\"s1\",\"items\":[{\"tool\":\"add_issue_comment\",\"target\":\"example/widgets#12\"}]}" \
   && malformed "{\"session\":\"s1\",\"t\":$now,\"items\":[\"add_issue_comment example/widgets#12\"]}" \
   && malformed "{\"session\":\"s1\",\"t\":$now,\"items\":[{\"tool\":\"add_issue_comment\",\"target\":\"example/widgets#12\"},\"junk\"]}" \
   && malformed "{\"session\":\"s2\",\"t\":$now,\"items\":[]} {\"session\":\"s1\",\"t\":$now,\"items\":[{\"tool\":\"add_issue_comment\",\"target\":\"example/widgets#12\"}]}"'

approve "$all_items"
agent() { jq -cn --arg t "mcp__github-example__$1" --argjson i "$2" '{tool_name:$t, tool_input:$i, session_id:"s1", agent_id:"a1", agent_type:"lasp-dev:source-reader"}' | "$gate"; }
check "a call from a subagent gets no decision, even one the record lists" \
  '[ -z "$(agent issue_write "$create")" ] && [ -z "$(agent issue_write "$update")" ] && [ -z "$(agent add_issue_comment "$comment")" ]'
check "another GitHub write gets no decision" '[ "$(decision sub_issue_write "$update")" = none ] && [ "$(decision update_issue_comment "$comment")" = none ]'
check "input with no tool name, or not JSON, gets no decision and exits 0" \
  '[ -z "$(echo "{}" | "$gate")" ] && [ -z "$(echo "not json" | "$gate")" ]'
nojq=$(mktemp -d) && ln -s "$(command -v bash)" "$nojq/bash"
check "without jq a listed call gets no decision and exits 0" \
  'out=$(jq -cn --argjson i "$create" "{tool_name:\"mcp__gh__issue_write\", tool_input:\$i, session_id:\"s1\"}" | PATH="$nojq" "$gate") && [ -z "$out" ]'
rm -rf "$nojq"
rm -f .review/github-approval.json

matcher=$(jq -r '.hooks.PreToolUse[] | select(any(.hooks[]; .command | test("issue-gate"))) | .matcher' "$root/hooks/hooks.json")
check "hooks.json sends the gate issue_write and add_issue_comment under any server name" \
  '[ -n "$matcher" ] && (for t in mcp__github__issue_write mcp__github-example__add_issue_comment; do printf "%s" "$t" | grep -qE "^($matcher)$" || exit 1; done)'
check "hooks.json sends it no other tool" \
  '(for t in mcp__github__sub_issue_write mcp__github__update_issue_comment mcp__github__issue_read mcp__atlassian__jira_add_comment Bash; do ! printf "%s" "$t" | grep -qE "^($matcher)$" || exit 1; done)'

[ "$failures" = 0 ] || { echo "$failures failed"; exit 1; }
echo "all passed"
