from dataclasses import replace
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from wsjtx_free_freq import persistence
from wsjtx_free_freq.engine import Settings
from wsjtx_free_freq.gui import themes
from wsjtx_free_freq.persistence import AppSettings


@pytest.fixture
def ini_path(tmp_path: Path) -> Path:
    return tmp_path / "wsjtx-free-freq.ini"


def _store(path: Path) -> QSettings:
    return QSettings(str(path), QSettings.Format.IniFormat)


def _changed_engine() -> Settings:
    return Settings(
        search_low_hz=300,
        search_high_hz=2400,
        guard_hz=15,
        window_cycles=6,
        min_spacing_widths=2.5,
        min_clearance_hz=12,
        strong_enabled=True,
        strong_snr_db=-5,
        strong_extra_hz=25,
        heartbeat_timeout_s=60.5,
    )


def _changed_app() -> AppSettings:
    return AppSettings(udp_address="192.168.1.20", udp_port=2250, multicast_group="239.255.0.1", theme="Dark")


def test_defaults_when_nothing_is_stored(ini_path: Path) -> None:
    assert persistence.load_settings(_store(ini_path)) == (Settings(), AppSettings())


def test_values_round_trip_through_an_ini_file(ini_path: Path) -> None:
    persistence.save_settings(_store(ini_path), _changed_engine(), _changed_app())
    assert persistence.load_settings(_store(ini_path)) == (_changed_engine(), _changed_app())


def test_default_settings_round_trip_too(ini_path: Path) -> None:
    persistence.save_settings(_store(ini_path), Settings(), AppSettings())
    assert persistence.load_settings(_store(ini_path)) == (Settings(), AppSettings())


def test_empty_multicast_group_round_trips_as_unicast(ini_path: Path) -> None:
    persistence.save_settings(_store(ini_path), Settings(), AppSettings(multicast_group=""))
    assert persistence.load_app_settings(_store(ini_path)).multicast_group == ""


def test_saved_file_is_plain_ini_text(ini_path: Path) -> None:
    persistence.save_settings(_store(ini_path), Settings(), AppSettings(udp_port=2250))
    text = ini_path.read_text()
    assert "[General]" in text
    assert "udp_port=2250" in text


@pytest.mark.parametrize(
    ("key", "raw"),
    [
        ("udp_port", "not a port"),
        ("udp_port", "0"),
        ("udp_port", "65536"),
        ("udp_port", "2237.5"),
        ("udp_address", "not an address"),
        ("udp_address", "999.1.1.1"),
        ("multicast_group", "192.168.1.1"),
        ("multicast_group", "garbage"),
        ("theme", "   "),
        ("guard_hz", "-1"),
        ("guard_hz", "lots"),
        ("guard_hz", "501"),
        ("window_cycles", "0"),
        ("min_spacing_widths", "nan"),
        ("min_spacing_widths", "inf"),
        ("min_spacing_widths", "-2"),
        ("heartbeat_timeout_s", "0.5"),
        ("strong_enabled", "maybe"),
        ("strong_snr_db", "1e9"),
    ],
)
def test_bad_stored_value_falls_back_to_its_default(ini_path: Path, key: str, raw: str) -> None:
    store = _store(ini_path)
    store.setValue(key, raw)
    store.sync()
    engine, app = persistence.load_settings(_store(ini_path))
    assert (engine, app) == (Settings(), AppSettings())


def test_bad_value_does_not_disturb_good_neighbours(ini_path: Path) -> None:
    store = _store(ini_path)
    persistence.save_settings(store, _changed_engine(), _changed_app())
    store.setValue("guard_hz", "junk")
    store.setValue("udp_port", 0)
    store.sync()
    engine, app = persistence.load_settings(_store(ini_path))
    assert engine == replace(_changed_engine(), guard_hz=Settings().guard_hz)
    assert app == replace(_changed_app(), udp_port=AppSettings().udp_port)


def test_hand_edited_ini_with_garbage_falls_back(ini_path: Path) -> None:
    ini_path.write_text("[General]\nguard_hz=abc\nstrong_enabled=2\nudp_port=\nwindow_cycles=7\n")
    engine, app = persistence.load_settings(_store(ini_path))
    assert engine.guard_hz == Settings().guard_hz
    assert engine.strong_enabled == Settings().strong_enabled
    assert app.udp_port == AppSettings().udp_port
    assert engine.window_cycles == 7


def test_inverted_search_range_resets_both_ends(ini_path: Path) -> None:
    store = _store(ini_path)
    store.setValue("search_low_hz", 2000)
    store.setValue("search_high_hz", 1000)
    store.sync()
    engine = persistence.load_engine_settings(_store(ini_path))
    assert (engine.search_low_hz, engine.search_high_hz) == (Settings().search_low_hz, Settings().search_high_hz)


def test_theme_default_matches_gui_theme_default() -> None:
    assert persistence.DEFAULT_THEME == themes.DEFAULT_THEME


def test_default_store_is_the_vk5as_application_store() -> None:
    store = persistence.default_store()
    assert store.organizationName() == "VK5AS"
    assert store.applicationName() == "wsjtx-free-freq"


def test_hand_written_bool_and_bool_in_a_number_field(ini_path: Path) -> None:
    ini_path.write_text("[General]\nstrong_enabled=true\nguard_hz=true\nstrong_extra_hz=false\n")
    engine = persistence.load_engine_settings(_store(ini_path))
    assert engine.strong_enabled is True
    assert engine.guard_hz == Settings().guard_hz
    assert engine.strong_extra_hz == Settings().strong_extra_hz


def test_stored_false_reads_back_as_false(ini_path: Path) -> None:
    store = _store(ini_path)
    store.setValue("strong_enabled", False)
    store.setValue("min_clearance_hz", True)
    store.sync()
    engine = persistence.load_engine_settings(_store(ini_path))
    assert engine.strong_enabled is False
    assert engine.min_clearance_hz == Settings().min_clearance_hz
