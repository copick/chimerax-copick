from typing import Union

from chimerax.core.session import Session
from chimerax.label.label2d import LabelModel


def get_label_model(session: Session, name: str) -> Union[None, LabelModel]:
    """The model of the 2D label created as ``2dlabel create <name>``, or None.

    Matched by the label's own name: ChimeraX renames a label's model to its text when the text changes, so the model
    name only matches until the first update.
    """
    for m in session.models.list():
        if isinstance(m, LabelModel) and getattr(getattr(m, "label", None), "name", m.name) == name:
            return m

    return None
