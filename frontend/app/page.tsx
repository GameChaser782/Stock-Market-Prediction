"use client";

import { useState } from "react";
import { MessageSquare, Scale, BarChart2, Cpu } from "lucide-react";
import ChatPanel from "@/components/ChatPanel";
import DebatePanel from "@/components/DebatePanel";
import PortfolioPanel from "@/components/PortfolioPanel";

type Tab = "chat" | "portfolio" | "debate";

const tabs = [
  { id: "chat" as Tab, label: "Chat", icon: MessageSquare },
  { id: "portfolio" as Tab, label: "Portfolio", icon: BarChart2 },
  { id: "debate" as Tab, label: "Debate", icon: Scale },
];

export default function Home() {
  const [tab, setTab] = useState<Tab>("chat");

  return (
    <div className="h-screen flex flex-col bg-[#0d0d1a]">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-white/5 bg-[#0d0d1a]/80 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-violet-400" />
          <span className="font-semibold text-white">PortfolioIQ</span>
          <span className="text-xs text-gray-500 hidden sm:block">— AI Financial Advisor</span>
        </div>
        <nav className="flex items-center gap-1 bg-white/5 rounded-xl p-1">
          {tabs.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  tab === t.id
                    ? "bg-violet-600 text-white"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            );
          })}
        </nav>
        <div className="w-24 hidden sm:block" />
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <div className={tab === "chat" ? "h-full" : "hidden"}>
          <ChatPanel />
        </div>
        <div className={tab === "portfolio" ? "h-full overflow-y-auto" : "hidden"}>
          <PortfolioPanel />
        </div>
        <div className={tab === "debate" ? "h-full overflow-y-auto" : "hidden"}>
          <DebatePanel />
        </div>
      </main>
    </div>
  );
}
