"""Band map: one lane per slot on a shared audio offset axis, with occupancy, guard bands, free locations and Rx/Tx."""

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from wsjtx_free_freq.engine import DEFAULT_SETTINGS, FREE_STEP_HZ, MODES, InstanceView, Settings, Slot, SlotView
from wsjtx_free_freq.geometry import Axis
from wsjtx_free_freq.gui.themes import FREE_LOCATION_COLOUR

LANE_HEIGHT = 46
LABEL_PX = 40  # left margin holding the slot name
RIGHT_PX = 10
AXIS_PX = 22  # tick labels underneath the lanes
TICK_HZ = 500
TX_COLOUR = "#e0457b"  # reads on both palettes; Rx takes the palette's highlight
_DEFAULT_MODE = "FT8"
_EMPTY = SlotView(occupied=(), free=(), decode_count=0)


class BandMap(QWidget):
    """Shows the first instance in a snapshot; drawn from the palette, so it follows the theme."""

    offset_chosen = pyqtSignal(int)  # audio offset in Hz under a click on a lane

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._instance: InstanceView | None = None
        self._settings: Settings = DEFAULT_SETTINGS
        self.setMinimumHeight(LANE_HEIGHT * len(Slot) + AXIS_PX)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip("Click to set Rx")

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Pick the audio offset under a left click on a lane, rounded and kept inside the search range."""
        if event is None or event.button() != Qt.MouseButton.LeftButton:
            return
        if event.position().y() >= LANE_HEIGHT * len(Slot):
            return  # the axis labels below the lanes
        s = self._settings
        top = s.search_high_hz - self._signal_width()
        self.offset_chosen.emit(self.axis().offset_at(event.position().x(), FREE_STEP_HZ, s.search_low_hz, top))

    def show_snapshot(self, instance: InstanceView | None, settings: Settings) -> None:
        """Take the instance to draw (None while nothing is heard) and redraw."""
        self._instance = instance
        self._settings = settings
        self.update()

    def axis(self) -> Axis:
        """Return the audio offset axis at the widget's current width."""
        s = self._settings
        return Axis(s.search_low_hz, s.search_high_hz, LABEL_PX, self.width() - LABEL_PX - RIGHT_PX)

    def _slot_view(self, slot: Slot) -> SlotView:
        return _EMPTY if self._instance is None else self._instance.slots[slot]

    def _signal_width(self) -> int:
        mode = self._instance.mode if self._instance is not None else None
        return MODES.get(mode or _DEFAULT_MODE, MODES[_DEFAULT_MODE]).signal_width_hz

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        text = pal.color(QPalette.ColorRole.Text)
        muted = pal.color(QPalette.ColorRole.PlaceholderText)
        painter.fillRect(self.rect(), pal.color(QPalette.ColorRole.Base))
        small = QFont(self.font())
        small.setPointSizeF(7.5)
        painter.setFont(small)
        axis = self.axis()
        width_hz = self._signal_width()
        window = max(1, self._settings.window_cycles)
        for i, slot in enumerate(Slot):
            top = i * LANE_HEIGHT + 2
            height = LANE_HEIGHT - 4
            lane = QRectF(axis.x_of(axis.low_hz), top, axis.x_of(axis.high_hz) - axis.x_of(axis.low_hz), height)
            painter.fillRect(lane, pal.color(QPalette.ColorRole.AlternateBase))
            painter.setPen(muted)
            painter.drawText(QRectF(0, top, LABEL_PX - 4, height), Qt.AlignmentFlag.AlignCenter, slot.value)
            view = self._slot_view(slot)
            for occ in view.occupied:
                guard = QColor(text)
                guard.setAlpha(60)
                painter.fillRect(self._span(axis, occ.blocked_low_hz, occ.blocked_high_hz, top + 4, height - 8), guard)
                signal = QColor(text)
                signal.setAlpha(int(255 * (1 - 0.7 * occ.age_cycles / window)))
                painter.fillRect(
                    self._span(axis, occ.offset_hz, occ.offset_hz + width_hz, top + 8, height - 16), signal
                )
            for loc in view.free:
                block = QColor(FREE_LOCATION_COLOUR)
                block.setAlpha(150)
                rect = self._span(axis, loc.offset_hz, loc.offset_hz + width_hz, top + 8, height - 16)
                painter.fillRect(rect, block)
                painter.setPen(text)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(loc.rank))
        if self._instance is not None:
            self._draw_markers(painter, axis, self._instance)
        painter.setPen(muted)
        axis_top = len(Slot) * LANE_HEIGHT + 2
        for hz in axis.ticks(TICK_HZ):
            x = axis.x_of(hz)
            painter.drawLine(QPointF(x, axis_top), QPointF(x, axis_top + 4))
            painter.drawText(QRectF(x - 25, axis_top + 4, 50, 14), Qt.AlignmentFlag.AlignCenter, str(hz))

    def _draw_markers(self, painter: QPainter, axis: Axis, instance: InstanceView) -> None:
        bottom = len(Slot) * LANE_HEIGHT - 2
        palette_highlight = self.palette().color(QPalette.ColorRole.Highlight)
        for hz, colour, label, dx in (
            (instance.rx_hz, palette_highlight, "Rx", 3),
            (instance.tx_hz, QColor(TX_COLOUR), "Tx", 17),
        ):
            if hz is None:
                continue
            x = axis.x_of(hz)
            painter.setPen(QPen(colour, 2))
            painter.drawLine(QPointF(x, 2), QPointF(x, bottom))
            painter.drawText(QPointF(x + dx, 12), label)

    @staticmethod
    def _span(axis: Axis, low_hz: int, high_hz: int, top: float, height: float) -> QRectF:
        return QRectF(axis.x_of(low_hz), top, axis.x_of(high_hz) - axis.x_of(low_hz), height)
