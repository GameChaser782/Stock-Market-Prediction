from __future__ import annotations

from .registry import ToolRegistry, tool
from ..data.provider import get_provider


@tool
def stock_lookup(ticker: str) -> str:
    """Get current price and basic info for a stock ticker (e.g. AAPL, RELIANCE.NS, BTC-USD)."""
    provider = get_provider()
    quote = provider.get_quote(ticker.upper().strip())
    if not quote:
        return f"Could not find stock data for '{ticker}'. Try adding .NS for Indian stocks (e.g. RELIANCE.NS)."

    profile = provider.get_profile(ticker.upper().strip())

    name = profile.get("name") or quote.get("name", ticker)
    currency = profile.get("currency") or quote.get("currency", "USD")
    price = quote.get("price", 0)
    change_pct = quote.get("change_pct", 0)
    market_cap = quote.get("market_cap") or (profile.get("market_cap", 0) * 1e6 if profile.get("market_cap") else None)
    sector = profile.get("sector") or quote.get("sector", "N/A")

    return (
        f"{ticker.upper()} ({name})\n"
        f"Price:       {currency} {price:.2f}\n"
        f"Change:      {change_pct:+.2f}%\n"
        f"Market Cap:  {_fmt(market_cap)}\n"
        f"52W High:    {quote.get('week_52_high', profile.get('week_52_high', 'N/A'))}\n"
        f"52W Low:     {quote.get('week_52_low', profile.get('week_52_low', 'N/A'))}\n"
        f"Sector:      {sector}\n"
        f"Exchange:    {profile.get('exchange', 'N/A')}"
    )


def _fmt(n) -> str:
    if not n:
        return "N/A"
    try:
        n = float(n)
        if n >= 1e12: return f"{n/1e12:.2f}T"
        if n >= 1e9:  return f"{n/1e9:.2f}B"
        if n >= 1e6:  return f"{n/1e6:.2f}M"
        return str(n)
    except Exception:
        return "N/A"


ToolRegistry.register(stock_lookup)
