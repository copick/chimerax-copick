"""Narrow stubs for testing bundle logic outside ChimeraX."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"


class Placeholder:
    """Import-compatible stand-in for ChimeraX, ArtiaX, Qt, and copick types."""

    def __init__(self, *args, **kwargs):
        pass


def _module(monkeypatch, name: str, **attributes) -> ModuleType:
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


@pytest.fixture
def tool_module(monkeypatch):
    """Load ``src/tool.py`` with only its import-time host APIs stubbed."""

    for package in (
        "chimerax",
        "chimerax.artiax",
        "chimerax.artiax.io",
        "chimerax.artiax.particle",
        "chimerax.core",
        "chimerax.ome_zarr",
        "copick.impl",
        "copick.util",
        "copick_shared_ui",
        "copick_shared_ui.core",
        "Qt",
    ):
        _module(monkeypatch, package)

    _module(monkeypatch, "copick")
    _module(monkeypatch, "chimerax.artiax.ArtiaX", OPTIONS_PARTLIST_CHANGED="options changed")
    _module(monkeypatch, "chimerax.artiax.io.formats", get_formats=lambda _session: {})
    _module(
        monkeypatch,
        "chimerax.artiax.particle.ParticleList",
        PARTLIST_CHANGED="particle list changed",
        ParticleList=Placeholder,
        lock_particlelist=lambda *_args, **_kwargs: None,
    )
    _module(
        monkeypatch,
        "chimerax.core.commands",
        log_equivalent_command=lambda *_args, **_kwargs: None,
        run=lambda *_args, **_kwargs: None,
    )
    _module(monkeypatch, "chimerax.core.models", Surface=Placeholder)
    _module(monkeypatch, "chimerax.core.tools", ToolInstance=Placeholder)
    _module(
        monkeypatch,
        "chimerax.ome_zarr.open",
        open_ome_zarr_from_store=lambda *_args, **_kwargs: ([], ""),
    )
    _module(monkeypatch, "chimerax.ui", MainToolWindow=Placeholder)
    _module(monkeypatch, "copick.impl.filesystem", CopickTomogramFSSpec=Placeholder)
    _module(
        monkeypatch,
        "copick.models",
        CopickLocation=Placeholder,
        CopickMesh=Placeholder,
        CopickPicks=Placeholder,
        CopickPoint=Placeholder,
        CopickSegmentation=Placeholder,
    )
    _module(monkeypatch, "copick.util.uri", serialize_copick_uri=lambda entity: str(entity))
    _module(
        monkeypatch,
        "copick_shared_ui.core.thumbnail_cache",
        set_global_cache_config=lambda *_args, **_kwargs: None,
        set_global_cache_image_interface=lambda *_args, **_kwargs: None,
    )
    _module(monkeypatch, "Qt.QtCore", QModelIndex=Placeholder)
    _module(monkeypatch, "Qt.QtGui", QFont=Placeholder)
    _module(monkeypatch, "Qt.QtWidgets", QVBoxLayout=Placeholder)

    bundle_package = _module(monkeypatch, "portable_bundle")
    bundle_package.__path__ = [str(SOURCE_ROOT)]
    _module(monkeypatch, "portable_bundle.misc.colorops", palette_from_root=lambda _root: "")
    _module(monkeypatch, "portable_bundle.misc.meshops", ensure_mesh=lambda mesh: mesh)
    _module(monkeypatch, "portable_bundle.misc.pickops", append_no_duplicates=lambda left, _right: left)
    _module(monkeypatch, "portable_bundle.misc.settings", CoPickSettings=Placeholder)
    _module(monkeypatch, "portable_bundle.ui.EntityTable", TablePicks=Placeholder)
    _module(monkeypatch, "portable_bundle.ui.main_widget", MainWidget=Placeholder)
    _module(monkeypatch, "portable_bundle.ui.tree", TreeTomogram=Placeholder)

    spec = importlib.util.spec_from_file_location("portable_bundle.tool", SOURCE_ROOT / "tool.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module
