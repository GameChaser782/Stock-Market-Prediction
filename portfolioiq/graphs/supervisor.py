from __future__ import annotations

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from ..config import AgentConfig
from ..llm import create_llm
from ..memory.long_term import SQLiteLongTermMemory
from ..state import AgentState


def build_supervisor_graph(config: AgentConfig, extra_tools: list[BaseTool] | None = None):
    """Build the main supervisor agent graph with financial tools."""
    from ..tools.registry import ToolRegistry

    ToolRegistry.load_builtins()
    tools = ToolRegistry.get(config.tools)
    if extra_tools:
        tools.extend(extra_tools)

    llm = create_llm(config)
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    # Long-term memory
    long_mem: SQLiteLongTermMemory | None = None
    if config.long_term_memory:
        import os
        db_path = os.path.join(config.memory_dir, "memory.db")
        long_mem = SQLiteLongTermMemory(db_path=db_path)

    # ── Node: recall_memory ───────────────────────────────────────────────────
    def recall_memory(state: AgentState) -> dict:
        if long_mem is None:
            return {"memory_context": ""}
        messages = state["messages"]
        user_id = state.get("user_profile", {}).get("user_id", "default")
        query = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                query = str(m.content)
                break
        if not query:
            return {"memory_context": ""}
        memories = long_mem.recall(user_id, query)
        if not memories:
            return {"memory_context": ""}
        lines = [f"- {m['key']}: {m['value']}" for m in memories]
        ctx = "What I remember about this user:\n" + "\n".join(lines)
        return {"memory_context": ctx}

    # ── Node: agent ───────────────────────────────────────────────────────────
    def agent_node(state: AgentState) -> dict:
        system_parts = [config.persona_text]
        if state.get("memory_context"):
            system_parts.append("\n\n" + state["memory_context"])
        system_msg = SystemMessage(content="\n".join(system_parts))
        response = llm_with_tools.invoke([system_msg] + list(state["messages"]))
        return {"messages": [response]}

    # ── Node: extract_memory ─────────────────────────────────────────────────
    def extract_memory(state: AgentState) -> dict:
        if long_mem is None:
            return {}
        user_id = state.get("user_profile", {}).get("user_id", "default")
        messages = state["messages"]
        lines = []
        for m in messages[-6:]:
            if isinstance(m, HumanMessage):
                lines.append(f"User: {m.content}")
            elif isinstance(m, AIMessage) and m.content:
                lines.append(f"Assistant: {m.content}")
        if lines:
            long_mem.extract_and_store(user_id, "\n".join(lines), create_llm(config))
        return {}

    # ── Conditional edge ──────────────────────────────────────────────────────
    def should_continue(state: AgentState) -> Literal["tools", "extract_memory"]:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "extract_memory"

    # ── Build graph ───────────────────────────────────────────────────────────
    builder = StateGraph(AgentState)

    builder.add_node("recall_memory", recall_memory)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("extract_memory", extract_memory)

    builder.add_edge(START, "recall_memory")
    builder.add_edge("recall_memory", "agent")
    builder.add_conditional_edges("agent", should_continue)
    builder.add_edge("tools", "agent")
    builder.add_edge("extract_memory", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
