from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable, Protocol

import duckdb


class DBManagerProtocol(Protocol):
    path: Path | None

    def connect(self, db_path: str) -> None: ...
    def close(self) -> None: ...
    def list_objects(self) -> list[tuple[str, str]]: ...
    def preview_table_with_rowid(
        self, table_name: str, limit: int = 200, offset: int = 0
    ) -> tuple[list[str], list[tuple], list[int]]: ...
    def execute_sql(self, sql: str) -> tuple[list[str], list[tuple], str]: ...
    def begin_transaction(self) -> None: ...
    def commit_transaction(self) -> None: ...
    def rollback_transaction(self) -> None: ...
    def update_cell_by_rowid(
        self, table_name: str, column_name: str, rowid: int, new_value: object
    ) -> None: ...
    def delete_row_by_rowid(self, table_name: str, rowid: int) -> None: ...
    def insert_row(self, table_name: str, values: dict[str, object]) -> None: ...
    def list_columns(self, table_name: str) -> Iterable[str]: ...
    def list_columns_with_types(self, table_name: str) -> Iterable[tuple[str, str]]: ...
    def count_rows(self, table_name: str) -> int: ...
    def get_object_sql(self, object_type: str, object_name: str) -> str: ...
    def get_index_info(self, index_name: str) -> tuple[list[str], list[tuple]]: ...
    def table_exists(self, table_name: str) -> bool: ...
    def import_csv(self, file_path: Path, table_name: str, create_if_missing: bool) -> int: ...
    def import_parquet(
        self, file_path: Path, table_name: str, create_if_missing: bool
    ) -> int: ...


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

    def preview_table_with_rowid(
        self,
        table_name: str,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[str], list[tuple], list[int]]:
        conn = self.require_conn()
        escaped = table_name.replace('"', '""')
        sql = (
            f'SELECT rowid as "__rowid__", * FROM "{escaped}" '
            f"LIMIT {int(limit)} OFFSET {int(offset)}"
        )
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        raw_rows = [tuple(row) for row in cur.fetchall()]
        if not cols:
            return [], [], []
        rowids = [int(r[0]) for r in raw_rows]
        return cols[1:], [tuple(r[1:]) for r in raw_rows], rowids

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
        self.require_conn().execute("BEGIN")

    def commit_transaction(self) -> None:
        self.require_conn().commit()

    def rollback_transaction(self) -> None:
        self.require_conn().rollback()

    def update_cell_by_rowid(
        self, table_name: str, column_name: str, rowid: int, new_value: object
    ) -> None:
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        escaped_col = column_name.replace('"', '""')
        conn.execute(
            f'UPDATE "{escaped_table}" SET "{escaped_col}" = ? WHERE rowid = ?',
            (new_value, rowid),
        )

    def delete_row_by_rowid(self, table_name: str, rowid: int) -> None:
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        conn.execute(f'DELETE FROM "{escaped_table}" WHERE rowid = ?', (rowid,))

    def insert_row(self, table_name: str, values: dict[str, object]) -> None:
        if not values:
            raise ValueError("No values provided for insert.")
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        cols = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in values]
        placeholders = ", ".join(["?"] * len(values))
        conn.execute(
            f'INSERT INTO "{escaped_table}" ({", ".join(cols)}) VALUES ({placeholders})',
            tuple(values.values()),
        )

    def list_columns(self, table_name: str) -> Iterable[str]:
        cur = self.require_conn().execute(f'PRAGMA table_info("{table_name.replace(chr(34), chr(34)*2)}")')
        for row in cur.fetchall():
            yield row["name"]

    def list_columns_with_types(self, table_name: str) -> Iterable[tuple[str, str]]:
        cur = self.require_conn().execute(f'PRAGMA table_info("{table_name.replace(chr(34), chr(34)*2)}")')
        for row in cur.fetchall():
            yield row["name"], (str(row["type"] or "").strip() or "UNKNOWN")

    def count_rows(self, table_name: str) -> int:
        row = self.require_conn().execute(
            f'SELECT COUNT(*) AS c FROM "{table_name.replace(chr(34), chr(34)*2)}"'
        ).fetchone()
        return int(row["c"] if row else 0)

    def get_object_sql(self, object_type: str, object_name: str) -> str:
        row = self.require_conn().execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = ? AND name = ?
            LIMIT 1
            """,
            (object_type, object_name),
        ).fetchone()
        return str(row["sql"] or "") if row else ""

    def get_index_info(self, index_name: str) -> tuple[list[str], list[tuple]]:
        cur = self.require_conn().execute(f'PRAGMA index_info("{index_name.replace(chr(34), chr(34)*2)}")')
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = [tuple(row) for row in cur.fetchall()]
        return cols, rows

    def table_exists(self, table_name: str) -> bool:
        row = self.require_conn().execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (table_name,),
        ).fetchone()
        return row is not None

    def import_csv(self, file_path: Path, table_name: str, create_if_missing: bool) -> int:
        with file_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV file has no header.")
            columns = [c.strip() for c in reader.fieldnames if c and c.strip()]
            rows = [tuple(row.get(col) for col in columns) for row in reader]
        return self._import_rows(table_name, columns, rows, create_if_missing)

    def import_parquet(self, file_path: Path, table_name: str, create_if_missing: bool) -> int:
        try:
            import pandas as pd  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Parquet import requires pandas (and pyarrow/fastparquet).") from exc
        df = pd.read_parquet(file_path)
        columns = [str(c) for c in df.columns]
        rows = [tuple(None if v != v else v for v in row) for row in df.itertuples(index=False, name=None)]
        return self._import_rows(table_name, columns, rows, create_if_missing)

    def _import_rows(
        self, table_name: str, columns: list[str], rows: list[tuple], create_if_missing: bool
    ) -> int:
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        escaped_cols = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in columns]
        if create_if_missing and not self.table_exists(table_name):
            conn.execute(f'CREATE TABLE "{escaped_table}" ({", ".join(f"{c} TEXT" for c in escaped_cols)})')
        placeholders = ", ".join(["?"] * len(columns))
        conn.executemany(
            f'INSERT INTO "{escaped_table}" ({", ".join(escaped_cols)}) VALUES ({placeholders})',
            rows,
        )
        conn.commit()
        return len(rows)


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
        rows.extend(
            (
                "table" if str(r[0]) == "BASE TABLE" else "view",
                str(r[1]),
            )
            for r in conn.execute(
                """
                SELECT table_type, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                """
            ).fetchall()
        )
        try:
            rows.extend(
                ("index", str(r[0]))
                for r in conn.execute(
                    """
                    SELECT DISTINCT index_name
                    FROM duckdb_indexes()
                    WHERE schema_name NOT IN ('information_schema', 'pg_catalog')
                    """
                ).fetchall()
            )
        except Exception:
            pass
        order = {"table": 1, "view": 2, "index": 3, "trigger": 4}
        rows.sort(key=lambda x: (order.get(x[0], 99), x[1]))
        return rows

    def preview_table_with_rowid(
        self, table_name: str, limit: int = 200, offset: int = 0
    ) -> tuple[list[str], list[tuple], list[int]]:
        cur = self.require_conn().execute(
            f'SELECT rowid as "__rowid__", * FROM "{table_name.replace(chr(34), chr(34)*2)}" '
            f"LIMIT {int(limit)} OFFSET {int(offset)}"
        )
        cols = [d[0] for d in cur.description] if cur.description else []
        raw_rows = cur.fetchall()
        if not cols:
            return [], [], []
        rowids = [int(r[0]) for r in raw_rows]
        return cols[1:], [tuple(r[1:]) for r in raw_rows], rowids

    def execute_sql(self, sql: str) -> tuple[list[str], list[tuple], str]:
        query = sql.strip()
        if not query:
            return [], [], "No SQL to execute."
        cur = self.require_conn().execute(query)
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
        self, table_name: str, column_name: str, rowid: int, new_value: object
    ) -> None:
        self.require_conn().execute(
            f'UPDATE "{table_name.replace(chr(34), chr(34)*2)}" '
            f'SET "{column_name.replace(chr(34), chr(34)*2)}" = ? WHERE rowid = ?',
            [new_value, rowid],
        )

    def delete_row_by_rowid(self, table_name: str, rowid: int) -> None:
        self.require_conn().execute(
            f'DELETE FROM "{table_name.replace(chr(34), chr(34)*2)}" WHERE rowid = ?',
            [rowid],
        )

    def insert_row(self, table_name: str, values: dict[str, object]) -> None:
        if not values:
            raise ValueError("No values provided for insert.")
        cols = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in values]
        placeholders = ", ".join(["?"] * len(values))
        self.require_conn().execute(
            f'INSERT INTO "{table_name.replace(chr(34), chr(34)*2)}" '
            f'({", ".join(cols)}) VALUES ({placeholders})',
            list(values.values()),
        )

    def list_columns(self, table_name: str) -> Iterable[str]:
        escaped_name = table_name.replace("'", "''")
        rows = self.require_conn().execute(f"PRAGMA table_info('{escaped_name}')").fetchall()
        for row in rows:
            yield str(row[1])

    def list_columns_with_types(self, table_name: str) -> Iterable[tuple[str, str]]:
        escaped_name = table_name.replace("'", "''")
        rows = self.require_conn().execute(f"PRAGMA table_info('{escaped_name}')").fetchall()
        for row in rows:
            yield str(row[1]), (str(row[2] or "").strip() or "UNKNOWN")

    def count_rows(self, table_name: str) -> int:
        row = self.require_conn().execute(
            f'SELECT COUNT(*) FROM "{table_name.replace(chr(34), chr(34)*2)}"'
        ).fetchone()
        return int(row[0] if row else 0)

    def get_object_sql(self, object_type: str, object_name: str) -> str:
        conn = self.require_conn()
        esc = object_name.replace("'", "''")
        if object_type in {"table", "view"}:
            row = conn.execute(f"SELECT sql FROM duckdb_tables() WHERE table_name = '{esc}' LIMIT 1").fetchone()
            if row and row[0]:
                return str(row[0])
            row = conn.execute(f"SELECT sql FROM duckdb_views() WHERE view_name = '{esc}' LIMIT 1").fetchone()
            return str(row[0]) if row and row[0] else ""
        if object_type == "index":
            row = conn.execute(f"SELECT sql FROM duckdb_indexes() WHERE index_name = '{esc}' LIMIT 1").fetchone()
            return str(row[0]) if row and row[0] else ""
        return ""

    def get_index_info(self, index_name: str) -> tuple[list[str], list[tuple]]:
        rows = self.require_conn().execute(
            f"""
            SELECT index_name, table_name, expressions, is_unique
            FROM duckdb_indexes()
            WHERE index_name = '{index_name.replace("'", "''")}'
            """
        ).fetchall()
        return ["index_name", "table_name", "expressions", "is_unique"], rows

    def table_exists(self, table_name: str) -> bool:
        row = self.require_conn().execute(
            f"""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
              AND table_name = '{table_name.replace("'", "''")}'
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
            rows = [tuple(row.get(col) for col in columns) for row in reader]
        return self._import_rows(table_name, columns, rows, create_if_missing)

    def import_parquet(self, file_path: Path, table_name: str, create_if_missing: bool) -> int:
        try:
            import pandas as pd  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Parquet import requires pandas (and pyarrow/fastparquet).") from exc
        df = pd.read_parquet(file_path)
        columns = [str(c) for c in df.columns]
        rows = [tuple(None if v != v else v for v in row) for row in df.itertuples(index=False, name=None)]
        return self._import_rows(table_name, columns, rows, create_if_missing)

    def _import_rows(
        self, table_name: str, columns: list[str], rows: list[tuple], create_if_missing: bool
    ) -> int:
        conn = self.require_conn()
        escaped_table = table_name.replace('"', '""')
        escaped_cols = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in columns]
        if create_if_missing and not self.table_exists(table_name):
            conn.execute(f'CREATE TABLE "{escaped_table}" ({", ".join(f"{c} VARCHAR" for c in escaped_cols)})')
        placeholders = ", ".join(["?"] * len(columns))
        conn.executemany(
            f'INSERT INTO "{escaped_table}" ({", ".join(escaped_cols)}) VALUES ({placeholders})',
            rows,
        )
        return len(rows)
