from wsjtx_free_freq.engine import Slot
from wsjtx_free_freq.labels import NO_FREE_LOCATIONS, format_free_location, format_slot_title


def test_free_location_label_has_rank_and_offset_then_clearance_underneath() -> None:
    assert format_free_location(1, 1500, 40) == "1.  1500 Hz\n±40 Hz clear"


def test_free_location_label_keeps_two_digit_rank() -> None:
    assert format_free_location(10, 200, 12) == "10.  200 Hz\n±12 Hz clear"


def test_slot_title_names_the_slot_its_parity_and_the_window() -> None:
    assert format_slot_title(Slot.FIRST, 3, 4) == "1st slot (even, 3 decodes, last 4 cycles)"
    assert format_slot_title(Slot.SECOND, 0, 4) == "2nd slot (odd, 0 decodes, last 4 cycles)"


def test_empty_state_text() -> None:
    assert NO_FREE_LOCATIONS == "No free locations"
