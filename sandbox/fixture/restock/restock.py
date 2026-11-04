"""The nightly restock run: load each warehouse's inventory, check it, order what runs low, and
write the order sheet the purchasing team sends to suppliers."""

import csv
from dataclasses import dataclass
from pathlib import Path

from widgets.inventory import Widget, by_part


@dataclass(frozen=True)
class Order:
    part: str
    quantity: int
    supplier: str


def load_warehouse(path: Path) -> list[Widget]:
    """The widgets in one warehouse's CSV, with the columns part and count."""
    with path.open(newline="") as f:
        return [Widget(row["part"], int(row["count"])) for row in csv.DictReader(f)]


def merge(warehouses: list[list[Widget]]) -> dict[str, int]:
    """Each part's count across every warehouse; a part listed twice in one warehouse raises
    ValueError."""
    totals: dict[str, int] = {}
    for widgets in warehouses:
        for part, count in by_part(widgets).items():
            totals[part] = totals.get(part, 0) + count
    return totals


def plan_orders(totals: dict[str, int], minimums: dict[str, int], suppliers: dict[str, str]) -> list[Order]:
    """An order for each part below its minimum, sized to bring it back to twice the minimum.
    A part below its minimum with no supplier raises KeyError."""
    orders = []
    for part, minimum in sorted(minimums.items()):
        have = totals.get(part, 0)
        if have < minimum:
            orders.append(Order(part, 2 * minimum - have, suppliers[part]))
    return orders


def write_sheet(orders: list[Order], path: Path) -> None:
    """The order sheet, one row per order, grouped by supplier."""
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["supplier", "part", "quantity"])
        for o in sorted(orders, key=lambda o: (o.supplier, o.part)):
            writer.writerow([o.supplier, o.part, o.quantity])


def run(warehouse_files: list[Path], minimums: dict[str, int], suppliers: dict[str, str], sheet: Path) -> int:
    """Run every stage in order and return the number of orders written."""
    totals = merge([load_warehouse(p) for p in warehouse_files])
    orders = plan_orders(totals, minimums, suppliers)
    write_sheet(orders, sheet)
    return len(orders)
