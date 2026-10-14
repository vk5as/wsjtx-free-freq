"""UDP listener: binds one port and hands every datagram, with its sender, to the engine. No domain logic."""

import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QHostAddress, QUdpSocket

from wsjtx_free_freq.engine import Engine
from wsjtx_free_freq.persistence import DEFAULT_ADDRESS, DEFAULT_PORT

DEFAULT_HOST = DEFAULT_ADDRESS


class UdpListener(QObject):
    """Feeds the engine; emits `datagram_received` after each one so the view can refresh."""

    datagram_received = pyqtSignal()

    def __init__(self, engine: Engine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._socket = QUdpSocket(self)
        self._socket.readyRead.connect(self._read_pending)

    def bind(self, port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> bool:
        """Bind unicast `host`:`port`, dropping any earlier binding; port 0 picks a free one. False if the port is taken."""
        self._socket.close()
        return self._socket.bind(QHostAddress(host), port)

    def local_port(self) -> int:
        return self._socket.localPort()

    def _read_pending(self) -> None:
        while self._socket.hasPendingDatagrams():
            data, address, port = self._socket.readDatagram(self._socket.pendingDatagramSize())
            host = "" if address is None else address.toString()
            self._engine.receive(bytes(data), (host, port), time.monotonic())
            self.datagram_received.emit()
