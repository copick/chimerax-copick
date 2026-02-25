from chimerax.core.settings import Settings


class CoPickSettings(Settings):
    EXPLICIT_SAVE = {}

    AUTO_SAVE = {
        "zarr_level": 2,  # Preferred zarr pyramid level (0=full, 1=2x, 2=4x downsampled)
    }
