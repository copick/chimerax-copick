from typing import Iterable, Optional, Tuple

from copick.models import CopickRun
from copick_shared_ui.core.types import is_filament_object

from .BaseEntityDialog import BaseEntityDialog, ColoredComboBox


def next_manual_session_id(entities: Iterable) -> str:
    """The next free ``manual-X`` session ID among ``entities``."""
    existing = {str(e.session_id).lower() for e in entities if getattr(e, "session_id", None)}
    counter = 1
    while f"manual-{counter}" in existing:
        counter += 1
    return f"manual-{counter}"


class _NewEntityDialog(BaseEntityDialog):
    """Object + user + session for a new entity; subclasses choose the objects and the existing entities."""

    title = "Create New"
    info = ""
    ok_text = "Create"

    def __init__(self, run: CopickRun, parent=None, preset_user_id: str = None):
        self._run = run
        default_user_id = run.root.user_id if run and run.root and run.root.user_id else "ArtiaX"
        super().__init__(parent, preset_user_id, default_user_id)

    def _objects(self):
        return list(self._run.root.pickable_objects) if self._run and self._run.root else []

    def _existing(self):
        return []

    def _setup_specific_ui(self):
        self.setWindowTitle(self.title)
        self._object_combo = ColoredComboBox()
        self._object_combo.setToolTip("Select the pickable object")
        self._form_layout.insertRow(0, "Object:", self._object_combo)
        self._info_label.setText(self.info)
        self._object_combo.currentTextChanged.connect(self._update_ok_button)

    def _populate_initial_data(self):
        for obj in self._objects():
            self._object_combo.addColoredItem(obj.name, obj.color if obj.color else (128, 128, 128, 255))
        self._session_edit.setText(next_manual_session_id(self._existing()))

    def get_selection(self) -> Optional[Tuple[str, str, str]]:
        if self.result() != self.Accepted:
            return None
        object_name = self._object_combo.currentText()
        user_id = self.get_user_id()
        session_id = self.get_session_id()
        if not object_name or not user_id or not session_id:
            return None
        return object_name, user_id, session_id

    def _validate_additional_fields(self) -> bool:
        return bool(self._object_combo.currentText())

    def _get_ok_button_text(self) -> str:
        return self.ok_text

    def _use_dialog_button_box(self) -> bool:
        return True


class NewFilamentsDialog(_NewEntityDialog):
    """A new set of traced filaments (filament objects only)."""

    title = "Trace New Filaments"
    info = (
        "Start a new set of traced filaments. Click on the tomogram plane to place control points; the "
        "centreline is a Catmull-Rom curve through them. Only objects declared as filaments are listed "
        "(Edit Object Types → Is Filament)."
    )
    ok_text = "Start tracing"

    def _objects(self):
        return [o for o in super()._objects() if is_filament_object(o)]

    def _existing(self):
        return list(getattr(self._run, "filaments", []))


class NewInstanceSegmentationDialog(_NewEntityDialog):
    """A new, empty instance segmentation to paint."""

    title = "New Instance Segmentation"
    info = (
        "Start a new instance segmentation at the shown tomogram's voxel spacing. Paint instance IDs on the "
        "tomogram plane (right mouse: paint copick instance); IDs match picks and filaments of the same object."
    )
    ok_text = "Start painting"

    def _existing(self):
        return list(self._run.segmentations)
