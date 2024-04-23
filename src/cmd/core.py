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

    t = tools.get_singleton(session, CopickTool, "Copick", create=create)
    return t


def copick_start(session, config_file: str):
    """Start Copick UI."""
    if not session.ui.is_gui:
        session.logger.warning("Copick requires Chimerax GUI.")

    copick = get_singleton(session)
    copick.from_config_file(config_file)


def register_copick(logger):
    """Register all commands with ChimeraX, and specify expected arguments."""
    from chimerax.core.commands import CmdDesc, FileNameArg, register

    def register_copick_start():
        desc = CmdDesc(
            required=[("config_file", FileNameArg)],
            synopsis="Start the Copick GUI or load a new config file.",
            # url='help:user/commands/copick_start.html'
        )
        register("copick start", desc, copick_start)

    register_copick_start()
