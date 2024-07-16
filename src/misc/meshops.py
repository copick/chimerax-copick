from typing import Union

import trimesh as tm


def ensure_mesh(trimesh_object: Union[tm.Trimesh, tm.Scene]) -> Union[None, tm.Trimesh]:
    if isinstance(trimesh_object, tm.Scene):
        if len(trimesh_object.geometry) == 0:
            return None
        else:
            return tm.util.concatenate(list(trimesh_object.geometry.values()))
    elif isinstance(trimesh_object, tm.Trimesh):
        return trimesh_object
    else:
        raise ValueError("Input must be a Trimesh or Scene object")
