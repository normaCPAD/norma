"""Data preview panel: the loaded table as a grid."""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel
from PySide6.QtCore import Qt

from norma.studio import i18n
from norma.studio.widgets.models import DataFrameModel


class DataPanel(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.model = DataFrameModel()
        lay = QVBoxLayout(self)
        self.title = QLabel(i18n.t("no_table")); self.title.setObjectName("h1")
        lay.addWidget(self.title)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setAlternatingRowColors(True)
        self.view.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.view)
        session.tableLoaded.connect(self._on_loaded)

    def _on_loaded(self, df):
        self.model.set_dataframe(df.head(2000))
        t = self.session.table
        self.title.setText(f"{t.name} — {t.n} × {len(t.columns)}  ({i18n.t('preview')} {min(2000, t.n)})")
