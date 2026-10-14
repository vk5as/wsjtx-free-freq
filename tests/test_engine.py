import dataclasses

from wsjtx_datagrams import (
    CLOSE,
    DECODE,
    MAGIC,
    decode_message,
    heartbeat,
    message,
    status,
    status_fields,
    u32,
    utf8,
)
from wsjtx_free_freq.engine import Engine, InstanceView, Settings, Slot

SENDER = ("127.0.0.1", 2237)
FT8_CYCLE_MS = 15_000


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


def test_decode_at_0000_lands_in_first_slot_and_at_0015_in_second() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=FT8_CYCLE_MS, delta_hz=1200), SENDER, now=0.0)
    inst = only(engine)
    assert [o.offset_hz for o in inst.slots[Slot.FIRST].occupied] == [1000]
    assert [o.offset_hz for o in inst.slots[Slot.SECOND].occupied] == [1200]
    assert inst.slots[Slot.FIRST].decode_count == 1
    assert inst.slots[Slot.SECOND].decode_count == 1


def test_decode_older_than_window_cycles_drops_out() -> None:
    engine = Engine()  # window_cycles defaults to 4
    for cycle in (0, 2, 4, 6, 8):
        engine.receive(decode_message(time_ms=cycle * FT8_CYCLE_MS, delta_hz=1000 + cycle * 10), SENDER, now=0.0)
    first = only(engine).slots[Slot.FIRST]
    assert first.decode_count == 4
    assert sorted(o.offset_hz for o in first.occupied) == [1020, 1040, 1060, 1080]


def test_age_cycles_and_blocked_range() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000, snr=-7), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=2 * FT8_CYCLE_MS, delta_hz=1200, snr=3), SENDER, now=0.0)
    by_offset = {o.offset_hz: o for o in only(engine).slots[Slot.FIRST].occupied}
    assert by_offset[1200].age_cycles == 0
    assert by_offset[1000].age_cycles == 1
    assert by_offset[1000].snr_db == -7
    assert (by_offset[1000].blocked_low_hz, by_offset[1000].blocked_high_hz) == (990, 1060)


def test_age_counts_only_cycles_of_its_own_slot() -> None:
    engine = Engine()
    for cycle in (0, 1, 2):  # cycle 1 is the other slot
        engine.receive(decode_message(time_ms=cycle * FT8_CYCLE_MS, delta_hz=1000 + cycle), SENDER, now=0.0)
    ages = {o.offset_hz: o.age_cycles for o in only(engine).slots[Slot.FIRST].occupied}
    assert ages == {1000: 1, 1002: 0}


def test_window_cycles_change_applies_on_next_snapshot() -> None:
    engine = Engine()
    for cycle in (0, 2, 4, 6, 8):
        engine.receive(decode_message(time_ms=cycle * FT8_CYCLE_MS), SENDER, now=0.0)
    assert only(engine).slots[Slot.FIRST].decode_count == 4
    engine.settings = dataclasses.replace(engine.settings, window_cycles=2)
    assert only(engine).slots[Slot.FIRST].decode_count == 2
    engine.settings = dataclasses.replace(engine.settings, window_cycles=10)
    assert only(engine).slots[Slot.FIRST].decode_count == 5


def test_slot_parity_holds_across_midnight() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=86_400_000 - FT8_CYCLE_MS, delta_hz=1000), SENDER, now=0.0)  # 23:59:45
    engine.receive(decode_message(time_ms=0, delta_hz=1200), SENDER, now=0.0)
    inst = only(engine)
    assert [o.offset_hz for o in inst.slots[Slot.FIRST].occupied] == [1200]
    assert [o.offset_hz for o in inst.slots[Slot.SECOND].occupied] == [1000]


def test_ft4_decodes_do_not_enter_occupancy() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, mode="+"), SENDER, now=0.0)
    assert only(engine).slots[Slot.FIRST].decode_count == 0
