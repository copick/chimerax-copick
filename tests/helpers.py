"""Small independent OME-Zarr fixtures for the application consumer seam."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import zarr
from zarr.storage import LocalStore


def spatial_axes():
    return [{"name": axis, "type": "space", "unit": "angstrom"} for axis in ("z", "y", "x")]


def write_ome_image(
    path: Path,
    *,
    zarr_format: int,
    paths=("0", "1"),
    array_options=None,
):
    """Write equivalent two-level 0.4/v2 or 0.5/v3 image data."""

    values = (
        np.arange(4 * 6 * 8, dtype=np.int16).reshape(4, 6, 8),
        np.arange(2 * 3 * 4, dtype=np.int16).reshape(2, 3, 4),
    )
    store = LocalStore(path)
    group = zarr.group(store=store, zarr_format=zarr_format)
    options = dict(array_options or {})
    if zarr_format == 2:
        options.setdefault("chunks", (1, 2, 2))
        options.setdefault("compressor", None)
    else:
        options.setdefault("chunks", (1, 2, 2))
        options.setdefault("dimension_names", ("z", "y", "x"))

    for level_path, level_values in zip(paths, values, strict=True):
        group.create_array(level_path, data=level_values, **options)

    version = "0.4" if zarr_format == 2 else "0.5"
    multiscales = [
        {
            "version": version,
            "axes": spatial_axes(),
            "datasets": [
                {
                    "path": level_path,
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [10.0 * 2**level, 10.0 * 2**level, 10.0 * 2**level]},
                    ],
                }
                for level, level_path in enumerate(paths)
            ],
        },
    ]
    if zarr_format == 2:
        group.attrs["multiscales"] = multiscales
    else:
        group.attrs["ome"] = {"version": "0.5", "multiscales": multiscales}
    return store, values


def snapshot(path: Path):
    return {item.relative_to(path).as_posix(): item.read_bytes() for item in path.rglob("*") if item.is_file()}


def first_declared_path(group):
    attributes = dict(group.attrs)
    return attributes.get("ome", attributes)["multiscales"][0]["datasets"][0]["path"]
