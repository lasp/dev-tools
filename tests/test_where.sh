#!/usr/bin/env bash
# Runs hooks/where.sh in scratch repositories and checks the session-start line it prints: the
# ticket from the branch or from .review/context.md, the Branch: line that keeps that fallback on
# its own branch, the plan file found by its exact name, and the build and lock parts.
# Run: bash tests/test_where.sh
set -u

root=$(cd "$(dirname "$0")/.." && pwd)
hook="$root/hooks/where.sh"
failures=0
made=()
trap 'rm -rf "${made[@]}"' EXIT

check() {
  if eval "$2"; then
    echo "  ok    $1"
  else
    echo "  FAIL  $1"
    echo "        line: $line"
    failures=$((failures + 1))
  fi
}

# The ticket key of the scratch repositories' standard.
standard="ticket:\n  pattern: 'PROJ-\\d+'\n  project: PROJ\n"

# A repository on branch $1, with its own standard, and an empty .review/.
scratch() {
  local d
  d=$(mktemp -d)
  git -C "$d" init -q -b "$1"
  git -C "$d" remote add origin "git@github.com:someone/scratch.git"
  mkdir "$d/standards" && printf "$standard" >"$d/standards/profile.yaml"
  git -C "$d" add standards
  git -C "$d" -c user.name=t -c user.email=t@t commit -q -m init
  mkdir "$d/.review"
  printf '%s' "$d"
}

# The whole message, every line of it.
where() { echo '{}' | bash "$hook" | jq -r .systemMessage; }
# A plan file the person approved at the plan gate.
approved() { printf '# Plan\nApproved by: a-reviewer\n' >"$1"; }

echo "where.sh"

d=$(scratch PROJ-1-test) && made+=("$d") && cd "$d" || exit 1
approved .review/implementation-plan-proj-1.md
line=$(where)
check "a branch with a key names its ticket and finds its plan" \
  '[ "${line%% · next*}" = "PROJ-1 · PROJ-1-test · plan approved · no build" ]'
printf '# Plan\n' >.review/implementation-plan-proj-1.md
line=$(where)
check "a plan with no Approved by: line is a draft" \
  '[ "${line%% · next*}" = "PROJ-1 · PROJ-1-test · plan drafted · no build" ]'
printf '# Plan\nApproved by: a-reviewer\n\n## Revision 1 — PRRT_9\n' >.review/implementation-plan-proj-1.md
line=$(where)
check "a redesign with no Approved by: line of its own is a draft" \
  '[ "${line%% · next*}" = "PROJ-1 · PROJ-1-test · redesign drafted · no build" ]'
printf 'Approved by: a-reviewer\n' >>.review/implementation-plan-proj-1.md
line=$(where)
check "and approved once its section carries one" \
  '[ "${line%% · next*}" = "PROJ-1 · PROJ-1-test · plan approved · no build" ]'

d=$(scratch PROJ-2-test) && made+=("$d") && cd "$d" || exit 1
touch .review/implementation-plan-proj-2-extra.md .review/implementation-plan-x-proj-2.md
line=$(where)
check "a plan file that only contains the key is not the plan" '[[ "$line" == *"· no plan ·"* ]]'
approved .review/implementation-plan-proj-2.md
line=$(where)
check "the exact name is" '[[ "$line" == *"· plan approved ·"* ]]'

d=$(scratch feature/PROJ-3-test) && made+=("$d") && cd "$d" || exit 1
line=$(where)
check "a key after a feature/ prefix is the ticket" '[[ "$line" == "PROJ-3 · feature/PROJ-3-test ·"* ]]'

d=$(scratch proj-775-log-retention) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/context
echo "# PROJ-775 · Configure log retention" >.review/context/PROJ-775.md
echo .review/ >>.git/info/exclude
line=$(where)
check "a key in lower case starts the branch too, written in the pattern's case" \
  '[[ "$line" == "PROJ-775 · proj-775-log-retention ·"* ]]'
line=$(bash "$hook" --fields)
check "and its context page and plan are the canonical key's" \
  '[[ "$line" == "ticket=PROJ-775"$'"'"'\n'"'"'* ]] && [[ "$line" == *"context=$(pwd -P)/.review/context/PROJ-775.md"* ]] && [[ "$line" == *"plan=$(pwd -P)/.review/implementation-plan-proj-775.md"* ]]'
line=$(bash "$hook" --fields --ticket proj-775)
check "a --ticket key in lower case is read as the canonical key" '[[ "$line" == "ticket=PROJ-775"$'"'"'\n'"'"'* ]]'

d=$(scratch feature/Proj-12-mixed) && made+=("$d") && cd "$d" || exit 1
line=$(where)
check "a mixed-case key after a feature/ prefix is the ticket" '[[ "$line" == "PROJ-12 · feature/Proj-12-mixed ·"* ]]'

d=$(scratch proj-775-log) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/reopened
echo .review/ >>.git/info/exclude
echo "# Plan" >.review/implementation-plan-proj-775-log.md
printf 'Reopened: PRRT_1 · the frame was wrong\n' >.review/reopened/proj-775-log.txt
line=$(bash "$hook" --fields)
check "a lower-case key on a branch with its own plan leaves the branch its own work" \
  '[[ "$line" == "ticket="$'"'"'\n'"'"'* ]] && [[ "$line" == *"plan=$(pwd -P)/.review/implementation-plan-proj-775-log.md"* ]] && [[ "$line" == *$'"'"'\nreopened=PRRT_1\n'"'"'* ]]'

d=$(scratch fix-proj-13) && made+=("$d") && cd "$d" || exit 1
line=$(bash "$hook" --fields)
check "a key that does not start the branch is still not the ticket" '[[ "$line" == "ticket="$'"'"'\n'"'"'* ]]'

d=$(scratch fix/thing) && made+=("$d") && cd "$d" || exit 1
line=$(where)
check "with no ticket, plan or build, the line says so once" \
  '[ "$line" = "no ticket on this branch · fix/thing · next: /lasp-dev:work" ]'
approved .review/implementation-plan-fix-thing.md
line=$(where)
check "with no ticket, the plan is named for the branch" \
  '[ "${line%% · next*}" = "no ticket · fix/thing · plan approved · no build" ]'

d=$(scratch feature/x) && made+=("$d") && cd "$d" || exit 1
printf '# PROJ-830 · A ticket\n\nGoal: something\n' >.review/context.md
line=$(where)
check "no key and a context page with no Branch: line uses the page" '[[ "$line" == "PROJ-830 · feature/x · "* ]]'
printf '# PROJ-830 · A ticket\nBranch: feature/x\n\nGoal: something\n' >.review/context.md
approved .review/implementation-plan-proj-830.md
line=$(where)
check "no key and a matching Branch: line uses the page" \
  '[ "${line%% · next*}" = "PROJ-830 · feature/x · plan approved · no build" ]'

d=$(scratch feature/y) && made+=("$d") && cd "$d" || exit 1
printf 'Controlled: PROJ-831 — CUI\n# PROJ-831 · A ticket\nBranch: feature/y\n\nGoal: something\n' >.review/context.md
line=$(where)
check "a context page that opens with a Controlled: line is read past it to its heading" '[[ "$line" == "PROJ-831 · feature/y · "* ]]'
printf 'Controlled: PROJ-831 — CUI\n# PROJ-831 · A ticket\nBranch: feature/other\n' >.review/context.md
line=$(where)
check "and its Branch: line still says which branch the page is on" '[[ "$line" == "PROJ-831 is on feature/other, not here · feature/y · "* ]]'
printf 'Controlled: PROJ-831 — CUI\n\n# PROJ-831 · A ticket\n' >.review/context.md
line=$(where)
check "but only the line straight after it is the heading" '[[ "$line" != "PROJ-831"* ]]'

d=$(scratch feature/z) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/context
printf '# retry-policy · Retry a failed download\n\n## Placement\n' >.review/context/retry-policy.md
cp .review/context/retry-policy.md .review/context.md
line=$(bash "$hook" --fields)
check "a page under a slug is a drafted ticket not yet filed: its slug, no ticket and no context" \
  '[[ "$line" == "ticket="$'"'"'\nbranch=feature/z\ncontext=\n'"'"'* ]] && [[ "$line" == *$'"'"'\nslug=retry-policy\nelsewhere='"'"' ]]'
line=$(python3 "$root/scripts/next_phase.py" --fields <(bash "$hook" --fields))
check "and work stops on it, naming the file to file in the tracker" \
  '[[ "$line" == *"why: unfiled"* ]] && [[ "$line" == *".review/context/retry-policy.jira.txt"* ]]'
printf '# retry-policy · Retry a failed download\nBranch: feature/z\n' >.review/context.md
line=$(bash "$hook" --fields)
check "and so is one whose Branch: line names this branch" '[[ "$line" == *$'"'"'\nslug=retry-policy\n'"'"'* ]]'
printf 'Controlled: retry-policy — CUI\n# retry-policy · Retry a failed download\nBranch: feature/z\n' >.review/context.md
line=$(bash "$hook" --fields)
check "and so is one that opens with a Controlled: line" '[[ "$line" == *$'"'"'\nslug=retry-policy\n'"'"'* ]]'
printf '# retry-policy · Retry a failed download\nBranch: feature/other\n' >.review/context.md
line=$(bash "$hook" --fields)
check "but not one whose Branch: line names another branch" '[[ "$line" == "ticket="$'"'"'\n'"'"'* ]] && [[ "$line" == *$'"'"'\nslug=\n'"'"'* ]]'
printf '# PROJ-830 · A ticket\n' >.review/context.md
printf '# PROJ-830 · A ticket\n' >.review/context/PROJ-830.md
line=$(bash "$hook" --fields)
check "and a first line with a key gives the ticket, not a slug" '[[ "$line" == "ticket=PROJ-830"$'"'"'\n'"'"'* ]] && [[ "$line" == *$'"'"'\nslug=\n'"'"'* ]]'
printf '# no-such-page · A ticket\n' >.review/context.md
line=$(bash "$hook" --fields)
check "and a slug with no page under .review/context/ is no slug" '[[ "$line" == *$'"'"'\nslug=\n'"'"'* ]]'
printf '# retry-policy · Retry what PROJ-830 left out\n' >.review/context.md
line=$(bash "$hook" --fields)
check "and a key in a slug page's summary is not its ticket" \
  '[[ "$line" == "ticket="$'"'"'\n'"'"'* ]] && [[ "$line" == *$'"'"'\nslug=retry-policy\n'"'"'* ]]'
cp .review/context/retry-policy.md .review/context.md
line=$(bash "$hook" --fields --ticket PROJ-9)
check "and a key given on a slug page is that ticket, with no slug" \
  '[[ "$line" == "ticket=PROJ-9"$'"'"'\n'"'"'* ]] && [[ "$line" == *$'"'"'\nslug=\n'"'"'* ]]'
: >.review/implementation-plan-feature-z.md
line=$(bash "$hook" --fields)
check "and a branch with its own plan is its own work, with no slug" \
  '[[ "$line" == "ticket="$'"'"'\n'"'"'* ]] && [[ "$line" == *$'"'"'\nslug=\n'"'"'* ]]'

d=$(scratch standards/review-loops-phase0) && made+=("$d") && cd "$d" || exit 1
printf '# PROJ-830 · A ticket\nBranch: PROJ-830-src-seq-ctr-order-report\n\nGoal: something\n' >.review/context.md
touch .review/implementation-plan-proj-830.md
line=$(where)
check "no key and a Branch: line naming another branch says where the ticket is" \
  '[ "$line" = "PROJ-830 is on PROJ-830-src-seq-ctr-order-report, not here · standards/review-loops-phase0 · next: /lasp-dev:work" ]'
approved .review/implementation-plan-standards-review-loops-phase0.md
line=$(where)
check "but a branch with its own plan is its own work, not the page's ticket" \
  '[ "${line%% · next*}" = "no ticket · standards/review-loops-phase0 · plan approved · no build" ]'

d=$(scratch PROJ-4-test) && made+=("$d") && cd "$d" || exit 1
approved .review/implementation-plan-proj-4.md
mkdir -p .review/build
printf 'Build: passed\n' >.review/build/outcome.md
printf '{"t":"2026-09-30T10:00:00Z","branch":"PROJ-4-test"}\n' >.review/build/events.jsonl
line=$(where)
check "a finished build is named, and the line ends at next" \
  '[ "$line" = "PROJ-4 · PROJ-4-test · plan approved · build passed · next: /lasp-dev:work" ]'

printf '{"session":"another","skill":"implement-change","t":"2026-09-30T10:05:00Z"}\n' >.review/lock
line=$(where)
check "a lock another session holds is named before next" \
  '[ "$line" = "PROJ-4 · PROJ-4-test · plan approved · build passed · held by implement-change since 2026-09-30T10:05:00Z · next: /lasp-dev:work" ]'
touch -t 202609300000 .review/lock
line=$(where)
check "but a lock untouched for four hours is stale and not named" \
  '[ "$line" = "PROJ-4 · PROJ-4-test · plan approved · build passed · next: /lasp-dev:work" ]'
line=$(bash "$hook" --fields)
check "and --fields gives it as no lock" '[[ "$line" == *$'"'"'\nlock=\n'"'"'* ]]'
rm .review/lock

printf '{"t":"2026-09-30T10:00:00Z","branch":"another-branch"}\n' >.review/build/events.jsonl
line=$(where)
check "a build recorded for another branch is not this branch's" \
  '[ "$line" = "PROJ-4 · PROJ-4-test · plan approved · no build · next: /lasp-dev:work" ]'
mkdir -p .review/build/done/PROJ-4-test
printf 'Build: passed\n' >.review/build/done/PROJ-4-test/outcome.md
line=$(where)
check "but this branch's finished build, parked by a build on another branch, is" \
  '[ "$line" = "PROJ-4 · PROJ-4-test · plan approved · build passed · next: /lasp-dev:work" ]'
rm -r .review/build/done

d=$(scratch PROJ-5-test) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/context .review/build
echo "# PROJ-5" >.review/context/PROJ-5.md
printf '# Plan\nBase: main\n' >.review/implementation-plan-proj-5.md
printf 'Build: passed\nDepth: standard\nReopened: PRRT_9 · the frame was wrong\nReopened: PRRT_12 · the cache was wrong\n' >.review/build/outcome.md
printf '{"t":"2026-09-30T10:00:00Z","branch":"PROJ-5-test"}\n' >.review/build/events.jsonl
echo .review/ >>.git/info/exclude
line=$(bash "$hook" --fields)
check "--fields prints the facts, one per line, on a clean tree" \
  '[ "$line" = "$(printf "ticket=PROJ-5\nbranch=PROJ-5-test\ncontext=$(pwd -P)/.review/context/PROJ-5.md\nplan=$(pwd -P)/.review/implementation-plan-proj-5.md\nbase=main\noutcome=Build: passed\noutcome_reopened=PRRT_9 PRRT_12\nbuild_branch=PROJ-5-test\ndirty=false\nlock=\nprofile=standards/profile.yaml\npart=\nreopened=\nreopened_file=$(pwd -P)/.review/reopened/PROJ-5.txt\nslug=\nelsewhere=")" ]'
echo x >notes.txt
echo x >todo.txt
touch -t 202609010000 notes.txt todo.txt
line=$(bash "$hook" --fields)
check "untracked files older than the build leave the tree clean" '[[ "$line" == *"dirty=false"* ]]'
echo x >made.txt
line=$(bash "$hook" --fields)
check "an untracked file made since the build started is dirty" '[[ "$line" == *"dirty=true"* ]]'
mv .review/build/events.jsonl events.keep
line=$(bash "$hook" --fields)
check "with no build, an untracked file is dirty" '[[ "$line" == *"dirty=true"* ]]'
mv events.keep .review/build/events.jsonl
rm made.txt
git add notes.txt
printf '{"session":"another","skill":"pr-fix","t":"2026-09-30T10:05:00Z"}\n' >.review/lock
line=$(bash "$hook" --fields)
check "and says when the tree is dirty and who holds the lock" \
  '[[ "$line" == *"dirty=true"* ]] && [[ "$line" == *"lock=pr-fix"* ]]'
git -c user.name=t -c user.email=t@t commit -q -m notes
echo y >notes.txt
line=$(bash "$hook" --fields)
check "an unstaged change to a tracked file is dirty" '[[ "$line" == *"dirty=true"* ]]'
rm .review/lock
mkdir -p src/pkg && cd src/pkg || exit 1
line=$(bash "$hook" --fields)
check "--fields from a subdirectory reads the top level's .review/" \
  '[[ "$line" == *$'"'"'\noutcome=Build: passed\n'"'"'* ]] && [[ "$line" == *"base=main"* ]]'
check "and its paths name the top level's files, which a caller there can open" \
  '[ -f "$(printf "%s\n" "$line" | sed -n "s/^plan=//p")" ] && [ -f "$(printf "%s\n" "$line" | sed -n "s/^context=//p")" ]'
line=$(jq -cn --arg c "$d/src/pkg" '{cwd:$c}' | bash "$hook" | jq -r .systemMessage)
check "and so does the session-start line from the payload's cwd" \
  '[ "${line%% · next*}" = "PROJ-5 · PROJ-5-test · plan drafted · build passed" ]'
cd "$(mktemp -d)" && made+=("$PWD")
line=$(jq -cn --arg c "$d/src" '{cwd:$c}' | bash "$hook" | jq -r .systemMessage)
check "the payload's cwd decides the repository, not the hook's working directory" \
  '[[ "$line" == "PROJ-5 · PROJ-5-test · "* ]]'
out=$(jq -cn --arg c "$d/gone" '{cwd:$c}' | bash "$hook"; echo "exit $?")
line=$out
check "a payload cwd that does not exist prints nothing and exits 0" '[ "$out" = "exit 0" ]'
cd "$d" || exit 1

d=$(scratch PROJ-9-x) && made+=("$d") && cd "$d" || exit 1
approved .review/implementation-plan-proj-9.md
git checkout -q --detach
line=$(bash "$hook" --fields)
check "a detached HEAD is no branch, with no plan named for it" \
  '[[ "$line" == "ticket="$'"'"'\nbranch=\ncontext=\nplan=\n'"'"'* ]] && [[ "$line" == *$'"'"'\nreopened_file=\n'"'"'* ]]'
line=$(where)
check "and the session-start line says no branch" \
  '[ "$line" = "no ticket on this branch · no branch · next: /lasp-dev:work" ]'

d=$(scratch PROJ-6-two) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/context
printf '# PROJ-6\nBranch: PROJ-6-one (part 1 of 2)\nBranch: PROJ-6-two (part 2 of 2)\n' >.review/context/PROJ-6.md
cp .review/context/PROJ-6.md .review/context.md
printf '# Plan\nBase: main (part 1 of 2)\nBase: PROJ-6-one (part 2 of 2)\n' >.review/implementation-plan-proj-6.md
line=$(bash "$hook" --fields)
mkdir -p .review/reopened
printf 'Reopened: PRRT_9 · the frame was wrong\nReopened: PRRT_12 · the cache was wrong\n' >.review/reopened/PROJ-6.txt
printf 'Reopened: PRRT_1 · another ticket\n' >.review/reopened/PROJ-7.txt
check "the second part of a two-part ticket gets its part and its base" \
  '[[ "$line" == *"base=PROJ-6-one"* ]] && [[ "$line" == *"part=2 of 2"* ]]'
line=$(bash "$hook" --fields)
check "and the thread ids of its own reopened file, not another ticket's" '[[ "$line" == *$'"'"'\nreopened=PRRT_9 PRRT_12\nreopened_file='"'"'"$(pwd -P)/.review/reopened/PROJ-6.txt"$'"'"'\n'"'"'* ]]'
printf 'Reopened: PRRT_9\n' >>.review/reopened/PROJ-6.txt
bash "$hook" --fields >/dev/null 2>&1
rc=$?
line="exit $rc"
check "a reopened line with no clause exits 1" '[ "$rc" = 1 ]'


git -c user.name=t -c user.email=t@t checkout -q -b feature/x
line=$(where)
check "a branch none of the page's Branch: lines names is told where the ticket is" \
  '[[ "$line" == "PROJ-6 is on PROJ-6-one, not here · feature/x"* ]]'

d=$(scratch feature/y) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/reopened
printf '# Plan\nBase: main\n' >.review/implementation-plan-feature-y.md
printf 'Reopened: PRRT_3 · the frame was wrong\nReopened: session-7-1 · the reader must judge prose\n' >.review/reopened/feature-y.txt
printf 'Reopened: PRRT_1 · a ticket of the same name\n' >.review/reopened/.txt
line=$(bash "$hook" --fields)
check "a branch with no ticket reads its own reopened file, threads and session reopens alike" \
  '[[ "$line" == *$'"'"'\nreopened=PRRT_3 session-7-1\nreopened_file='"'"'"$(pwd -P)/.review/reopened/feature-y.txt"$'"'"'\n'"'"'* ]]'

for bad in 'session-1' 'session-0007-1'; do
  printf 'Reopened: %s · an id in another form\n' "$bad" >.review/reopened/feature-y.txt
  bash "$hook" --fields >/dev/null 2>err; rc=$?
  check "a session reopen written $bad is refused, naming the form" \
    '[ "$rc" = 1 ] && grep -q "session-<pr>-<n>" err'
done

# A standard that keys tickets as GEO-\d+.
d=$(scratch GEO-12-x) && made+=("$d") && cd "$d" || exit 1
printf "ticket:\n  pattern: 'GEO-\\d+'\n" >standards/profile.yaml
line=$(where)
check "the profile's ticket pattern names the ticket, its \\d read as a digit" \
  '[[ "$line" == "GEO-12 · GEO-12-x · "* ]]'

d=$(scratch fix-after-GEO-12) && made+=("$d") && cd "$d" || exit 1
printf "ticket:\n  pattern: 'PROJ-\\d+|GEO-\\d+'\n" >standards/profile.yaml
line=$(where)
check "a pattern with an alternation still starts the branch name" \
  '[[ "$line" == "no ticket on this branch · fix-after-GEO-12 · "* ]]'
line=$(bash "$hook" --fields)
check "--fields names the profile file the repository runs on" \
  '[[ "$line" == *$'"'"'\nprofile=standards/profile.yaml\n'"'"'* ]]'
rm -r standards
line=$(bash "$hook" --fields)
check "and none for a repository with no standard" '[[ "$line" == *$'"'"'\nprofile=none\n'"'"'* ]]'

# A standard whose tracker is GitHub's and records no pattern: the key is the issue number.
github="issue_tracker:\n  kind: github\n  statuses:\n    - {name: ready, next: implement-change, role: approved}\n  pr_statuses: []\n"
for b in 59-words issue-59-words Issue-59-words feature/59-x feature/issue-59-x; do
  d=$(scratch "$b") && made+=("$d") && cd "$d" || exit 1
  printf "$github" >standards/profile.yaml
  line=$(bash "$hook" --fields | head -1)
  check "on a GitHub tracker, the branch $b names issue 59 by its number" '[ "$line" = "ticket=59" ]'
done
line=$(bash "$hook" --fields)
check "and its plan and reopened file are the number's" \
  '[[ "$line" == *"plan=$(pwd -P)/.review/implementation-plan-59.md"* ]] && [[ "$line" == *"reopened_file=$(pwd -P)/.review/reopened/59.txt"* ]]'
line=$(where)
check "and the session-start line shows it as #59" '[ "${line%% · next*}" = "#59 · feature/issue-59-x · no plan · no build" ]'
line=$(bash "$hook" --fields --ticket 12 | head -1)
check "--ticket 12, a bare number, is the issue" '[ "$line" = "ticket=12" ]'
line=$(bash "$hook" --fields --ticket issue-12 | head -1)
check "and so is issue-12, reduced to its number" '[ "$line" = "ticket=12" ]'
bash "$hook" --fields --ticket '#12' >/dev/null 2>&1; rc=$?
line="exit $rc"
check "but #12 is not a key: an argument is the bare number" '[ "$rc" = 1 ]'
d=$(scratch fix/no-number) && made+=("$d") && cd "$d" || exit 1
printf "$github" >standards/profile.yaml
mkdir -p .review/context
printf '# #59 · Retry a failed download\nBranch: fix/no-number\n' >.review/context/59.md
cp .review/context/59.md .review/context.md
echo .review/ >>.git/info/exclude
line=$(bash "$hook" --fields)
check "a context page headed # #59 names issue 59 and is its page" \
  '[[ "$line" == "ticket=59"$'"'"'\n'"'"'* ]] && [[ "$line" == *"context=$(pwd -P)/.review/context/59.md"* ]] && [[ "$line" == *$'"'"'\nslug=\n'"'"'* ]]'
printf '# #59 · Retry\nBranch: 59-elsewhere\n' >.review/context.md
line=$(where)
check "and one built on another branch says so as #59" '[[ "$line" == "#59 is on 59-elsewhere, not here · fix/no-number · "* ]]'
d=$(scratch GH-7-x) && made+=("$d") && cd "$d" || exit 1
printf "ticket:\n  pattern: 'GH-\\\\d+'\n$github" >standards/profile.yaml
line=$(bash "$hook" --fields | head -1)
check "a GitHub tracker's recorded pattern names the issue, reduced to its number" '[ "$line" = "ticket=7" ]'
d=$(scratch 59-words) && made+=("$d") && cd "$d" || exit 1
printf "$github" >standards/profile.yaml
for b in PROJ-42-csv PROJ-43-x PROJ-44-y; do git branch "$b"; done
line=$(bash "$hook" --fields | head -1)
check "a GitHub tracker reads no pattern detected from a Jira-keyed history" '[ "$line" = "ticket=59" ]'
d=$(scratch 59-words) && made+=("$d") && cd "$d" || exit 1
line=$(bash "$hook" --fields | head -1)
check "a Jira repository's branch 59-words names no ticket" '[ "$line" = "ticket=" ]'
bash "$hook" --fields --ticket 59 >/dev/null 2>&1; rc=$?
line="exit $rc"
check "and --ticket 59 is not one of its keys" '[ "$rc" = 1 ]'

d=$(scratch proj-5-lower) && made+=("$d") && cd "$d" || exit 1
printf "ticket:\n  pattern: 'proj-\\d+'\n" >standards/profile.yaml
line=$(where)
check "a key the pattern matches exactly is written as found" '[[ "$line" == "proj-5 · proj-5-lower · "* ]]'

# A plugin copy with no profile reader, as with no python3: no pattern, so no ticket.
bare=$(mktemp -d) && made+=("$bare")
mkdir -p "$bare/hooks" && cp "$hook" "$bare/hooks/"
d=$(scratch PROJ-4-reader) && made+=("$d") && cd "$d" || exit 1
line=$(echo '{}' | bash "$bare/hooks/where.sh" | jq -r .systemMessage)
check "with no profile reader, the branch names no ticket rather than a team's pattern" \
  '[[ "$line" == "no ticket on this branch · PROJ-4-reader · "* ]]'
out=$(bash "$bare/hooks/where.sh" --fields --ticket PROJ-4 2>err); rc=$?
check "and a given key exits 1 saying the profile could not be read" \
  '[ "$rc" = 1 ] && grep -q "no ticket key pattern: the profile could not be read" err'

# A plugin copy whose default profile is missing, so profile.py refuses: a filed ticket's context page
# on this branch is read as neither a ticket nor an unfiled draft.
broken=$(mktemp -d) && made+=("$broken")
mkdir -p "$broken/hooks" "$broken/scripts" && cp "$hook" "$broken/hooks/" && cp "$root/scripts/profile.py" "$root/scripts/profile.sh" "$broken/scripts/"
d=$(scratch PROJ-4-reader) && made+=("$d") && cd "$d" || exit 1
printf '# PROJ-4 · a filed ticket\nBranch: PROJ-4-reader\n' >.review/context.md
mkdir -p .review/context && cp .review/context.md .review/context/PROJ-4.md
line=$(bash "$broken/hooks/where.sh" --fields)
check "with a default profile profile.py refuses, a context page is no ticket and no unfiled draft" \
  '[[ "$line" == "ticket="$'"'"'\n'"'"'* ]] && [[ "$line" == *$'"'"'\nslug=\n'"'"'* ]]'

d=$(mktemp -d) && made+=("$d") && cd "$d" || exit 1
git init -q -b PROJ-8-fresh && git remote add origin "git@github.com:someone/scratch.git"
mkdir standards && printf "$standard" >standards/profile.yaml && git add standards && git -c user.name=t -c user.email=t@t commit -q -m init
line=$(bash "$hook" --fields)
check "--fields in a clone with no .review/ prints every line, the local ones empty" \
  '[ "$line" = "$(printf "ticket=PROJ-8\nbranch=PROJ-8-fresh\ncontext=\nplan=$(pwd -P)/.review/implementation-plan-proj-8.md\nbase=\noutcome=\noutcome_reopened=\nbuild_branch=\ndirty=false\nlock=\nprofile=standards/profile.yaml\npart=\nreopened=\nreopened_file=$(pwd -P)/.review/reopened/PROJ-8.txt\nslug=\nelsewhere=")" ] && [ ! -e .review ]'

d=$(scratch main) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/context
printf '# PROJ-830\nBranch: PROJ-830-x\n' >.review/context/PROJ-830.md
printf '# PROJ-9\n' >.review/context.md
echo .review/ >>.git/info/exclude
line=$(bash "$hook" --fields --ticket PROJ-830)
check "--ticket names the ticket on a branch that does not, and where it is built" \
  '[[ "$line" == "ticket=PROJ-830"$'"'"'\n'"'"'* ]] && [[ "$line" == *"context=$(pwd -P)/.review/context/PROJ-830.md"* ]] && [[ "$line" == *"plan=$(pwd -P)/.review/implementation-plan-proj-830.md"* ]] && [[ "$line" == *"part="$'"'"'\n'"'"'* ]] && [[ "$line" == *"elsewhere=PROJ-830-x" ]]'
line=$(bash "$hook" --fields --ticket PROJ-831)
check "and a key with no page of its own is not given another ticket's" \
  '[[ "$line" == "ticket=PROJ-831"$'"'"'\n'"'"'* ]] && [[ "$line" == *"context="$'"'"'\n'"'"'* ]] && [[ "$line" == *"elsewhere=" ]]'
# A reviewer on their own branch drafts a ticket from someone else's pull request: the page
# ticket-draft writes names the pull request's head, and .review/context.md stays the reviewer's.
d=$(scratch review-loader) && made+=("$d") && cd "$d" || exit 1
mkdir -p .review/context
printf '# PROJ-9\nBranch: review-loader\n' >.review/context.md
printf '# PROJ-840\nBranch: fix-loader-typo\n\n## Placement\n' >.review/context/PROJ-840.md
echo .review/ >>.git/info/exclude
line=$(bash "$hook" --fields)
check "a page drafted from a pull request leaves the reviewer's branch its own ticket" \
  '[[ "$line" == "ticket=PROJ-9"$'"'"'\n'"'"'* ]] && [[ "$line" == *"elsewhere=" ]]'
bash "$hook" --fields --ticket PROJ-840 >.review/work-fields.txt
line=$(python3 "$root/scripts/next_phase.py" --fields .review/work-fields.txt)
check "and work on its key here says it is built on the pull request's head, not to plan it" \
  '[[ "$line" == *"elsewhere"* ]] && [[ "$line" == *"fix-loader-typo"* ]] && [[ "$line" != *"implement-change"* ]]'
bash "$hook" --fields --ticket main >/dev/null 2>&1
rc=$?
line="exit $rc"
check "a --ticket that is not a key exits 1" '[ "$rc" = 1 ]'
bash "$hook" --fields PROJ-830 >/dev/null 2>&1
rc=$?
line="exit $rc"
check "and so does an argument --fields does not read" '[ "$rc" = 1 ]'
env PATH=/nonexistent /bin/bash "$hook" --fields >/dev/null 2>&1
rc=$?
line="exit $rc"
check "and --fields with no jq on the PATH" '[ "$rc" = 1 ]'

d=$(scratch PROJ-7-refused) && made+=("$d") && cd "$d" || exit 1
printf "${standard}flavor: plain\n" >standards/profile.yaml
line=$(where)
check "a standard the schema refuses says the profile is refused and why" \
  '[ "${line%% · next*}" = "profile refused: standards/profile.yaml: unknown key '"'"'flavor'"'"' · PROJ-7-refused" ]'
printf "$standard" >standards/profile.yaml
line=$(where)
check "and with it read, names the ticket again" '[ "${line%% · next*}" = "PROJ-7 · PROJ-7-refused · no plan · no build" ]'
nomktemp=$(mktemp -d) && made+=("$nomktemp")
printf '#!/bin/sh\nexit 1\n' >"$nomktemp/mktemp" && chmod +x "$nomktemp/mktemp"
line=$(echo '{}' | PATH="$nomktemp:$PATH" bash "$hook" | jq -r .systemMessage)
check "a shell that cannot make a temporary file still reads the profile" '[ "${line%% · next*}" = "PROJ-7 · PROJ-7-refused · no plan · no build" ]'

[ "$failures" = 0 ] && echo "All where.sh checks passed." || echo "$failures where.sh check(s) failed."
exit "$failures"
