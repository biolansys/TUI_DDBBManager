# SQLite TUI Manager (Textual)

Terminal UI app to inspect and manage SQLite databases, inspired by tools like DBeaver.

## Features

- Open SQLite files (`.db`, `.db3`, `.sqlite`, `.sqlite3`)
- File picker modal with directory navigation (`Parent`, select file)
- Persistent named connections (saved and reused from the left panel)
- Double-click a saved connection to open it
- Schema browser with:
  - Tables, views, indexes, triggers
  - Table/view columns in collapsible subtrees
  - Row count shown next to table names
  - Color-coded object type labels
- Database info panel with file metadata and selected object info
- Data tab:
  - Table preview grid
  - View/index/trigger metadata and SQL definition
  - Full SQL viewer for long definitions
- Table data editing:
  - Insert row (JSON input)
  - Edit selected cell
  - Delete selected row (with confirmation)
  - Transaction controls (`Tx+`, `Tx=`, `Tx-`)
- Query workspace:
  - Multiple query tabs (`Q1`, `Q2`, ...)
  - Run SQL and view tab-specific results
  - Load/save query files with file navigator modals
  - Export active query result via popup menu to CSV or Parquet
- Export tools:
  - Database report to Markdown (`.md`)
  - Full schema DDL export to SQL (`.sql`)

## Requirements

- Python 3.8+

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
- `Ctrl+E`: Export active query result (CSV/Parquet popup)
- `Ctrl+M`: Export DB report to Markdown
- `Ctrl+D`: Export DB schema to SQL

## Quick Usage

1. Set DB path and click `Op` (or `Br` to browse).
2. Optionally save it as a named connection with `Reg`.
3. Explore schema on the left; select objects to inspect details in `Data`.
4. Use `Query` tab(s) to run SQL.
5. Use footer shortcuts for query load/save/export and DB exports.
