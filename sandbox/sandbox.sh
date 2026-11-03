#!/usr/bin/env bash
# Builds a sandbox for running the plugin's skills: the plugin and the repositories the scenarios
# run in, cloned at fixed commits, each with a local bare repository as its push target, so a
# session can fetch from GitHub but never push to it. Nothing outside the sandbox directory is written.
#
#   sandbox/sandbox.sh <dir> --plugin-ref <sha> --owner <owner> --repo <name>=<path>@<ref>...
#       [--venv <name>] [--mcp-from-user <name>...]
#
#   <dir>          the sandbox; created, and refused if it already exists
#   --plugin-ref   the plugin commit under test, from this clone
#   --owner        the GitHub owner every clone's origin fetches from, as github.com/<owner>/<name>
#   --repo         clone the repository <name> from the clone at <path> at <ref>, pinned and pushed
#                  nowhere; at least one. A skill that reads a consumer beside the repository finds
#                  it there. Git LFS objects the source already has are copied in
#   --venv         also create repos/<name>/.venv with `poetry install`, which implement-change-wave
#                  needs; <name> is one of the --repo names
#   --mcp-from-user  copy these MCP server definitions out of your user-scope configuration into
#                  <dir>/mcp.json, which sbx-claude passes with --strict-mcp-config. The file is
#                  written with mode 600, never printed, and read by nothing but Claude Code.
#
# Each clone is checked out on a branch named for the commit's own branch where one contains it
# (so `work` and `pr-create` see a real branch name), else on live/<sha7>. Origin fetches from
# GitHub; its push URL is the bare repository under remotes/. The commits are written to
# <dir>/pins so the runner reports against them.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="" plugin_ref="" owner="" venv="" mcp=() repos=()
while [ $# -gt 0 ]; do
    case "$1" in
        --plugin-ref) plugin_ref=$2; shift 2 ;;
        --owner) owner=$2; shift 2 ;;
        --repo) repos+=("$2"); shift 2 ;;
        --venv) venv=$2; shift 2 ;;
        --mcp-from-user)
            shift
            while [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; do mcp+=("$1"); shift; done
            ;;
        -*) echo "sandbox.sh: unknown option $1" >&2; exit 2 ;;
        *) dir=$1; shift ;;
    esac
done
if [ -z "$dir" ] || [ -z "$plugin_ref" ] || [ -z "$owner" ] || [ "${#repos[@]}" -eq 0 ]; then
    echo "usage: sandbox.sh <dir> --plugin-ref <sha> --owner <owner> --repo <name>=<path>@<ref>... [--venv <name>]" >&2
    exit 2
fi
[ -e "$dir" ] && { echo "sandbox.sh: $dir exists; choose a new directory" >&2; exit 1; }
# Every refusal comes before the first write, so a refused build leaves no directory to remove.
git -C "$here" rev-parse --verify -q "$plugin_ref^{commit}" >/dev/null || { echo "sandbox.sh: --plugin-ref $plugin_ref is not a commit here" >&2; exit 1; }
names=(dev-tools)
for spec in "${repos[@]}"; do
    name=${spec%%=*} rest=${spec#*=}
    [ -n "$name" ] && [ "$name" != "$spec" ] && [ "${rest%@*}" != "$rest" ] || { echo "sandbox.sh: --repo $spec is not <name>=<path>@<ref>" >&2; exit 2; }
    case " ${names[*]} " in *" $name "*) echo "sandbox.sh: --repo $name is the plugin's clone or given twice" >&2; exit 2 ;; esac
    [ -d "${rest%@*}/.git" ] || [ -f "${rest%@*}/.git" ] || { echo "sandbox.sh: no git clone at ${rest%@*}" >&2; exit 1; }
    git -C "${rest%@*}" rev-parse --verify -q "${rest##*@}^{commit}" >/dev/null || { echo "sandbox.sh: ${rest##*@} is not a commit in ${rest%@*}" >&2; exit 1; }
    names+=("$name")
done
if [ -n "$venv" ]; then
    case " ${names[*]:1} " in *" $venv "*) ;; *) echo "sandbox.sh: --venv $venv is not a --repo name" >&2; exit 2 ;; esac
fi

mkdir -p "$dir/repos" "$dir/remotes" "$dir/runs"
dir=$(cd "$dir" && pwd)

# The branch that contains $2 in the clone at $1, preferring one whose tip is $2.
branch_for() {
    local b
    b=$(git -C "$1" for-each-ref refs/heads --points-at "$2" --format='%(refname:short)' | head -1)
    [ -n "$b" ] || b=$(git -C "$1" for-each-ref refs/heads --contains "$2" --format='%(refname:short)' | head -1)
    printf '%s' "${b:-live/$(git -C "$1" rev-parse --short "$2")}"
}

# clone <name> <source> <ref>: a bare copy as the push target, a working clone at <ref>, and the
# Git LFS objects the source already has.
clone() {
    local name=$1 source=$2 ref=$3 sha branch lfs
    sha=$(git -C "$source" rev-parse --verify "$ref^{commit}")
    branch=$(branch_for "$source" "$sha")
    git clone -q --bare "$source" "$dir/remotes/$name.git"
    GIT_LFS_SKIP_SMUDGE=1 git clone -q --no-checkout "$dir/remotes/$name.git" "$dir/repos/$name"
    GIT_LFS_SKIP_SMUDGE=1 git -C "$dir/repos/$name" checkout -q -B "$branch" "$sha"
    git -C "$dir/repos/$name" remote set-url origin "https://github.com/$owner/$name.git"
    # run.py's reset puts origin back to this, since a scenario's setup may point it elsewhere.
    git -C "$dir/repos/$name" config sandbox.fetch "https://github.com/$owner/$name.git"
    git -C "$dir/repos/$name" remote set-url --push origin "$dir/remotes/$name.git"
    echo "$name $sha $branch" >>"$dir/pins"
    lfs="$(git -C "$source" rev-parse --git-common-dir)/lfs/objects"
    case "$lfs" in /*) ;; *) lfs="$source/$lfs" ;; esac
    if [ -d "$lfs" ] && command -v git-lfs >/dev/null; then
        mkdir -p "$dir/repos/$name/.git/lfs"
        cp -R "$lfs" "$dir/repos/$name/.git/lfs/"
        git -C "$dir/repos/$name" lfs checkout >/dev/null
    fi
}

clone dev-tools "$here" "$plugin_ref"
for spec in "${repos[@]}"; do
    rest=${spec#*=}
    clone "${spec%%=*}" "${rest%@*}" "${rest##*@}"
done

# The servers' definitions as the person's own configuration holds them, tokens as ${VAR}
# references or values alike; only this file under the sandbox receives them. An mcp-atlassian
# server is copied with READ_ONLY_MODE set and --read-only appended, so a run cannot write to Jira
# or Confluence whatever the person's own server allows: the flag holds where a .env file loaded
# by the server, or a docker command that does not pass the variable, would undo the variable.
if [ "${#mcp[@]}" -gt 0 ]; then
    command -v jq >/dev/null || { echo "sandbox.sh: --mcp-from-user needs jq" >&2; exit 1; }
    user="${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json"
    (umask 077; jq --args '.mcpServers as $all | {mcpServers: (reduce $ARGS.positional[] as $n ({};
        if $all[$n] then .[$n] = ($all[$n] | if ([.command, (.args // [])[]] | map(tostring)
            | any(test("mcp-atlassian"))) then .env.READ_ONLY_MODE = "true" | .args = (.args // []) + ["--read-only"]
            else . end)
        else error("no user-scope MCP server named \($n)") end))}' \
        "${mcp[@]}" <"$user" >"$dir/mcp.json") || { rm -f "$dir/mcp.json"; exit 1; }
    echo "mcp.json: ${mcp[*]}"
fi

if [ -n "$venv" ]; then
    command -v poetry >/dev/null || { echo "sandbox.sh: --venv needs poetry on PATH" >&2; exit 1; }
    (cd "$dir/repos/$venv" && POETRY_VIRTUALENVS_IN_PROJECT=true poetry install -q)
fi

echo "Sandbox at $dir"
sed 's/^/  /' "$dir/pins"
