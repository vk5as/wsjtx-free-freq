"""Header bar: instance dropdown, then connection, dial frequency, mode, Rx and Tx for the selected WSJT-X instance."""

from dataclasses import dataclass

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from wsjtx_free_freq.engine import InstanceView, Snapshot
from wsjtx_free_freq.gui.formatting import MISSING, format_dial

CONNECTED_COLOUR = "#4c4"
IDLE_COLOUR = "#888"


@dataclass(frozen=True)
class _Shown:
    connected: bool
    text: str
    dial: str
    mode: str
    rx: str
    tx: str


def _hz(value: int | None) -> str:
    return MISSING if value is None else f"{value} Hz"


class HeaderBar(QFrame):
    """Shows the selected instance; its values are the labels' text. Settings asks the window to open its dialog."""

    instance_selected = pyqtSignal()  # the operator picked another instance in the dropdown
    settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
        self._selected: str | None = None
        self.instance_box = QComboBox()
        self.instance_box.currentIndexChanged.connect(self._on_choice)
        layout.addWidget(self.instance_box)
        layout.addSpacing(16)
        self.dot = QLabel("●")
        self.connection_label = QLabel()
        layout.addWidget(self.dot)
        layout.addWidget(self.connection_label)
        layout.addSpacing(16)
        self.dial_label = self._field(layout, "Dial")
        self.mode_label = self._field(layout, "Mode")
        self.rx_label = self._field(layout, "Rx")
        self.tx_label = self._field(layout, "Tx")
        layout.addStretch()
        self.settings_button = QPushButton("Settings…")
        self.settings_button.clicked.connect(self.settings_requested)
        layout.addWidget(self.settings_button)
        self.show_snapshot(Snapshot(instances=()))

    @staticmethod
    def _field(layout: QHBoxLayout, caption: str) -> QLabel:
        layout.addWidget(QLabel(caption))
        value = QLabel(MISSING)
        layout.addWidget(value)
        layout.addSpacing(10)
        return value

    @property
    def selected_id(self) -> str | None:
        """Id of the instance the header shows and Set Rx goes to; None while no instance is heard."""
        return self._selected

    def _on_choice(self, index: int) -> None:
        chosen = self.instance_box.itemText(index)
        if chosen and chosen != self._selected:
            self._selected = chosen
            self.instance_selected.emit()

    def _sync_choices(self, ids: list[str]) -> None:
        """Make the dropdown list `ids`, keeping the selection if it is still there, else the first heard."""
        shown = [self.instance_box.itemText(i) for i in range(self.instance_box.count())]
        if shown == ids:
            return
        with QSignalBlocker(self.instance_box):
            self.instance_box.clear()
            self.instance_box.addItems(ids)
            if self._selected not in ids:
                self._selected = ids[0] if ids else None
            self.instance_box.setCurrentIndex(ids.index(self._selected) if self._selected in ids else -1)

    def show_snapshot(self, snapshot: Snapshot) -> InstanceView | None:
        """Show the selected instance in `snapshot` and return it, or a waiting state and None if there is none."""
        self._sync_choices([inst.id for inst in snapshot.instances])
        inst = next((i for i in snapshot.instances if i.id == self._selected), None)
        if inst is None:
            self._paint(
                _Shown(connected=False, text="Waiting for WSJT-X", dial=MISSING, mode=MISSING, rx=MISSING, tx=MISSING)
            )
            return None
        self._paint(
            _Shown(
                connected=inst.connected,
                text="Connected" if inst.connected else "Disconnected",
                dial=format_dial(inst.dial_hz),
                mode=MISSING if inst.mode is None else inst.mode,
                rx=_hz(inst.rx_hz),
                tx=_hz(inst.tx_hz),
            )
        )
        return inst

    def _paint(self, shown: _Shown) -> None:
        colour = CONNECTED_COLOUR if shown.connected else IDLE_COLOUR
        self.dot.setStyleSheet(f"color: {colour}; font-size: 16px;")
        self.connection_label.setText(shown.text)
        self.dial_label.setText(shown.dial)
        self.mode_label.setText(shown.mode)
        self.rx_label.setText(shown.rx)
        self.tx_label.setText(shown.tx)
