# PortfolioIQ

> AI agents that debate, analyze, and advise on your portfolio.

Multi-agent financial advisor with bull/bear stock debates, live news analysis, and ML price predictions. One command to run.

**[Live docs →](https://gamechaser782.github.io/PortfolioIQ/)**

---

## Quickstart

```bash
pip install portfolioiq
portfolioiq setup     # interactive wizard: pick LLM provider + API keys
portfolioiq serve     # starts backend + serves React frontend at localhost:8000
```

Optional CLI commands:

```bash
portfolioiq chat              # interactive terminal chat
portfolioiq debate AAPL       # 3-round bull vs bear debate
portfolioiq train --ticker AAPL --days 365
portfolioiq predict AAPL
```

Docker:

```bash
docker compose up
```

---

## Features

| Feature | Description |
|---|---|
| **Bull/Bear Debate** | Two agents argue opposing cases with real data. Moderator gives verdict + confidence score. |
| **Stock Analysis** | Fundamentals + technicals + risk scoring across Researcher → Analyst → Risk Assessor. |
| **News Impact** | Maps global macro events (tariffs, rate decisions) to your portfolio stocks. |
| **ML Predictions** | XGBoost classifier: 5-day price direction using OHLCV + technical indicators. |
| **Streaming Chat** | SSE-streamed responses from the supervisor agent, with long-term memory. |
| **Session Persistence** | Portfolio saved across restarts in local SQLite (gitignored). |
| **Multi-Provider LLM** | Ollama, Gemini, Claude, OpenAI — all equal. Pick during setup. |

---

## Directory Structure

```
PortfolioIQ/
├── pyproject.toml              # pip installable, CLI entry point
├── Makefile                    # make run / make test / make train
├── .env.example                # copy to .env, fill in keys
│
├── portfolioiq/                # main Python package
│   ├── __main__.py             # CLI commands
│   ├── config.py               # YAML + .env config loader
│   ├── agent.py                # PortfolioAgent (supervisor)
│   ├── server.py               # FastAPI app + all REST endpoints
│   │
│   ├── graphs/                 # LangGraph StateGraphs
│   │   ├── debate.py           # bull → bear → check_rounds → moderator loop
│   │   ├── analysis.py         # researcher → analyst → risk_assessor
│   │   └── news.py             # news_analyst graph
│   │
│   ├── tools/                  # @tool decorated financial tools
│   │   ├── stock_lookup.py
│   │   ├── get_fundamentals.py
│   │   ├── get_earnings.py
│   │   ├── get_history.py
│   │   ├── calculate_indicators.py
│   │   └── news_search.py      # Tavily → DuckDuckGo fallback
│   │
│   ├── data/
│   │   └── provider.py         # Finnhub (fast) + yfinance (fallback)
│   │
│   ├── memory/
│   │   └── long_term.py        # SQLite long-term memory
│   │
│   ├── sessions.py             # session persistence (SQLite in .portfolioiq/)
│   │
│   └── ml/                     # XGBoost ML pipeline
│       ├── features.py         # ~20 OHLCV + indicator features
│       ├── train.py            # TimeSeriesSplit cross-validation
│       └── predict.py
│
├── agents/                     # per-agent YAML config + persona markdown
│   ├── supervisor.yaml + supervisor_persona.md
│   ├── bull_debater.yaml + bull_debater_persona.md
│   ├── bear_debater.yaml + bear_debater_persona.md
│   ├── moderator.yaml + moderator_persona.md
│   ├── researcher.yaml + researcher_persona.md
│   ├── analyst.yaml + analyst_persona.md
│   ├── news_analyst.yaml + news_analyst_persona.md
│   └── risk_assessor.yaml + risk_assessor_persona.md
│
└── frontend/                   # Next.js App Router (TypeScript + Tailwind)
    ├── app/page.tsx             # main shell: tabs + session state
    └── components/
        ├── ChatPanel.tsx
        ├── DebatePanel.tsx
        ├── PortfolioPanel.tsx
        ├── SessionManager.tsx
        ├── StockSearch.tsx
        └── TickerAutocomplete.tsx
```

---

## Configuration

Copy `.env.example` to `.env`:

```
# LLM Provider (pick one)
MODEL_PROVIDER=ollama          # ollama | gemini | anthropic | openai
MODEL_NAME=llama3              # model name for the chosen provider

# API keys (only the one you need)
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...

# Financial data (optional — yfinance works without keys)
FINNHUB_API_KEY=...            # faster data, 60 req/min free
TAVILY_API_KEY=...             # better news search
```

Or run `portfolioiq setup` for an interactive wizard.

---

## REST API

Full OpenAPI docs at `http://localhost:8000/docs`.

| Endpoint | Description |
|---|---|
| `GET /api/health` | Server status + active provider/model |
| `GET /api/search?q=` | Symbol autocomplete (no key needed) |
| `GET /api/quote/{ticker}` | Current price, change, currency |
| `POST /api/stream` | SSE streaming chat |
| `GET /api/debate/{ticker}` | Bull/bear debate (`?rounds=1-5`) |
| `GET /api/analyze/{ticker}` | Full analysis |
| `GET /api/news/{ticker}` | News impact analysis |
| `GET/POST /api/sessions` | List / create sessions |
| `GET/PUT/DELETE /api/sessions/{id}` | Load / save / delete a session |

---

## Contributing

The codebase is designed to be extended module by module.

**Adding a new agent:**
1. Create `agents/my_agent.yaml` and `agents/my_agent_persona.md`
2. Implement the node function in `portfolioiq/graphs/`
3. Wire it into the supervisor routing logic

**Adding a new tool:**
1. Add `portfolioiq/tools/my_tool.py` with a `@tool` decorated function
2. List it in the relevant agent's `yaml` tool list

**Adding a data provider:**
Extend `portfolioiq/data/provider.py` — implement `get_quote()`, `get_fundamentals()`, `get_candles()` and set it as the primary provider.

**Setup for development:**

```bash
git clone https://github.com/GameChaser782/PortfolioIQ
cd PortfolioIQ
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
cp .env.example .env
portfolioiq setup
```

---

## Disclaimer

Not financial advice. For educational and research purposes only.
