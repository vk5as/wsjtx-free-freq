"""CI smoke test: construct the real main window offscreen, show it, feed it a fake WSJT-X, check the header.

Runs outside pytest so the same check can later run against an installed wheel. The fake sender sits next to
this file, so running the script directly puts it on sys.path.
"""

import os
import sys
import time
from collections.abc import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fake_wsjtx import send_once
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.gui.main_window import WINDOW_TITLE, MainWindow

WAIT_S = 5.0


def _pump_until(app: QCoreApplication, done: Callable[[], bool], timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while not done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(listen_port=0)  # port 0: any free port
    window.show()
    app.processEvents()
    shown = window.isVisible()
    if not shown or window.windowTitle() != WINDOW_TITLE:
        window.close()
        sys.stderr.write("The main window did not show with the expected title\n")
        return 1

    header = window.header
    port = window.listener.local_port()
    send_once("127.0.0.1", port, dial_hz=14074000, mode="FT8")
    _pump_until(app, lambda: header.connection_label.text() == "Connected", WAIT_S)

    checks = {
        "connected": header.connection_label.text() == "Connected",
        "dial": header.dial_label.text() == "14.074 000 MHz",
        "mode": header.mode_label.text() == "FT8",
    }
    window.close()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        sys.stderr.write(f"Header did not show {', '.join(failed)} after a fake WSJT-X on port {port}\n")
        return 1
    sys.stdout.write(f"GUI construction OK on Python {sys.version.split()[0]}; live header OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
