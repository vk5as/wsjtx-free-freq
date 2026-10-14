"""Settings dialog: edits the values the window can change. OK is enabled only while `problems` finds nothing."""

from dataclasses import replace

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from wsjtx_free_freq import persistence
from wsjtx_free_freq.engine import Settings
from wsjtx_free_freq.persistence import AppSettings
from wsjtx_free_freq.settings_check import problems


def _int_box(low: int, high: int, value: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    return box


class SettingsDialog(QDialog):
    """Shows the current values; `values` gives what they would be, with the fields it does not show left as they were."""

    def __init__(self, engine: Settings, app: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._engine = engine
        self._app = app
        self.address = QLineEdit(app.udp_address)
        self.port = _int_box(persistence.MIN_PORT, persistence.MAX_PORT, app.udp_port)
        self.multicast = QLineEdit(app.multicast_group)
        self.search_low = _int_box(0, persistence.MAX_AUDIO_HZ, engine.search_low_hz)
        self.search_high = _int_box(0, persistence.MAX_AUDIO_HZ, engine.search_high_hz)
        self.guard = _int_box(0, persistence.MAX_GUARD_HZ, engine.guard_hz)
        self.occupancy = _int_box(persistence.MIN_WINDOW_CYCLES, persistence.MAX_WINDOW_CYCLES, engine.window_cycles)
        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(0.0, persistence.MAX_SPACING_WIDTHS)
        self.spacing.setDecimals(2)
        self.spacing.setValue(engine.min_spacing_widths)
        self.clearance = _int_box(0, persistence.MAX_CLEARANCE_HZ, engine.min_clearance_hz)
        self.error = QLabel()
        self.error.setStyleSheet("color: #d44;")
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow("UDP address", self.address)
        form.addRow("UDP port", self.port)
        form.addRow("Multicast group", self.multicast)
        form.addRow("Search low (Hz)", self.search_low)
        form.addRow("Search high (Hz)", self.search_high)
        form.addRow("Guard band (Hz)", self.guard)
        form.addRow("Occupancy window (cycles)", self.occupancy)
        form.addRow("Minimum spacing (signal widths)", self.spacing)
        form.addRow("Minimum clearance (Hz)", self.clearance)
        form.addRow(self.error)
        form.addRow(self.buttons)

        self.address.textChanged.connect(self._validate)
        self.multicast.textChanged.connect(self._validate)
        for box in (self.port, self.search_low, self.search_high, self.guard, self.occupancy, self.clearance):
            box.valueChanged.connect(self._validate)
        self.spacing.valueChanged.connect(self._validate)
        self._validate()

    def values(self) -> tuple[Settings, AppSettings]:
        """Return the engine and app settings as the fields now read; fields not shown here keep their current value."""
        engine = replace(
            self._engine,
            search_low_hz=self.search_low.value(),
            search_high_hz=self.search_high.value(),
            guard_hz=self.guard.value(),
            window_cycles=self.occupancy.value(),
            min_spacing_widths=self.spacing.value(),
            min_clearance_hz=self.clearance.value(),
        )
        app = replace(
            self._app,
            udp_address=self.address.text().strip(),
            udp_port=self.port.value(),
            multicast_group=self.multicast.text().strip(),
        )
        return engine, app

    def accept(self) -> None:
        """Refuses to confirm while any value is invalid, whatever triggered it."""
        engine, app = self.values()
        if not problems(engine, app):
            super().accept()

    def _validate(self, *_: object) -> None:
        engine, app = self.values()
        found = problems(engine, app)
        self.error.setText("\n".join(found))
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setEnabled(not found)
