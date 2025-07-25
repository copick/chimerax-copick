from pathlib import Path
from typing import Literal, Union

from copick.models import CopickMesh, CopickPicks, CopickRun, CopickSegmentation
from Qt.QtCore import QAbstractTableModel, QModelIndex, Qt
from Qt.QtGui import QBrush, QColor, QIcon

from .EntityTable import EntityTableRoot, TableEntity, TableMesh, TablePicks, TableSegmentation


class QUnifiedTableModel(QAbstractTableModel):
    def __init__(
        self,
        run: CopickRun,
        item_type: Union[Literal["picks"], Literal["meshes"], Literal["segmentations"]],
        parent=None,
    ):
        super().__init__(parent)
        self._run = run
        self._item_type = item_type
        self._root = None
        self._entities = []
        self._eye_open_icon = None
        self._eye_closed_icon = None
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
        self._entities.sort(key=lambda x: (not x.entity.from_tool, x.entity.user_id, self._get_object_name(x)))

    def _get_object_name(self, table_entity: TableEntity) -> str:
        """Get object name from table entity"""
        return table_entity.data(1) or ""

    def rowCount(self, parent=QModelIndex()):
        return len(self._entities)

    def columnCount(self, parent=QModelIndex()):
        return 3  # User/Tool (with lock/unlock icon), Object, Session

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = ["User/Tool", "Object", "Session"]
            return headers[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._entities):
            return None

        entity = self._entities[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                # Show user/tool name with lock/unlock indicator
                access_indicator = "🔒" if (entity.entity.from_tool or entity.entity.read_only) else "✏️"
                return f"{access_indicator} {entity.data(0)}"
            elif column == 1:
                return entity.data(1)
            elif column == 2:
                return entity.data(2)

        elif role == Qt.BackgroundRole:
            color = QColor(*entity.color())
            color.setAlpha(50)  # Semi-transparent background
            return QBrush(color)

        elif role == Qt.DecorationRole:
            if column == 1:  # Eye icon for active state in object column
                if entity.is_active:
                    return self._eye_open_icon if self._eye_open_icon else QIcon()
                else:
                    return self._eye_closed_icon if self._eye_closed_icon else QIcon()

        elif role == Qt.ToolTipRole:
            if column == 0:
                if entity.entity.from_tool or entity.entity.read_only:
                    return f"Tool-generated entity (read-only): {entity.data(0)}"
                else:
                    return f"User-generated entity (editable): {entity.data(0)}"
            elif column == 1:
                status = "Visible" if entity.is_active else "Hidden"
                return f"{entity.data(1)} - {status}"

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
                # Emit data changed for the object column (where the eye icon is)
                index = self.index(i, 1)
                self.dataChanged.emit(index, index, [Qt.DecorationRole])
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
