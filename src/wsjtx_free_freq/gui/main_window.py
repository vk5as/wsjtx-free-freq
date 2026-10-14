"""The application window: the header bar and one slot panel per slot, fed by the UDP listener through the engine."""

import time
from dataclasses import replace

from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from wsjtx_free_freq.engine import EMPTY_SLOT, Engine, InstanceView, Settings, Slot
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


def _listen_key(app: AppSettings) -> tuple[str, int, str]:
    """Return the settings that decide what the listener binds and joins."""
    return app.udp_address, app.udp_port, app.multicast_group


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
        self.listener.bind(self.app_settings.udp_port, self.app_settings.udp_address, self.app_settings.multicast_group)
        self.header = HeaderBar()
        self.header.settings_requested.connect(self.open_settings)
        self.band_map = BandMap()
        self.band_map.offset_chosen.connect(self.set_rx)
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
        self.header.instance_selected.connect(self.refresh)
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
        """Make these settings current: rebind the listener if its address or port changed or it has a problem, then save and redraw.

        A refused rebind keeps the old network fields; everything else is still applied and saved.
        """
        old = self.app_settings
        attempt = app_settings
        refused = False
        if (_listen_key(attempt) != _listen_key(old) or self.listener.problem) and not self.listener.bind(
            attempt.udp_port, attempt.udp_address, attempt.multicast_group
        ):
            self.listener.bind(old.udp_port, old.udp_address, old.multicast_group)
            app_settings = replace(
                attempt, udp_address=old.udp_address, udp_port=old.udp_port, multicast_group=old.multicast_group
            )
            refused = True
        self.engine.settings = engine_settings
        self.app_settings = app_settings
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, app_settings.theme)
        if self._store is not None:
            save_settings(self._store, engine_settings, app_settings)
        self.refresh()
        if refused:
            QMessageBox.warning(
                self,
                WINDOW_TITLE,
                f"Could not listen on {attempt.udp_address}:{attempt.udp_port}. "
                f"The port may be in use. Still listening on {old.udp_address}:{old.udp_port}. "
                "Other settings were applied; the network settings were not.",
            )

    def set_rx(self, offset_hz: int) -> None:
        """Move the selected instance's Rx to `offset_hz` over UDP, then remind the operator to press Tx ← Rx.

        Ignored unless the selected instance is supported and connected, and a negative offset is ignored too.
        """
        inst = self._selected()
        if inst is None or not inst.supported or not inst.connected:
            return
        try:
            outgoing = self.engine.set_rx(inst.id, offset_hz)
        except ValueError:  # a Qt slot must not raise
            return
        self.listener.send(outgoing)
        self.rx_hint.show_rx(offset_hz)

    def _selected(self) -> InstanceView | None:
        """Return the instance the header has selected, as of now, or None when it is not heard."""
        snapshot = self.engine.snapshot(time.monotonic())
        return next((i for i in snapshot.instances if i.id == self.header.selected_id), None)

    def refresh(self) -> None:
        """Redraw the header and slot panels from the engine's current snapshot."""
        snapshot = self.engine.snapshot(time.monotonic())
        inst = self.header.show_snapshot(snapshot, self.listener.problem)
        self.band_map.show_snapshot(inst, self.engine.settings)
        unsupported = None if inst is None or inst.supported else inst.mode
        for slot, panel in self.slot_panels.items():
            view = EMPTY_SLOT if inst is None else inst.slots[slot]
            panel.show_slot(view, self.engine.settings.window_cycles, unsupported)
