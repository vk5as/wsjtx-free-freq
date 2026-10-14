"""Fake WSJT-X sender: sends Heartbeat and Status datagrams to a host and port, for trying the app without WSJT-X.

.venv/bin/python scripts/fake_wsjtx.py --port 2237 --dial-hz 14074000 --mode FT8
"""

import argparse
import socket
import sys
import time

from wsjtx_free_freq.encoder import heartbeat, status


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
        sock.sendto(heartbeat(msg_id), (host, port))
        sock.sendto(status(msg_id, dial_hz=dial_hz, mode=mode, rx_df=rx_df, tx_df=tx_df), (host, port))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2237)
    parser.add_argument("--id", default="WSJT-X", dest="msg_id")
    parser.add_argument("--dial-hz", type=int, default=14074000)
    parser.add_argument("--mode", default="FT8")
    parser.add_argument("--rx", type=int, default=1500, dest="rx_df")
    parser.add_argument("--tx", type=int, default=1000, dest="tx_df")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between sends; Ctrl-C to stop")
    args = parser.parse_args(argv)
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
            time.sleep(args.interval)
    except KeyboardInterrupt:
        sys.stdout.write("stopped\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
