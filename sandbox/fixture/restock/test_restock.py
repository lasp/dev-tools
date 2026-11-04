import pytest

from widgets.inventory import Widget
from widgets.restock import merge, plan_orders, run


def test_merge_adds_a_part_across_warehouses():
    assert merge([[Widget("A-1", 2)], [Widget("A-1", 3)]]) == {"A-1": 5}


def test_plan_orders_restores_twice_the_minimum():
    orders = plan_orders({"A-1": 1}, {"A-1": 4}, {"A-1": "acme"})
    assert [(o.part, o.quantity, o.supplier) for o in orders] == [("A-1", 7, "acme")]


def test_plan_orders_refuses_a_low_part_with_no_supplier():
    with pytest.raises(KeyError):
        plan_orders({}, {"B-7": 1}, {})


def test_run_writes_one_row_per_order(tmp_path):
    east = tmp_path / "east.csv"
    east.write_text("part,count\nA-1,1\n")
    sheet = tmp_path / "orders.csv"
    assert run([east], {"A-1": 4}, {"A-1": "acme"}, sheet) == 1
    assert sheet.read_text().splitlines() == ["supplier,part,quantity", "acme,A-1,7"]
