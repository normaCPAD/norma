"""Relational schema diagram: each normalized relation is a draggable box (title bar +
attributes, primary key underlined); shared attributes are drawn as foreign-key edges
that follow the boxes. Switch between the 3NF and BCNF decompositions.
"""
from __future__ import annotations
import math
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
                               QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QComboBox, QLabel,
                               QPushButton, QFileDialog)
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QFont
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF

from norma.studio.export import export_scene
from norma.studio import i18n


class RelationItem(QGraphicsRectItem):
    def __init__(self, rel, view):
        super().__init__()
        self.rel = rel; self.view = view
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemSendsScenePositionChanges)
        self.setBrush(QBrush(QColor("white"))); self.setPen(QPen(QColor("#3a4660"), 1.5))
        self.setZValue(2)
        key = set(rel.key)
        rows = "".join(f"<div>{'<u>'+a+'</u>' if a in key else a}</div>" for a in sorted(rel.attributes))
        html = (f"<div style='background:#2d7ff9;color:white;padding:2px 6px;font-weight:bold'>{rel.name}</div>"
                f"<div style='padding:3px 6px'>{rows}</div>")
        self.text = QGraphicsTextItem(self)
        self.text.setHtml(html); self.text.setFont(QFont("Sans", 8))
        br = self.text.boundingRect()
        self.setRect(0, 0, max(120, br.width() + 6), br.height() + 4)

    def center(self):
        return self.pos() + self.rect().center()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.view._update_edges()
        return super().itemChange(change, value)


class SchemaScene(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.items_by_name = {}
        self.edges = []          # (itemA, itemB, label, line_item, text_item)

    def wheelEvent(self, e):
        f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def set_relations(self, relations):
        sc = self.scene(); sc.clear(); self.items_by_name = {}; self.edges = []
        if not relations:
            sc.addText("Aucun schema (lancez l'analyse).", QFont("Sans", 11)).setDefaultTextColor(QColor("#889"))
            return
        n = len(relations); R = max(220, 70 * n / math.pi)
        for i, rel in enumerate(relations):
            it = RelationItem(rel, self)
            ang = 2 * math.pi * i / n - math.pi / 2
            it.setPos(R * math.cos(ang) - it.rect().width() / 2, R * math.sin(ang))
            sc.addItem(it); self.items_by_name[rel.name] = it
        # foreign-key edges: relations that share attributes
        names = list(self.items_by_name)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = self.items_by_name[names[i]], self.items_by_name[names[j]]
                shared = set(a.rel.attributes) & set(b.rel.attributes)
                if shared:
                    pen = QPen(QColor("#6b7891"), 1.5)
                    line = sc.addLine(QLineF(a.center(), b.center()), pen); line.setZValue(0)
                    lbl = sc.addText(", ".join(sorted(shared)), QFont("Sans", 7))
                    lbl.setDefaultTextColor(QColor("#6b7891")); lbl.setZValue(1)
                    self.edges.append((a, b, line, lbl))
        self._update_edges()
        self.setSceneRect(sc.itemsBoundingRect().adjusted(-40, -40, 40, 40))
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def _update_edges(self):
        for a, b, line, lbl in self.edges:
            ca, cb = a.center(), b.center()
            line.setLine(QLineF(ca, cb))
            lbl.setPos((ca + cb) / 2)


class SchemaView(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        t = QLabel(i18n.t("schema_title")); t.setObjectName("h1"); bar.addWidget(t); bar.addStretch(1)
        bar.addWidget(QLabel(i18n.t("form") + " :"))
        self.combo = QComboBox(); self.combo.addItems(["BCNF", "3NF"]); self.combo.currentTextChanged.connect(self.refresh)
        bar.addWidget(self.combo)
        self.relayout = QPushButton(i18n.t("relayout")); self.relayout.setObjectName("ghost"); self.relayout.clicked.connect(self.refresh)
        bar.addWidget(self.relayout)
        self.pdf = QPushButton(i18n.t("export_pdf")); self.pdf.setObjectName("ghost"); self.pdf.clicked.connect(lambda: self._export("pdf"))
        self.svg = QPushButton(i18n.t("export_svg")); self.svg.setObjectName("ghost"); self.svg.clicked.connect(lambda: self._export("svg"))
        bar.addWidget(self.pdf); bar.addWidget(self.svg)
        lay.addLayout(bar)
        self.scene = SchemaScene(); lay.addWidget(self.scene)
        self.nf = QLabel(""); self.nf.setStyleSheet("color:#556;"); lay.addWidget(self.nf)
        session.schemaChanged.connect(self.refresh)

    def _export(self, fmt):
        from norma.studio import files
        title = i18n.t("export_pdf" if fmt == "pdf" else "export_svg")
        path = files.ask_save_path(self, title, f"schema.{fmt}", f"{fmt.upper()} (*.{fmt})", fmt)
        if path and files.run_save(self, lambda p: export_scene(self.scene, p), path, title):
            self.session.status.emit(f"{i18n.t('saved')} : {path}")

    def refresh(self, *_):
        sch = self.session.schema
        rels = sch.relations_bcnf if self.combo.currentText() == "BCNF" else sch.relations_3nf
        self.scene.set_relations(rels)
        keys = " ; ".join("{" + ", ".join(sorted(k)) + "}" for k in sch.keys) or "-"
        self.nf.setText(f"{i18n.t('current_nf')} : {sch.normal_form}    •    {i18n.t('candidate_keys')} : {keys}")
