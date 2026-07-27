"""Qt table models: a plain DataFrame view and an anomaly heatmap view."""
from __future__ import annotations
import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtGui import QColor


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame | None = None):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()

    def set_dataframe(self, df: pd.DataFrame):
        self.beginResetModel(); self._df = df; self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return str(self._df.iat[index.row(), index.column()])
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)


class AnomalyModel(DataFrameModel):
    """DataFrame view whose cell background encodes the per-cell violation score."""
    def __init__(self):
        super().__init__()
        self._scores: np.ndarray | None = None

    def set_scores(self, df: pd.DataFrame, scores: np.ndarray | None):
        self._scores = scores
        self.set_dataframe(df)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.BackgroundRole and self._scores is not None:
            r, c = index.row(), index.column()
            if r < self._scores.shape[0] and c < self._scores.shape[1]:
                s = float(self._scores[r, c])
                if s > 0.5:                       # white -> amber -> red ramp
                    t = min(1.0, (s - 0.5) * 2)
                    return QColor(255, int(210 - 150 * t), int(150 - 150 * t))
            return None
        if role == Qt.ToolTipRole and self._scores is not None:
            r, c = index.row(), index.column()
            if r < self._scores.shape[0] and c < self._scores.shape[1]:
                return f"violation = {self._scores[r, c]:.3f}"
        return super().data(index, role)
