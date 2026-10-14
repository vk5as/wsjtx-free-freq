"""Entry point: creates the Qt application and shows the main window."""

import sys

from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.gui.main_window import MainWindow
from wsjtx_free_freq.gui.themes import DEFAULT_THEME, apply_theme


def main() -> int:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    apply_theme(app, DEFAULT_THEME)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
