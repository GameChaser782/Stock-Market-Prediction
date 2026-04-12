"""Train XGBoost price direction classifier on historical data."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .features import build_features


def train(ticker: str, days: int = 730) -> dict:
    """
    Train a price direction model for a ticker.

    Returns a dict with accuracy, feature importances, and model path.
    """
    try:
        import joblib
        from xgboost import XGBClassifier
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.metrics import accuracy_score, classification_report
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        raise ImportError("Install ML dependencies: pip install 'portfolioiq[ml]'")

    from ..data.provider import get_provider
    provider = get_provider()

    print(f"[ML] Fetching {days} days of data for {ticker}...")
    candles = provider.get_candles(ticker, days=days)

    if len(candles) < 60:
        raise ValueError(f"Not enough data for {ticker} ({len(candles)} candles, need 60+).")

    print(f"[ML] Building features from {len(candles)} candles...")
    df = build_features(candles)

    feature_cols = [c for c in df.columns if c not in ("target", "date", "close")]
    X = df[feature_cols].values
    y = df["target"].values

    # Time-series cross-validation (don't shuffle — order matters!)
    tscv = TimeSeriesSplit(n_splits=5)
    scores = []

    for train_idx, val_idx in tscv.split(X):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        model = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        preds = model.predict(X_val)
        scores.append(accuracy_score(y_val, preds))

    avg_accuracy = sum(scores) / len(scores)
    print(f"[ML] Cross-val accuracy: {avg_accuracy:.2%} (over 5 folds)")

    # Final model on all data
    final_model = XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
        random_state=42, n_jobs=-1,
    )
    final_model.fit(X, y, verbose=False)

    # Save model + metadata
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)
    model_path = models_dir / f"{ticker.upper()}.joblib"
    meta_path = models_dir / f"{ticker.upper()}_meta.json"

    joblib.dump({"model": final_model, "feature_cols": feature_cols}, model_path)

    importances = dict(zip(feature_cols, final_model.feature_importances_.tolist()))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]

    meta = {
        "ticker": ticker.upper(),
        "days_trained": days,
        "samples": len(X),
        "accuracy_cv": round(avg_accuracy, 4),
        "top_features": top_features,
        "model_path": str(model_path),
    }

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"[ML] Model saved to {model_path}")
    return meta
