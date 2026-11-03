#!/usr/bin/env bash
# SessionStart: loads the wording of the review rules that apply to this repository into the
# session, so a session that is not building or reviewing follows them too, and says in one line
# how many it loaded. The rules are standard_file.sh --rules's, from the repository's own standard
# or the one its standard: pointer names, fetched once when this clone never has and otherwise as
# last fetched; a repository with none loads nothing, reaches no network and says nothing, and one
# whose rules cannot be read, such as a standard elsewhere that could not be fetched, or one this
# clone is set not to read, loads nothing and says why in one line, to the person and the model.
# Always exits 0.
set -u
export STANDARD_OFFLINE=1
command -v jq >/dev/null 2>&1 || exit 0
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
payload=$(cat 2>/dev/null || true)
cwd=$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null)
top=$(git -C "${cwd:-$PWD}" rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$top" || exit 0
# Why no rules loaded, to the person and to the model, so neither takes the session as following them.
say() { jq -cn --arg m "$1" '{systemMessage: $m, hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $m}}'; }
# A clone that has never fetched the standard its pointer names fetches it once here, so even its
# first session loads the rules; one that has reads it as last fetched, with no network, as does one
# whose git config names its own lasp-dev.standard. No credential is asked for: a helper
# answers or the fetch fails. The fetch runs in a process group of its own, stopped after
# FIRST_FETCH_SECONDS (a whole number up to 15, else 10) and killed 2 seconds later, which the cache
# is built to survive. A fetch that failed or was stopped is not tried here again for a day, so a
# person without access is not asked to sign or wait at every session start; a build or review
# still fetches.
fetch_error=""
if grep -qE '^standard:' standards/profile.yaml 2>/dev/null && [ -z "$(git config --get lasp-dev.standard)" ]; then
  limit=${FIRST_FETCH_SECONDS:-10}
  [[ "$limit" =~ ^[0-9]+$ ]] && [ "$limit" -le 15 ] || limit=10
  stamp="$(git rev-parse --git-common-dir)/lasp-dev/first-fetch-failed"
  if [ -z "$(find "$stamp" -mmin -1440 2>/dev/null)" ]; then
    fetch_error=$(
      set -m
      GIT_ASKPASS=true GCM_INTERACTIVE=never bash "$here/../scripts/standard.sh" --cached 2>&1 >/dev/null &
      pid=$!
      (sleep "$limit"; kill -- -"$pid"; sleep 2; kill -KILL -- -"$pid") >/dev/null 2>&1 &
      watch=$!
      wait "$pid"
      rc=$?
      if [ "$rc" -gt 128 ]; then
        wait "$watch"
        echo "standard.sh: could not fetch the standard within ${limit}s"
      else
        kill -- -"$watch" 2>/dev/null
      fi
    )
    if bash "$here/../scripts/standard.sh" --offline >/dev/null 2>&1; then
      rm -f "$stamp"
    elif printf '%s' "$fetch_error" | grep -q '^standard.sh: could not fetch'; then
      mkdir -p "$(dirname "$stamp")" && touch "$stamp"
      fetch_error="$fetch_error; tried again here after a day, or at a build or review; git config lasp-dev.standard none stops trying"
    fi
  fi
fi
# The error is read by asking again, never through a temporary file, which a sandboxed shell may
# not be allowed to make.
if ! text=$(bash "$here/../scripts/standard_file.sh" --rules 2>/dev/null); then
  why=$(printf '%s\n' "$fetch_error" | sed -n 's/^standard\.sh: //p' | tail -1)
  [ -n "$why" ] || why=$(bash "$here/../scripts/standard_file.sh" --rules 2>&1 >/dev/null | sed -n '1s/^[a-z_.]*: //p')
  say "review rules not loaded: ${why:-standard_file.sh failed}"
  exit 0
fi
if [ -z "$text" ]; then
  if [ "$(git config --get lasp-dev.standard 2>/dev/null)" = none ] && grep -q '^standard:' standards/profile.yaml 2>/dev/null; then
    say "review rules not loaded: this clone reads no standard, as git config lasp-dev.standard is none; git config --unset lasp-dev.standard reads it again"
  fi
  exit 0
fi
count=$(printf '%s\n' "$text" | grep -c '^R-[0-9][0-9]* · ')
context=$(printf 'The review rules of this repository. Follow them in any change you make here, as its reviewers will:\n\n%s\n' "$text")
jq -cn --arg m "review rules loaded: $count" --arg c "$context" \
  '{systemMessage: $m, hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $c}}'
exit 0
