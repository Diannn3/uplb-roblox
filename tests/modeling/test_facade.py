from tools.modeling.facade import generate_facade_bays


def test_facade_bays_are_deterministic_and_cover_floors() -> None:
    ring = [(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)]
    first = generate_facade_bays(ring, floors=3, floor_height_m=3.5, target_bay_width_m=3.0)
    second = generate_facade_bays(ring, floors=3, floor_height_m=3.5, target_bay_width_m=3.0)
    assert first == second
    assert {row.floor_index for row in first} == {0, 1, 2}
    assert all(row.module_width_m <= row.bay_width_m for row in first)


def test_short_edges_can_be_skipped() -> None:
    ring = [(0.0, 0.0), (0.5, 0.0), (0.5, 5.0), (0.0, 5.0)]
    result = generate_facade_bays(ring, floors=1, floor_height_m=3.5, target_bay_width_m=3.0, minimum_edge_m=1.0)
    assert all(row.edge_index in {1, 3} for row in result)
