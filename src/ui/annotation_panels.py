"""Panels of the Copick Annotate window: the shared instance browser plus the few controls the Copick Edit toolbar does
not already have. Rows wrap (FlowLayout), so the window never forces a wide dock. Every control runs a ``copick ...``
command, so actions are logged and scriptable."""

from typing import Any

import numpy as np
from chimerax.core.commands import run
from copick_shared_ui.util.filament_session import INSERT_MODE_LABELS, INSERT_MODES
from copick_shared_ui.util.instances import rows_from_points
from copick_shared_ui.widgets.flow_layout import FlowLayout
from copick_shared_ui.widgets.instances import InstanceBrowserWidget
from Qt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .emoji_font import apply_emoji_font


def _labelled(label: str, widget: QWidget) -> QWidget:
    """``label`` and ``widget`` kept together on one line of a flow row."""
    box = QWidget()
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(3)
    lay.addWidget(QLabel(label))
    lay.addWidget(widget)
    return box


def _flow_row(*widgets: QWidget) -> QWidget:
    row = QWidget()
    lay = FlowLayout(row, h_spacing=6, v_spacing=3)
    for w in widgets:
        lay.addWidget(w)
    return row


def _button(text: str, tip: str, slot, checkable: bool = False) -> QPushButton:
    """A push button like the copick dock's (native, with the emoji font fallback)."""
    b = QPushButton(text)
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.clicked.connect(slot)
    apply_emoji_font(b)
    return b


def _browser(title: str) -> InstanceBrowserWidget:
    """An instance browser whose action buttons look like the rest of copick's."""
    return InstanceBrowserWidget(title=title, button_factory=lambda text, tip, slot: _button(text, tip, slot))


class SaveAnnotationDialog(QDialog):
    """User / session (and optionally pick sampling) for saving a filament set or instance segmentation."""

    def __init__(self, parent, title: str, user_id: str, session_id: str, picks: bool = False, spacing: float = 100.0):
        super().__init__(parent)
        self.setWindowTitle(title)
        form = QFormLayout(self)
        self.user_edit = QLineEdit(user_id)
        self.session_edit = QLineEdit(session_id if str(session_id) != "0" else "manual-1")
        form.addRow("User ID:", self.user_edit)
        form.addRow("Session ID:", self.session_edit)
        self.picks_cb = None
        if picks:
            self.picks_cb = QCheckBox("Also write picks sampled along the filaments")
            self.spacing = QDoubleSpinBox()
            self.spacing.setRange(1.0, 100000.0)
            self.spacing.setSuffix(" Å")
            self.spacing.setValue(spacing)
            self.spacing.setEnabled(False)
            note = QLabel("Sampled picks replace the whole picks set of this object / user / session.")
            note.setWordWrap(True)
            note.setStyleSheet("color: #d08000;")
            note.setVisible(False)
            self.picks_cb.toggled.connect(self.spacing.setEnabled)
            self.picks_cb.toggled.connect(note.setVisible)
            form.addRow(self.picks_cb)
            form.addRow("Pick spacing:", self.spacing)
            form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        spacing = self.spacing.value() if self.picks_cb is not None and self.picks_cb.isChecked() else None
        return self.user_edit.text().strip(), self.session_edit.text().strip(), spacing


class FilamentPanel(QWidget):
    """Tracing controls and the filament browser of the active filament set."""

    def __init__(self, tool: Any, parent=None):
        super().__init__(parent)
        self.tool = tool
        self.ctl = tool.filaments
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.info = QLabel("No filament set active. Double-click a row to show it, or ＋ to trace new filaments.")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.trace_btn = _button(
            "✏️ Trace",
            "Trace mode: right-click the tomogram plane to add control points, "
            "drag them to move, shift-click to remove",
            self._toggle_trace,
            checkable=True,
        )
        self.cut_btn = _button(
            "✂️ Cut",
            "Cut mode: right-click a filament on the tomogram plane to split it in two there (Cmd/Ctrl+Z undoes)",
            self._toggle_cut,
            checkable=True,
        )
        self.active_spin = QSpinBox()
        self.active_spin.setRange(1, 10_000_000)
        self.active_spin.valueChanged.connect(lambda v: self._cmd(f"copick filament select {v}"))
        self.mode_combo = QComboBox()
        for mode in INSERT_MODES:
            self.mode_combo.addItem(INSERT_MODE_LABELS[mode], mode)
        self.mode_combo.setToolTip(
            "Where a new control point goes: after the last, before the first, or into the nearest segment",
        )
        self.mode_combo.currentIndexChanged.connect(lambda _i: self._set_mode(self.mode_combo.currentData()))
        self.convert_btn = _button(
            "→ Catmull-Rom",
            "This filament is a B-spline fit: its control points can be moved but not added or removed. "
            "Convert it to an editable Catmull-Rom curve.",
            lambda: self._cmd("copick filament convert"),
        )
        self.save_btn = _button("💾", "Save the filament set…", self._save)
        self.transparency_spin = QSpinBox()
        self.transparency_spin.setRange(0, 100)
        self.transparency_spin.setSuffix(" %")
        self.transparency_spin.setKeyboardTracking(False)  # one command per committed value
        self.transparency_spin.setToolTip(
            "Transparency of the filament tubes, whether coloured by instance or by object (all filament sets)",
        )
        self.transparency_spin.valueChanged.connect(lambda v: self._cmd(f"copick filament style transparency {v}"))
        layout.addWidget(
            _flow_row(
                self.trace_btn,
                self.cut_btn,
                _labelled("Filament", self.active_spin),
                _labelled("New points", self.mode_combo),
                _labelled("Transparency", self.transparency_spin),
                self.convert_btn,
                self.save_btn,
            ),
        )

        self.browser = _browser("Filaments")
        self.browser.set_capabilities(
            new=True,
            delete=True,
            reverse=True,
            merge=True,
            merge_tip="Join the selected filaments end to end (into the current one)",
            color_toggle=True,
        )
        self.browser.color_by_instance_toggled.connect(
            lambda on: self._cmd(f"copick filament style color {'instance' if on else 'object'}"),
        )
        self.browser.current_changed.connect(lambda k: self._cmd(f"copick filament select {k}"))
        self.browser.focus_requested.connect(lambda k: self._cmd(f"copick filament focus {k}"))
        self.browser.visibility_changed.connect(self._on_visibility)
        self.browser.new_requested.connect(lambda: self._cmd("copick filament new"))
        self.browser.delete_requested.connect(lambda ks: [self._cmd(f"copick filament delete {k}") for k in ks])
        self.browser.reverse_requested.connect(lambda k: self._cmd(f"copick filament reverse {k}"))
        self.browser.merge_requested.connect(
            lambda sources, target: self._cmd(
                f"copick filament join {','.join(str(k) for k in [target, *sources])} target {target}",
            ),
        )
        layout.addWidget(self.browser, 1)

        # The list and the 3D view share one filament selection (Ctrl-click tubes, or select rows).
        self.browser.selection_changed.connect(self.ctl.select_in_scene)
        self.ctl.selection_listeners.append(self._on_scene_selection)

        self.ctl.listeners.append(self.refresh)
        self.refresh()

    def _cmd(self, command: str) -> None:
        run(self.tool.session, command)

    def _on_scene_selection(self, ids) -> None:
        """Filaments selected in the 3D view: select their rows; a single one becomes the active filament."""
        self.browser.set_selected_keys(ids)
        edit = self.ctl.edit_session
        if len(ids) == 1 and edit is not None and edit.active_id != ids[0]:
            self._cmd(f"copick filament select {ids[0]}")

    def _toggle_trace(self, on: bool) -> None:
        self._cmd(f"copick filament trace {'on' if on else 'off'}")

    def _toggle_cut(self, on: bool) -> None:
        self._cmd(f"copick filament cut {'on' if on else 'off'}")

    def _set_mode(self, mode: str) -> None:
        edit = self.ctl.edit_session
        if edit is not None:
            edit.insert_mode = mode

    def _on_visibility(self, keys) -> None:
        if self.ctl.active is not None:
            self.ctl.active[1].set_visible_ids(keys)

    def _save(self) -> None:
        edit = self.ctl.edit_session
        if edit is None:
            return
        obj = edit.object
        spacing = float(getattr(obj, "radius", None) or 100.0)
        root = edit.run.root
        user = edit.user_id if not edit.read_only else (root.user_id or "ArtiaX")
        dlg = SaveAnnotationDialog(self, "Save filaments", user, edit.session_id, picks=True, spacing=spacing)
        if dlg.exec_() != QDialog.Accepted:
            return
        user, session, spacing = dlg.values()
        cmd = f"copick filament save userId {user} sessionId {session}"
        if spacing:
            cmd += f" pickSpacing {spacing:g}"
        self._cmd(cmd)

    def refresh(self) -> None:
        edit = self.ctl.edit_session
        from ..filaments.controller import CUT_MODE, TRACE_MODE

        self.browser.set_color_by_instance(self.ctl.color_by_instance())
        self.transparency_spin.blockSignals(True)
        self.transparency_spin.setValue(round(self.ctl.transparency()))
        self.transparency_spin.blockSignals(False)
        right = self.ctl.right_mode if self.ctl.editing else None
        for btn, mode in ((self.trace_btn, TRACE_MODE), (self.cut_btn, CUT_MODE)):
            btn.blockSignals(True)
            btn.setChecked(right == mode)
            btn.blockSignals(False)
        if edit is None:
            self.info.setText(
                "No filament set active. Double-click a filament set in the Filaments table, or start one "
                "with New Filaments.",
            )
            self.convert_btn.setVisible(False)
            self.browser.clear()
            return
        state = " · unsaved changes" if edit.dirty else ""
        ro = " · read-only source: save under a user session" if edit.read_only else ""
        self.info.setText(
            f"<b>{edit.object_name}</b> ({edit.user_id}/{edit.session_id}) · {len(edit.to_list())} filaments · "
            f"step {edit.step:g} Å{state}{ro}",
        )
        for w, v in ((self.active_spin, edit.active_id),):
            w.blockSignals(True)
            w.setValue(int(v))
            w.blockSignals(False)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(edit.insert_mode)))
        self.mode_combo.blockSignals(False)
        self.convert_btn.setVisible(edit.kind(edit.active_id) == "bspline")
        from copick_shared_ui.util.instances import InstanceRow, rows_from_filaments

        rows = rows_from_filaments(edit.to_list())
        if not self.ctl.color_by_instance():  # the swatches show what the tubes show
            rgba = tuple(float(c) / 255 for c in (getattr(edit.object, "color", None) or (255, 255, 255, 255))[:4])
            for r in rows:
                r.color = rgba
        known = {r.instance_id for r in rows}
        rows += [InstanceRow(i, count=len(c), label="pending") for i, c in edit.pending.items() if i not in known]
        self.browser.set_rows(sorted(rows, key=lambda r: r.instance_id), kind="filaments")
        self.browser.set_current(edit.active_id, emit=False)
        self.browser.set_selected_keys(self.ctl.scene_selected_ids() or self.browser.selected_keys())


class InstancePanel(QWidget):
    """Instance browser of the active instance / panoptic segmentation, and instance editing controls."""

    def __init__(self, tool: Any, parent=None):
        super().__init__(parent)
        self.tool = tool
        self.ctl = tool.segmentations
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.info = QLabel("Double-click an instance or panoptic segmentation to browse its instances.")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.edit_btn = _button(
            "✏️ Edit",
            "Edit the selected instance segmentation (loads full resolution)",
            self._edit,
        )
        self.id_spin = QSpinBox()
        self.id_spin.setRange(0, 2**31 - 1)
        self.id_spin.valueChanged.connect(lambda v: self._cmd(f"copick instance id {v}"))
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(1.0, 5000.0)
        self.radius_spin.setSuffix(" Å")
        self.radius_spin.setValue(self.ctl.paint_radius)
        self.radius_spin.valueChanged.connect(lambda v: self._cmd(f"copick instance brush {v:g}"))
        self.bg_cb = QCheckBox("background only")
        self.bg_cb.setToolTip("Paint only background voxels (keep other instances)")
        self.bg_cb.toggled.connect(lambda on: setattr(self.ctl, "background_only", bool(on)))
        self.save_btn = _button("💾", "Save the instance segmentation…", self._save)
        self.edit_widgets = [
            _labelled("ID", self.id_spin),
            _labelled("Brush", self.radius_spin),
            self.bg_cb,
            self.save_btn,
        ]
        layout.addWidget(_flow_row(self.edit_btn, *self.edit_widgets))

        self.browser = _browser("Instances")
        self.browser.current_changed.connect(self._on_current)
        self.browser.focus_requested.connect(self._on_focus)
        self.browser.visibility_changed.connect(self._on_visibility)
        self.browser.new_requested.connect(lambda: self._cmd("copick instance new"))
        self.browser.delete_requested.connect(self._on_delete)
        self.browser.merge_requested.connect(self._on_merge)
        layout.addWidget(self.browser, 1)
        self.selected_segmentation = None
        self.ctl.listeners.append(self.refresh)
        self.refresh()

    def _cmd(self, command: str) -> None:
        run(self.tool.session, command)

    def _current_seg(self):
        return self.ctl.active_key

    def _edit(self) -> None:
        seg = self.selected_segmentation or self.ctl.active_key
        if seg is None:
            self.tool.session.logger.warning("copick: select an instance segmentation first.")
            return
        from copick.util.uri import serialize_copick_uri

        self._cmd(f"copick instance edit {serialize_copick_uri(seg)}")

    def _save(self) -> None:
        edit = self.ctl.edit
        if edit is None:
            return
        root = edit.run.root
        user = edit.user_id if not edit.read_only else (root.user_id or "ArtiaX")
        dlg = SaveAnnotationDialog(self, "Save instance segmentation", user, edit.session_id)
        if dlg.exec_() != QDialog.Accepted:
            return
        user, session, _ = dlg.values()
        self._cmd(f"copick instance save userId {user} sessionId {session}")

    def _on_current(self, key: int) -> None:
        if self.ctl.editing and self.ctl.edit_key is self._current_seg():
            self._cmd(f"copick instance id {key}")

    def _on_focus(self, key: int) -> None:
        seg = self._current_seg()
        if seg is not None:
            self.ctl.focus(seg, key)

    def _on_visibility(self, keys) -> None:
        seg = self._current_seg()
        if seg is not None:
            self.ctl.set_visible(seg, keys)

    def _on_delete(self, keys) -> None:
        if self.ctl.editing:
            self._cmd(f"copick instance delete {','.join(str(k) for k in keys)}")

    def _on_merge(self, sources, target: int) -> None:
        if self.ctl.editing:
            self._cmd(f"copick instance merge {','.join(str(k) for k in sources)} into {target}")

    def refresh(self) -> None:
        seg = self._current_seg()
        editing = self.ctl.editing and self.ctl.edit_key is seg
        for w in self.edit_widgets:
            w.setVisible(editing)
        self.edit_btn.setVisible(not editing)
        if seg is None:
            self.info.setText("Double-click an instance or panoptic segmentation to browse its instances.")
            self.browser.clear()
            return
        info = self.ctl.info.get(seg, {})
        kind = info.get("kind", "instance")
        self.browser.set_title("Panoptic segments" if kind == "panoptic" else "Instances")
        self.browser.set_capabilities(new=editing, delete=editing, merge=editing)
        name = getattr(seg, "name", None) or (self.ctl.edit.object_name if self.ctl.edit else "")
        level = info.get("level", 0)
        state = ""
        if editing:
            edit = self.ctl.edit
            state = f" · editing, current ID {edit.current_id}" + (" · unsaved changes" if edit.dirty else "")
            self.id_spin.blockSignals(True)
            self.id_spin.setValue(edit.current_id)
            self.id_spin.blockSignals(False)
        self.info.setText(f"<b>{name}</b> · {kind} · level {level}{state}")
        self.browser.set_rows(self.ctl.rows(seg), kind=kind)


class PicksInstancePanel(QWidget):
    """Instance browser for the current particle list (instance IDs of picks, e.g. filament IDs)."""

    def __init__(self, tool: Any, parent=None):
        super().__init__(parent)
        self.tool = tool
        self.picks = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.browser = _browser("Pick instances")
        self.browser.set_capabilities(color_toggle=True)
        self.browser.focus_requested.connect(self._on_focus)
        self.browser.visibility_changed.connect(self._on_visibility)
        self.browser.color_by_instance_toggled.connect(self._on_color)
        layout.addWidget(self.browser)

    def set_picks(self, picks) -> None:
        self.picks = picks
        self.refresh()

    def refresh(self) -> None:
        pl = self.tool.picks_map.get(self.picks) if self.picks is not None else None
        if pl is None or pl.deleted:
            self.browser.clear()
            return
        ids = [int(p["instance_id"]) for _id, p in pl.data] if pl.size else []
        scores = [float(p["score"]) for _id, p in pl.data] if pl.size else []
        base = tuple(np.asarray(pl.color, dtype=float)[:4] / 255.0) if hasattr(pl, "color") else (1, 1, 1, 1)
        self.browser.set_title(f"Pick instances · {self.picks.pickable_object_name}")
        self.browser.set_rows(rows_from_points(ids, scores, base), kind="picks")

    def _on_focus(self, key: int) -> None:
        if self.picks is not None:
            self.tool.focus_pick_instance(self.picks, key)

    def _on_visibility(self, keys) -> None:
        if self.picks is not None:
            self.tool.set_pick_instances_visible(self.picks, keys)

    def _on_color(self, on: bool) -> None:
        if self.picks is not None:
            self.tool.set_color_picks_by_instance(self.picks, on)
