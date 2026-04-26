"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { MessageSquare, BarChart2, Cpu } from "lucide-react";
import ChatPanel from "@/components/ChatPanel";
import PortfolioPanel from "@/components/PortfolioPanel";
import SessionManager from "@/components/SessionManager";
import { getSession, saveSession, type PortfolioEntry } from "@/lib/api";

type Tab = "chat" | "portfolio";

const tabs = [
  { id: "chat" as Tab, label: "Chat", icon: MessageSquare },
  { id: "portfolio" as Tab, label: "Portfolio", icon: BarChart2 },
];

const DEBOUNCE_MS = 1500;

export default function Home() {
  const [tab, setTab] = useState<Tab>("chat");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState("");
  const [portfolio, setPortfolio] = useState<PortfolioEntry[]>([]);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadSession = useCallback(async (id: string) => {
    try {
      const s = await getSession(id);
      setPortfolio(s.data?.portfolio ?? []);
    } catch {
      setPortfolio([]);
    }
  }, []);

  const scheduleAutoSave = useCallback((id: string, data: PortfolioEntry[]) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      try { await saveSession(id, { portfolio: data }); } catch { /* silent */ }
    }, DEBOUNCE_MS);
  }, []);

  const handlePortfolioChange = useCallback((newPortfolio: PortfolioEntry[]) => {
    setPortfolio(newPortfolio);
    if (sessionId) scheduleAutoSave(sessionId, newPortfolio);
  }, [sessionId, scheduleAutoSave]);

  const handleSelectSession = useCallback(async (id: string, name: string) => {
    setSessionId(id);
    setSessionName(name);
    if (id) await loadSession(id);
    else setPortfolio([]);
  }, [loadSession]);

  const handleNewSession = useCallback(async (id: string, name: string) => {
    setSessionId(id || null);
    setSessionName(name);
    setPortfolio([]);
  }, []);

  // Switch to Chat tab when portfolio analyze is triggered
  useEffect(() => {
    const handler = () => setTab("chat");
    window.addEventListener("portfolioiq:analyze", handler);
    return () => window.removeEventListener("portfolioiq:analyze", handler);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-[#0d0d1a]">
      <header className="flex items-center justify-between pl-4 pr-6 py-2.5 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-violet-400" />
          <span className="font-semibold text-white">PortfolioIQ</span>
        </div>

        <nav className="flex items-center gap-1 bg-white/5 rounded-xl p-1">
          {tabs.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  tab === t.id ? "bg-violet-600 text-white" : "text-gray-400 hover:text-white"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            );
          })}
        </nav>

        <SessionManager
          currentId={sessionId}
          onSelect={handleSelectSession}
          onNew={handleNewSession}
        />
      </header>

      <main className="flex-1 overflow-hidden">
        <div className={tab === "chat" ? "h-full" : "hidden"}>
          <ChatPanel
            sessionId={sessionId}
            portfolio={portfolio}
            currentSessionName={sessionName}
          />
        </div>
        <div className={tab === "portfolio" ? "h-full overflow-y-auto" : "hidden"}>
          <PortfolioPanel
            portfolio={portfolio}
            onPortfolioChange={handlePortfolioChange}
          />
        </div>
      </main>
    </div>
  );
}
