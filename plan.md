# PortfolioIQ — Implementation Plan

**Last Updated:** April 26, 2026

---

## Overview

PortfolioIQ is a multi-agent financial advisor built on LangGraph. Eight specialized agents handle stock analysis, bull/bear debates, news impact, and portfolio risk. One command to run.

**Tagline:** "AI agents that debate, analyze, and advise on your portfolio"

---

## Architecture

```
User Query → [Supervisor Agent] routes to:

  /analyze  → [Researcher] → [Analyst] → [Risk Assessor] → Response
  /debate   → [Researcher] → [Bull Agent] ←→ [Bear Agent] → [Moderator] → Verdict
  /news     → [News Analyst] → [Impact Assessment] → Response
  /chat     → [Advisor Agent] (general conversation with memory)
```

---

## Phases

### ✅ Phase 1: Foundation (DONE)
- Python package with `pyproject.toml` and CLI entry point
- Config system (YAML + .env, multi-provider LLM factory)
- Financial tools: `stock_lookup`, `get_fundamentals`, `get_history`, `get_earnings`, `calculate_indicators`, `news_search`
- `DataProvider`: Finnhub (fast) + yfinance (fallback), symbol search via Yahoo Finance v1 API (no key, ~50ms)
- Supervisor agent + LangGraph graph
- FastAPI server: `/api/chat`, `/api/stream` (SSE), `/api/quote`, `/api/search`
- SQLite long-term memory
- Basic chat frontend (Next.js + Tailwind)

### ✅ Phase 2: Debate Feature (DONE)
- `bull_debater`, `bear_debater`, `moderator` agents with YAML + persona files
- Debate StateGraph: `gather_data → bull_round → bear_round → check_rounds (loop) → moderator → END`
- Each debater sees opponent's previous arguments (evidence-based rebuttals)
- Moderator outputs structured JSON: verdict, confidence (0-100), key_factors, recommendation
- `/api/debate/{ticker}?rounds=1-5` endpoint
- `portfolioiq debate AAPL` CLI command
- `DebatePanel` frontend with `TickerAutocomplete` and split-screen bull/bear columns

### ✅ Phase 3: Data + UX Fixes (DONE)
- Symbol search: blocks MUTUALFUND/OPTION types, prefers major exchanges (NMS, NYQ, NSI, BSE, LSE, etc.)
- Portfolio quantity: replaced browser number inputs with `+/-` buttons, integer-only, no 1.001 drift
- Currency totals: `currencyTotals()` groups by currency — separate INR/USD totals, no hardcoded USD
- Session persistence: `portfolioiq/sessions.py` with SQLite in `.portfolioiq/sessions.db` (gitignored)
- Session endpoints: `GET/POST /api/sessions`, `GET/PUT/DELETE /api/sessions/{id}`
- `SessionManager` dropdown in header (create, select, delete, last-updated display)
- Auto-save: 1.5s debounce on portfolio changes, portfolio state lifted to `page.tsx`
- GitHub Pages `index.html` rewritten as a docs/quickstart site
- `README.md` rewritten for directory structure + collaboration guide

### ✅ Phase 4: ML Pipeline (DONE)
- Feature engineering: ~20 features (returns, MA distances, RSI, MACD, Bollinger, ATR, volume ratios, candlestick patterns)
- XGBoost classifier with `TimeSeriesSplit` (n_splits=5, no data leakage)
- Target: price higher in 5 days?
- `portfolioiq train --ticker AAPL --days 365`
- `portfolioiq predict AAPL`
- `/api/predict/{ticker}` endpoint
- Models saved to `portfolioiq/ml/models/{TICKER}.joblib`

### Phase 5: Polish for Stars (TODO)
- [ ] Architecture diagram (Mermaid or PNG) for README
- [ ] Demo GIF of live debate for README
- [ ] Comparison table vs TradingAgents in README
- [ ] `pytest tests/` passing (currently no test suite)
- [ ] GitHub Actions CI (lint + test)
- [ ] Docker compose with Ollama sidecar
- [ ] `news_analyst` + `risk_assessor` graphs wired to `/api/news` and `/api/analyze`

---

## Tech Stack

| Layer | Tech |
|---|---|
| Agent orchestration | LangGraph StateGraph |
| LLM interface | LangChain Core |
| API server | FastAPI + Uvicorn |
| Financial data | Finnhub SDK (primary) + yfinance (fallback) |
| Symbol search | Yahoo Finance v1 REST (no key) |
| ML | XGBoost + scikit-learn |
| Persistence | SQLite (memory + sessions) |
| Frontend | Next.js App Router + Tailwind + TypeScript |
| LLM providers | Ollama, Gemini, Claude, OpenAI (all equal) |

---

## Key Decisions

- **LangGraph over CrewAI:** fine-grained control over debate round loop with conditional edges
- **Supervisor pattern:** only invoke agents needed per query (saves API calls)
- **Finnhub + yfinance:** Finnhub is faster (REST, not scraping), yfinance is the automatic fallback — no breakage without a key
- **All LLM providers equal:** no default, user picks via setup wizard — maximizes accessibility
- **SQLite for sessions:** no external dependency, gitignored folder, works offline
- **XGBoost over neural nets:** ships fast, handles tabular financial data well
