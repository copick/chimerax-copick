"""
Duplicate settings overlay menu for configuring duplicate behavior
"""
from Qt.QtCore import Qt, Signal
from Qt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QRadioButton, 
    QPushButton, QLabel, QButtonGroup
)


class DuplicateSettingsOverlay(QWidget):
    """Overlay widget for configuring duplicate behavior settings"""
    
    # Signal emitted when settings change
    settingsChanged = Signal(str)  # Emits the selected mode
    
    MODES = {
        "ask": "Always ask for session ID",
        "auto_increment": "Smart auto-increment (-copy1, -copy2, etc.)",
        "simple_copy": "Simple suffix (-copy)"
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "ask"  # Default mode
        self._setup_ui()
        self._connect_signals()
        self.hide()
        
    def _setup_ui(self):
        """Setup the overlay UI"""
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(45, 45, 45, 240);
                border: 1px solid rgba(100, 100, 100, 200);
                border-radius: 8px;
                color: white;
            }
            QRadioButton {
                color: white;
                font-size: 12px;
                padding: 4px 8px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
            }
            QRadioButton::indicator::unchecked {
                border: 2px solid #666;
                border-radius: 7px;
                background-color: transparent;
            }
            QRadioButton::indicator::checked {
                border: 2px solid #4A90E2;
                border-radius: 7px;
                background-color: #4A90E2;
            }
            QLabel {
                color: #ccc;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton {
                background-color: rgba(70, 130, 200, 180);
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 11px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(70, 130, 200, 220);
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        
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
        
    def _on_selection_changed(self, button):
        """Handle radio button selection change"""
        if button == self._ask_radio:
            self._current_mode = "ask"
        elif button == self._auto_radio:
            self._current_mode = "auto_increment"
        elif button == self._simple_radio:
            self._current_mode = "simple_copy"
            
        self.settingsChanged.emit(self._current_mode)
        
    def get_current_mode(self) -> str:
        """Get the currently selected mode"""
        return self._current_mode
        
    def set_current_mode(self, mode: str):
        """Set the current mode"""
        if mode not in self.MODES:
            mode = "ask"
            
        self._current_mode = mode
        
        # Update radio buttons
        if mode == "ask":
            self._ask_radio.setChecked(True)
        elif mode == "auto_increment":
            self._auto_radio.setChecked(True)
        elif mode == "simple_copy":
            self._simple_radio.setChecked(True)
            
    def show_at_position(self, x: int, y: int):
        """Show the overlay at a specific position"""
        self.move(x, y)
        self.show()
        self.raise_()
        
    def get_mode_description(self, mode: str) -> str:
        """Get description for a mode"""
        return self.MODES.get(mode, "Unknown mode")