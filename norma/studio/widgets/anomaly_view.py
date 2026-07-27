"""Anomaly panel: the data grid with cells shaded by their violation score."""
from __future__ import annotations
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableView, QLabel, QSlider
from PySide6.QtCore import Qt

from norma.studio.widgets.models import AnomalyModel
from norma.studio import i18n


class AnomalyPanel(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.model = AnomalyModel()
        lay = QVBoxLayout(self)

        top = QHBoxLayout()
        title = QLabel(i18n.t("anomaly_title")); title.setObjectName("h1")
        top.addWidget(title); top.addStretch(1)
        top.addWidget(QLabel(i18n.t("threshold")))
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(50, 99); self.slider.setValue(50)
        self.slider.setFixedWidth(160); self.slider.valueChanged.connect(self._refresh)
        top.addWidget(self.slider)
        self.count = QLabel("")
        top.addWidget(self.count)
        lay.addLayout(top)

        self.view = QTableView(); self.view.setModel(self.model)
        self.view.setAlternatingRowColors(False)
        lay.addWidget(self.view)
        self.legend = QLabel(i18n.t("anomaly_legend"))
        self.legend.setStyleSheet("color:#667;")
        lay.addWidget(self.legend)
        session.scoresChanged.connect(self._refresh)

    def _refresh(self, *_):
        t, sc = self.session.table, self.session.scores
        if t is None:
            return
        df = t.df.head(3000)
        scores = sc[:3000] if sc is not None else None
        self.model.set_scores(df, scores)
        if scores is not None:
            thr = self.slider.value() / 100.0
            n = int((scores > thr).sum())
            rows = int((scores.max(axis=1) > thr).sum())
            self.count.setText(f"{n} cellules / {rows} lignes au-dessus de {thr:.2f}")
