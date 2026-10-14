import pytest

from wsjtx_free_freq.encoder import heartbeat, status
from wsjtx_free_freq.engine import Engine
from wsjtx_free_freq.gui.header import HeaderBar

SENDER = ("127.0.0.1", 50000)


def _fed_engine(now: float) -> Engine:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now)
    engine.receive(status("WSJT-X", dial_hz=14074000, mode="FT8", rx_df=1500, tx_df=1000), SENDER, now)
    return engine


@pytest.mark.usefixtures("qapp")
def test_header_shows_connected_dial_mode_and_offsets_from_the_first_instance() -> None:
    header = HeaderBar()
    header.show_snapshot(_fed_engine(now=100.0).snapshot(now=101.0))
    assert header.connection_label.text() == "Connected"
    assert header.dial_label.text() == "14.074 000 MHz"
    assert header.mode_label.text() == "FT8"
    assert header.rx_label.text() == "1500 Hz"
    assert header.tx_label.text() == "1000 Hz"


@pytest.mark.usefixtures("qapp")
def test_header_shows_disconnected_once_heartbeats_stop() -> None:
    header = HeaderBar()
    header.show_snapshot(_fed_engine(now=100.0).snapshot(now=200.0))
    assert header.connection_label.text() == "Disconnected"
    assert header.dial_label.text() == "14.074 000 MHz"


@pytest.mark.usefixtures("qapp")
def test_header_with_no_instances_shows_waiting_and_dashes() -> None:
    header = HeaderBar()
    header.show_snapshot(Engine().snapshot(now=0.0))
    assert header.connection_label.text() == "Waiting for WSJT-X"
    assert header.dial_label.text() == "-"
    assert header.mode_label.text() == "-"
