"""Entry point: creates the Qt application and shows the main window."""

import sys

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.engine import Engine
from wsjtx_free_freq.gui.main_window import MainWindow
from wsjtx_free_freq.gui.themes import DEFAULT_THEME, THEMES, apply_theme
from wsjtx_free_freq.persistence import default_store, load_settings


def startup(app: QApplication, store: QSettings) -> MainWindow:
    """Build the window from the stored settings: engine settings, listen address and port, and theme."""
    engine_settings, app_settings = load_settings(store)
    apply_theme(app, app_settings.theme if app_settings.theme in THEMES else DEFAULT_THEME)
    return MainWindow(engine=Engine(engine_settings), store=store, app_settings=app_settings)


def main() -> int:
    existing = QApplication.instance()
    app = existing if isinstance(existing, QApplication) else QApplication(sys.argv)
    window = startup(app, default_store())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
