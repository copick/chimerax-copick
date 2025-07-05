"""Gallery widget for displaying copick runs in a grid layout with thumbnails."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from chimerax.core.session import Session
from Qt.QtCore import QModelIndex, QSortFilterProxyModel, Qt, QThreadPool, Signal, Slot
from Qt.QtGui import QPixmap
from Qt.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .async_workers import AsyncWorkerSignals, RunThumbnailWorker
from .theme_utils import (
    get_theme_stylesheet,
    get_button_stylesheet,
    get_input_stylesheet,
    get_theme_colors,
)

# Import copick models only when needed to avoid circular import issues
if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


class RunCard(QFrame):
    """Individual run card widget with thumbnail and info"""

    clicked = Signal(object)  # Emits the run object
    info_requested = Signal(object)  # Emits the run object for info view

    def __init__(self, run: "CopickRun", parent: Optional[QWidget] = None, objectName: str = "run_card") -> None:
        super().__init__(parent)
        self.setObjectName(objectName)
        self.run: "CopickRun" = run
        self.thumbnail_pixmap: Optional[QPixmap] = None
        self._setup_ui()
        self._setup_style()

    def _setup_ui(self) -> None:
        """Setup the card UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Thumbnail container with info button overlay
        thumbnail_container = QWidget()
        thumbnail_container.setFixedSize(200, 200)

        # Thumbnail label (placeholder)
        self.thumbnail_label = QLabel(thumbnail_container, objectName="run_card_thumbnail_label")
        self.thumbnail_label.setFixedSize(200, 200)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        # Style will be applied via parent widget
        self.thumbnail_label.setText("Loading...")

        # Info button overlay (floating in top-right corner)
        self.info_button = QPushButton("ℹ️", thumbnail_container, objectName="run_card_info_button")
        self.info_button.setFixedSize(24, 24)
        self.info_button.setToolTip("View run details")
        # Style will be applied via parent widget
        self.info_button.move(170, 6)  # Position in top-right corner with margin
        self.info_button.clicked.connect(lambda: self.info_requested.emit(self.run))

        layout.addWidget(thumbnail_container)

        # Run name label
        self.name_label = QLabel(self.run.name, objectName="run_card_name_label")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        # Style will be applied via parent widget
        layout.addWidget(self.name_label)

        # Status label (for error display)
        self.status_label = QLabel(objectName="run_card_status_label")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)
        # Style will be applied via parent widget
        layout.addWidget(self.status_label)

    def _setup_style(self) -> None:
        """Setup the card styling"""
        self.setFixedSize(220, 260)
        self.setCursor(Qt.PointingHandCursor)
        # Style will be applied by parent widget
        
    def _apply_card_styling(self, parent_widget: QWidget) -> None:
        """Apply theme-aware styling to this card"""
        colors = get_theme_colors(parent_widget)
        
        # Apply individual component styles
        self.thumbnail_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {colors['bg_secondary']};
                border: 1px solid {colors['border_primary']};
                border-radius: 4px;
                color: {colors['text_muted']};
            }}
        """)
        
        self.name_label.setStyleSheet(
            f"""
            QLabel {{
                color: {colors['text_primary']};
                font-weight: bold;
                font-size: 12px;
                padding: 4px;
            }}
        """)
        
        self.status_label.setStyleSheet(
            f"""
            QLabel {{
                color: #ff6b6b;
                font-size: 10px;
                padding: 2px;
            }}
        """)
        
        self.info_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: rgba(70, 130, 200, 180);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(70, 130, 200, 220);
            }}
            QPushButton:pressed {{
                background-color: rgba(70, 130, 200, 255);
            }}
        """)

    def set_thumbnail(self, pixmap: Optional[QPixmap]) -> None:
        """Set the thumbnail pixmap"""
        if pixmap:
            # Scale pixmap to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(self.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled_pixmap)
            self.thumbnail_pixmap = pixmap
        else:
            self.thumbnail_label.setText("No thumbnail")

    def set_error(self, error_message: str) -> None:
        """Show error state"""
        self.thumbnail_label.setText("Error")
        self.status_label.setText(f"Error: {error_message}")
        self.status_label.setVisible(True)

    def mousePressEvent(self, event: Any) -> None:
        """Handle mouse click"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.run)
        super().mousePressEvent(event)


class CopickGalleryWidget(QWidget):
    """Gallery widget displaying copick runs in a grid with thumbnails"""

    run_selected = Signal(object)  # Emits selected run
    info_requested = Signal(object)  # Emits run for info view

    def __init__(self, session: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Initialize debug log file
        try:
            with open("/tmp/copick_gallery_debug.log", "w") as f:
                f.write("=== CopickGalleryWidget Debug Log Started ===\n")
        except Exception:
            pass

        self.session: Session = session
        self.copick_root: Optional[Any] = None
        self.runs: List["CopickRun"] = []
        self.filtered_runs: List["CopickRun"] = []
        self.all_run_cards: Dict[str, RunCard] = {}  # run_name -> RunCard (persistent cache)
        self.visible_run_cards: Dict[str, RunCard] = {}  # run_name -> RunCard (currently visible)
        self.search_filter: str = ""
        self.thumbnail_cache: Dict[str, QPixmap] = {}  # run_name -> QPixmap (thumbnail cache)
        self._grid_dirty: bool = True  # Flag to track if grid needs updating

        # Async components
        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(16)
        self._signals = AsyncWorkerSignals()
        self._signals.thumbnail_loaded.connect(self._on_thumbnail_loaded)

        # Track widget lifecycle
        self._is_destroyed: bool = False

        self._setup_ui()
        
        # Apply theme-aware styling
        self._apply_styling()
        
        # Connect to theme change events
        self._connect_theme_events()

        # Register for app quit trigger
        session.triggers.add_handler("app quit", self._app_quit)

    def _setup_ui(self) -> None:
        """Setup the gallery UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("📸 Run Gallery", objectName="gallery_title_label")
        # Style will be applied via parent widget
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Regenerate thumbnails button
        self.regenerate_button = QPushButton("🔄 Regenerate Thumbnails", objectName="regenerate_thumbnails_button")
        self.regenerate_button.setToolTip("Clear cache and regenerate all thumbnails")
        # Style will be applied via parent widget
        self.regenerate_button.clicked.connect(self._on_regenerate_thumbnails)
        header_layout.addWidget(self.regenerate_button)

        # Search box
        self.search_box = QLineEdit(objectName="gallery_search_input")
        self.search_box.setPlaceholderText("Search runs...")
        self.search_box.setFixedWidth(200)
        # Style will be applied via parent widget
        self.search_box.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self.search_box)

        layout.addLayout(header_layout)

        # Scroll area for grid
        self.scroll_area = QScrollArea(objectName="gallery_scroll_area")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Style will be applied via parent widget
        layout.addWidget(self.scroll_area)

        # Grid widget
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll_area.setWidget(self.grid_widget)

        # Empty state label
        self.empty_label = QLabel("No runs to display", objectName="gallery_empty_state_label")
        self.empty_label.setAlignment(Qt.AlignCenter)
        # Style will be applied via parent widget
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

    def _app_quit(self, *args: Any) -> None:
        """Handle app quit trigger"""
        if not self._is_destroyed:
            # Clear thread pool immediately on app quit
            self._thread_pool.clear()
            # Don't wait for completion during app quit to avoid hanging
            self.deleteLater()

    def delete(self) -> None:
        """Clean up widget resources"""
        if self._is_destroyed:
            return

        self._is_destroyed = True

        self._thread_pool.clear()
        self._thread_pool.waitForDone(3000)

        # Clear caches
        self.all_run_cards.clear()
        self.visible_run_cards.clear()
        self.thumbnail_cache.clear()

    def set_copick_root(self, copick_root: Optional[Any]) -> None:
        """Set the copick root and load runs"""
        # Clear thread pool to cancel any pending thumbnail loads from previous session
        self._thread_pool.clear()

        # Clear caches when root changes
        self.all_run_cards.clear()
        self.visible_run_cards.clear()
        self.thumbnail_cache.clear()
        self._grid_dirty = True

        self.copick_root = copick_root
        if copick_root:
            self.runs = list(copick_root.runs)
            self.filtered_runs = self.runs.copy()
            self._update_grid()
        else:
            self.runs = []
            self.filtered_runs = []
            self._clear_grid()

    def apply_search_filter(self, filter_text: str) -> None:
        """Apply search filter from external source (like tree widget)"""
        self.search_filter = filter_text.lower()
        self.search_box.setText(filter_text)  # Update search box
        self._filter_runs()
        self._update_grid()

    @Slot(str)
    def _on_search_changed(self, text: str):
        """Handle search box text change"""
        self.search_filter = text.lower()
        self._filter_runs()
        self._update_grid()

    def _filter_runs(self) -> None:
        """Filter runs based on search text"""
        old_filtered = {run.name for run in self.filtered_runs}

        if not self.search_filter:
            self.filtered_runs = self.runs.copy()
        else:
            self.filtered_runs = [run for run in self.runs if self.search_filter in run.name.lower()]

        # Check if filtering actually changed the results
        new_filtered = {run.name for run in self.filtered_runs}
        self._grid_dirty = old_filtered != new_filtered

    def _clear_grid(self) -> None:
        """Clear all cards from the grid layout (but keep them cached)"""
        # Remove all cards from layout but don't delete them
        for i in reversed(range(self.grid_layout.count())):
            child = self.grid_layout.itemAt(i).widget()
            if child:
                # Temporarily reparent to None to remove from layout without deleting
                child.setParent(None)

        self.visible_run_cards.clear()
        self.empty_label.setVisible(True)
        self.grid_widget.setVisible(False)

    def _update_grid(self) -> None:
        """Update the grid with current filtered runs using cached cards"""
        if self._is_destroyed:
            return

        # Only update if grid is dirty
        if not self._grid_dirty:
            return

        # Clear existing grid layout (but keep cards cached)
        self._clear_grid()

        if not self.filtered_runs:
            self.empty_label.setVisible(True)
            self.grid_widget.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.grid_widget.setVisible(True)

        # Calculate grid dimensions
        cards_per_row = max(1, (self.scroll_area.width() - 30) // 235)  # 220 card width + 15 spacing

        # Add cards for filtered runs (reuse cached cards where possible)
        for i, run in enumerate(self.filtered_runs):
            row = i // cards_per_row
            col = i % cards_per_row

            # Check if we already have this card cached
            if run.name in self.all_run_cards:
                # Reuse existing card
                card = self.all_run_cards[run.name]
            else:
                # Create new card
                card = RunCard(run)
                card.clicked.connect(self._on_run_card_clicked)
                card.info_requested.connect(self._on_run_info_requested)
                card._apply_card_styling(self)  # Apply theme-aware styling
                self.all_run_cards[run.name] = card

                # Check if we have a cached thumbnail
                if run.name in self.thumbnail_cache:
                    card.set_thumbnail(self.thumbnail_cache[run.name])
                else:
                    # Start thumbnail loading
                    self._load_run_thumbnail(run, run.name)

            # Add to visible cards and grid layout
            self.visible_run_cards[run.name] = card
            self.grid_layout.addWidget(card, row, col)

        # Mark grid as clean
        self._grid_dirty = False

    def _load_run_thumbnail(self, run: "CopickRun", thumbnail_id: str, force_regenerate: bool = False) -> None:
        """Start async loading of run thumbnail"""
        if self._is_destroyed:
            return

        worker = RunThumbnailWorker(self._signals, run, thumbnail_id, force_regenerate)
        self._thread_pool.start(worker)

    @Slot(str, object, object)
    def _on_thumbnail_loaded(self, thumbnail_id: str, pixmap: Optional[QPixmap], error: Optional[str]) -> None:
        """Handle thumbnail loading completion"""
        if self._is_destroyed or thumbnail_id not in self.all_run_cards:
            return

        card = self.all_run_cards[thumbnail_id]

        if error:
            card.set_error(error)
        else:
            card.set_thumbnail(pixmap)
            # Cache the thumbnail for future use
            if pixmap:
                self.thumbnail_cache[thumbnail_id] = pixmap

    @Slot(object)
    def _on_run_card_clicked(self, run: "CopickRun") -> None:
        """Handle run card click - switch to 3D view and emit signal for main widget to handle"""
        try:
            # Switch to OpenGL view (index 0) - let main widget handle the volume loading
            main_window = self.session.ui.main_window
            stack_widget = main_window._stack
            stack_widget.setCurrentIndex(0)

            # Emit signal to let main widget handle tomogram loading and tree updates
            self.run_selected.emit(run)

        except Exception as e:
            print(f"Gallery: Error handling run card click: {e}")
            # Still emit the signal as fallback
            self.run_selected.emit(run)

    def _select_best_tomogram_from_run(self, run: "CopickRun") -> Optional["CopickTomogram"]:
        """Select the best tomogram from a run (prefer denoised, highest voxel spacing)"""
        try:
            all_tomograms = []

            # Collect all tomograms from all voxel spacings
            for vs in run.voxel_spacings:
                for tomo in vs.tomograms:
                    all_tomograms.append(tomo)

            if not all_tomograms:
                return None

            # Preference order for tomogram types (denoised first)
            preferred_types = ["denoised", "wbp"]

            # Group by voxel spacing (highest first)
            voxel_spacings = sorted({tomo.voxel_spacing.voxel_size for tomo in all_tomograms}, reverse=True)

            # Try each voxel spacing, starting with highest
            for vs_size in voxel_spacings:
                vs_tomograms = [tomo for tomo in all_tomograms if tomo.voxel_spacing.voxel_size == vs_size]

                # Try preferred types in order
                for preferred_type in preferred_types:
                    for tomo in vs_tomograms:
                        if preferred_type.lower() in tomo.tomo_type.lower():
                            return tomo

                # If no preferred type found, return the first tomogram at this voxel spacing
                if vs_tomograms:
                    return vs_tomograms[0]

            # Fallback: return any tomogram
            return all_tomograms[0] if all_tomograms else None

        except Exception as e:
            print(f"Gallery: Error selecting best tomogram: {e}")
            return None

    def _load_tomogram_and_switch_view(self, tomogram: "CopickTomogram") -> None:
        """Load the tomogram and switch to OpenGL view - uses the same pattern as info widget"""
        try:
            copick_tool = self.session.copick

            # Get the main window and stack widget for view switching
            main_window = self.session.ui.main_window
            stack_widget = main_window._stack

            # Switch to OpenGL view (index 0)
            stack_widget.setCurrentIndex(0)

            # Find the tomogram in the tree and get its QModelIndex using the safe approach
            tomogram_index = self._find_tomogram_in_tree(tomogram)

            if tomogram_index and tomogram_index.isValid():
                # This is exactly what _on_tree_double_click does - just call switch_volume
                copick_tool.switch_volume(tomogram_index)

            # Expand the run in the tree widget
            self._expand_run_in_tree(tomogram)

        except Exception as e:
            print(f"Gallery: Error loading tomogram: {e}")

    def _find_tomogram_in_tree(self, tomogram: "CopickTomogram") -> Optional[QModelIndex]:
        """Find the tomogram in the tree model and return its QModelIndex - safe approach"""
        try:
            copick_tool = self.session.copick
            tree_view = copick_tool._mw._tree_view
            model = tree_view.model()

            if not model:
                return None

            # Get current run from tomogram
            current_run = tomogram.voxel_spacing.run

            # Navigate the tree structure: Root -> Run -> VoxelSpacing -> Tomogram
            for run_row in range(model.rowCount()):
                run_index = model.index(run_row, 0)
                if not run_index.isValid():
                    continue

                # Get the actual item (handling proxy model if present)
                if isinstance(model, QSortFilterProxyModel):
                    source_run_index = model.mapToSource(run_index)
                    run_item = source_run_index.internalPointer()
                else:
                    run_item = run_index.internalPointer()

                if not run_item:
                    continue

                # Check if this is the right run
                if hasattr(run_item, "run"):
                    if run_item.run.name != current_run.name:
                        continue
                elif hasattr(run_item, "name"):
                    if run_item.name != current_run.name:
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
                    if isinstance(model, QSortFilterProxyModel):
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
                        if isinstance(model, QSortFilterProxyModel):
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

        except Exception as e:
            print(f"Gallery: Error finding tomogram in tree: {e}")
            return None

    def _expand_run_in_tree(self, tomogram: "CopickTomogram") -> None:
        """Expand the current run and voxel spacing in the tree widget"""
        try:
            copick_tool = self.session.copick
            tree_view = copick_tool._mw._tree_view
            model = tree_view.model()

            if not model:
                return

            # Get current run from tomogram
            current_run = tomogram.voxel_spacing.run

            # Find the run in the tree model and expand it
            for row in range(model.rowCount()):
                index = model.index(row, 0)
                if index.isValid():
                    # Get the item and check if it matches our current run
                    if isinstance(model, QSortFilterProxyModel):
                        source_index = model.mapToSource(index)
                        item = source_index.internalPointer()
                    else:
                        item = index.internalPointer()

                    # Check if this is the right run
                    if (
                        hasattr(item, "run")
                        and item.run == current_run
                        or hasattr(item, "name")
                        and item.name == current_run.name
                    ):
                        tree_view.expand(index)
                        tree_view.setCurrentIndex(index)

                        # Also expand all voxel spacings within this run
                        self._expand_all_voxel_spacings(model, index)
                        break

        except Exception as e:
            print(f"Gallery: Error expanding run in tree: {e}")

    def _expand_all_voxel_spacings(
        self,
        run_index: QModelIndex,
    ) -> None:
        """Expand all voxel spacings under the given run"""
        try:
            copick_tool = self.session.copick
            tree_view = copick_tool._mw._tree_view
            model = tree_view.model()

            # Force lazy loading of voxel spacings
            if isinstance(model, QSortFilterProxyModel):
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

        except Exception as e:
            print(f"Gallery: Error expanding voxel spacings: {e}")
            
    def _apply_styling(self) -> None:
        """Apply theme-aware styling to all components"""
        # Apply main stylesheet
        self.setStyleSheet(get_theme_stylesheet(self))
        
        colors = get_theme_colors(self)
        
        # Gallery-specific styles
        gallery_styles = f"""
            QLabel[objectName="gallery_title_label"] {{
                color: {colors['text_primary']};
                font-size: 18px;
                font-weight: bold;
                padding: 8px;
            }}
            
            QLabel[objectName="gallery_empty_state_label"] {{
                color: {colors['text_muted']};
                font-size: 14px;
                padding: 40px;
            }}
            
            QScrollArea[objectName="gallery_scroll_area"] {{
                border: none;
                background-color: {colors['bg_primary']};
            }}
            
            RunCard {{
                background-color: {colors['bg_tertiary']};
                border: 1px solid {colors['border_secondary']};
                border-radius: 8px;
            }}
            
            RunCard:hover {{
                border: 2px solid {colors['border_accent']};
                background-color: {colors['bg_quaternary']};
            }}
            
            QLabel[objectName="run_card_thumbnail_label"] {{
                background-color: {colors['bg_secondary']};
                border: 1px solid {colors['border_primary']};
                border-radius: 4px;
                color: {colors['text_muted']};
            }}
            
            QLabel[objectName="run_card_name_label"] {{
                color: {colors['text_primary']};
                font-weight: bold;
                font-size: 12px;
                padding: 4px;
            }}
            
            QLabel[objectName="run_card_status_label"] {{
                color: #ff6b6b;
                font-size: 10px;
                padding: 2px;
            }}
            
            QPushButton[objectName="run_card_info_button"] {{
                background-color: rgba(70, 130, 200, 180);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }}
            
            QPushButton[objectName="run_card_info_button"]:hover {{
                background-color: rgba(70, 130, 200, 220);
            }}
            
            QPushButton[objectName="run_card_info_button"]:pressed {{
                background-color: rgba(70, 130, 200, 255);
            }}
        """
        
        # Apply combined styles
        self.setStyleSheet(get_theme_stylesheet(self) + gallery_styles)
        
        # Apply button styles
        self.regenerate_button.setStyleSheet(get_button_stylesheet("accent", self))
        
        # Apply input styles
        self.search_box.setStyleSheet(get_input_stylesheet(self))
        
    def _connect_theme_events(self) -> None:
        """Connect to theme change events"""
        try:
            # Connect to palette change events if available
            from Qt.QtWidgets import QApplication
            app = QApplication.instance()
            if app and hasattr(app, 'paletteChanged'):
                app.paletteChanged.connect(self._on_theme_changed)
        except Exception:
            pass  # Theme change detection not available
            
    def _on_theme_changed(self) -> None:
        """Handle theme change by reapplying styles"""
        self._apply_styling()
        
        # Update all existing run cards
        for card in self.all_run_cards.values():
            card._apply_card_styling(self)

    @Slot()
    def _on_regenerate_thumbnails(self) -> None:
        """Handle regenerate thumbnails button click"""
        # Clear both memory and disk cache
        from ..io.thumbnail_cache import get_global_cache

        cache = get_global_cache()
        cache.clear_cache()

        # Clear memory cache
        self.thumbnail_cache.clear()

        # Reset all cards to loading state
        for card in self.all_run_cards.values():
            card.thumbnail_label.setText("Regenerating...")
            card.thumbnail_label.setPixmap(QPixmap())  # Clear existing pixmap
            card.status_label.setVisible(False)

        # Force regenerate all visible thumbnails
        for run in self.filtered_runs:
            if run.name in self.all_run_cards:
                self._load_run_thumbnail(run, run.name, force_regenerate=True)

    @Slot(object)
    def _on_run_info_requested(self, run: "CopickRun") -> None:
        """Handle run info button click"""
        self.info_requested.emit(run)

    def resizeEvent(self, event: Any) -> None:
        """Handle widget resize to update grid layout"""
        super().resizeEvent(event)
        # Mark grid as dirty and trigger update to recalculate cards per row
        if self.filtered_runs:
            self._grid_dirty = True
            self._update_grid()
