"""Repair panel: preview the proposed cell corrections (before -> after, rule, confidence),
then apply ('clean') or undo. Safe-zone thresholds are exposed."""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QSpinBox,
                               QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from norma.studio import i18n
from norma.repair import RepairConfig


class RepairPanel(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        lay = QVBoxLayout(self)
        self.title = QLabel(i18n.t("repair_title")); self.title.setObjectName("h1")
        lay.addWidget(self.title)
        self.desc = QLabel(i18n.t("repair_desc")); self.desc.setWordWrap(True); self.desc.setStyleSheet("color:#667;")
        lay.addWidget(self.desc)

        opt = QHBoxLayout()
        opt.addWidget(QLabel(i18n.t("confidence")))
        self.conf = QSlider(Qt.Horizontal); self.conf.setRange(50, 100); self.conf.setValue(90)
        self.conf.setFixedWidth(140); self.conf.valueChanged.connect(self._preview)
        opt.addWidget(self.conf); self.conf_lbl = QLabel("0.90"); opt.addWidget(self.conf_lbl)
        opt.addSpacing(12); opt.addWidget(QLabel(i18n.t("min_group")))
        self.group = QSpinBox(); self.group.setRange(1, 100); self.group.setValue(5); self.group.valueChanged.connect(self._preview)
        opt.addWidget(self.group)
        self.cb_fd = QCheckBox("FD"); self.cb_fd.setChecked(True); self.cb_fd.toggled.connect(self._preview)
        self.cb_ord = QCheckBox(i18n.t("order")); self.cb_ord.setChecked(True); self.cb_ord.toggled.connect(self._preview)
        self.cb_lin = QCheckBox(i18n.t("linear")); self.cb_lin.setChecked(True); self.cb_lin.toggled.connect(self._preview)
        for w in (self.cb_fd, self.cb_ord, self.cb_lin):
            opt.addWidget(w)
        opt.addStretch(1)
        lay.addLayout(opt)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([i18n.t("col_row"), i18n.t("col_column"),
                                              i18n.t("col_before"), i18n.t("col_after"), i18n.t("col_rule")])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table)

        bar = QHBoxLayout()
        self.count = QLabel(""); bar.addWidget(self.count); bar.addStretch(1)
        self.preview_btn = QPushButton(i18n.t("preview")); self.preview_btn.setObjectName("ghost"); self.preview_btn.clicked.connect(self._preview)
        self.undo_btn = QPushButton(i18n.t("undo")); self.undo_btn.setObjectName("ghost"); self.undo_btn.clicked.connect(self.session.undo_repair)
        self.apply_btn = QPushButton(i18n.t("apply_clean")); self.apply_btn.clicked.connect(self.session.apply_repair)
        self.apply_btn.setEnabled(False); self.undo_btn.setEnabled(False)
        bar.addWidget(self.preview_btn); bar.addWidget(self.undo_btn); bar.addWidget(self.apply_btn)
        lay.addLayout(bar)

        session.analyzed.connect(self._preview)
        session.repairReady.connect(self._fill)
        session.repaired.connect(self._after_apply)

    def _config(self):
        return RepairConfig(min_confidence=self.conf.value() / 100.0, min_group=self.group.value(),
                            repair_fd=self.cb_fd.isChecked(), repair_order=self.cb_ord.isChecked(),
                            repair_linear=self.cb_lin.isChecked())

    def _preview(self, *_):
        self.conf_lbl.setText(f"{self.conf.value()/100:.2f}")
        if self.session.table is None or not self.session.rules:
            return
        self.session.compute_repair(self._config())

    def _fill(self):
        r = self.session.repair_result
        if r is None:
            return
        self.table.setRowCount(min(len(r.edits), 500))
        for i, e in enumerate(r.edits[:500]):
            for j, v in enumerate([e.row, e.column, e.old, e.new, e.rule]):
                it = QTableWidgetItem(str(v))
                if j == 3:
                    it.setForeground(QColor("#1b8a5a"))
                self.table.setItem(i, j, it)
        by = ", ".join(f"{c}:{k}" for c, k in sorted(r.by_column.items(), key=lambda z: -z[1])[:8])
        self.count.setText(f"{r.n_edits} {i18n.t('edits_count')}  ({by})")
        self.apply_btn.setEnabled(r.n_edits > 0)

    def _after_apply(self):
        self.undo_btn.setEnabled(self.session._backup is not None)
        self.apply_btn.setEnabled(self.session._backup is None and
                                  self.session.repair_result is not None and
                                  self.session.repair_result.n_edits > 0)
