"""CI smoke test: construct the real main window offscreen, show it, feed it a fake WSJT-X, check the header.

Runs outside pytest so the same check also runs against an installed wheel: the Release workflow does that on Windows
with ``--installed``, from a checkout that holds only ``scripts/``, which additionally requires the package to come
from site-packages and to ship its ``py.typed`` marker. The fake sender sits next to this file, so running the script
directly puts it on sys.path.
"""

import argparse
import importlib.resources
import os
import random
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fake_wsjtx import FakeWsjtx
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

import wsjtx_free_freq
from wsjtx_free_freq.engine import Slot
from wsjtx_free_freq.gui.main_window import WINDOW_TITLE, MainWindow
from wsjtx_free_freq.gui.slot_panel import SlotPanel

WAIT_S = 5.0
DECODES = 20


def check_installed() -> str | None:
    """Return why this is not an installed wheel (None if it is)."""
    location = Path(wsjtx_free_freq.__file__)
    if "site-packages" not in location.parts:
        return f"wsjtx_free_freq was imported from {location}, not from an installed wheel"
    if not (importlib.resources.files("wsjtx_free_freq") / "py.typed").is_file():
        return "The installed wheel does not ship py.typed"
    return None


def _pump_until(app: QCoreApplication, done: Callable[[], bool], timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while not done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _has_free_location_button(panel: SlotPanel) -> bool:
    return any(not button.isHidden() for button in panel.buttons)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true", help="Also require an installed wheel, not a source tree")
    args = parser.parse_args(argv)
    if args.installed:
        problem = check_installed()
        if problem is not None:
            sys.stderr.write(f"{problem}\n")
            return 1
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(listen_port=0)  # port 0: any free port
    fake = FakeWsjtx()
    window.show()
    app.processEvents()
    shown = window.isVisible()
    if not shown or window.windowTitle() != WINDOW_TITLE:
        window.close()
        sys.stderr.write("The main window did not show with the expected title\n")
        return 1

    header = window.header
    port = window.listener.local_port()
    fake.send_once("127.0.0.1", port, dial_hz=14074000, mode="FT8")
    _pump_until(app, lambda: header.connection_label.text() == "Connected", WAIT_S)

    fake.send_decodes("127.0.0.1", port, count=DECODES, rng=random.Random(9))  # noqa: S311 - fixed seed, test traffic
    panels = window.slot_panels
    _pump_until(app, lambda: all(_has_free_location_button(panel) for panel in panels.values()), WAIT_S)

    first_button = panels[Slot.FIRST].buttons[0]
    expected_rx = window.engine.snapshot(time.monotonic()).instances[0].slots[Slot.FIRST].free[0].offset_hz
    first_button.click()
    rx_dfs: list[int] = []

    def _configure_arrived() -> bool:
        rx_dfs.extend(fake.configures())
        return bool(rx_dfs)

    _pump_until(app, _configure_arrived, WAIT_S)

    hint = window.rx_hint
    hint_shown = hint.isVisible()
    hint.dismiss.click()
    checks = {
        "connected": header.connection_label.text() == "Connected",
        "dial": header.dial_label.text() == "14.074 000 MHz",
        "mode": header.mode_label.text() == "FT8",
        "1st slot free location buttons": _has_free_location_button(panels[Slot.FIRST]),
        "2nd slot free location buttons": _has_free_location_button(panels[Slot.SECOND]),
        "Configure received for the clicked location": rx_dfs == [expected_rx],
        "Rx hint shown after the click": hint_shown,
        "Rx hint dismissed": not hint.isVisible(),
    }
    fake.close()
    window.close()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        sys.stderr.write(f"Did not show {', '.join(failed)} after a fake WSJT-X on port {port}\n")
        return 1
    sys.stdout.write(
        f"GUI construction OK on Python {sys.version.split()[0]}; live header, free locations and Rx click OK\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
