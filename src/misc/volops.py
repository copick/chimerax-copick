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


def switch_to_slab(session: Session) -> None:
    vol = _valid_vol(session)

    if vol:
        vol.integer_slab_position = vol.slab_count // 2 + 1


def switch_to_volren(session: Session) -> None:
    vol = _valid_vol(session)

    if vol:
        sx, sy, sz = vol.region[2]
        run(session, f"volume #{vol.id_string} style image imageMode 'full region' step {sx},{sy},{sz}")


def switch_to_ortho(session: Session):
    vol = _valid_vol(session)

    if vol:
        szx, szy, szz = vol.data.size
        szx = szx // 2 + 1
        szy = szy // 2 + 1
        szz = szz // 2 + 1
        sx, sy, sz = vol.region[2]
        run(
            session,
            f"volume #{vol.id_string} colorMode l8 orthoplanes xyz positionPlanes {szx},{szy},{szz} "
            f"imageMode orthoplanes step {sx},{sy},{sz}",
        )


def switch_to_surf(session: Session):
    vol = _valid_vol(session)

    if vol:
        sx, sy, sz = vol.region[2]
        run(session, f"volume #{vol.id_string} style surface step {sx},{sy},{sz}")


def set_step(step: Tuple[int, int, int], session: Session):
    vol = _valid_vol(session)

    if vol:
        sx, sy, sz = step
        run(session, f"volume #{vol.id_string} step {sx},{sy},{sz}")
