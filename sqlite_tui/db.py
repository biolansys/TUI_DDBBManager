from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable


class SQLiteManager:
    def __init__(self) -> None:
        self.conn: sqlite3.Connection | None = None
        self.path: Path | None = None

    def connect(self, db_path: str) -> None:
        path = Path(db_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Database file not found: {path}")
        self.close()
        self.conn = sqlite3.connect(path.as_posix())
        self.conn.row_factory = sqlite3.Row
        self.path = path

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            self.path = None

    def require_conn(self) -> sqlite3.Connection:
        if self.conn is None:
            raise RuntimeError("No database connection. Open a SQLite file first.")
        return self.conn

    def list_objects(self) -> list[tuple[str, str]]:
        conn = self.require_conn()
        cur = conn.execute(
            """
            SELECT type, name
            FROM sqlite_master
            WHERE type IN ('table', 'view', 'index', 'trigger')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY
              CASE type
                WHEN 'table' THEN 1
                WHEN 'view' THEN 2
                WHEN 'index' THEN 3
                WHEN 'trigger' THEN 4
                ELSE 99
              END,
              name
            """
        )
        return [(row["type"], row["name"]) for row in cur.fetchall()]

    def preview_table(self, table_name: str, limit: int = 200) -> tuple[list[str], list[tuple]]:
        conn = self.require_conn()
        escaped = table_name.replace('"', '""')
        sql = f'SELECT * FROM "{escaped}" LIMIT {int(limit)}'
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [tuple(row) for row in cur.fetchall()]
        return cols, rows

    def preview_table_with_rowid(
        self,
        table_name: str,
        limit: int = 200,
    ) -> tuple[list[str], list[tuple], list[int]]:
        conn = self.require_conn()
        escaped = table_name.replace('"', '""')
        sql = f'SELECT rowid as "__rowid__", * FROM "{escaped}" LIMIT {int(limit)}'
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        raw_rows = [tuple(row) for row in cur.fetchall()]
        if not cols:
            return [], [], []
        rowids = [int(r[0]) for r in raw_rows]
        visible_cols = cols[1:]
        visible_rows = [tuple(r[1:]) for r in raw_rows]
        return visible_cols, visible_rows, rowids

    def execute_sql(self, sql: str) -> tuple[list[str], list[tuple], str]:
        conn = self.require_conn()
        query = sql.strip()
        if not query:
            return [], [], "No SQL to execute."

        cur = conn.cursor()
        cur.execute(query)

        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = [tuple(row) for row in cur.fetchall()]
            return cols, rows, f"{len(rows)} row(s)."

        conn.commit()
        affected = cur.rowcount if cur.rowcount is not None else 0
        return [], [], f"Statement executed. Affected rows: {affected}."

    def begin_transaction(self) -> None:
        conn = self.require_conn()
        conn.execute("BEGIN")

    def commit_transaction(self) -> None:
        conn = self.require_conn()
        conn.commit()

    def rollback_transaction(self) -> None:
        conn = self.require_conn()
        conn.rollback()

    def update_cell_by_rowid(
        self,
        table_name: str,
        column_name: str,
        rowid: int,
        new_value: object,
    ) -> None:
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        escaped_col = column_name.replace('"', '""')
        sql = f'UPDATE "{escaped_table}" SET "{escaped_col}" = ? WHERE rowid = ?'
        conn.execute(sql, (new_value, rowid))

    def delete_row_by_rowid(self, table_name: str, rowid: int) -> None:
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        sql = f'DELETE FROM "{escaped_table}" WHERE rowid = ?'
        conn.execute(sql, (rowid,))

    def insert_row(self, table_name: str, values: dict[str, object]) -> None:
        if not values:
            raise ValueError("No values provided for insert.")
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        cols = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in values]
        placeholders = ", ".join(["?"] * len(values))
        sql = f'INSERT INTO "{escaped_table}" ({", ".join(cols)}) VALUES ({placeholders})'
        conn.execute(sql, tuple(values.values()))

    def list_columns(self, table_name: str) -> Iterable[str]:
        conn = self.require_conn()
        escaped = table_name.replace('"', '""')
        cur = conn.execute(f'PRAGMA table_info("{escaped}")')
        for row in cur.fetchall():
            yield row["name"]

    def list_columns_with_types(self, table_name: str) -> Iterable[tuple[str, str]]:
        conn = self.require_conn()
        escaped = table_name.replace('"', '""')
        cur = conn.execute(f'PRAGMA table_info("{escaped}")')
        for row in cur.fetchall():
            col_type = str(row["type"] or "").strip() or "UNKNOWN"
            yield row["name"], col_type

    def count_rows(self, table_name: str) -> int:
        conn = self.require_conn()
        escaped = table_name.replace('"', '""')
        cur = conn.execute(f'SELECT COUNT(*) AS c FROM "{escaped}"')
        row = cur.fetchone()
        return int(row["c"] if row else 0)

    def get_object_sql(self, object_type: str, object_name: str) -> str:
        conn = self.require_conn()
        cur = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = ? AND name = ?
            LIMIT 1
            """,
            (object_type, object_name),
        )
        row = cur.fetchone()
        if not row:
            return ""
        return str(row["sql"] or "")

    def get_index_info(self, index_name: str) -> tuple[list[str], list[tuple]]:
        conn = self.require_conn()
        escaped = index_name.replace('"', '""')
        cur = conn.execute(f'PRAGMA index_info("{escaped}")')
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [tuple(row) for row in cur.fetchall()]
        return cols, rows

    def table_exists(self, table_name: str) -> bool:
        conn = self.require_conn()
        cur = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (table_name,),
        )
        return cur.fetchone() is not None

    def import_csv(self, file_path: Path, table_name: str, create_if_missing: bool) -> int:
        with file_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV file has no header.")
            columns = [c.strip() for c in reader.fieldnames if c and c.strip()]
            if not columns:
                raise ValueError("CSV header is empty.")
            rows = []
            for row in reader:
                rows.append(tuple(row.get(col) for col in columns))
        return self._import_rows(table_name, columns, rows, create_if_missing=create_if_missing)

    def import_parquet(self, file_path: Path, table_name: str, create_if_missing: bool) -> int:
        try:
            import pandas as pd  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Parquet import requires pandas (and pyarrow/fastparquet).") from exc
        df = pd.read_parquet(file_path)
        columns = [str(c) for c in df.columns]
        if not columns:
            raise ValueError("Parquet file has no columns.")
        rows = [tuple(None if v != v else v for v in row) for row in df.itertuples(index=False, name=None)]
        return self._import_rows(table_name, columns, rows, create_if_missing=create_if_missing)

    def _import_rows(
        self,
        table_name: str,
        columns: list[str],
        rows: list[tuple],
        create_if_missing: bool,
    ) -> int:
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        escaped_cols = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in columns]
        if create_if_missing and not self.table_exists(table_name):
            col_defs = ", ".join(f'{c} TEXT' for c in escaped_cols)
            conn.execute(f'CREATE TABLE "{escaped_table}" ({col_defs})')
        placeholders = ", ".join(["?"] * len(columns))
        sql = f'INSERT INTO "{escaped_table}" ({", ".join(escaped_cols)}) VALUES ({placeholders})'
        conn.executemany(sql, rows)
        conn.commit()
        return len(rows)
