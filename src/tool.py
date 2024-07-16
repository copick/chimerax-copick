# Python
from copy import deepcopy
from sys import platform
from typing import Any, Tuple

# Copick
import copick
import numpy as np
from chimerax.artiax.ArtiaX import OPTIONS_PARTLIST_CHANGED
from chimerax.artiax.io.formats import get_formats

# ArtiaX
from chimerax.artiax.particle.ParticleList import (
    PARTLIST_CHANGED,
    ParticleList,
    lock_particlelist,
)
from chimerax.core.commands import run
from chimerax.core.models import Surface

# ChimeraX
from chimerax.core.tools import ToolInstance

# OME-Zarr
from chimerax.ome_zarr.open import open_ome_zarr_from_store
from chimerax.ui import MainToolWindow
from copick.impl.filesystem import CopickTomogramFSSpec
from copick.models import CopickLocation, CopickMesh, CopickPicks, CopickPoint, CopickSegmentation

# Qt
from Qt.QtCore import QModelIndex
from Qt.QtGui import QFont
from Qt.QtWidgets import QVBoxLayout

from .misc.colorops import palette_from_root
from .misc.meshops import ensure_mesh
from .misc.pickops import append_no_duplicates

# from .ui.pickstable import TablePicks
from .ui.EntityTable import TableMesh, TablePicks, TableSegmentation

# This tool
from .ui.main_widget import MainWidget
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
        # self.tool_window.create_child_window("ABC")
        self._build_ui()

        self.root = None
        self.picks_map = {}
        """Map picks to particle lists."""
        self.seg_map = {}
        """Map segmentations to volumes."""
        self.mesh_map = {}
        """Map meshes to surface objects."""

        # Mouse Modes
        from .mouse.mousemodes import WheelMovePlanesMode

        self.wheel_move_planes_mode = WheelMovePlanesMode(self.session)
        self.session.ui.mouse_modes.add_mode(self.wheel_move_planes_mode)
        run(self.session, "ui mousemode shift wheel 'move copick planes'")
        self.session.triggers.add_handler("app quit", self._store)

        # Info label
        self.session.triggers.add_handler("set mouse mode", self._update_mouse_info_label)
        self.session.ArtiaX.triggers.add_handler(OPTIONS_PARTLIST_CHANGED, self._update_object_info_label)
        self._show_info_label = True
        self._update_mouse_info_label()
        self._update_object_info_label()

        # Shortcuts
        from .shortcuts.shortcuts import register_shortcuts

        register_shortcuts(self.session)
        run(session, "ks")

        # Stepper
        self.stepper_list = []
        self._mw.picks_stepper(self.stepper_list)
        self._active_particle = None

        # Colors
        self.palette_command = ""

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

        self.root = copick.from_file(config_file)
        self._mw.set_root(self.root)
        self.palette_command = palette_from_root(self.root)

    def close_all(self):
        for _p, pl in self.picks_map.items():
            pl.delete()
        self.picks_map = {}
        self.update_stepper(None)

        for _s, vol in self.seg_map.items():
            vol.delete()
        self.seg_map = {}

        for _m, surf in self.mesh_map.items():
            surf.delete()
        self.mesh_map = {}

    def _store(self, *args, **kwargs):
        self.store()

    def store(self):
        for pick, pl in self.picks_map.items():
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
            self._mw._meshes_table.set_view(tomo.voxel_spacing.run)
            self._mw._segmentations_table.set_view(tomo.voxel_spacing.run)

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

        if item.entity in self.picks_map:
            particles = self.picks_map[item.entity]
            particles.display = not particles.display
            self._mw.set_entity_active(item.entity, particles.display)
            self.update_stepper(particles)
        else:
            picks = item.entity
            self.show_particles_from_picks(picks)
            self._mw.set_entity_active(picks, True)

    def show_particles_from_picks(self, picks: CopickPicks):
        from chimerax.geometry import Place, translation

        formats = get_formats(self.session)

        root = picks.run.root
        name = picks.pickable_object_name
        pick_obj = root.get_object(name)

        data = formats["Copick Picks file"].particle_data(self.session, file_name=None, oripix=1, trapix=1)
        partlist = ParticleList(name, self.session, data)
        self.picks_map[picks] = partlist

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

            if pick_obj.zarr() is not None:
                model, msg = open_ome_zarr_from_store(self.session, pick_obj.zarr(), name)
                model = model[0]
                volume = model.child_models()[0]
            else:
                volume = None

        # Have to call this now to set before OPTIONS_PARTLIST_CHANGED is triggered
        partlist.editing_locked = picks.from_tool

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

        if picks.trust_orientation and volume is None:
            partlist.show_axes()
            partlist.show_markers()

        if picks.trust_orientation and volume is not None:
            partlist.hide_markers()
            partlist.hide_axes()

        if picks.from_tool:
            lock_particlelist([partlist], True, "all", True)

        run(self.session, "artiax cap true", log=False)

        if partlist.selected_particles is not None:
            partlist.selected_particles = False

        self.update_stepper(partlist)

    def activate_particles(self, index: QModelIndex):
        # Only on valid indices
        if not index.isValid():
            return

        # Only on picks
        item = index.internalPointer()
        if not isinstance(item, TablePicks):
            return

        # Only if particle list exists
        if item.entity not in self.picks_map:
            return

        self.session.ArtiaX.selected_partlist = self.picks_map[item.entity].id
        self.session.ArtiaX.options_partlist = self.picks_map[item.entity].id

        self.update_stepper(self.picks_map[item.entity])

    def update_stepper(self, partlist: ParticleList):
        if partlist is None:
            self.stepper_list = []
            self._mw.picks_stepper(self.stepper_list)
            self._active_particle = None
            return

        self.stepper_list = list(partlist.data.particle_ids)
        self._mw.picks_stepper(self.stepper_list)
        self._active_particle = None

    def _set_active_particle(self, idx: int):
        self.active_particle = idx

    @property
    def active_particle(self):
        if self._active_particle is None:
            return None

        idx = self.stepper_list.index(self._active_particle) if self._active_particle in self.stepper_list else None

        return idx

    @active_particle.setter
    def active_particle(self, value):
        if value is None:
            self._active_particle = None
            self._mw.set_stepper_state(len(self.stepper_list), 0)
            return

        if not self.stepper_list:
            self._active_particle = None
            return

        if value < 0:
            value = 0
        if value >= len(self.stepper_list):
            value = len(self.stepper_list) - 1

        artia = self.session.ArtiaX
        ap = self.stepper_list[value]
        pl = artia.partlists.get(artia.options_partlist)

        if pl:
            try:
                pl.data[ap]
            except KeyError:
                self._active_particle = None
                self._mw.set_stepper_state(len(self.stepper_list), 0)
                return

            if pl.selected_particles is not None:
                pl.selected_particles = pl.particle_ids == ap
                pl.displayed_particles = pl.particle_ids == ap

            self._active_particle = ap
            self._mw.set_stepper_state(len(self.stepper_list), value)
            self.focus_particle()

    def next_particle(self):
        # No current list
        if not self.stepper_list:
            return

        artia = self.session.ArtiaX
        pl = artia.partlists.get(artia.options_partlist)
        if pl is None:
            return

        # Try incrementing
        next_part = 0 if self.active_particle is None else min(self.active_particle + 1, len(self.stepper_list) - 1)

        # Try to find the next particle that still exists
        if self.stepper_list[next_part] not in pl.data:
            part_found = False
            while next_part < len(self.stepper_list) - 1:
                next_part += 1
                if self.stepper_list[next_part] in pl.data:
                    part_found = True
                    break
            if not part_found:
                return

        ap = self.stepper_list[next_part]
        pl.selected_particles = pl.particle_ids == ap
        pl.displayed_particles = pl.particle_ids == ap

        self.active_particle = next_part

    def prev_particle(self):
        # No current list
        if not self.stepper_list:
            return

        artia = self.session.ArtiaX
        pl = artia.partlists.get(artia.options_partlist)
        if pl is None:
            return

        # Try incrementing
        next_part = 0 if self.active_particle is None else max(self.active_particle - 1, 0)

        # Try to find the next particle that still exists
        if self.stepper_list[next_part] not in pl.data:
            part_found = False
            while next_part > 0:
                next_part -= 1
                if self.stepper_list[next_part] in pl.data:
                    part_found = True
                    break
            if not part_found:
                return

        ap = self.stepper_list[next_part]
        pl.selected_particles = pl.particle_ids == ap
        pl.displayed_particles = pl.particle_ids == ap

        self.active_particle = next_part

    def focus_particle(self):
        artia = self.session.ArtiaX
        pl = artia.partlists.get(artia.options_partlist)
        if pl is None:
            return

        ap = self._active_particle
        if ap is None:
            return

        part = pl.data[ap]
        r = pl.radius
        vol = self.active_volume
        image_mode = vol.rendering_options.image_mode

        if image_mode == "orthoplanes":
            step = vol.region[2]
            vs = vol.data.step
            pp = (
                int(round(part["pos_x"] / vs[0])),
                int(round(part["pos_y"] / vs[1])),
                int(round(part["pos_z"] / vs[2])),
            )
            run(
                self.session,
                f"volume #{vol.id_string} colorMode l8 orthoplanes xyz positionPlanes {pp[0]},{pp[1]},{pp[2]} "
                f"imageMode orthoplanes step {step[0]},{step[1]},{step[2]}",
                log=False,
            )
        else:
            self.active_volume.normal = [0, 0, 1]
            self.active_volume.slab_position = part["pos_z"]

        run(
            self.session,
            f"view matrix camera 1,0,0,{part['pos_x']},0,1,0,{part['pos_y']},0,0,1,{part['pos_z'] + 100 * r}",
            log=False,
        )
        run(self.session, f"cofr {part['pos_x']},{part['pos_y']},{part['pos_z']}", log=False)

    def remove_particle(self):
        artia = self.session.ArtiaX
        pl = artia.partlists.get(artia.options_partlist)
        if pl is None:
            return

        ap = self._active_particle
        if ap is None:
            return

        pl.triggers.manual_block(PARTLIST_CHANGED)
        pl.delete_data([self._active_particle])
        pl.selected_particles = np.zeros((pl.size,), dtype=bool)
        pl.displayed_particles = np.zeros((pl.size,), dtype=bool)

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
        req_name = item.entity.pickable_object_name
        req_run = item.entity.run

        # Test if present
        cur_picks = req_run.get_picks(user_id=user_id, object_name=req_name)
        if len(cur_picks) > 0:
            np = cur_picks[0]
            np = append_no_duplicates(item.entity, np)
        else:
            np = req_run.new_picks(user_id=user_id, object_name=req_name, session_id="19")
            np.meta.trust_orientation = item.entity.trust_orientation
            np.points = deepcopy(item.entity.points)
            self._mw.update_picks_table()

        np.store()

        if item.entity in self.picks_map:
            self.picks_map[item.entity].display = False
            item.is_active = False

        if np in self.picks_map:
            self.picks_map[np].delete()
            self.picks_map.pop(np)

        self._mw._picks_table.set_view(req_run)
        self.show_particles_from_picks(np)
        self._mw.set_entity_active(np, True)

    ########################
    # Segmentation actions #
    ########################
    def show_segmentation(self, index: QModelIndex):
        # Only on valid indices
        if not index.isValid():
            return

        # Only on segmentations
        item = index.internalPointer()
        if not isinstance(item, TableSegmentation):
            return

        if item.entity in self.seg_map:
            volume = self.seg_map[item.entity]
            volume.display = not volume.display
            self._mw.set_entity_active(item.entity, volume.display)
        else:
            seg = item.entity
            self.show_volume_from_segmentation(seg)
            self._mw.set_entity_active(seg, True)

    def show_volume_from_segmentation(self, seg: CopickSegmentation):
        root = seg.run.root
        name = seg.name

        model, msg = open_ome_zarr_from_store(self.session, seg.zarr(), name)
        model = model[0]

        vol = model.child_models()[0]
        self.session.models.add([vol])

        # ArtiaX creates a new volume object, so we need to use that one instead of the zarr model
        seg_vol = self.session.ArtiaX.import_tomogram(vol)
        self.session.ArtiaX.options_tomogram = self.active_volume.id
        self.seg_map[seg] = seg_vol

        # Make appear as surface with correct colormap
        run(self.session, f"volume #{seg_vol.id_string} style surface", log=False)
        run(self.session, f"volume #{seg_vol.id_string} level 0.5", log=False)
        run(self.session, f"volume #{seg_vol.id_string} step 1", log=False)

        if seg.is_multilabel:
            offset = seg_vol.data.step[1] * -2.0
            run(
                self.session,
                f"color sample #{seg_vol.id_string} map #{seg_vol.id_string} palette {self.palette_command} offset {offset}",
                log=True,
            )
        else:
            obj_name = seg.name
            pick_obj = root.get_object(obj_name)
            seg_vol.color = np.array(pick_obj.color)

    ################
    # Mesh actions #
    ################
    def show_mesh(self, index: QModelIndex):
        # Only on valid indices
        if not index.isValid():
            return

        # Only on meshes
        item = index.internalPointer()
        if not isinstance(item, TableMesh):
            return

        print(self.mesh_map)
        print(item.entity)
        if item.entity in self.mesh_map:
            surf = self.mesh_map[item.entity]
            surf.display = not surf.display
            self._mw.set_entity_active(item.entity, surf.display)
        else:
            mesh = item.entity
            self.show_surf_from_mesh(mesh)
            self._mw.set_entity_active(mesh, True)

    def show_surf_from_mesh(self, mesh: CopickMesh):
        root = mesh.run.root
        obj_name = mesh.pickable_object_name

        tm_mesh = ensure_mesh(mesh.load())
        surf = Surface(obj_name, self.session)
        surf.set_geometry(
            vertices=tm_mesh.vertices.copy(),
            normals=tm_mesh.vertex_normals.copy(),
            triangles=tm_mesh.faces.astype(np.int32),
        )
        self.session.models.add([surf])
        self.mesh_map[mesh] = surf

        pick_obj = root.get_object(obj_name)
        col = np.array(pick_obj.color)
        surf.color = col

    def delete(self):
        self.store()
        super().delete()

    @property
    def show_info(self):
        return self._show_info_label

    @show_info.setter
    def show_info(self, value: bool):
        self._show_info_label = value
        self.mouse_info_label.display = value
        self.object_info_label.display = value

    @property
    def mouse_info_label(self):
        from .misc.labelops import get_label_model

        return get_label_model(self.session, "mouse_info")

    @property
    def object_info_label(self):
        from .misc.labelops import get_label_model

        return get_label_model(self.session, "object_info")

    def _update_mouse_info_label(self, name: str = None, data: Tuple[Any] = None):
        if name is None and data is None:
            mb = self.session.ui.mouse_modes.bindings
            right_mode = [b.mode for b in mb if b.button == "right" and not b.modifiers]
            mode = right_mode[0].name if right_mode else ""
            run(
                self.session,
                f"2dlabel create mouse_info text 'Press ? for help | right mouse: {mode}'"
                f" bold true xpos 0.05 ypos 0.95",
                log=False,
            )

        if name == "set mouse mode":
            button, _, mode = data
            if button == "right":
                run(
                    self.session,
                    f"2dlabel mouse_info text 'Press ? for help | right mouse: {mode.name}' visibility {self._show_info_label}",
                    log=False,
                )

    def _update_object_info_label(self, name: str = None, data: Tuple[Any] = None):
        if name is None and data is None:
            run(
                self.session,
                "2dlabel create object_info text 'Particles shown | Current Object: None | Editable: No' "
                "bold true xpos 0.05 ypos 0.02 size 14",
                log=False,
            )

        if name == OPTIONS_PARTLIST_CHANGED:
            artia = self.session.ArtiaX

            visibility = "shown" if artia.partlists.display else "hidden"

            if artia.options_partlist is not None:
                pl = artia.partlists.get(artia.options_partlist)
                obj_name = pl.name
                editable = "Yes" if not pl.editing_locked else "No"
            else:
                obj_name = "None"
                editable = "No"

            run(
                self.session,
                f"2dlabel object_info text 'Particles {visibility} | Current Object: {obj_name} | "
                f"Editable: {editable}' bold true xpos 0.05 ypos 0.02 size 14",
                log=False,
            )
