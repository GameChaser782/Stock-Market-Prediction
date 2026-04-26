"use client";

import { useState, useEffect, useCallback } from "react";
import { FolderOpen, Plus, Trash2, ChevronDown, Check, Clock } from "lucide-react";
import {
  listSessions, createSession, deleteSession,
  type SessionSummary,
} from "@/lib/api";

interface Props {
  currentId: string | null;
  onSelect: (id: string, name: string) => void;
  onNew: (id: string, name: string) => void;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  return d.toLocaleDateString();
}

export default function SessionManager({ currentId, onSelect, onNew }: Props) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const load = useCallback(async () => {
    const s = await listSessions();
    setSessions(s);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleNew = async () => {
    const name = newName.trim() || `Session ${new Date().toLocaleDateString()}`;
    const session = await createSession(name);
    setSessions((prev) => [{ ...session, stock_count: 0 }, ...prev]);
    setCreating(false);
    setNewName("");
    setOpen(false);
    onNew(session.id, session.name);
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (currentId === id) onNew("", "");
  };

  const current = sessions.find((s) => s.id === currentId);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl px-3 py-2 text-sm text-gray-300 transition-colors"
      >
        <FolderOpen className="w-4 h-4 text-violet-400" />
        <span className="max-w-[120px] truncate">
          {current ? current.name : "No session"}
        </span>
        <ChevronDown className={`w-3.5 h-3.5 text-gray-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute top-full mt-1 right-0 w-64 bg-[#1a1a2e] border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
          {/* New session */}
          {creating ? (
            <div className="p-3 border-b border-white/5 flex gap-2">
              <input
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleNew()}
                placeholder="Session name…"
                className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white outline-none focus:border-violet-500"
              />
              <button
                onClick={handleNew}
                className="bg-violet-600 hover:bg-violet-500 text-white px-3 py-1.5 rounded-lg text-sm transition-colors"
              >
                Create
              </button>
            </div>
          ) : (
            <button
              onClick={() => setCreating(true)}
              className="w-full flex items-center gap-2 px-4 py-3 text-sm text-violet-400 hover:bg-white/5 border-b border-white/5 transition-colors"
            >
              <Plus className="w-4 h-4" /> New session
            </button>
          )}

          {/* Session list */}
          {sessions.length === 0 ? (
            <p className="text-xs text-gray-600 text-center py-4">No sessions yet</p>
          ) : (
            <div className="max-h-64 overflow-y-auto">
              {sessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => { onSelect(s.id, s.name); setOpen(false); }}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition-colors text-left"
                >
                  {s.id === currentId && <Check className="w-3.5 h-3.5 text-violet-400 shrink-0" />}
                  {s.id !== currentId && <div className="w-3.5 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{s.name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Clock className="w-3 h-3 text-gray-600" />
                      <span className="text-xs text-gray-500">{formatDate(s.updated_at)}</span>
                      {s.stock_count > 0 && (
                        <span className="text-xs text-gray-600">· {s.stock_count} stock{s.stock_count !== 1 ? "s" : ""}</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, s.id)}
                    className="text-gray-700 hover:text-red-400 transition-colors shrink-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
