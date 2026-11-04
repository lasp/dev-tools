#!/usr/bin/env bash
# Pipes hand-written hook payloads through hooks/build-record.sh in a scratch repository and
# checks what it writes to .review/build/ and .review/lock. Run: bash tests/test_build_record.sh
set -u

root=$(cd "$(dirname "$0")/.." && pwd)
hook="$root/hooks/build-record.sh"
transcript="$root/tests/fixtures/transcript.jsonl"
failures=0
made=()
trap 'rm -rf "${made[@]}"' EXIT

check() {
  if eval "$2"; then
    echo "  ok    $1"
  else
    echo "  FAIL  $1"
    failures=$((failures + 1))
  fi
}

# A scratch repository with no .review/, its own standard keying tickets and counting gates;
# scratch() adds .review/, already ignored.
bare() {
  local d
  d=$(mktemp -d)
  git -C "$d" init -q -b PROJ-1-test
  git -C "$d" remote add origin "https://github.com/someone/scratch.git"
  mkdir "$d/standards"
  printf "ticket:\n  pattern: 'PROJ-\\d+'\n  project: PROJ\nlint:\n  regex: 'pre-commit[[:space:]]+run'\ntypes:\n  regex: '(mypy|pyright)'\ngates:\n  tests: pytest\n" >"$d/standards/profile.yaml"
  git -C "$d" add standards
  git -C "$d" -c user.name=t -c user.email=t@t commit -q -m init
  printf '%s' "$d"
}

scratch() {
  local d
  d=$(bare)
  mkdir "$d/.review"
  echo .review/ >>"$d/.git/info/exclude"
  printf '%s' "$d"
}

prompt() { jq -cn --arg p "$1" --arg s "$2" '{prompt:$p, session_id:$s}' | "$hook" prompt; }
bash_event() { jq -cn --arg c "$1" '{tool_name:"Bash", session_id:"s1", tool_input:{command:$c}}' | "$hook" event; }
events() { wc -l <.review/build/events.jsonl | tr -d ' '; }

echo "build-record.sh"

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
check "a typed implement-change starts a build" \
  '[ "$(head -1 .review/build/events.jsonl | jq -r .kind)" = start ]'
check "and takes the lock" '[ "$(jq -r .skill .review/lock)" = implement-change ]'

bash_event 'echo "run pytest later"'
check "pytest inside a quoted string is not a gate" '! grep -q "\"gate\"" .review/build/events.jsonl'
bash_event "uv run pytest -q tests/"
check "uv run pytest is a tests gate" '[ "$(grep -c "\"gate\":\"tests\"" .review/build/events.jsonl)" = 1 ]'
bash_event "pre-commit run --files x"
check "pre-commit run --files is a lint gate" '[ "$(grep -c "\"gate\":\"lint\"" .review/build/events.jsonl)" = 1 ]'
bash_event "uvx pre-commit run --all-files"
check "uvx pre-commit run is a lint gate" '[ "$(grep -c "\"gate\":\"lint\"" .review/build/events.jsonl)" = 2 ]'
bash_event "time pytest tests/unit"
check "time pytest is a tests gate" '[ "$(grep -c "\"gate\":\"tests\"" .review/build/events.jsonl)" = 2 ]'
bash_event "uv run --extra dev pytest -q"
check "uv run --extra dev pytest is a tests gate" '[ "$(grep -c "\"gate\":\"tests\"" .review/build/events.jsonl)" = 3 ]'
bash_event "make test && tox -e py311 && nox -s tests"
check "make, tox and nox are not a tests gate" '[ "$(grep -c "\"gate\":\"tests\"" .review/build/events.jsonl)" = 3 ]'
jq -cn '{tool_name:"Agent", session_id:"s1", tool_input:{subagent_type:"implementation-reviewer"}}' | "$hook" event
check "an implementation-reviewer Agent call is a round" '[ "$(grep -c "\"kind\":\"round\"" .review/build/events.jsonl)" = 1 ]'

out=$(prompt "/lasp-dev:pr-fix 1" s2)
check "a second session's pr-fix against a held lock is refused, and told to ask and how to take it over" \
  '[ "$(jq -r .session .review/lock)" = s1 ] && printf "%s" "$out" | jq -e ".hookSpecificOutput.additionalContext | test(\"held by implement-change\") and test(\"Take over\") and test(\"take pr-fix\")" >/dev/null'
out=$(prompt "/lasp-dev:pr-review 1" s2)
check "a second session's pr-review takes no lock and is not refused" \
  '[ "$(jq -r .session .review/lock)" = s1 ] && [ -z "$out" ]'

echo "Build: passed" >.review/build/outcome.md
before=$(events)
bash_event "pytest"
check "an event after outcome.md exists appends nothing" '[ "$(events)" = "$before" ]'
jq -cn '{session_id:"s1"}' | "$hook" summary
echo "final" >.review/build/already-checked.md
# The block and the outcome in one second, which bash 3.2's -nt cannot order.
touch -t 202101010000 .review/build/outcome.md .review/build/already-checked.md
jq -cn '{session_id:"s1"}' | "$hook" summary
check "a summary after the fold leaves already-checked.md alone, even in the outcome's second" \
  '[ "$(cat .review/build/already-checked.md)" = final ]'
rm .review/build/outcome.md
bash_event "pytest"
echo "Build: passed" >.review/build/outcome.md
jq -cn '{session_id:"s1"}' | "$hook" summary
check "an outcome removed for changes and written again is folded with the new events" \
  'grep -q "tests 4 · reviewer rounds 1" .review/build/already-checked.md'

before=$(events)
prompt "/lasp-dev:implement-change PROJ-1" s1
check "implement-change again on a closed build keeps outcome.md and the fold, appending nothing" \
  '[ -e .review/build/outcome.md ] && [ "$(events)" = "$before" ] && [ "$(tail -1 .review/build/events.jsonl | jq -r .kind)" = fold ]'
rm .review/build/outcome.md
"$hook" start </dev/null
check "start after outcome.md is removed reopens the build with a resume event" \
  '[ "$(tail -1 .review/build/events.jsonl | jq -r .kind)" = resume ]'
echo "Build: passed" >.review/build/outcome.md
jq -cn '{session_id:"s1"}' | "$hook" summary
check "and the reopened build's outcome is folded again" \
  'grep -q "^Gates: " .review/build/already-checked.md'

jq -cn '{session_id:"s1"}' | "$hook" end
check "end releases this session's lock" '[ ! -e .review/lock ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
bash_event "pytest"
echo "Build: passed" >.review/build/outcome.md
git -c user.name=t -c user.email=t@t checkout -q -b PROJ-2-next
bash_event "pytest"
jq -cn '{session_id:"s1"}' | "$hook" summary
check "a closed build records no move to the session's next branch" \
  '! grep -q "\"kind\":\"move\"" .review/build/events.jsonl'
prompt "/lasp-dev:implement-change PROJ-2" s1
check "so the next build starts afresh without the closed build's counts" \
  '[ "$(head -1 .review/build/events.jsonl | jq -r .kind)" = start ] && ! grep -q "\"gate\"" .review/build/events.jsonl'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
"$hook" start </dev/null
check "start with no payload starts a build for session manual" \
  '[ "$(head -1 .review/build/events.jsonl | jq -r ".kind + \" \" + .session")" = "start manual" ]'
jq -cn '{session_id:"s9"}' | "$hook" start
check "start again on the branch resumes it, with the payload's session" \
  '[ "$(tail -1 .review/build/events.jsonl | jq -r ".kind + \" \" + .session")" = "resume s9" ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/implement-change PROJ-1" s1
# The fixture's timestamps are after the build's start, so every usage block is in range.
jq -cn --arg t "$transcript" '{session_id:"s1", transcript_path:$t}' | "$hook" summary
check "summary counts a message id repeated across lines once" \
  'grep -qx "Tokens since the build started: 155 in · 15 out · 1000 cached, main session plus 0 subagents" .review/build/already-checked.md'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
echo "wave report" >.review/build/wave-1.md
git -c user.name=t -c user.email=t@t checkout -q -b PROJ-2-other
prompt "/lasp-dev:implement-change PROJ-2" s1
check "a build started afresh removes the last build's wave reports" '[ ! -e .review/build/wave-1.md ]'
agent() { jq -cn --arg a "$1" --arg p "$2" '{tool_name:"Agent", session_id:"s1", tool_input:{subagent_type:$a, prompt:$p}}' | "$hook" event; }
for wave in 1 2; do
  agent lasp-dev:implementation-reviewer "wave $wave"
  agent lasp-dev:focused-reviewer "Brief: /x/skills/implement-change/reviews/simplicity.md"
  agent focused-reviewer "Brief: /x/skills/implement-change/reviews/documentation.md"
done
agent lasp-dev:focused-reviewer "no brief named"
jq -cn '{session_id:"s1"}' | "$hook" summary
check "two rounds and five reviewer events give reviewer rounds 2 · reviewers 5" \
  'grep -q "reviewer rounds 2 · reviewers 5 · wall clock" .review/build/already-checked.md'
check "a reviewer event carries the brief's focus, or unknown" \
  '[ "$(jq -r "select(.kind == \"reviewer\") | .focus" .review/build/events.jsonl | sort | uniq -c | tr -s " " | tr "\n" ",")" = " 2 documentation, 2 simplicity, 1 unknown," ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
jq -cn '{session_id:"s1"}' | "$hook" summary
bash_event "pytest"
jq -cn '{tool_name:"Agent", session_id:"s1", tool_input:{subagent_type:"implementation-reviewer"}}' | "$hook" event
echo "Build: passed" >.review/build/outcome.md
jq -cn '{session_id:"s1"}' | "$hook" summary
check "the first summary after outcome.md folds the build's events" \
  'grep -q "tests 1 · reviewer rounds 1" .review/build/already-checked.md'
echo "final" >.review/build/already-checked.md
jq -cn '{session_id:"s1"}' | "$hook" summary
check "and a later summary leaves the block alone" '[ "$(cat .review/build/already-checked.md)" = final ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
jq -cn '{session_id:"s1"}' | "$hook" summary
bash_event "pytest"
echo "Build: passed" >.review/build/outcome.md
jq -cn '{tool_name:"Skill", session_id:"s1", tool_input:{skill:"lasp-dev:pr-create"}}' | "$hook" event
check "pr-create started in the outcome's turn folds the block first" \
  'grep -q "tests 1 · reviewer rounds 0" .review/build/already-checked.md && [ "$(jq -r .skill .review/lock)" = implement-change ]'
echo "final" >.review/build/already-checked.md
jq -cn '{tool_name:"Skill", session_id:"s1", tool_input:{skill:"lasp-dev:pr-create"}}' | "$hook" event
check "and pr-create after the fold leaves the block alone" '[ "$(cat .review/build/already-checked.md)" = final ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:pr-review 1" s1
check "a typed pr-review takes no lock" '[ ! -e .review/lock ]'

# A plugin copy, and a repository whose own standard counts `npm test` as the tests gate.
plug=$(mktemp -d) && made+=("$plug")
mkdir -p "$plug/hooks" "$plug/scripts" "$plug/standards"
cp "$hook" "$plug/hooks/" && cp "$root/scripts/review_dir.sh" "$root/scripts/profile.py" "$root/scripts/profile.sh" "$root/scripts/survey.py" "$plug/scripts/"
cp "$root/standards/default-profile.yaml" "$plug/standards/"
d=$(scratch) && made+=("$d") && cd "$d" || exit 1
git remote set-url origin "https://github.com/someone/web.git"
mkdir -p standards
patterns="lint:\n  regex: 'pre-commit[[:space:]]+run'\ntypes:\n  regex: '(mypy|pyright)'\n"
printf "${patterns}gates:\n  tests: 'npm[[:space:]]+test'\n" >standards/profile.yaml
jq -cn --arg p "/lasp-dev:implement-change PROJ-1" '{prompt:$p, session_id:"s1"}' | "$plug/hooks/build-record.sh" prompt
for c in "npm test" "pytest"; do
  jq -cn --arg c "$c" '{tool_name:"Bash", session_id:"s1", tool_input:{command:$c}}' | "$plug/hooks/build-record.sh" event
done
check "a profile's tests gate counts npm test, and pytest no longer" \
  '[ "$(grep -c "\"gate\":\"tests\"" .review/build/events.jsonl)" = 1 ]'

printf "${patterns}gates:\n  tests: 'npm[[:space:]]+test|tox'\n" >standards/profile.yaml
for c in "echo tox" "tox -e py"; do
  jq -cn --arg c "$c" '{tool_name:"Bash", session_id:"s1", tool_input:{command:$c}}' | "$plug/hooks/build-record.sh" event
done
check "a gate pattern with an alternation counts only a command it starts" \
  '[ "$(grep -c "\"gate\":\"tests\"" .review/build/events.jsonl)" = 2 ]'
jq -cn '{session_id:"s1"}' | "$plug/hooks/build-record.sh" summary
check "a profile with no pattern reading not yet recorded adds nothing to the Gates line" \
  'grep -qE "^Gates: .* wall clock [0-9?]+ min$" .review/build/already-checked.md'
printf "posted_text: plain\n" >standards/profile.yaml
jq -cn '{session_id:"s1"}' | "$plug/hooks/build-record.sh" summary
check "with its own profile, a pattern it leaves out is named as none" \
  'grep -q " min · patterns: none for lint, types, tests, which the repository does not state$" .review/build/already-checked.md'
printf "flavor: sweet\n" >standards/profile.yaml
jq -cn '{session_id:"s1"}' | "$plug/hooks/build-record.sh" summary
check "a profile that is refused says so" \
  'grep -q " min · patterns: none, the profile is refused: .*flavor" .review/build/already-checked.md'
rm -f standards/profile.yaml
jq -cn '{session_id:"s1"}' | "$plug/hooks/build-record.sh" summary
check "a repository with no standard says the patterns are its own or the default profile's" \
  'grep -q " min · patterns: the repository'"'"'s own, else the default profile'"'"'s$" .review/build/already-checked.md'
git remote remove origin
jq -cn '{session_id:"s1"}' | "$plug/hooks/build-record.sh" summary
check "and with no remote, the default profile's" \
  'grep -q " min · patterns: the default profile'"'"'s, no profile read$" .review/build/already-checked.md'

# A plugin copy with no profile reader, as with no python3: no gate pattern, so no gate counted.
bare=$(mktemp -d) && made+=("$bare")
mkdir -p "$bare/hooks" "$bare/scripts"
cp "$hook" "$bare/hooks/" && cp "$root/scripts/review_dir.sh" "$bare/scripts/"
d=$(scratch) && made+=("$d") && cd "$d" || exit 1
jq -cn '{prompt:"/lasp-dev:implement-change PROJ-1", session_id:"s1"}' | "$bare/hooks/build-record.sh" prompt
jq -cn '{tool_name:"Bash", session_id:"s1", tool_input:{command:"pytest -q"}}' | "$bare/hooks/build-record.sh" event
check "with no profile reader, pytest counts as no gate rather than a default" \
  '[ "$(head -1 .review/build/events.jsonl | jq -r .kind)" = start ] && ! grep -q "\"gate\"" .review/build/events.jsonl'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/reopened
printf 'Reopened: PRRT_9 · the frame was wrong\n' >.review/reopened/PROJ-1.txt
prompt "/lasp-dev:implement-change PROJ-1" s1
prompt "/lasp-dev:implement-change PROJ-1" s1
check "a build's start leaves the reopened file pr-fix wrote" '[ "$(cat .review/reopened/PROJ-1.txt)" = "Reopened: PRRT_9 · the frame was wrong" ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
echo "Build: passed" >.review/build/outcome.md
jq -cn '{session_id:"s1"}' | "$hook" summary
echo x >change.txt
before=$(events)
prompt "/lasp-dev:implement-change PROJ-1" s1
check "a resume with uncommitted changes keeps outcome.md and the block, appending nothing" \
  '[ -e .review/build/outcome.md ] && grep -q "^Gates: " .review/build/already-checked.md && [ "$(events)" = "$before" ]'
rm .review/build/outcome.md
bash_event "pytest"
check "a resume that goes back into the build records its gates once outcome.md is removed" \
  '[ "$(tail -1 .review/build/events.jsonl | jq -r .gate)" = tests ]'
echo "Build: passed" >.review/build/outcome.md
jq -cn '{session_id:"s1"}' | "$hook" summary
git -c user.name=t -c user.email=t@t add change.txt
git -c user.name=t -c user.email=t@t commit -q -m change
before=$(events)
prompt "/lasp-dev:implement-change PROJ-1" s1
check "a resume on a clean tree after the commit keeps outcome.md and the block, appending nothing" \
  '[ "$(cat .review/build/outcome.md)" = "Build: passed" ] && grep -q "tests 1 · " .review/build/already-checked.md && [ "$(events)" = "$before" ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/build
{
  echo '{"t":"2026-10-01T10:00:00Z","kind":"start","branch":"PROJ-1-test","session":"s1"}'
  echo '{"t":"2026-10-01T10:10:00Z","kind":"gate","gate":"tests"}'
  echo '{"t":"2026-10-01T10:11:00Z","kind":"fold"}'
  echo '{"t":"2026-10-02T10:11:00Z","kind":"resume","session":"s2"}'
  echo '{"t":"2026-10-02T10:16:00Z","kind":"gate","gate":"tests"}'
} >.review/build/events.jsonl
echo "Build: passed" >.review/build/outcome.md
jq -cn '{session_id:"s2"}' | "$hook" summary
check "the wall clock leaves out the day between the fold and the resume" \
  'grep -q "tests 2 · reviewer rounds 0 · reviewers 0 · wall clock 16 min" .review/build/already-checked.md'

guard() { jq -cn --arg f "$1" '{tool_name:"Write", session_id:"s1", tool_input:{file_path:$f}}' | "$hook" guard; }
exclude() { git rev-parse --git-path info/exclude; }

d=$(bare) && made+=("$d") && cd "$d" || exit 1
guard "$d/notes.md" >/dev/null
check "a write outside .review/ changes nothing" \
  '[ ! -e .review ] && ! grep -qx ".review/" "$(exclude)"'
out=$(guard "$d/.review/plan.md")
check "a write under .review/ creates it and leaves .review/ in the exclude file" \
  '[ -d .review ] && [ "$(grep -cx ".review/" "$(exclude)")" = 1 ] && git check-ignore -q .review/x && [ -n "$out" ]'
out=$(guard "$d/.review/plan.md")
check "and a second write adds nothing" '[ "$(grep -cx ".review/" "$(exclude)")" = 1 ] && [ -z "$out" ]'

d=$(bare) && made+=("$d") && cd "$d" || exit 1
ln -s "$d" "$d.link" && made+=("$d.link")
guard "$d.link/.review/plan.md" >/dev/null
check "a write through a symlinked path is still under .review/" '[ -d .review ] && git check-ignore -q .review/x'

d=$(bare) && made+=("$d") && cd "$d" || exit 1
printf 'build/' >.git/info/exclude
git worktree add -q "$d/wt" -b PROJ-2-wt && cd "$d/wt" || exit 1
guard "$d/wt/.review/plan.md" >/dev/null
check "in a worktree, .review/ goes to the shared exclude file on a line of its own" \
  '[ -d .review ] && git check-ignore -q .review/x && [ "$(cat "$d/.git/info/exclude")" = "$(printf "build/\n.review/")" ]'

d=$(bare) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:pr-fix 1" s1 >/dev/null
check "a typed phase skill with no .review/ creates it, keeps it ignored and takes the lock" \
  '[ "$(jq -r .skill .review/lock)" = pr-fix ] && git check-ignore -q .review/x'

d=$(mktemp -d) && made+=("$d") && cd "$d" || exit 1
out=$(prompt "/lasp-dev:implement-change PROJ-1" s1)
check "outside a git repository a typed phase skill creates no .review/" '[ ! -e .review ] && [ -z "$out" ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
printf 'Build: passed\nDepth: standard\n' >.review/build/outcome.md
echo "Gates: lint 1" >.review/build/already-checked.md
git -c user.name=t -c user.email=t@t checkout -q -b feature/PROJ-2-other
prompt "/lasp-dev:implement-change PROJ-2" s1
check "a build on another branch parks the finished one under done/, never deletes it" \
  '[ "$(head -1 .review/build/done/PROJ-1-test/outcome.md)" = "Build: passed" ] && [ -s .review/build/done/PROJ-1-test/already-checked.md ] && [ "$(head -1 .review/build/events.jsonl | jq -r .branch)" = feature/PROJ-2-other ]'
echo "unfinished" >.review/build/wave-1.md
git checkout -q PROJ-1-test
prompt "/lasp-dev:implement-change PROJ-1" s1
check "and starting back on that branch brings it back, closed, and drops the open one" \
  '[ "$(head -1 .review/build/outcome.md)" = "Build: passed" ] && [ -s .review/build/already-checked.md ] && [ ! -e .review/build/done/PROJ-1-test ] && [ ! -e .review/build/wave-1.md ] && [ ! -e .review/build/done/feature/PROJ-2-other ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:pr-fix 1" s1
touch -t 202609300000 .review/lock
jq -cn '{tool_name:"Bash", session_id:"s2", tool_input:{command:"ls"}}' | "$hook" event
check "another session's events leave the lock's age alone" '[ -n "$(find .review/lock -mmin +240)" ]'
bash_event "ls"
check "the holder's own events keep its lock fresh" '[ "$(jq -r .session .review/lock)" = s1 ] && [ -z "$(find .review/lock -mmin +240)" ]'
touch -t 202609300000 .review/lock
jq -cn '{session_id:"s1"}' | "$hook" summary
check "and so does its Stop" '[ -z "$(find .review/lock -mmin +240)" ]'
jq -cn '{session_id:"s2"}' | "$hook" release
check "release by another session leaves the lock" '[ -s .review/lock ]'
jq -cn '{session_id:"s1"}' | "$hook" release
check "release by the holder removes it" '[ ! -e .review/lock ]'
prompt "/lasp-dev:pr-fix 1" s1
touch -t 202609300000 .review/lock
out=$(prompt "/lasp-dev:implement-change PROJ-1" s2)
check "a lock untouched for four hours is stale: taken, with a note, and the build starts" \
  '[ "$(jq -r .session .review/lock)" = s2 ] && printf "%s" "$out" | jq -e ".hookSpecificOutput.additionalContext | test(\"stale\")" >/dev/null && [ "$(head -1 .review/build/events.jsonl | jq -r .session)" = s2 ]'
touch .review/lock
jq -cn '{session_id:"s3"}' | "$hook" take implement-change
check "take hands a live lock to the person's session" '[ "$(jq -r .session .review/lock)" = s3 ] && [ "$(jq -r .skill .review/lock)" = implement-change ]'
check "and the lock lists both sessions it was taken from" '[ "$(jq -c .took_from .review/lock)" = "[\"s1\",\"s2\"]" ]'
touch -t 202609300000 .review/lock && touch -r .review/lock lock.ref
out=$(prompt "carry on" s1)
check "the session a stale lock was taken from is told at its next prompt, and the lock keeps its holder and age" \
  'printf "%s" "$out" | jq -e ".hookSpecificOutput.additionalContext | test(\"took the\")" >/dev/null && [ "$(jq -r .session .review/lock)" = s3 ] && [ ! .review/lock -nt lock.ref ]'
out=$(prompt "carry on" s1)
check "and is told once" '[ -z "$out" ] && [ "$(jq -c .took_from .review/lock)" = "[\"s2\"]" ]'
touch .review/lock
out=$(prompt "/lasp-dev:implement-change PROJ-1" s2)
again=$(jq -cn '{tool_name:"Bash", session_id:"s2", tool_input:{command:"bash build-record.sh take implement-change"}}' | "$hook" guard)
check "a phase skill started by a session whose lock was taken is told who holds it, and its take-over command is not refused" \
  'printf "%s" "$out" | jq -e ".hookSpecificOutput.additionalContext | test(\"held by\")" >/dev/null && [ "$(jq -r .session .review/lock)" = s3 ] && [ -z "$again" ] && [ "$(jq -r ".took_from // empty" .review/lock)" = "" ]'
out=$(jq -cn '{tool_name:"Bash", session_id:"s3", tool_input:{command:"ls"}}' | "$hook" guard)
check "the holder's own calls are not refused" '[ -z "$out" ]'
"$hook" take implement-change </dev/null 2>/dev/null
rc=$?
check "take with no session exits 1 and leaves the lock" '[ "$rc" = 1 ] && [ "$(jq -r .session .review/lock)" = s3 ]'
jq -cn '{session_id:"s4"}' | "$hook" take pr-review 2>/dev/null
rc=$?
check "and so does take for a skill that takes no lock" '[ "$rc" = 1 ] && [ "$(jq -r .session .review/lock)" = s3 ]'
jq -cn '{session_id:"s4"}' | "$hook" take implement-change
out=$(jq -cn '{tool_name:"Bash", session_id:"s3", tool_input:{command:"git commit -m x"}}' | "$hook" guard)
again=$(jq -cn '{tool_name:"Bash", session_id:"s3", tool_input:{command:"git commit -m x"}}' | "$hook" guard)
check "the session take took a live lock from has its next Bash call refused with the notice, once" \
  'printf "%s" "$out" | jq -e ".hookSpecificOutput.permissionDecision == \"deny\"" >/dev/null && [ -z "$again" ]'
jq -cn '{session_id:"s5"}' | "$hook" take implement-change
before=$(events)
out=$(jq -cn '{tool_name:"Bash", session_id:"s4", tool_input:{command:"pytest"}}' | "$hook" event)
check "a session whose lock was taken is told after a tool call, and that call records nothing" \
  'printf "%s" "$out" | jq -e ".hookSpecificOutput.additionalContext | test(\"took the\")" >/dev/null && [ "$(events)" = "$before" ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
git -c user.name=t -c user.email=t@t checkout -q -b feature/PROJ-7-x
prompt "/lasp-dev:implement-change PROJ-7" s1
printf 'Build: passed\n' >.review/build/outcome.md
git -c user.name=t -c user.email=t@t checkout -q -b PROJ-8-y
prompt "/lasp-dev:implement-change PROJ-8" s1
check "a branch name with / parks under nested directories" '[ "$(head -1 .review/build/done/feature/PROJ-7-x/outcome.md)" = "Build: passed" ]'
git checkout -q feature/PROJ-7-x
prompt "/lasp-dev:implement-change PROJ-7" s1
check "and comes back from them" '[ "$(head -1 .review/build/outcome.md)" = "Build: passed" ] && [ ! -e .review/build/done/feature/PROJ-7-x ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
bash_event "pytest"
git -c user.name=t -c user.email=t@t checkout -q -b PROJ-2-new
bash_event "ls"
jq -cn '{session_id:"s1"}' | "$hook" start fresh
check "start fresh after the session's open build followed it to a new branch starts that branch's own record" \
  '[ "$(events)" = 1 ] && [ "$(jq -r ".kind + \" \" + .branch + \" \" + .session" .review/build/events.jsonl)" = "start PROJ-2-new s1" ]'
jq -cn '{session_id:"s1"}' | "$hook" start bogus 2>/dev/null
rc=$?
check "start with another argument exits 1 and leaves the record" '[ "$rc" = 1 ] && [ "$(events)" = 1 ]'

gates() { grep -c "\"gate\":\"$1\"" .review/build/events.jsonl; }
d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
for c in "pytest --collect-only -q" "uv run pytest --co" "pytest --version" "python -m pytest -V" "pytest -h" \
  "pytest --help | head" "pre-commit run --help" "mypy --version" "uvx pyright --help"; do
  bash_event "$c"
done
check "a run that only collects or prints its version or help is no gate" '! grep -q "\"gate\"" .review/build/events.jsonl'
bash_event "mypy --version && pytest -q tests/ && pre-commit run --all-files"
check "but a real run joined to one still is" '[ "$(gates tests) $(gates lint) $(gates types)" = "1 1 0" ]'
bash_event "pytest -k 'help or version' --cov=x"
check "and a run whose quoted or longer words only look like those flags is one" '[ "$(gates tests)" = 2 ]'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
prompt "/lasp-dev:implement-change PROJ-1" s1
mkdir -p src/pkg
(cd src/pkg && jq -cn --arg c "$d/src/pkg" '{tool_name:"Bash", session_id:"s1", cwd:$c, tool_input:{command:"uv run pytest"}}' | "$hook" event)
check "an event sent from a subdirectory is recorded at the top level" '[ "$(gates tests)" = 1 ] && [ ! -e src/pkg/.review ]'
o=$(mktemp -d) && made+=("$o")
(cd "$o" && jq -cn --arg c "$d/src" '{tool_name:"Bash", session_id:"s1", cwd:$c, tool_input:{command:"pytest"}}' | "$hook" event)
check "the payload's cwd decides the repository, not the hook's working directory" '[ "$(gates tests)" = 2 ]'
jq -cn --arg c "$d/gone" '{tool_name:"Bash", session_id:"s1", cwd:$c, tool_input:{command:"pytest"}}' | "$hook" event
rc=$?
check "a payload cwd that does not exist records nothing and exits 0" '[ "$rc" = 0 ] && [ "$(gates tests)" = 2 ]'
jq -cn --arg c "$d/gone" '{session_id:"s3", cwd:$c}' | "$hook" take implement-change 2>/dev/null
rc=$?
check "and take from it exits 1, leaving the lock" '[ "$rc" = 1 ] && [ "$(jq -r .session .review/lock)" = s1 ]'
(cd src && jq -cn --arg c "$d/src" '{session_id:"s1", cwd:$c}' | "$hook" summary)
check "a summary from a subdirectory writes the top level's block" 'grep -q "tests 2 · " .review/build/already-checked.md'

d=$(scratch) && made+=("$d") && cd "$d" || exit 1
git checkout -q --detach
prompt "/lasp-dev:implement-change PROJ-1" s1
check "a build started on a detached HEAD records no branch" \
  '[ "$(head -1 .review/build/events.jsonl | jq -r ".kind + \" [\" + .branch + \"]\"")" = "start []" ] && [ "$(jq -r .branch .review/lock)" = "" ]'
jq -cn '{tool_name:"Bash", session_id:"s2", tool_input:{command:"pytest"}}' | "$hook" event
bash_event "pytest"
check "and records only its own session's events, so detached checkouts share no build" '[ "$(gates tests)" = 1 ]'
echo "Build: passed" >.review/build/outcome.md
git -c user.name=t -c user.email=t@t checkout -q -b PROJ-2-next
prompt "/lasp-dev:implement-change PROJ-2" s1
check "and parks nothing under done/HEAD when a build starts on a branch" \
  '[ ! -e .review/build/done/HEAD ] && [ "$(head -1 .review/build/events.jsonl | jq -r .branch)" = PROJ-2-next ]'
git checkout -q --detach
bash_event "pytest"
check "the build's own session on a detached HEAD moves it nowhere" \
  '! grep -q "\"kind\":\"move\"" .review/build/events.jsonl && [ "$(jq -r "select(.branch) | .branch" .review/build/events.jsonl | tail -1)" = PROJ-2-next ]'

# A session started in repository a, building a change in repository b.
a=$(scratch) && made+=("$a") && cd "$a" || exit 1
b=$(scratch) && made+=("$b")
b_top=$(cd "$b" && pwd -P)
at_a() { jq -c --arg c "$a" '. + {cwd:$c}' | "$hook" "$@"; }
write_in() { jq -cn --arg f "$1" --arg s "$2" '{tool_name:"Write", session_id:$s, tool_input:{file_path:$f}}' | at_a guard; }
jq -cn '{prompt:"/lasp-dev:implement-change PROJ-1", session_id:"s1"}' | at_a prompt
out=$(write_in "$a/src/x.py" s1)
check "a write in the session's own repository is not refused or marked" \
  '[ -z "$out" ] && ! grep -q "\"kind\":\"elsewhere\"" .review/build/events.jsonl'
out=$(write_in "$b/src/new/x.py" s2)
check "another session's write in another repository is not refused or marked" \
  '[ -z "$out" ] && ! grep -q "\"kind\":\"elsewhere\"" .review/build/events.jsonl'
out=$(write_in "$b/src/new/x.py" s1)
check "a write in another repository while holding the lock is refused, naming it and the release" \
  'printf "%s" "$out" | jq -e ".hookSpecificOutput.permissionDecision == \"deny\" and (.hookSpecificOutput.permissionDecisionReason | test(\"this edit is in '"$b_top"'\") and test(\"Stop\") and test(\"release\"))" >/dev/null'
check "and marks the build here, writing no record in the other repository" \
  '[ "$(jq -r "select(.kind == \"elsewhere\") | .repo" .review/build/events.jsonl)" = "$b_top" ] && [ ! -e "$b/.review/build" ] && [ ! -e "$b/.review/lock" ]'
jq -cn '{tool_name:"Bash", session_id:"s1", tool_input:{command:"cd b && pytest"}}' | at_a event
jq -cn '{session_id:"s1"}' | at_a summary
check "so the build's block records its gates and tokens as not recorded, never as counts" \
  'grep -qx "Gates: not recorded, this session also edited $b_top while its build was recorded here" .review/build/already-checked.md && grep -qx "Tokens since the build started: not recorded" .review/build/already-checked.md'
eval "$(printf "%s" "$out" | jq -r .hookSpecificOutput.permissionDecisionReason | sed -n "s/.*run: //p")"
out=$(write_in "$b/src/new/x.py" s1)
check "the release the refusal names frees the lock, and the write is then allowed" \
  '[ ! -e .review/lock ] && [ -z "$out" ] && [ "$(grep -c "\"kind\":\"elsewhere\"" .review/build/events.jsonl)" = 1 ]'

# A repository c inside a parent repository p, with a nested repository and two worktrees.
write_at() { jq -cn --arg c "$1" --arg f "$2" '{tool_name:"Write", session_id:"s1", cwd:$c, tool_input:{file_path:$f}}' | "$hook" guard; }
p=$(mktemp -d) && made+=("$p") && git init -q "$p"
c="$p/c" && mv "$(scratch)" "$c" && cd "$c" || exit 1
jq -cn --arg c "$c" '{prompt:"/lasp-dev:implement-change PROJ-1", session_id:"s1", cwd:$c}' | "$hook" prompt
git init -q "$c/vendor/lib"
out=$(write_at "$c" "$c/vendor/lib/x.py")
check "a write in a repository nested in the session's, as a submodule is, is not another repository" '[ -z "$out" ]'
git worktree add -q "$c/.claude/worktrees/w1" -b PROJ-1-w1
out=$(write_at "$c" "$c/.claude/worktrees/w1/x.py")
check "nor is a write in a worktree nested in it" '[ -z "$out" ]'
git worktree add -q "$p/c-wt" -b PROJ-1-wt
out=$(write_at "$c" "$p/c-wt/x.py")
check "nor in a sibling worktree of the same repository" '[ -z "$out" ]'
out=$(write_at "$c" "$p/.claude/plan.md")
check "nor in the repository the session's sits in, as a home directory under git holds plans" '[ -z "$out" ]'
check "and none of them marks the build" '! grep -q "\"kind\":\"elsewhere\"" .review/build/events.jsonl'
mkdir -p src
out=$(write_at "$c/src" "$c/src/x.py")
check "a session in a subdirectory writing in its own repository is not refused" '[ -z "$out" ]'
out=$(write_at "$c/src" "$b/x.py")
check "and its write in another repository is refused" \
  'printf "%s" "$out" | jq -e ".hookSpecificOutput.permissionDecision == \"deny\"" >/dev/null && grep -q "\"kind\":\"elsewhere\"" .review/build/events.jsonl'

e=$(scratch) && made+=("$e") && cd "$e" || exit 1
jq -cn --arg c "$e" '{prompt:"/lasp-dev:implement-change PROJ-1", session_id:"s1", cwd:$c}' | "$hook" prompt
jq -cn --arg c "$e" '{session_id:"s1", cwd:$c}' | "$hook" release
out=$(write_at "$e" "$b/x.py")
check "with the lock released, a write in another repository is allowed but still marks the open build" \
  '[ -z "$out" ] && [ "$(jq -r "select(.kind == \"elsewhere\") | .repo" .review/build/events.jsonl)" = "$b_top" ]'

e=$(scratch) && made+=("$e") && cd "$e" || exit 1
jq -cn --arg c "$e" '{prompt:"/lasp-dev:implement-change PROJ-1", session_id:"s1", cwd:$c}' | "$hook" prompt
jq -cn --arg c "$e" '{session_id:"s1", cwd:$c}' | "$hook" release
echo "Build: passed" >.review/build/outcome.md
out=$(write_at "$e" "$b/x.py")
check "a closed build is not marked by a later write in another repository" \
  '[ -z "$out" ] && ! grep -q "\"kind\":\"elsewhere\"" .review/build/events.jsonl'

if [ "$failures" -gt 0 ]; then
  echo "$failures failed"
  exit 1
fi
echo "all passed"
