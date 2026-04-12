from __future__ import annotations

from .registry import ToolRegistry, tool
from ..data.provider import get_provider


@tool
def get_earnings(ticker: str) -> str:
    """Get earnings history (EPS beats/misses) and upcoming earnings date for a stock."""
    ticker = ticker.upper().strip()
    provider = get_provider()
    earnings = provider.get_earnings(ticker)

    lines = [f"=== Earnings: {ticker} ==="]

    if not earnings:
        return f"No earnings data available for '{ticker}'."

    lines.append("\n--- EPS History (last 4 quarters) ---")
    for e in earnings:
        actual = e.get("eps_actual")
        estimate = e.get("eps_estimate")
        surprise = e.get("surprise_pct")

        if surprise is not None:
            beat = "BEAT" if surprise > 0 else ("MISS" if surprise < 0 else "MET")
            surprise_str = f"{beat} ({surprise:+.1f}%)"
        else:
            surprise_str = "N/A"

        lines.append(
            f"  {str(e.get('period', 'N/A')):15}  "
            f"Est: {str(estimate or 'N/A'):8}  "
            f"Act: {str(actual or 'N/A'):8}  "
            f"{surprise_str}"
        )

    return "\n".join(lines)


ToolRegistry.register(get_earnings)
