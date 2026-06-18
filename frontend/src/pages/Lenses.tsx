import { useCallback, useEffect, useMemo, useState } from "react";
import { api, loadStatic } from "../api/client";
import { useAsync, useInterval } from "../api/hooks";
import { useAuth } from "../auth";
import {
  ARTICLE_DND_TYPE,
  ArticleAttachment,
  Asset,
  FeedItem,
  FeedPage,
  Lens,
  Topic,
} from "../api/types";
import { useI18n } from "../i18n";
import { LensComposer } from "../components/LensComposer";
import { EmptyState, Modal, Spinner, Toast, timeAgo } from "../components/ui";

const POLL_MS = 45_000;
const MAX_LENSES = 5;

export default function Lenses() {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const lenses = useAsync(() => api.get<Lens[]>("/lenses"), []);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const active = useMemo(
    () => lenses.data?.find((l) => l.lensId === activeId) ?? lenses.data?.[0] ?? null,
    [lenses.data, activeId]
  );

  if (lenses.loading) return <Spinner label={t("feed.loadingLenses")} />;
  if (!lenses.data?.length)
    return <EmptyState title={t("feed.noLenses")} hint={t("feed.createInSettings")} />;

  const atCap = lenses.data.length >= MAX_LENSES;

  return (
    <div>
      <div className="mb-5 flex items-center gap-2 border-b border-ink-200">
        <div className="flex flex-1 gap-1 overflow-x-auto">
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
        <button
          onClick={() => setCreating(true)}
          disabled={atCap}
          title={atCap ? t("settings.maxLenses") : t("settings.newLens")}
          className="shrink-0 rounded-lg px-2.5 py-1 text-lg leading-none text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-800 disabled:cursor-not-allowed disabled:opacity-40"
          aria-label={t("settings.newLens")}
        >
          +
        </button>
      </div>
      {active && <Feed lens={active} />}

      {creating && (
        <CreateLensModal
          onClose={() => setCreating(false)}
          onCreated={(lensId) => {
            setCreating(false);
            lenses.reload();
            refresh();
            setActiveId(lensId);
          }}
        />
      )}
    </div>
  );
}

function CreateLensModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (lensId: string) => void;
}) {
  const { t } = useI18n();
  const topics = useAsync(() => loadStatic<Topic[]>("taxonomy.json"), []);
  const assets = useAsync(() => loadStatic<Asset[]>("assets.json"), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create(data: { name: string; topicIds: string[]; trackedAssetIds: string[] }) {
    setBusy(true);
    try {
      const lens = await api.post<Lens>("/lenses", data);
      onCreated(lens.lensId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create lens");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={t("settings.newLensTitle")} onClose={onClose}>
      {topics.loading || assets.loading || !topics.data || !assets.data ? (
        <Spinner />
      ) : (
        <LensComposer
          showSuggest
          topics={topics.data}
          assets={assets.data}
          maxTopics={10}
          maxAssets={10}
          submitLabel={t("lens.create")}
          onSubmit={create}
          busy={busy}
        />
      )}
      {error && <Toast message={error} onClose={() => setError(null)} />}
    </Modal>
  );
}

function Feed({ lens }: { lens: Lens }) {
  const { t } = useI18n();
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

  if (loading && items.length === 0) return <Spinner label={t("feed.loading")} />;
  if (items.length === 0)
    return <EmptyState title={t("feed.noNews")} hint={t("feed.noNewsHint")} />;

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <FeedCard key={item.articleId} item={item} />
      ))}
    </div>
  );
}

function FeedCard({ item }: { item: FeedItem }) {
  const { t, lang } = useI18n();
  // Prefer the Chinese title/abstraction in zh mode, falling back to English
  // (e.g. older articles abstracted before bilingual support).
  const title = lang === "zh" && item.titleZh ? item.titleZh : item.title;
  const abstraction =
    lang === "zh" && item.abstractionZh ? item.abstractionZh : item.abstraction;

  function onDragStart(e: React.DragEvent) {
    const payload: ArticleAttachment = {
      articleId: item.articleId,
      title,
      source: item.source,
      content: abstraction ?? item.excerpt,
      url: item.url,
    };
    e.dataTransfer.setData(ARTICLE_DND_TYPE, JSON.stringify(payload));
    e.dataTransfer.effectAllowed = "copy";
  }

  return (
    <article
      draggable
      onDragStart={onDragStart}
      className="card group cursor-grab p-4 transition-shadow hover:shadow-md active:cursor-grabbing"
    >
      <div className="mb-1 flex items-center gap-2 text-xs text-ink-400">
        <span className="font-medium text-ink-600">{item.source}</span>
        <span>·</span>
        <span>{timeAgo(item.publishedAt)}</span>
        <span className="ml-auto flex items-center gap-2">
          <span className="hidden text-ink-400 group-hover:inline" aria-hidden>
            ⠿ {t("feed.dragToChat")}
          </span>
          {abstraction && (
            <span className="rounded-full bg-wing-500/10 px-2 py-0.5 font-medium text-wing-600">
              {t("feed.aiSummary")}
            </span>
          )}
        </span>
      </div>
      <a
        href={item.url}
        target="_blank"
        rel="noreferrer"
        draggable={false}
        className="block font-semibold leading-snug text-ink-900 hover:text-wing-600"
      >
        {title}
      </a>
      <p className="mt-1 text-sm leading-relaxed text-ink-600">
        {abstraction ?? item.excerpt}
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
