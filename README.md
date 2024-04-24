# chimerax-copick
A collaborative cryo-ET annotation plugin for ChimeraX.

## Requirements

- [ChimeraX](https://www.cgl.ucsf.edu/chimerax/download.html)
- [ChimeraX-OME-Zarr](https://github.com/uermel/chimerax-ome-zarr)
- [ArtiaX](https://github.com/FrangakisLab/ArtiaX)
- [copick](https://github.com/uermel/copick)

## Data Spec

Uses the copick data model and backend to store and retrieve data.

## Example project

An example project can be obtained from [Zenodo](https://doi.org/10.5281/zenodo.11049961).

To test with the example project:
1. Download chimerax-copick from the releases page
2. Download and unpack the example project
3. Add the location to the root `sample_project` directory to the config (json-)file (`overlay_root` variable in `copick_config_filesystem.json`)
4. Install in ChimeraX using `toolshed install /PATH/TO/ChimeraX_copick-0.1.1-py3-none-any.whl`
5. Restart ChimeraX
6. Run `copick start /PATH/TO/copick_config_filesystem.json` in the ChimeraX command line.
