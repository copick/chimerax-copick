# Python
from sys import platform

# ChimeraX
from chimerax.core.tools import ToolInstance

# OME-Zarr
from chimerax.ome_zarr.open import open_ome_zarr_from_store
from chimerax.ui import MainToolWindow

# Copick
from copick.impl.filesystem import CopickRootFSSpec, CopickTomogramFSSpec

# Qt
from Qt.QtCore import QModelIndex
from Qt.QtGui import QFont
from Qt.QtWidgets import QVBoxLayout

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
        self._build_ui()

        self.root = None

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

        # Find the first run that has a tomogram
        tomo = None

        for run in self.root.runs:
            for vs in run.voxel_spacings:
                if vs.tomograms:
                    tomo = vs.tomograms[0]
                    break

        self._mw._picks_list.set_view(tomo.voxel_spacing.run)

    def close_all(self):
        pass

    def store(self):
        pass

    def close_active_volume(self):
        # Close the active volume
        if self.active_volume and not self.active_volume.deleted:
            self.active_volume.delete()

    def load_tomo(self, tomo: CopickTomogramFSSpec):
        """Load a tomogram from the copick backend system."""
        name = f"{tomo.voxel_spacing.run.name} - {tomo.voxel_spacing.voxel_size}"
        mods, msg = open_ome_zarr_from_store(self.session, tomo.zarr(), name)

        self.active_volume = mods[0]
        self.session.models.add([self.active_volume])

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

        # Close the active volume
        self.close_active_volume()

        # Store all the picks
        self.store()

        # Open the new volume
        tomo = item.tomogram

        self.load_tomo(tomo)
