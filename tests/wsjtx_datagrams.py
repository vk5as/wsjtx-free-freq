"""Encoder for WSJT-X NetworkMessage datagrams, used by tests to build real wire bytes.

Written independently of the package's decoder so tests check the decoder against the WSJT-X layout.
"""

import struct

MAGIC = 0xADBCCBDA
HEARTBEAT = 0
STATUS = 1
CLEAR = 3
CLOSE = 6
DECODE = 2
NULL_U32 = 0xFFFFFFFF


def u8(value: int) -> bytes:
    return struct.pack(">B", value)


def u32(value: int) -> bytes:
    return struct.pack(">I", value)


def i32(value: int) -> bytes:
    return struct.pack(">i", value)


def u64(value: int) -> bytes:
    return struct.pack(">Q", value)


def double(value: float) -> bytes:
    return struct.pack(">d", value)


def boolean(value: bool) -> bytes:
    return b"\x01" if value else b"\x00"


def utf8(value: str | None) -> bytes:
    """QByteArray-style utf8: length then bytes, 0xFFFFFFFF for null."""
    if value is None:
        return u32(NULL_U32)
    raw = value.encode("utf-8")
    return u32(len(raw)) + raw


def message(msg_type: int, msg_id: str | None, *fields: bytes, schema: int = 3, magic: int = MAGIC) -> bytes:
    """Header followed by the given already-encoded fields."""
    return u32(magic) + u32(schema) + u32(msg_type) + utf8(msg_id) + b"".join(fields)


def clear_message(msg_id: str, *, window: int = 0, schema: int = 3) -> bytes:
    """Clear (type 3): window 0 is Band Activity, 1 is Rx Frequency, 2 is both."""
    return message(CLEAR, msg_id, u8(window), schema=schema)


def heartbeat(
    msg_id: str,
    *,
    max_schema: int = 3,
    version: str = "2.7.0",
    revision: str = "abc123",
    schema: int = 3,
) -> bytes:
    return message(HEARTBEAT, msg_id, u32(max_schema), utf8(version), utf8(revision), schema=schema)


def status_fields(  # noqa: PLR0913
    *,
    dial_hz: int = 14074000,
    mode: str | None = "FT8",
    rx_df: int = 1500,
    tx_df: int = 1000,
    fast_mode: bool = False,
    tr_period: int = 15,
) -> list[bytes]:
    """Status fields in WSJT-X order. Callers slice the list to model older senders."""
    return [
        u64(dial_hz),
        utf8(mode),
        utf8("K1ABC"),  # DX call
        utf8("-10"),  # report
        utf8("FT8"),  # Tx mode
        boolean(False),  # Tx enabled
        boolean(False),  # transmitting
        boolean(True),  # decoding
        u32(rx_df),
        u32(tx_df),
        utf8("VK5AS"),  # DE call
        utf8("PF95"),  # DE grid
        utf8("FN20"),  # DX grid
        boolean(False),  # Tx watchdog
        utf8(""),  # sub-mode
        boolean(fast_mode),
        u8(0),  # special operation mode
        u32(NULL_U32),  # frequency tolerance
        u32(tr_period),
        utf8("default"),  # configuration name
        utf8("CQ K1ABC"),  # Tx message
    ]


def decode_message(  # noqa: PLR0913
    msg_id: str = "WSJT-X",
    *,
    time_ms: int = 0,
    snr: int = -10,
    delta_hz: int = 1500,
    mode: str | None = "~",
    text: str = "CQ K1ABC FN20",
    new: bool = True,
    delta_time: float = 0.1,
    low_confidence: bool = False,
    off_air: bool = False,
    schema: int = 3,
) -> bytes:
    """Decode (type 2): Time is ms since UTC midnight, mode "~" is FT8 and "+" is FT4."""
    return message(
        DECODE,
        msg_id,
        boolean(new),
        u32(time_ms),
        i32(snr),
        double(delta_time),
        u32(delta_hz),
        utf8(mode),
        utf8(text),
        boolean(low_confidence),
        boolean(off_air),
        schema=schema,
    )


def status(  # noqa: PLR0913
    msg_id: str,
    *,
    dial_hz: int = 14074000,
    mode: str | None = "FT8",
    rx_df: int = 1500,
    tx_df: int = 1000,
    fast_mode: bool = False,
    tr_period: int = 15,
    schema: int = 3,
) -> bytes:
    fields = status_fields(
        dial_hz=dial_hz, mode=mode, rx_df=rx_df, tx_df=tx_df, fast_mode=fast_mode, tr_period=tr_period
    )
    return message(STATUS, msg_id, *fields, schema=schema)


CONFIGURE = 15


def decode_configure(datagram: bytes) -> dict[str, object]:
    """Read a Configure back field by field, in WSJT-X order. Null utf8 and quint32 read as None."""
    pos = 0

    def take(n: int) -> bytes:
        nonlocal pos
        chunk = datagram[pos : pos + n]
        pos += n
        return chunk

    def read_u32() -> int | None:
        value = int.from_bytes(take(4), "big")
        return None if value == NULL_U32 else value

    def read_utf8() -> str | None:
        length = read_u32()
        return None if length is None else take(length).decode("utf-8")

    fields: dict[str, object] = {}
    fields["magic"] = read_u32()
    fields["schema"] = read_u32()
    fields["type"] = read_u32()
    fields["id"] = read_utf8()
    fields["mode"] = read_utf8()
    fields["frequency_tolerance"] = int.from_bytes(take(4), "big")
    fields["submode"] = read_utf8()
    fields["fast_mode"] = take(1) != b"\x00"
    fields["tr_period"] = int.from_bytes(take(4), "big")
    fields["rx_df"] = int.from_bytes(take(4), "big")
    fields["dx_call"] = read_utf8()
    fields["dx_grid"] = read_utf8()
    fields["generate_messages"] = take(1) != b"\x00"
    fields["trailing_bytes"] = len(datagram) - pos
    return fields
