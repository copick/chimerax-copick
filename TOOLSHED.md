**Collaborative annotation of cryo-electron tomograms, right inside ChimeraX.**

ChimeraX-copick turns ChimeraX into a full annotation environment for cryo-ET data
managed with [copick](https://copick.github.io/copick/). Browse runs in a thumbnail
gallery, load tomograms at any resolution, and create and edit particle picks, meshes,
and segmentations — all stored in a portable, shareable [copick](https://copick.github.io/copick/)
project that works equally well against local files, S3/SSH/SMB storage, or the
[CZ cryoET Data Portal](https://cryoetdataportal.czscience.com/).

Picking and 3D visualization are powered by
[ArtiaX](https://github.com/FrangakisLab/ArtiaX); volumes are streamed as multiscale
OME-Zarr so even large tomograms open quickly.

![ChimeraX-copick picking interface](https://copick.github.io/copick/assets/chimerax_tutorial/main_gui_view_tomogram.png)

### Features

- **Run gallery & tree browser** — preview every tomogram as a thumbnail, or navigate
  the project hierarchy (Run → Voxel Spacing → Tomogram) and search/filter by run name.
- **Particle picking** — create pick sets per object type, place points on planes,
  step through particles, and translate/rotate individual or selected particles.
- **Meshes & segmentations** — display surface meshes and multilabel/single-label
  voxel segmentations with project colors.
- **Flexible visualization** — tilted-slab, orthoplanes, volume rendering, and
  isosurface modes; resolution stepping (1×/2×/4×); contrast inversion.
- **Edit object types** — define pickable objects (name, color, radius, EMDB/PDB,
  GO/UniProt identifier) and save them back to your config.
- **Reads & writes copick projects** — local, cloud (S3), remote (SSH/SMB), or the
  CZ cryoET Data Portal. Annotations you create are written to a local *overlay*; portal
  data stays read-only.
- **Scriptable** — drive the viewer from the ChimeraX command line: open runs and
  show/hide picks, meshes, and segmentations by copick URI (see Commands below).
- **Automatic saving** — picks are saved when you switch tomograms, close the tool,
  or quit ChimeraX.

### Installation

Install from the ChimeraX Toolshed:

1. In ChimeraX, open **Tools → More Tools…**
2. Search for **copick** and click **Install**.
3. Restart ChimeraX if prompted.

ChimeraX-copick requires ChimeraX ≥ 1.7 and pulls in
[ArtiaX](https://github.com/FrangakisLab/ArtiaX),
[ChimeraX-OME-Zarr](https://github.com/uermel/chimerax-ome-zarr), and
[copick](https://copick.github.io/copick/) automatically.

To create or import projects from the command line (see the examples below), also
install the copick CLI in your terminal environment:

    pip install "copick[all]"

The `all` extra includes the fsspec backends copick is tested against
(`local`, `s3`, `smb`, `ssh`). Use `pip>=25.2` or [`uv pip`](https://docs.astral.sh/uv/pip/).

### Quick start

A copick project is described by a small JSON **config file**. Point ChimeraX at one
with:

    copick start /path/to/config.json

Below are two ways to get a working config in a couple of minutes — one starting from
a public Data Portal dataset (no downloads), one starting from your own `.mrc`
tomograms.

#### Option A — Start from a CZ cryoET Data Portal dataset

This builds a config that streams tomograms and existing annotations directly from the
[Data Portal](https://cryoetdataportal.czscience.com/), while writing anything *you*
create to a local overlay folder. We'll use
[dataset 10301](https://cryoetdataportal.czscience.com/datasets/10301).

In a terminal:

    # Generate a config for one (or more) portal datasets
    copick config dataportal \
        --dataset-id 10301 \
        --overlay ./overlay \
        --output config.json

Then in the ChimeraX command line:

    copick start config.json

That's it — no downloads, no JSON editing. The pickable object types are discovered
from the dataset automatically, so the tomograms **and** the existing (read-only) portal
annotations show up right away. Anything you pick yourself is written to `./overlay`.

Even faster, you can create *and* load a portal config without leaving ChimeraX:

    copick new config.json config_type portal dataset_ids 10301

#### Option B — Start from your own MRC tomograms

This creates a local project and imports `.mrc` reconstructions into it. Each tomogram
is converted to multiscale OME-Zarr so it streams efficiently in the viewer.

In a terminal:

    # 1. Create a local project config and declare the objects you'll annotate.
    #    --objects format: name,is_particle,[radius],[pdb_id]  (repeat per object)
    copick config filesystem \
        --config config.json \
        --overlay-root ./my_project \
        --objects ribosome,True,150,7P6Z \
        --objects membrane,False \
        --proj-name my-project \
        --proj-description "My cryo-ET dataset"

    # 2. Import a single tomogram (file type and voxel size are read from the MRC header).
    #    The run is named after the file (TS_001) unless you pass --run.
    copick add tomogram TS_001.mrc --config config.json --tomo-type wbp

    # 3. Or batch-import a whole folder of MRCs; the run name is taken from each filename.
    copick add tomogram "tomograms/*.mrc" --config config.json --tomo-type wbp

Then in the ChimeraX command line:

    copick start config.json

Useful `copick add tomogram` flags: `--voxel-size` (override the header), `--run` /
`--run-regex` (control run naming), `--flip` / `--transpose` (fix axis conventions).
See the [`add` CLI reference](https://copick.github.io/copick/cli/add/).

### Using the plugin

Once a project is loaded you'll see the **Annotation Panel** (Picks / Meshes /
Segmentations tabs) and the **Tomogram Panel** (run/voxel-spacing/tomogram tree), with
a thumbnail **gallery** for quickly choosing a run.

- **Open a tomogram:** click a gallery thumbnail, or double-click a tomogram in the tree.
- **Define object types:** click **✏️ Edit Object Types**.
- **Create a pick set:** in the **Picks** tab click **📄 New**, choose an object, then
  **right-click** in the tomogram to place particles (mouse mode auto-switches to
  *mark plane*).
- **Enable keyboard shortcuts:** run `cks` in the ChimeraX command line, then press
  `?` to list all shortcuts. Common ones: `q` slab, `e` orthoplanes, `w` toggle
  particles, `a`/`d` previous/next particle, `.` invert contrast.

A complete, illustrated walkthrough is in the
**[ChimeraX-copick tutorial](https://copick.github.io/copick/examples/tutorials/chimerax/)**.

### Commands

The plugin adds these commands to the ChimeraX command line. The annotation commands act
on the currently open run and address picks/meshes/segmentations by **copick URI**
(`object_name:user_id/session_id`; segmentations add `@voxel_spacing`). A URI of `*` — the
default — matches everything in the run, and glob/regex patterns match multiple entities.

Project & session:

- `copick start <config.json>` — load a project (or switch to a different config); opens the GUI.
- `copick new <config.json> [config_type filesystem|portal] [dataset_ids …] [root_dir …] [name …] [description …]` — create a config file and load it immediately.
- `copick reload` — reload the current project from its config file.
- `cks [shortcut]` — enable copick keyboard shortcuts in the graphics window.

Open a tomogram:

- `copick open run <run_name> [tomo_type …] [zarr_level 0–2]` — open a run's tomogram in the viewer.

Show, hide, and create annotations:

- `copick open picks|mesh|segmentation [uri]` — load and display matching annotations (`copick show …` is an alias of `copick open …`).
- `copick hide picks|mesh|segmentation [uri]` — hide matching annotations.
- `copick new picks <object_name> [user_id …] [session_id …]` — create a new, empty pick set in the active run.

### Documentation & links

- **copick documentation:** <https://copick.github.io/copick/>
- **Quick start:** <https://copick.github.io/copick/quickstart/>
- **ChimeraX-copick tutorial:** <https://copick.github.io/copick/examples/tutorials/chimerax/>
- **Data Portal tutorial:** <https://copick.github.io/copick/examples/tutorials/data_portal/>
- **CLI reference:** <https://copick.github.io/copick/cli/> ([`config`](https://copick.github.io/copick/cli/config/) · [`add`](https://copick.github.io/copick/cli/add/))
- **Data model:** <https://copick.github.io/copick/datamodel/>
- **copick ecosystem (napari-copick, CellCanvas, …):** <https://copick.github.io/copick/tools/>
- **CZ cryoET Data Portal:** <https://cryoetdataportal.czscience.com/>
- **Source & issues:** <https://github.com/copick/chimerax-copick>

*ChimeraX-copick is open source (MIT). Built on
[ArtiaX](https://github.com/FrangakisLab/ArtiaX) and the
[copick](https://copick.github.io/copick/) data ecosystem.*
