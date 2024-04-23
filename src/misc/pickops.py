import numpy as np
from copick.models import CopickPicks


def append_no_duplicates(inp: CopickPicks, out: CopickPicks) -> CopickPicks:
    # Special cases
    if out.points is None:
        out.points = inp.points if inp.points is not None else []
        return out

    if len(inp.points) == 0:
        return out

    if len(out.points) == 0:
        out.points = inp.points if inp.points is not None else []
        return out

    # Convert to numpy arrays
    inp_arr = np.ndarray((len(inp.points), 3))
    for idx, pt in enumerate(inp.points):
        inp_arr[idx, :] = [pt.location.x, pt.location.y, pt.location.z]

    out_arr = np.ndarray((len(out.points), 3))
    for idx, pt in enumerate(out.points):
        out_arr[idx, :] = [pt.location.x, pt.location.y, pt.location.z]

    # If not existing in out, append it
    for idx, pt in enumerate(inp_arr):
        if not np.any(np.all(np.isclose(pt, out_arr), axis=1)):
            out.points.append(inp.points[idx])

    return out
