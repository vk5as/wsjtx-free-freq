"""Settings persistence: engine and app settings to and from QSettings. No widgets, no sockets.

Stored values that are missing, of the wrong type, or out of range fall back to the default for that setting.
"""

import ipaddress
import math
from dataclasses import dataclass

from PyQt6.QtCore import QSettings

from wsjtx_free_freq.engine import Settings

ORGANISATION = "VK5AS"
APPLICATION = "wsjtx-free-freq"

DEFAULT_ADDRESS = "127.0.0.1"
DEFAULT_PORT = 2237
DEFAULT_THEME = "System"  # gui.themes.DEFAULT_THEME; a test keeps the two equal

MIN_PORT = 1
MAX_PORT = 65535
MAX_AUDIO_HZ = 5000
MAX_GUARD_HZ = 500
MIN_WINDOW_CYCLES = 1
MAX_WINDOW_CYCLES = 100
MAX_SPACING_WIDTHS = 100.0
MAX_CLEARANCE_HZ = 1000


@dataclass(frozen=True)
class AppSettings:
    """Settings the engine does not read: where the listener binds and which theme is shown."""

    udp_address: str = DEFAULT_ADDRESS
    udp_port: int = DEFAULT_PORT
    multicast_group: str = ""  # empty means unicast only
    theme: str = DEFAULT_THEME


def default_store() -> QSettings:
    """Return the per-user store for this application, in the platform's native format."""
    return QSettings(ORGANISATION, APPLICATION)


def _to_int(raw: object) -> int:
    if isinstance(raw, bool):
        raise TypeError(raw)
    return int(str(raw))


def _to_float(raw: object) -> float:
    if isinstance(raw, bool):
        raise TypeError(raw)
    value = float(str(raw))
    if not math.isfinite(value):
        raise ValueError(raw)
    return value


def _int(store: QSettings, key: str, default: int, low: int, high: int) -> int:
    try:
        value = _to_int(store.value(key))
    except (TypeError, ValueError):
        return default
    return value if low <= value <= high else default


def _float(store: QSettings, key: str, default: float, low: float, high: float) -> float:
    try:
        value = _to_float(store.value(key))
    except (TypeError, ValueError):
        return default
    return value if low <= value <= high else default


def _bool(store: QSettings, key: str, *, default: bool) -> bool:
    raw = store.value(key)
    if isinstance(raw, bool):
        return raw
    if raw == "true":
        return True
    if raw == "false":
        return False
    return default


def _text(store: QSettings, key: str, default: str) -> str:
    raw = store.value(key)
    return raw if isinstance(raw, str) else default


def _address(store: QSettings, key: str, default: str) -> str:
    try:
        return str(ipaddress.ip_address(_text(store, key, "")))
    except ValueError:
        return default


def _multicast(store: QSettings, key: str, default: str) -> str:
    raw = _text(store, key, default)
    if raw == "":
        return ""
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return default
    return str(address) if address.is_multicast else default


def load_engine_settings(store: QSettings) -> Settings:
    """Load the engine settings as stored, with defaults for anything missing or bad."""
    d = Settings()
    low = _int(store, "search_low_hz", d.search_low_hz, 0, MAX_AUDIO_HZ)
    high = _int(store, "search_high_hz", d.search_high_hz, 0, MAX_AUDIO_HZ)
    if low >= high:
        low, high = d.search_low_hz, d.search_high_hz
    return Settings(
        search_low_hz=low,
        search_high_hz=high,
        guard_hz=_int(store, "guard_hz", d.guard_hz, 0, MAX_GUARD_HZ),
        window_cycles=_int(store, "window_cycles", d.window_cycles, MIN_WINDOW_CYCLES, MAX_WINDOW_CYCLES),
        min_spacing_widths=_float(store, "min_spacing_widths", d.min_spacing_widths, 0.0, MAX_SPACING_WIDTHS),
        min_clearance_hz=_int(store, "min_clearance_hz", d.min_clearance_hz, 0, MAX_CLEARANCE_HZ),
        strong_enabled=_bool(store, "strong_enabled", default=d.strong_enabled),
        strong_snr_db=_int(store, "strong_snr_db", d.strong_snr_db, -30, 50),
        strong_extra_hz=_int(store, "strong_extra_hz", d.strong_extra_hz, 0, 500),
        heartbeat_timeout_s=_float(store, "heartbeat_timeout_s", d.heartbeat_timeout_s, 1.0, 3600.0),
    )


def load_app_settings(store: QSettings) -> AppSettings:
    """Load the app settings as stored, with defaults for anything missing or bad."""
    d = AppSettings()
    theme = _text(store, "theme", d.theme)
    return AppSettings(
        udp_address=_address(store, "udp_address", d.udp_address),
        udp_port=_int(store, "udp_port", d.udp_port, MIN_PORT, MAX_PORT),
        multicast_group=_multicast(store, "multicast_group", d.multicast_group),
        theme=theme if theme.strip() else d.theme,
    )


def load_settings(store: QSettings) -> tuple[Settings, AppSettings]:
    """Both sets of settings, as stored, with defaults for anything missing or bad."""
    return load_engine_settings(store), load_app_settings(store)


def save_settings(store: QSettings, engine: Settings, app: AppSettings) -> None:
    """Write both sets of settings and flush them to the store."""
    store.setValue("search_low_hz", engine.search_low_hz)
    store.setValue("search_high_hz", engine.search_high_hz)
    store.setValue("guard_hz", engine.guard_hz)
    store.setValue("window_cycles", engine.window_cycles)
    store.setValue("min_spacing_widths", engine.min_spacing_widths)
    store.setValue("min_clearance_hz", engine.min_clearance_hz)
    store.setValue("strong_enabled", engine.strong_enabled)
    store.setValue("strong_snr_db", engine.strong_snr_db)
    store.setValue("strong_extra_hz", engine.strong_extra_hz)
    store.setValue("heartbeat_timeout_s", engine.heartbeat_timeout_s)
    store.setValue("udp_address", app.udp_address)
    store.setValue("udp_port", app.udp_port)
    store.setValue("multicast_group", app.multicast_group)
    store.setValue("theme", app.theme)
    store.sync()
