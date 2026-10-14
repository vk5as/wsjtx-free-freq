"""Header bar: connection, dial frequency, mode, Rx and Tx for the first WSJT-X instance."""

from dataclasses import dataclass

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from wsjtx_free_freq.engine import Snapshot
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
    """Shows the first instance in the snapshot; its values are the labels' text. Settings asks the window to open its dialog."""

    settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
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

    def show_snapshot(self, snapshot: Snapshot, problem: str = "") -> None:
        """Show the first instance in `snapshot`, or a waiting state. A listen `problem` replaces the connection text."""
        if not snapshot.instances:
            self._paint(
                _Shown(
                    connected=False,
                    text=problem or "Waiting for WSJT-X",
                    dial=MISSING,
                    mode=MISSING,
                    rx=MISSING,
                    tx=MISSING,
                )
            )
            return
        inst = snapshot.instances[0]
        self._paint(
            _Shown(
                connected=inst.connected and not problem,
                text=problem or ("Connected" if inst.connected else "Disconnected"),
                dial=format_dial(inst.dial_hz),
                mode=MISSING if inst.mode is None else inst.mode,
                rx=_hz(inst.rx_hz),
                tx=_hz(inst.tx_hz),
            )
        )

    def _paint(self, shown: _Shown) -> None:
        colour = CONNECTED_COLOUR if shown.connected else IDLE_COLOUR
        self.dot.setStyleSheet(f"color: {colour}; font-size: 16px;")
        self.connection_label.setText(shown.text)
        self.dial_label.setText(shown.dial)
        self.mode_label.setText(shown.mode)
        self.rx_label.setText(shown.rx)
        self.tx_label.setText(shown.tx)
