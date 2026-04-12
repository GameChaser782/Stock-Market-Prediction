from __future__ import annotations

from .registry import ToolRegistry, tool
from ..data.provider import get_provider
from .stock_lookup import _fmt


@tool
def get_fundamentals(ticker: str) -> str:
    """Get fundamental financial data: P/E ratio, revenue, margins, debt, EPS, and growth metrics."""
    provider = get_provider()
    ticker = ticker.upper().strip()
    m = provider.get_fundamentals(ticker)

    if not m:
        return f"No fundamental data found for '{ticker}'. Make sure the ticker is correct."

    def pct(v):
        return f"{float(v)*100:.2f}%" if v is not None else "N/A"

    def val(v, fmt=".2f"):
        return f"{v:{fmt}}" if v is not None else "N/A"

    lines = [f"=== Fundamentals: {ticker} ==="]

    lines.append("\n--- Valuation ---")
    lines.append(f"P/E (TTM):        {val(m.get('pe_ttm'))}")
    lines.append(f"Forward P/E:      {val(m.get('pe_forward'))}")
    lines.append(f"P/B Ratio:        {val(m.get('pb_ratio'))}")
    lines.append(f"P/S Ratio:        {val(m.get('ps_ratio'))}")
    lines.append(f"EV/EBITDA:        {val(m.get('ev_ebitda'))}")

    lines.append("\n--- Profitability ---")
    lines.append(f"Gross Margin:     {pct(m.get('gross_margin'))}")
    lines.append(f"Operating Margin: {pct(m.get('operating_margin'))}")
    lines.append(f"Net Margin:       {pct(m.get('net_margin'))}")
    lines.append(f"ROE:              {pct(m.get('roe'))}")
    lines.append(f"ROA:              {pct(m.get('roa'))}")

    lines.append("\n--- Growth ---")
    lines.append(f"Revenue (TTM):    {_fmt(m.get('revenue_ttm'))}")
    lines.append(f"Revenue Growth:   {pct(m.get('revenue_growth_1y'))}")
    lines.append(f"EPS (TTM):        {val(m.get('eps_ttm'))}")
    lines.append(f"EPS Growth:       {pct(m.get('eps_growth_1y'))}")

    lines.append("\n--- Balance Sheet ---")
    lines.append(f"Debt/Equity:      {val(m.get('debt_equity'))}")
    lines.append(f"Current Ratio:    {val(m.get('current_ratio'))}")
    lines.append(f"Free Cash Flow:   {_fmt(m.get('free_cash_flow'))}")

    lines.append("\n--- Market ---")
    lines.append(f"Beta:             {val(m.get('beta'))}")
    lines.append(f"52W High:         {val(m.get('week_52_high'))}")
    lines.append(f"52W Low:          {val(m.get('week_52_low'))}")
    div = m.get('dividend_yield')
    if div:
        lines.append(f"Dividend Yield:   {pct(div)}")

    return "\n".join(lines)


ToolRegistry.register(get_fundamentals)
