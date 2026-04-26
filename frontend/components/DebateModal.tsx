"use client";

import { useEffect, useRef, useState } from "react";
import { X, TrendingUp, TrendingDown, Activity, Search, AlertCircle } from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import type { DebateEvent, DebateVerdict } from "@/lib/api";

interface Round {
  round: number;
  bull: string;
  bear: string;
}

interface ChartSpec {
  chart_type: string;
  title: string;
  data: Record<string, unknown>[];
  x_key?: string;
  y_key?: string;
  color?: string;
}

interface Props {
  ticker: string;
  eventStream: AsyncGenerator<DebateEvent> | null;
  storedDebate?: {
    rounds_data: Round[];
    charts_data: ChartSpec[];
    verdict: DebateVerdict;
    portfolio_recommendation?: string;
    web_searches?: string[];
  } | null;
  onClose: () => void;
  onDone?: (debateId: string, verdict: string, confidence: number) => void;
}

const VERDICT_COLOR: Record<string, string> = {
  "Strong Buy": "#10b981",
  "Buy": "#34d399",
  "Hold": "#f59e0b",
  "Sell": "#f87171",
  "Strong Sell": "#ef4444",
};

function VerdictBadge({ verdict, confidence }: { verdict: string; confidence: number }) {
  const color = VERDICT_COLOR[verdict] || "#94a3b8";
  return (
    <div className="flex items-center gap-3">
      <span
        className="px-3 py-1 rounded-full text-sm font-bold"
        style={{ background: `${color}20`, color }}
      >
        {verdict}
      </span>
      <div className="flex items-center gap-1.5">
        <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${confidence}%`, background: color }}
          />
        </div>
        <span className="text-xs text-gray-400">{confidence}%</span>
      </div>
    </div>
  );
}

export default function DebateModal({ ticker, eventStream, storedDebate, onClose, onDone }: Props) {
  const [logs, setLogs] = useState<string[]>([]);
  const [rounds, setRounds] = useState<Round[]>([]);
  const [charts, setCharts] = useState<ChartSpec[]>([]);
  const [verdict, setVerdict] = useState<DebateVerdict | null>(null);
  const [portfolioRec, setPortfolioRec] = useState<string | null>(null);
  const [webSearches, setWebSearches] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [pendingRound, setPendingRound] = useState<Partial<Round> | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const logBottomRef = useRef<HTMLDivElement>(null);
  const latestVerdict = useRef<DebateVerdict | null>(null);

  // Load stored debate
  useEffect(() => {
    if (storedDebate) {
      setRounds(storedDebate.rounds_data || []);
      setCharts(storedDebate.charts_data || []);
      setVerdict(storedDebate.verdict || null);
      setPortfolioRec(storedDebate.portfolio_recommendation || null);
      setWebSearches(storedDebate.web_searches || []);
      setDone(true);
    }
  }, [storedDebate]);

  // Stream live debate
  useEffect(() => {
    if (!eventStream) return;
    let cancelled = false;

    (async () => {
      for await (const event of eventStream) {
        if (cancelled) break;
        if (event.type === "log") {
          setLogs((prev) => [...prev, event.message]);
        } else if (event.type === "bull") {
          setPendingRound((prev) => ({ ...prev, round: event.round, bull: event.text }));
        } else if (event.type === "bear") {
          const r = event.round;
          const bearText = event.text;
          setPendingRound((prev) => {
            const complete: Round = { round: r, bull: prev?.bull ?? "", bear: bearText };
            setRounds((rs) => [...rs.filter(x => x.round !== r), complete].sort((a,b) => a.round - b.round));
            return null;
          });
        } else if (event.type === "chart") {
          const { type: _, ...chartSpec } = event as DebateEvent & { type: "chart" };
          setCharts((prev) => [...prev, chartSpec as ChartSpec]);
        } else if (event.type === "verdict") {
          latestVerdict.current = event.data;
          setVerdict(event.data);
        } else if (event.type === "portfolio_rec") {
          setPortfolioRec(event.text);
        } else if (event.type === "done") {
          setDone(true);
          setLogs((prev) => [...prev, "✅ Debate complete."]);
          onDone?.(event.debate_id, latestVerdict.current?.verdict ?? "Hold", latestVerdict.current?.confidence ?? 50);
        } else if (event.type === "error") {
          setLogs((prev) => [...prev, `❌ Error: ${event.message}`]);
          setDone(true);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [eventStream]);

  // Auto-scroll
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [rounds, pendingRound]);
  useEffect(() => {
    logBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const allMessages: Array<{ side: "bull" | "bear"; round: number; text: string }> = [];
  for (const r of rounds) {
    allMessages.push({ side: "bull", round: r.round, text: r.bull });
    allMessages.push({ side: "bear", round: r.round, text: r.bear });
  }
  if (pendingRound?.bull && !pendingRound?.bear) {
    allMessages.push({ side: "bull", round: pendingRound.round ?? 0, text: pendingRound.bull });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-[#0f0f20] border border-white/10 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/8 shrink-0">
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5 text-violet-400" />
            <span className="font-semibold text-white">{ticker} — Bull vs Bear</span>
            {verdict && <VerdictBadge verdict={verdict.verdict} confidence={verdict.confidence} />}
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto">

          {/* Progress log (while running) */}
          {!done && logs.length > 0 && (
            <div className="px-5 pt-4 pb-2">
              <div className="bg-black/40 border border-white/5 rounded-xl p-3 max-h-28 overflow-y-auto">
                {logs.map((l, i) => (
                  <div key={i} className="text-xs text-gray-400 font-mono leading-relaxed">{l}</div>
                ))}
                <div ref={logBottomRef} />
              </div>
            </div>
          )}

          {/* Web searches badge */}
          {done && webSearches.length > 0 && (
            <div className="px-5 pt-3 flex flex-wrap gap-2">
              {webSearches.slice(0, 4).map((s, i) => (
                <span key={i} className="flex items-center gap-1 text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded-full">
                  <Search className="w-3 h-3" />
                  {s.replace(/^(Tavily|Gemini Search \(\w+ R\d+\)): /, "").slice(0, 50)}
                </span>
              ))}
            </div>
          )}

          {/* Debate chat */}
          <div className="px-5 py-4 space-y-3">
            {allMessages.map((msg, idx) => {
              const isBull = msg.side === "bull";
              return (
                <div key={idx} className={`flex gap-2.5 ${isBull ? "" : "flex-row-reverse"}`}>
                  {/* Avatar */}
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${
                    isBull ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                  }`}>
                    {isBull ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                  </div>
                  {/* Bubble */}
                  <div className={`flex-1 max-w-[82%] ${isBull ? "" : "items-end flex flex-col"}`}>
                    <div className={`text-[10px] font-medium mb-0.5 ${isBull ? "text-emerald-400" : "text-red-400"} ${isBull ? "" : "text-right"}`}>
                      {isBull ? "Marcus • Bull" : "Priya • Bear"} · R{msg.round}
                    </div>
                    <div className={`text-sm text-gray-200 leading-relaxed px-3.5 py-2.5 rounded-2xl ${
                      isBull
                        ? "bg-emerald-500/10 border border-emerald-500/15 rounded-tl-sm"
                        : "bg-red-500/10 border border-red-500/15 rounded-tr-sm"
                    }`}>
                      {msg.text}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Typing indicator */}
            {!done && (
              <div className="flex gap-2 items-center text-gray-500 text-sm">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-gray-600 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-1.5 h-1.5 bg-gray-600 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-1.5 h-1.5 bg-gray-600 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-xs">{logs[logs.length - 1] ?? "Processing..."}</span>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Charts */}
          {charts.length > 0 && (
            <div className="px-5 pb-4 space-y-4">
              {charts.map((chart, i) => (
                <div key={i} className="bg-white/3 border border-white/8 rounded-xl p-4">
                  <p className="text-sm font-medium text-gray-300 mb-3">{chart.title}</p>
                  {chart.chart_type === "price" && (
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={chart.data as Record<string, unknown>[]}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis
                          dataKey={chart.x_key ?? "date"}
                          tick={{ fontSize: 10, fill: "#64748b" }}
                          tickFormatter={(v: string) => v?.slice(5) ?? ""}
                          interval="preserveStartEnd"
                        />
                        <YAxis
                          tick={{ fontSize: 10, fill: "#64748b" }}
                          domain={["auto", "auto"]}
                          width={50}
                        />
                        <Tooltip
                          contentStyle={{ background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 }}
                          labelStyle={{ color: "#94a3b8" }}
                        />
                        <Line
                          type="monotone"
                          dataKey={chart.y_key ?? "close"}
                          stroke={chart.color ?? "#8b5cf6"}
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                  {chart.chart_type === "earnings" && (
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={chart.data as Record<string, unknown>[]}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="period" tick={{ fontSize: 10, fill: "#64748b" }} />
                        <YAxis tick={{ fontSize: 10, fill: "#64748b" }} width={45} />
                        <Tooltip
                          contentStyle={{ background: "#1a1a2e", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, fontSize: 12 }}
                        />
                        <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
                        <Bar dataKey="estimate" fill="#6366f1" radius={[3,3,0,0]} name="EPS Est." />
                        <Bar dataKey="actual" fill="#10b981" radius={[3,3,0,0]} name="EPS Actual" />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Verdict */}
          {verdict && (
            <div className="mx-5 mb-4 bg-white/3 border border-white/10 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-widest text-gray-500">Verdict</span>
                <VerdictBadge verdict={verdict.verdict} confidence={verdict.confidence} />
              </div>
              <p className="text-sm text-gray-200">{verdict.recommendation}</p>
              {verdict.key_factors?.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {verdict.key_factors.map((f, i) => (
                    <span key={i} className="text-xs bg-violet-500/10 text-violet-300 border border-violet-500/20 px-2 py-0.5 rounded-full">{f}</span>
                  ))}
                </div>
              )}
              <p className="text-xs text-gray-600">{verdict.disclaimer}</p>
            </div>
          )}

          {/* Portfolio recommendation */}
          {portfolioRec && (
            <div className="mx-5 mb-5 bg-amber-500/8 border border-amber-500/20 rounded-xl p-4 flex gap-3">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-amber-400 mb-1">Portfolio Fit</p>
                <p className="text-sm text-gray-200">{portfolioRec}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
