import socket
from collections.abc import Generator
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.engine import Settings
from wsjtx_free_freq.gui.app import startup
from wsjtx_free_freq.persistence import AppSettings, save_settings


@pytest.fixture
def clean_app(qapp: QApplication) -> Generator[QApplication, None, None]:
    yield qapp
    qapp.setStyleSheet("")
    qapp.setPalette(QPalette())


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
    return port


@pytest.mark.usefixtures("clean_app")
def test_startup_uses_the_stored_port_engine_settings_and_theme(tmp_path: Path, clean_app: QApplication) -> None:
    port = _free_port()
    engine_settings = Settings(guard_hz=17, window_cycles=3)
    store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    save_settings(store, engine_settings, AppSettings(udp_port=port, theme="Dark"))

    window = startup(clean_app, store)
    try:
        assert window.listener.local_port() == port
        assert window.engine.settings == engine_settings
        assert clean_app.property("wsjtx_free_freq_theme") == "Dark"
    finally:
        window.close()


@pytest.mark.usefixtures("clean_app")
def test_startup_with_nothing_stored_uses_defaults(tmp_path: Path, clean_app: QApplication) -> None:
    store = QSettings(str(tmp_path / "empty.ini"), QSettings.Format.IniFormat)
    window = startup(clean_app, store)
    try:
        assert window.engine.settings == Settings()
        assert clean_app.property("wsjtx_free_freq_theme") == "System"
    finally:
        window.close()
