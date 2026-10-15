import os
import sys
from collections.abc import Iterator
from types import TracebackType

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


@pytest.fixture(autouse=True)
def slot_errors() -> Iterator[list[BaseException]]:
    """Fail any test where a Qt slot raised.

    PyQt hands an exception escaping a slot to sys.excepthook and, by default, then aborts the whole app. Here the
    hook records it instead, and the test fails at teardown. A test that expects a slot error clears the list.
    """
    caught: list[BaseException] = []

    def hook(_type: type[BaseException], value: BaseException, _tb: TracebackType | None) -> None:
        caught.append(value)

    previous = sys.excepthook
    sys.excepthook = hook
    try:
        yield caught
    finally:
        sys.excepthook = previous
    if caught:
        pytest.fail(f"a Qt slot raised: {caught[0]!r}")
