"""Encoder for the WSJT-X NetworkMessage Heartbeat and Status, the mirror of codec.py.

Used by scripts/fake_wsjtx.py and tests. Field order follows WSJT-X's NetworkMessage.hpp.
"""

import struct

from wsjtx_free_freq.codec import HEARTBEAT, MAGIC, STATUS

_NULL = 0xFFFFFFFF
_TRUE = b"\x01"
_FALSE = b"\x00"
VERSION = "2.7.0"
REVISION = "abc123"


def _u8(value: int) -> bytes:
    return struct.pack(">B", value)


def _u32(value: int) -> bytes:
    return struct.pack(">I", value)


def _u64(value: int) -> bytes:
    return struct.pack(">Q", value)


def _utf8(value: str) -> bytes:
    raw = value.encode("utf-8")
    return _u32(len(raw)) + raw


def _message(msg_type: int, msg_id: str, *fields: bytes, schema: int = 3) -> bytes:
    return _u32(MAGIC) + _u32(schema) + _u32(msg_type) + _utf8(msg_id) + b"".join(fields)


def heartbeat(msg_id: str, *, schema: int = 3) -> bytes:
    """Encode a Heartbeat for instance `msg_id`."""
    return _message(HEARTBEAT, msg_id, _u32(schema), _utf8(VERSION), _utf8(REVISION), schema=schema)


def status(  # noqa: PLR0913
    msg_id: str,
    *,
    dial_hz: int = 14074000,
    mode: str = "FT8",
    rx_df: int = 1500,
    tx_df: int = 1000,
    fast_mode: bool = False,
    tr_period: int = 15,
    schema: int = 3,
) -> bytes:
    """Encode a Status for instance `msg_id`, with the fields a current WSJT-X sends."""
    fields = (
        _u64(dial_hz),
        _utf8(mode),
        _utf8("K1ABC"),  # DX call
        _utf8("-10"),  # report
        _utf8("FT8"),  # Tx mode
        _FALSE,  # Tx enabled
        _FALSE,  # transmitting
        _TRUE,  # decoding
        _u32(rx_df),
        _u32(tx_df),
        _utf8("VK5AS"),  # DE call
        _utf8("PF95"),  # DE grid
        _utf8("FN20"),  # DX grid
        _FALSE,  # Tx watchdog
        _utf8(""),  # sub-mode
        (_TRUE if fast_mode else _FALSE),
        _u8(0),  # special operation mode
        _u32(_NULL),  # frequency tolerance
        _u32(tr_period),
        _utf8("default"),  # configuration name
        _utf8("CQ K1ABC"),  # Tx message
    )
    return _message(STATUS, msg_id, *fields, schema=schema)
