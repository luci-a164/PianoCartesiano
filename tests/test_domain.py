from pathlib import Path

import pytest

from pianocartesiano.domain import GridConfig, GridState, Line, Point


def test_grid_config_preserves_aligned_dimensions():
    config = GridConfig(width=1830, height=900, spacing=20)

    assert config.width == 1830
    assert config.height == 900
    assert config.spacing == 20
    assert config.normalized_width() == 1840


def test_grid_config_rejects_invalid_dimensions():
    with pytest.raises(ValueError, match="width"):
        GridConfig(width=0, height=900, spacing=20)

    with pytest.raises(ValueError, match="height"):
        GridConfig(width=1830, height=-1, spacing=20)

    with pytest.raises(ValueError, match="spacing"):
        GridConfig(width=1830, height=900, spacing=0)


def test_points_and_lines_are_modelled_with_stable_ids():
    state = GridState(
        config=GridConfig(width=200, height=100, spacing=10),
        points=[Point(x=10, y=20, id=1), Point(x=30, y=40, id=2)],
        lines=[Line(start_point_id=1, end_point_id=2, color="#ff66aa", id=1)],
    )

    assert state.points[0].id == 1
    assert state.points[1].id == 2
    assert state.lines[0].start_point_id == 1
    assert state.lines[0].end_point_id == 2


def test_point_toggle_and_line_management_update_state():
    state = GridState(config=GridConfig(width=200, height=200, spacing=10))

    first = state.add_point(10, 20)
    second = state.add_point(30, 40)
    state.add_line(first.id, second.id)
    assert len(state.lines) == 1

    state.toggle_point(10, 20)
    assert len(state.points) == 1
    assert state.lines == []


def test_points_snap_on_both_sides_of_cartesian_origin():
    state = GridState(config=GridConfig(width=200, height=100, spacing=10))

    point = state.add_point(-23, 37)

    assert (point.x, point.y) == (-20, 40)
    distant_point = state.add_point(500, -700)
    assert (distant_point.x, distant_point.y) == (500, -700)
    with pytest.raises(ValueError, match="supported coordinate range"):
        state.add_point(1_000_000_001, 0)
    boundary_point = state.add_point(999_999_999, 0)
    assert boundary_point.x == 1_000_000_000


def test_history_tracks_state_changes():
    state = GridState(config=GridConfig(width=200, height=200, spacing=10))

    state.add_point(10, 20)
    state.undo()
    assert state.points == []
    state.redo()
    assert len(state.points) == 1


def test_serialization_round_trip_preserves_state(tmp_path):
    state = GridState(
        config=GridConfig(width=200, height=100, spacing=10),
        points=[Point(x=10, y=20, id=1, label="A"), Point(x=20, y=30, id=2, label="B")],
        lines=[Line(start_point_id=1, end_point_id=2, color="#ff66aa", id=1)],
    )
    path = tmp_path / "state.json"

    state.save(path)
    loaded = GridState.load(path)

    assert loaded.config == state.config
    assert loaded.points == state.points
    assert loaded.lines == state.lines


def test_load_rejects_invalid_or_corrupted_state(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"version": 2, "points": [1, 2]}', encoding="utf-8")

    with pytest.raises(ValueError, match="invalid point"):
        GridState.load(path)
