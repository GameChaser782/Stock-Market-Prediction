"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Trash2, Minus, Plus, TrendingUp, Activity, BriefcaseBusiness, ShieldAlert } from "lucide-react";
import StockSearch, { type PortfolioEntry } from "./StockSearch";
import { getStockSnapshots, type StockSnapshot } from "@/lib/api";

function currencyTotals(portfolio: PortfolioEntry[]): Record<string, number> {
  return portfolio.reduce<Record<string, number>>((acc, s) => {
    const cur = s.currency || "USD";
    acc[cur] = (acc[cur] || 0) + s.price * s.quantity;
    return acc;
  }, {});
}

function fmt(n: number) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtSigned(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "N/A";
  const abs = Math.abs(n);
  const prefix = n > 0 ? "+" : n < 0 ? "-" : "";
  return `${prefix}${fmt(abs)}`;
}

function fmtPct(n?: number | null) {
  if (n == null || Number.isNaN(n)) return "N/A";
  const abs = Math.abs(n);
  const prefix = n > 0 ? "+" : n < 0 ? "-" : "";
  return `${prefix}${abs.toFixed(2)}%`;
}

function pillTone(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "bg-white/5 text-gray-400";
  if (value > 0) return "bg-emerald-500/15 text-emerald-400";
  if (value < 0) return "bg-red-500/15 text-red-400";
  return "bg-white/5 text-gray-300";
}

interface Props {
  portfolio: PortfolioEntry[];
  onPortfolioChange: (p: PortfolioEntry[]) => void;
}

export default function PortfolioPanel({ portfolio, onPortfolioChange }: Props) {
  const [snapshots, setSnapshots] = useState<Record<string, StockSnapshot>>({});

  const addStock = useCallback((entry: PortfolioEntry) => {
    onPortfolioChange(
      portfolio.find((s) => s.symbol === entry.symbol)
        ? portfolio.map((s) =>
            s.symbol === entry.symbol ? { ...s, quantity: s.quantity + entry.quantity } : s
          )
        : [...portfolio, entry]
    );
  }, [portfolio, onPortfolioChange]);

  const removeStock = useCallback((symbol: string) => {
    onPortfolioChange(portfolio.filter((s) => s.symbol !== symbol));
  }, [portfolio, onPortfolioChange]);

  const setQty = useCallback((symbol: string, qty: number) => {
    if (qty < 1) return;
    onPortfolioChange(
      portfolio.map((s) => (s.symbol === symbol ? { ...s, quantity: qty } : s))
    );
  }, [portfolio, onPortfolioChange]);

  const totals = currencyTotals(portfolio);

  useEffect(() => {
    if (!portfolio.length) {
      Promise.resolve().then(() => setSnapshots({}));
      return;
    }
    let cancelled = false;
    getStockSnapshots(portfolio.map((stock) => stock.symbol))
      .then((items) => {
        if (cancelled) return;
        const mapped = Object.fromEntries(items.map((item) => [item.symbol, item]));
        setSnapshots(mapped);
      });
    return () => {
      cancelled = true;
    };
  }, [portfolio]);

  const analyzePortfolio = () => {
    if (!portfolio.length) return;
    const summary = portfolio
      .map((s) => `${s.symbol}: ${s.quantity} shares @ ${s.currency} ${fmt(s.price)}`)
      .join(", ");
    window.dispatchEvent(
      new CustomEvent("portfolioiq:analyze", { detail: `Analyze my portfolio: ${summary}` })
    );
  };

  const enrichedPortfolio = useMemo(() => {
    return portfolio.map((stock) => {
      const snapshot = snapshots[stock.symbol];
      const currentPrice = snapshot?.quote?.price ?? stock.price;
      const totalValue = currentPrice * stock.quantity;
      return {
        stock,
        snapshot,
        currentPrice,
        totalValue,
      };
    });
  }, [portfolio, snapshots]);

  const analytics = useMemo(() => {
    const grandTotal = enrichedPortfolio.reduce((sum, item) => sum + item.totalValue, 0) || 1;

    const bySector = new Map<string, number>();
    const byExchange = new Map<string, number>();
    let weightedRisk = 0;
    let weightedVolatility = 0;
    let volatilityWeight = 0;

    for (const item of enrichedPortfolio) {
      const sector = item.snapshot?.profile?.sector || "Unclassified";
      const exchange = item.snapshot?.profile?.exchange || item.snapshot?.quote?.ticker || "Unknown";
      bySector.set(sector, (bySector.get(sector) || 0) + item.totalValue);
      byExchange.set(exchange, (byExchange.get(exchange) || 0) + item.totalValue);

      const risk = item.snapshot?.metrics?.risk_score;
      if (risk != null) weightedRisk += risk * item.totalValue;

      const vol = item.snapshot?.metrics?.annualized_volatility_pct;
      if (vol != null) {
        weightedVolatility += vol * item.totalValue;
        volatilityWeight += item.totalValue;
      }
    }

    const sectors = Array.from(bySector.entries())
      .map(([name, value]) => ({ name, value, weight: (value / grandTotal) * 100 }))
      .sort((a, b) => b.value - a.value);
    const exchanges = Array.from(byExchange.entries())
      .map(([name, value]) => ({ name, value, weight: (value / grandTotal) * 100 }))
      .sort((a, b) => b.value - a.value);

    return {
      grandTotal,
      sectors,
      exchanges,
      weightedRiskScore: weightedRisk ? weightedRisk / grandTotal : null,
      weightedVolatility: volatilityWeight ? weightedVolatility / volatilityWeight : null,
    };
  }, [enrichedPortfolio]);

  const analyticsLoading = portfolio.length > 0 && enrichedPortfolio.some(({ snapshot }) => !snapshot);

  return (
    <div className="min-h-full p-4">
      <StockSearch onAdd={addStock} />

      {portfolio.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-gray-600 py-16">
          <TrendingUp className="w-8 h-8" />
          <p className="text-sm">Add stocks above to build your portfolio</p>
          <p className="text-xs">Select a session (top-right) to save your portfolio across restarts</p>
        </div>
      ) : (
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-2">
            {enrichedPortfolio.map(({ stock: s, snapshot, currentPrice, totalValue }) => {
              const dayChange = snapshot?.quote?.change;
              const dayChangePct = snapshot?.quote?.change_pct;
              const yearChange = snapshot?.metrics?.one_year_change;
              const yearChangePct = snapshot?.metrics?.one_year_change_pct;
              const sector = snapshot?.profile?.sector;
              const exchange = snapshot?.profile?.exchange;
              const riskLabel = snapshot?.metrics?.risk_label;

              return (
                <div
                  key={s.symbol}
                  className="bg-white/5 border border-white/10 rounded-2xl px-4 py-4"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold text-white">{s.symbol}</span>
                        <span className="text-xs text-gray-500 truncate">{s.name}</span>
                        {sector && (
                          <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-gray-400">
                            {sector}
                          </span>
                        )}
                        {exchange && (
                          <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-gray-500">
                            {exchange}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-sm text-gray-300">
                        {s.currency} {fmt(currentPrice)} current price
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        {s.quantity} shares · position value {s.currency} {fmt(totalValue)}
                        {riskLabel ? ` · ${riskLabel} risk` : ""}
                      </div>
                    </div>

                    <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[280px]">
                      <div className="rounded-xl bg-white/[0.03] px-3 py-2">
                        <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">1D</div>
                        <div className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${pillTone(dayChange)}`}>
                          {s.currency} {fmtSigned(dayChange)} · {fmtPct(dayChangePct)}
                        </div>
                      </div>
                      <div className="rounded-xl bg-white/[0.03] px-3 py-2">
                        <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">1Y</div>
                        <div className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${pillTone(yearChange)}`}>
                          {s.currency} {fmtSigned(yearChange)} · {fmtPct(yearChangePct)}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between gap-3 border-t border-white/5 pt-3">
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => setQty(s.symbol, s.quantity - 1)}
                        disabled={s.quantity <= 1}
                        className="w-7 h-7 flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 text-gray-300 transition-colors"
                      >
                        <Minus className="w-3.5 h-3.5" />
                      </button>
                      <input
                        type="number"
                        value={s.quantity}
                        min={1}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!isNaN(v)) setQty(s.symbol, v);
                        }}
                        className="w-12 bg-white/5 border border-white/10 rounded-lg text-xs text-white text-center outline-none focus:border-violet-500 py-1"
                      />
                      <button
                        onClick={() => setQty(s.symbol, s.quantity + 1)}
                        className="w-7 h-7 flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 text-gray-300 transition-colors"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <button
                      onClick={() => removeStock(s.symbol)}
                      className="text-gray-600 hover:text-red-400 transition-colors shrink-0"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <aside className="space-y-4">
            <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-white">
                <BriefcaseBusiness className="h-4 w-4 text-violet-300" />
                Allocation
              </div>
              <div className="mt-3 space-y-3">
                {Object.entries(totals).map(([currency, total]) => (
                  <div key={currency} className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">{currency} total</span>
                    <span className="font-semibold text-white">{currency} {fmt(total)}</span>
                  </div>
                ))}
                {enrichedPortfolio.map(({ stock, totalValue }) => {
                  const weight = (totalValue / analytics.grandTotal) * 100;
                  return (
                    <div key={stock.symbol}>
                      <div className="mb-1 flex items-center justify-between text-xs">
                        <span className="font-mono text-gray-300">{stock.symbol}</span>
                        <span className="text-gray-500">{weight.toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-white/5">
                        <div className="h-full rounded-full bg-violet-500" style={{ width: `${Math.min(weight, 100)}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-white">
                <Activity className="h-4 w-4 text-emerald-300" />
                Market Exposure
              </div>
              <div className="mt-3 space-y-4">
                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.16em] text-gray-500">Sector mix</div>
                  <div className="space-y-2">
                    {analytics.sectors.slice(0, 5).map((sector) => (
                      <div key={sector.name} className="flex items-center justify-between text-sm">
                        <span className="text-gray-300">{sector.name}</span>
                        <span className="text-gray-500">{sector.weight.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.16em] text-gray-500">Exchange mix</div>
                  <div className="space-y-2">
                    {analytics.exchanges.slice(0, 5).map((exchange) => (
                      <div key={exchange.name} className="flex items-center justify-between text-sm">
                        <span className="text-gray-300">{exchange.name}</span>
                        <span className="text-gray-500">{exchange.weight.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-white">
                <ShieldAlert className="h-4 w-4 text-amber-300" />
                Risk Snapshot
              </div>
              <div className="mt-3 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Weighted risk score</span>
                  <span className="font-semibold text-white">
                    {analytics.weightedRiskScore != null ? analytics.weightedRiskScore.toFixed(0) : "N/A"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Portfolio volatility</span>
                  <span className="font-semibold text-white">
                    {analytics.weightedVolatility != null ? `${analytics.weightedVolatility.toFixed(1)}%` : "N/A"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Data refresh</span>
                  <span className="font-semibold text-white">{analyticsLoading ? "Refreshing…" : "Live snapshot"}</span>
                </div>
              </div>
            </section>

            <button
              onClick={analyzePortfolio}
              className="w-full bg-violet-600 hover:bg-violet-500 text-white py-2.5 rounded-xl text-sm font-medium transition-colors"
            >
              Analyze Portfolio with AI →
            </button>
          </aside>
        </div>
      )}
    </div>
  );
}
