from typing import Any, Callable, Optional, Union

from copick.models import CopickRoot
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QApplication, QFileIconProvider, QStyle

from .tree import TreeRoot, TreeRun, TreeTomogram, TreeVoxelSpacing


class QCoPickTreeModel(QAbstractItemModel):
    def __init__(
        self,
        root_item: CopickRoot,
        parent=None,
        tomo_state: Optional[Callable[[Any], Optional[str]]] = None,
    ):
        super().__init__(parent)
        self._root = TreeRoot(root=root_item)
        self._icon_provider = QFileIconProvider()
        self._tomo_state = tomo_state
        """Returns "shown", "loaded" or None for a copick tomogram."""

    def _state_of(self, item: TreeTomogram) -> Optional[str]:
        return self._tomo_state(item.tomogram) if self._tomo_state else None

    def refresh_tomogram_markers(self):
        """Re-query icons/fonts of all tomogram rows that have been built (lazy children)."""
        roles = [Qt.ItemDataRole.DecorationRole, Qt.ItemDataRole.FontRole, Qt.ItemDataRole.ToolTipRole]
        for run_item in self._root._children or []:
            for vs_item in run_item._children or []:
                tomos = vs_item._children or []
                if not tomos:
                    continue
                first = self.createIndex(0, 0, tomos[0])
                last = self.createIndex(len(tomos) - 1, 0, tomos[-1])
                self.dataChanged.emit(first, last, roles)

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

        if role == Qt.ItemDataRole.DisplayRole:
            return item.data(index.column())

        if role == 1 and index.column() == 0:
            if isinstance(item, (TreeRoot, TreeRun, TreeVoxelSpacing)):
                return self._icon_provider.icon(QFileIconProvider.IconType.Folder)
            elif isinstance(item, TreeTomogram):
                state = self._state_of(item)
                if state == "shown":
                    app = QApplication.instance()

                    icon = app.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
                    return icon
                else:
                    # Loaded-but-hidden tomograms are marked by a bold name (FontRole below).
                    return self._icon_provider.icon(QFileIconProvider.IconType.File)

        if isinstance(item, TreeTomogram) and index.column() == 0:
            if role == Qt.ItemDataRole.FontRole:
                if self._state_of(item) is not None:
                    font = QFont()
                    font.setBold(True)
                    return font
            elif role == Qt.ItemDataRole.ToolTipRole:
                state = self._state_of(item)
                if state == "shown":
                    return "Shown (loaded)"
                if state == "loaded":
                    return "Loaded, hidden - double-click to show instantly"
                return "Double-click to load"

        return None

    def hasChildren(self, parent: QModelIndex = ...) -> bool:
        parentItem = self._root if not parent.isValid() else parent.internalPointer()

        return parentItem.has_children  # parentItem.is_dir

    def canFetchMore(self, parent: QModelIndex = ...):
        parentItem = self._root if not parent.isValid() else parent.internalPointer()

        if parentItem.childCount() == 0:
            return True

        return False

    def fetchMore(self, parent: QModelIndex = ...):
        parentItem = self._root if not parent.isValid() else parent.internalPointer()

        if parentItem.childCount() == 0:
            _ = parentItem.children  # Trigger loading of children

    def headerData(self, section, orientation, role=...):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 0:
                return "Name"
            elif section == 1:
                return "Size"

    def flags(self, index: QModelIndex) -> Union[Qt.ItemFlag, None]:
        if not index.isValid():
            return None

        index.internalPointer()
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
