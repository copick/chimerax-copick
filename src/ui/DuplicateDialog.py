"""
Dialog for editing session ID and user ID when duplicating objects with real-time validation
"""
from Qt.QtGui import QColor
from Qt.QtWidgets import QLabel

from .BaseEntityDialog import BaseEntityDialog


class DuplicateDialog(BaseEntityDialog):
    """Dialog for editing session ID and user ID when duplicating objects with real-time validation"""

    def __init__(
        self,
        original_name: str,
        suggested_name: str,
        parent=None,
        preset_user_id: str = None,
        default_user_id: str = None,
        object_name: str = None,
        object_color: tuple = None,
    ):
        self.original_name = original_name
        self.suggested_name = suggested_name
        self._object_name = object_name
        self._object_color = object_color or (128, 128, 128, 255)  # Default gray
        super().__init__(parent, preset_user_id, default_user_id)

    def _setup_specific_ui(self):
        """Setup UI elements specific to DuplicateDialog"""
        self.setWindowTitle("Duplicate Object")

        # Update header
        self._header.setText(f"Duplicating: {self.original_name}")

        # Add object field (colored, read-only) before user ID if object name is provided
        if self._object_name:
            self._object_display = QLabel()
            self._object_display.setText(self._object_name)

            # Create colored background style
            color = QColor(*self._object_color)
            color.setAlpha(100)  # Semi-transparent
            rgb_str = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"

            self._object_display.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {rgb_str};
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #333;
                    font-weight: bold;
                }}
            """,
            )
            self._object_display.setToolTip("Object type for this duplicate")
            self._form_layout.insertRow(0, "Object:", self._object_display)

        # Set info text based on object type
        object_type = "object"
        if self._object_name:
            # Try to determine type from object name or default to "object"
            if "pick" in self._object_name.lower():
                object_type = "pick"
            elif "segment" in self._object_name.lower():
                object_type = "segmentation"
            elif "mesh" in self._object_name.lower():
                object_type = "mesh"

        self._info_label.setText(f"Create a duplicate {object_type} with the specified parameters.")

    def _populate_initial_data(self):
        """Populate initial data specific to DuplicateDialog"""
        # Set the suggested session name
        self._session_edit.setText(self.suggested_name)

    def _validate_additional_fields(self) -> bool:
        """Validate additional fields specific to DuplicateDialog"""
        # No additional validation needed for duplicate dialog
        return True

    def _get_ok_button_text(self) -> str:
        """Get the text for the OK button"""
        return "Create Duplicate"

    def _use_dialog_button_box(self) -> bool:
        """Whether to use QDialogButtonBox or custom buttons"""
        return False

    def get_object_name(self) -> str:
        """Get the object name if available"""
        return self._object_name or ""
