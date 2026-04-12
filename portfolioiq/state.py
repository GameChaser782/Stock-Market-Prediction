from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State for the main supervisor/chat agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    memory_context: str
    user_profile: dict


class DebateState(TypedDict):
    """State for the bull/bear debate graph."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    stock_ticker: str
    stock_data: dict
    bull_arguments: list
    bear_arguments: list
    current_round: int
    max_rounds: int
    verdict: str
    confidence_score: float
