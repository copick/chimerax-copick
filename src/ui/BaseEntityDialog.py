"""
Base dialog class for object creation and editing with common validation functionality
"""

from typing import Tuple

from copick_shared_ui.util.validation import validate_copick_name
from Qt.QtCore import Qt
from Qt.QtGui import QColor, QFont
from Qt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
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
                self.view().model().setData(self.view().model().index(i, 0), color, Qt.BackgroundRole)


class BaseEntityDialog(QDialog):
    """Base dialog class for object creation and editing"""

    def __init__(self, parent=None, preset_user_id: str = None, default_user_id: str = None):
        super().__init__(parent)
        self._preset_user_id = preset_user_id
        self._default_user_id = default_user_id or "ArtiaX"  # Default to ArtiaX if no default provided
        self._setup_common_ui()
        self._setup_specific_ui()
        self._connect_signals()
        self._populate_initial_data()
        self._validate_all_inputs()

    def _setup_common_ui(self):
        """Setup the common UI elements"""
        self.setModal(True)
        self.setMinimumSize(400, 200)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().MinimumExpanding)

        self._main_layout = QVBoxLayout()
        self._main_layout.setContentsMargins(12, 12, 12, 12)
        self._main_layout.setSpacing(8)

        # Header
        self._header = QLabel()
        header_font = QFont()
        header_font.setBold(True)
        self._header.setFont(header_font)
        self._main_layout.addWidget(self._header)

        # Form layout for input fields
        self._form_layout = QFormLayout()
        self._form_layout.setSpacing(6)

        # User ID input
        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("Enter user ID")
        self._user_edit.setToolTip("User identifier for this object")

        # Set default user ID
        default_user = self._preset_user_id or self._default_user_id
        if default_user:
            self._user_edit.setText(default_user)

        # Handle preset user ID (make read-only)
        if self._preset_user_id:
            self._user_edit.setReadOnly(True)
            self._user_edit.setStyleSheet("background-color: #f0f0f0; color: #666;")
            self._user_edit.setToolTip("User ID is pre-configured and cannot be changed")

        self._form_layout.addRow("User ID:", self._user_edit)

        # User ID validation label
        self._user_validation = QLabel()
        self._user_validation.setStyleSheet(
            """
            QLabel {
                color: #d32f2f;
                font-size: 10px;
                padding: 2px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 3px;
            }
        """,
        )
        self._user_validation.setWordWrap(True)
        self._user_validation.hide()
        self._form_layout.addRow("", self._user_validation)

        # Session ID input
        self._session_edit = QLineEdit()
        self._session_edit.setPlaceholderText("Enter session ID")
        self._session_edit.setToolTip("Session identifier for this object")
        self._form_layout.addRow("Session ID:", self._session_edit)

        # Session ID validation label
        self._session_validation = QLabel()
        self._session_validation.setStyleSheet(
            """
            QLabel {
                color: #d32f2f;
                font-size: 10px;
                padding: 2px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 3px;
            }
        """,
        )
        self._session_validation.setWordWrap(True)
        self._session_validation.hide()
        self._form_layout.addRow("", self._session_validation)

        self._main_layout.addLayout(self._form_layout)

        # Info label
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: gray; font-style: italic;")
        self._info_label.setAlignment(Qt.AlignCenter)
        self._main_layout.addWidget(self._info_label)

        # Add stretch before buttons
        self._main_layout.addStretch()

        # Buttons
        self._setup_buttons()

        self.setLayout(self._main_layout)

    def _setup_buttons(self):
        """Setup dialog buttons"""
        # For NewPickDialog style (using QDialogButtonBox)
        if self._use_dialog_button_box():
            self._button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self._ok_button = self._button_box.button(QDialogButtonBox.Ok)
            self._ok_button.setText(self._get_ok_button_text())
            self._ok_button.setStyleSheet(
                """
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
            """,
            )
            self._button_box.accepted.connect(self.accept)
            self._button_box.rejected.connect(self.reject)
            self._main_layout.addWidget(self._button_box)
        else:
            # For DuplicateDialog style (custom buttons with separator)
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            self._main_layout.addWidget(separator)

            button_layout = QHBoxLayout()
            button_layout.addStretch()

            cancel_button = QPushButton("Cancel")
            cancel_button.setMinimumWidth(80)
            button_layout.addWidget(cancel_button)

            self._ok_button = QPushButton(self._get_ok_button_text())
            self._ok_button.setMinimumWidth(120)
            self._ok_button.setDefault(True)
            self._ok_button.setStyleSheet(
                """
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
            """,
            )
            button_layout.addWidget(self._ok_button)

            self._ok_button.clicked.connect(self.accept)
            cancel_button.clicked.connect(self.reject)

            self._main_layout.addLayout(button_layout)

    def _connect_signals(self):
        """Connect validation signals"""
        if not self._preset_user_id:  # Only validate if user can edit
            self._user_edit.textChanged.connect(self._validate_user_id)
        self._session_edit.textChanged.connect(self._validate_session_id)

    def _validate_user_id(self, text=None):
        """Validate user ID input"""
        if self._preset_user_id:
            return  # Skip validation for preset user ID

        if text is None:
            text = self._user_edit.text()

        is_valid, sanitized, error_msg = validate_copick_name(text)

        if is_valid:
            self._user_validation.hide()
            self._user_edit.setStyleSheet("" if not self._preset_user_id else "background-color: #f0f0f0; color: #666;")
        else:
            self._user_validation.setText(error_msg)
            self._user_validation.show()
            self._user_edit.setStyleSheet(
                """
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """,
            )

        self._update_ok_button()
        self.adjustSize()

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
            self._session_edit.setStyleSheet(
                """
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """,
            )

        self._update_ok_button()
        self.adjustSize()

    def _validate_all_inputs(self):
        """Validate all inputs"""
        if not self._preset_user_id:
            self._validate_user_id()
        self._validate_session_id()
        self._validate_additional_fields()

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

        # Check additional validation from subclasses
        additional_valid = self._validate_additional_fields()

        # Enable OK button only if all validations pass
        all_valid = user_valid and session_valid and additional_valid
        self._ok_button.setEnabled(all_valid)

    def get_user_id(self) -> str:
        """Get the entered user ID"""
        return self._user_edit.text().strip()

    def get_session_id(self) -> str:
        """Get the entered session ID"""
        return self._session_edit.text().strip()

    def exec_(self) -> int:
        """Execute the dialog and focus the appropriate input"""
        # Focus on the first editable field
        if self._preset_user_id:
            self._session_edit.setFocus()
            self._session_edit.selectAll()
        else:
            self._user_edit.setFocus()
            self._user_edit.selectAll()
        return super().exec_()

    # Methods to be implemented by subclasses
    def _setup_specific_ui(self):
        """Setup UI elements specific to the dialog type"""
        pass

    def _populate_initial_data(self):
        """Populate initial data specific to the dialog type"""
        pass

    def _validate_additional_fields(self) -> bool:
        """Validate additional fields specific to the dialog type"""
        return True

    def _get_ok_button_text(self) -> str:
        """Get the text for the OK button"""
        return "OK"

    def _use_dialog_button_box(self) -> bool:
        """Whether to use QDialogButtonBox or custom buttons"""
        return True
