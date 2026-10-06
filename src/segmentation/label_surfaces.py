"""Surfaces for label volumes (instance and panoptic segmentations): one ChimeraX ``Surface`` per label, grouped under
a parent model, coloured per instance (copick-shared-ui colours, so an ID looks the same as its picks and filaments).

The geometry is computed with ChimeraX's C routine ``chimerax.segment.segmentation_surfaces`` (uint8 to uint32 label
maps), off the UI thread; surfaces are created on the main thread.
"""

from typing import Dict, Iterable, Optional, Tuple

import numpy as np
import zarr
from chimerax.core.models import Model, Surface

Geometry = Tuple[np.ndarray, np.ndarray, np.ndarray]  # vertices, normals, triangles


def level_keys(group) -> list:
    return sorted((k for k in group if k.isdigit()), key=int)


def level_voxel_size(group, path: str, base_voxel_size: float) -> float:
    """Spatial voxel size of a pyramid level from the OME-NGFF metadata (scale only; copick writes no translation)."""
    try:
        for ds in group.attrs["multiscales"][0]["datasets"]:
            if ds["path"] == path:
                for t in ds["coordinateTransformations"]:
                    if t["type"] == "scale":
                        return float(t["scale"][-1])
    except (KeyError, IndexError, TypeError):
        pass
    return base_voxel_size * 2 ** int(path)


def read_label_level(seg, level: int) -> Tuple[np.ndarray, float, int]:
    """Read one pyramid level of a segmentation: ``(array, voxel size of that level, level used)``. Panoptic arrays
    come back as ``(2, Z, Y, X)``."""
    group = zarr.open(seg.zarr(), mode="r")
    keys = level_keys(group)
    if not keys:
        raise ValueError(f"No pyramid levels in segmentation {seg.name}")
    level = max(0, min(int(level), len(keys) - 1))
    path = keys[level]
    return np.asarray(group[path]), level_voxel_size(group, path, seg.voxel_size), level


def compute_label_surfaces(
    volume: np.ndarray,
    voxel_size: float,
    ids: Optional[Iterable[int]] = None,
) -> Dict[int, Geometry]:
    """Surface geometry per label of a ``(Z, Y, X)`` label volume, in Angstrom. ``ids`` restricts the labels."""
    from chimerax.segment import segmentation_surfaces
    from chimerax.surface import calculate_vertex_normals

    vol = np.ascontiguousarray(volume)
    if vol.dtype.kind not in "ui" or vol.dtype.itemsize > 4:
        vol = vol.astype(np.uint32)
    wanted = None if ids is None else {int(i) for i in ids}
    out: Dict[int, Geometry] = {}
    if wanted is not None and len(wanted) <= 8:
        # A few labels: compute each on its bounding box (cheap partial rebuilds after edits).
        for label in wanted:
            idx = np.nonzero(vol == label)
            if len(idx[0]) == 0:
                continue
            lo = [max(0, int(a.min()) - 1) for a in idx]
            hi = [int(a.max()) + 2 for a in idx]
            sub = np.ascontiguousarray((vol[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] == label).astype(np.uint8))
            for _rid, va, ta in segmentation_surfaces(sub):
                va = (va + np.array([lo[2], lo[1], lo[0]], dtype=np.float32)) * voxel_size
                out[label] = (va.astype(np.float32), calculate_vertex_normals(va, ta), ta)
        return out
    for label, va, ta in segmentation_surfaces(vol):
        label = int(label)
        if label == 0 or (wanted is not None and label not in wanted):
            continue
        va = (va * voxel_size).astype(np.float32)
        out[label] = (va, calculate_vertex_normals(va, ta), ta)
    return out


class LabelSurfaceModel(Model):
    """A parent model holding one surface per label key."""

    def __init__(self, name: str, session):
        Model.__init__(self, name, session)
        self.surfaces: Dict[int, Surface] = {}
        self._hidden = set()

    def set_surfaces(
        self,
        geometry: Dict[int, Geometry],
        colors: Dict[int, Iterable[int]],
        names: Optional[Dict[int, str]] = None,
        replace: bool = True,
    ) -> None:
        """Create or update the surfaces of ``geometry``; with ``replace``, drop surfaces of keys not in it."""
        if replace:
            for key in [k for k in self.surfaces if k not in geometry]:
                self.surfaces.pop(key).delete()
        for key, (va, na, ta) in geometry.items():
            surf = self.surfaces.get(key)
            if surf is None or surf.deleted:
                surf = Surface((names or {}).get(key, f"label {key}"), self.session)
                surf.clip_cap = True
                self.add([surf])
                self.surfaces[key] = surf
            surf.set_geometry(va, na, ta)
            surf.color = np.asarray(colors.get(key, (180, 180, 180, 255)), dtype=np.uint8)
            surf.display = key not in self._hidden
            surf.copick_label = key

    def remove_keys(self, keys: Iterable[int]) -> None:
        for key in keys:
            surf = self.surfaces.pop(int(key), None)
            if surf is not None and not surf.deleted:
                surf.delete()

    def set_visible_keys(self, keys: Iterable[int]) -> None:
        keys = {int(k) for k in keys}
        self._hidden = set(self.surfaces) - keys
        for key, surf in self.surfaces.items():
            surf.display = key in keys

    def key_for_surface(self, surface) -> Optional[int]:
        return getattr(surface, "copick_label", None)
