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
from .copick_gallery_widget import CopickGalleryWidget


class FilterProxyModel(QSortFilterProxyModel):
    """Custom proxy model that filters only run names, not their children"""

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Override to only filter run names, completely ignore children to prevent eager loading"""
        if not self.filterRegularExpression().pattern():
            # No filter applied - accept everything
            return True

        source_model = self.sourceModel()
        if not source_model:
            return False

        # PERFORMANCE FIX: Only filter at the root level (runs only)
        # This completely prevents any interaction with child items during filtering
        if source_parent.isValid():
            # This is a child item (voxel spacing or tomogram)
            # NEVER process children during filtering to avoid any possibility of lazy loading
            # If the parent run matches, children will be shown automatically by Qt
            return True

        # Only process root-level items (runs)
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

        # Should never reach here with the new logic, but safety fallback
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

        # Create top button bar
        self._create_top_buttons()

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

        # Create horizontal layout to center the stepper widget
        stepper_layout = QHBoxLayout()
        stepper_layout.addStretch()  # Left stretch
        stepper_layout.addWidget(self._picks_stepper)
        stepper_layout.addStretch()  # Right stretch
        stepper_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        stepper_container = QWidget()
        stepper_container.setLayout(stepper_layout)

        picks_layout.addWidget(self._picks_table)
        picks_layout.addWidget(stepper_container)
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

        # Add table settings buttons to top layout (after tables are created)
        self._add_table_settings_buttons()

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
        self._search_overlay.setStyleSheet(
            """
            QWidget {
                background-color: rgba(45, 45, 45, 200);
                border: 1px solid rgba(100, 100, 100, 180);
                border-radius: 6px;
            }
        """
        )

        # Search overlay layout
        overlay_layout = QHBoxLayout()
        overlay_layout.setContentsMargins(6, 4, 6, 4)
        overlay_layout.setSpacing(3)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search runs...")
        self._search_input.setMaximumHeight(24)
        self._search_input.setStyleSheet(
            """
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
        """
        )

        # Clear/Close button (does both clear and close)
        self._clear_button = QPushButton("✕")
        self._clear_button.setMaximumSize(22, 22)
        self._clear_button.setToolTip("Clear search and close")
        self._clear_button.setStyleSheet(
            """
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
        """
        )

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
        self._search_toggle.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(240, 240, 240, 200);
                border: 1px solid #ccc;
                border-radius: 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(220, 220, 220, 220);
            }
        """
        )
        # Hide search toggle initially - only show on tree hover
        self._search_toggle.hide()

        # Navigation buttons (floating at top-right corner, hidden initially)
        button_style = """
            QPushButton {
                background-color: rgba(240, 240, 240, 200);
                border: 1px solid #ccc;
                border-radius: 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(220, 220, 220, 220);
            }
        """

        # 3D View button
        self._view_3d_button = QPushButton("🧊")
        self._view_3d_button.setParent(self._tree_view)
        self._view_3d_button.setMaximumSize(30, 30)
        self._view_3d_button.setToolTip("Switch to 3D view")
        self._view_3d_button.setStyleSheet(button_style)
        self._view_3d_button.hide()

        # Details View button
        self._view_details_button = QPushButton("ℹ️")
        self._view_details_button.setParent(self._tree_view)
        self._view_details_button.setMaximumSize(30, 30)
        self._view_details_button.setToolTip("Switch to details view")
        self._view_details_button.setStyleSheet(button_style)
        self._view_details_button.hide()

        # Gallery View button
        self._view_gallery_button = QPushButton("📸")
        self._view_gallery_button.setParent(self._tree_view)
        self._view_gallery_button.setMaximumSize(30, 30)
        self._view_gallery_button.setToolTip("Switch to gallery view")
        self._view_gallery_button.setStyleSheet(button_style)
        self._view_gallery_button.hide()

        # Add only tree view to main layout
        layout.addWidget(self._tree_view)
        container.setLayout(layout)

        # Install event filter to handle resizing and mouse events
        self._tree_view.installEventFilter(self)
        # Set mouse tracking to detect enter/leave events
        self._tree_view.setMouseTracking(True)

        return container

    def _create_top_buttons(self):
        """Create the top button bar with Add Object Type and Reload buttons"""
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)

        # Edit Object Types button
        self._edit_objects_button = QPushButton("✏️ Edit Object Types")
        self._edit_objects_button.setToolTip("Edit and manage pickable object types")

        # Reload button
        self._reload_button = QPushButton("🔄 Reload")
        self._reload_button.setToolTip("Reload the current copick session")

        # Add buttons to layout with center alignment
        button_layout.addStretch()  # Left stretch
        button_layout.addWidget(self._edit_objects_button)
        button_layout.addWidget(self._reload_button)

        # Add settings buttons from tables (will be added later in _build)
        # Placeholder for table settings buttons
        button_layout.addStretch()  # Right stretch

        # Create container widget
        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        button_widget.setMaximumHeight(35)

        # Store layout reference for adding settings buttons later
        self._top_button_layout = button_layout

        # Add to main layout
        self._layout.addWidget(button_widget)

    def _add_table_settings_buttons(self):
        """Add a single shared settings button to the top button layout"""
        # Remove the last stretch before adding button
        item_count = self._top_button_layout.count()
        if item_count > 0:
            last_item = self._top_button_layout.itemAt(item_count - 1)
            if last_item.spacerItem():  # Remove the right stretch
                self._top_button_layout.removeItem(last_item)

        # Create single shared settings button
        self._shared_settings_button = QPushButton("⚙")
        self._shared_settings_button.setToolTip("Table settings (applies to all tables)")
        self._shared_settings_button.clicked.connect(self._on_shared_settings_clicked)
        self._top_button_layout.addWidget(self._shared_settings_button)

        # Add back the right stretch
        self._top_button_layout.addStretch()

    def set_root(self, root: CopickRootFSSpec):
        self._root = root
        self._model = QCoPickTreeModel(root)

        # Set up filter proxy model for search functionality
        self._filter_model = FilterProxyModel()
        self._filter_model.setSourceModel(self._model)
        self._filter_model.setRecursiveFilteringEnabled(False)  # We handle filtering manually
        self._filter_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._filter_model.setFilterRole(Qt.DisplayRole)

        self._tree_view.setModel(self._filter_model)

        # Connect selection model after setting the model
        if self._tree_view.selectionModel():
            self._tree_view.selectionModel().selectionChanged.connect(self._on_tree_selection_changed)

        # Update gallery widget with new root if it exists
        self._update_gallery_widget_root(root)

    def _connect(self):
        # Top button actions
        self._edit_objects_button.clicked.connect(self._on_edit_object_types)
        self._reload_button.clicked.connect(self._on_reload)

        # Tree actions
        self._tree_view.doubleClicked.connect(self._on_tree_double_click)

        # Search functionality
        self._search_toggle.clicked.connect(self._toggle_search)
        self._search_input.textChanged.connect(self._filter_tree)
        self._clear_button.clicked.connect(self._clear_and_close_search)

        # Navigation button functionality
        self._view_3d_button.clicked.connect(self._navigate_to_3d)
        self._view_details_button.clicked.connect(self._navigate_to_details)
        self._view_gallery_button.clicked.connect(self._navigate_to_gallery)

        # Picks actions - use wrapper methods to handle proxy model mapping
        self._picks_table.get_table_view().doubleClicked.connect(self._on_picks_double_click)
        self._picks_table.get_table_view().clicked.connect(self._on_picks_click)
        self._picks_table.duplicateClicked.connect(self._copick.duplicate_particles)
        self._picks_table.newClicked.connect(self._copick.new_particles)
        self._picks_table.deleteClicked.connect(self._copick.delete_particles)

        # Meshes actions - use wrapper methods to handle proxy model mapping
        self._meshes_table.get_table_view().doubleClicked.connect(self._on_meshes_double_click)
        self._meshes_table.duplicateClicked.connect(self._copick.duplicate_mesh)
        self._meshes_table.newClicked.connect(self._copick.new_mesh)
        self._meshes_table.deleteClicked.connect(self._copick.delete_mesh)

        # Segmentations actions - use wrapper methods to handle proxy model mapping
        self._segmentations_table.get_table_view().doubleClicked.connect(self._on_segmentations_double_click)
        self._segmentations_table.duplicateClicked.connect(self._copick.duplicate_segmentation)
        self._segmentations_table.newClicked.connect(self._copick.new_segmentation)
        self._segmentations_table.deleteClicked.connect(self._copick.delete_segmentation)

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

    def clear_all_tables(self):
        """Clear all table models by setting them to None"""
        self._picks_table._table.setModel(None)
        self._meshes_table._table.setModel(None)
        self._segmentations_table._table.setModel(None)

        # Reset internal state
        self._picks_table._run = None
        self._picks_table._source_model = None
        self._picks_table._filter_model = None

        self._meshes_table._run = None
        self._meshes_table._source_model = None
        self._meshes_table._filter_model = None

        self._segmentations_table._run = None
        self._segmentations_table._source_model = None
        self._segmentations_table._filter_model = None

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
        if hasattr(self, "_search_overlay") and hasattr(self, "_tree_view"):
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
        if hasattr(self, "_search_toggle") and hasattr(self, "_tree_view"):
            tree_width = self._tree_view.width()
            tree_height = self._tree_view.height()
            button_size = 30

            # Position at bottom-right corner with margin
            x = tree_width - button_size - 10
            y = tree_height - button_size - 15

            self._search_toggle.setGeometry(x, y, button_size, button_size)

    def _position_navigation_buttons(self):
        """Position the three navigation buttons vertically at top-right corner"""
        if hasattr(self, "_tree_view"):
            tree_width = self._tree_view.width()
            button_size = 30
            gap = 5
            start_x = tree_width - button_size - 10
            start_y = 10

            # Position 3D view button at top
            if hasattr(self, "_view_3d_button"):
                self._view_3d_button.setGeometry(start_x, start_y, button_size, button_size)

            # Position details button below 3D
            if hasattr(self, "_view_details_button"):
                y = start_y + button_size + gap
                self._view_details_button.setGeometry(start_x, y, button_size, button_size)

            # Position gallery button below details
            if hasattr(self, "_view_gallery_button"):
                y = start_y + 2 * (button_size + gap)
                self._view_gallery_button.setGeometry(start_x, y, button_size, button_size)

    def eventFilter(self, obj, event):
        """Handle resize events to reposition floating elements and mouse hover events"""
        if obj == self._tree_view:
            if event.type() == QEvent.Type.Resize:
                self._position_search_toggle()
                self._position_navigation_buttons()
                if self._search_overlay.isVisible():
                    self._position_search_overlay()
            elif event.type() == QEvent.Type.Enter:
                # Show search and navigation buttons when mouse enters tree view
                if not self._search_overlay.isVisible():
                    self._search_toggle.show()
                    self._position_search_toggle()
                self._view_3d_button.show()
                self._view_details_button.show()
                self._view_gallery_button.show()
                self._position_navigation_buttons()
            elif event.type() == QEvent.Type.Leave:
                # Hide buttons when mouse leaves tree view (unless search is active)
                if not self._search_overlay.isVisible():
                    self._search_toggle.hide()
                self._view_3d_button.hide()
                self._view_details_button.hide()
                self._view_gallery_button.hide()
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

            # Also apply filter to gallery widget if it exists
            try:
                session = self._copick.session
                main_window = session.ui.main_window
                stack_widget = main_window._stack

                for i in range(stack_widget.count()):
                    widget = stack_widget.widget(i)
                    if hasattr(widget, "__class__") and widget.__class__.__name__ == "CopickGalleryWidget":
                        widget.apply_search_filter(text)
                        break
            except Exception:
                pass  # Silently handle errors

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
        if hasattr(self._picks_table, "_filter_model") and self._picks_table._filter_model:
            source_index = self._picks_table._filter_model.mapToSource(proxy_index)
            self._copick.show_particles(source_index)
        else:
            self._copick.show_particles(proxy_index)

    def _on_picks_click(self, proxy_index: QModelIndex):
        """Handle click on picks table by mapping proxy index to source index"""
        if not proxy_index.isValid():
            return

        # Map proxy index to source index
        if hasattr(self._picks_table, "_filter_model") and self._picks_table._filter_model:
            source_index = self._picks_table._filter_model.mapToSource(proxy_index)
            self._copick.activate_particles(source_index)
        else:
            self._copick.activate_particles(proxy_index)

    def _on_meshes_double_click(self, proxy_index: QModelIndex):
        """Handle double-click on meshes table by mapping proxy index to source index"""
        if not proxy_index.isValid():
            return

        # Map proxy index to source index
        if hasattr(self._meshes_table, "_filter_model") and self._meshes_table._filter_model:
            source_index = self._meshes_table._filter_model.mapToSource(proxy_index)
            self._copick.show_mesh(source_index)
        else:
            self._copick.show_mesh(proxy_index)

    def _on_segmentations_double_click(self, proxy_index: QModelIndex):
        """Handle double-click on segmentations table by mapping proxy index to source index"""
        if not proxy_index.isValid():
            return

        # Map proxy index to source index
        if hasattr(self._segmentations_table, "_filter_model") and self._segmentations_table._filter_model:
            source_index = self._segmentations_table._filter_model.mapToSource(proxy_index)
            self._copick.show_segmentation(source_index)
        else:
            self._copick.show_segmentation(proxy_index)

    def _on_edit_object_types(self):
        """Handle Edit Object Types button click"""
        self._copick.edit_object_types()

    def _on_reload(self):
        """Handle Reload button click"""
        self._copick.reload_session()

    def _on_shared_settings_clicked(self):
        """Handle shared settings button click - show settings for current tab"""
        current_tab_index = self._object_tabs.currentIndex()

        # Get the current table's settings overlay
        current_table = None
        if current_tab_index == 0:  # Picks tab
            current_table = self._picks_table
        elif current_tab_index == 1:  # Meshes tab
            current_table = self._meshes_table
        elif current_tab_index == 2:  # Segmentations tab
            current_table = self._segmentations_table

        if current_table:
            # Position the overlay relative to the shared settings button
            self._position_shared_settings_overlay(current_table._settings_overlay)

            # Show the overlay
            if current_table._settings_overlay.isVisible():
                current_table._settings_overlay.hide()
            else:
                current_table._settings_overlay.show()
                current_table._settings_overlay.raise_()
                current_table._settings_overlay.activateWindow()

    def _position_shared_settings_overlay(self, overlay):
        """Position the settings overlay relative to the shared settings button"""
        if hasattr(self, "_shared_settings_button"):
            # Get button position in global coordinates
            button_global_pos = self._shared_settings_button.mapToGlobal(self._shared_settings_button.rect().topLeft())

            # Position overlay below the button with some offset
            overlay_width = 280
            overlay_height = 140
            x = (
                button_global_pos.x() - overlay_width + self._shared_settings_button.width()
            )  # Align right edge with button
            y = button_global_pos.y() + self._shared_settings_button.height() + 5  # Below button with gap

            # Get the screen that contains the button (not just primary screen)
            from Qt.QtWidgets import QApplication

            app = QApplication.instance()
            screen = app.screenAt(button_global_pos)
            if screen is None:
                # Fallback to primary screen if we can't determine the current screen
                screen = app.primaryScreen()
            screen_geometry = screen.geometry()

            # Ensure we don't go off-screen to the left
            if x < screen_geometry.left() + 10:
                x = screen_geometry.left() + 10

            # Ensure we don't go off-screen to the right
            if x + overlay_width > screen_geometry.right() - 10:
                x = screen_geometry.right() - overlay_width - 10

            # Ensure vertical positioning is within screen bounds
            if y + overlay_height > screen_geometry.bottom() - 10:
                # Position above the button instead
                y = button_global_pos.y() - overlay_height - 5

            if y < screen_geometry.top() + 10:
                y = screen_geometry.top() + 10

            overlay.move(x, y)

    def _on_gallery_run_selected(self, run):
        """Handle run selection from gallery widget"""
        try:
            # Update current run
            self._current_run = run
            self.set_current_run(run)

            # Switch back to OpenGL view to show the selected run
            session = self._copick.session
            main_window = session.ui.main_window
            stack_widget = main_window._stack
            stack_widget.setCurrentIndex(0)

        except Exception as e:
            print(f"Error handling gallery run selection: {e}")

    def _navigate_to_3d(self):
        """Navigate to 3D/OpenGL view"""
        try:
            session = self._copick.session
            main_window = session.ui.main_window
            stack_widget = main_window._stack

            # Switch to OpenGL view (first widget is usually the graphics view)
            stack_widget.setCurrentIndex(0)

        except Exception as e:
            print(f"Error navigating to 3D view: {e}")

    def _navigate_to_details(self):
        """Navigate to details/info view"""
        try:
            session = self._copick.session
            main_window = session.ui.main_window
            stack_widget = main_window._stack

            # Check if our copick info widget is already in the stack
            copick_widget = None
            for i in range(stack_widget.count()):
                widget = stack_widget.widget(i)
                if hasattr(widget, "__class__") and widget.__class__.__name__ == "CopickInfoWidget":
                    copick_widget = widget
                    break

            # If no copick widget exists, create one
            if copick_widget is None:
                from .copick_info_widget import CopickInfoWidget

                copick_widget = CopickInfoWidget(session)

                # Update with current run if one is selected
                if hasattr(self, "_current_run") and self._current_run:
                    copick_widget.set_run(self._current_run)
                elif hasattr(self, "_current_run_name") and self._current_run_name:
                    copick_widget.set_run_name(self._current_run_name)

                stack_widget.addWidget(copick_widget)

                # Store reference for cleanup
                self._copick_html_widget = copick_widget

            # Switch to copick info view
            stack_widget.setCurrentWidget(copick_widget)

        except Exception as e:
            print(f"Error navigating to details view: {e}")

    def _navigate_to_gallery(self):
        """Navigate to gallery view"""
        try:
            session = self._copick.session
            main_window = session.ui.main_window
            stack_widget = main_window._stack

            # Check if our gallery widget is already in the stack
            gallery_widget = None
            for i in range(stack_widget.count()):
                widget = stack_widget.widget(i)
                if hasattr(widget, "__class__") and widget.__class__.__name__ == "CopickGalleryWidget":
                    gallery_widget = widget
                    break

            # If no gallery widget exists, create one
            if gallery_widget is None:
                gallery_widget = CopickGalleryWidget(session)

                # Set copick root if available
                if hasattr(self, "_root") and self._root:
                    gallery_widget.set_copick_root(self._root)

                # Connect gallery run selection to main widget
                gallery_widget.run_selected.connect(self._on_gallery_run_selected)

                stack_widget.addWidget(gallery_widget)

                # Store reference for cleanup
                self._copick_gallery_widget = gallery_widget

            # Switch to gallery view
            stack_widget.setCurrentWidget(gallery_widget)

            # Apply current search filter to gallery
            if hasattr(self, "_search_input") and self._search_input.text():
                gallery_widget.apply_search_filter(self._search_input.text())

        except Exception as e:
            print(f"Error navigating to gallery view: {e}")

    def _update_gallery_widget_root(self, root):
        """Update gallery and info widgets when copick root changes"""
        try:
            session = self._copick.session
            main_window = session.ui.main_window
            stack_widget = main_window._stack

            # Update widgets in the stack
            for i in range(stack_widget.count()):
                widget = stack_widget.widget(i)
                if hasattr(widget, "__class__"):
                    if widget.__class__.__name__ == "CopickGalleryWidget":
                        # Update the gallery widget with the new root
                        widget.set_copick_root(root)
                        print(f"Updated gallery widget with new copick root")
                    elif widget.__class__.__name__ == "CopickInfoWidget":
                        # Clear the info widget when root changes (no specific run selected yet)
                        widget.set_run(None)
                        print(f"Cleared info widget for new copick root")
        except Exception as e:
            print(f"Error updating widgets for new root: {e}")

    def set_current_run_name(self, run_name: str):
        """Update the current run name and notify the HTML widget if it exists"""
        self._current_run_name = run_name

        # Update info widget if it exists
        try:
            session = self._copick.session
            main_window = session.ui.main_window
            stack_widget = main_window._stack

            for i in range(stack_widget.count()):
                widget = stack_widget.widget(i)
                if hasattr(widget, "__class__") and widget.__class__.__name__ == "CopickInfoWidget":
                    widget.set_run_name(run_name)
                    break
        except:
            pass  # Silently handle errors

    def set_current_run(self, run):
        """Update the current run object and notify the HTML widget if it exists"""
        self._current_run = run
        if run:
            self._current_run_name = run.name
        else:
            self._current_run_name = None

        # Update info widget if it exists
        try:
            session = self._copick.session
            main_window = session.ui.main_window
            stack_widget = main_window._stack

            for i in range(stack_widget.count()):
                widget = stack_widget.widget(i)
                if hasattr(widget, "__class__") and widget.__class__.__name__ == "CopickInfoWidget":
                    widget.set_run(run)
                    break
        except:
            pass  # Silently handle errors

    def _on_tree_selection_changed(self, selected, deselected):
        """Handle tree selection changes to update run object in HTML widget"""
        try:
            if not selected.indexes():
                return

            # Get the first selected index
            proxy_index = selected.indexes()[0]
            if not proxy_index.isValid():
                return

            # Map proxy model index to source model index
            if hasattr(self, "_filter_model") and self._filter_model is not None:
                source_index = self._filter_model.mapToSource(proxy_index)
            else:
                source_index = proxy_index

            if not source_index.isValid():
                return

            # Get the item from the source index
            item = source_index.internalPointer()

            # Check if it's a run and update the current run object
            if isinstance(item, TreeRun):
                # Pass the actual run object for async loading
                self.set_current_run(item.run)

        except Exception as e:
            # Silently handle errors to avoid breaking the selection
            print(f"Error handling tree selection: {e}")

    def cleanup(self):
        """Clean up resources, especially the info widget"""
        try:
            # Clean up info and gallery widgets if they exist
            if hasattr(self, "_copick_html_widget"):
                self._copick_html_widget.delete()
                delattr(self, "_copick_html_widget")

            if hasattr(self, "_copick_gallery_widget"):
                self._copick_gallery_widget.delete()
                delattr(self, "_copick_gallery_widget")

            # Also remove from ChimeraX stack if it exists
            session = self._copick.session
            main_window = session.ui.main_window
            stack_widget = main_window._stack

            # Remove any CopickInfoWidget and CopickGalleryWidget from the stack
            widgets_to_remove = []
            for i in range(stack_widget.count()):
                widget = stack_widget.widget(i)
                if hasattr(widget, "__class__") and widget.__class__.__name__ in [
                    "CopickInfoWidget",
                    "CopickGalleryWidget",
                ]:
                    widgets_to_remove.append(widget)

            for widget in widgets_to_remove:
                stack_widget.removeWidget(widget)
                widget.delete()

        except Exception:
            # Silently handle cleanup errors
            pass
