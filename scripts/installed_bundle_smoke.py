"""Run from ChimeraX's Python after installing an exact release wheel."""

import importlib.metadata
import json
import platform

import chimerax.copick
from chimerax.copick import tool


packages = [
    "ChimeraX-copick",
    "ChimeraX-Core",
    "ChimeraX-OME-Zarr",
    "copick",
    "copick-shared-ui",
    "zarr",
    "numcodecs",
    "fsspec",
]
versions = {name: importlib.metadata.version(name) for name in packages}

assert chimerax.copick.bundle_api is not None
assert tool.CopickTool.help == "help:user/tools/copick.html"
print(json.dumps({"python": platform.python_version(), "packages": versions}, indent=2, sort_keys=True))
