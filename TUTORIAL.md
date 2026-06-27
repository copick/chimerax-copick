# ChimeraX-Copick Plugin Tutorial

!!! warning "Mouse Required"
    We strongly recommend using a mouse for this workflow, as **right-clicking** is essential for placing and manipulating picks.

---

## Installation

### 1. Download ChimeraX

Download and install ChimeraX from the [official website](https://www.cgl.ucsf.edu/chimerax/){ target="_blank" }

### 2. Install the Copick Plugin

1. Open ChimeraX
2. Go to **Tools > More Tools...** to open the toolshed
3. Search for `copick` in the search bar
4. Download and install the copick plugin

<!-- Screenshot: ChimeraX toolshed with "copick" search results -->

---

## Setup for Remote Data Access

!!! info "Optional Step"
    Skip this section if your data is already available on your local machine.

If your data is stored on a remote repository, establish an SSH tunnel:

```bash
ssh -L 2222:localhost:22 username@your-remote-server
```

This creates a local port forwarding from port 2222 to the remote server's port 22, allowing secure access to remote data.

---

## 1. Opening a Copick Project

To load a copick project into ChimeraX:

1. Open ChimeraX
2. In the command line at the bottom, enter:
   ```
   copick start /path/to/your/config.json
   ```
3. Press ++enter++

<!-- Screenshot: ChimeraX command line with the `copick start` command highlighted -->

The plugin will launch and display the **Copick Control Panel** on the left side of the window along with a **Run Gallery** showing thumbnail previews of all available tomograms.

<figure markdown="span">
  <!-- ![Main GUI](assets/main_gui.png){ width="100%" } -->
  <figcaption>Run Gallery showing thumbnail previews of all available tomograms. Each thumbnail displays a central slice preview with the run ID.</figcaption>
</figure>

### Understanding the Main Interface

The Copick Control Panel contains three main tabs:

<div class="center-table" markdown>

| Tab | Purpose |
|:---:|---------|
| **Picks** | Manage particle pick sets (point annotations) |
| **Meshes** | View mesh segmentations |
| **Segmentations** | View volumetric segmentations |

</div>

Below the tabs is a **Tree View** showing your project hierarchy:

```
Project Name (root)
├── Run (individual tomogram datasets)
│   ├── Voxel Spacing (e.g., 10.0 Å, 5.0 Å)
│   │   ├── denoised
│   │   └── wbp
│   └── Voxel Spacing (e.g., 5.0 Å)
└── Run 2
    └── ...
```

<!-- Screenshot (FULL): Annotated view of the Copick Control Panel -->

### Tree View Navigation Buttons

The tree view has floating buttons that appear on hover:

<div class="center-table" markdown>

| Button | Description |
|:------:|-------------|
| [3D View](javascript:void(0); "<img src='assets/hover/tree_3d_button.png'>") | Switch to 3D tomogram view |
| [Info](javascript:void(0); "<img src='assets/hover/tree_info_button.png'>") | Show detailed run information |
| [Gallery](javascript:void(0); "<img src='assets/hover/tree_gallery_button.png'>") | Return to gallery view |
| [Search](javascript:void(0); "<img src='assets/hover/tree_search_button.png'>") | Search/filter runs by name |

</div>

---

## 2. Adding an Object Type

Before you can pick particles of a specific type, you need to define **Pickable Object Types** in your configuration.

### Opening the Edit Object Types Dialog

In the Copick Control Panel, click the [Edit Object Types](javascript:void(0); "<img src='assets/hover/edit_object_types_button.png'>") button (pencil icon) at the top.

### The Edit Object Types Dialog

The dialog has two main sections:

#### Existing Object Types (Top Section)

A table showing all currently defined pickable objects:

<div class="center-table" markdown>

| Column | Description |
|--------|-------------|
| **Name** | Object identifier (e.g., "ribosome", "membrane") |
| **Type** | "Particle" or "Segmentation" |
| **Label** | Unique numeric ID |
| **Color** | Visualization color |
| **EMDB/PDB** | Database references |
| **Additional Info** | Radius, threshold, etc. |

</div>

<!-- Screenshot (FULL): Existing Object Types table with example entries -->

#### Table Management Buttons

<div class="center-table" markdown>

| Button | Action |
|:------:|--------|
| [Edit Selected](javascript:void(0); "<img src='assets/hover/edit_selected_button.png'>") | Modify the selected object |
| [Delete Selected](javascript:void(0); "<img src='assets/hover/delete_selected_button.png'>") | Remove the selected object |
| [Add New](javascript:void(0); "<img src='assets/hover/add_new_button.png'>") | Create a new object type |

</div>

### Creating a New Object Type

1. Click the [Add New](javascript:void(0); "<img src='assets/hover/add_new_button.png'>") button

2. Fill in the **Object Configuration** form:

=== "Basic Properties (Required)"

    <div class="center-table" markdown>

    | Field | Description |
    |-------|-------------|
    | [Name](javascript:void(0); "<img src='assets/hover/form_name_field.png'>") | Unique identifier (e.g., "ribosome", "atp-synthase") |
    | [Is Particle](javascript:void(0); "<img src='assets/hover/form_is_particle_field.png'>") | :material-checkbox-marked: for point picks, :material-checkbox-blank-outline: for segmentation masks |
    | [Label](javascript:void(0); "<img src='assets/hover/form_label_field.png'>") | Unique numeric identifier (auto-increments) |
    | [Color](javascript:void(0); "<img src='assets/hover/form_color_field.png'>") | Click the color box to choose visualization color |

    </div>

=== "Optional Properties"

    <div class="center-table" markdown>

    | Field | Description |
    |-------|-------------|
    | **EMDB ID** | Link to EMDB entry (e.g., EMD-1234) |
    | **PDB ID** | Link to PDB structure (e.g., 1ABC) |
    | **Identifier** | GO term or UniProt ID |
    | **Map Threshold** | Isosurface threshold for visualization |
    | **Radius (Å)** | Particle display radius in Angstroms |

    </div>

<!-- Screenshot (FULL): Complete Object Configuration form with fields filled in -->

3. Click the [Save Object](javascript:void(0); "<img src='assets/hover/save_object_button.png'>") button to add the new object type

4. The status will show a success message

5. Click **Save & Close** to apply changes to your configuration

!!! success "Changes Saved"
    Changes to object types are saved to your configuration file and persist across sessions.

---

## 3. Opening a Tomogram

=== "From the Gallery View"

    1. In the **Run Gallery**, browse available tomograms as thumbnails
    2. Click on any thumbnail to select that tomogram/run
    3. The tomogram will load into the 3D viewer

    <!-- Screenshot (FULL): Gallery view with multiple thumbnails -->

=== "From the Tree View"

    1. Expand a **Run** in the tree view by clicking the arrow :material-chevron-right:
    2. Expand a **Voxel Spacing** (e.g., "10.0")
    3. **Double-click** on a tomogram type (e.g., "wbp" or "denoised")

    <!-- Screenshot (FULL): Tree view expanded showing hierarchy -->

### The 3D Visualization Interface

Once a tomogram is loaded, ChimeraX displays:

<div class="center-table" markdown>

| Component | Location | Purpose |
|-----------|:--------:|---------|
| **Copick Control Panel** | Left | Manage picks, meshes, segmentations |
| **Tomogram View** | Center | 3D volume visualization |
| **Toolbar** | Top | Particle manipulation tools |
| **Contrast Panel** | Right | Adjust center/width for visualization |
| **Slicing Depth Panel** | Right | Navigate Z-planes |

</div>

<figure markdown="span">
  <!-- ![Opened Tomogram](assets/gui_opened_tomogram.png){ width="100%" } -->
  <figcaption>ChimeraX picking interface: Copick Control Panel (left), tomogram visualization (center), toolbar (top), and navigation panels (right).</figcaption>
</figure>

### Visualization Modes

Use keyboard shortcuts to switch display modes:

<div class="center-table" markdown>

| Shortcut | Mode | Description |
|:--------:|------|-------------|
| ++q+q++ | Tilted Slab | Single plane view (default) |
| ++e+e++ | Orthoplanes | XY, XZ, YZ planes simultaneously |
| ++x+x++ | XY View | View from Z axis |
| ++y+y++ | YZ View | View from X axis |
| ++z+z++ | XZ View | View from Y axis |

</div>

<!-- Screenshot: Side-by-side comparison of Tilted Slab vs Orthoplanes view -->

### Adjusting Contrast

Use the [Contrast](javascript:void(0); "<img src='assets/hover/contrast_slider.png'>") panel (right side) to adjust visualization:

- **Center**: Midpoint of the grayscale range
- **Width**: Contrast range

!!! tip "Invert Contrast"
    Press ++period+period++ (two periods) to quickly invert contrast for better particle visibility.

---

## 4. Creating a New Particle List

A **Particle List** (Pick Set) is a collection of particle locations for a specific object type.

### Steps to Create a New Pick Set

1. Ensure you have a tomogram open

2. In the **Picks** tab of the Copick Control Panel, click the [New](javascript:void(0); "<img src='assets/hover/new_picks_button.png'>") button (document icon) in the bottom-right corner

3. The **Create New Pick** dialog appears:

    <div class="center-table" markdown>

    | Field | Description | Default |
    |-------|-------------|---------|
    | [Object](javascript:void(0); "<img src='assets/hover/dialog_object_dropdown.png'>") | Select the particle type to pick | First in list |
    | **User ID** | Your identifier | From config or "ArtiaX" |
    | **Session ID** | Unique session identifier | "manual-1", "manual-2", etc. |

    </div>

    <!-- Screenshot (FULL): Create New Pick dialog -->

4. Select your desired **Object** from the dropdown (objects are color-coded)

5. Optionally modify the **User ID** and **Session ID**

6. Click **Create**

### What Happens Next

After creating the pick set:

- [x] A new entry appears in the **Picks** table
- [x] The mouse mode automatically switches to **"mark plane"** for picking
- [x] You can now start placing particles!

<!-- Screenshot (FULL): Picks table showing the newly created pick set highlighted -->

### Understanding the Picks Table

The Picks table displays:

<div class="center-table" markdown>

| Column | Description |
|--------|-------------|
| **User/Tool** | Who created the picks |
| **Object** | Particle type (color-coded) |
| **Session** | Session identifier |

</div>

**Table buttons** (bottom-right, on hover):

<div class="center-table" markdown>

| Button | Action |
|:------:|--------|
| [New](javascript:void(0); "<img src='assets/hover/picks_new_button.png'>") | Create new pick set |
| [Duplicate](javascript:void(0); "<img src='assets/hover/picks_duplicate_button.png'>") | Duplicate selected pick set |
| [Delete](javascript:void(0); "<img src='assets/hover/picks_delete_button.png'>") | Delete selected pick set |
| [Search](javascript:void(0); "<img src='assets/hover/picks_search_button.png'>") | Search/filter picks |
| [Settings](javascript:void(0); "<img src='assets/hover/picks_settings_button.png'>") | Duplication settings |

</div>

---

## 5. Picking Particles

### Placing Particles

With a pick set selected and mouse mode set to "mark plane":

1. **Navigate** to the region of interest using:
    - Mouse wheel to scroll through Z-planes
    - ++f+f++ shortcut for "move planes" mode

2. **Right-click** on the tomogram where you see a particle

3. The particle marker appears at the clicked location

<!-- Screenshot (FULL): Tomogram view showing particle picking -->

### Mouse Modes for Picking

<div class="center-table" markdown>

| Shortcut | Mode | Description |
|:--------:|------|-------------|
| ++a+p++ | Mark Plane | **Add** particles on current plane (default for new picks) |
| ++d+p++ | Delete Picked | **Remove** particle under cursor |
| ++s+s++ | Select | **Select** particles for batch operations |

</div>

<!-- Screenshot: Toolbar showing active mouse mode -->

### Navigating Between Particles

Use the [Stepper Widget](javascript:void(0); "<img src='assets/hover/stepper_widget.png'>") below the Picks table:

<div class="center-table" markdown>

| Control | Action |
|:-------:|--------|
| `<<` | Jump to previous particle |
| `>>` | Jump to next particle |
| Index | Shows current particle number |

</div>

**Keyboard shortcuts:**

- ++a+a++ - Previous particle
- ++d+d++ - Next particle

### Editing Particles

=== "Moving Particles"

    1. Press ++s+s++ or select "Select" mode
    2. Click on a particle to select it
    3. Use toolbar buttons:
        - [Translate Selected Particles](javascript:void(0); "<img src='assets/hover/toolbar_translate_button.png'>")
        - [Rotate Selected Particles](javascript:void(0); "<img src='assets/hover/toolbar_rotate_button.png'>")

=== "Deleting Single Particle"

    - Press ++minus+minus++ to remove the currently active particle
    - Or press ++d+p++ for "delete picked" mode, then right-click on particles

=== "Deleting Multiple Particles"

    1. Press ++s+s++ for select mode
    2. Click particles to select them (or ++s+a++ to select all)
    3. Press ++d+s++ to delete selected particles

    <!-- Screenshot: Selected particles highlighted -->

### Controlling Particle Display

<div class="center-table" markdown>

| Shortcut | Effect |
|:--------:|--------|
| ++w+w++ | Toggle particle list visibility (show/hide all) |
| ++0+0++ | Set 0% transparency (fully opaque) |
| ++5+5++ | Set 50% transparency |
| ++8+8++ | Set 80% transparency |

</div>

### Toolbar Actions

=== "View Controls"

    - [XY](javascript:void(0); "<img src='assets/hover/toolbar_xy_button.png'>") / [XZ](javascript:void(0); "<img src='assets/hover/toolbar_xz_button.png'>") / [YZ](javascript:void(0); "<img src='assets/hover/toolbar_yz_button.png'>") view buttons
    - [Clip toggle](javascript:void(0); "<img src='assets/hover/toolbar_clip_button.png'>")
    - [Invert Contrast](javascript:void(0); "<img src='assets/hover/toolbar_invert_button.png'>")

=== "Mouse Modes"

    - [Select](javascript:void(0); "<img src='assets/hover/toolbar_select_button.png'>")
    - [Rotate](javascript:void(0); "<img src='assets/hover/toolbar_rotate_mode_button.png'>")
    - [Translate](javascript:void(0); "<img src='assets/hover/toolbar_translate_mode_button.png'>")
    - [Pivot](javascript:void(0); "<img src='assets/hover/toolbar_pivot_button.png'>")

=== "Particle Display"

    - [Show/Hide Markers](javascript:void(0); "<img src='assets/hover/toolbar_markers_button.png'>")
    - [Show/Hide Axes](javascript:void(0); "<img src='assets/hover/toolbar_axes_button.png'>")
    - [Show/Hide Surfaces](javascript:void(0); "<img src='assets/hover/toolbar_surfaces_button.png'>")

=== "Visualization"

    - [Tilted Slab](javascript:void(0); "<img src='assets/hover/toolbar_slab_button.png'>")
    - [Volume Rendering](javascript:void(0); "<img src='assets/hover/toolbar_volren_button.png'>")
    - [Orthoplanes](javascript:void(0); "<img src='assets/hover/toolbar_ortho_button.png'>")
    - [Surface](javascript:void(0); "<img src='assets/hover/toolbar_surface_button.png'>")

=== "Resolution"

    - **1x** - Full resolution
    - **2x** - Faster, lower detail
    - **4x** - Fastest, lowest detail

<!-- Screenshot (FULL): Annotated toolbar with button groups labeled -->

---

## Saving Your Work

!!! success "Automatic Saving"
    **Picks are automatically saved** when you:

    - Switch to a different tomogram
    - Close the Copick tool
    - Exit ChimeraX

The picks are stored in the overlay directory specified in your copick configuration.

---

## Quick Reference: Keyboard Shortcuts

!!! tip "Show All Shortcuts"
    Press ++question++ to display all shortcuts in the ChimeraX log window.

### Particles

<div class="center-table" markdown>

| Shortcut | Action |
|:--------:|--------|
| ++w+w++ | Toggle particle display |
| ++a+a++ | Previous particle |
| ++d+d++ | Next particle |
| ++s+a++ | Select all particles |
| ++minus+minus++ | Remove active particle |

</div>

### Picking

<div class="center-table" markdown>

| Shortcut | Action |
|:--------:|--------|
| ++a+p++ | Add on plane mode |
| ++d+p++ | Delete picked mode |
| ++s+s++ | Select mode |
| ++d+s++ | Delete selected particles |

</div>

### Visualization

<div class="center-table" markdown>

| Shortcut | Action |
|:--------:|--------|
| ++q+q++ | Single plane (slab) |
| ++e+e++ | Orthoplanes |
| ++x+x++ | XY view |
| ++y+y++ | YZ view |
| ++z+z++ | XZ view |
| ++c+c++ | Toggle clipping |
| ++f+f++ | Move planes mode |
| ++r+r++ | Rotate slab mode |
| ++period+period++ | Invert contrast |

</div>

### Transparency

<div class="center-table" markdown>

| Shortcut | Action |
|:--------:|--------|
| ++0+0++ | 0% transparency (opaque) |
| ++5+5++ | 50% transparency |
| ++8+8++ | 80% transparency |

</div>

### Info

<div class="center-table" markdown>

| Shortcut | Action |
|:--------:|--------|
| ++i+l++ | Toggle info label |
| ++question++ | Show all shortcuts |

</div>

<!-- Screenshot (FULL): ChimeraX log window showing the keyboard shortcuts table -->

---

## Troubleshooting

??? question "Picks aren't appearing"
    - Ensure a pick set is selected in the Picks table
    - Check that mouse mode is set to "mark plane" (++a+p++)
    - Verify you're **right-clicking**, not left-clicking

??? question "Can't see particles"
    - Press ++w+w++ to toggle visibility
    - Adjust transparency with ++0+0++, ++5+5++, or ++8+8++

??? question "Keyboard shortcuts not working"
    Run `cks` in the ChimeraX command line to enable Copick keyboard shortcuts:
    ```
    cks
    ```

??? question "Tomogram not loading"
    - Check that your config file path is correct
    - Verify the data files exist at the paths specified in the config
    - For remote data, ensure your SSH tunnel is active

---

## Screenshot Checklist

!!! abstract "For Documentation Maintainers"
    Complete list of screenshots needed for this tutorial.

### Full Interface Screenshots

1. ChimeraX toolshed with "copick" search results
2. Main GUI after loading project (Run Gallery + Control Panel)
3. Annotated Copick Control Panel (tabs, tree view, buttons)
4. Edit Object Types dialog - full view with existing objects
5. Object Configuration form with fields filled in
6. Gallery view with multiple thumbnails
7. Tree view expanded with tomogram selection
8. Complete 3D interface with all panels annotated
9. Side-by-side Tilted Slab vs Orthoplanes comparison
10. Create New Pick dialog with fields
11. Picks table with newly created pick set
12. Tomogram view showing particle picking action
13. Selected particles highlighted in view
14. Annotated toolbar with button groups
15. ChimeraX log window with shortcuts table

### Hover/Tooltip Screenshots

Place these in `assets/hover/` directory:

<div class="center-table" markdown>

| Filename | Description |
|----------|-------------|
| `tree_3d_button.png` | Tree view 3D button |
| `tree_info_button.png` | Tree view Info button |
| `tree_gallery_button.png` | Tree view Gallery button |
| `tree_search_button.png` | Tree view Search button |
| `edit_object_types_button.png` | Edit Object Types button |
| `edit_selected_button.png` | Edit Selected button |
| `delete_selected_button.png` | Delete Selected button |
| `add_new_button.png` | Add New button |
| `form_name_field.png` | Name form field |
| `form_is_particle_field.png` | Is Particle checkbox |
| `form_label_field.png` | Label form field |
| `form_color_field.png` | Color picker button |
| `save_object_button.png` | Save Object button |
| `contrast_slider.png` | Contrast slider panel |
| `new_picks_button.png` | New picks button |
| `dialog_object_dropdown.png` | Object dropdown in dialog |
| `picks_new_button.png` | Picks table New button |
| `picks_duplicate_button.png` | Picks table Duplicate button |
| `picks_delete_button.png` | Picks table Delete button |
| `picks_search_button.png` | Picks table Search button |
| `picks_settings_button.png` | Picks table Settings button |
| `stepper_widget.png` | Particle stepper widget |
| `toolbar_translate_button.png` | Translate particles button |
| `toolbar_rotate_button.png` | Rotate particles button |
| `toolbar_xy_button.png` | XY view button |
| `toolbar_xz_button.png` | XZ view button |
| `toolbar_yz_button.png` | YZ view button |
| `toolbar_clip_button.png` | Clip toggle button |
| `toolbar_invert_button.png` | Invert contrast button |
| `toolbar_select_button.png` | Select mode button |
| `toolbar_rotate_mode_button.png` | Rotate mode button |
| `toolbar_translate_mode_button.png` | Translate mode button |
| `toolbar_pivot_button.png` | Pivot mode button |
| `toolbar_markers_button.png` | Show/Hide Markers button |
| `toolbar_axes_button.png` | Show/Hide Axes button |
| `toolbar_surfaces_button.png` | Show/Hide Surfaces button |
| `toolbar_slab_button.png` | Tilted Slab button |
| `toolbar_volren_button.png` | Volume Rendering button |
| `toolbar_ortho_button.png` | Orthoplanes button |
| `toolbar_surface_button.png` | Surface button |

</div>