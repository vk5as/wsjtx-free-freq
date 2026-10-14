import socket
import time
from collections.abc import Callable

import pytest
from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.codec import encode_heartbeat
from wsjtx_free_freq.engine import Engine
from wsjtx_free_freq.gui.listener import UdpListener

GROUP = "239.255.0.1"
WAIT_S = 3.0

pytestmark = pytest.mark.usefixtures("qapp")


def _pump(app: QApplication, done: Callable[[], bool], timeout_s: float = WAIT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while not done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _heard(engine: Engine) -> bool:
    return engine.snapshot(time.monotonic()).instances != ()


def _app() -> QApplication:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    return app


def test_unicast_datagram_reaches_the_engine_when_no_group_is_set() -> None:
    engine = Engine()
    listener = UdpListener(engine)
    assert listener.bind(0, "127.0.0.1", "")
    assert listener.problem == ""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.sendto(encode_heartbeat("WSJT-X"), ("127.0.0.1", listener.local_port()))
        _pump(_app(), lambda: _heard(engine))
    assert _heard(engine)


def test_multicast_datagram_reaches_the_engine_when_the_group_is_joined() -> None:
    engine = Engine()
    listener = UdpListener(engine)
    assert listener.bind(0, "127.0.0.1", GROUP)
    if listener.problem:
        pytest.skip(f"this platform does not allow joining {GROUP}: {listener.problem}")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        try:
            sender.sendto(encode_heartbeat("WSJT-X"), (GROUP, listener.local_port()))
        except OSError as error:
            pytest.skip(f"this platform cannot send to {GROUP} on localhost: {error}")
        _pump(_app(), lambda: _heard(engine))
    assert _heard(engine)


def test_a_group_that_cannot_be_joined_is_reported_not_raised() -> None:
    listener = UdpListener(Engine())
    assert listener.bind(0, "127.0.0.1", "10.0.0.1")
    assert "10.0.0.1" in listener.problem


def test_a_port_that_is_taken_is_reported_not_raised() -> None:
    listener = UdpListener(Engine())
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken_port = int(taken.getsockname()[1])
        assert not listener.bind(taken_port, "127.0.0.1", "")
    assert f"127.0.0.1:{taken_port}" in listener.problem


def test_a_good_bind_clears_an_earlier_problem() -> None:
    listener = UdpListener(Engine())
    listener.bind(0, "127.0.0.1", "10.0.0.1")
    assert listener.problem
    assert listener.bind(0, "127.0.0.1", "")
    assert listener.problem == ""
