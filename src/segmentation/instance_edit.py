"""Editing state for an instance segmentation in ChimeraX: an in-memory label volume with a sphere brush, picking,
merge / delete, a bounding-box undo stack, and saving through copick (``new_segmentation(is_instance=True)``).

ChimeraX's own segmentation tool writes only 0/1 masks, so multi-ID editing works on this numpy array; the viewer
rebuilds the surfaces of the IDs each edit touches. Qt-free.
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
from copick_shared_ui.util.instances import delete_labels, label_bboxes, label_counts, merge_labels, next_instance_id

MAX_UNDO = 20


class InstanceEditSession:
    """An instance segmentation being edited.

    Args:
        run: The copick run.
        object_name: Pickable object the instances belong to.
        user_id, session_id: Identity used when saving.
        volume: ``(Z, Y, X)`` instance IDs.
        voxel_size: Voxel size of ``volume`` in Angstrom (the loaded pyramid level).
        base_voxel_size: Voxel spacing the segmentation is stored at (level 0).
        level: Pyramid level of ``volume`` (0 = full resolution).
        source: The ``CopickSegmentation`` it was opened from, if any.
    """

    def __init__(
        self,
        run: Any,
        object_name: str,
        user_id: str,
        session_id: str,
        volume: np.ndarray,
        voxel_size: float,
        base_voxel_size: float,
        level: int = 0,
        source: Any = None,
    ):
        self.run = run
        self.object_name = object_name
        self.user_id = user_id
        self.session_id = session_id
        self.volume = np.ascontiguousarray(volume)
        if self.volume.dtype.kind not in "ui" or self.volume.dtype.itemsize < 2:
            self.volume = self.volume.astype(np.uint16)
        self.voxel_size = float(voxel_size)
        self.base_voxel_size = float(base_voxel_size)
        self.level = int(level)
        self.source = source
        self.current_id = 1
        self.dirty = False
        self._undo: List[Tuple[Tuple[slice, slice, slice], np.ndarray]] = []
        self._counts: Optional[Dict[int, int]] = None
        self._bboxes: Optional[Dict[int, Tuple[slice, slice, slice]]] = None
        self.current_id = self.next_id()

    # -- queries ---------------------------------------------------------------------------------------------------

    @property
    def read_only(self) -> bool:
        return str(self.session_id) == "0" or bool(getattr(self.source, "read_only", False))

    def counts(self) -> Dict[int, int]:
        if self._counts is None:
            self._counts = label_counts(self.volume)
        return self._counts

    def bboxes(self) -> Dict[int, Tuple[slice, slice, slice]]:
        if self._bboxes is None:
            self._bboxes = label_bboxes(self.volume)
        return self._bboxes

    def ids(self) -> List[int]:
        return sorted(self.counts())

    def next_id(self) -> int:
        return next_instance_id(self.counts().keys())

    def center_of(self, instance_id: int) -> Optional[np.ndarray]:
        """Bounding-box centre of an ID, ``[x, y, z]`` Angstrom."""
        box = self.bboxes().get(int(instance_id))
        if box is None:
            return None
        zyx = np.array([(s.start + s.stop - 1) / 2.0 for s in box])
        return zyx[::-1] * self.voxel_size

    def index_of(self, xyz: Sequence[float]) -> Tuple[int, int, int]:
        """``(z, y, x)`` voxel index of a point in Angstrom."""
        ijk = np.round(np.asarray(xyz, dtype=float) / self.voxel_size).astype(int)
        return int(ijk[2]), int(ijk[1]), int(ijk[0])

    def pick(self, xyz: Sequence[float]) -> int:
        """The ID at a point (0 outside the volume or on background)."""
        z, y, x = self.index_of(xyz)
        if not (0 <= z < self.volume.shape[0] and 0 <= y < self.volume.shape[1] and 0 <= x < self.volume.shape[2]):
            return 0
        return int(self.volume[z, y, x])

    # -- edits -----------------------------------------------------------------------------------------------------

    def _invalidate(self) -> None:
        self._counts = None
        self._bboxes = None
        self.dirty = True

    def _push_undo(self, region: Tuple[slice, slice, slice]) -> None:
        self._undo.append((region, self.volume[region].copy()))
        if len(self._undo) > MAX_UNDO:
            self._undo.pop(0)

    def _ensure_capacity(self, value: int) -> None:
        if value > np.iinfo(self.volume.dtype).max:
            self.volume = self.volume.astype(np.uint32)

    def paint(
        self,
        xyz: Sequence[float],
        radius: float,
        value: Optional[int] = None,
        background_only: bool = False,
    ) -> Set[int]:
        """Write ``value`` (default the current ID; 0 erases) into a sphere of ``radius`` Angstrom around ``xyz``.

        Returns:
            The IDs whose voxels changed (including ``value`` unless it is 0).
        """
        value = self.current_id if value is None else int(value)
        self._ensure_capacity(value)
        center = np.asarray(self.index_of(xyz), dtype=float)
        r = max(float(radius) / self.voxel_size, 0.5)
        lo = np.maximum(np.floor(center - r).astype(int), 0)
        hi = np.minimum(np.ceil(center + r).astype(int) + 1, self.volume.shape)
        if np.any(hi <= lo):
            return set()
        region = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi, strict=True))
        zz, yy, xx = np.ogrid[region[0], region[1], region[2]]
        mask = (zz - center[0]) ** 2 + (yy - center[1]) ** 2 + (xx - center[2]) ** 2 <= r * r
        block = self.volume[region]
        if background_only and value != 0:
            mask &= block == 0
        if not mask.any():
            return set()
        self._push_undo(region)
        touched = {int(i) for i in np.unique(block[mask]) if i != 0}
        block[mask] = value
        if value:
            touched.add(value)
        self._invalidate()
        return touched

    def relabel(self, ids: Iterable[int], value: int) -> Set[int]:
        """Set every voxel of ``ids`` to ``value`` (0 deletes). The whole volume is one undo step."""
        ids = [int(i) for i in ids if int(i) != int(value)]
        if not ids:
            return set()
        region = (slice(None), slice(None), slice(None))
        self._push_undo(region)
        if value:
            self._ensure_capacity(value)
            merge_labels(self.volume, ids, value)
        else:
            delete_labels(self.volume, ids)
        self._invalidate()
        return set(ids) | ({int(value)} if value else set())

    def undo(self) -> Set[int]:
        """Undo the last edit; returns the IDs present before or after in the restored region."""
        if not self._undo:
            return set()
        region, old = self._undo.pop()
        now = self.volume[region]
        touched = {int(i) for i in np.unique(now) if i != 0} | {int(i) for i in np.unique(old) if i != 0}
        self.volume[region] = old
        self._invalidate()
        return touched

    # -- saving ----------------------------------------------------------------------------------------------------

    def full_resolution(self, target_shape: Optional[Sequence[int]] = None) -> np.ndarray:
        """The volume at level 0 (nearest-neighbour upsampling when edited at a coarser level)."""
        if self.level == 0 and (target_shape is None or tuple(target_shape) == self.volume.shape):
            return self.volume
        from scipy.ndimage import zoom

        if target_shape is None:
            factor = self.voxel_size / self.base_voxel_size
            target_shape = tuple(int(round(s * factor)) for s in self.volume.shape)
        factors = [t / s for t, s in zip(target_shape, self.volume.shape, strict=True)]
        up = zoom(self.volume, factors, order=0)
        out = np.zeros(target_shape, dtype=self.volume.dtype)
        sl = tuple(slice(0, min(a, b)) for a, b in zip(up.shape, target_shape, strict=True))
        out[sl] = up[sl]
        return out

    def save(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        exist_ok: bool = True,
        target_shape: Optional[Sequence[int]] = None,
    ) -> Any:
        """Store as an instance segmentation (copick picks the dtype, uint16 or wider)."""
        user_id = user_id or self.user_id
        session_id = session_id or self.session_id
        seg = self.run.new_segmentation(
            self.base_voxel_size,
            self.object_name,
            session_id,
            user_id=user_id,
            is_instance=True,
            exist_ok=exist_ok,
        )
        seg.from_numpy(self.full_resolution(target_shape), levels=3)
        self.user_id, self.session_id, self.source = user_id, session_id, seg
        self.dirty = False
        return seg
