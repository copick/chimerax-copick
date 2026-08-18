"""Native smoke collected only inside ChimeraX Daily release-gate runs."""

import pytest


pytestmark = pytest.mark.chimerax


def test_bundle_imports_inside_chimerax():
    import chimerax.copick
    from chimerax.copick import tool

    assert chimerax.copick.bundle_api is not None
    assert tool.CopickTool.help == "help:user/tools/copick.html"
