"""SQL panel: generate DDL from the discovered schema, and parse hand-edited DDL back
into the visual schema (bidirectional visual <-> SQL)."""
from __future__ import annotations
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton,
                               QLabel, QComboBox)
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import Qt

from norma.studio.sql import schema_to_ddl, parse_ddl
from norma.studio import i18n

_KEYWORDS = (r"\b(CREATE|TABLE|PRIMARY|KEY|FOREIGN|REFERENCES|CHECK|ASSERTION|NOT|EXISTS|"
             r"SELECT|FROM|WHERE|AND|OR|ALTER|ADD|CONSTRAINT|UNIQUE|VARCHAR|DOUBLE|"
             r"PRECISION|INTEGER|INT)\b")


class SqlHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self.kw = QTextCharFormat(); self.kw.setForeground(QColor("#6cb6ff")); self.kw.setFontWeight(QFont.Bold)
        self.com = QTextCharFormat(); self.com.setForeground(QColor("#7d8aa0")); self.com.setFontItalic(True)
        self.str = QTextCharFormat(); self.str.setForeground(QColor("#9ece6a"))

    def highlightBlock(self, text):
        for m in re.finditer(_KEYWORDS, text, re.IGNORECASE):
            self.setFormat(m.start(), m.end() - m.start(), self.kw)
        for m in re.finditer(r"\([0-9]+\)|'[^']*'", text):
            self.setFormat(m.start(), m.end() - m.start(), self.str)
        c = text.find("--")
        if c >= 0:
            self.setFormat(c, len(text) - c, self.com)


class SqlPanel(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        t = QLabel(i18n.t("sql_title")); t.setObjectName("h1"); bar.addWidget(t); bar.addStretch(1)
        self.form = QComboBox(); self.form.addItems(["BCNF", "3NF"])
        bar.addWidget(QLabel(i18n.t("form") + " :")); bar.addWidget(self.form)
        self.gen = QPushButton(i18n.t("generate_from_schema")); self.gen.clicked.connect(self.generate)
        self.apply = QPushButton(i18n.t("apply_sql")); self.apply.setObjectName("ghost"); self.apply.clicked.connect(self.apply_sql)
        bar.addWidget(self.gen); bar.addWidget(self.apply)
        lay.addLayout(bar)
        self.edit = QPlainTextEdit(); self.edit.setTabStopDistance(28)
        SqlHighlighter(self.edit.document())
        lay.addWidget(self.edit)
        self.msg = QLabel(""); self.msg.setStyleSheet("color:#667;"); lay.addWidget(self.msg)
        session.schemaChanged.connect(self.generate)

    def generate(self):
        if self.session.table is None or not self.session.schema.relations_bcnf:
            self.edit.setPlainText(i18n.t("sql_placeholder"))
            return
        self.edit.setPlainText(schema_to_ddl(self.session, which=self.form.currentText().lower()))
        self.msg.setText(i18n.t("sql_generated"))

    def apply_sql(self):
        rels = parse_ddl(self.edit.toPlainText())
        if not rels:
            self.msg.setText(i18n.t("sql_none"))
            return
        self.session.set_external_relations(rels)
        self.msg.setText(i18n.t("sql_parsed").format(n=len(rels)))
