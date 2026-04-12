"""
News impact analysis graph.
Fetches recent news for a ticker and uses an LLM to analyze global macro impact.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from ..config import AgentConfig, load_config
from ..llm import create_llm
from ..data.provider import get_provider
from ..tools.news_search import news_search


class NewsState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    ticker: str
    company_news: list
    macro_news: str
    analysis: str


_NEWS_ANALYST_PERSONA = """\
You are a macro-aware financial news analyst. Your specialty is connecting global events to individual stock movements.

When analyzing news impact:
1. Identify the top 3 most impactful recent developments (company-specific AND macro)
2. Explain HOW each development affects this specific stock (supply chain? demand? regulation? sentiment?)
3. Assign a short-term impact score: Strongly Negative / Negative / Neutral / Positive / Strongly Positive
4. Identify the key macro risks (geopolitical, currency, interest rate, sector-wide) that investors often overlook
5. Give a "news sentiment" summary: what's the overall narrative in the market right now?

Be specific — mention actual events, not generic risks. Connect dots between global news and stock fundamentals.
"""


def build_news_graph(config: AgentConfig | None = None):
    if config is None:
        config = load_config("supervisor")

    llm = create_llm(config)
    provider = get_provider()

    def fetch_news(state: NewsState) -> dict:
        ticker = state["ticker"].upper()
        company_news = provider.get_news(ticker, days=14)
        return {"company_news": company_news}

    def analyze_impact(state: NewsState) -> dict:
        ticker = state["ticker"]
        news = state.get("company_news", [])
        macro_query = state.get("macro_news", "")

        news_text = "\n".join(
            f"[{n.get('datetime','?')}] {n.get('headline','')}" for n in news[:8]
        ) or "No recent company news found."

        # Try to get macro context via web search
        macro_context = ""
        try:
            macro_result = news_search.invoke({"query": f"global macro news affecting {ticker} sector 2025", "max_results": 3})
            macro_context = f"\n\nMacro/Global Context:\n{macro_result}"
        except Exception:
            pass

        prompt = (
            f"Analyze the news impact on {ticker}.\n\n"
            f"Recent Company News:\n{news_text}"
            f"{macro_context}"
        )

        response = llm.invoke([
            SystemMessage(content=_NEWS_ANALYST_PERSONA),
            HumanMessage(content=prompt),
        ])
        analysis = response.content if isinstance(response.content, str) else str(response.content)
        return {"analysis": analysis}

    builder = StateGraph(NewsState)
    builder.add_node("fetch_news", fetch_news)
    builder.add_node("analyze_impact", analyze_impact)

    builder.add_edge(START, "fetch_news")
    builder.add_edge("fetch_news", "analyze_impact")
    builder.add_edge("analyze_impact", END)

    return builder.compile()


def run_news_analysis(ticker: str, config: AgentConfig | None = None) -> dict:
    graph = build_news_graph(config)
    result = graph.invoke({
        "messages": [],
        "ticker": ticker.upper(),
        "company_news": [],
        "macro_news": "",
        "analysis": "",
    })
    return {
        "ticker": ticker.upper(),
        "news": result.get("company_news", []),
        "analysis": result.get("analysis", ""),
    }
