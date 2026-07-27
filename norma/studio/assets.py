"""Bundled brand assets (the original NORMA logo) and a robust SVG -> QIcon loader.

Linux note: the taskbar/launcher icon is resolved from the application's *desktop file
name* (its app-id / WM_CLASS), not from ``setWindowIcon``. ``main()`` calls
``QApplication.setDesktopFileName("norma-studio")`` and a matching ``.desktop`` + themed
icon must be installed (see ``packaging/install_linux_desktop.sh``). The QIcon below always
carries concrete rasterized sizes so X11 window managers have real bitmaps to display.
"""
from __future__ import annotations
import os

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
ICON_SVG = os.path.join(ASSETS_DIR, "icon.svg")
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
DESKTOP_ID = "norma-studio"


def render_png(path: str, size: int = 256) -> None:
    """Rasterize the logo SVG to a PNG (used by the desktop-integration installer)."""
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QPixmap, QPainter
    from PySide6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(ICON_SVG)
    pm = QPixmap(QSize(size, size)); pm.fill(Qt.transparent)
    p = QPainter(pm); renderer.render(p); p.end()
    pm.save(path, "PNG")


def app_icon():
    """Return the NORMA icon as a QIcon carrying concrete pixmaps at every standard size,
    so both the window and the taskbar have real bitmaps (SVG-only icons render empty on
    some window managers)."""
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QIcon, QPixmap, QPainter
    from PySide6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(ICON_SVG)
    icon = QIcon()
    for s in ICON_SIZES:
        pm = QPixmap(QSize(s, s)); pm.fill(Qt.transparent)
        p = QPainter(pm); renderer.render(p); p.end()
        icon.addPixmap(pm)
    return icon
