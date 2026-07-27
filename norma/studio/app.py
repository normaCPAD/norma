"""norma-studio main window and entry point."""
from __future__ import annotations
import os, sys, traceback
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QDockWidget, QToolBar,
                               QFileDialog, QMessageBox, QDialog, QFormLayout, QComboBox, QLineEdit,
                               QSpinBox, QDialogButtonBox, QListWidget, QVBoxLayout, QLabel, QPushButton,
                               QProgressBar)
from PySide6.QtGui import QAction, QKeySequence, QActionGroup
from PySide6.QtCore import Qt, QThread, QObject, Signal

from norma.studio import i18n, prefs
from norma.studio.style import apply_style
from norma.studio.session import NormaSession
from norma.studio.widgets.data_panel import DataPanel
from norma.studio.widgets.rules_panel import RulesPanel
from norma.studio.widgets.fd_graph import FDGraphPanel
from norma.studio.widgets.schema_view import SchemaView
from norma.studio.widgets.sql_panel import SqlPanel
from norma.studio.widgets.anomaly_view import AnomalyPanel
from norma.studio.widgets.deploy_panel import DeployPanel
from norma.studio.widgets.repair_panel import RepairPanel
from norma.studio.widgets.report_panel import ReportPanel
from norma.studio.widgets.preferences import PreferencesDialog
from norma.studio import db as dbmod
from norma.studio import files
from norma.studio.assets import app_icon
from norma.export import export, FORMATS
from norma import contract as ct

_WINDOWS = []          # keep references alive across language rebuilds


class AnalyzeWorker(QObject):
    """Runs the (CPU-bound, Qt-free) analysis off the UI thread."""
    done = Signal(object, object)      # model, scores
    failed = Signal(str)

    def __init__(self, session):
        super().__init__(); self.session = session

    def run(self):
        try:
            model, scores = self.session.compute_analysis()
            self.done.emit(model, scores)
        except Exception:
            self.failed.emit(traceback.format_exc())


class DbDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("connect_db")); self.df = None
        lay = QVBoxLayout(self); form = QFormLayout()
        self.driver = QComboBox()
        for d in (dbmod.available_drivers() or ["QSQLITE"]):
            self.driver.addItem(dbmod.DRIVER_LABELS.get(d, d), d)
        self.database = QLineEdit(); self.host = QLineEdit("localhost")
        self.port = QSpinBox(); self.port.setRange(0, 65535)
        self.user = QLineEdit(); self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        form.addRow(i18n.t("db_driver"), self.driver); form.addRow(i18n.t("db_database"), self.database)
        form.addRow(i18n.t("db_host"), self.host); form.addRow(i18n.t("db_port"), self.port)
        form.addRow(i18n.t("db_user"), self.user); form.addRow(i18n.t("db_password"), self.password)
        lay.addLayout(form)
        cbtn = QPushButton(i18n.t("db_connect_btn")); cbtn.clicked.connect(self._connect); lay.addWidget(cbtn)
        lay.addWidget(QLabel(i18n.t("db_tables")))
        self.tables = QListWidget(); self.tables.itemDoubleClicked.connect(self._load); lay.addWidget(self.tables)
        bb = QDialogButtonBox(QDialogButtonBox.Cancel); bb.rejected.connect(self.reject); lay.addWidget(bb)
        self._db = None

    def _connect(self):
        try:
            self._db = dbmod.open_connection(self.driver.currentData(), self.database.text(),
                                             self.host.text(), self.port.value(), self.user.text(), self.password.text())
            self.tables.clear(); self.tables.addItems(dbmod.list_tables(self._db))
        except Exception as e:
            QMessageBox.critical(self, "Connexion", str(e))

    def _load(self, item):
        try:
            self.df = dbmod.load_table(self._db, item.text()); self.table_name = item.text(); self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Lecture", str(e))


class MainWindow(QMainWindow):
    def __init__(self, session=None):
        super().__init__()
        self.session = session or NormaSession()
        self.setWindowTitle(i18n.t("app_title"))
        self.setWindowIcon(app_icon())
        self.resize(1320, 860)

        self.tabs = QTabWidget()
        self.tabs.addTab(DataPanel(self.session), i18n.t("tab_data"))
        self.tabs.addTab(FDGraphPanel(self.session), i18n.t("tab_fdgraph"))
        self.tabs.addTab(SchemaView(self.session), i18n.t("tab_schema"))
        self.tabs.addTab(SqlPanel(self.session), i18n.t("tab_sql"))
        self.tabs.addTab(AnomalyPanel(self.session), i18n.t("tab_anomalies"))
        self.tabs.addTab(RepairPanel(self.session), i18n.t("tab_repair"))
        self.tabs.addTab(ReportPanel(self.session), i18n.t("tab_report"))
        self.tabs.addTab(DeployPanel(self.session), i18n.t("tab_deploy"))
        self.setCentralWidget(self.tabs)

        dock = QDockWidget(i18n.t("dock_constraints"), self)
        dock.setWidget(RulesPanel(self.session))
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self._build_menus()
        self.progress = QProgressBar(); self.progress.setRange(0, 0); self.progress.setMaximumWidth(160)
        self.progress.setVisible(False); self.statusBar().addPermanentWidget(self.progress)
        self._thread = None
        self.session.status.connect(lambda msg: self.statusBar().showMessage(msg, 6000))
        self.statusBar().showMessage(i18n.t("ready"))
        self._apply_cursors()
        for sig in (self.session.tableLoaded, self.session.analyzed,
                    self.session.schemaChanged, self.session.rulesChanged):
            sig.connect(self._update_actions)
        self._update_actions()

    def _apply_cursors(self):
        from PySide6.QtWidgets import QAbstractButton
        for b in self.findChildren(QAbstractButton):
            b.setCursor(Qt.PointingHandCursor)

    def _update_actions(self, *_):
        has_table = self.session.table is not None
        has_schema = bool(self.session.schema.relations_bcnf)
        has_rules = has_table and bool(self.session.enabled_objects())
        self.a_run.setEnabled(has_table)
        self.a_sql.setEnabled(has_schema)
        self.a_export_dq.setEnabled(has_rules)
        self.a_freeze.setEnabled(has_rules)
        self.a_check.setEnabled(has_table)

    def _build_menus(self):
        tb = QToolBar("Main"); tb.setMovable(False); self.addToolBar(tb)
        mb = self.menuBar()
        fmenu = mb.addMenu(i18n.t("menu_file")); vmenu = mb.addMenu(i18n.t("menu_view"))
        amenu = mb.addMenu(i18n.t("menu_analysis")); lmenu = mb.addMenu(i18n.t("menu_lang"))

        def act(text, slot, sc=None):
            a = QAction(text, self); a.triggered.connect(slot)
            if sc: a.setShortcut(QKeySequence(sc))
            return a

        self.a_open = act(i18n.t("open_data"), self.open_csv, "Ctrl+O")
        self.a_db = act(i18n.t("connect_db"), self.connect_db, "Ctrl+B")
        self.a_run = act(i18n.t("analyze"), self.analyze, "Ctrl+R")
        self.a_sql = act(i18n.t("export_sql"), self.export_sql, "Ctrl+E")
        self.a_export_dq = act(i18n.t("export_constraints"), self.export_constraints, "Ctrl+Shift+E")
        self.a_freeze = act(i18n.t("freeze_contract"), self.freeze_contract)
        self.a_check = act(i18n.t("check_contract"), self.check_contract)
        self.a_pref = act(i18n.t("preferences"), self.preferences)
        self.a_quit = act(i18n.t("quit"), self.close, "Ctrl+Q")
        for a, tip in ((self.a_open, "tip_open"), (self.a_db, "tip_db"),
                       (self.a_run, "tip_run"), (self.a_sql, "tip_sql")):
            a.setToolTip(i18n.t(tip))
        for a in (self.a_open, self.a_db, self.a_run, self.a_sql, self.a_export_dq):
            tb.addAction(a)
        for a in (self.a_open, self.a_db):
            fmenu.addAction(a)
        fmenu.addSeparator()
        for a in (self.a_sql, self.a_export_dq, self.a_freeze, self.a_check):
            fmenu.addAction(a)
        fmenu.addSeparator()
        fmenu.addAction(self.a_quit)
        vmenu.addAction(self.a_pref)
        amenu.addAction(self.a_run)
        grp = QActionGroup(self)
        for code, label in i18n.LANGUAGES.items():
            a = QAction(label, self, checkable=True); a.setChecked(code == i18n.language())
            a.triggered.connect(lambda _=False, c=code: self.set_language(c))
            grp.addAction(a); lmenu.addAction(a)

    # -- slots ---------------------------------------------------------------
    def open_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, i18n.t("open_data"), "",
            "Data (*.csv *.tsv *.parquet *.pq *.xlsx *.xls *.json *.jsonl *.ndjson);;"
            "CSV (*.csv);;Parquet (*.parquet *.pq);;Excel (*.xlsx *.xls);;JSON (*.json *.jsonl);;All (*)")
        if path:
            self._guard(lambda: self.session.load_path(path))

    def connect_db(self):
        dlg = DbDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.df is not None:
            self._guard(lambda: self.session.load_dataframe(dlg.df, dlg.table_name))

    def analyze(self):
        if self.session.table is None:
            QMessageBox.information(self, "norma", i18n.t("ready")); return
        if self._thread is not None:
            return
        self.a_run.setEnabled(False); self.progress.setVisible(True)
        self.session.status.emit(i18n.t("status_analyzing"))
        self._thread = QThread(self)
        self._worker = AnalyzeWorker(self.session); self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_analysis_done)
        self._worker.failed.connect(self._on_analysis_fail)
        self._thread.start()

    def _on_analysis_done(self, model, scores):
        self.session.apply_analysis(model, scores)
        self._end_analysis()

    def _on_analysis_fail(self, tb):
        self._end_analysis()
        QMessageBox.critical(self, "norma", tb)

    def _end_analysis(self):
        if self._thread is not None:
            self._thread.quit(); self._thread.wait(); self._thread = None
        self.a_run.setEnabled(True); self.progress.setVisible(False)

    def export_sql(self):
        from norma.studio.sql import schema_to_ddl
        from norma.studio import files
        if not self.session.schema.relations_bcnf:
            return
        path = files.ask_save_path(self, i18n.t("export_sql"), "schema.sql", "SQL (*.sql)", "sql")
        if path and files.save_text(self, path, schema_to_ddl(self.session), "SQL"):
            self.statusBar().showMessage(f"{i18n.t('saved')} : {path}", 6000)

    def export_constraints(self):
        """Export the enabled constraints to a data-quality ecosystem format."""
        if self.session.table is None or not self.session.enabled_objects():
            QMessageBox.information(self, "norma", i18n.t("ready")); return
        dlg = QDialog(self); dlg.setWindowTitle(i18n.t("export_constraints"))
        form = QFormLayout(dlg); combo = QComboBox(); combo.addItems(FORMATS)
        form.addRow(i18n.t("export_format"), combo)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); form.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        fmt = combo.currentText()
        out = QFileDialog.getExistingDirectory(self, i18n.t("choose_out_dir"), files.last_dir())
        if not out:
            return

        def do():
            report = self.session.build_report()
            written = []
            for name, content in export(report, fmt, kinds=self.session.table.kinds).items():
                dest = os.path.join(out, name)
                os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(content)
                written.append(name)
            self.statusBar().showMessage(i18n.t("exported_n").format(n=len(written), d=out), 8000)
        self._guard(do)

    def freeze_contract(self):
        """Write a versioned norma.yml contract from the enabled constraints."""
        if self.session.table is None or not self.session.enabled_objects():
            QMessageBox.information(self, "norma", i18n.t("ready")); return
        path = files.ask_save_path(self, i18n.t("freeze_contract"), "norma.yml",
                                   "YAML (*.yml *.yaml)", "yml")
        if not path:
            return

        def do():
            contract = ct.freeze(self.session.build_report())
            if files.save_text(self, path, ct.dump(contract), "contract"):
                self.statusBar().showMessage(i18n.t("contract_saved").format(path=path), 8000)
        self._guard(do)

    def check_contract(self):
        """Re-validate the current table against a saved norma.yml contract."""
        if self.session.table is None:
            QMessageBox.information(self, "norma", i18n.t("ready")); return
        path, _ = QFileDialog.getOpenFileName(self, i18n.t("open_contract"), files.last_dir(),
                                              "YAML (*.yml *.yaml);;All (*)")
        if not path:
            return

        def do():
            results = ct.check(self.session.table, ct.load(path))
            ok = sum(1 for r in results if r.ok)
            lines = []
            for r in results:
                mark = "✓" if r.ok else ("?" if r.violations < 0 else "✗")
                lines.append(f"{mark}  {r.id}: {r.detail}")
            summary = i18n.t("check_summary").format(ok=ok, total=len(results))
            QMessageBox.information(self, i18n.t("check_title"), summary + "\n\n" + "\n".join(lines))
        self._guard(do)

    def preferences(self):
        dlg = PreferencesDialog(self)
        if dlg.exec() == QDialog.Accepted:
            v = dlg.values()
            old_lang = prefs.language()
            prefs.set_many(**v)
            apply_style(QApplication.instance(), v["theme"], v["accent"])
            if v["language"] != old_lang:
                self.set_language(v["language"])

    def set_language(self, code):
        i18n.set_language(code); prefs.set_many(language=code)
        win = MainWindow(self.session); _WINDOWS.append(win); win.show()
        self.session.refresh_all()
        self.close()

    def _guard(self, fn):
        try:
            fn()
        except Exception:
            QMessageBox.critical(self, "norma", traceback.format_exc())


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("norma studio")
    app.setApplicationDisplayName("norma studio")
    app.setOrganizationName("norma")
    app.setDesktopFileName("norma-studio")   # how the taskbar/launcher resolves the icon
    app.setWindowIcon(app_icon())
    i18n.set_language(prefs.language())
    apply_style(app, prefs.theme(), prefs.accent())
    win = MainWindow(); _WINDOWS.append(win); win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
