"""The application window: the header bar, fed by the UDP listener through the engine."""

import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from wsjtx_free_freq.engine import Engine
from wsjtx_free_freq.gui.header import HeaderBar
from wsjtx_free_freq.gui.listener import DEFAULT_PORT, UdpListener

WINDOW_TITLE = "WSJT-X Free Frequency"
REFRESH_MS = 1000


class MainWindow(QMainWindow):
    """Top-level window of the application."""

    def __init__(self, listen_port: int = DEFAULT_PORT, engine: Engine | None = None) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.engine = Engine() if engine is None else engine
        self.listener = UdpListener(self.engine, self)
        self.listener.bind(listen_port)
        self.header = HeaderBar()
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addWidget(self.header)
        layout.addStretch()
        self.setCentralWidget(body)
        self.listener.datagram_received.connect(self.refresh)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(REFRESH_MS)
        self.refresh()

    def refresh(self) -> None:
        """Redraw the header from the engine's current snapshot."""
        self.header.show_snapshot(self.engine.snapshot(time.monotonic()))
