import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { ChatTurn } from "../api/types";

export function ChatPanel({ onClose }: { onClose: () => void }) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .get<{ turns: ChatTurn[] }>("/chat/history")
      .then((d) => setTurns(d.turns))
      .catch(() => {});
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, sending]);

  async function send() {
    const message = input.trim();
    if (!message || sending) return;
    setInput("");
    setTurns((t) => [...t, { role: "user", content: message }]);
    setSending(true);
    try {
      const res = await api.post<{ response: string }>("/chat/messages", { message });
      setTurns((t) => [...t, { role: "assistant", content: res.response }]);
    } catch {
      setTurns((t) => [
        ...t,
        { role: "assistant", content: "Sorry — something went wrong. Please try again." },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <aside className="fixed right-0 top-0 z-40 flex h-screen w-full max-w-md flex-col border-l border-ink-200 bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-ink-200 px-4 py-3">
        <div className="font-semibold">Chat</div>
        <button onClick={onClose} className="text-ink-400 hover:text-ink-800">
          ✕
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {turns.length === 0 && (
          <p className="text-sm text-ink-400">
            Ask anything about your lenses, topics, and recent summaries. I have your
            financial context.
          </p>
        )}
        {turns.map((t, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
              t.role === "user"
                ? "ml-auto bg-wing-600 text-white"
                : "bg-ink-100 text-ink-800"
            }`}
          >
            {t.content}
          </div>
        ))}
        {sending && (
          <div className="max-w-[85%] rounded-2xl bg-ink-100 px-3 py-2 text-sm text-ink-400">
            thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-ink-200 p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={1}
            placeholder="Message…"
            className="input resize-none"
          />
          <button onClick={send} disabled={sending} className="btn-primary">
            Send
          </button>
        </div>
      </div>
    </aside>
  );
}
