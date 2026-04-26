"use client";

import { useState } from "react";
import { TrendingUp, TrendingDown, Scale, Loader2, AlertCircle } from "lucide-react";
import { runDebate, type DebateResult } from "@/lib/api";
import TickerAutocomplete from "./TickerAutocomplete";

export default function DebatePanel() {
  const [ticker, setTicker] = useState("");
  const [rounds, setRounds] = useState(3);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DebateResult | null>(null);
  const [error, setError] = useState("");
  const [activeRound, setActiveRound] = useState(0);

  const startDebate = async () => {
    if (!ticker.trim() || loading) return;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const r = await runDebate(ticker.trim().toUpperCase(), rounds);
      setResult(r);
      setActiveRound(0);
    } catch {
      setError("Failed to run debate. Make sure the backend is running and the ticker is valid.");
    } finally {
      setLoading(false);
    }
  };

  const verdictColor = (v: string) => {
    if (v?.includes("Buy")) return "text-emerald-400";
    if (v?.includes("Sell")) return "text-red-400";
    return "text-yellow-400";
  };

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      {/* Input row */}
      <div className="flex gap-2">
        <TickerAutocomplete
          value={ticker}
          onChange={(sym) => setTicker(sym)}
          placeholder="Search ticker… (e.g. AAPL, TSLA, RELIANCE.NS)"
          className="flex-1"
        />
        <select
          value={rounds}
          onChange={(e) => setRounds(parseInt(e.target.value))}
          className="bg-white/5 border border-white/10 rounded-xl px-3 text-sm text-white outline-none focus:border-violet-500 shrink-0"
        >
          {[1, 2, 3, 4, 5].map((r) => (
            <option key={r} value={r} className="bg-[#1a1a2e]">{r} round{r > 1 ? "s" : ""}</option>
          ))}
        </select>
        <button
          onClick={startDebate}
          disabled={!ticker.trim() || loading}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl text-sm font-medium transition-colors shrink-0"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scale className="w-4 h-4" />}
          {loading ? "Debating…" : "Debate"}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {loading && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 text-gray-400">
          <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
          <p className="text-sm">Running {rounds}-round debate on {ticker}…</p>
          <p className="text-xs text-gray-600">Fetching real data, building arguments, judging…</p>
        </div>
      )}

      {result && !loading && (
        <div className="flex-1 overflow-y-auto space-y-4">
          {/* Verdict card */}
          <div className="bg-gradient-to-br from-violet-900/40 to-indigo-900/40 border border-violet-500/30 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-white">Moderator Verdict — {result.ticker}</h3>
              <span className={`text-lg font-bold ${verdictColor(result.verdict?.verdict)}`}>
                {result.verdict?.verdict}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="bg-white/5 rounded-xl p-3">
                <div className="text-xs text-gray-400 mb-1">Confidence</div>
                <div className="text-white font-semibold">{result.verdict?.confidence}%</div>
                <div className="h-1.5 bg-white/10 rounded-full mt-2">
                  <div
                    className="h-full bg-violet-500 rounded-full transition-all"
                    style={{ width: `${result.verdict?.confidence}%` }}
                  />
                </div>
              </div>
              <div className="bg-white/5 rounded-xl p-3">
                <div className="text-xs text-gray-400 mb-1">Stronger Case</div>
                <div className={`font-semibold capitalize ${
                  result.verdict?.stronger_case === "bull" ? "text-emerald-400"
                  : result.verdict?.stronger_case === "bear" ? "text-red-400"
                  : "text-yellow-400"
                }`}>
                  {result.verdict?.stronger_case}
                </div>
              </div>
            </div>
            {result.verdict?.key_factors?.length > 0 && (
              <div className="mb-3">
                <div className="text-xs text-gray-400 mb-2">Key Factors</div>
                <ul className="space-y-1">
                  {result.verdict.key_factors.map((f, i) => (
                    <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                      <span className="text-violet-400 mt-0.5">•</span>{f}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {result.verdict?.recommendation && (
              <p className="text-sm text-gray-300 border-t border-white/10 pt-3">
                {result.verdict.recommendation}
              </p>
            )}
          </div>

          {/* Round navigation */}
          {result.bull_arguments.length > 1 && (
            <div className="flex gap-1">
              {result.bull_arguments.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setActiveRound(i)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    activeRound === i ? "bg-violet-600 text-white" : "bg-white/5 text-gray-400 hover:bg-white/10"
                  }`}
                >
                  Round {i + 1}
                </button>
              ))}
            </div>
          )}

          {/* Split-screen debate */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-emerald-900/20 border border-emerald-500/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium text-emerald-400">Bull Case</span>
                <span className="text-xs text-gray-500 ml-auto">Round {activeRound + 1}</span>
              </div>
              <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                {result.bull_arguments[activeRound]}
              </p>
            </div>
            <div className="bg-red-900/20 border border-red-500/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <TrendingDown className="w-4 h-4 text-red-400" />
                <span className="text-sm font-medium text-red-400">Bear Case</span>
                <span className="text-xs text-gray-500 ml-auto">Round {activeRound + 1}</span>
              </div>
              <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                {result.bear_arguments[activeRound]}
              </p>
            </div>
          </div>

          {/* Summaries */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="text-xs text-emerald-400 mb-2">Bull Summary</div>
              <p className="text-sm text-gray-300">{result.verdict?.bull_summary}</p>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="text-xs text-red-400 mb-2">Bear Summary</div>
              <p className="text-sm text-gray-300">{result.verdict?.bear_summary}</p>
            </div>
          </div>

          <p className="text-xs text-gray-600 text-center pb-2">{result.verdict?.disclaimer}</p>
        </div>
      )}

      {!result && !loading && !error && (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-gray-600">
          <Scale className="w-8 h-8" />
          <p className="text-sm">Enter a ticker and start a bull vs bear debate</p>
          <p className="text-xs">Two AI agents argue both sides with real data. A moderator judges.</p>
        </div>
      )}
    </div>
  );
}
