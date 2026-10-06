from typing import Callable, Optional, Tuple, Type, Union

import copick.models
from copick.models import CopickMesh, CopickPicks, CopickRun, CopickSegmentation
from copick_shared_ui.core.types import SEGMENTATION_TYPE_LABELS, segmentation_type_of

# copick versions without the Filaments entity have no CopickFilaments
CopickFilaments = getattr(copick.models, "CopickFilaments", None)


class TableEntity:
    CopickClass = None

    def __init__(self, entity: CopickClass, parent: "EntityTableRoot"):
        self.entity = entity
        self.parent = parent
        self.is_active = False
        self.has_children = False

    def child(self, row) -> None:
        return None

    def childCount(self) -> int:
        return 0

    def childIndex(self) -> Union[int, None]:
        return self.parent.get_entity().index(self.entity)

    def data(self, column: int) -> str:
        if column == 0:
            return self.entity.user_id
        elif column == 1:
            if isinstance(self.entity, CopickSegmentation):
                return self.entity.name
            return self.entity.pickable_object_name
        elif column == 2:
            return self.entity.session_id
        elif column == 3 and isinstance(self.entity, CopickSegmentation):
            return SEGMENTATION_TYPE_LABELS[segmentation_type_of(self.entity)]
        return None

    def kind(self) -> Optional[str]:
        """The segmentation type (binary, multilabel, instance, panoptic), or None for other entities."""
        if isinstance(self.entity, CopickSegmentation):
            return segmentation_type_of(self.entity)
        return None

    def color(self) -> Tuple[int, ...]:
        color = getattr(self.entity, "color", None)
        if color is None:  # filaments (and instance/panoptic stores) take their object's colour
            name = getattr(self.entity, "pickable_object_name", None) or getattr(self.entity, "name", "")
            obj = self.entity.run.root.get_object(name)
            color = obj.color if obj is not None and obj.color else (128, 128, 128, 255)
        return tuple(color)

    @property
    def locked(self) -> bool:
        """Tool output or read-only storage (filaments have no ``read_only`` on every backend)."""
        return bool(getattr(self.entity, "from_tool", False) or getattr(self.entity, "read_only", False))

    def columnCount(self) -> int:
        return 3


class TablePicks(TableEntity):
    CopickClass = CopickPicks


class TableMesh(TableEntity):
    CopickClass = CopickMesh


class TableSegmentation(TableEntity):
    CopickClass = CopickSegmentation

    def columnCount(self) -> int:
        return 4


class TableFilaments(TableEntity):
    CopickClass = CopickFilaments


class EntityTableRoot:
    def __init__(self, run: CopickRun, get_entity: Callable, entity_clz: Type[TableEntity]):
        self.run = run
        self._children = None
        self.parent = None
        self.get_entity = get_entity
        self.is_active = False
        self.entity_clz = entity_clz

    @property
    def children(self):
        if self._children is None:
            self._children = [self.entity_clz(pick, self) for pick in self.get_entity()]

        if len(self._children) != len(self.get_entity()):
            self._children = [self.entity_clz(pick, self) for pick in self.get_entity()]

        return self._children

    def child(self, row) -> TableEntity:
        return self.children[row]

    def childCount(self) -> int:
        return len(self.children)

    def childIndex(self) -> Union[int, None]:
        return None

    def data(self, column: int) -> str:
        if column == 0:
            return self.run.name
        elif column == 1:
            return ""

    def columnCount(self) -> int:
        return 3

    def get_item(self, entity: Union[CopickPicks, CopickMesh, CopickSegmentation]) -> Union[None, TableEntity]:
        for child in self.children:
            if child.entity == entity:
                return child
        return None
