from copick.models import CopickRoot


def palette_from_root(root: CopickRoot) -> str:
    com = ""
    for pickobj in root.pickable_objects:
        com += f"{pickobj.label},rgba({pickobj.color[0]},{pickobj.color[1]},{pickobj.color[2]},{pickobj.color[3]/255}):"
    return com[:-1]
