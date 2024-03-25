# Python
from sys import platform

# ChimeraX
from chimerax.core.tools import ToolInstance

# Qt
from Qt.QtGui import QFont

from .misc.settings import CoPickSettings

# This tool
from .ui.main_widget import MainToolWindow


class CoPickTool(ToolInstance):
    # Does this instance persist when session closes
    SESSION_ENDURING = False
    # We do save/restore in sessions
    SESSION_SAVE = True
    # Let ChimeraX know about our help page

    def __init__(self, session, tool_name):
        # Initialize base class
        super().__init__(session, tool_name)

        # Display Name
        self.display_name = "CoPick"

        # Store self in session
        session.remote_browser = self

        # Set the font
        if platform == "darwin":
            self.font = QFont("Arial", 10)
        else:
            self.font = QFont("Arial", 7)

        self.settings = CoPickSettings(session, "CoPick", version="1")
        """Settings."""

        # UI
        self.tool_window = MainToolWindow(self, close_destroys=False)
        self._build_ui()

        # Zarr plugin available?
        self.can_read_omezarr = False
        try:
            self.can_read_omezarr = True
        except Exception:
            self.can_read_omezarr = False

        # If on MAC, add the zsh profile to the path (for AWS authentication)
        # env_if_mac()
