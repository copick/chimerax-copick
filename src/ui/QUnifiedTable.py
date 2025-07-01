from typing import Literal, Union

from copick.models import CopickMesh, CopickPicks, CopickRun, CopickSegmentation
from Qt.QtCore import QModelIndex, Signal, QSortFilterProxyModel, Qt, QEvent
from Qt.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .NewPickDialog import NewPickDialog
from .QUnifiedTableModel import QUnifiedTableModel
from .DuplicateSettingsOverlay import DuplicateSettingsOverlay
from .DuplicateDialog import DuplicateDialog
from .validation import generate_smart_copy_name


class TableFilterProxyModel(QSortFilterProxyModel):
    """Custom proxy model for table search across user, object, and session columns"""

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Override to search across user, object, and session columns"""
        if not self.filterRegularExpression().pattern():
            return True

        source_model = self.sourceModel()
        if not source_model:
            return False

        # Check all three columns (User/Tool, Object, Session)
        for column in range(3):
            index = source_model.index(source_row, column, source_parent)
            if index.isValid():
                data = source_model.data(index, Qt.ItemDataRole.DisplayRole)
                if data and self.filterRegularExpression().match(str(data)).hasMatch():
                    return True

        return False


class QUnifiedTable(QWidget):
    """Unified table widget replacing QDoubleTable with single table and new buttons"""

    # Signals for button actions
    duplicateClicked = Signal(QModelIndex)
    newClicked = Signal(str, str, str)  # object_name, user_id, session_id
    deleteClicked = Signal(QModelIndex)

    def __init__(
        self,
        item_type: Union[Literal["picks"], Literal["meshes"], Literal["segmentations"]],
        parent=None,
    ):
        super().__init__(parent)
        self.item_type = item_type
        self._run = None
        self._source_model = None
        self._filter_model = None
        self._duplicate_mode = "ask"  # Default duplicate behavior
        self._custom_suffix = "-copy"  # Default custom suffix
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the UI components"""
        # Main layout
        layout = QVBoxLayout()

        # Create container for table with overlay search
        table_container = QWidget()
        table_container_layout = QVBoxLayout()
        table_container_layout.setContentsMargins(0, 0, 0, 0)
        table_container_layout.setSpacing(0)

        # Table view
        self._table = QTableView()
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))

        # Create overlay search widget (floating at bottom-left)
        self._search_overlay = QWidget(self._table)
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
        self._search_input.setPlaceholderText(f"Search {self.item_type}...")
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

        # Clear/Close button
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
        self._search_overlay.hide()

        # Define common dark style for floating buttons (works in light and dark mode)
        button_style = """
            QPushButton {
                background-color: rgba(60, 60, 60, 220);
                border: 1px solid rgba(80, 80, 80, 180);
                border-radius: 15px;
                font-size: 14px;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 240);
                border: 1px solid rgba(100, 100, 100, 200);
            }
            QPushButton:disabled {
                background-color: rgba(40, 40, 40, 150);
                color: rgba(150, 150, 150, 150);
                border: 1px solid rgba(60, 60, 60, 120);
            }
        """

        # Search toggle button (floating at bottom-right corner, hidden initially)
        self._search_toggle = QPushButton("🔍")
        self._search_toggle.setParent(self._table)
        self._search_toggle.setMaximumSize(30, 30)
        self._search_toggle.setToolTip(f"Search {self.item_type}")
        self._search_toggle.setStyleSheet(button_style)
        self._search_toggle.hide()
        
        # Settings button (will be moved to top bar by parent widget)
        self._settings_button = QPushButton("⚙")
        self._settings_button.setToolTip("Table settings")

        # Install event filter for hover behavior
        self._table.installEventFilter(self)
        self._table.setMouseTracking(True)

        # Add table to container
        table_container_layout.addWidget(self._table)
        table_container.setLayout(table_container_layout)
        
        # Create floating action buttons (overlaid on table)
        self._new_button = QPushButton("📄")
        self._new_button.setParent(self._table)
        self._new_button.setMaximumSize(30, 30)
        self._new_button.setToolTip("Create a new entity")
        self._new_button.setStyleSheet(button_style)
        self._new_button.hide()
        
        # Copy button
        self._duplicate_button = QPushButton("📋")
        self._duplicate_button.setParent(self._table)
        self._duplicate_button.setMaximumSize(30, 30)
        self._duplicate_button.setToolTip("Copy the selected entity")
        self._duplicate_button.setEnabled(False)  # Disabled until selection
        self._duplicate_button.setStyleSheet(button_style)
        self._duplicate_button.hide()
        
        # Delete button
        self._delete_button = QPushButton("❌")
        self._delete_button.setParent(self._table)
        self._delete_button.setMaximumSize(30, 30)
        self._delete_button.setToolTip("Delete the selected entity")
        self._delete_button.setEnabled(False)  # Disabled until selection
        self._delete_button.setStyleSheet(button_style)
        self._delete_button.hide()

        # Create settings overlay (hidden initially) - use None as parent so it's a top-level window
        self._settings_overlay = DuplicateSettingsOverlay(None)
        self._settings_overlay.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._settings_overlay.hide()
        
        # Track delete confirmation setting
        self._delete_confirmation = True  # Show confirmation dialog by default

        # Add to main layout (no button layout needed anymore)
        layout.setContentsMargins(0, 0, 0, 0)  # Remove default margins
        layout.setSpacing(0)  # No spacing needed
        layout.addWidget(table_container)

        self.setLayout(layout)

    def _connect_signals(self):
        """Connect widget signals"""
        self._duplicate_button.clicked.connect(self._on_duplicate_clicked)
        self._new_button.clicked.connect(self._on_new_clicked)
        self._delete_button.clicked.connect(self._on_delete_clicked)

        # Search functionality
        self._search_toggle.clicked.connect(self._toggle_search)
        self._search_input.textChanged.connect(self._filter_table)
        self._clear_button.clicked.connect(self._clear_and_close_search)

        # Settings functionality
        self._settings_button.clicked.connect(self._toggle_settings)
        self._settings_overlay.settingsChanged.connect(self._on_settings_changed)

        # Note: selection model connection will be done in set_view() when model is set

    def set_view(self, run: CopickRun):
        """Set the run data and update the table model"""
        self._run = run
        self._source_model = QUnifiedTableModel(run, self.item_type)

        # Set up filter proxy model for search functionality
        self._filter_model = TableFilterProxyModel()
        self._filter_model.setSourceModel(self._source_model)
        self._filter_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._filter_model.setFilterRole(Qt.DisplayRole)

        self._table.setModel(self._filter_model)

        # Connect selection model after model is set
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Resize columns to content
        self._table.resizeColumnsToContents()

    def set_entity_active(self, entity: Union[CopickMesh, CopickPicks, CopickSegmentation], active: bool):
        """Update the active state of an entity"""
        if self._source_model:
            self._source_model.set_entity_active(entity, active)

    def update(self):
        """Refresh the table data"""
        if self._source_model:
            self._source_model.update_all()
            self._table.resizeColumnsToContents()

    def _on_selection_changed(self, selected, deselected):
        """Handle table selection changes"""
        has_selection = len(self._table.selectionModel().selectedRows()) > 0
        self._duplicate_button.setEnabled(has_selection)
        self._delete_button.setEnabled(has_selection)

    def _on_duplicate_clicked(self):
        """Handle duplicate button click with settings-based behavior"""
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return

        proxy_index = selected_rows[0]
        # Map proxy index to source index
        if self._filter_model:
            source_index = self._filter_model.mapToSource(proxy_index)
        else:
            source_index = proxy_index

        # Get the entity to determine current session ID
        entity = self._source_model.get_entity(source_index) if self._source_model else None
        if not entity:
            return

        original_session_id = getattr(entity, "session_id", "session")

        if self._duplicate_mode == "ask":
            # Show dialog for session ID input
            suggested_name = f"{original_session_id}-copy1"
            
            # Get object name and color information for the dialog
            object_name = ""
            object_color = (128, 128, 128, 255)  # Default gray
            
            if hasattr(entity, 'pickable_object_name'):
                object_name = entity.pickable_object_name
            elif hasattr(entity, 'name'):
                object_name = entity.name
                
            if hasattr(entity, 'color'):
                # Convert color to RGBA format with full alpha
                entity_color = list(entity.color)
                if len(entity_color) == 3:
                    entity_color.append(255)  # Add alpha if missing
                object_color = tuple(entity_color)
            
            dialog = DuplicateDialog(
                original_session_id, 
                suggested_name, 
                self, 
                object_name=object_name, 
                object_color=object_color
            )
            if dialog.exec_() == DuplicateDialog.Accepted:
                new_session_id = dialog.get_session_id()
                self._emit_duplicate_with_session_id(source_index, new_session_id)

        elif self._duplicate_mode == "auto_increment":
            # Generate smart auto-increment name
            existing_names = self._get_existing_session_ids()
            new_session_id = generate_smart_copy_name(original_session_id, existing_names)
            self._emit_duplicate_with_session_id(source_index, new_session_id)

        elif self._duplicate_mode == "simple_copy":
            # Simple -copy suffix
            new_session_id = f"{original_session_id}-copy"
            self._emit_duplicate_with_session_id(source_index, new_session_id)

        elif self._duplicate_mode == "custom_suffix":
            # Custom suffix from settings
            new_session_id = f"{original_session_id}{self._custom_suffix}"
            self._emit_duplicate_with_session_id(source_index, new_session_id)

    def _emit_duplicate_with_session_id(self, source_index, session_id):
        """Emit duplicate signal with custom session ID"""
        # For now, emit the original signal - this will need to be enhanced
        # to pass the custom session ID to the handler
        self.duplicateClicked.emit(source_index)

    def _get_existing_session_ids(self) -> list:
        """Get list of existing session IDs for smart naming"""
        if not self._source_model:
            return []

        session_ids = []
        for row in range(self._source_model.rowCount()):
            index = self._source_model.index(row, 2)  # Session ID column
            session_id = self._source_model.data(index, Qt.ItemDataRole.DisplayRole)
            if session_id:
                session_ids.append(str(session_id))
        return session_ids

    def _on_new_clicked(self):
        """Handle new button click - show dialog for new entity creation"""
        if not self._run:
            return

        # Show dialog based on item type
        if self.item_type == "picks":
            # Get preset user ID from root if available
            preset_user_id = None
            if self._run.root and self._run.root.user_id:
                preset_user_id = self._run.root.user_id

            dialog = NewPickDialog(self._run, self, preset_user_id)
            if dialog.exec_() == NewPickDialog.Accepted:
                selection = dialog.get_selection()
                if selection:
                    object_name, user_id, session_id = selection
                    self.newClicked.emit(object_name, user_id, session_id)
        else:
            # For meshes and segmentations, we could implement similar dialogs
            # For now, emit with default values
            self.newClicked.emit("", "", "")
    
    def _on_delete_clicked(self):
        """Handle delete button click with optional confirmation dialog"""
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return

        proxy_index = selected_rows[0]
        # Map proxy index to source index
        if self._filter_model:
            source_index = self._filter_model.mapToSource(proxy_index)
        else:
            source_index = proxy_index

        # Get the entity to show in confirmation dialog
        entity = self._source_model.get_entity(source_index) if self._source_model else None
        if not entity:
            return

        # Show confirmation dialog if enabled
        if self._delete_confirmation:
            entity_type = self.item_type.rstrip('s')  # Remove 's' from 'picks', 'meshes', 'segmentations'
            
            # Get object type information
            object_type = ""
            if hasattr(entity, 'pickable_object_name'):
                object_type = f" ({entity.pickable_object_name})"
            elif hasattr(entity, 'name'):
                object_type = f" ({entity.name})"
            
            entity_info = f"{getattr(entity, 'user_id', 'Unknown')} - {getattr(entity, 'session_id', 'Unknown')}{object_type}"
            
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle(f"Delete {entity_type.title()}")
            msg_box.setText(f"Are you sure you want to delete this {entity_type}?")
            msg_box.setInformativeText(f"{entity_info}\n\nThis action cannot be undone.")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            if msg_box.exec_() != QMessageBox.StandardButton.Yes:
                return
        
        # Emit the delete signal
        self.deleteClicked.emit(source_index)

    def get_selected_entity(self) -> Union[CopickMesh, CopickPicks, CopickSegmentation, None]:
        """Get the currently selected entity"""
        selected_rows = self._table.selectionModel().selectedRows()
        if selected_rows and self._source_model:
            proxy_index = selected_rows[0]
            # Map proxy index to source index
            if self._filter_model:
                source_index = self._filter_model.mapToSource(proxy_index)
                return self._source_model.get_entity(source_index)
            else:
                return self._source_model.get_entity(proxy_index)
        return None

    def get_table_view(self) -> QTableView:
        """Get the underlying table view for direct access if needed"""
        return self._table

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
        """Position the search overlay at the bottom-left of the table view"""
        if hasattr(self, "_search_overlay") and hasattr(self, "_table"):
            table_height = self._table.height()
            table_width = self._table.width()
            overlay_width = min(240, table_width - 60)  # Leave space for search toggle button
            overlay_height = 32  # Fixed height for search overlay

            # Position at bottom-left with some margin
            x = 10
            y = table_height - overlay_height - 15

            self._search_overlay.setGeometry(x, y, overlay_width, overlay_height)

    def _position_search_toggle(self):
        """Position the search toggle button at bottom-right corner"""
        if hasattr(self, "_search_toggle") and hasattr(self, "_table"):
            table_width = self._table.width()
            table_height = self._table.height()
            button_size = 30

            # Position at bottom-right corner with margin
            x = table_width - button_size - 10
            y = table_height - button_size - 15

            self._search_toggle.setGeometry(x, y, button_size, button_size)
    
    def _position_action_buttons(self):
        """Position the floating action buttons in a vertical stack above search toggle"""
        if hasattr(self, "_table"):
            table_width = self._table.width()
            table_height = self._table.height()
            button_size = 30
            margin = 10
            spacing = 5  # Space between buttons

            # Position from bottom-right, stacking upward
            x = table_width - button_size - margin
            
            # Start with search toggle position and stack upward
            search_y = table_height - button_size - 15
            
            # Delete button (above search)
            delete_y = search_y - button_size - spacing
            self._delete_button.setGeometry(x, delete_y, button_size, button_size)
            
            # Copy button (above delete)
            copy_y = delete_y - button_size - spacing
            self._duplicate_button.setGeometry(x, copy_y, button_size, button_size)
            
            # New button (above copy)
            new_y = copy_y - button_size - spacing
            self._new_button.setGeometry(x, new_y, button_size, button_size)

    def eventFilter(self, obj, event):
        """Handle resize events to reposition floating elements and mouse hover events"""
        if obj == self._table:
            if event.type() == QEvent.Type.Resize:
                self._position_search_toggle()
                self._position_action_buttons()
                if self._search_overlay.isVisible():
                    self._position_search_overlay()
            elif event.type() == QEvent.Type.Enter:
                # Show action buttons and search toggle when mouse enters table view
                if not self._search_overlay.isVisible():
                    self._search_toggle.show()
                    self._position_search_toggle()
                
                # Always show action buttons on hover
                self._new_button.show()
                self._duplicate_button.show()
                self._delete_button.show()
                self._position_action_buttons()
                
            elif event.type() == QEvent.Type.Leave:
                # Hide search toggle when mouse leaves table view (unless search is active)
                if not self._search_overlay.isVisible():
                    self._search_toggle.hide()
                
                # Hide action buttons when mouse leaves
                self._new_button.hide()
                self._duplicate_button.hide()
                self._delete_button.hide()
                
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        """Handle resize events to reposition overlays"""
        super().resizeEvent(event)
        if hasattr(self, "_settings_overlay") and self._settings_overlay.isVisible():
            self._position_settings_overlay()

    def _filter_table(self, text: str):
        """Filter the table view based on search text"""
        if self._filter_model:
            self._filter_model.setFilterFixedString(text)

    def _clear_search(self):
        """Clear the search input and reset the filter"""
        self._search_input.clear()
        if self._filter_model:
            self._filter_model.setFilterFixedString("")

    def _clear_and_close_search(self):
        """Clear the search input, reset the filter, and close the overlay"""
        self._clear_search()
        self._search_overlay.hide()

    def _toggle_settings(self):
        """Toggle the visibility of the settings overlay"""
        if self._settings_overlay.isVisible():
            self._settings_overlay.hide()
        else:
            self._position_settings_overlay()
            self._settings_overlay.show()
            self._settings_overlay.raise_()
            self._settings_overlay.activateWindow()

    def _position_settings_overlay(self):
        """Position the settings overlay to the left of the floating settings button"""
        if hasattr(self, "_settings_overlay") and hasattr(self, "_settings_button"):
            # Get button position in global coordinates
            button_global_pos = self._settings_button.mapToGlobal(self._settings_button.rect().topLeft())

            # Position overlay to the left of the floating button
            overlay_width = 280
            overlay_height = 140
            x = button_global_pos.x() - overlay_width - 10  # Gap from button
            y = button_global_pos.y()

            # Get screen geometry to ensure we stay on screen
            from Qt.QtWidgets import QApplication

            screen = QApplication.primaryScreen().geometry()

            # Ensure we don't go off-screen to the left
            if x < screen.left() + 10:
                x = screen.left() + 10

            # Ensure vertical positioning is within screen bounds
            if y + overlay_height > screen.bottom() - 10:
                y = screen.bottom() - overlay_height - 10
            if y < screen.top() + 10:
                y = screen.top() + 10

            self._settings_overlay.move(x, y)

    def _on_settings_changed(self, mode: str, custom_suffix: str):
        """Handle settings change"""
        self._duplicate_mode = mode
        self._custom_suffix = custom_suffix
        # Update settings button tooltip to show current mode
        mode_desc = self._settings_overlay.get_mode_description(mode)
        self._settings_button.setToolTip(f"Duplicate settings\nCurrent: {mode_desc}")

    def get_duplicate_mode(self) -> str:
        """Get current duplicate mode"""
        return self._duplicate_mode

    def set_duplicate_mode(self, mode: str):
        """Set duplicate mode"""
        self._duplicate_mode = mode
        self._settings_overlay.set_current_mode(mode)
        custom_suffix = self._settings_overlay.get_custom_suffix()
        self._on_settings_changed(mode, custom_suffix)
        
    def get_delete_confirmation(self) -> bool:
        """Get current delete confirmation setting"""
        return self._delete_confirmation
    
    def set_delete_confirmation(self, enabled: bool):
        """Set delete confirmation setting"""
        self._delete_confirmation = enabled
    
    def get_settings_button(self) -> QPushButton:
        """Get the settings button for placement in parent layout"""
        return self._settings_button
