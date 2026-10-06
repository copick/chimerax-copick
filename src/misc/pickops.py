import colorsys
from typing import Iterable, List, Sequence, Tuple

import numpy as np
from copick.models import CopickLocation, CopickPicks, CopickPoint

# Values a particle placed in the GUI starts with. ArtiaX fills every key with 0, and a pick saved with score 0
# looks rejected to every tool that filters on score.
NEW_PARTICLE_DEFAULTS = {"score": 1.0, "instance_id": 0}


def point_pose(point: CopickPoint) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split a copick point into ArtiaX's origin, shift and rotation.

    copick's particle centre is ``location + t``, with ``t`` the transform's translation in the tomogram frame (Å).
    ArtiaX places a particle at ``origin · translation · rotation``, the same model, so the location is the origin
    and ``t`` is the shift.

    Returns:
        origin (3,), shift (3,) and rotation (3, 3).
    """
    transform = np.asarray(point.transformation, dtype=float)
    origin = np.array([point.location.x, point.location.y, point.location.z], dtype=float)
    return origin, transform[:3, 3].copy(), transform[:3, :3].copy()


def point_identity(point: CopickPoint) -> Tuple[int, float]:
    """A point's instance_id and score, with copick's defaults (0 and 1.0) where they are missing."""
    return _instance_id(point.instance_id), _score(point.score)


def point_from_pose(
    origin: Sequence[float],
    shift: Sequence[float],
    rotation: np.ndarray,
    instance_id=0,
    score=1.0,
) -> CopickPoint:
    """Build a copick point from ArtiaX's origin, shift and rotation (3x3, or a 3x4 whose last column is ignored)."""
    transform = np.eye(4)
    transform[:3, :3] = np.asarray(rotation, dtype=float)[:3, :3]
    transform[:3, 3] = np.asarray(shift, dtype=float)
    return CopickPoint(
        location=CopickLocation(x=float(origin[0]), y=float(origin[1]), z=float(origin[2])),
        transformation_=transform.tolist(),
        instance_id=_instance_id(instance_id),
        score=_score(score),
    )


def with_new_particle_defaults(data):
    """Make ``data.new_particle()`` start particles at :data:`NEW_PARTICLE_DEFAULTS`; returns ``data``.

    Wraps the method on this one instance rather than subclassing the format's ParticleData: ArtiaX restores sessions
    by resolving classes through the owning bundle, and this bundle has no ``get_class`` for its own.
    """
    if getattr(data.new_particle, "_copick_defaults", False):
        return data
    original = data.new_particle

    def new_particle(*args, **kwargs):
        particle = original(*args, **kwargs)
        for key, value in NEW_PARTICLE_DEFAULTS.items():
            particle[key] = value
        return particle

    new_particle._copick_defaults = True
    data.new_particle = new_particle
    return data


def is_filament(obj) -> bool:
    """Whether a pickable object is declared a filament.

    copick >= 1.28 has ``is_filament``; older copick still carries the spec in ``metadata["copick"]["filament"]``.
    """
    flag = getattr(obj, "is_filament", None)
    if isinstance(flag, bool):
        return flag
    metadata = getattr(obj, "metadata", None)
    namespace = metadata.get("copick") if isinstance(metadata, dict) else None
    return isinstance(namespace, dict) and namespace.get("filament") is not None


def offset_instance_ids(points: Iterable[CopickPoint], existing: Iterable[CopickPoint]) -> List[CopickPoint]:
    """Copies of ``points`` whose instance ids are moved past the largest id in ``existing``.

    Two pick sets both number their filaments from 1, so merging one into the other unchanged would join unrelated
    filaments. Unassigned points (0) stay 0.
    """
    start = max((_instance_id(p.instance_id) for p in existing), default=0)
    moved = []
    for point in points:
        copy = point.model_copy(deep=True)
        instance_id = _instance_id(copy.instance_id)
        copy.instance_id = instance_id + start if instance_id > 0 else 0
        moved.append(copy)
    return moved


def instance_id_colors(instance_ids: Sequence[int], base_rgba: Sequence[int]) -> np.ndarray:
    """One RGBA colour per particle: each instance its own hue, unassigned (0) particles the object's colour.

    Hues step by the golden ratio so neighbouring ids stay distinguishable.

    Returns:
        (N, 4) uint8, in the order of ``instance_ids``.
    """
    ids = np.asarray([_instance_id(i) for i in instance_ids], dtype=np.int64)
    colors = np.tile(np.asarray(base_rgba, dtype=np.uint8)[:4], (len(ids), 1))
    for value in np.unique(ids[ids > 0]):
        rgb = colorsys.hsv_to_rgb((value * 0.618033988749895) % 1.0, 0.65, 0.95)
        colors[ids == value, :3] = np.round(np.array(rgb) * 255).astype(np.uint8)
    return colors


def append_no_duplicates(inp: CopickPicks, out: CopickPicks, offset_ids: bool = False) -> CopickPicks:
    """Append the points of ``inp`` that ``out`` does not already have at the same location.

    With ``offset_ids``, the appended points' instance ids are moved past those already in ``out``
    (:func:`offset_instance_ids`), which is what merging two sets of filaments needs.
    """
    # Special cases
    if out.points is None:
        out.points = inp.points if inp.points is not None else []
        return out

    if inp.points is None:
        out.points = []
        return out

    if len(inp.points) == 0:
        return out

    if len(out.points) == 0:
        out.points = inp.points if inp.points is not None else []
        return out

    # Convert to numpy arrays
    inp_arr = np.ndarray((len(inp.points), 3))
    for idx, pt in enumerate(inp.points):
        inp_arr[idx, :] = [pt.location.x, pt.location.y, pt.location.z]

    out_arr = np.ndarray((len(out.points), 3))
    for idx, pt in enumerate(out.points):
        out_arr[idx, :] = [pt.location.x, pt.location.y, pt.location.z]

    # If not existing in out, append it
    new_points = [
        inp.points[idx] for idx, pt in enumerate(inp_arr) if not np.any(np.all(np.isclose(pt, out_arr), axis=1))
    ]
    if offset_ids:
        new_points = offset_instance_ids(new_points, out.points)
    out.points.extend(new_points)

    return out


def _instance_id(value) -> int:
    return 0 if value is None else int(value)


def _score(value) -> float:
    return 1.0 if value is None or not np.isfinite(float(value)) else float(value)
