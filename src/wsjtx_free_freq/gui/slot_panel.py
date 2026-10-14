"""One slot under the header: its title, a 2x5 grid of free location buttons, or the empty state."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from wsjtx_free_freq.engine import MAX_FREE_LOCATIONS, Slot, SlotView
from wsjtx_free_freq.gui.themes import FREE_LOCATION_OBJECT
from wsjtx_free_freq.labels import NO_FREE_LOCATIONS, format_free_location, format_slot_title, format_unsupported_mode

GRID_COLUMNS = 5


class SlotPanel(QFrame):
    """Shows one slot of the first instance. Buttons are created once and shown or hidden on each update."""

    location_chosen = pyqtSignal(int)  # audio offset in Hz of the free location whose button was clicked

    def __init__(self, slot: Slot, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slot = slot
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        self.title = QLabel()
        font = self.title.font()
        font.setPointSizeF(font.pointSizeF() * 1.25)
        font.setBold(True)
        self.title.setFont(font)
        layout.addWidget(self.title)
        grid = QGridLayout()
        self.buttons: list[QPushButton] = []
        self._offsets: list[int] = []
        for n in range(MAX_FREE_LOCATIONS):
            button = QPushButton()
            button.setObjectName(FREE_LOCATION_OBJECT)
            button.hide()
            button.clicked.connect(lambda _checked=False, n=n: self.location_chosen.emit(self._offsets[n]))
            grid.addWidget(button, n // GRID_COLUMNS, n % GRID_COLUMNS)
            self.buttons.append(button)
        layout.addLayout(grid)
        self.empty = QLabel(NO_FREE_LOCATIONS)
        layout.addWidget(self.empty)
        self.unsupported = QLabel()
        layout.addWidget(self.unsupported)

    def show_slot(self, view: SlotView, window_cycles: int, unsupported: str | None = None) -> None:
        """Redraw from `view`: one button per free location, or the empty state when there are none.

        `unsupported` is the instance's mode when the engine does not support it; the message is shown, and the engine
        gives such a slot no free locations.
        """
        self.title.setText(format_slot_title(self._slot, view.decode_count, window_cycles))
        self.unsupported.setText("" if unsupported is None else format_unsupported_mode(unsupported))
        self.unsupported.setVisible(unsupported is not None)
        self._offsets = [loc.offset_hz for loc in view.free]
        for n, button in enumerate(self.buttons):
            if n < len(view.free):
                loc = view.free[n]
                button.setText(format_free_location(loc.rank, loc.offset_hz, loc.gap_hz))
                button.show()
            else:
                button.hide()
        self.empty.setVisible(not view.free and unsupported is None)
