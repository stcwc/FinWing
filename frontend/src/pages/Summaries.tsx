import { useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAsync } from "../api/hooks";
import { Lens, Summary } from "../api/types";
import { EmptyState, Modal, Spinner, Toast } from "../components/ui";

function monthBounds(d: Date) {
  const from = new Date(d.getFullYear(), d.getMonth(), 1);
  const to = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const iso = (x: Date) => x.toISOString().slice(0, 10);
  return { from: iso(from), to: iso(to), days: to.getDate(), firstWeekday: from.getDay() };
}

export default function Summaries() {
  const lenses = useAsync(() => api.get<Lens[]>("/lenses"), []);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [month, setMonth] = useState(new Date());
  const [open, setOpen] = useState<Summary | null>(null);

  const active = lenses.data?.find((l) => l.lensId === activeId) ?? lenses.data?.[0];
  const bounds = useMemo(() => monthBounds(month), [month]);

  const summaries = useAsync(
    () =>
      active
        ? api.get<Summary[]>(
            `/lenses/${active.lensId}/summaries?from=${bounds.from}&to=${bounds.to}`
          )
        : Promise.resolve([]),
    [active?.lensId, bounds.from]
  );

  if (lenses.loading) return <Spinner />;
  if (!lenses.data?.length)
    return <EmptyState title="No lenses yet" hint="Create one in Settings." />;

  const byDate = new Map((summaries.data ?? []).map((s) => [s.date, s]));
  const monthLabel = month.toLocaleString("default", { month: "long", year: "numeric" });

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="flex gap-1 overflow-x-auto">
          {lenses.data.map((l) => {
            const isActive = (active?.lensId ?? "") === l.lensId;
            return (
              <button
                key={l.lensId}
                onClick={() => setActiveId(l.lensId)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                  isActive ? "bg-ink-100 text-ink-900" : "text-ink-400 hover:bg-ink-50"
                }`}
              >
                {l.name}
              </button>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            className="btn-ghost"
            onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}
          >
            ‹
          </button>
          <span className="w-40 text-center text-sm font-medium">{monthLabel}</span>
          <button
            className="btn-ghost"
            onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}
          >
            ›
          </button>
        </div>
      </div>

      <div className="card p-4">
        <div className="mb-2 grid grid-cols-7 text-center text-xs font-medium text-ink-400">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => (
            <div key={d}>{d}</div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {Array.from({ length: bounds.firstWeekday }).map((_, i) => (
            <div key={`pad${i}`} />
          ))}
          {Array.from({ length: bounds.days }).map((_, i) => {
            const day = i + 1;
            const date = `${bounds.from.slice(0, 8)}${String(day).padStart(2, "0")}`;
            const summary = byDate.get(date);
            return (
              <button
                key={date}
                disabled={!summary}
                onClick={() => summary && setOpen(summary)}
                className={`aspect-square rounded-lg border p-1.5 text-left text-xs transition-colors ${
                  summary
                    ? "border-wing-500/30 bg-wing-500/5 hover:bg-wing-500/10"
                    : "border-ink-100 text-ink-400"
                }`}
              >
                <div className="font-medium">{day}</div>
                {summary && (
                  <div className="mt-1 line-clamp-2 text-[10px] leading-tight text-ink-600">
                    {summary.editedByUser ? "✎ " : ""}
                    {summary.body.replace(/[#*]/g, "").slice(0, 40)}…
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {open && (
        <SummaryModal
          summary={open}
          lensId={active!.lensId}
          onClose={() => setOpen(null)}
          onSaved={(s) => {
            setOpen(null);
            summaries.reload();
            return s;
          }}
        />
      )}
    </div>
  );
}

function SummaryModal({
  summary,
  lensId,
  onClose,
  onSaved,
}: {
  summary: Summary;
  lensId: string;
  onClose: () => void;
  onSaved: (s: Summary) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(summary.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    try {
      await api.put(`/lenses/${lensId}/summaries/${summary.date}`, {
        body,
        version: summary.version,
      });
      onSaved({ ...summary, body, editedByUser: true, version: summary.version + 1 });
    } catch (e) {
      setError(
        e instanceof ApiError && e.code === "VERSION_CONFLICT"
          ? "This summary changed elsewhere. Close and reopen to get the latest."
          : "Could not save."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={summary.date} onClose={onClose}>
      {summary.assetMoves.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {summary.assetMoves.map((m) => (
            <span
              key={m.assetId}
              className={`chip ${m.move >= 0 ? "text-wing-600" : "text-red-600"}`}
            >
              {m.symbol} {m.move >= 0 ? "▲" : "▼"} {Math.abs(m.move).toFixed(1)}%
            </span>
          ))}
        </div>
      )}

      {editing ? (
        <textarea
          className="input min-h-64 font-mono text-xs"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
      ) : (
        <div className="prose-sm max-h-96 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
          {summary.body}
        </div>
      )}

      <div className="mt-4 flex justify-end gap-2">
        {editing ? (
          <>
            <button className="btn-ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button className="btn-primary" disabled={busy} onClick={save}>
              {busy ? "Saving…" : "Save"}
            </button>
          </>
        ) : (
          <button className="btn-outline" onClick={() => setEditing(true)}>
            Edit
          </button>
        )}
      </div>
      {error && <Toast message={error} onClose={() => setError(null)} />}
    </Modal>
  );
}
