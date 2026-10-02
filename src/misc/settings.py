from chimerax.core.settings import Settings


class CoPickSettings(Settings):
    EXPLICIT_SAVE = {}

    AUTO_SAVE = {
        "zarr_level": 2,  # Preferred zarr pyramid level (0=full, 1=2x, 2=4x downsampled)
        "spotlight_radius": 500.0,  # Spotlight sphere radius in physical units (Å)
        "spotlight_weighted": True,  # Gaussian falloff (True) or hard sphere (False)
        "spotlight_mode": "volume",  # Render mode: surface, mesh, volume, mip
        "spotlight_features": "dark",  # Feature polarity in the data: dark or light
        "spotlight_particles": False,  # Also hide particles outside the spotlight sphere
    }
