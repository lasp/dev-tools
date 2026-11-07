#!/usr/bin/env bash
# SessionStart: says where the ticket on this branch stands, from local files only, in one line
# the person sees and the model reads:
#
#   PROJ-830 · <branch> · plan approved · build passed · next: /lasp-dev:work
#
# With --fields it prints instead the facts the line is built from, one `name=value` per line, for
# scripts/next_phase.py; context, plan and reopened_file are absolute paths. Fields: ticket, branch (empty with none, a detached HEAD included), context (the
# ticket's context page, or empty), plan (the plan file's path, whether or not it exists yet, or
# empty with neither a ticket nor a branch), base (the plan's Base: line), outcome (the first
# line of this branch's outcome.md, current or parked under .review/build/done/<branch>/, or empty), outcome_reopened (the thread ids on that
# outcome.md's Reopened: lines, space-separated, or empty), build_branch, dirty (true or false; an untracked file counts only when made
# since the build started, or with no build), lock (the skill a live .review/lock names, whichever session holds it, or empty; a lock untouched for four
# hours is stale and empty here), profile (profile.py's source: the files of the repository's standard
# it read, `none` when it has none, or empty when the profile was not read), part (`k of n` when the context page gives
# this branch a part of the ticket's pull requests, or empty), reopened (the ids, a thread's or
# `session-<pr>-<n>`, of the reopened file, which pr-fix writes when review reopens the design,
# space-separated, or empty), reopened_file (that file's path, `.review/reopened/<ticket>.txt`, or
# with no ticket `.review/reopened/<branch, / as ->.txt`, whether or not it exists yet, or empty
# with neither), slug (a new ticket not yet filed: the word starting with a letter that opens
# .review/context.md's heading, `# <slug> · …`, its first line or its second after a
# `Controlled:` line, when the heading opens with no key,
# .review/context/<slug>.md exists and the page has no Branch: line or one naming this branch;
# ticket and context stay empty; else empty) and
# elsewhere (the first branch the ticket's context page names when none of its Branch: lines
# names this one, or empty). `--fields --ticket <key>` takes the ticket
# from the key, in the profile's ticket key pattern, rather than from the branch or context.md.
# Where the profile's tracker is GitHub's, the key is the issue's number, `ticket=59`, and the
# session-start line shows it as `#59`; the pattern is the standard's, never one detected, and
# with none recorded it is `(issue-)?\d+`. There a branch's number ends at `-`, `_` or the name's
# end, but not by `-NN-NN`, and `--ticket` takes the bare number as well as the pattern.
#
# .review/ is the one at the repository's top level, found from the SessionStart payload's cwd, or
# the working directory when there is none, so a session in a subdirectory reads the same files.
# The session-start line is inert unless that directory has a .review/ directory, and
# always exits 0. --fields prints its lines with or without .review/, every value empty that no
# file gives, and exits 1 without jq, on an argument it does not read, or on a reopened file
# with a line that is not `Reopened: <id> · <clause>`. Never calls GitHub or
# any other service, and writes nothing.
set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
fields=""
given=""
if [ "${1:-}" = "--fields" ]; then
  fields=yes
  if [ "${2:-}" = "--ticket" ] && [ -n "${3:-}" ] && [ -z "${4:-}" ]; then
    given=$3
  elif [ -n "${2:-}" ]; then
    echo "where.sh: --fields takes nothing or --ticket <key>, not: ${*:2}" >&2
    exit 1
  fi
  command -v jq >/dev/null 2>&1 || { echo "where.sh: --fields needs jq, to read .review/build/events.jsonl and .review/lock" >&2; exit 1; }
else
  command -v jq >/dev/null 2>&1 || exit 0
fi
payload=""
[ -n "$fields" ] || [ -t 0 ] || payload=$(cat 2>/dev/null) || payload=""
session=$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null)
cwd=${cwd:-$PWD}
top=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null) || top=$cwd
cd "$top" 2>/dev/null || exit 0
[ -n "$fields" ] || [ -d ".review" ] || exit 0

branch=$(git symbolic-ref --short -q HEAD 2>/dev/null || echo "")

# The ticket key pattern from the repository's profile, or the defaults'. With none readable, no
# key is matched: the branch and the context pages name no ticket. As a hook it reads a standard
# elsewhere only as last fetched; with --fields, for a skill, it may fetch one never fetched.
[ -n "$fields" ] || export STANDARD_OFFLINE=1
helper="$here/../scripts/profile.sh"
if [ -f "$helper" ]; then . "$helper"; else profile_field() { printf '%s' "$2"; }; profile_ere() { printf '%s' "${1//\\d/[0-9]}"; }; profile_project() { :; }; profile_read_defaults() { :; }; fi
key=$(profile_ere "$(profile_field ticket.pattern '')" 2>/dev/null) || key=""
# A GitHub tracker's key is the issue number: a match is reduced to its digits. Its pattern is the
# one the standard records, never one detected from a Jira-keyed history, and with none,
# `59-x`, `issue-59-x` and `feature/59-x` all name issue 59. A Jira tracker, or none, keeps the
# profile's pattern.
profile_read_defaults
tracker=$(profile_project issue_tracker.kind 2>/dev/null) || tracker=""
if [ "$tracker" = github ]; then
  key=$(profile_ere "$(profile_project ticket.pattern)" 2>/dev/null) || key=""
  [ -n "$key" ] || key='(issue-)?[0-9]+'
fi

# A GitHub key, the last run of digits in what the pattern matched.
number() { printf '%s' "$1" | grep -oE '[0-9]+' | tail -1; }
# A context page's Branch: lines, one per pull request of the ticket, each `<branch>` or
# `<branch> (part k of n)`: the branch names, and this branch's part.
# Only the lines above the page's first `## ` section count, where implement-change writes them.
branches_of() { sed '/^## /q' "$1" 2>/dev/null | sed -n 's/^Branch: //p' | sed -E 's/ \(part [0-9]+ of [0-9]+\)$//'; }
# A context page's heading, `# <ticket> · <summary>`: its first line, or its second when the first
# is the `Controlled:` line a page written from a cleared item opens with.
heading_of() { awk 'NR == 1 && /^Controlled:/ { next } { print; exit }' "$1" 2>/dev/null; }
# The key the heading opens with; a key in the summary, such as a follow-up's source, is not the
# page's.
key_of() {
  [ -n "$key" ] || return 0
  if [ "$tracker" = github ]; then
    heading_of "$1" | sed -nE "s/^#[[:space:]]+#?($key)([^[:alnum:]].*)?\$/\1/p" | while IFS= read -r k; do number "$k"; done
  else
    heading_of "$1" | sed -nE "s/^#[[:space:]]+($key)([^[:alnum:]].*)?\$/\1/p"
  fi
}
part_of() { awk -v b="$branch" 'sub(/^Branch: /, "") && index($0, b " (part ") == 1 { s = substr($0, length(b) + 8); sub(/\)$/, "", s); print s; exit }' "$1" 2>/dev/null; }

# The key starts the branch name, after an optional <word>/ prefix such as feature/. With no key
# in the branch name, the ticket .review/context.md names, unless none of its Branch: lines
# names this branch: .review/ belongs to the working tree, not to the branch. A given key is the
# ticket wherever the branch is, and its context page's Branch: lines say whether it is here.
# The key is matched ignoring case, so a lower-case key starting a branch name counts. It is
# written as found when the pattern matches it exactly, and otherwise upper-cased, as Jira writes
# keys.
canon() {
  if [ "$tracker" = github ]; then number "$1"
  elif printf '%s' "$1" | grep -qxE "($key)"; then printf '%s' "$1"; else printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; fi
}
on=""
slug=""
if [ -n "$given" ]; then
  [ -n "$key" ] || { echo "where.sh: no ticket key pattern: the profile could not be read" >&2; exit 1; }
  # On a GitHub tracker a bare number is an issue's, whatever pattern the standard records, as
  # work and implement-change pass it.
  printf '%s' "$given" | grep -qxiE "($key)" || { [ "$tracker" = github ] && printf '%s' "$given" | grep -qxE '[0-9]+'; } \
    || { echo "where.sh: $given is not a ticket key in the pattern $key" >&2; exit 1; }
  ticket=$(canon "$given")
  page=".review/context/$ticket.md"
  [ -f "$page" ] || page=.review/context.md
  [ "$(key_of "$page")" = "$ticket" ] && on=$(branches_of "$page")
else
  ticket=""
  matched=""
  [ -n "$key" ] && matched=$(printf '%s' "$branch" | grep -oiE "^([A-Za-z]+/)?($key)" || true)
  ticket=${matched##*/}
  # On a GitHub tracker the number is followed by `-`, `_` or the name's end, but not by
  # `-NN-NN`: `release/1.2.0`, `2fa-support`, `123abc` and `2026-11-06-cleanup` name no issue, while
  # `hotfix/3`, a number as the whole last component, names issue 3.
  if [ "$tracker" = github ] && [ -n "$matched" ]; then
    rest=${branch:${#matched}}
    case $rest in '' | -* | _*) ;; *) ticket="" ;; esac
    printf '%s' "$rest" | grep -qE '^-[0-9]{2}-[0-9]{2}([^0-9]|$)' && ticket=""
  fi
  # A key that matches only ignoring case on a branch that already has its own plan is not taken:
  # that work began before such keys were read, under the branch's name.
  if [ -n "$ticket" ] && ! printf '%s' "$ticket" | grep -qxE "($key)" && [ -f ".review/implementation-plan-${branch//\//-}.md" ]; then
    ticket=""
  fi
  [ -n "$ticket" ] && ticket=$(canon "$ticket")
  # A branch with its own plan is its own work, a new change implement-change started here, not
  # the ticket .review/context.md was last copied for.
  # With no pattern, no page is read as a ticket or as an unfiled draft.
  if [ -n "$key" ] && [ -z "$ticket" ] && [ -f .review/context.md ] && [ ! -f ".review/implementation-plan-${branch//\//-}.md" ]; then
    ticket=$(key_of .review/context.md)
    on=$(branches_of .review/context.md)
    # A page under a slug is a ticket ticket-draft drafted and nobody has filed yet.
    if [ -z "$ticket" ] && { [ -z "$on" ] || printf '%s\n' "$on" | grep -qxF -- "$branch"; }; then
      slug=$(heading_of .review/context.md | sed -nE 's/^# ([A-Za-z][A-Za-z0-9._-]*)( .*)?$/\1/p')
      [ -n "$slug" ] && [ -f ".review/context/$slug.md" ] || slug=""
    fi
  fi
fi
elsewhere=""
if [ -n "$ticket" ] && [ -n "$on" ] && ! printf '%s\n' "$on" | grep -qxF -- "$branch"; then
  elsewhere=$(printf '%s' "$on" | head -1)
fi

plan=""
if [ -n "$ticket" ]; then
  plan=".review/implementation-plan-$(printf '%s' "$ticket" | tr '[:upper:]' '[:lower:]').md"
elif [ -n "$branch" ]; then
  plan=".review/implementation-plan-${branch//\//-}.md"
fi
events=".review/build/events.jsonl"
build_branch=$(jq -r 'select(.branch) | .branch' "$events" 2>/dev/null | tail -1)
outcome=""
outcome_reopened=""
# A lock untouched for 240 minutes, build-record.sh's LOCK_STALE_MIN, is stale and holds nothing.
live_lock=false
[ -s ".review/lock" ] && [ -z "$(find .review/lock -mmin +240 2>/dev/null)" ] && live_lock=true

# This branch's finished build: the current one, or the one a build on another branch parked.
built=""
if [ -s ".review/build/outcome.md" ] && [ -s "$events" ] && [ "$build_branch" = "$branch" ]; then
  built=".review/build"
elif [ -n "$branch" ] && [ -s ".review/build/done/$branch/outcome.md" ]; then
  built=".review/build/done/$branch"
fi
if [ -n "$built" ]; then
  outcome=$(head -1 "$built/outcome.md")
  outcome_reopened=$(sed -n 's/^Reopened: \([^ ]*\) · .*/\1/p' "$built/outcome.md" | paste -sd ' ' -)
fi

if [ -n "$fields" ]; then
  context=""
  [ -n "$ticket" ] && [ -f ".review/context/$ticket.md" ] && context=".review/context/$ticket.md"
  page=$context
  [ -n "$page" ] || [ "$(key_of .review/context.md)" != "$ticket" ] || page=.review/context.md
  part=""
  [ -n "$page" ] && part=$(part_of "$page")
  # The plan's Base: line for this part, `Base: <branch> (part k of n)`, else its only one.
  base=""
  [ -n "$part" ] && base=$(sed -n "s/^Base: \(.*\) (part $part)\$/\1/p" "$plan" 2>/dev/null | head -1)
  [ -n "$base" ] || base=$(sed -n 's/^Base: //p' "$plan" 2>/dev/null | head -1 | sed -E 's/ \(part [0-9]+ of [0-9]+\)$//')
  # Dirty: a tracked change, or an untracked file made since the build started, so a build's new
  # files count and notes that were lying in the tree before it do not; with no build, any
  # untracked file counts.
  dirty=false
  if [ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    dirty=true
  else
    # A file stamped with the build's start, since BSD find cannot read an ISO time itself; when
    # it cannot be made, every untracked file counts.
    started=$(head -1 .review/build/events.jsonl 2>/dev/null | jq -r '.t // empty' 2>/dev/null)
    ref=""
    [ -n "$started" ] && { ref=$(mktemp 2>/dev/null) && touch -d "$started" "$ref" 2>/dev/null || ref=""; }
    while IFS= read -r -d '' f; do
      if [ -z "$ref" ] || [ -n "$(find "$f" -maxdepth 0 -newer "$ref" 2>/dev/null)" ]; then dirty=true; break; fi
    done < <(git ls-files -z --others --exclude-standard 2>/dev/null)
    [ -z "$ref" ] || rm -f "$ref"
  fi
  lock=""
  "$live_lock" && lock=$(jq -r '.skill // empty' .review/lock 2>/dev/null)
  reopened=""
  # Keyed as the plan is, by the ticket as written, or by the branch when there is no ticket.
  name=${ticket:-${branch//\//-}}
  file=""
  [ -n "$name" ] && file=".review/reopened/$name.txt"
  if [ -f "$file" ]; then
    bad=$(grep -vnE '^Reopened: [^ ]+ · .+$' "$file" | head -1)
    [ -z "$bad" ] || { echo "where.sh: $file line $bad is not 'Reopened: <id> · <clause>'" >&2; exit 1; }
    bad=$(grep -nE '^Reopened: session-' "$file" | grep -vE '^[0-9]+:Reopened: session-[1-9][0-9]*-[0-9]+ · ' | head -1)
    [ -z "$bad" ] || { echo "where.sh: $file line $bad is not 'Reopened: session-<pr>-<n> · <clause>'" >&2; exit 1; }
    reopened=$(awk '{ print $2 }' "$file" | paste -sd ' ' -)
  fi
  # Paths are absolute, so a caller in a subdirectory reads the files at the top level.
  printf '%s\n' "ticket=$ticket" "branch=$branch" "context=${context:+$top/$context}" "plan=${plan:+$top/$plan}" "base=$base" \
    "outcome=$outcome" "outcome_reopened=$outcome_reopened" "build_branch=$build_branch" "dirty=$dirty" "lock=$lock" \
    "profile=$(profile_field source '')" "part=$part" \
    "reopened=$reopened" "reopened_file=${file:+$top/$file}" "slug=$slug" "elsewhere=$elsewhere"
  exit 0
fi

# People see a GitHub issue as #<n>.
shown=$ticket
[ "$tracker" = github ] && [ -n "$ticket" ] && shown="#$ticket"
if [ -n "$elsewhere" ]; then
  parts=("$shown is on $elsewhere, not here" "${branch:-no branch}")
else
  parts=("${shown:-no ticket}" "${branch:-no branch}")

  # The last `## Revision` section of a reopened plan, its redesign, carries its own approval.
  if awk '/^## Revision /{r=1;a=0} r&&/^Approved by: [^[:space:]]/{a=1} END{exit !(r&&!a)}' "$plan" 2>/dev/null; then
    parts+=("redesign drafted")
  elif grep -q '^Approved by: [^[:space:]]' "$plan" 2>/dev/null; then
    parts+=("plan approved")
  elif [ -f "$plan" ]; then
    parts+=("plan drafted")
  else
    parts+=("no plan")
  fi
  build="no build"
  [ -n "$outcome" ] && build="build $(printf '%s' "$outcome" | sed -E 's/^Build:[[:space:]]*//')"
  parts+=("$build")
  # Nothing started on this branch: one part rather than three negatives.
  if [ -z "$ticket" ] && [ ! -f "$plan" ] && [ -z "$outcome" ]; then
    parts=("no ticket on this branch" "${branch:-no branch}")
  fi
fi

# A profile refused with no values read at all, as a standard or a default profile the schema
# refuses is: with no ticket pattern no ticket can be named, so the line says why instead.
if [ -n "${profile_error:-}" ] && [ -z "${profile_lines:-}" ]; then
  parts=("profile refused: $profile_error" "${branch:-no branch}")
fi

if "$live_lock" && [ "$(jq -r '.session // empty' .review/lock 2>/dev/null)" != "$session" ]; then
  parts+=("$(jq -r '"held by \(.skill) since \(.t)"' .review/lock 2>/dev/null)")
fi
parts+=("next: /lasp-dev:work")

line=""
for p in "${parts[@]}"; do line="${line:+$line · }$p"; done

jq -cn --arg m "$line" '{systemMessage: $m, hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $m}}'
exit 0
