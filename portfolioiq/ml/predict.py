"""Run ML prediction for a ticker."""
from __future__ import annotations

from pathlib import Path


def predict(ticker: str) -> dict:
    """
    Load trained model and predict 5-day price direction.

    Returns: {ticker, direction, probability, confidence, top_factors}
    """
    try:
        import joblib
    except ImportError:
        raise ImportError("Install ML dependencies: pip install 'portfolioiq[ml]'")

    ticker = ticker.upper()
    models_dir = Path(__file__).parent / "models"
    model_path = models_dir / f"{ticker}.joblib"

    if not model_path.exists():
        return {
            "ticker": ticker,
            "error": f"No trained model found for {ticker}. Run: portfolioiq train --ticker {ticker}",
        }

    artifact = joblib.load(model_path)
    model = artifact["model"]
    feature_cols = artifact["feature_cols"]

    from ..data.provider import get_provider
    from .features import build_features

    provider = get_provider()
    candles = provider.get_candles(ticker, days=120)

    if len(candles) < 60:
        return {"ticker": ticker, "error": "Not enough data for prediction."}

    df = build_features(candles)
    if df.empty:
        return {"ticker": ticker, "error": "Feature extraction failed."}

    # Use the most recent row
    X_latest = df[feature_cols].iloc[[-1]].values
    prob = float(model.predict_proba(X_latest)[0][1])  # prob of going UP
    direction = "UP" if prob > 0.5 else "DOWN"
    confidence = prob if prob > 0.5 else (1 - prob)

    # Top contributing features
    importances = dict(zip(feature_cols, model.feature_importances_.tolist()))
    top_factors = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:3]
    top_factors = [{"feature": k, "importance": round(v, 4)} for k, v in top_factors]

    current_price = candles[-1]["close"]

    return {
        "ticker": ticker,
        "current_price": current_price,
        "direction": direction,
        "probability": round(prob, 4),
        "confidence": f"{confidence:.1%}",
        "horizon": "5 trading days",
        "top_factors": top_factors,
        "disclaimer": "ML prediction only. Not financial advice.",
    }
