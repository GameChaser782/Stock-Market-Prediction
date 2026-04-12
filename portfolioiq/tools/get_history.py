from __future__ import annotations

from .registry import ToolRegistry, tool
from ..data.provider import get_provider


@tool
def get_history(ticker: str, period: str = "3mo") -> str:
    """Get historical price data for a stock.

    Args:
        ticker: Stock ticker symbol (e.g. AAPL, RELIANCE.NS)
        period: Time period — 1mo, 3mo, 6mo, 1y, 2y
    """
    ticker = ticker.upper().strip()
    period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730}
    days = period_days.get(period, 90)

    provider = get_provider()
    candles = provider.get_candles(ticker, days=days)

    if not candles:
        return f"No historical data found for '{ticker}'."

    start = candles[0]
    end = candles[-1]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    vols = [c["volume"] for c in candles]

    pct_change = ((end["close"] - start["close"]) / start["close"]) * 100

    recent = candles[-5:]
    recent_str = "\n".join(
        f"  {c['date']}  O:{c['open']:.2f}  H:{c['high']:.2f}  L:{c['low']:.2f}  C:{c['close']:.2f}  V:{c['volume']:,}"
        for c in recent
    )

    return (
        f"=== Price History: {ticker} ({period}) ===\n"
        f"Start:       {start['date']} @ {start['close']:.2f}\n"
        f"End:         {end['date']} @ {end['close']:.2f}\n"
        f"Change:      {pct_change:+.2f}%\n"
        f"Period High: {max(highs):.2f}\n"
        f"Period Low:  {min(lows):.2f}\n"
        f"Avg Volume:  {sum(vols)//len(vols):,}\n\n"
        f"--- Recent 5 Sessions ---\n{recent_str}"
    )


ToolRegistry.register(get_history)
