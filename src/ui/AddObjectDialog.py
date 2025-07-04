"""
Dialog for adding a new PickableObject to the copick configuration
"""

from typing import Tuple

from copick.models import PickableObject
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
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..misc.validation import validate_copick_name


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
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: rgba({r}, {g}, {b}, {a});
                border: 2px solid #666;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #333;
            }}
        """,
        )
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


class AddObjectDialog(QDialog):
    """Dialog for adding a new PickableObject"""

    def __init__(self, parent=None, existing_objects=None):
        super().__init__(parent)
        self._existing_objects = existing_objects or []
        self._existing_labels = {obj.label for obj in self._existing_objects if obj.label is not None}
        self._existing_names = {obj.name.lower() for obj in self._existing_objects}

        self.setModal(True)
        self.setWindowTitle("Add Pickable Object Type")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)

        self._setup_ui()
        self._connect_signals()
        self._populate_existing_objects()
        self._populate_initial_data()
        self._validate_all_inputs()

    def _setup_ui(self):
        """Setup the dialog UI"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Header
        header = QLabel("Add New Pickable Object Type")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(14)
        header.setFont(header_font)
        main_layout.addWidget(header)

        # Info label
        info_label = QLabel("Review existing objects below, then configure the new object type.")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(info_label)

        # Existing objects table
        self._create_existing_objects_table()
        main_layout.addWidget(self._existing_objects_group)

        # New object input fields
        self._create_new_object_inputs()
        main_layout.addWidget(self._new_object_group)

        # Buttons
        self._button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._ok_button = self._button_box.button(QDialogButtonBox.Ok)
        self._ok_button.setText("Add Object")
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

        main_layout.addWidget(self._button_box)
        self.setLayout(main_layout)

    def _create_existing_objects_table(self):
        """Create the existing objects overview table"""
        self._existing_objects_group = QGroupBox("Existing Object Types")
        group_layout = QVBoxLayout()

        self._objects_table = QTableWidget()
        self._objects_table.setColumnCount(6)
        self._objects_table.setHorizontalHeaderLabels(["Name", "Type", "Label", "Color", "EMDB/PDB", "Additional Info"])

        # Configure table appearance
        self._objects_table.setAlternatingRowColors(True)
        self._objects_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._objects_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._objects_table.setMaximumHeight(150)

        # Configure column widths
        header = self._objects_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Label
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Color
        header.resizeSection(3, 60)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # EMDB/PDB
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # Additional Info

        group_layout.addWidget(self._objects_table)
        self._existing_objects_group.setLayout(group_layout)

    def _create_new_object_inputs(self):
        """Create the new object input fields in two columns"""
        self._new_object_group = QGroupBox("New Object Configuration")
        main_layout = QVBoxLayout()

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
        self._name_validation.setStyleSheet(
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
        self._name_validation.setWordWrap(True)
        self._name_validation.hide()
        left_layout.addRow("", self._name_validation)

        # Is particle checkbox
        self._is_particle_cb = QCheckBox("Is Particle")
        self._is_particle_cb.setChecked(True)
        self._is_particle_cb.setToolTip(
            "Check if this object should be represented by points, uncheck for segmentation masks",
        )
        left_layout.addRow("Type:", self._is_particle_cb)

        # Label (numeric ID)
        self._label_spin = QSpinBox()
        self._label_spin.setRange(1, 9999)
        self._label_spin.setValue(1)
        self._label_spin.setToolTip("Unique numeric identifier for this object type")
        left_layout.addRow("Label*:", self._label_spin)

        # Label validation
        self._label_validation = QLabel()
        self._label_validation.setStyleSheet(
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

        main_layout.addLayout(grid_layout)
        self._new_object_group.setLayout(main_layout)

    def _connect_signals(self):
        """Connect widget signals"""
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._name_edit.textChanged.connect(self._validate_name)
        self._label_spin.valueChanged.connect(self._validate_label)

    def _populate_existing_objects(self):
        """Populate the existing objects table"""
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
                color_button.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: rgba({r}, {g}, {b}, {a});
                        border: 1px solid #666;
                        border-radius: 2px;
                    }}
                """,
                )
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

    def _populate_initial_data(self):
        """Find next available label"""
        next_label = max(self._existing_labels) + 1 if self._existing_labels else 1
        self._label_spin.setValue(next_label)

    def _validate_name(self, text=None):
        """Validate object name"""
        if text is None:
            text = self._name_edit.text()

        # Basic validation
        is_valid, sanitized, error_msg = validate_copick_name(text)

        # Check for uniqueness
        if is_valid and text.strip().lower() in self._existing_names:
            is_valid = False
            error_msg = f"Object name '{text}' already exists. Please choose a different name."

        if is_valid:
            self._name_validation.hide()
            self._name_edit.setStyleSheet("")
        else:
            self._name_validation.setText(error_msg)
            self._name_validation.show()
            self._name_edit.setStyleSheet(
                """
                QLineEdit {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """,
            )

        self._update_ok_button()
        self.adjustSize()

    def _validate_label(self, value=None):
        """Validate object label"""
        if value is None:
            value = self._label_spin.value()

        is_valid = value not in self._existing_labels

        if is_valid:
            self._label_validation.hide()
            self._label_spin.setStyleSheet("")
        else:
            error_msg = f"Label {value} is already in use. Please choose a different label."
            self._label_validation.setText(error_msg)
            self._label_validation.show()
            self._label_spin.setStyleSheet(
                """
                QSpinBox {
                    border: 2px solid #d32f2f;
                    background-color: rgba(211, 47, 47, 0.05);
                }
            """,
            )

        self._update_ok_button()
        self.adjustSize()

    def _validate_all_inputs(self):
        """Validate all inputs"""
        self._validate_name()
        self._validate_label()

    def _update_ok_button(self):
        """Update OK button state based on validation"""
        name_text = self._name_edit.text().strip()
        name_valid, _, _ = validate_copick_name(name_text)

        # Check name uniqueness
        if name_valid and name_text.lower() in self._existing_names:
            name_valid = False

        # Check label uniqueness
        label_valid = self._label_spin.value() not in self._existing_labels

        # Enable OK button only if all validations pass
        all_valid = name_valid and label_valid and bool(name_text)
        self._ok_button.setEnabled(all_valid)

    def exec_(self) -> int:
        """Execute the dialog and focus the name input"""
        self._name_edit.setFocus()
        self._name_edit.selectAll()
        return super().exec_()

    def get_pickable_object(self) -> PickableObject:
        """Create PickableObject from dialog inputs"""
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
            radius=radius,
        )
