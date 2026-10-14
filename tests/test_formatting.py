from wsjtx_free_freq.gui.formatting import format_dial


def test_dial_frequency_is_shown_in_mhz_with_grouped_digits() -> None:
    assert format_dial(14074000) == "14.074 000 MHz"


def test_dial_frequency_keeps_sub_kilohertz_digits() -> None:
    assert format_dial(7074123) == "7.074 123 MHz"


def test_missing_dial_frequency_shows_a_dash() -> None:
    assert format_dial(None) == "-"
