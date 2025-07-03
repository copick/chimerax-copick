from typing import Optional
import numpy as np
import zarr
from Qt.QtCore import QObject, QThreadPool, QUrl, Qt, Signal, Slot, QMetaObject, Q_ARG, QVariant
from Qt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QPushButton,
    QGridLayout,
)
from Qt.QtGui import QFont, QPixmap, QPainter, QColor, QDesktopServices, QImage

from .async_workers import AsyncWorkerSignals, DataLoadWorker, ThumbnailLoadWorker


class CopickInfoWidget(QWidget):
    """Native Qt widget for displaying copick run information with async loading"""

    def __init__(self, session, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.session = session
        self.current_run_name = None
        self.current_run = None
        self._is_destroyed = False
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(4)  # Limit concurrent threads
        self._loading_states = {}  # Track what's currently loading
        self._loaded_data = {}  # Cache loaded data

        # Shared signals for async workers
        self._signals = AsyncWorkerSignals()
        self._signals.data_loaded.connect(self._handle_data_loaded)
        self._signals.thumbnail_loaded.connect(self._handle_thumbnail_loaded)

        # Register for app quit trigger to ensure proper cleanup
        session.triggers.add_handler("app quit", self._app_quit)

        self._setup_ui()
        self._thumbnails = {}  # Cache for loaded thumbnails
        self._thumbnail_widgets = {}  # Map thumbnail_id to widget
        self._update_display()

    def _on_tomogram_card_clicked(self, tomogram):
        """Handle click on tomogram card - load tomogram and switch to OpenGL view"""
        if not hasattr(self.session, "copick") or not self.session.copick:
            return
        copick_tool = self.session.copick
        self._load_tomogram_and_switch_view(tomogram, copick_tool)

    def _load_tomogram_and_switch_view(self, tomogram, copick_tool):
        """Load the tomogram and switch to OpenGL view - replicates tree double-click behavior"""
        # Get the main window and stack widget for view switching
        main_window = self.session.ui.main_window
        stack_widget = main_window._stack

        # Switch to OpenGL view (index 0)
        stack_widget.setCurrentIndex(0)

        # Find the tomogram in the tree and get its QModelIndex
        tomogram_index = self._find_tomogram_in_tree(tomogram, copick_tool)

        if tomogram_index and tomogram_index.isValid():
            # This is exactly what _on_tree_double_click does - just call switch_volume
            copick_tool.switch_volume(tomogram_index)

        # Expand the run in the tree widget
        self._expand_run_in_tree(copick_tool)

    def _find_tomogram_in_tree(self, tomogram, copick_tool):
        """Find the tomogram in the tree model and return its QModelIndex"""
        tree_view = copick_tool._mw._tree_view
        model = tree_view.model()

        if not model:
            return None

        # Navigate the tree structure: Root -> Run -> VoxelSpacing -> Tomogram
        for run_row in range(model.rowCount()):
            run_index = model.index(run_row, 0)
            if not run_index.isValid():
                continue

            # Get the actual item (handling proxy model if present)
            if hasattr(model, "mapToSource"):
                source_run_index = model.mapToSource(run_index)
                run_item = source_run_index.internalPointer()
            else:
                run_item = run_index.internalPointer()

            if not run_item:
                continue

            # Check if this is the right run
            if hasattr(run_item, "run"):
                if run_item.run.name != self.current_run.name:
                    continue
            elif hasattr(run_item, "name"):
                if run_item.name != self.current_run.name:
                    continue
            else:
                continue

            # Force lazy loading by accessing the children property directly
            if hasattr(run_item, "children"):
                vs_children = run_item.children  # This triggers lazy loading
                vs_count = len(vs_children)
            else:
                vs_count = model.rowCount(run_index)

            for vs_row in range(vs_count):
                vs_index = model.index(vs_row, 0, run_index)
                if not vs_index.isValid():
                    continue

                # Get voxel spacing item
                if hasattr(model, "mapToSource"):
                    source_vs_index = model.mapToSource(vs_index)
                    vs_item = source_vs_index.internalPointer()
                else:
                    vs_item = vs_index.internalPointer()

                if not vs_item:
                    continue

                # Check if this voxel spacing contains our tomogram
                if hasattr(vs_item, "voxel_spacing"):
                    vs_obj = vs_item.voxel_spacing
                    if vs_obj.voxel_size != tomogram.voxel_spacing.voxel_size:
                        continue
                else:
                    continue

                # Force lazy loading by accessing the children property directly
                if hasattr(vs_item, "children"):
                    tomo_children = vs_item.children  # This triggers lazy loading
                    tomo_count = len(tomo_children)
                else:
                    tomo_count = model.rowCount(vs_index)

                for tomo_row in range(tomo_count):
                    tomo_index = model.index(tomo_row, 0, vs_index)
                    if not tomo_index.isValid():
                        continue

                    # Get tomogram item
                    if hasattr(model, "mapToSource"):
                        source_tomo_index = model.mapToSource(tomo_index)
                        tomo_item = source_tomo_index.internalPointer()
                        final_index = source_tomo_index
                    else:
                        tomo_item = tomo_index.internalPointer()
                        final_index = tomo_index

                    if not tomo_item:
                        continue

                    # Check if this is our tomogram - compare by type and voxel spacing
                    if hasattr(tomo_item, "tomogram"):
                        tomo_obj = tomo_item.tomogram
                        if (
                            tomo_obj.tomo_type == tomogram.tomo_type
                            and tomo_obj.voxel_spacing.voxel_size == tomogram.voxel_spacing.voxel_size
                        ):
                            return final_index

        return None

    def _expand_run_in_tree(self, copick_tool):
        """Expand the current run and voxel spacing in the tree widget"""
        tree_view = copick_tool._mw._tree_view
        model = tree_view.model()

        if model and self.current_run:
            # Find the run in the tree model and expand it
            for row in range(model.rowCount()):
                index = model.index(row, 0)
                if index.isValid():
                    # Get the item and check if it matches our current run
                    if hasattr(model, "mapToSource"):
                        source_index = model.mapToSource(index)
                        item = source_index.internalPointer()
                    else:
                        item = index.internalPointer()

                    # Check if this is the right run
                    if hasattr(item, "run") and item.run == self.current_run:
                        tree_view.expand(index)
                        tree_view.setCurrentIndex(index)

                        # Also expand all voxel spacings within this run
                        self._expand_all_voxel_spacings(tree_view, model, index)
                        break
                    elif hasattr(item, "name") and item.name == self.current_run.name:
                        tree_view.expand(index)
                        tree_view.setCurrentIndex(index)

                        # Also expand all voxel spacings within this run
                        self._expand_all_voxel_spacings(tree_view, model, index)
                        break

    def _expand_all_voxel_spacings(self, tree_view, model, run_index):
        """Expand all voxel spacings under the given run"""
        # Force lazy loading of voxel spacings
        if hasattr(model, "mapToSource"):
            source_run_index = model.mapToSource(run_index)
            run_item = source_run_index.internalPointer()
        else:
            run_item = run_index.internalPointer()

        vs_children = run_item.children  # Force lazy loading
        vs_count = len(vs_children)

        # Expand each voxel spacing
        for vs_row in range(vs_count):
            vs_index = model.index(vs_row, 0, run_index)
            if vs_index.isValid():
                tree_view.expand(vs_index)

    def _app_quit(self, *args):
        """Handle app quit trigger to ensure proper cleanup"""
        if not self._is_destroyed:
            # Clear thread pool immediately on app quit
            if hasattr(self, '_thread_pool'):
                self._thread_pool.clear()
                # Don't wait for completion during app quit to avoid hanging
            self.deleteLater()

    def delete(self):
        """Properly clean up the widget"""
        if self._is_destroyed:
            return

        self._is_destroyed = True

        # Stop thread pool
        self._thread_pool.clear()
        self._thread_pool.waitForDone(3000)  # Wait up to 3 seconds

    def _setup_ui(self):
        """Set up the UI components"""
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header section - fixed size
        self._create_header(layout)

        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QFrame.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Content widget inside scroll area
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(10, 10, 10, 10)
        self._content_layout.setSpacing(12)
        self._content_layout.setAlignment(Qt.AlignTop)  # Prevent excessive stretching
        self._content_widget.setLayout(self._content_layout)
        self._content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        scroll_area.setWidget(self._content_widget)
        layout.addWidget(scroll_area, 1)  # Give it stretch factor

        # Footer hint - fixed size
        self._create_footer(layout)

        self.setLayout(layout)

        # Apply styling
        self._apply_styling()

    def _create_header(self, layout):
        """Create the header section"""
        header_widget = QWidget()
        header_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(10, 10, 10, 15)
        header_layout.setSpacing(8)
        header_layout.setAlignment(Qt.AlignCenter)

        # Title
        title_label = QLabel("Copick Run Details")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(title_label)

        # Run name
        self._run_name_label = QLabel("No run selected")
        name_font = QFont()
        name_font.setPointSize(18)
        name_font.setBold(True)
        self._run_name_label.setFont(name_font)
        self._run_name_label.setAlignment(Qt.AlignCenter)
        self._run_name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._run_name_label.setStyleSheet("color: #007AFF; margin-bottom: 5px;")
        header_layout.addWidget(self._run_name_label)

        header_widget.setLayout(header_layout)
        layout.addWidget(header_widget, 0)  # No stretch

    def _create_footer(self, layout):
        """Create the footer hint"""
        footer_label = QLabel("💡 Use the overlay button on the tree widget to switch between OpenGL and info views")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        footer_label.setStyleSheet(
            """
            QLabel {
                background-color: rgba(45, 45, 45, 100);
                border-radius: 6px;
                padding: 10px;
                font-size: 10px;
                color: #999;
            }
        """
        )
        layout.addWidget(footer_label, 0)  # No stretch

    def _apply_styling(self):
        """Apply overall widget styling"""
        self.setStyleSheet(
            """
            QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #666;
            }
        """
        )

    def set_run_name(self, run_name: str):
        """Set the current run name and update the display"""
        self.current_run_name = run_name
        self.current_run = None  # Will be set by set_run()
        self._update_display()

    def set_run(self, run):
        """Set the current run object and start async loading"""
        if self._is_destroyed:
            return

        self.current_run = run
        if run:
            self.current_run_name = run.name
            # Clear previous data and loading states
            self._loaded_data.clear()
            self._loading_states.clear()

            # Start async loading of all data types
            self._start_async_loading()
        else:
            self.current_run_name = None
            self._loaded_data.clear()
            self._loading_states.clear()

        self._update_display()

    def _start_async_loading(self):
        """Start asynchronous loading of all run data"""
        if not self.current_run or self._is_destroyed:
            return

        data_types = ["voxel_spacings", "tomograms", "picks", "meshes", "segmentations"]

        for data_type in data_types:
            if data_type not in self._loading_states:
                self._loading_states[data_type] = "loading"
                worker = DataLoadWorker(self._signals, self.current_run, data_type)
                self._thread_pool.start(worker)

    def _handle_data_loaded(self, data_type, data, error):
        """Handle data loading completion"""
        if self._is_destroyed:
            return

        if error:
            self._loading_states[data_type] = f"error: {error}"
        else:
            self._loading_states[data_type] = "loaded"
            self._loaded_data[data_type] = data

        # Update the display to show new data
        self._update_display()

    def _handle_thumbnail_loaded(self, thumbnail_id, pixmap, error):
        """Handle thumbnail loading completion"""
        if self._is_destroyed:
            return

        if error:
            # Could show error placeholder, but for now just leave the loading placeholder
            pass
        else:
            # Store the thumbnail
            self._thumbnails[thumbnail_id] = pixmap

            # Update the widget if it exists and is still valid
            if thumbnail_id in self._thumbnail_widgets:
                widget = self._thumbnail_widgets[thumbnail_id]
                try:
                    # Check if widget is still valid before accessing it
                    if widget and not widget.isHidden():
                        # Find the thumbnail label in the widget and update it
                        thumbnail_label = widget.findChild(QLabel, "thumbnail_label")
                        if thumbnail_label and not thumbnail_label.isHidden():
                            # Use adaptive scaling based on widget size
                            widget_size = thumbnail_label.size()
                            # Leave some margin around the thumbnail
                            max_size = min(widget_size.width() - 20, widget_size.height() - 20)
                            if max_size > 0:
                                scaled_pixmap = pixmap.scaled(
                                    max_size,
                                    max_size,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation,
                                )
                                thumbnail_label.setPixmap(scaled_pixmap)
                    else:
                        # Clean up the reference
                        del self._thumbnail_widgets[thumbnail_id]
                except RuntimeError:
                    # Widget has been deleted - clean up the reference
                    if thumbnail_id in self._thumbnail_widgets:
                        del self._thumbnail_widgets[thumbnail_id]

    def _on_thumbnail_loaded(self, thumbnail_id, pixmap, error):
        """Qt slot method for handling thumbnail loading from worker threads"""
        # This method is called by QMetaObject.invokeMethod from worker threads
        self._handle_thumbnail_loaded(thumbnail_id, pixmap, error)

    @Slot(str, QVariant, QVariant)
    def _on_thumbnail_loaded_slot(self, thumbnail_id, pixmap, error):
        """Properly decorated Qt slot for thumbnail loading"""
        self._handle_thumbnail_loaded(thumbnail_id, pixmap, error)

    def _update_display(self):
        """Update the widget display"""
        # Update run name
        run_display = self.current_run_name or "No run selected"
        self._run_name_label.setText(run_display)

        # Clear existing content
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Clear thumbnail widget references since widgets are being deleted
        self._thumbnail_widgets.clear()

        if self.current_run:
            # Add voxel spacings section with nested tomograms
            self._add_voxel_spacings_section()

            # Add annotations group (picks, meshes, segmentations)
            self._add_annotations_section()
        else:
            # Show empty state
            empty_label = QLabel("Select a run from the copick tree to view its contents.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #999; font-style: italic; padding: 40px;")
            self._content_layout.addWidget(empty_label)

    def _add_voxel_spacings_section(self):
        """Add the voxel spacings section with nested tomograms"""
        voxel_status = self._loading_states.get("voxel_spacings", "not_started")
        tomo_status = self._loading_states.get("tomograms", "not_started")

        # Create section frame
        section_frame = self._create_section_frame()
        section_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        section_layout = QVBoxLayout()
        section_layout.setContentsMargins(15, 15, 15, 15)
        section_layout.setSpacing(12)

        # Section header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("📏 Voxel Spacings & Tomograms")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(title_label)

        # Status indicator - combine voxel spacing and tomogram status
        if voxel_status == "loading" or tomo_status == "loading":
            status_label = self._create_status_label("loading", "")
            status_label.setText("Loading...")
        elif voxel_status == "loaded" and tomo_status == "loaded":
            vs_count = len(self._loaded_data.get("voxel_spacings", []))
            tomo_count = len(self._loaded_data.get("tomograms", []))
            status_label = self._create_status_label("loaded", "")
            status_label.setText(f"✓ {vs_count} voxel spacings, {tomo_count} tomograms")
        elif voxel_status.startswith("error:") or tomo_status.startswith("error:"):
            status_label = self._create_status_label("error: Combined data error", "")
            status_label.setText("✗ Error loading data")
        else:
            status_label = self._create_status_label("pending", "")
            status_label.setText("Pending...")

        status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        header_layout.addStretch()
        header_layout.addWidget(status_label)

        section_layout.addLayout(header_layout)

        # Content - wait for both voxel spacings AND tomograms to load
        if voxel_status == "loaded" and tomo_status == "loaded" and "voxel_spacings" in self._loaded_data:
            voxel_spacings = self._loaded_data["voxel_spacings"]
            tomograms = self._loaded_data.get("tomograms", [])

            if voxel_spacings:
                content_widget = self._create_nested_voxel_tomogram_content(voxel_spacings, tomograms)
                content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                section_layout.addWidget(content_widget)
            else:
                empty_label = QLabel("No voxel spacings found")
                empty_label.setAlignment(Qt.AlignCenter)
                empty_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                empty_label.setStyleSheet("color: #999; font-style: italic; padding: 15px;")
                section_layout.addWidget(empty_label)
        else:
            # Show loading placeholder until both are loaded
            if voxel_status == "loading" or tomo_status == "loading":
                content_label = self._create_content_placeholder("loading")
            elif voxel_status.startswith("error:") or tomo_status.startswith("error:"):
                content_label = self._create_content_placeholder("error: Failed to load data")
            else:
                content_label = self._create_content_placeholder("pending")
            content_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            section_layout.addWidget(content_label)

        section_frame.setLayout(section_layout)
        self._content_layout.addWidget(section_frame)

    def _add_annotations_section(self):
        """Add the annotations group section"""
        picks_status = self._loading_states.get("picks", "not_started")
        meshes_status = self._loading_states.get("meshes", "not_started")
        seg_status = self._loading_states.get("segmentations", "not_started")

        # Create section frame
        section_frame = self._create_section_frame()
        section_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        section_layout = QVBoxLayout()
        section_layout.setContentsMargins(15, 15, 15, 15)
        section_layout.setSpacing(12)

        # Section header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("📋 Annotations")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(title_label)

        # Overall status
        picks_count = len(self._loaded_data.get("picks", []))
        meshes_count = len(self._loaded_data.get("meshes", []))
        seg_count = len(self._loaded_data.get("segmentations", []))
        total_count = picks_count + meshes_count + seg_count

        all_loaded = all(status == "loaded" for status in [picks_status, meshes_status, seg_status])
        any_loading = any(status == "loading" for status in [picks_status, meshes_status, seg_status])

        if any_loading:
            status_label = self._create_status_label("loading", "")
            status_label.setText("Loading annotations...")
        elif all_loaded:
            status_label = self._create_status_label("loaded", "")
            status_label.setText(f"✓ {total_count} annotations")
        else:
            status_label = self._create_status_label("pending", "")
            status_label.setText("Pending...")

        status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        header_layout.addStretch()
        header_layout.addWidget(status_label)

        section_layout.addLayout(header_layout)

        # Subsections
        subsections_widget = QWidget()
        subsections_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        subsections_layout = QVBoxLayout()
        subsections_layout.setContentsMargins(10, 0, 0, 0)  # Reduced indent
        subsections_layout.setSpacing(8)

        # Add each annotation type
        subsections_layout.addWidget(self._create_annotation_subsection("picks", "📍 Picks", picks_status))
        subsections_layout.addWidget(self._create_annotation_subsection("meshes", "🕸 Meshes", meshes_status))
        subsections_layout.addWidget(self._create_annotation_subsection("segmentations", "🖌 Segmentations", seg_status))

        subsections_widget.setLayout(subsections_layout)
        section_layout.addWidget(subsections_widget)

        section_frame.setLayout(section_layout)
        self._content_layout.addWidget(section_frame)

    def _create_section_frame(self):
        """Create a styled frame for a section"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        frame.setStyleSheet(
            """
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                border: 1px solid #444;
            }
        """
        )
        return frame

    def _create_status_label(self, status, data_type):
        """Create a status indicator label"""
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)

        if status == "loading":
            label.setText("Loading...")
            label.setStyleSheet(
                """
                QLabel {
                    background-color: #FFF3CD;
                    color: #856404;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """
            )
        elif status == "loaded":
            count = len(self._loaded_data.get(data_type, []))
            label.setText(f"✓ Loaded ({count} items)")
            label.setStyleSheet(
                """
                QLabel {
                    background-color: #D4EDDA;
                    color: #155724;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """
            )
        elif status.startswith("error:"):
            error_msg = status[6:]  # Remove "error:" prefix
            label.setText(f"✗ Error: {error_msg[:20]}...")
            label.setStyleSheet(
                """
                QLabel {
                    background-color: #F8D7DA;
                    color: #721C24;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """
            )
        else:
            label.setText("Pending...")
            label.setStyleSheet(
                """
                QLabel {
                    background-color: #555;
                    color: #ccc;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }
            """
            )

        return label

    def _create_content_placeholder(self, status):
        """Create a placeholder label for content"""
        if status == "loading":
            text = "Loading data..."
        elif status.startswith("error:"):
            text = "Failed to load data"
        else:
            text = "Not loaded yet"

        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #999; font-style: italic; padding: 20px;")
        return label

    def _create_nested_voxel_tomogram_content(self, voxel_spacings, tomograms):
        """Create nested voxel spacing and tomogram content"""
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # Group tomograms by voxel spacing
        voxel_to_tomos = {}
        for vs in voxel_spacings:
            voxel_to_tomos[vs.voxel_size] = []

        for tomo in tomograms:
            vs_size = tomo.voxel_spacing.voxel_size
            if vs_size in voxel_to_tomos:
                voxel_to_tomos[vs_size].append(tomo)

        for vs in voxel_spacings:
            vs_widget = self._create_voxel_spacing_widget(vs, voxel_to_tomos.get(vs.voxel_size, []))
            content_layout.addWidget(vs_widget)

        content_widget.setLayout(content_layout)
        return content_widget

    def _create_voxel_spacing_widget(self, voxel_spacing, tomograms):
        """Create a widget for a voxel spacing with its tomograms"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        frame.setStyleSheet(
            """
            QFrame {
                background-color: #1a1a1a;
                border-radius: 6px;
                border: 1px solid #444;
            }
        """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header with voxel spacing info
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel(f"📏 Voxel Spacing {voxel_spacing.voxel_size:.2f}Å")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)

        # Add CryoET link if applicable
        link_button = self._create_cryoet_link_button(voxel_spacing)
        if link_button:
            header_layout.addStretch()
            header_layout.addWidget(link_button)

        layout.addLayout(header_layout)

        # Tomograms grid
        if tomograms:
            # Create a grid layout for tomogram cards
            tomo_grid_widget = QWidget()
            tomo_grid_layout = QGridLayout()
            tomo_grid_layout.setContentsMargins(15, 0, 0, 0)  # Indent tomograms
            tomo_grid_layout.setSpacing(8)

            # Calculate grid dimensions (3 columns)
            cols = 3

            for i, tomo in enumerate(tomograms):
                row = i // cols
                col = i % cols

                tomo_card = self._create_tomogram_card(tomo)
                tomo_grid_layout.addWidget(tomo_card, row, col)

            tomo_grid_widget.setLayout(tomo_grid_layout)
            layout.addWidget(tomo_grid_widget)
        else:
            empty_label = QLabel("No tomograms found")
            empty_label.setStyleSheet("color: #999; font-style: italic; margin-left: 15px;")
            layout.addWidget(empty_label)

        frame.setLayout(layout)
        return frame

    def _create_tomogram_card(self, tomogram):
        """Create a card widget for a tomogram with thumbnail"""
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.setMinimumSize(200, 240)  # Reasonable minimum size
        # No maximum size - let cards expand to fill available space
        card.setStyleSheet(
            """
            QFrame {
                background-color: #3d3d3d;
                border-radius: 8px;
                border: 1px solid #555;
            }
            QFrame:hover {
                border: 1px solid #007AFF;
                background-color: #4d4d4d;
            }
        """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Thumbnail area - adaptive size with proper centering
        thumbnail_label = QLabel()
        thumbnail_label.setObjectName("thumbnail_label")  # For finding later
        thumbnail_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        thumbnail_label.setAlignment(Qt.AlignCenter)
        thumbnail_label.setScaledContents(False)  # We'll handle scaling manually
        thumbnail_label.setStyleSheet(
            """
            QLabel {
                background-color: #2d2d2d;
                border-radius: 6px;
                border: 1px solid #444;
            }
        """
        )

        # Create unique ID for this tomogram thumbnail
        thumbnail_id = f"tomo_{id(tomogram)}"

        # Check if thumbnail is already loaded
        if thumbnail_id in self._thumbnails:
            # Use cached thumbnail with adaptive scaling
            pixmap = self._thumbnails[thumbnail_id]
            # Scale thumbnail to fit nicely in card (leaving some margin)
            max_size = min(card.minimumSize().width() - 40, card.minimumSize().height() - 80)
            scaled_pixmap = pixmap.scaled(
                max_size, max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            thumbnail_label.setPixmap(scaled_pixmap)
        else:
            # Show loading placeholder and start async loading
            thumbnail_label.setText("⏳")
            thumbnail_label.setStyleSheet(thumbnail_label.styleSheet() + "color: #999; font-size: 24px;")

            # Store widget reference for later update
            self._thumbnail_widgets[thumbnail_id] = card

            # Start async thumbnail loading
            if not self._is_destroyed:
                worker = ThumbnailLoadWorker(self._signals, tomogram, thumbnail_id)
                self._thread_pool.start(worker)

        layout.addWidget(thumbnail_label)

        # Info section
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # Tomogram name
        name_label = QLabel(tomogram.tomo_type)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("color: #fff; font-weight: bold; font-size: 10px;")
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)

        # CryoET link if applicable
        link_button = self._create_cryoet_link_button(tomogram)
        if link_button:
            link_button.setFixedHeight(18)
            link_button.setStyleSheet(link_button.styleSheet() + "font-size: 8px; padding: 1px 4px;")
            info_layout.addWidget(link_button)

        info_widget = QWidget()
        info_widget.setLayout(info_layout)
        layout.addWidget(info_widget)

        # Make the card clickable
        card.mousePressEvent = lambda event: self._on_tomogram_card_clicked(tomogram)

        # Add visual feedback for clickability
        card.setStyleSheet(
            card.styleSheet().rstrip("}")
            + """
            cursor: pointer;
        }"""
        )

        card.setLayout(layout)
        return card

    def _create_tomogram_widget(self, tomogram):
        """Create a widget for a tomogram"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Icon and name
        icon_label = QLabel("🧊")
        icon_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(icon_label)

        name_label = QLabel(tomogram.tomo_type)
        name_label.setStyleSheet("color: #fff; font-size: 11px;")
        layout.addWidget(name_label)

        layout.addStretch()

        # Add CryoET link if applicable
        link_button = self._create_cryoet_link_button(tomogram)
        if link_button:
            layout.addWidget(link_button)

        widget.setLayout(layout)
        widget.setStyleSheet(
            """
            QWidget {
                background-color: #3d3d3d;
                border-radius: 4px;
            }
        """
        )
        return widget

    def _create_annotation_subsection(self, data_type, title, status):
        """Create an annotation subsection widget"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        frame.setStyleSheet(
            """
            QFrame {
                background-color: #1a1a1a;
                border-radius: 4px;
                border: 1px solid #444;
            }
        """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Subsection header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        # Status indicator
        if status == "loading":
            status_label = QLabel("⏳")
        elif status == "loaded":
            count = len(self._loaded_data.get(data_type, []))
            status_label = QLabel(f"({count})")
        elif status.startswith("error:"):
            status_label = QLabel("⚠️")
        else:
            status_label = QLabel("⏳")

        status_label.setStyleSheet("color: #999; font-size: 10px;")
        header_layout.addStretch()
        header_layout.addWidget(status_label)

        layout.addLayout(header_layout)

        # Content
        if status == "loaded" and data_type in self._loaded_data:
            data = self._loaded_data[data_type]
            if data:
                content_widget = self._create_annotation_items_widget(data_type, data)
                layout.addWidget(content_widget)
            else:
                empty_label = QLabel("No items found")
                empty_label.setStyleSheet("color: #999; font-style: italic; margin-left: 10px;")
                layout.addWidget(empty_label)
        else:
            content_label = self._create_content_placeholder(status)
            layout.addWidget(content_label)

        frame.setLayout(layout)
        return frame

    def _create_annotation_items_widget(self, data_type, data):
        """Create a widget containing annotation items"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 0, 0, 0)  # Indent content
        layout.setSpacing(4)

        # Show all items
        for item in data:
            item_widget = self._create_annotation_item_widget(data_type, item)
            layout.addWidget(item_widget)

        widget.setLayout(layout)
        return widget

    def _create_annotation_item_widget(self, data_type, item):
        """Create a widget for a single annotation item"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Info layout
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        if data_type == "picks":
            name = f"📍 {item.pickable_object_name}"
            point_count = len(item.points) if hasattr(item, "points") else "N/A"
            details = f"User: {item.user_id} | Session: {item.session_id} | Points: {point_count}"
        elif data_type == "meshes":
            name = f"🕸 {item.pickable_object_name}"
            details = f"User: {item.user_id} | Session: {item.session_id}"
        elif data_type == "segmentations":
            seg_name = getattr(
                item, "name", item.pickable_object_name if hasattr(item, "pickable_object_name") else "Unknown"
            )
            name = f"🖌 {seg_name}"
            details = f"User: {item.user_id} | Session: {item.session_id}"
        else:
            name = str(item)
            details = ""

        # Name label
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #fff; font-weight: bold; font-size: 11px;")
        info_layout.addWidget(name_label)

        # Details label
        if details:
            details_label = QLabel(details)
            details_label.setStyleSheet("color: #999; font-size: 9px;")
            info_layout.addWidget(details_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Add CryoET link if applicable
        link_button = self._create_cryoet_link_button(item)
        if link_button:
            layout.addWidget(link_button)

        widget.setLayout(layout)
        widget.setStyleSheet(
            """
            QWidget {
                background-color: #3d3d3d;
                border-radius: 4px;
            }
        """
        )
        return widget

    def _create_cryoet_link_button(self, item):
        """Create a CryoET Data Portal link button for an item if applicable"""
        try:
            # Import here to avoid circular imports
            from copick.impl.cryoet_data_portal import (
                CopickRunCDP,
                CopickTomogramCDP,
                CopickPicksCDP,
                CopickSegmentationCDP,
            )

            # Check if this is a CryoET Data Portal project
            if hasattr(item, "run") and isinstance(item.run, CopickRunCDP):
                run_id = item.run.portal_run_id

                if hasattr(item, "meta") and hasattr(item.meta, "portal_tomo_id"):
                    # Tomogram link
                    url = f"https://cryoetdataportal.czscience.com/runs/{run_id}?table-tab=Tomograms"
                elif hasattr(item, "meta") and hasattr(item.meta, "portal_annotation_id"):
                    # Annotation link (picks, segmentations)
                    url = f"https://cryoetdataportal.czscience.com/runs/{run_id}?table-tab=Annotations"
                elif (
                    hasattr(item, "voxel_spacing")
                    and hasattr(item.voxel_spacing, "run")
                    and isinstance(item.voxel_spacing.run, CopickRunCDP)
                ):
                    # Voxel spacing or tomogram via voxel spacing
                    run_id = item.voxel_spacing.run.portal_run_id
                    url = f"https://cryoetdataportal.czscience.com/runs/{run_id}"
                else:
                    # General run link
                    url = f"https://cryoetdataportal.czscience.com/runs/{run_id}"

                # Create button
                button = QPushButton("🌐 Portal")
                button.setStyleSheet(
                    """
                    QPushButton {
                        background-color: rgba(0, 122, 255, 0.1);
                        color: #007AFF;
                        border: none;
                        border-radius: 3px;
                        padding: 2px 6px;
                        font-size: 9px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: rgba(0, 122, 255, 0.2);
                    }
                """
                )
                button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
                return button

            return None
        except Exception:
            return None
