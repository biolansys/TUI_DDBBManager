from __future__ import annotations

import json
from pathlib import Path


class ConnectionStore:
    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or (Path.home() / ".sqlite_tui_connections.json")

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
            if name and path:
                cleaned.append({"name": name, "path": path})
        return cleaned

    def save(self, connections: list[dict[str, str]]) -> None:
        self.store_path.write_text(
            json.dumps(connections, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
