#!/usr/bin/env bash
# PreToolUse and PostToolUse on Read, Grep, Bash, Edit, Write, MultiEdit and NotebookEdit; the
# argument says which, `pre` or `post`. scripts/controlled_gate.py decides: before a call that reads
# past the first line of a `.review/` file opening with `Controlled:`, it asks, naming the item and
# its warning, unless the person cleared that item earlier in the session; after such a call ran,
# it records the item as cleared. When `pre` fails, or prints what is not a decision, the call is
# asked about, since nothing checked it. With no python3, a call whose input names `.review` is
# asked about.
set -u
ask='{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"%s"}}\n'
mode=${1:-pre}
input=$(cat)
command -v python3 >/dev/null 2>&1 || {
  if [ "$mode" = pre ]; then
    case "$input" in
      *.review*) printf "$ask" "python3 is not installed, so the controlled-file check could not run on this call, which names .review. Allow it only if no file it reads opens with Controlled:." ;;
    esac
  fi
  exit 0
}
if [ "$mode" = post ]; then
  printf '%s' "$input" | python3 "$(dirname "$0")/../scripts/controlled_gate.py" post >/dev/null 2>&1
  exit 0
fi
out=$(printf '%s' "$input" | python3 "$(dirname "$0")/../scripts/controlled_gate.py" pre 2>/dev/null)
status=$?
if [ "$status" -ne 0 ]; then
  printf "$ask" "The controlled-file check failed (exit $status), so it could not tell whether this call reads a .review file that opens with Controlled:. Allow it only if it reads no such file."
elif [ -n "$out" ] && ! printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hookSpecificOutput"]["permissionDecision"]' 2>/dev/null; then
  printf "$ask" "The controlled-file check printed something it could not read, so this call is asked about."
else
  [ -n "$out" ] && printf '%s\n' "$out"
fi
exit 0
