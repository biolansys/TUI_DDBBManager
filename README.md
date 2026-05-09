# SQLite TUI Manager (Textual)

Terminal UI app to inspect and manage SQLite databases, inspired by tools like DBeaver.

## Features

- Open any SQLite file from a path input
- Browse filesystem with a file explorer modal to select DB files
- Register named connections
- Reuse saved connections from a left panel
- Browse tables and views in a schema tree
- Preview table data in a grid
- Basic data editing for tables (insert, update cell, delete row)
- Transaction controls (Begin, Commit, Rollback)
- Run custom SQL in a query editor
- View query results and errors inline

## Requirements

- Python 3.10+

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m sqlite_tui
```

## Quick usage

1. Type a SQLite file path or click `Browse...` to pick one.
2. Optionally type a connection name and press `Register` to persist it.
3. Select a saved connection in the left panel and click `Connect Selected`.
4. Use the schema panel to select a table or view.
5. Go to `Query` tab to run SQL.
