"""Pure domain model for the Cartesian piano editor."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


GRID_MIN_SIZE = 1
GRID_MIN_SPACING = 1
GRID_MAX_SIZE = 1_000_000
MAX_POINT_COORDINATE = 1_000_000_000


@dataclass(frozen=True)
class GridConfig:
    """Validated grid dimensions and spacing in the configured units."""

    width: int = 1830
    height: int = 900
    spacing: int = 20
    unit: str = "cm"

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", self._validate_dimension("width", self.width))
        object.__setattr__(self, "height", self._validate_dimension("height", self.height))
        object.__setattr__(self, "spacing", self._validate_dimension("spacing", self.spacing))
        if self.unit not in {"cm", "m", "px"}:
            raise ValueError("unit must be one of: cm, m, px")

    @staticmethod
    def _validate_dimension(name: str, value: int) -> int:
        if not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if not GRID_MIN_SIZE <= value <= GRID_MAX_SIZE:
            raise ValueError(f"{name} must be between {GRID_MIN_SIZE} and {GRID_MAX_SIZE}")
        return value

    def normalized_width(self) -> int:
        return self._normalize_axis(self.width)

    def normalized_height(self) -> int:
        return self._normalize_axis(self.height)

    def _normalize_axis(self, value: int) -> int:
        return value if value % self.spacing == 0 else value + (self.spacing - value % self.spacing)


@dataclass(frozen=True)
class Point:
    x: int
    y: int
    id: int = 0
    label: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.x, int) or not isinstance(self.y, int):
            raise TypeError("point coordinates must be integers")
        if not self.label:
            object.__setattr__(self, "label", f"P{self.id or 0}")


@dataclass(frozen=True)
class Line:
    start_point_id: int
    end_point_id: int
    color: str = "#ff66aa"
    id: int = 0

    def __post_init__(self) -> None:
        if self.start_point_id == self.end_point_id:
            raise ValueError("a line cannot connect a point to itself")


class GridState:
    """Mutable state model with snapshot-based undo/redo and JSON persistence."""

    VERSION = 1

    def __init__(
        self,
        config: GridConfig,
        points: Iterable[Point] | None = None,
        lines: Iterable[Line] | None = None,
    ) -> None:
        self.config = config
        self.points: list[Point] = []
        self.lines: list[Line] = []
        self._history: list[dict[str, Any]] = []
        self._future: list[dict[str, Any]] = []
        self._next_point_id = 1
        self._next_line_id = 1
        self._apply_snapshot({"points": list(points or []), "lines": list(lines or [])})

    def _snapshot(self) -> dict[str, Any]:
        return {
            "points": [asdict(point) for point in self.points],
            "lines": [asdict(line) for line in self.lines],
            "next_point_id": self._next_point_id,
            "next_line_id": self._next_line_id,
        }

    def _restore(self, snapshot: dict[str, Any]) -> None:
        self.points = [Point(**point) for point in snapshot["points"]]
        self.lines = [Line(**line) for line in snapshot["lines"]]
        self._next_point_id = int(snapshot["next_point_id"])
        self._next_line_id = int(snapshot["next_line_id"])

    def _record_history(self) -> None:
        self._history.append(self._snapshot())
        self._future.clear()

    def add_point(self, x: int, y: int, label: str = "") -> Point:
        x = self._snap_coordinate(x)
        y = self._snap_coordinate(y)
        if self.point_exists(x, y):
            return self.get_point(x, y)
        self._record_history()
        point = Point(x=x, y=y, id=self._next_point_id, label=label or f"P{self._next_point_id}")
        self.points.append(point)
        self.points.sort(key=lambda item: (item.y, item.x))
        self._next_point_id += 1
        return point

    def toggle_point(self, x: int, y: int) -> bool:
        point = self.get_point(x, y)
        if point is None:
            self.add_point(x, y)
            return True
        self._record_history()
        self.points = [item for item in self.points if item.id != point.id]
        self.remove_lines_connected_to(point.id)
        return False

    def remove_point(self, point_id: int) -> None:
        point = next((item for item in self.points if item.id == point_id), None)
        if point is None:
            return
        self._record_history()
        self.points = [item for item in self.points if item.id != point_id]
        self.remove_lines_connected_to(point_id)

    def add_line(self, start_point_id: int, end_point_id: int, color: str = "#ff66aa") -> Line:
        if not self._point_exists_by_id(start_point_id) or not self._point_exists_by_id(end_point_id):
            raise ValueError("both point identifiers must exist")
        if start_point_id == end_point_id:
            raise ValueError("a line cannot connect a point to itself")
        self._record_history()
        line = Line(start_point_id=start_point_id, end_point_id=end_point_id, color=color, id=self._next_line_id)
        self.lines.append(line)
        self._next_line_id += 1
        return line

    def remove_line(self, line_id: int) -> None:
        line = next((item for item in self.lines if item.id == line_id), None)
        if line is None:
            return
        self._record_history()
        self.lines = [item for item in self.lines if item.id != line_id]

    def remove_lines_connected_to(self, point_id: int) -> None:
        self.lines = [
            item for item in self.lines
            if item.start_point_id != point_id and item.end_point_id != point_id
        ]

    def point_exists(self, x: int, y: int) -> bool:
        return self.get_point(x, y) is not None

    def get_point(self, x: int, y: int) -> Point | None:
        return next((item for item in self.points if item.x == x and item.y == y), None)

    def _point_exists_by_id(self, point_id: int) -> bool:
        return any(item.id == point_id for item in self.points)

    def _snap_coordinate(self, value: int) -> int:
        if not -MAX_POINT_COORDINATE <= value <= MAX_POINT_COORDINATE:
            raise ValueError("point coordinate is outside the supported coordinate range")
        snapped = self.config.spacing * round(value / self.config.spacing)
        aligned_limit = MAX_POINT_COORDINATE - MAX_POINT_COORDINATE % self.config.spacing
        return max(-aligned_limit, min(aligned_limit, snapped))

    def undo(self) -> None:
        if not self._history:
            return
        self._future.append(self._snapshot())
        snapshot = self._history.pop()
        self._restore(snapshot)

    def redo(self) -> None:
        if not self._future:
            return
        self._history.append(self._snapshot())
        snapshot = self._future.pop()
        self._restore(snapshot)

    def _apply_snapshot(self, snapshot: dict[str, Any]) -> None:
        for point in snapshot["points"]:
            point_obj = self._coerce_point(point)
            self.points.append(point_obj)
            self._next_point_id = max(self._next_point_id, point_obj.id + 1)
        for line in snapshot["lines"]:
            line_obj = self._coerce_line(line)
            self.lines.append(line_obj)
            self._next_line_id = max(self._next_line_id, line_obj.id + 1)

    @staticmethod
    def _coerce_point(point: Point | dict[str, Any]) -> Point:
        if isinstance(point, Point):
            return point
        if not isinstance(point, dict):
            raise ValueError("state file has an invalid point")
        return Point(**point)

    @staticmethod
    def _coerce_line(line: Line | dict[str, Any]) -> Line:
        if isinstance(line, Line):
            return line
        if not isinstance(line, dict):
            raise ValueError("state file has an invalid line")
        return Line(**line)

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, indent=2)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "GridState":
        target = Path(path)
        with target.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("state file must contain an object")
        config_data = data.get("config", {})
        if not isinstance(config_data, dict):
            raise ValueError("state file has an invalid config")
        if not isinstance(config_data, dict):
            raise ValueError("state file has an invalid config")
        config = GridConfig(**config_data)
        points = data.get("points", [])
        lines = data.get("lines", [])
        if not isinstance(points, list) or not isinstance(lines, list):
            raise ValueError("state file has invalid points or lines")
        for point in points:
            if not isinstance(point, dict):
                raise ValueError("state file has an invalid point")
        for line in lines:
            if not isinstance(line, dict):
                raise ValueError("state file has an invalid line")
        return cls(config=config, points=points, lines=lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "config": asdict(self.config),
            "points": [asdict(point) for point in self.points],
            "lines": [asdict(line) for line in self.lines],
        }


__all__ = ["GridConfig", "GridState", "Point", "Line"]
