"use client";

import { useState, useEffect, useCallback } from "react";
import { Minus, Plus } from "lucide-react";
import TickerAutocomplete from "./TickerAutocomplete";
import { getQuote, type SearchResult } from "@/lib/api";

export interface PortfolioEntry {
  symbol: string;
  name: string;
  quantity: number;
  price: number;
  currency: string;
}

interface Props {
  onAdd: (entry: PortfolioEntry) => void;
}

export default function StockSearch({ onAdd }: Props) {
  const [ticker, setTicker] = useState("");
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quotePrice, setQuotePrice] = useState<number | null>(null);
  const [quoteCurrency, setQuoteCurrency] = useState("USD");

  useEffect(() => {
    if (!selected) { setQuotePrice(null); return; }
    setQuoteLoading(true);
    getQuote(selected.symbol)
      .then((q) => {
        if (q) { setQuotePrice(q.price); setQuoteCurrency(q.currency || "USD"); }
      })
      .finally(() => setQuoteLoading(false));
  }, [selected]);

  const handleSelect = useCallback((symbol: string, result?: SearchResult) => {
    setTicker(symbol);
    if (result) setSelected(result);
    else setSelected(null);
  }, []);

  const handleAdd = useCallback(() => {
    if (!selected || !quotePrice || quantity <= 0) return;
    onAdd({
      symbol: selected.symbol,
      name: selected.name,
      quantity,
      price: quotePrice,
      currency: quoteCurrency,
    });
    setTicker("");
    setSelected(null);
    setQuantity(1);
    setQuotePrice(null);
  }, [selected, quotePrice, quantity, quoteCurrency, onAdd]);

  const adjustQty = (delta: number) => {
    setQuantity((q) => Math.max(1, q + delta));
  };

  return (
    <div className="space-y-2">
      <TickerAutocomplete
        value={ticker}
        onChange={handleSelect}
        placeholder="Search ticker or company name… (e.g. AAPL, Reliance, Gold ETF)"
      />

      {selected && (
        <div className="flex items-center gap-3 bg-violet-500/10 border border-violet-500/30 rounded-xl px-4 py-3">
          <div className="flex-1 min-w-0">
            <span className="font-mono font-semibold text-white">{selected.symbol}</span>
            <span className="text-gray-400 text-sm ml-2 truncate">{selected.name}</span>
            {quoteLoading ? (
              <span className="text-xs text-gray-500 ml-2">Loading price…</span>
            ) : quotePrice != null ? (
              <span className="text-sm text-emerald-400 ml-2 font-medium">
                {quoteCurrency} {quotePrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => adjustQty(-1)}
              className="w-7 h-7 flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 transition-colors"
            >
              <Minus className="w-3.5 h-3.5" />
            </button>
            <input
              type="number"
              value={quantity}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (!isNaN(v) && v >= 1) setQuantity(v);
              }}
              min={1}
              className="w-12 bg-white/5 border border-white/10 rounded-lg text-sm text-white text-center outline-none focus:border-violet-500 py-1"
            />
            <button
              onClick={() => adjustQty(1)}
              className="w-7 h-7 flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          <button
            onClick={handleAdd}
            disabled={!quotePrice || quantity < 1}
            className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-1.5 rounded-lg text-sm font-medium transition-colors shrink-0"
          >
            <Plus className="w-4 h-4" />
            Add
          </button>
        </div>
      )}
    </div>
  );
}
