from Qt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from qtpy.QtCore import Signal


class StepWidget(QWidget):
    stateChanged = Signal(int)

    def __init__(self, max: int, state: int = 0, parent=None):
        super().__init__(parent=parent)
        self._min = 0
        self._max = max
        self._state = state
        self._build()
        self._connect()

    def _build(self):
        self._layout = QHBoxLayout()

        self._bck_button = QPushButton("<<")
        self._fwd_button = QPushButton(">>")

        self._text = QLineEdit("0")
        self._text.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))
        self._text.setMaximumWidth(60)

        self._label = QLabel(f"of {self._state}")
        self._label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))

        self._layout.addWidget(self._bck_button)
        self._layout.addWidget(self._text)
        self._layout.addWidget(self._label)
        self._layout.addWidget(self._fwd_button)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))

        self.setLayout(self._layout)

    def _connect(self):
        self._bck_button.clicked.connect(self._bck)
        self._fwd_button.clicked.connect(self._fwd)
        self._text.editingFinished.connect(self._txt)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value: int):
        self._state = value
        self._update()

    def _bck(self):
        self.state = max(self._min, self._state - 1)

    def _fwd(self):
        self.state = min(self._max, self._state + 1)

    def _txt(self):
        self.state = max(self._min, min(self._max, int(self._text.text())))

    def _update(self):
        self._text.setText(str(self._state))
        self._label.setText(f"of {self._max}")
        self.stateChanged.emit(self._state)

    def set(self, max: int, state: int = 0):
        self._max = max
        self._state = state
        self._text.setText(str(self._state))
        self._label.setText(f"of {self._max}")
