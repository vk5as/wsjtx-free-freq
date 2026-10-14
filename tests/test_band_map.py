import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent
from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.engine import DEFAULT_SETTINGS, FreeLocation, InstanceView, Occupied, Slot, SlotView
from wsjtx_free_freq.gui.band_map import LANE_HEIGHT, BandMap


def _instance(
    free: tuple[FreeLocation, ...] = (),
    occupied: tuple[Occupied, ...] = (),
    rx: int | None = 1500,
    tx: int | None = 1500,
    width: int | None = 50,
) -> InstanceView:
    empty = SlotView(occupied=(), free=(), decode_count=0)
    busy = SlotView(occupied=occupied, free=free, decode_count=len(occupied))
    return InstanceView(
        id="WSJT-X",
        connected=True,
        dial_hz=14074000,
        mode="FT8",
        supported=width is not None,
        signal_width_hz=width,
        rx_hz=rx,
        tx_hz=tx,
        slots={Slot.FIRST: busy, Slot.SECOND: empty},
    )


def _image(band: BandMap) -> QImage:
    return band.grab().toImage()


def _near(image: QImage, band: BandMap, hz: int, row: int) -> QColor:
    """Colour at an audio offset on a row."""
    return QColor(image.pixel(round(band.axis().x_of(hz)), row))


@pytest.fixture
def band(qapp: QApplication) -> BandMap:  # noqa: ARG001 - the fixture creates the QApplication
    band = BandMap()
    band.resize(600, 120)
    return band


def test_redraws_when_the_snapshot_changes(band: BandMap) -> None:
    band.show_snapshot(_instance(), DEFAULT_SETTINGS)
    empty = _image(band)
    band.show_snapshot(
        _instance(
            occupied=(Occupied(offset_hz=800, snr_db=-5, age_cycles=0, blocked_low_hz=790, blocked_high_hz=860),)
        ),
        DEFAULT_SETTINGS,
    )
    assert _image(band) != empty


def test_free_locations_are_drawn_green_at_their_offsets(band: BandMap) -> None:
    band.show_snapshot(
        _instance(free=(FreeLocation(rank=1, offset_hz=2000, clearance_hz=50, gap_hz=50),)), DEFAULT_SETTINGS
    )
    image = _image(band)
    x = round(band.axis().x_of(2000 + 3))
    colour = QColor(image.pixel(x, 15))
    assert colour.green() > colour.red()
    assert colour.green() > colour.blue()


def test_rx_and_tx_markers_are_drawn_at_their_offsets(band: BandMap) -> None:
    band.show_snapshot(_instance(rx=600, tx=2200), DEFAULT_SETTINGS)
    image = _image(band)
    rx = _near(image, band, 600, 30)
    tx = _near(image, band, 2200, 30)
    blank = _near(image, band, 1400, 30)
    assert rx != blank
    assert tx != blank
    assert rx != tx


def test_no_snapshot_draws_no_markers_or_blocks(band: BandMap) -> None:
    band.show_snapshot(None, DEFAULT_SETTINGS)
    image = _image(band)
    assert _near(image, band, 600, 30) == _near(image, band, 1400, 30)


def _click(band: BandMap, x: int, y: int) -> list[int]:
    chosen: list[int] = []
    band.offset_chosen.connect(chosen.append)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(x, y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(band, press)
    return chosen


def test_clicking_a_lane_emits_the_offset_under_the_pointer_rounded_to_5_hz(band: BandMap) -> None:
    band.show_snapshot(_instance(), DEFAULT_SETTINGS)
    assert band.axis().x_of(1500) == 315.0  # exact pixel, so the offset is exactly 1500 Hz
    assert _click(band, 315, 30) == [1500]


def test_a_click_right_of_the_axis_is_clamped_to_the_search_range_minus_the_signal_width(band: BandMap) -> None:
    band.show_snapshot(_instance(), DEFAULT_SETTINGS)  # FT8 signal is 50 Hz wide
    assert _click(band, 599, 30) == [2750]


def test_a_click_clamps_to_the_selected_instances_signal_width(band: BandMap) -> None:
    band.show_snapshot(_instance(width=83), DEFAULT_SETTINGS)  # FT4 signal is 83 Hz wide
    assert _click(band, 599, 30) == [2800 - 83]


def test_an_unsupported_instance_ignores_clicks(band: BandMap) -> None:
    band.show_snapshot(_instance(width=None), DEFAULT_SETTINGS)
    assert _click(band, 315, 30) == []


def test_a_click_on_the_axis_labels_emits_nothing(band: BandMap) -> None:
    band.show_snapshot(_instance(), DEFAULT_SETTINGS)
    assert _click(band, 315, len(Slot) * LANE_HEIGHT + 5) == []


def test_the_band_map_is_a_crosshair_that_says_click_to_set_rx(band: BandMap) -> None:
    assert band.cursor().shape() == Qt.CursorShape.CrossCursor
    assert band.toolTip() == "Click to set Rx"
