"""Fake WSJT-X sender: sends Heartbeat, Status and optionally FT8 Decode datagrams, and prints any Configure it gets back.

.venv/bin/python scripts/fake_wsjtx.py --port 2237 --dial-hz 14074000 --mode FT8 --decodes 10
"""

import argparse
import random
import socket
import struct
import sys
import time

from wsjtx_free_freq.codec import encode_decode, encode_heartbeat, encode_status

FT8_CYCLE_MS = 15_000
DAY_MS = 86_400_000
CALLS = ("K1ABC", "W1XYZ", "G4DEF", "JA2GHI", "VK3JKL", "DL5MNO")
LOOKBACK_CYCLES = 8  # spans both slots, so each slot gets decodes in its occupancy window
_CONFIGURE = 15
_HEADER_BYTES = 12  # magic, schema and type, each a uint32


def _skip_utf8(data: bytes, pos: int) -> int:
    length = int.from_bytes(data[pos : pos + 4], "big")
    return pos + 4 + length


def configure_rx_df(datagram: bytes) -> int | None:
    """Rx DF of a Configure, or None if the datagram is not one. Reads the fields in WSJT-X order."""
    if len(datagram) < _HEADER_BYTES or struct.unpack_from(">I", datagram, 8)[0] != _CONFIGURE:
        return None
    pos = _skip_utf8(datagram, _HEADER_BYTES)  # the instance id
    pos = _skip_utf8(datagram, pos)  # mode
    pos += 4  # frequency tolerance
    pos = _skip_utf8(datagram, pos)  # submode
    pos += 1 + 4  # fast mode, T/R period
    return int(struct.unpack_from(">I", datagram, pos)[0])


class FakeWsjtx:
    """One UDP socket for everything: it sends like WSJT-X, and the app's Configure replies arrive on it."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((host, port))
        self._sock.settimeout(0.0)  # never block; configures() polls

    @property
    def port(self) -> int:
        return int(self._sock.getsockname()[1])

    def close(self) -> None:
        self._sock.close()

    def send_once(  # noqa: PLR0913
        self,
        host: str,
        port: int,
        *,
        msg_id: str = "WSJT-X",
        dial_hz: int = 14074000,
        mode: str = "FT8",
        rx_df: int = 1500,
        tx_df: int = 1000,
    ) -> None:
        """Send one Heartbeat and one Status to host:port."""
        self._sock.sendto(encode_heartbeat(msg_id), (host, port))
        self._sock.sendto(encode_status(msg_id, dial_hz=dial_hz, mode=mode, rx_df=rx_df, tx_df=tx_df), (host, port))

    def send_decodes(self, host: str, port: int, *, count: int, msg_id: str = "WSJT-X", rng: random.Random) -> None:
        """Send `count` FT8 decodes at random audio offsets, in cycles from the last few, so both slots get some."""
        now_ms = int(time.time() * 1000)
        newest_cycle = now_ms // FT8_CYCLE_MS
        for _ in range(count):
            cycle = newest_cycle - rng.randrange(LOOKBACK_CYCLES)
            time_ms = (cycle * FT8_CYCLE_MS + rng.randrange(FT8_CYCLE_MS)) % DAY_MS  # ms since UTC midnight
            datagram = encode_decode(
                msg_id,
                time_ms=time_ms,
                snr_db=rng.randint(-20, 10),
                delta_hz=rng.randint(200, 2800),
                text=f"CQ {rng.choice(CALLS)} FN20",
            )
            self._sock.sendto(datagram, (host, port))

    def configures(self) -> list[int]:
        """Rx DF of every Configure received since the last call. Does not block."""
        rx_dfs: list[int] = []
        while True:
            try:
                datagram = self._sock.recv(65_535)
            except BlockingIOError:
                return rx_dfs
            rx_df = configure_rx_df(datagram)
            if rx_df is not None:
                rx_dfs.append(rx_df)
                sys.stdout.write(f"Configure received: Rx DF {rx_df} Hz\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2237)
    parser.add_argument("--id", default="WSJT-X", dest="msg_id")
    parser.add_argument("--dial-hz", type=int, default=14074000)
    parser.add_argument("--mode", default="FT8")
    parser.add_argument("--rx", type=int, default=1500, dest="rx_df")
    parser.add_argument("--tx", type=int, default=1000, dest="tx_df")
    parser.add_argument("--decodes", type=int, default=0, help="FT8 decodes to send each interval")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between sends; Ctrl-C to stop")
    args = parser.parse_args(argv)
    rng = random.Random()  # noqa: S311 - test traffic, not security
    fake = FakeWsjtx(args.host, 0)
    try:
        while True:
            fake.send_once(
                args.host,
                args.port,
                msg_id=args.msg_id,
                dial_hz=args.dial_hz,
                mode=args.mode,
                rx_df=args.rx_df,
                tx_df=args.tx_df,
            )
            if args.decodes:
                fake.send_decodes(args.host, args.port, count=args.decodes, msg_id=args.msg_id, rng=rng)
            fake.configures()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        sys.stdout.write("stopped\n")
    finally:
        fake.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
