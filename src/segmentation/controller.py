"""Instance and panoptic segmentations in a running copick tool: surface display (computed off the UI thread) and
instance editing (``paint`` / ``erase`` / ``pick copick instance`` mouse modes, merge / delete / undo, save).

Binary and multilabel segmentations keep the existing volume-surface path in ``tool.show_volume_from_segmentation``.
"""

from typing import Any, Callable, Dict, Iterable, List, Optional, Set

import numpy as np
from copick_shared_ui.core.types import segmentation_type_of
from copick_shared_ui.util.instances import (
    InstanceRow,
    instance_colors,
    label_bboxes,
    label_counts,
    panoptic_segments,
    rows_from_counts,
)
from superqt.utils import thread_worker

from .instance_edit import InstanceEditSession
from .label_surfaces import LabelSurfaceModel, compute_label_surfaces, read_label_level

MAX_PANOPTIC_SEGMENTS = 500


def _instance_colors(ids: Iterable[int]) -> Dict[int, np.ndarray]:
    ids = list(ids)
    colors = instance_colors(ids, (180, 180, 180, 255), dtype=np.uint8)
    return {int(i): c for i, c in zip(ids, colors, strict=True)}


def _load_impl(seg: Any, level: int, objects: Dict[int, tuple]):
    """Read a level and compute the surfaces (worker thread)."""
    kind = segmentation_type_of(seg)
    data, voxel_size, level = read_label_level(seg, level)
    result = {"segmentation": seg, "kind": kind, "voxel_size": voxel_size, "level": level}
    if kind == "panoptic":
        segments, rows = panoptic_segments(data[0], data[1], objects)
        result["rows"] = rows
        if len(rows) > MAX_PANOPTIC_SEGMENTS:
            # Too many segments for one surface each: show the label channel (one surface per object) instead.
            labels = data[0]
            result["fallback"] = True
            result["geometry"] = compute_label_surfaces(labels, voxel_size)
            result["bboxes"] = label_bboxes(labels)
        else:
            result["geometry"] = compute_label_surfaces(segments, voxel_size)
            result["bboxes"] = label_bboxes(segments)
    else:
        result["volume"] = data
        result["counts"] = label_counts(data)
        result["bboxes"] = label_bboxes(data)
        result["geometry"] = compute_label_surfaces(data, voxel_size)
    return result


_load_worker = thread_worker(_load_impl)


def _surfaces_impl(volume: np.ndarray, voxel_size: float, ids: Optional[List[int]]):
    return compute_label_surfaces(volume, voxel_size, ids)


_surfaces_worker = thread_worker(_surfaces_impl)


def _save_impl(edit: InstanceEditSession, user_id: str, session_id: str, target_shape):
    return edit.save(user_id=user_id, session_id=session_id, target_shape=target_shape)


_save_worker = thread_worker(_save_impl)


class SegmentationController:
    """Owns the label-surface models of instance and panoptic segmentations, and the instance editing session."""

    def __init__(self, tool: Any):
        self.tool = tool
        self.session = tool.session
        self.models: Dict[Any, LabelSurfaceModel] = {}  # CopickSegmentation -> model
        self.info: Dict[Any, dict] = {}  # CopickSegmentation -> {"kind", "rows", "bboxes", "voxel_size", ...}
        self.edit: Optional[InstanceEditSession] = None
        self.edit_model: Optional[LabelSurfaceModel] = None
        self.edit_key: Any = None
        self.active_key: Any = None
        self.paint_radius = float(getattr(tool.settings, "paint_radius", 50.0))
        self.background_only = False
        self.listeners: List[Callable[[], None]] = []
        self._workers = []
        self._pending_touched: Set[int] = set()
        self._prev_right_mode: Optional[str] = None

    def notify(self) -> None:
        for listener in list(self.listeners):
            try:
                listener()
            except Exception as e:
                self.session.logger.warning(f"copick: segmentation listener failed: {e}")

    def _keep(self, worker) -> None:
        self._workers.append(worker)
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)

    def _objects(self, root: Any) -> Dict[int, tuple]:
        return {
            o.label: (o.name, tuple(np.asarray(o.color or (128, 128, 128, 255), dtype=float) / 255.0))
            for o in root.config.pickable_objects
        }

    # -- display -----------------------------------------------------------------------------------------------

    def show(
        self,
        seg: Any,
        level: Optional[int] = None,
        on_done: Optional[Callable[[Any], None]] = None,
        blocking: bool = False,
    ) -> None:
        """Load and show an instance or panoptic segmentation as surfaces."""
        level = self.tool.settings.zarr_level if level is None else level
        if seg in self.models and not self.models[seg].deleted:
            self.models[seg].display = True
            self.active_key = seg
            self.notify()
            if on_done:
                on_done(self.models[seg])
            return
        objects = self._objects(seg.run.root)

        def finished(result: dict) -> None:
            model = self._build_model(result)
            if on_done:
                on_done(model)

        if blocking:
            finished(_load_impl(seg, level, objects))
            return
        self.session.logger.status(f"copick: loading {segmentation_type_of(seg)} segmentation {seg.name}...")
        worker = _load_worker(seg, level, objects)
        worker.returned.connect(finished)
        worker.errored.connect(lambda e: self.session.logger.error(f"copick: loading {seg.name} failed: {e}"))
        self._keep(worker)
        worker.start()

    def _build_model(self, result: dict) -> LabelSurfaceModel:
        seg = result["segmentation"]
        kind = result["kind"]
        model = LabelSurfaceModel(f"{seg.name} {kind} ({seg.user_id}/{seg.session_id})", self.session)
        self.session.models.add([model])
        if kind == "panoptic":
            rows: List[InstanceRow] = result["rows"]
            if result.get("fallback"):
                objects = self._objects(seg.run.root)
                colors = {k: (np.asarray(v[1]) * 255).astype(np.uint8) for k, v in objects.items()}
                names = {k: v[0] for k, v in objects.items()}
                self.session.logger.warning(
                    f"copick: {len(rows)} panoptic segments; showing one surface per object instead.",
                )
            else:
                colors = {r.row_key: (np.asarray(r.color) * 255).astype(np.uint8) for r in rows}
                names = {r.row_key: f"{r.label} #{r.instance_id}" if r.instance_id else r.label for r in rows}
            model.set_surfaces(result["geometry"], colors, names)
        else:
            counts = result["counts"]
            rows = rows_from_counts(counts, label=seg.name)
            model.set_surfaces(result["geometry"], _instance_colors(counts), {i: f"{seg.name} #{i}" for i in counts})
        self.models[seg] = model
        self.info[seg] = {
            "kind": kind,
            "rows": rows,
            "bboxes": result["bboxes"],
            "voxel_size": result["voxel_size"],
            "level": result["level"],
            "fallback": result.get("fallback", False),
        }
        model.copick_segmentation = seg
        self.active_key = seg
        self.session.logger.status("")
        self.notify()
        return model

    def hide(self, seg: Any) -> None:
        model = self.models.get(seg)
        if model is not None and not model.deleted:
            model.display = False
        self.notify()

    def close_all(self) -> None:
        self.stop_editing()
        for model in self.models.values():
            if not model.deleted:
                model.delete()
        self.models.clear()
        self.info.clear()
        self.edit = None
        self.edit_model = None
        self.edit_key = None
        self.active_key = None
        self.notify()

    def forget(self, seg: Any) -> None:
        model = self.models.pop(seg, None)
        self.info.pop(seg, None)
        if model is not None and not model.deleted:
            model.delete()
        if self.edit_key is seg:
            self.edit = None
            self.edit_model = None
            self.edit_key = None
        self.notify()

    def rows(self, seg: Any) -> List[InstanceRow]:
        if self.edit is not None and self.edit_key is seg:
            return rows_from_counts(self.edit.counts(), label=self.edit.object_name)
        return list(self.info.get(seg, {}).get("rows", []))

    def focus(self, seg: Any, key: int) -> None:
        if self.edit is not None and self.edit_key is seg:
            xyz = self.edit.center_of(key)
        else:
            info = self.info.get(seg)
            box = info["bboxes"].get(int(key)) if info else None
            xyz = (
                None
                if box is None
                else np.array([(s.start + s.stop - 1) / 2.0 for s in box])[::-1] * info["voxel_size"]
            )
        if xyz is not None:
            self.tool.focus_xyz(xyz, radius=4 * (self.edit.voxel_size if self.edit else 20.0))

    def set_visible(self, seg: Any, keys: Iterable[int]) -> None:
        model = self.models.get(seg)
        if model is not None and not model.deleted:
            model.set_visible_keys(keys)

    # -- editing ---------------------------------------------------------------------------------------------------

    def start_editing(
        self,
        seg: Any = None,
        object_name: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        blocking: bool = False,
        on_ready: Optional[Callable[[], None]] = None,
    ) -> None:
        """Edit an instance segmentation (loaded at level 0), or a new empty one for ``object_name`` at the active
        tomogram's voxel spacing."""
        if seg is not None:

            def ready(result: dict) -> None:
                existing = self.models.get(seg)
                if existing is not None and not existing.deleted and self.info.get(seg, {}).get("level", 0) != 0:
                    existing.delete()
                    self.models.pop(seg, None)
                model = self.models.get(seg)
                if model is None or model.deleted:
                    model = self._build_model(result)
                self.edit = InstanceEditSession(
                    seg.run,
                    seg.name,
                    seg.user_id,
                    seg.session_id,
                    result["volume"],
                    result["voxel_size"],
                    seg.voxel_size,
                    level=result["level"],
                    source=seg,
                )
                self.edit._counts = result["counts"]
                self.edit._bboxes = result["bboxes"]
                self.edit_model, self.edit_key = model, seg
                self._enter_mode()
                if on_ready:
                    on_ready()

            if blocking:
                ready(_load_impl(seg, 0, {}))
            else:
                worker = _load_worker(seg, 0, {})
                worker.returned.connect(ready)
                worker.errored.connect(lambda e: self.session.logger.error(f"copick: loading {seg.name} failed: {e}"))
                self._keep(worker)
                worker.start()
            return
        vol = self.tool.active_volume
        if vol is None or vol.deleted:
            raise ValueError("Open a tomogram first.")
        import zarr

        tomo = vol.copick_tomo
        shape = zarr.open(tomo.zarr(), mode="r")["0"].shape
        vs = float(tomo.voxel_spacing.voxel_size)
        run = tomo.voxel_spacing.run
        root = run.root
        user_id = user_id or root.user_id or "ArtiaX"
        self.edit = InstanceEditSession(
            run,
            object_name,
            user_id,
            session_id or "manual",
            np.zeros(shape, dtype=np.uint16),
            vs,
            vs,
            level=0,
        )
        model = LabelSurfaceModel(f"{object_name} instance ({user_id}/{self.edit.session_id}) (new)", self.session)
        self.session.models.add([model])
        self.edit_model, self.edit_key = model, self.edit
        self.models[self.edit] = model
        self.info[self.edit] = {"kind": "instance", "rows": [], "bboxes": {}, "voxel_size": vs, "level": 0}
        self._enter_mode()
        if on_ready:
            on_ready()

    def _enter_mode(self) -> None:
        from chimerax.core.commands import run

        bindings = self.session.ui.mouse_modes.bindings
        right = [b.mode.name for b in bindings if b.button == "right" and not b.modifiers]
        if right and "copick instance" not in right[0]:
            self._prev_right_mode = right[0]
        self.active_key = self.edit_key
        run(self.session, "ui mousemode right 'paint copick instance'", log=False)
        self.tool.annotate("instances")
        self.session.logger.info(
            f"copick: editing instances of {self.edit.object_name} (current ID {self.edit.current_id}, "
            f"brush {self.paint_radius:g} Å)",
        )
        self.notify()

    def stop_editing(self) -> None:
        from chimerax.core.commands import run

        if self.edit is None:
            return
        if self._prev_right_mode:
            run(self.session, f"ui mousemode right '{self._prev_right_mode}'", log=False)
            self._prev_right_mode = None
        self.notify()

    @property
    def editing(self) -> bool:
        return self.edit is not None

    def paint(self, xyz, value: Optional[int] = None) -> Set[int]:
        if self.edit is None:
            return set()
        touched = self.edit.paint(xyz, self.paint_radius, value=value, background_only=self.background_only)
        self._pending_touched |= touched
        return touched

    def pick(self, xyz) -> int:
        if self.edit is None:
            return 0
        value = self.edit.pick(xyz)
        if value:
            self.edit.current_id = value
            self.session.logger.status(f"copick: current instance ID {value}")
            self.notify()
        return value

    def new_id(self) -> int:
        if self.edit is None:
            return 0
        self.edit.current_id = self.edit.next_id()
        self.notify()
        return self.edit.current_id

    def set_current_id(self, value: int) -> None:
        if self.edit is not None:
            self.edit.current_id = int(value)
            self.notify()

    def relabel(self, ids: Iterable[int], value: int) -> None:
        if self.edit is None:
            return
        self._pending_touched |= self.edit.relabel(ids, value)
        self.flush()

    def undo(self) -> None:
        if self.edit is None:
            return
        self._pending_touched |= self.edit.undo()
        self.flush()

    def flush(self, blocking: bool = False) -> None:
        """Rebuild the surfaces of the IDs touched since the last flush."""
        if self.edit is None or not self._pending_touched:
            return
        touched = sorted(self._pending_touched)
        self._pending_touched = set()
        volume, voxel_size = self.edit.volume, self.edit.voxel_size
        ids = touched if len(touched) <= 8 else None

        def apply(geometry: dict) -> None:
            model = self.edit_model
            if model is None or model.deleted:
                return
            present = set(self.edit.counts())
            gone = [i for i in touched if i not in present]
            model.remove_keys(gone)
            name = self.edit.object_name
            model.set_surfaces(
                geometry,
                _instance_colors(geometry),
                {i: f"{name} #{i}" for i in geometry},
                replace=ids is None,
            )
            self.info.setdefault(self.edit_key, {})["bboxes"] = self.edit.bboxes()
            self.notify()

        if blocking:
            apply(_surfaces_impl(volume.copy(), voxel_size, ids))
            return
        worker = _surfaces_worker(volume.copy(), voxel_size, ids)
        worker.returned.connect(apply)
        worker.errored.connect(lambda e: self.session.logger.error(f"copick: surface update failed: {e}"))
        self._keep(worker)
        worker.start()

    def save(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        on_done: Optional[Callable[[Any], None]] = None,
        blocking: bool = False,
    ):
        if self.edit is None:
            self.session.logger.warning("copick: no instance segmentation is being edited.")
            return None
        edit = self.edit
        user_id = user_id or edit.user_id
        session_id = session_id or edit.session_id
        if str(session_id) == "0":
            self.session.logger.error("copick: session 0 is reserved for tool output; save under another session.")
            return None
        target_shape = None
        vol = self.tool.active_volume
        if edit.level != 0 and vol is not None and not vol.deleted:
            import zarr

            target_shape = zarr.open(vol.copick_tomo.zarr(), mode="r")["0"].shape
        old_key = self.edit_key

        def finished(seg: Any) -> None:
            model = self.models.pop(old_key, None)
            info = self.info.pop(old_key, None)
            if model is not None:
                self.models[seg] = model
                model.name = f"{seg.name} instance ({seg.user_id}/{seg.session_id})"
                model.copick_segmentation = seg
            if info is not None:
                self.info[seg] = info
            self.edit_key = seg
            self.active_key = seg
            self.session.logger.info(
                f"copick: saved instance segmentation {seg.name}:{seg.user_id}/{seg.session_id}@{seg.voxel_size} "
                f"({len(edit.counts())} instances)",
            )
            self.tool._mw.update_segmentations_table()
            self.notify()
            if on_done:
                on_done(seg)

        if blocking:
            seg = _save_impl(edit, user_id, session_id, target_shape)
            finished(seg)
            return seg
        worker = _save_worker(edit, user_id, session_id, target_shape)
        worker.returned.connect(finished)
        worker.errored.connect(lambda e: self.session.logger.error(f"copick: saving instances failed: {e}"))
        self._keep(worker)
        worker.start()
        return worker
