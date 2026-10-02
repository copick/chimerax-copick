"""Carry the viewing state from one loaded tomogram to another when switching between them.

All tomograms of a run share the same physical frame (ArtiaX places them at origin 0 with
step = voxel size), so slab offsets and orthoplane positions are transferred in Angstrom and
re-expressed in the target's grid. Contrast levels and step are per-tomogram and not copied.
"""

from typing import Any, Dict

from chimerax.artiax.volume.Tomogram import Tomogram

from .volops import switch_to_ortho, switch_to_surf, switch_to_volren


def capture_view_state(vol: Tomogram) -> Dict[str, Any]:
    ro = vol.rendering_options
    state = {
        "contrast_mode": vol.contrast_mode,
        "is_clipped": vol.is_clipped,
    }

    if vol.surface_shown and not vol.image_shown:
        state["mode"] = "surface"
    elif ro.image_mode == "orthoplanes":
        state["mode"] = "ortho"
        state["ortho_shown"] = tuple(ro.orthoplanes_shown)
        state["ortho_xyz"] = tuple(vol.data.ijk_to_xyz(ro.orthoplane_positions))
    elif ro.image_mode == "tilted slab":
        state["mode"] = "slab"
        state["normal"] = tuple(vol.normal)
        state["offset"] = float(vol.slab_position)
    else:
        state["mode"] = "volren"

    return state


def apply_view_state(vol: Tomogram, state: Dict[str, Any]) -> None:
    session = vol.session

    if state["contrast_mode"] != vol.contrast_mode:
        vol.contrast_mode = state["contrast_mode"]

    mode = state["mode"]
    if mode == "slab":
        vol.normal = state["normal"]
        vol.slab_position = min(max(state["offset"], vol.min_offset), vol.max_offset)
    elif mode == "ortho":
        ijk = vol.data.xyz_to_ijk(state["ortho_xyz"])
        size = vol.data.size
        positions = tuple(min(max(int(round(c)), 0), s - 1) for c, s in zip(ijk, size, strict=False))
        axes = "".join(a for a, shown in zip("xyz", state["ortho_shown"], strict=False) if shown) or "xyz"
        switch_to_ortho(session, vol=vol, positions=positions, axes=axes)
    elif mode == "volren":
        switch_to_volren(session, vol=vol)
    elif mode == "surface":
        switch_to_surf(session, vol=vol)

    # Clip planes are global scene planes at the same physical offset, so only the flag moves.
    # Re-issue them in slab mode in case the offset was clamped to the target's extent.
    vol._is_clipped = state["is_clipped"]
    if state["is_clipped"] and mode == "slab":
        vol._set_clipping()
