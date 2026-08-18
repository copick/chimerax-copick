"""Application parity at the copick-store to ChimeraX-reader boundary."""

from types import SimpleNamespace

import numpy as np
import pytest
import zarr
from zarr.codecs import GzipCodec, TransposeCodec, ZstdCodec

from tests.helpers import first_declared_path, snapshot, write_ome_image


class Tomogram:
    def __init__(self, store):
        self.store = store
        self.zarr_calls = 0
        self.voxel_spacing = SimpleNamespace(run=SimpleNamespace(name="run-1"), voxel_size=10.0)

    def zarr(self):
        self.zarr_calls += 1
        return self.store


class RecordingReader:
    def __init__(self):
        self.calls = []

    def __call__(self, session, store, name, **kwargs):
        group = zarr.open_group(store=store, mode="r")
        path = first_declared_path(group)
        volume = SimpleNamespace(
            decoded=np.asarray(group[path]),
            declared_path=path,
            region=((0, 0, 0), tuple(size - 1 for size in group[path].shape), kwargs.get("initial_step")),
        )
        model = SimpleNamespace(child_models=lambda: [volume])
        self.calls.append(SimpleNamespace(session=session, store=store, name=name, kwargs=kwargs, volume=volume))
        return [model], ""


def _load(tool_module, monkeypatch, store, level):
    reader = RecordingReader()
    imported = []
    models = []
    artiax = SimpleNamespace(import_tomogram=lambda volume: imported.append(volume) or SimpleNamespace())
    session = SimpleNamespace(ArtiaX=artiax, models=SimpleNamespace(add=lambda values: models.extend(values)))
    tool = tool_module.CopickTool.__new__(tool_module.CopickTool)
    tool.session = session
    tool.settings = SimpleNamespace(zarr_level=level)
    tool.active_volume = None
    monkeypatch.setattr(tool_module, "open_ome_zarr_from_store", reader)
    tomogram = Tomogram(store)

    tool.load_tomo(tomogram)
    return tool, tomogram, reader.calls[0], imported, models


@pytest.mark.parametrize(
    ("zarr_format", "paths"),
    [
        (2, ("0", "1")),
        (2, ("s0", "preview")),
        (3, ("0", "1")),
        (3, ("s0", "preview")),
    ],
)
@pytest.mark.parametrize("level", [0, 1, 2])
def test_tomogram_handoff_is_metadata_label_agnostic_and_read_only(
    tool_module, monkeypatch, tmp_path, zarr_format, paths, level
):
    path = tmp_path / f"format-{zarr_format}-{paths[0]}-{level}.zarr"
    store, expected = write_ome_image(path, zarr_format=zarr_format, paths=paths)
    before = snapshot(path)

    tool, tomogram, call, imported, models = _load(tool_module, monkeypatch, store, level)

    assert tomogram.zarr_calls == 1
    assert call.store is store
    assert call.kwargs == {"initial_step": (2**level, 2**level, 2**level)}
    assert call.volume.declared_path == paths[0]
    np.testing.assert_array_equal(call.volume.decoded, expected[0])
    assert imported == models == [call.volume]
    assert tool.active_volume.copick_tomo is tomogram
    assert snapshot(path) == before


@pytest.mark.parametrize(
    "array_options",
    [
        {"chunks": (2, 3, 4), "compressors": (GzipCodec(level=2),)},
        {
            "chunks": (1, 2, 2),
            "shards": (2, 4, 4),
            "filters": (TransposeCodec(order=(2, 1, 0)),),
            "compressors": (ZstdCodec(level=3),),
        },
    ],
    ids=["alternate-chunks-gzip", "multiple-shards-transpose-zstd"],
)
def test_supported_noncanonical_v3_layout_is_passed_without_application_policy(
    tool_module, monkeypatch, tmp_path, array_options
):
    path = tmp_path / "noncanonical.zarr"
    store, expected = write_ome_image(
        path,
        zarr_format=3,
        paths=("fine", "coarse"),
        array_options=array_options,
    )
    before = snapshot(path)

    _tool, _tomogram, call, _imported, _models = _load(tool_module, monkeypatch, store, 0)

    assert call.volume.declared_path == "fine"
    np.testing.assert_array_equal(call.volume.decoded, expected[0])
    assert snapshot(path) == before
