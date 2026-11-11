#!/usr/bin/env bash
# PreToolUse and PostToolUse on Read, Grep, Bash, Edit, Write, MultiEdit and NotebookEdit; the
# argument says which, `pre` or `post`. scripts/controlled_gate.py decides: before a call that reads
# past the first line of a `.review/` file opening with `Controlled:`, it asks, naming the item and
# its warning, unless the person cleared that item earlier in the session; after such a call ran,
# it records the item as cleared. It asks only on a held file it found: when the check cannot run,
# fails, or prints what is not a decision, the call passes.
set -u
mode=${1:-pre}
command -v python3 >/dev/null 2>&1 || exit 0
if [ "$mode" = post ]; then
  python3 "$(dirname "$0")/../scripts/controlled_gate.py" post >/dev/null 2>&1
  exit 0
fi
out=$(python3 "$(dirname "$0")/../scripts/controlled_gate.py" pre 2>/dev/null) || exit 0
if [ -n "$out" ] && printf '%s' "$out" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["hookSpecificOutput"]["permissionDecision"]' 2>/dev/null; then
  printf '%s\n' "$out"
fi
exit 0
