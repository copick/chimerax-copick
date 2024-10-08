from functools import partial

from chimerax.artiax.particle.ParticleList import delete_selected_particles

from ..misc.volops import set_step, switch_to_ortho, switch_to_slab, switch_to_surf, switch_to_volren

_providers = {
    "XY": "artiax view xy",
    "XZ": "artiax view xz",
    "YZ": "artiax view yz",
    "Clip": "artiax clip toggle",
    "Invert Contrast": "artiax invert",
    "Select": "ui mousemode right select",
    "Rotate": "ui mousemode right rotate",
    "Translate": "ui mousemode right translate",
    "Pivot": "ui mousemode right pivot",
    "Translate Selected Particles": 'ui mousemode right "translate selected particles"',
    "Rotate Selected Particles": 'ui mousemode right "rotate selected particles"',
    "Translate Picked Particle": 'ui mousemode right "translate picked particle"',
    "Rotate Picked Particle": 'ui mousemode right "rotate picked particle"',
    "Delete Selected Particles": delete_selected_particles,
    "Delete Picked Particle": 'ui mousemode right "delete picked particle"',
    "Show Markers": "artiax show markers",
    "Hide Markers": "artiax hide markers",
    "Show Axes": "artiax show axes",
    "Hide Axes": "artiax hide axes",
    "Show Surfaces": "artiax show surfaces",
    "Hide Surfaces": "artiax hide surfaces",
    "Tilted Slab": switch_to_slab,
    "Volume Rendering": switch_to_volren,
    "Orthoplanes": switch_to_ortho,
    "Surface": switch_to_surf,
    "1x": partial(set_step, (1, 1, 1)),
    "2x": partial(set_step, (2, 2, 2)),
    "4x": partial(set_step, (4, 4, 4)),
}


def run_provider(session, name):
    what = _providers[name]

    if not isinstance(what, str):
        what(session)
    else:
        from chimerax.core.commands import run

        run(session, what)
