"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Search, X, TrendingUp, Plus } from "lucide-react";
import { searchSymbols, getQuote, type SearchResult } from "@/lib/api";

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

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function StockSearch({ onAdd }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [quantity, setQuantity] = useState("1");
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quotePrice, setQuotePrice] = useState<number | null>(null);
  const [quoteCurrency, setQuoteCurrency] = useState("USD");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const debouncedQuery = useDebounce(query, 200); // 200ms debounce for snappy feel

  // Fetch suggestions whenever debounced query changes
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    searchSymbols(debouncedQuery)
      .then((res) => {
        setResults(res);
        setOpen(res.length > 0);
      })
      .finally(() => setLoading(false));
  }, [debouncedQuery]);

  // When a symbol is selected, fetch its current price
  useEffect(() => {
    if (!selected) return;
    setQuoteLoading(true);
    setQuotePrice(null);
    getQuote(selected.symbol)
      .then((q) => {
        if (q) {
          setQuotePrice(q.price);
          setQuoteCurrency(q.currency || "USD");
        }
      })
      .finally(() => setQuoteLoading(false));
  }, [selected]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSelect = useCallback((r: SearchResult) => {
    setSelected(r);
    setQuery(r.symbol);
    setOpen(false);
  }, []);

  const handleAdd = () => {
    if (!selected || !quotePrice) return;
    const qty = parseFloat(quantity);
    if (isNaN(qty) || qty <= 0) return;
    onAdd({
      symbol: selected.symbol,
      name: selected.name,
      quantity: qty,
      price: quotePrice,
      currency: quoteCurrency,
    });
    setQuery("");
    setSelected(null);
    setQuantity("1");
    setQuotePrice(null);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && results.length > 0 && !selected) {
      handleSelect(results[0]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="w-full">
      {/* Search input */}
      <div className="relative">
        <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus-within:border-violet-500 transition-colors">
          <Search className="w-4 h-4 text-gray-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (selected) setSelected(null);
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => results.length > 0 && setOpen(true)}
            placeholder="Search ticker or company name... (e.g. AAPL, Reliance)"
            className="flex-1 bg-transparent text-white placeholder-gray-500 outline-none text-sm"
          />
          {loading && (
            <span className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin shrink-0" />
          )}
          {query && (
            <button
              onClick={() => { setQuery(""); setSelected(null); setResults([]); setOpen(false); }}
              className="text-gray-500 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Dropdown */}
        {open && (
          <div
            ref={dropdownRef}
            className="absolute top-full mt-1 left-0 right-0 bg-[#1a1a2e] border border-white/10 rounded-xl shadow-xl z-50 overflow-hidden"
          >
            {results.map((r) => (
              <button
                key={r.symbol}
                onClick={() => handleSelect(r)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition-colors text-left"
              >
                <TrendingUp className="w-4 h-4 text-violet-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-white text-sm">{r.symbol}</span>
                    <span className="text-xs text-gray-500 bg-white/5 px-1.5 py-0.5 rounded">{r.exchange}</span>
                    {r.type !== "EQUITY" && (
                      <span className="text-xs text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded">{r.type}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 truncate">{r.name}</p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Selected stock — add to portfolio */}
      {selected && (
        <div className="mt-3 flex items-center gap-3 bg-violet-500/10 border border-violet-500/30 rounded-xl px-4 py-3">
          <div className="flex-1">
            <span className="font-mono font-semibold text-white">{selected.symbol}</span>
            <span className="text-gray-400 text-sm ml-2">{selected.name}</span>
            {quoteLoading ? (
              <span className="text-xs text-gray-500 ml-2">Loading price...</span>
            ) : quotePrice ? (
              <span className="text-sm text-green-400 ml-2">{quoteCurrency} {quotePrice.toFixed(2)}</span>
            ) : null}
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400">Qty</label>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              min="0.001"
              step="1"
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              className="w-20 bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-sm text-white text-center outline-none focus:border-violet-500"
            />
            <button
              onClick={handleAdd}
              disabled={!quotePrice || isNaN(parseFloat(quantity))}
              className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
