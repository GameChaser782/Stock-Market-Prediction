"""
Unified financial data provider.

Priority:
  1. Finnhub  (FINNHUB_API_KEY set)        — real-time, fast, reliable
  2. yfinance fallback                      — free, slower, scraping-based

Search / autocomplete always uses the Yahoo Finance v1 search endpoint
(no key needed, ~50ms response time).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import httpx

_YF_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
_YF_HEADERS = {"User-Agent": "Mozilla/5.0"}


# ── Symbol search (autocomplete) ─────────────────────────────────────────────

def search_symbols(query: str, limit: int = 8) -> list[dict]:
    """Fast symbol search using Yahoo Finance's search endpoint. No API key needed."""
    if not query or len(query) < 1:
        return []
    try:
        r = httpx.get(
            _YF_SEARCH_URL,
            params={"q": query, "quotesCount": limit, "newsCount": 0, "enableFuzzyQuery": True},
            headers=_YF_HEADERS,
            timeout=3.0,
        )
        r.raise_for_status()
        quotes = r.json().get("quotes", [])
        return [
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname") or "",
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", "EQUITY"),
            }
            for q in quotes
            if q.get("symbol")
        ]
    except Exception:
        return []


# ── Data provider ─────────────────────────────────────────────────────────────

class DataProvider:
    """Fetches financial data from Finnhub (with yfinance fallback)."""

    def __init__(self) -> None:
        self._finnhub_key = os.getenv("FINNHUB_API_KEY")
        self._client: Any = None
        if self._finnhub_key:
            try:
                import finnhub
                self._client = finnhub.Client(api_key=self._finnhub_key)
            except ImportError:
                pass

    @property
    def using_finnhub(self) -> bool:
        return self._client is not None

    # ── Quote ─────────────────────────────────────────────────────────────────

    def get_quote(self, ticker: str) -> dict:
        """Return current quote: price, change_pct, open, high, low, prev_close."""
        ticker = ticker.upper().strip()
        if self._client:
            try:
                q = self._client.quote(ticker)
                if q.get("c"):
                    return {
                        "ticker": ticker,
                        "price": q["c"],
                        "change": q.get("d", 0),
                        "change_pct": q.get("dp", 0),
                        "open": q.get("o", 0),
                        "high": q.get("h", 0),
                        "low": q.get("l", 0),
                        "prev_close": q.get("pc", 0),
                    }
            except Exception:
                pass
        # fallback: yfinance
        return self._yf_quote(ticker)

    def _yf_quote(self, ticker: str) -> dict:
        import yfinance as yf
        suffixes = ["", ".NS", ".BO"]
        for s in suffixes:
            t = ticker + s if not any(ticker.endswith(x) for x in [".NS", ".BO", "-USD"]) else ticker
            try:
                stock = yf.Ticker(t)
                info = stock.info
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                if price:
                    return {
                        "ticker": t,
                        "name": info.get("shortName", t),
                        "price": float(price),
                        "change": info.get("regularMarketChange", 0),
                        "change_pct": info.get("regularMarketChangePercent", 0),
                        "open": info.get("open", 0),
                        "high": info.get("dayHigh", 0),
                        "low": info.get("dayLow", 0),
                        "prev_close": info.get("previousClose", 0),
                        "currency": info.get("currency", "USD"),
                        "market_cap": info.get("marketCap"),
                        "sector": info.get("sector"),
                        "week_52_high": info.get("fiftyTwoWeekHigh"),
                        "week_52_low": info.get("fiftyTwoWeekLow"),
                    }
            except Exception:
                if s == "":
                    continue
        return {}

    # ── Company profile ───────────────────────────────────────────────────────

    def get_profile(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()
        if self._client:
            try:
                p = self._client.company_profile2(symbol=ticker)
                if p.get("name"):
                    return {
                        "name": p.get("name"),
                        "ticker": p.get("ticker"),
                        "exchange": p.get("exchange"),
                        "currency": p.get("currency"),
                        "country": p.get("country"),
                        "sector": p.get("finnhubIndustry"),
                        "market_cap": p.get("marketCapitalization"),
                        "employees": p.get("employeeTotal"),
                        "ipo_date": p.get("ipo"),
                        "website": p.get("weburl"),
                    }
            except Exception:
                pass
        return {}

    # ── Fundamentals ──────────────────────────────────────────────────────────

    def get_fundamentals(self, ticker: str) -> dict:
        ticker = ticker.upper().strip()
        if self._client:
            try:
                m = self._client.company_basic_financials(ticker, "all")
                metrics = m.get("metric", {})
                if metrics:
                    return {
                        # Valuation
                        "pe_ttm": metrics.get("peNormalizedAnnual"),
                        "pe_forward": metrics.get("peExclExtraTTM"),
                        "pb_ratio": metrics.get("pbAnnual"),
                        "ps_ratio": metrics.get("psTTM"),
                        "ev_ebitda": metrics.get("evEbitdaTTM"),
                        "peg_ratio": metrics.get("pegRatio"),
                        # Profitability
                        "gross_margin": metrics.get("grossMarginTTM"),
                        "operating_margin": metrics.get("operatingMarginTTM"),
                        "net_margin": metrics.get("netMarginTTM"),
                        "roe": metrics.get("roeTTM"),
                        "roa": metrics.get("roaTTM"),
                        # Growth
                        "revenue_ttm": metrics.get("revenueTTM"),
                        "revenue_growth_1y": metrics.get("revenueGrowthTTMYoy"),
                        "eps_ttm": metrics.get("epsTTM"),
                        "eps_growth_1y": metrics.get("epsGrowthTTMYoy"),
                        # Balance sheet
                        "total_debt": metrics.get("totalDebt/totalEquityAnnual"),
                        "current_ratio": metrics.get("currentRatioAnnual"),
                        "debt_equity": metrics.get("totalDebt/totalEquityAnnual"),
                        "free_cash_flow": metrics.get("freeCashFlowTTM"),
                        # Market
                        "beta": metrics.get("beta"),
                        "week_52_high": metrics.get("52WeekHigh"),
                        "week_52_low": metrics.get("52WeekLow"),
                        "week_52_return": metrics.get("52WeekPriceReturnDaily"),
                        "dividend_yield": metrics.get("dividendYieldIndicatedAnnual"),
                    }
            except Exception:
                pass
        # fallback: yfinance
        return self._yf_fundamentals(ticker)

    def _yf_fundamentals(self, ticker: str) -> dict:
        import yfinance as yf
        try:
            info = yf.Ticker(ticker).info
            return {
                "pe_ttm": info.get("trailingPE"),
                "pe_forward": info.get("forwardPE"),
                "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "gross_margin": info.get("grossMargins"),
                "operating_margin": info.get("operatingMargins"),
                "net_margin": info.get("profitMargins"),
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "revenue_ttm": info.get("totalRevenue"),
                "revenue_growth_1y": info.get("revenueGrowth"),
                "eps_ttm": info.get("trailingEps"),
                "total_debt": info.get("totalDebt"),
                "current_ratio": info.get("currentRatio"),
                "debt_equity": info.get("debtToEquity"),
                "free_cash_flow": info.get("freeCashflow"),
                "beta": info.get("beta"),
                "dividend_yield": info.get("dividendYield"),
            }
        except Exception:
            return {}

    # ── Historical candles ────────────────────────────────────────────────────

    def get_candles(self, ticker: str, days: int = 180) -> list[dict]:
        """Return daily OHLCV candles for the last N days."""
        ticker = ticker.upper().strip()
        end = int(time.time())
        start = int((datetime.now() - timedelta(days=days)).timestamp())

        if self._client:
            try:
                r = self._client.stock_candles(ticker, "D", start, end)
                if r.get("s") == "ok":
                    candles = []
                    for i in range(len(r["t"])):
                        candles.append({
                            "date": datetime.fromtimestamp(r["t"][i]).strftime("%Y-%m-%d"),
                            "open": r["o"][i],
                            "high": r["h"][i],
                            "low": r["l"][i],
                            "close": r["c"][i],
                            "volume": r["v"][i],
                        })
                    return candles
            except Exception:
                pass
        return self._yf_candles(ticker, days)

    def _yf_candles(self, ticker: str, days: int) -> list[dict]:
        import yfinance as yf
        period = "1y" if days > 180 else "6mo" if days > 90 else "3mo"
        try:
            hist = yf.Ticker(ticker).history(period=period)
            candles = []
            for idx, row in hist.iterrows():
                candles.append({
                    "date": str(idx.date()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            return candles
        except Exception:
            return []

    # ── News ──────────────────────────────────────────────────────────────────

    def get_news(self, ticker: str, days: int = 7) -> list[dict]:
        """Return recent company news."""
        ticker = ticker.upper().strip()
        if self._client:
            try:
                end = datetime.now().strftime("%Y-%m-%d")
                start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                items = self._client.company_news(ticker, _from=start, to=end)
                return [
                    {
                        "headline": n.get("headline"),
                        "source": n.get("source"),
                        "url": n.get("url"),
                        "summary": n.get("summary"),
                        "datetime": datetime.fromtimestamp(n["datetime"]).strftime("%Y-%m-%d") if n.get("datetime") else "",
                    }
                    for n in (items[:10] if items else [])
                ]
            except Exception:
                pass
        return []

    # ── Earnings ──────────────────────────────────────────────────────────────

    def get_earnings(self, ticker: str) -> list[dict]:
        ticker = ticker.upper().strip()
        if self._client:
            try:
                items = self._client.company_earnings(ticker, limit=4)
                return [
                    {
                        "period": e.get("period"),
                        "eps_actual": e.get("actual"),
                        "eps_estimate": e.get("estimate"),
                        "surprise_pct": e.get("surprisePercent"),
                    }
                    for e in (items or [])
                ]
            except Exception:
                pass
        return self._yf_earnings(ticker)

    def _yf_earnings(self, ticker: str) -> list[dict]:
        import yfinance as yf
        try:
            hist = yf.Ticker(ticker).earnings_history
            if hist is None or hist.empty:
                return []
            result = []
            for _, row in hist.tail(4).iterrows():
                result.append({
                    "period": str(row.get("quarter", "")),
                    "eps_actual": row.get("epsActual"),
                    "eps_estimate": row.get("epsEstimate"),
                    "surprise_pct": row.get("surprisePercent"),
                })
            return result
        except Exception:
            return []


@lru_cache(maxsize=1)
def get_provider() -> DataProvider:
    """Singleton provider instance."""
    return DataProvider()
