from typing import Union

from chimerax.core.session import Session
from chimerax.label.label2d import LabelModel


def get_label_model(session: Session, name: str) -> Union[None, LabelModel]:
    for m in session.models.list():
        if isinstance(m, LabelModel) and m.name == name:
            return m

    return None
