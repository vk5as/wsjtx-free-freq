"""CI smoke test: construct the real main window offscreen, show it, close it.

Runs outside pytest so the same check can later run against an installed wheel.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.gui.main_window import WINDOW_TITLE, MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.processEvents()
    shown = window.isVisible()
    window.close()
    if not shown or window.windowTitle() != WINDOW_TITLE:
        sys.stderr.write("The main window did not show with the expected title\n")
        return 1
    sys.stdout.write(f"GUI construction OK on Python {sys.version.split()[0]}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
