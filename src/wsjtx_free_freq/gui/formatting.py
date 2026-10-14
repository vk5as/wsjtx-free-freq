"""Text for the header: frequencies, modes and offsets as the operator reads them."""

MISSING = "-"


def format_dial(hz: int | None) -> str:
    """Dial frequency as MHz with digits grouped in threes, e.g. 14074000 -> '14.074 000 MHz'."""
    if hz is None:
        return MISSING
    mhz, rest = divmod(hz, 1_000_000)
    khz, hz_part = divmod(rest, 1000)
    return f"{mhz}.{khz:03d} {hz_part:03d} MHz"
