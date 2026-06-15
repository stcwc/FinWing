import { useState } from "react";
import { api } from "../api/client";
import { Toast } from "../components/ui";

export default function Feedback() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  async function submit() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api.post("/feedback", { text: text.trim() });
      setText("");
      setToast("Thanks — your feedback was sent.");
    } catch {
      setToast("Could not send feedback. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-2 text-xl font-semibold">Feedback</h1>
      <p className="mb-4 text-sm text-ink-400">
        Found a bug, hit a limit, or have an idea? Send it here — only the FinWing admin
        sees this.
      </p>
      <div className="card p-4">
        <textarea
          className="input min-h-40"
          value={text}
          maxLength={5000}
          placeholder="What's on your mind?"
          onChange={(e) => setText(e.target.value)}
        />
        <div className="mt-3 flex justify-end">
          <button className="btn-primary" disabled={busy || !text.trim()} onClick={submit}>
            {busy ? "Sending…" : "Send feedback"}
          </button>
        </div>
      </div>
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
