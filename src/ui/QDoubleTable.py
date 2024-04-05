from typing import Literal, Union

from copick.models import CopickRun
from qtpy.QtWidgets import (
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .QCoPickTableModel import QCoPickTableModel


class QDoubleTable(QWidget):
    def __init__(
        self,
        item_type: Union[Literal["picks"], Literal["meshes"], Literal["segmentations"]],
        parent=None,
    ):
        super().__init__()
        self.item_type = item_type
        self._build()
        self._connect()

    def _build(self):
        self._layout = QVBoxLayout()
        self._tool_table = QTableView()
        self._take_button = QPushButton("▼ ▼ ▼")
        self._user_table = QTableView()
        self._tool_table.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))
        self._user_table.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))

        self._layout.addWidget(self._tool_table)
        self._layout.addWidget(self._take_button)
        self._layout.addWidget(self._user_table)
        self.setLayout(self._layout)

    def _connect(self):
        pass

    def set_view(self, run: CopickRun):
        self._tool_table.setModel(QCoPickTableModel(run, self.item_type, "tool"))
        self._user_table.setModel(QCoPickTableModel(run, self.item_type, "user"))
