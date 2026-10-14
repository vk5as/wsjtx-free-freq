import time

import pytest
from PyQt6.QtWidgets import QMainWindow

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


def _two_senders() -> Engine:
    engine = Engine()
    for msg_id, address, dial in (("WSJT-X", FIRST, 14074000), ("WSJT-X 2", SECOND, 7074000)):
        engine.receive(encode_heartbeat(msg_id), address, 100.0)
        engine.receive(encode_status(msg_id, dial_hz=dial, mode="FT8", rx_df=1500, tx_df=1000), address, 100.0)
    return engine


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
