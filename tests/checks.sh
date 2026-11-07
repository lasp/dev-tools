#!/usr/bin/env bash
# Runs the pull request checks one after another and prints one line per step; a failed step
# also prints the last 40 lines of its output, and the full logs stay in the directory the last
# line names. Serial on purpose: run together, test_profile, test_window_merges and
# test_surface_diff fail on each other's temporary state.
#
#   bash tests/checks.sh            the tests of what the branch changes against origin/main,
#                                   committed or not, then check_static.py and codespell:
#                                   - a changed tests/test_* file;
#                                   - for a script, hook or sandbox .py or .sh, every test file
#                                     naming it, and every test file naming a script, hook or
#                                     sandbox file that names it;
#                                   - for any other file under scripts/, hooks/, sandbox/ or
#                                     standards/templates/, every test file naming it, or the
#                                     whole suite when none does;
#                                   - the whole suite for tests/fixtures/, pyproject.toml or
#                                     .python-version.
#                                   Skills, agents and docs get the static checks only.
#   bash tests/checks.sh NAME...    only tests/test_NAME.py or tests/test_NAME.sh for each NAME,
#                                   such as `next_phase where`
#   bash tests/checks.sh --all      CI's steps but its gitleaks scan: the mcp-atlassian cache, the
#                                   unit tests, every tests/test_*.sh, check_static.py, both
#                                   again on Python 3.9, codespell and `claude plugin validate .`,
#                                   the last with the installed claude, not CI's pinned version
#
# Exits 0 when every step passed, 1 when one failed, and 2 for a NAME with no test file, a
# missing tool, or no origin/main to compare with.
cd "$(dirname "$0")/.." || exit 2
# The tests make hundreds of throwaway commits. Without the person's git configuration they run
# as on CI, which has none, and unsigned: a signing key there makes each commit about twice as slow.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
logs=$(mktemp -d "${TMPDIR:-/tmp}/checks.XXXXXX") || exit 2
home=""
failed=0 n=0
trap '[ "$failed" = 1 ] || rm -rf "$logs"; [ -z "$home" ] || rm -rf "$home"' EXIT

step() {
  local name=$1; shift
  n=$((n + 1))
  local log="$logs/$n-${name//[^A-Za-z0-9_.-]/_}.log" start=$SECONDS
  if "$@" >"$log" 2>&1; then
    printf 'ok    %-28s %3ss\n' "$name" $((SECONDS - start))
  else
    printf 'FAIL  %-28s %3ss\n' "$name" $((SECONDS - start))
    tail -n 40 "$log" | sed 's/^/      /'
    failed=1
  fi
}

need() { command -v "$1" >/dev/null || { echo "checks.sh: $1 is not on PATH" >&2; exit 2; }; }

run_test() {
  case $1 in
    *.py) step "$(basename "$1")" uv run python -m unittest discover -s tests -p "$(basename "$1")" ;;
    *.sh) step "$(basename "$1")" bash "$1" ;;
  esac
}

naming() { grep -l -F "$1" tests/test_*.py tests/test_*.sh 2>/dev/null; }

static() {
  step "check_static" uv run python scripts/check_static.py
  step "codespell" uv run codespell --builtin clear,rare,en-GB_to_en-US --skip "./.git,./tests/fixtures" .
}

whole_suite() {
  step "unit tests" uv run python -m unittest discover -s tests
  for t in tests/test_*.sh; do
    run_test "$t"
  done
}

need uv
if [ "$1" = --all ]; then
  need uvx
  need claude
  step "mcp-atlassian cache" uvx --from mcp-atlassian@0.23.1 python -c pass
  whole_suite
  static
  step "unit tests, python 3.9" uv run --isolated --python 3.9 python -m unittest discover -s tests
  step "check_static, python 3.9" uv run --isolated --python 3.9 python scripts/check_static.py
  home=$(mktemp -d) || exit 2
  step "plugin validate" env HOME="$home" claude plugin validate .
elif [ $# -gt 0 ]; then
  tests=()
  for name in "$@"; do
    if [ -f "tests/test_$name.py" ]; then
      tests+=("tests/test_$name.py")
    elif [ -f "tests/test_$name.sh" ]; then
      tests+=("tests/test_$name.sh")
    else
      echo "checks.sh: no tests/test_$name.py or tests/test_$name.sh" >&2
      exit 2
    fi
  done
  for t in "${tests[@]}"; do
    run_test "$t"
  done
else
  base=$(git merge-base origin/main HEAD 2>/dev/null) \
    || { echo "checks.sh: no origin/main to compare with; name the tests or pass --all" >&2; exit 2; }
  selected=$logs/selected
  whole=0
  : >"$selected"
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    name=$(basename "$f")
    case $f in
      tests/fixtures/* | pyproject.toml | .python-version) whole=1 ;;
      tests/test_*.py | tests/test_*.sh) [ -f "$f" ] && echo "$f" >>"$selected" ;;
      scripts/*.py | scripts/*.sh | hooks/*.sh | sandbox/*.py)
        naming "$name" >>"$selected"
        for loader in $(grep -l -F "$name" scripts/*.py scripts/*.sh hooks/*.sh sandbox/*.py 2>/dev/null); do
          [ "$loader" = "$f" ] || naming "$(basename "$loader")" >>"$selected"
        done ;;
      scripts/* | hooks/* | sandbox/* | standards/templates/*)
        naming "$name" >>"$selected" || whole=1 ;;
    esac
  done < <({ git diff --name-only --no-renames "$base"; git ls-files --others --exclude-standard; } | sort -u)
  if [ "$whole" = 1 ]; then
    whole_suite
  else
    while IFS= read -r t; do
      run_test "$t"
    done < <(sort -u "$selected")
  fi
  static
fi

if [ "$failed" = 1 ]; then
  echo "full logs: $logs"
  exit 1
fi
echo "all $n passed"
