from typing import List, Optional, Union

from chimerax.core.tools import ToolInstance
from copick.impl.filesystem import CopickRootFSSpec
from copick.models import CopickMesh, CopickPicks, CopickSegmentation
from Qt.QtCore import QObject, Qt, QSortFilterProxyModel, QModelIndex, QEvent
from Qt.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..ui.QCoPickTreeModel import QCoPickTreeModel
from ..ui.step_widget import StepWidget
from .QUnifiedTable import QUnifiedTable
from ..ui.tree import TreeRoot, TreeRun, TreeVoxelSpacing, TreeTomogram


class FilterProxyModel(QSortFilterProxyModel):
    """Custom proxy model that filters only run names, not their children"""
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Override to only filter run names, always show children of matching runs"""
        if not self.filterRegularExpression().pattern():
            # No filter applied - accept everything
            return True
        
        source_model = self.sourceModel()
        if not source_model:
            return False
        
        # Get the item for this row
        source_index = source_model.index(source_row, 0, source_parent)
        if not source_index.isValid():
            return False
        
        item = source_index.internalPointer()
        
        # Always accept root
        if isinstance(item, TreeRoot):
            return True
        
        # For runs (top level), apply the filter to their name
        if isinstance(item, TreeRun):
            item_text = source_model.data(source_index, Qt.ItemDataRole.DisplayRole)
            if item_text:
                return self.filterRegularExpression().match(item_text).hasMatch()
            return False
        
        # For children of runs (TreeVoxelSpacing, TreeTomogram), check if their ancestor run matches
        if isinstance(item, (TreeVoxelSpacing, TreeTomogram)):
            # Find the TreeRun ancestor
            current_item = item
            while current_item and not isinstance(current_item, TreeRun):
                current_item = current_item.parent
            
            if isinstance(current_item, TreeRun):
                # Check if the ancestor run matches the filter
                run_name = current_item.run.name
                return self.filterRegularExpression().match(run_name).hasMatch()
        
        return False


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
        # Top level layout with tight spacing
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(2, 2, 2, 2)  # Minimal margins
        self._layout.setSpacing(2)  # Tight spacing
        self.setLayout(self._layout)

        # Create main splitter (vertical - tables on top, tree on bottom)
        self._main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Create tables container widget
        tables_widget = QWidget()
        tables_widget.setMinimumHeight(200)  # Minimum height for tables

        # Picks widget with tight layout
        picks_layout = QVBoxLayout()
        picks_layout.setContentsMargins(1, 1, 1, 1)  # Minimal margins
        picks_layout.setSpacing(2)  # Tight spacing
        picks_widget = QWidget()
        self._picks_table = QUnifiedTable("picks")
        self._picks_stepper = StepWidget(0, 0)
        self._picks_stepper.setMaximumHeight(45)  # Appropriate height for buttons and text
        picks_layout.addWidget(self._picks_table)
        picks_layout.addWidget(self._picks_stepper)
        picks_widget.setLayout(picks_layout)

        # Mesh widget with tight layout
        meshes_layout = QVBoxLayout()
        meshes_layout.setContentsMargins(1, 1, 1, 1)  # Minimal margins
        meshes_layout.setSpacing(2)  # Tight spacing
        meshes_widget = QWidget()
        self._meshes_table = QUnifiedTable("meshes")
        meshes_layout.addWidget(self._meshes_table)
        meshes_widget.setLayout(meshes_layout)

        # Segmentation widget with tight layout
        segmentations_layout = QVBoxLayout()
        segmentations_layout.setContentsMargins(1, 1, 1, 1)  # Minimal margins
        segmentations_layout.setSpacing(2)  # Tight spacing
        segmentations_widget = QWidget()
        self._segmentations_table = QUnifiedTable("segmentations")
        segmentations_layout.addWidget(self._segmentations_table)
        segmentations_widget.setLayout(segmentations_layout)

        # Create tabbed widget for tables
        self._object_tabs = QTabWidget()
        self._object_tabs.addTab(picks_widget, "Picks")
        self._object_tabs.addTab(meshes_widget, "Meshes")
        self._object_tabs.addTab(segmentations_widget, "Segmentations")

        # Set up tables container with tight layout
        tables_layout = QVBoxLayout()
        tables_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        tables_layout.setSpacing(0)  # No spacing
        tables_layout.addWidget(self._object_tabs)
        tables_widget.setLayout(tables_layout)

        # Create tree container with search functionality
        tree_container = self._create_tree_container()
        tree_container.setContentsMargins(0, 0, 0, 0)  # Remove margins

        # Add widgets to splitter
        self._main_splitter.addWidget(tables_widget)
        self._main_splitter.addWidget(tree_container)

        # Set initial splitter sizes (60% tables, 40% tree)
        self._main_splitter.setSizes([300, 200])
        self._main_splitter.setStretchFactor(0, 1)  # Tables can stretch
        self._main_splitter.setStretchFactor(1, 1)  # Tree can stretch

        # Add splitter to main layout
        self._layout.addWidget(self._main_splitter)

    def _create_tree_container(self) -> QWidget:
        """Create tree container with overlay search functionality"""
        container = QWidget()
        container.setMinimumHeight(120)  # Reduced minimum height
        layout = QVBoxLayout()
        layout.setContentsMargins(1, 1, 1, 1)  # Minimal margins
        layout.setSpacing(0)  # No spacing to maximize tree area

        # Tree view setup - takes full space
        self._tree_view = QTreeView()
        self._tree_view.setHeaderHidden(False)

        # Create overlay search widget (floating at bottom-left)
        self._search_overlay = QWidget(self._tree_view)
        self._search_overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(45, 45, 45, 200);
                border: 1px solid rgba(100, 100, 100, 180);
                border-radius: 6px;
            }
        """)
        
        # Search overlay layout
        overlay_layout = QHBoxLayout()
        overlay_layout.setContentsMargins(6, 4, 6, 4)
        overlay_layout.setSpacing(3)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search runs...")
        self._search_input.setMaximumHeight(24)
        self._search_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid rgba(120, 120, 120, 180);
                border-radius: 3px;
                padding: 3px 6px;
                color: #333;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid rgba(70, 130, 200, 200);
                background-color: rgba(255, 255, 255, 255);
            }
        """)

        # Clear/Close button (does both clear and close)
        self._clear_button = QPushButton("✕")
        self._clear_button.setMaximumSize(22, 22)
        self._clear_button.setToolTip("Clear search and close")
        self._clear_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(200, 200, 200, 180);
                border: none;
                border-radius: 11px;
                font-weight: bold;
                color: #666;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(220, 220, 220, 200);
                color: #333;
            }
        """)

        overlay_layout.addWidget(self._search_input)
        overlay_layout.addWidget(self._clear_button)
        self._search_overlay.setLayout(overlay_layout)

        # Position overlay at top-right and hide initially
        self._search_overlay.hide()

        # Search toggle button (floating at bottom-right corner, hidden initially)
        self._search_toggle = QPushButton("🔍")
        self._search_toggle.setParent(self._tree_view)
        self._search_toggle.setMaximumSize(30, 30)
        self._search_toggle.setToolTip("Search runs")
        self._search_toggle.setStyleSheet("""
            QPushButton {
                background-color: rgba(240, 240, 240, 200);
                border: 1px solid #ccc;
                border-radius: 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(220, 220, 220, 220);
            }
        """)
        # Hide search toggle initially - only show on tree hover
        self._search_toggle.hide()

        # Add only tree view to main layout
        layout.addWidget(self._tree_view)
        container.setLayout(layout)
        
        # Install event filter to handle resizing and mouse events
        self._tree_view.installEventFilter(self)
        # Set mouse tracking to detect enter/leave events
        self._tree_view.setMouseTracking(True)
        
        return container

    def set_root(self, root: CopickRootFSSpec):
        self._model = QCoPickTreeModel(root)

        # Set up filter proxy model for search functionality
        self._filter_model = FilterProxyModel()
        self._filter_model.setSourceModel(self._model)
        self._filter_model.setRecursiveFilteringEnabled(False)  # We handle filtering manually
        self._filter_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._filter_model.setFilterRole(Qt.DisplayRole)

        self._tree_view.setModel(self._filter_model)

    def _connect(self):
        # Tree actions
        self._tree_view.doubleClicked.connect(self._on_tree_double_click)

        # Search functionality
        self._search_toggle.clicked.connect(self._toggle_search)
        self._search_input.textChanged.connect(self._filter_tree)
        self._clear_button.clicked.connect(self._clear_and_close_search)

        # Picks actions - use wrapper methods to handle proxy model mapping
        self._picks_table.get_table_view().doubleClicked.connect(self._on_picks_double_click)
        self._picks_table.get_table_view().clicked.connect(self._on_picks_click)
        self._picks_table.duplicateClicked.connect(self._copick.duplicate_particles)
        self._picks_table.newClicked.connect(self._copick.new_particles)

        # Meshes actions - use wrapper methods to handle proxy model mapping
        self._meshes_table.get_table_view().doubleClicked.connect(self._on_meshes_double_click)
        self._meshes_table.duplicateClicked.connect(self._copick.duplicate_mesh)
        self._meshes_table.newClicked.connect(self._copick.new_mesh)

        # Segmentations actions - use wrapper methods to handle proxy model mapping
        self._segmentations_table.get_table_view().doubleClicked.connect(self._on_segmentations_double_click)
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

    def _toggle_search(self):
        """Toggle the visibility of the search overlay"""
        is_visible = self._search_overlay.isVisible()
        
        if not is_visible:
            # Position and show overlay
            self._position_search_overlay()
            self._search_overlay.show()
            self._search_input.setFocus()
        else:
            # Hide overlay and clear search
            self._search_overlay.hide()
            self._clear_search()
    
    def _position_search_overlay(self):
        """Position the search overlay at the bottom-left of the tree view"""
        if hasattr(self, '_search_overlay') and hasattr(self, '_tree_view'):
            tree_height = self._tree_view.height()
            tree_width = self._tree_view.width()
            overlay_width = min(240, tree_width - 60)  # Leave space for search toggle button
            overlay_height = 32  # Fixed height for search overlay
            
            # Position at bottom-left with some margin
            x = 10
            y = tree_height - overlay_height - 15
            
            self._search_overlay.setGeometry(x, y, overlay_width, overlay_height)
    
    def _position_search_toggle(self):
        """Position the search toggle button at bottom-right corner"""
        if hasattr(self, '_search_toggle') and hasattr(self, '_tree_view'):
            tree_width = self._tree_view.width()
            tree_height = self._tree_view.height()
            button_size = 30
            
            # Position at bottom-right corner with margin
            x = tree_width - button_size - 10
            y = tree_height - button_size - 15
            
            self._search_toggle.setGeometry(x, y, button_size, button_size)
    
    def eventFilter(self, obj, event):
        """Handle resize events to reposition floating elements and mouse hover events"""
        if obj == self._tree_view:
            if event.type() == QEvent.Type.Resize:
                self._position_search_toggle()
                if self._search_overlay.isVisible():
                    self._position_search_overlay()
            elif event.type() == QEvent.Type.Enter:
                # Show search toggle when mouse enters tree view
                if not self._search_overlay.isVisible():
                    self._search_toggle.show()
                    self._position_search_toggle()
            elif event.type() == QEvent.Type.Leave:
                # Hide search toggle when mouse leaves tree view (unless search is active)
                if not self._search_overlay.isVisible():
                    self._search_toggle.hide()
        return super().eventFilter(obj, event)

    def _filter_tree(self, text: str):
        """Filter the tree view based on search text"""
        if hasattr(self, "_filter_model"):
            # Store currently expanded items before filtering
            expanded_items = []
            if hasattr(self, "_tree_view") and self._tree_view.model() is not None:
                model = self._tree_view.model()
                for row in range(model.rowCount()):
                    index = model.index(row, 0)
                    if self._tree_view.isExpanded(index):
                        expanded_items.append(row)

            # Apply the filter
            self._filter_model.setFilterFixedString(text)

            if text:
                # Keep runs collapsed when filtering - don't auto-expand
                pass
            else:
                # When clearing search, restore previous expanded state
                self._tree_view.collapseAll()
                # Restore previously expanded items
                if hasattr(self, "_tree_view") and self._tree_view.model() is not None:
                    model = self._tree_view.model()
                    for row in expanded_items:
                        if row < model.rowCount():
                            index = model.index(row, 0)
                            self._tree_view.expand(index)

    def _on_tree_double_click(self, proxy_index: QModelIndex):
        """Handle double-click events on the tree view by mapping proxy indices to source indices"""
        if not proxy_index.isValid():
            return

        # Map proxy model index to source model index
        if hasattr(self, "_filter_model") and self._filter_model is not None:
            source_index = self._filter_model.mapToSource(proxy_index)
            if source_index.isValid():
                self._copick.switch_volume(source_index)
        else:
            # Fallback: if no filter model, pass the index directly
            self._copick.switch_volume(proxy_index)

    def _clear_search(self):
        """Clear the search input and reset the filter"""
        self._search_input.clear()
        if hasattr(self, "_filter_model"):
            self._filter_model.setFilterFixedString("")
            self._tree_view.collapseAll()
    
    def _clear_and_close_search(self):
        """Clear the search input, reset the filter, and close the overlay"""
        self._clear_search()
        self._search_overlay.hide()
    
    def _on_picks_double_click(self, proxy_index: QModelIndex):
        """Handle double-click on picks table by mapping proxy index to source index"""
        if not proxy_index.isValid():
            return
        
        # Map proxy index to source index
        if hasattr(self._picks_table, '_filter_model') and self._picks_table._filter_model:
            source_index = self._picks_table._filter_model.mapToSource(proxy_index)
            self._copick.show_particles(source_index)
        else:
            self._copick.show_particles(proxy_index)
    
    def _on_picks_click(self, proxy_index: QModelIndex):
        """Handle click on picks table by mapping proxy index to source index"""
        if not proxy_index.isValid():
            return
        
        # Map proxy index to source index
        if hasattr(self._picks_table, '_filter_model') and self._picks_table._filter_model:
            source_index = self._picks_table._filter_model.mapToSource(proxy_index)
            self._copick.activate_particles(source_index)
        else:
            self._copick.activate_particles(proxy_index)
    
    def _on_meshes_double_click(self, proxy_index: QModelIndex):
        """Handle double-click on meshes table by mapping proxy index to source index"""
        if not proxy_index.isValid():
            return
        
        # Map proxy index to source index
        if hasattr(self._meshes_table, '_filter_model') and self._meshes_table._filter_model:
            source_index = self._meshes_table._filter_model.mapToSource(proxy_index)
            self._copick.show_mesh(source_index)
        else:
            self._copick.show_mesh(proxy_index)
    
    def _on_segmentations_double_click(self, proxy_index: QModelIndex):
        """Handle double-click on segmentations table by mapping proxy index to source index"""
        if not proxy_index.isValid():
            return
        
        # Map proxy index to source index
        if hasattr(self._segmentations_table, '_filter_model') and self._segmentations_table._filter_model:
            source_index = self._segmentations_table._filter_model.mapToSource(proxy_index)
            self._copick.show_segmentation(source_index)
        else:
            self._copick.show_segmentation(proxy_index)
