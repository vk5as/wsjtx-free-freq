"""Take the README's screenshots: the real GUI, fed by the fake WSJT-X sender, on Qt's offscreen platform.

Run it from a checkout with the development install::

    .venv/bin/python scripts/take_screenshots.py            # writes docs/images/*.png
    .venv/bin/python scripts/take_screenshots.py -o /tmp/x  # or somewhere else, to compare

Nothing touches the user's settings: the window gets no settings store. What is fixed, so a re-run gives near
enough the same pictures: the decodes' random seed, the window size and the theme of each picture. What is not: the
decodes' cycles follow the wall clock, so which slot gets which decode can change between runs. This is a
maintainer's tool; CI does not run it.
"""

import argparse
import os
import random
import sys
import time
from collections.abc import Callable
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fake_wsjtx import FakeWsjtx
from PyQt6.QtWidgets import QApplication, QWidget

from wsjtx_free_freq.engine import Slot
from wsjtx_free_freq.gui.main_window import MainWindow
from wsjtx_free_freq.gui.settings_dialog import SettingsDialog
from wsjtx_free_freq.gui.themes import apply_theme
from wsjtx_free_freq.persistence import AppSettings

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "images"
_SIZE = (1200, 640)
_SEED = 7074
_DECODES = 40
_TIMEOUT_S = 10.0


def _pump_until(app: QApplication, done: Callable[[], bool]) -> None:
    end = time.monotonic() + _TIMEOUT_S
    while not done():
        if time.monotonic() > end:
            msg = "the window did not reach the state the screenshot needs"
            raise RuntimeError(msg)
        app.processEvents()
        time.sleep(0.02)


def _save(widget: QWidget, path: Path) -> None:
    if not widget.grab().save(str(path)):
        msg = f"could not write {path}"
        raise RuntimeError(msg)
    sys.stdout.write(f"wrote {path}\n")


def _decoded(window: MainWindow) -> int:
    instances = window.engine.snapshot(time.monotonic()).instances
    return sum(view.decode_count for view in instances[0].slots.values()) if instances else 0


def _main_window(app: QApplication, theme: str, *, set_rx: bool) -> MainWindow:
    apply_theme(app, theme)
    window = MainWindow(listen_port=0)
    window.resize(*_SIZE)
    window.show()
    fake = FakeWsjtx()
    port = window.listener.local_port()
    fake.send_once("127.0.0.1", port, dial_hz=14074000, mode="FT8", rx_df=1500, tx_df=1500)
    _pump_until(app, lambda: window.header.connection_label.text() == "Connected")
    fake.send_decodes("127.0.0.1", port, count=_DECODES, rng=random.Random(_SEED))  # noqa: S311 - fixed demo traffic
    _pump_until(app, lambda: _decoded(window) >= _DECODES)
    if set_rx:
        window.slot_panels[Slot.FIRST].buttons[0].click()
        _pump_until(app, lambda: bool(fake.configures()))
    app.processEvents()
    fake.close()
    return window


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help="directory for the PNGs")
    args = parser.parse_args(argv)
    out: Path = args.output
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    assert isinstance(app, QApplication)  # noqa: S101 - narrows the type for mypy

    dark = _main_window(app, "Dark", set_rx=True)
    _save(dark, out / "main_dark.png")
    # The window listens on a free port; the dialog shows the default one, as a user would see it.
    dialog = SettingsDialog(dark.engine.settings, AppSettings(), dark)
    dialog.show()
    app.processEvents()
    _save(dialog, out / "settings_dialog.png")
    dialog.close()
    dark.close()

    light = _main_window(app, "Light", set_rx=False)
    _save(light, out / "main_light.png")
    light.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
