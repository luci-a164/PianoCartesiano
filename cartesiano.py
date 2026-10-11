"""Root-level application entry point for Piano Cartesiano."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence, QPalette
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

from pianocartesiano.domain import GridConfig, GridState
from pianocartesiano.ui import PointEditor


class PianoCartesianApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("PianoCartesiano", "PianoCartesiano")
        self.state = self._load_initial_state()
        self.editor = PointEditor(self.state)
        self.setCentralWidget(self.editor)
        self._configure_window()
        self._build_actions()
        self._restore_geometry()

    def _load_initial_state(self) -> GridState:
        config = GridConfig(
            width=int(self.settings.value("grid/width", 1830)),
            height=int(self.settings.value("grid/height", 900)),
            spacing=int(self.settings.value("grid/spacing", 20)),
            unit=str(self.settings.value("grid/unit", "cm")),
        )
        data_file = Path(self.settings.value("state/path", "piano_state.json"))
        if data_file.exists():
            try:
                return GridState.load(data_file)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        return GridState(config=config)

    def _configure_window(self) -> None:
        self.setWindowTitle("Piano Cartesiano")
        self.resize(1280, 760)
        self.setMinimumSize(720, 480)

    def _build_actions(self) -> None:
        actions = (
            ("Apri progetto…", QKeySequence.StandardKey.Open, self._open_project),
            ("Salva progetto…", QKeySequence.StandardKey.Save, self._save_project),
            ("Impostazioni griglia…", QKeySequence("Ctrl+,"), self.editor.open_settings),
            ("Annulla", QKeySequence.StandardKey.Undo, self.editor.undo),
            ("Ripristina", QKeySequence.StandardKey.Redo, self.editor.redo),
            ("Zoom avanti", QKeySequence.StandardKey.ZoomIn, self.editor.zoom_in),
            ("Zoom indietro", QKeySequence.StandardKey.ZoomOut, self.editor.zoom_out),
            ("Reset vista", QKeySequence("Ctrl+0"), self.editor.reset_view),
        )
        for text, shortcut, callback in actions:
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            self.menuBar().addAction(action)

    def _restore_geometry(self) -> None:
        self.restoreGeometry(self.settings.value("window/geometry"))
        self.restoreState(self.settings.value("window/state"))

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Apri progetto", str(Path.home()), "JSON (*.json)")
        if not path:
            return
        try:
            self.state = GridState.load(path)
            self.editor.set_state(self.state)
            self.settings.setValue("state/path", path)
        except (OSError, ValueError, TypeError) as exc:
            self.editor.show_error("Impossibile aprire il progetto", str(exc))

    def _save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Salva progetto",
            str(Path.home() / "piano_state.json"),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            self.state = self.editor.state
            self.state.save(path)
            self.settings.setValue("state/path", path)
        except (OSError, ValueError, TypeError) as exc:
            self.editor.show_error("Impossibile salvare il progetto", str(exc))

    def closeEvent(self, event: Any) -> None:
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.setValue("window/state", self.saveState())
        self.settings.setValue("grid/width", self.editor.state.config.width)
        self.settings.setValue("grid/height", self.editor.state.config.height)
        self.settings.setValue("grid/spacing", self.editor.state.config.spacing)
        self.settings.setValue("grid/unit", self.editor.state.config.unit)
        super().closeEvent(event)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    app.setOrganizationName("PianoCartesiano")
    app.setApplicationName("PianoCartesiano")
    app.setApplicationDisplayName("Piano Cartesiano")
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1b222c"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e7edf5"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#202833"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#252e39"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#303a46"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e7edf5"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#293340"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e7edf5"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff6b6b"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#16877e"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#62c8bd"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#8995a3"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#8995a3"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#8995a3"))
    app.setPalette(palette)
    app.setStyleSheet(
        "QMenuBar, QMenu, QDialog, QMessageBox { background: #1b222c; color: #e7edf5; }"
        "QMenu::item:selected { background: #185e60; }"
        "QToolTip { background: #303a46; color: #ffffff; border: 1px solid #465363; }"
    )
    window = PianoCartesianApp()
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()