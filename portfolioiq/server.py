from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, AsyncIterator, Any, Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .agent import PortfolioAgent


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    user_id: str = "default"


class SessionCreate(BaseModel):
    name: str
    data: dict[str, Any] = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class MessageCreate(BaseModel):
    session_id: str
    chat_id: str
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatCreate(BaseModel):
    session_id: str
    name: str = "New chat"


class PortfolioSnapshotRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)


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

    @app.post("/api/stocks/snapshots")
    def stock_snapshots(body: PortfolioSnapshotRequest):
        """Return non-LLM stock snapshots for portfolio analytics."""
        from .data.provider import get_provider

        def annualized_volatility(closes: list[float]) -> float | None:
            if len(closes) < 3:
                return None
            returns = []
            for idx in range(1, len(closes)):
                prev = closes[idx - 1]
                curr = closes[idx]
                if prev:
                    returns.append((curr - prev) / prev)
            if len(returns) < 2:
                return None
            mean = sum(returns) / len(returns)
            variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
            return (variance ** 0.5) * (252 ** 0.5) * 100

        def risk_summary(beta: Any, debt_equity: Any, volatility: float | None) -> tuple[int, str]:
            score = 35
            try:
                if beta is not None:
                    beta_val = float(beta)
                    score += min(max((beta_val - 1.0) * 22, 0), 30)
            except Exception:
                pass
            try:
                if debt_equity is not None:
                    de_val = float(debt_equity)
                    score += min(max(de_val / 12, 0), 20)
            except Exception:
                pass
            if volatility is not None:
                score += min(max((volatility - 20) * 0.9, 0), 25)
            score = max(5, min(int(round(score)), 95))
            label = "Low" if score < 35 else "Moderate" if score < 65 else "High"
            return score, label

        provider = get_provider()
        symbols = []
        for symbol in body.symbols:
            symbol = symbol.upper().strip()
            if symbol and symbol not in symbols:
                symbols.append(symbol)

        snapshots = []
        for symbol in symbols[:50]:
            quote = provider.get_quote(symbol) or {}
            profile = provider.get_profile(symbol) or {}
            fundamentals = provider.get_fundamentals(symbol) or {}
            candles = provider.get_candles(symbol, days=365) or []

            closes = [float(c["close"]) for c in candles if c.get("close") is not None]
            latest_close = closes[-1] if closes else quote.get("price")
            first_close = closes[0] if closes else None
            one_year_change = None
            one_year_change_pct = None
            if latest_close is not None and first_close:
                one_year_change = float(latest_close) - float(first_close)
                one_year_change_pct = (one_year_change / float(first_close)) * 100 if first_close else None

            volatility = annualized_volatility(closes)
            risk_score, risk_label = risk_summary(
                fundamentals.get("beta"),
                fundamentals.get("debt_equity"),
                volatility,
            )

            snapshots.append({
                "symbol": symbol,
                "quote": quote,
                "profile": profile,
                "fundamentals": fundamentals,
                "metrics": {
                    "one_year_change": one_year_change,
                    "one_year_change_pct": one_year_change_pct,
                    "annualized_volatility_pct": volatility,
                    "fifty_two_week_high": max(closes) if closes else quote.get("week_52_high"),
                    "fifty_two_week_low": min(closes) if closes else quote.get("week_52_low"),
                    "risk_score": risk_score,
                    "risk_label": risk_label,
                },
            })
        return {"snapshots": snapshots}

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

    # ── Debate streaming ──────────────────────────────────────────────────────
    @app.get("/api/debate/stream/{ticker}")
    async def stream_debate_endpoint(
        ticker: str,
        rounds: int = Query(default=3, ge=1, le=5),
        session_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        portfolio: Optional[str] = None,  # JSON-encoded portfolio array
    ):
        """Stream debate as SSE. Each event: data: <json>\n\n"""
        from .graphs.debate import stream_debate as _stream

        portfolio_list = []
        if portfolio:
            try:
                portfolio_list = json.loads(portfolio)
            except Exception:
                pass

        async def event_generator():
            try:
                async for event in _stream(
                    ticker=ticker.upper(),
                    rounds=rounds,
                    config=agent.config,
                    session_id=session_id,
                    chat_id=chat_id,
                    portfolio=portfolio_list or None,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # ── Chat history ──────────────────────────────────────────────────────────
    @app.get("/api/chats/session/{session_id}")
    def list_chats(session_id: str):
        from .chat_store import get_chat_store
        return get_chat_store().list_chats(session_id)

    @app.post("/api/chats", status_code=201)
    def create_chat(body: ChatCreate):
        from .chat_store import get_chat_store
        return get_chat_store().create_chat(body.session_id, body.name)

    @app.patch("/api/chats/{chat_id}")
    def rename_chat(chat_id: str, body: dict):
        from .chat_store import get_chat_store
        name = body.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        chat = get_chat_store().rename_chat(chat_id, name)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return chat

    @app.delete("/api/chats/{chat_id}", status_code=204)
    def delete_chat(chat_id: str):
        from .chat_store import get_chat_store
        if not get_chat_store().delete_chat(chat_id):
            raise HTTPException(status_code=404, detail="Chat not found")

    @app.get("/api/chat/history/{chat_id}")
    def get_chat_history(chat_id: str):
        from .chat_store import get_chat_store
        return get_chat_store().get_messages(chat_id)

    @app.post("/api/chat/message", status_code=201)
    def save_chat_message(body: MessageCreate):
        from .chat_store import get_chat_store
        return get_chat_store().add_message(
            session_id=body.session_id,
            chat_id=body.chat_id,
            role=body.role,
            content=body.content,
            metadata=body.metadata,
        )

    @app.delete("/api/chat/history/{chat_id}", status_code=204)
    def clear_chat_history(chat_id: str):
        from .chat_store import get_chat_store
        get_chat_store().delete_chat_messages(chat_id)

    # ── Debates ───────────────────────────────────────────────────────────────
    @app.get("/api/debates/{debate_id}")
    def get_debate(debate_id: str):
        from .chat_store import get_chat_store
        debate = get_chat_store().get_debate(debate_id)
        if not debate:
            raise HTTPException(status_code=404, detail="Debate not found")
        return debate

    @app.get("/api/debates/chat/{chat_id}")
    def list_chat_debates(chat_id: str):
        from .chat_store import get_chat_store
        return get_chat_store().list_debates(chat_id)

    # ── PDF upload ────────────────────────────────────────────────────────────
    @app.post("/api/upload/pdf")
    async def upload_pdf(file: UploadFile):
        import hashlib
        upload_dir = os.path.join(os.getenv("AGENT_MEMORY_DIR", ".portfolioiq"), "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        content = await file.read()
        file_hash = hashlib.md5(content).hexdigest()[:8]
        filename = f"{file_hash}_{file.filename}"
        filepath = os.path.join(upload_dir, filename)

        with open(filepath, "wb") as f:
            f.write(content)

        # Extract text
        text = ""
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages[:20])
        except ImportError:
            text = "[PDF text extraction requires: pip install pypdf]"
        except Exception as e:
            text = f"[Could not extract text: {e}]"

        return {
            "id": file_hash,
            "filename": file.filename,
            "path": filepath,
            "text_preview": text[:500],
            "text_length": len(text),
        }

    # ── Sessions ──────────────────────────────────────────────────────────────
    @app.get("/api/sessions")
    def list_sessions():
        from .sessions import get_store
        from .chat_store import get_chat_store
        sessions = get_store().list_all()
        chat_store = get_chat_store()
        # Strip full data from list view, only return summary
        summaries = []
        for s in sessions:
            stats = chat_store.get_session_stats(s["id"])
            summaries.append(
                {"id": s["id"], "name": s["name"],
                 "created_at": s["created_at"], "updated_at": s["updated_at"],
                 "stock_count": len(s["data"].get("portfolio", [])),
                 "message_count": stats["message_count"],
                 "last_message": stats["last_message"],
                 "last_message_role": stats["last_message_role"],
                 "last_message_at": stats["last_message_at"]}
            )
        summaries.sort(key=lambda s: s["last_message_at"] or s["updated_at"], reverse=True)
        return summaries

    @app.post("/api/sessions", status_code=201)
    def create_session(body: SessionCreate):
        from .sessions import get_store
        return get_store().create(name=body.name, data=body.data)

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str):
        from .sessions import get_store
        session = get_store().get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @app.put("/api/sessions/{session_id}")
    def update_session(session_id: str, body: SessionUpdate):
        from .sessions import get_store
        session = get_store().update(session_id, name=body.name, data=body.data)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @app.delete("/api/sessions/{session_id}", status_code=204)
    def delete_session(session_id: str):
        from .sessions import get_store
        if not get_store().delete(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

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
