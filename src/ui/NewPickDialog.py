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

from .validation import validate_copick_name


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
        self._validation_labels = {}
        self._setup_ui()
        self._populate_objects()
        self._connect_validation()
        
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
        
        # User ID validation label
        self._user_validation = QLabel()
        self._user_validation.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-size: 10px;
                padding: 2px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 3px;
            }
        """)
        self._user_validation.setWordWrap(True)
        self._user_validation.hide()
        form_layout.addRow("", self._user_validation)
        
        # Session ID  
        self._session_edit = QLineEdit()
        self._session_edit.setPlaceholderText("Enter session ID")
        self._session_edit.setToolTip("Session identifier for this pick session")
        form_layout.addRow("Session ID:", self._session_edit)
        
        # Session ID validation label
        self._session_validation = QLabel()
        self._session_validation.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-size: 10px;
                padding: 2px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 3px;
            }
        """)
        self._session_validation.setWordWrap(True)
        self._session_validation.hide()
        form_layout.addRow("", self._session_validation)
        
        # Info label
        info_label = QLabel("Create a new pick entity with the specified parameters.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-style: italic;")
        
        # Buttons
        self._button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._ok_button = self._button_box.button(QDialogButtonBox.Ok)
        self._ok_button.setText("Create")
        self._ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #888;
            }
        """)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        
        # Layout
        layout.addWidget(info_label)
        layout.addLayout(form_layout)
        layout.addStretch()
        layout.addWidget(self._button_box)
        
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
            
        # Set initial focus
        if self._preset_user_id:
            self._session_edit.setFocus()
        else:
            self._user_edit.setFocus()
    
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
        
    def _connect_validation(self):
        """Connect validation signals"""
        if not self._preset_user_id:  # Only validate if user can edit
            self._user_edit.textChanged.connect(self._validate_user_id)
        self._session_edit.textChanged.connect(self._validate_session_id)
        
        # Initial validation
        if not self._preset_user_id:
            self._validate_user_id()
        self._validate_session_id()
        
    def _validate_user_id(self, text=None):
        """Validate user ID input"""
        if self._preset_user_id:
            return  # Skip validation for preset user ID
            
        if text is None:
            text = self._user_edit.text()
            
        is_valid, sanitized, error_msg = validate_copick_name(text)
        
        if is_valid:
            self._user_validation.hide()
            self._user_edit.setStyleSheet("")
        else:
            self._user_validation.setText(error_msg)
            self._user_validation.show()
            self._user_edit.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """)
            
        self._update_ok_button()
        
    def _validate_session_id(self, text=None):
        """Validate session ID input"""
        if text is None:
            text = self._session_edit.text()
            
        is_valid, sanitized, error_msg = validate_copick_name(text)
        
        if is_valid:
            self._session_validation.hide()
            self._session_edit.setStyleSheet("")
        else:
            self._session_validation.setText(error_msg)
            self._session_validation.show()
            self._session_edit.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """)
            
        self._update_ok_button()
        
    def _update_ok_button(self):
        """Update OK button state based on validation"""
        user_valid = True
        session_valid = True
        
        # Check user ID validation (only if not preset)
        if not self._preset_user_id:
            user_text = self._user_edit.text()
            user_valid, _, _ = validate_copick_name(user_text)
            
        # Check session ID validation
        session_text = self._session_edit.text()
        session_valid, _, _ = validate_copick_name(session_text)
        
        # Check if object is selected
        object_selected = bool(self._object_combo.currentText())
        
        # Enable OK button only if all validations pass
        all_valid = user_valid and session_valid and object_selected
        self._ok_button.setEnabled(all_valid)