"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Search, X, TrendingUp } from "lucide-react";
import { searchSymbols, type SearchResult } from "@/lib/api";

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

interface Props {
  value: string;
  onChange: (symbol: string, result?: SearchResult) => void;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
  autoFocus?: boolean;
}

export default function TickerAutocomplete({
  value,
  onChange,
  placeholder = "Search ticker or company name...",
  className = "",
  inputClassName = "",
  autoFocus = false,
}: Props) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const debouncedQuery = useDebounce(query, 220);

  // Sync external value changes
  useEffect(() => {
    setQuery(value);
  }, [value]);

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

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSelect = useCallback((r: SearchResult) => {
    setQuery(r.symbol);
    setOpen(false);
    onChange(r.symbol, r);
  }, [onChange]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && results.length > 0) {
      handleSelect(results[0]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const clear = () => {
    setQuery("");
    setResults([]);
    setOpen(false);
    onChange("");
    inputRef.current?.focus();
  };

  return (
    <div className={`relative ${className}`}>
      <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus-within:border-violet-500 transition-colors">
        <Search className="w-4 h-4 text-gray-400 shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          autoFocus={autoFocus}
          onChange={(e) => {
            setQuery(e.target.value.toUpperCase());
            onChange(e.target.value.toUpperCase());
          }}
          onKeyDown={handleKey}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder={placeholder}
          className={`flex-1 bg-transparent text-white placeholder-gray-500 outline-none text-sm font-mono ${inputClassName}`}
        />
        {loading && (
          <span className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin shrink-0" />
        )}
        {query && !loading && (
          <button onClick={clear} className="text-gray-500 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {open && (
        <div
          ref={dropdownRef}
          className="absolute top-full mt-1 left-0 right-0 bg-[#1a1a2e] border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden"
        >
          {results.map((r) => (
            <button
              key={r.symbol}
              onMouseDown={(e) => { e.preventDefault(); handleSelect(r); }}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-white/5 transition-colors text-left"
            >
              <TrendingUp className="w-3.5 h-3.5 text-violet-400 shrink-0" />
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
  );
}
