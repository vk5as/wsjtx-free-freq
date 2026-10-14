"""The application window: the header bar and one slot panel per slot, fed by the UDP listener through the engine."""

import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from wsjtx_free_freq.engine import Engine, Slot, SlotView
from wsjtx_free_freq.gui.header import HeaderBar
from wsjtx_free_freq.gui.listener import DEFAULT_PORT, UdpListener
from wsjtx_free_freq.gui.slot_panel import SlotPanel

WINDOW_TITLE = "WSJT-X Free Frequency"
REFRESH_MS = 1000
_NO_DECODES = SlotView(occupied=(), free=(), decode_count=0)


class MainWindow(QMainWindow):
    """Top-level window of the application."""

    def __init__(self, listen_port: int = DEFAULT_PORT, engine: Engine | None = None) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.engine = Engine() if engine is None else engine
        self.listener = UdpListener(self.engine, self)
        self.listener.bind(listen_port)
        self.header = HeaderBar()
        self.slot_panels = {slot: SlotPanel(slot) for slot in Slot}
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addWidget(self.header)
        for slot in Slot:
            layout.addWidget(self.slot_panels[slot])
        layout.addStretch()
        self.setCentralWidget(body)
        self.listener.datagram_received.connect(self.refresh)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(REFRESH_MS)
        self.refresh()

    def refresh(self) -> None:
        """Redraw the header and slot panels from the engine's current snapshot."""
        snapshot = self.engine.snapshot(time.monotonic())
        self.header.show_snapshot(snapshot)
        slots = snapshot.instances[0].slots if snapshot.instances else None
        for slot, panel in self.slot_panels.items():
            view = _NO_DECODES if slots is None else slots[slot]
            panel.show_slot(view, self.engine.settings.window_cycles)
