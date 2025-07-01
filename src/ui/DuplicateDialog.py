"""
Dialog for editing session ID when duplicating entities with real-time validation
"""
from Qt.QtCore import Qt
from Qt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFrame
)
from Qt.QtGui import QFont

from .validation import validate_copick_name


class DuplicateDialog(QDialog):
    """Dialog for editing session ID and user ID with real-time validation"""
    
    def __init__(self, original_name: str, suggested_name: str, parent=None, preset_user_id: str = None, default_user_id: str = None):
        super().__init__(parent)
        self.original_name = original_name
        self.suggested_name = suggested_name
        self.final_name = suggested_name
        self._preset_user_id = preset_user_id
        self._default_user_id = default_user_id
        self.final_user_id = preset_user_id or default_user_id or ""
        self._setup_ui()
        self._connect_signals()
        self._validate_all_inputs()
        
    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Duplicate Entity")
        self.setModal(True)
        self.setFixedSize(400, 250)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(f"Duplicating: {self.original_name}")
        header_font = QFont()
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Input fields layout
        input_layout = QVBoxLayout()
        input_layout.setSpacing(8)
        
        # User ID input
        user_label = QLabel("User ID:")
        input_layout.addWidget(user_label)
        
        self._user_input = QLineEdit()
        self._user_input.setText(self.final_user_id)
        self._user_input.setPlaceholderText("Enter user ID")
        input_layout.addWidget(self._user_input)
        
        # User ID validation message
        self._user_validation_label = QLabel()
        self._user_validation_label.setWordWrap(True)
        self._user_validation_label.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-size: 11px;
                padding: 4px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 4px;
            }
        """)
        self._user_validation_label.hide()
        input_layout.addWidget(self._user_validation_label)
        
        # Session ID input
        session_label = QLabel("New Session ID:")
        input_layout.addWidget(session_label)
        
        self._session_input = QLineEdit()
        self._session_input.setText(self.suggested_name)
        self._session_input.setPlaceholderText("Enter session ID")
        input_layout.addWidget(self._session_input)
        
        # Session ID validation message
        self._session_validation_label = QLabel()
        self._session_validation_label.setWordWrap(True)
        self._session_validation_label.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-size: 11px;
                padding: 4px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 4px;
            }
        """)
        self._session_validation_label.hide()
        input_layout.addWidget(self._session_validation_label)
        
        # Handle preset user ID (make read-only)
        if self._preset_user_id:
            self._user_input.setReadOnly(True)
            self._user_input.setStyleSheet("background-color: #f0f0f0; color: #666;")
            self._user_input.setToolTip("User ID is pre-configured and cannot be changed")
        
        layout.addLayout(input_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setMinimumWidth(80)
        button_layout.addWidget(self._cancel_button)
        
        self._ok_button = QPushButton("Create Duplicate")
        self._ok_button.setMinimumWidth(120)
        self._ok_button.setDefault(True)
        self._ok_button.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #888;
            }
        """)
        button_layout.addWidget(self._ok_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def _connect_signals(self):
        """Connect widget signals"""
        if not self._preset_user_id:  # Only connect if user can edit
            self._user_input.textChanged.connect(self._validate_user_id)
        self._session_input.textChanged.connect(self._validate_session_id)
        self._ok_button.clicked.connect(self.accept)
        self._cancel_button.clicked.connect(self.reject)
        
    def _validate_user_id(self, text=None):
        """Validate user ID input"""
        if self._preset_user_id:
            return  # Skip validation for preset user ID
            
        if text is None:
            text = self._user_input.text()
            
        is_valid, sanitized, error_msg = validate_copick_name(text)
        
        if is_valid:
            self._user_validation_label.hide()
            self._user_input.setStyleSheet("")
            self.final_user_id = text
        else:
            self._user_validation_label.setText(error_msg)
            self._user_validation_label.show()
            self._user_input.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """)
            
        self._update_ok_button()
        
    def _validate_session_id(self, text=None):
        """Validate session ID input"""
        if text is None:
            text = self._session_input.text()
            
        is_valid, sanitized, error_msg = validate_copick_name(text)
        
        if is_valid:
            self._session_validation_label.hide()
            self._session_input.setStyleSheet("")
            self.final_name = text
        else:
            self._session_validation_label.setText(error_msg)
            self._session_validation_label.show()
            self._session_input.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """)
            
        self._update_ok_button()
        
    def _validate_all_inputs(self):
        """Validate all inputs"""
        if not self._preset_user_id:
            self._validate_user_id()
        self._validate_session_id()
        
    def _update_ok_button(self):
        """Update OK button state based on validation"""
        user_valid = True
        session_valid = True
        
        # Check user ID validation (only if not preset)
        if not self._preset_user_id:
            user_text = self._user_input.text()
            user_valid, _, _ = validate_copick_name(user_text)
            
        # Check session ID validation
        session_text = self._session_input.text()
        session_valid, _, _ = validate_copick_name(session_text)
        
        # Enable OK button only if all validations pass
        all_valid = user_valid and session_valid
        self._ok_button.setEnabled(all_valid)
            
    def get_session_id(self) -> str:
        """Get the final session ID"""
        return self.final_name
        
    def get_user_id(self) -> str:
        """Get the final user ID"""
        return self.final_user_id
        
    def exec_(self) -> int:
        """Execute the dialog and focus the appropriate input"""
        # Focus on the first editable field
        if self._preset_user_id:
            self._session_input.setFocus()
            self._session_input.selectAll()
        else:
            self._user_input.setFocus()
            self._user_input.selectAll()
        return super().exec_()