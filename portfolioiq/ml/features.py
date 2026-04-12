"""Feature engineering for price direction prediction."""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_features(candles: list[dict]) -> pd.DataFrame:
    """
    Convert raw OHLCV candles into ML features.

    Features: price momentum, RSI, MACD, Bollinger position, volume trend,
              volatility, and lagged returns.
    """
    if len(candles) < 50:
        raise ValueError("Need at least 50 candles to build features.")

    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    c = df["close"]
    v = df["volume"]

    # Returns
    df["return_1d"] = c.pct_change(1)
    df["return_5d"] = c.pct_change(5)
    df["return_20d"] = c.pct_change(20)

    # Moving averages & distance from MA
    df["ma20"] = c.rolling(20).mean()
    df["ma50"] = c.rolling(50).mean()
    df["price_vs_ma20"] = (c - df["ma20"]) / df["ma20"]
    df["price_vs_ma50"] = (c - df["ma50"]) / df["ma50"]
    df["ma20_vs_ma50"] = (df["ma20"] - df["ma50"]) / df["ma50"]

    # RSI
    df["rsi_14"] = _rsi(c, 14)

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["macd"] = macd
    df["macd_signal"] = signal
    df["macd_hist"] = macd - signal
    df["macd_cross"] = (macd > signal).astype(int)

    # Bollinger Band position
    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    df["bb_position"] = (c - bb_lower) / (bb_upper - bb_lower + 1e-10)
    df["bb_width"] = (bb_upper - bb_lower) / bb_mid

    # Volatility
    df["volatility_20d"] = df["return_1d"].rolling(20).std()
    df["atr_14"] = _atr(df, 14)

    # Volume features
    df["volume_ratio"] = v / v.rolling(20).mean()
    df["volume_trend"] = v.rolling(5).mean() / v.rolling(20).mean()

    # Candlestick features
    df["body_size"] = (df["close"] - df["open"]) / df["open"]
    df["upper_shadow"] = (df["high"] - df[["close", "open"]].max(axis=1)) / df["open"]
    df["lower_shadow"] = (df[["close", "open"]].min(axis=1) - df["low"]) / df["open"]

    # Target: will price be higher in 5 days? (1 = yes, 0 = no)
    df["target"] = (c.shift(-5) > c).astype(int)

    feature_cols = [
        "return_1d", "return_5d", "return_20d",
        "price_vs_ma20", "price_vs_ma50", "ma20_vs_ma50",
        "rsi_14", "macd", "macd_signal", "macd_hist", "macd_cross",
        "bb_position", "bb_width",
        "volatility_20d", "atr_14",
        "volume_ratio", "volume_trend",
        "body_size", "upper_shadow", "lower_shadow",
    ]

    df = df.dropna()
    return df[feature_cols + ["target", "date", "close"]]


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("inf"))
    return 100 - 100 / (1 + rs)


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean() / df["close"]
