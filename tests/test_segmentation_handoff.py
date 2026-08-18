"""Segmentation model wiring stays independent of its Zarr format."""

from types import SimpleNamespace

import numpy as np
import pytest

from tests.helpers import snapshot, write_ome_image


class Segmentation(SimpleNamespace):
    __hash__ = object.__hash__

    def zarr(self):
        self.zarr_calls += 1
        return self.store


@pytest.mark.parametrize("zarr_format", [2, 3])
@pytest.mark.parametrize("is_multilabel", [False, True])
def test_segmentation_store_and_display_contract_are_format_independent(
    tool_module, monkeypatch, tmp_path, zarr_format, is_multilabel
):
    path = tmp_path / f"segmentation-{zarr_format}-{is_multilabel}.zarr"
    store, _values = write_ome_image(path, zarr_format=zarr_format, paths=("seg", "coarse"))
    before = snapshot(path)
    pickable_object = SimpleNamespace(color=[100, 110, 120, 255])
    root = SimpleNamespace(get_object=lambda _name: pickable_object)
    segmentation = Segmentation(
        name="ribosome",
        run=SimpleNamespace(root=root),
        store=store,
        zarr_calls=0,
        is_multilabel=is_multilabel,
    )
    child = SimpleNamespace()
    imported_volume = SimpleNamespace(
        id_string="17",
        data=SimpleNamespace(step=(10.0, 10.0, 10.0)),
        child_models=lambda: [child],
    )
    source_volume = SimpleNamespace()
    model = SimpleNamespace(child_models=lambda: [source_volume])
    viewer_calls = []
    commands = []

    def open_store(session, received_store, name):
        viewer_calls.append((session, received_store, name))
        return [model], ""

    artiax = SimpleNamespace(import_tomogram=lambda volume: imported_volume, options_tomogram=None)
    session = SimpleNamespace(
        ArtiaX=artiax,
        models=SimpleNamespace(add=lambda _models: None),
    )
    tool = tool_module.CopickTool.__new__(tool_module.CopickTool)
    tool.session = session
    tool.active_volume = SimpleNamespace(id=7)
    tool.seg_map = {}
    tool.palette_command = "red:1,green:2"
    monkeypatch.setattr(tool_module, "open_ome_zarr_from_store", open_store)
    monkeypatch.setattr(
        tool_module,
        "run",
        lambda _session, command, **kwargs: commands.append((command, kwargs)),
    )

    tool.show_volume_from_segmentation(segmentation)

    assert segmentation.zarr_calls == 1
    assert viewer_calls[0][1] is store
    assert viewer_calls[0][2] == "ribosome"
    assert tool.seg_map[segmentation] is imported_volume
    assert artiax.options_tomogram == 7
    assert [command for command, _kwargs in commands[:3]] == [
        "volume #17 style surface",
        "volume #17 level 0.5",
        "volume #17 step 1",
    ]
    if is_multilabel:
        assert commands[3][0] == "color sample #17 map #17 palette red:1,green:2 offset -20.0"
    else:
        np.testing.assert_array_equal(imported_volume.color, [100, 110, 120, 255])
        np.testing.assert_array_equal(child.color, [100, 110, 120, 255])
    assert snapshot(path) == before
