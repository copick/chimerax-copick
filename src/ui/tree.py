from typing import Union

from copick.models import (
    CopickRoot,
    CopickRun,
    CopickTomogram,
    CopickVoxelSpacing,
)


class TreeRoot:
    def __init__(self, root: CopickRoot):
        self.root = root
        self.parent = None
        self._children = None

    @property
    def children(self):
        if self._children is None:
            self._children = [TreeRun(run, self) for run in self.root.runs]

        if len(self._children) != len(self.root.runs):
            self._children = [TreeRun(run, self) for run in self.root.runs]

        return self._children

    def child(self, row) -> "TreeRun":
        return self.children[row]

    def childCount(self) -> int:
        return len(self.children)

    def childIndex(self) -> Union[int, None]:
        return None

    def data(self, column: int) -> str:
        if column == 0:
            return self.root.config.name
        elif column == 1:
            return ""

    def columnCount(self) -> int:
        return 1

    @property
    def has_children(self) -> bool:
        return len(self.children) > 0


class TreeRun:
    def __init__(self, run: CopickRun, parent: TreeRoot):
        self.run = run
        self.parent = parent
        self._children = None

    @property
    def children(self):
        # Only load children when explicitly accessed (lazy loading)
        if self._children is None:
            self._children = [TreeVoxelSpacing(voxel_spacing, self) for voxel_spacing in self.run.voxel_spacings]

        if len(self._children) != len(self.run.voxel_spacings):
            self._children = [TreeVoxelSpacing(voxel_spacing, self) for voxel_spacing in self.run.voxel_spacings]

        return self._children

    def child(self, row) -> "TreeVoxelSpacing":
        return self.children[row]

    def childCount(self) -> int:
        # For lazy loading, we need to avoid accessing .voxel_spacings unnecessarily
        # Return 1 if we haven't loaded children yet (assume there might be children)
        # This allows the tree to show expansion arrows without loading data
        if self._children is None:
            # Don't load children just to count them - return a placeholder count
            # This prevents eager loading while still showing expandable items
            return 0  # Assume there might be children - will be corrected when expanded
        return len(self._children)

    def childIndex(self) -> Union[int, None]:
        return self.run.root.runs.index(self.run)

    def data(self, column: int) -> str:
        if column == 0:
            return self.run.name
        elif column == 1:
            return ""

    def columnCount(self) -> int:
        return 1

    @property
    def has_children(self) -> bool:
        return True


class TreeVoxelSpacing:
    def __init__(self, voxel_spacing: CopickVoxelSpacing, parent: TreeRun):
        self.voxel_spacing = voxel_spacing
        self.parent = parent
        self._children = None

    @property
    def children(self):
        if self._children is None:
            self._children = [TreeTomogram(tomogram, self) for tomogram in self.voxel_spacing.tomograms]

        if len(self._children) != len(self.voxel_spacing.tomograms):
            self._children = [TreeTomogram(tomogram, self) for tomogram in self.voxel_spacing.tomograms]

        return self._children

    def child(self, row) -> "TreeTomogram":
        return self.children[row]

    def childCount(self) -> int:
        # For lazy loading, avoid accessing .tomograms unnecessarily
        if self._children is None:
            return 0  # Assume there might be children - will be corrected when expanded
        return len(self._children)

    def childIndex(self) -> Union[int, None]:
        return self.voxel_spacing.run.voxel_spacings.index(self.voxel_spacing)

    def data(self, column: int) -> str:
        if column == 0:
            return f"VS:{self.voxel_spacing.voxel_size:.3f}"
        elif column == 1:
            return ""

    def columnCount(self) -> int:
        return 1

    @property
    def has_children(self) -> bool:
        return True


class TreeTomogram:
    def __init__(self, tomogram: CopickTomogram, parent: TreeVoxelSpacing):
        self.tomogram = tomogram
        self.parent = parent
        self.is_active = False
        self.has_children = False

    def child(self, row) -> None:
        return None

    def childCount(self) -> int:
        return 0

    def childIndex(self) -> Union[int, None]:
        return self.tomogram.voxel_spacing.tomograms.index(self.tomogram)

    def data(self, column: int) -> str:
        if column == 0:
            return self.tomogram.tomo_type
        elif column == 1:
            return ""

    def columnCount(self) -> int:
        return 1
