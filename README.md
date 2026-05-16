# DDBB Manager TUI (Textual python library)

Terminal UI app to inspect and manage SQLite, DuckDB, MySQL, and PostgreSQL databases from the terminal.

## Supported Engines

- SQLite
- DuckDB
- MySQL
- PostgreSQL

Select the engine from the top bar before opening a connection.

## Features

### Connection and Session
- Open database files/URIs from path input.
- File picker with directory navigation (`Parent`, select file).
- Engine-specific file filters:
  - SQLite: `.db`, `.db3`, `.sqlite`, `.sqlite3`
  - DuckDB: `.duckdb`, `.ddb`, `.db`
  - MySQL/PostgreSQL: use URI (no file picker)
- MySQL connection URI format:
  - `mysql://user:password@host:3306/database`
- PostgreSQL connection URI format:
  - `postgresql://user:password@host:5432/database`
- Save named connections with engine type.
- Auto-reopen last used connection on startup:
  - SQLite/DuckDB: if file still exists
  - MySQL/PostgreSQL: reconnect using saved URI

### Connection Management (Left Panel)
- Grouped connections tree:
  - `Favorites`
  - `Tags`
  - `Others`
- Connection actions:
  - `Pin` / unpin favorite
  - `Tag` (comma-separated tags)
  - `Ren` rename
  - `Del` delete (with confirmation)
  - `Test` connection
- Double-click a saved connection to open it.

### Schema Explorer
- Browse tables, views, indexes, triggers (when available in selected engine).
- Expand tables/views to see columns and column types.
- Table row count shown in schema label.
- Color-coded object type labels.
- MySQL index nodes are identified as `table.index` to avoid name collisions.

### Database Info Panel
- Database path, size, table/view counters, modified timestamp.
- Selected object info.
- Vertical scrolling for long content.

### Data Tab
- Table preview with pagination:
  - configurable fetch size input
  - previous/next page buttons
- Object detail view for views/indexes/triggers.
- Full SQL text area for long object definitions.
- Data editing:
  - insert row
  - edit selected cell
  - delete selected row (confirmation)
- Transaction controls:
  - `Tx+` begin
  - `Tx=` commit
  - `Tx-` rollback

### Query Tab
- Multiple query tabs (`Q1`, `Q2`, ...).
- Query execution with result pagination (`Run`, `Prev`, `Next`).
- Query load/save using file navigator modals.
- Export result button with export wizard.

### Explain Tab
- `Explain` and `Analyze` actions from Query controls.
- Engine-aware explain behavior:
  - SQLite: `EXPLAIN QUERY PLAN` / `EXPLAIN`
  - DuckDB: `EXPLAIN` / `EXPLAIN ANALYZE`
  - MySQL: `EXPLAIN` / `EXPLAIN ANALYZE` (server-version dependent)
  - PostgreSQL: `EXPLAIN` / `EXPLAIN ANALYZE`
- Formatted explain output plus full raw output panel.
- Explain panel auto-clears on context/query changes.

### DDL Tab
- DDL editor for selected schema object.
- `Apply DDL` executes editor SQL.
- `Save DDL` saves editor content to `.sql`.
- SQLite helper behavior:
  - when editing table CREATE DDL, missing columns can be applied via `ALTER TABLE ... ADD COLUMN`.

### Import Wizard
- Import from CSV or Parquet.
- Wizard includes:
  - source preview
  - target table
  - column mapping JSON
  - type overrides JSON
- Existing table: confirmation then append.
- Missing table: auto-create then load.

### Export Tools
- Export DB report to Markdown (`.md`).
- Export DB schema DDL to SQL (`.sql`).
- Query result export wizard:
  - CSV options: delimiter, quote char, header on/off
  - Parquet options: compression

### Header / UI
- Header title: `DDBB Manager`.
- Right-aligned date-time display (`dd/mm/yyyy HH:MM:SS`).
- Help modal (`Ctrl+H`) that renders `README.md` with markdown formatting.

## Requirements

- Python 3.8+
- Dependencies include:
  - `textual`
  - `duckdb`
  - `mysql-connector-python`
  - `psycopg[binary]`

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m sqlite_tui
```

## Keyboard Shortcuts

- `Ctrl+R`: Run query (active query tab)
- `Ctrl+L`: Load query file
- `Ctrl+S`: Save query file
- `Ctrl+T`: New query tab
- `Ctrl+I`: Import file (CSV/Parquet wizard)
- `Ctrl+M`: Export DB report to Markdown
- `Ctrl+D`: Export DB schema to SQL
- `Ctrl+H`: Open Help modal

## Quick Usage

1. Choose engine type (`SQLite`, `DuckDB`, `MySQL`, or `PostgreSQL`).
2. Set DB path/URI and click `Open DB`.
   - For SQLite/DuckDB you can use `Browse`.
   - For MySQL/PostgreSQL, paste URI directly.
3. Optionally save connection with `Register`.
4. Explore schema and selected object details in `Data` and `DDL`.
5. Use `Query` tabs for SQL execution, explain/analyze, and result export.
