"""Entry point: creates the Qt application and shows the main window."""

import sys

from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.gui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
