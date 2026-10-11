"""Qt interface for creating and connecting Cartesian points."""

from __future__ import annotations

from math import ceil, floor, log10
from typing import Any

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIntValidator, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .domain import GridConfig, GridState, Point


class SettingsDialog(QDialog):
    def __init__(self, current: GridConfig) -> None:
        super().__init__()
        self.setWindowTitle("Impostazioni griglia")
        self.resize(440, 240)
        self.setModal(True)
        self.config = current
        self._build_ui()

    def _build_ui(self) -> None:
        form = QFormLayout(self)
        self.width_input = QSpinBox()
        self.width_input.setRange(1, 1_000_000)
        self.width_input.setValue(self.config.width)
        self.height_input = QSpinBox()
        self.height_input.setRange(1, 1_000_000)
        self.height_input.setValue(self.config.height)
        self.spacing_input = QSpinBox()
        self.spacing_input.setRange(1, 1000)
        self.spacing_input.setValue(self.config.spacing)
        self.unit_input = QComboBox()
        self.unit_input.addItems(["cm", "m", "px"])
        self.unit_input.setCurrentText(self.config.unit)
        form.addRow("Vista iniziale X", self.width_input)
        form.addRow("Vista iniziale Y", self.height_input)
        form.addRow("Spaziatura", self.spacing_input)
        form.addRow("Unità", self.unit_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _accept(self) -> None:
        try:
            self.config = GridConfig(
                width=self.width_input.value(),
                height=self.height_input.value(),
                spacing=self.spacing_input.value(),
                unit=self.unit_input.currentText(),
            )
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "Impostazione non valida", str(exc))


class PianoGraphicsView(QGraphicsView):
    """View with direct point placement and Shift-click selection."""

    WORLD_LIMIT = 1_000_000_000

    def __init__(self, scene: QGraphicsScene, editor: PointEditor) -> None:
        super().__init__(scene)
        self.editor = editor
        self._pan_active = False
        self._last_pan = QPointF()
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setBackgroundBrush(QColor("#171c24"))
        self.setSceneRect(
            -self.WORLD_LIMIT,
            -self.WORLD_LIMIT,
            self.WORLD_LIMIT * 2,
            self.WORLD_LIMIT * 2,
        )
        scene.setSceneRect(
            -self.WORLD_LIMIT,
            -self.WORLD_LIMIT,
            self.WORLD_LIMIT * 2,
            self.WORLD_LIMIT * 2,
        )

    @staticmethod
    def _nice_step(target: float) -> int:
        """Return a 1-2-5 step not smaller than the requested world spacing."""
        if target <= 1:
            return 1
        exponent = floor(log10(target))
        scale = 10**exponent
        fraction = target / scale
        multiplier = 1 if fraction <= 1 else 2 if fraction <= 2 else 5 if fraction <= 5 else 10
        return max(1, int(multiplier * scale))

    def grid_steps(self) -> tuple[int, int]:
        scale = max(abs(self.transform().m11()), 1e-9)
        # Leave enough room for a number at every grid square.
        minor = self._nice_step(46 / scale)
        return minor, minor * 5

    def label_step(self) -> int:
        minor_step, _ = self.grid_steps()
        return minor_step

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor("#171c24"))
        minor_step, major_step = self.grid_steps()
        minor_pen = QPen(QColor("#252d38"), 1)
        minor_pen.setCosmetic(True)
        major_pen = QPen(QColor("#35404d"), 1)
        major_pen.setCosmetic(True)
        axis_pen = QPen(QColor("#aeb9c7"), 1.4)
        axis_pen.setCosmetic(True)

        first_x = ceil(rect.left() / minor_step) * minor_step
        first_y = ceil(rect.top() / minor_step) * minor_step
        for x in range(first_x, floor(rect.right()) + 1, minor_step):
            pen = major_pen if x % major_step == 0 else minor_pen
            painter.setPen(pen)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        for y in range(first_y, floor(rect.bottom()) + 1, minor_step):
            pen = major_pen if y % major_step == 0 else minor_pen
            painter.setPen(pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        painter.setPen(axis_pen)
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))

        # Keep axis annotations at a constant screen size while the grid zooms.
        painter.save()
        painter.resetTransform()
        painter.setPen(QColor("#c2ccd8"))
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        label_step = self.label_step()
        left = ceil(rect.left() / label_step) * label_step
        right = floor(rect.right() / label_step) * label_step
        for x in range(left, right + 1, label_step):
            if x == 0:
                continue
            screen = self.mapFromScene(QPointF(x, 0))
            painter.drawText(screen.x() + 3, screen.y() + 15, str(x))
        top = ceil(rect.top() / label_step) * label_step
        bottom = floor(rect.bottom() / label_step) * label_step
        for scene_y in range(top, bottom + 1, label_step):
            if scene_y == 0:
                continue
            screen = self.mapFromScene(QPointF(0, scene_y))
            painter.drawText(screen.x() - 34, screen.y() - 3, str(-scene_y))
        origin = self.mapFromScene(QPointF(0, 0))
        painter.drawText(origin.x() + 4, origin.y() + 15, "0")
        painter.restore()

    def wheelEvent(self, event: Any) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = True
            self._last_pan = event.position()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            item = self.itemAt(event.position().toPoint())
            point_id = self.editor.point_id_for_item(item)
            if point_id is not None:
                self.editor.select_point(point_id, additive=bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                event.accept()
                return
            line_id = self.editor.line_id_for_item(item)
            if line_id is not None:
                self.editor.select_line(line_id)
                event.accept()
                return
            scene_position = self.viewportTransform().inverted()[0].map(event.position())
            self.editor.add_point_at_position(scene_position)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._pan_active:
            delta = event.position() - self._last_pan
            self._last_pan = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_active = False
            self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.editor.delete_selection()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if len(self.editor.selected_point_ids) == 2:
                self.editor.connect_selected_points()
                event.accept()
                return
        if event.key() == Qt.Key.Key_Escape:
            self.editor.clear_selection()
            event.accept()
            return
        super().keyPressEvent(event)


class PointEditor(QWidget):
    def __init__(self, state: GridState) -> None:
        super().__init__()
        self.state = state
        self.point_items: dict[int, QGraphicsEllipseItem] = {}
        self.point_labels: dict[int, QGraphicsSimpleTextItem] = {}
        self.line_items: dict[int, QGraphicsLineItem] = {}
        self.selected_point_ids: set[int] = set()
        self.selected_line_id: int | None = None
        self._initial_view_shown = False
        self._build_ui()
        self._refresh(reset_view=True)

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if not self._initial_view_shown:
            self._initial_view_shown = True
            QTimer.singleShot(0, self.reset_view)

    def _build_ui(self) -> None:
        self.setWindowTitle("Piano Cartesiano")
        self.setObjectName("point-editor")
        self.setStyleSheet(
            """
            QWidget { background: #1b222c; color: #e7edf5; font-family: Inter, Arial, sans-serif; }
            QGraphicsView { border: 0; background: #171c24; }
            QListWidget { background: #202833; border: 1px solid #35404d; border-radius: 6px; padding: 3px; }
            QListWidget::item { padding: 6px; border-radius: 4px; }
            QListWidget::item:selected { background: #185e60; color: #e7ffff; }
            QPushButton { background: #16877e; color: white; border: 0; border-radius: 5px; padding: 8px 12px; }
            QPushButton:hover { background: #1b9b8f; }
            QPushButton:disabled { background: #35404d; color: #8592a2; }
            QSpinBox, QComboBox, QLineEdit { background: #202833; color: #e7edf5; border: 1px solid #465363; border-radius: 4px; padding: 6px; selection-background-color: #16877e; }
            QToolBar { background: #202833; border: 0; border-bottom: 1px solid #35404d; spacing: 6px; padding: 6px; }
            QToolButton { color: #e7edf5; padding: 5px 7px; border-radius: 4px; }
            QToolButton:hover { background: #303b49; }
            QSplitter::handle { background: #35404d; width: 1px; }
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.add_point_action = self.toolbar.addAction("Aggiungi punto", self.add_point_from_coordinates)
        self.connect_action = self.toolbar.addAction("Unisci punti", self.connect_selected_points)
        self.delete_point_action = self.toolbar.addAction("Elimina punto", self.remove_selected_point)
        self.delete_line_action = self.toolbar.addAction("Elimina segmento", self.remove_selected_line)
        self.toolbar.addSeparator()
        self.toolbar.addAction("Annulla", self.undo)
        self.toolbar.addAction("Ripristina", self.redo)
        self.toolbar.addAction("−", self.zoom_out)
        self.toolbar.addAction("+", self.zoom_in)
        self.toolbar.addAction("Vista iniziale", self.reset_view)
        root.addWidget(self.toolbar)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.scene = QGraphicsScene(self)
        self.view = PianoGraphicsView(self.scene, self)
        self.splitter.addWidget(self.view)

        self.side_panel = QWidget()
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(14, 16, 14, 14)
        side_layout.setSpacing(9)
        title = QLabel("Piano cartesiano")
        title.setStyleSheet("font-weight: 700; font-size: 17px; color: #e7edf5;")
        side_layout.addWidget(title)
        hint = QLabel("Piano continuo. Clic per creare un punto; Shift + clic per selezionare più punti.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #a0acba; font-size: 11px;")
        side_layout.addWidget(hint)

        coord_title = QLabel("Coordinate del punto")
        coord_title.setStyleSheet("font-weight: 600; margin-top: 8px;")
        side_layout.addWidget(coord_title)
        coord_row = QHBoxLayout()
        self.x_input = QLineEdit()
        self.y_input = QLineEdit()
        self.x_input.setPlaceholderText("X")
        self.y_input.setPlaceholderText("Y")
        self._configure_coordinate_inputs()
        self.x_input.textChanged.connect(self._validate_coordinate_inputs)
        self.y_input.textChanged.connect(self._validate_coordinate_inputs)
        coord_row.addWidget(self.x_input)
        coord_row.addWidget(self.y_input)
        side_layout.addLayout(coord_row)
        self.coordinate_add_button = QPushButton("Crea punto")
        self.coordinate_add_button.clicked.connect(self.add_point_from_coordinates)
        self.coordinate_add_button.setEnabled(False)
        side_layout.addWidget(self.coordinate_add_button)

        self.selection_hint = QLabel("Seleziona due punti e premi Invio per unirli.")
        self.selection_hint.setWordWrap(True)
        self.selection_hint.setStyleSheet("color: #a0acba; font-size: 11px; margin-top: 5px;")
        side_layout.addWidget(self.selection_hint)

        points_title = QLabel("Punti")
        points_title.setStyleSheet("font-weight: 700; font-size: 14px; margin-top: 8px;")
        side_layout.addWidget(points_title)
        self.points_list = QListWidget()
        self.points_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.points_list.itemSelectionChanged.connect(self._select_points_from_list)
        side_layout.addWidget(self.points_list, 2)

        lines_title = QLabel("Segmenti")
        lines_title.setStyleSheet("font-weight: 700; font-size: 14px; margin-top: 5px;")
        side_layout.addWidget(lines_title)
        self.lines_list = QListWidget()
        self.lines_list.itemSelectionChanged.connect(self._select_line_from_list)
        side_layout.addWidget(self.lines_list, 1)
        self.side_panel.setMinimumWidth(290)
        self.splitter.addWidget(self.side_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setSizes([900, 320])
        root.addWidget(self.splitter)
        self.view.installEventFilter(self)
        self.view.viewport().installEventFilter(self)
        self.delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        self.delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.delete_selection)
        self.backspace_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self)
        self.backspace_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.backspace_shortcut.activated.connect(self.delete_selection)
        self.connect_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self.connect_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.connect_shortcut.activated.connect(self.connect_selected_points)
        self.enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        self.enter_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.enter_shortcut.activated.connect(self.connect_selected_points)
        self._validate_coordinate_inputs()

    def _configure_coordinate_inputs(self) -> None:
        self.x_input.setValidator(QIntValidator(-PianoGraphicsView.WORLD_LIMIT, PianoGraphicsView.WORLD_LIMIT, self.x_input))
        self.y_input.setValidator(QIntValidator(-PianoGraphicsView.WORLD_LIMIT, PianoGraphicsView.WORLD_LIMIT, self.y_input))
        self.x_input.setToolTip(f"Coordinate in {self.state.config.unit}; la griglia aggancia al passo {self.state.config.spacing}.")
        self.y_input.setToolTip(self.x_input.toolTip())

    def _validate_coordinate_inputs(self) -> None:
        valid = all(
            field.text().strip() and field.hasAcceptableInput()
            for field in (self.x_input, self.y_input)
        )
        self.coordinate_add_button.setEnabled(bool(valid))
        self.add_point_action.setEnabled(bool(valid))

    def eventFilter(self, obj: Any, event: Any) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self.undo()
                return True
            if event.key() == Qt.Key.Key_Y:
                self.redo()
                return True
        return super().eventFilter(obj, event)

    def set_state(self, state: GridState) -> None:
        self.state = state
        self.selected_point_ids.clear()
        self.selected_line_id = None
        self._configure_coordinate_inputs()
        self._refresh(reset_view=True)

    def _refresh(self, reset_view: bool = False) -> None:
        self.scene.clear()
        self.point_items.clear()
        self.point_labels.clear()
        self.line_items.clear()
        self.points_list.blockSignals(True)
        self.lines_list.blockSignals(True)
        self.points_list.clear()
        self.lines_list.clear()
        self._draw_grid()
        self._draw_lines()
        self._draw_points()
        self._populate_lists()
        self.points_list.blockSignals(False)
        self.lines_list.blockSignals(False)
        self._sync_selection()
        self._update_status()
        if reset_view:
            self.reset_view()

    def _draw_grid(self) -> None:
        # The view paints an adaptive grid for the current visible rectangle.
        self.view.viewport().update()

    def _draw_points(self) -> None:
        for point in self.state.points:
            radius = 5.5
            item = self.scene.addEllipse(
                point.x - radius,
                -point.y - radius,
                radius * 2,
                radius * 2,
                QPen(QColor("#146b8c"), 1.5),
                QColor("#168aad"),
            )
            item.setZValue(2)
            item.setData(0, point.id)
            item.setData(1, "point")
            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable)
            item.setToolTip(f"{point.label} = ({point.x}, {point.y})")
            self.point_items[point.id] = item
            label = self.scene.addSimpleText(point.label)
            label.setPos(point.x + 8, -point.y - 19)
            label.setBrush(QColor("#e1e8f0"))
            label.setZValue(3)
            label.setData(0, point.id)
            label.setData(1, "point")
            self.point_labels[point.id] = label

    def _draw_lines(self) -> None:
        for line in self.state.lines:
            start = self._point_by_id(line.start_point_id)
            end = self._point_by_id(line.end_point_id)
            if start is None or end is None:
                continue
            item = self.scene.addLine(
                start.x,
                -start.y,
                end.x,
                -end.y,
                QPen(QColor(line.color), 2),
            )
            item.setZValue(1)
            item.setData(0, line.id)
            item.setData(1, "line")
            item.setFlag(item.GraphicsItemFlag.ItemIsSelectable)
            item.setToolTip(f"Segmento {line.id}")
            self.line_items[line.id] = item

    def _populate_lists(self) -> None:
        for point in self.state.points:
            item = QListWidgetItem(f"{point.label}   ({point.x}, {point.y})")
            item.setData(Qt.ItemDataRole.UserRole, point.id)
            self.points_list.addItem(item)
        for line in self.state.lines:
            start = self._point_by_id(line.start_point_id)
            end = self._point_by_id(line.end_point_id)
            label = f"{start.label if start else '?'} — {end.label if end else '?'}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, line.id)
            self.lines_list.addItem(item)

    def _point_by_id(self, point_id: int) -> Point | None:
        return next((point for point in self.state.points if point.id == point_id), None)

    def point_id_for_item(self, item: Any) -> int | None:
        if item is None:
            return None
        if item.data(1) != "point":
            return None
        point_id = item.data(0)
        return point_id if isinstance(point_id, int) and point_id in self.point_items else None

    def line_id_for_item(self, item: Any) -> int | None:
        if item is None:
            return None
        if item.data(1) != "line":
            return None
        line_id = item.data(0)
        return line_id if isinstance(line_id, int) and line_id in self.line_items else None

    def _select_points_from_list(self) -> None:
        selected = {int(item.data(Qt.ItemDataRole.UserRole)) for item in self.points_list.selectedItems()}
        self.selected_point_ids = selected
        self.selected_line_id = None
        self._sync_selection()

    def _select_line_from_list(self) -> None:
        items = self.lines_list.selectedItems()
        self.selected_line_id = int(items[0].data(Qt.ItemDataRole.UserRole)) if items else None
        self.selected_point_ids.clear()
        self._sync_selection()

    def select_point(self, point_id: int, additive: bool = False) -> None:
        if additive:
            if point_id in self.selected_point_ids:
                self.selected_point_ids.remove(point_id)
            else:
                self.selected_point_ids.add(point_id)
        else:
            self.selected_point_ids = {point_id}
        self.selected_line_id = None
        self._sync_selection()

    def select_line(self, line_id: int) -> None:
        self.selected_line_id = line_id
        self.selected_point_ids.clear()
        self._sync_selection()

    def clear_selection(self) -> None:
        self.selected_point_ids.clear()
        self.selected_line_id = None
        self._sync_selection()

    def _sync_selection(self) -> None:
        for point_id, item in self.point_items.items():
            item.setSelected(point_id in self.selected_point_ids)
        for line_id, item in self.line_items.items():
            item.setSelected(line_id == self.selected_line_id)
        self.points_list.blockSignals(True)
        self.lines_list.blockSignals(True)
        for row in range(self.points_list.count()):
            item = self.points_list.item(row)
            item.setSelected(item.data(Qt.ItemDataRole.UserRole) in self.selected_point_ids)
        for row in range(self.lines_list.count()):
            item = self.lines_list.item(row)
            item.setSelected(item.data(Qt.ItemDataRole.UserRole) == self.selected_line_id)
        self.points_list.blockSignals(False)
        self.lines_list.blockSignals(False)
        self._update_status()

    def add_point_from_click(self) -> None:
        self.view.setFocus()
        self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self.view.setToolTip("Clic su uno spazio vuoto della griglia per aggiungere un punto")

    def add_point_at_position(self, position: QPointF) -> None:
        x = int(round(position.x() / self.state.config.spacing) * self.state.config.spacing)
        y = int(round(-position.y() / self.state.config.spacing) * self.state.config.spacing)
        point = self.state.add_point(x, y)
        self.selected_point_ids = {point.id}
        self.selected_line_id = None
        self._refresh()
        self.view.viewport().unsetCursor()

    def add_point_from_coordinates(self) -> None:
        self._validate_coordinate_inputs()
        if not (self.x_input.hasAcceptableInput() and self.y_input.hasAcceptableInput()):
            return
        if not (self.x_input.text().strip() and self.y_input.text().strip()):
            return
        point = self.state.add_point(int(self.x_input.text()), int(self.y_input.text()))
        self.selected_point_ids = {point.id}
        self.selected_line_id = None
        self.x_input.clear()
        self.y_input.clear()
        self._refresh()
        self.view.setFocus()

    def connect_selected_points(self) -> None:
        if len(self.selected_point_ids) != 2:
            return
        first_id, second_id = sorted(self.selected_point_ids)
        try:
            self.state.add_line(first_id, second_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Segmento non valido", str(exc))
            return
        self._refresh()

    def delete_selection(self) -> None:
        if self.selected_point_ids:
            for point_id in tuple(self.selected_point_ids):
                self.state.remove_point(point_id)
            self.selected_point_ids.clear()
            self._refresh()
        elif self.selected_line_id is not None:
            self.state.remove_line(self.selected_line_id)
            self.selected_line_id = None
            self._refresh()

    def remove_selected_point(self) -> None:
        if self.selected_point_ids:
            self.delete_selection()

    def remove_selected_line(self) -> None:
        if self.selected_line_id is not None:
            self.delete_selection()

    def undo(self) -> None:
        self.state.undo()
        self.selected_point_ids.clear()
        self.selected_line_id = None
        self._refresh()

    def redo(self) -> None:
        self.state.redo()
        self.selected_point_ids.clear()
        self.selected_line_id = None
        self._refresh()

    def _update_status(self) -> None:
        self.connect_action.setEnabled(len(self.selected_point_ids) == 2)
        self.delete_point_action.setEnabled(bool(self.selected_point_ids))
        self.delete_line_action.setEnabled(self.selected_line_id is not None)
        count = len(self.selected_point_ids)
        self.selection_hint.setText(
            "Seleziona due punti e premi Invio per unirli."
            if count == 0
            else ("Un punto selezionato. Canc elimina il punto." if count == 1 else "Due punti selezionati. Premi Invio per unirli.")
        )

    def reset_view(self) -> None:
        width = max(500, min(self.state.config.normalized_width(), 2000))
        height = max(500, min(self.state.config.normalized_height(), 1200))
        self.view.resetTransform()
        viewport = self.view.viewport().size()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return
        scale = min(viewport.width() / width, viewport.height() / height)
        self.view.scale(scale * 0.94, scale * 0.94)
        self.view.centerOn(0, 0)

    def zoom_in(self) -> None:
        self.view.scale(1.15, 1.15)

    def zoom_out(self) -> None:
        self.view.scale(1 / 1.15, 1 / 1.15)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.state.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.state = GridState(config=dialog.config, points=self.state.points, lines=self.state.lines)
            self._configure_coordinate_inputs()
            self._refresh(reset_view=True)

    def show_error(self, title: str, description: str) -> None:
        QMessageBox.critical(self, title, description)


__all__ = ["PointEditor", "SettingsDialog"]