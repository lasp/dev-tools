#!/usr/bin/env bash
# Prints the standard every build and review agent loads, as one file: the review contract from
# the plugin this script ships in, then the standard's review rules, decisions, terminology, agent
# guidance and data conventions, each under a `# <path>` heading and otherwise verbatim. The ledger
# stops before its held-candidates heading, so a reviewer never loads a rule the team has not
# admitted; that heading at any other level or with a suffix exits 1. In a standard covering
# several repositories, a rule, decision, agent guidance or data convention tagged `repos: [...]`
# loads only in the repositories it names; a `repos:` line that is not that list of names exits 1,
# naming the entry.
# Run from the code repository's top level; the skills redirect it to .review/standard.md.
#
# The standard is the repository's own standards/, or, when its standards/profile.yaml is the one
# line `standard: <owner>/<repo>`, the standard that repository holds, fetched afresh by
# standard.sh first, since the profile below reads its settings from what that fetch wrote; or a
# local checkout git's config names for a trial. .review/standard/source records which, one line,
# `<owner>/<repo>@<7-character sha>`, `@local` or `@none`, for pr-review's standards: line. A failed
# fetch stops the standard; no earlier copy stands in. With `git config lasp-dev.standard none`,
# the person's choice when the standard cannot be fetched, it writes the contract alone and says so.
# A pointer beside the repository's own ledger or decisions would be a second standard.
#
# A standard elsewhere with neither review-rules.md nor decisions.md is empty, and a plugin missing
# its contract is broken: each exits 1 naming the file and prints nothing, so the standard is
# written whole or not at all. Decisions with no ledger are a standard with no rules yet. Any other
# repository gets the contract and whichever of its own ledger, decisions, terminology, agent
# guidance and data conventions exist.
#
# With --rules, as the session-start hook runs it, it prints instead only the wording of the
# rules that apply to the repository, each live reviewer-tier rule's heading and its `> ` lines,
# from a standard elsewhere only as already fetched; it writes nothing, never fetches, and prints
# nothing for a repository with no ledger or no such rule.
set -euo pipefail

rules=""
if [ "${1:-}" = --rules ]; then
  rules=yes
  export STANDARD_OFFLINE=1
  # A repository with neither a ledger nor a pointer has no rules to load and nothing to say.
  [ -f standards/review-rules.md ] || { [ -f standards/profile.yaml ] && grep -qE '^standard:' standards/profile.yaml; } || exit 0
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
plugin="$(cd "$here/.." && pwd -P)"
dir=standards
label=standards
elsewhere=no
unread=""
[ -n "$rules" ] || { mkdir -p .review/standard && rm -f .review/standard/source; }
source_line() { [ -n "$rules" ] || printf '%s\n' "$1" >.review/standard/source; }
if [ -f standards/profile.yaml ] && grep -qE '^standard:' standards/profile.yaml; then
  for f in review-rules.md decisions.md; do
    if [ -f "standards/$f" ]; then
      echo "standard_file.sh: standards/profile.yaml names a standard, and standards/$f is here too; a repository's standard is in one place" >&2
      exit 1
    fi
  done
  fetched=$(bash "$here/standard.sh" ${rules:+--offline}) || exit 1
  IFS=$'\t' read -r named directory version <<<"$fetched"
  if [ "$version" = none ]; then
    unread=$named
    source_line "$named@none"
  else
    dir=$directory
    elsewhere=yes
    if [ "$version" = local ]; then
      label="$named/standards (local)"
      source_line "$named@local"
    else
      label="$named/standards"
      source_line "$named@${version:0:7}"
    fi
  fi
fi

# A profile that is there and refused stops the standard, naming why; the hooks default instead.
profile_py="$here/profile.py"
command -v python3 >/dev/null 2>&1 && [ -f "$profile_py" ] \
  || { echo "standard_file.sh: the profile could not be read, which needs python3 and the plugin's scripts/profile.py" >&2; exit 1; }
profile_repo=$(git remote get-url origin 2>/dev/null | sed -E 's#\.git$##; s#^.*[:/]([^/:]+/[^/]+)$#\1#') || profile_repo=""
if [ -n "$profile_repo" ]; then
  python3 "$profile_py" "$profile_repo" >/dev/null || { echo "standard_file.sh: the profile for $profile_repo is refused" >&2; exit 1; }
fi
[ -n "$rules" ] && [ -n "$unread" ] && exit 0
if [ -n "$unread" ]; then
  echo "standard_file.sh: $unread's standard is not read, as lasp-dev.standard in git's config is none: the review contract alone" >&2
  [ -f "$plugin/standards/review-contract.md" ] || { echo "standard_file.sh: no review-contract.md in $plugin/standards" >&2; exit 1; }
  printf '# %s\n\n' "dev-tools/standards/review-contract.md"; cat "$plugin/standards/review-contract.md"; printf '\n'
  exit 0
fi

own=()
[ -f "$dir/review-rules.md" ] && own+=(review-rules.md)
[ -f "$dir/decisions.md" ] && own+=(decisions.md)
if [ ${#own[@]} -eq 0 ] && [ "$elsewhere" = yes ]; then
  echo "standard_file.sh: no $label/review-rules.md or $label/decisions.md in $(pwd)" >&2
  exit 1
fi
# The held candidates are cut only at that exact heading; the same words at another level or with
# a suffix would leave them in what reviewers load, so they stop the standard instead.
if [ -f "$dir/review-rules.md" ]; then
  stray=$(grep -nE '^#+[[:space:]]*Candidates below the criteria' "$dir/review-rules.md" | grep -vE '^[0-9]+:## Candidates below the criteria[[:space:]]*$' || true)
  if [ -n "$stray" ]; then
    echo "standard_file.sh: $label/review-rules.md heads its held candidates as '${stray#*:}', not '## Candidates below the criteria'" >&2
    exit 1
  fi
fi

shared="$plugin/standards"
[ -f "$shared/review-contract.md" ] || { echo "standard_file.sh: no review-contract.md in $shared" >&2; exit 1; }

# A standard with profiles/ covers several repositories: an entry whose `repos:` line
# does not name this one, ignoring case, is left out of what it loads.
# A heading inside a code fence is not one, and only a block's first `repos:` line counts, as
# rule_lint.py, which refuses a second, reads it.
mine=""
if [ -d "$dir/profiles" ]; then
  [ -n "$profile_repo" ] || { echo "standard_file.sh: $label covers several repositories, and with no origin remote this one's name is not known" >&2; exit 1; }
  mine=$(printf '%s' "${profile_repo##*/}" | tr '[:upper:]' '[:lower:]')
fi
for_repo() {
  if [ -z "$mine" ]; then cat "$1"; return; fi
  awk -v repo="$mine" -v file="$1" '
    function flush() { if (keep) printf "%s", buf; buf = "" }
    { sub(/\r$/, "") }
    fence == "" && /^(#|##|###) / { flush(); block = ($0 ~ /^### [RDAF]-[0-9]+/); keep = 1; tagged = 0; id = $2 }
    /^(```|~~~)/ {
      match($0, /^(`+|~+)/); mark = substr($0, 1, RLENGTH)
      if (fence == "") fence = mark
      else if (substr(mark, 1, 1) == substr(fence, 1, 1) && length(mark) >= length(fence)) fence = ""
    }
    !block { print; next }
    { buf = buf $0 "\n" }
    fence == "" && /^repos:/ && !tagged++ {
      if ($0 !~ /^repos:[ \t]*\[[ \t]*[\047"]?[A-Za-z0-9_.-]+[\047"]?([ \t]*,[ \t]*[\047"]?[A-Za-z0-9_.-]+[\047"]?)*[ \t]*\][ \t]*$/) {
        printf "standard_file.sh: %s: %s has a repos: line that is not a list of names, %s\n", file, id, $0 > "/dev/stderr"
        bad = 1; exit 1
      }
      line = tolower($0); sub(/^repos:[ \t]*\[/, "", line); sub(/\][ \t]*$/, "", line)
      n = split(line, names, ","); keep = 0
      for (i = 1; i <= n; i++) { name = names[i]; gsub(/[ \t\047"]/, "", name); if (name == repo) keep = 1 }
    }
    END { if (!bad) flush() }' "$1"
}
section() { printf '# %s\n\n' "$1"; for_repo "$2"; printf '\n'; }
# The ledger without its held candidates; a ledger without the heading prints whole.
ledger() { printf '# %s\n\n' "$1"; for_repo "$2" | sed '/^## Candidates below the criteria[[:space:]]*$/,$d'; printf '\n'; }

if [ -n "$rules" ]; then
  [ -f "$dir/review-rules.md" ] || exit 0
  # Each live reviewer-tier rule's heading and wording, the `> ` lines unquoted; nothing inside a
  # code fence is a heading or wording, as rule_lint.py reads them.
  ledger "$label/review-rules.md" "$dir/review-rules.md" | awk '
    function flush() { if (live && text != "") printf "%s\n%s\n", head, text; text = "" }
    { sub(/\r$/, "") }
    /^(```|~~~)/ {
      match($0, /^(`+|~+)/); mark = substr($0, 1, RLENGTH)
      if (fence == "") fence = mark
      else if (substr(mark, 1, 1) == substr(fence, 1, 1) && length(mark) >= length(fence)) fence = ""
      next
    }
    fence != "" { next }
    /^(#|##|###) / { flush(); head = ""; live = 0 }
    /^### R-[0-9]+/ { head = substr($0, 5) }
    head != "" && /tier:/ && /status:/ { live = ($0 ~ /tier:[ *]*reviewer/ && $0 ~ /status:[ *]*(provisional|established)/) }
    head != "" && /^>/ { line = $0; sub(/^>[ \t]?/, "", line); text = text line "\n" }
    END { flush() }'
  exit 0
fi
section "dev-tools/standards/review-contract.md" "$shared/review-contract.md"
for f in ${own[@]+"${own[@]}"}; do
  if [ "$f" = review-rules.md ]; then ledger "$label/$f" "$dir/$f"; else section "$label/$f" "$dir/$f"; fi
done
for f in terminology.md agent-guidance.md data-conventions.md; do
  if [ -f "$dir/$f" ]; then section "$label/$f" "$dir/$f"; fi
done
