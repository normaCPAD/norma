"""Persisted user preferences (theme, accent color, language) via QSettings."""
from __future__ import annotations
from PySide6.QtCore import QSettings

from norma.studio.style import DEFAULT_ACCENT

_S = lambda: QSettings("norma", "studio")


def get(key, default):
    return _S().value(key, default)


def set_many(**kw):
    s = _S()
    for k, v in kw.items():
        s.setValue(k, v)
    s.sync()


def theme() -> str:
    return str(get("theme", "light"))


def accent() -> str:
    return str(get("accent", DEFAULT_ACCENT))


def language() -> str:
    return str(get("language", "fr"))
