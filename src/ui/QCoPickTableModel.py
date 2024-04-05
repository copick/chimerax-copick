from typing import Any, Literal, Union

from copick.models import CopickRun
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtWidgets import QApplication, QFileIconProvider, QStyle

from .table import TableRootPicks  # , ListRootMeshes, ListRootSegmentations


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

        if role == 0:
            return item.data(index.column())

        if role == 1 and index.column() == 0:
            if item.is_active:
                app = QApplication.instance()

                icon = app.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
                return icon
            else:
                return self._icon_provider.icon(QFileIconProvider.IconType.File)
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
