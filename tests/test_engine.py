import dataclasses
import itertools
import random

import pytest

from wsjtx_datagrams import (
    CLOSE,
    DECODE,
    MAGIC,
    clear_message,
    decode_configure,
    decode_message,
    heartbeat,
    message,
    status,
    status_fields,
    u32,
    utf8,
)
from wsjtx_free_freq.engine import MAX_WINDOW_CYCLES, Engine, InstanceView, Settings, Slot, UnknownInstanceError

SENDER = ("127.0.0.1", 2237)
FT8_CYCLE_MS = 15_000
FT4_CYCLE_MS = 7_500


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


def test_later_message_makes_a_timed_out_instance_connected_again() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    assert only(engine, now=50.0).connected is False
    engine.receive(heartbeat("WSJT-X"), SENDER, now=50.0)
    assert only(engine, now=50.0).connected is True


def test_close_makes_instance_not_connected() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    engine.receive(message(CLOSE, "WSJT-X"), SENDER, now=1.0)
    inst = only(engine, now=1.0)
    assert inst.connected is False


def test_instance_is_connected_again_on_next_message_after_close() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    engine.receive(message(CLOSE, "WSJT-X"), SENDER, now=1.0)
    engine.receive(status("WSJT-X"), SENDER, now=2.0)
    assert only(engine, now=2.0).connected is True


def test_close_only_affects_the_instance_it_names() -> None:
    engine = Engine()
    engine.receive(heartbeat("A"), SENDER, now=0.0)
    engine.receive(heartbeat("B"), SENDER, now=0.0)
    engine.receive(message(CLOSE, "A"), SENDER, now=1.0)
    a, b = engine.snapshot(1.0).instances
    assert (a.id, a.connected) == ("A", False)
    assert (b.id, b.connected) == ("B", True)


def test_close_from_unknown_instance_is_ignored() -> None:
    engine = Engine()
    engine.receive(heartbeat("A"), SENDER, now=0.0)
    engine.receive(message(CLOSE, "Ghost"), SENDER, now=1.0)
    assert [inst.id for inst in engine.snapshot(1.0).instances] == ["A"]


def test_decodes_for_one_instance_never_enter_another_instances_slots() -> None:
    engine = Engine()
    engine.receive(decode_message("A", time_ms=0, delta_hz=1000), SENDER, now=0.0)
    engine.receive(decode_message("B", time_ms=0, delta_hz=1500), SENDER, now=0.0)
    engine.receive(decode_message("B", time_ms=FT8_CYCLE_MS, delta_hz=1600), SENDER, now=0.0)
    a, b = engine.snapshot(0.0).instances
    assert [o.offset_hz for o in a.slots[Slot.FIRST].occupied] == [1000]
    assert a.slots[Slot.SECOND].decode_count == 0
    assert [o.offset_hz for o in b.slots[Slot.FIRST].occupied] == [1500]
    assert [o.offset_hz for o in b.slots[Slot.SECOND].occupied] == [1600]


def test_status_for_one_instance_does_not_change_another() -> None:
    engine = Engine()
    engine.receive(status("A", rx_df=100, tx_df=200, mode="FT8"), SENDER, now=0.0)
    engine.receive(status("B", rx_df=300, tx_df=400, mode="FT4"), SENDER, now=0.0)
    a, b = engine.snapshot(0.0).instances
    assert (a.rx_hz, a.tx_hz, a.mode) == (100, 200, "FT8")
    assert (b.rx_hz, b.tx_hz, b.mode) == (300, 400, "FT4")


def test_set_rx_addresses_each_instance_at_its_own_sender() -> None:
    engine = Engine()
    engine.receive(status("A"), ("192.0.2.1", 2237), now=0.0)
    engine.receive(status("B"), ("192.0.2.2", 2238), now=0.0)
    assert engine.set_rx("A", 1000).address == ("192.0.2.1", 2237)
    assert engine.set_rx("B", 1000).address == ("192.0.2.2", 2238)


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


def test_set_rx_rejects_a_negative_offset() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X"), SENDER, now=0.0)
    with pytest.raises(ValueError, match="negative"):
        engine.set_rx("WSJT-X", -5)


def test_set_rx_uses_the_instance_schema() -> None:
    engine = Engine()
    engine.receive(status("OLD", schema=2), SENDER, now=0.0)
    engine.receive(status("NEW", schema=3), SENDER, now=0.0)
    assert decode_configure(engine.set_rx("OLD", 1500).payload)["schema"] == 2
    assert decode_configure(engine.set_rx("NEW", 1500).payload)["schema"] == 3


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


def _blocked_range(settings: Settings, snr: int) -> tuple[int, int]:
    engine = Engine(settings)
    engine.receive(decode_message(time_ms=0, delta_hz=1000, snr=snr), SENDER, now=0.0)
    (occupied,) = only(engine).slots[Slot.FIRST].occupied
    return occupied.blocked_low_hz, occupied.blocked_high_hz


def test_strong_decode_gets_extra_guard_when_enabled() -> None:
    assert _blocked_range(Settings(strong_enabled=True), snr=10) == (970, 1080)


def test_strong_decode_gets_base_guard_when_disabled() -> None:
    assert _blocked_range(Settings(strong_enabled=False), snr=30) == (990, 1060)


def test_weak_decode_gets_base_guard_when_enabled() -> None:
    assert _blocked_range(Settings(strong_enabled=True), snr=9) == (990, 1060)


def test_strong_snr_threshold_is_inclusive() -> None:
    assert _blocked_range(Settings(strong_enabled=True, strong_snr_db=-5), snr=-5) == (970, 1080)
    assert _blocked_range(Settings(strong_enabled=True, strong_snr_db=-5), snr=-6) == (990, 1060)


def test_strong_decode_changes_free_locations_and_keeps_clear_of_it() -> None:
    def free(settings: Settings) -> tuple[tuple[int, int], ...]:
        engine = Engine(settings)
        engine.receive(decode_message(time_ms=0, delta_hz=1000, snr=10), SENDER, now=0.0)
        return tuple((f.offset_hz, f.clearance_hz) for f in only(engine).slots[Slot.FIRST].free)

    plain = free(Settings(strong_enabled=False))
    widened = free(Settings(strong_enabled=True))
    assert widened != plain
    for offset, _ in widened:
        assert not (offset <= 1080 and offset + 50 >= 970), offset


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


def test_decodes_whose_mode_symbol_differs_from_status_are_ignored() -> None:
    ft8 = Engine()  # no status yet, so the mode is FT8
    ft8.receive(decode_message(time_ms=0, mode="+"), SENDER, now=0.0)
    assert only(ft8).slots[Slot.FIRST].decode_count == 0
    ft4 = Engine()
    ft4.receive(status("WSJT-X", mode="FT4", tr_period=0), SENDER, now=0.0)
    ft4.receive(decode_message(time_ms=0, mode="~"), SENDER, now=0.0)
    assert only(ft4).slots[Slot.FIRST].decode_count == 0


def test_ft4_decodes_go_to_slots_on_7_5_second_cycles() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", mode="FT4", tr_period=0), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=0, mode="+", delta_hz=1000), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=FT4_CYCLE_MS, mode="+", delta_hz=1200), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=2 * FT4_CYCLE_MS, mode="+", delta_hz=1400), SENDER, now=0.0)
    inst = only(engine)
    assert sorted(o.offset_hz for o in inst.slots[Slot.FIRST].occupied) == [1000, 1400]
    assert [o.offset_hz for o in inst.slots[Slot.SECOND].occupied] == [1200]


def test_ft4_signal_width_sets_blocked_range_and_candidates() -> None:
    settings = Settings(search_low_hz=200, search_high_hz=320)  # FT8 candidates 200..270, FT4 candidates 200..235
    ft8 = Engine(settings)
    ft8.receive(decode_message(time_ms=0, mode="~", delta_hz=200), SENDER, now=0.0)
    assert only(ft8).slots[Slot.FIRST].free  # 265 and 270 clear an FT8 signal at 200 (blocks 190..260)
    ft4 = Engine(settings)
    ft4.receive(status("WSJT-X", mode="FT4", tr_period=0), SENDER, now=0.0)
    ft4.receive(decode_message(time_ms=0, mode="+", delta_hz=200), SENDER, now=0.0)
    slot = only(ft4).slots[Slot.FIRST]
    assert (slot.occupied[0].blocked_low_hz, slot.occupied[0].blocked_high_hz) == (190, 293)
    assert slot.free == ()


def test_status_tr_period_does_not_override_ft8_cycle_length() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", tr_period=10), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=10_000, delta_hz=1200), SENDER, now=0.0)  # cycle 0 at 15 s, not 1 at 10 s
    inst = only(engine)
    assert inst.slots[Slot.FIRST].decode_count == 1
    assert inst.slots[Slot.SECOND].decode_count == 0


def test_ft4_truncated_tr_period_still_slots_on_7_5_second_cycles() -> None:
    # WSJT-X sends T/R period as whole seconds, so FT4's 7.5 s arrives as 7
    engine = Engine()
    engine.receive(status("WSJT-X", mode="FT4", tr_period=7), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=FT4_CYCLE_MS, mode="+", delta_hz=1000), SENDER, now=0.0)  # cycle 1
    engine.receive(decode_message(time_ms=14_500, mode="+", delta_hz=1200), SENDER, now=0.0)  # cycle 1, 2 at 7 s
    inst = only(engine)
    assert sorted(o.offset_hz for o in inst.slots[Slot.SECOND].occupied) == [1000, 1200]
    assert inst.slots[Slot.FIRST].decode_count == 0


def test_zero_tr_period_keeps_the_mode_default_cycle() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", tr_period=0), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=FT8_CYCLE_MS, delta_hz=1200), SENDER, now=0.0)
    assert only(engine).slots[Slot.SECOND].decode_count == 1


def test_ft4_slot_parity_and_dedupe_hold_across_midnight() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", mode="FT4", tr_period=0), SENDER, now=0.0)
    late = 86_400_000 - FT4_CYCLE_MS  # 23:59:52.5, cycle 11519
    engine.receive(decode_message(time_ms=late, mode="+", delta_hz=1000), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=0, mode="+", delta_hz=1200), SENDER, now=0.0)  # cycle 11520
    engine.receive(decode_message(time_ms=late, mode="+", delta_hz=1000, new=False), SENDER, now=0.0)
    inst = only(engine)
    assert [o.offset_hz for o in inst.slots[Slot.FIRST].occupied] == [1200]
    assert [o.offset_hz for o in inst.slots[Slot.SECOND].occupied] == [1000]


def test_empty_slot_offers_ten_free_locations_at_full_clearance() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    free = only(engine).slots[Slot.FIRST].free
    assert len(free) == 10
    assert [f.rank for f in free] == list(range(1, 11))
    assert all(f.clearance_hz == 2600 for f in free)


def test_gap_is_the_physical_distance_to_the_nearest_occupancy_without_age_weighting() -> None:
    engine = Engine(Settings(search_low_hz=200, search_high_hz=1100))
    engine.receive(decode_message(time_ms=0, delta_hz=1000), SENDER, now=0.0)  # cycle 0: blocks 990..1060
    engine.receive(
        decode_message(time_ms=7 * FT8_CYCLE_MS, delta_hz=1500), SENDER, now=0.0
    )  # cycle 7: other slot, makes cycle 0 age 3
    free = {f.offset_hz: f for f in only(engine).slots[Slot.FIRST].free}
    assert free[900].gap_hz == 40  # 900..950 against 990: 40 Hz physical gap
    assert free[900].clearance_hz == 160  # ranking still weights it by age: 40 * (1 + 3)


def test_empty_slot_gap_is_the_whole_search_span() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    free = only(engine).slots[Slot.FIRST].free
    assert all(f.gap_hz == 2600 for f in free)


def test_candidate_overlapping_a_blocked_range_is_never_free() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=200), SENDER, now=0.0)  # blocks 190..260
    free = only(engine).slots[Slot.FIRST].free
    assert free
    for f in free:
        assert not (f.offset_hz <= 260 and f.offset_hz + 50 >= 190), f


def test_free_locations_rank_by_clearance_highest_first() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000), SENDER, now=0.0)  # blocks 990..1060
    free = only(engine).slots[Slot.FIRST].free
    assert [(f.rank, f.offset_hz, f.clearance_hz) for f in free] == [
        (rank, 2750 - 100 * (rank - 1), 1690 - 100 * (rank - 1)) for rank in range(1, 11)
    ]


def test_clearance_ties_go_to_the_offset_nearest_tx() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", tx_df=1000), SENDER, now=0.0)  # empty slot: every candidate ties
    free = only(engine).slots[Slot.FIRST].free
    assert free[0].offset_hz == 1000
    distances = [abs(f.offset_hz - 1000) for f in free]
    assert distances == sorted(distances)


def test_stale_neighbour_ranks_above_fresh_one_at_equal_gap() -> None:
    engine = Engine(Settings(search_high_hz=600))  # candidates 200..550
    stale = decode_message(time_ms=0, delta_hz=450)  # cycle 0: age 2 at cycle 4, blocks 440..510
    fresh = decode_message(time_ms=4 * FT8_CYCLE_MS, delta_hz=300)  # cycle 4: age 0, blocks 290..360
    engine.receive(stale, SENDER, now=0.0)
    engine.receive(fresh, SENDER, now=0.0)
    offsets = [f.offset_hz for f in only(engine).slots[Slot.FIRST].free]
    # 200 is 40 Hz below the fresh block; 550 is 40 Hz above the stale block, scaled by 3
    assert {200, 550} <= set(offsets)
    assert offsets.index(550) < offsets.index(200)


def test_fully_occupied_slot_gives_no_free_locations() -> None:
    engine = Engine(Settings(search_high_hz=300))  # candidates 200..250, all inside 190..260
    engine.receive(decode_message(time_ms=0, delta_hz=200), SENDER, now=0.0)
    assert only(engine).slots[Slot.FIRST].free == ()


def test_window_ages_across_midnight() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=86_400_000 - 2 * FT8_CYCLE_MS, delta_hz=1000), SENDER, now=0.0)  # 23:59:30
    engine.receive(decode_message(time_ms=0, delta_hz=1200), SENDER, now=0.0)  # 00:00:00
    first = only(engine).slots[Slot.FIRST]
    ages = {o.offset_hz: o.age_cycles for o in first.occupied}
    assert ages == {1000: 1, 1200: 0}


def test_window_ages_across_midnight_when_the_late_decode_arrives_last() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1200), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=86_400_000 - 2 * FT8_CYCLE_MS, delta_hz=1000), SENDER, now=0.0)
    first = only(engine).slots[Slot.FIRST]
    ages = {o.offset_hz: o.age_cycles for o in first.occupied}
    assert ages == {1000: 1, 1200: 0}


def test_truncated_and_garbage_datagrams_never_raise() -> None:
    rng = random.Random(18)  # noqa: S311
    valid = [heartbeat("WSJT-X"), status("WSJT-X"), decode_message(time_ms=5000), decode_message(mode=None)]
    junk = [bytes(rng.getrandbits(8) for _ in range(rng.randrange(0, 200))) for _ in range(500)]
    engine = Engine()
    for datagram in [*valid, *junk]:
        for end in range(len(datagram) + 1):
            engine.receive(datagram[:end], SENDER, now=0.0)
        engine.receive(datagram, SENDER, now=0.0)
    engine.snapshot(0.0)


def test_low_confidence_decode_counts() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000, low_confidence=True), SENDER, now=0.0)
    assert only(engine).slots[Slot.FIRST].decode_count == 1


def test_clear_does_not_change_snapshot() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=0, delta_hz=1000), SENDER, now=0.0)
    before = engine.snapshot(now=100.0)  # past the heartbeat timeout, so connected is False
    engine.receive(clear_message("WSJT-X"), ("10.0.0.9", 9999), now=100.0)
    assert engine.snapshot(now=100.0) == before


def test_clear_from_unknown_instance_creates_nothing() -> None:
    engine = Engine()
    engine.receive(clear_message("WSJT-X", window=2), SENDER, now=0.0)
    assert engine.snapshot(0.0).instances == ()


def test_off_air_decodes_do_not_appear() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000, off_air=True), SENDER, now=0.0)
    assert only(engine).slots[Slot.FIRST].decode_count == 0


def test_re_sent_decode_counts_once() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000, text="CQ K1ABC FN20"), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=0, delta_hz=1000, text="CQ K1ABC FN20", new=False), SENDER, now=0.0)
    assert only(engine).slots[Slot.FIRST].decode_count == 1


def test_decode_differing_in_time_offset_or_message_is_not_a_duplicate() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000, text="CQ K1ABC FN20"), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=0, delta_hz=1001, text="CQ K1ABC FN20"), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=0, delta_hz=1000, text="CQ W1XYZ FN31"), SENDER, now=0.0)
    engine.receive(decode_message(time_ms=0, delta_hz=1000, text="CQ K1ABC FN20"), SENDER, now=0.0)
    assert only(engine).slots[Slot.FIRST].decode_count == 3


def test_re_sent_decode_counts_once_across_midnight() -> None:
    engine = Engine()
    engine.receive(
        decode_message(time_ms=86_400_000 - FT8_CYCLE_MS, delta_hz=1000, text="CQ K1ABC FN20"), SENDER, now=0.0
    )
    engine.receive(decode_message(time_ms=0, delta_hz=1200), SENDER, now=0.0)  # 00:00:00, after the unwrap
    engine.receive(
        decode_message(time_ms=86_400_000 - FT8_CYCLE_MS, delta_hz=1000, text="CQ K1ABC FN20", new=False),
        SENDER,
        now=0.0,
    )
    assert only(engine).slots[Slot.SECOND].decode_count == 1


def _occupy_both_slots(engine: Engine, instance_id: str = "WSJT-X") -> None:
    engine.receive(decode_message(instance_id, time_ms=0, delta_hz=1000), SENDER, now=0.0)
    engine.receive(decode_message(instance_id, time_ms=FT8_CYCLE_MS, delta_hz=1200), SENDER, now=0.0)


def _decode_counts(inst: InstanceView) -> tuple[int, int]:
    return (inst.slots[Slot.FIRST].decode_count, inst.slots[Slot.SECOND].decode_count)


def test_dial_change_clears_both_slots() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", dial_hz=14074000), SENDER, now=0.0)
    _occupy_both_slots(engine)
    engine.receive(status("WSJT-X", dial_hz=7074000), SENDER, now=1.0)
    assert _decode_counts(only(engine, now=1.0)) == (0, 0)


def test_mode_change_clears_both_slots() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", mode="FT8"), SENDER, now=0.0)
    _occupy_both_slots(engine)
    engine.receive(status("WSJT-X", mode="FT4"), SENDER, now=1.0)
    assert _decode_counts(only(engine, now=1.0)) == (0, 0)


def test_rx_and_tx_changes_keep_occupancy() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", rx_df=100, tx_df=200), SENDER, now=0.0)
    _occupy_both_slots(engine)
    engine.receive(status("WSJT-X", rx_df=300, tx_df=400), SENDER, now=1.0)
    assert _decode_counts(only(engine, now=1.0)) == (1, 1)


def test_dial_change_on_one_instance_leaves_others_alone() -> None:
    engine = Engine()
    engine.receive(status("A", dial_hz=14074000), SENDER, now=0.0)
    engine.receive(status("B", dial_hz=14074000), SENDER, now=0.0)
    _occupy_both_slots(engine, "A")
    _occupy_both_slots(engine, "B")
    engine.receive(status("A", dial_hz=7074000), SENDER, now=1.0)
    a, b = engine.snapshot(1.0).instances
    assert _decode_counts(a) == (0, 0)
    assert _decode_counts(b) == (1, 1)


def test_chosen_locations_are_at_least_the_default_spacing_apart() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000), SENDER, now=0.0)
    offsets = sorted(f.offset_hz for f in only(engine).slots[Slot.FIRST].free)
    assert len(offsets) > 1
    assert all(b - a >= 100 for a, b in itertools.pairwise(offsets))


def test_locations_under_minimum_clearance_never_appear() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000), SENDER, now=0.0)  # blocks 990..1060
    engine.receive(decode_message(time_ms=0, delta_hz=1400), SENDER, now=0.0)  # blocks 1390..1460
    free = only(engine).slots[Slot.FIRST].free
    assert free
    assert all(f.clearance_hz >= 10 for f in free)


def test_crowded_slot_shows_fewer_locations_than_the_maximum() -> None:
    engine = Engine(Settings(search_high_hz=600))  # candidates 200..550
    engine.receive(decode_message(time_ms=0, delta_hz=500), SENDER, now=0.0)  # blocks 490..560
    free = only(engine).slots[Slot.FIRST].free
    # 435 and up are under 10 Hz clearance or within 100 Hz of a chosen location, so only three remain
    assert [f.offset_hz for f in free] == [200, 300, 400]


def test_spacing_follows_settings() -> None:
    engine = Engine(Settings(min_spacing_widths=1.0))  # 50 Hz
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    offsets = [f.offset_hz for f in only(engine).slots[Slot.FIRST].free]
    assert offsets[:3] == [200, 250, 300]


def test_clearance_minimum_follows_settings() -> None:
    engine = Engine()
    engine.receive(decode_message(time_ms=0, delta_hz=1000), SENDER, now=0.0)
    engine.settings = dataclasses.replace(engine.settings, min_clearance_hz=1000)
    free = only(engine).slots[Slot.FIRST].free
    assert free
    assert all(f.clearance_hz >= 1000 for f in free)


def test_ft8_and_ft4_instances_are_supported() -> None:
    for mode in ("FT8", "FT4"):
        engine = Engine()
        engine.receive(status("WSJT-X", mode=mode), SENDER, now=0.0)
        assert only(engine).supported is True


def test_instance_before_any_status_is_supported() -> None:
    engine = Engine()
    engine.receive(heartbeat("WSJT-X"), SENDER, now=0.0)
    assert only(engine).supported is True


def test_jt65_status_marks_instance_unsupported() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", mode="JT65"), SENDER, now=0.0)
    assert only(engine).supported is False


def test_switching_back_to_ft8_recovers_support() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", mode="JT65"), SENDER, now=0.0)
    engine.receive(status("WSJT-X", mode="FT8"), SENDER, now=1.0)
    assert only(engine, now=1.0).supported is True


def test_unsupported_mode_lists_no_free_or_occupied_locations() -> None:
    engine = Engine()
    engine.receive(status("WSJT-X", mode="JT65"), SENDER, now=0.0)
    for slot in Slot:
        view = only(engine).slots[slot]
        assert view.free == ()
        assert view.occupied == ()


def test_a_silent_slot_ages_out_when_the_other_slot_keeps_decoding() -> None:
    engine = Engine()  # window_cycles defaults to 4
    engine.receive(
        decode_message(time_ms=0, delta_hz=1000), SENDER, now=0.0
    )  # FIRST slot, then the operator transmits there
    for cycle in (1, 3, 5, 7):  # SECOND slot only
        engine.receive(decode_message(time_ms=cycle * FT8_CYCLE_MS, delta_hz=1100), SENDER, now=0.0)
    assert [o.offset_hz for o in only(engine).slots[Slot.FIRST].occupied] == [1000]  # FIRST is at cycle 6: age 3
    engine.receive(decode_message(time_ms=9 * FT8_CYCLE_MS, delta_hz=1100), SENDER, now=0.0)
    assert only(engine).slots[Slot.FIRST].occupied == ()  # FIRST is at cycle 8: age 4 reaches the window


def test_largest_allowed_window_still_sees_decodes_that_old() -> None:
    engine = Engine(Settings(window_cycles=MAX_WINDOW_CYCLES))
    for cycle in range(0, 300, 2):  # FIRST slot for 150 of its cycles, the newest at cycle 298
        engine.receive(decode_message(time_ms=cycle * FT8_CYCLE_MS, delta_hz=1000 + cycle), SENDER, now=0.0)
    first = only(engine).slots[Slot.FIRST]
    assert first.decode_count == MAX_WINDOW_CYCLES
    assert min(o.age_cycles for o in first.occupied) == 0
    assert max(o.age_cycles for o in first.occupied) == MAX_WINDOW_CYCLES - 1


def test_decodes_older_than_the_largest_window_are_forgotten() -> None:
    engine = Engine()
    for cycle in range(0, 4000, 2):
        engine.receive(decode_message(time_ms=cycle * FT8_CYCLE_MS, delta_hz=1000 + cycle), SENDER, now=0.0)
    instance = engine._instances["WSJT-X"]  # bounded memory is internal, so this one looks inside
    assert len(instance.heard) <= 2 * MAX_WINDOW_CYCLES + 2
    assert len(instance.seen) <= 2 * MAX_WINDOW_CYCLES + 2
