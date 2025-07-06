"""ChimeraX-specific implementation of the copick info widget using shared components."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from Qt.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QThreadPool,
)
from Qt.QtGui import QPixmap
from Qt.QtWidgets import QLabel, QTreeView, QWidget

from .async_workers import AsyncWorkerSignals, ThumbnailLoadWorker
from .theme_utils import get_theme_colors

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram

# Import shared components - error out if not available
from copick_shared_ui.widgets.info.info_widget import CopickInfoWidget
from copick_shared_ui.core.models import (
    AbstractImageInterface,
    AbstractInfoSessionInterface,
    AbstractThemeInterface,
    AbstractWorkerInterface,
)


class ChimeraXInfoSessionInterface(AbstractInfoSessionInterface):
    """ChimeraX-specific session interface for info widget."""

    def __init__(self, session: Any):
        self.session = session
        self.current_run: Optional["CopickRun"] = None

    def load_tomogram_and_switch_view(self, tomogram: "CopickTomogram") -> None:
        """Load the tomogram and switch to OpenGL view - replicates tree double-click behavior."""
        # Get the main window and stack widget for view switching
        main_window = self.session.ui.main_window
        stack_widget = main_window._stack

        # Switch to OpenGL view (index 0)
        stack_widget.setCurrentIndex(0)

        # Find the tomogram in the tree and get its QModelIndex
        tomogram_index = self._find_tomogram_in_tree(tomogram)

        if tomogram_index and tomogram_index.isValid():
            # This is exactly what _on_tree_double_click does - just call switch_volume
            copick_tool = self.session.copick
            copick_tool.switch_volume(tomogram_index)

        # Expand the run in the tree widget
        self._expand_run_in_tree()

    def navigate_to_gallery(self) -> None:
        """Navigate back to gallery view."""
        try:
            # Get the main widget and call its navigation method
            copick_tool = self.session.copick
            copick_tool._mw._navigate_to_gallery()
        except Exception as e:
            print(f"Error navigating back to gallery: {e}")

    def expand_run_in_tree(self, run: "CopickRun") -> None:
        """Expand the run in the tree view."""
        self._expand_run_in_tree()

    # get_portal_link is now inherited from AbstractInfoSessionInterface

    def _find_tomogram_in_tree(self, tomogram: "CopickTomogram") -> Optional[QModelIndex]:
        """Find the tomogram in the tree model and return its QModelIndex."""
        copick_tool = self.session.copick
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
            if isinstance(model, QSortFilterProxyModel):
                source_run_index = model.mapToSource(run_index)
                run_item = source_run_index.internalPointer()
            else:
                run_item = run_index.internalPointer()

            if not run_item:
                continue

            # Check if this is the right run
            if hasattr(run_item, "run"):
                if run_item.run.name != tomogram.voxel_spacing.run.name:
                    continue
            elif hasattr(run_item, "name"):
                if run_item.name != tomogram.voxel_spacing.run.name:
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

    def _expand_run_in_tree(self) -> None:
        """Expand the current run and voxel spacing in the tree widget."""
        copick_tool = self.session.copick
        tree_view = copick_tool._mw._tree_view
        model = tree_view.model()

        if model and self.current_run:
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
                        and item.run == self.current_run
                        or hasattr(item, "name")
                        and item.name == self.current_run.name
                    ):
                        tree_view.expand(index)
                        tree_view.setCurrentIndex(index)

                        # Also expand all voxel spacings within this run
                        self._expand_all_voxel_spacings(tree_view, model, index)
                        break

    def _expand_all_voxel_spacings(
        self,
        tree_view: QTreeView,
        model: QAbstractItemModel,
        run_index: QModelIndex,
    ) -> None:
        """Expand all voxel spacings under the given run."""
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


class ChimeraXThemeInterface(AbstractThemeInterface):
    """ChimeraX-specific theme interface."""

    def __init__(self, widget: Optional[QWidget] = None):
        self.widget = widget
        self._theme_change_callbacks: List[callable] = []

    def get_theme_colors(self) -> Dict[str, str]:
        """Get color scheme for current ChimeraX theme."""
        colors = get_theme_colors(self.widget)
        # Map ChimeraX colors to shared UI color names
        return {
            'bg_primary': colors['bg_primary'],
            'bg_secondary': colors['bg_secondary'], 
            'bg_tertiary': colors['bg_tertiary'],
            'bg_quaternary': colors['bg_quaternary'],
            'border_primary': colors['border_primary'],
            'border_secondary': colors['border_secondary'],
            'border_accent': colors['border_accent'],
            'text_primary': colors['text_primary'],
            'text_secondary': colors['text_secondary'],
            'text_muted': colors['text_muted'],
            'accent_primary': colors['accent_blue'],
            'success': colors['status_success_bg'],
            'warning': colors['status_warning_bg'],
            'error': colors['status_error_bg'],
        }

    def get_theme_stylesheet(self) -> str:
        """Get base stylesheet for current ChimeraX theme."""
        from .theme_utils import get_theme_stylesheet
        return get_theme_stylesheet(self.widget)

    def get_button_stylesheet(self, button_type: str = "primary") -> str:
        """Get button stylesheet for current ChimeraX theme."""
        from .theme_utils import get_button_stylesheet
        return get_button_stylesheet(button_type, self.widget)

    def get_input_stylesheet(self) -> str:
        """Get input field stylesheet for current ChimeraX theme."""
        from .theme_utils import get_input_stylesheet
        return get_input_stylesheet(self.widget)

    def connect_theme_changed(self, callback: callable) -> None:
        """Connect to ChimeraX theme change events."""
        self._theme_change_callbacks.append(callback)
        try:
            # Connect to palette change events if available
            from Qt.QtWidgets import QApplication
            app = QApplication.instance()
            if app and hasattr(app, 'paletteChanged'):
                app.paletteChanged.connect(self._emit_theme_changed)
        except Exception:
            pass  # Theme change detection not available

    def _emit_theme_changed(self) -> None:
        """Emit theme changed to all callbacks."""
        for callback in self._theme_change_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Error in theme change callback: {e}")


class ChimeraXImageInterface(AbstractImageInterface):
    """ChimeraX-specific image/pixmap interface."""


    def scale_pixmap(self, pixmap: Any, size: tuple, smooth: bool = True) -> Any:
        """Scale a pixmap to the specified size."""
        try:
            if pixmap is None:
                return None

            width, height = size
            transform_mode = Qt.SmoothTransformation if smooth else Qt.FastTransformation
            return pixmap.scaled(width, height, Qt.KeepAspectRatio, transform_mode)

        except Exception as e:
            print(f"Error scaling pixmap: {e}")
            return pixmap

    def save_pixmap(self, pixmap: Any, path: str) -> bool:
        """Save pixmap to file."""
        try:
            if pixmap is None:
                return False
            return pixmap.save(path)
        except Exception:
            return False

    def load_pixmap(self, path: str) -> Optional[Any]:
        """Load pixmap from file."""
        try:
            pixmap = QPixmap(path)
            return pixmap if not pixmap.isNull() else None
        except Exception:
            return None


class ChimeraXWorkerInterface(AbstractWorkerInterface):
    """ChimeraX-specific worker interface using QThreadPool."""

    def __init__(self, session: Any):
        self.session = session
        self._thread_pool: QThreadPool = QThreadPool()
        self._thread_pool.setMaxThreadCount(4)  # Limit concurrent threads
        self._signals: AsyncWorkerSignals = AsyncWorkerSignals()

    def start_thumbnail_worker(
        self,
        item: Union["CopickRun", "CopickTomogram"],
        thumbnail_id: str,
        callback: callable,
        force_regenerate: bool = False,
    ) -> None:
        """Start a thumbnail loading worker using ChimeraX's QThreadPool."""
        from copick_shared_ui.workers.chimerax import ChimeraXThumbnailWorker, ChimeraXWorkerSignals
        
        # Use unified worker system
        signals = ChimeraXWorkerSignals()
        worker = ChimeraXThumbnailWorker(signals, item, thumbnail_id, force_regenerate)
        
        # Connect to callback
        def on_thumbnail_loaded(loaded_id: str, pixmap: Any, error: Optional[str]):
            if loaded_id == thumbnail_id:
                callback(thumbnail_id, pixmap, error)
        
        signals.thumbnail_loaded.connect(on_thumbnail_loaded)
        self._thread_pool.start(worker)

    def clear_workers(self) -> None:
        """Clear all pending workers."""
        self._thread_pool.clear()

    def shutdown_workers(self, timeout_ms: int = 3000) -> None:
        """Shutdown all workers with timeout."""
        self._thread_pool.clear()
        self._thread_pool.waitForDone(timeout_ms)


class ChimeraXCopickInfoWidget(CopickInfoWidget):
    """ChimeraX-specific copick info widget."""

    def __init__(self, session: Any, parent: Optional[QObject] = None) -> None:
        self.session = session

        # Create platform interfaces
        session_interface = ChimeraXInfoSessionInterface(session)
        theme_interface = ChimeraXThemeInterface(self)
        worker_interface = ChimeraXWorkerInterface(session)
        image_interface = ChimeraXImageInterface()

        super().__init__(
            session_interface=session_interface,
            theme_interface=theme_interface,
            worker_interface=worker_interface,
            image_interface=image_interface,
            parent=parent,
        )

        # Store reference to session interface for run tracking
        self._session_interface = session_interface

        # Register for app quit trigger to ensure proper cleanup
        session.triggers.add_handler("app quit", self._app_quit)

        # Connect tomogram clicked signal to load tomogram
        self.tomogram_clicked.connect(self._on_tomogram_clicked)

    def _app_quit(self, *args: Any) -> None:
        """Handle app quit trigger to ensure proper cleanup."""
        if not self._is_destroyed:
            # Clear thread pool immediately on app quit
            self.worker_interface.clear_workers()
            self.deleteLater()

    def _on_tomogram_clicked(self, tomogram: "CopickTomogram") -> None:
        """Handle tomogram click by loading it in ChimeraX."""
        # Use the session interface to load tomogram and switch view
        self.session_interface.load_tomogram_and_switch_view(tomogram)

    def set_run(self, run: Optional["CopickRun"]) -> None:
        """Set the current run object and make it available to session interface."""
        # Store reference for session interface
        self._session_interface.current_run = run
        
        # Call parent implementation
        super().set_run(run)

    def delete(self) -> None:
        """Properly clean up the widget."""
        if self._is_destroyed:
            return

        self._is_destroyed = True

        # Stop thread pool
        self.worker_interface.shutdown_workers(timeout_ms=3000)

        # Call parent cleanup
        super().delete()


# Alias for backward compatibility
CopickInfoWidget = ChimeraXCopickInfoWidget