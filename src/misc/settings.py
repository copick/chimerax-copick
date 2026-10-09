from chimerax.core.settings import Settings


class CoPickSettings(Settings):
    EXPLICIT_SAVE = {}

    AUTO_SAVE = {
        "zarr_level": 2,  # Preferred zarr pyramid level (0=full, 1=2x, 2=4x downsampled)
        "max_loaded_tomograms": 4,  # Tomograms of a run kept loaded for instant switching
        "spotlight_radius": 500.0,  # Spotlight sphere radius in physical units (Å)
        "spotlight_weighted": True,  # Gaussian falloff (True) or hard sphere (False)
        "spotlight_mode": "volume",  # Render mode: surface, mesh, volume, mip
        "spotlight_features": "dark",  # Feature polarity in the data: dark or light
        "spotlight_particles": False,  # Also hide particles outside the spotlight sphere
        "filament_tube_scale": 0.5,  # Filament tube radius as a fraction of the object radius
        "filament_pick_spacing": 0.0,  # Default spacing of picks sampled along filaments (0 = object radius)
        "filament_color_by_instance": True,  # Colour filament tubes by filament ID (False: the object's colour)
        "filament_transparency": 0.0,  # Transparency of filament tubes, percent (0 = the object colour's alpha)
        "paint_radius": 50.0,  # Instance paint brush radius (Å)
        "color_picks_by_instance": False,  # Colour every particle list by instance ID (filaments always are)
    }
