from typing import Callable, Tuple, Type, Union

from copick.models import CopickMesh, CopickPicks, CopickRun, CopickSegmentation


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
            if isinstance(self.entity, (CopickPicks, CopickMesh)):
                return self.entity.pickable_object_name
            elif isinstance(self.entity, CopickSegmentation):
                return self.entity.name

    def color(self) -> Tuple[int, ...]:
        return tuple(self.entity.color)

    def columnCount(self) -> int:
        return 2


class TablePicks(TableEntity):
    CopickClass = CopickPicks


class TableMesh(TableEntity):
    CopickClass = CopickMesh


class TableSegmentation(TableEntity):
    CopickClass = CopickSegmentation


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
        return 2

    def get_item(self, entity: Union[CopickPicks, CopickMesh, CopickSegmentation]) -> Union[None, TableEntity]:
        for child in self.children:
            if child.entity == entity:
                return child
        return None
