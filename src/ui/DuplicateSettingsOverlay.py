"""
Duplicate settings overlay menu for configuring duplicate behavior
"""
from Qt.QtCore import Signal
from Qt.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class DuplicateSettingsOverlay(QWidget):
    """Overlay widget for configuring duplicate behavior settings"""

    # Signal emitted when settings change
    settingsChanged = Signal(str, str)  # Emits the selected mode and custom suffix

    MODES = {
        "ask": "Always ask for session ID",
        "auto_increment": "Smart auto-increment (-copy1, -copy2, etc.)",
        "simple_copy": "Simple suffix (-copy)",
        "custom_suffix": "Custom suffix",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "ask"  # Default mode
        self._custom_suffix = "-copy"  # Default custom suffix
        self._setup_ui()
        self._connect_signals()
        self.hide()

    def _setup_ui(self):
        """Setup the overlay UI"""
        # Set fixed size to ensure visibility
        self.setFixedSize(300, 180)

        self.setStyleSheet(
            """
            DuplicateSettingsOverlay {
                background-color: #2d2d2d;
                border: 2px solid #666;
                border-radius: 8px;
                color: white;
            }
            QRadioButton {
                color: white;
                font-size: 11px;
                padding: 6px 8px;
                spacing: 8px;
                background-color: transparent;
            }
            QRadioButton:hover {
                background-color: rgba(255, 255, 255, 25);
                border-radius: 4px;
            }
            QRadioButton::indicator {
                width: 12px;
                height: 12px;
            }
            QRadioButton::indicator::unchecked {
                border: 2px solid #888;
                border-radius: 6px;
                background-color: transparent;
            }
            QRadioButton::indicator::checked {
                border: 2px solid #4A90E2;
                border-radius: 6px;
                background-color: #4A90E2;
            }
            QLabel {
                color: #ddd;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                background-color: transparent;
            }
            QLineEdit {
                background-color: #3d3d3d;
                border: 1px solid #666;
                border-radius: 4px;
                color: white;
                font-size: 11px;
                padding: 4px 8px;
                min-width: 100px;
            }
            QLineEdit:focus {
                border: 2px solid #4A90E2;
            }
            QLineEdit:disabled {
                background-color: #2a2a2a;
                color: #888;
                border: 1px solid #444;
            }
            QPushButton {
                background-color: #4A90E2;
                border: 1px solid #357ABD;
                border-radius: 4px;
                color: white;
                font-size: 10px;
                padding: 4px 12px;
                font-weight: bold;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #357ABD;
                border: 1px solid #2980B9;
            }
        """,
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Header
        header = QLabel("Duplicate Behavior")
        layout.addWidget(header)

        # Radio button group
        self._button_group = QButtonGroup()

        # Option 1: Always ask
        self._ask_radio = QRadioButton("Always ask for session ID")
        self._ask_radio.setChecked(True)  # Default
        self._button_group.addButton(self._ask_radio, 0)
        layout.addWidget(self._ask_radio)

        # Option 2: Smart auto-increment
        self._auto_radio = QRadioButton("Smart auto-increment (-copy1, -copy2, etc.)")
        self._button_group.addButton(self._auto_radio, 1)
        layout.addWidget(self._auto_radio)

        # Option 3: Simple copy
        self._simple_radio = QRadioButton("Simple suffix (-copy)")
        self._button_group.addButton(self._simple_radio, 2)
        layout.addWidget(self._simple_radio)

        # Option 4: Custom suffix
        custom_layout = QHBoxLayout()
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(8)

        self._custom_radio = QRadioButton("Custom suffix:")
        self._button_group.addButton(self._custom_radio, 3)
        custom_layout.addWidget(self._custom_radio)

        self._custom_suffix_input = QLineEdit()
        self._custom_suffix_input.setText(self._custom_suffix)
        self._custom_suffix_input.setEnabled(False)  # Initially disabled
        self._custom_suffix_input.setMaximumWidth(80)
        custom_layout.addWidget(self._custom_suffix_input)

        custom_layout.addStretch()
        layout.addLayout(custom_layout)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._close_button = QPushButton("Close")
        button_layout.addWidget(self._close_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _connect_signals(self):
        """Connect widget signals"""
        self._button_group.buttonClicked.connect(self._on_selection_changed)
        self._close_button.clicked.connect(self.hide)
        self._custom_suffix_input.textChanged.connect(self._on_custom_suffix_changed)
        self._custom_radio.toggled.connect(self._on_custom_radio_toggled)

    def _on_selection_changed(self, button):
        """Handle radio button selection change"""
        if button == self._ask_radio:
            self._current_mode = "ask"
        elif button == self._auto_radio:
            self._current_mode = "auto_increment"
        elif button == self._simple_radio:
            self._current_mode = "simple_copy"
        elif button == self._custom_radio:
            self._current_mode = "custom_suffix"

        self.settingsChanged.emit(self._current_mode, self._custom_suffix)

    def _on_custom_radio_toggled(self, checked):
        """Handle custom radio button toggle"""
        self._custom_suffix_input.setEnabled(checked)
        if checked:
            self._custom_suffix_input.setFocus()
            self._custom_suffix_input.selectAll()

    def _on_custom_suffix_changed(self, text):
        """Handle custom suffix text change"""
        self._custom_suffix = text
        if self._current_mode == "custom_suffix":
            self.settingsChanged.emit(self._current_mode, self._custom_suffix)

    def get_current_mode(self) -> str:
        """Get the currently selected mode"""
        return self._current_mode

    def set_current_mode(self, mode: str, custom_suffix: str = None):
        """Set the current mode"""
        if mode not in self.MODES:
            mode = "ask"

        self._current_mode = mode

        if custom_suffix is not None:
            self._custom_suffix = custom_suffix
            self._custom_suffix_input.setText(custom_suffix)

        # Update radio buttons
        if mode == "ask":
            self._ask_radio.setChecked(True)
        elif mode == "auto_increment":
            self._auto_radio.setChecked(True)
        elif mode == "simple_copy":
            self._simple_radio.setChecked(True)
        elif mode == "custom_suffix":
            self._custom_radio.setChecked(True)

        # Enable/disable custom suffix input
        self._custom_suffix_input.setEnabled(mode == "custom_suffix")

    def show_at_position(self, x: int, y: int):
        """Show the overlay at a specific position"""
        self.move(x, y)
        self.show()
        self.raise_()
        # Ensure the widget has focus and is on top
        self.activateWindow()
        self.setFocus()

    def get_mode_description(self, mode: str) -> str:
        """Get description for a mode"""
        return self.MODES.get(mode, "Unknown mode")

    def get_custom_suffix(self) -> str:
        """Get the current custom suffix"""
        return self._custom_suffix

    def set_custom_suffix(self, suffix: str):
        """Set the custom suffix"""
        self._custom_suffix = suffix
        self._custom_suffix_input.setText(suffix)
