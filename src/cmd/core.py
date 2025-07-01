# vim: set expandtab shiftwidth=4 softtabstop=4:

# ChimeraX


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


def register_copick(logger):
    """Register all commands with ChimeraX, and specify expected arguments."""
    from chimerax.core.commands import CmdDesc, FileNameArg, StringArg, register

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

    register_copick_start()
    register_copick_keyboard_shortcuts()
