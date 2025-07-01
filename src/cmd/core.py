# vim: set expandtab shiftwidth=4 softtabstop=4:

# ChimeraX
from pathlib import Path
from typing import Optional, List
import json

# Copick imports
from copick.models import CopickConfig
from copick.impl.filesystem import CopickConfigFSSpec
from copick.impl.cryoet_data_portal import CopickConfigCDP
from copick import from_czcdp_datasets


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
    session, config_path: Path, root_dir: Optional[str], name: Optional[str], description: Optional[str]
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
        overlay_root="",
        overlay_fs_args={"auto_mkdir": True},
        config_type="filesystem",
    )

    # Create CopickConfigFSSpec with the root directory
    fs_config = CopickConfigFSSpec(**config.model_dump(), overlay_root=str(root_path))

    # Write configuration to file
    with open(config_path, "w") as f:
        json.dump(fs_config.model_dump(), f, indent=2)

    session.logger.info(f"Created filesystem config with root: {root_dir}")


def _create_portal_config(
    session, config_path: Path, dataset_ids: Optional[List[int]], name: Optional[str], description: Optional[str]
):
    """Create a cryoet data portal-based copick configuration"""

    if not dataset_ids:
        session.logger.error("Dataset IDs are required for portal configuration. Use dataset_ids=[10301] syntax.")
        return

    # Use config file directory as default overlay root
    overlay_root = str(config_path.parent / "copick_overlay")

    # Create CopickRootCDP using the from_czcdp_datasets API
    copick_root = from_czcdp_datasets(
        dataset_ids=dataset_ids,
        overlay_root=overlay_root,
        overlay_fs_args={"auto_mkdir": True},
        output_path=str(config_path),
    )

    session.logger.info(f"Created portal config for datasets: {dataset_ids} at {config_path}")


def register_copick(logger):
    """Register all commands with ChimeraX, and specify expected arguments."""
    from chimerax.core.commands import CmdDesc, FileNameArg, StringArg, ListOf, IntArg, register

    def register_copick_start():
        desc = CmdDesc(
            required=[("config_file", FileNameArg)],
            synopsis="Start the Copick GUI or load a new config file.",
            # url='help:user/commands/copick_start.html'
        )
        register("copick start", desc, copick_start)

    def register_copick_keyboard_shortcuts():
        desc = CmdDesc(
            optional=[("shortcut", StringArg)],
            synopsis="Start using Copick keyboard shortcuts.",
            # url='help:user/commands/copick_start.html'
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
            # url='help:user/commands/copick_new.html'
        )
        register("copick new", desc, copick_new)

    register_copick_start()
    register_copick_keyboard_shortcuts()
    register_copick_new()
