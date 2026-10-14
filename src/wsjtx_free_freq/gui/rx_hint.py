"""Hint line under the header, shown after a free location sets Rx: Tx is still WSJT-X's to set (ADR 0001)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class RxHint(QFrame):
    """Hidden until `show_rx`; the Dismiss button hides it again."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(self)
        self.text = QLabel()
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.dismiss = QPushButton("Dismiss")
        layout.addWidget(self.text)
        layout.addStretch()
        layout.addWidget(self.dismiss)
        self.dismiss.clicked.connect(self.hide)
        self.hide()

    def show_rx(self, offset_hz: int) -> None:
        self.text.setText(f"Rx set to {offset_hz} Hz. Press <b>Tx ← Rx</b> in WSJT-X to move your Tx too.")
        self.show()
