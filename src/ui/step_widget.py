from typing import Optional

from Qt.QtCore import QRegularExpression, Qt
from Qt.QtGui import QRegularExpressionValidator
from Qt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from qtpy.QtCore import Signal

# Shown in the index box while no particle is active.
IDLE_TEXT = "–"


class StepWidget(QWidget):
    """Display-only stepper (``<< [k] of N >>``) for particles or filaments.

    The widget holds no stepping state of its own: the owning tool is the single authority
    and pushes the current position via :meth:`set_state`. User input is forwarded as
    requests. Positions are shown 1-based; an idle stepper (no active particle) shows
    ``– of N``.
    """

    stepRequested = Signal(int)
    """Relative step request: -1 for ``<<``, +1 for ``>>``."""
    jumpRequested = Signal(int)
    """Absolute jump request, as a 0-based index (converted from the typed 1-based number)."""

    def __init__(self, parent=None, noun: str = "particle", prev_key: str = "aa", next_key: str = "dd"):
        super().__init__(parent=parent)
        self._noun, self._prev_key, self._next_key = noun, prev_key, next_key
        self._total = 0
        self._index: Optional[int] = None
        self._build()
        self._connect()
        self.set_state(0, None, enabled=False)

    def _build(self):
        self._layout = QHBoxLayout()

        self._bck_button = QPushButton("<<")
        self._fwd_button = QPushButton(">>")
        self._bck_button.setToolTip(f"Previous {self._noun} ({self._prev_key})")
        self._fwd_button.setToolTip(f"Next {self._noun} ({self._next_key})")

        self._text = QLineEdit(IDLE_TEXT)
        self._text.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))
        self._text.setMaximumWidth(60)
        # Digits only. Range checking happens in _txt(): a ranged QIntValidator would treat
        # out-of-range input as "intermediate" and swallow editingFinished, leaving it stuck.
        self._text.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d*"), self._text))
        self._text.setToolTip(f"Type a {self._noun} number and press Enter to jump to it")

        self._label = QLabel("of 0")
        self._label.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))

        self._layout.addWidget(self._bck_button)
        self._layout.addWidget(self._text)
        self._layout.addWidget(self._label)
        self._layout.addWidget(self._fwd_button)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum))

        self.setLayout(self._layout)

    def _connect(self):
        self._bck_button.clicked.connect(lambda: self.stepRequested.emit(-1))
        self._fwd_button.clicked.connect(lambda: self.stepRequested.emit(1))
        self._text.editingFinished.connect(self._txt)

    @property
    def index(self) -> Optional[int]:
        """Currently displayed 0-based index, or ``None`` when idle."""
        return self._index

    @property
    def total(self) -> int:
        return self._total

    def _txt(self):
        text = self._text.text().strip()
        try:
            number = int(text)
        except ValueError:
            number = None

        if number is None or not (1 <= number <= self._total):
            # Invalid / out-of-range input: restore the displayed position.
            self._render()
            return

        if self._index is not None and number - 1 == self._index:
            return

        self.jumpRequested.emit(number - 1)

    def _render(self):
        self._text.setText(IDLE_TEXT if self._index is None else str(self._index + 1))
        self._label.setText(f"of {self._total}")

    def set_state(self, total: int, index: Optional[int] = None, enabled: bool = True):
        """Show ``index`` (0-based, ``None`` = idle) out of ``total``. Does not emit signals."""
        self._total = max(0, int(total))
        self._index = index if index is not None and 0 <= index < self._total else None
        self._render()

        enabled = bool(enabled) and self._total > 0
        self._bck_button.setEnabled(enabled)
        self._fwd_button.setEnabled(enabled)
        self._text.setEnabled(enabled)


class ElidedLabel(QLabel):
    """Single-line label that elides its text instead of widening its parent.

    The horizontal size policy is ``Ignored`` and the minimum width hint is 0, so a long
    list name never pins the dock's minimum width; the full text is kept as the tooltip.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFullText(text)

    def setFullText(self, text: str):
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        self._elide()

    def fullText(self) -> str:
        return self._full_text

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        width = max(0, self.width() - 4)
        super().setText(self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, width))
