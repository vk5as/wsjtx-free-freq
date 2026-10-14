"""Settings dialog: edits the values the window can change. OK is enabled only while `problems` finds nothing."""

from dataclasses import replace

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from wsjtx_free_freq.gui.themes import THEMES
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
        self.strong = QCheckBox()
        self.strong.setChecked(engine.strong_enabled)
        self.strong_snr = _int_box(persistence.MIN_STRONG_SNR_DB, persistence.MAX_STRONG_SNR_DB, engine.strong_snr_db)
        self.strong_extra = _int_box(0, persistence.MAX_STRONG_EXTRA_HZ, engine.strong_extra_hz)
        self.strong_snr.setEnabled(engine.strong_enabled)
        self.strong_extra.setEnabled(engine.strong_enabled)
        self.theme = QComboBox()
        self.theme.addItems(list(THEMES))
        self.theme.setCurrentText(app.theme)
        self.error = QLabel()
        self.error.setStyleSheet("color: #d44;")
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self._lay_out()

        self.address.textChanged.connect(self._validate)
        self.multicast.textChanged.connect(self._validate)
        for box in (self.port, self.search_low, self.search_high, self.guard, self.occupancy, self.clearance):
            box.valueChanged.connect(self._validate)
        self.strong.toggled.connect(self.strong_snr.setEnabled)
        self.strong.toggled.connect(self.strong_extra.setEnabled)
        self.strong_snr.valueChanged.connect(self._validate)
        self.strong_extra.valueChanged.connect(self._validate)
        self.spacing.valueChanged.connect(self._validate)
        self._validate()

    def _lay_out(self) -> None:
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
        form.addRow("Wider guard band for strong signals", self.strong)
        form.addRow("Strong signal SNR (dB)", self.strong_snr)
        form.addRow("Strong signal extra guard (Hz)", self.strong_extra)
        form.addRow("Theme", self.theme)
        form.addRow(self.error)
        form.addRow(self.buttons)

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
            strong_enabled=self.strong.isChecked(),
            strong_snr_db=self.strong_snr.value(),
            strong_extra_hz=self.strong_extra.value(),
        )
        app = replace(
            self._app,
            udp_address=self.address.text().strip(),
            udp_port=self.port.value(),
            multicast_group=self.multicast.text().strip(),
            theme=self.theme.currentText(),
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
