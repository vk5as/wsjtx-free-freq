from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


class _Emitter(QObject):
    fired = pyqtSignal()


def _boom() -> None:
    msg = "boom"
    raise ValueError(msg)


def test_an_exception_in_a_slot_is_caught_not_fatal(qapp: QApplication, slot_errors: list[BaseException]) -> None:
    emitter = _Emitter()
    emitter.fired.connect(_boom)
    emitter.fired.emit()
    qapp.processEvents()
    assert [type(e) for e in slot_errors] == [ValueError]
    slot_errors.clear()  # expected here; any other test with a slot error fails
