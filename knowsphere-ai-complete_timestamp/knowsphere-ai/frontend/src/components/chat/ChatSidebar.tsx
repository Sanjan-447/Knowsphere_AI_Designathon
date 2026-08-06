import { useState } from "react";
import type { ChatSessionType } from "@/types";

interface Props {
  sessions: ChatSessionType[];
  activeSessionId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onRename: (id: number, title: string) => void;
  onDelete: (id: number) => void;
}

export function ChatSidebar({ sessions, activeSessionId, onSelect, onNew, onRename, onDelete }: Props) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");

  function startRename(session: ChatSessionType) {
    setEditingId(session.id);
    setEditValue(session.title);
  }

  function commitRename(id: number) {
    if (editValue.trim()) onRename(id, editValue.trim());
    setEditingId(null);
  }

  return (
    <div className="flex h-full w-64 flex-shrink-0 flex-col border-r border-rule bg-white/60">
      <div className="p-3">
        <button
          onClick={onNew}
          className="w-full rounded bg-ink py-2 text-sm font-medium text-paper hover:bg-ink-soft"
        >
          + New chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {sessions.length === 0 && (
          <p className="px-2 py-4 text-center text-xs text-[#6B6558]">No conversations yet.</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            className={`group mb-1 flex items-center gap-1 rounded px-2 py-2 text-sm ${
              s.id === activeSessionId ? "bg-gold-soft" : "hover:bg-paper-dim"
            }`}
          >
            {editingId === s.id ? (
              <input
                autoFocus
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={() => commitRename(s.id)}
                onKeyDown={(e) => e.key === "Enter" && commitRename(s.id)}
                className="min-w-0 flex-1 rounded border border-gold px-1.5 py-0.5 text-xs focus:outline-none"
              />
            ) : (
              <button onClick={() => onSelect(s.id)} className="min-w-0 flex-1 truncate text-left text-ink">
                {s.title}
              </button>
            )}
            <div className="hidden flex-shrink-0 gap-1 group-hover:flex">
              <button
                onClick={() => startRename(s)}
                title="Rename"
                className="text-[11px] text-[#6B6558] hover:text-ink"
              >
                ✎
              </button>
              <button
                onClick={() => confirm("Delete this chat?") && onDelete(s.id)}
                title="Delete"
                className="text-[11px] text-[#6B6558] hover:text-danger"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
