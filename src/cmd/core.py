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


def _find_tomogram_by_type(run, tomo_type: str, voxel_size: Optional[float] = None):
    """Find a tomogram of the given type in a run, preferring the largest voxel spacing.

    The largest voxel spacing is the most downsampled (fastest to load), matching the
    gallery's default selection behavior. ``voxel_size`` restricts the search to one spacing.
    """
    matches = []
    for vs in run.voxel_spacings:
        if voxel_size is not None and abs(vs.voxel_size - voxel_size) > 1e-3:
            continue
        for tomo in vs.tomograms:
            if tomo.tomo_type == tomo_type:
                matches.append(tomo)
    if not matches:
        return None
    matches.sort(key=lambda t: t.voxel_spacing.voxel_size, reverse=True)
    return matches[0]


def _next_session_id(run, entities=None) -> str:
    """Generate the next available 'manual-X' session id for a run (see NewPickDialog); ``entities`` defaults to the
    run's picks."""
    entities = run.picks if entities is None else entities
    existing = {str(p.session_id).lower() for p in entities if p.session_id}
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

    # Loading a new particle list makes it ArtiaX's current list (which the stepper follows).
    # For a bulk open, keep the list that was current before so the stepper doesn't land on
    # whichever entity happened to be processed last.
    prev_pl = tool._current_partlist() if object_type == "picks" and len(entities) > 1 else None

    method = getattr(tool, method_name)
    for entity in entities:
        method(entity)

    if prev_pl is not None and not prev_pl.deleted and prev_pl.display and tool._current_partlist() is not prev_pl:
        session.ArtiaX.selected_partlist = prev_pl.id
        session.ArtiaX.options_partlist = prev_pl.id

    noun = object_type if len(entities) == 1 else f"{object_type} entities"
    session.logger.info(f"{verb} {len(entities)} {noun} in run '{run.name}'.")


def copick_open_run(
    session,
    run_name: str,
    tomo_type: Optional[str] = None,
    voxel_size: Optional[float] = None,
    zarr_level: Optional[int] = None,
):
    """Open a run's tomogram in the copick session (switches instantly if already loaded)."""
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
        tomo = _find_tomogram_by_type(crun, tomo_type, voxel_size)
        if tomo is None:
            at = f" at voxel size {voxel_size}" if voxel_size is not None else ""
            session.logger.error(f"No tomogram of type '{tomo_type}'{at} in run '{run_name}'.")
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


def _format_tomo_key(key) -> str:
    _run, voxel_size, tomo_type = key
    return f"{tomo_type} @ {voxel_size:g} Å"


def copick_show_tomogram(session, tomogram: Optional[str] = None, voxel_size: Optional[float] = None):
    """Show a tomogram of the active run, loading it if needed.

    ``tomogram`` is a tomo type, or ``next`` (cycle through loaded tomograms) or ``back``
    (flip to the previously shown one). Without arguments the shown tomogram is reported.
    """
    tool = _get_running_tool(session)
    if tool is None:
        return

    if tomogram == "next":
        tool.show_next_tomogram()
        return
    if tomogram == "back":
        tool.show_previous_tomogram()
        return

    run = _active_run(session, tool)
    if run is None:
        return
    if tomogram is None:
        copick_list_tomograms(session)
        return

    tomo = _find_tomogram_by_type(run, tomogram, voxel_size)
    if tomo is None:
        at = f" at voxel size {voxel_size}" if voxel_size is not None else ""
        session.logger.error(f"No tomogram of type '{tomogram}'{at} in run '{run.name}'.")
        return
    tool.open_tomogram(tomo)


def copick_close_tomogram(
    session,
    tomo_type: Optional[str] = None,
    voxel_size: Optional[float] = None,
    others: bool = False,
):
    """Unload a loaded tomogram (default: the shown one), or all but the shown one."""
    tool = _get_running_tool(session)
    if tool is None:
        return

    if others:
        n = len(tool.loaded_tomograms) - 1
        tool.unload_other_tomograms()
        session.logger.info(f"Unloaded {max(n, 0)} other tomogram(s).")
        return

    if tomo_type is None:
        key = tool._key_for_volume(tool.active_volume)
        if key is None:
            session.logger.warning("No tomogram is shown.")
            return
    else:
        matches = [
            k
            for k, _v in tool.loaded_tomograms
            if k[2] == tomo_type and (voxel_size is None or abs(k[1] - voxel_size) <= 1e-3)
        ]
        if not matches:
            session.logger.warning(f"No loaded tomogram matches '{tomo_type}'.")
            return
        if len(matches) > 1:
            names = ", ".join(_format_tomo_key(k) for k in matches)
            session.logger.warning(f"Several loaded tomograms match ({names}); give voxel_size.")
            return
        key = matches[0]

    tool.unload_tomogram(key)
    session.logger.info(f"Unloaded tomogram {_format_tomo_key(key)}.")


def copick_list_tomograms(session):
    """Log the loaded tomograms of the active run; the shown one is marked."""
    tool = _get_running_tool(session)
    if tool is None:
        return

    loaded = tool.loaded_tomograms
    if not loaded:
        session.logger.info("No tomograms loaded.")
        return

    cap = tool.settings.max_loaded_tomograms
    lines = [f"Loaded tomograms ({len(loaded)}/{cap}) of run '{loaded[0][0][0]}':"]
    for key, vol in loaded:
        mark = "▶" if vol is tool.active_volume else " "
        lines.append(f"  {mark} #{vol.id_string}  {_format_tomo_key(key)}")
    session.logger.info("\n".join(lines))


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


def copick_view(session, mode):
    """Switch the main viewport between the 3D canvas, gallery and details views."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    mw = tool._mw
    {
        "3d": mw._navigate_to_3d,
        "gallery": mw._navigate_to_gallery,
        "details": mw._navigate_to_details,
    }[mode]()


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
    session.logger.info(f"Docked '{ti.display_name}' to {dest}.")


def copick_spotlight(
    session,
    state=None,
    radius=None,
    weighted=None,
    mode=None,
    features=None,
    surface_level=None,
    image_levels=None,
    particles=None,
):
    """Configure and toggle the spotlight mode (sphere of data around the active particle)."""
    tool = _get_running_tool(session)
    if tool is None:
        return

    levels = None
    if image_levels is not None:
        if len(image_levels) < 2 or len(image_levels) % 2 != 0:
            session.logger.error(
                "image_levels must be an even number of comma-separated values: "
                "value1,brightness1,value2,brightness2,...",
            )
            return
        levels = [(image_levels[i], image_levels[i + 1]) for i in range(0, len(image_levels), 2)]

    tool.spotlight.configure(
        radius=radius,
        weighted=weighted,
        mode=mode,
        features=features,
        surface_level=surface_level,
        image_levels=levels,
        particles=particles,
    )

    if state == "on":
        tool.spotlight.enable()
    elif state == "off":
        tool.spotlight.disable()
    elif state == "toggle":
        tool.spotlight.toggle()
    elif state == "report":
        tool.spotlight.report()
    elif state == "reset":
        tool.spotlight.reset()
    elif state is None and all(
        v is None for v in (radius, weighted, mode, features, surface_level, image_levels, particles)
    ):
        session.logger.info(tool.spotlight.status())


# ---------------------------------------------------------------------------------------------------------------------
# Filaments
# ---------------------------------------------------------------------------------------------------------------------


def copick_open_filaments(session, uri: Optional[str] = None):
    """Show filament sets in the active run matching the given copick URI (default: all)."""
    _apply_to_entities(session, "filaments", uri, "_show_filaments_entity", "Showed")


def copick_hide_filaments(session, uri: Optional[str] = None):
    """Hide filament sets in the active run matching the given copick URI (default: all)."""
    _apply_to_entities(session, "filaments", uri, "_hide_filaments_entity", "Hid")


def _object_or_error(session, tool, object_name: str):
    obj = tool.root.get_object(object_name)
    if obj is None:
        session.logger.error(f"Object '{object_name}' is not defined in the config. Add it via 'Edit Object Types'.")
    return obj


def copick_new_filaments(session, object_name: str, user_id: Optional[str] = None, session_id: Optional[str] = None):
    """Start tracing a new set of filaments of ``object_name`` in the active run."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    run = _active_run(session, tool)
    if run is None:
        return
    obj = _object_or_error(session, tool, object_name)
    if obj is None:
        return
    from copick_shared_ui.core.types import is_filament_object

    if not is_filament_object(obj):
        session.logger.warning(f"'{object_name}' is not declared a filament (Edit Object Types → Is Filament).")
    user_id = user_id or tool.root.user_id or "ArtiaX"
    session_id = session_id or _next_session_id(run, list(getattr(run, "filaments", [])))
    tool.new_filaments(object_name, user_id, session_id)
    session.logger.info(f"Tracing new filaments '{object_name}:{user_id}/{session_id}' (right mouse: trace).")


def _filament_controller(session):
    tool = _get_running_tool(session)
    if tool is None:
        return None
    if tool.filaments.active is None:
        session.logger.warning("No active filament set. Open one (copick open filaments) or start one.")
        return None
    return tool.filaments


def copick_filament(session, action: str, instance_id: Optional[int] = None):
    """Filament tracing actions on the active filament set."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    ctl = tool.filaments
    if action in ("on", "off", "toggle"):  # 'copick filament trace on|off|toggle'
        from ..filaments.controller import TRACE_MODE

        tracing = ctl.editing and ctl.right_mode == TRACE_MODE
        on = (not tracing) if action == "toggle" else action == "on"
        if on:
            ctl.start_tracing()
        elif tracing or action == "off":
            ctl.stop_tracing()
        return
    if _filament_controller(session) is None:
        return
    if action == "new":
        i = ctl.new_filament()
        session.logger.info(f"New filament {i}: click on the tomogram plane to add control points.")
    elif action == "select":
        if instance_id is not None:
            ctl.set_active_filament(instance_id)
    elif action == "focus":
        ctl.focus(instance_id if instance_id is not None else ctl.edit_session.active_id)
    elif action == "go":
        if instance_id is not None:
            ctl.go_to_filament(instance_id)
    elif action == "next":
        ctl.step_filament(1)
    elif action == "previous":
        ctl.step_filament(-1)
    elif action == "reverse":
        ctl.reverse(instance_id)
    elif action == "delete":
        ctl.delete_filament(instance_id)
    elif action == "convert":
        ctl.convert(instance_id)


def copick_filament_trace(session, state: str = "toggle"):
    copick_filament(session, state)


def copick_filament_join(session, ids=None, target: Optional[int] = None):
    """Join filaments end to end; default: the filaments selected in the 3D view (Ctrl-click their tubes), or else in
    the Copick Annotate window's filament list (the two are kept in step)."""
    tool = _get_running_tool(session)
    if tool is None or _filament_controller(session) is None:
        return
    if not ids:
        ids = tool.filaments.scene_selected_ids()
        annotate = tool.annotate(create=False)
        if not ids and annotate is not None:
            ids = annotate.filament_panel.browser.selected_keys()
        if target is None:
            active = tool.filaments.edit_session.active_id
            target = active if active in ids else None
    if len(ids or []) < 2:
        session.logger.warning("copick: select two or more filaments in the Copick Annotate filament list to join.")
        return
    tool.filaments.join(ids, target=target)


def copick_filament_cut(session, state: str = "toggle", at=None, instance_id: Optional[int] = None):
    """Cut mode on / off, or cut the filament nearest to the point ``at`` (Angstrom) in two."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    ctl = tool.filaments
    if at is not None:
        if _filament_controller(session) is not None:
            ctl.cut_at(at, instance_id=instance_id, tolerance=float("inf"))
        return
    from ..filaments.controller import CUT_MODE

    cutting = ctl.editing and ctl.right_mode == CUT_MODE
    on = (not cutting) if state == "toggle" else state == "on"
    if on:
        ctl.start_cutting()
    elif cutting:
        ctl.stop_tracing()


def copick_filament_style(session, color: Optional[str] = None, transparency: Optional[float] = None):
    """Colour filaments by instance ID or by their object's colour, and set their transparency (percent).

    Applies to every filament set and is remembered. Instance colours take their alpha from the object's colour, so
    the transparency is the same in both modes. Without options, reports the current style.
    """
    tool = _get_running_tool(session)
    if tool is None:
        return
    ctl = tool.filaments
    if color is not None or transparency is not None:
        ctl.set_style(color_by_instance=None if color is None else color == "instance", transparency=transparency)
    mode = "instance" if ctl.color_by_instance() else "object"
    session.logger.info(f"copick: filaments coloured by {mode}, transparency {ctl.transparency():g}%")


def copick_filament_save(
    session,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    pick_spacing: Optional[float] = None,
):
    """Save the active filament set (optionally with picks sampled every ``pick_spacing`` Angstrom)."""
    ctl = _filament_controller(session)
    if ctl is not None:
        ctl.save(user_id=user_id, session_id=session_id, pick_spacing=pick_spacing)


# ---------------------------------------------------------------------------------------------------------------------
# Instance segmentations
# ---------------------------------------------------------------------------------------------------------------------


def copick_new_segmentation(
    session,
    object_name: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """Start a new (empty) instance segmentation of ``object_name`` at the shown tomogram's voxel spacing."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    run = _active_run(session, tool)
    if run is None or _object_or_error(session, tool, object_name) is None:
        return
    user_id = user_id or tool.root.user_id or "ArtiaX"
    session_id = session_id or _next_session_id(run, list(run.segmentations))
    tool.new_segmentation(object_name, user_id, session_id)


def _ids(text: str):
    from copick_shared_ui.util.instances import parse_id_set

    return sorted(parse_id_set(text))


def copick_instance(session, action: str, ids: Optional[str] = None, into: Optional[int] = None):
    """Instance editing and browsing actions on the edited / active instance segmentation."""
    from chimerax.core.commands import run as run_command

    tool = _get_running_tool(session)
    if tool is None:
        return
    ctl = tool.segmentations
    if action in ("paint", "erase", "pick"):
        run_command(session, f"ui mousemode right '{action} copick instance'", log=False)
        return
    if action in ("show", "hide", "isolate"):
        seg = ctl.active_key
        if seg is None:
            session.logger.warning("No instance or panoptic segmentation is active.")
            return
        keys = {r.row_key for r in ctl.rows(seg)}
        chosen = set(_ids(ids or ""))
        visible = {"show": keys, "hide": keys - chosen, "isolate": chosen}[action]
        if action == "show" and chosen:
            visible = chosen | {k for k, s in ctl.models[seg].surfaces.items() if s.display}
        ctl.set_visible(seg, visible)
        return
    if not ctl.editing:
        session.logger.warning("No instance segmentation is being edited (copick instance edit <uri>).")
        return
    if action == "new":
        session.logger.info(f"Current instance ID {ctl.new_id()}")
    elif action == "id":
        ctl.set_current_id(int(ids))
    elif action == "undo":
        ctl.undo()
    elif action == "delete":
        ctl.relabel(_ids(ids or ""), 0)
    elif action == "merge":
        if into is None:
            session.logger.error("copick instance merge IDS into ID")
            return
        ctl.relabel(_ids(ids or ""), int(into))


def copick_instance_edit(session, uri: Optional[str] = None):
    """Edit an instance segmentation of the active run (matching ``uri``; loads level 0)."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    run = _active_run(session, tool)
    if run is None:
        return
    entities = [
        e for e in _resolve_entities(session, tool, run, uri, "segmentation") if getattr(e, "is_instance", False)
    ]
    if len(entities) != 1:
        session.logger.error(f"'{uri}' matches {len(entities)} instance segmentations; give a unique URI.")
        return
    seg = entities[0]
    tool.segmentations.start_editing(seg, on_ready=lambda: tool._mw.set_entity_active(seg, True))


def copick_instance_brush(session, radius: float):
    tool = _get_running_tool(session)
    if tool is not None:
        tool.segmentations.paint_radius = float(radius)
        tool.settings.paint_radius = float(radius)


def copick_instance_save(session, user_id: Optional[str] = None, session_id: Optional[str] = None):
    tool = _get_running_tool(session)
    if tool is not None:
        tool.segmentations.save(user_id=user_id, session_id=session_id)


def copick_save(session):
    """Save every edited annotation: picks, filament sets opened from an editable file, and the edited instance
    segmentation (when it was opened from an editable store)."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    tool.store()
    ctl = tool.segmentations
    edit = ctl.edit
    if edit is not None and edit.dirty:
        if edit.read_only or edit.source is None:
            session.logger.warning("copick: the edited instance segmentation is new or read-only; use 'Save…'.")
        else:
            ctl.save()
    active = tool.filaments.active
    if active is not None and active[0].dirty and (active[0].read_only or active[0].source is None):
        session.logger.warning("copick: the active filament set is new or read-only; use 'Save…'.")
    session.logger.info("copick: saved edited annotations.")


def copick_annotate(session, state: str = "show", page: Optional[str] = None):
    """Show, hide or toggle the Copick Annotate window (filament tracing, instance editing and browsing)."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    annotate = tool.annotate(create=state != "hide")
    if annotate is None:
        return
    shown = annotate.tool_window.shown
    if state == "hide" or (state == "toggle" and shown):
        annotate.tool_window.shown = False
        return
    annotate.show_page(page or _current_page(annotate))


def _current_page(annotate) -> str:
    return {0: "filaments", 1: "instances", 2: "picks"}.get(annotate.tabs.currentIndex(), "filaments")


def copick_color_picks(session, state: str = "on"):
    """Colour every loaded particle list by instance ID (on) or by object (off)."""
    tool = _get_running_tool(session)
    if tool is None:
        return
    tool.settings.color_picks_by_instance = state == "on"
    for picks in list(tool.picks_map):
        tool.set_color_picks_by_instance(picks, state == "on")


def register_copick(logger):
    """Register all commands with ChimeraX, and specify expected arguments."""
    from chimerax.core.commands import (
        BoolArg,
        CmdDesc,
        EnumOf,
        FileNameArg,
        Float3Arg,
        FloatArg,
        FloatsArg,
        IntArg,
        ListOf,
        StringArg,
        register,
    )

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
            keyword=[("tomo_type", StringArg), ("voxel_size", FloatArg), ("zarr_level", IntArg)],
            synopsis="Open a run's tomogram in the copick session.",
            url="help:user/commands/copick_open_run.html",
        )
        register("copick open run", desc, copick_open_run)

    def register_tomogram_commands():
        register(
            "copick show tomogram",
            CmdDesc(
                optional=[("tomogram", StringArg)],
                keyword=[("voxel_size", FloatArg)],
                synopsis="Show a tomogram of the active run (tomo type, 'next' or 'back'), loading it if needed.",
                url="help:user/commands/copick_tomogram.html",
            ),
            copick_show_tomogram,
        )
        register(
            "copick close tomogram",
            CmdDesc(
                optional=[("tomo_type", StringArg)],
                keyword=[("voxel_size", FloatArg), ("others", BoolArg)],
                synopsis="Unload a loaded tomogram (default: the shown one), or all others.",
                url="help:user/commands/copick_tomogram.html",
            ),
            copick_close_tomogram,
        )
        register(
            "copick list tomograms",
            CmdDesc(
                synopsis="List the loaded tomograms of the active run.",
                url="help:user/commands/copick_tomogram.html",
            ),
            copick_list_tomograms,
        )

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

    def register_copick_view():
        desc = CmdDesc(
            required=[("mode", EnumOf(["3d", "gallery", "details"]))],
            synopsis="Switch the viewport between 3D canvas, gallery and details views.",
            url="help:user/commands/copick_view.html",
        )
        register("copick view", desc, copick_view)

    def register_copick_dock():
        desc = CmdDesc(
            required=[("tool_name", StringArg)],
            optional=[("side", EnumOf(["left", "right", "top", "bottom", "float"]))],
            keyword=[("tab_with", StringArg)],
            synopsis="Dock a tool window to an edge, float it, or tab it with another tool.",
            url="help:user/commands/copick_dock.html",
        )
        register("copick dock", desc, copick_dock)

    def register_copick_spotlight():
        desc = CmdDesc(
            optional=[("state", EnumOf(["on", "off", "toggle", "report", "reset"]))],
            keyword=[
                ("radius", FloatArg),
                ("weighted", BoolArg),
                ("mode", EnumOf(["surface", "mesh", "volume", "mip"])),
                ("features", EnumOf(["dark", "light"])),
                ("surface_level", FloatArg),
                ("image_levels", FloatsArg),
                ("particles", BoolArg),
            ],
            synopsis="Show a spherical spotlight of tomogram data around the active particle.",
            url="help:user/commands/copick_spotlight.html",
        )
        register("copick spotlight", desc, copick_spotlight)

    def register_annotation_commands():
        from chimerax.core.commands import IntArg as _IntArg

        entity_url = "help:user/commands/copick_filaments.html"
        for verb in ("open", "show"):
            register(
                f"copick {verb} filaments",
                CmdDesc(
                    optional=[("uri", StringArg)],
                    synopsis="Show filament sets matching a copick URI.",
                    url=entity_url,
                ),
                copick_open_filaments,
            )
        register(
            "copick hide filaments",
            CmdDesc(
                optional=[("uri", StringArg)],
                synopsis="Hide filament sets matching a copick URI.",
                url=entity_url,
            ),
            copick_hide_filaments,
        )
        register(
            "copick new filaments",
            CmdDesc(
                required=[("object_name", StringArg)],
                keyword=[("user_id", StringArg), ("session_id", StringArg)],
                synopsis="Start tracing a new set of filaments in the active run.",
                url=entity_url,
            ),
            copick_new_filaments,
        )
        register(
            "copick filament trace",
            CmdDesc(
                optional=[("state", EnumOf(["on", "off", "toggle"]))],
                synopsis="Switch the filament trace mouse mode on or off.",
                url=entity_url,
            ),
            copick_filament_trace,
        )
        register(
            "copick filament",
            CmdDesc(
                required=[
                    (
                        "action",
                        EnumOf(["new", "select", "focus", "go", "next", "previous", "reverse", "delete", "convert"]),
                    ),
                ],
                optional=[("instance_id", _IntArg)],
                synopsis="Filament tracing actions on the active filament set.",
                url=entity_url,
            ),
            copick_filament,
        )
        register(
            "copick filament join",
            CmdDesc(
                optional=[("ids", ListOf(IntArg))],
                keyword=[("target", IntArg)],
                synopsis="Join filaments end to end (default: those selected in the 3D view or the Annotate window).",
                url=entity_url,
            ),
            copick_filament_join,
        )
        register(
            "copick filament cut",
            CmdDesc(
                optional=[("state", EnumOf(["on", "off", "toggle"]))],
                keyword=[("at", Float3Arg), ("instance_id", _IntArg)],
                synopsis="Cut mode on or off, or cut a filament in two at a point.",
                url=entity_url,
            ),
            copick_filament_cut,
        )
        register(
            "copick filament style",
            CmdDesc(
                keyword=[("color", EnumOf(["instance", "object"])), ("transparency", FloatArg)],
                synopsis="Colour filaments by instance or object, and set their transparency.",
                url=entity_url,
            ),
            copick_filament_style,
        )
        register(
            "copick filament save",
            CmdDesc(
                keyword=[("user_id", StringArg), ("session_id", StringArg), ("pick_spacing", FloatArg)],
                synopsis="Save the active filament set, optionally with sampled picks.",
                url=entity_url,
            ),
            copick_filament_save,
        )
        inst_url = "help:user/commands/copick_instance.html"
        register(
            "copick new segmentation",
            CmdDesc(
                required=[("object_name", StringArg)],
                keyword=[("user_id", StringArg), ("session_id", StringArg)],
                synopsis="Start a new instance segmentation in the active run.",
                url=inst_url,
            ),
            copick_new_segmentation,
        )
        register(
            "copick instance",
            CmdDesc(
                required=[
                    (
                        "action",
                        EnumOf(
                            [
                                "paint",
                                "erase",
                                "pick",
                                "new",
                                "id",
                                "undo",
                                "delete",
                                "merge",
                                "show",
                                "hide",
                                "isolate",
                            ],
                        ),
                    ),
                ],
                optional=[("ids", StringArg)],
                keyword=[("into", _IntArg)],
                synopsis="Instance editing and browsing actions.",
                url=inst_url,
            ),
            copick_instance,
        )
        register(
            "copick instance edit",
            CmdDesc(
                optional=[("uri", StringArg)],
                synopsis="Edit an instance segmentation of the active run.",
                url=inst_url,
            ),
            copick_instance_edit,
        )
        register(
            "copick instance brush",
            CmdDesc(required=[("radius", FloatArg)], synopsis="Set the instance paint brush radius (Å).", url=inst_url),
            copick_instance_brush,
        )
        register(
            "copick instance save",
            CmdDesc(
                keyword=[("user_id", StringArg), ("session_id", StringArg)],
                synopsis="Save the edited instance segmentation.",
                url=inst_url,
            ),
            copick_instance_save,
        )
        register(
            "copick save",
            CmdDesc(synopsis="Save all edited picks, filaments and instance segmentations.", url=inst_url),
            copick_save,
        )
        register(
            "copick annotate",
            CmdDesc(
                optional=[("state", EnumOf(["show", "hide", "toggle"]))],
                keyword=[("page", EnumOf(["filaments", "instances", "picks"]))],
                synopsis="Show or hide the Copick Annotate window.",
                url=inst_url,
            ),
            copick_annotate,
        )
        register(
            "copick colorpicks",
            CmdDesc(
                optional=[("state", EnumOf(["on", "off"]))],
                synopsis="Colour particle lists by instance ID (on) or object (off).",
                url=inst_url,
            ),
            copick_color_picks,
        )

    register_copick_start()
    register_copick_keyboard_shortcuts()
    register_annotation_commands()
    register_copick_new()
    register_copick_open_run()
    register_tomogram_commands()
    register_entity_commands()
    register_copick_new_picks()
    register_copick_reload()
    register_copick_view()
    register_copick_dock()
    register_copick_spotlight()
