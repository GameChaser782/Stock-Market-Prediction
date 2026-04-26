"""
Local session store for PortfolioIQ.

Sessions persist portfolio + settings to .portfolioiq/sessions.db (gitignored).
Each session has a unique ID, a name, and arbitrary JSON data.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


class SessionStore:
    def __init__(self, db_path: str = ".portfolioiq/sessions.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    data TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, name: str, data: dict | None = None) -> dict:
        now = datetime.now().isoformat()
        sid = str(uuid.uuid4())[:8]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (id, name, data, created_at, updated_at) VALUES (?,?,?,?,?)",
                (sid, name, json.dumps(data or {}), now, now),
            )
            conn.commit()
        return self.get(sid)

    def get(self, session_id: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, name, data, created_at, updated_at FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "data": json.loads(row[2]),
                "created_at": row[3], "updated_at": row[4]}

    def list_all(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, name, data, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {"id": r[0], "name": r[1], "data": json.loads(r[2]),
             "created_at": r[3], "updated_at": r[4]}
            for r in rows
        ]

    def update(self, session_id: str, name: str | None = None, data: dict | None = None) -> dict | None:
        session = self.get(session_id)
        if not session:
            return None
        new_name = name if name is not None else session["name"]
        new_data = data if data is not None else session["data"]
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET name=?, data=?, updated_at=? WHERE id=?",
                (new_name, json.dumps(new_data), now, session_id),
            )
            conn.commit()
        return self.get(session_id)

    def delete(self, session_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            conn.commit()
        return cur.rowcount > 0


from functools import lru_cache

@lru_cache(maxsize=1)
def get_store() -> SessionStore:
    import os
    db_path = os.path.join(os.getenv("AGENT_MEMORY_DIR", ".portfolioiq"), "sessions.db")
    return SessionStore(db_path=db_path)
