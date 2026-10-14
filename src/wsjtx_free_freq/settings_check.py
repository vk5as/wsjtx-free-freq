"""Checks on settings the Settings dialog offers, as plain messages. No widgets, so tests run without Qt.

Bounds come from persistence, so a value that passes here also loads back unchanged.
"""

import ipaddress

from wsjtx_free_freq import persistence
from wsjtx_free_freq.engine import WIDEST_SIGNAL_HZ, Settings
from wsjtx_free_freq.persistence import AppSettings


def _address_problem(address: str) -> str | None:
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return f"UDP address {address!r} is not an IP address"
    return None


def _group_problem(group: str) -> str | None:
    if group == "":
        return None
    try:
        address = ipaddress.ip_address(group)
    except ValueError:
        address = None
    if isinstance(address, ipaddress.IPv4Address) and address.is_multicast:
        return None
    return f"Multicast group {group!r} is not an IPv4 multicast address"


def _range_problem(name: str, value: float, low: float, high: float) -> str | None:
    if low <= value <= high:
        return None
    return f"{name} must be between {low:g} and {high:g}"


def problems(engine: Settings, app: AppSettings) -> tuple[str, ...]:
    """Every problem with these values, one message each; empty when they can be applied and saved."""
    found: list[str | None] = [
        _address_problem(app.udp_address),
        _group_problem(app.multicast_group),
        _range_problem("UDP port", app.udp_port, persistence.MIN_PORT, persistence.MAX_PORT),
        _range_problem("Search low", engine.search_low_hz, 0, persistence.MAX_AUDIO_HZ),
        _range_problem("Search high", engine.search_high_hz, 0, persistence.MAX_AUDIO_HZ),
        _range_problem("Guard band", engine.guard_hz, 0, persistence.MAX_GUARD_HZ),
        _range_problem(
            "Occupancy window", engine.window_cycles, persistence.MIN_WINDOW_CYCLES, persistence.MAX_WINDOW_CYCLES
        ),
        _range_problem("Minimum spacing", engine.min_spacing_widths, 0.0, persistence.MAX_SPACING_WIDTHS),
        _range_problem("Minimum clearance", engine.min_clearance_hz, 0, persistence.MAX_CLEARANCE_HZ),
        _range_problem(
            "Strong signal SNR", engine.strong_snr_db, persistence.MIN_STRONG_SNR_DB, persistence.MAX_STRONG_SNR_DB
        ),
        _range_problem("Strong signal extra guard", engine.strong_extra_hz, 0, persistence.MAX_STRONG_EXTRA_HZ),
    ]
    if engine.search_low_hz >= engine.search_high_hz:
        found.append("Search low must be below search high")
    elif engine.search_high_hz - engine.search_low_hz < WIDEST_SIGNAL_HZ:
        found.append(f"Search range must be at least {WIDEST_SIGNAL_HZ} Hz wide to fit the widest signal")
    return tuple(message for message in found if message is not None)
