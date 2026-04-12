"""
Full stock analysis pipeline: Research → Technical → Fundamental → Risk → Recommendation.
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


class AnalysisState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    ticker: str
    raw_data: dict
    technical_analysis: str
    fundamental_analysis: str
    final_report: str


_ANALYST_PERSONA = """\
You are a senior equity analyst with 20 years of experience across US and emerging markets.

When given stock data, produce a structured analysis covering:

1. **Valuation Assessment** — Is the stock cheap, fair, or expensive vs peers and history?
2. **Business Quality** — Revenue growth trajectory, margin trends, competitive moat
3. **Technical Setup** — What do RSI, MACD, moving averages suggest about near-term momentum?
4. **Risk Factors** — Top 3 risks that could cause the thesis to fail
5. **Score** — Overall investment quality score 1-100, where:
   - 80-100: Strong buy — exceptional quality and value
   - 60-79: Buy — solid fundamentals, reasonable price
   - 40-59: Hold — fair value, watch for catalyst
   - 20-39: Sell — overvalued or deteriorating fundamentals
   - 0-19: Strong sell — avoid

Format your output as:
**Valuation:** ...
**Business Quality:** ...
**Technical Setup:** ...
**Risks:** ...
**Score: X/100 — [verdict]**
**Summary:** One paragraph for a busy investor.
"""


def build_analysis_graph(config: AgentConfig | None = None):
    if config is None:
        config = load_config("supervisor")

    llm = create_llm(config)
    provider = get_provider()

    def gather_data(state: AnalysisState) -> dict:
        ticker = state["ticker"].upper()
        quote = provider.get_quote(ticker)
        fundamentals = provider.get_fundamentals(ticker)
        candles = provider.get_candles(ticker, days=180)
        earnings = provider.get_earnings(ticker)
        news = provider.get_news(ticker, days=7)

        return {
            "raw_data": {
                "quote": quote,
                "fundamentals": fundamentals,
                "candles": candles[-30:] if candles else [],  # last 30 days
                "earnings": earnings,
                "news": news[:5],
            }
        }

    def analyze(state: AnalysisState) -> dict:
        ticker = state["ticker"]
        d = state["raw_data"]

        # Build compact data summary for LLM
        q = d.get("quote", {})
        f = d.get("fundamentals", {})
        earnings = d.get("earnings", [])
        news = d.get("news", [])
        candles = d.get("candles", [])

        # Technical indicators (calculated inline)
        tech_summary = ""
        if len(candles) >= 20:
            import pandas as pd
            close = pd.Series([c["close"] for c in candles])
            ma20 = close.rolling(20).mean().iloc[-1]
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, float("inf"))
            rsi = float((100 - 100 / (1 + rs)).iloc[-1])
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd = ema12 - ema26
            sig = macd.ewm(span=9).mean()
            tech_summary = (
                f"MA(20)={ma20:.2f} ({'above' if close.iloc[-1] > ma20 else 'below'}), "
                f"RSI={rsi:.1f}, "
                f"MACD={'bullish' if macd.iloc[-1] > sig.iloc[-1] else 'bearish'}"
            )

        data_text = f"""
Stock: {ticker}
Price: {q.get('price', 'N/A')}  Change: {q.get('change_pct', 0):+.2f}%

Fundamentals:
  P/E: {f.get('pe_ttm', 'N/A')}  Fwd P/E: {f.get('pe_forward', 'N/A')}  P/B: {f.get('pb_ratio', 'N/A')}
  Revenue Growth: {f.get('revenue_growth_1y', 'N/A')}  Net Margin: {f.get('net_margin', 'N/A')}
  ROE: {f.get('roe', 'N/A')}  Debt/Equity: {f.get('debt_equity', 'N/A')}
  Beta: {f.get('beta', 'N/A')}  Free Cash Flow: {f.get('free_cash_flow', 'N/A')}

Technical: {tech_summary or 'Insufficient data'}

Recent Earnings:
{chr(10).join(f"  {e.get('period','?')}: Est={e.get('eps_estimate','?')} Act={e.get('eps_actual','?')} ({e.get('surprise_pct',0):+.1f}%)" for e in earnings)}

Recent News:
{chr(10).join(f"  [{n.get('datetime','?')}] {n.get('headline','')}" for n in news)}
"""

        response = llm.invoke([
            SystemMessage(content=_ANALYST_PERSONA),
            HumanMessage(content=data_text),
        ])
        analysis = response.content if isinstance(response.content, str) else str(response.content)
        return {"final_report": analysis}

    builder = StateGraph(AnalysisState)
    builder.add_node("gather_data", gather_data)
    builder.add_node("analyze", analyze)

    builder.add_edge(START, "gather_data")
    builder.add_edge("gather_data", "analyze")
    builder.add_edge("analyze", END)

    return builder.compile()


def run_analysis(ticker: str, config: AgentConfig | None = None) -> dict:
    graph = build_analysis_graph(config)
    result = graph.invoke({
        "messages": [],
        "ticker": ticker.upper(),
        "raw_data": {},
        "technical_analysis": "",
        "fundamental_analysis": "",
        "final_report": "",
    })
    return {
        "ticker": ticker.upper(),
        "report": result.get("final_report", ""),
        "raw_data": result.get("raw_data", {}),
    }
