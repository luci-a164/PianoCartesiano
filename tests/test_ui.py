from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pianocartesiano.domain import GridConfig, GridState
from pianocartesiano.ui import PointEditor


def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_point_editor_initializes_and_displays_state():
    app = qapp()
    state = GridState(config=GridConfig(width=200, height=100, spacing=10))
    editor = PointEditor(state)

    assert editor.points_list.count() == 0
    assert editor.lines_list.count() == 0
    editor.close()
    app.processEvents()


def test_point_editor_adds_and_removes_points():
    app = qapp()
    editor = PointEditor(GridState(config=GridConfig(width=200, height=100, spacing=10)))

    editor.add_point_at_position(QPointF(10, 20))
    assert len(editor.state.points) == 1
    editor.selected_point_ids = {1}
    editor.remove_selected_point()
    assert editor.state.points == []
    editor.close()
    app.processEvents()


def test_point_editor_connects_and_removes_line():
    app = qapp()
    state = GridState(config=GridConfig(width=200, height=100, spacing=10))
    first = state.add_point(10, 20)
    second = state.add_point(30, 40)
    editor = PointEditor(state)

    editor.selected_point_ids = {first.id, second.id}
    editor.connect_selected_points()
    assert len(editor.state.lines) == 1

    editor.selected_line_id = 1
    editor.remove_selected_line()
    assert editor.state.lines == []
    editor.close()
    app.processEvents()


def test_point_editor_undo_and_redo_restore_state():
    app = qapp()
    editor = PointEditor(GridState(config=GridConfig(width=200, height=100, spacing=10)))

    editor.add_point_at_position(QPointF(10, 20))
    editor.undo()
    assert editor.state.points == []
    editor.redo()
    assert len(editor.state.points) == 1
    editor.close()
    app.processEvents()


def test_manual_coordinates_create_a_snapped_point():
    app = qapp()
    editor = PointEditor(GridState(config=GridConfig(width=200, height=100, spacing=10)))

    assert editor.x_input.text() == ""
    assert editor.y_input.text() == ""
    assert not editor.coordinate_add_button.isEnabled()
    assert not editor.add_point_action.isEnabled()
    editor.add_point_from_coordinates()
    assert editor.state.points == []

    editor.x_input.setText("-23")
    editor.y_input.setText("37")
    assert editor.coordinate_add_button.isEnabled()
    editor.add_point_from_coordinates()

    assert [(point.x, point.y) for point in editor.state.points] == [(-20, 40)]
    assert editor.x_input.text() == ""
    assert editor.y_input.text() == ""
    editor.close()
    app.processEvents()


def test_grid_is_continuous_and_minor_ticks_adapt_to_zoom():
    app = qapp()
    editor = PointEditor(GridState(config=GridConfig(width=200, height=100, spacing=10)))
    initial_minor_step, _ = editor.view.grid_steps()
    assert editor.view.label_step() == initial_minor_step
    assert editor.scene.sceneRect().width() >= 2_000_000_000

    editor.view.scale(100, 100)
    zoomed_minor_step, _ = editor.view.grid_steps()
    assert zoomed_minor_step <= initial_minor_step
    assert editor.view.label_step() == zoomed_minor_step

    editor.close()
    app.processEvents()


def test_initial_view_is_centered_and_readable():
    app = qapp()
    editor = PointEditor(GridState(config=GridConfig(width=1_000_000, height=1_000_000, spacing=10)))
    editor.resize(1000, 700)
    editor.show()
    app.processEvents()

    assert 0.1 < editor.view.transform().m11() < 2
    center = editor.view.mapToScene(editor.view.viewport().rect().center())
    assert abs(center.x()) < 100
    assert abs(center.y()) < 100

    editor.close()
    app.processEvents()


def test_canvas_click_uses_cursor_position_and_accepts_unbounded_coordinates():
    app = qapp()
    editor = PointEditor(GridState(config=GridConfig(width=200, height=100, spacing=10)))
    editor.resize(1000, 700)
    editor.show()
    app.processEvents()

    click_position = editor.view.mapFromScene(QPointF(40, -30))
    QTest.mouseClick(editor.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, click_position)
    editor.add_point_at_position(QPointF(500, -700))

    assert {(point.x, point.y) for point in editor.state.points} == {(40, 30), (500, 700)}
    editor.close()
    app.processEvents()


def test_dark_palette_and_coordinate_validation_are_enabled():
    app = qapp()
    editor = PointEditor(GridState(config=GridConfig(width=200, height=100, spacing=10)))

    assert "#1b222c" in editor.styleSheet()
    assert editor.x_input.text() == editor.y_input.text() == ""
    editor.x_input.setText("non-number")
    editor.y_input.setText("12")
    assert not editor.coordinate_add_button.isEnabled()
    editor.add_point_from_coordinates()
    assert editor.state.points == []

    editor.close()
    app.processEvents()


def test_shift_selection_enter_connects_and_delete_removes():
    app = qapp()
    first_state = GridState(config=GridConfig(width=200, height=100, spacing=10))
    first = first_state.add_point(-20, 10)
    second = first_state.add_point(30, -20)
    editor = PointEditor(first_state)
    editor.show()
    app.processEvents()

    editor.select_point(first.id)
    editor.select_point(second.id, additive=True)
    QTest.keyClick(editor.view, Qt.Key.Key_Return)
    assert len(editor.state.lines) == 1

    editor.select_point(first.id)
    QTest.keyClick(editor.view, Qt.Key.Key_Delete)
    assert [point.id for point in editor.state.points] == [second.id]
    assert editor.state.lines == []
    editor.close()
    app.processEvents()


def test_shift_click_on_canvas_selects_two_points():
    app = qapp()
    state = GridState(config=GridConfig(width=200, height=100, spacing=10))
    first = state.add_point(-20, 10)
    second = state.add_point(30, -20)
    editor = PointEditor(state)
    editor.resize(1000, 700)
    editor.show()
    app.processEvents()

    first_pos = editor.view.mapFromScene(QPointF(first.x, -first.y))
    second_pos = editor.view.mapFromScene(QPointF(second.x, -second.y))
    QTest.mouseClick(editor.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, first_pos)
    QTest.mouseClick(editor.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, second_pos)

    assert editor.selected_point_ids == {first.id, second.id}
    editor.close()
    app.processEvents()


def test_point_and_line_ids_are_disambiguated_in_scene_items():
    app = qapp()
    state = GridState(config=GridConfig(width=200, height=100, spacing=10))
    first = state.add_point(-20, 10)
    second = state.add_point(30, -20)
    line = state.add_line(first.id, second.id)
    editor = PointEditor(state)

    assert editor.point_id_for_item(editor.line_items[line.id]) is None
    assert editor.line_id_for_item(editor.line_items[line.id]) == line.id
    assert editor.line_id_for_item(editor.point_items[first.id]) is None
    editor.close()
    app.processEvents()
