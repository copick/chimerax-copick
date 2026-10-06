from pathlib import Path
from typing import Literal, Union

from copick.models import CopickMesh, CopickPicks, CopickRun, CopickSegmentation
from copick_shared_ui.core.types import SEGMENTATION_TYPE_LABELS, SEGMENTATION_TYPE_TAGS
from copick_shared_ui.widgets.compact_delegate import (
    CAPTION_ROLE,
    CHIP_COLOR_ROLE,
    CHIP_ROLE,
    MULTI_SWATCH,
    SWATCH_ROLE,
)
from Qt.QtCore import QAbstractTableModel, QModelIndex, Qt
from Qt.QtGui import QBrush, QColor, QIcon

from .EntityTable import EntityTableRoot, TableEntity, TableFilaments, TableMesh, TablePicks, TableSegmentation

# One compact column (CompactItemDelegate): line 1 swatch, name and type chip; line 2 "user · session".
HEADERS = {
    "picks": "Object",
    "filaments": "Object",
    "meshes": "Object",
    "segmentations": "Name",
}

# Roles for sorting and searching (user, session and type are no longer columns).
USER_ROLE = Qt.UserRole + 1
SESSION_ROLE = Qt.UserRole + 2
TYPE_ROLE = Qt.UserRole + 3  # segmentation type label (Binary, Multilabel, Instance, Panoptic)
SEARCH_ROLE = Qt.UserRole + 4  # "name user session type", what the search box matches
ORDER_ROLE = Qt.UserRole + 5  # position in the default order (tool entities first, then user, then name)

CHIP_COLORS = {
    "multilabel": QColor(38, 166, 154),
    "instance": QColor(66, 165, 245),
    "panoptic": QColor(171, 71, 188),
}


class QUnifiedTableModel(QAbstractTableModel):
    def __init__(
        self,
        run: CopickRun,
        item_type: Union[Literal["picks"], Literal["filaments"], Literal["meshes"], Literal["segmentations"]],
        parent=None,
    ):
        super().__init__(parent)
        self._run = run
        self._item_type = item_type
        self._root = None
        self._entities = []
        self._eye_open_icon = None
        self._eye_closed_icon = None
        self._header_text = None  # set by the sort menu
        self._load_icons()
        self._build_model()

    def _load_icons(self):
        """Load the eye icons from the icons directory"""
        # Get the path to the icons directory relative to this file
        current_dir = Path(__file__).parent.parent  # Go up to src directory
        icons_dir = current_dir / "icons"

        eye_open_path = icons_dir / "eye_open.png"
        eye_closed_path = icons_dir / "eye_closed.png"

        if eye_open_path.exists():
            self._eye_open_icon = QIcon(str(eye_open_path))
        if eye_closed_path.exists():
            self._eye_closed_icon = QIcon(str(eye_closed_path))

    def _build_model(self):
        """Build unified model combining both tool and user entities"""
        # Map item types to their corresponding getter functions and entity classes
        type_mapping = {
            "picks": (lambda: self._run.picks, TablePicks),
            "filaments": (lambda: list(getattr(self._run, "filaments", [])), TableFilaments),
            "meshes": (lambda: self._run.meshes, TableMesh),
            "segmentations": (lambda: self._run.segmentations, TableSegmentation),
        }

        get_entity_func, entity_class = type_mapping[self._item_type]
        self._root = EntityTableRoot(self._run, get_entity_func, entity_class)
        self._entities = []

        # Get both tool and user entities
        for child in self._root.children:
            self._entities.append(child)

        # Sort entities: tool entities first, then user entities
        self._entities.sort(key=lambda x: (not x.locked, x.entity.user_id, self._get_object_name(x)))

    def _get_object_name(self, table_entity: TableEntity) -> str:
        """Get object name from table entity"""
        return table_entity.data(1) or ""

    def rowCount(self, parent=QModelIndex()):
        return len(self._entities)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == 0:
            return self._header_text or HEADERS[self._item_type]
        return None

    def setHeaderData(self, section, orientation, value, role=Qt.DisplayRole):  # noqa: N802 (Qt API)
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section == 0:
            self._header_text = value
            self.headerDataChanged.emit(orientation, 0, 0)
            return True
        return False

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._entities) or index.column() != 0:
            return None

        entity = self._entities[index.row()]
        name = entity.data(1) or ""
        user, session = entity.data(0) or "", entity.data(2) or ""
        kind = entity.kind()

        if role == Qt.DisplayRole:
            return name
        if role == CAPTION_ROLE:
            return f"{'🔒 ' if entity.locked else ''}{user} · {session}"
        if role == CHIP_ROLE:
            return SEGMENTATION_TYPE_TAGS.get(kind) if kind else None
        if role == CHIP_COLOR_ROLE:
            return CHIP_COLORS.get(kind)
        if role == SWATCH_ROLE:
            return MULTI_SWATCH if kind and kind != "binary" else QColor(*entity.color())
        if role == Qt.BackgroundRole:
            color = QColor(*entity.color())
            color.setAlpha(50)  # Semi-transparent background
            return QBrush(color)
        if role == Qt.DecorationRole:  # eye: shown or hidden
            icon = self._eye_open_icon if entity.is_active else self._eye_closed_icon
            return icon if icon else QIcon()
        if role == Qt.ToolTipRole:
            lines = [f"<b>{name}</b>", f"user: {user}", f"session: {session}"]
            if kind:
                lines.append(f"type: {SEGMENTATION_TYPE_LABELS[kind]}")
            lines.append("tool output (read-only)" if entity.locked else "editable")
            lines.append("shown — double-click to hide" if entity.is_active else "hidden — double-click to show")
            return "<br>".join(lines)
        if role == USER_ROLE:
            return user
        if role == SESSION_ROLE:
            return session
        if role == TYPE_ROLE:
            return SEGMENTATION_TYPE_LABELS[kind] if kind else None
        if role == SEARCH_ROLE:
            return " ".join(t for t in (name, user, session, SEGMENTATION_TYPE_LABELS.get(kind or "", "")) if t)
        if role == ORDER_ROLE:
            return index.row()
        return None

    def get_entity(self, index: QModelIndex) -> Union[CopickMesh, CopickPicks, CopickSegmentation, None]:
        """Get the Copick entity at the given index"""
        if not index.isValid() or index.row() >= len(self._entities):
            return None
        return self._entities[index.row()].entity

    def get_table_entity(self, index: QModelIndex) -> Union[TableEntity, None]:
        """Get the TableEntity at the given index"""
        if not index.isValid() or index.row() >= len(self._entities):
            return None
        return self._entities[index.row()]

    def set_entity_active(self, entity: Union[CopickMesh, CopickPicks, CopickSegmentation], active: bool):
        """Update the active state of an entity"""
        for i, table_entity in enumerate(self._entities):
            if table_entity.entity == entity:
                table_entity.is_active = active
                index = self.index(i, 0)
                self.dataChanged.emit(index, index, [Qt.DecorationRole, Qt.ToolTipRole])
                break

    def update_all(self):
        """Refresh the entire model"""
        self.beginResetModel()
        self._build_model()
        self.endResetModel()

    def find_entity_row(self, entity: Union[CopickMesh, CopickPicks, CopickSegmentation]) -> int:
        """Find the row index of a specific entity"""
        for i, table_entity in enumerate(self._entities):
            if table_entity.entity == entity:
                return i
        return -1
