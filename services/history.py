import json
import os
from datetime import datetime


HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "optimization_history.json")


class OptimizationHistory:
    def __init__(self):
        self.filepath = HISTORY_FILE
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.filepath):
            self._write([])

    def _read(self) -> list:
        try:
            with open(self.filepath) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, records: list):
        with open(self.filepath, "w") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def add_entry(self, category: str, resource_id: str, description: str, user: str, savings: str = ""):
        records = self._read()
        records.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "resource_id": resource_id,
            "description": description,
            "user": user,
            "savings": savings,
        })
        self._write(records)

    def get_all(self) -> list:
        records = self._read()
        return list(reversed(records))

    def clear(self):
        self._write([])

    def get_summary(self) -> dict:
        records = self._read()
        total_actions = len(records)
        by_user = {}
        for r in records:
            u = r.get("user", "unknown")
            by_user[u] = by_user.get(u, 0) + 1
        return {
            "total": total_actions,
            "by_user": by_user,
        }
