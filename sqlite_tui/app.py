from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)

from .connections import ConnectionStore
from .db import SQLiteManager


class FilePickerScreen(ModalScreen[Optional[str]]):
    def __init__(self, start_path: Path) -> None:
        super().__init__()
        self.start_path = start_path
        self.selected_file: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="file-picker-modal"):
            yield Static("Select a SQLite database file")
            yield DirectoryTree(str(self.start_path), id="file-tree")
            with Horizontal(id="file-picker-actions"):
                yield Button("Parent", id="goto-parent")
                yield Button("Select", id="pick-file", variant="primary")
                yield Button("Cancel", id="cancel-pick")
            yield Static("No file selected.", id="file-picker-status")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        if path.suffix.lower() not in {".db", ".db3", ".sqlite", ".sqlite3"}:
            self.query_one("#file-picker-status", Static).update(
                "Select a .db, .db3, .sqlite, or .sqlite3 file."
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


class SQLiteTUI(App):
    CSS_PATH = "app.tcss"
    BINDINGS = [("ctrl+r", "run_query", "Run Query"), ("ctrl+o", "open_db", "Open DB")]

    def __init__(self) -> None:
        super().__init__()
        self.db = SQLiteManager()
        self.connection_store = ConnectionStore()
        self.connections: list[dict[str, str]] = []
        self.selected_connection: dict[str, str] | None = None
        self.selected_object: str | None = None
        self.selected_object_type: str | None = None
        self.current_table_name: str | None = None
        self.current_table_columns: list[str] = []
        self.current_rowids: list[int] = []
        self.selected_cell_row: int | None = None
        self.selected_cell_col: int | None = None
        self.query_tab_count: int = 1
        self._last_conn_click_name: str | None = None
        self._last_conn_click_at: float = 0.0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="topbar"):
            yield Input(placeholder="Path to SQLite database file", id="db-path")
            yield Button("Br", id="browse-db")
            yield Input(placeholder="Connection name", id="conn-name")
            yield Button("Op", id="open-db", variant="primary")
            yield Button("Reg", id="register-conn")
            yield Button("Ref", id="refresh-schema")
            yield Button("Exit", id="exit-app", variant="error")
        with Horizontal(id="main"):
            with Vertical(id="left-column"):
                with Vertical(id="connections-pane"):
                    yield Static("Connections")
                    yield Tree("Saved connections", id="connections-tree")
                with Vertical(id="db-info-pane"):
                    yield Static("Database Info")
                    yield Static("No database open.", id="db-info")
            with Vertical(id="schema-pane"):
                yield Static("Schema")
                yield Tree("Database objects", id="schema-tree")
            with Vertical(id="workspace"):
                with TabbedContent():
                    with TabPane("Data"):
                        with VerticalScroll(id="data-scroll"):
                            yield DataTable(id="data-table")
                            yield TextArea("", id="data-sql")
                        with Horizontal(id="data-actions"):
                            yield Button("Tx+", id="tx-begin")
                            yield Button("Tx=", id="tx-commit")
                            yield Button("Tx-", id="tx-rollback")
                            yield Button("Ins", id="insert-row")
                            yield Button("Edit", id="edit-cell")
                            yield Button("Del", id="delete-row", variant="error")
                    with TabPane("Query"):
                        with Horizontal(id="query-actions"):
                            yield Button("+Tab", id="new-query-tab")
                            yield Button("Load", id="load-query")
                            yield Button("Save", id="save-query")
                            yield Button("Run SQL", id="run-sql", variant="success")
                            yield Button("MD", id="export-md")
                            yield Button("DDL", id="export-schema-sql")
                        with TabbedContent(id="query-tabs"):
                            with TabPane("Q1", id="query-pane-1"):
                                yield TextArea.code_editor(
                                    "",
                                    language="sql",
                                    id="query-editor-1",
                                    classes="query-editor",
                                )
                                yield DataTable(id="query-table-1", classes="query-table")
        yield Static("No database open.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#db-path", Input).value = "example.db"
        data_sql = self.query_one("#data-sql", TextArea)
        data_sql.language = "sql"
        data_sql.read_only = True
        data_sql.display = False
        self.connections = self.connection_store.load()
        self._refresh_connections()
        self._set_status("Set a SQLite file path and press Open.")

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
                    f"Selected connection: {node_data['name']} -> {node_data['path']}"
                )
                now = time.monotonic()
                name = node_data["name"]
                if self._last_conn_click_name == name and (now - self._last_conn_click_at) <= 0.45:
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
        self._clear_data_tab()
        self.selected_object = obj_name
        self.selected_object_type = obj_type
        if obj_type == "table":
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
        self._refresh_db_info()

    def action_open_db(self) -> None:
        raw = self.query_one("#db-path", Input).value.strip()
        if not raw:
            self._set_status("Please provide a database path.")
            return
        try:
            self._clear_data_tab()
            self._clear_query_tab()
            self.db.connect(raw)
            self.selected_object = None
            self.selected_object_type = None
            self._refresh_schema()
            self._refresh_db_info()
            self._set_status(f"Connected to: {Path(raw).expanduser().resolve()}")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Open failed: {exc}")

    def action_browse_db(self) -> None:
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

        self.push_screen(FilePickerScreen(start_path.resolve()), _on_file_picked)

    def action_register_connection(self) -> None:
        name = self.query_one("#conn-name", Input).value.strip()
        raw_path = self.query_one("#db-path", Input).value.strip()

        if not name:
            self._set_status("Please provide a connection name.")
            return
        if not raw_path:
            self._set_status("Please provide a database path.")
            return

        path = str(Path(raw_path).expanduser().resolve())
        replaced = False
        for idx, conn in enumerate(self.connections):
            if conn["name"] == name:
                self.connections[idx] = {"name": name, "path": path}
                replaced = True
                break
        if not replaced:
            self.connections.append({"name": name, "path": path})

        try:
            self.connection_store.save(self.connections)
            self._refresh_connections()
            self._set_status(f"Connection '{name}' registered.")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Register failed: {exc}")

    def action_run_query(self) -> None:
        editor, table = self._get_active_query_widgets()
        sql = editor.text
        table.clear(columns=True)
        try:
            cols, rows, msg = self.db.execute_sql(sql)
            if cols:
                table.add_columns(*cols)
                for row in rows:
                    table.add_row(*[self._fmt_cell(v) for v in row])
            self._set_status(msg)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"SQL error: {exc}")

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
        self._set_status(f"Created query tab Q{n}.")

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
        for conn in self.connections:
            root.add_leaf(f"{conn['name']} ({conn['path']})", data=conn)
        tree.root.expand_all()

    def _load_table_preview(self, table_name: str) -> None:
        table = self.query_one("#data-table", DataTable)
        self._set_data_sql_text(None)
        try:
            cols, rows, rowids = self.db.preview_table_with_rowid(table_name, limit=200)
            table.add_columns(*cols)
            for row in rows:
                table.add_row(*[self._fmt_cell(v) for v in row])
            self.current_table_name = table_name
            self.current_table_columns = cols
            self.current_rowids = rowids
            self.selected_cell_row = None
            self.selected_cell_col = None
            self._set_status(f"Loaded table: {table_name} ({len(rows)} preview rows)")
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
                table.add_row("Indexed Columns", ", ".join(str(row[2]) for row in rows))
                for row in rows:
                    # PRAGMA index_info columns: seqno, cid, name
                    table.add_row(f"Column seq {row[0]}", str(row[2]))
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

    def _clear_query_tab(self) -> None:
        for i in range(1, self.query_tab_count + 1):
            editor = self.query_one(f"#query-editor-{i}", TextArea)
            table = self.query_one(f"#query-table-{i}", DataTable)
            editor.text = ""
            table.clear(columns=True)

    def _get_active_query_widgets(self) -> tuple[TextArea, DataTable]:
        tabs = self.query_one("#query-tabs", TabbedContent)
        active = tabs.active or "query-pane-1"
        suffix = active.replace("query-pane-", "")
        editor = self.query_one(f"#query-editor-{suffix}", TextArea)
        table = self.query_one(f"#query-table-{suffix}", DataTable)
        return editor, table

    def _set_data_sql_text(self, sql_text: str | None) -> None:
        sql_view = self.query_one("#data-sql", TextArea)
        if sql_text:
            sql_view.text = sql_text
            sql_view.display = True
        else:
            sql_view.text = ""
            sql_view.display = False

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
        if self.current_table_name:
            self._clear_data_tab()
            self._load_table_preview(self.current_table_name)

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
        lines.append("-- SQLite schema export")
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


def main() -> None:
    SQLiteTUI().run()
