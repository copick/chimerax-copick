from typing import List, Optional, Union

from chimerax.core.tools import ToolInstance
from copick.impl.filesystem import CopickRootFSSpec
from copick.models import CopickMesh, CopickPicks, CopickSegmentation
from Qt.QtCore import QObject, Qt
from Qt.QtWidgets import (
    QSplitter,
    QTabWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..ui.QCoPickTreeModel import QCoPickTreeModel
from ..ui.step_widget import StepWidget
from .QUnifiedTable import QUnifiedTable


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
        self._layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self._layout)

        # Create main splitter (vertical - tables on top, tree on bottom)
        self._main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Create tables container widget
        tables_widget = QWidget()
        tables_widget.setMinimumHeight(200)  # Minimum height for tables

        # Picks widget with improved layout
        picks_layout = QVBoxLayout()
        picks_layout.setContentsMargins(2, 2, 2, 2)
        picks_widget = QWidget()
        self._picks_table = QUnifiedTable("picks")
        self._picks_stepper = StepWidget(0, 0)
        self._picks_stepper.setMaximumHeight(40)  # Limit stepper height
        picks_layout.addWidget(self._picks_table)
        picks_layout.addWidget(self._picks_stepper)
        picks_widget.setLayout(picks_layout)

        # Mesh widget with improved layout
        meshes_layout = QVBoxLayout()
        meshes_layout.setContentsMargins(2, 2, 2, 2)
        meshes_widget = QWidget()
        self._meshes_table = QUnifiedTable("meshes")
        meshes_layout.addWidget(self._meshes_table)
        meshes_widget.setLayout(meshes_layout)

        # Segmentation widget with improved layout
        segmentations_layout = QVBoxLayout()
        segmentations_layout.setContentsMargins(2, 2, 2, 2)
        segmentations_widget = QWidget()
        self._segmentations_table = QUnifiedTable("segmentations")
        segmentations_layout.addWidget(self._segmentations_table)
        segmentations_widget.setLayout(segmentations_layout)

        # Create tabbed widget for tables
        self._object_tabs = QTabWidget()
        self._object_tabs.addTab(picks_widget, "Picks")
        self._object_tabs.addTab(meshes_widget, "Meshes")
        self._object_tabs.addTab(segmentations_widget, "Segmentations")

        # Set up tables container
        tables_layout = QVBoxLayout()
        tables_layout.setContentsMargins(0, 0, 0, 0)
        tables_layout.addWidget(self._object_tabs)
        tables_widget.setLayout(tables_layout)

        # Tree View with minimum size
        self._tree_view = QTreeView()
        self._tree_view.setMinimumHeight(150)  # Minimum height for tree view
        self._tree_view.setHeaderHidden(False)  # Show headers for better usability

        # Add widgets to splitter
        self._main_splitter.addWidget(tables_widget)
        self._main_splitter.addWidget(self._tree_view)

        # Set initial splitter sizes (60% tables, 40% tree)
        self._main_splitter.setSizes([300, 200])
        self._main_splitter.setStretchFactor(0, 1)  # Tables can stretch
        self._main_splitter.setStretchFactor(1, 1)  # Tree can stretch

        # Add splitter to main layout
        self._layout.addWidget(self._main_splitter)

    def set_root(self, root: CopickRootFSSpec):
        self._model = QCoPickTreeModel(root)
        self._tree_view.setModel(self._model)

    def _connect(self):
        # Tree actions
        self._tree_view.doubleClicked.connect(self._copick.switch_volume)

        # Picks actions
        self._picks_table.get_table_view().doubleClicked.connect(self._copick.show_particles)
        self._picks_table.get_table_view().clicked.connect(self._copick.activate_particles)
        self._picks_table.duplicateClicked.connect(self._copick.duplicate_particles)
        self._picks_table.newClicked.connect(self._copick.new_particles)

        # Meshes actions
        self._meshes_table.get_table_view().doubleClicked.connect(self._copick.show_mesh)
        self._meshes_table.duplicateClicked.connect(self._copick.duplicate_mesh)
        self._meshes_table.newClicked.connect(self._copick.new_mesh)

        # Segmentations actions
        self._segmentations_table.get_table_view().doubleClicked.connect(self._copick.show_segmentation)
        self._segmentations_table.duplicateClicked.connect(self._copick.duplicate_segmentation)
        self._segmentations_table.newClicked.connect(self._copick.new_segmentation)

        self._picks_stepper.stateChanged.connect(self._copick._set_active_particle)

    def set_entity_active(self, picks: Union[CopickMesh, CopickPicks, CopickSegmentation], active: bool):
        if isinstance(picks, CopickPicks):
            self._picks_table.set_entity_active(picks, active)
        elif isinstance(picks, CopickMesh):
            self._meshes_table.set_entity_active(picks, active)
        elif isinstance(picks, CopickSegmentation):
            self._segmentations_table.set_entity_active(picks, active)

    def update_picks_table(self):
        self._picks_table.update()

    def picks_stepper(self, pick_list: List[str]):
        self._picks_stepper.set(len(pick_list), 0)

    def set_stepper_state(self, max: int, state: int = 0):
        self._picks_stepper.set(max, state)
