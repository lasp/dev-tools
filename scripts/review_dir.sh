#!/usr/bin/env bash
# Creates .review/, the plugin's working state, and keeps it out of git: where the repository's
# ignore rules do not cover it, appends .review/ to the exclude file git names for this clone,
# which changes nothing in the repository, and prints one line saying so. Run from the
# repository's top level by hooks/build-record.sh, or given that directory as its one argument;
# outside a git repository, or given a directory it cannot enter, it creates nothing.
# Always exits 0.
[ -z "$1" ] || cd "$1" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
mkdir -p .review 2>/dev/null || exit 0
git check-ignore -q .review/x 2>/dev/null && exit 0
# A worktree's .git is a file, so the exclude file's path is asked of git, never assumed.
exclude=$(git rev-parse --git-path info/exclude 2>/dev/null) || exit 0
mkdir -p "$(dirname "$exclude")" 2>/dev/null
[ -s "$exclude" ] && [ -n "$(tail -c 1 "$exclude")" ] && printf '\n' >>"$exclude"
printf '.review/\n' >>"$exclude" 2>/dev/null \
  && echo "Added .review/ to $exclude, so git ignores the plugin's working state."
exit 0
