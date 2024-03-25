from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel


class PickableObject(BaseModel):
    name: str
    mrc_path: str


class CopickConfig(BaseModel):
    name: Optional[str] = "CoPick"
    description: Optional[str] = "Let's CoPick!"
    version: Optional[str] = 1.0

    pickable_objects: Dict[str, PickableObject]

    runs: List[str]
    voxel_spacings: List[float]

    available_pre_picks = Dict[str, List[str]]  # run_name: List of pre-pick tool names


class CopickLocation(BaseModel):
    x: float
    y: float
    z: float
    unit: Optional[str] = "angstrom"


class CopickPoint(BaseModel):
    location: CopickLocation
    orientation: Optional[np.ndarray] = np.array(
        [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
    )
    instance_id: Optional[int] = 0
    score: Optional[float] = 1.0


class CopickPicks(BaseModel):
    pickable_object_name: str  # Name from CopickConfig.pickable_objects.keys()

    # If user generated picks:
    # Unique identifier for the user
    user_id: Optional[str]
    # Unique identifier for the pick session (prevent race if they run multiple instances of napari, Chimerax, etc)
    session_id: Optional[str]

    # If tool generated picks:
    # Name of the tool that generated the picks
    tool_name: Optional[str]

    run_name: str
    voxel_spacing: float

    Points: List[CopickPoint]
