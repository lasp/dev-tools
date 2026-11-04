#!/usr/bin/env bash
# Records what a build actually did, so the PR body's "already checked" block is measured
# rather than remembered.
#
#   build-record.sh guard     PreToolUse on Bash|Write|Edit: refuses, once, a call from a session
#                             whose lock was taken; refuses a Write or Edit in another repository
#                             while this session holds the lock; a write under .review/ keeps it
#                             ignored
#   build-record.sh event     PostToolUse: classify one tool call, append it
#   build-record.sh prompt    UserPromptSubmit: a typed /implement-change starts a build
#   build-record.sh start     by hand: start or resume a build for this session, or `manual`;
#                             `start fresh` starts one even when a build is recorded on this branch
#   build-record.sh summary   Stop: fold the events into a block
#   build-record.sh end       SessionEnd: release this session's lock, then summary
#   build-record.sh release   by implement-change and pr-fix at their last step: release this
#                             session's lock
#   build-record.sh take S    by hand, on the person's say-so: take another session's live lock
#                             for skill S, implement-change or pr-fix; exits 1 without a session
#
# It also holds the working tree for one session at a time while it changes the branch. Starting
# implement-change or pr-fix writes .review/lock, one JSON line {skill, session, branch, t}. A
# live lock another session holds is never overwritten: the hook tells the model to ask the person,
# who may take it over with `take`, and no build is started or reset until then. The holder's own
# events keep the lock fresh; one untouched for LOCK_STALE_MIN minutes is stale and taken with a
# note. A taken lock lists the sessions it was taken from in took_from, and each is told once, at
# its next prompt or tool call, that the working tree is no longer its own: as context on a prompt
# or after a call, and as the refusal of the call when that is a Bash, Write or Edit call. The
# skill releases it at its last step, and SessionEnd when its session matches.
#
# Every .review/ path is under the repository's top level, found from the payload's cwd, or the
# working directory when the payload names none, so a call from a subdirectory reaches the same
# record; outside a repository it is that directory itself. A session started in one repository
# that changes another would measure that work here. So while this session holds the lock or
# its open build, a Write or Edit whose file is in another repository, one neither holding this
# one nor held by it nor sharing its git directory as a worktree does, marks that build
# `elsewhere`, and its summary then records its gates and tokens as not recorded; while the
# session holds the lock, the call is refused too.
# Events and summaries are inert until that directory has a .review/ directory; a phase
# skill's start, or a write under it, creates it, and scripts/review_dir.sh keeps it out of git
# where the repository's ignore rules do not. A build starts when implement-change is invoked,
# by the Skill tool or by a typed slash command (which fires UserPromptSubmit, not PostToolUse).
# The start event records the branch and the session. Invoking implement-change again on the
# same branch resumes that build; on another branch it parks a closed build under
# .review/build/done/<branch>/, drops an open one, and starts over, or brings that branch's parked
# build back. `start fresh` does the same on the build's own branch too and brings no parked build
# back, so a new change in the session whose open build followed it onto the new branch starts its
# own record. A build is closed once implement-change writes .review/build/outcome.md: events
# then change nothing, and the first summary after it on the build's branch writes the block and
# appends a fold event, after which later summaries leave the block alone until another event is
# recorded. Starting pr-create runs that summary too, since an outcome and pr-create in one turn
# have no Stop between them. No event records a closed build's move: it is parked instead. Invoking
# implement-change again on the branch resumes the build: an open one gets a resume event, and a
# closed one keeps outcome.md, the block and the fold as they are, with nothing appended, until
# implement-change removes outcome.md to go back into the build and runs `start`, which appends
# the resume event.
# The wall clock leaves out the time before each resume event: the gap between sessions, or the
# wait while a finished build sat at its diff gate. `start` is also for a build the hook did not see
# begin: it takes the session from a payload on stdin when there is one. The build follows the
# session that started it onto a new branch, since implement-change branches after it starts;
# events and summaries from another session on another branch are ignored, and tokens are
# counted only in the session that started the build, its own subagents included. Always exits
# 0, but for `take`, and `start` with an argument other than `fresh`, run by hand: a hook that fails
# a tool call would be worse than no measurement.
set -u
# A hook reads a standard elsewhere only as a build or review last fetched it, never fetching.
export STANDARD_OFFLINE=1

mode="${1:-event}"
dir=".review/build"
log="$dir/events.jsonl"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
review_dir="$(cd "$here/.." && pwd)/scripts/review_dir.sh"

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# True once the repository has a .review/ directory, making .review/build/ in it.
active() { [ -d .review ] && mkdir -p "$dir" 2>/dev/null; }

append() { printf '%s\n' "$1" >>"$log" 2>/dev/null || true; }

# The branch, or empty with none, a detached HEAD included.
branch() { git symbolic-ref --short -q HEAD 2>/dev/null || echo ""; }

start_field() { [ -s "$log" ] && head -1 "$log" | jq -r ".$1 // empty" 2>/dev/null; }

# The branch the build is on now: the latest branch any start or move event recorded.
build_branch() { [ -s "$log" ] && jq -r 'select(.branch) | .branch' "$log" 2>/dev/null | tail -1; }

# True when the recorded build is branch $1's. With no branch, it is only the build session $2
# started, so detached checkouts never share one.
this_build() { [ "$(build_branch)" = "$1" ] && { [ -n "$1" ] || [ "$2" = "$(start_field session)" ]; }; }

# True when the block was folded after the outcome: the log's last event is the fold. Nothing is
# appended while outcome.md exists, a resume included, so any later event means the build was
# reopened.
folded() { [ "$(tail -1 "$log" | jq -r '.kind // empty' 2>/dev/null)" = fold ]; }

# Moves the recorded build to done/<its branch>/ when it is closed, so a build on another branch
# never deletes a finished one: pr-create on that branch still finds its outcome and block.
park() {
  local old f
  old=$(build_branch)
  [ -n "$old" ] && [ -e "$dir/outcome.md" ] || return 0
  rm -rf "${dir:?}/done/$old" 2>/dev/null
  mkdir -p "$dir/done/$old" 2>/dev/null || return 0
  for f in "$log" "$dir/outcome.md" "$dir/already-checked.md" "$dir"/wave-*.md; do
    [ -e "$f" ] && mv "$f" "$dir/done/$old/" 2>/dev/null
  done
  return 0
}

# Moves this branch's parked build back into place; false when there is none.
unpark() {
  [ -s "$dir/done/$1/events.jsonl" ] || return 1
  mv "$dir/done/$1"/* "$dir/" 2>/dev/null
  rm -rf "${dir:?}/done/$1" 2>/dev/null
  return 0
}

# Starts a build, or resumes the one already recorded for this branch. A closed build, one with
# outcome.md, is left as it is. Starting on another branch parks a closed build and drops an open
# one, then brings back this branch's parked build, if any, under the same rules. With `fresh`, a
# build recorded on this branch is parked or dropped too, and no parked build comes back.
start_build() {
  local b s
  mkdir -p "$dir" 2>/dev/null
  b=$(branch)
  s="$1"
  if [ "${2:-}" != fresh ] && [ -s "$log" ] && this_build "$b" "$s"; then
    [ -e "$dir/outcome.md" ] && return 0
    rm -f "$dir/already-checked.md" 2>/dev/null
    append "$(jq -cn --arg t "$(now)" --arg s "$s" '{t:$t,kind:"resume",session:$s}')"
  else
    park
    rm -f "$log" "$dir/already-checked.md" "$dir/outcome.md" "$dir"/wave-*.md 2>/dev/null
    if [ "${2:-}" != fresh ] && [ -n "$b" ] && unpark "$b"; then
      start_build "$s"
      return 0
    fi
    append "$(jq -cn --arg t "$(now)" --arg b "$b" --arg s "$s" '{t:$t,kind:"start",branch:$b,session:$s}')"
  fi
}

# True when a build is recorded and it belongs to the current branch. The session that started
# the build takes it to a new branch; any other session on another branch does not.
on_build_branch() {
  local b s
  [ -s "$log" ] || return 1
  b=$(branch)
  s="$1"
  this_build "$b" "$s" && return 0
  [ -n "$s" ] && [ -n "$b" ] && [ "$s" = "$(start_field session)" ] || return 1
  append "$(jq -cn --arg t "$(now)" --arg b "$b" '{t:$t,kind:"move",branch:$b}')"
}

# The phase skill a name refers to, bare or with a plugin prefix, or nothing.
phase_skill() {
  case "$1" in
    implement-change | *:implement-change | pr-fix | *:pr-fix)
      printf '%s' "${1##*:}"
      ;;
  esac
}

# A lock untouched this many minutes is stale. Its holder's own hook events touch it, so this is
# idle time, not age: long enough for a gate wait over lunch or a meeting, short of overnight, so a
# session that crashed yesterday never blocks today. where.sh uses the same number.
LOCK_STALE_MIN=240

lock_stale() { [ -n "$(find .review/lock -mmin +"$LOCK_STALE_MIN" 2>/dev/null)" ]; }

# Keeps the lock fresh while the session holding it is active.
touch_lock() {
  [ -n "$1" ] && [ -s .review/lock ] && [ "$(jq -r '.session // empty' .review/lock 2>/dev/null)" = "$1" ] &&
    touch .review/lock 2>/dev/null
  return 0
}

# Creates .review/ and keeps it ignored, then takes .review/lock for this session. A stale lock is
# taken, with a note, and a live one only with `force`, from `take`; either way the session that
# held it joins took_from. Returns 1 outside a git repository, where review_dir.sh creates nothing,
# and, having told the model to ask the person, when another session holds a live lock.
take_lock() {
  local held note added took="" from="" prior
  added=$(bash "$review_dir" 2>/dev/null)
  [ -d .review ] || return 1
  held=$(jq -r '.session // empty' .review/lock 2>/dev/null)
  if [ -s .review/lock ] && [ "$held" != "$2" ]; then
    from=$held
    if lock_stale; then
      took=$(jq -r '"Took a stale `.review/lock`: \(.skill) in another session, on \(if (.branch // "") == "" then "no branch" else .branch end), untouched for over 4 hours."' .review/lock 2>/dev/null)
    elif [ "${4:-}" != force ]; then
      note=$(jq -r '"`.review/lock` is held by \(.skill) in another session, active in the last 4 hours, on \(if (.branch // "") == "" then "no branch" else .branch end). Do not go on yet: ask the person in one AskUserQuestion whether to Take over, Stop, or discuss it."' .review/lock 2>/dev/null)
      note="$note On Take over, run: $(run_line "$(jq -cn --arg s "$2" '{session_id: $s}')" "take $1")"
      jq -cn --arg e "$3" --arg c "${added:+$added }$note" '{hookSpecificOutput: {hookEventName: $e, additionalContext: $c}}'
      return 1
    fi
  fi
  prior=$(jq -c --arg f "$from" --arg s "$2" '(.took_from // []) + [$f | select(. != "")] - [$s] | unique' .review/lock 2>/dev/null)
  jq -cn --arg k "$1" --arg s "$2" --arg b "$(branch)" --arg t "$(now)" --argjson f "${prior:-[]}" \
    '{skill: $k, session: $s, branch: $b, t: $t} + (if $f == [] then {} else {took_from: $f} end)' >.review/lock 2>/dev/null
  added="${added:+$added }$took"
  [ -z "${added// /}" ] || jq -cn --arg e "$3" --arg c "$added" '{hookSpecificOutput: {hookEventName: $e, additionalContext: $c}}'
  return 0
}

# When another session took this session's lock: prints the output that tells it, a denial for
# PreToolUse and context for any other event $2, and drops it from took_from without refreshing the
# lock's age, so it is told once. False, printing nothing, otherwise.
tell_taken() {
  local note tmp=.review/lock.tmp
  [ -n "$1" ] && [ -s .review/lock ] &&
    jq -e --arg s "$1" '(.took_from // []) | index($s)' .review/lock >/dev/null 2>&1 || return 1
  note=$(jq -r '"Another session took the `.review/lock` this session held, and holds it for \(.skill) on \(if (.branch // "") == "" then "no branch" else .branch end): this working tree is no longer held by this session. Stop and ask the person before any further edit, commit or push."' .review/lock 2>/dev/null)
  jq -c --arg s "$1" '.took_from -= [$s] | if .took_from == [] then del(.took_from) else . end' .review/lock >"$tmp" 2>/dev/null &&
    touch -r .review/lock "$tmp" && mv "$tmp" .review/lock
  if [ "$2" = PreToolUse ]; then
    jq -cn --arg c "$note" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $c}}'
  else
    jq -cn --arg e "$2" --arg c "$note" '{hookSpecificOutput: {hookEventName: $e, additionalContext: $c}}'
  fi
}

# True when the command runs the tool in command position: at the start, or after `&&`, `||`,
# `;`, `|` or `(`, after any `NAME=value` assignments, optionally through a runner (`timeout N`,
# `time`, `env`, `uv run` or `uvx` with its options, `poetry run`, `python3.12 -m`) or by path,
# and followed by whitespace, `)`, `|`, `;`, `&` or the end. Quoted strings are removed first, so
# `grep pytest`, `pip show pytest` and `git commit -m 'x; pytest ok'` are not a test run. `make`,
# `tox` and `nox` are not runners here. A run that only prints information, with `--collect-only`
# (`--co`), `--version` (`-V`) or `--help` (`-h`) among its words, is not a run of the tool; another
# joined to it by `&&`, `||`, `;` or `|` still is.
invokes() {
  printf '%s' "$1" | sed -E "s/'[^']*'//g; s/\"[^\"]*\"//g" | awk '{ gsub(/&&|\|\||;|\|/, "\n"); print }' | grep -E \
    "(^|&&|\|\||;|\||\()[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*(env[[:space:]]+|time[[:space:]]+|timeout[[:space:]]+[0-9]+[smh]?[[:space:]]+)*(((uv|poetry|pdm|hatch)[[:space:]]+run|uvx)[[:space:]]+(-[^[:space:]]+[[:space:]]+([^-[:space:]][^[:space:]]*[[:space:]]+)?)*)?([^[:space:]]*/)?(python(3(\.[0-9]+)?)?[[:space:]]+-m[[:space:]]+)?([^[:space:]]*/)?($2)([[:space:];|&)]|\$)" |
    grep -Eqv "[[:space:]](--collect-only|--co|--version|-V|--help|-h)([[:space:])]|\$)"
}

# The path as the filesystem resolves it, for a file that may not exist yet: its nearest existing
# directory, symlinks resolved, then the rest as written.
resolved() {
  local p="$1" rest=""
  [ "${p#/}" = "$p" ] && p="$PWD/$p"
  while [ -n "$p" ] && [ ! -d "$p" ]; do
    rest="/${p##*/}$rest"
    p="${p%/*}"
  done
  printf '%s%s' "$(cd "${p:-/}" && pwd -P)" "$rest"
}

# The top level of the repository a file is in, symlinks resolved, or empty outside one.
repo_of() {
  local d
  d=$(resolved "$1")
  d=${d%/*}
  while [ -n "$d" ] && [ ! -d "$d" ]; do d=${d%/*}; done
  d=$(git -C "${d:-/}" rev-parse --show-toplevel 2>/dev/null) && cd "$d" 2>/dev/null && pwd -P
}

# The git directory a repository's worktrees share, symlinks resolved.
common_of() { (cd "$1" 2>/dev/null && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P); }

# True when session $1 holds the lock here or started the open build here.
building() {
  [ "$(jq -r '.session // empty' .review/lock 2>/dev/null)" = "$1" ] && return 0
  [ -s "$log" ] && [ ! -e "$dir/outcome.md" ] && [ "$(start_field session)" = "$1" ]
}

# True when top level $1 is another repository than this one: neither holds the other, as a
# submodule, a nested worktree or a repository at the home directory does, and the two share no
# git directory, as worktrees of one repository do.
another() {
  local me
  me=$(pwd -P)
  case "$1/" in "$me"/*) return 1 ;; esac
  case "$me/" in "$1"/*) return 1 ;; esac
  [ "$(common_of "$1")" != "$(common_of "$me")" ]
}

# A shell command piping JSON $1 into this script's mode $2, single-quoted so any path survives.
run_line() {
  local j=$1 h="$here/build-record.sh" r="'\\''"
  printf "printf '%%s' '%s' | bash '%s' %s" "${j//\'/$r}" "${h//\'/$r}" "$2"
}

# Session $1 is writing in repository $2, not this one: marks the open build it started here, once,
# and, when it holds the lock, refuses the call. False, printing nothing, when it holds no lock.
elsewhere() {
  if [ -s "$log" ] && [ ! -e "$dir/outcome.md" ] && [ "$(start_field session)" = "$1" ] &&
    ! grep -q '"kind":"elsewhere"' "$log"; then
    append "$(jq -cn --arg t "$(now)" --arg r "$2" '{t:$t,kind:"elsewhere",repo:$r}')"
  fi
  [ "$(jq -r '.session // empty' .review/lock 2>/dev/null)" = "$1" ] || return 1
  jq -cn --arg c "This session holds \`.review/lock\` in $top for $(jq -r .skill .review/lock), and records its build there, but this edit is in $2. The work would be measured in the wrong repository. Do not go on: ask the person in one AskUserQuestion whether to Stop and start a session in $2 (recommended), Go on unrecorded, or discuss it. On either Stop or Go on unrecorded, run: $(run_line "$(jq -cn --arg s "$1" --arg c "$top" '{session_id: $s, cwd: $c}')" release)" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $c}}'
}

# A hook's payload; `start`, `release` and `take` run by hand may have none.
payload=""
[ -t 0 ] || payload=$(cat 2>/dev/null) || payload=""
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null)
cwd=${cwd:-$PWD}
top=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || top=$cwd
if ! cd "$top" 2>/dev/null; then
  [ "$mode" = take ] && { echo "build-record.sh take: cannot enter $top" >&2; exit 1; }
  exit 0
fi

if [ "$mode" = "guard" ]; then
  command -v jq >/dev/null 2>&1 || exit 0
  session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
  tell_taken "$session" PreToolUse && exit 0
  file=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
  [ -n "$file" ] || exit 0
  git rev-parse --git-dir >/dev/null 2>&1 || exit 0
  if [ -n "$session" ] && building "$session"; then
    there=$(repo_of "$file")
    [ -n "$there" ] && another "$there" && elsewhere "$session" "$there" && exit 0
  fi
  case "$(resolved "$file")" in
    "$(resolved "$top")"/.review/*) bash "$review_dir" ;;
  esac
  exit 0
fi

if [ "$mode" = "prompt" ]; then
  command -v jq >/dev/null 2>&1 || exit 0
  prompt=$(printf '%s' "$payload" | jq -r '.prompt // empty' 2>/dev/null)
  session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
  touch_lock "$session"
  name=$(printf '%s\n' "$prompt" | head -1 | sed -nE 's|^[[:space:]]*/([A-Za-z0-9_-]+:)?([A-Za-z0-9_-]+)([[:space:]].*)?$|\2|p')
  skill=$(phase_skill "$name")
  # A phase skill's start goes to take_lock instead, which offers the take-over, so the notice is
  # dropped unprinted.
  if [ -z "$skill" ]; then
    tell_taken "$session" UserPromptSubmit
    exit 0
  fi
  tell_taken "$session" UserPromptSubmit >/dev/null
  take_lock "$skill" "$session" UserPromptSubmit || exit 0
  [ "$skill" = "implement-change" ] && start_build "$session"
  exit 0
fi

case "$mode" in
  "release")
    # Run by implement-change and pr-fix at their last step: this session's lock goes.
    command -v jq >/dev/null 2>&1 || exit 0
    session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
    [ -n "$session" ] && [ "$(jq -r '.session // empty' .review/lock 2>/dev/null)" = "$session" ] && rm -f .review/lock
    exit 0
    ;;
  "take")
    # Run when the person says to take over another session's live lock.
    command -v jq >/dev/null 2>&1 || { echo "build-record.sh take: needs jq" >&2; exit 1; }
    session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
    skill=$(phase_skill "${2:-}")
    if [ -z "$session" ] || [ -z "$skill" ]; then
      echo "build-record.sh take: needs {\"session_id\"} on stdin and implement-change or pr-fix" >&2
      exit 1
    fi
    take_lock "$skill" "$session" PostToolUse force >/dev/null || exit 1
    [ "$skill" = "implement-change" ] && start_build "$session"
    exit 0
    ;;
  "start")
    case "${2:-}" in
      "" | fresh) ;;
      *) echo "build-record.sh start: takes no argument, or fresh" >&2; exit 1 ;;
    esac
    command -v jq >/dev/null 2>&1 || exit 0
    active || exit 0
    session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
    start_build "${session:-manual}" "${2:-}"
    exit 0
    ;;
esac

if [ "$mode" = "event" ]; then
  command -v jq >/dev/null 2>&1 || exit 0

  tool=$(printf '%s' "$payload" | jq -r '.tool_name // empty' 2>/dev/null)
  [ -n "$tool" ] || exit 0
  session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
  touch_lock "$session"
  # A phase skill's start goes to take_lock instead, which offers the take-over, so the notice is
  # dropped unprinted.
  if [ "$tool" != "Skill" ] || [ -z "$(phase_skill "$(printf '%s' "$payload" | jq -r '.tool_input.skill // empty' 2>/dev/null)")" ]; then
    tell_taken "$session" PostToolUse && exit 0
  fi

  if [ "$tool" = "Skill" ]; then
    # pr-create copies the block into the pull request body, and a build whose outcome and
    # pr-create fall in one turn has had no Stop to fold it, so fold it now.
    case "$(printf '%s' "$payload" | jq -r '.tool_input.skill // empty' 2>/dev/null)" in
      pr-create | *:pr-create) printf '%s' "$payload" | "$here/build-record.sh" summary; exit 0 ;;
    esac
    skill=$(phase_skill "$(printf '%s' "$payload" | jq -r '.tool_input.skill // empty' 2>/dev/null)")
    [ -n "$skill" ] || exit 0
    tell_taken "$session" PostToolUse >/dev/null
    take_lock "$skill" "$session" PostToolUse || exit 0
    [ "$skill" = "implement-change" ] && start_build "$session"
    exit 0
  fi

  active || exit 0
  [ -e "$dir/outcome.md" ] && exit 0
  on_build_branch "$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)" || exit 0

  case "$tool" in
    Bash)
      cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null)
      # The gate patterns from the repository's profile, or the default profile's; a pattern none gives
      # counts nothing.
      helper="$here/../scripts/profile.sh"
      if [ -f "$helper" ]; then . "$helper"; else profile_field() { printf '%s' "$2"; }; fi
      for g in lint:lint.regex tests:gates.tests types:types.regex; do
        pattern=$(profile_field "${g#*:}" '')
        if [ -n "$pattern" ] && invokes "$cmd" "$pattern"; then
          append "$(jq -cn --arg t "$(now)" --arg g "${g%%:*}" '{t:$t,kind:"gate",gate:$g}')"
        fi
      done
      ;;
    Agent | Task)
      sub=$(printf '%s' "$payload" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
      case "$sub" in
        implementation-reviewer | *:implementation-reviewer)
          append "$(jq -cn --arg t "$(now)" '{t:$t,kind:"round"}')"
          ;;
        focused-reviewer | *:focused-reviewer)
          # The focus is the brief the prompt names, reviews/<focus>.md.
          focus=$(printf '%s' "$payload" | jq -r '.tool_input.prompt // empty' 2>/dev/null |
            grep -oE 'reviews/[a-z-]+\.md' | head -1 | sed -E 's|^reviews/||; s|\.md$||')
          append "$(jq -cn --arg t "$(now)" --arg f "${focus:-unknown}" '{t:$t,kind:"reviewer",focus:$f}')"
          ;;
      esac
      ;;
  esac
  exit 0
fi

if [ "$mode" = "end" ]; then
  command -v jq >/dev/null 2>&1 || exit 0
  session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
  if [ -n "$session" ] && [ "$(jq -r '.session // empty' .review/lock 2>/dev/null)" = "$session" ]; then
    rm -f .review/lock
  fi
fi

# summary
command -v jq >/dev/null 2>&1 || exit 0
[ "$mode" = "end" ] || touch_lock "$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)"
active || exit 0
[ -e "$dir/outcome.md" ] && folded && exit 0
[ -e "$dir/outcome.md" ] && [ "$(build_branch)" != "$(branch)" ] && exit 0
on_build_branch "$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)" || exit 0

first=$(head -1 "$log" | jq -r '.t // empty' 2>/dev/null)

# Tokens come from the session transcript, whose path the Stop and SessionEnd payloads carry,
# and from the transcripts of the subagents that session spawned, which Claude Code writes to
# <transcript without .jsonl>/subagents/agent-*.jsonl. They are counted only in the session that
# started the build, and only from the build's first event, so planning earlier in that session
# is not charged to it. One API response is written as several lines that repeat its usage, so
# each message id counts once. A summary from another session keeps the figure already written.
tokens="not recorded"
previous=$(sed -n 's/^Tokens since the build started: //p' "$dir/already-checked.md" 2>/dev/null)
[ -n "$previous" ] && tokens=$previous
session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
transcript=$(printf '%s' "$payload" | jq -r '.transcript_path // empty' 2>/dev/null)
if [ -n "$session" ] && [ "$session" = "$(start_field session)" ] \
  && [ -n "$transcript" ] && [ -r "$transcript" ] && [ -n "$first" ]; then
  files=("$transcript")
  for f in "${transcript%.jsonl}"/subagents/agent-*.jsonl; do
    [ -r "$f" ] && files+=("$f")
  done
  totals=$(jq -rn --arg since "$first" --arg main "$transcript" '
      reduce (inputs | select(.type == "assistant" and (.timestamp // "") >= $since and .message.usage)
              | {f: input_filename, id: (.message.id // .uuid), u: .message.usage}) as $e
        ({}; .[$e.id] = $e)
      | [.[]]
      | {inp: (map(.u.input_tokens // 0) | add // 0),
         out: (map(.u.output_tokens // 0) | add // 0),
         cr:  (map(.u.cache_read_input_tokens // 0) | add // 0),
         cc:  (map(.u.cache_creation_input_tokens // 0) | add // 0),
         subs: (map(select(.f != $main) | .f) | unique | length)}
      | "\(.inp + .cc) in · \(.out) out · \(.cr) cached, main session plus \(.subs) subagent\(if .subs == 1 then "" else "s" end)"' \
    "${files[@]}" 2>/dev/null)
  [ -n "$totals" ] && [ "$totals" != "null" ] && tokens=$totals
fi

lint=$(grep -c '"gate":"lint"' "$log" 2>/dev/null); lint=${lint:-0}
tests=$(grep -c '"gate":"tests"' "$log" 2>/dev/null); tests=${tests:-0}
types=$(grep -c '"gate":"types"' "$log" 2>/dev/null); types=${types:-0}
rounds=$(grep -c '"kind":"round"' "$log" 2>/dev/null); rounds=${rounds:-0}
reviewers=$(grep -c '"kind":"reviewer"' "$log" 2>/dev/null); reviewers=${reviewers:-0}

# The wall clock is the time from each event to the next, except the time before a resume event,
# which is the gap between sessions.
mins=$(jq -rn '[inputs | {k: .kind, s: (.t | fromdateiso8601)}]
    | [range(1; length) as $i | select(.[$i].k != "resume") | .[$i].s - .[$i - 1].s]
    | ((add // 0) + 59) / 60 | floor' "$log" 2>/dev/null)
[ -n "$mins" ] || mins="?"

# Where the gate patterns came from, said when the repository has no profile, the profile could
# not be read or was refused, or a pattern reads `not yet recorded`.
patterns=""
helper="$here/../scripts/profile.sh"
if [ -f "$helper" ]; then
  . "$helper"
  src=$(profile_field source '')
  unrecorded=""
  for f in lint:lint.regex types:types.regex tests:gates.tests; do
    [ -n "$(profile_raw "${f#*:}")" ] || unrecorded="${unrecorded:+$unrecorded, }${f%%:*}"
  done
  if [ -n "$profile_error" ] && [ -z "$profile_lines" ]; then
    patterns=" · patterns: none, the profile is refused: $profile_error"
  elif [ -z "$src" ]; then
    patterns=" · patterns: the default profile's, no profile read"
  elif [ "$src" = none ]; then
    # Its patterns are what is detected, else the default profile's.
    patterns=" · patterns: the repository's own, else the default profile's"
  elif [ -n "$unrecorded" ]; then
    # A pattern its standard leaves out is none.
    patterns=" · patterns: none for $unrecorded, which the repository does not state"
  fi
fi

gates="lint $lint · types $types · tests $tests · reviewer rounds $rounds · reviewers $reviewers · wall clock $mins min$patterns"
# A build whose session also wrote in another repository may have its gates and tokens counted
# here, so neither is a measurement of this build.
other=$(jq -r 'select(.kind == "elsewhere") | .repo' "$log" 2>/dev/null | head -1)
if [ -n "$other" ]; then
  gates="not recorded, this session also edited $other while its build was recorded here"
  tokens="not recorded"
fi

{
  echo "Gates: $gates"
  echo "Tokens since the build started: $tokens"
  echo
  echo "Measured by the plugin's hooks from $(wc -l <"$log" | tr -d ' ') recorded events. How the"
  echo "build ended is a judgment no hook makes: implement-change writes its Build: line to"
  echo "$dir/outcome.md from the implementation reviewer's last verdict."
} >"$dir/already-checked.md" 2>/dev/null || true
[ -e "$dir/outcome.md" ] && append "$(jq -cn --arg t "$(now)" '{t:$t,kind:"fold"}')"

exit 0
