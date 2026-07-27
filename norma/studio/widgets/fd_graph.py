"""Functional-dependency graph with draggable attribute nodes and edges that follow.

A *single-source* FD ``A -> B`` is drawn as one green arrow ``A -> B``.
A *composite* FD ``{A,B} -> C`` is drawn through an explicit **AND-junction** node
(``∧``): the determinant attributes connect to the junction by plain teal connectors
(no arrowhead), and a single teal arrow leaves the junction towards each determined
attribute. One junction is shared by all FDs with the *same* left-hand side, so
``{A,B} -> C`` and ``{A,B} -> D`` share a junction and read as one composite key --
unambiguously distinct from the independent ``A -> {C,D}`` plus ``B -> {C,D}``.
Arrange nodes by hand, then export the scene as a vector PDF/SVG for the paper.
"""
from __future__ import annotations
import math
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
                               QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsItem, QGraphicsPathItem,
                               QPushButton, QLabel, QFileDialog)
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QFont, QPainterPath
from PySide6.QtCore import Qt, QPointF, QLineF

from norma.core.constraint import FunctionalDependency
from norma.studio.export import export_scene
from norma.studio import i18n

NODE_R = 26
JUNC_R = 9
GREEN = "#1b8a5a"   # single-source FD
TEAL = "#0f7d8a"    # composite FD (via junction)


class NodeItem(QGraphicsEllipseItem):
    radius = NODE_R

    def __init__(self, name, governed, view):
        super().__init__(-NODE_R, -NODE_R, 2 * NODE_R, 2 * NODE_R)
        self.name = name; self.view = view
        col = QColor("#2d7ff9") if governed else QColor("#9aa6b8")
        self.setBrush(QBrush(QColor("#eaf2ff") if governed else QColor("#eef1f6")))
        self.setPen(QPen(col.darker(120), 2))
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable |
                      QGraphicsItem.ItemSendsScenePositionChanges)
        self.setZValue(2)
        # Keep a reference: a QGraphicsItem parent does not own its child in PySide6,
        # so a local-only text item gets garbage-collected and the label vanishes.
        self.label = QGraphicsTextItem(name, self); self.label.setFont(QFont("Sans", 8))
        self.label.setDefaultTextColor(QColor("#22303f"))
        br = self.label.boundingRect(); self.label.setPos(-br.width() / 2, -br.height() / 2)

    def center(self):
        return self.pos()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged and self.view:
            self.view.update_edges()
        return super().itemChange(change, value)


class JunctionItem(QGraphicsEllipseItem):
    """AND-junction for a composite determinant. Auto-placed at the centroid of its
    member attribute nodes, so it follows when they are dragged."""
    radius = JUNC_R

    def __init__(self, members):
        super().__init__(-JUNC_R, -JUNC_R, 2 * JUNC_R, 2 * JUNC_R)
        self.members = members
        self.setBrush(QBrush(QColor("#d7f0f2")))
        self.setPen(QPen(QColor(TEAL), 2))
        self.setZValue(1)
        self.label = QGraphicsTextItem("∧", self); self.label.setFont(QFont("Sans", 8, QFont.Bold))
        self.label.setDefaultTextColor(QColor(TEAL))
        br = self.label.boundingRect(); self.label.setPos(-br.width() / 2, -br.height() / 2)
        self.reposition()

    def center(self):
        return self.pos()

    def reposition(self):
        n = len(self.members)
        if not n:
            return
        x = sum(m.center().x() for m in self.members) / n
        y = sum(m.center().y() for m in self.members) / n
        self.setPos(x, y)


class ArrowEdge(QGraphicsPathItem):
    def __init__(self, nfrom, nto, color, dashed=False, head=True, width=2.0, curv=0.0):
        super().__init__()
        self.nfrom, self.nto, self.head, self.curv = nfrom, nto, head, curv
        pen = QPen(QColor(color), width); pen.setCapStyle(Qt.RoundCap)
        if dashed:
            pen.setStyle(Qt.DashLine)
        self.setPen(pen); self.setZValue(0)
        self.update_path()

    def update_path(self):
        a, b = self.nfrom.center(), self.nto.center()
        ra, rb = self.nfrom.radius, self.nto.radius
        full = QLineF(a, b)
        if full.length() < ra + rb + 2:
            self.setPath(QPainterPath()); return
        t = QLineF(a, b); t.setLength(full.length() - rb); b2 = t.p2()
        s = QLineF(a, b2); s.setLength(ra); a2 = s.p2()
        path = QPainterPath(a2)
        if abs(self.curv) < 1e-6:                       # straight
            path.lineTo(b2)
            ang = math.atan2(b2.y() - a2.y(), b2.x() - a2.x())
        else:                                           # quadratic arc (for A<->B pairs)
            mx, my = (a2.x() + b2.x()) / 2, (a2.y() + b2.y()) / 2
            dx, dy = b2.x() - a2.x(), b2.y() - a2.y()
            L = math.hypot(dx, dy) or 1.0
            cx, cy = mx - dy / L * self.curv, my + dx / L * self.curv
            path.quadTo(QPointF(cx, cy), b2)
            ang = math.atan2(b2.y() - cy, b2.x() - cx)  # tangent at the arrow tip
        if self.head:
            h, w = 11, 0.42
            for sgn in (-1, 1):
                path.moveTo(b2)
                path.lineTo(QPointF(b2.x() - h * math.cos(ang + sgn * w),
                                    b2.y() - h * math.sin(ang + sgn * w)))
        self.setPath(path)


class FDGraphView(QGraphicsView):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.edges = []
        self.junctions = []
        session.rulesChanged.connect(self.rebuild)
        session.schemaChanged.connect(self.rebuild)

    def wheelEvent(self, e):
        f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        r = self.scene().sceneRect()
        if not r.isNull():
            self.fitInView(r, Qt.KeepAspectRatio)

    def update_edges(self):
        for j in self.junctions:
            j.reposition()
        for e in self.edges:
            e.update_path()

    def _add_legend(self, sc):
        """Small colour key, drawn above the graph so it is included in exports."""
        br = sc.itemsBoundingRect()
        x, y = br.left(), br.top() - 30
        t1 = sc.addText(i18n.t("fd_legend_simple"), QFont("Sans", 8))
        t1.setDefaultTextColor(QColor(GREEN)); t1.setPos(x, y)
        t2 = sc.addText(i18n.t("fd_legend_composite"), QFont("Sans", 8))
        t2.setDefaultTextColor(QColor(TEAL))
        t2.setPos(x + t1.boundingRect().width() + 24, y)

    def rebuild(self):
        sc = self.scene(); sc.clear(); self.edges = []; self.junctions = []
        fds = [r.obj for r in self.session.rules
               if r.enabled and isinstance(r.obj, FunctionalDependency)]
        fd_attrs = {a for fd in fds for a in (set(fd.lhs) | {fd.rhs})}
        # Cover every modelled column -- not only those touched by an FD -- so the FD
        # graph spans the same attributes as the relational schema. Columns governed by
        # no FD appear as isolated (grey) nodes, mirroring CPAD's ungoverned columns.
        cols = set()
        tbl = getattr(self.session, "table", None)
        if tbl is not None:
            try:
                cols = set(tbl.modeling_columns())
            except Exception:
                cols = set()
        attrs = sorted(cols | fd_attrs)
        if not attrs:
            sc.addText("Aucune dependance fonctionnelle.", QFont("Sans", 11)).setDefaultTextColor(QColor("#889"))
            return
        governed = {fd.rhs for fd in fds}

        # --- group attributes by connected component of the FD graph, so each
        # independent dependency cluster is laid out on its own circle (instead of
        # one big circle where unrelated clusters tangle their edges across it). ---
        parent = {a: a for a in attrs}

        def find(x):
            r = x
            while parent[r] != r:
                r = parent[r]
            while parent[x] != r:
                parent[x], x = r, parent[x]
            return r

        for fd in fds:
            members = list(fd.lhs) + [fd.rhs]
            for m in members[1:]:
                parent[find(members[0])] = find(m)
        clusters = {}
        for a in attrs:
            clusters.setdefault(find(a), []).append(a)
        fd_comps = sorted((sorted(v) for v in clusters.values() if len(v) > 1),
                          key=lambda c: -len(c))
        isolated = sorted(a for v in clusters.values() if len(v) == 1 for a in v)

        nodes = {}
        pad = 80.0
        x = 0.0
        max_r = 0.0
        for comp_attrs in fd_comps:                     # each component -> its own circle
            k = len(comp_attrs)
            r = max(95.0, 30.0 * k / math.pi * 1.8)
            cx = x + r
            for i, a in enumerate(comp_attrs):
                ang = 2 * math.pi * i / k - math.pi / 2
                it = NodeItem(a, a in governed, self)
                it.setPos(cx + r * math.cos(ang), r * math.sin(ang))
                sc.addItem(it); nodes[a] = it
            x = cx + r + pad
            max_r = max(max_r, r)
        if isolated:                                    # ungoverned columns -> bottom strip
            step = 82.0
            row_w = (len(isolated) - 1) * step
            x0 = (max(x - pad, row_w) - row_w) / 2
            y = max_r + 130.0
            for j, a in enumerate(isolated):
                it = NodeItem(a, a in governed, self)
                it.setPos(x0 + j * step, y)
                sc.addItem(it); nodes[a] = it

        # Single-source FDs: one green arrow (curved if A<->B is mutual). Composite FDs:
        # group by left-hand side so every RHS of the same determinant shares a junction.
        single_pairs = {(fd.lhs[0], fd.rhs) for fd in fds if not fd.is_composite}
        comp = {}  # frozenset(lhs) -> {"lhs": tuple, "rhs": [..]}
        for fd in fds:
            if fd.is_composite:
                g = comp.setdefault(frozenset(fd.lhs), {"lhs": fd.lhs, "rhs": []})
                g["rhs"].append(fd.rhs)
            else:
                s, t = fd.lhs[0], fd.rhs
                curv = 16.0 if (t, s) in single_pairs else 0.0
                e = ArrowEdge(nodes[s], nodes[t], GREEN, curv=curv)
                sc.addItem(e); self.edges.append(e)

        for g in comp.values():
            members = [nodes[a] for a in g["lhs"]]
            j = JunctionItem(members); sc.addItem(j); self.junctions.append(j)
            for m in members:                                   # LHS -> junction (no head)
                e = ArrowEdge(m, j, TEAL, head=False, width=1.6)
                sc.addItem(e); self.edges.append(e)
            for rhs in g["rhs"]:                                 # junction -> RHS (arrow)
                e = ArrowEdge(j, nodes[rhs], TEAL)
                sc.addItem(e); self.edges.append(e)

        self.update_edges()
        if comp:
            self._add_legend(sc)
        self.setSceneRect(sc.itemsBoundingRect().adjusted(-40, -40, 40, 40))
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)


class FDGraphPanel(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.title = QLabel(i18n.t("tab_fdgraph")); self.title.setObjectName("h1")
        bar.addWidget(self.title); bar.addStretch(1)
        self.pdf = QPushButton(i18n.t("export_pdf")); self.pdf.setObjectName("ghost"); self.pdf.clicked.connect(lambda: self._export("pdf"))
        self.svg = QPushButton(i18n.t("export_svg")); self.svg.setObjectName("ghost"); self.svg.clicked.connect(lambda: self._export("svg"))
        bar.addWidget(self.pdf); bar.addWidget(self.svg)
        lay.addLayout(bar)
        self.view = FDGraphView(session); lay.addWidget(self.view)
        hint = QLabel(i18n.t("fd_hint"))
        hint.setStyleSheet("color:#667;"); lay.addWidget(hint)

    def _export(self, fmt):
        from norma.studio import files
        title = i18n.t("export_pdf" if fmt == "pdf" else "export_svg")
        path = files.ask_save_path(self, title, f"fd_graph.{fmt}", f"{fmt.upper()} (*.{fmt})", fmt)
        if path and files.run_save(self, lambda p: export_scene(self.view, p), path, title):
            self.session.status.emit(f"{i18n.t('saved')} : {path}")
