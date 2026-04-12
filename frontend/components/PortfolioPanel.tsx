"use client";

import { useState } from "react";
import { Trash2, TrendingUp, TrendingDown, Minus, ExternalLink } from "lucide-react";
import StockSearch, { type PortfolioEntry } from "./StockSearch";

export default function PortfolioPanel() {
  const [portfolio, setPortfolio] = useState<PortfolioEntry[]>([]);

  const addStock = (entry: PortfolioEntry) => {
    setPortfolio((prev) => {
      const existing = prev.find((s) => s.symbol === entry.symbol);
      if (existing) {
        return prev.map((s) =>
          s.symbol === entry.symbol
            ? { ...s, quantity: s.quantity + entry.quantity }
            : s
        );
      }
      return [...prev, entry];
    });
  };

  const removeStock = (symbol: string) => {
    setPortfolio((prev) => prev.filter((s) => s.symbol !== symbol));
  };

  const updateQty = (symbol: string, qty: number) => {
    if (qty <= 0) return removeStock(symbol);
    setPortfolio((prev) =>
      prev.map((s) => (s.symbol === symbol ? { ...s, quantity: qty } : s))
    );
  };

  const totalValue = portfolio.reduce((sum, s) => sum + s.price * s.quantity, 0);

  const analyzePortfolio = () => {
    const summary = portfolio
      .map((s) => `${s.symbol}: ${s.quantity} shares @ ${s.currency} ${s.price.toFixed(2)}`)
      .join(", ");
    // Dispatch a custom event to prefill the chat
    window.dispatchEvent(
      new CustomEvent("portfolioiq:analyze", { detail: `Analyze my portfolio: ${summary}` })
    );
  };

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      <StockSearch onAdd={addStock} />

      {portfolio.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
          Add stocks above to build your portfolio
        </div>
      ) : (
        <>
          {/* Holdings list */}
          <div className="flex-1 overflow-y-auto space-y-2">
            {portfolio.map((s) => {
              const value = s.price * s.quantity;
              const pct = (value / totalValue) * 100;
              return (
                <div
                  key={s.symbol}
                  className="bg-white/5 border border-white/10 rounded-xl px-4 py-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-white">{s.symbol}</span>
                        <span className="text-xs text-gray-500 truncate">{s.name}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-gray-400">
                          {s.currency} {s.price.toFixed(2)}
                        </span>
                        <span className="text-xs text-gray-500">×</span>
                        <input
                          type="number"
                          value={s.quantity}
                          onChange={(e) => updateQty(s.symbol, parseFloat(e.target.value))}
                          min="0.001"
                          step="1"
                          className="w-16 bg-white/5 border border-white/10 rounded px-2 py-0.5 text-xs text-white text-center outline-none focus:border-violet-500"
                        />
                        <span className="text-xs text-gray-400">= {s.currency} {value.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <div className="text-sm font-medium text-white">
                          {pct.toFixed(1)}%
                        </div>
                        <div className="h-1.5 w-16 bg-white/10 rounded-full mt-1">
                          <div
                            className="h-full bg-violet-500 rounded-full"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                      <button
                        onClick={() => removeStock(s.symbol)}
                        className="text-gray-600 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Summary */}
          <div className="border-t border-white/10 pt-4 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Total Portfolio Value</span>
              <span className="font-semibold text-white text-lg">
                ${totalValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </span>
            </div>
            <button
              onClick={analyzePortfolio}
              className="w-full bg-violet-600 hover:bg-violet-500 text-white py-2.5 rounded-xl text-sm font-medium transition-colors"
            >
              Analyze Portfolio with AI
            </button>
          </div>
        </>
      )}
    </div>
  );
}
