# vim: set expandtab shiftwidth=4 softtabstop=4:

# ChimeraX
import json
from pathlib import Path
from typing import List, Optional

from copick import from_czcdp_datasets
from copick.impl.filesystem import CopickConfigFSSpec

# Copick imports
from copick.models import CopickConfig
from copick.util.uri import resolve_copick_objects


def get_singleton(session, create=True):
    if not session.ui.is_gui:
        return None

    from chimerax.artiax.cmd import get_singleton
    from chimerax.core import tools

    from ..tool import CopickTool

    a = get_singleton(session)
    a.tool_window.shown = False

    t = tools.get_singleton(session, CopickTool, "copick", create=create)
    return t


def copick_start(session, config_file: str):
    """Start Copick UI."""
    if not session.ui.is_gui:
        session.logger.warning("Copick requires Chimerax GUI.")

    copick = get_singleton(session, create=True)
    copick.from_config_file(config_file)


def cks(session, shortcut=None):
    """
    Enable copick keyboard shortcuts.  Keys typed in the graphics window will be interpreted as shortcuts.

    Parameters
    ----------
    shortcut : string
      Keyboard shortcut to execute.  If no shortcut is specified switch to shortcut input mode.
    """

    from ..shortcuts.shortcuts import copick_keyboard_shortcuts

    ks = copick_keyboard_shortcuts(session)
    if shortcut is None:
        ks.enable_shortcuts()
    else:
        ks.try_shortcut(shortcut)


def copick_new(
    session,
    config_file: str,
    config_type: str = "filesystem",
    dataset_ids: Optional[List[int]] = None,
    root_dir: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
):
    """Create a new copick configuration file.

    Parameters
    ----------
    config_file : str
        Path where the new configuration file should be saved
    config_type : str
        Type of configuration to create: 'filesystem' or 'portal'
    dataset_ids : List[int], optional
        Dataset IDs for cryoet data portal configuration
    root_dir : str, optional
        Root directory path for filesystem configuration
    name : str, optional
        Name for the copick project
    description : str, optional
        Description for the copick project
    """

    config_path = Path(config_file)

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_type.lower() == "filesystem":
        _create_filesystem_config(session, config_path, root_dir, name, description)
    elif config_type.lower() == "portal":
        _create_portal_config(session, config_path, dataset_ids, name, description)
    else:
        session.logger.error(f"Unknown config type: {config_type}. Use 'filesystem' or 'portal'.")
        return

    session.logger.info(f"Successfully created copick configuration: {config_file}")

    # Automatically load the newly created configuration
    if session.ui.is_gui:
        copick = get_singleton(session, create=True)
        copick.from_config_file(str(config_path))
        session.logger.info(f"Loaded copick project: {config_file}")
    else:
        session.logger.warning("Cannot auto-load project - ChimeraX GUI required.")


def _create_filesystem_config(
    session,
    config_path: Path,
    root_dir: Optional[str],
    name: Optional[str],
    description: Optional[str],
):
    """Create a filesystem-based copick configuration"""

    # Use config file directory as default root if not specified
    if root_dir is None:
        root_dir = str(config_path.parent / "copick_data")

    # Ensure root directory exists
    root_path = Path(root_dir)
    root_path.mkdir(parents=True, exist_ok=True)

    # Create basic CopickConfig
    config = CopickConfig(
        name=name or config_path.stem,
        description=description or f"Copick project created from {config_path.name}",
        version="1.6.0",
        pickable_objects=[],
        config_type="filesystem",
    )

    # Create CopickConfigFSSpec with the root directory
    fs_config = CopickConfigFSSpec(
        **config.model_dump(),
        overlay_root=str(root_path),
        overlay_fs_args={"auto_mkdir": True},
    )

    # Write configuration to file
    with open(config_path, "w") as f:
        json.dump(fs_config.model_dump(), f, indent=2)

    session.logger.info(f"Created filesystem config with root: {root_dir}")


def _create_portal_config(
    session,
    config_path: Path,
    dataset_ids: Optional[List[int]],
    name: Optional[str],
    description: Optional[str],
):
    """Create a cryoet data portal-based copick configuration"""

    if not dataset_ids:
        session.logger.error("Dataset IDs are required for portal configuration. Use dataset_ids=[10301] syntax.")
        return

    # Use config file directory as default overlay root
    overlay_root = str(config_path.parent / "copick_overlay")

    # Create CopickRootCDP using the from_czcdp_datasets API
    from_czcdp_datasets(
        dataset_ids=dataset_ids,
        overlay_root=overlay_root,
        overlay_fs_args={"auto_mkdir": True},
        output_path=str(config_path),
    )

    session.logger.info(f"Created portal config for datasets: {dataset_ids} at {config_path}")


# ============================================================================
# Scripting commands for UI actions (open/show/hide entities, new picks, reload)
# ============================================================================


def _get_running_tool(session):
    """Return the running CopickTool with a loaded project, or None (with a warning)."""
    tool = getattr(session, "copick", None)
    if tool is None or tool.root is None:
        session.logger.warning("Copick is not running. Run 'copick start <config>' first.")
        return None
    return tool


def _find_tool_window(session, name):
    """Return (ToolInstance, ToolWindow) for the open tool matching ``name``, or raise.

    Matching mirrors ChimeraX's ``ui tool show``: casefold exact match on display_name,
    then on tool_name, then a prefix match. Returns the tool's main window (its
    MainToolWindow when available, otherwise its first window).
    """
    from chimerax.core.errors import UserError

    mw = session.ui.main_window
    t2w = mw.tool_instance_to_windows
    lc = name.casefold()
    for pred in (
        lambda ti: ti.display_name.casefold() == lc,
        lambda ti: ti.tool_name.casefold() == lc,
        lambda ti: ti.display_name.casefold().startswith(lc) or ti.tool_name.casefold().startswith(lc),
    ):
        matches = [ti for ti in t2w if pred(ti)]
        if matches:
            ti = matches[0]
            win = getattr(ti, "tool_window", None)
            if win not in t2w[ti]:
                win = t2w[ti][0]
            return ti, win
    names = ", ".join(sorted({ti.display_name for ti in t2w})) or "(none)"
    raise UserError(f'No open tool matching "{name}". Open tools: {names}')


def _active_run(session, tool):
    """Return the run of the active tomogram, or None (with a warning)."""
    if tool.active_volume is None:
        session.logger.warning("No run is open. Open a run first, e.g. 'copick open run <name>'.")
        return None
    return tool.active_volume.copick_tomo.voxel_spacing.run


def _find_tomogram_by_type(run, tomo_type: str):
    """Find a tomogram of the given type in a run, preferring the largest voxel spacing.

    The largest voxel spacing is the most downsampled (fastest to load), matching the
    gallery's default selection behavior.
    """
    matches = []
    for vs in run.voxel_spacings:
        for tomo in vs.tomograms:
            if tomo.tomo_type == tomo_type:
                matches.append(tomo)
    if not matches:
        return None
    matches.sort(key=lambda t: t.voxel_spacing.voxel_size, reverse=True)
    return matches[0]


def _next_session_id(run) -> str:
    """Generate the next available 'manual-X' session id for a run (see NewPickDialog)."""
    existing = {p.session_id.lower() for p in run.picks if p.session_id}
    counter = 1
    while f"manual-{counter}" in existing:
        counter += 1
    return f"manual-{counter}"


def _resolve_entities(session, tool, run, uri: Optional[str], object_type: str) -> List:
    """Resolve a copick URI to entities scoped to the active run (empty list on error)."""
    try:
        return resolve_copick_objects(uri or "*", tool.root, object_type, run_name=run.name)
    except ValueError as e:
        session.logger.error(f"Invalid copick URI '{uri}': {e}")
        return []


def _apply_to_entities(session, object_type: str, uri: Optional[str], method_name: str, verb: str):
    """Resolve a URI and apply a CopickTool show/hide method to each matching entity."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    run = _active_run(session, tool)
    if run is None:
        return

    entities = _resolve_entities(session, tool, run, uri, object_type)
    if not entities:
        session.logger.warning(f"No {object_type} matching '{uri or '*'}' found in run '{run.name}'.")
        return

    method = getattr(tool, method_name)
    for entity in entities:
        method(entity)

    noun = object_type if len(entities) == 1 else f"{object_type} entities"
    session.logger.info(f"{verb} {len(entities)} {noun} in run '{run.name}'.")


def copick_open_run(session, run_name: str, tomo_type: Optional[str] = None, zarr_level: Optional[int] = None):
    """Open a run's tomogram in the copick session."""
    tool = _get_running_tool(session)
    if tool is None:
        return

    crun = tool.root.get_run(run_name)
    if crun is None:
        session.logger.error(f"Run '{run_name}' not found.")
        return

    if zarr_level is not None and zarr_level not in (0, 1, 2):
        clamped = max(0, min(2, zarr_level))
        session.logger.warning(f"zarr_level {zarr_level} out of range [0, 2]; using {clamped}.")
        zarr_level = clamped

    if tomo_type:
        tomo = _find_tomogram_by_type(crun, tomo_type)
        if tomo is None:
            session.logger.error(f"No tomogram of type '{tomo_type}' in run '{run_name}'.")
            return
    else:
        tomo = tool._mw._select_best_tomogram_from_run(crun)
        if tomo is None:
            session.logger.error(f"Run '{run_name}' has no tomograms.")
            return

    tool.open_tomogram(tomo, zarr_level=zarr_level)
    session.logger.info(
        f"Opened tomogram '{tomo.tomo_type}' (voxel {tomo.voxel_spacing.voxel_size}) for run '{run_name}'.",
    )


def copick_open_picks(session, uri: Optional[str] = None):
    """Show picks in the active run matching the given copick URI (default: all)."""
    _apply_to_entities(session, "picks", uri, "_show_picks_entity", "Showed")


def copick_open_mesh(session, uri: Optional[str] = None):
    """Show meshes in the active run matching the given copick URI (default: all)."""
    _apply_to_entities(session, "mesh", uri, "_show_mesh_entity", "Showed")


def copick_open_segmentation(session, uri: Optional[str] = None):
    """Show segmentations in the active run matching the given copick URI (default: all)."""
    _apply_to_entities(session, "segmentation", uri, "_show_segmentation_entity", "Showed")


def copick_hide_picks(session, uri: Optional[str] = None):
    """Hide picks in the active run matching the given copick URI (default: all)."""
    _apply_to_entities(session, "picks", uri, "_hide_picks_entity", "Hid")


def copick_hide_mesh(session, uri: Optional[str] = None):
    """Hide meshes in the active run matching the given copick URI (default: all)."""
    _apply_to_entities(session, "mesh", uri, "_hide_mesh_entity", "Hid")


def copick_hide_segmentation(session, uri: Optional[str] = None):
    """Hide segmentations in the active run matching the given copick URI (default: all)."""
    _apply_to_entities(session, "segmentation", uri, "_hide_segmentation_entity", "Hid")


def copick_new_picks(session, object_name: str, user_id: Optional[str] = None, session_id: Optional[str] = None):
    """Create a new (empty) set of picks in the active run."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    run = _active_run(session, tool)
    if run is None:
        return

    if tool.root.get_object(object_name) is None:
        session.logger.error(
            f"Object '{object_name}' is not defined in the config. Add it via 'Edit Object Types' first.",
        )
        return

    if user_id is None:
        user_id = tool.root.user_id if tool.root.user_id is not None else "ArtiaX"
    if session_id is None:
        session_id = _next_session_id(run)

    tool.new_particles(object_name, user_id, session_id)
    session.logger.info(f"Created new picks '{object_name}:{user_id}/{session_id}' in run '{run.name}'.")


def copick_reload(session):
    """Reload the current copick session from its config file."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    tool.reload_session()


def copick_dock(session, tool_name, side=None, tab_with=None):
    """Dock any ChimeraX tool window to an edge, float it, or tab it with another tool."""
    from chimerax.core.errors import UserError
    from Qt.QtCore import Qt, QTimer

    if not session.ui.is_gui:
        raise UserError("Docking requires the ChimeraX GUI.")
    if side is None and tab_with is None:
        raise UserError("Specify a side (left/right/top/bottom/float) or 'tabWith <tool>'.")

    mw = session.ui.main_window
    ti, win = _find_tool_window(session, tool_name)
    dw = win._dock_widget

    if tab_with is not None:
        _, target = _find_tool_window(session, tab_with)
        tdw = target._dock_widget
        dw.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dw.setFloating(False)
        mw.addDockWidget(mw.dockWidgetArea(tdw), dw)
        mw.tabifyDockWidget(tdw, dw)
        QTimer.singleShot(0, dw.raise_)
        dest = f"tabbed with '{target.tool_instance.display_name}'"
    elif side == "float":
        dw.setFloating(True)
        dest = "float"
    else:
        areas = {
            "left": Qt.DockWidgetArea.LeftDockWidgetArea,
            "right": Qt.DockWidgetArea.RightDockWidgetArea,
            "top": Qt.DockWidgetArea.TopDockWidgetArea,
            "bottom": Qt.DockWidgetArea.BottomDockWidgetArea,
        }
        # Widen allowed areas so top/bottom docking sticks (default is left|right only).
        dw.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dw.setFloating(False)
        mw.addDockWidget(areas[side], dw)
        dest = side

    win.shown = True
    session.logger.info(f"[copick debug] docked '{ti.display_name}' -> {dest}")


def register_copick(logger):
    """Register all commands with ChimeraX, and specify expected arguments."""
    from chimerax.core.commands import CmdDesc, EnumOf, FileNameArg, IntArg, ListOf, StringArg, register

    def register_copick_start():
        desc = CmdDesc(
            required=[("config_file", FileNameArg)],
            synopsis="Start the Copick GUI or load a new config file.",
            url="help:user/commands/copick_start.html",
        )
        register("copick start", desc, copick_start)

    def register_copick_keyboard_shortcuts():
        desc = CmdDesc(
            optional=[("shortcut", StringArg)],
            synopsis="Start using Copick keyboard shortcuts.",
            url="help:user/commands/copick_cks.html",
        )
        register("cks", desc, cks)

    def register_copick_new():
        desc = CmdDesc(
            required=[("config_file", FileNameArg)],
            keyword=[
                ("config_type", StringArg),
                ("dataset_ids", ListOf(IntArg)),
                ("root_dir", StringArg),
                ("name", StringArg),
                ("description", StringArg),
            ],
            synopsis="Create a new copick configuration file (filesystem or cryoet data portal).",
            url="help:user/commands/copick_new.html",
        )
        register("copick new", desc, copick_new)

    entity_url = "help:user/commands/copick_open.html"

    def register_copick_open_run():
        desc = CmdDesc(
            required=[("run_name", StringArg)],
            keyword=[("tomo_type", StringArg), ("zarr_level", IntArg)],
            synopsis="Open a run's tomogram in the copick session.",
            url="help:user/commands/copick_open_run.html",
        )
        register("copick open run", desc, copick_open_run)

    def register_entity_commands():
        # open/show/hide for picks, meshes and segmentations, all addressed by copick URI.
        # 'show' is an alias of 'open' (idempotent load + show).
        def entity_uri_desc(synopsis):
            return CmdDesc(optional=[("uri", StringArg)], synopsis=synopsis, url=entity_url)

        for verb in ("open", "show"):
            register(
                f"copick {verb} picks",
                entity_uri_desc("Show picks in the active run matching a copick URI."),
                copick_open_picks,
            )
            register(
                f"copick {verb} mesh",
                entity_uri_desc("Show meshes in the active run matching a copick URI."),
                copick_open_mesh,
            )
            register(
                f"copick {verb} segmentation",
                entity_uri_desc("Show segmentations in the active run matching a copick URI."),
                copick_open_segmentation,
            )

        register(
            "copick hide picks",
            entity_uri_desc("Hide picks in the active run matching a copick URI."),
            copick_hide_picks,
        )
        register(
            "copick hide mesh",
            entity_uri_desc("Hide meshes in the active run matching a copick URI."),
            copick_hide_mesh,
        )
        register(
            "copick hide segmentation",
            entity_uri_desc("Hide segmentations in the active run matching a copick URI."),
            copick_hide_segmentation,
        )

    def register_copick_new_picks():
        desc = CmdDesc(
            required=[("object_name", StringArg)],
            keyword=[("user_id", StringArg), ("session_id", StringArg)],
            synopsis="Create a new (empty) set of picks in the active run.",
            url="help:user/commands/copick_new_picks.html",
        )
        register("copick new picks", desc, copick_new_picks)

    def register_copick_reload():
        desc = CmdDesc(
            synopsis="Reload the current copick session from its config file.",
            url="help:user/commands/copick_reload.html",
        )
        register("copick reload", desc, copick_reload)

    def register_copick_dock():
        desc = CmdDesc(
            required=[("tool_name", StringArg)],
            optional=[("side", EnumOf(["left", "right", "top", "bottom", "float"]))],
            keyword=[("tab_with", StringArg)],
            synopsis="Dock a tool window to an edge, float it, or tab it with another tool.",
            url="help:user/commands/copick_dock.html",
        )
        register("copick dock", desc, copick_dock)

    register_copick_start()
    register_copick_keyboard_shortcuts()
    register_copick_new()
    register_copick_open_run()
    register_entity_commands()
    register_copick_new_picks()
    register_copick_reload()
    register_copick_dock()
