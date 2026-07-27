"""Look & feel: Fusion base + light/dark themes parameterized by an accent color."""
from __future__ import annotations
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

DEFAULT_ACCENT = "#2d7ff9"

_LIGHT = dict(window="#f5f7fb", base="white", alt="#f0f3f9", text="#1a1f29",
              panel="#eef1f6", border="#d0d6e0", header="#f1f4fa", toolbar="#20242b",
              toolbar_text="#e6e9ef", editor_bg="#1d2026", editor_fg="#e6e9ef", muted="#667")
_DARK = dict(window="#1b1e24", base="#22262e", alt="#262b34", text="#e6e9ef",
             panel="#2a2f3a", border="#3a414e", header="#2a2f3a", toolbar="#15171c",
             toolbar_text="#e6e9ef", editor_bg="#15171c", editor_fg="#e6e9ef", muted="#9aa6b8")


def _qss(c: dict, accent: str, hover: str, press: str) -> str:
    return f"""
QMainWindow, QWidget {{ font-size: 10pt; color: {c['text']}; }}
QToolBar {{ background: {c['toolbar']}; border: 0; padding: 5px; spacing: 6px; }}
QToolBar QToolButton {{ color: {c['toolbar_text']}; padding: 6px 12px; border-radius: 6px; font-weight: 600; }}
QToolBar QToolButton:hover {{ background: #333c4d; }}
QToolBar QToolButton:pressed {{ background: {accent}; }}
QToolBar QToolButton:disabled {{ color: #5a6472; }}
QMenuBar {{ background: {c['toolbar']}; color: {c['toolbar_text']}; }}
QMenuBar::item:selected {{ background: {accent}; }}
QMenu::item:selected {{ background: {accent}; color: white; }}
QDockWidget {{ font-weight: 600; }}
QDockWidget::title {{ background: {c['panel']}; padding: 6px; }}
QTabWidget::pane {{ border: 1px solid {c['border']}; }}
QTabBar::tab {{ background: {c['panel']}; padding: 7px 14px; border: 1px solid {c['border']}; border-bottom: 0; color: {c['text']}; }}
QTabBar::tab:hover {{ background: {c['base']}; }}
QTabBar::tab:selected {{ background: {c['base']}; border-bottom: 2px solid {accent}; }}
QHeaderView::section {{ background: {c['header']}; padding: 5px; border: 0; border-right: 1px solid {c['border']}; font-weight: 600; color: {c['text']}; }}
QTableView {{ background: {c['base']}; gridline-color: {c['border']}; selection-background-color: {accent}; selection-color: white; }}
QPushButton {{ background: {accent}; color: white; padding: 7px 14px; border-radius: 6px; border: 0; font-weight: 600; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {press}; }}
QPushButton:disabled {{ background: #b8c2d6; color: #eef2f8; }}
QPushButton#ghost {{ background: {c['panel']}; color: {c['text']}; border: 1px solid {c['border']}; font-weight: 500; }}
QPushButton#ghost:hover {{ border: 1px solid {accent}; color: {accent}; }}
QPushButton#ghost:pressed {{ background: {c['border']}; }}
QPushButton#ghost:disabled {{ color: #9aa6b8; border-color: {c['border']}; }}
QPlainTextEdit, QTextEdit {{ font-family: "DejaVu Sans Mono", monospace; font-size: 10pt; background: {c['editor_bg']}; color: {c['editor_fg']}; border: 0; }}
QGraphicsView {{ background: {c['base']}; border: 1px solid {c['border']}; }}
QStatusBar {{ background: {c['toolbar']}; color: {c['muted']}; }}
QLabel#h1 {{ font-size: 13pt; font-weight: 700; color: {c['text']}; }}
QCheckBox {{ spacing: 6px; }}
QComboBox, QLineEdit, QSpinBox {{ background: {c['base']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 4px; padding: 4px; }}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{ border: 1px solid {accent}; }}
QSlider::handle:horizontal {{ background: {accent}; width: 14px; border-radius: 7px; margin: -4px 0; }}
QSlider::groove:horizontal {{ height: 6px; background: {c['border']}; border-radius: 3px; }}
"""


def apply_style(app: QApplication, theme: str = "light", accent: str = DEFAULT_ACCENT):
    c = _DARK if theme == "dark" else _LIGHT
    acc = QColor(accent)
    hover = acc.lighter(112).name() if theme == "dark" else acc.darker(110).name()
    press = acc.darker(125).name()
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(c["window"]))
    pal.setColor(QPalette.Base, QColor(c["base"]))
    pal.setColor(QPalette.AlternateBase, QColor(c["alt"]))
    pal.setColor(QPalette.Text, QColor(c["text"]))
    pal.setColor(QPalette.WindowText, QColor(c["text"]))
    pal.setColor(QPalette.Button, QColor(c["panel"]))
    pal.setColor(QPalette.ButtonText, QColor(c["text"]))
    pal.setColor(QPalette.ToolTipBase, QColor(c["base"]))
    pal.setColor(QPalette.ToolTipText, QColor(c["text"]))
    pal.setColor(QPalette.Highlight, QColor(accent))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    app.setPalette(pal)
    app.setStyleSheet(_qss(c, accent, hover, press))
