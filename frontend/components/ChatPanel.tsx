"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Loader2, Swords, Paperclip, ChevronRight, MessageSquareText, PanelLeft, Plus } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { streamChat, streamDebate, getChatHistory, saveChatMessage, getDebate, listChats, createChat } from "@/lib/api";
import type { ChatMessage, ChatThreadSummary, DebateEvent, PortfolioEntry } from "@/lib/api";
import MentionInput from "./MentionInput";
import DebateModal from "./DebateModal";

interface LocalMessage {
  id: string;
  role: "user" | "assistant" | "debate_block";
  content: string;
  streaming?: boolean;
  debateId?: string;
  debateTicker?: string;
  debateVerdict?: string;
  debateConfidence?: number;
}

const EPHEMERAL_THREAD_ID = `thread-${Math.random().toString(36).slice(2)}`;
const WELCOME = "Hi! I'm PortfolioIQ. Ask me about any stock, or use **@AAPL** to mention a ticker.\n\nTap **+** to start a debate or attach a PDF.";

interface Props {
  sessionId: string | null;
  portfolio: PortfolioEntry[];
  currentSessionName: string;
}

function previewText(message?: string) {
  if (!message) return "No messages yet";
  return message.length > 72 ? `${message.slice(0, 72)}…` : message;
}

export default function ChatPanel({ sessionId, portfolio, currentSessionName }: Props) {
  const [messages, setMessages] = useState<LocalMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: WELCOME,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [debateModal, setDebateModal] = useState<{
    ticker: string;
    stream: AsyncGenerator<DebateEvent> | null;
    stored: object | null;
    blockId?: string;
  } | null>(null);
  const [debateMode, setDebateMode] = useState(false);
  const [plusOpen, setPlusOpen] = useState(false);
  const [chats, setChats] = useState<ChatThreadSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadChats = useCallback(async () => {
    if (!sessionId) {
      setChats([]);
      setActiveChatId(null);
      return [];
    }
    const data = await listChats(sessionId);
    setChats(data);
    return data;
  }, [sessionId]);

  const ensureChat = useCallback(async () => {
    if (!sessionId) return null;
    if (activeChatId) return activeChatId;
    const created = await createChat(sessionId, `Chat ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
    setChats((prev) => [created, ...prev]);
    setActiveChatId(created.id);
    return created.id;
  }, [sessionId, activeChatId]);

  // Load chat history when session changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([{ id: "welcome", role: "assistant", content: WELCOME }]);
      setChats([]);
      setActiveChatId(null);
      return;
    }

    (async () => {
      const data = await loadChats();
      setActiveChatId((prev) => (prev && data.some((chat) => chat.id === prev) ? prev : (data[0]?.id ?? null)));
    })();
  }, [sessionId, loadChats]);

  useEffect(() => {
    if (!activeChatId) {
      setMessages([{ id: "welcome", role: "assistant", content: WELCOME }]);
      return;
    }

    (async () => {
      const history = await getChatHistory(activeChatId);
      const mapped: LocalMessage[] = history.map((m: ChatMessage) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        debateId: (m.metadata?.debate_id as string) || undefined,
        debateTicker: (m.metadata?.ticker as string) || undefined,
        debateVerdict: ((m.metadata?.verdict as Record<string, unknown>)?.verdict as string) || undefined,
        debateConfidence: ((m.metadata?.verdict as Record<string, unknown>)?.confidence as number) || undefined,
      }));
      setMessages([{ id: "welcome", role: "assistant", content: WELCOME }, ...mapped]);
    })();
  }, [activeChatId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const normalizeMentions = useCallback((text: string) => {
    return text.replace(/@([\w.]+)/g, (_, ticker: string) => `@${ticker.toUpperCase()}`);
  }, []);

  const extractTicker = useCallback((text: string) => {
    const match = text.match(/@([\w.]+)/i);
    return match ? match[1].toUpperCase() : null;
  }, []);

  const sendMessage = useCallback(async (msg: string) => {
    if (!msg || loading) return;
    const normalizedMsg = normalizeMentions(msg.trim());
    const chatId = await ensureChat();
    setInput("");
    setLoading(true);

    const userMsg: LocalMessage = { id: Date.now().toString(), role: "user", content: normalizedMsg };
    const assistantId = `${Date.now()}-ai`;

    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);

    // Persist to history
    if (sessionId && chatId) {
      saveChatMessage(sessionId, chatId, "user", normalizedMsg).catch(() => {});
    }

    try {
      let fullResponse = "";
      for await (const token of streamChat(normalizedMsg, chatId ?? EPHEMERAL_THREAD_ID)) {
        fullResponse += token;
        setMessages((prev) =>
          prev.map((m) => m.id === assistantId ? { ...m, content: m.content + token } : m)
        );
      }
      if (sessionId && chatId) {
        saveChatMessage(sessionId, chatId, "assistant", fullResponse).catch(() => {});
        setChats(await loadChats());
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: "Sorry, something went wrong. Is the backend running?", streaming: false }
            : m
        )
      );
    } finally {
      setMessages((prev) =>
        prev.map((m) => m.id === assistantId ? { ...m, streaming: false } : m)
      );
      setLoading(false);
    }
  }, [loading, normalizeMentions, sessionId, ensureChat, loadChats]);

  const send = useCallback(() => sendMessage(input.trim()), [input, sendMessage]);

  // Handle portfolio analyze event
  useEffect(() => {
    const handler = (e: Event) => {
      const msg = (e as CustomEvent<string>).detail;
      if (msg) sendMessage(msg);
    };
    window.addEventListener("portfolioiq:analyze", handler);
    return () => window.removeEventListener("portfolioiq:analyze", handler);
  }, [sendMessage]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (debateMode) {
        startDebate(input);
        return;
      }
      send();
    }
  };

  const handleNewChat = useCallback(async () => {
    if (!sessionId) return;
    const created = await createChat(sessionId, `Chat ${chats.length + 1}`);
    setChats((prev) => [created, ...prev]);
    setActiveChatId(created.id);
    setMessages([{ id: "welcome", role: "assistant", content: WELCOME }]);
  }, [sessionId, chats.length]);

  // Start a debate
  const startDebate = useCallback(async (rawText?: string) => {
    const source = (rawText ?? input).trim();
    const ticker = extractTicker(source);
    if (!ticker) return;
    const chatId = await ensureChat();
    setDebateMode(false);
    setInput("");

    const blockId = `debate-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: blockId, role: "debate_block", content: `Debate: ${ticker}`, debateTicker: ticker, debateVerdict: "Running..." },
    ]);

    const stream = streamDebate(ticker, 3, sessionId ?? undefined, chatId ?? undefined, portfolio.length > 0 ? portfolio : undefined);
    setDebateModal({
      ticker,
      stream,
      stored: null,
      blockId,
    });
  }, [extractTicker, input, sessionId, portfolio, ensureChat]);

  // Open stored debate
  const openDebate = useCallback(async (debateId: string) => {
    try {
      const stored = await getDebate(debateId);
      const ticker = stored.ticker;
      setDebateModal({ ticker, stream: null, stored });
    } catch (e) {
      console.error(e);
    }
  }, []);

  // Markdown components styled for the dark chat UI
  const mdComponents = {
    p: ({ children }: { children?: React.ReactNode }) => <p className="mb-1.5 last:mb-0">{children}</p>,
    strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-semibold text-white">{children}</strong>,
    em: ({ children }: { children?: React.ReactNode }) => <em className="italic text-gray-300">{children}</em>,
    ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc pl-4 mb-1.5 space-y-0.5">{children}</ul>,
    ol: ({ children }: { children?: React.ReactNode }) => <ol className="list-decimal pl-4 mb-1.5 space-y-0.5">{children}</ol>,
    li: ({ children }: { children?: React.ReactNode }) => <li className="text-gray-200">{children}</li>,
    h1: ({ children }: { children?: React.ReactNode }) => <h1 className="text-base font-bold text-white mt-2 mb-1">{children}</h1>,
    h2: ({ children }: { children?: React.ReactNode }) => <h2 className="text-sm font-bold text-white mt-2 mb-1">{children}</h2>,
    h3: ({ children }: { children?: React.ReactNode }) => <h3 className="text-sm font-semibold text-gray-200 mt-1.5 mb-0.5">{children}</h3>,
    code: ({ children }: { children?: React.ReactNode }) => <code className="bg-white/10 text-violet-300 px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
    blockquote: ({ children }: { children?: React.ReactNode }) => <blockquote className="border-l-2 border-violet-500 pl-3 text-gray-400 italic">{children}</blockquote>,
  };

  return (
    <div className="flex h-full">
      <aside className={`${sidebarOpen ? "flex" : "hidden"} w-80 shrink-0 flex-col border-r border-white/5 bg-white/[0.02]`}>
        <div className="border-b border-white/5 px-4 py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs uppercase tracking-[0.18em] text-gray-500">Chats</div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="text-xs text-gray-500 hover:text-white"
            >
              Hide
            </button>
          </div>
          <div className="mt-1 text-sm text-gray-300">
            {currentSessionName || "Select a portfolio session first"}
          </div>
          <button
            onClick={() => void handleNewChat()}
            disabled={!sessionId}
            className="mt-3 inline-flex items-center gap-2 rounded-xl bg-violet-600 px-3 py-2 text-sm text-white disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
            New chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2">
          {!sessionId ? (
            <div className="px-3 py-4 text-sm text-gray-500">
              Pick or create a portfolio session first.
            </div>
          ) : chats.length === 0 ? (
            <div className="px-3 py-4 text-sm text-gray-500">
              No chats yet in this session. Start one with `New chat`.
            </div>
          ) : (
            <div className="space-y-1.5">
              {chats.map((chat) => {
                const active = chat.id === activeChatId;
                return (
                  <button
                    key={chat.id}
                    onClick={() => setActiveChatId(chat.id)}
                    className={`w-full rounded-2xl border px-3 py-3 text-left transition-colors ${
                      active
                        ? "border-violet-500/40 bg-violet-500/10"
                        : "border-white/5 bg-white/[0.03] hover:bg-white/[0.06]"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <MessageSquareText className={`h-4 w-4 ${active ? "text-violet-300" : "text-gray-500"}`} />
                      <span className="truncate text-sm font-medium text-white">{chat.name}</span>
                    </div>
                    <div className="mt-1 text-xs text-gray-400">{previewText(chat.last_message)}</div>
                    <div className="mt-2 text-[11px] text-gray-500">{chat.message_count} msgs</div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
      <div className="px-4 pt-3">
        <button
          onClick={() => setSidebarOpen((open) => !open)}
          className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-300 hover:bg-white/10"
        >
          <PanelLeft className="h-4 w-4 text-violet-300" />
          {sidebarOpen ? "Hide chats" : "Show chats"}
        </button>
      </div>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((m) => {
          // Debate block
          if (m.role === "debate_block") {
            const ticker = m.debateTicker ?? "?";
            const verdict = m.debateVerdict;
            const conf = m.debateConfidence;
            const isRunning = verdict === "Running..." || !verdict;
            return (
              <div key={m.id} className="flex justify-start">
                <button
                  onClick={() => m.debateId ? openDebate(m.debateId) : undefined}
                  className="group bg-white/5 border border-white/10 hover:border-violet-500/40 rounded-xl px-4 py-3 flex items-center gap-3 transition-all max-w-xs text-left"
                >
                  <div className="w-8 h-8 rounded-full bg-violet-600/20 flex items-center justify-center shrink-0">
                    <Swords className="w-4 h-4 text-violet-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-white text-sm">{ticker}</span>
                      {verdict && verdict !== "Running..." && (
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                          verdict.includes("Buy") ? "bg-emerald-500/15 text-emerald-400" :
                          verdict.includes("Sell") ? "bg-red-500/15 text-red-400" :
                          "bg-amber-500/15 text-amber-400"
                        }`}>{verdict}</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {isRunning ? (
                        <span className="flex items-center gap-1">
                          <Loader2 className="w-3 h-3 animate-spin" /> Running debate...
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          Debate · {conf}% confidence
                          <ChevronRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              </div>
            );
          }

          // Normal message
          return (
            <div key={m.id} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                m.role === "assistant" ? "bg-violet-600" : "bg-gray-700"
              }`}>
                {m.role === "assistant" ? <Bot className="w-4 h-4 text-white" /> : <User className="w-4 h-4 text-white" />}
              </div>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-violet-600 text-white"
                  : "bg-white/5 border border-white/10 text-gray-200"
              }`}>
                {m.content ? (
                  m.role === "user" ? (
                    <span className="whitespace-pre-wrap">{m.content}</span>
                  ) : (
                    <>
                      <ReactMarkdown components={mdComponents}>{m.content}</ReactMarkdown>
                      {m.streaming && (
                        <span className="inline-block w-1.5 h-4 bg-violet-400 ml-0.5 animate-pulse align-middle" />
                      )}
                    </>
                  )
                ) : (
                  m.streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : null
                )}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      {/* Main input */}
      <div className="px-4 pb-4">
        {/* + menu */}
        {plusOpen && (
          <div className="mb-2 bg-[#1a1a2e] border border-white/10 rounded-xl overflow-hidden shadow-xl w-48">
            <button
              onClick={() => { setPlusOpen(false); setDebateMode(true); }}
              className="w-full flex items-center gap-2.5 px-4 py-3 text-sm text-gray-300 hover:bg-white/5 transition-colors"
            >
              <Swords className="w-4 h-4 text-violet-400" /> Start Debate
            </button>
            <button
              onClick={() => { setPlusOpen(false); fileRef.current?.click(); }}
              className="w-full flex items-center gap-2.5 px-4 py-3 text-sm text-gray-300 hover:bg-white/5 transition-colors border-t border-white/5"
            >
              <Paperclip className="w-4 h-4 text-blue-400" /> Attach PDF
            </button>
          </div>
        )}

        <div className="flex items-end gap-2 bg-white/5 border border-white/10 rounded-2xl px-4 py-3 focus-within:border-violet-500 transition-colors">
          {/* + button */}
          <button
            onClick={() => setPlusOpen((o) => !o)}
            className={`w-7 h-7 flex items-center justify-center rounded-lg text-lg font-light transition-colors shrink-0 mb-0.5 ${
              plusOpen ? "bg-violet-600 text-white" : "text-gray-500 hover:text-white hover:bg-white/10"
            }`}
          >
            +
          </button>

          <MentionInput
            value={input}
            onChange={setInput}
            onKeyDown={handleKey}
            placeholder={debateMode ? "Debate mode: mention a stock like @AAPL and press Enter" : "Ask about any stock... or use @AAPL"}
            className="flex-1 bg-transparent text-white placeholder-gray-500 outline-none resize-none text-sm max-h-32 overflow-y-auto"
            disabled={loading}
          />

          {debateMode && (
            <button
              onClick={() => setDebateMode(false)}
              className="text-gray-500 hover:text-white text-xs px-2 shrink-0 mb-1"
            >
              Cancel
            </button>
          )}

          <button
            onClick={() => debateMode ? startDebate(input) : send()}
            disabled={loading || !(debateMode ? extractTicker(input) : input.trim())}
            className="w-8 h-8 flex items-center justify-center bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors shrink-0"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 text-white animate-spin" />
            ) : debateMode ? (
              <Swords className="w-4 h-4 text-white" />
            ) : (
              <Send className="w-4 h-4 text-white" />
            )}
          </button>
        </div>
        <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={() => {}} />
        <p className="text-xs text-gray-600 mt-1.5 text-center">Not financial advice. Always do your own research.</p>
      </div>

      {/* Debate modal */}
      {debateModal && (
        <DebateModal
          ticker={debateModal.ticker}
          eventStream={debateModal.stream}
          storedDebate={debateModal.stored as Parameters<typeof DebateModal>[0]["storedDebate"]}
          onClose={() => setDebateModal(null)}
          onDone={async (debateId, verdict, confidence) => {
            if (debateModal.blockId) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === debateModal.blockId
                    ? { ...m, debateId, debateVerdict: verdict, debateConfidence: confidence }
                    : m
                )
              );
            }
            if (sessionId) setChats(await loadChats());
          }}
        />
      )}
      </div>
    </div>
  );
}
