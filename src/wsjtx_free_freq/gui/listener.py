"""UDP listener: binds one port and hands every datagram, with its sender, to the engine. No domain logic."""

import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QHostAddress, QUdpSocket

from wsjtx_free_freq.engine import Engine, Outgoing
from wsjtx_free_freq.persistence import DEFAULT_ADDRESS, DEFAULT_PORT

DEFAULT_HOST = DEFAULT_ADDRESS


class UdpListener(QObject):
    """Feeds the engine; emits `datagram_received` once each time a read drains so the view can refresh."""

    datagram_received = pyqtSignal()

    def __init__(self, engine: Engine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._socket = QUdpSocket(self)
        self._socket.readyRead.connect(self._read_pending)
        self.problem = ""  # why the last bind or join failed; empty when listening as asked

    def bind(self, port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, group: str = "") -> bool:
        """Bind `port` on `host`, dropping any earlier binding; port 0 picks a free one. False if the port is taken.

        With a `group`, the socket binds any address (group traffic is addressed to the group, not to `host`), shares
        the port so other listeners can too, and joins the group. A failed join leaves the socket bound and sets `problem`.
        """
        self._socket.close()
        self.problem = ""
        if group:
            shared = QUdpSocket.BindFlag.ShareAddress | QUdpSocket.BindFlag.ReuseAddressHint
            bound = self._socket.bind(QHostAddress.SpecialAddress.AnyIPv4, port, shared)
        else:
            bound = self._socket.bind(QHostAddress(host), port)
        if not bound:
            self.problem = f"Could not listen on {host}:{port}. The port may be in use."
            return False
        if group and not self._socket.joinMulticastGroup(QHostAddress(group)):
            self.problem = f"Could not join multicast group {group}."
        return True

    def local_port(self) -> int:
        return self._socket.localPort()

    def send(self, outgoing: Outgoing) -> None:
        """Send one datagram from the bound socket, so WSJT-X's replies come back to this listener."""
        host, port = outgoing.address
        self._socket.writeDatagram(outgoing.payload, QHostAddress(host), port)

    def _read_pending(self) -> None:
        while self._socket.hasPendingDatagrams():
            data, address, port = self._socket.readDatagram(self._socket.pendingDatagramSize())
            host = "" if address is None else address.toString()
            self._engine.receive(bytes(data), (host, port), time.monotonic())
        self.datagram_received.emit()
