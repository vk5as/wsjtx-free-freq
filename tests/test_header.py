import pytest

from wsjtx_free_freq.codec import encode_heartbeat, encode_status
from wsjtx_free_freq.engine import Engine
from wsjtx_free_freq.gui.header import HeaderBar

SENDER = ("127.0.0.1", 50000)


def _fed_engine(now: float) -> Engine:
    engine = Engine()
    engine.receive(encode_heartbeat("WSJT-X"), SENDER, now)
    engine.receive(encode_status("WSJT-X", dial_hz=14074000, mode="FT8", rx_df=1500, tx_df=1000), SENDER, now)
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


def _two_instance_engine(now: float) -> Engine:
    engine = Engine()
    for msg_id, dial in (("WSJT-X", 14074000), ("WSJT-X 2", 7074000)):
        engine.receive(encode_heartbeat(msg_id), (msg_id, 50000), now)
        engine.receive(encode_status(msg_id, dial_hz=dial, mode="FT8", rx_df=1500, tx_df=1000), (msg_id, 50000), now)
    return engine


@pytest.mark.usefixtures("qapp")
def test_header_lists_every_instance_and_selects_the_first_heard_by_default() -> None:
    header = HeaderBar()
    header.show_snapshot(_two_instance_engine(now=100.0).snapshot(now=101.0))
    assert [header.instance_box.itemText(i) for i in range(header.instance_box.count())] == ["WSJT-X", "WSJT-X 2"]
    assert header.selected_id == "WSJT-X"
    assert header.dial_label.text() == "14.074 000 MHz"


@pytest.mark.usefixtures("qapp")
def test_choosing_another_instance_shows_it_and_emits_instance_selected() -> None:
    header = HeaderBar()
    snapshot = _two_instance_engine(now=100.0).snapshot(now=101.0)
    header.show_snapshot(snapshot)
    selections: list[bool] = []
    header.instance_selected.connect(lambda: selections.append(True))
    header.instance_box.setCurrentIndex(1)
    assert selections == [True]
    assert header.selected_id == "WSJT-X 2"
    shown = header.show_snapshot(snapshot)
    assert shown is not None
    assert shown.id == "WSJT-X 2"
    assert header.dial_label.text() == "7.074 000 MHz"


@pytest.mark.usefixtures("qapp")
def test_header_shows_a_listen_problem_in_place_of_the_waiting_text() -> None:
    header = HeaderBar()
    header.show_snapshot(Engine().snapshot(now=0.0), "Could not join multicast group 239.1.2.3.")
    assert header.connection_label.text() == "Could not join multicast group 239.1.2.3."
    assert header.dial_label.text() == "-"


@pytest.mark.usefixtures("qapp")
def test_header_shows_a_listen_problem_over_a_connected_instance() -> None:
    header = HeaderBar()
    header.show_snapshot(_fed_engine(now=100.0).snapshot(now=101.0), "Could not listen on 127.0.0.1:2237.")
    assert header.connection_label.text() == "Could not listen on 127.0.0.1:2237."
    assert header.dial_label.text() == "14.074 000 MHz"
