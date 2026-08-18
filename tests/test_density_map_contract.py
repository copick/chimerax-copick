"""Consumer tests for the copick 2.0 density-map store contract."""

from types import SimpleNamespace

import pytest


class PickableObject:
    name = "ribosome"
    color = [10, 20, 30, 255]
    radius = 42
    map_threshold = 0.6

    def __init__(self, *, exists, store):
        self.exists = exists
        self.store = store
        self.has_density_map_calls = 0
        self.zarr_calls = 0

    def has_density_map(self):
        self.has_density_map_calls += 1
        return self.exists

    def zarr(self):
        self.zarr_calls += 1
        return self.store


class ParticleList:
    def __init__(self, name, session, data):
        self.name = name
        self.session = session
        self.data = data
        self.selected_particles = None
        self.attached = []

    def attach_display_model(self, volume):
        self.attached.append(volume)

    def hide_surfaces(self):
        pass

    def show_markers(self):
        pass

    def show_axes(self):
        pass

    def hide_markers(self):
        pass

    def hide_axes(self):
        pass


class ParticleData:
    def new_particle(self):
        raise AssertionError("the fixture contains no points")


class Entity(SimpleNamespace):
    __hash__ = object.__hash__


def _exercise_particle_load(tool_module, monkeypatch, pickable_object, opener):
    root = SimpleNamespace(get_object=lambda _name: pickable_object)
    picks = Entity(
        run=SimpleNamespace(root=root),
        pickable_object_name=pickable_object.name,
        points=[],
        from_tool=False,
        read_only=False,
        trust_orientation=True,
    )
    artiax = SimpleNamespace(added=[], add_particlelist=lambda partlist: artiax.added.append(partlist))
    session = SimpleNamespace(ArtiaX=artiax)
    tool = tool_module.CopickTool.__new__(tool_module.CopickTool)
    tool.session = session
    tool.picks_map = {}
    tool.update_stepper = lambda _partlist: None

    formats = {"Copick Picks file": SimpleNamespace(particle_data=lambda *_args, **_kwargs: ParticleData())}
    monkeypatch.setattr(tool_module, "get_formats", lambda _session: formats)
    monkeypatch.setattr(tool_module, "ParticleList", ParticleList)
    monkeypatch.setattr(tool_module, "open_ome_zarr_from_store", opener)

    tool.show_particles_from_picks(picks)
    return artiax.added[0]


def test_present_density_map_is_obtained_once_and_passed_unchanged(tool_module, monkeypatch):
    store = object()
    pickable_object = PickableObject(exists=True, store=store)
    volume = SimpleNamespace(region=((0, 0, 0), (9, 9, 9), (2, 2, 2)))
    model = SimpleNamespace(child_models=lambda: [volume])
    viewer_calls = []

    def open_store(session, received_store, name):
        viewer_calls.append((session, received_store, name))
        return [model], ""

    partlist = _exercise_particle_load(tool_module, monkeypatch, pickable_object, open_store)

    assert pickable_object.has_density_map_calls == 1
    assert pickable_object.zarr_calls == 1
    assert viewer_calls[0][1] is store
    assert viewer_calls[0][2] == "ribosome"
    assert partlist.attached == [volume]
    assert volume.region[2] == (1, 1, 1)
    assert partlist.surface_level == 0.6


@pytest.mark.parametrize("is_particle", [False, True])
def test_object_without_density_map_does_not_open_or_construct_store(tool_module, monkeypatch, is_particle):
    pickable_object = PickableObject(exists=False, store=object())
    pickable_object.is_particle = is_particle

    def unexpected_open(*_args):
        raise AssertionError("viewer must not open an absent density map")

    partlist = _exercise_particle_load(tool_module, monkeypatch, pickable_object, unexpected_open)

    assert pickable_object.has_density_map_calls == 1
    assert pickable_object.zarr_calls == 0
    assert partlist.attached == []


def test_true_existence_with_none_store_is_a_clear_contract_error(tool_module, monkeypatch):
    pickable_object = PickableObject(exists=True, store=None)

    with pytest.raises(RuntimeError, match="reports a density map but returned no store"):
        _exercise_particle_load(tool_module, monkeypatch, pickable_object, lambda *_args: None)

    assert pickable_object.has_density_map_calls == 1
    assert pickable_object.zarr_calls == 1


def test_viewer_failure_is_not_swallowed(tool_module, monkeypatch):
    pickable_object = PickableObject(exists=True, store=object())

    def fail(*_args):
        raise PermissionError("backend denied density-map read")

    with pytest.raises(PermissionError, match="backend denied density-map read"):
        _exercise_particle_load(tool_module, monkeypatch, pickable_object, fail)
