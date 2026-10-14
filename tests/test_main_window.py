import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow

from wsjtx_datagrams import decode_configure, decode_message
from wsjtx_free_freq.engine import Engine, Outgoing
from wsjtx_free_freq.gui.main_window import MainWindow


@pytest.mark.usefixtures("qapp")
def test_main_window_is_an_empty_window_titled_for_the_app() -> None:
    window = MainWindow(listen_port=0)
    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "WSJT-X Free Frequency"
    assert window.centralWidget() is not None
    window.close()


@pytest.mark.usefixtures("qapp")
def test_clicking_the_band_map_sends_the_rounded_offset_through_set_rx(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = Engine()
    engine.receive(decode_message("WSJT-X", time_ms=0, delta_hz=1000), ("127.0.0.1", 50000), now=0.0)
    window = MainWindow(listen_port=0, engine=engine)
    window.band_map.resize(600, 120)
    sent: list[Outgoing] = []
    monkeypatch.setattr(window.listener, "send", sent.append)
    window.refresh()
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(315, 30),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(window.band_map, press)
    assert len(sent) == 1
    assert decode_configure(sent[0].payload)["rx_df"] == 1500
    assert window.rx_hint.text.text().startswith("Rx set to 1500 Hz")
    window.close()
