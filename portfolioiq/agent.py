from __future__ import annotations

import uuid
from typing import AsyncIterator, Callable

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool

from .config import AgentConfig, load_config
from .graphs.supervisor import build_supervisor_graph


class PortfolioAgent:
    """Main entry point for PortfolioIQ."""

    def __init__(
        self,
        agent_name: str = "supervisor",
        config_dir: str = "agents",
        config: AgentConfig | None = None,
    ) -> None:
        self.config = config or load_config(agent_name, config_dir)
        self._extra_tools: list[BaseTool] = []
        self._graph = None  # built lazily on first use

    def _get_graph(self):
        if self._graph is None:
            self._graph = build_supervisor_graph(self.config, self._extra_tools)
        return self._graph

    def tool(self, func: Callable) -> Callable:
        """Decorator to register a custom tool. Call before first chat()."""
        from langchain_core.tools import tool as lc_tool
        t = lc_tool(func)
        self._extra_tools.append(t)
        self._graph = None  # force rebuild
        return func

    def add_tool(self, t: BaseTool) -> None:
        self._extra_tools.append(t)
        self._graph = None

    def chat(self, message: str, thread_id: str = "default", user_id: str = "default") -> str:
        """Send a message and return the full response string."""
        graph = self._get_graph()
        result = graph.invoke(
            {
                "messages": [HumanMessage(content=message)],
                "memory_context": "",
                "user_profile": {"user_id": user_id},
            },
            config={"configurable": {"thread_id": thread_id}},
        )
        content = result["messages"][-1].content
        if isinstance(content, list):
            return "".join(
                block["text"] for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        return content

    async def stream(
        self,
        message: str,
        thread_id: str = "default",
        user_id: str = "default",
    ) -> AsyncIterator[str]:
        """
        Stream the final response tokens.

        The supervisor graph may call tools before producing a final answer.
        We buffer each LLM invocation and only yield its tokens if that
        invocation ends without tool calls (i.e. it IS the final response).
        This prevents garbled output from intermediate tool-calling text.
        """
        graph = self._get_graph()

        # run_id → {"tokens": [str, ...], "has_tool_call": bool}
        runs: dict[str, dict] = {}

        async for event in graph.astream_events(
            {
                "messages": [HumanMessage(content=message)],
                "memory_context": "",
                "user_profile": {"user_id": user_id},
            },
            config={"configurable": {"thread_id": thread_id}},
            version="v2",
        ):
            kind = event["event"]
            node = event["metadata"].get("langgraph_node", "")
            run_id = event.get("run_id", "")

            if kind == "on_chat_model_start" and node == "agent":
                runs[run_id] = {"tokens": [], "has_tool_call": False}

            elif kind == "on_chat_model_stream" and node == "agent":
                chunk = event["data"]["chunk"]
                if chunk.tool_call_chunks:
                    if run_id in runs:
                        runs[run_id]["has_tool_call"] = True
                elif chunk.content and run_id in runs and not runs[run_id]["has_tool_call"]:
                    content = chunk.content
                    if isinstance(content, list):
                        text = "".join(
                            b["text"] for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                    else:
                        text = str(content)
                    if text:
                        runs[run_id]["tokens"].append(text)

            elif kind == "on_chat_model_end" and node == "agent":
                if run_id in runs and not runs[run_id]["has_tool_call"]:
                    for token in runs[run_id]["tokens"]:
                        yield token
                runs.pop(run_id, None)

    def serve(self, host: str | None = None, port: int | None = None) -> None:
        """Start the FastAPI server."""
        from .server import run_server
        run_server(
            self,
            host=host or self.config.server_host,
            port=port or self.config.server_port,
        )

    def new_thread(self) -> str:
        return str(uuid.uuid4())
