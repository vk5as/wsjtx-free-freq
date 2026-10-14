"""Decoder for the WSJT-X NetworkMessage format (big-endian QDataStream, schema 2 and 3).

Only the Heartbeat (0), Status (1), Decode (2) and Close (6) messages are decoded. Anything else, bad magic or a missing Id gives None.
Trailing fields that older WSJT-X versions do not send come back as None. A Decode missing any field gives None.
Configure (15) is encoded, never decoded: it is the only message this program sends.
"""

import struct
from dataclasses import dataclass

MAGIC = 0xADBCCBDA
HEARTBEAT = 0
STATUS = 1
DECODE = 2
CLOSE = 6
CONFIGURE = 15
_NULL = 0xFFFFFFFF


@dataclass(frozen=True)
class Heartbeat:
    """Heartbeat message: liveness of one WSJT-X instance."""

    id: str
    schema: int
    max_schema: int | None


@dataclass(frozen=True)
class Status:
    """Status message: the radio and audio state of one WSJT-X instance."""

    id: str
    schema: int
    dial_hz: int | None
    mode: str | None
    rx_df: int | None
    tx_df: int | None
    fast_mode: bool | None
    tr_period_s: int | None


@dataclass(frozen=True)
class Close:
    """Close message: the instance is shutting down, or has been asked to."""

    id: str
    schema: int


@dataclass(frozen=True)
class Decode:
    """Decode message: one message WSJT-X decoded. Time is ms since UTC midnight; mode "~" is FT8, "+" is FT4."""

    id: str
    schema: int
    new: bool
    time_ms: int
    snr_db: int
    delta_time_s: float
    delta_hz: int
    mode: str
    message: str
    low_confidence: bool
    off_air: bool


class _Reader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def _take(self, n: int) -> bytes | None:
        end = self._pos + n
        if end > len(self._data):
            self._pos = len(self._data)
            return None
        chunk = self._data[self._pos : end]
        self._pos = end
        return chunk

    def _uint(self, n: int) -> int | None:
        raw = self._take(n)
        return None if raw is None else int.from_bytes(raw, "big")

    def u8(self) -> int | None:
        return self._uint(1)

    def u32(self) -> int | None:
        value = self._uint(4)
        return None if value == _NULL else value

    def i32(self) -> int | None:
        raw = self._take(4)
        return None if raw is None else int.from_bytes(raw, "big", signed=True)

    def u64(self) -> int | None:
        return self._uint(8)

    def f64(self) -> float | None:
        raw = self._take(8)
        return None if raw is None else struct.unpack(">d", raw)[0]

    def boolean(self) -> bool | None:
        raw = self._take(1)
        return None if raw is None else raw != b"\x00"

    def utf8(self) -> str | None:
        length = self.u32()
        if length is None:
            return None
        raw = self._take(length)
        return None if raw is None else raw.decode("utf-8", errors="replace")


def decode(datagram: bytes) -> Heartbeat | Status | Decode | Close | None:
    """Return the Heartbeat, Status or Decode in a datagram, or None if it is not one."""
    reader = _Reader(datagram)
    if reader.u32() != MAGIC:
        return None
    schema = reader.u32()
    msg_type = reader.u32()
    msg_id = reader.utf8()
    if schema is None or msg_type is None or msg_id is None:
        return None
    if msg_type == HEARTBEAT:
        return Heartbeat(msg_id, schema, reader.u32())
    if msg_type == STATUS:
        return _status(reader, msg_id, schema)
    if msg_type == DECODE:
        return _decode(reader, msg_id, schema)
    return Close(msg_id, schema) if msg_type == CLOSE else None


def _decode(reader: _Reader, msg_id: str, schema: int) -> Decode | None:
    new = reader.boolean()
    time_ms = reader.u32()
    snr_db = reader.i32()
    delta_time_s = reader.f64()
    delta_hz = reader.u32()
    mode = reader.utf8()
    text = reader.utf8()
    low_confidence = reader.boolean()
    off_air = reader.boolean()
    if (
        new is None
        or time_ms is None
        or snr_db is None
        or delta_time_s is None
        or delta_hz is None
        or mode is None
        or text is None
        or low_confidence is None
        or off_air is None
    ):
        return None
    return Decode(msg_id, schema, new, time_ms, snr_db, delta_time_s, delta_hz, mode, text, low_confidence, off_air)


def _status(reader: _Reader, msg_id: str, schema: int) -> Status:
    dial_hz = reader.u64()
    mode = reader.utf8()
    for _ in range(3):  # DX call, report, Tx mode
        reader.utf8()
    for _ in range(3):  # Tx enabled, transmitting, decoding
        reader.boolean()
    rx_df = reader.u32()
    tx_df = reader.u32()
    for _ in range(3):  # DE call, DE grid, DX grid
        reader.utf8()
    reader.boolean()  # Tx watchdog
    reader.utf8()  # sub-mode
    fast_mode = reader.boolean()
    reader.u8()  # special operation mode
    reader.u32()  # frequency tolerance
    tr_period_s = reader.u32()
    return Status(msg_id, schema, dial_hz, mode, rx_df, tx_df, fast_mode, tr_period_s)


def encode_configure(schema: int, msg_id: str, *, rx_df: int, fast_mode: bool) -> bytes:
    """Configure that sets only Rx DF. Mode, submode, T/R period, DX call and grid are left empty or null."""
    return b"".join(
        [
            struct.pack(">II", MAGIC, schema),
            struct.pack(">I", CONFIGURE),
            _utf8(msg_id),
            _utf8(""),  # mode
            struct.pack(">I", _NULL),  # frequency tolerance
            _utf8(""),  # submode
            struct.pack(">?", fast_mode),
            struct.pack(">I", _NULL),  # T/R period
            struct.pack(">I", rx_df),
            _utf8(""),  # DX call
            _utf8(""),  # DX grid
            b"\x00",  # generate messages
        ]
    )


def _utf8(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack(">I", len(raw)) + raw
