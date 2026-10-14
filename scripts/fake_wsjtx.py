"""Fake WSJT-X sender: sends Heartbeat, Status and optionally FT8 Decode datagrams, for trying the app without WSJT-X.

.venv/bin/python scripts/fake_wsjtx.py --port 2237 --dial-hz 14074000 --mode FT8 --decodes 10
"""

import argparse
import random
import socket
import sys
import time

from wsjtx_free_freq.codec import encode_decode, encode_heartbeat, encode_status

FT8_CYCLE_MS = 15_000
DAY_MS = 86_400_000
CALLS = ("K1ABC", "W1XYZ", "G4DEF", "JA2GHI", "VK3JKL", "DL5MNO")
LOOKBACK_CYCLES = 8  # spans both slots, so each slot gets decodes in its occupancy window


def send_once(  # noqa: PLR0913
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
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(encode_heartbeat(msg_id), (host, port))
        sock.sendto(encode_status(msg_id, dial_hz=dial_hz, mode=mode, rx_df=rx_df, tx_df=tx_df), (host, port))


def send_decodes(host: str, port: int, *, count: int, msg_id: str = "WSJT-X", rng: random.Random) -> None:
    """Send `count` FT8 decodes at random audio offsets, in cycles from the last few, so both slots get some."""
    now_ms = int(time.time() * 1000)
    newest_cycle = now_ms // FT8_CYCLE_MS
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
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
            sock.sendto(datagram, (host, port))


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
    try:
        while True:
            send_once(
                args.host,
                args.port,
                msg_id=args.msg_id,
                dial_hz=args.dial_hz,
                mode=args.mode,
                rx_df=args.rx_df,
                tx_df=args.tx_df,
            )
            if args.decodes:
                send_decodes(args.host, args.port, count=args.decodes, msg_id=args.msg_id, rng=rng)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        sys.stdout.write("stopped\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
