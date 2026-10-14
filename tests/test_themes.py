from collections.abc import Generator

import pytest
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from wsjtx_free_freq.gui import themes


@pytest.fixture
def clean_app(qapp: QApplication) -> Generator[QApplication, None, None]:
    yield qapp
    qapp.setStyleSheet("")
    qapp.setPalette(QPalette())


def _contrast(a: QColor, b: QColor) -> float:
    def lum(c: QColor) -> float:
        def ch(v: int) -> float:
            s = v / 255
            return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

        return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.usefixtures("clean_app")
def test_registry_ships_system_light_and_dark() -> None:
    assert set(themes.THEMES) == {"System", "Light", "Dark"}


@pytest.mark.parametrize("name", ["System", "Light", "Dark"])
def test_every_theme_applies_fusion_with_a_palette(clean_app: QApplication, name: str) -> None:
    themes.apply_theme(clean_app, name)
    style = clean_app.style()
    assert style is not None
    assert style.name().lower() == "fusion"
    assert clean_app.palette().color(QPalette.ColorRole.Window).isValid()


def test_dark_theme_uses_prototype_palette(clean_app: QApplication) -> None:
    themes.apply_theme(clean_app, "Dark")
    p = clean_app.palette()
    assert p.color(QPalette.ColorRole.Window) == QColor("#1e2129")
    assert p.color(QPalette.ColorRole.Base) == QColor("#161920")
    assert p.color(QPalette.ColorRole.Highlight) == QColor("#3a7bd5")


def test_light_theme_is_light(clean_app: QApplication) -> None:
    themes.apply_theme(clean_app, "Light")
    assert clean_app.palette().color(QPalette.ColorRole.Window).lightness() > 128
    assert clean_app.palette().color(QPalette.ColorRole.Text).lightness() < 128


@pytest.mark.parametrize("name", ["Light", "Dark"])
def test_buttons_and_band_map_text_are_readable(clean_app: QApplication, name: str) -> None:
    themes.apply_theme(clean_app, name)
    p = clean_app.palette()
    # WCAG AA for normal text
    assert _contrast(p.color(QPalette.ColorRole.ButtonText), p.color(QPalette.ColorRole.Button)) >= 4.5
    assert _contrast(p.color(QPalette.ColorRole.Text), p.color(QPalette.ColorRole.Base)) >= 4.5


def test_switching_theme_replaces_the_previous_palette(clean_app: QApplication) -> None:
    themes.apply_theme(clean_app, "Dark")
    themes.apply_theme(clean_app, "Light")
    assert clean_app.palette().color(QPalette.ColorRole.Window) != QColor("#1e2129")


def test_adding_a_theme_is_one_registry_entry(clean_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = themes.Theme(palette=lambda _app: themes.dark_palette())
    monkeypatch.setitem(themes.THEMES, "Custom", custom)
    themes.apply_theme(clean_app, "Custom")
    assert clean_app.palette().color(QPalette.ColorRole.Window) == QColor("#1e2129")
