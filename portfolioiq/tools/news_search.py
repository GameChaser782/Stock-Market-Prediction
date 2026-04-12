from __future__ import annotations

import os

from .registry import ToolRegistry, tool


@tool
def news_search(query: str, max_results: int = 5) -> str:
    """Search for recent financial news. Use for stock-specific news, earnings, macro events, sector trends.

    Args:
        query: Search query (e.g. "Apple earnings Q1 2025", "US China trade war tech stocks")
        max_results: Number of results to return (default 5)
    """
    # Try Tavily first (best quality)
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_key)
            results = client.search(query, max_results=max_results, search_depth="advanced")
            lines = [f"=== News: {query} ==="]
            for r in results.get("results", []):
                lines.append(f"\n• {r.get('title', 'No title')}")
                lines.append(f"  {r.get('url', '')}")
                content = r.get("content", "")
                if content:
                    lines.append(f"  {content[:300]}...")
            return "\n".join(lines)
        except Exception:
            pass

    # Fallback: DuckDuckGo
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        ddg = DuckDuckGoSearchRun()
        result = ddg.run(f"{query} site:reuters.com OR site:bloomberg.com OR site:cnbc.com OR site:economictimes.com")
        return f"=== News: {query} ===\n{result}"
    except Exception as e:
        return f"News search unavailable: {e}. Set TAVILY_API_KEY for better results."


ToolRegistry.register(news_search)
