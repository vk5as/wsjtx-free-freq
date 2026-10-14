import dataclasses

import pytest

from wsjtx_datagrams import CLOSE, DECODE, MAGIC, decode_configure, heartbeat, message, status, status_fields, u32, utf8
from wsjtx_free_freq.engine import Engine, InstanceView, Settings, Slot, UnknownInstanceError

SENDER = ("127.0.0.1", 2237)


def only(engine: Engine, now: float = 0.0) -> InstanceView:
    instances = engine.snapshot(now).instances
    assert len(instances) == 1
    return instances[0]


def test_heartbeat_creates_connected_instance_with_empty_slots() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    inst = only(engine)
    assert inst.id == "WSJT-X"
    assert inst.connected is True
    assert inst.dial_hz is None
    assert inst.mode is None
    assert inst.rx_hz is None
    assert inst.tx_hz is None
    assert set(inst.slots) == {Slot.FIRST, Slot.SECOND}
    for view in inst.slots.values():
        assert view.occupied == ()
        assert view.free == ()
        assert view.decode_count == 0


def test_status_sets_dial_mode_rx_and_tx() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", dial_hz=7074000, mode="FT4", rx_df=1234, tx_df=567), SENDER, now=0.0)
    inst = only(engine)
    assert inst.dial_hz == 7074000
    assert inst.mode == "FT4"
    assert inst.rx_hz == 1234
    assert inst.tx_hz == 567


def test_status_before_heartbeat_creates_connected_instance() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X"), SENDER, now=0.0)
    assert only(engine).connected is True


def test_later_status_replaces_earlier_values() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", rx_df=100), SENDER, now=0.0)
    engine.receive(status("WSJT-X", rx_df=200), SENDER, now=1.0)
    assert only(engine, now=1.0).rx_hz == 200


def test_heartbeat_does_not_clear_status_values() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", rx_df=100), SENDER, now=0.0)
    engine.receive(heartbeat("WSJT-X"), SENDER, now=1.0)
    assert only(engine, now=1.0).rx_hz == 100


def test_instances_are_kept_in_first_heard_order() -> None:
    engine = Engine()
    engine.receive(status("second-heard"), SENDER, now=0.0)
    engine.receive(heartbeat("first-heard-later"), SENDER, now=1.0)
    engine.receive(status("second-heard", rx_df=77), SENDER, now=2.0)
    instances = engine.snapshot(2.0).instances
    assert [i.id for i in instances] == ["second-heard", "first-heard-later"]
    assert instances[0].rx_hz == 77
    assert instances[1].rx_hz is None


def test_instances_have_independent_state() -> None:
    engine = Engine()
    engine.receive(status("A", dial_hz=14074000), SENDER, now=0.0)
    engine.receive(status("B", dial_hz=7074000), SENDER, now=0.0)
    a, b = engine.snapshot(0.0).instances
    assert (a.id, a.dial_hz) == ("A", 14074000)
    assert (b.id, b.dial_hz) == ("B", 7074000)


def test_wrong_magic_is_ignored_without_raising() -> None:
    engine = Engine()
    engine.receive(message(0, "WSJT-X", u32(3), utf8("2.7.0"), utf8("x"), magic=MAGIC ^ 1), SENDER, now=0.0)
    engine.receive(b"\x00\x00\x00\x00" + status("WSJT-X")[4:], SENDER, now=0.0)
    assert engine.snapshot(0.0).instances == ()


def test_malformed_datagrams_are_ignored_without_raising() -> None:
    engine = Engine()
    for junk in [b"", b"\xad\xbc", status("WSJT-X")[:10], message(0, None, u32(3))]:
        engine.receive(junk, SENDER, now=0.0)
    assert engine.snapshot(0.0).instances == ()


def test_other_message_types_are_ignored() -> None:
    engine = Engine()
    engine.receive(message(DECODE, "WSJT-X", utf8("junk")), SENDER, now=0.0)
    engine.receive(message(CLOSE, "WSJT-X"), SENDER, now=0.0)
    engine.receive(message(99, "WSJT-X"), SENDER, now=0.0)
    assert engine.snapshot(0.0).instances == ()


def test_null_mode_reads_as_none() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", mode=None), SENDER, now=0.0)
    assert only(engine).mode is None


def test_older_schema_status_is_read_the_same() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", schema=2, dial_hz=3573000, rx_df=900), SENDER, now=0.0)
    inst = only(engine)
    assert (inst.dial_hz, inst.rx_hz) == (3573000, 900)


def test_status_missing_trailing_fields_still_reads_the_front() -> None:
    fields = status_fields(dial_hz=14074000, mode="FT8", rx_df=1500, tx_df=1000)
    engine = Engine()
    engine.receive(message(1, "WSJT-X", *fields[:10]), SENDER, now=0.0)
    inst = only(engine)
    assert (inst.dial_hz, inst.mode, inst.rx_hz, inst.tx_hz) == (14074000, "FT8", 1500, 1000)


def test_status_truncated_inside_a_field_does_not_raise() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X")[:-5], SENDER, now=0.0)
    assert only(engine).dial_hz == 14074000


def test_heartbeat_missing_max_schema_still_creates_instance() -> None:
    engine = Engine()
    engine.receive(message(0, "WSJT-X"), SENDER, now=0.0)
    assert only(engine).connected is True


def test_connection_is_lost_after_heartbeat_timeout() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=100.0)
    assert only(engine, now=144.9).connected is True
    assert only(engine, now=145.1).connected is False


def test_timeout_comes_from_settings() -> None:
    engine = Engine(Settings(heartbeat_timeout_s=5.0))
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    assert only(engine, now=4.0).connected is True
    assert only(engine, now=6.0).connected is False


def test_settings_default_to_the_spec() -> None:
    assert Settings() == Settings(
        search_low_hz=200,
        search_high_hz=2800,
        guard_hz=10,
        window_cycles=4,
        min_spacing_widths=2.0,
        min_clearance_hz=10,
        strong_enabled=False,
        strong_snr_db=10,
        strong_extra_hz=20,
        heartbeat_timeout_s=45.0,
    )


def test_settings_can_be_replaced_and_are_read_back() -> None:
    engine = Engine()
    assert engine.settings == Settings()
    engine.settings = dataclasses.replace(engine.settings, guard_hz=25)
    assert engine.settings.guard_hz == 25


def test_slot_values_match_the_glossary() -> None:
    assert Slot.FIRST.value == "1st"
    assert Slot.SECOND.value == "2nd"


def test_set_rx_is_addressed_to_the_last_sender() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X"), ("192.0.2.1", 2237), now=0.0)
    engine.receive(heartbeat("WSJT-X"), ("192.0.2.9", 4000), now=1.0)
    out = engine.set_rx("WSJT-X", 1234)
    assert out.address == ("192.0.2.9", 4000)


def test_set_rx_payload_is_a_configure_that_only_moves_rx() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", fast_mode=False), SENDER, now=0.0)
    fields = decode_configure(engine.set_rx("WSJT-X", 1234).payload)
    assert fields == {
        "magic": MAGIC,
        "schema": 3,
        "type": 15,
        "id": "WSJT-X",
        "mode": "",
        "frequency_tolerance": 0xFFFFFFFF,
        "submode": "",
        "fast_mode": False,
        "tr_period": 0xFFFFFFFF,
        "rx_df": 1234,
        "dx_call": "",
        "dx_grid": "",
        "generate_messages": False,
        "trailing_bytes": 0,
    }


def test_set_rx_copies_fast_mode_from_the_last_status() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", fast_mode=True), SENDER, now=0.0)
    assert decode_configure(engine.set_rx("WSJT-X", 1500).payload)["fast_mode"] is True
    engine.receive(status("WSJT-X", fast_mode=False), SENDER, now=1.0)
    assert decode_configure(engine.set_rx("WSJT-X", 1500).payload)["fast_mode"] is False


def test_set_rx_fast_mode_defaults_to_false_without_a_status() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    assert decode_configure(engine.set_rx("WSJT-X", 1500).payload)["fast_mode"] is False


def test_set_rx_unknown_instance_raises() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X"), SENDER, now=0.0)
    with pytest.raises(UnknownInstanceError, match="NOPE"):
        engine.set_rx("NOPE", 1500)


def test_set_rx_uses_the_instance_schema() -> None:
    engine = Engine()
    engine.receive(status("OLD", schema=2), SENDER, now=0.0)
    engine.receive(status("NEW", schema=3), SENDER, now=0.0)
    assert decode_configure(engine.set_rx("OLD", 1500).payload)["schema"] == 2
    assert decode_configure(engine.set_rx("NEW", 1500).payload)["schema"] == 3
