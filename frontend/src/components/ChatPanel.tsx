import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { ARTICLE_DND_TYPE, ArticleAttachment, ChatTurn } from "../api/types";
import { useI18n } from "../i18n";

export function ChatPanel({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [attachments, setAttachments] = useState<ArticleAttachment[]>([]);
  const [dragOver, setDragOver] = useState(false);
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

  function onDragOver(e: React.DragEvent) {
    if (e.dataTransfer.types.includes(ARTICLE_DND_TYPE)) {
      e.preventDefault();
      setDragOver(true);
    }
  }

  function onDrop(e: React.DragEvent) {
    const raw = e.dataTransfer.getData(ARTICLE_DND_TYPE);
    setDragOver(false);
    if (!raw) return;
    e.preventDefault();
    try {
      const a = JSON.parse(raw) as ArticleAttachment;
      setAttachments((prev) =>
        prev.some((p) => p.articleId === a.articleId) ? prev : [...prev, a]
      );
    } catch {
      /* ignore malformed payloads */
    }
  }

  function removeAttachment(id: string) {
    setAttachments((prev) => prev.filter((a) => a.articleId !== id));
  }

  async function send() {
    const message = input.trim();
    if ((!message && attachments.length === 0) || sending) return;
    const sentAttachments = attachments;
    const display =
      message ||
      (sentAttachments.length === 1
        ? sentAttachments[0].title
        : `${sentAttachments.length} ✕ ${t("chat.attached")}`);

    setInput("");
    setAttachments([]);
    setTurns((prev) => [...prev, { role: "user", content: display }]);
    setSending(true);
    try {
      const res = await api.post<{ response: string }>("/chat/messages", {
        message: display,
        attachments: sentAttachments.map((a) => ({
          title: a.title,
          source: a.source,
          content: a.content,
          url: a.url,
        })),
      });
      setTurns((prev) => [...prev, { role: "assistant", content: res.response }]);
    } catch {
      setTurns((prev) => [...prev, { role: "assistant", content: t("chat.error") }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <aside
      onDragOver={onDragOver}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      className="fixed right-0 top-0 z-40 flex h-screen w-full max-w-md flex-col border-l border-ink-200 bg-white shadow-xl"
    >
      <div className="flex items-center justify-between border-b border-ink-200 px-4 py-3">
        <div className="font-semibold">{t("chat.title")}</div>
        <button onClick={onClose} className="text-ink-400 hover:text-ink-800">
          ✕
        </button>
      </div>

      <div className="relative flex-1 space-y-3 overflow-y-auto p-4">
        {turns.length === 0 && attachments.length === 0 && (
          <p className="text-sm text-ink-400">{t("chat.empty")}</p>
        )}
        {turns.map((turn, i) => (
          <div
            key={i}
            className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
              turn.role === "user"
                ? "ml-auto bg-wing-600 text-white"
                : "bg-ink-100 text-ink-800"
            }`}
          >
            {turn.content}
          </div>
        ))}
        {sending && (
          <div className="max-w-[85%] rounded-2xl bg-ink-100 px-3 py-2 text-sm text-ink-400">
            {t("chat.thinking")}
          </div>
        )}
        <div ref={endRef} />

        {dragOver && (
          <div className="pointer-events-none absolute inset-2 flex items-center justify-center rounded-xl border-2 border-dashed border-wing-500 bg-wing-500/5 text-sm font-medium text-wing-600">
            {t("chat.drop")}
          </div>
        )}
      </div>

      {/* Attached news tiles */}
      {attachments.length > 0 && (
        <div className="border-t border-ink-200 px-3 pt-3">
          <div className="mb-1 text-xs font-medium text-ink-400">
            {t("chat.attached")} ({attachments.length})
          </div>
          <div className="flex max-h-32 flex-col gap-2 overflow-y-auto">
            {attachments.map((a) => (
              <div
                key={a.articleId}
                className="flex items-start gap-2 rounded-lg border border-ink-200 bg-ink-50 px-2 py-1.5"
              >
                <span className="mt-0.5 text-wing-600">📎</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-medium text-ink-800">{a.title}</div>
                  <div className="truncate text-[10px] text-ink-400">{a.source}</div>
                </div>
                <button
                  onClick={() => removeAttachment(a.articleId)}
                  className="text-ink-400 hover:text-ink-800"
                  aria-label="Remove"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

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
            placeholder={
              attachments.length > 0 ? t("chat.placeholderAttached") : t("chat.placeholder")
            }
            className="input resize-none"
          />
          <button onClick={send} disabled={sending} className="btn-primary">
            {t("chat.send")}
          </button>
        </div>
      </div>
    </aside>
  );
}
