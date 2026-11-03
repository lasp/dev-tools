#!/usr/bin/env bash
# Finds the standard a repository's standards/profile.yaml points at with its `standard:` line and
# prints one line, `<owner>/<repo><TAB><directory><TAB><version>`: the repository that holds the
# standard, the directory holding its standards/ files, and the commit they were read at, or
# `local` for a checkout named in git's config. Run from the code repository's top level;
# standard_file.sh reads the ledger, decisions and terminology from the directory, and profile.py
# the settings. With no `standard:` line it prints nothing.
#
# A trial of changes not yet merged reads a local checkout of the standard's repository, named once
# per clone with `git config lasp-dev.standard <absolute path>`, as it stands, committed or not;
# its origin must name the pointer's repository. `git config lasp-dev.standard none`, the
# person's choice when the standard cannot be fetched, prints the version `none` and the directory `-`,
# and the readers go on without the standard and say so. Otherwise the fetch goes as the person's git
# reaches the repository's own origin, under their global and system config and this repository's
# config file's url.<base>.insteadOf mappings, so a private one needs no other credential, into a partial
# clone in this repository's git directory, and the commit's standards/ is written out beside it,
# so every later read is of plain files with no network.
#
# With no option it fetches, as a build or review does at its step. With --cached, a cache that
# has fetched before is read as it stands, as of its last fetch; one that never has fetches once.
# With --offline, as a hook reads it, nothing is ever fetched, and a clone that has not fetched
# yet exits 1 saying so. A pointer that is not one `standard: <owner>/<repo>` line, a failed fetch,
# or a repository with no standards/ on its default branch exits 1 naming why; no earlier fetch
# stands in for a failed one.
set -euo pipefail

mode=fetch
case "${1:-}" in
  --cached) mode=cached ;;
  --offline) mode=offline ;;
  "") ;;
  *) echo "standard.sh: unknown option $1" >&2; exit 2 ;;
esac

profile=standards/profile.yaml
[ -f "$profile" ] || exit 0
# The file's lines without comments or blanks; a pointer is the only line of a file that has one.
lines=$(tr -d '\r' <"$profile" | sed -E 's/(^|[[:space:]])#.*$//; s/[[:space:]]+$//' | grep -v '^$' || true)
printf '%s\n' "$lines" | grep -qE '^standard:' || exit 0
if [ "$(printf '%s\n' "$lines" | grep -c '')" != 1 ] \
    || ! printf '%s' "$lines" | grep -qE "^standard:[[:space:]]+([A-Za-z0-9-]+/[A-Za-z0-9_.-]+|'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+'|\"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+\")$"; then
  echo "standard.sh: $profile holds a standard: line, so it holds that one line alone, standard: <owner>/<repo>" >&2
  exit 1
fi
named=$(printf '%s' "$lines" | sed -E "s/^standard:[[:space:]]+//; s/['\"]//g")

checkout=$(git config --get lasp-dev.standard || true)
if [ "$checkout" = none ]; then
  printf '%s\t-\tnone\n' "$named"
  exit 0
fi
if [ -n "$checkout" ]; then
  case "$checkout" in
    /*) ;;
    *) echo "standard.sh: lasp-dev.standard in git's config is $checkout, not an absolute path" >&2; exit 1 ;;
  esac
  [ -d "$checkout/standards" ] || { echo "standard.sh: $checkout, which lasp-dev.standard names, has no standards/" >&2; exit 1; }
  theirs=$(git -C "$checkout" config --get remote.origin.url 2>/dev/null | sed -E 's#\.git/?$##; s#^.*[:/]([^/:]+/[^/]+)$#\1#' || true)
  if [ "$(printf '%s' "$theirs" | tr '[:upper:]' '[:lower:]')" != "$(printf '%s' "$named" | tr '[:upper:]' '[:lower:]')" ]; then
    echo "standard.sh: $checkout, which lasp-dev.standard names, is a checkout of ${theirs:-no origin}, not $named" >&2
    exit 1
  fi
  printf '%s\t%s\t%s\n' "$named" "$(cd "$checkout/standards" && pwd -P)" local
  exit 0
fi

# The standard's URL on origin's host and in origin's form, SSH or HTTPS, host aliases included;
# with no origin, GitHub over HTTPS. A url.<base>.insteadOf mapping in git's config overrides it.
# The URL as configured: `git remote get-url` would apply insteadOf, which the fetch applies itself.
origin=$(git config --get remote.origin.url || true)
if [[ "$origin" =~ ^([a-z+]+://[^/]+)/ ]]; then
  url="${BASH_REMATCH[1]}/$named.git"
elif [[ "$origin" =~ ^([^/:]+): ]]; then
  url="${BASH_REMATCH[1]}:$named.git"
else
  url="https://github.com/$named.git"
fi
base="$(cd "$(git rev-parse --git-common-dir)" && pwd -P)/lasp-dev/standard/${named/\//__}"
cache="$base.git"
# The cache is named by --git-dir, never -C, so a directory that is not yet a repository is refused
# rather than resolved upward to this repository's own. Its ref `done` is written only once a fetch
# has written the commit's standards/ out to $base/<sha>, so a fetch stopped at any earlier point,
# a hook's at its timeout included, leaves a cache the next fetch fills again; FETCH_HEAD, which a
# fetch in progress empties, is never what a read goes by.
done=refs/lasp-dev/standards
cached_git() { git --git-dir="$cache" "$@"; }
written() {
  local sha
  sha=$(cached_git rev-parse -q --verify "$done" 2>/dev/null) && [ -d "$base/$sha/standards" ] && printf '%s' "$sha"
}
if [ "$mode" != fetch ] && sha=$(written); then
  printf '%s\t%s\t%s\n' "$named" "$base/$sha/standards" "$sha"
  exit 0
fi
if [ "$mode" = offline ]; then
  echo "standard.sh: $named's standard has not been fetched in this clone; a build or a review fetches it, or run bash $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/standard.sh from the repository's top level" >&2
  exit 1
fi

# The cache is a repository of its own, which reads the person's global and system config but not
# this repository's: this repository's url.<base>.insteadOf mappings are passed to every git the
# fetch runs, the fetches of a partial clone's blobs included, through git's environment.
n=${GIT_CONFIG_COUNT:-0}
while IFS= read -r -d '' entry; do
  export "GIT_CONFIG_KEY_$n=${entry%%$'\n'*}" "GIT_CONFIG_VALUE_$n=${entry#*$'\n'}"
  n=$((n + 1))
done < <(git config --local --includes -z --get-regexp '^url\..*\.insteadof$' || true)
export GIT_CONFIG_COUNT=$n

# Only a fetch writes the cache's configuration, and only what differs, so a read never contends
# for its lock. Two runs setting up one new cache at once race on the init and the config lock, and
# write the same values, so a step that fails is not the answer: the end state is, checked, and set
# up once more after a second before the run gives up.
setup() {
  cached_git rev-parse --git-dir >/dev/null 2>&1 || git init -q --bare "$cache" 2>/dev/null || true
  [ "$(cached_git config --get remote.standard.url 2>/dev/null || true)" = "$url" ] \
    || cached_git remote set-url standard "$url" 2>/dev/null || cached_git remote add standard "$url" 2>/dev/null || true
  [ "$(cached_git config --get remote.standard.promisor 2>/dev/null || true)" = true ] \
    || cached_git config remote.standard.promisor true 2>/dev/null || true
  [ "$(cached_git config --get remote.standard.partialclonefilter 2>/dev/null || true)" = blob:none ] \
    || cached_git config remote.standard.partialclonefilter blob:none 2>/dev/null || true
}
ready() {
  cached_git rev-parse --git-dir >/dev/null 2>&1 \
    && [ "$(cached_git config --get remote.standard.url || true)" = "$url" ] \
    && [ "$(cached_git config --get remote.standard.promisor || true)" = true ] \
    && [ "$(cached_git config --get remote.standard.partialclonefilter || true)" = blob:none ]
}
setup
if ! ready; then
  sleep 1
  setup
  ready || { echo "standard.sh: could not set up the cache $cache for $url; deleting it starts the cache over" >&2; exit 1; }
fi

# Never a prompt: a session cannot answer one, so a missing credential fails the fetch.
export GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh} -o BatchMode=yes -o ConnectTimeout=15"
# Each run fetches into a ref of its own, so two fetches at once never read each other's
# FETCH_HEAD.
fetched=refs/lasp-dev/fetch-$$
trap 'cached_git update-ref -d "$fetched" >/dev/null 2>&1 || true' EXIT
if ! cached_git fetch -q --filter=blob:none standard "+HEAD:$fetched"; then
  echo "standard.sh: could not fetch $url, which $profile names, on origin's host and in its form; a url.<base>.insteadOf mapping in git's config points it elsewhere, and deleting $cache starts the cache over" >&2
  exit 1
fi
sha=$(cached_git log -1 --format=%H "$fetched" -- standards/)
if [ -z "$sha" ] || ! cached_git rev-parse -q --verify "$sha:standards" >/dev/null; then
  echo "standard.sh: $named has no standards/ on its default branch" >&2
  exit 1
fi
if [ ! -d "$base/$sha/standards" ]; then
  # Written beside its final place and moved there whole, so a reader never sees part of it.
  partial="$base/$sha.$$.tmp"
  rm -rf "$partial" && mkdir -p "$partial"
  if ! cached_git archive --format=tar "$sha" standards/ | tar -x -C "$partial"; then
    rm -rf "$partial"
    echo "standard.sh: could not read standards/ of $named at ${sha:0:7}" >&2
    exit 1
  fi
  # Another run may have put the same commit's files in place first; then this copy goes.
  if [ -e "$base/$sha" ] || ! mv "$partial" "$base/$sha" 2>/dev/null; then
    rm -rf "$partial"
  fi
  # A run that put the directory in place between the check and the move gets this copy inside it.
  rm -rf "$base/$sha/$(basename "$partial")"
  [ -d "$base/$sha/standards" ] || { echo "standard.sh: could not write standards/ of $named at ${sha:0:7} to $base/$sha" >&2; exit 1; }
fi
previous=$(cached_git rev-parse -q --verify "$done" 2>/dev/null || true)
cached_git update-ref "$done" "$sha"
# An earlier commit's files go ten minutes after a later commit replaced them, so a read already
# on them finishes: the replaced directory's clock starts now. A run stopped mid-write leaves a
# .tmp that goes the same way.
[ -n "$previous" ] && [ "$previous" != "$sha" ] && [ -d "$base/$previous" ] && touch "$base/$previous"
find "$base" -mindepth 1 -maxdepth 1 ! -name "$sha" -mmin +10 -exec rm -rf {} + 2>/dev/null || true
printf '%s\t%s\t%s\n' "$named" "$base/$sha/standards" "$sha"
