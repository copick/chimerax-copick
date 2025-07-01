from typing import Optional, Tuple

from copick.models import CopickRun

from .BaseEntityDialog import BaseEntityDialog, ColoredComboBox


class NewPickDialog(BaseEntityDialog):
    """Dialog for creating new picks with object, user, and session selection"""
    
    def __init__(self, run: CopickRun, parent=None, preset_user_id: str = None):
        self._run = run
        # Set default user ID from run if available
        default_user_id = run.root.user_id if run and run.root and run.root.user_id else "ArtiaX"
        super().__init__(parent, preset_user_id, default_user_id)
        
    def _setup_specific_ui(self):
        """Setup UI elements specific to NewPickDialog"""
        self.setWindowTitle("Create New Pick")
        
        # Object selection (add before user ID)
        self._object_combo = ColoredComboBox()
        self._object_combo.setToolTip("Select the pickable object type")
        self._form_layout.insertRow(0, "Object:", self._object_combo)
        
        # Set info text
        self._info_label.setText("Create a new set of picks with the specified parameters.")
        
        # Connect object combo change to validation
        self._object_combo.currentTextChanged.connect(self._update_ok_button)
    
    def _populate_initial_data(self):
        """Populate initial data specific to NewPickDialog"""
        self._populate_objects()
    
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
        if self.result() == self.Accepted:
            object_name = self.get_selected_object_name()
            user_id = self.get_user_id()
            session_id = self.get_session_id()
            
            # Validate inputs
            if not object_name or not user_id or not session_id:
                return None
                
            return (object_name, user_id, session_id)
        return None
    
    def get_selected_object_name(self) -> str:
        """Get the currently selected object name"""
        return self._object_combo.currentText()
        
    def _validate_additional_fields(self) -> bool:
        """Validate additional fields specific to NewPickDialog"""
        # Check if object is selected
        return bool(self._object_combo.currentText())
    
    def _get_ok_button_text(self) -> str:
        """Get the text for the OK button"""
        return "Create"
    
    def _use_dialog_button_box(self) -> bool:
        """Whether to use QDialogButtonBox or custom buttons"""
        return True