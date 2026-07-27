"""Preferences dialog: theme (light/dark), accent color, language."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QFormLayout, QComboBox, QPushButton, QDialogButtonBox,
                               QColorDialog)
from PySide6.QtGui import QColor

from norma.studio import i18n, prefs


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("preferences"))
        form = QFormLayout(self)
        self.theme = QComboBox()
        self.theme.addItem(i18n.t("pref_light"), "light")
        self.theme.addItem(i18n.t("pref_dark"), "dark")
        self.theme.setCurrentIndex(0 if prefs.theme() == "light" else 1)

        self._accent = prefs.accent()
        self.accent_btn = QPushButton(self._accent); self.accent_btn.clicked.connect(self._pick)
        self._paint_accent()

        self.lang = QComboBox()
        for code, label in i18n.LANGUAGES.items():
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(list(i18n.LANGUAGES).index(prefs.language()))

        form.addRow(i18n.t("pref_theme"), self.theme)
        form.addRow(i18n.t("pref_accent"), self.accent_btn)
        form.addRow(i18n.t("pref_language"), self.lang)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._accent), self, i18n.t("pref_accent"))
        if c.isValid():
            self._accent = c.name(); self.accent_btn.setText(self._accent); self._paint_accent()

    def _paint_accent(self):
        self.accent_btn.setStyleSheet(f"background:{self._accent}; color:white; padding:6px 12px; border-radius:6px;")

    def values(self):
        return {"theme": self.theme.currentData(),
                "accent": self._accent,
                "language": self.lang.currentData()}
