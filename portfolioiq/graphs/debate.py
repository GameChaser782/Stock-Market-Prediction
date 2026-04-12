"""
Bull vs Bear debate graph.

Flow:
  gather_data → bull_round → bear_round → [loop if rounds < max] → moderator → END

Each debater sees the opponent's previous arguments and must:
  1. Make a new argument backed by real data/news
  2. Directly rebut the opponent's strongest point
"""
from __future__ import annotations

import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from ..config import AgentConfig, load_config
from ..llm import create_llm
from ..state import DebateState
from ..data.provider import get_provider

_BULL_PERSONA = """\
You are a BULL analyst arguing for buying {ticker}.
Your job: make the strongest possible BULLISH case using REAL data and evidence.

Rules:
- Cite specific metrics (P/E, revenue growth %, margins, cash flow)
- Reference specific recent news/events that support your case
- Directly address and rebut the bear's strongest argument if one was made
- Structure your argument: 1) Main thesis, 2) Data evidence (3 specific points), 3) Rebuttal (if applicable)
- Be confident but honest — acknowledge if a bear point is partially valid, then explain why it doesn't outweigh the upside
- Max 300 words. Dense, specific, factual.
"""

_BEAR_PERSONA = """\
You are a BEAR analyst arguing for selling/avoiding {ticker}.
Your job: make the strongest possible BEARISH case using REAL data and evidence.

Rules:
- Cite specific risks (overvaluation metrics, debt levels, competition, macro headwinds)
- Reference specific recent news/events that support your case
- Directly address and rebut the bull's latest argument
- Structure your argument: 1) Main concern, 2) Risk evidence (3 specific points), 3) Rebuttal of bull's case
- Be precise — use actual numbers and percentages, not vague language
- Max 300 words. Dense, specific, factual.
"""

_MODERATOR_PERSONA = """\
You are an impartial debate moderator and financial analyst.

You have just watched a {rounds}-round bull vs bear debate on {ticker}.
Evaluate both sides objectively and deliver your verdict.

Your output MUST be valid JSON in this exact format:
{{
  "bull_summary": "<2-3 sentence summary of the bull's strongest arguments>",
  "bear_summary": "<2-3 sentence summary of the bear's strongest arguments>",
  "stronger_case": "bull" | "bear" | "neutral",
  "verdict": "<one of: Strong Buy, Buy, Hold, Sell, Strong Sell>",
  "confidence": <integer 0-100>,
  "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"],
  "recommendation": "<1-2 sentence actionable recommendation>",
  "disclaimer": "This is AI-generated analysis for informational purposes only. Not financial advice."
}}

Score argument QUALITY (data specificity, logical coherence, rebuttal effectiveness), not just which side you personally agree with.
"""


def build_debate_graph(config: AgentConfig | None = None):
    """Build the bull vs bear debate graph."""
    if config is None:
        config = load_config("supervisor")

    llm = create_llm(config)
    provider = get_provider()

    # ── Node: gather_data ─────────────────────────────────────────────────────
    def gather_data(state: DebateState) -> dict:
        ticker = state["stock_ticker"].upper().strip()
        quote = provider.get_quote(ticker)
        fundamentals = provider.get_fundamentals(ticker)
        earnings = provider.get_earnings(ticker)
        news = provider.get_news(ticker, days=14)

        stock_data = {
            "ticker": ticker,
            "quote": quote,
            "fundamentals": fundamentals,
            "earnings": earnings,
            "news": [{"headline": n["headline"], "date": n["datetime"]} for n in news[:5]],
        }

        # Format data as a briefing both agents can reference
        lines = [f"=== Stock Briefing: {ticker} ==="]
        if quote:
            lines.append(f"Price: {quote.get('price', 'N/A')}  Change: {quote.get('change_pct', 0):+.2f}%")
        if fundamentals:
            f = fundamentals
            lines.append(f"P/E: {f.get('pe_ttm', 'N/A')}  Revenue Growth: {f.get('revenue_growth_1y', 'N/A')}")
            lines.append(f"Net Margin: {f.get('net_margin', 'N/A')}  Debt/Equity: {f.get('debt_equity', 'N/A')}")
            lines.append(f"Beta: {f.get('beta', 'N/A')}")
        if earnings:
            lines.append("\nRecent Earnings:")
            for e in earnings:
                lines.append(f"  {e.get('period','?')}: Est {e.get('eps_estimate','?')} Act {e.get('eps_actual','?')} ({e.get('surprise_pct', 0):+.1f}%)")
        if news:
            lines.append("\nRecent Headlines:")
            for n in news[:4]:
                lines.append(f"  [{n['datetime']}] {n['headline']}")

        stock_data["briefing"] = "\n".join(lines)

        return {
            "stock_data": stock_data,
            "bull_arguments": [],
            "bear_arguments": [],
            "current_round": 0,
        }

    # ── Node: bull_round ──────────────────────────────────────────────────────
    def bull_round(state: DebateState) -> dict:
        ticker = state["stock_ticker"]
        round_num = state["current_round"] + 1
        briefing = state["stock_data"].get("briefing", "")
        bear_args = state.get("bear_arguments", [])

        context = f"{briefing}\n\nRound {round_num} of {state['max_rounds']}."
        if bear_args:
            context += f"\n\nBear's last argument:\n{bear_args[-1]}"

        persona = _BULL_PERSONA.format(ticker=ticker)
        response = llm.invoke([
            SystemMessage(content=persona),
            HumanMessage(content=context),
        ])

        arg = response.content if isinstance(response.content, str) else str(response.content)
        return {
            "bull_arguments": state["bull_arguments"] + [arg],
            "current_round": round_num,
        }

    # ── Node: bear_round ──────────────────────────────────────────────────────
    def bear_round(state: DebateState) -> dict:
        ticker = state["stock_ticker"]
        round_num = state["current_round"]
        briefing = state["stock_data"].get("briefing", "")
        bull_args = state.get("bull_arguments", [])

        context = f"{briefing}\n\nRound {round_num} of {state['max_rounds']}."
        if bull_args:
            context += f"\n\nBull's latest argument:\n{bull_args[-1]}"

        persona = _BEAR_PERSONA.format(ticker=ticker)
        response = llm.invoke([
            SystemMessage(content=persona),
            HumanMessage(content=context),
        ])

        arg = response.content if isinstance(response.content, str) else str(response.content)
        return {"bear_arguments": state["bear_arguments"] + [arg]}

    # ── Node: moderator ───────────────────────────────────────────────────────
    def moderator_node(state: DebateState) -> dict:
        ticker = state["stock_ticker"]
        rounds = state["current_round"]

        transcript = ""
        for i, (bull, bear) in enumerate(zip(state["bull_arguments"], state["bear_arguments"]), 1):
            transcript += f"\n--- Round {i} ---\nBULL:\n{bull}\n\nBEAR:\n{bear}\n"

        persona = _MODERATOR_PERSONA.format(ticker=ticker, rounds=rounds)
        response = llm.invoke([
            SystemMessage(content=persona),
            HumanMessage(content=f"Debate transcript:\n{transcript}"),
        ])

        raw = response.content if isinstance(response.content, str) else str(response.content)

        # Parse JSON from response
        try:
            # Try to extract JSON block
            import re
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                verdict_data = json.loads(m.group())
                return {
                    "verdict": json.dumps(verdict_data),
                    "confidence_score": float(verdict_data.get("confidence", 50)),
                }
        except Exception:
            pass

        return {"verdict": raw, "confidence_score": 50.0}

    # ── Conditional: loop or finish ───────────────────────────────────────────
    def check_rounds(state: DebateState) -> Literal["bull_round", "moderator"]:
        if state["current_round"] < state["max_rounds"]:
            return "bull_round"
        return "moderator"

    # ── Build graph ───────────────────────────────────────────────────────────
    builder = StateGraph(DebateState)
    builder.add_node("gather_data", gather_data)
    builder.add_node("bull_round", bull_round)
    builder.add_node("bear_round", bear_round)
    builder.add_node("moderator", moderator_node)

    builder.add_edge(START, "gather_data")
    builder.add_edge("gather_data", "bull_round")
    builder.add_edge("bull_round", "bear_round")
    builder.add_conditional_edges("bear_round", check_rounds)
    builder.add_edge("moderator", END)

    return builder.compile()


def run_debate(ticker: str, rounds: int = 3, config: AgentConfig | None = None) -> dict:
    """Run a full debate and return the structured result."""
    graph = build_debate_graph(config)
    result = graph.invoke({
        "messages": [],
        "stock_ticker": ticker.upper(),
        "stock_data": {},
        "bull_arguments": [],
        "bear_arguments": [],
        "current_round": 0,
        "max_rounds": rounds,
        "verdict": "",
        "confidence_score": 0.0,
    })

    verdict_raw = result.get("verdict", "{}")
    try:
        verdict = json.loads(verdict_raw) if isinstance(verdict_raw, str) else verdict_raw
    except Exception:
        verdict = {"raw": verdict_raw}

    return {
        "ticker": ticker.upper(),
        "rounds": rounds,
        "bull_arguments": result.get("bull_arguments", []),
        "bear_arguments": result.get("bear_arguments", []),
        "stock_data": result.get("stock_data", {}),
        "verdict": verdict,
    }
