# Sourced by the hooks and where.sh: reads this repository's profile once, through
# profile.py, and answers one field at a time. The repository is the owner/name in the origin
# remote's URL. With no remote, or a profile profile.py refuses, it reads the default profile's
# values under the standard's (profile.py --defaults) with no source, and a field the profile reads
# as `not yet recorded` gives that value. When --defaults is refused too, as for a default profile
# or a standard the schema refuses or a standard elsewhere not yet fetched, there are no values at
# all, and profile.py's message on the repository is kept in profile_error for the hook to say.
# With no python3, every field gives the caller's default, so a hook never fails on the profile.
#
#   . scripts/profile.sh; profile_field ticket.pattern ''

profile_repo=$(git remote get-url origin 2>/dev/null | sed -E 's#\.git$##; s#^.*[:/]([^/:]+/[^/]+)$#\1#') || profile_repo=""
profile_py="$(dirname "${BASH_SOURCE[0]}")/profile.py"
profile_lines=""
profile_defaults=""
profile_error=""
# profile.py's answer to "$@", its error dropped. The error is read by asking again, never through
# a temporary file, which a sandboxed shell may not be allowed to make.
profile_ask() { python3 "$profile_py" "$@" 2>/dev/null; }

if command -v python3 >/dev/null 2>&1; then
  { [ -n "$profile_repo" ] && profile_lines=$(profile_ask "$profile_repo"); } \
    || profile_lines=$(profile_ask --defaults) || profile_lines=""
  # Refused for --defaults too: the hooks say why.
  if [ -z "$profile_lines" ] && [ -n "$profile_repo" ]; then
    profile_error=$(python3 "$profile_py" "$profile_repo" 2>&1 >/dev/null | sed -n '1s/^profile.py: //p') || :
  fi
  # The defaults, read once, for the fields the profile has not recorded.
  case "$profile_lines" in
    *": not yet recorded"*) profile_defaults=$(profile_ask --defaults) || profile_defaults="" ;;
  esac
fi

# The field's value; the defaults' when the profile has none or reads `not yet recorded`, under the
# field or its section; else the caller's default.
profile_field() {
  local v
  v=$(printf '%s\n' "$profile_lines" | sed -n "s/^$1: //p" | head -1)
  if { [ -z "$v" ] || [ "$v" = "not yet recorded" ]; } && [ "$1" != source ]; then
    v=$(printf '%s\n' "$profile_defaults" | sed -n "s/^$1: //p" | head -1)
  fi
  if [ -n "$v" ] && [ "$v" != "not yet recorded" ]; then printf '%s' "$v"; else printf '%s' "$2"; fi
}

# The field as the profile itself gives it, empty when it has none or reads `not yet recorded`.
profile_raw() {
  local v
  v=$(printf '%s\n' "$profile_lines" | sed -n "s/^$1: //p" | head -1)
  [ "$v" = "not yet recorded" ] || printf '%s' "$v"
}

# A project field, which profile.py prints only under --defaults, such as issue_tracker.kind: the
# defaults' value, read here when the profile did not need them, or empty when it reads `not yet
# recorded` or the defaults cannot be read.
profile_project() {
  local v
  [ -n "$profile_defaults" ] || profile_defaults=$(profile_ask --defaults) || profile_defaults=""
  v=$(printf '%s\n' "$profile_defaults" | sed -n "s/^$1: //p" | head -1)
  [ "$v" = "not yet recorded" ] || printf '%s' "$v"
}

# A profile pattern as grep -E reads it: `\d` becomes `[0-9]`.
profile_ere() { printf '%s' "${1//\\d/[0-9]}"; }
