# chimerax-copick
A collaborative cryo-ET annotation tool

## Data Spec

Shared data is organized as follows:

```
[copick_root]/
|-- copick_config.json (spec: src/io/copick_models.py:CopickConfig)
|-- ObjectMrcs/
|   |-- [mrc_path].mrc (index: src/io/copick_models.py:CopickConfig.pickable_objects.mrc_path)
|-- ExperimentRuns
    |-- [run_name]/ (index: src/io/copick_models.py:CopickPicks.runs)
    |   |-- Tomograms/
    |   |   |-- VoxelSpacing[xx.yyy] (index: src/io/copick_models.py:CopickPicks.voxel_spacings)
    |   |   |   |-- CanonicalTomogram
    |   |   |   |   |-- [run_name].zarr/
    |   |   |   |   |   |-- [subdirectories according to OME-NGFF spec at 100%, 50% and 25% scale]
    |   |   |   |-- Annotations/
    |   |   |   |   |-- [user_id]_[session_id]_[object_name].json (spec: src/io/copick_models.py:CopickPicks)
    |   |   |   |   |-- [tool_name]_[object_name].json (spec: src/io/copick_models.py:CopickPicks)
```
