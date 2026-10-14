import socket

import pytest
from PyQt6.QtWidgets import QMainWindow

from wsjtx_free_freq.gui.main_window import MainWindow


@pytest.mark.usefixtures("qapp")
def test_main_window_is_an_empty_window_titled_for_the_app() -> None:
    window = MainWindow(listen_port=0)
    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "WSJT-X Free Frequency"
    assert window.centralWidget() is not None
    window.close()


@pytest.mark.usefixtures("qapp")
def test_a_port_taken_at_startup_is_shown_in_the_header() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken_port = int(taken.getsockname()[1])
        window = MainWindow(listen_port=taken_port)
    assert str(taken_port) in window.header.connection_label.text()
    window.close()
