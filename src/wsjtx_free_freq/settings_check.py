"""Checks on settings the Settings dialog offers, as plain messages. No widgets, so tests run without Qt.

Bounds come from persistence, so a value that passes here also loads back unchanged.
"""

import ipaddress

from wsjtx_free_freq import persistence
from wsjtx_free_freq.engine import Settings
from wsjtx_free_freq.persistence import AppSettings


def _address_problem(address: str) -> str | None:
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return f"UDP address {address!r} is not an IP address"
    return None


def _range_problem(name: str, value: float, low: float, high: float) -> str | None:
    if low <= value <= high:
        return None
    return f"{name} must be between {low:g} and {high:g}"


def problems(engine: Settings, app: AppSettings) -> tuple[str, ...]:
    """Every problem with these values, one message each; empty when they can be applied and saved."""
    found: list[str | None] = [
        _address_problem(app.udp_address),
        _range_problem("UDP port", app.udp_port, persistence.MIN_PORT, persistence.MAX_PORT),
        _range_problem("Search low", engine.search_low_hz, 0, persistence.MAX_AUDIO_HZ),
        _range_problem("Search high", engine.search_high_hz, 0, persistence.MAX_AUDIO_HZ),
        _range_problem("Guard band", engine.guard_hz, 0, persistence.MAX_GUARD_HZ),
        _range_problem(
            "Occupancy window", engine.window_cycles, persistence.MIN_WINDOW_CYCLES, persistence.MAX_WINDOW_CYCLES
        ),
        _range_problem("Minimum spacing", engine.min_spacing_widths, 0.0, persistence.MAX_SPACING_WIDTHS),
        _range_problem("Minimum clearance", engine.min_clearance_hz, 0, persistence.MAX_CLEARANCE_HZ),
    ]
    if engine.search_low_hz >= engine.search_high_hz:
        found.append("Search low must be below search high")
    return tuple(message for message in found if message is not None)
