"""RDBMS connectivity through Qt's SQL drivers (SQLite, PostgreSQL, MySQL, ODBC).

Used by the connection dialog to browse server tables and pull one into a DataFrame for
analysis. Driver availability depends on the Qt plugins installed on the machine
(QSQLITE is always present; QODBC / QPSQL / QMYSQL need their plugins).
"""
from __future__ import annotations
import pandas as pd
from PySide6.QtSql import QSqlDatabase, QSqlQuery

_CONN = "norma_studio_conn"

DRIVER_LABELS = {
    "QSQLITE": "SQLite (fichier)",
    "QPSQL": "PostgreSQL",
    "QMYSQL": "MySQL / MariaDB",
    "QODBC": "ODBC (generique)",
}


def available_drivers() -> list[str]:
    have = set(QSqlDatabase.drivers())
    return [d for d in DRIVER_LABELS if d in have]


def open_connection(driver: str, database: str, host: str = "", port: int = 0,
                    user: str = "", password: str = "") -> QSqlDatabase:
    if QSqlDatabase.contains(_CONN):
        QSqlDatabase.removeDatabase(_CONN)
    db = QSqlDatabase.addDatabase(driver, _CONN)
    db.setDatabaseName(database)
    if host:
        db.setHostName(host)
    if port:
        db.setPort(int(port))
    if user:
        db.setUserName(user)
    if password:
        db.setPassword(password)
    if not db.open():
        raise RuntimeError(db.lastError().text() or "Echec de connexion")
    return db


def list_tables(db: QSqlDatabase) -> list[str]:
    return list(db.tables())


def load_table(db: QSqlDatabase, table: str, limit: int = 100000) -> pd.DataFrame:
    q = QSqlQuery(db)
    q.exec(f"SELECT * FROM {table} LIMIT {int(limit)}")
    rec = q.record()
    cols = [rec.fieldName(i) for i in range(rec.count())]
    rows = []
    while q.next():
        rows.append(["" if q.value(i) is None else str(q.value(i)) for i in range(len(cols))])
    return pd.DataFrame(rows, columns=cols)
