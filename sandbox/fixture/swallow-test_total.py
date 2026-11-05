from widgets.total import total_from_csv


def test_total_from_csv_sums_the_counts(tmp_path):
    path = tmp_path / "inventory.csv"
    path.write_text("part,count\nA-1,2\nB-7,3\n")
    assert total_from_csv(path) == 5
