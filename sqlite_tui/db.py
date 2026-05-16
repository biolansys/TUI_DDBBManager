from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable, Protocol
from urllib.parse import parse_qs, unquote, urlparse

import duckdb
import mysql.connector
try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None  # type: ignore[assignment]


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


class MySQLManager:
    def __init__(self) -> None:
        self.conn: mysql.connector.MySQLConnection | None = None
        self.path: Path | None = None
        self._db_name: str = ""
        self._pk_map: dict[int, tuple[list[str], tuple]] = {}

    def connect(self, db_path: str) -> None:
        parsed = urlparse(db_path)
        if parsed.scheme.lower() != "mysql":
            raise ValueError("MySQL connection must use URI format: mysql://user:pass@host:3306/database")
        user = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        host = parsed.hostname or "localhost"
        port = parsed.port or 3306
        database = (parsed.path or "").lstrip("/")
        if not user or not database:
            raise ValueError("MySQL URI must include user and database.")
        self.close()
        self.conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            autocommit=False,
        )
        self._db_name = database
        self.path = Path(f"mysql_{database}.conn")

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        self.path = None
        self._db_name = ""
        self._pk_map = {}

    def require_conn(self) -> mysql.connector.MySQLConnection:
        if self.conn is None:
            raise RuntimeError("No database connection. Open a MySQL connection first.")
        return self.conn

    def list_objects(self) -> list[tuple[str, str]]:
        conn = self.require_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT TABLE_TYPE, TABLE_NAME
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            ORDER BY TABLE_TYPE, TABLE_NAME
            """
        )
        rows: list[tuple[str, str]] = []
        for table_type, name in cur.fetchall():
            rows.append(("table" if str(table_type) == "BASE TABLE" else "view", str(name)))
        cur.execute(
            """
            SELECT INDEX_NAME, TABLE_NAME
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND INDEX_NAME <> 'PRIMARY'
            GROUP BY INDEX_NAME, TABLE_NAME
            ORDER BY INDEX_NAME
            """
        )
        for idx, tbl in cur.fetchall():
            rows.append(("index", f"{tbl}.{idx}"))
        cur.close()
        order = {"table": 1, "view": 2, "index": 3, "trigger": 4}
        rows.sort(key=lambda x: (order.get(x[0], 99), x[1]))
        return rows

    def _get_pk_columns(self, table_name: str) -> list[str]:
        conn = self.require_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.key_column_usage
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND constraint_name = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        )
        cols = [str(r[0]) for r in cur.fetchall()]
        cur.close()
        return cols

    def preview_table_with_rowid(
        self, table_name: str, limit: int = 200, offset: int = 0
    ) -> tuple[list[str], list[tuple], list[int]]:
        conn = self.require_conn()
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM `{table_name}` LIMIT %s OFFSET %s", (int(limit), int(offset)))
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()

        pk_cols = self._get_pk_columns(table_name)
        self._pk_map = {}
        rowids: list[int] = []
        for idx, row in enumerate(rows, start=1):
            rowids.append(idx)
            if pk_cols:
                pos = [cols.index(c) for c in pk_cols if c in cols]
                if len(pos) == len(pk_cols):
                    self._pk_map[idx] = (pk_cols, tuple(row[p] for p in pos))
        return cols, [tuple(r) for r in rows], rowids

    def execute_sql(self, sql: str) -> tuple[list[str], list[tuple], str]:
        conn = self.require_conn()
        query = sql.strip()
        if not query:
            return [], [], "No SQL to execute."
        cur = conn.cursor()
        cur.execute(query)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            cur.close()
            return cols, [tuple(r) for r in rows], f"{len(rows)} row(s)."
        affected = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        cur.close()
        return [], [], f"Statement executed. Affected rows: {affected}."

    def begin_transaction(self) -> None:
        self.require_conn().start_transaction()

    def commit_transaction(self) -> None:
        self.require_conn().commit()

    def rollback_transaction(self) -> None:
        self.require_conn().rollback()

    def update_cell_by_rowid(
        self, table_name: str, column_name: str, rowid: int, new_value: object
    ) -> None:
        if rowid not in self._pk_map:
            raise RuntimeError("MySQL edit requires table with PRIMARY KEY in current preview page.")
        pk_cols, pk_vals = self._pk_map[rowid]
        where = " AND ".join([f"`{c}` = %s" for c in pk_cols])
        sql = f"UPDATE `{table_name}` SET `{column_name}` = %s WHERE {where}"
        params = [new_value, *pk_vals]
        cur = self.require_conn().cursor()
        cur.execute(sql, params)
        cur.close()

    def delete_row_by_rowid(self, table_name: str, rowid: int) -> None:
        if rowid not in self._pk_map:
            raise RuntimeError("MySQL delete requires table with PRIMARY KEY in current preview page.")
        pk_cols, pk_vals = self._pk_map[rowid]
        where = " AND ".join([f"`{c}` = %s" for c in pk_cols])
        sql = f"DELETE FROM `{table_name}` WHERE {where}"
        cur = self.require_conn().cursor()
        cur.execute(sql, list(pk_vals))
        cur.close()

    def insert_row(self, table_name: str, values: dict[str, object]) -> None:
        if not values:
            raise ValueError("No values provided for insert.")
        cols = [f"`{c}`" for c in values]
        placeholders = ", ".join(["%s"] * len(values))
        sql = f"INSERT INTO `{table_name}` ({', '.join(cols)}) VALUES ({placeholders})"
        cur = self.require_conn().cursor()
        cur.execute(sql, list(values.values()))
        cur.close()

    def list_columns(self, table_name: str) -> Iterable[str]:
        cur = self.require_conn().cursor()
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        )
        for row in cur.fetchall():
            yield str(row[0])
        cur.close()

    def list_columns_with_types(self, table_name: str) -> Iterable[tuple[str, str]]:
        cur = self.require_conn().cursor()
        cur.execute(
            """
            SELECT COLUMN_NAME, COLUMN_TYPE
            FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        )
        for row in cur.fetchall():
            yield str(row[0]), str(row[1] or "UNKNOWN")
        cur.close()

    def count_rows(self, table_name: str) -> int:
        cur = self.require_conn().cursor()
        cur.execute(f"SELECT COUNT(*) FROM `{table_name}`")
        row = cur.fetchone()
        cur.close()
        return int(row[0] if row else 0)

    def get_object_sql(self, object_type: str, object_name: str) -> str:
        cur = self.require_conn().cursor()
        if object_type in {"table", "view"}:
            cur.execute("SHOW CREATE TABLE `{}`".format(object_name.replace("`", "``")))
            row = cur.fetchone()
            cur.close()
            return str(row[1]) if row and len(row) > 1 else ""
        if object_type == "index":
            table_name, index_name = self._split_index_identity(object_name)
            if not table_name:
                cur.close()
                return ""
            cur.execute(
                """
                SELECT TABLE_NAME, GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)
                FROM information_schema.statistics
                WHERE table_schema = DATABASE() AND INDEX_NAME = %s AND TABLE_NAME = %s
                GROUP BY TABLE_NAME
                LIMIT 1
                """,
                (index_name, table_name),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return ""
            return f"CREATE INDEX `{index_name}` ON `{row[0]}` ({row[1]});"
        return ""

    def get_index_info(self, index_name: str) -> tuple[list[str], list[tuple]]:
        table_name, real_index_name = self._split_index_identity(index_name)
        if not table_name:
            return ["table_name", "index_name", "column_name", "non_unique", "seq_in_index"], []
        cur = self.require_conn().cursor()
        cur.execute(
            """
            SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX
            FROM information_schema.statistics
            WHERE table_schema = DATABASE() AND INDEX_NAME = %s AND TABLE_NAME = %s
            ORDER BY TABLE_NAME, SEQ_IN_INDEX
            """,
            (real_index_name, table_name),
        )
        rows = cur.fetchall()
        cur.close()
        return ["table_name", "index_name", "column_name", "non_unique", "seq_in_index"], [tuple(r) for r in rows]

    def table_exists(self, table_name: str) -> bool:
        cur = self.require_conn().cursor()
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = %s
            LIMIT 1
            """,
            (table_name,),
        )
        row = cur.fetchone()
        cur.close()
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
        cur = conn.cursor()
        if create_if_missing and not self.table_exists(table_name):
            defs = ", ".join([f"`{c}` TEXT" for c in columns])
            cur.execute(f"CREATE TABLE `{table_name}` ({defs})")
        placeholders = ", ".join(["%s"] * len(columns))
        cols = ", ".join([f"`{c}`" for c in columns])
        cur.executemany(f"INSERT INTO `{table_name}` ({cols}) VALUES ({placeholders})", rows)
        conn.commit()
        cur.close()
        return len(rows)

    @staticmethod
    def _split_index_identity(value: str) -> tuple[str, str]:
        if "." not in value:
            return "", value
        table_name, index_name = value.split(".", 1)
        return table_name, index_name


class PostgreSQLManager:
    def __init__(self) -> None:
        self.conn: object | None = None
        self.path: Path | None = None
        self._pk_map: dict[int, str] = {}

    def connect(self, db_path: str) -> None:
        if psycopg is None:
            raise RuntimeError("PostgreSQL support requires psycopg. Install dependency: psycopg[binary].")
        parsed = urlparse(db_path)
        scheme = parsed.scheme.lower()
        if scheme not in {"postgresql", "postgres"}:
            raise ValueError("PostgreSQL connection must use URI format: postgresql://user:pass@host:5432/database")
        self.close()
        self.conn = psycopg.connect(db_path)
        self.path = Path(f"postgresql_{(parsed.path or '/db').lstrip('/')}.conn")

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        self.path = None
        self._pk_map = {}

    def require_conn(self):
        if self.conn is None:
            raise RuntimeError("No database connection. Open a PostgreSQL connection first.")
        return self.conn

    def list_objects(self) -> list[tuple[str, str]]:
        conn = self.require_conn()
        rows: list[tuple[str, str]] = []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_type, table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_type, table_name
                """
            )
            for table_type, name in cur.fetchall():
                rows.append(("table" if str(table_type) == "BASE TABLE" else "view", str(name)))
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY indexname
                """
            )
            for (index_name,) in cur.fetchall():
                rows.append(("index", str(index_name)))
            cur.execute(
                """
                SELECT trigger_name
                FROM information_schema.triggers
                WHERE trigger_schema = 'public'
                ORDER BY trigger_name
                """
            )
            for (trigger_name,) in cur.fetchall():
                rows.append(("trigger", str(trigger_name)))
        order = {"table": 1, "view": 2, "index": 3, "trigger": 4}
        rows.sort(key=lambda x: (order.get(x[0], 99), x[1]))
        return rows

    def preview_table_with_rowid(
        self, table_name: str, limit: int = 200, offset: int = 0
    ) -> tuple[list[str], list[tuple], list[int]]:
        conn = self.require_conn()
        self._pk_map = {}
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT ctid::text AS "__rowid__", * FROM "{table_name.replace(chr(34), chr(34)*2)}" '
                "LIMIT %s OFFSET %s",
                (int(limit), int(offset)),
            )
            cols = [d.name for d in cur.description] if cur.description else []
            raw_rows = cur.fetchall()
        if not cols:
            return [], [], []
        rowids: list[int] = []
        for idx, row in enumerate(raw_rows, start=1):
            rowids.append(idx)
            self._pk_map[idx] = str(row[0])
        return cols[1:], [tuple(r[1:]) for r in raw_rows], rowids

    def execute_sql(self, sql: str) -> tuple[list[str], list[tuple], str]:
        conn = self.require_conn()
        query = sql.strip()
        if not query:
            return [], [], "No SQL to execute."
        with conn.cursor() as cur:
            cur.execute(query)
            if cur.description:
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
                return cols, [tuple(r) for r in rows], f"{len(rows)} row(s)."
            affected = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
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
        ctid = self._pk_map.get(rowid)
        if not ctid:
            raise RuntimeError("No selected row context for update.")
        with self.require_conn().cursor() as cur:
            cur.execute(
                f'UPDATE "{table_name.replace(chr(34), chr(34)*2)}" '
                f'SET "{column_name.replace(chr(34), chr(34)*2)}" = %s WHERE ctid::text = %s',
                (new_value, ctid),
            )

    def delete_row_by_rowid(self, table_name: str, rowid: int) -> None:
        ctid = self._pk_map.get(rowid)
        if not ctid:
            raise RuntimeError("No selected row context for delete.")
        with self.require_conn().cursor() as cur:
            cur.execute(
                f'DELETE FROM "{table_name.replace(chr(34), chr(34)*2)}" WHERE ctid::text = %s',
                (ctid,),
            )

    def insert_row(self, table_name: str, values: dict[str, object]) -> None:
        if not values:
            raise ValueError("No values provided for insert.")
        cols = [f'"{c.replace(chr(34), chr(34) * 2)}"' for c in values]
        placeholders = ", ".join(["%s"] * len(values))
        sql = f'INSERT INTO "{table_name.replace(chr(34), chr(34)*2)}" ({", ".join(cols)}) VALUES ({placeholders})'
        with self.require_conn().cursor() as cur:
            cur.execute(sql, list(values.values()))

    def list_columns(self, table_name: str) -> Iterable[str]:
        with self.require_conn().cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            )
            for row in cur.fetchall():
                yield str(row[0])

    def list_columns_with_types(self, table_name: str) -> Iterable[tuple[str, str]]:
        with self.require_conn().cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            )
            for row in cur.fetchall():
                yield str(row[0]), str(row[1] or "UNKNOWN")

    def count_rows(self, table_name: str) -> int:
        with self.require_conn().cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table_name.replace(chr(34), chr(34)*2)}"')
            row = cur.fetchone()
            return int(row[0] if row else 0)

    def get_object_sql(self, object_type: str, object_name: str) -> str:
        with self.require_conn().cursor() as cur:
            if object_type == "view":
                cur.execute(
                    """
                    SELECT definition
                    FROM pg_views
                    WHERE schemaname = 'public' AND viewname = %s
                    LIMIT 1
                    """,
                    (object_name,),
                )
                row = cur.fetchone()
                return f'CREATE VIEW "{object_name}" AS\n{row[0]}' if row and row[0] else ""
            if object_type == "index":
                cur.execute("SELECT pg_get_indexdef(%s::regclass)", (object_name,))
                row = cur.fetchone()
                return str(row[0]) if row and row[0] else ""
            if object_type == "trigger":
                cur.execute(
                    """
                    SELECT pg_get_triggerdef(t.oid)
                    FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE NOT t.tgisinternal
                      AND n.nspname = 'public'
                      AND t.tgname = %s
                    LIMIT 1
                    """,
                    (object_name,),
                )
                row = cur.fetchone()
                return str(row[0]) if row and row[0] else ""
            if object_type == "table":
                cols = list(self.list_columns_with_types(object_name))
                if not cols:
                    return ""
                defs = ",\n  ".join([f'"{c}" {t}' for c, t in cols])
                return f'CREATE TABLE "{object_name}" (\n  {defs}\n)'
        return ""

    def get_index_info(self, index_name: str) -> tuple[list[str], list[tuple]]:
        with self.require_conn().cursor() as cur:
            cur.execute(
                """
                SELECT
                  i.indexname,
                  i.tablename,
                  a.attname,
                  ix.indisunique,
                  s.n
                FROM pg_indexes i
                JOIN pg_class ic ON ic.relname = i.indexname
                JOIN pg_index ix ON ix.indexrelid = ic.oid
                JOIN LATERAL generate_subscripts(ix.indkey, 1) AS s(n) ON TRUE
                JOIN pg_attribute a
                  ON a.attrelid = ix.indrelid
                 AND a.attnum = ix.indkey[s.n]
                WHERE i.schemaname = 'public'
                  AND i.indexname = %s
                ORDER BY s.n
                """,
                (index_name,),
            )
            rows = cur.fetchall()
        return ["index_name", "table_name", "column_name", "is_unique", "seq_in_index"], [tuple(r) for r in rows]

    def table_exists(self, table_name: str) -> bool:
        with self.require_conn().cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
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
            with conn.cursor() as cur:
                cur.execute(f'CREATE TABLE "{escaped_table}" ({", ".join(f"{c} TEXT" for c in escaped_cols)})')
        placeholders = ", ".join(["%s"] * len(columns))
        with conn.cursor() as cur:
            cur.executemany(
                f'INSERT INTO "{escaped_table}" ({", ".join(escaped_cols)}) VALUES ({placeholders})',
                rows,
            )
        conn.commit()
        return len(rows)
