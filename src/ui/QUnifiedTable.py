from typing import Literal, Union

from copick.models import CopickMesh, CopickPicks, CopickRun, CopickSegmentation
from Qt.QtCore import QModelIndex, Signal
from Qt.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .NewPickDialog import NewPickDialog
from .QUnifiedTableModel import QUnifiedTableModel


class QUnifiedTable(QWidget):
    """Unified table widget replacing QDoubleTable with single table and new buttons"""
    
    # Signals for button actions
    duplicateClicked = Signal(QModelIndex)
    newClicked = Signal(str, str, str)  # object_name, user_id, session_id
    
    def __init__(
        self,
        item_type: Union[Literal["picks"], Literal["meshes"], Literal["segmentations"]],
        parent=None,
    ):
        super().__init__(parent)
        self.item_type = item_type
        self._run = None
        self._model = None
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup the UI components"""
        # Main layout
        layout = QVBoxLayout()
        
        # Table view
        self._table = QTableView()
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        
        # Button layout - center aligned with tight spacing
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 2, 0, 2)  # Minimal margins
        button_layout.setSpacing(8)  # Tight spacing between buttons
        
        # Duplicate button
        self._duplicate_button = QPushButton("Duplicate")
        self._duplicate_button.setToolTip("Duplicate the selected entity")
        self._duplicate_button.setEnabled(False)  # Disabled until selection
        
        # New button  
        self._new_button = QPushButton("New")
        self._new_button.setToolTip("Create a new entity")
        
        # Center the buttons
        button_layout.addStretch()  # Left stretch
        button_layout.addWidget(self._duplicate_button)
        button_layout.addWidget(self._new_button)
        button_layout.addStretch()  # Right stretch
        
        # Add to main layout with tight spacing
        layout.setContentsMargins(0, 0, 0, 0)  # Remove default margins
        layout.setSpacing(2)  # Minimal spacing between table and buttons
        layout.addWidget(self._table)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def _connect_signals(self):
        """Connect widget signals"""
        self._duplicate_button.clicked.connect(self._on_duplicate_clicked)
        self._new_button.clicked.connect(self._on_new_clicked)
        # Note: selection model connection will be done in set_view() when model is set
        
    def set_view(self, run: CopickRun):
        """Set the run data and update the table model"""
        self._run = run
        self._model = QUnifiedTableModel(run, self.item_type)
        self._table.setModel(self._model)
        
        # Connect selection model after model is set
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        
        # Resize columns to content
        self._table.resizeColumnsToContents()
        
    def set_entity_active(self, entity: Union[CopickMesh, CopickPicks, CopickSegmentation], active: bool):
        """Update the active state of an entity"""
        if self._model:
            self._model.set_entity_active(entity, active)
            
    def update(self):
        """Refresh the table data"""
        if self._model:
            self._model.update_all()
            self._table.resizeColumnsToContents()
            
    def _on_selection_changed(self, selected, deselected):
        """Handle table selection changes"""
        has_selection = len(self._table.selectionModel().selectedRows()) > 0
        self._duplicate_button.setEnabled(has_selection)
        
    def _on_duplicate_clicked(self):
        """Handle duplicate button click"""
        selected_rows = self._table.selectionModel().selectedRows()
        if selected_rows:
            index = selected_rows[0]  # Get first selected row
            self.duplicateClicked.emit(index)
            
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
            
    def get_selected_entity(self) -> Union[CopickMesh, CopickPicks, CopickSegmentation, None]:
        """Get the currently selected entity"""
        selected_rows = self._table.selectionModel().selectedRows()
        if selected_rows and self._model:
            index = selected_rows[0]
            return self._model.get_entity(index)
        return None
        
    def get_table_view(self) -> QTableView:
        """Get the underlying table view for direct access if needed"""
        return self._table