"""Constraint panel: lists the discovered + expert constraints, lets the user enable or
disable each (which re-synthesizes the schema live) and add expert FDs."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QDialog, QListWidget, QComboBox, QDialogButtonBox, QAbstractItemView, QFormLayout,
    QHeaderView)
from PySide6.QtCore import Qt

from norma.studio import i18n

_KIND_COLOR = {"FD": "#1b8a5a", "composite-DC": "#1b6f8a", "order-DC": "#b6720d",
               "linear-DC": "#8a1b6f"}


class AddExpertDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("expert_title"))
        form = QFormLayout(self)
        self.lhs = QListWidget(); self.lhs.addItems(columns)
        self.lhs.setSelectionMode(QAbstractItemView.MultiSelection)
        self.lhs.setMaximumHeight(160)
        self.rhs = QComboBox(); self.rhs.addItems(columns)
        form.addRow(QLabel(i18n.t("expert_sources")))
        form.addRow(self.lhs)
        form.addRow(i18n.t("expert_target"), self.rhs)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        form.addRow(bb)

    def result_fd(self):
        lhs = [i.text() for i in self.lhs.selectedItems()]
        return lhs, self.rhs.currentText()


class RulesPanel(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        lay = QVBoxLayout(self)
        head = QLabel(i18n.t("rules_title")); head.setObjectName("h1")
        lay.addWidget(head)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", i18n.t("col_type"), i18n.t("col_rule"), i18n.t("col_conf")])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 26); self.table.setColumnWidth(1, 92); self.table.setColumnWidth(3, 52)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self.table)

        row = QHBoxLayout()
        self.add_btn = QPushButton(i18n.t("add_expert")); self.add_btn.clicked.connect(self._add_expert)
        self.del_btn = QPushButton(i18n.t("remove")); self.del_btn.setObjectName("ghost"); self.del_btn.clicked.connect(self._remove)
        row.addWidget(self.add_btn); row.addWidget(self.del_btn); row.addStretch(1)
        lay.addLayout(row)
        self.summary = QLabel(""); self.summary.setStyleSheet("color:#556;")
        lay.addWidget(self.summary)

        session.rulesChanged.connect(self.refresh)
        self._loading = False

    def refresh(self):
        self._loading = True
        rules = self.session.rules
        self.table.setRowCount(len(rules))
        for i, r in enumerate(rules):
            chk = QTableWidgetItem(); chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if r.enabled else Qt.Unchecked)
            self.table.setItem(i, 0, chk)
            kind = QTableWidgetItem(r.kind + ("*" if r.source == "expert" else ""))
            kind.setForeground(Qt.black)
            color = _KIND_COLOR.get(r.kind)
            if color:
                kind.setForeground(Qt.GlobalColor.black)
            self.table.setItem(i, 1, kind)
            txt = QTableWidgetItem(r.text)
            self.table.setItem(i, 2, txt)
            conf = QTableWidgetItem(f"{r.confidence:.2f}")
            self.table.setItem(i, 3, conf)
        self._loading = False
        n_on = sum(1 for r in rules if r.enabled)
        self.summary.setText(f"{n_on}/{len(rules)} {i18n.t('active')}  •  "
                             f"{i18n.t('normal_form')} : {self.session.schema.normal_form}")

    def _on_item_changed(self, item):
        if self._loading or item.column() != 0:
            return
        self.session.set_enabled(item.row(), item.checkState() == Qt.Checked)
        self.summary.setText(f"forme normale : {self.session.schema.normal_form}")

    def _add_expert(self):
        if self.session.table is None:
            return
        dlg = AddExpertDialog(self.session.table.modeling_columns(), self)
        if dlg.exec() == QDialog.Accepted:
            lhs, rhs = dlg.result_fd()
            if lhs and rhs and rhs not in lhs:
                self.session.add_expert_fd(lhs, rhs)

    def _remove(self):
        rows = {i.row() for i in self.table.selectedItems()}
        for r in sorted(rows, reverse=True):
            self.session.remove_rule(r)
