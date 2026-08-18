"""Application-level contracts for passing copick stores to the viewer."""

from __future__ import annotations

from typing import Any, Protocol


class DensityMapObject(Protocol):
    """The public copick object surface used by chimerax-copick."""

    name: str

    def has_density_map(self) -> bool: ...

    def zarr(self) -> Any | None: ...


def density_map_store(pickable_object: DensityMapObject) -> Any | None:
    """Return one density-map store, using copick's explicit existence contract."""

    if not pickable_object.has_density_map():
        return None

    store = pickable_object.zarr()
    if store is None:
        name = getattr(pickable_object, "name", "<unknown>")
        raise RuntimeError(f"Copick object {name!r} reports a density map but returned no store")
    return store
