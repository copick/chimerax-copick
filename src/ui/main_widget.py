from typing import Optional

from chimerax.core.tools import ToolInstance
from copick.impl.filesystem import CopickRootFSSpec
from Qt.QtCore import QObject
from Qt.QtWidgets import (
    QTabWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..ui.QCoPickTreeModel import QCoPickTreeModel
from .QDoubleTable import QDoubleTable


class MainWidget(QWidget):
    def __init__(
        self,
        copick: ToolInstance,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent=parent)

        self._copick = copick
        self._root = None
        self._model = None

        self._build()
        self._connect()

    def _build(self):
        # Top level layout
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._object_tabs = QTabWidget()
        self._picks_table = QDoubleTable("picks")
        self._object_tabs.addTab(self._picks_table, "Picks")
        self._object_tabs.addTab(QDoubleTable("meshes"), "Meshes")
        self._object_tabs.addTab(QDoubleTable("segmentations"), "Segmentations")

        # Tree View
        self._tree_view = QTreeView(parent=self)
        # self._tree_view.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))

        # Main layout
        # self._layout.addWidget(self._connectbox)
        self._layout.addWidget(self._object_tabs)
        self._layout.addWidget(self._tree_view)

    def set_root(self, root: CopickRootFSSpec):
        self._model = QCoPickTreeModel(root)
        self._tree_view.setModel(self._model)

    def _connect(self):
        self._tree_view.doubleClicked.connect(self._copick.switch_volume)
        self._picks_table._tool_table.doubleClicked.connect(self._copick.show_particles)
        self._picks_table._user_table.doubleClicked.connect(self._copick.show_particles)
        self._picks_table._user_table.clicked.connect(self._copick.activate_particles)
        self._picks_table.takeClicked.connect(self._copick.take_particles)
