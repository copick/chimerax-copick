from typing import List, Optional

from chimerax.core.tools import ToolInstance
from copick.impl.filesystem import CopickRootFSSpec
from copick.models import CopickPicks
from Qt.QtCore import QObject
from Qt.QtWidgets import (
    QSizePolicy,
    QTabWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..ui.QCoPickTreeModel import QCoPickTreeModel
from ..ui.step_widget import StepWidget
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

        # Picks widget
        picks_layout = QVBoxLayout()
        picks_widget = QWidget()
        picks_widget.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))
        self._picks_table = QDoubleTable("picks")
        self._picks_stepper = StepWidget(0, 0)
        self._picks_table.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))
        self._picks_stepper.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))
        picks_layout.addWidget(self._picks_table)
        picks_layout.addWidget(self._picks_stepper)
        picks_widget.setLayout(picks_layout)

        self._object_tabs = QTabWidget()
        self._object_tabs.addTab(picks_widget, "Picks")
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
        self._picks_table._tool_table.clicked.connect(self._copick.activate_particles)
        self._picks_table.takeClicked.connect(self._copick.take_particles)

        self._picks_stepper.stateChanged.connect(self._copick._set_active_particle)

    def set_picks_active(self, picks: CopickPicks, active: bool):
        self._picks_table.set_picks_active(picks, active)

    def update_picks_table(self):
        self._picks_table.update()

    def picks_stepper(self, pick_list: List[str]):
        self._picks_stepper.set(len(pick_list), 0)

    def set_stepper_state(self, max: int, state: int = 0):
        self._picks_stepper.set(max, state)
