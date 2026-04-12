from __future__ import annotations

import pandas as pd

from .registry import ToolRegistry, tool
from ..data.provider import get_provider


@tool
def calculate_indicators(ticker: str, period: str = "6mo") -> str:
    """Calculate technical indicators: RSI, MACD, Bollinger Bands, moving averages, volume trend.

    Args:
        ticker: Stock ticker symbol
        period: Lookback period (6mo recommended for sufficient data)
    """
    ticker = ticker.upper().strip()
    period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
    days = period_days.get(period, 180)

    provider = get_provider()
    candles = provider.get_candles(ticker, days=days)

    if not candles or len(candles) < 30:
        return f"Not enough data to calculate indicators for '{ticker}'."

    close = pd.Series([c["close"] for c in candles])
    volume = pd.Series([c["volume"] for c in candles])
    current = close.iloc[-1]
    date = candles[-1]["date"]

    lines = [f"=== Technical Indicators: {ticker} ===", f"As of: {date}", f"Current Price: {current:.2f}"]

    # Moving Averages
    ma20 = close.rolling(20).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

    lines.append("\n--- Moving Averages ---")
    lines.append(f"MA(20):  {ma20:.2f}  {'▲ above' if current > ma20 else '▼ below'}")
    if ma50:
        lines.append(f"MA(50):  {ma50:.2f}  {'▲ above' if current > ma50 else '▼ below'}")
    if ma200:
        lines.append(f"MA(200): {ma200:.2f}  {'▲ above' if current > ma200 else '▼ below'}")

    # RSI
    rsi = _rsi(close)
    rsi_label = "Overbought" if rsi > 70 else ("Oversold" if rsi < 30 else "Neutral")
    lines.append(f"\n--- RSI (14) ---")
    lines.append(f"RSI: {rsi:.1f}  → {rsi_label}")

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    macd_label = "Bullish" if macd.iloc[-1] > signal.iloc[-1] else "Bearish"
    lines.append(f"\n--- MACD (12,26,9) ---")
    lines.append(f"MACD:   {macd.iloc[-1]:.4f}")
    lines.append(f"Signal: {signal.iloc[-1]:.4f}")
    lines.append(f"Hist:   {hist.iloc[-1]:.4f}  → {macd_label}")

    # Bollinger Bands
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = (bb_mid + 2 * bb_std).iloc[-1]
    bb_lower = (bb_mid - 2 * bb_std).iloc[-1]
    bb_pct = (current - bb_lower) / (bb_upper - bb_lower) * 100 if bb_upper != bb_lower else 50
    lines.append(f"\n--- Bollinger Bands (20,2) ---")
    lines.append(f"Upper:    {bb_upper:.2f}")
    lines.append(f"Middle:   {bb_mid.iloc[-1]:.2f}")
    lines.append(f"Lower:    {bb_lower:.2f}")
    lines.append(f"Position: {bb_pct:.0f}% of band width")

    # Volume
    avg_vol = volume.rolling(20).mean().iloc[-1]
    last_vol = volume.iloc[-1]
    vol_label = "High" if last_vol > avg_vol * 1.5 else ("Low" if last_vol < avg_vol * 0.5 else "Normal")
    lines.append(f"\n--- Volume ---")
    lines.append(f"Last:    {last_vol:,.0f}")
    lines.append(f"Avg(20): {avg_vol:,.0f}  → {vol_label} volume")

    # Summary
    bullish = sum([
        current > ma20,
        bool(ma50 and current > ma50),
        rsi > 50,
        macd.iloc[-1] > signal.iloc[-1],
    ])
    trend = "Strong Bullish" if bullish >= 3 else ("Bullish" if bullish == 2 else ("Bearish" if bullish == 1 else "Strong Bearish"))
    lines.append(f"\n--- Summary ---")
    lines.append(f"Bullish signals: {bullish}/4 → {trend}")

    return "\n".join(lines)


def _rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("inf"))
    return float((100 - 100 / (1 + rs)).iloc[-1])


ToolRegistry.register(calculate_indicators)
