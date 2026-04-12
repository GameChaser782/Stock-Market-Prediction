from __future__ import annotations

import os
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

if TYPE_CHECKING:
    from .agent import PortfolioAgent


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    user_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    thread_id: str


def create_app(agent: "PortfolioAgent") -> FastAPI:
    app = FastAPI(
        title="PortfolioIQ",
        description="Multi-agent financial advisor — debates, analysis, news, ML predictions.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "provider": agent.config.model_provider,
            "model": agent.config.model_name,
        }

    # ── Symbol search (autocomplete) ──────────────────────────────────────────
    @app.get("/api/search")
    def search(q: str = Query(..., min_length=1)):
        """Fast symbol search for the frontend search bar. No API key needed."""
        from .data.provider import search_symbols
        results = search_symbols(q, limit=8)
        return {"results": results}

    # ── Chat ──────────────────────────────────────────────────────────────────
    @app.post("/api/chat", response_model=ChatResponse)
    def chat(req: ChatRequest):
        try:
            response = agent.chat(req.message, thread_id=req.thread_id, user_id=req.user_id)
            return ChatResponse(response=response, thread_id=req.thread_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/stream")
    async def stream(req: ChatRequest):
        async def token_generator() -> AsyncIterator[str]:
            async for token in agent.stream(req.message, thread_id=req.thread_id, user_id=req.user_id):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(token_generator(), media_type="text/event-stream")

    # ── Debate ────────────────────────────────────────────────────────────────
    @app.get("/api/debate/{ticker}")
    def debate(ticker: str, rounds: int = Query(default=3, ge=1, le=5)):
        """Run a bull vs bear debate on a stock. rounds=1-5."""
        from .graphs.debate import run_debate
        try:
            return run_debate(ticker.upper(), rounds=rounds, config=agent.config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Full analysis ─────────────────────────────────────────────────────────
    @app.get("/api/analyze/{ticker}")
    def analyze(ticker: str):
        """Full stock analysis: fundamentals + technicals + news + score."""
        from .graphs.analysis import run_analysis
        try:
            return run_analysis(ticker.upper(), config=agent.config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── News impact ───────────────────────────────────────────────────────────
    @app.get("/api/news/{ticker}")
    def news_impact(ticker: str):
        """Fetch and analyze news impact on a stock."""
        from .graphs.news import run_news_analysis
        try:
            return run_news_analysis(ticker.upper(), config=agent.config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Quote (fast, no AI) ───────────────────────────────────────────────────
    @app.get("/api/quote/{ticker}")
    def quote(ticker: str):
        """Get current stock price and basic info. Fast, no LLM call."""
        from .data.provider import get_provider
        provider = get_provider()
        q = provider.get_quote(ticker.upper())
        if not q:
            raise HTTPException(status_code=404, detail=f"Stock '{ticker}' not found.")
        return q

    # ── ML predict ────────────────────────────────────────────────────────────
    @app.get("/api/predict/{ticker}")
    def predict(ticker: str):
        """Run ML prediction for a trained ticker model."""
        from .ml.predict import predict as ml_predict
        try:
            return ml_predict(ticker.upper())
        except ImportError:
            raise HTTPException(status_code=501, detail="Install ML deps: pip install 'portfolioiq[ml]'")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Memory ────────────────────────────────────────────────────────────────
    @app.get("/api/memory/{user_id}")
    def get_memory(user_id: str):
        if not agent.config.long_term_memory:
            return {"memories": []}
        db_path = os.path.join(agent.config.memory_dir, "memory.db")
        from .memory.long_term import SQLiteLongTermMemory
        mem = SQLiteLongTermMemory(db_path=db_path)
        return {"user_id": user_id, "memories": mem.fetch_all(user_id)}

    # ── Frontend (Next.js static export) ──────────────────────────────────────
    frontend_out = os.path.join(os.path.dirname(__file__), "..", "frontend", "out")
    if os.path.isdir(frontend_out):
        app.mount("/", StaticFiles(directory=frontend_out, html=True), name="frontend")

    return app


def run_server(agent: "PortfolioAgent", host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn
    app = create_app(agent)
    print(f"\n  PortfolioIQ  http://{host}:{port}")
    print(f"  Provider:    {agent.config.model_provider}/{agent.config.model_name}")
    print(f"  API docs:    http://{host}:{port}/docs\n")
    uvicorn.run(app, host=host, port=port)
