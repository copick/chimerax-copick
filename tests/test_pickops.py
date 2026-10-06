"""Pick <-> particle conversion, without ChimeraX: run with ``pytest tests``."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from copick.models import CopickLocation, CopickPoint, PickableObject


def _load_pickops():
    # Importing the bundle package pulls in ChimeraX; the helpers only need copick and numpy.
    path = Path(__file__).resolve().parents[1] / "src" / "misc" / "pickops.py"
    spec = importlib.util.spec_from_file_location("chimerax_copick_pickops", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pickops = _load_pickops()


def _rotation_zyz(a, b, c):
    """Rotation by a about Z, then b about the new Y, then c about the new Z (degrees)."""

    def axis(i, deg):
        t = np.radians(deg)
        c_, s_ = np.cos(t), np.sin(t)
        if i == "z":
            return np.array([[c_, -s_, 0], [s_, c_, 0], [0, 0, 1]])
        return np.array([[c_, 0, s_], [0, 1, 0], [-s_, 0, c_]])

    return axis("z", a) @ axis("y", b) @ axis("z", c)


def _point(location, shift=(0.0, 0.0, 0.0), euler=(0.0, 0.0, 0.0), instance_id=0, score=1.0):
    transform = np.eye(4)
    transform[:3, :3] = _rotation_zyz(*euler)
    transform[:3, 3] = shift
    return CopickPoint(
        location=CopickLocation(x=location[0], y=location[1], z=location[2]),
        transformation_=transform.tolist(),
        instance_id=instance_id,
        score=score,
    )


def _translation(v):
    m = np.eye(4)
    m[:3, 3] = v
    return m


def test_shifted_rotated_point_round_trips():
    point = _point((100.0, 200.0, 300.0), shift=(4.0, -6.0, 2.5), euler=(30, 60, -45), instance_id=7, score=0.25)
    origin, shift, rotation = pickops.point_pose(point)
    # ArtiaX hands the rotation back as a 3x4 Place matrix with no translation.
    back = pickops.point_from_pose(origin, shift, np.hstack([rotation, np.zeros((3, 1))]), 7, 0.25)
    assert back.location == point.location
    assert np.allclose(back.transformation, point.transformation)
    assert (back.instance_id, back.score) == (7, 0.25)


def test_artiax_transform_places_the_particle_at_location_plus_shift():
    point = _point((100.0, 200.0, 300.0), shift=(4.0, -6.0, 2.5), euler=(10, 20, 30))
    origin, shift, rotation = pickops.point_pose(point)
    rot = np.eye(4)
    rot[:3, :3] = rotation
    # ArtiaX: full_transform = origin * translation * rotation
    full = _translation(origin) @ _translation(shift) @ rot
    expected = np.asarray(point.transformation).copy()
    expected[:3, 3] += [100.0, 200.0, 300.0]
    assert np.allclose(full, expected)


def test_missing_identity_takes_copick_defaults():
    point = _point((1.0, 2.0, 3.0))
    point.instance_id, point.score = None, None
    assert pickops.point_identity(point) == (0, 1.0)
    assert pickops.point_identity(_point((1.0, 2.0, 3.0), score=float("nan"))) == (0, 1.0)
    built = pickops.point_from_pose((0, 0, 0), (0, 0, 0), np.eye(3), instance_id=None, score=None)
    assert (built.instance_id, built.score) == (0, 1.0)


class _FakeParticleData:
    """ArtiaX zero-fills every key of a new particle."""

    def __init__(self):
        self.particles = []

    def new_particle(self):
        particle = {"score": 0, "instance_id": 0, "shift_x": 0}
        self.particles.append(particle)
        return particle


def test_new_particles_start_at_score_one():
    data = pickops.with_new_particle_defaults(_FakeParticleData())
    assert pickops.with_new_particle_defaults(data) is data  # wrapping twice is a no-op
    particle = data.new_particle()
    assert particle["score"] == 1.0 and particle["instance_id"] == 0 and particle["shift_x"] == 0
    # Loading overwrites the defaults with the point's own values.
    loaded = data.new_particle()
    loaded["score"], loaded["instance_id"] = 0.5, 3
    assert data.particles[1] == {"score": 0.5, "instance_id": 3, "shift_x": 0}


def test_is_filament_reads_the_property_or_the_metadata():
    assert pickops.is_filament(SimpleNamespace(is_filament=True))
    assert not pickops.is_filament(SimpleNamespace(is_filament=False, metadata={"copick": {"filament": {}}}))
    # copick < 1.28: no property, the spec is in metadata
    assert pickops.is_filament(SimpleNamespace(metadata={"copick": {"filament": {"polar": True}}}))
    assert not pickops.is_filament(SimpleNamespace(metadata={"copick": {"filament": None}}))
    assert not pickops.is_filament(SimpleNamespace(metadata={"copick": "something else"}))
    assert not pickops.is_filament(SimpleNamespace(metadata=None))
    assert pickops.is_filament(
        PickableObject(name="microtubule", is_particle=True, label=1, metadata={"copick": {"filament": {}}}),
    )
    assert not pickops.is_filament(PickableObject(name="ribosome", is_particle=True, label=2))


def test_merging_filaments_keeps_them_apart():
    existing = SimpleNamespace(points=[_point((0, 0, 0), instance_id=1), _point((0, 10, 0), instance_id=2)])
    incoming = SimpleNamespace(
        points=[
            _point((0, 0, 0), instance_id=1),  # already present: skipped
            _point((50, 0, 0), instance_id=1),
            _point((60, 0, 0), instance_id=1),
            _point((70, 0, 0), instance_id=0),
            _point((80, 0, 0), instance_id=3),
        ],
    )
    merged = pickops.append_no_duplicates(incoming, existing, offset_ids=True)
    assert [p.instance_id for p in merged.points] == [1, 2, 3, 3, 0, 5]
    assert [p.instance_id for p in incoming.points] == [1, 1, 1, 0, 3], "the source set is not modified"

    plain = SimpleNamespace(points=[_point((0, 0, 0), instance_id=1)])
    merged = pickops.append_no_duplicates(SimpleNamespace(points=[_point((5, 0, 0), instance_id=1)]), plain)
    assert [p.instance_id for p in merged.points] == [1, 1]


def test_instance_colours():
    base = [255, 0, 0, 200]
    colors = pickops.instance_id_colors([0, 1, 1, 2, 0], base)
    assert colors.shape == (5, 4) and colors.dtype == np.uint8
    assert (colors[0] == base).all() and (colors[4] == base).all()
    assert (colors[1] == colors[2]).all() and not (colors[1] == colors[3]).all()
    assert (colors[:, 3] == 200).all()


@pytest.mark.parametrize("ids", [[], [0, 0]])
def test_instance_colours_without_instances(ids):
    assert (pickops.instance_id_colors(ids, [1, 2, 3, 255]) == [1, 2, 3, 255]).all()
