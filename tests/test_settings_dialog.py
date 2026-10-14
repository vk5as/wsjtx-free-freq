import socket
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from wsjtx_free_freq import persistence
from wsjtx_free_freq.codec import encode_decode, encode_heartbeat, encode_status
from wsjtx_free_freq.engine import FreeLocation, Settings, Slot
from wsjtx_free_freq.gui import themes
from wsjtx_free_freq.gui.main_window import MainWindow
from wsjtx_free_freq.gui.settings_dialog import SettingsDialog
from wsjtx_free_freq.persistence import AppSettings

SENDER = ("127.0.0.1", 50000)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _ok_enabled(dialog: SettingsDialog) -> bool:
    button = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert button is not None
    return button.isEnabled()


def _pump(app: QApplication, done: Callable[[], bool], timeout_s: float = 3.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture(autouse=True)
def warnings(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record message boxes instead of blocking on them."""
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: shown.append(text))
    return shown


@pytest.fixture
def window() -> Iterator[MainWindow]:
    win = MainWindow(listen_port=_free_port())
    yield win
    win.close()


@pytest.fixture
def ini_store(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_dialog_shows_the_current_values() -> None:
    dialog = SettingsDialog(Settings(guard_hz=15), AppSettings(udp_port=2250))
    assert dialog.port.value() == 2250
    assert dialog.guard.value() == 15
    assert dialog.address.text() == "127.0.0.1"


def test_values_keep_the_fields_the_dialog_does_not_show() -> None:
    engine = replace(Settings(), strong_enabled=True, heartbeat_timeout_s=60.0)
    app = AppSettings(multicast_group="239.255.0.1", theme="Dark")
    engine_out, app_out = SettingsDialog(engine, app).values()
    assert engine_out == engine
    assert app_out == app


def test_inverted_search_range_cannot_be_confirmed() -> None:
    dialog = SettingsDialog(Settings(), AppSettings())
    dialog.search_low.setValue(3000)
    dialog.search_high.setValue(2800)
    assert not _ok_enabled(dialog)
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_bad_address_cannot_be_confirmed() -> None:
    dialog = SettingsDialog(Settings(), AppSettings())
    dialog.address.setText("localhost")
    assert not _ok_enabled(dialog)
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.error.text() != ""


def test_valid_values_enable_ok_and_clear_the_error() -> None:
    dialog = SettingsDialog(Settings(), AppSettings())
    dialog.search_low.setValue(3000)
    dialog.search_high.setValue(2800)
    dialog.search_high.setValue(3500)
    assert _ok_enabled(dialog)
    assert dialog.error.text() == ""


def test_guard_band_change_updates_free_locations_immediately(window: MainWindow) -> None:
    now = time.monotonic()
    window.engine.receive(encode_heartbeat("WSJT-X"), SENDER, now)
    window.engine.receive(encode_status("WSJT-X", dial_hz=14074000, mode="FT8", rx_df=1500, tx_df=1000), SENDER, now)
    window.engine.receive(
        encode_decode("WSJT-X", time_ms=30_000, snr_db=-7, delta_hz=1000, text="CQ K1ABC FN20"), SENDER, now
    )

    def free_locations() -> tuple[FreeLocation, ...]:
        return window.engine.snapshot(now).instances[0].slots[Slot.FIRST].free

    before = free_locations()
    window.apply_settings(replace(window.engine.settings, guard_hz=200), window.app_settings)
    assert window.engine.settings.guard_hz == 200
    assert free_locations() != before


def test_changing_the_port_rebinds_and_receives_on_the_new_port(window: MainWindow) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    new_port = _free_port()
    window.apply_settings(window.engine.settings, replace(window.app_settings, udp_port=new_port))
    assert window.listener.local_port() == new_port

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.sendto(encode_heartbeat("WSJT-X"), ("127.0.0.1", new_port))
        _pump(app, lambda: window.engine.snapshot(time.monotonic()).instances != ())
    assert [inst.id for inst in window.engine.snapshot(time.monotonic()).instances] == ["WSJT-X"]


def test_a_port_that_is_taken_is_refused_and_the_old_one_kept(window: MainWindow, warnings: list[str]) -> None:
    old_port = window.listener.local_port()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken_port = int(taken.getsockname()[1])
        window.apply_settings(window.engine.settings, replace(window.app_settings, udp_port=taken_port))
    assert window.listener.local_port() == old_port
    assert window.app_settings.udp_port != taken_port
    assert len(warnings) == 1


def test_apply_saves_to_the_store(tmp_path: Path) -> None:
    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    win = MainWindow(listen_port=_free_port(), store=store)
    engine = replace(Settings(), guard_hz=25, min_clearance_hz=12)
    app_settings = replace(win.app_settings, theme="Dark")
    win.apply_settings(engine, app_settings)
    win.close()
    reread = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    assert persistence.load_settings(reread) == (engine, app_settings)


def test_cancel_changes_nothing(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    def cancelled(self: SettingsDialog) -> int:
        self.guard.setValue(99)
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(SettingsDialog, "exec", cancelled)
    before = window.engine.settings
    window.open_settings()
    assert window.engine.settings == before


def test_header_button_opens_the_dialog_and_ok_applies_it(
    ini_store: QSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow(listen_port=_free_port(), store=ini_store)

    def accepted(self: SettingsDialog) -> int:
        self.clearance.setValue(40)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(SettingsDialog, "exec", accepted)
    window.header.settings_button.click()
    assert window.engine.settings.min_clearance_hz == 40
    assert persistence.load_engine_settings(ini_store).min_clearance_hz == 40
    window.close()


def test_strong_signal_fields_follow_the_checkbox() -> None:
    dialog = SettingsDialog(Settings(strong_enabled=False), AppSettings())
    assert not dialog.strong_snr.isEnabled()
    assert not dialog.strong_extra.isEnabled()
    dialog.strong.setChecked(True)
    assert dialog.strong_snr.isEnabled()
    assert dialog.strong_extra.isEnabled()


def test_strong_signal_values_are_read_back() -> None:
    dialog = SettingsDialog(Settings(), AppSettings())
    dialog.strong.setChecked(True)
    dialog.strong_snr.setValue(-5)
    dialog.strong_extra.setValue(40)
    engine, _ = dialog.values()
    assert (engine.strong_enabled, engine.strong_snr_db, engine.strong_extra_hz) == (True, -5, 40)


def test_theme_dropdown_lists_every_registry_theme() -> None:
    dialog = SettingsDialog(Settings(), AppSettings())
    assert [dialog.theme.itemText(i) for i in range(dialog.theme.count())] == list(themes.THEMES)


def test_theme_dropdown_shows_and_returns_the_chosen_theme() -> None:
    dialog = SettingsDialog(Settings(), AppSettings(theme="Dark"))
    assert dialog.theme.currentText() == "Dark"
    dialog.theme.setCurrentText("Light")
    assert dialog.values()[1].theme == "Light"


def test_ok_applies_the_chosen_theme_immediately(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    def accepted(self: SettingsDialog) -> int:
        self.theme.setCurrentText("Light")
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(SettingsDialog, "exec", accepted)
    window.open_settings()
    assert app.property("wsjtx_free_freq_theme") == "Light"
    assert window.app_settings.theme == "Light"
