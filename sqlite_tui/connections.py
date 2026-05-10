from __future__ import annotations

import json
from pathlib import Path


class ConnectionStore:
    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or (Path.home() / ".sqlite_tui_connections.json")
        self.state_path = Path.home() / ".sqlite_tui_state.json"

    def load(self) -> list[dict[str, str]]:
        if not self.store_path.exists():
            return []
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        cleaned: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            path = str(item.get("path", "")).strip()
            conn_type = str(item.get("type", "")).strip().lower()
            if not conn_type:
                conn_type = self._infer_type_from_path(path)
            if conn_type not in {"sqlite", "duckdb"}:
                conn_type = "sqlite"
            if name and path:
                cleaned.append({"name": name, "path": path, "type": conn_type})
        return cleaned

    def save(self, connections: list[dict[str, str]]) -> None:
        self.store_path.write_text(
            json.dumps(connections, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def load_last_used(self) -> dict[str, str] | None:
        if not self.state_path.exists():
            return None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        last = data.get("last_used")
        if not isinstance(last, dict):
            return None
        name = str(last.get("name", "")).strip()
        path = str(last.get("path", "")).strip()
        conn_type = str(last.get("type", "")).strip().lower()
        if not path or conn_type not in {"sqlite", "duckdb"}:
            return None
        out = {"path": path, "type": conn_type}
        if name:
            out["name"] = name
        return out

    def save_last_used(self, name: str, path: str, conn_type: str) -> None:
        payload = {
            "last_used": {
                "name": name,
                "path": path,
                "type": conn_type,
            }
        }
        self.state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    @staticmethod
    def _infer_type_from_path(path: str) -> str:
        suffix = Path(path).suffix.lower()
        if suffix in {".duckdb", ".ddb"}:
            return "duckdb"
        return "sqlite"
