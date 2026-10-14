"""The application window: the header bar and one slot panel per slot, fed by the UDP listener through the engine."""

import time

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from wsjtx_free_freq.engine import Engine, Settings, Slot, SlotView
from wsjtx_free_freq.gui.band_map import BandMap
from wsjtx_free_freq.gui.header import HeaderBar
from wsjtx_free_freq.gui.listener import DEFAULT_HOST, UdpListener
from wsjtx_free_freq.gui.rx_hint import RxHint
from wsjtx_free_freq.gui.settings_dialog import SettingsDialog
from wsjtx_free_freq.gui.slot_panel import SlotPanel
from wsjtx_free_freq.gui.themes import apply_theme
from wsjtx_free_freq.persistence import DEFAULT_PORT, AppSettings, save_settings

WINDOW_TITLE = "WSJT-X Free Frequency"
REFRESH_MS = 1000
_NO_DECODES = SlotView(occupied=(), free=(), decode_count=0)


class MainWindow(QMainWindow):
    """Top-level window of the application."""

    def __init__(
        self,
        listen_port: int = DEFAULT_PORT,
        engine: Engine | None = None,
        listen_host: str = DEFAULT_HOST,
        *,
        store: QSettings | None = None,
        app_settings: AppSettings | None = None,
    ) -> None:
        """`store` is where Settings saves to (None: this run only). `app_settings` replaces the listen arguments."""
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.engine = Engine() if engine is None else engine
        self.app_settings = (
            AppSettings(udp_address=listen_host, udp_port=listen_port) if app_settings is None else app_settings
        )
        self._store = store
        self.listener = UdpListener(self.engine, self)
        self.listener.bind(self.app_settings.udp_port, self.app_settings.udp_address)
        self.header = HeaderBar()
        self.header.settings_requested.connect(self.open_settings)
        self.band_map = BandMap()
        self.rx_hint = RxHint()
        self.slot_panels = {slot: SlotPanel(slot) for slot in Slot}
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addWidget(self.header)
        layout.addWidget(self.band_map)
        layout.addWidget(self.rx_hint)
        for slot in Slot:
            layout.addWidget(self.slot_panels[slot])
            self.slot_panels[slot].location_chosen.connect(self.set_rx)
        layout.addStretch()
        self.setCentralWidget(body)
        self.listener.datagram_received.connect(self.refresh)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(REFRESH_MS)
        self.refresh()

    def open_settings(self) -> None:
        """Show the Settings dialog; OK applies and saves what it returns, Cancel changes nothing."""
        dialog = SettingsDialog(self.engine.settings, self.app_settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            engine_settings, app_settings = dialog.values()
            self.apply_settings(engine_settings, app_settings)

    def apply_settings(self, engine_settings: Settings, app_settings: AppSettings) -> None:
        """Make these settings current: rebind the listener if its address or port changed, then save and redraw."""
        old = self.app_settings
        moved = (app_settings.udp_address, app_settings.udp_port) != (old.udp_address, old.udp_port)
        if moved and not self.listener.bind(app_settings.udp_port, app_settings.udp_address):
            self.listener.bind(old.udp_port, old.udp_address)
            QMessageBox.warning(
                self,
                WINDOW_TITLE,
                f"Could not listen on {app_settings.udp_address}:{app_settings.udp_port}. "
                f"The port may be in use. Still listening on {old.udp_address}:{old.udp_port}.",
            )
            return
        self.engine.settings = engine_settings
        self.app_settings = app_settings
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, app_settings.theme)
        if self._store is not None:
            save_settings(self._store, engine_settings, app_settings)
        self.refresh()

    def set_rx(self, offset_hz: int) -> None:
        """Move the first instance's Rx to `offset_hz` over UDP, then remind the operator to press Tx ← Rx."""
        snapshot = self.engine.snapshot(time.monotonic())
        if not snapshot.instances:
            return
        self.listener.send(self.engine.set_rx(snapshot.instances[0].id, offset_hz))
        self.rx_hint.show_rx(offset_hz)

    def refresh(self) -> None:
        """Redraw the header and slot panels from the engine's current snapshot."""
        snapshot = self.engine.snapshot(time.monotonic())
        self.header.show_snapshot(snapshot)
        inst = snapshot.instances[0] if snapshot.instances else None
        self.band_map.show_snapshot(inst, self.engine.settings)
        unsupported = None if inst is None or inst.supported else inst.mode
        for slot, panel in self.slot_panels.items():
            view = _NO_DECODES if inst is None else inst.slots[slot]
            panel.show_slot(view, self.engine.settings.window_cycles, unsupported)
