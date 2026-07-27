"""Vector export of a QGraphicsScene to PDF or SVG, so the schema and FD-graph diagrams
(arranged interactively) can be dropped straight into a paper as crisp vector figures."""
from __future__ import annotations
from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QPainter, QPageSize, QColor


def export_scene(view, path: str, margin: float = 12.0):
    scene = view.scene()
    rect = scene.itemsBoundingRect().adjusted(-margin, -margin, margin, margin)
    if rect.isEmpty():
        rect = QRectF(0, 0, 400, 300)

    if path.lower().endswith(".svg"):
        from PySide6.QtSvg import QSvgGenerator
        gen = QSvgGenerator()
        gen.setFileName(path)
        gen.setSize(rect.size().toSize())
        gen.setViewBox(QRectF(0, 0, rect.width(), rect.height()))
        gen.setTitle("norma schema")
        p = QPainter(gen)
        p.setRenderHint(QPainter.Antialiasing)
        scene.render(p, QRectF(0, 0, rect.width(), rect.height()), rect)
        p.end()
        return

    from PySide6.QtPrintSupport import QPrinter
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    printer.setPageSize(QPageSize(QSizeF(rect.width(), rect.height()), QPageSize.Point))
    printer.setFullPage(True)
    p = QPainter(printer)
    p.setRenderHint(QPainter.Antialiasing)
    page = QRectF(printer.pageRect(QPrinter.DevicePixel))
    scene.render(p, page, rect)              # vector painting -> vector PDF
    p.end()
