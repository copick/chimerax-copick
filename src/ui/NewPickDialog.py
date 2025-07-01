from typing import Optional, Tuple

from copick.models import CopickRun
from Qt.QtCore import Qt
from Qt.QtGui import QColor, QPalette
from Qt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class ColoredComboBox(QComboBox):
    """Combobox that displays items with colored backgrounds"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = {}
    
    def addColoredItem(self, text: str, color: Tuple[int, int, int, int]):
        """Add an item with a colored background"""
        self.addItem(text)
        self._colors[self.count() - 1] = color
    
    def paintEvent(self, event):
        super().paintEvent(event)
    
    def showPopup(self):
        """Override to apply colors when dropdown opens"""
        super().showPopup()
        # Apply colors to dropdown items
        for i in range(self.count()):
            if i in self._colors:
                color = QColor(*self._colors[i])
                color.setAlpha(100)  # Semi-transparent
                self.view().model().setData(
                    self.view().model().index(i, 0),
                    color,
                    Qt.BackgroundRole
                )


class NewPickDialog(QDialog):
    """Dialog for creating new pick entities with object, user, and session selection"""
    
    def __init__(self, run: CopickRun, parent=None, preset_user_id: str = None):
        super().__init__(parent)
        self._run = run
        self._preset_user_id = preset_user_id
        self._setup_ui()
        self._populate_objects()
        
    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Create New Pick")
        self.setModal(True)
        self.resize(400, 200)
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # Object selection
        self._object_combo = ColoredComboBox()
        self._object_combo.setToolTip("Select the pickable object type")
        form_layout.addRow("Object:", self._object_combo)
        
        # User ID
        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("Enter user ID")
        self._user_edit.setToolTip("User identifier for this pick session")
        form_layout.addRow("User ID:", self._user_edit)
        
        # Session ID  
        self._session_edit = QLineEdit()
        self._session_edit.setPlaceholderText("Enter session ID")
        self._session_edit.setToolTip("Session identifier for this pick session")
        form_layout.addRow("Session ID:", self._session_edit)
        
        # Info label
        info_label = QLabel("Create a new pick entity with the specified parameters.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-style: italic;")
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Layout
        layout.addWidget(info_label)
        layout.addLayout(form_layout)
        layout.addStretch()
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # Set default values and handle preset user ID
        if self._preset_user_id:
            # Use preset user ID and make field read-only
            self._user_edit.setText(self._preset_user_id)
            self._user_edit.setReadOnly(True)
            self._user_edit.setStyleSheet("background-color: #f0f0f0; color: #666;")
            self._user_edit.setToolTip("User ID is pre-configured and cannot be changed")
        elif self._run.root.user_id:
            # Use root user ID as default but allow editing
            self._user_edit.setText(self._run.root.user_id)
    
    def _populate_objects(self):
        """Populate the object combobox with available pickable objects"""
        if not self._run or not self._run.root:
            return
            
        root = self._run.root
        
        # Get all pickable objects
        objects = root.pickable_objects
        
        for obj in objects:
            # Add object with its color
            color = obj.color if obj.color else (128, 128, 128, 255)  # Default gray
            self._object_combo.addColoredItem(obj.name, color)
    
    def get_selection(self) -> Optional[Tuple[str, str, str]]:
        """Get the selected values from the dialog
        
        Returns:
            Tuple of (object_name, user_id, session_id) or None if cancelled
        """
        if self.result() == QDialog.Accepted:
            object_name = self._object_combo.currentText()
            user_id = self._user_edit.text().strip()
            session_id = self._session_edit.text().strip()
            
            # Validate inputs
            if not object_name:
                return None
            if not user_id:
                return None
            if not session_id:
                return None
                
            return (object_name, user_id, session_id)
        return None
    
    def get_selected_object_name(self) -> str:
        """Get the currently selected object name"""
        return self._object_combo.currentText()
    
    def get_user_id(self) -> str:
        """Get the entered user ID"""
        return self._user_edit.text().strip()
    
    def get_session_id(self) -> str:
        """Get the entered session ID"""  
        return self._session_edit.text().strip()