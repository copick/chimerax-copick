"""Shared async workers for copick UI components."""

from typing import Optional
import numpy as np
import zarr
from Qt.QtCore import QRunnable, Signal, QObject
from ..io.thumbnail_cache import get_global_cache


class AsyncWorkerSignals(QObject):
    """Signals for async workers to communicate with UI thread."""

    data_loaded = Signal(str, object, str)  # data_type, data, error
    thumbnail_loaded = Signal(str, object, object)  # thumbnail_id, pixmap, error


class DataLoadWorker(QRunnable):
    """Worker for loading run data in background thread"""

    def __init__(self, signals, run, data_type):
        super().__init__()
        self.signals = signals
        self.run = run
        self.data_type = data_type
        self.setAutoDelete(True)

    def run(self):
        """Load data and update widget via signals"""
        try:
            if self.data_type == "voxel_spacings":
                # Load voxel spacings (lazy loaded)
                data = list(self.run.voxel_spacings)
                self.signals.data_loaded.emit(self.data_type, data, None)
            elif self.data_type == "tomograms":
                # Load all tomograms across all voxel spacings
                tomograms = []
                for vs in self.run.voxel_spacings:
                    tomograms.extend(list(vs.tomograms))
                self.signals.data_loaded.emit(self.data_type, tomograms, None)
            elif self.data_type == "picks":
                # Load picks
                data = list(self.run.picks)
                self.signals.data_loaded.emit(self.data_type, data, None)
            elif self.data_type == "meshes":
                # Load meshes
                data = list(self.run.meshes)
                self.signals.data_loaded.emit(self.data_type, data, None)
            elif self.data_type == "segmentations":
                # Load segmentations
                data = list(self.run.segmentations)
                self.signals.data_loaded.emit(self.data_type, data, None)
        except Exception as e:
            # Send error signal
            self.signals.data_loaded.emit(self.data_type, None, str(e))


class ThumbnailLoadWorker(QRunnable):
    """Worker for loading tomogram thumbnails in background thread"""

    def __init__(self, signals, tomogram, thumbnail_id, force_regenerate=False):
        super().__init__()
        self.signals = signals
        self.tomogram = tomogram
        self.thumbnail_id = thumbnail_id
        self.force_regenerate = force_regenerate
        self.setAutoDelete(True)

    def run(self):
        """Load thumbnail and update widget via signals"""
        try:
            # Get the thumbnail cache
            cache = get_global_cache()

            # Generate cache key for this tomogram
            cache_key = cache.get_cache_key(
                run_name=self.tomogram.voxel_spacing.run.name,
                tomogram_type=self.tomogram.tomo_type,
                voxel_spacing=self.tomogram.voxel_spacing.voxel_size,
            )

            # Try to load from cache first (unless force regenerate)
            if not self.force_regenerate and cache.has_thumbnail(cache_key):
                cached_pixmap = cache.load_thumbnail(cache_key)
                if cached_pixmap is not None:
                    # print(f"Loaded thumbnail from cache for {self.thumbnail_id}")
                    self.signals.thumbnail_loaded.emit(self.thumbnail_id, cached_pixmap, None)
                    return

            # Load from copick data if not in cache or force regenerate
            # print(f"Generating thumbnail from copick data for {self.thumbnail_id}")

            # Try all available zarr groups from lowest to highest resolution
            zarr_groups_to_try = ["2", "1", "0"]  # Start with lowest resolution first
            zarr_array = None

            for zarr_group in zarr_groups_to_try:
                try:
                    # Use the faster zarr-based API: zarr.open(tomogram.zarr())[group]
                    zarr_store = zarr.open(self.tomogram.zarr())
                    zarr_array = zarr_store[zarr_group]
                    break
                except Exception:
                    continue

            if zarr_array is None:
                # Fallback: try the convenience method
                full_array = self.tomogram.numpy(zarr_group="2")  # Default to lowest resolution
                # Get array dimensions
                shape = full_array.shape
                z_center = shape[0] // 2
                # Extract full X/Y extent at center Z slice
                data_slice = full_array[z_center, :, :]
            else:
                # Get array dimensions directly from zarr
                shape = zarr_array.shape
                z_center = shape[0] // 2

                # Extract full X/Y extent at center Z slice directly from zarr (faster)
                data_slice = np.array(zarr_array[z_center, :, :])

            # Generate thumbnail from data slice
            pixmap = self._array_to_pixmap(data_slice)

            # Save to cache
            # if cache.save_thumbnail(cache_key, pixmap):
            # print(f"Saved thumbnail to cache for {self.thumbnail_id}")
            # else:
            # print(f"Failed to save thumbnail to cache for {self.thumbnail_id}")

            self.signals.thumbnail_loaded.emit(self.thumbnail_id, pixmap, None)

        except Exception as e:
            # Send error signal
            self.signals.thumbnail_loaded.emit(self.thumbnail_id, None, str(e))

    def _array_to_pixmap(self, data_array):
        """Convert numpy array to QPixmap for display"""
        from Qt.QtGui import QPixmap, QImage

        # Normalize to 0-255 range
        min_val = np.min(data_array)
        max_val = np.max(data_array)

        if max_val > min_val:
            normalized = ((data_array - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(data_array, dtype=np.uint8)

        # Convert to QImage (grayscale)
        height, width = normalized.shape
        bytes_per_line = width
        q_image = QImage(normalized.data, width, height, bytes_per_line, QImage.Format_Grayscale8)

        # Convert to QPixmap
        return QPixmap.fromImage(q_image)


class RunThumbnailWorker(QRunnable):
    """Worker for selecting and loading best tomogram thumbnail for a run"""

    def __init__(self, signals, run, thumbnail_id, force_regenerate=False):
        super().__init__()
        self.signals = signals
        self.run = run
        self.thumbnail_id = thumbnail_id
        self.force_regenerate = force_regenerate
        self.setAutoDelete(True)

    def run(self):
        """Select best tomogram and load its thumbnail"""
        try:
            # Find the best tomogram for this run
            best_tomogram = self._select_best_tomogram()

            if best_tomogram is None:
                self.signals.thumbnail_loaded.emit(self.thumbnail_id, None, "No suitable tomogram found")
                return

            # Load thumbnail for the selected tomogram
            thumbnail_worker = ThumbnailLoadWorker(
                self.signals, best_tomogram, self.thumbnail_id, self.force_regenerate
            )
            thumbnail_worker.run()

        except Exception as e:
            self.signals.thumbnail_loaded.emit(self.thumbnail_id, None, str(e))

    def _select_best_tomogram(self):
        """Select the best tomogram (prefer denoised, highest voxel spacing)"""
        try:
            all_tomograms = []

            # Collect all tomograms from all voxel spacings
            for vs in self.run.voxel_spacings:
                for tomo in vs.tomograms:
                    all_tomograms.append(tomo)

            if not all_tomograms:
                return None

            # Preference order for tomogram types (denoised first)
            preferred_types = ["denoised", "wbp", "ribo", "defocus"]

            # Group by voxel spacing (highest first)
            voxel_spacings = sorted(set(tomo.voxel_spacing.voxel_size for tomo in all_tomograms), reverse=True)

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

        except Exception:
            return None
