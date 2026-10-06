"""Filament sets in a running copick tool: display, tracing (via the ``trace copick filament`` mouse mode), editing
and saving. Commands, toolbar buttons, shortcuts and the Filaments tab all go through this controller.

Undo: every edit step of a set's ``FilamentEditSession`` is mirrored as an action on ChimeraX's undo stack, so
Edit > Undo / Redo, Cmd+Z / Ctrl+Z and the ``undo`` / ``redo`` commands step through filament edits in order with
everything else ChimeraX can undo.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from copick_shared_ui.util.filament_session import FilamentEditSession
from copick_shared_ui.util.filaments import nearest_point_to_line, point_at_arc_length
from superqt.utils import thread_worker

from .model import FilamentSetModel


def _save_impl(session: FilamentEditSession, user_id: str, session_id: str, pick_spacing: Optional[float]):
    return session.save(user_id=user_id, session_id=session_id, pick_spacing=pick_spacing)


_save_worker = thread_worker(_save_impl)

#: ChimeraX keeps 10 undo steps by default; tracing raises that to this many.
UNDO_DEPTH = 100

#: The filament mouse modes (bound to the right button).
TRACE_MODE = "trace copick filament"
CUT_MODE = "cut copick filament"
FILAMENT_MODES = (TRACE_MODE, CUT_MODE)

_undo_action_class = None


def _filament_undo_action(controller: "FilamentController", edit: FilamentEditSession, label: str):
    """An UndoAction that undoes / redoes one step of ``edit`` (class built lazily: chimerax.core is only importable
    inside ChimeraX)."""
    global _undo_action_class
    if _undo_action_class is None:
        from chimerax.core.undo import UndoAction

        class FilamentUndoAction(UndoAction):
            def __init__(self, controller, edit, label):
                super().__init__(label, can_redo=True)
                self.controller, self.edit = controller, edit

            def undo(self):
                self.controller.apply_history(self.edit, redo=False)

            def redo(self):
                self.controller.apply_history(self.edit, redo=True)

        _undo_action_class = FilamentUndoAction
    return _undo_action_class(controller, edit, label)


class FilamentController:
    """Owns the filament sessions and models of the current run."""

    def __init__(self, tool: Any):
        self.tool = tool
        self.session = tool.session
        # key: the CopickFilaments it was opened from, or the session itself for new, unsaved traces
        self.entries: Dict[Any, Tuple[FilamentEditSession, FilamentSetModel]] = {}
        self.active_key: Any = None
        self.editing = False
        self._prev_right_mode: Optional[str] = None
        self.listeners: List[Callable[[], None]] = []
        #: Called with the filament IDs selected in the 3D view when that selection changes.
        self.selection_listeners: List[Callable[[List[int]], None]] = []
        self._scene_selection: List[int] = []
        self._workers = []
        self._undo_actions: Dict[int, list] = {}  # id(edit session) -> its actions on ChimeraX's undo stack
        self._drag_edit: Optional[FilamentEditSession] = None

    # -- state -----------------------------------------------------------------------------------------------------

    def notify(self) -> None:
        for listener in list(self.listeners):
            try:
                listener()
            except Exception as e:  # never let a UI listener break an edit
                self.session.logger.warning(f"copick: filament listener failed: {e}")

    @property
    def active(self) -> Optional[Tuple[FilamentEditSession, FilamentSetModel]]:
        entry = self.entries.get(self.active_key)
        if entry is not None and entry[1].deleted:
            self.entries.pop(self.active_key, None)
            return None
        return entry

    @property
    def edit_session(self) -> Optional[FilamentEditSession]:
        return self.active[0] if self.active else None

    def tube_scale(self) -> float:
        return float(getattr(self.tool.settings, "filament_tube_scale", 0.5))

    # -- open / close ----------------------------------------------------------------------------------------------

    def show(self, copick_filaments: Any) -> FilamentSetModel:
        """Load (if needed) and show a filament set; makes it the active set."""
        entry = self.entries.get(copick_filaments)
        if entry is None or entry[1].deleted:
            step = copick_filaments.voxel_spacing or self._tomogram_voxel_size() or 10.0
            edit = FilamentEditSession.from_filaments(copick_filaments, step=step)
            self._track_history(edit)
            model = FilamentSetModel(self.session, edit, tube_scale=self.tube_scale())
            self.session.models.add([model])
            model.redraw()
            self.entries[copick_filaments] = (edit, model)
        else:
            entry[1].display = True
        self.active_key = copick_filaments
        self.notify()
        return self.entries[copick_filaments][1]

    def hide(self, copick_filaments: Any) -> None:
        entry = self.entries.get(copick_filaments)
        if entry is not None and not entry[1].deleted:
            entry[1].display = False
        self.notify()

    def is_shown(self, copick_filaments: Any) -> bool:
        entry = self.entries.get(copick_filaments)
        return entry is not None and not entry[1].deleted and entry[1].display

    def new(self, object_name: str, user_id: str, session_id: str) -> FilamentEditSession:
        """Start a new (unsaved) filament set in the active run and switch to tracing."""
        run = self.tool.active_run()
        if run is None:
            raise ValueError("Open a tomogram first.")
        step = self._tomogram_voxel_size() or 10.0
        edit = FilamentEditSession(run, object_name, user_id, session_id, step=step)
        self._track_history(edit)
        model = FilamentSetModel(self.session, edit, tube_scale=self.tube_scale())
        self.session.models.add([model])
        self.entries[edit] = (edit, model)
        self.active_key = edit
        self.start_tracing()
        return edit

    def close_all(self) -> None:
        for edit, model in self.entries.values():
            self._forget_history(edit)
            if not model.deleted:
                model.delete()
        self.entries.clear()
        self.active_key = None
        self.stop_tracing()
        self.notify()

    def delete_entity(self, copick_filaments: Any) -> None:
        entry = self.entries.pop(copick_filaments, None)
        if entry is not None:
            self._forget_history(entry[0])
        if entry is not None and not entry[1].deleted:
            entry[1].delete()
        if self.active_key is copick_filaments:
            self.active_key = None
        self.notify()

    def set_active(self, key: Any) -> None:
        if key in self.entries:
            self.active_key = key
            if self.editing:
                for _e, m in self.entries.values():
                    m.set_show_controls(m is self.entries[key][1])
            self.notify()

    def _tomogram_voxel_size(self) -> Optional[float]:
        vol = self.tool.active_volume
        if vol is None or vol.deleted or not hasattr(vol, "copick_tomo"):
            return None
        return float(vol.copick_tomo.voxel_spacing.voxel_size)

    # -- tracing mode ----------------------------------------------------------------------------------------------

    @property
    def right_mode(self) -> Optional[str]:
        """Name of the mouse mode on the right button (no modifiers)."""
        bindings = self.session.ui.mouse_modes.bindings
        names = [b.mode.name for b in bindings if b.button == "right" and not b.modifiers]
        return names[0] if names else None

    def start_tracing(self) -> None:
        """Right mouse button: trace (add / move / remove control points)."""
        self._start_mode(TRACE_MODE)

    def start_cutting(self) -> None:
        """Right mouse button: cut the filament under the click in two."""
        self._start_mode(CUT_MODE)

    def _start_mode(self, mode_name: str) -> None:
        from chimerax.core.commands import run

        if self.active is None:
            self.session.logger.warning("copick: no filament set is active; open or create one first.")
            return
        right = self.right_mode
        if right and right not in FILAMENT_MODES:
            self._prev_right_mode = right
        self._enter_editing()
        run(self.session, f"ui mousemode right '{mode_name}'", log=False)
        self.notify()

    def _enter_editing(self) -> None:
        if not self.editing:
            self.editing = True
            self.tool.annotate("filaments")
        active = self.active
        for _e, model in self.entries.values():
            if not model.deleted:
                model.set_show_controls(active is not None and model is active[1])

    def on_mouse_mode_set(self, button: str, modifiers, mode) -> None:
        """Another mode took the right button: leave filament editing (hide the handles, update the panel)."""
        if button != "right" or modifiers or not self.editing:
            return
        if mode is not None and getattr(mode, "name", None) in FILAMENT_MODES:
            return
        self.editing = False
        self._prev_right_mode = None
        for _e, model in self.entries.values():
            if not model.deleted:
                model.set_show_controls(False)
        self.notify()

    def mode_enabled(self, mode_name: str) -> None:
        """A filament mouse mode was bound (from the toolbar, a command or ``ui mousemode``): show the handles."""
        if self.active is not None:
            self._enter_editing()
        self.notify()

    def stop_tracing(self) -> None:
        from chimerax.core.commands import run

        if not self.editing:
            return
        self.editing = False
        for _e, model in self.entries.values():
            if not model.deleted:
                model.set_show_controls(False)
        if self._prev_right_mode:
            run(self.session, f"ui mousemode right '{self._prev_right_mode}'", log=False)
        self.notify()

    # -- edits (each regenerates through copick core and redraws) ----------------------------------------------

    def _redraw(self, ids=None) -> None:
        edit, model = self.active
        model.redraw(ids)
        self.notify()

    def add_point(self, xyz) -> Optional[int]:
        if self.active is None:
            return None
        edit, _model = self.active
        try:
            index = edit.insert_point(np.asarray(xyz, dtype=float))
        except ValueError as e:
            self.session.logger.warning(str(e))
            return None
        self._redraw([edit.active_id])
        return index

    def move_point(self, instance_id: int, index: int, xyz) -> None:
        edit, _model = self.active
        edit.move_point(instance_id, index, np.asarray(xyz, dtype=float))
        self._redraw([instance_id])

    def remove_point(self, instance_id: int, index: int) -> None:
        edit, _model = self.active
        try:
            edit.remove_point(instance_id, index)
        except ValueError as e:
            self.session.logger.warning(str(e))
            return
        self._redraw([instance_id])

    def hit_control(self, xyz1, xyz2, tolerance: float) -> Optional[Tuple[int, int]]:
        """The control point (``(instance_id, index)``) closest to the viewer along a pick ray, if any."""
        if self.active is None:
            return None
        points = self.active[1].all_control_points()
        if not points:
            return None
        hit = nearest_point_to_line(np.array([p for _i, _k, p in points]), xyz1, xyz2, tolerance)
        if hit is None:
            return None
        instance_id, index, _p = points[hit]
        return instance_id, index

    def new_filament(self) -> Optional[int]:
        if self.active is None:
            return None
        instance_id = self.active[0].new_filament()
        self._redraw([])
        return instance_id

    def set_active_filament(self, instance_id: int) -> None:
        if self.active is None:
            return
        self.active[0].active_id = int(instance_id)
        self._redraw([])

    def go_to_filament(self, instance_id: int) -> None:
        """Make a filament active and focus the view on it (the dock stepper's jump)."""
        if self.active is None or int(instance_id) not in self.active[0].ids():
            return
        self.set_active_filament(instance_id)
        self.focus(int(instance_id))

    def step_filament(self, delta: int) -> Optional[int]:
        if self.active is None:
            return None
        edit = self.active[0]
        ids = edit.ids()
        if not ids:
            return None
        i = ids.index(edit.active_id) if edit.active_id in ids else -1
        edit.active_id = ids[(i + delta) % len(ids)]
        self._redraw([])
        self.focus(edit.active_id)
        return edit.active_id

    def reverse(self, instance_id: Optional[int] = None) -> None:
        if self.active is None:
            return
        edit = self.active[0]
        instance_id = edit.active_id if instance_id is None else int(instance_id)
        edit.reverse(instance_id)
        self._redraw([instance_id])

    def delete_filament(self, instance_id: Optional[int] = None) -> None:
        if self.active is None:
            return
        edit = self.active[0]
        instance_id = edit.active_id if instance_id is None else int(instance_id)
        edit.delete_filament(instance_id)
        self._redraw([instance_id])

    def convert(self, instance_id: Optional[int] = None) -> None:
        if self.active is None:
            return
        edit = self.active[0]
        instance_id = edit.active_id if instance_id is None else int(instance_id)
        edit.convert_to_catmull_rom(instance_id)
        self._redraw([instance_id])

    def focus(self, instance_id: int) -> None:
        if self.active is None:
            return
        edit = self.active[0]
        if instance_id in edit.filaments:
            xyz = point_at_arc_length(np.asarray(edit.filaments[instance_id].points), 0.5)
        else:
            cps = edit.controls(instance_id)
            if not len(cps):
                return
            xyz = cps.mean(axis=0)
        self.tool.focus_xyz(xyz, radius=self.active[1].radius)
        spotlight = getattr(self.tool, "spotlight", None)
        if spotlight is not None and spotlight.enabled:
            spotlight.on_active_particle(xyz)

    # -- undo / redo -----------------------------------------------------------------------------------------------

    def _track_history(self, edit: FilamentEditSession) -> None:
        edit.on_history = lambda label, edit=edit: self._register_undo(edit, label)

    def _register_undo(self, edit: FilamentEditSession, label: str) -> None:
        undo = getattr(self.session, "undo", None)
        if undo is None:
            return
        if 0 < undo.max_depth < UNDO_DEPTH:
            undo.set_depth(UNDO_DEPTH)
        actions = self._undo_actions.setdefault(id(edit), [])
        actions.append(undo.register(_filament_undo_action(self, edit, label)))
        del actions[: -UNDO_DEPTH * 2]

    def _forget_history(self, edit: FilamentEditSession) -> None:
        """Drop a closed set's steps from ChimeraX's undo stack (other steps stay undoable)."""
        undo = getattr(self.session, "undo", None)
        for action in self._undo_actions.pop(id(edit), []):
            if undo is not None:
                undo.deregister(action, delete_history=False)
        edit.on_history = None

    def apply_history(self, edit: FilamentEditSession, redo: bool) -> None:
        """Undo or redo one step of a filament set (called by ChimeraX's undo stack); shows the set it changed."""
        key = next((k for k, (e, _m) in self.entries.items() if e is edit), None)
        if key is None or self.entries[key][1].deleted:
            self.session.logger.status("copick: that filament set is closed")
            return
        label = edit.redo() if redo else edit.undo()
        if label is None:
            return
        model = self.entries[key][1]
        model.display = True
        if key is not self.active_key:
            self.set_active(key)
        model.redraw()
        self.notify()
        self.session.logger.status(f"copick: {'redo' if redo else 'undo'} {label.lower()}")

    def cut_at(self, xyz, instance_id: Optional[int] = None, tolerance: Optional[float] = None) -> Optional[Tuple[int, int]]:
        """Cut the filament under ``xyz`` (or ``instance_id``) in two; one undo step. Returns the two piece IDs."""
        if self.active is None:
            return None
        edit, model = self.active
        if tolerance is None:
            tolerance = max(4 * edit.step, 1.5 * (model.radius or 0.0))
        try:
            pieces = edit.cut(np.asarray(xyz, dtype=float), instance_id=instance_id, tolerance=tolerance)
        except ValueError as e:
            self.session.logger.status(f"copick: {e}", color="orange red")
            return None
        self._redraw(list(pieces))
        self.session.logger.info(f"copick: cut filament {pieces[0]} into {pieces[0]} and {pieces[1]}")
        return pieces

    # -- selection in the 3D view (Ctrl-click a tube), mirrored in the filament list ------------------------------

    def scene_selected_ids(self) -> List[int]:
        """IDs of the active set's filaments whose tubes are selected in the 3D view."""
        if self.active is None:
            return []
        tubes = self.active[1]._tubes
        return sorted(i for i, surf in tubes.items() if not surf.deleted and surf.selected)

    def select_in_scene(self, instance_ids) -> None:
        """Select exactly these filaments' tubes in the 3D view (from the filament list)."""
        if self.active is None:
            return
        keep = {int(i) for i in instance_ids}
        for i, surf in self.active[1]._tubes.items():
            if not surf.deleted and surf.selected != (i in keep):
                surf.selected = i in keep
        self._scene_selection = sorted(i for i in keep if i in self.active[1]._tubes)

    def on_scene_selection_changed(self) -> None:
        """ChimeraX's selection changed: tell the filament list if the selected filaments changed."""
        ids = self.scene_selected_ids()
        if ids == self._scene_selection:
            return
        self._scene_selection = ids
        for listener in list(self.selection_listeners):
            try:
                listener(ids)
            except Exception as e:
                self.session.logger.warning(f"copick: filament selection listener failed: {e}")

    def join(self, instance_ids, target: Optional[int] = None) -> Optional[int]:
        """Join filaments end to end (nearest ends first) into ``target`` (default the first); one undo step."""
        if self.active is None:
            return None
        edit = self.active[0]
        try:
            joined = edit.join([int(i) for i in instance_ids], target=target)
        except ValueError as e:
            self.session.logger.warning(f"copick: {e}")
            return None
        self._redraw()
        others = [int(i) for i in instance_ids if int(i) != joined]
        self.session.logger.info(f"copick: joined filaments {', '.join(map(str, others))} into {joined}")
        return joined

    def begin_drag(self) -> None:
        """Group the moves of a control-point drag into one undo step (ended by ``end_drag``)."""
        self.end_drag()
        if self.active is not None:
            self._drag_edit = self.active[0]
            self._drag_edit.begin_step("Move filament point")

    def end_drag(self) -> None:
        edit, self._drag_edit = self._drag_edit, None
        if edit is not None:
            edit.end_step()

    # -- saving ----------------------------------------------------------------------------------------------------

    def save(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        pick_spacing: Optional[float] = None,
        on_done: Optional[Callable[[dict], None]] = None,
        blocking: bool = False,
    ):
        """Save the active set (in a thread unless ``blocking``). Sampled picks replace the whole picks set."""
        if self.active is None:
            self.session.logger.warning("copick: no active filament set to save.")
            return None
        edit, model = self.active
        user_id = user_id or edit.user_id
        session_id = session_id or edit.session_id
        if str(session_id) == "0":
            self.session.logger.error("copick: session 0 is reserved for tool output; save under another session.")
            return None
        if pick_spacing:
            # An open particle list of that picks set would overwrite the sampled picks on the next store().
            self.tool.store()
        key = self.active_key

        def finished(result: dict) -> None:
            target = result["filaments"]
            entry = self.entries.pop(key, None)
            if entry is not None:
                self.entries[target] = entry
                model.name = f"{edit.object_name} filaments ({edit.user_id}/{edit.session_id})"
            self.active_key = target
            picks_note = f" and {result['n_picks']} sampled picks" if result["n_picks"] else ""
            self.session.logger.info(
                f"copick: saved {result['n_filaments']} filaments "
                f"({edit.object_name}:{edit.user_id}/{edit.session_id}){picks_note}",
            )
            if result.get("picks") is not None:
                self.tool.reload_picks_entity(result["picks"])
            self.tool._mw.update_filaments_table()
            self.notify()
            if on_done is not None:
                on_done(result)

        if blocking:
            result = _save_impl(edit, user_id, session_id, pick_spacing)
            finished(result)
            return result
        worker = _save_worker(edit, user_id, session_id, pick_spacing)
        worker.returned.connect(finished)
        worker.errored.connect(lambda e: self.session.logger.error(f"copick: saving filaments failed: {e}"))
        worker.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self._workers.append(worker)
        worker.start()
        return worker

    def save_dirty(self) -> None:
        """Store edited sets that were opened from a user (editable) filament file (used by ``tool.store()``)."""
        for key, (edit, _model) in list(self.entries.items()):
            if edit.dirty and not edit.read_only and edit.source is not None and key is edit.source:
                try:
                    edit.save()
                except Exception as e:
                    self.session.logger.error(f"copick: could not store filaments {edit.object_name}: {e}")
