import socket
import time

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow

from wsjtx_datagrams import decode_configure, decode_message
from wsjtx_free_freq.codec import encode_decode, encode_heartbeat, encode_status
from wsjtx_free_freq.engine import Engine, Outgoing, Slot
from wsjtx_free_freq.gui.main_window import MainWindow

FIRST = ("10.0.0.1", 2237)
SECOND = ("10.0.0.2", 2237)


@pytest.mark.usefixtures("qapp")
def test_main_window_is_an_empty_window_titled_for_the_app() -> None:
    window = MainWindow(listen_port=0)
    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "WSJT-X Free Frequency"
    assert window.centralWidget() is not None
    window.close()


@pytest.mark.usefixtures("qapp")
def test_clicking_the_band_map_sends_the_rounded_offset_through_set_rx(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = Engine()
    engine.receive(decode_message("WSJT-X", time_ms=0, delta_hz=1000), ("127.0.0.1", 50000), now=time.monotonic())
    window = MainWindow(listen_port=0, engine=engine)
    window.band_map.resize(600, 120)
    sent: list[Outgoing] = []
    monkeypatch.setattr(window.listener, "send", sent.append)
    window.refresh()
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(315, 30),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(window.band_map, press)
    assert len(sent) == 1
    assert decode_configure(sent[0].payload)["rx_df"] == 1500
    assert window.rx_hint.text.text().startswith("Rx set to 1500 Hz")
    window.close()


def _two_senders() -> Engine:
    engine = Engine()
    now = time.monotonic()
    for msg_id, address, dial in (("WSJT-X", FIRST, 14074000), ("WSJT-X 2", SECOND, 7074000)):
        engine.receive(encode_heartbeat(msg_id), address, now)
        engine.receive(encode_status(msg_id, dial_hz=dial, mode="FT8", rx_df=1500, tx_df=1000), address, now)
    return engine


def _one_sender(mode: str, now: float) -> Engine:
    engine = Engine()
    engine.receive(encode_heartbeat("WSJT-X"), FIRST, now)
    engine.receive(encode_status("WSJT-X", dial_hz=14074000, mode=mode, rx_df=1500, tx_df=1000), FIRST, now)
    return engine


@pytest.mark.usefixtures("qapp")
def test_set_rx_is_ignored_when_the_instance_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    window = MainWindow(listen_port=0, engine=_one_sender("JT65", time.monotonic()))
    sent: list[Outgoing] = []
    monkeypatch.setattr(window.listener, "send", sent.append)
    window.set_rx(1234)
    assert sent == []
    assert window.rx_hint.isHidden()
    window.close()


@pytest.mark.usefixtures("qapp")
def test_set_rx_is_ignored_when_the_instance_is_not_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    window = MainWindow(listen_port=0, engine=_one_sender("FT8", now=0.0))  # heard long ago, so timed out
    sent: list[Outgoing] = []
    monkeypatch.setattr(window.listener, "send", sent.append)
    window.set_rx(1234)
    assert sent == []
    assert window.rx_hint.isHidden()
    window.close()


@pytest.mark.usefixtures("qapp")
def test_set_rx_ignores_a_negative_offset_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    window = MainWindow(listen_port=0, engine=_two_senders())
    sent: list[Outgoing] = []
    monkeypatch.setattr(window.listener, "send", sent.append)
    window.set_rx(-5)
    assert sent == []
    window.close()


@pytest.mark.usefixtures("qapp")
def test_switching_the_dropdown_switches_the_header_to_that_instance() -> None:
    window = MainWindow(listen_port=0, engine=_two_senders())
    assert window.header.dial_label.text() == "14.074 000 MHz"
    window.header.instance_box.setCurrentIndex(1)
    assert window.header.dial_label.text() == "7.074 000 MHz"
    window.close()


@pytest.mark.usefixtures("qapp")
def test_set_rx_goes_only_to_the_selected_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    window = MainWindow(listen_port=0, engine=_two_senders())
    sent: list[Outgoing] = []
    monkeypatch.setattr(window.listener, "send", sent.append)
    window.header.instance_box.setCurrentIndex(1)
    window.set_rx(1234)
    assert [outgoing.address for outgoing in sent] == [SECOND]
    window.close()


def _titles(window: MainWindow) -> list[str]:
    return [window.slot_panels[slot].title.text() for slot in Slot]


@pytest.mark.usefixtures("qapp")
def test_slot_grids_show_the_selected_instance_only() -> None:
    engine = _two_senders()
    now_ms = int(time.time() * 1000)
    datagram = encode_decode("WSJT-X 2", time_ms=now_ms % 86_400_000, snr_db=-5, delta_hz=900, text="CQ K1ABC FN20")
    engine.receive(datagram, SECOND, time.monotonic())
    window = MainWindow(listen_port=0, engine=engine)
    assert all("0 decodes" in title for title in _titles(window))
    window.header.instance_box.setCurrentIndex(1)
    assert sum("1 decodes" in title for title in _titles(window)) == 1
    window.close()


def _band_map_marked_at(window: MainWindow, hz: int) -> bool:
    """Whether the band map draws something at `hz` on the first lane where an empty lane would be blank."""
    band = window.band_map
    band.resize(600, 120)
    image = band.grab().toImage()
    blank = image.pixel(round(band.axis().x_of(1400)), 30)
    return image.pixel(round(band.axis().x_of(hz)), 30) != blank


@pytest.mark.usefixtures("qapp")
def test_band_map_shows_the_selected_instance_only() -> None:
    engine = Engine()
    for msg_id, address, offset in (("WSJT-X", FIRST, 600), ("WSJT-X 2", SECOND, 2200)):
        engine.receive(encode_heartbeat(msg_id), address, 100.0)
        engine.receive(encode_status(msg_id, dial_hz=14074000, mode="FT8", rx_df=offset, tx_df=offset), address, 100.0)
    window = MainWindow(listen_port=0, engine=engine)
    assert _band_map_marked_at(window, 600)
    assert not _band_map_marked_at(window, 2200)
    window.header.instance_box.setCurrentIndex(1)
    assert _band_map_marked_at(window, 2200)
    assert not _band_map_marked_at(window, 600)
    window.close()


@pytest.mark.usefixtures("qapp")
def test_a_port_taken_at_startup_is_shown_in_the_header() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken_port = int(taken.getsockname()[1])
        window = MainWindow(listen_port=taken_port)
    assert str(taken_port) in window.header.connection_label.text()
    window.close()
