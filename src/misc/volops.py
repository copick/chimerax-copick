from typing import Tuple, Union

from chimerax.artiax.volume.Tomogram import Tomogram
from chimerax.core.commands import run
from chimerax.core.session import Session


def _valid_vol(session: Session) -> Union[Tomogram, None]:
    if not hasattr(session, "copick"):
        return None

    if session.copick.active_volume is None:
        return None

    if session.copick.active_volume.deleted:
        return None

    return session.copick.active_volume


def _exit_spotlight(session: Session) -> None:
    """Switching to a regular view mode turns spotlight off (restores the source volume)."""
    tool = getattr(session, "copick", None)
    spotlight = getattr(tool, "spotlight", None) if tool else None
    if spotlight is not None and spotlight.enabled:
        spotlight.disable()


def _target_vol(session: Session, vol: Union[Tomogram, None]) -> Union[Tomogram, None]:
    """Explicit volume (used when transferring view state), else the active one (UI actions)."""
    if vol is not None:
        return vol
    _exit_spotlight(session)
    return _valid_vol(session)


def switch_to_slab(session: Session, vol: Tomogram = None) -> None:
    vol = _target_vol(session, vol)

    if vol:
        step = vol.region[2]
        vol.integer_slab_position = vol.slab_count // 2 + 1
        reg = vol.region
        vol.region = (reg[0], reg[1], step)


def switch_to_volren(session: Session, vol: Tomogram = None) -> None:
    log = vol is None  # log UI actions, not internal view-state transfers
    vol = _target_vol(session, vol)

    if vol:
        sx, sy, sz = vol.region[2]
        run(session, f"volume #{vol.id_string} style image imageMode 'full region' step {sx},{sy},{sz}", log=log)


def switch_to_ortho(session: Session, vol: Tomogram = None, positions: Tuple[int, int, int] = None, axes: str = "xyz"):
    log = vol is None  # log UI actions, not internal view-state transfers
    vol = _target_vol(session, vol)

    if vol:
        if positions is None:
            szx, szy, szz = vol.data.size
            positions = (szx // 2 + 1, szy // 2 + 1, szz // 2 + 1)
        px, py, pz = positions
        sx, sy, sz = vol.region[2]
        run(
            session,
            f"volume #{vol.id_string} colorMode l8 orthoplanes {axes} positionPlanes {px},{py},{pz} "
            f"imageMode orthoplanes step {sx},{sy},{sz}",
            log=log,
        )


def switch_to_surf(session: Session, vol: Tomogram = None):
    log = vol is None  # log UI actions, not internal view-state transfers
    vol = _target_vol(session, vol)

    if vol:
        sx, sy, sz = vol.region[2]
        run(session, f"volume #{vol.id_string} style surface step {sx},{sy},{sz}", log=log)


def toggle_clip(session: Session) -> None:
    """Toggle slab clipping on the shown tomogram.

    ``artiax clip toggle`` picks the first displayed ArtiaX tomogram, which can be a
    segmentation (also an ArtiaX tomogram) once several tomograms have been loaded.
    """
    vol = _valid_vol(session)
    if vol is None:
        run(session, "artiax clip toggle")
        return

    from chimerax.artiax.util.clip import clip

    clip(session, "toggle", model=vol)


def set_step(step: Tuple[int, int, int], session: Session, vol: Tomogram = None):
    if vol is None:
        vol = _valid_vol(session)

    if vol:
        sx, sy, sz = step
        run(session, f"volume #{vol.id_string} step {sx},{sy},{sz}")
