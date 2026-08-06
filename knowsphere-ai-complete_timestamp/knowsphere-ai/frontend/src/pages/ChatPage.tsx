import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import * as chatApi from "@/api/chat";
import type { ChatMessageType, ChatSessionType, Citation } from "@/types";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { CitationCard } from "@/components/chat/CitationCard";
import { SourcePanel } from "@/components/chat/SourcePanel";

const SUGGESTED_QUESTIONS = [
  "How many vacation days do I get per year?",
  "What's covered under our benefits plan?",
  "What's the onboarding process for new hires?",
];

interface DisplayMessage extends Omit<ChatMessageType, "id"> {
  id: number | string;
  streaming?: boolean;
}

export function ChatPage() {
  const [sessions, setSessions] = useState<ChatSessionType[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [copiedId, setCopiedId] = useState<number | string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<number | string, "helpful" | "not_helpful">>({});
  const [error, setError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  async function loadSessions() {
    try {
      const data = await chatApi.listSessions();
      setSessions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chats.");
    }
  }

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function openSession(id: number) {
    setActiveSessionId(id);
    try {
      const data = await chatApi.getSession(id);
      setMessages(data.messages || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversation.");
    }
  }

  async function handleNewChat() {
    setActiveSessionId(null);
    setMessages([]);
  }

  async function handleRename(id: number, title: string) {
    await chatApi.renameSession(id, title);
    await loadSessions();
  }

  async function handleDelete(id: number) {
    await chatApi.deleteSession(id);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
    }
    await loadSessions();
  }

  async function ensureSession(): Promise<number> {
    if (activeSessionId) return activeSessionId;
    const session = await chatApi.createSession();
    setActiveSessionId(session.id);
    await loadSessions();
    return session.id;
  }

  async function handleSend(question?: string) {
    const text = (question ?? input).trim();
    if (!text || isSending) return;
    setInput("");
    setError(null);
    setIsSending(true);

    const sessionId = await ensureSession();

    const userMsg: DisplayMessage = {
      id: `local-user-${Date.now()}`, session_id: sessionId, role: "user",
      content: text, provider_used: null, model_used: null, created_at: new Date().toISOString(), citations: [],
    };
    const assistantId = `local-assistant-${Date.now()}`;
    const assistantMsg: DisplayMessage = {
      id: assistantId, session_id: sessionId, role: "assistant",
      content: "", provider_used: null, model_used: null, created_at: new Date().toISOString(),
      citations: [], streaming: true,
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    await chatApi.streamMessage(sessionId, text, 8, {
      onChunk: (chunk) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + chunk } : m))
        );
      },
      onDone: (finalMessage) => {
        const fm = finalMessage as ChatMessageType | null;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? fm
                ? { ...fm, streaming: false }
                : { ...m, streaming: false }
              : m
          )
        );
        setIsSending(false);
        loadSessions();
      },
      onError: (err) => {
        setError(err);
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)));
        setIsSending(false);
      },
    });
  }

  function handleCopy(msg: DisplayMessage) {
    navigator.clipboard.writeText(msg.content);
    setCopiedId(msg.id);
    setTimeout(() => setCopiedId(null), 1500);
  }

  async function handleFeedback(msg: DisplayMessage, rating: "helpful" | "not_helpful") {
    if (typeof msg.id !== "number") return; // local-only optimistic messages don't have a real ID yet
    try {
      await chatApi.submitFeedback(msg.id, rating);
      setFeedbackGiven((prev) => ({ ...prev, [msg.id]: rating }));
    } catch {
      // best-effort — feedback failing shouldn't interrupt the chat experience
    }
  }

  return (
    <div className="flex h-full">
      <ChatSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={openSession}
        onNew={handleNewChat}
        onRename={handleRename}
        onDelete={handleDelete}
      />

      <div className="flex flex-1 flex-col">
        <div className="border-b border-rule px-8 py-4">
          <h1 className="font-display text-lg font-semibold text-ink">Ask Knowsphere</h1>
          <p className="text-xs text-[#6B6558]">Answers are grounded in your organization's documents, with citations.</p>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-8 py-6">
          {messages.length === 0 && (
            <div className="mx-auto max-w-lg pt-10 text-center">
              <p className="mb-4 text-sm text-[#6B6558]">Try asking:</p>
              <div className="space-y-2">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="block w-full rounded border border-rule bg-white px-4 py-2.5 text-left text-sm text-ink hover:border-gold"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mx-auto max-w-2xl space-y-5">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : ""}`}>
                <div className={`max-w-[85%] ${msg.role === "user" ? "" : "w-full"}`}>
                  <div
                    className={`rounded px-4 py-3 text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-ink text-paper"
                        : "border border-rule bg-white text-[#23262B]"
                    }`}
                  >
                    {msg.role === "assistant" ? (
                      <div className="prose-sm">
                        <ReactMarkdown>{msg.content || (msg.streaming ? "…" : "")}</ReactMarkdown>
                      </div>
                    ) : (
                      msg.content
                    )}
                  </div>

                  {msg.role === "assistant" && !msg.streaming && (
                    <div className="mt-1.5 flex items-center gap-3">
                      <button
                        onClick={() => handleCopy(msg)}
                        className="text-[11px] text-[#6B6558] hover:text-ink"
                      >
                        {copiedId === msg.id ? "Copied!" : "Copy"}
                      </button>
                      {msg.provider_used && msg.provider_used !== "none" && (
                        <span className="text-[11px] text-[#6B6558]">via {msg.model_used}</span>
                      )}
                      <span className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleFeedback(msg, "helpful")}
                          title="Helpful"
                          className={`text-xs ${feedbackGiven[msg.id as number] === "helpful" ? "opacity-100" : "opacity-40 hover:opacity-100"}`}
                        >
                          👍
                        </button>
                        <button
                          onClick={() => handleFeedback(msg, "not_helpful")}
                          title="Not helpful"
                          className={`text-xs ${feedbackGiven[msg.id as number] === "not_helpful" ? "opacity-100" : "opacity-40 hover:opacity-100"}`}
                        >
                          👎
                        </button>
                      </span>
                    </div>
                  )}

                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2 space-y-1.5">
                      {msg.citations.map((c) => (
                        <CitationCard key={c.marker} citation={c} onClick={() => setSelectedCitation(c)} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="mx-8 mb-2 rounded border border-danger/40 bg-danger/5 px-3 py-2 text-xs text-danger">
            {error}
          </div>
        )}

        <div className="border-t border-rule px-8 py-4">
          <div className="mx-auto flex max-w-2xl gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Ask about policies, benefits, onboarding…"
              disabled={isSending}
              className="flex-1 rounded border border-rule px-4 py-2.5 text-sm focus:border-gold focus:outline-none disabled:opacity-60"
            />
            <button
              onClick={() => handleSend()}
              disabled={isSending || !input.trim()}
              className="rounded bg-ink px-5 py-2.5 text-sm font-medium text-paper hover:bg-ink-soft disabled:opacity-40"
            >
              {isSending ? "…" : "Ask"}
            </button>
          </div>
        </div>
      </div>

      <SourcePanel citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
    </div>
  );
}
