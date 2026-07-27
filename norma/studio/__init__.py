"""norma.studio -- a desktop application (PySide6/Qt) for unsupervised relational
normalization on top of the CPAD engine.

Features: load CSV or connect to an RDBMS (ODBC/SQLite/PostgreSQL), discover FD / denial
/ order / linear constraints, edit them and add expert constraints, visualize the FD
graph and the proposed relational schema, generate SQL DDL from the schema (and parse SQL
back), and highlight the anomalous cells.

Launch:  python -m norma.studio
"""
__all__ = ["main"]


def main():
    from norma.studio.app import main as _main
    return _main()
