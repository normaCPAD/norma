"""Clean-database panel: configure and build a SQLite database from the discovered
schema (anomaly-free data + constraint views + triggers)."""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox,
                               QPushButton, QPlainTextEdit, QLineEdit, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt

from norma.studio import i18n
from norma.studio.deploy import build_script, create_sqlite
from norma.studio.widgets.sql_panel import SqlHighlighter


class DeployPanel(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        lay = QVBoxLayout(self)
        self.title = QLabel(i18n.t("deploy_title")); self.title.setObjectName("h1")
        lay.addWidget(self.title)
        self.desc = QLabel(i18n.t("deploy_desc")); self.desc.setWordWrap(True); self.desc.setStyleSheet("color:#667;")
        lay.addWidget(self.desc)

        row = QHBoxLayout()
        self.lbl_thr = QLabel(i18n.t("clean_threshold"))
        row.addWidget(self.lbl_thr)
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(50, 99); self.slider.setValue(70)
        self.slider.setFixedWidth(180); self.slider.valueChanged.connect(self._refresh)
        row.addWidget(self.slider)
        self.thr_val = QLabel("0.70"); row.addWidget(self.thr_val); row.addStretch(1)
        lay.addLayout(row)

        opt = QHBoxLayout()
        self.cb_trig = QCheckBox(i18n.t("incl_triggers")); self.cb_trig.setChecked(True); self.cb_trig.toggled.connect(self._refresh)
        self.cb_view = QCheckBox(i18n.t("incl_views")); self.cb_view.setChecked(True); self.cb_view.toggled.connect(self._refresh)
        opt.addWidget(self.cb_trig); opt.addWidget(self.cb_view); opt.addStretch(1)
        lay.addLayout(opt)

        self.script = QPlainTextEdit(); SqlHighlighter(self.script.document())
        lay.addWidget(self.script)

        bottom = QHBoxLayout()
        self.gen = QPushButton(i18n.t("gen_script")); self.gen.setObjectName("ghost"); self.gen.clicked.connect(self._refresh)
        self.create = QPushButton(i18n.t("create_db")); self.create.clicked.connect(self._create)
        bottom.addStretch(1); bottom.addWidget(self.gen); bottom.addWidget(self.create)
        lay.addLayout(bottom)
        self.msg = QLabel(""); self.msg.setStyleSheet("color:#667;"); lay.addWidget(self.msg)

        session.schemaChanged.connect(self._refresh)
        session.scoresChanged.connect(self._refresh)

    def _thr(self):
        return self.slider.value() / 100.0

    def _refresh(self, *_):
        self.thr_val.setText(f"{self._thr():.2f}")
        has = bool(self.session.schema.relations_bcnf)
        self.gen.setEnabled(has); self.create.setEnabled(has)
        if self.session.table is None or not has:
            self.script.setPlainText("-- " + i18n.t("ready"))
            return
        self.script.setPlainText(build_script(self.session, self._thr(),
                                              self.cb_trig.isChecked(), self.cb_view.isChecked()))

    def _create(self):
        from norma.studio import files
        if not self.session.schema.relations_bcnf:
            return
        path = files.ask_save_path(self, i18n.t("create_db"), "clean.db", "SQLite (*.db *.sqlite)", "db")
        if not path:
            return
        try:
            n_clean, n_tot, counts = create_sqlite(self.session, path, self._thr(),
                                                   self.cb_trig.isChecked(), self.cb_view.isChecked())
            tbls = ", ".join(f"{k}={v}" for k, v in counts.items())
            self.msg.setText(f"{i18n.t('saved')} : {path}  •  {n_clean}/{n_tot} lignes propres  •  {tbls}")
            self.session.status.emit(f"{i18n.t('saved')} : {path}")
        except Exception as e:
            QMessageBox.critical(self, "norma", str(e))
