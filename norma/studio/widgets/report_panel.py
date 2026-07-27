"""Quality report panel: renders the 'data health' report and exports it to HTML or PDF."""
from __future__ import annotations
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QTextBrowser, QFileDialog)
from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout, QFont
from PySide6.QtCore import QSizeF, QMarginsF

from norma.studio import i18n


class ReportPanel(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.title = QLabel(i18n.t("report_title")); self.title.setObjectName("h1")
        bar.addWidget(self.title); bar.addStretch(1)
        self.refresh = QPushButton(i18n.t("refresh")); self.refresh.setObjectName("ghost"); self.refresh.clicked.connect(self._refresh)
        self.exp_html = QPushButton(i18n.t("export_html")); self.exp_html.setObjectName("ghost"); self.exp_html.clicked.connect(lambda: self._export("html"))
        self.exp_pdf = QPushButton(i18n.t("export_pdf")); self.exp_pdf.clicked.connect(lambda: self._export("pdf"))
        for b in (self.exp_html, self.exp_pdf):
            b.setEnabled(False)
        bar.addWidget(self.refresh); bar.addWidget(self.exp_html); bar.addWidget(self.exp_pdf)
        lay.addLayout(bar)
        self.view = QTextBrowser(); self.view.setOpenExternalLinks(True)
        self.view.setStyleSheet("background:white;color:#1a1f29;")
        lay.addWidget(self.view)
        self._html = ""

        for sig in (session.analyzed, session.schemaChanged, session.repaired, session.scoresChanged):
            sig.connect(self._refresh)

    def _refresh(self):
        self._html = self.session.quality_html()
        self.view.setHtml(self._html)
        ready = self.session.table is not None and bool(self.session.schema.relations_bcnf)
        self.exp_html.setEnabled(ready); self.exp_pdf.setEnabled(ready)

    def _export(self, fmt):
        from norma.studio import files
        if not self._html:
            self._refresh()
        if fmt == "html":
            path = files.ask_save_path(self, i18n.t("export_html"), "rapport_qualite.html", "HTML (*.html)", "html")
            ok = path and files.save_text(self, path, self._html, "HTML")
        else:
            path = files.ask_save_path(self, i18n.t("export_pdf"), "rapport_qualite.pdf", "PDF (*.pdf)", "pdf")
            ok = path and files.run_save(self, self._print_pdf, path, "PDF")
        if path and ok:
            self.session.status.emit(f"{i18n.t('saved')} : {path}")

    def _print_pdf(self, path):
        from PySide6.QtPrintSupport import QPrinter
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat); printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageMargins(QMarginsF(14, 14, 14, 14), QPageLayout.Millimeter)
        doc = QTextDocument(); doc.setDefaultFont(QFont("Helvetica", 10))
        doc.setHtml(self._html)
        doc.setPageSize(QSizeF(printer.pageRect(QPrinter.Point).size()))  # points -> readable scale
        doc.print_(printer)
