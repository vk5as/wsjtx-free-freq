from dataclasses import replace

from wsjtx_free_freq import persistence
from wsjtx_free_freq.engine import Settings
from wsjtx_free_freq.persistence import AppSettings
from wsjtx_free_freq.settings_check import problems


def test_defaults_have_no_problems() -> None:
    assert problems(Settings(), AppSettings()) == ()


def test_low_not_below_high_is_a_problem() -> None:
    assert problems(replace(Settings(), search_low_hz=2800, search_high_hz=2800), AppSettings()) != ()
    assert problems(replace(Settings(), search_low_hz=2900, search_high_hz=2800), AppSettings()) != ()


def test_search_range_must_stay_within_audio() -> None:
    assert problems(replace(Settings(), search_high_hz=persistence.MAX_AUDIO_HZ + 1), AppSettings()) != ()
    assert problems(replace(Settings(), search_low_hz=-1), AppSettings()) != ()


def test_port_must_be_in_range() -> None:
    assert problems(Settings(), replace(AppSettings(), udp_port=persistence.MIN_PORT - 1)) != ()
    assert problems(Settings(), replace(AppSettings(), udp_port=persistence.MAX_PORT + 1)) != ()
    assert problems(Settings(), replace(AppSettings(), udp_port=persistence.MIN_PORT)) == ()
    assert problems(Settings(), replace(AppSettings(), udp_port=persistence.MAX_PORT)) == ()


def test_address_must_be_an_ip_address() -> None:
    assert problems(Settings(), replace(AppSettings(), udp_address="not an address")) != ()
    assert problems(Settings(), replace(AppSettings(), udp_address="")) != ()
    assert problems(Settings(), replace(AppSettings(), udp_address="192.168.1.20")) == ()


def test_guard_window_spacing_and_clearance_use_persistence_bounds() -> None:
    assert problems(replace(Settings(), guard_hz=persistence.MAX_GUARD_HZ + 1), AppSettings()) != ()
    assert problems(replace(Settings(), guard_hz=-1), AppSettings()) != ()
    assert problems(replace(Settings(), window_cycles=persistence.MIN_WINDOW_CYCLES - 1), AppSettings()) != ()
    assert problems(replace(Settings(), window_cycles=persistence.MAX_WINDOW_CYCLES + 1), AppSettings()) != ()
    assert problems(replace(Settings(), min_spacing_widths=persistence.MAX_SPACING_WIDTHS + 0.1), AppSettings()) != ()
    assert problems(replace(Settings(), min_spacing_widths=-0.1), AppSettings()) != ()
    assert problems(replace(Settings(), min_clearance_hz=persistence.MAX_CLEARANCE_HZ + 1), AppSettings()) != ()
    assert problems(replace(Settings(), min_clearance_hz=-1), AppSettings()) != ()


def test_every_bound_edge_is_accepted() -> None:
    edge = Settings(
        search_low_hz=0,
        search_high_hz=persistence.MAX_AUDIO_HZ,
        guard_hz=persistence.MAX_GUARD_HZ,
        window_cycles=persistence.MAX_WINDOW_CYCLES,
        min_spacing_widths=persistence.MAX_SPACING_WIDTHS,
        min_clearance_hz=persistence.MAX_CLEARANCE_HZ,
    )
    assert problems(edge, AppSettings()) == ()
    low = replace(edge, guard_hz=0, window_cycles=persistence.MIN_WINDOW_CYCLES, min_spacing_widths=0.0)
    assert problems(replace(low, min_clearance_hz=0), AppSettings()) == ()


def test_problems_are_reported_per_field() -> None:
    bad = problems(replace(Settings(), search_low_hz=3000), replace(AppSettings(), udp_port=0))
    assert len(bad) == 2


def test_strong_signal_options_use_persistence_bounds() -> None:
    assert problems(replace(Settings(), strong_snr_db=persistence.MIN_STRONG_SNR_DB - 1), AppSettings()) != ()
    assert problems(replace(Settings(), strong_snr_db=persistence.MAX_STRONG_SNR_DB + 1), AppSettings()) != ()
    assert problems(replace(Settings(), strong_extra_hz=-1), AppSettings()) != ()
    assert problems(replace(Settings(), strong_extra_hz=persistence.MAX_STRONG_EXTRA_HZ + 1), AppSettings()) != ()
    edge = replace(
        Settings(),
        strong_snr_db=persistence.MAX_STRONG_SNR_DB,
        strong_extra_hz=persistence.MAX_STRONG_EXTRA_HZ,
    )
    assert problems(edge, AppSettings()) == ()


def test_multicast_group_is_empty_or_a_multicast_address() -> None:
    assert problems(Settings(), replace(AppSettings(), multicast_group="")) == ()
    assert problems(Settings(), replace(AppSettings(), multicast_group="239.255.0.1")) == ()
    assert problems(Settings(), replace(AppSettings(), multicast_group="192.168.1.1")) != ()
    assert problems(Settings(), replace(AppSettings(), multicast_group="garbage")) != ()


def test_search_range_must_be_as_wide_as_the_widest_signal() -> None:
    assert problems(replace(Settings(), search_low_hz=200, search_high_hz=282), AppSettings()) != ()
    assert problems(replace(Settings(), search_low_hz=200, search_high_hz=283), AppSettings()) == ()


def test_multicast_group_must_be_ipv4() -> None:
    assert problems(Settings(), replace(AppSettings(), multicast_group="ff02::1")) != ()
