"""
Dialog for editing and managing PickableObject types in the copick configuration
"""
from typing import List, Optional, Tuple

from Qt.QtCore import Qt
from Qt.QtGui import QFont
from Qt.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from copick.models import PickableObject
from .validation import validate_copick_name


class ColorButton(QPushButton):
    """Button that displays and allows selection of a color"""
    
    def __init__(self, color: Tuple[int, int, int, int] = (100, 100, 100, 255), parent=None):
        super().__init__(parent)
        self._color = color
        self.setMaximumSize(30, 30)
        self.setMinimumSize(30, 30)
        self.clicked.connect(self._select_color)
        self._update_appearance()
    
    def _update_appearance(self):
        """Update button appearance to show current color"""
        r, g, b, a = self._color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({r}, {g}, {b}, {a});
                border: 2px solid #666;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #333;
            }}
        """)
        self.setToolTip(f"RGBA: ({r}, {g}, {b}, {a})")
    
    def _select_color(self):
        """Open color dialog to select new color"""
        from Qt.QtGui import QColor
        current_color = QColor(*self._color[:3])  # RGB only for QColor
        color = QColorDialog.getColor(current_color, self, "Select Object Color")
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue(), self._color[3])  # Keep alpha
            self._update_appearance()
    
    def get_color(self) -> Tuple[int, int, int, int]:
        """Get the current color"""
        return self._color
    
    def set_color(self, color: Tuple[int, int, int, int]):
        """Set the current color"""
        self._color = color
        self._update_appearance()


class EditObjectTypesDialog(QDialog):
    """Dialog for editing and managing PickableObject types"""
    
    def __init__(self, parent=None, existing_objects=None):
        super().__init__(parent)
        self._existing_objects = list(existing_objects) if existing_objects else []
        self._original_objects = [obj.model_copy(deep=True) for obj in self._existing_objects]  # Keep original state
        self._selected_object = None
        self._editing_mode = False  # True when editing, False when adding new
        
        self.setModal(True)
        self.setWindowTitle("Edit Object Types")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        
        self._setup_ui()
        self._connect_signals()
        self._populate_objects_table()
        self._reset_form()
        self._update_button_states()
        
    def _setup_ui(self):
        """Setup the dialog UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # Header
        header = QLabel("✏️ Edit Object Types")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(14)
        header.setFont(header_font)
        main_layout.addWidget(header)
        
        # Info label
        info_label = QLabel("Select an object type from the table to edit, or create a new one using the form below.")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(info_label)
        
        # Objects table with management buttons
        self._create_objects_table()
        main_layout.addWidget(self._objects_group)
        
        # Form for editing/adding
        self._create_object_form()
        main_layout.addWidget(self._form_group)
        
        # Dialog buttons
        self._button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._ok_button = self._button_box.button(QDialogButtonBox.Ok)
        self._ok_button.setText("Save Changes")
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
        
        main_layout.addWidget(self._button_box)
        self.setLayout(main_layout)
    
    def _create_objects_table(self):
        """Create the objects management table"""
        self._objects_group = QGroupBox("Existing Object Types")
        group_layout = QVBoxLayout()
        
        # Table management buttons
        table_buttons_layout = QHBoxLayout()
        table_buttons_layout.setContentsMargins(0, 0, 0, 5)
        
        self._edit_button = QPushButton("✏️ Edit Selected")
        self._edit_button.setEnabled(False)
        self._edit_button.setToolTip("Edit the selected object type")
        
        self._delete_button = QPushButton("❌ Delete Selected")
        self._delete_button.setEnabled(False)
        self._delete_button.setToolTip("Delete the selected object type")
        
        self._new_button = QPushButton("📄 Add New")
        self._new_button.setToolTip("Create a new object type")
        
        table_buttons_layout.addWidget(self._edit_button)
        table_buttons_layout.addWidget(self._delete_button)
        table_buttons_layout.addStretch()
        table_buttons_layout.addWidget(self._new_button)
        
        group_layout.addLayout(table_buttons_layout)
        
        # Objects table
        self._objects_table = QTableWidget()
        self._objects_table.setColumnCount(6)
        self._objects_table.setHorizontalHeaderLabels([
            "Name", "Type", "Label", "Color", "EMDB/PDB", "Additional Info"
        ])
        
        # Configure table appearance
        self._objects_table.setAlternatingRowColors(True)
        self._objects_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._objects_table.setSelectionMode(QTableWidget.SingleSelection)
        self._objects_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._objects_table.setMaximumHeight(200)
        
        # Configure column widths
        header = self._objects_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Label
        header.setSectionResizeMode(3, QHeaderView.Fixed)             # Color
        header.resizeSection(3, 60)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # EMDB/PDB
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # Additional Info
        
        group_layout.addWidget(self._objects_table)
        self._objects_group.setLayout(group_layout)
    
    def _create_object_form(self):
        """Create the object form for editing/adding"""
        self._form_group = QGroupBox("Object Configuration")
        main_layout = QVBoxLayout()
        
        # Form status label
        self._form_status = QLabel("Ready to add new object")
        self._form_status.setStyleSheet("font-weight: bold; color: #4A90E2; padding: 5px;")
        main_layout.addWidget(self._form_status)
        
        # Grid layout for two columns
        grid_layout = QGridLayout()
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setHorizontalSpacing(20)
        
        # Left column - Basic properties
        left_group = QGroupBox("Basic Properties")
        left_layout = QFormLayout()
        
        # Object name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Enter object name (e.g., 'ribosome', 'membrane')")
        self._name_edit.setToolTip("Unique name for this pickable object type")
        left_layout.addRow("Name*:", self._name_edit)
        
        # Name validation label
        self._name_validation = QLabel()
        self._name_validation.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-size: 10px;
                padding: 2px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 3px;
            }
        """)
        self._name_validation.setWordWrap(True)
        self._name_validation.hide()
        left_layout.addRow("", self._name_validation)
        
        # Is particle checkbox
        self._is_particle_cb = QCheckBox("Is Particle")
        self._is_particle_cb.setChecked(True)
        self._is_particle_cb.setToolTip("Check if this object should be represented by points, uncheck for segmentation masks")
        left_layout.addRow("Type:", self._is_particle_cb)
        
        # Label (numeric ID)
        self._label_spin = QSpinBox()
        self._label_spin.setRange(1, 9999)
        self._label_spin.setValue(1)
        self._label_spin.setToolTip("Unique numeric identifier for this object type")
        left_layout.addRow("Label*:", self._label_spin)
        
        # Label validation
        self._label_validation = QLabel()
        self._label_validation.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-size: 10px;
                padding: 2px;
                background-color: rgba(211, 47, 47, 0.1);
                border: 1px solid rgba(211, 47, 47, 0.3);
                border-radius: 3px;
            }
        """)
        self._label_validation.setWordWrap(True)
        self._label_validation.hide()
        left_layout.addRow("", self._label_validation)
        
        # Color selection
        color_widget = QWidget()
        color_layout = QHBoxLayout()
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(5)
        
        self._color_button = ColorButton()
        color_layout.addWidget(self._color_button)
        color_layout.addWidget(QLabel("Click to change color"))
        color_layout.addStretch()
        color_widget.setLayout(color_layout)
        
        left_layout.addRow("Color:", color_widget)
        left_group.setLayout(left_layout)
        
        # Right column - Optional properties
        right_group = QGroupBox("Optional Properties")
        right_layout = QFormLayout()
        
        # EMDB ID
        self._emdb_edit = QLineEdit()
        self._emdb_edit.setPlaceholderText("e.g., EMD-1234")
        self._emdb_edit.setToolTip("EMDB ID for this object type")
        right_layout.addRow("EMDB ID:", self._emdb_edit)
        
        # PDB ID
        self._pdb_edit = QLineEdit()
        self._pdb_edit.setPlaceholderText("e.g., 1ABC")
        self._pdb_edit.setToolTip("PDB ID for this object type")
        right_layout.addRow("PDB ID:", self._pdb_edit)
        
        # Identifier (GO/UniProt)
        self._identifier_edit = QLineEdit()
        self._identifier_edit.setPlaceholderText("e.g., GO:0005840 or P12345")
        self._identifier_edit.setToolTip("Gene Ontology ID or UniProtKB accession")
        right_layout.addRow("Identifier:", self._identifier_edit)
        
        # Map threshold
        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(-9999.0, 9999.0)
        self._threshold_spin.setDecimals(3)
        self._threshold_spin.setValue(0.0)
        self._threshold_spin.setSpecialValueText("None")
        self._threshold_spin.setToolTip("Threshold for isosurface rendering (set to minimum for None)")
        right_layout.addRow("Map Threshold:", self._threshold_spin)
        
        # Radius
        self._radius_spin = QDoubleSpinBox()
        self._radius_spin.setRange(0.1, 1000.0)
        self._radius_spin.setDecimals(1)
        self._radius_spin.setValue(10.0)
        self._radius_spin.setSpecialValueText("None")
        self._radius_spin.setToolTip("Radius for particle display (set to minimum for None)")
        right_layout.addRow("Radius (Å):", self._radius_spin)
        
        right_group.setLayout(right_layout)
        
        # Add groups to grid
        grid_layout.addWidget(left_group, 0, 0)
        grid_layout.addWidget(right_group, 0, 1)
        
        # Form action buttons
        form_buttons_layout = QHBoxLayout()
        form_buttons_layout.setContentsMargins(0, 10, 0, 0)
        
        self._apply_button = QPushButton("✅ Apply Changes")
        self._apply_button.setEnabled(False)
        self._apply_button.setToolTip("Apply changes to the selected object or add new object")
        
        self._cancel_edit_button = QPushButton("❌ Cancel")
        self._cancel_edit_button.setEnabled(False)
        self._cancel_edit_button.setToolTip("Cancel current editing operation")
        
        form_buttons_layout.addWidget(self._apply_button)
        form_buttons_layout.addWidget(self._cancel_edit_button)
        form_buttons_layout.addStretch()
        
        main_layout.addLayout(grid_layout)
        main_layout.addLayout(form_buttons_layout)
        self._form_group.setLayout(main_layout)
    
    def _connect_signals(self):
        """Connect widget signals"""
        # Dialog buttons
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        
        # Table management buttons
        self._edit_button.clicked.connect(self._edit_selected_object)
        self._delete_button.clicked.connect(self._delete_selected_object)
        self._new_button.clicked.connect(self._new_object)
        
        # Form buttons
        self._apply_button.clicked.connect(self._apply_changes)
        self._cancel_edit_button.clicked.connect(self._cancel_edit)
        
        # Table selection
        self._objects_table.selectionModel().selectionChanged.connect(self._on_table_selection_changed)
        self._objects_table.doubleClicked.connect(self._edit_selected_object)
        
        # Form validation
        self._name_edit.textChanged.connect(self._validate_form)
        self._label_spin.valueChanged.connect(self._validate_form)
    
    def _populate_objects_table(self):
        """Populate the objects table"""
        self._objects_table.setRowCount(len(self._existing_objects))
        
        for row, obj in enumerate(self._existing_objects):
            # Name
            name_item = QTableWidgetItem(obj.name)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._objects_table.setItem(row, 0, name_item)
            
            # Type
            type_text = "Particle" if obj.is_particle else "Segmentation"
            type_item = QTableWidgetItem(type_text)
            type_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._objects_table.setItem(row, 1, type_item)
            
            # Label
            label_text = str(obj.label) if obj.label is not None else "None"
            label_item = QTableWidgetItem(label_text)
            label_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._objects_table.setItem(row, 2, label_item)
            
            # Color
            if obj.color:
                r, g, b, a = obj.color
                color_widget = QWidget()
                color_layout = QHBoxLayout()
                color_layout.setContentsMargins(5, 2, 5, 2)
                color_button = QPushButton()
                color_button.setEnabled(False)
                color_button.setMaximumSize(20, 20)
                color_button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: rgba({r}, {g}, {b}, {a});
                        border: 1px solid #666;
                        border-radius: 2px;
                    }}
                """)
                color_layout.addWidget(color_button)
                color_layout.addStretch()
                color_widget.setLayout(color_layout)
                self._objects_table.setCellWidget(row, 3, color_widget)
            else:
                color_item = QTableWidgetItem("None")
                color_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._objects_table.setItem(row, 3, color_item)
            
            # EMDB/PDB
            ids = []
            if obj.emdb_id:
                ids.append(f"EMDB:{obj.emdb_id}")
            if obj.pdb_id:
                ids.append(f"PDB:{obj.pdb_id}")
            id_text = ", ".join(ids) if ids else "None"
            id_item = QTableWidgetItem(id_text)
            id_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._objects_table.setItem(row, 4, id_item)
            
            # Additional Info
            info_parts = []
            if obj.identifier:
                info_parts.append(f"ID:{obj.identifier}")
            if obj.map_threshold is not None:
                info_parts.append(f"Threshold:{obj.map_threshold}")
            if obj.radius is not None:
                info_parts.append(f"Radius:{obj.radius}Å")
            info_text = ", ".join(info_parts) if info_parts else "None"
            info_item = QTableWidgetItem(info_text)
            info_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._objects_table.setItem(row, 5, info_item)
    
    def _on_table_selection_changed(self):
        """Handle table selection changes"""
        self._update_button_states()
    
    def _update_button_states(self):
        """Update button states based on current state"""
        has_selection = len(self._objects_table.selectionModel().selectedRows()) > 0
        self._edit_button.setEnabled(has_selection and not self._editing_mode)
        self._delete_button.setEnabled(has_selection and not self._editing_mode)
        self._new_button.setEnabled(not self._editing_mode)
        
        # Form buttons
        self._apply_button.setEnabled(self._editing_mode and self._is_form_valid())
        self._cancel_edit_button.setEnabled(self._editing_mode)
    
    def _edit_selected_object(self):
        """Edit the currently selected object"""
        selected_rows = self._objects_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        if 0 <= row < len(self._existing_objects):
            self._selected_object = self._existing_objects[row]
            self._editing_mode = True
            self._populate_form_from_object(self._selected_object)
            self._form_status.setText(f"Editing: {self._selected_object.name}")
            self._form_status.setStyleSheet("font-weight: bold; color: #FF8C00; padding: 5px;")
            self._update_button_states()
    
    def _delete_selected_object(self):
        """Delete the currently selected object"""
        selected_rows = self._objects_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        if 0 <= row < len(self._existing_objects):
            obj_to_delete = self._existing_objects[row]
            
            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Delete Object Type",
                f"Are you sure you want to delete the object type '{obj_to_delete.name}'?\n\n"
                f"This action cannot be undone.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._existing_objects.pop(row)
                self._populate_objects_table()
                self._reset_form()
                self._update_button_states()
    
    def _new_object(self):
        """Start creating a new object"""
        self._selected_object = None
        self._editing_mode = True
        self._reset_form()
        self._populate_initial_data()
        self._form_status.setText("Creating new object")
        self._form_status.setStyleSheet("font-weight: bold; color: #4A90E2; padding: 5px;")
        self._update_button_states()
        self._name_edit.setFocus()
    
    def _apply_changes(self):
        """Apply current form changes"""
        if not self._is_form_valid():
            return
        
        new_object = self._create_object_from_form()
        
        if self._selected_object:
            # Update existing object
            row = self._existing_objects.index(self._selected_object)
            self._existing_objects[row] = new_object
        else:
            # Add new object
            self._existing_objects.append(new_object)
        
        self._populate_objects_table()
        self._reset_form()
        self._update_button_states()
    
    def _cancel_edit(self):
        """Cancel current editing operation"""
        self._reset_form()
        self._update_button_states()
    
    def _reset_form(self):
        """Reset form to default state"""
        self._selected_object = None
        self._editing_mode = False
        self._form_status.setText("Ready to add new object")
        self._form_status.setStyleSheet("font-weight: bold; color: #4A90E2; padding: 5px;")
        
        # Clear form fields
        self._name_edit.clear()
        self._is_particle_cb.setChecked(True)
        self._label_spin.setValue(1)
        self._color_button.set_color((100, 100, 100, 255))
        self._emdb_edit.clear()
        self._pdb_edit.clear()
        self._identifier_edit.clear()
        self._threshold_spin.setValue(self._threshold_spin.minimum())
        self._radius_spin.setValue(self._radius_spin.minimum())
        
        # Hide validation messages
        self._name_validation.hide()
        self._label_validation.hide()
        self._name_edit.setStyleSheet("")
        self._label_spin.setStyleSheet("")
    
    def _populate_form_from_object(self, obj: PickableObject):
        """Populate form fields from an object"""
        self._name_edit.setText(obj.name)
        self._is_particle_cb.setChecked(obj.is_particle)
        
        if obj.label is not None:
            self._label_spin.setValue(obj.label)
        
        if obj.color:
            self._color_button.set_color(obj.color)
        
        self._emdb_edit.setText(obj.emdb_id or "")
        self._pdb_edit.setText(obj.pdb_id or "")
        self._identifier_edit.setText(obj.identifier or "")
        
        if obj.map_threshold is not None:
            self._threshold_spin.setValue(obj.map_threshold)
        else:
            self._threshold_spin.setValue(self._threshold_spin.minimum())
        
        if obj.radius is not None:
            self._radius_spin.setValue(obj.radius)
        else:
            self._radius_spin.setValue(self._radius_spin.minimum())
    
    def _populate_initial_data(self):
        """Populate initial data for new object"""
        existing_labels = {obj.label for obj in self._existing_objects if obj.label is not None}
        if existing_labels:
            next_label = max(existing_labels) + 1
        else:
            next_label = 1
        self._label_spin.setValue(next_label)
    
    def _create_object_from_form(self) -> PickableObject:
        """Create PickableObject from current form data"""
        name = self._name_edit.text().strip()
        is_particle = self._is_particle_cb.isChecked()
        label = self._label_spin.value()
        color = self._color_button.get_color()
        
        # Handle optional fields
        emdb_id = self._emdb_edit.text().strip() or None
        pdb_id = self._pdb_edit.text().strip() or None
        identifier = self._identifier_edit.text().strip() or None
        
        # Handle threshold (None if at minimum)
        threshold = None
        if self._threshold_spin.value() != self._threshold_spin.minimum():
            threshold = self._threshold_spin.value()
        
        # Handle radius (None if at minimum)
        radius = None
        if self._radius_spin.value() != self._radius_spin.minimum():
            radius = self._radius_spin.value()
        
        return PickableObject(
            name=name,
            is_particle=is_particle,
            label=label,
            color=color,
            emdb_id=emdb_id,
            pdb_id=pdb_id,
            identifier=identifier,
            map_threshold=threshold,
            radius=radius
        )
    
    def _validate_form(self):
        """Validate the current form state"""
        name_text = self._name_edit.text().strip()
        
        # Validate name
        is_valid, _, error_msg = validate_copick_name(name_text)
        
        # Check for uniqueness (excluding current object being edited)
        existing_names = {obj.name.lower() for obj in self._existing_objects 
                         if obj != self._selected_object}
        
        if is_valid and name_text.lower() in existing_names:
            is_valid = False
            error_msg = f"Object name '{name_text}' already exists. Please choose a different name."
        
        # Update name validation display
        if is_valid:
            self._name_validation.hide()
            self._name_edit.setStyleSheet("")
        else:
            self._name_validation.setText(error_msg)
            self._name_validation.show()
            self._name_edit.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """)
        
        # Validate label uniqueness
        label_value = self._label_spin.value()
        existing_labels = {obj.label for obj in self._existing_objects 
                          if obj != self._selected_object and obj.label is not None}
        
        label_valid = label_value not in existing_labels
        
        if label_valid:
            self._label_validation.hide()
            self._label_spin.setStyleSheet("")
        else:
            error_msg = f"Label {label_value} is already in use. Please choose a different label."
            self._label_validation.setText(error_msg)
            self._label_validation.show()
            self._label_spin.setStyleSheet("""
                QSpinBox {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """)
        
        self._update_button_states()
        self.adjustSize()
    
    def _is_form_valid(self) -> bool:
        """Check if the current form state is valid"""
        name_text = self._name_edit.text().strip()
        name_valid, _, _ = validate_copick_name(name_text)
        
        # Check name uniqueness
        existing_names = {obj.name.lower() for obj in self._existing_objects 
                         if obj != self._selected_object}
        if name_valid and name_text.lower() in existing_names:
            name_valid = False
        
        # Check label uniqueness
        label_value = self._label_spin.value()
        existing_labels = {obj.label for obj in self._existing_objects 
                          if obj != self._selected_object and obj.label is not None}
        label_valid = label_value not in existing_labels
        
        return name_valid and label_valid and bool(name_text)
    
    def get_objects(self) -> List[PickableObject]:
        """Get the current list of objects"""
        return self._existing_objects
    
    def has_changes(self) -> bool:
        """Check if there are any changes compared to the original objects"""
        if len(self._existing_objects) != len(self._original_objects):
            return True
        
        for current, original in zip(self._existing_objects, self._original_objects):
            if (current.name != original.name or 
                current.is_particle != original.is_particle or
                current.label != original.label or
                current.color != original.color or
                current.emdb_id != original.emdb_id or
                current.pdb_id != original.pdb_id or
                current.identifier != original.identifier or
                current.map_threshold != original.map_threshold or
                current.radius != original.radius):
                return True
        
        return False