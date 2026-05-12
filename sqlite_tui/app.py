from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    DirectoryTree,
    Footer,
    Select,
    Header,
    Input,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)

from .connections import ConnectionStore
from .db import DBManagerProtocol, DuckDBManager, MySQLManager, SQLiteManager


class FilePickerScreen(ModalScreen[Optional[str]]):
    def __init__(self, start_path: Path, db_type: str) -> None:
        super().__init__()
        self.start_path = start_path
        self.db_type = db_type
        self.selected_file: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            title = "Select a SQLite database file" if self.db_type == "sqlite" else "Select a DuckDB database file"
            if self.db_type == "mysql":
                title = "MySQL uses URI (no file picker): mysql://user:pass@host:3306/database"
            yield Static(title)
            yield DirectoryTree(str(self.start_path), id="file-tree")
            with Horizontal(id="file-picker-actions"):
                yield Button("Parent", id="goto-parent")
                yield Button("Select", id="pick-file", variant="primary")
                yield Button("Cancel", id="cancel-pick")
            yield Static("No file selected.", id="file-picker-status")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        allowed = {".db", ".db3", ".sqlite", ".sqlite3"} if self.db_type == "sqlite" else {".duckdb", ".ddb", ".db"}
        if self.db_type == "mysql":
            self.query_one("#file-picker-status", Static).update("MySQL uses URI; close this picker and paste URI.")
            self.selected_file = None
            return
        if path.suffix.lower() not in allowed:
            allowed_txt = ".db, .db3, .sqlite, .sqlite3" if self.db_type == "sqlite" else ".duckdb, .ddb, .db"
            self.query_one("#file-picker-status", Static).update(
                f"Select a {allowed_txt} file."
            )
            self.selected_file = None
            return
        self.selected_file = str(path.resolve())
        self.query_one("#file-picker-status", Static).update(f"Selected: {self.selected_file}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-pick":
            self.dismiss(None)
            return
        if event.button.id == "goto-parent":
            tree = self.query_one("#file-tree", DirectoryTree)
            current = Path(tree.path)
            parent = current.parent
            tree.path = str(parent)
            tree.reload()
            self.query_one("#file-picker-status", Static).update(f"Current folder: {parent}")
            return
        if event.button.id == "pick-file":
            if self.selected_file:
                self.dismiss(self.selected_file)
            else:
                self.query_one("#file-picker-status", Static).update(
                    "Select a file first."
                )


class QueryLoadPickerScreen(ModalScreen[Optional[str]]):
    def __init__(self, start_path: Path) -> None:
        super().__init__()
        self.start_path = start_path
        self.selected_file: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            yield Static("Load query file")
            yield DirectoryTree(str(self.start_path), id="query-load-tree")
            with Horizontal(id="file-picker-actions"):
                yield Button("Parent", id="query-load-parent")
                yield Button("Select", id="query-load-select", variant="primary")
                yield Button("Cancel", id="query-load-cancel")
            yield Static("No file selected.", id="query-load-status")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        if path.suffix.lower() not in {".sql", ".txt"}:
            self.query_one("#query-load-status", Static).update(
                "Select a .sql or .txt file."
            )
            self.selected_file = None
            return
        self.selected_file = str(path.resolve())
        self.query_one("#query-load-status", Static).update(f"Selected: {self.selected_file}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "query-load-cancel":
            self.dismiss(None)
            return
        if event.button.id == "query-load-parent":
            tree = self.query_one("#query-load-tree", DirectoryTree)
            current = Path(tree.path)
            parent = current.parent
            tree.path = str(parent)
            tree.reload()
            self.query_one("#query-load-status", Static).update(f"Current folder: {parent}")
            return
        if event.button.id == "query-load-select":
            if self.selected_file:
                self.dismiss(self.selected_file)
            else:
                self.query_one("#query-load-status", Static).update("Select a file first.")


class QuerySavePickerScreen(ModalScreen[Optional[str]]):
    def __init__(self, start_path: Path, default_name: str = "query.sql") -> None:
        super().__init__()
        self.start_path = start_path
        self.default_name = default_name

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            yield Static("Save query file")
            yield DirectoryTree(str(self.start_path), id="query-save-tree")
            yield Input(value=self.default_name, placeholder="File name", id="query-save-name")
            with Horizontal(id="file-picker-actions"):
                yield Button("Parent", id="query-save-parent")
                yield Button("Save", id="query-save-select", variant="primary")
                yield Button("Cancel", id="query-save-cancel")
            yield Static("Select a folder and file name.", id="query-save-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "query-save-cancel":
            self.dismiss(None)
            return
        if event.button.id == "query-save-parent":
            tree = self.query_one("#query-save-tree", DirectoryTree)
            current = Path(tree.path)
            parent = current.parent
            tree.path = str(parent)
            tree.reload()
            self.query_one("#query-save-status", Static).update(f"Current folder: {parent}")
            return
        if event.button.id == "query-save-select":
            tree = self.query_one("#query-save-tree", DirectoryTree)
            file_name = self.query_one("#query-save-name", Input).value.strip()
            if not file_name:
                self.query_one("#query-save-status", Static).update("File name is required.")
                return
            if not file_name.lower().endswith(".sql"):
                file_name = f"{file_name}.sql"
            full_path = (Path(tree.path) / file_name).resolve()
            self.dismiss(str(full_path))


class PromptScreen(ModalScreen[Optional[str]]):
    def __init__(self, title: str, placeholder: str, initial: str = "") -> None:
        super().__init__()
        self.title = title
        self.placeholder = placeholder
        self.initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            yield Static(self.title)
            yield Input(placeholder=self.placeholder, value=self.initial, id="prompt-input")
            with Horizontal(id="file-picker-actions"):
                yield Button("OK", id="prompt-ok", variant="primary")
                yield Button("Cancel", id="prompt-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prompt-cancel":
            self.dismiss(None)
            return
        if event.button.id == "prompt-ok":
            value = self.query_one("#prompt-input", Input).value
            self.dismiss(value)


class ConfirmScreen(ModalScreen[bool]):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            yield Static(self.message)
            with Horizontal(id="file-picker-actions"):
                yield Button("Yes", id="confirm-yes", variant="error")
                yield Button("No", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
            return
        self.dismiss(False)


class ExportResultMenuScreen(ModalScreen[Optional[str]]):
    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            yield Static("Export query result")
            with Horizontal(id="file-picker-actions"):
                yield Button("CSV", id="export-csv", variant="primary")
                yield Button("Parquet", id="export-parquet")
                yield Button("Cancel", id="export-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-cancel":
            self.dismiss(None)
            return
        if event.button.id == "export-csv":
            self.dismiss("csv")
            return
        if event.button.id == "export-parquet":
            self.dismiss("parquet")
            return


class ExportOptionsScreen(ModalScreen[Optional[dict[str, Any]]]):
    def __init__(self, export_format: str, default_path: str) -> None:
        super().__init__()
        self.export_format = export_format
        self.default_path = default_path

    def compose(self) -> ComposeResult:
        with Vertical(id="export-options-modal"):
            yield Static(f"Export Options ({self.export_format.upper()})")
            if self.export_format == "csv":
                yield Static(
                    "\n".join(
                        [
                            "CSV options:",
                            "- Delimiter: field separator (e.g. ',', ';', '|').",
                            '- Quote char: text quote character (e.g. \'"\' or "\'").',
                            "- Header: true/false to include column names.",
                        ]
                    ),
                    id="export-options-help",
                )
            else:
                yield Static(
                    "\n".join(
                        [
                            "Parquet options:",
                            "- Compression: snappy, gzip, brotli, zstd, or none",
                            "  (availability depends on parquet engine).",
                        ]
                    ),
                    id="export-options-help",
                )
            yield Input(value=self.default_path, placeholder="Output file path", id="export-path")
            if self.export_format == "csv":
                yield Input(value=",", placeholder="Delimiter", id="export-csv-delimiter")
                yield Input(value='"', placeholder="Quote char", id="export-csv-quote")
                yield Input(value="true", placeholder="Header true/false", id="export-csv-header")
            else:
                yield Input(value="snappy", placeholder="Compression", id="export-parquet-compression")
            with Horizontal(id="file-picker-actions"):
                yield Button("Export", id="export-options-apply", variant="primary")
                yield Button("Cancel", id="export-options-cancel")
            yield Static("Configure options and export.", id="export-options-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-options-cancel":
            self.dismiss(None)
            return
        if event.button.id != "export-options-apply":
            return
        path = self.query_one("#export-path", Input).value.strip()
        if not path:
            self.query_one("#export-options-status", Static).update("Output path is required.")
            return
        payload: dict[str, Any] = {"format": self.export_format, "path": path}
        if self.export_format == "csv":
            delim = self.query_one("#export-csv-delimiter", Input).value
            quote = self.query_one("#export-csv-quote", Input).value
            header_raw = self.query_one("#export-csv-header", Input).value.strip().lower()
            if not delim:
                self.query_one("#export-options-status", Static).update("Delimiter is required.")
                return
            if not quote:
                self.query_one("#export-options-status", Static).update("Quote char is required.")
                return
            payload["delimiter"] = delim[0]
            payload["quotechar"] = quote[0]
            payload["header"] = header_raw not in {"false", "0", "no", "n"}
        else:
            compression = self.query_one("#export-parquet-compression", Input).value.strip() or "snappy"
            payload["compression"] = compression
        self.dismiss(payload)


class ImportFilePickerScreen(ModalScreen[Optional[str]]):
    def __init__(self, start_path: Path) -> None:
        super().__init__()
        self.start_path = start_path
        self.selected_file: Optional[str] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            yield Static("Import file to table")
            yield DirectoryTree(str(self.start_path), id="import-file-tree")
            with Horizontal(id="file-picker-actions"):
                yield Button("Parent", id="import-parent")
                yield Button("Select", id="import-select", variant="primary")
                yield Button("Cancel", id="import-cancel")
            yield Static("Select a .csv or .parquet file.", id="import-status")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        if path.suffix.lower() not in {".csv", ".parquet"}:
            self.selected_file = None
            self.query_one("#import-status", Static).update("Select a .csv or .parquet file.")
            return
        self.selected_file = str(path.resolve())
        self.query_one("#import-status", Static).update(f"Selected: {self.selected_file}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-cancel":
            self.dismiss(None)
            return
        if event.button.id == "import-parent":
            tree = self.query_one("#import-file-tree", DirectoryTree)
            current = Path(tree.path)
            parent = current.parent
            tree.path = str(parent)
            tree.reload()
            self.query_one("#import-status", Static).update(f"Current folder: {parent}")
            return
        if event.button.id == "import-select":
            if not self.selected_file:
                self.query_one("#import-status", Static).update("Select a file first.")
                return
            self.dismiss(self.selected_file)


class ImportWizardScreen(ModalScreen[Optional[dict[str, Any]]]):
    def __init__(
        self,
        file_path: Path,
        default_table: str,
        source_columns: list[str],
        preview_rows: list[dict[str, Any]],
    ) -> None:
        super().__init__()
        self.file_path = file_path
        self.default_table = default_table
        self.source_columns = source_columns
        self.preview_rows = preview_rows

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            yield Static(f"Import Wizard: {self.file_path.name}")
            yield Static(
                "\n".join(
                    [
                        "Reference:",
                        "- Preview shows first rows from source file.",
                        '- Column map JSON: {"old_col":"new_col"}',
                        '- Type overrides JSON: {"new_col":"INTEGER"}',
                        "- Existing table: confirm and append rows.",
                        "- Missing table: create table and load rows.",
                    ]
                ),
                id="import-wizard-reference",
            )
            yield Static(self._build_preview_text(), id="import-wizard-preview")
            yield Input(value=self.default_table, placeholder="Target table", id="import-wizard-table")
            yield Input(value="{}", placeholder='Column map JSON, e.g. {"src":"dest"}', id="import-wizard-map")
            yield Input(value="{}", placeholder='Type overrides JSON, e.g. {"dest":"INTEGER"}', id="import-wizard-types")
            with Horizontal(id="file-picker-actions"):
                yield Button("Apply", id="import-wizard-apply", variant="primary")
                yield Button("Cancel", id="import-wizard-cancel")
            yield Static("Review preview and mappings.", id="import-wizard-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-wizard-cancel":
            self.dismiss(None)
            return
        if event.button.id != "import-wizard-apply":
            return
        table = self.query_one("#import-wizard-table", Input).value.strip()
        map_raw = self.query_one("#import-wizard-map", Input).value.strip() or "{}"
        types_raw = self.query_one("#import-wizard-types", Input).value.strip() or "{}"
        try:
            col_map = json.loads(map_raw)
            type_map = json.loads(types_raw)
            if not isinstance(col_map, dict):
                raise ValueError("Column map must be a JSON object.")
            if not isinstance(type_map, dict):
                raise ValueError("Type overrides must be a JSON object.")
            self.dismiss(
                {
                    "table": table,
                    "column_map": {str(k): str(v) for k, v in col_map.items()},
                    "type_overrides": {str(k): str(v) for k, v in type_map.items()},
                }
            )
        except Exception as exc:  # noqa: BLE001
            self.query_one("#import-wizard-status", Static).update(f"Invalid JSON: {exc}")

    def _build_preview_text(self) -> str:
        lines = ["Columns: " + ", ".join(self.source_columns), "", "Preview (first rows):"]
        if not self.preview_rows:
            lines.append("(empty file)")
            return "\n".join(lines)
        for idx, row in enumerate(self.preview_rows, start=1):
            parts = [f"{k}={row.get(k)!r}" for k in self.source_columns]
            lines.append(f"{idx}. " + ", ".join(parts))
        return "\n".join(lines)


class SQLiteTUI(App):
    CSS_PATH = "app.tcss"
    TITLE = "DDBB Manager"
    BINDINGS = [
        ("ctrl+r", "run_query", "Run Query"),
        ("ctrl+l", "load_query", "Load Query"),
        ("ctrl+s", "save_query", "Save Query"),
        ("ctrl+t", "new_query_tab", "New Query Tab"),
        ("ctrl+i", "import_file", "Import File"),
        ("ctrl+m", "export_markdown", "Export MD"),
        ("ctrl+d", "export_schema_sql", "Export DDL"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.db_type: str = "sqlite"
        self.db_managers: dict[str, DBManagerProtocol] = {
            "sqlite": SQLiteManager(),
            "duckdb": DuckDBManager(),
            "mysql": MySQLManager(),
        }
        self.db: DBManagerProtocol = self.db_managers["sqlite"]
        self.connection_store = ConnectionStore()
        self.connections: list[dict[str, str]] = []
        self.selected_connection: dict[str, str] | None = None
        self.selected_object: str | None = None
        self.selected_object_type: str | None = None
        self.current_table_name: str | None = None
        self.current_table_columns: list[str] = []
        self.current_rowids: list[int] = []
        self.current_table_page: int = 0
        self.selected_cell_row: int | None = None
        self.selected_cell_col: int | None = None
        self.query_tab_count: int = 1
        self.query_results: dict[str, tuple[list[str], list[tuple]]] = {}
        self.query_pages: dict[str, int] = {"1": 0}
        self.query_sql_base: dict[str, str] = {}
        self.query_is_paginated: dict[str, bool] = {}
        self._last_conn_click_name: str | None = None
        self._last_conn_click_at: float = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="header-datetime-row"):
            yield Static("", id="header-datetime")
        with Horizontal(id="topbar"):
            yield Select(
                [("SQLite", "sqlite"), ("DuckDB", "duckdb"), ("MySQL", "mysql")],
                value="sqlite",
                id="db-type",
                allow_blank=False,
            )
            yield Input(placeholder="Path to database file", id="db-path")
            yield Button("Browse", id="browse-db")
            yield Input(placeholder="Connection name", id="conn-name")
            yield Button("Register", id="register-conn")
            yield Button("Open DB", id="open-db", variant="primary")
            yield Button("Refresh", id="refresh-schema")
            yield Button("Exit", id="exit-app", variant="error")
        with Horizontal(id="main"):
            with Vertical(id="left-column"):
                with Vertical(id="connections-pane"):
                    yield Static("Connections")
                    yield Tree("Saved connections", id="connections-tree")
                    with Horizontal(id="conn-actions"):
                        yield Button("Pin", id="pin-conn")
                        yield Button("Tag", id="tag-conn")
                        yield Button("Ren", id="rename-conn")
                        yield Button("Del", id="delete-conn", variant="error")
                        yield Button("Test", id="test-conn")
                with Vertical(id="db-info-pane"):
                    with VerticalScroll(id="db-info-scroll"):
                        yield Static("No database open.", id="db-info")
            with Vertical(id="schema-pane"):
                yield Static("Schema")
                yield Tree("Database objects", id="schema-tree")
            with Vertical(id="workspace"):
                with TabbedContent(id="main-tabs"):
                    with TabPane("Data", id="tab-data"):
                        with VerticalScroll(id="data-scroll"):
                            yield DataTable(id="data-table")
                            yield TextArea("", id="data-sql")
                        with Horizontal(id="data-actions"):
                            yield Input(value="200", id="data-fetch-size")
                            yield Button("<", id="data-prev-page")
                            yield Button(">", id="data-next-page")
                            yield Button("Tx+", id="tx-begin")
                            yield Button("Tx=", id="tx-commit")
                            yield Button("Tx-", id="tx-rollback")
                            yield Button("Ins", id="insert-row")
                            yield Button("Edit", id="edit-cell")
                            yield Button("Del", id="delete-row", variant="error")
                    with TabPane("Query", id="tab-query"):
                        with TabbedContent(id="query-tabs"):
                            with TabPane("Q1", id="query-pane-1"):
                                yield TextArea.code_editor(
                                    "",
                                    language="sql",
                                    id="query-editor-1",
                                    classes="query-editor",
                                )
                                yield DataTable(id="query-table-1", classes="query-table")
                        with Horizontal(id="query-page-actions"):
                            yield Button("Run", id="run-sql", variant="success")
                            yield Button("Export", id="export-query-result")
                            yield Button("Explain", id="explain-sql")
                            yield Button("Analyze", id="explain-analyze")
                            yield Button("Prev", id="query-prev-page")
                            yield Button("Next", id="query-next-page")
                    with TabPane("Explain", id="tab-explain"):
                        yield TextArea("", id="explain-text")
                        yield TextArea("", id="explain-raw")
                    with TabPane("DDL", id="tab-ddl"):
                        yield TextArea.code_editor(
                            "",
                            language="sql",
                            id="ddl-editor",
                            classes="ddl-editor",
                        )
                        with Horizontal(id="ddl-actions"):
                            yield Button("Apply DDL", id="apply-ddl", variant="success")
                            yield Button("Save DDL", id="save-ddl")
        yield Static("No database open.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#db-path", Input).value = self._default_db_path_for_type("sqlite")
        data_sql = self.query_one("#data-sql", TextArea)
        data_sql.language = "sql"
        data_sql.read_only = True
        data_sql.display = False
        explain_text = self.query_one("#explain-text", TextArea)
        explain_text.language = "sql"
        explain_text.read_only = True
        explain_raw = self.query_one("#explain-raw", TextArea)
        explain_raw.language = "sql"
        explain_raw.read_only = True
        ddl_editor = self.query_one("#ddl-editor", TextArea)
        ddl_editor.language = "sql"
        self.connections = self.connection_store.load()
        for conn in self.connections:
            if "type" not in conn:
                conn["type"] = "sqlite"
            if "tags" not in conn:
                conn["tags"] = []
            if "pinned" not in conn:
                conn["pinned"] = False
        self._refresh_connections()
        self._set_status("Set a database file path and press Open.")
        self._update_header_datetime()
        self.set_interval(1.0, self._update_header_datetime)
        self._open_last_used_if_available()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "db-type":
            return
        new_type = str(event.value)
        self._switch_db_type(new_type)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-db":
            self.action_open_db()
        elif event.button.id == "browse-db":
            self.action_browse_db()
        elif event.button.id == "register-conn":
            self.action_register_connection()
        elif event.button.id == "refresh-schema":
            self._refresh_schema()
        elif event.button.id == "export-md":
            self.action_export_markdown()
        elif event.button.id == "export-schema-sql":
            self.action_export_schema_sql()
        elif event.button.id == "exit-app":
            self.exit()
        elif event.button.id == "run-sql":
            self.action_run_query()
        elif event.button.id == "load-query":
            self.action_load_query()
        elif event.button.id == "save-query":
            self.action_save_query()
        elif event.button.id == "new-query-tab":
            self.action_new_query_tab()
        elif event.button.id == "tx-begin":
            self.action_begin_transaction()
        elif event.button.id == "tx-commit":
            self.action_commit_transaction()
        elif event.button.id == "tx-rollback":
            self.action_rollback_transaction()
        elif event.button.id == "insert-row":
            self.action_insert_row()
        elif event.button.id == "edit-cell":
            self.action_edit_cell()
        elif event.button.id == "delete-row":
            self.action_delete_row()
        elif event.button.id == "explain-sql":
            self.action_explain_query(analyze=False)
        elif event.button.id == "explain-analyze":
            self.action_explain_query(analyze=True)
        elif event.button.id == "rename-conn":
            self.action_rename_connection()
        elif event.button.id == "delete-conn":
            self.action_delete_connection()
        elif event.button.id == "test-conn":
            self.action_test_connection()
        elif event.button.id == "pin-conn":
            self.action_toggle_pin_connection()
        elif event.button.id == "tag-conn":
            self.action_set_tags_connection()
        elif event.button.id == "apply-ddl":
            self.action_apply_ddl()
        elif event.button.id == "save-ddl":
            self.action_save_ddl()
        elif event.button.id == "data-prev-page":
            self.action_data_prev_page()
        elif event.button.id == "data-next-page":
            self.action_data_next_page()
        elif event.button.id == "query-prev-page":
            self.action_query_prev_page()
        elif event.button.id == "query-next-page":
            self.action_query_next_page()
        elif event.button.id == "export-query-result":
            self.action_export_query_result()

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        if event.data_table.id != "data-table":
            return
        self.selected_cell_row = event.coordinate.row
        self.selected_cell_col = event.coordinate.column

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        source_tree = event.node.tree
        if source_tree.id == "connections-tree":
            node_data = event.node.data
            if isinstance(node_data, dict):
                self.selected_connection = node_data
                self._set_status(
                    f"Selected connection: {node_data['name']} [{node_data.get('type', 'sqlite')}] -> {node_data['path']}"
                )
                now = time.monotonic()
                name = node_data["name"]
                if self._last_conn_click_name == name and (now - self._last_conn_click_at) <= 0.45:
                    conn_type = str(node_data.get("type", "sqlite"))
                    self.query_one("#db-type", Select).value = conn_type
                    self._switch_db_type(conn_type)
                    self.query_one("#db-path", Input).value = node_data["path"]
                    self.action_open_db()
                self._last_conn_click_name = name
                self._last_conn_click_at = now
            return

        node_data = event.node.data
        if not node_data:
            return
        obj_type, obj_name = node_data
        if obj_type == "column":
            self._set_status(f"Selected column: {obj_name}")
            return
        self._clear_explain_tab()
        self._clear_ddl_tab()
        self._clear_data_tab()
        self.selected_object = obj_name
        self.selected_object_type = obj_type
        if obj_type == "table":
            self.current_table_page = 0
            self._load_table_preview(obj_name)
        elif obj_type == "view":
            self._load_view_info(obj_name)
            self._set_status(f"Selected view: {obj_name}")
        elif obj_type == "index":
            self._load_index_info(obj_name)
            self._set_status(f"Selected index: {obj_name}")
        elif obj_type == "trigger":
            self._load_trigger_info(obj_name)
            self._set_status(f"Selected trigger: {obj_name}")
        else:
            self._set_status(f"Selected {obj_type}: {obj_name}")
        self._load_selected_object_ddl(obj_type, obj_name)
        self._refresh_db_info()

    def action_open_db(self) -> None:
        raw = self.query_one("#db-path", Input).value.strip()
        if not raw:
            self._set_status("Please provide a database path.")
            return
        try:
            self._clear_explain_tab()
            self._clear_ddl_tab()
            self._clear_data_tab()
            self._clear_query_tab()
            self.db.connect(raw)
            self.selected_object = None
            self.selected_object_type = None
            self._refresh_schema()
            self._refresh_db_info()
            conn_name = self.query_one("#conn-name", Input).value.strip()
            stored_path = raw
            shown_path = raw
            if self.db_type != "mysql":
                stored_path = str(Path(raw).expanduser().resolve())
                shown_path = stored_path
            self.connection_store.save_last_used(conn_name, stored_path, self.db_type)
            self._set_status(f"Connected ({self.db_type}) to: {shown_path}")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Open failed: {exc}")

    def action_browse_db(self) -> None:
        if self.db_type == "mysql":
            self._set_status("MySQL uses URI. Example: mysql://user:pass@host:3306/database")
            return
        current = self.query_one("#db-path", Input).value.strip()
        if current:
            candidate = Path(current).expanduser()
            start_path = candidate.parent if candidate.exists() else Path.cwd()
        else:
            start_path = Path.cwd()

        def _on_file_picked(selected_path: str | None) -> None:
            if selected_path:
                self.query_one("#db-path", Input).value = selected_path
                self._set_status(f"Selected file: {selected_path}")

        self.push_screen(FilePickerScreen(start_path.resolve(), self.db_type), _on_file_picked)

    def action_register_connection(self) -> None:
        name = self.query_one("#conn-name", Input).value.strip()
        raw_path = self.query_one("#db-path", Input).value.strip()

        if not name:
            self._set_status("Please provide a connection name.")
            return
        if not raw_path:
            self._set_status("Please provide a database path.")
            return

        path = raw_path if self.db_type == "mysql" else str(Path(raw_path).expanduser().resolve())
        replaced = False
        for idx, conn in enumerate(self.connections):
            if conn["name"] == name:
                self.connections[idx] = {"name": name, "path": path, "type": self.db_type}
                if "tags" not in self.connections[idx]:
                    self.connections[idx]["tags"] = []
                if "pinned" not in self.connections[idx]:
                    self.connections[idx]["pinned"] = False
                replaced = True
                break
        if not replaced:
            self.connections.append(
                {"name": name, "path": path, "type": self.db_type, "tags": [], "pinned": False}
            )

        try:
            self.connection_store.save(self.connections)
            self._refresh_connections()
            self._set_status(f"Connection '{name}' registered.")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Register failed: {exc}")

    def action_rename_connection(self) -> None:
        if not self.selected_connection:
            self._set_status("Select a connection first.")
            return
        current_name = self.selected_connection["name"]

        def _on_name(raw: str | None) -> None:
            if not raw:
                return
            new_name = raw.strip()
            if not new_name:
                self._set_status("Connection name cannot be empty.")
                return
            for conn in self.connections:
                if conn is self.selected_connection:
                    continue
                if conn["name"] == new_name:
                    self._set_status(f"Connection '{new_name}' already exists.")
                    return
            self.selected_connection["name"] = new_name
            try:
                self.connection_store.save(self.connections)
                self._refresh_connections()
                self._set_status(f"Connection renamed to '{new_name}'.")
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Rename failed: {exc}")

        self.push_screen(
            PromptScreen("Rename connection", "New connection name", current_name),
            _on_name,
        )

    def action_delete_connection(self) -> None:
        if not self.selected_connection:
            self._set_status("Select a connection first.")
            return
        target = self.selected_connection

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                self._set_status("Delete cancelled.")
                return
            try:
                self.connections = [c for c in self.connections if c is not target]
                self.connection_store.save(self.connections)
                self.selected_connection = None
                self._refresh_connections()
                self._set_status("Connection deleted.")
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Delete failed: {exc}")

        self.push_screen(
            ConfirmScreen(f"Delete connection '{target['name']}'?"),
            _on_confirm,
        )

    def action_test_connection(self) -> None:
        if not self.selected_connection:
            self._set_status("Select a connection first.")
            return
        conn_type = str(self.selected_connection.get("type", "sqlite"))
        path = self.selected_connection.get("path", "")
        if conn_type not in {"sqlite", "duckdb"}:
            self._set_status(f"Unsupported connection type: {conn_type}")
            return
        manager: DBManagerProtocol = SQLiteManager() if conn_type == "sqlite" else DuckDBManager()
        try:
            manager.connect(path)
            _ = manager.list_objects()
            manager.close()
            self._set_status(f"Connection test passed: {self.selected_connection['name']}")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Connection test failed: {exc}")

    def action_toggle_pin_connection(self) -> None:
        if not self.selected_connection:
            self._set_status("Select a connection first.")
            return
        current = bool(self.selected_connection.get("pinned", False))
        self.selected_connection["pinned"] = not current
        try:
            self.connection_store.save(self.connections)
            self._refresh_connections()
            self._set_status(
                f"Connection {'pinned' if self.selected_connection['pinned'] else 'unpinned'}."
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Pin update failed: {exc}")

    def action_set_tags_connection(self) -> None:
        if not self.selected_connection:
            self._set_status("Select a connection first.")
            return
        existing = ", ".join(self.selected_connection.get("tags", []))

        def _on_tags(raw: str | None) -> None:
            if raw is None:
                return
            tags = [t.strip() for t in raw.split(",") if t.strip()]
            self.selected_connection["tags"] = tags
            try:
                self.connection_store.save(self.connections)
                self._refresh_connections()
                self._set_status("Tags updated.")
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Tag update failed: {exc}")

        self.push_screen(
            PromptScreen("Set tags (comma-separated)", "tag1, tag2", existing),
            _on_tags,
        )

    def action_run_query(self) -> None:
        self._clear_explain_tab()
        self._clear_ddl_tab()
        self._run_query_for_page(reset_page=True)

    def _run_query_for_page(self, reset_page: bool = False) -> None:
        editor, table = self._get_active_query_widgets()
        suffix = self._get_active_query_suffix()
        sql = editor.text.strip()
        if reset_page:
            self.query_pages[suffix] = 0
            self.query_sql_base[suffix] = sql
        table.clear(columns=True)
        try:
            page = self.query_pages.get(suffix, 0)
            fetch_size = 200
            base_sql = self.query_sql_base.get(suffix, sql)
            paginated = self._is_paginated_query(base_sql)
            run_sql = base_sql
            if paginated:
                offset = page * fetch_size
                run_sql = self._paginate_sql(base_sql, fetch_size, offset)
            cols, rows, msg = self.db.execute_sql(run_sql)
            self.query_is_paginated[suffix] = paginated
            self.query_results[suffix] = (cols, rows)
            if cols:
                table.add_columns(*cols)
                for row in rows:
                    table.add_row(*[self._fmt_cell(v) for v in row])
            if paginated and cols:
                self._set_status(
                    f"{msg} Page {page + 1} (fetch size {fetch_size})."
                )
            else:
                self._set_status(msg)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"SQL error: {exc}")

    def action_query_next_page(self) -> None:
        suffix = self._get_active_query_suffix()
        cols, rows = self.query_results.get(suffix, ([], []))
        fetch_size = 200
        if not self.query_is_paginated.get(suffix, False):
            self._set_status("Pagination is available for SELECT/WITH queries.")
            return
        if cols and len(rows) < fetch_size:
            self._set_status("Last page reached.")
            return
        self.query_pages[suffix] = self.query_pages.get(suffix, 0) + 1
        self._run_query_for_page(reset_page=False)

    def action_query_prev_page(self) -> None:
        suffix = self._get_active_query_suffix()
        page = self.query_pages.get(suffix, 0)
        if page <= 0:
            self._set_status("Already at first page.")
            return
        self.query_pages[suffix] = page - 1
        self._run_query_for_page(reset_page=False)

    def action_explain_query(self, analyze: bool) -> None:
        editor, _ = self._get_active_query_widgets()
        base_sql = editor.text.strip().rstrip(";")
        if not base_sql:
            self._set_status("Write a query first.")
            return
        explain_sql = self._build_explain_sql(base_sql, analyze)
        try:
            cols, rows, _ = self.db.execute_sql(explain_sql)
            text = self.query_one("#explain-text", TextArea)
            text.text = self._format_explain_text(explain_sql, cols, rows)
            raw = self.query_one("#explain-raw", TextArea)
            raw.text = self._format_explain_raw(cols, rows)
            self.query_one("#main-tabs", TabbedContent).active = "tab-explain"
            self._set_status("Explain generated.")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Explain error: {exc}")

    def action_load_query(self) -> None:
        start_path = Path.cwd()
        current_path = self.query_one("#db-path", Input).value.strip()
        if current_path:
            candidate = Path(current_path).expanduser()
            if candidate.exists():
                start_path = candidate.parent

        def _on_path(raw: str | None) -> None:
            if not raw:
                return
            try:
                path = Path(raw).expanduser().resolve()
                text = path.read_text(encoding="utf-8")
                editor, _ = self._get_active_query_widgets()
                editor.text = text
                self._clear_explain_tab()
                self._clear_ddl_tab()
                self._set_status(f"Query loaded: {path}")
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Load query failed: {exc}")

        self.push_screen(QueryLoadPickerScreen(start_path), _on_path)

    def action_save_query(self) -> None:
        start_path = Path.cwd()
        current_path = self.query_one("#db-path", Input).value.strip()
        if current_path:
            candidate = Path(current_path).expanduser()
            if candidate.exists():
                start_path = candidate.parent

        def _on_path(raw: str | None) -> None:
            if not raw:
                return
            try:
                path = Path(raw).expanduser().resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                editor, _ = self._get_active_query_widgets()
                sql_text = editor.text
                path.write_text(sql_text, encoding="utf-8")
                self._set_status(f"Query saved: {path}")
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Save query failed: {exc}")

        self.push_screen(QuerySavePickerScreen(start_path), _on_path)

    def action_new_query_tab(self) -> None:
        self.query_tab_count += 1
        n = self.query_tab_count
        tabs = self.query_one("#query-tabs", TabbedContent)
        pane = TabPane(
            f"Q{n}",
            TextArea.code_editor(
                "",
                language="sql",
                id=f"query-editor-{n}",
                classes="query-editor",
            ),
            DataTable(id=f"query-table-{n}", classes="query-table"),
            id=f"query-pane-{n}",
        )
        tabs.add_pane(pane)
        tabs.active = f"query-pane-{n}"
        self._clear_explain_tab()
        self._clear_ddl_tab()
        self.query_results[str(n)] = ([], [])
        self.query_pages[str(n)] = 0
        self.query_sql_base[str(n)] = ""
        self.query_is_paginated[str(n)] = False
        self._set_status(f"Created query tab Q{n}.")

    def action_export_query_result(self) -> None:
        suffix = self._get_active_query_suffix()
        cols, rows = self.query_results.get(suffix, ([], []))
        if not cols:
            self._set_status("No query result to export in active tab.")
            return

        def _on_format(selected_format: str | None) -> None:
            if not selected_format:
                return
            default_name = "query_result.csv" if selected_format == "csv" else "query_result.parquet"
            start_path = Path.cwd()
            current_path = self.query_one("#db-path", Input).value.strip()
            if current_path:
                candidate = Path(current_path).expanduser()
                if candidate.exists():
                    start_path = candidate.parent

            def _on_options(opts: dict[str, Any] | None) -> None:
                if not opts:
                    return
                try:
                    path = Path(str(opts.get("path", ""))).expanduser().resolve()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if selected_format == "csv":
                        if path.suffix.lower() != ".csv":
                            path = path.with_suffix(".csv")
                        with path.open("w", newline="", encoding="utf-8") as f:
                            writer = csv.writer(f)
                            writer = csv.writer(
                                f,
                                delimiter=str(opts.get("delimiter", ","))[0],
                                quotechar=str(opts.get("quotechar", '"'))[0],
                            )
                            if bool(opts.get("header", True)):
                                writer.writerow(cols)
                            writer.writerows(rows)
                    else:
                        if path.suffix.lower() != ".parquet":
                            path = path.with_suffix(".parquet")
                        try:
                            import pandas as pd  # type: ignore[import-not-found]
                        except Exception as exc:  # noqa: BLE001
                            raise RuntimeError(
                                "Parquet export requires pandas (and pyarrow/fastparquet)."
                            ) from exc
                        df = pd.DataFrame(rows, columns=cols)
                        df.to_parquet(path, index=False, compression=str(opts.get("compression", "snappy")))
                    self._set_status(f"Query result exported: {path}")
                except Exception as exc:  # noqa: BLE001
                    self._set_status(f"Export failed: {exc}")

            self.push_screen(
                ExportOptionsScreen(
                    selected_format,
                    str((start_path / default_name).resolve()),
                ),
                _on_options,
            )

        self.push_screen(ExportResultMenuScreen(), _on_format)

    def action_import_file(self) -> None:
        if self.db.path is None:
            self._set_status("Open a database first.")
            return
        start_path = self.db.path.parent if self.db.path else Path.cwd()

        def _on_file(raw_path: str | None) -> None:
            if not raw_path:
                return
            file_path = Path(raw_path).expanduser().resolve()
            default_table = self._sanitize_table_name(file_path.stem)
            try:
                source_columns, all_rows = self._read_import_file(file_path)
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Import read failed: {exc}")
                return
            preview_rows = all_rows[:5]

            def _on_wizard(payload: dict[str, Any] | None) -> None:
                if not payload:
                    return
                table_name = self._sanitize_table_name(str(payload.get("table", "")))
                if not table_name:
                    self._set_status("Invalid table name.")
                    return
                col_map = payload.get("column_map", {})
                type_map = payload.get("type_overrides", {})
                mapped_columns = [str(col_map.get(c, c)) for c in source_columns]
                mapped_rows = [
                    {str(col_map.get(k, k)): v for k, v in row.items()}
                    for row in all_rows
                ]

                def _do_import() -> None:
                    try:
                        inserted = self._import_rows_with_mapping(
                            table_name=table_name,
                            mapped_columns=mapped_columns,
                            mapped_rows=mapped_rows,
                            type_overrides=type_map if isinstance(type_map, dict) else {},
                        )
                        self._refresh_schema()
                        self._set_status(
                            f"Imported {inserted} row(s) into table '{table_name}'."
                        )
                    except Exception as exc:  # noqa: BLE001
                        self._set_status(f"Import failed: {exc}")

                if self.db.table_exists(table_name):
                    self.push_screen(
                        ConfirmScreen(
                            f"Table '{table_name}' exists. Load data into existing table?"
                        ),
                        lambda ok: _do_import() if ok else self._set_status("Import cancelled."),
                    )
                else:
                    _do_import()

            self.push_screen(
                ImportWizardScreen(
                    file_path=file_path,
                    default_table=default_table,
                    source_columns=source_columns,
                    preview_rows=preview_rows,
                ),
                _on_wizard,
            )

        self.push_screen(ImportFilePickerScreen(start_path), _on_file)

    def action_export_markdown(self) -> None:
        if self.db.path is None:
            self._set_status("Open a database first.")
            return
        default_path = str(self.db.path.with_suffix(".md"))

        def _on_path(raw: str | None) -> None:
            if not raw:
                return
            try:
                out_path = Path(raw).expanduser().resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(self._build_db_markdown_report(), encoding="utf-8")
                self._set_status(f"Markdown exported: {out_path}")
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Markdown export failed: {exc}")

        self.push_screen(
            PromptScreen("Export DB report (.md)", "Output file path", default_path),
            _on_path,
        )

    def action_export_md(self) -> None:
        self.action_export_markdown()

    def action_export_schema_sql(self) -> None:
        if self.db.path is None:
            self._set_status("Open a database first.")
            return
        default_path = str(self.db.path.with_name(f"{self.db.path.stem}_schema.sql"))

        def _on_path(raw: str | None) -> None:
            if not raw:
                return
            try:
                out_path = Path(raw).expanduser().resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(self._build_schema_sql_dump(), encoding="utf-8")
                self._set_status(f"Schema SQL exported: {out_path}")
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Schema export failed: {exc}")

        self.push_screen(
            PromptScreen("Export schema (.sql)", "Output file path", default_path),
            _on_path,
        )

    def action_apply_ddl(self) -> None:
        if self.db.path is None:
            self._set_status("Open a database first.")
            return
        sql = self.query_one("#ddl-editor", TextArea).text.strip()
        if not sql:
            self._set_status("DDL editor is empty.")
            return
        handled, message = self._try_apply_sqlite_create_table_patch(sql)
        if handled:
            self._refresh_schema()
            self._set_status(message)
            return
        try:
            _, _, msg = self.db.execute_sql(sql)
            self._refresh_schema()
            self._set_status(f"DDL applied. {msg}")
        except Exception as exc:  # noqa: BLE001
            if self._try_apply_sqlite_table_alter_from_create(sql, str(exc)):
                self._refresh_schema()
                return
            self._set_status(f"Apply DDL failed: {exc}")

    def _try_apply_sqlite_create_table_patch(self, sql: str) -> tuple[bool, str]:
        if self.db_type != "sqlite":
            return False, ""
        if self.selected_object_type != "table" or not self.selected_object:
            return False, ""
        if not sql.lstrip().lower().startswith("create table"):
            return False, ""

        table_name = self.selected_object
        try:
            existing_cols = {c.lower() for c in self.db.list_columns(table_name)}
            parsed_defs = self._parse_create_table_column_defs(sql)
            new_defs = [col_def for col_name, col_def in parsed_defs if col_name.lower() not in existing_cols]
            if not new_defs:
                if "if not exists" in sql.lower():
                    return True, "No new columns to add. CREATE TABLE IF NOT EXISTS does not alter existing tables."
                return False, ""
            escaped_table = table_name.replace('"', '""')
            for col_def in new_defs:
                self.db.execute_sql(f'ALTER TABLE "{escaped_table}" ADD COLUMN {col_def}')
            self._load_selected_object_ddl("table", table_name)
            return True, f"Added {len(new_defs)} new column(s) to '{table_name}' via ALTER TABLE."
        except Exception as exc:  # noqa: BLE001
            return True, f"Automatic ALTER TABLE patch failed: {exc}"

    def action_save_ddl(self) -> None:
        if self.db.path is None:
            self._set_status("Open a database first.")
            return
        sql = self.query_one("#ddl-editor", TextArea).text
        if not sql.strip():
            self._set_status("DDL editor is empty.")
            return

        default_name = "schema_object.sql"
        if self.selected_object:
            safe = self._sanitize_table_name(self.selected_object) or "schema_object"
            default_name = f"{safe}.sql"
        default_path = str((self.db.path.parent / default_name).resolve())

        def _on_path(raw: str | None) -> None:
            if not raw:
                return
            try:
                out_path = Path(raw).expanduser().resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(sql, encoding="utf-8")
                self._set_status(f"DDL saved: {out_path}")
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Save DDL failed: {exc}")

        self.push_screen(
            PromptScreen("Save DDL (.sql)", "Output file path", default_path),
            _on_path,
        )

    def action_begin_transaction(self) -> None:
        try:
            self.db.begin_transaction()
            self._set_status("Transaction started.")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Begin failed: {exc}")

    def action_commit_transaction(self) -> None:
        try:
            self.db.commit_transaction()
            self._set_status("Transaction committed.")
            self._reload_current_table_if_needed()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Commit failed: {exc}")

    def action_rollback_transaction(self) -> None:
        try:
            self.db.rollback_transaction()
            self._set_status("Transaction rolled back.")
            self._reload_current_table_if_needed()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Rollback failed: {exc}")

    def action_insert_row(self) -> None:
        if not self._ensure_selected_table():
            return
        cols_text = ", ".join(self.current_table_columns)
        title = (
            f"Insert row in {self.current_table_name}\n"
            f"Provide JSON object with columns. Available: {cols_text}"
        )

        def _on_insert(raw: str | None) -> None:
            if raw is None:
                return
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("Value must be a JSON object.")
                values: dict[str, object] = {}
                for key, value in parsed.items():
                    if key not in self.current_table_columns:
                        raise ValueError(f"Unknown column: {key}")
                    values[key] = value
                self.db.insert_row(self.current_table_name or "", values)
                self._set_status("Row inserted.")
                self._reload_current_table_if_needed()
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Insert failed: {exc}")

        self.push_screen(PromptScreen(title, '{"col": "value"}'), _on_insert)

    def action_edit_cell(self) -> None:
        if not self._ensure_selected_table():
            return
        if self.selected_cell_row is None or self.selected_cell_col is None:
            self._set_status("Select a table cell first.")
            return
        row_index = self.selected_cell_row
        col_index = self.selected_cell_col
        if row_index >= len(self.current_rowids) or col_index >= len(self.current_table_columns):
            self._set_status("Selected cell is out of range.")
            return
        rowid = self.current_rowids[row_index]
        column_name = self.current_table_columns[col_index]
        title = (
            f"Edit {column_name} (rowid={rowid})\n"
            "Use NULL (exact text) for SQL NULL."
        )

        def _on_edit(raw: str | None) -> None:
            if raw is None:
                return
            try:
                new_value: object = None if raw == "NULL" else raw
                self.db.update_cell_by_rowid(
                    self.current_table_name or "",
                    column_name,
                    rowid,
                    new_value,
                )
                self._set_status("Cell updated.")
                self._reload_current_table_if_needed()
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Update failed: {exc}")

        self.push_screen(PromptScreen(title, "New value"), _on_edit)

    def action_delete_row(self) -> None:
        if not self._ensure_selected_table():
            return
        if self.selected_cell_row is None:
            self._set_status("Select a row first (any cell in that row).")
            return
        row_index = self.selected_cell_row
        if row_index >= len(self.current_rowids):
            self._set_status("Selected row is out of range.")
            return
        rowid = self.current_rowids[row_index]
        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                self._set_status("Delete cancelled.")
                return
            try:
                self.db.delete_row_by_rowid(self.current_table_name or "", rowid)
                self._set_status(f"Row deleted (rowid={rowid}).")
                self._reload_current_table_if_needed()
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Delete failed: {exc}")

        self.push_screen(
            ConfirmScreen(f"Delete selected row (rowid={rowid}) from {self.current_table_name}?"),
            _on_confirm,
        )

    def action_data_next_page(self) -> None:
        if not self.current_table_name:
            self._set_status("Select a table first.")
            return
        fetch_size = self._get_fetch_size("#data-fetch-size")
        if len(self.current_rowids) < fetch_size:
            self._set_status("Last page reached.")
            return
        self.current_table_page += 1
        self._load_table_preview(self.current_table_name)

    def action_data_prev_page(self) -> None:
        if not self.current_table_name:
            self._set_status("Select a table first.")
            return
        if self.current_table_page <= 0:
            self._set_status("Already at first page.")
            return
        self.current_table_page -= 1
        self._load_table_preview(self.current_table_name)

    def _refresh_schema(self) -> None:
        tree = self.query_one("#schema-tree", Tree)
        tree.clear()
        root = tree.root
        root.expand()
        try:
            for obj_type, obj_name in self.db.list_objects():
                type_styles = {
                    "table": "bold green",
                    "view": "bold cyan",
                    "index": "bold yellow",
                    "trigger": "bold magenta",
                }
                type_text = Text(f"{obj_type}", style=type_styles.get(obj_type, "bold white"))
                label = Text.assemble(type_text, Text(f": {obj_name}"))
                if obj_type == "table":
                    try:
                        row_count = self.db.count_rows(obj_name)
                        label = Text.assemble(label, Text(f" ({row_count})", style="dim"))
                    except Exception:
                        label = Text.assemble(label, Text(" (?)", style="dim"))
                obj_node = root.add(
                    label,
                    data=(obj_type, obj_name),
                    expand=False,
                )
                if obj_type in {"table", "view"}:
                    for col_name, col_type in self.db.list_columns_with_types(obj_name):
                        obj_node.add_leaf(
                            f"{col_name} ({col_type})",
                            data=("column", col_name),
                        )
            tree.root.expand()
            self._set_status("Schema loaded.")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Schema load error: {exc}")

    def _refresh_db_info(self) -> None:
        info = self.query_one("#db-info", Static)
        if self.db.path is None:
            info.update("No database open.")
            return
        path = self.db.path
        try:
            stat = path.stat()
            size_kb = stat.st_size / 1024
            objects = self.db.list_objects()
            table_count = sum(1 for t, _ in objects if t == "table")
            view_count = sum(1 for t, _ in objects if t == "view")
            info.update(
                "\n".join(
                    [
                        f"Path: {path}",
                        f"Size: {size_kb:.1f} KB",
                        f"Tables: {table_count}",
                        f"Views: {view_count}",
                        f"Modified: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))}",
                        "",
                        self._selected_object_info(),
                    ]
                )
            )
        except Exception as exc:  # noqa: BLE001
            info.update(f"Info error: {exc}")

    def _selected_object_info(self) -> str:
        if not self.selected_object or not self.selected_object_type:
            return "Selected object: none"
        if self.selected_object_type != "table":
            return f"Selected {self.selected_object_type}: {self.selected_object}"
        try:
            columns = list(self.db.list_columns(self.selected_object))
        except Exception as exc:  # noqa: BLE001
            return f"Selected table: {self.selected_object}\nColumns: error ({exc})"
        if not columns:
            return f"Selected table: {self.selected_object}\nColumns: none"
        return (
            f"Selected table: {self.selected_object}\n"
            f"Columns ({len(columns)}): {', '.join(columns)}"
        )

    def _refresh_connections(self) -> None:
        tree = self.query_one("#connections-tree", Tree)
        tree.clear()
        root = tree.root
        root.expand()
        favorites = [c for c in self.connections if bool(c.get("pinned", False))]
        non_favorites = [c for c in self.connections if not bool(c.get("pinned", False))]

        fav_node = root.add("Favorites", expand=True)
        for conn in sorted(favorites, key=lambda c: c["name"].lower()):
            self._add_connection_leaf(fav_node, conn)

        tag_map: dict[str, list[dict[str, str]]] = {}
        for conn in non_favorites:
            for tag in conn.get("tags", []):
                tag_map.setdefault(str(tag), []).append(conn)

        tags_node = root.add("Tags", expand=True)
        for tag in sorted(tag_map.keys(), key=lambda t: t.lower()):
            tag_node = tags_node.add(tag, expand=False)
            for conn in sorted(tag_map[tag], key=lambda c: c["name"].lower()):
                self._add_connection_leaf(tag_node, conn)

        others_node = root.add("Others", expand=True)
        tagged_ids = {id(c) for lst in tag_map.values() for c in lst}
        for conn in sorted(non_favorites, key=lambda c: c["name"].lower()):
            if id(conn) in tagged_ids:
                continue
            self._add_connection_leaf(others_node, conn)
        tree.root.expand_all()

    def _add_connection_leaf(self, parent_node: Tree.Node, conn: dict[str, str]) -> None:
        conn_type = str(conn.get("type", "sqlite")).upper()
        tags = conn.get("tags", [])
        tags_txt = f" tags={','.join(tags)}" if tags else ""
        pin = " *" if bool(conn.get("pinned", False)) else ""
        parent_node.add_leaf(
            f"{conn['name']}{pin} [{conn_type}] ({conn['path']}){tags_txt}",
            data=conn,
        )

    def _load_table_preview(self, table_name: str) -> None:
        table = self.query_one("#data-table", DataTable)
        table.clear(columns=True)
        self._set_data_sql_text(None)
        try:
            fetch_size = self._get_fetch_size("#data-fetch-size")
            offset = self.current_table_page * fetch_size
            cols, rows, rowids = self.db.preview_table_with_rowid(
                table_name, limit=fetch_size, offset=offset
            )
            table.add_columns(*cols)
            for row in rows:
                table.add_row(*[self._fmt_cell(v) for v in row])
            self.current_table_name = table_name
            self.current_table_columns = cols
            self.current_rowids = rowids
            self.selected_cell_row = None
            self.selected_cell_col = None
            self._set_status(
                f"Loaded table: {table_name} page {self.current_table_page + 1} "
                f"({len(rows)} rows, fetch size {fetch_size})"
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Table preview error: {exc}")

    def _load_index_info(self, index_name: str) -> None:
        table = self.query_one("#data-table", DataTable)
        self._clear_current_table_context()
        try:
            sql = self.db.get_object_sql("index", index_name)
            cols, rows = self.db.get_index_info(index_name)
            table.add_columns("Property", "Value")
            table.add_row("Type", "INDEX")
            table.add_row("Name", index_name)
            table.add_row("SQL", sql or "(no SQL definition)")
            table.add_row("", "")
            if cols and rows:
                row_maps = [dict(zip(cols, row)) for row in rows]

                def _first_present(m: dict[str, object], keys: list[str]) -> object | None:
                    for key in keys:
                        if key in m:
                            return m[key]
                    return None

                col_values: list[str] = []
                for m in row_maps:
                    v = _first_present(m, ["name", "column_name", "expressions"])
                    if v is not None:
                        col_values.append(str(v))
                if col_values:
                    table.add_row("Indexed Columns", ", ".join(col_values))
                else:
                    table.add_row("Indexed Columns", "(not available)")

                for idx, m in enumerate(row_maps, start=1):
                    seq = _first_present(m, ["seqno", "seq_in_index"])
                    seq_label = f"Entry {seq}" if seq is not None else f"Entry {idx}"
                    details = []
                    for c in cols:
                        details.append(f"{c}={m.get(c)}")
                    table.add_row(seq_label, ", ".join(details))
            else:
                table.add_row("Indexed Columns", "(none)")
            self._set_data_sql_text(sql or "(no SQL definition)")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Index info error: {exc}")

    def _load_trigger_info(self, trigger_name: str) -> None:
        table = self.query_one("#data-table", DataTable)
        self._clear_current_table_context()
        try:
            sql = self.db.get_object_sql("trigger", trigger_name)
            table.add_columns("Property", "Value")
            table.add_row("Type", "TRIGGER")
            table.add_row("Name", trigger_name)
            table.add_row("SQL", sql or "(no SQL definition)")
            self._set_data_sql_text(sql or "(no SQL definition)")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Trigger info error: {exc}")

    def _load_view_info(self, view_name: str) -> None:
        table = self.query_one("#data-table", DataTable)
        self._clear_current_table_context()
        try:
            sql = self.db.get_object_sql("view", view_name)
            table.add_columns("Property", "Value")
            table.add_row("Type", "VIEW")
            table.add_row("Name", view_name)
            table.add_row("SQL", sql or "(no SQL definition)")
            self._set_data_sql_text(sql or "(no SQL definition)")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"View info error: {exc}")

    def _clear_data_tab(self) -> None:
        self.query_one("#data-table", DataTable).clear(columns=True)
        self._set_data_sql_text(None)
        self._clear_current_table_context()
        self.current_table_page = 0

    def _clear_query_tab(self) -> None:
        for i in range(1, self.query_tab_count + 1):
            editor = self.query_one(f"#query-editor-{i}", TextArea)
            table = self.query_one(f"#query-table-{i}", DataTable)
            editor.text = ""
            table.clear(columns=True)
            self.query_results[str(i)] = ([], [])
            self.query_pages[str(i)] = 0
            self.query_sql_base[str(i)] = ""
            self.query_is_paginated[str(i)] = False
        self._clear_explain_tab()
        self._clear_ddl_tab()

    def _get_active_query_widgets(self) -> tuple[TextArea, DataTable]:
        tabs = self.query_one("#query-tabs", TabbedContent)
        active = tabs.active or "query-pane-1"
        suffix = active.replace("query-pane-", "")
        editor = self.query_one(f"#query-editor-{suffix}", TextArea)
        table = self.query_one(f"#query-table-{suffix}", DataTable)
        return editor, table

    def _get_active_query_suffix(self) -> str:
        tabs = self.query_one("#query-tabs", TabbedContent)
        active = tabs.active or "query-pane-1"
        return active.replace("query-pane-", "")

    def _get_fetch_size(self, input_id: str) -> int:
        raw = self.query_one(input_id, Input).value.strip()
        try:
            value = int(raw)
        except ValueError:
            value = 200
        return max(1, min(value, 10000))

    @staticmethod
    def _is_paginated_query(sql: str) -> bool:
        q = sql.lstrip().lower()
        return q.startswith("select") or q.startswith("with")

    @staticmethod
    def _paginate_sql(sql: str, limit: int, offset: int) -> str:
        base = sql.strip().rstrip(";")
        return f"SELECT * FROM ({base}) AS _q LIMIT {int(limit)} OFFSET {int(offset)}"

    def _set_data_sql_text(self, sql_text: str | None) -> None:
        sql_view = self.query_one("#data-sql", TextArea)
        if sql_text:
            sql_view.text = sql_text
            sql_view.display = True
        else:
            sql_view.text = ""
            sql_view.display = False

    def _clear_explain_tab(self) -> None:
        self.query_one("#explain-text", TextArea).text = ""
        self.query_one("#explain-raw", TextArea).text = ""

    def _clear_ddl_tab(self) -> None:
        self.query_one("#ddl-editor", TextArea).text = ""

    def _read_import_file(self, file_path: Path) -> tuple[list[str], list[dict[str, Any]]]:
        ext = file_path.suffix.lower()
        if ext == ".csv":
            with file_path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise ValueError("CSV file has no header.")
                cols = [str(c).strip() for c in reader.fieldnames if c and str(c).strip()]
                rows = [{c: row.get(c) for c in cols} for row in reader]
                return cols, rows
        if ext == ".parquet":
            try:
                import pandas as pd  # type: ignore[import-not-found]
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("Parquet import requires pandas (and pyarrow/fastparquet).") from exc
            df = pd.read_parquet(file_path)
            cols = [str(c) for c in df.columns]
            rows = df.to_dict(orient="records")
            return cols, rows
        raise ValueError("Unsupported import format. Use .csv or .parquet")

    def _import_rows_with_mapping(
        self,
        table_name: str,
        mapped_columns: list[str],
        mapped_rows: list[dict[str, Any]],
        type_overrides: dict[str, str],
    ) -> int:
        unique_cols: list[str] = []
        for c in mapped_columns:
            if c not in unique_cols:
                unique_cols.append(c)
        if not unique_cols:
            raise ValueError("No columns to import.")

        if not self.db.table_exists(table_name):
            defs: list[str] = []
            for col in unique_cols:
                override = str(type_overrides.get(col, "")).strip()
                col_type = override if override else ("VARCHAR" if self.db_type == "duckdb" else "TEXT")
                defs.append(f'{self._quote_ident(col)} {col_type}')
            create_sql = f"CREATE TABLE {self._quote_ident(table_name)} ({', '.join(defs)})"
            self.db.execute_sql(create_sql)

        inserted = 0
        for row in mapped_rows:
            payload = {c: row.get(c) for c in unique_cols}
            self.db.insert_row(table_name, payload)
            inserted += 1
        return inserted

    @staticmethod
    def _format_explain_text(sql: str, cols: list[str], rows: list[tuple]) -> str:
        lines = ["-- Explain Query", sql, ""]
        if not cols:
            lines.append("(no result columns)")
            return "\n".join(lines)
        header = " | ".join(cols)
        lines.append(header)
        lines.append("-" * len(header))
        for row in rows:
            lines.append(" | ".join("NULL" if v is None else str(v) for v in row))
        return "\n".join(lines)

    @staticmethod
    def _format_explain_raw(cols: list[str], rows: list[tuple]) -> str:
        if not cols:
            return "(no raw result)"
        lines = [", ".join(cols), "-" * 24]
        for row in rows:
            for idx, value in enumerate(row):
                col = cols[idx] if idx < len(cols) else f"col_{idx}"
                lines.append(f"{col}: {'NULL' if value is None else value}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _build_explain_sql(self, base_sql: str, analyze: bool) -> str:
        # SQLite does not support "EXPLAIN ANALYZE <query>".
        # Use engine-specific explain forms.
        if self.db_type == "sqlite":
            if analyze:
                return f"EXPLAIN {base_sql}"
            return f"EXPLAIN QUERY PLAN {base_sql}"
        return f"{'EXPLAIN ANALYZE' if analyze else 'EXPLAIN'} {base_sql}"

    def _clear_current_table_context(self) -> None:
        self.current_table_name = None
        self.current_table_columns = []
        self.current_rowids = []
        self.selected_cell_row = None
        self.selected_cell_col = None

    def _ensure_selected_table(self) -> bool:
        if self.selected_object_type != "table" or not self.current_table_name:
            self._set_status("Select a table first.")
            return False
        return True

    def _reload_current_table_if_needed(self) -> None:
        table_name = self.current_table_name
        if table_name:
            self._clear_data_tab()
            self._load_table_preview(table_name)

    def _load_selected_object_ddl(self, obj_type: str, obj_name: str) -> None:
        try:
            sql = self.db.get_object_sql(obj_type, obj_name).strip()
        except Exception:
            sql = ""
        editor = self.query_one("#ddl-editor", TextArea)
        if sql:
            editor.text = sql if sql.endswith(";") else f"{sql};"
        else:
            editor.text = f"-- No DDL found for {obj_type}: {obj_name}"

    def _try_apply_sqlite_table_alter_from_create(self, sql: str, error_text: str) -> bool:
        if self.db_type != "sqlite":
            return False
        if self.selected_object_type != "table" or not self.selected_object:
            return False
        if "already exists" not in error_text.lower():
            return False
        if not sql.lstrip().lower().startswith("create table"):
            return False

        table_name = self.selected_object
        try:
            existing_cols = {c.lower() for c in self.db.list_columns(table_name)}
            parsed_defs = self._parse_create_table_column_defs(sql)
            new_defs = [col_def for col_name, col_def in parsed_defs if col_name.lower() not in existing_cols]
            if not new_defs:
                self._set_status("No new columns to add. Table already exists.")
                return True

            escaped_table = table_name.replace('"', '""')
            for col_def in new_defs:
                self.db.execute_sql(f'ALTER TABLE "{escaped_table}" ADD COLUMN {col_def}')
            self._set_status(
                f"DDL applied as ALTER TABLE. Added {len(new_defs)} new column(s) to '{table_name}'."
            )
            self._load_selected_object_ddl("table", table_name)
            return True
        except Exception as exc:  # noqa: BLE001
            self._set_status(
                "Table exists and CREATE TABLE failed. "
                f"Automatic ALTER TABLE fallback also failed: {exc}"
            )
            return True

    @staticmethod
    def _parse_create_table_column_defs(sql: str) -> list[tuple[str, str]]:
        text = sql.strip()
        start = text.find("(")
        if start < 0:
            return []
        depth = 0
        end = -1
        for idx in range(start, len(text)):
            ch = text[idx]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        if end < 0:
            return []

        inner = text[start + 1 : end]
        parts: list[str] = []
        buf: list[str] = []
        depth = 0
        for ch in inner:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                part = "".join(buf).strip()
                if part:
                    parts.append(part)
                buf = []
                continue
            buf.append(ch)
        last = "".join(buf).strip()
        if last:
            parts.append(last)

        out: list[tuple[str, str]] = []
        for part in parts:
            low = part.lstrip().lower()
            if low.startswith(("constraint ", "primary ", "foreign ", "unique ", "check ")):
                continue
            name = SQLiteTUI._extract_column_name_from_def(part)
            if not name:
                continue
            out.append((name, part))
        return out

    @staticmethod
    def _extract_column_name_from_def(definition: str) -> str:
        s = definition.strip()
        if not s:
            return ""
        if s[0] == '"':
            end = s.find('"', 1)
            return s[1:end] if end > 1 else ""
        if s[0] == "[":
            end = s.find("]", 1)
            return s[1:end] if end > 1 else ""
        if s[0] == "`":
            end = s.find("`", 1)
            return s[1:end] if end > 1 else ""
        return s.split()[0] if s.split() else ""

    def _build_db_markdown_report(self) -> str:
        if self.db.path is None:
            return "# Database Report\n\nNo database open.\n"
        db_path = self.db.path
        stat = db_path.stat()
        objects = self.db.list_objects()
        tables = [name for typ, name in objects if typ == "table"]
        views = [name for typ, name in objects if typ == "view"]
        indexes = [name for typ, name in objects if typ == "index"]
        triggers = [name for typ, name in objects if typ == "trigger"]

        lines: list[str] = []
        lines.append("# Database Report")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Path: `{db_path}`")
        lines.append(f"- Size: `{stat.st_size}` bytes")
        lines.append(
            f"- Modified: `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))}`"
        )
        lines.append(f"- Tables: `{len(tables)}`")
        lines.append(f"- Views: `{len(views)}`")
        lines.append(f"- Indexes: `{len(indexes)}`")
        lines.append(f"- Triggers: `{len(triggers)}`")
        lines.append("")
        lines.append("## Objects")
        lines.append("")

        for obj_type, obj_name in objects:
            lines.append(f"### {obj_type}: `{obj_name}`")
            if obj_type == "table":
                try:
                    row_count = self.db.count_rows(obj_name)
                    lines.append(f"- Rows: `{row_count}`")
                except Exception:
                    lines.append("- Rows: `unknown`")
            if obj_type in {"table", "view"}:
                cols = list(self.db.list_columns_with_types(obj_name))
                lines.append("- Columns:")
                if cols:
                    for col_name, col_type in cols:
                        lines.append(f"  - `{col_name}` ({col_type})")
                else:
                    lines.append("  - none")
            obj_sql = self.db.get_object_sql(obj_type, obj_name).strip()
            if obj_sql:
                lines.append("- SQL:")
                lines.append("```sql")
                lines.append(obj_sql)
                lines.append("```")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _build_schema_sql_dump(self) -> str:
        if self.db.path is None:
            return "-- No database open.\n"
        lines: list[str] = []
        lines.append(f"-- {self.db_type.upper()} schema export")
        lines.append(f"-- Source: {self.db.path}")
        lines.append(
            f"-- Generated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
        )
        lines.append("")
        for obj_type, obj_name in self.db.list_objects():
            sql = self.db.get_object_sql(obj_type, obj_name).strip()
            if not sql:
                continue
            lines.append(f"-- {obj_type}: {obj_name}")
            lines.append(f"{sql};")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _fmt_cell(value: object) -> str:
        if value is None:
            return "NULL"
        return str(value)

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _update_header_datetime(self) -> None:
        self.query_one("#header-datetime", Static).update(
            datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )

    def _open_last_used_if_available(self) -> None:
        last = self.connection_store.load_last_used()
        if not last:
            return
        conn_type = str(last.get("type", "sqlite"))
        if conn_type not in self.db_managers:
            return
        raw_path = str(last.get("path", "")).strip()
        if not raw_path:
            return
        if conn_type != "mysql":
            try:
                path = Path(raw_path).expanduser().resolve()
            except Exception:
                return
            if not path.exists():
                return
            raw_path = str(path)
        self.query_one("#db-type", Select).value = conn_type
        self._switch_db_type(conn_type)
        self.query_one("#db-path", Input).value = raw_path
        if last.get("name"):
            self.query_one("#conn-name", Input).value = str(last.get("name"))
        self.action_open_db()

    def _switch_db_type(self, db_type: str) -> None:
        if db_type not in self.db_managers:
            self._set_status(f"Unsupported DB type: {db_type}")
            return
        if db_type == self.db_type:
            return
        try:
            self.db.close()
        except Exception:
            pass
        self.db_type = db_type
        self.db = self.db_managers[db_type]
        current = self.query_one("#db-path", Input).value.strip()
        if not current:
            self.query_one("#db-path", Input).value = self._default_db_path_for_type(db_type)
        self._clear_data_tab()
        self._clear_query_tab()
        self.selected_object = None
        self.selected_object_type = None
        self.query_one("#schema-tree", Tree).clear()
        self.query_one("#db-info", Static).update("No database open.")
        self._set_status(f"Connection type set to {db_type.upper()}.")

    @staticmethod
    def _default_db_path_for_type(db_type: str) -> str:
        if db_type == "sqlite":
            return "example.db"
        if db_type == "duckdb":
            return "example.duckdb"
        return "mysql://user:password@localhost:3306/database"

    @staticmethod
    def _sanitize_table_name(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value.strip())
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned.strip("_")

    @staticmethod
    def _quote_ident(value: str) -> str:
        return '"' + value.replace('"', '""') + '"'


def main() -> None:
    SQLiteTUI().run()
