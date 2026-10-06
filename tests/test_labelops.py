"""2D label lookup, without ChimeraX: run with ``pytest tests``."""

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace


class LabelModel:
    def __init__(self, label):
        self.label = label
        self.name = label.name


def _load_labelops():
    # labelops imports two ChimeraX modules; stand-ins are enough for the lookup.
    stubs = {
        "chimerax": types.ModuleType("chimerax"),
        "chimerax.core": types.ModuleType("chimerax.core"),
        "chimerax.core.session": types.ModuleType("chimerax.core.session"),
        "chimerax.label": types.ModuleType("chimerax.label"),
        "chimerax.label.label2d": types.ModuleType("chimerax.label.label2d"),
    }
    stubs["chimerax.core.session"].Session = object
    stubs["chimerax.label.label2d"].LabelModel = LabelModel
    saved = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        path = Path(__file__).resolve().parents[1] / "src" / "misc" / "labelops.py"
        spec = importlib.util.spec_from_file_location("chimerax_copick_labelops", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return module


labelops = _load_labelops()


def _session(*models):
    return SimpleNamespace(models=SimpleNamespace(list=lambda: list(models)))


def test_label_found_after_its_text_changes():
    mouse = LabelModel(SimpleNamespace(name="mouse_info", text="right mouse: translate"))
    info = LabelModel(SimpleNamespace(name="object_info", text="Particles shown"))
    session = _session(object(), mouse, info)
    assert labelops.get_label_model(session, "mouse_info") is mouse

    # ChimeraX renames the label's model to its text on every update
    mouse.name = "Press ? for help | right mouse: trace copick filament"
    info.name = "Particles shown | Current Object: microtubule | Editable: Yes"
    assert labelops.get_label_model(session, "mouse_info") is mouse
    assert labelops.get_label_model(session, "object_info") is info
    assert labelops.get_label_model(session, "missing") is None
