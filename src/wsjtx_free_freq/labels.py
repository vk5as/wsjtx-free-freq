"""Text for free location buttons and slot titles. Pure, so it is tested outside the gui package."""

from wsjtx_free_freq.engine import Slot

NO_FREE_LOCATIONS = "No free locations"
_PARITY = {Slot.FIRST: "even", Slot.SECOND: "odd"}


def format_free_location(rank: int, offset_hz: int, clearance_hz: int) -> str:
    """Button label: rank and offset on the first line, clearance underneath."""
    return f"{rank}.  {offset_hz} Hz\n±{clearance_hz} Hz clear"


def format_slot_title(slot: Slot, decode_count: int, window_cycles: int) -> str:
    """Slot name, its parity and the occupancy it rests on, e.g. '1st slot (even, 3 decodes, last 4 cycles)'."""
    return f"{slot.value} slot ({_PARITY[slot]}, {decode_count} decodes, last {window_cycles} cycles)"
