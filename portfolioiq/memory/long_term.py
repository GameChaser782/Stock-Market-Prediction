from __future__ import annotations

import re
from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from .backends.sqlite import SQLiteBackend

_EXTRACTION_PROMPT = """\
You are a memory extraction assistant. Given a conversation, extract factual information about the user worth remembering for future sessions.

Rules:
- Extract facts about the user's portfolio, preferences, financial goals, or ongoing research
- Each fact should be a concise key-value pair
- Only extract things explicitly stated, not inferred
- Output each fact as: KEY: value
- If nothing is worth remembering, output: NONE

Example output:
portfolio_stocks: AAPL, MSFT, RELIANCE.NS
risk_tolerance: moderate
investment_horizon: long-term
interested_in: emerging markets, tech sector
"""


class LongTermMemory(ABC):
    @abstractmethod
    def store(self, user_id: str, key: str, value: str) -> None: ...

    @abstractmethod
    def recall(self, user_id: str, query: str, k: int = 5) -> list[dict]: ...

    @abstractmethod
    def extract_and_store(self, user_id: str, conversation_text: str, llm: BaseChatModel) -> None: ...


class SQLiteLongTermMemory(LongTermMemory):
    """Zero-config long-term memory backed by SQLite."""

    def __init__(self, db_path: str = ".portfolioiq/memory.db") -> None:
        self._backend = SQLiteBackend(db_path)

    def store(self, user_id: str, key: str, value: str) -> None:
        self._backend.upsert(user_id, key, value)

    def recall(self, user_id: str, query: str, k: int = 5) -> list[dict]:
        return self._backend.search(user_id, query, k)

    def fetch_all(self, user_id: str) -> list[dict]:
        return self._backend.fetch_all(user_id)

    def extract_and_store(self, user_id: str, conversation_text: str, llm: BaseChatModel) -> None:
        """Ask the LLM to extract memorable facts from the conversation."""
        try:
            response = llm.invoke([
                SystemMessage(content=_EXTRACTION_PROMPT),
                HumanMessage(content=f"Conversation:\n{conversation_text}"),
            ])
            text = response.content.strip()
            if text == "NONE" or not text:
                return
            for line in text.splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().lower().replace(" ", "_")
                    key = re.sub(r"[^a-z0-9_]", "", key)
                    value = value.strip()
                    if key and value:
                        self._backend.upsert(user_id, key, value)
        except Exception:
            pass  # Memory extraction is best-effort; never crash the agent
