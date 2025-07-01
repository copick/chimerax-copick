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
    """Dialog for editing session ID with real-time validation"""
    
    def __init__(self, original_name: str, suggested_name: str, parent=None):
        super().__init__(parent)
        self.original_name = original_name
        self.suggested_name = suggested_name
        self.final_name = suggested_name
        self._setup_ui()
        self._connect_signals()
        self._validate_current_input()
        
    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Duplicate Entity")
        self.setModal(True)
        self.setFixedSize(400, 180)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(f"Duplicating: {self.original_name}")
        header_font = QFont()
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Session ID input
        input_layout = QVBoxLayout()
        input_layout.setSpacing(4)
        
        session_label = QLabel("New Session ID:")
        input_layout.addWidget(session_label)
        
        self._session_input = QLineEdit()
        self._session_input.setText(self.suggested_name)
        self._session_input.selectAll()
        input_layout.addWidget(self._session_input)
        
        # Validation message
        self._validation_label = QLabel()
        self._validation_label.setWordWrap(True)
        self._validation_label.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-size: 11px;
                padding: 4px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 4px;
            }
        """)
        self._validation_label.hide()
        input_layout.addWidget(self._validation_label)
        
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
        self._session_input.textChanged.connect(self._validate_current_input)
        self._ok_button.clicked.connect(self.accept)
        self._cancel_button.clicked.connect(self.reject)
        
    def _validate_current_input(self):
        """Validate the current input and update UI accordingly"""
        current_text = self._session_input.text()
        is_valid, sanitized, error_msg = validate_copick_name(current_text)
        
        if is_valid:
            # Valid input
            self._validation_label.hide()
            self._ok_button.setEnabled(True)
            self._session_input.setStyleSheet("")
            self.final_name = current_text
        else:
            # Invalid input
            self._validation_label.setText(error_msg)
            self._validation_label.show()
            self._ok_button.setEnabled(False)
            self._session_input.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """)
            
    def get_session_id(self) -> str:
        """Get the final session ID"""
        return self.final_name
        
    def exec_(self) -> int:
        """Execute the dialog and focus the input"""
        self._session_input.setFocus()
        return super().exec_()