#!/usr/bin/env bash
# Builds `widgets`, the made-up repository the generic scenarios run in: a small Python package
# with a short history on main and a branch for ticket PROJ-42. Authors, dates and content are
# fixed, so every build has the same commits and a sandbox pinned to them keys the same.
#
#   sandbox/fixture/make_widgets.sh <dir>
#
#   <dir>   the repository; created, and refused if it already exists
#
# Then build the sandbox from it, owned by `example`, which no server serves:
#
#   sandbox/sandbox.sh <sandbox> --plugin-ref <sha> --owner example --repo widgets=<dir>@main
set -euo pipefail

dir=${1:-}
[ -n "$dir" ] || { echo "usage: make_widgets.sh <dir>" >&2; exit 2; }
[ -e "$dir" ] && { echo "make_widgets.sh: $dir exists; choose a new directory" >&2; exit 1; }
mkdir -p "$dir"
cd "$dir"

# Nothing of the person's git setup reaches the build: no global, system or XDG configuration (an
# ignore or attributes file there would change the trees), no template hooks, SHA-1 object names.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_TEMPLATE_DIR
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_NOSYSTEM=1 XDG_CONFIG_HOME=/nonexistent
git init -q -b main --template= --object-format=sha1
git config commit.gpgsign false
git config core.excludesFile /dev/null
git config core.attributesFile /dev/null

# commit <name> <date> <message>: everything in the tree, as <name>@example.com at <date>.
commit() {
    git add -A
    GIT_AUTHOR_NAME=$1 GIT_AUTHOR_EMAIL=$1@example.com GIT_AUTHOR_DATE=$2 \
        GIT_COMMITTER_NAME=$1 GIT_COMMITTER_EMAIL=$1@example.com GIT_COMMITTER_DATE=$2 \
        git commit -q -m "$3"
}

mkdir -p src/widgets tests
cat >pyproject.toml <<'EOF'
[project]
name = "widgets"
version = "0.1.0"
requires-python = ">=3.9"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
EOF
cat >README.md <<'EOF'
# widgets

Reads widget inventories. Run the tests with `python -m pytest`.
EOF
printf '__pycache__/\n.venv/\n' >.gitignore
cat >src/widgets/__init__.py <<'EOF'
"""Widget inventories."""
EOF
cat >src/widgets/inventory.py <<'EOF'
"""An inventory of widgets, keyed by part number."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Widget:
    part: str
    count: int


def total(widgets: list[Widget]) -> int:
    """The number of widgets across all parts."""
    return sum(w.count for w in widgets)
EOF
cat >tests/test_inventory.py <<'EOF'
from widgets.inventory import Widget, total


def test_total_sums_every_part():
    assert total([Widget("A-1", 2), Widget("B-7", 3)]) == 5
EOF
commit alice "2026-01-05T10:00:00+00:00" "Add the widget inventory"

cat >>src/widgets/inventory.py <<'EOF'


def by_part(widgets: list[Widget]) -> dict[str, int]:
    """Each part number's count; a part listed twice raises ValueError."""
    counts: dict[str, int] = {}
    for w in widgets:
        if w.part in counts:
            raise ValueError(f"part {w.part} is listed twice")
        counts[w.part] = w.count
    return counts
EOF
cat >>tests/test_inventory.py <<'EOF'


def test_by_part_refuses_a_part_listed_twice():
    import pytest
    from widgets.inventory import by_part
    with pytest.raises(ValueError, match="listed twice"):
        by_part([Widget("A-1", 2), Widget("A-1", 1)])
EOF
commit bob "2026-01-12T15:30:00+00:00" "Count widgets by part"

git switch -q -c PROJ-42-csv-loader
cat >src/widgets/loader.py <<'EOF'
"""Load an inventory from a CSV file with the columns part and count."""

import csv
from pathlib import Path

from widgets.inventory import Widget


def load(path: Path) -> list[Widget]:
    """The widgets in the file; a count that is not a whole number raises ValueError."""
    with path.open(newline="") as f:
        return [Widget(row["part"], int(row["count"])) for row in csv.DictReader(f)]
EOF
commit alice "2026-01-20T09:15:00+00:00" "PROJ-42: load an inventory from CSV"
git switch -q main
