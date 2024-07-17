from functools import partial
from typing import Any, List, Tuple

import numpy as np
from chimerax.artiax.ArtiaX import OPTIONS_PARTLIST_CHANGED
from chimerax.artiax.particle.ParticleList import delete_selected_particles
from chimerax.core.session import Session
from chimerax.log.tool import Log
from chimerax.shortcuts.shortcuts import Shortcut, keyboard_shortcuts, list_keyboard_shortcuts

from ..misc.volops import switch_to_ortho, switch_to_slab


def copick_shortcuts() -> Tuple[List[Tuple[Any, ...]], Tuple[Any, ...]]:
    csc = [
        # Particles
        ("ww", change_particle_display, "Hide/Show ArtiaX particle lists.", "Particles", {}, "Copick"),
        ("aa", previous_particle, "Previous Particle.", "Particles", {}, "Copick"),
        ("ss", "ui mousemode right select", "Select particles mode", "Particles", {}, "Copick"),
        ("dd", next_particle, "Next Particle.", "Particles", {}, "Copick"),
        ("sa", select_all, "Select all particles for active particle list.", "Particles", {}, "Copick"),
        ("--", remove_particle, "Remove Particle.", "Particles", {}, "Copick"),
        # Picking
        ("ap", "ui mousemode right 'mark plane'", "Add on plane mode", "Picking", {}, "Copick"),
        ("dp", "ui mousemode right 'delete picked particle'", "Delete picked mode", "Picking", {}, "Copick"),
        ("ds", delete_selected_particles, "Delete selected particles", "Picking", {}, "Copick"),
        # Visualization
        ("cc", "artiax clip toggle", "Turn Clipping On/Off", "Visualization", {}, "Copick"),
        ("qq", switch_to_slab, "Switch to single plane.", "Visualization", {}, "Copick"),
        ("ee", switch_to_ortho, "Switch to orthoplanes.", "Visualization", {}, "Copick"),
        ("xx", "artiax view xy", "View XY orientation.", "Visualization", {}, "Copick"),
        ("yy", "artiax view yz", "View YZ orientation.", "Visualization", {}, "Copick"),
        ("zz", "artiax view xz", "View XZ orientation.", "Visualization", {}, "Copick"),
        ("ff", "ui mousemode right 'move planes'", "Move planes mouse mode.", "Visualization", {}, "Copick"),
        ("rr", "ui mousemode right 'rotate slab'", "Rotate slab mouse mode.", "Visualization", {}, "Copick"),
        (
            "00",
            partial(set_transparency, 0),
            "Set 0% transparency for active particle list.",
            "Particles",
            {},
            "Copick",
        ),
        (
            "55",
            partial(set_transparency, 50),
            "Set 50% transparency for active particle list.",
            "Particles",
            {},
            "Copick",
        ),
        (
            "88",
            partial(set_transparency, 80),
            "Set 80% transparency for active particle list.",
            "Particles",
            {},
            "Copick",
        ),
        # Info
        ("il", toggle_info_label, "Toggle Info Label.", "Info", {}, "Copick"),
        ("?", show_help, "Show Shortcuts in Log.", "Info", {}, "Copick"),
    ]

    catcols = (
        (
            "Particles",
            "Picking",
            "Visualization",
            "Info",
        ),
    )

    return csc, catcols


def register_shortcuts(session: Session):
    ksc = keyboard_shortcuts(session)
    ksc.shortcuts.clear()

    scs, catcols = copick_shortcuts()
    ksc.category_columns = catcols

    for sc in scs:
        sequence, command, description, category, _, _ = sc
        if isinstance(command, str):
            sc = Shortcut(sequence, command, session, description, category=category)
        else:
            sc = Shortcut(sequence, command, session, description, category=category, session_arg=True)
        ksc.add_shortcut(sc)


## Particles ##
def change_particle_display(session: Session):
    if not hasattr(session, "ArtiaX"):
        return

    session.ArtiaX.partlists.display = not session.ArtiaX.partlists.display
    session.copick._update_object_info_label(OPTIONS_PARTLIST_CHANGED, ())


def previous_particle(session: Session):
    session.copick.prev_particle()


def next_particle(session: Session):
    session.copick.next_particle()


def remove_particle(session: Session):
    session.copick.remove_particle()


def select_all(session: Session):
    if not hasattr(session, "ArtiaX"):
        return

    artia = session.ArtiaX
    pl = artia.partlists.get(artia.options_partlist)

    if pl and pl.selected_particles is not None:
        pl.selected_particles = np.logical_not(pl.selected_particles)


## Visualization ##
def set_transparency(value: float, session: Session):
    if not hasattr(session, "ArtiaX"):
        return

    artia = session.ArtiaX
    pl = artia.partlists.get(artia.options_partlist)

    if pl and pl.color is not None:
        col = pl.color
        col[3] = round(255 * (100 - value) / 100)
        pl.color = col


## Info ##
def toggle_info_label(session: Session):
    if not hasattr(session, "copick"):
        return

    session.copick.show_info = not session.copick.show_info


def show_help(session: Session):
    list_keyboard_shortcuts(session)
    session.tools.find_by_class(Log)[0].tool_window.shown = True
