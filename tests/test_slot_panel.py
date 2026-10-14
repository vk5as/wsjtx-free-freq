import pytest

from wsjtx_datagrams import decode_message
from wsjtx_free_freq.engine import Engine, Slot, SlotView
from wsjtx_free_freq.gui.slot_panel import SlotPanel
from wsjtx_free_freq.labels import format_free_location

SENDER = ("127.0.0.1", 50000)
CYCLE_MS = 15_000


def _engine_with_decodes(offsets_by_cycle: dict[int, list[int]]) -> Engine:
    engine = Engine()
    for cycle, offsets in offsets_by_cycle.items():
        for offset in offsets:
            engine.receive(
                decode_message("WSJT-X", time_ms=cycle * CYCLE_MS, delta_hz=offset),
                SENDER,
                now=0.0,
            )
    return engine


def _visible_buttons(panel: SlotPanel) -> list[str]:
    return [b.text() for b in panel.buttons if not b.isHidden()]


@pytest.mark.usefixtures("qapp")
def test_one_button_per_free_location_in_the_slot_view() -> None:
    engine = _engine_with_decodes({0: [1500]})
    view = engine.snapshot(now=0.0).instances[0].slots[Slot.FIRST]
    panel = SlotPanel(Slot.FIRST)
    panel.show_slot(view, window_cycles=4)
    first = view.free[0]
    assert _visible_buttons(panel)[0] == format_free_location(first.rank, first.offset_hz, first.gap_hz)
    assert len(_visible_buttons(panel)) == len(view.free) == 10
    assert panel.empty.isHidden()
    assert panel.title.text() == "1st slot (even, 1 decodes, last 4 cycles)"


@pytest.mark.usefixtures("qapp")
def test_slot_grid_updates_live_from_the_engine() -> None:
    panel = SlotPanel(Slot.SECOND)
    panel.show_slot(SlotView(occupied=(), free=(), decode_count=0), window_cycles=4)
    assert _visible_buttons(panel) == []
    engine = _engine_with_decodes({1: [800, 2000]})
    panel.show_slot(engine.snapshot(now=0.0).instances[0].slots[Slot.SECOND], window_cycles=4)
    assert len(_visible_buttons(panel)) == 10
    assert panel.title.text() == "2nd slot (odd, 2 decodes, last 4 cycles)"


@pytest.mark.usefixtures("qapp")
def test_empty_state_is_shown_and_no_buttons_when_a_slot_has_no_free_locations() -> None:
    panel = SlotPanel(Slot.FIRST)
    panel.show_slot(SlotView(occupied=(), free=(), decode_count=0), window_cycles=4)
    assert _visible_buttons(panel) == []
    assert not panel.empty.isHidden()
    assert panel.empty.text() == "No free locations"


@pytest.mark.usefixtures("qapp")
def test_empty_state_clears_once_free_locations_return() -> None:
    panel = SlotPanel(Slot.FIRST)
    panel.show_slot(SlotView(occupied=(), free=(), decode_count=0), window_cycles=4)
    view = _engine_with_decodes({0: [1500]}).snapshot(now=0.0).instances[0].slots[Slot.FIRST]
    panel.show_slot(view, window_cycles=4)
    assert panel.empty.isHidden()


@pytest.mark.usefixtures("qapp")
def test_clicking_a_free_location_button_emits_its_audio_offset() -> None:
    engine = _engine_with_decodes({0: [1500]})
    view = engine.snapshot(now=0.0).instances[0].slots[Slot.FIRST]
    panel = SlotPanel(Slot.FIRST)
    panel.show_slot(view, window_cycles=4)
    chosen: list[int] = []
    panel.location_chosen.connect(chosen.append)
    panel.buttons[2].click()
    assert chosen == [view.free[2].offset_hz]


@pytest.mark.usefixtures("qapp")
def test_unsupported_mode_shows_message_and_no_buttons() -> None:
    panel = SlotPanel(Slot.FIRST)
    panel.show_slot(SlotView(occupied=(), free=(), decode_count=0), window_cycles=4, unsupported="JT65")
    assert _visible_buttons(panel) == []
    assert panel.empty.isHidden()
    assert not panel.unsupported.isHidden()
    assert panel.unsupported.text() == "Unsupported mode (JT65): only FT8 and FT4 are supported"


@pytest.mark.usefixtures("qapp")
def test_supported_mode_hides_unsupported_message() -> None:
    panel = SlotPanel(Slot.FIRST)
    panel.show_slot(SlotView(occupied=(), free=(), decode_count=0), window_cycles=4, unsupported="JT65")
    panel.show_slot(SlotView(occupied=(), free=(), decode_count=0), window_cycles=4)
    assert panel.unsupported.isHidden()
    assert not panel.empty.isHidden()
