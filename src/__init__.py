# vim: set expandtab shiftwidth=4 softtabstop=4:
from .version import __version__  # noqa
from chimerax.core.toolshed import BundleAPI


class _MyAPI(BundleAPI):
    api_version = 1

    @staticmethod
    def start_tool(session, bi, ti):
        if ti.name == "Copick":
            from . import tool

            return tool.CopickTool(session, ti.name)
        if ti.name == "Copick Annotate":
            if getattr(session, "copick", None) is None:
                session.logger.warning("Start Copick first (copick start <config>).")
                return None
            from .ui.annotate_tool import get_annotate_tool

            return get_annotate_tool(session)

    @staticmethod
    def register_command(bi, ci, logger):
        logger.status(ci.name)
        # Register all Copick commands
        if "copick" in ci.name:
            from .cmd.core import register_copick

            register_copick(logger)

    @staticmethod
    def run_provider(session, name, mgr, **kw):
        if mgr == session.toolbar:
            from .toolbar.toolbar import run_provider

            run_provider(session, name)


# Create the ``bundle_api`` object that ChimeraX expects.
bundle_api = _MyAPI()
