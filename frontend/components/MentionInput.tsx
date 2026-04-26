"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { searchSymbols, type SearchResult } from "@/lib/api";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  placeholder?: string;
  className?: string;
  rows?: number;
  disabled?: boolean;
}

const DEBOUNCE_MS = 220;

export default function MentionInput({
  value, onChange, onKeyDown, placeholder, className, rows = 1, disabled
}: Props) {
  const [suggestions, setSuggestions] = useState<SearchResult[]>([]);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Find the active @mention being typed
  const getActiveMention = useCallback((text: string, cursor: number) => {
    const before = text.slice(0, cursor);
    const match = before.match(/@([\w.]*)$/);
    return match ? { query: match[1], start: cursor - match[0].length } : null;
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const rawText = e.target.value;
    const cursor = e.target.selectionStart ?? rawText.length;
    const text = rawText.replace(/@([\w.]*)/g, (_, ticker: string) => `@${ticker.toUpperCase()}`);
    onChange(text);
    if (text !== rawText) {
      setTimeout(() => {
        textareaRef.current?.setSelectionRange(cursor, cursor);
      }, 0);
    }

    const mention = getActiveMention(text, cursor);
    if (mention) {
      const query = mention.query.toUpperCase();
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        const results = await searchSymbols(query || " ");
        setSuggestions(results.slice(0, 6));
        setActiveIdx(0);
        // Position dropdown near cursor (approximate)
        if (textareaRef.current && containerRef.current) {
          const rect = containerRef.current.getBoundingClientRect();
          setMenuPos({ top: rect.height, left: 0 });
        }
      }, DEBOUNCE_MS);
    } else {
      setSuggestions([]);
      setMenuPos(null);
    }
  };

  const selectSuggestion = useCallback((symbol: string) => {
    if (!textareaRef.current) return;
    const currentValue = textareaRef.current.value;
    const cursor = textareaRef.current.selectionStart ?? currentValue.length;
    const mention = getActiveMention(currentValue, cursor);
    if (!mention) return;
    const newText = currentValue.slice(0, mention.start) + `@${symbol} ` + currentValue.slice(cursor);
    onChange(newText);
    setSuggestions([]);
    setMenuPos(null);
    setTimeout(() => {
      textareaRef.current?.focus();
      const pos = mention.start + symbol.length + 2;
      textareaRef.current?.setSelectionRange(pos, pos);
    }, 0);
  }, [onChange, getActiveMention]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        if (suggestions[activeIdx]) {
          e.preventDefault();
          selectSuggestion(suggestions[activeIdx].symbol);
          return;
        }
      }
      if (e.key === "Escape") {
        setSuggestions([]);
        setMenuPos(null);
        return;
      }
    }
    onKeyDown?.(e);
  };

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSuggestions([]);
        setMenuPos(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={containerRef} className="relative flex-1">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        className={className}
        style={{ fieldSizing: "content" } as React.CSSProperties}
      />
      {suggestions.length > 0 && menuPos && (
        <div
          className="absolute z-50 bg-[#1a1a2e] border border-white/10 rounded-xl shadow-2xl overflow-hidden w-64"
          style={{ bottom: "calc(100% + 4px)", left: 0 }}
        >
          {suggestions.map((s, i) => (
            <button
              key={s.symbol}
              onMouseDown={(e) => { e.preventDefault(); selectSuggestion(s.symbol); }}
              className={`w-full text-left px-3 py-2.5 flex items-center gap-2.5 transition-colors ${
                i === activeIdx ? "bg-violet-600/30" : "hover:bg-white/5"
              }`}
            >
              <span className="font-mono font-semibold text-sm text-white w-16 shrink-0">{s.symbol}</span>
              <span className="text-xs text-gray-400 truncate">{s.name}</span>
              <span className="text-xs text-gray-600 ml-auto shrink-0">{s.exchange}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
