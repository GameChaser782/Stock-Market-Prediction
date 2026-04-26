"""
Chat history + debate persistence for PortfolioIQ.

Tables:
  chats    – chat threads within a portfolio session
  messages – per-chat chat log (text + debate_block types)
  debates  – full structured debate results
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path


class ChatStore:
    def __init__(self, db_path: str = ".portfolioiq/chat.db") -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    chat_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
            if "chat_id" not in cols:
                conn.execute("ALTER TABLE messages ADD COLUMN chat_id TEXT")
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_chat
                ON messages(chat_id, created_at)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS debates (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    chat_id TEXT,
                    ticker TEXT NOT NULL,
                    rounds_data TEXT NOT NULL DEFAULT '[]',
                    charts_data TEXT NOT NULL DEFAULT '[]',
                    verdict TEXT NOT NULL DEFAULT '{}',
                    web_searches TEXT NOT NULL DEFAULT '[]',
                    portfolio_recommendation TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            debate_cols = {row[1] for row in conn.execute("PRAGMA table_info(debates)").fetchall()}
            if "chat_id" not in debate_cols:
                conn.execute("ALTER TABLE debates ADD COLUMN chat_id TEXT")
            conn.commit()

    # ── Chats ─────────────────────────────────────────────────────────────────

    def create_chat(self, session_id: str, name: str = "New chat") -> dict:
        now = datetime.now().isoformat()
        cid = str(uuid.uuid4())[:12]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO chats (id,session_id,name,created_at,updated_at) VALUES (?,?,?,?,?)",
                (cid, session_id, name, now, now),
            )
            conn.commit()
        return self.get_chat(cid)

    def get_chat(self, chat_id: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id,session_id,name,created_at,updated_at FROM chats WHERE id=?",
                (chat_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "session_id": row[1],
            "name": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }

    def _ensure_legacy_chat(self, session_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            has_unassigned = conn.execute(
                "SELECT 1 FROM messages WHERE session_id=? AND (chat_id IS NULL OR chat_id='') LIMIT 1",
                (session_id,),
            ).fetchone()
            if not has_unassigned:
                return
            existing = conn.execute(
                "SELECT id FROM chats WHERE session_id=? ORDER BY updated_at ASC LIMIT 1",
                (session_id,),
            ).fetchone()
            if existing:
                chat_id = existing[0]
            else:
                now = datetime.now().isoformat()
                chat_id = str(uuid.uuid4())[:12]
                conn.execute(
                    "INSERT INTO chats (id,session_id,name,created_at,updated_at) VALUES (?,?,?,?,?)",
                    (chat_id, session_id, "Main chat", now, now),
                )
            conn.execute(
                "UPDATE messages SET chat_id=? WHERE session_id=? AND (chat_id IS NULL OR chat_id='')",
                (chat_id, session_id),
            )
            conn.execute(
                "UPDATE debates SET chat_id=? WHERE session_id=? AND (chat_id IS NULL OR chat_id='')",
                (chat_id, session_id),
            )
            conn.execute(
                "UPDATE chats SET updated_at=? WHERE id=?",
                (datetime.now().isoformat(), chat_id),
            )
            conn.commit()

    def list_chats(self, session_id: str) -> list[dict]:
        self._ensure_legacy_chat(session_id)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id,session_id,name,created_at,updated_at FROM chats "
                "WHERE session_id=? ORDER BY updated_at DESC, created_at DESC",
                (session_id,),
            ).fetchall()
            chats = []
            for row in rows:
                count_row = conn.execute(
                    "SELECT COUNT(*) FROM messages WHERE chat_id=?",
                    (row[0],),
                ).fetchone()
                last_row = conn.execute(
                    "SELECT role,content,created_at FROM messages WHERE chat_id=? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (row[0],),
                ).fetchone()
                chats.append({
                    "id": row[0],
                    "session_id": row[1],
                    "name": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                    "message_count": int(count_row[0] if count_row else 0),
                    "last_message": last_row[1] if last_row else "",
                    "last_message_role": last_row[0] if last_row else "",
                    "last_message_at": last_row[2] if last_row else None,
                })
        return chats

    def rename_chat(self, chat_id: str, name: str) -> dict | None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE chats SET name=?, updated_at=? WHERE id=?",
                (name, now, chat_id),
            )
            conn.commit()
        if cur.rowcount <= 0:
            return None
        return self.get_chat(chat_id)

    def delete_chat(self, chat_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            # Delete messages
            conn.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
            # Delete debates
            conn.execute("DELETE FROM debates WHERE chat_id=?", (chat_id,))
            # Delete chat thread
            cur = conn.execute("DELETE FROM chats WHERE id=?", (chat_id,))
            conn.commit()
            return cur.rowcount > 0

    # ── Messages ──────────────────────────────────────────────────────────────

    def add_message(self, session_id: str, chat_id: str, role: str, content: str,
                    metadata: dict | None = None) -> dict:
        now = datetime.now().isoformat()
        mid = str(uuid.uuid4())[:12]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (id,session_id,chat_id,role,content,metadata,created_at) VALUES (?,?,?,?,?,?,?)",
                (mid, session_id, chat_id, role, content, json.dumps(metadata or {}), now),
            )
            conn.execute(
                "UPDATE chats SET updated_at=? WHERE id=?",
                (now, chat_id),
            )
            conn.commit()
        return {"id": mid, "session_id": session_id, "chat_id": chat_id, "role": role,
                "content": content, "metadata": metadata or {}, "created_at": now}

    def get_messages(self, chat_id: str, limit: int = 200) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id,session_id,chat_id,role,content,metadata,created_at FROM messages "
                "WHERE chat_id=? ORDER BY created_at ASC LIMIT ?",
                (chat_id, limit),
            ).fetchall()
        return [{"id": r[0], "session_id": r[1], "chat_id": r[2], "role": r[3],
                 "content": r[4], "metadata": json.loads(r[5]), "created_at": r[6]}
                for r in rows]

    def delete_chat_messages(self, chat_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
            conn.commit()

    def get_session_stats(self, session_id: str) -> dict:
        self._ensure_legacy_chat(session_id)
        with sqlite3.connect(self.db_path) as conn:
            count_row = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id=?",
                (session_id,),
            ).fetchone()
            last_row = conn.execute(
                "SELECT role,content,created_at FROM messages "
                "WHERE session_id=? ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return {
            "message_count": int(count_row[0] if count_row else 0),
            "last_message": last_row[1] if last_row else "",
            "last_message_role": last_row[0] if last_row else "",
            "last_message_at": last_row[2] if last_row else None,
        }

    # ── Debates ───────────────────────────────────────────────────────────────

    def save_debate(self, ticker: str, rounds_data: list, charts_data: list,
                    verdict: dict, web_searches: list,
                    portfolio_recommendation: str | None = None,
                    session_id: str | None = None,
                    chat_id: str | None = None) -> dict:
        now = datetime.now().isoformat()
        did = str(uuid.uuid4())[:12]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO debates (id,session_id,chat_id,ticker,rounds_data,charts_data,"
                "verdict,web_searches,portfolio_recommendation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (did, session_id, chat_id, ticker, json.dumps(rounds_data), json.dumps(charts_data),
                 json.dumps(verdict), json.dumps(web_searches), portfolio_recommendation, now),
            )
            if chat_id:
                conn.execute(
                    "UPDATE chats SET updated_at=? WHERE id=?",
                    (now, chat_id),
                )
            conn.commit()
        return self.get_debate(did)

    def get_debate(self, debate_id: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id,session_id,chat_id,ticker,rounds_data,charts_data,verdict,"
                "web_searches,portfolio_recommendation,created_at FROM debates WHERE id=?",
                (debate_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0], "session_id": row[1], "chat_id": row[2], "ticker": row[3],
            "rounds_data": json.loads(row[4]),
            "charts_data": json.loads(row[5]),
            "verdict": json.loads(row[6]),
            "web_searches": json.loads(row[7]),
            "portfolio_recommendation": row[8],
            "created_at": row[9],
        }

    def list_debates(self, chat_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id,ticker,verdict,created_at FROM debates "
                "WHERE chat_id=? ORDER BY created_at DESC",
                (chat_id,),
            ).fetchall()
        return [{"id": r[0], "ticker": r[1],
                 "verdict": json.loads(r[2]), "created_at": r[3]}
                for r in rows]


@lru_cache(maxsize=1)
def get_chat_store() -> ChatStore:
    import os
    db_path = os.path.join(os.getenv("AGENT_MEMORY_DIR", ".portfolioiq"), "chat.db")
    return ChatStore(db_path=db_path)
