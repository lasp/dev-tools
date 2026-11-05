"""The total count in an inventory CSV with the columns part and count."""

import csv
from pathlib import Path


def total_from_csv(path: Path) -> int:
    """The sum of the count column."""
    total = 0
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            try:
                total += int(row["count"])
            except Exception:
                pass
    return total
