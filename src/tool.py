from sys import platform

from chimerax.core.tools import ToolInstance

# Qt
from Qt.QtGui import QFont


class CoPickTool(ToolInstance):
    # Does this instance persist when session closes
    SESSION_ENDURING = False
    # We do save/restore in sessions
    SESSION_SAVE = False
    # Let ChimeraX know about our help page
    # help = "help:user/tools/artiax.html"

    # ==============================================================================
    # Instance Initialization ======================================================
    # ==============================================================================

    def __init__(self, session, tool_name):
        # Initialize base class
        super().__init__(session, tool_name)

        # Display Name
        self.display_name = "RemoteBrowser"

        # Store self in session
        session.remote_browser = self

        # Set the font
        if platform == "darwin":
            self.font = QFont("Arial", 10)
        else:
            self.font = QFont("Arial", 7)
