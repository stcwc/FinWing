import { api } from "../api/client";
import { useAsync, useInterval } from "../api/hooks";
import { Lens, Quote, QuotesResponse } from "../api/types";
import { useI18n } from "../i18n";

// Match the up/down palette used in the digest email (_moves_html).
const UP = "#0b8457";
const DOWN = "#c0392b";

function QuoteChip({ q }: { q: Quote }) {
  const base =
    "inline-flex items-center gap-1.5 rounded-lg border border-ink-200 bg-white px-2.5 py-1 text-xs";

  if (q.price == null || q.change == null) {
    return (
      <span className={base} title={q.name}>
        <span className="font-semibold text-ink-800">{q.symbol}</span>
        <span className="text-ink-400">—</span>
      </span>
    );
  }

  const up = q.change >= 0;
  const color = up ? UP : DOWN;
  const arrow = up ? "▲" : "▼";
  const isYield = q.kind === "yield";
  const price = isYield ? `${q.price.toFixed(2)}%` : q.price.toFixed(2);
  const delta = isYield
    ? `${Math.abs(q.change).toFixed(2)}pp`
    : `${Math.abs(q.change).toFixed(2)} (${Math.abs(q.percentChange ?? 0).toFixed(2)}%)`;

  return (
    <span className={base} title={q.name}>
      <span className="font-semibold text-ink-800">{q.symbol}</span>
      <span className="tabular-nums text-ink-600">{price}</span>
      <span className="tabular-nums font-medium" style={{ color }}>
        {arrow} {delta}
      </span>
    </span>
  );
}

/** Live-ish price ticker for a lens's tracked assets. Polls the read-only,
 *  server-cached quotes endpoint; the cache is refreshed out of band. */
export function LensTicker({ lens }: { lens: Lens }) {
  const { t } = useI18n();
  const quotes = useAsync(
    () => api.get<QuotesResponse>(`/lenses/${lens.lensId}/quotes`),
    [lens.lensId]
  );
  useInterval(() => quotes.reload(), 60_000);

  if (!lens.trackedAssetIds.length) return null;

  const data = quotes.data?.quotes ?? [];
  // First load: hold a thin space so the feed below doesn't jump.
  if (!data.length) return <div className="mb-4 h-7" />;

  const latest = data
    .map((q) => q.asOf)
    .filter((x): x is string => Boolean(x))
    .sort()
    .pop();
  const asOf = latest
    ? new Date(latest).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <div className="mb-4">
      <div className="flex flex-wrap gap-1.5">
        {data.map((q) => (
          <QuoteChip key={q.assetId} q={q} />
        ))}
      </div>
      {asOf && (
        <div className="mt-1 text-[11px] text-ink-400">
          {t("ticker.asOf")} {asOf}
        </div>
      )}
    </div>
  );
}
