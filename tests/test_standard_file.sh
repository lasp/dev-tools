#!/usr/bin/env bash
# Runs a copy of scripts/standard_file.sh, with the standard.sh it fetches through, in a scratch
# plugin, from a scratch code repository, and checks the sections it writes, in order, for a
# repository with only the ledger and one with the ledger and its decisions, one with decisions
# alone, and one whose standards/profile.yaml points at a standard in another repository, fetched
# from a local stand-in for GitHub or read from a local checkout; and that a standard elsewhere
# with neither file, a pointer that is malformed or cannot be fetched, or a missing file in the
# plugin's standards/, writes nothing; and that the session-start hook fetches a standard never fetched, within
# its limit, and in a repository with no standard fetches and says nothing; and that
# standard_index.py lists what it writes. The held-candidates
# check also greps the skills that write the ledger for the heading the script cuts at.
# Run: bash tests/test_standard_file.sh
set -u

root=$(cd "$(dirname "$0")/.." && pwd)
original="$root/scripts/standard_file.sh"
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

echo "standard_file.sh"

parent=$(mktemp -d) && made+=("$parent")
plugin="$parent/plugin"
mkdir -p "$parent/repo/standards" "$plugin/scripts" "$plugin/standards"
cp "$original" "$plugin/scripts/standard_file.sh"
cp "$(dirname "$original")/standard.sh" "$plugin/scripts/standard.sh"
script="$plugin/scripts/standard_file.sh"
echo "body of review-rules" >"$parent/repo/standards/review-rules.md"
echo "shared review-contract" >"$plugin/standards/review-contract.md"
cd "$parent/repo" || exit 1
# The profile detects from a commit.
git init -q . && git remote add origin "git@github.com:example-team/repo.git"
git -c user.name=t -c user.email=t@t commit -q --allow-empty -m init

out=$(bash "$script" 2>err); rc=$?
check "a plugin without its profile reader exits 1 naming why and prints nothing" \
  '[ "$rc" = 1 ] && [ -z "$out" ] && grep -q "the profile could not be read" err'
cp "$root/scripts/profile.py" "$root/scripts/profile.sh" "$root/scripts/survey.py" "$plugin/scripts/"
cp "$root/standards/default-profile.yaml" "$plugin/standards/"

out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "a repository with only the ledger exits 0" '[ "$rc" = 0 ] && [ ! -s err ]'
check "it writes the contract and the ledger, in order" \
  '[ "$headings" = "# dev-tools/standards/review-contract.md,# standards/review-rules.md," ]'
check "the contract comes first, from the plugin the script is in" \
  '[ "$(printf "%s\n" "$out" | sed -n 3p)" = "shared review-contract" ]'

printf '### R-001 · A rule\n\nbody of the rule\n\n## Candidates below the criteria\n\n- candidate one\n- candidate two\n' >standards/review-rules.md
out=$(bash "$script" 2>err); rc=$?
check "the ledger stops before its held candidates, headed as onboard's first rules and revise's apply head them" \
  '[ "$rc" = 0 ] && [[ "$out" == *"body of the rule"* ]] && [[ "$out" != *"candidate one"* ]] && [[ "$out" != *"candidate two"* ]] && [[ "$out" != *"Candidates below"* ]] &&
   grep -q "\`## Candidates below the criteria\`" "$root/skills/onboard/first-rules.md" && grep -q "\`## Candidates below the criteria\`" "$root/skills/revise/apply.md"'
for heading in '### Candidates below the criteria' '## Candidates below the criteria (held)'; do
  printf '### R-001 · A rule\n\nbody of the rule\n\n%s\n\n- candidate one\n' "$heading" >standards/review-rules.md
  out=$(bash "$script" 2>err); rc=$?
  check "the candidates heading as '$heading' exits 1 and prints nothing" \
    '[ "$rc" = 1 ] && [ -z "$out" ] && grep -q "heads its held candidates as" err'
done
printf '### R-001 · A rule\n\nbody of the rule\n' >standards/review-rules.md
out=$(bash "$script" 2>err); rc=$?
check "a ledger without the candidates heading prints verbatim" \
  '[ "$rc" = 0 ] && [ "$(printf "%s\n" "$out" | sed -n "/^# standards\/review-rules.md$/,/^# /p" | sed -n 3,5p)" = "$(printf "### R-001 · A rule\n\nbody of the rule")" ]'
printf '### R-001 · A rule\n\ntier: reviewer · status: provisional · since: 2026-10\n\n> body of the rule\n' >standards/review-rules.md
bash "$script" >standard.out 2>err
listed=$(python3 "$root/scripts/standard_index.py" standard.out 2>&1); rc=$?
check "standard_index.py lists what standard_file.sh writes, each rule under its file" \
  '[ "$rc" = 0 ] && [[ "$listed" == *"Rules, from standards/review-rules.md:
  R-001 · A rule · provisional · reviewer"* ]]'
rm -f standard.out
echo "body of review-rules" >standards/review-rules.md

echo "body of decisions" >standards/decisions.md
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "a repository with its decisions adds them after the ledger" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md,# standards/review-rules.md,# standards/decisions.md," ]'
check "each section holds its file verbatim" \
  '[ "$(printf "%s\n" "$out" | sed -n "/^# standards\/decisions.md$/,/^# /p" | sed -n 3p)" = "body of decisions" ]'
echo "own terminology" >standards/terminology.md
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "a repository's own terminology follows its decisions" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md,# standards/review-rules.md,# standards/decisions.md,# standards/terminology.md," ]'
echo "own agent guidance" >standards/agent-guidance.md
echo "own data conventions" >standards/data-conventions.md
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "agent guidance, then data conventions, follow the terminology, each verbatim" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md,# standards/review-rules.md,# standards/decisions.md,# standards/terminology.md,# standards/agent-guidance.md,# standards/data-conventions.md," ] &&
   [[ "$out" == *"own agent guidance"* ]] && [[ "$out" == *"own data conventions"* ]]'
rm standards/terminology.md standards/agent-guidance.md standards/data-conventions.md

mkdir -p "$parent/dev-tools/standards"
for f in decisions terminology; do echo "sibling $f" >"$parent/dev-tools/standards/$f.md"; done
out=$(bash "$script" 2>err); rc=$?
check "a clone beside the repository is not read" '[ "$rc" = 0 ] && [[ "$out" != *"sibling"* ]]'

rm standards/review-rules.md
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "decisions with no ledger are a standard with no rules" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md,# standards/decisions.md," ]'

# A repository whose standards/profile.yaml points at a standard elsewhere: the script fetches the
# named repository with git, here a local one standing in for GitHub, and its standard stands in
# for the repository's own.
family="$parent/gh/example-team/family.git"
git init -q "$family" && mkdir -p "$family/standards/profiles"
printf '### R-001 · A family rule\n\n## Candidates below the criteria\n\n- held\n' >"$family/standards/review-rules.md"
echo "family decisions" >"$family/standards/decisions.md"
echo "family terminology" >"$family/standards/terminology.md"
printf "ticket:\n  pattern: 'FAM-\\\\d+'\n  project: FAM\n" >"$family/standards/profile.yaml"
printf "tests:\n  command: 'pytest member'\n" >"$family/standards/profiles/member.yaml"
: >"$family/standards/profiles/repo.yaml"
git -C "$family" add -A && git -C "$family" -c user.name=t -c user.email=t@t commit -qm standards
echo "elsewhere" >"$family/README.md"
git -C "$family" add -A && git -C "$family" -c user.name=t -c user.email=t@t commit -qm readme
git -C "$family" config uploadpack.allowFilter true
# GitHub, for every git the script runs, is the local folder.
export GIT_CONFIG_GLOBAL="$parent/gitconfig"
export GIT_TERMINAL_PROMPT=0
git config --global url."file://$parent/gh/".insteadOf "git@github.com:"
git config --global --add url."file://$parent/gh/".insteadOf "https://github.com/"
fsha=$(git -C "$family" log -1 --format=%h -- standards/)
mkdir -p "$parent/held" && mv standards/decisions.md "$parent/held/"
printf 'standard: example-team/family\n' >standards/profile.yaml
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "a pointer writes the fetched ledger, decisions and terminology" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md,# example-team/family/standards/review-rules.md,# example-team/family/standards/decisions.md,# example-team/family/standards/terminology.md," ]'
check "the fetched ledger loses its held candidates" '[[ "$out" != *"- held"* ]]'
check "source names the newest commit touching standards/, not the head" \
  '[ "$(cat .review/standard/source)" = "example-team/family@$fsha" ]'

# The URL takes origin's host and form; each case maps only its own, so a wrong form fails.
for form in "git@github.com:example-team/repo.git|git@github.com:" "ssh://git@github.com/example-team/repo.git|ssh://git@github.com/" "https://github.com/example-team/repo.git|https://github.com/"; do
  git remote set-url origin "${form%%|*}"
  : >"$GIT_CONFIG_GLOBAL" && git config --global url."file://$parent/gh/".insteadOf "${form#*|}"
  out=$(bash "$script" 2>err); rc=$?
  check "an origin of ${form%%|*} fetches in its own form" '[ "$rc" = 0 ]'
done
ln -s "$parent/gh" "$parent/g h=x"
: >"$GIT_CONFIG_GLOBAL" && git config url."file://$parent/g h=x/".insteadOf "https://github.com/"
rm -rf "$(git rev-parse --git-common-dir)/lasp-dev/standard"
out=$(bash "$script" 2>err); rc=$?
check "a mapping in the repository's own config, its base holding a space and =, reaches the fetch" '[ "$rc" = 0 ] && [ "$(cat .review/standard/source)" = "example-team/family@$fsha" ]'
git config --unset url."file://$parent/g h=x/".insteadOf
git config --global url."file://$parent/gh/".insteadOf "https://github.com/"
git config --global --add url."file://$parent/gh/".insteadOf "git@github.com:"

# The files are written out once per commit; a commit whose files cannot be read stops the
# standard, never reads as absent.
cache_root="$(cd "$(git rev-parse --git-common-dir)" && pwd -P)/lasp-dev/standard"
rm -rf "$cache_root"
shim="$parent/shim" && mkdir -p "$shim"
real_git=$(command -v git)
printf '#!/usr/bin/env bash\ncase "$*" in *archive*) exit 128 ;; esac\nexec "%s" "$@"\n' "$real_git" >"$shim/git"
chmod +x "$shim/git"
out=$(PATH="$shim:$PATH" bash "$script" 2>err); rc=$?
check "a failed read of the named repository's standard exits 1 and writes no source" \
  '[ "$rc" = 1 ] && grep -q "could not read standards/ of example-team/family" err && [ -z "$out" ] && [ ! -f .review/standard/source ]'
out=$(bash "$plugin/scripts/standard.sh" --offline 2>err); rc=$?
check "and a read offline after it finds nothing fetched and says so" \
  '[ "$rc" = 1 ] && grep -q "has not been fetched in this clone" err'

printf 'standard: example-team/family\r\n' >standards/profile.yaml
out=$(bash "$script" 2>err); rc=$?
check "a pointer with a carriage return is read" '[ "$rc" = 0 ]'
printf '# where the standard is\nstandard: "example-team/family"' >standards/profile.yaml
out=$(bash "$script" 2>err); rc=$?
check "a quoted pointer with a comment and no newline is read" '[ "$rc" = 0 ]'
out=$(bash "$plugin/scripts/standard.sh" --offline 2>err); rc=$?
check "a read offline prints the fetched standard's directory" \
  '[ "$rc" = 0 ] && [ -f "$(printf "%s" "$out" | cut -f2)/review-rules.md" ] && [[ "$(printf "%s" "$out" | cut -f2)" == "$cache_root/"* ]]'

git -C "$family" rm -q standards/review-rules.md standards/decisions.md
git -C "$family" -c user.name=t -c user.email=t@t commit -qm "no standard"
out=$(bash "$script" 2>err); rc=$?
check "a named repository with neither a ledger nor decisions exits 1" \
  '[ "$rc" = 1 ] && grep -q "no example-team/family/standards/review-rules.md or" err && [ -z "$out" ]'
git -C "$family" -c user.name=t -c user.email=t@t revert --no-edit HEAD >/dev/null || exit 1

printf 'standard: example-team/missing\n' >standards/profile.yaml
out=$(bash "$script" 2>err); rc=$?
check "a repository that cannot be fetched exits 1, naming it, and writes no source" \
  '[ "$rc" = 1 ] && grep -q "could not fetch .*example-team/missing" err && [ -z "$out" ] && [ ! -f .review/standard/source ]'

for body in "standard: example-team" "standard: example-team/family extra" "standard: example-team/family
tests:
  command: pytest"; do
  printf '%s\n' "$body" >standards/profile.yaml
  out=$(bash "$script" 2>err); rc=$?
  check "a pointer reading '${body//$'\n'/\\n}' is refused" \
    '[ "$rc" = 1 ] && grep -q "holds that one line alone" err && [ -z "$out" ]'
done
printf 'standard: example-team/family\n' >standards/profile.yaml

mv "$parent/held/decisions.md" standards/
for f in decisions.md review-rules.md; do
  [ -f "standards/$f" ] || echo "own $f" >"standards/$f"
  out=$(bash "$script" 2>err); rc=$?
  check "a pointer beside the repository's own $f is refused, naming both" \
    '[ "$rc" = 1 ] && grep -q "names a standard, and standards/$f is here too" err && [ -z "$out" ]'
  [ "$f" = review-rules.md ] && rm "standards/$f"
done

# A trial reads a local checkout of the standard's repository as it stands, committed or not.
trial="$parent/trial"
git clone -q "git@github.com:example-team/family.git" "$trial"
echo "uncommitted trial decisions" >"$trial/standards/decisions.md"
mv standards/decisions.md "$parent/held/"
git config lasp-dev.standard "$trial"
out=$(bash "$script" 2>err); rc=$?
check "a local checkout named in git's config is read as it stands, and marked local" \
  '[ "$rc" = 0 ] && [[ "$out" == *"# example-team/family/standards (local)/decisions.md"* ]] && [[ "$out" == *"uncommitted trial decisions"* ]] && [ "$(cat .review/standard/source)" = "example-team/family@local" ]'
git -C "$trial" remote set-url origin "git@github.com:example-team/other.git"
out=$(bash "$script" 2>err); rc=$?
check "a local checkout of another repository is refused" \
  '[ "$rc" = 1 ] && grep -q "is a checkout of example-team/other, not example-team/family" err && [ -z "$out" ]'
git config lasp-dev.standard none
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "with lasp-dev.standard none, the contract alone, said, and marked unread" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md," ] && grep -q "is not read" err && [ "$(cat .review/standard/source)" = "example-team/family@none" ]'
hook=$(printf '{"cwd":"%s"}' "$PWD" | bash "$root/hooks/rules.sh"); rc=$?
check "and the session-start hook says no standard is read and how to read it again" \
  '[ "$rc" = 0 ] && printf "%s" "$hook" | jq -r .systemMessage | grep -q "^review rules not loaded: this clone reads no standard.*git config --unset lasp-dev.standard"'
git config --unset lasp-dev.standard
rm -f standards/profile.yaml
rm -rf .review

# A repository with no standard: the default profile and what is detected.
git remote set-url origin "git@github.com:someone/member.git"
git add -A && git -c user.name=t -c user.email=t@t commit -qm "PROJ-1: a commit to detect from" >/dev/null
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "a repository with no standard gets the contract alone" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md," ]'
echo "body of review-rules" >standards/review-rules.md
echo "body of decisions" >standards/decisions.md
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "and with its own ledger and decisions adds them" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md,# standards/review-rules.md,# standards/decisions.md," ]'
printf 'flavor: plain\n' >standards/profile.yaml
out=$(bash "$script" 2>err); rc=$?
check "a profile with an unknown key stops it, naming the key" \
  '[ "$rc" = 1 ] && grep -q "unknown key .flavor." err && [ -z "$out" ]'
rm -f standards/profile.yaml standards/review-rules.md standards/decisions.md

bare="$parent/bare" && git init -q "$bare" && git -C "$bare" remote add origin https://github.com/someone/thing.git
hook=$(printf '{"cwd":"%s"}' "$bare" | bash "$root/hooks/rules.sh"); rc=$?
check "the hook says nothing in a repository with no standard, even one with no commit" '[ "$rc" = 0 ] && [ -z "$hook" ]'

# A ledger whose wording is still in an instruction file loads nothing at session start: the
# instruction file is already imported.
printf '### R-001 · Legacy\n\ntier: reviewer · status: established\n\nWording: [R-001 in the instruction file](../x.md#r-001)\n' >standards/review-rules.md
out=$(bash "$script" --rules 2>err); rc=$?
check "--rules prints nothing for a ledger that links its wording" '[ "$rc" = 0 ] && [ -z "$out" ]'
rm -f standards/review-rules.md

# A first build in a clone that never fetched: the fetch comes before the profile, which reads the
# standard's settings from what it wrote, so the build writes the standard rather than stopping at
# a profile refused for the missing fetch.
printf 'standard: example-team/family\n' >standards/profile.yaml
git add -A standards && git -c user.name=t -c user.email=t@t commit -qm "PROJ-2: points at the family" >/dev/null
rm -rf "$(git rev-parse --git-common-dir)/lasp-dev"
out=$(bash "$script" 2>err); rc=$?
headings=$(printf '%s\n' "$out" | grep '^# ' | tr '\n' ',')
check "a first build fetches the standard and writes it" \
  '[ "$rc" = 0 ] && [ "$headings" = "# dev-tools/standards/review-contract.md,# example-team/family/standards/review-rules.md,# example-team/family/standards/decisions.md,# example-team/family/standards/terminology.md," ]'
out=$(STANDARD_OFFLINE=1 python3 "$plugin/scripts/profile.py" --standard 2>err); rc=$?
check "--standard prints the fetched standard's directory, offline" \
  '[ "$rc" = 0 ] && [ -f "$out/review-rules.md" ] && [[ "$out" == "$cache_root/"* ]]'
check "and the profile reads the project's and the repository's settings from it" \
  '[ "$(python3 "$plugin/scripts/profile.py" someone/member --field ticket.project)" = FAM ] && [ "$(python3 "$plugin/scripts/profile.py" someone/member --field tests.command)" = "pytest member" ]'
# Tags: a rule or decision whose repos: line does not name this repository is not loaded.
printf '### R-001 · A family rule\n\nfor everyone\n\n### R-002 · Elsewhere only\nrepos: [other]\n\nnot for member\n\n### R-003 · Here too\nrepos: [Other, "MEMBER"]\n\nfor member\n\n## Candidates below the criteria\n\n- held\n' >"$family/standards/review-rules.md"
printf '# Decisions\n\n### D-001 · Shared\n\nshared decision\n\n### D-002 · Other only\nrepos: [other]\n\nother decision\n\n```python\n# set up\nfenced other\n```\n\nstill other\n\n````\n```\n### D-090 · inside\n````\n\n### D-003 · Two tags\nrepos: [other]\n\nrepos: [member] in the text\n\n### D-004 · CRLF tag\r\nrepos: [member]\r\n\r\ncrlf decision\r\n\n## Archive\n\nkept\n' >"$family/standards/decisions.md"
printf '# Agent guidance\n\n### A-001 · Everywhere\n\nguidance for all\n\n### A-002 · Other only\nrepos: [other]\n\nguidance for other\n' >"$family/standards/agent-guidance.md"
printf '# Data conventions\n\n### F-001 · Member only\nrepos: [member]\n\nconvention for member\n\n### F-002 · Other only\nrepos: [other]\n\nconvention for other\n' >"$family/standards/data-conventions.md"
git -C "$family" add -A && git -C "$family" -c user.name=t -c user.email=t@t commit -qm tags
out=$(bash "$script" 2>err); rc=$?
check "agent guidance and data conventions load only where tagged, as rules do" \
  '[ "$rc" = 0 ] && [[ "$out" == *"guidance for all"* ]] && [[ "$out" != *"guidance for other"* ]] &&
   [[ "$out" == *"convention for member"* ]] && [[ "$out" != *"convention for other"* ]]'
check "a standard for several loads only the rules and decisions tagged for this repository or untagged" \
  '[ "$rc" = 0 ] && [[ "$out" == *"for everyone"* ]] && [[ "$out" == *"for member"* ]] && [[ "$out" != *"not for member"* ]] && [[ "$out" != *"Elsewhere only"* ]] &&
   [[ "$out" == *"shared decision"* ]] && [[ "$out" != *"other decision"* ]] && [[ "$out" == *"## Archive"* ]] && [[ "$out" != *"- held"* ]] &&
   [[ "$out" != *"fenced other"* ]] && [[ "$out" != *"D-090"* ]] && [[ "$out" != *"still other"* ]] && [[ "$out" != *"in the text"* ]] && [[ "$out" == *"crlf decision"* ]]'
sed -i.bak 's/^repos: \[other\]$/repos: [other]  # widen later/' "$family/standards/review-rules.md" && rm "$family/standards/review-rules.md.bak"
git -C "$family" -c user.name=t -c user.email=t@t commit -qam "a tag with a comment"
out=$(bash "$script" 2>err); rc=$?
check "a repos: line that is not a list of names stops the standard, naming the rule" \
  '[ "$rc" = 1 ] && grep -q "R-002 has a repos: line that is not a list of names" err'
git -C "$family" reset -q --hard HEAD~1
git remote remove origin
out=$(bash "$script" 2>err); rc=$?
check "and with no origin, so no name to filter by, exits 1" \
  '[ "$rc" = 1 ] && [ -z "$out" ] && grep -q "this one.s name is not known" err'
git remote add origin "git@github.com:someone/member.git"
# --rules, as hooks/rules.sh runs it: the wording of the live reviewer-tier rules that apply here,
# from what was fetched, never fetching.
printf '### R-001 · Everywhere\ntier: reviewer · status: established\n\n```python\n# a comment\n>>> x\n```\n\n> wording one\n> wording two\n\n### R-002 · Elsewhere\ntier: reviewer · status: provisional\nrepos: [other]\n\n> not here\n\n### R-003 · A check\ntier: check · status: graduated\n\n> guidance\n\n### R-004 · Retired\ntier: — · status: retired\n\n## Candidates below the criteria\n\n### R-005 · Held\ntier: reviewer · status: provisional\n\n> held\n' >"$family/standards/review-rules.md"
git -C "$family" add -A && git -C "$family" -c user.name=t -c user.email=t@t commit -qm wording
bash "$script" >/dev/null 2>&1
out=$(bash "$script" --rules 2>err); rc=$?
check "--rules prints the live reviewer-tier rules that apply here, heading and wording" \
  '[ "$rc" = 0 ] && [ "$out" = "$(printf "R-001 · Everywhere\nwording one\nwording two")" ]'
check "and writes nothing under .review/" '[ "$(cat .review/standard/source)" = "example-team/family@$(git -C "$family" log -1 --format=%h -- standards/)" ]'
git remote set-url origin "git@github.com:someone/stranger.git"
out=$(bash "$script" --rules 2>err); rc=$?
check "--rules loads nothing in a repository the standard does not cover" '[ "$rc" = 1 ] && [ -z "$out" ]'
git remote set-url origin "git@github.com:someone/member.git"
hook=$(printf '{"cwd":"%s"}' "$PWD" | bash "$root/hooks/rules.sh"); rc=$?
check "the session-start hook loads them as context and says how many" \
  '[ "$rc" = 0 ] && [ "$(printf "%s" "$hook" | jq -r .systemMessage)" = "review rules loaded: 1" ] && printf "%s" "$hook" | jq -r .hookSpecificOutput.additionalContext | grep -qx "wording two"'
rm -rf "$(git rev-parse --git-common-dir)/lasp-dev"
out=$(bash "$script" --rules 2>err); rc=$?
check "--rules never fetches a standard not yet fetched" \
  '[ "$rc" = 1 ] && [ -z "$out" ] && [ ! -d "$(git rev-parse --git-common-dir)/lasp-dev" ]'
start=$(date +%s)
hook=$(printf '{"cwd":"%s"}' "$PWD" | FIRST_FETCH_SECONDS=13 bash "$root/hooks/rules.sh"); rc=$?
took=$(($(date +%s) - start))
check "the session-start hook fetches a standard never fetched, once, and loads its rules" \
  '[ "$rc" = 0 ] && [ "$(printf "%s" "$hook" | jq -r .systemMessage)" = "review rules loaded: 1" ] && [ -d "$(git rev-parse --git-common-dir)/lasp-dev" ]'
check "without waiting on its watchdog, and leaves none running" '[ "$took" -lt 5 ] && ! pgrep -f "^sleep 13$" >/dev/null'
first=$(bash "$root/scripts/standard.sh" --offline | cut -f3)
: >"$GIT_CONFIG_GLOBAL"
hook=$(printf '{"cwd":"%s"}' "$PWD" | GIT_SSH_COMMAND=false bash "$root/hooks/rules.sh"); rc=$?
check "a later session reads it as fetched, with no network" \
  '[ "$rc" = 0 ] && [ "$(printf "%s" "$hook" | jq -r .systemMessage)" = "review rules loaded: 1" ] && [ "$(bash "$root/scripts/standard.sh" --offline | cut -f3)" = "$first" ]'
rm -rf "$(git rev-parse --git-common-dir)/lasp-dev"
hook=$(printf '{"cwd":"%s"}' "$PWD" | GIT_SSH_COMMAND=false bash "$root/hooks/rules.sh"); rc=$?
check "one it cannot fetch loads no rules and says why and how to stop trying, to the person and the model" \
  '[ "$rc" = 0 ] && printf "%s" "$hook" | jq -r .systemMessage | grep -q "^review rules not loaded: could not fetch .*git config lasp-dev.standard none stops trying" &&
   [ "$(printf "%s" "$hook" | jq -r .hookSpecificOutput.additionalContext)" = "$(printf "%s" "$hook" | jq -r .systemMessage)" ]'
printf '#!/bin/sh\ntrap "" TERM\nsleep 30\nexit 1\n' >"$parent/slow-ssh" && chmod +x "$parent/slow-ssh"
start=$(date +%s)
hook=$(printf '{"cwd":"%s"}' "$PWD" | GIT_SSH_COMMAND="$parent/slow-ssh" bash "$root/hooks/rules.sh"); rc=$?
check "and the next session within a day does not try again" \
  '[ "$rc" = 0 ] && [ $(($(date +%s) - start)) -lt 3 ] && printf "%s" "$hook" | jq -r .systemMessage | grep -q "has not been fetched in this clone"'
rm -f "$(git rev-parse --git-common-dir)/lasp-dev/first-fetch-failed"
start=$(date +%s)
hook=$(printf '{"cwd":"%s"}' "$PWD" | FIRST_FETCH_SECONDS=1 GIT_SSH_COMMAND="$parent/slow-ssh" bash "$root/hooks/rules.sh"); rc=$?
check "a fetch that hangs, ignoring the stop, is killed 2 seconds after its limit, saying so, with nothing of it left running" \
  '[ "$rc" = 0 ] && [ $(($(date +%s) - start)) -lt 6 ] && printf "%s" "$hook" | jq -r .systemMessage | grep -q "could not fetch the standard within 1s" && ! pgrep -f "$parent/slow-ssh" >/dev/null'
rm -f "$(git rev-parse --git-common-dir)/lasp-dev/first-fetch-failed"
git config lasp-dev.standard relative/path
hook=$(printf '{"cwd":"%s"}' "$PWD" | GIT_SSH_COMMAND="$parent/slow-ssh" bash "$root/hooks/rules.sh"); rc=$?
check "a clone whose config names its own standard fetches nothing, and a mistake there is reported as it is, with no wait" \
  '[ "$rc" = 0 ] && printf "%s" "$hook" | jq -r .systemMessage | grep -q "not an absolute path" && ! printf "%s" "$hook" | grep -q "tried again" && [ ! -e "$(git rev-parse --git-common-dir)/lasp-dev/first-fetch-failed" ]'
git config --unset lasp-dev.standard
git config --global url."file://$parent/gh/".insteadOf "https://github.com/"
git config --global --add url."file://$parent/gh/".insteadOf "git@github.com:"
bash "$script" >/dev/null 2>&1
git remote set-url origin "git@github.com:someone/stranger.git"
out=$(bash "$script" 2>err); rc=$?
check "a repository the standard does not cover is refused" \
  '[ "$rc" = 1 ] && [ -z "$out" ] && grep -q "is refused" err && python3 "$plugin/scripts/profile.py" someone/stranger 2>&1 | grep -q "has no profiles/stranger.yaml, so the standard does not cover stranger"'
git remote set-url origin "git@github.com:someone/member.git"

# A first session in a repository with no standard, as anyone's outside a covered one is: nothing
# fetched, written or said.
plain=$(mktemp -d) && made+=("$plain") && git init -q "$plain"
hook=$(printf '{"cwd":"%s"}' "$plain" | GIT_SSH_COMMAND="$parent/slow-ssh" bash "$root/hooks/rules.sh"); rc=$?
check "the session-start hook in a repository with no standard says nothing and fetches nothing" \
  '[ "$rc" = 0 ] && [ -z "$hook" ] && [ ! -e "$plain/.git/lasp-dev" ] && [ -z "$(git -C "$plain" status --porcelain)" ]'

[ "$failures" = 0 ] && echo "All standard_file.sh checks passed." || echo "$failures standard_file.sh check(s) failed."
exit "$failures"
