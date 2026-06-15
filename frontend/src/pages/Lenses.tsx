import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useAsync, useInterval } from "../api/hooks";
import { FeedItem, FeedPage, Lens } from "../api/types";
import { EmptyState, Spinner, timeAgo } from "../components/ui";

const POLL_MS = 45_000;

export default function Lenses() {
  const lenses = useAsync(() => api.get<Lens[]>("/lenses"), []);
  const [activeId, setActiveId] = useState<string | null>(null);

  const active = useMemo(
    () => lenses.data?.find((l) => l.lensId === activeId) ?? lenses.data?.[0] ?? null,
    [lenses.data, activeId]
  );

  if (lenses.loading) return <Spinner label="Loading lenses…" />;
  if (!lenses.data?.length)
    return <EmptyState title="No lenses yet" hint="Create one in Settings." />;

  return (
    <div>
      <div className="mb-5 flex gap-1 overflow-x-auto border-b border-ink-200">
        {lenses.data.map((l) => {
          const isActive = (active?.lensId ?? "") === l.lensId;
          return (
            <button
              key={l.lensId}
              onClick={() => setActiveId(l.lensId)}
              className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "border-wing-500 text-ink-900"
                  : "border-transparent text-ink-400 hover:text-ink-600"
              }`}
            >
              {l.name}
            </button>
          );
        })}
      </div>
      {active && <Feed lens={active} />}
    </div>
  );
}

function Feed({ lens }: { lens: Lens }) {
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFeed = useCallback(async () => {
    try {
      const page = await api.get<FeedPage>(`/lenses/${lens.lensId}/feed`);
      setItems((prev) => mergeByArticleId(prev, page.items));
    } finally {
      setLoading(false);
    }
  }, [lens.lensId]);

  useEffect(() => {
    setItems([]);
    setLoading(true);
    fetchFeed();
  }, [fetchFeed]);

  // Poll: abstractions replace the excerpt in place on a later cycle.
  useInterval(fetchFeed, POLL_MS);

  if (loading && items.length === 0) return <Spinner label="Loading feed…" />;
  if (items.length === 0)
    return (
      <EmptyState
        title="No news yet"
        hint="New articles matching this lens will appear here within a minute or two."
      />
    );

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <FeedCard key={item.articleId} item={item} />
      ))}
    </div>
  );
}

function FeedCard({ item }: { item: FeedItem }) {
  return (
    <article className="card p-4 transition-shadow hover:shadow-md">
      <div className="mb-1 flex items-center gap-2 text-xs text-ink-400">
        <span className="font-medium text-ink-600">{item.source}</span>
        <span>·</span>
        <span>{timeAgo(item.publishedAt)}</span>
        {item.abstraction && (
          <span className="ml-auto rounded-full bg-wing-500/10 px-2 py-0.5 font-medium text-wing-600">
            AI summary
          </span>
        )}
      </div>
      <a
        href={item.url}
        target="_blank"
        rel="noreferrer"
        className="block font-semibold leading-snug text-ink-900 hover:text-wing-600"
      >
        {item.title}
      </a>
      <p className="mt-1 text-sm leading-relaxed text-ink-600">
        {item.abstraction ?? item.excerpt}
      </p>
    </article>
  );
}

/** Merge incoming items over existing, upgrading excerpt→abstraction; never
 *  downgrade an item that already has an abstraction. */
function mergeByArticleId(existing: FeedItem[], incoming: FeedItem[]): FeedItem[] {
  const map = new Map(existing.map((i) => [i.articleId, i]));
  for (const item of incoming) {
    const prev = map.get(item.articleId);
    if (!prev || (item.abstraction && !prev.abstraction)) map.set(item.articleId, item);
  }
  return [...map.values()].sort((a, b) =>
    b.publishedAt.localeCompare(a.publishedAt)
  );
}
