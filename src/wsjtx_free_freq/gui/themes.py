"""Named themes: Fusion palettes (plus optional style sheets) applied to the QApplication."""

from collections.abc import Callable
from dataclasses import dataclass, field

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

SYSTEM = "System"
DEFAULT_THEME = SYSTEM

_THEME_PROP = "wsjtx_free_freq_theme"
_WATCH_PROP = "wsjtx_free_freq_theme_watch"


def _palette(colors: dict[QPalette.ColorRole, str]) -> QPalette:
    p = QPalette()
    for role, c in colors.items():
        p.setColor(role, QColor(c))
    return p


def light_palette() -> QPalette:
    return _palette(
        {
            QPalette.ColorRole.Window: "#efefef",
            QPalette.ColorRole.WindowText: "#111",
            QPalette.ColorRole.Base: "#ffffff",
            QPalette.ColorRole.AlternateBase: "#f4f4f6",
            QPalette.ColorRole.Text: "#111",
            QPalette.ColorRole.Button: "#e2e2e6",
            QPalette.ColorRole.ButtonText: "#111",
            QPalette.ColorRole.Highlight: "#2f6fc0",
            QPalette.ColorRole.PlaceholderText: "#667",
        }
    )


def dark_palette() -> QPalette:
    return _palette(
        {
            QPalette.ColorRole.Window: "#1e2129",
            QPalette.ColorRole.WindowText: "#dde",
            QPalette.ColorRole.Base: "#161920",
            QPalette.ColorRole.AlternateBase: "#22262f",
            QPalette.ColorRole.Text: "#dde",
            QPalette.ColorRole.Button: "#2a2e38",
            QPalette.ColorRole.ButtonText: "#dde",
            QPalette.ColorRole.Highlight: "#3a7bd5",
            QPalette.ColorRole.PlaceholderText: "#889",
        }
    )


def _system_palette(app: QApplication) -> QPalette:
    hints = app.styleHints()
    if hints is not None and hints.colorScheme() == Qt.ColorScheme.Dark:
        return dark_palette()
    return light_palette()


@dataclass(frozen=True)
class Theme:
    """A Fusion palette builder, optionally with a style sheet; follows_os re-applies on OS scheme changes."""

    palette: Callable[[QApplication], QPalette]
    stylesheet: str = ""
    follows_os: bool = field(default=False, kw_only=True)


# The registry: adding a theme means adding one entry here.
THEMES: dict[str, Theme] = {
    SYSTEM: Theme(palette=_system_palette, follows_os=True),
    "Light": Theme(palette=lambda _app: light_palette()),
    "Dark": Theme(palette=lambda _app: dark_palette()),
}


def apply_theme(app: QApplication, name: str) -> None:
    """Apply the named theme to the application."""
    theme = THEMES[name]
    app.setStyle("Fusion")
    app.setPalette(theme.palette(app))
    app.setStyleSheet(theme.stylesheet)
    app.setProperty(_THEME_PROP, name)
    hints = app.styleHints()
    if theme.follows_os and hints is not None and not app.property(_WATCH_PROP):
        hints.colorSchemeChanged.connect(lambda _scheme: _reapply_if_system(app))
        app.setProperty(_WATCH_PROP, "watching")


def _reapply_if_system(app: QApplication) -> None:
    if app.property(_THEME_PROP) == SYSTEM:
        apply_theme(app, SYSTEM)
