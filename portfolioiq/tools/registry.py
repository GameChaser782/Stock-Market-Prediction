from __future__ import annotations

from langchain_core.tools import BaseTool, tool as langchain_tool

# Re-export for convenience
tool = langchain_tool


class ToolRegistry:
    """Central registry for agent tools."""

    _tools: dict[str, BaseTool] = {}

    @classmethod
    def register(cls, t: BaseTool) -> None:
        cls._tools[t.name] = t

    @classmethod
    def register_function(cls, func) -> BaseTool:
        """Decorate and register a plain function as a tool."""
        t = langchain_tool(func)
        cls.register(t)
        return t

    @classmethod
    def get(cls, names: list[str]) -> list[BaseTool]:
        """Fetch tools by name; skip unknowns with a warning."""
        result = []
        for name in names:
            if name in cls._tools:
                result.append(cls._tools[name])
            else:
                print(f"[portfolioiq] Warning: tool '{name}' not found in registry")
        return result

    @classmethod
    def all(cls) -> list[BaseTool]:
        return list(cls._tools.values())

    @classmethod
    def load_builtins(cls) -> None:
        """Auto-load all built-in financial tools."""
        from . import financial  # noqa: F401 — side-effect import registers tools
