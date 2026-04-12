from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class SQLiteBackend:
    """Lightweight SQLite storage for long-term memory facts."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON memories(user_id)")
            conn.commit()

    def upsert(self, user_id: str, key: str, value: str, metadata: dict | None = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memories (user_id, key, value, metadata)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, metadata=excluded.metadata
                """,
                (user_id, key, value, json.dumps(metadata or {})),
            )
            conn.commit()

    def fetch_all(self, user_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key, value, metadata, created_at FROM memories WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [{"key": r[0], "value": r[1], "metadata": json.loads(r[2]), "created_at": r[3]} for r in rows]

    def search(self, user_id: str, query: str, k: int = 5) -> list[dict]:
        """Simple keyword search — good enough without embeddings."""
        all_memories = self.fetch_all(user_id)
        query_lower = query.lower()
        scored = []
        for m in all_memories:
            score = sum(
                1 for word in query_lower.split()
                if word in m["key"].lower() or word in m["value"].lower()
            )
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:k]]
