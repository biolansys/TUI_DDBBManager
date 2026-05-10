from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import duckdb


class DuckDBManager:
    def __init__(self) -> None:
        self.conn: duckdb.DuckDBPyConnection | None = None
        self.path: Path | None = None

    def connect(self, db_path: str) -> None:
        path = Path(db_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Database file not found: {path}")
        self.close()
        self.conn = duckdb.connect(path.as_posix())
        self.path = path

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            self.path = None

    def require_conn(self) -> duckdb.DuckDBPyConnection:
        if self.conn is None:
            raise RuntimeError("No database connection. Open a DuckDB file first.")
        return self.conn

    def list_objects(self) -> list[tuple[str, str]]:
        conn = self.require_conn()
        rows: list[tuple[str, str]] = []

        table_view = conn.execute(
            """
            SELECT
              CASE WHEN table_type = 'BASE TABLE' THEN 'table' ELSE 'view' END AS obj_type,
              table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY obj_type, table_name
            """
        ).fetchall()
        rows.extend((str(r[0]), str(r[1])) for r in table_view)

        try:
            idx_rows = conn.execute(
                """
                SELECT DISTINCT 'index' AS obj_type, index_name
                FROM duckdb_indexes()
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog')
                ORDER BY index_name
                """
            ).fetchall()
            rows.extend((str(r[0]), str(r[1])) for r in idx_rows)
        except Exception:
            pass

        type_order = {"table": 1, "view": 2, "index": 3, "trigger": 4}
        rows.sort(key=lambda x: (type_order.get(x[0], 99), x[1]))
        return rows

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
        raw_rows = cur.fetchall()
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
        cur = conn.execute(query)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return cols, rows, f"{len(rows)} row(s)."
        return [], [], "Statement executed."

    def begin_transaction(self) -> None:
        self.require_conn().execute("BEGIN TRANSACTION")

    def commit_transaction(self) -> None:
        self.require_conn().execute("COMMIT")

    def rollback_transaction(self) -> None:
        self.require_conn().execute("ROLLBACK")

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
        conn.execute(sql, [new_value, rowid])

    def delete_row_by_rowid(self, table_name: str, rowid: int) -> None:
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        sql = f'DELETE FROM "{escaped_table}" WHERE rowid = ?'
        conn.execute(sql, [rowid])

    def insert_row(self, table_name: str, values: dict[str, object]) -> None:
        if not values:
            raise ValueError("No values provided for insert.")
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        cols = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in values]
        placeholders = ", ".join(["?"] * len(values))
        sql = f'INSERT INTO "{escaped_table}" ({", ".join(cols)}) VALUES ({placeholders})'
        conn.execute(sql, list(values.values()))

    def list_columns(self, table_name: str) -> Iterable[str]:
        conn = self.require_conn()
        escaped = table_name.replace("'", "''")
        rows = conn.execute(f"PRAGMA table_info('{escaped}')").fetchall()
        for row in rows:
            yield str(row[1])

    def list_columns_with_types(self, table_name: str) -> Iterable[tuple[str, str]]:
        conn = self.require_conn()
        escaped = table_name.replace("'", "''")
        rows = conn.execute(f"PRAGMA table_info('{escaped}')").fetchall()
        for row in rows:
            col_name = str(row[1])
            col_type = str(row[2] or "").strip() or "UNKNOWN"
            yield col_name, col_type

    def count_rows(self, table_name: str) -> int:
        conn = self.require_conn()
        escaped = table_name.replace('"', '""')
        row = conn.execute(f'SELECT COUNT(*) AS c FROM "{escaped}"').fetchone()
        return int(row[0] if row else 0)

    def get_object_sql(self, object_type: str, object_name: str) -> str:
        conn = self.require_conn()
        escaped_name = object_name.replace("'", "''")
        if object_type in {"table", "view"}:
            row = conn.execute(
                f"""
                SELECT sql
                FROM duckdb_tables()
                WHERE table_name = '{escaped_name}'
                LIMIT 1
                """
            ).fetchone()
            if row and row[0]:
                return str(row[0])
            row = conn.execute(
                f"""
                SELECT sql
                FROM duckdb_views()
                WHERE view_name = '{escaped_name}'
                LIMIT 1
                """
            ).fetchone()
            return str(row[0]) if row and row[0] else ""
        if object_type == "index":
            row = conn.execute(
                f"""
                SELECT sql
                FROM duckdb_indexes()
                WHERE index_name = '{escaped_name}'
                LIMIT 1
                """
            ).fetchone()
            return str(row[0]) if row and row[0] else ""
        return ""

    def get_index_info(self, index_name: str) -> tuple[list[str], list[tuple]]:
        conn = self.require_conn()
        escaped_name = index_name.replace("'", "''")
        rows = conn.execute(
            f"""
            SELECT index_name, table_name, expressions, is_unique
            FROM duckdb_indexes()
            WHERE index_name = '{escaped_name}'
            """
        ).fetchall()
        cols = ["index_name", "table_name", "expressions", "is_unique"]
        return cols, rows

    def table_exists(self, table_name: str) -> bool:
        conn = self.require_conn()
        escaped_name = table_name.replace("'", "''")
        row = conn.execute(
            f"""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
              AND table_name = '{escaped_name}'
            LIMIT 1
            """
        ).fetchone()
        return row is not None

    def import_csv(self, file_path: Path, table_name: str, create_if_missing: bool) -> int:
        with file_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV file has no header.")
            columns = [c.strip() for c in reader.fieldnames if c and c.strip()]
            if not columns:
                raise ValueError("CSV header is empty.")
            rows = [tuple(row.get(col) for col in columns) for row in reader]
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
            col_defs = ", ".join(f"{c} VARCHAR" for c in escaped_cols)
            conn.execute(f'CREATE TABLE "{escaped_table}" ({col_defs})')
        placeholders = ", ".join(["?"] * len(columns))
        sql = f'INSERT INTO "{escaped_table}" ({", ".join(escaped_cols)}) VALUES ({placeholders})'
        conn.executemany(sql, rows)
        return len(rows)
