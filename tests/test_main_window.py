import pytest
from PyQt6.QtWidgets import QMainWindow

from wsjtx_free_freq.gui.main_window import MainWindow


@pytest.mark.usefixtures("qapp")
def test_main_window_is_an_empty_window_titled_for_the_app() -> None:
    window = MainWindow()
    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "WSJT-X Free Frequency"
    assert window.centralWidget() is not None
    window.close()
