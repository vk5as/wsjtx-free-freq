"""The application window: the header bar and one slot panel per slot, fed by the UDP listener through the engine."""

import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from wsjtx_free_freq.engine import Engine, Slot, SlotView
from wsjtx_free_freq.gui.band_map import BandMap
from wsjtx_free_freq.gui.header import HeaderBar
from wsjtx_free_freq.gui.listener import DEFAULT_HOST, UdpListener
from wsjtx_free_freq.gui.slot_panel import SlotPanel
from wsjtx_free_freq.persistence import DEFAULT_PORT

WINDOW_TITLE = "WSJT-X Free Frequency"
REFRESH_MS = 1000
_NO_DECODES = SlotView(occupied=(), free=(), decode_count=0)


class MainWindow(QMainWindow):
    """Top-level window of the application."""

    def __init__(
        self, listen_port: int = DEFAULT_PORT, engine: Engine | None = None, listen_host: str = DEFAULT_HOST
    ) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.engine = Engine() if engine is None else engine
        self.listener = UdpListener(self.engine, self)
        self.listener.bind(listen_port, listen_host)
        self.header = HeaderBar()
        self.band_map = BandMap()
        self.slot_panels = {slot: SlotPanel(slot) for slot in Slot}
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addWidget(self.header)
        layout.addWidget(self.band_map)
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
        instance = snapshot.instances[0] if snapshot.instances else None
        self.band_map.show_snapshot(instance, self.engine.settings)
        for slot, panel in self.slot_panels.items():
            view = _NO_DECODES if instance is None else instance.slots[slot]
            panel.show_slot(view, self.engine.settings.window_cycles)
