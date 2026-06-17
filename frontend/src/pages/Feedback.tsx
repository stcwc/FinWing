import { useState } from "react";
import { api } from "../api/client";
import { useI18n } from "../i18n";
import { Toast } from "../components/ui";

export default function Feedback() {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  async function submit() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api.post("/feedback", { text: text.trim() });
      setText("");
      setToast(t("fb.sent"));
    } catch {
      setToast(t("fb.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-2 text-xl font-semibold">{t("fb.title")}</h1>
      <p className="mb-4 text-sm text-ink-400">{t("fb.subtitle")}</p>
      <div className="card p-4">
        <textarea
          className="input min-h-40"
          value={text}
          maxLength={5000}
          placeholder={t("fb.placeholder")}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="mt-3 flex justify-end">
          <button className="btn-primary" disabled={busy || !text.trim()} onClick={submit}>
            {busy ? t("fb.sending") : t("fb.send")}
          </button>
        </div>
      </div>
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
