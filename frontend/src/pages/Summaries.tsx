import { useState } from "react";
import { api, ApiError } from "../api/client";
import { useAsync } from "../api/hooks";
import { Lens, Summary } from "../api/types";
import { useI18n } from "../i18n";
import { EmptyState, Modal, Spinner, Toast } from "../components/ui";

interface LensSummary {
  lens: Lens;
  summary: Summary;
}

function monthBounds(d: Date) {
  const from = new Date(d.getFullYear(), d.getMonth(), 1);
  const to = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const iso = (x: Date) => x.toISOString().slice(0, 10);
  return { from: iso(from), to: iso(to), days: to.getDate(), firstWeekday: from.getDay() };
}

export default function Summaries() {
  const { t, lang } = useI18n();
  const locale = lang === "zh" ? "zh-CN" : "en-US";
  const lenses = useAsync(() => api.get<Lens[]>("/lenses"), []);
  const [month, setMonth] = useState(new Date());
  const [openDate, setOpenDate] = useState<string | null>(null);
  const bounds = monthBounds(month);

  // Fetch every lens's summaries for the month and group them by date so each
  // calendar day shows one entry per lens (not just the selected lens).
  const grouped = useAsync(async () => {
    const list = lenses.data ?? [];
    const lists = await Promise.all(
      list.map((lens) =>
        api
          .get<Summary[]>(`/lenses/${lens.lensId}/summaries?from=${bounds.from}&to=${bounds.to}`)
          .then((arr) => arr.map((summary) => ({ lens, summary })))
          .catch(() => [] as LensSummary[])
      )
    );
    const map = new Map<string, LensSummary[]>();
    for (const item of lists.flat()) {
      const arr = map.get(item.summary.date) ?? [];
      arr.push(item);
      map.set(item.summary.date, arr);
    }
    return map;
  }, [lenses.data, bounds.from]);

  if (lenses.loading) return <Spinner />;
  if (!lenses.data?.length)
    return <EmptyState title={t("feed.noLenses")} hint={t("feed.createInSettings")} />;

  const byDate = grouped.data ?? new Map<string, LensSummary[]>();
  const monthLabel = month.toLocaleString(locale, { month: "long", year: "numeric" });
  const weekdays = Array.from({ length: 7 }, (_, i) =>
    new Date(2024, 0, 7 + i).toLocaleString(locale, { weekday: "short" })
  );

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("nav.summaries")}</h1>
        <div className="flex items-center gap-2">
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
          {weekdays.map((d) => (
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
            const items = byDate.get(date) ?? [];
            const has = items.length > 0;
            return (
              <button
                key={date}
                disabled={!has}
                onClick={() => has && setOpenDate(date)}
                className={`aspect-square rounded-lg border p-1.5 text-left text-xs transition-colors ${
                  has
                    ? "border-wing-500/30 bg-wing-500/5 hover:bg-wing-500/10"
                    : "border-ink-100 text-ink-400"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{day}</span>
                  {has && (
                    <span className="rounded-full bg-wing-500/15 px-1.5 text-[10px] font-medium text-wing-600">
                      {items.length}
                    </span>
                  )}
                </div>
                {has && (
                  <div className="mt-1 space-y-0.5">
                    {items.slice(0, 3).map(({ lens }) => (
                      <div key={lens.lensId} className="truncate text-[10px] leading-tight text-ink-600">
                        {lens.name}
                      </div>
                    ))}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {openDate && (
        <DayModal
          date={openDate}
          items={byDate.get(openDate) ?? []}
          onClose={() => setOpenDate(null)}
          onSaved={() => grouped.reload()}
        />
      )}
    </div>
  );
}

function DayModal({
  date,
  items,
  onClose,
  onSaved,
}: {
  date: string;
  items: LensSummary[];
  onClose: () => void;
  onSaved: () => void;
}) {
  return (
    <Modal title={date} onClose={onClose}>
      <div className="max-h-[70vh] space-y-4 overflow-y-auto">
        {items.map(({ lens, summary }) => (
          <SummaryCard key={lens.lensId} lens={lens} initial={summary} onSaved={onSaved} />
        ))}
      </div>
    </Modal>
  );
}

function SummaryCard({
  lens,
  initial,
  onSaved,
}: {
  lens: Lens;
  initial: Summary;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [summary, setSummary] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(initial.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    try {
      await api.put(`/lenses/${lens.lensId}/summaries/${summary.date}`, {
        body,
        version: summary.version,
      });
      setSummary({ ...summary, body, editedByUser: true, version: summary.version + 1 });
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(
        e instanceof ApiError && e.code === "VERSION_CONFLICT"
          ? t("sum.conflict")
          : t("sum.saveFailed")
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-ink-200 p-4">
      <div className="mb-2 text-sm font-semibold text-ink-900">{lens.name}</div>

      {summary.assetMoves.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
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
        <div className="max-h-96 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
          {summary.body}
        </div>
      )}

      <div className="mt-3 flex justify-end gap-2">
        {editing ? (
          <>
            <button className="btn-ghost" onClick={() => setEditing(false)}>
              {t("sum.cancel")}
            </button>
            <button className="btn-primary" disabled={busy} onClick={save}>
              {busy ? t("sum.saving") : t("sum.save")}
            </button>
          </>
        ) : (
          <button className="btn-outline" onClick={() => setEditing(true)}>
            {t("sum.edit")}
          </button>
        )}
      </div>
      {error && <Toast message={error} onClose={() => setError(null)} />}
    </div>
  );
}
