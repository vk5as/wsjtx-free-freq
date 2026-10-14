"""The application window; empty until the panels arrive."""

from PyQt6.QtWidgets import QMainWindow, QWidget

WINDOW_TITLE = "WSJT-X Free Frequency"


class MainWindow(QMainWindow):
    """Top-level window of the application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setCentralWidget(QWidget())
