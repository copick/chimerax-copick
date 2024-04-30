from typing import Callable, Tuple, Union

from copick.models import (
    CopickPicks,
    CopickRun,
)


class TablePicks:
    def __init__(self, picks: CopickPicks, parent: "TableRootPicks"):
        self.picks = picks
        self.parent = parent
        self.is_active = False
        self.has_children = False

    def child(self, row) -> None:
        return None

    def childCount(self) -> int:
        return 0

    def childIndex(self) -> Union[int, None]:
        return self.parent.get_picks().index(self.picks)

    def data(self, column: int) -> str:
        if column == 0:
            return self.picks.user_id
        elif column == 1:
            return self.picks.pickable_object_name

    def color(self) -> Tuple[int, int, int, int]:
        return tuple(self.picks.color)

    def columnCount(self) -> int:
        return 2


class TableRootPicks:
    def __init__(self, run: CopickRun, get_picks: Callable):
        self.run = run
        self._children = None
        self.parent = None
        self.get_picks = get_picks
        self.is_active = False

    @property
    def children(self):
        if self._children is None:
            self._children = [TablePicks(pick, self) for pick in self.get_picks()]

        if len(self._children) != len(self.get_picks()):
            self._children = [TablePicks(pick, self) for pick in self.get_picks()]

        return self._children

    def child(self, row) -> TablePicks:
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

    def get_item(self, picks: CopickPicks) -> TablePicks:
        for child in self.children:
            if child.picks == picks:
                return child
        return None
