"""The "Copick Annotate" tool window: filament tracing, instance editing and instance browsing, kept out of the narrow
copick dock (tables + tree stay there at their old width).

Placement: tabbed into the right-hand group (with ArtiaX Options, Log, Models, Volume Viewer and Marker Placement) so
it gets the full height. ArtiaX runs ``ui tool show "ArtiaX Options"`` whenever the current particle list, tomogram or
geometric model changes, which raises its panel over every tab of the group. So this window watches the same ArtiaX
triggers: if it was the front tab when ArtiaX raised its panel, it raises itself back right after. If the user had
switched to another tab themselves, nothing happens. ChimeraX remembers where the user put the window.
"""

import contextlib
import time
from typing import Any, Optional

from chimerax.core.tools import ToolInstance
from chimerax.ui import MainToolWindow
from Qt.QtCore import QTimer
from Qt.QtWidgets import QTabWidget, QVBoxLayout

from .annotation_panels import FilamentPanel, InstancePanel, PicksInstancePanel
from .emoji_font import apply_emoji_font

TOOL_NAME = "Copick Annotate"
ARTIAX_OPTIONS = "ArtiaX Options"
# Tool windows to tab with, in order of preference (the right-hand group ArtiaX builds).
TAB_WITH = (ARTIAX_OPTIONS, "Log", "Models", "Volume Viewer")
# How recently the tab must have lost the front for an ArtiaX trigger to count as having covered it (seconds).
COVERED_WINDOW = 0.2


class CopickAnnotateTool(ToolInstance):
    SESSION_ENDURING = False
    SESSION_SAVE = False
    help = "help:user/tools/copick.html"

    def __init__(self, session, tool_name: str = TOOL_NAME):
        super().__init__(session, tool_name)
        self.display_name = TOOL_NAME
        self.copick = session.copick

        self.tool_window = MainToolWindow(self, close_destroys=False)
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        self.tabs = QTabWidget()
        apply_emoji_font(self.tabs)
        self.filament_panel = FilamentPanel(self.copick)
        self.instance_panel = InstancePanel(self.copick)
        self.picks_panel = PicksInstancePanel(self.copick)
        self.tabs.addTab(self.filament_panel, "Filaments")
        self.tabs.addTab(self.instance_panel, "Instances")
        self.tabs.addTab(self.picks_panel, "Pick instances")
        layout.addWidget(self.tabs)
        self.tool_window.ui_area.setLayout(layout)

        # Tabbed with the right-hand group for the full height (ChimeraX restores a position the user chose instead).
        target = self._tab_target()
        self.tool_window.manage(target if target is not None else "right")

        # Track whether this tab is in front, to undo ArtiaX raising its panel over it.
        self._front = False
        self._lost_front_at = float("-inf")
        dock = self._dock()
        if dock is not None:
            dock.visibilityChanged.connect(self._on_visibility_changed)

        self._handlers = []
        artiax = getattr(session, "ArtiaX", None)
        if artiax is not None:
            from chimerax.artiax.ArtiaX import OPTIONS_PARTLIST_CHANGED

            names = [OPTIONS_PARTLIST_CHANGED]
            try:
                from chimerax.artiax.ArtiaX import OPTIONS_GEOMODEL_CHANGED, OPTIONS_TOMO_CHANGED

                names += [OPTIONS_TOMO_CHANGED, OPTIONS_GEOMODEL_CHANGED]
            except ImportError:
                pass
            self._handlers = [
                (artiax.triggers, artiax.triggers.add_handler(n, self._after_artiax_raise)) for n in names
            ]

    def _tab_target(self):
        """The tool window to tab with: the first docked one of TAB_WITH that is shown."""
        by_name = {getattr(t, "display_name", None): t for t in self.session.tools.list()}
        for name in TAB_WITH:
            tool = by_name.get(name)
            tw = getattr(tool, "tool_window", None)
            dock = getattr(tw, "_dock_widget", None) if tw is not None else None
            if tw is not None and tw.shown and dock is not None and not dock.isFloating():
                return tw
        return None

    # -- pages -----------------------------------------------------------------------------------------------------

    def show_page(self, page: str, raise_window: bool = True) -> None:
        """Show the window on ``"filaments"``, ``"instances"`` or ``"picks"``."""
        widget = {"filaments": self.filament_panel, "instances": self.instance_panel, "picks": self.picks_panel}[page]
        self.tabs.setCurrentWidget(widget)
        if not self.tool_window.shown:
            self.tool_window.shown = True
        if raise_window:
            self._raise()

    # -- living next to ArtiaX -------------------------------------------------------------------------------------

    def _dock(self):
        return getattr(self.tool_window, "_dock_widget", None)

    def _artiax_dock(self):
        for t in self.session.tools.list():
            if getattr(t, "display_name", None) == ARTIAX_OPTIONS and getattr(t, "tool_window", None) is not None:
                return getattr(t.tool_window, "_dock_widget", None)
        return None

    def tabbed_with_artiax(self) -> bool:
        dock, other = self._dock(), self._artiax_dock()
        if dock is None or other is None:
            return False
        return other in self.session.ui.main_window.tabifiedDockWidgets(dock)

    def _raise(self) -> None:
        dock = self._dock()
        if dock is not None:
            dock.raise_()

    def _on_visibility_changed(self, visible: bool) -> None:
        if not visible and self._front:
            self._lost_front_at = time.monotonic()
        self._front = bool(visible)

    def _after_artiax_raise(self, *_args) -> None:
        """ArtiaX just raised its options panel. If this tab was in front a moment ago (Qt may report the switch
        before or after this handler runs), raise it again once ArtiaX is done."""
        if not self.tool_window.shown or not self.tabbed_with_artiax():
            return
        covered_now = time.monotonic() - self._lost_front_at < COVERED_WINDOW
        if self._front or covered_now:
            QTimer.singleShot(0, self._raise)

    def delete(self) -> None:
        for triggers, handler in self._handlers:
            with contextlib.suppress(Exception):  # the ArtiaX model may already be gone
                triggers.remove_handler(handler)
        self._handlers = []
        for panel in (self.filament_panel, self.instance_panel):
            listeners = panel.ctl.listeners
            if panel.refresh in listeners:
                listeners.remove(panel.refresh)
        selection_listeners = self.filament_panel.ctl.selection_listeners
        if self.filament_panel._on_scene_selection in selection_listeners:
            selection_listeners.remove(self.filament_panel._on_scene_selection)
        if getattr(self.copick, "_annotate", None) is self:
            self.copick._annotate = None
        super().delete()


def get_annotate_tool(session, create: bool = True) -> Optional[CopickAnnotateTool]:
    """The Copick Annotate window of the running copick tool (created on demand)."""
    tool: Any = getattr(session, "copick", None)
    if tool is None:
        return None
    current = getattr(tool, "_annotate", None)
    if current is not None and not getattr(current, "deleted", False):
        return current
    if not create:
        return None
    tool._annotate = CopickAnnotateTool(session)
    return tool._annotate
