"""Centralized, robust file saving: remembers the last directory, enforces the file
extension, confirms overwrite (native dialog), reports success/errors. Used by every
export so the save experience is consistent."""
from __future__ import annotations
import os
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QMessageBox


def _settings():
    return QSettings("norma", "studio")


def last_dir() -> str:
    return str(_settings().value("last_dir", os.path.expanduser("~")))


def _remember(path: str):
    _settings().setValue("last_dir", os.path.dirname(os.path.abspath(path)))


def ask_save_path(parent, title: str, default_name: str, file_filter: str, ext: str) -> str | None:
    """Open a Save dialog starting in the last-used directory, return a path guaranteed to
    end with `.ext` (or None if cancelled)."""
    start = os.path.join(last_dir(), default_name)
    path, _ = QFileDialog.getSaveFileName(parent, title, start, file_filter)
    if not path:
        return None
    if ext and not path.lower().endswith("." + ext.lower()):
        path += "." + ext
    _remember(path)
    return path


def save_text(parent, path: str, text: str, label: str = "Fichier") -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except OSError as e:
        QMessageBox.critical(parent, "norma", f"{label} : {e}")
        return False


def run_save(parent, fn, path: str, label: str = "Fichier") -> bool:
    """Run a save callable `fn(path)` with error handling."""
    try:
        fn(path)
        return True
    except Exception as e:
        QMessageBox.critical(parent, "norma", f"{label} : {e}")
        return False
