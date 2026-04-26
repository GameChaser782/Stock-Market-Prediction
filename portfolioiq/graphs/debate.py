"""
Bull vs Bear debate — streaming, conversational, web-grounded.

Flow:
  gather_data → [for each round: bull_round → bear_round] → moderator → charts → END

Streaming yields events: log | bull | bear | chart | verdict | done
"""
from __future__ import annotations

import json
import os
import re
from typing import AsyncGenerator, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from ..config import AgentConfig, load_config
from ..llm import create_llm
from ..state import DebateState
from ..data.provider import get_provider

# ── Personas ──────────────────────────────────────────────────────────────────

_BULL_PERSONA = """\
You are Marcus — a sharp, confident bull trader who's been in the markets for 15 years.
You're debating {ticker} with a skeptical bear. Talk like a real person, not an analyst report.

Rules:
- 2-3 short paragraphs MAX. No bullet points. No headers. Just talk.
- Use actual numbers but weave them into sentences naturally.
- React directly to what the bear just said — call out their weak points.
- Be confident but not arrogant. Admit what's hard to argue.
- Sound like you're in a room with someone, not writing a research note.
- Keep it under 180 words.
"""

_BEAR_PERSONA = """\
You are Priya — a cautious, data-driven bear analyst who's seen too many bubbles.
You're debating {ticker} with an overconfident bull. Push back hard but stay sharp.

Rules:
- 2-3 short paragraphs MAX. No bullet points. No headers. Just talk.
- Use actual numbers but weave them into sentences naturally.
- Directly challenge the bull's last point — don't let them slide on weak logic.
- Be direct and skeptical. You're not here to agree.
- Sound like a conversation, not an earnings call.
- Keep it under 180 words.
"""

_MODERATOR_PERSONA = """\
You are a sharp financial journalist wrapping up a {rounds}-round debate on {ticker}.
You've listened to both sides. Give your honest verdict.

Your output MUST be valid JSON in this exact format:
{{
  "stronger_case": "bull" | "bear" | "neutral",
  "verdict": "Strong Buy" | "Buy" | "Hold" | "Sell" | "Strong Sell",
  "confidence": <integer 0-100>,
  "key_factors": ["<factor 1>", "<factor 2>", "<factor 3>"],
  "recommendation": "<2-3 sentence plain-English takeaway. Sound like a person.>",
  "disclaimer": "AI-generated analysis. Not financial advice."
}}

Score based on who made the better argument, not just your prior view.
"""

_PORTFOLIO_REC_PERSONA = """\
You've just watched a {rounds}-round debate on {ticker}.
The user already holds these stocks: {portfolio}.

In 2-3 sentences, give a direct recommendation: should they add {ticker} to their portfolio or not?
Consider their existing holdings (concentration, sector overlap, risk balance).
Sound like a trusted friend who knows markets — not a lawyer or compliance officer.
"""


# ── Gemini search helper ──────────────────────────────────────────────────────

def _gemini_search_available() -> bool:
    """Check if we can use Gemini with Google Search grounding."""
    return bool(os.getenv("GOOGLE_API_KEY")) and os.getenv("AGENT_PROVIDER", "").lower() == "gemini"


def _gemini_search_call(prompt: str, system: str = "") -> tuple[str, list[str]]:
    """
    Call Gemini with Google Search grounding.
    Returns (response_text, list_of_search_queries_used).
    """
    from google import genai
    from google.genai import types

    api_key = os.getenv("GOOGLE_API_KEY")
    model = os.getenv("AGENT_MODEL", "gemini-2.5-flash")

    client = genai.Client(api_key=api_key)
    tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(
        temperature=0.7,
        tools=[tool],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        system_instruction=system if system else None,
    )

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    resp = client.models.generate_content(model=model, contents=contents, config=config)

    text = ""
    searches_used = []
    for candidate in resp.candidates:
        for part in candidate.content.parts:
            if hasattr(part, "text") and part.text:
                text += part.text
        # Extract search queries used
        if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
            gm = candidate.grounding_metadata
            if hasattr(gm, "search_entry_point") and gm.search_entry_point:
                queries = getattr(gm.search_entry_point, "rendered_content", "")
                if queries:
                    searches_used.append(queries[:100])
            if hasattr(gm, "web_search_queries") and gm.web_search_queries:
                searches_used.extend(gm.web_search_queries[:3])

    return text.strip(), searches_used


# ── Tavily fallback search ────────────────────────────────────────────────────

def _tavily_search(query: str, max_results: int = 3) -> str:
    """Search with Tavily, return formatted results."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results = client.search(query=query, max_results=max_results, search_depth="basic")
        snippets = []
        for r in results.get("results", []):
            snippets.append(f"[{r.get('title','')}] {r.get('content','')[:200]}")
        return "\n".join(snippets)
    except Exception:
        return ""


# ── Streaming debate runner ───────────────────────────────────────────────────

async def stream_debate(
    ticker: str,
    rounds: int = 3,
    config: AgentConfig | None = None,
    session_id: str | None = None,
    chat_id: str | None = None,
    portfolio: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields debate events:
      {"type": "log", "message": "..."}
      {"type": "bull", "round": N, "text": "..."}
      {"type": "bear", "round": N, "text": "..."}
      {"type": "chart", "chart_type": "price"|"fundamentals", "data": [...], "title": "..."}
      {"type": "verdict", "data": {...}}
      {"type": "portfolio_rec", "text": "..."}
      {"type": "done", "debate_id": "..."}
    """
    import asyncio
    from ..chat_store import get_chat_store

    if config is None:
        config = load_config("supervisor")

    ticker = ticker.upper().strip()
    llm = create_llm(config)
    provider = get_provider()
    use_gemini = _gemini_search_available()

    rounds_data = []
    web_searches: list[str] = []
    charts_data = []

    # ── Step 1: Gather data ───────────────────────────────────────────────────
    yield {"type": "log", "message": f"Fetching market data for {ticker}..."}
    await asyncio.sleep(0)

    quote = provider.get_quote(ticker)
    fundamentals = provider.get_fundamentals(ticker)
    earnings = provider.get_earnings(ticker)
    news = provider.get_news(ticker, days=14)
    history = provider.get_candles(ticker, days=365)

    # Build briefing
    lines = [f"=== {ticker} Data Briefing ==="]
    if quote:
        lines.append(f"Price: {quote.get('price','N/A')}  Change today: {quote.get('change_pct',0):+.2f}%")
    if fundamentals:
        f = fundamentals
        lines.append(f"P/E: {f.get('pe_ttm','N/A')}  Revenue Growth YoY: {f.get('revenue_growth_1y','N/A')}")
        lines.append(f"Net Margin: {f.get('net_margin','N/A')}  Debt/Equity: {f.get('debt_equity','N/A')}")
        lines.append(f"Market Cap: {f.get('market_cap','N/A')}  Beta: {f.get('beta','N/A')}")
    if earnings:
        lines.append("Recent Earnings (EPS Estimate vs Actual):")
        for e in earnings[:3]:
            lines.append(f"  {e.get('period','?')}: Est {e.get('eps_estimate','?')} / Act {e.get('eps_actual','?')} ({e.get('surprise_pct',0):+.1f}% surprise)")
    if news:
        lines.append("Recent Headlines:")
        for n in news[:5]:
            lines.append(f"  [{n.get('datetime','')}] {n.get('headline','')}")
    briefing = "\n".join(lines)

    # ── Step 2: Web search ────────────────────────────────────────────────────
    if use_gemini:
        yield {"type": "log", "message": f"Searching web for latest {ticker} news and analysis (Gemini)..."}
    else:
        yield {"type": "log", "message": f"Searching Tavily for {ticker} analysis..."}
    await asyncio.sleep(0)

    if not use_gemini:
        search_snippet = _tavily_search(f"{ticker} stock analysis outlook 2025 2026")
        if search_snippet:
            briefing += f"\n\nWeb Search Results:\n{search_snippet}"
            web_searches.append(f"Tavily: {ticker} stock analysis")

    # ── Step 3: Debate rounds ─────────────────────────────────────────────────
    bull_args: list[str] = []
    bear_args: list[str] = []

    for round_num in range(1, rounds + 1):
        # Bull turn
        yield {"type": "log", "message": f"🐂 Bull Round {round_num} — Marcus is thinking..."}
        await asyncio.sleep(0)

        bull_context = briefing + f"\n\nThis is Round {round_num} of {rounds}."
        if bear_args:
            bull_context += f"\n\nBear's last point:\n{bear_args[-1]}"

        if use_gemini:
            bull_text, searches = _gemini_search_call(
                prompt=bull_context,
                system=_BULL_PERSONA.format(ticker=ticker),
            )
            web_searches.extend([f"Gemini Search (Bull R{round_num}): {s}" for s in searches])
        else:
            resp = llm.invoke([
                SystemMessage(content=_BULL_PERSONA.format(ticker=ticker)),
                HumanMessage(content=bull_context),
            ])
            bull_text = resp.content if isinstance(resp.content, str) else str(resp.content)

        bull_args.append(bull_text)
        yield {"type": "bull", "round": round_num, "text": bull_text}
        await asyncio.sleep(0)

        # Bear turn
        yield {"type": "log", "message": f"🐻 Bear Round {round_num} — Priya is thinking..."}
        await asyncio.sleep(0)

        bear_context = briefing + f"\n\nThis is Round {round_num} of {rounds}."
        bear_context += f"\n\nBull's latest point:\n{bull_args[-1]}"

        if use_gemini:
            bear_text, searches = _gemini_search_call(
                prompt=bear_context,
                system=_BEAR_PERSONA.format(ticker=ticker),
            )
            web_searches.extend([f"Gemini Search (Bear R{round_num}): {s}" for s in searches])
        else:
            resp = llm.invoke([
                SystemMessage(content=_BEAR_PERSONA.format(ticker=ticker)),
                HumanMessage(content=bear_context),
            ])
            bear_text = resp.content if isinstance(resp.content, str) else str(resp.content)

        bear_args.append(bear_text)
        yield {"type": "bear", "round": round_num, "text": bear_text}

        rounds_data.append({"round": round_num, "bull": bull_text, "bear": bear_text})
        yield {"type": "log", "message": f"Round {round_num} complete."}
        await asyncio.sleep(0)

    # ── Step 4: Moderator verdict ─────────────────────────────────────────────
    yield {"type": "log", "message": "⚖️ Moderator reviewing the debate..."}
    await asyncio.sleep(0)

    transcript = ""
    for rd in rounds_data:
        transcript += f"\n--- Round {rd['round']} ---\nMarcus (Bull):\n{rd['bull']}\n\nPriya (Bear):\n{rd['bear']}\n"

    mod_persona = _MODERATOR_PERSONA.format(ticker=ticker, rounds=rounds)
    if use_gemini:
        verdict_raw, _ = _gemini_search_call(
            prompt=f"Debate transcript:\n{transcript}\n\nReturn ONLY valid JSON.",
            system=mod_persona,
        )
    else:
        resp = llm.invoke([
            SystemMessage(content=mod_persona),
            HumanMessage(content=f"Debate transcript:\n{transcript}\n\nReturn ONLY valid JSON."),
        ])
        verdict_raw = resp.content if isinstance(resp.content, str) else str(resp.content)

    verdict = {}
    try:
        m = re.search(r'\{[\s\S]*\}', verdict_raw)
        if m:
            verdict = json.loads(m.group())
    except Exception:
        verdict = {"verdict": "Hold", "confidence": 50, "recommendation": verdict_raw,
                   "key_factors": [], "stronger_case": "neutral",
                   "disclaimer": "AI-generated analysis. Not financial advice."}

    yield {"type": "verdict", "data": verdict}
    await asyncio.sleep(0)

    # ── Step 5: Charts ────────────────────────────────────────────────────────
    yield {"type": "log", "message": "📊 Building charts..."}
    await asyncio.sleep(0)

    # Price chart (1yr daily closes)
    if history:
        price_data = [
            {"date": h.get("date", ""), "close": h.get("close", 0)}
            for h in history[-252:]  # up to 1 year of trading days
            if h.get("close")
        ]
        if price_data:
            charts_data.append({
                "type": "price",
                "title": f"{ticker} — 1 Year Price",
                "data": price_data,
                "x_key": "date",
                "y_key": "close",
                "color": "#8b5cf6",
            })
            yield {"type": "chart", "chart_type": "price", "title": f"{ticker} — 1 Year Price",
                   "data": price_data, "x_key": "date", "y_key": "close", "color": "#8b5cf6"}
            await asyncio.sleep(0)

    # Earnings chart
    if earnings and len(earnings) >= 2:
        earnings_data = [
            {"period": e.get("period", ""), "estimate": e.get("eps_estimate", 0),
             "actual": e.get("eps_actual", 0)}
            for e in reversed(earnings[:6])
            if e.get("period")
        ]
        if earnings_data:
            charts_data.append({
                "type": "earnings",
                "title": f"{ticker} — EPS: Estimate vs Actual",
                "data": earnings_data,
            })
            yield {"type": "chart", "chart_type": "earnings",
                   "title": f"{ticker} — EPS: Estimate vs Actual", "data": earnings_data}
            await asyncio.sleep(0)

    # ── Step 6: Portfolio recommendation ─────────────────────────────────────
    portfolio_rec = None
    if portfolio:
        yield {"type": "log", "message": "💼 Checking portfolio fit..."}
        await asyncio.sleep(0)

        portfolio_summary = ", ".join(
            f"{s.get('symbol','?')} ({s.get('quantity',0)} shares)"
            for s in portfolio[:8]
        )
        rec_prompt = (
            f"Debate summary on {ticker}:\n"
            f"Verdict: {verdict.get('verdict','Hold')} ({verdict.get('confidence',50)}% confidence)\n"
            f"Key factors: {', '.join(verdict.get('key_factors', []))}\n\n"
            f"User's portfolio: {portfolio_summary}\n\n"
            f"Should they add {ticker}?"
        )
        rec_persona = _PORTFOLIO_REC_PERSONA.format(
            ticker=ticker, rounds=rounds, portfolio=portfolio_summary
        )
        if use_gemini:
            portfolio_rec, _ = _gemini_search_call(prompt=rec_prompt, system=rec_persona)
        else:
            resp = llm.invoke([
                SystemMessage(content=rec_persona),
                HumanMessage(content=rec_prompt),
            ])
            portfolio_rec = resp.content if isinstance(resp.content, str) else str(resp.content)

        yield {"type": "portfolio_rec", "text": portfolio_rec}
        await asyncio.sleep(0)

    # ── Step 7: Save to DB ────────────────────────────────────────────────────
    yield {"type": "log", "message": "💾 Saving debate..."}
    await asyncio.sleep(0)

    store = get_chat_store()
    debate_record = store.save_debate(
        ticker=ticker,
        rounds_data=rounds_data,
        charts_data=charts_data,
        verdict=verdict,
        web_searches=web_searches,
        portfolio_recommendation=portfolio_rec,
        session_id=session_id,
        chat_id=chat_id,
    )
    debate_id = debate_record["id"]

    # Add debate block to chat history
    if session_id and chat_id:
        store.add_message(
            session_id=session_id,
            chat_id=chat_id,
            role="debate_block",
            content=f"Debate: {ticker}",
            metadata={"debate_id": debate_id, "ticker": ticker, "verdict": verdict},
        )

    yield {"type": "done", "debate_id": debate_id}


# ── Sync wrapper (for CLI / old endpoint) ────────────────────────────────────

def run_debate(ticker: str, rounds: int = 3, config: AgentConfig | None = None) -> dict:
    """Sync wrapper for backwards compat (CLI, tests)."""
    import asyncio

    rounds_data = []
    verdict = {}
    charts_data = []

    async def _collect():
        nonlocal verdict, charts_data
        async for event in stream_debate(ticker, rounds, config):
            if event["type"] == "bull":
                # rounds_data is accumulated inside stream_debate
                pass
            elif event["type"] == "verdict":
                verdict = event["data"]
            elif event["type"] == "chart":
                charts_data.append(event)
            elif event["type"] == "done":
                pass

    asyncio.run(_collect())

    # Re-run synchronously to get full data (simpler for CLI)
    if config is None:
        config = load_config("supervisor")
    llm = create_llm(config)
    provider = get_provider()

    quote = provider.get_quote(ticker.upper())
    fundamentals = provider.get_fundamentals(ticker.upper())

    return {
        "ticker": ticker.upper(),
        "rounds": rounds,
        "verdict": verdict,
        "stock_data": {"quote": quote, "fundamentals": fundamentals},
    }
