from pathlib import Path
from typing import Any, Literal, Union

from copick.models import CopickPicks, CopickRun
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtGui import QColor, QIcon
from qtpy.QtWidgets import QFileIconProvider

from .table import TablePicks, TableRootPicks  # , ListRootMeshes, ListRootSegmentations


class QCoPickTableModel(QAbstractItemModel):
    def __init__(
        self,
        run: CopickRun,
        item_type: Union[Literal["picks"], Literal["meshes"], Literal["segmentations"]],
        item_source: Union[Literal["user"], Literal["tool"]],
        parent=None,
    ):
        super().__init__(parent)
        self._icon_provider = QFileIconProvider()
        icons = Path(__file__).parent.parent / "icons"
        self._icon_eye_closed = QIcon(str(icons / "eye_closed.png"))
        self._icon_eye_open = QIcon(str(icons / "eye_open.png"))

        if item_type == "picks":
            if item_source == "user":
                self._root = TableRootPicks(run=run, get_picks=run.user_picks)
            elif item_source == "tool":
                self._root = TableRootPicks(run=run, get_picks=run.tool_picks)

    def index(self, row: int, column: int, parent=QModelIndex()) -> Union[QModelIndex, None]:
        if not self.hasIndex(row, column, parent):
            return None

        parentItem = self._root if not parent.isValid() else parent.internalPointer()
        childItem = parentItem.child(row)

        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return None

    def item_index(self, item: Union[TablePicks]) -> QModelIndex:
        childItem = item
        parentItem = childItem.parent

        if parentItem != self._root:
            return self.createIndex(parentItem.childIndex(), 0, parentItem)
        else:
            return QModelIndex()

    def parent(self, index: QModelIndex) -> Union[QModelIndex, None]:
        if not index.isValid():
            return None

        childItem = index.internalPointer()
        parentItem = childItem.parent

        if parentItem != self._root:
            # print(f"createIndex({parentItem.childIndex()}, 0, {parentItem})")
            return self.createIndex(parentItem.childIndex(), 0, parentItem)
        else:
            return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        parentItem = self._root if not parent.isValid() else parent.internalPointer()

        return parentItem.childCount()

    def columnCount(self, parent: QModelIndex = QModelIndex()):
        return self._root.columnCount()

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.ItemDataRole.BackgroundRole:
            r, g, b, a = item.color()
            return QColor(r, g, b, a)

        if role == 0:
            return item.data(index.column())

        if role == 1 and index.column() == 0:
            if item.is_active:
                return self._icon_eye_open
            else:
                return self._icon_eye_closed
        else:
            return None

    def hasChildren(self, parent: QModelIndex = ...) -> bool:
        parentItem = self._root if not parent.isValid() else parent.internalPointer()

        return parentItem.has_children  # parentItem.is_dir

    def headerData(self, section, orientation, role=...):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 0:
                return "User/Tool"
            elif section == 1:
                return "Object"

    def flags(self, index: QModelIndex) -> Union[Qt.ItemFlag, None]:
        if not index.isValid():
            return None

        index.internalPointer()
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_picks_active(self, picks: CopickPicks, active: bool):
        item = self._root.get_item(picks)

        if item:
            item.is_active = active
            self.dataChanged.emit(self.item_index(item), self.item_index(item))

    def update_all(self):
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        self.layoutChanged.emit()
