# Python
from copy import deepcopy
from sys import platform

import numpy as np
from chimerax.artiax.io.formats import get_formats

# ArtiaX
from chimerax.artiax.particle.ParticleList import ParticleList, lock_particlelist
from chimerax.core.commands import run

# ChimeraX
from chimerax.core.tools import ToolInstance

# OME-Zarr
from chimerax.ome_zarr.open import open_ome_zarr_from_store
from chimerax.ui import MainToolWindow

# Copick
from copick.impl.filesystem import CopickRootFSSpec, CopickTomogramFSSpec
from copick.models import CopickLocation, CopickPicks, CopickPoint

# Qt
from Qt.QtCore import QModelIndex
from Qt.QtGui import QFont
from Qt.QtWidgets import QVBoxLayout

from .misc.pickops import append_no_duplicates

# This tool
from .ui.main_widget import MainWidget
from .ui.table import TablePicks
from .ui.tree import TreeTomogram


class CopickTool(ToolInstance):
    # Does this instance persist when session closes
    SESSION_ENDURING = False
    # We do save/restore in sessions
    SESSION_SAVE = True
    # Let ChimeraX know about our help page

    def __init__(self, session, tool_name):
        # Initialize base class
        super().__init__(session, tool_name)

        # Display Name
        self.display_name = "copick"

        # Store self in session
        session.copick = self

        # Vars for tracking objects
        self.active_volume = None

        # Set the font
        if platform == "darwin":
            self.font = QFont("Arial", 10)
        else:
            self.font = QFont("Arial", 7)

        # self.settings = CoPickSettings(session, "copick", version="1")
        """Settings."""

        # UI
        self.tool_window = MainToolWindow(self, close_destroys=False)
        self._build_ui()

        self.root = None
        self.list_map = {}
        """Map picks to particle lists."""

        # Mouse Modes
        from .mouse.mousemodes import WheelMovePlanesMode

        self.wheel_move_planes_mode = WheelMovePlanesMode(self.session)
        self.session.ui.mouse_modes.add_mode(self.wheel_move_planes_mode)
        run(self.session, "ui mousemode shift wheel 'move copick planes'")
        self.session.triggers.add_handler("app quit", self._store)

    def _build_ui(self):
        tw = self.tool_window

        self._layout = QVBoxLayout()
        self._mw = MainWidget(self)
        self._layout.addWidget(self._mw)

        tw.ui_area.setLayout(self._layout)
        tw.manage("left")

    def from_config_file(self, config_file: str):
        if self.root is not None:
            self.store()
            self.close_all()

        self.root = CopickRootFSSpec.from_file(config_file)
        self._mw.set_root(self.root)

    def close_all(self):
        for _p, pl in self.list_map.items():
            pl.delete()
        self.list_map = {}

    def _store(self, *args, **kwargs):
        self.store()

    def store(self):
        for pick, pl in self.list_map.items():
            if pick.from_tool:
                continue

            points = []
            for _id, p in pl.data:
                rotmat = np.eye(4)
                rotmat[0:3, :] = p.rotation.matrix
                point = CopickPoint(
                    location=CopickLocation(x=p["location_x"], y=p["location_y"], z=p["location_z"]),
                    transformation_=rotmat.tolist(),
                    instance_id=p["instance_id"],
                    score=p["score"],
                )
                points.append(point)

            pick.points = points
            pick.store()

    def close_active_volume(self):
        # Close the active volume
        if self.active_volume and not self.active_volume.deleted:
            self.active_volume.delete()

    def load_tomo(self, tomo: CopickTomogramFSSpec):
        """Load a tomogram from the copick backend system."""
        name = f"{tomo.voxel_spacing.run.name} - {tomo.voxel_spacing.voxel_size}"
        mods, msg = open_ome_zarr_from_store(self.session, tomo.zarr(), name)

        vol = mods[0].child_models()[0]
        self.session.models.add([vol])

        # ArtiaX creates a new volume object, so we need to use that one instead of the zarr model
        tomo_vol = self.session.ArtiaX.import_tomogram(vol)
        self.active_volume = tomo_vol
        self.active_volume.copick_tomo = tomo

    def switch_volume(self, index: QModelIndex):
        # Only on valid indices
        if not index.isValid():
            return

        # Only on tomograms
        item = index.internalPointer()
        if not isinstance(item, TreeTomogram):
            return

        # Only if new tomogram
        if item.is_active:
            return

        # Previous and current tomogram
        tomo = item.tomogram
        close_all = False
        if self.active_volume is not None:
            prev_tomo = self.active_volume.copick_tomo
            close_all = tomo.voxel_spacing.run != prev_tomo.voxel_spacing.run
        else:
            close_all = True

        # Close the active volume
        self.close_active_volume()

        # Store all the picks
        self.store()

        # Close all the particles if it's a different run
        if close_all:
            self.close_all()
            self._mw._picks_table.set_view(tomo.voxel_spacing.run)

        # Open the new volume
        self.load_tomo(tomo)

    def show_particles(self, index: QModelIndex):
        # Only on valid indices
        if not index.isValid():
            return

        # Only on picks
        item = index.internalPointer()
        if not isinstance(item, TablePicks):
            return

        # Store all the picks
        self.store()

        if item.picks in self.list_map:
            particles = self.list_map[item.picks]
            particles.display = not particles.display
            return
        else:
            picks = item.picks
            self.show_particles_from_picks(picks)

    def show_particles_from_picks(self, picks: CopickPicks):
        from chimerax.geometry import Place, translation

        formats = get_formats(self.session)

        root = picks.run.root
        name = picks.pickable_object_name
        pick_obj = root.get_object(name)

        data = formats["Copick Picks file"].particle_data(self.session, file_name=None, oripix=1, trapix=1)
        partlist = ParticleList(name, self.session, data)
        self.list_map[picks] = partlist

        points = picks.points if picks.points is not None else []
        for p in points:
            origin = translation((p.location.x, p.location.y, p.location.z))
            transl = translation((0, 0, 0))
            rotation = Place(matrix=p.transformation[0:3, :])
            partlist.new_particle(origin, transl, rotation)

        partlist.radius = 40
        partlist.selected = False

        volume = None
        if pick_obj is not None:
            partlist.color = np.array(pick_obj.color)

            model, msg = open_ome_zarr_from_store(self.session, pick_obj.zarr(), name)
            model = model[0]
            volume = model.child_models()[0]

        self.session.ArtiaX.add_particlelist(partlist)

        if pick_obj.radius is not None:
            partlist.radius = pick_obj.radius

        if volume is not None:
            reg = volume.region
            reg = (reg[0], reg[1], (1, 1, 1))
            volume.region = reg
            partlist.attach_display_model(volume)
            if pick_obj.map_threshold is not None:
                partlist.surface_level = pick_obj.map_threshold

        if not picks.trust_orientation:
            partlist.hide_surfaces()
            partlist.show_markers()

        if picks.trust_orientation:
            partlist.hide_markers()
            partlist.hide_axes()

        if picks.from_tool:
            lock_particlelist([partlist], True, "all", True)

        run(self.session, "artiax cap true", log=False)

        if partlist.selected_particles is not None:
            partlist.selected_particles[:] = False

    def activate_particles(self, index: QModelIndex):
        # Only on valid indices
        if not index.isValid():
            return

        # Only on picks
        item = index.internalPointer()
        if not isinstance(item, TablePicks):
            return

        # Only if particle list exists
        if item.picks not in self.list_map:
            return

        self.session.ArtiaX.selected_partlist = self.list_map[item.picks]
        self.session.ArtiaX.options_partlist = self.list_map[item.picks]

    def take_particles(self, index: QModelIndex):
        # Only on valid indices
        if not index.isValid():
            return

        # Only on picks
        item = index.internalPointer()
        if not isinstance(item, TablePicks):
            return

        # Test if already present or not
        # Own user_id
        user_id = self.root.user_id if self.root.user_id is not None else "ArtiaX"

        # Requested object and run
        req_name = item.picks.pickable_object_name
        req_run = item.picks.run

        # Test if present
        cur_picks = req_run.get_picks(user_id=user_id, object_name=req_name)
        if len(cur_picks) > 0:
            np = cur_picks[0]
            np = append_no_duplicates(item.picks, np)
        else:
            np = req_run.new_picks(user_id=user_id, object_name=req_name, session_id="19")
            np.meta.trust_orientation = item.picks.trust_orientation
            np.points = deepcopy(item.picks.points)

        np.store()

        if item.picks in self.list_map:
            self.list_map[item.picks].display = False

        if np in self.list_map:
            self.list_map[np].delete()
            self.list_map.pop(np)

        self._mw._picks_table.set_view(req_run)
        self.show_particles_from_picks(np)

    def delete(self):
        self.store()
        super().delete()
