import { useMemo, useState } from "react";
import Fuse from "fuse.js";
import { Asset, Topic } from "../api/types";
import { useI18n } from "../i18n";

interface Props {
  topics: Topic[];
  assets: Asset[];
  initialName?: string;
  initialTopicIds?: string[];
  initialAssetIds?: string[];
  maxTopics: number;
  maxAssets: number;
  submitLabel: string;
  onSubmit: (data: {
    name: string;
    topicIds: string[];
    trackedAssetIds: string[];
  }) => void;
  busy?: boolean;
}

/**
 * Lens editor shared by onboarding and settings. Topics drive what NEWS the
 * lens sees; tracked assets drive what PRICE moves the summary reports. Topic
 * selection *suggests* assets (opt-in), it never silently mutates the chosen
 * asset list — matching the design's "suggest, never silently mutate" rule.
 */
export function LensEditor(props: Props) {
  const { t: tr } = useI18n();
  const [name, setName] = useState(props.initialName ?? "");
  const [topicIds, setTopicIds] = useState<string[]>(props.initialTopicIds ?? []);
  const [assetIds, setAssetIds] = useState<string[]>(props.initialAssetIds ?? []);
  const [assetQuery, setAssetQuery] = useState("");

  const assetById = useMemo(
    () => new Map(props.assets.map((a) => [a.assetId, a])),
    [props.assets]
  );
  const topicById = useMemo(
    () => new Map(props.topics.map((t) => [t.topicId, t])),
    [props.topics]
  );

  const grouped = useMemo(() => {
    const m = new Map<string, Topic[]>();
    for (const t of props.topics) {
      const arr = m.get(t.category) ?? [];
      arr.push(t);
      m.set(t.category, arr);
    }
    return [...m.entries()];
  }, [props.topics]);

  // Assets suggested by the currently selected topics, not yet added.
  const suggestions = useMemo(() => {
    const set = new Set<string>();
    for (const tid of topicIds)
      for (const aid of topicById.get(tid)?.assetIds ?? []) set.add(aid);
    return [...set].filter((aid) => !assetIds.includes(aid));
  }, [topicIds, assetIds, topicById]);

  const fuse = useMemo(
    () => new Fuse(props.assets, { keys: ["symbol", "name"], threshold: 0.3 }),
    [props.assets]
  );
  const searchResults = assetQuery
    ? fuse
        .search(assetQuery)
        .map((r) => r.item)
        .filter((a) => !assetIds.includes(a.assetId))
        .slice(0, 6)
    : [];

  function toggleTopic(id: string) {
    setTopicIds((cur) =>
      cur.includes(id)
        ? cur.filter((t) => t !== id)
        : cur.length < props.maxTopics
          ? [...cur, id]
          : cur
    );
  }

  function addAsset(id: string) {
    setAssetIds((cur) =>
      cur.includes(id) || cur.length >= props.maxAssets ? cur : [...cur, id]
    );
    setAssetQuery("");
  }

  const canSubmit = name.trim().length > 0 && topicIds.length > 0 && !props.busy;

  return (
    <div className="space-y-6">
      <div>
        <label className="mb-1 block text-sm font-medium">{tr("lens.name")}</label>
        <input
          className="input"
          value={name}
          maxLength={60}
          placeholder={tr("lens.namePlaceholder")}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <label className="text-sm font-medium">{tr("lens.topics")}</label>
          <span className="text-xs text-ink-400">
            {topicIds.length}/{props.maxTopics} — {tr("lens.topicsHint")}
          </span>
        </div>
        <div className="card max-h-72 space-y-4 overflow-y-auto p-4">
          {grouped.map(([category, ts]) => (
            <div key={category}>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-400">
                {category}
              </div>
              <div className="flex flex-wrap gap-2">
                {ts.map((t) => {
                  const active = topicIds.includes(t.topicId);
                  return (
                    <button
                      key={t.topicId}
                      onClick={() => toggleTopic(t.topicId)}
                      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                        active
                          ? "bg-wing-600 text-white"
                          : "bg-ink-100 text-ink-600 hover:bg-ink-200"
                      }`}
                    >
                      {t.displayName}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <label className="text-sm font-medium">{tr("lens.trackedAssets")}</label>
          <span className="text-xs text-ink-400">
            {assetIds.length}/{props.maxAssets} — {tr("lens.trackedAssetsHint")}
          </span>
        </div>

        <div className="mb-2 flex flex-wrap gap-2">
          {assetIds.length === 0 && (
            <span className="text-xs text-ink-400">{tr("lens.noAssets")}</span>
          )}
          {assetIds.map((id) => {
            const a = assetById.get(id);
            return (
              <span key={id} className="chip">
                {a?.symbol ?? id}
                {a && !a.hasPriceFeed && (
                  <span className="text-ink-400" title="No price feed">
                    ⚠
                  </span>
                )}
                <button
                  onClick={() => setAssetIds((cur) => cur.filter((x) => x !== id))}
                  className="text-ink-400 hover:text-ink-800"
                >
                  ✕
                </button>
              </span>
            );
          })}
        </div>

        {suggestions.length > 0 && (
          <div className="mb-2 text-xs">
            <span className="text-ink-400">{tr("lens.suggestedFromTopics")} </span>
            {suggestions.map((id) => (
              <button
                key={id}
                onClick={() => addAsset(id)}
                className="mr-1 rounded-full border border-dashed border-ink-200 px-2 py-0.5 text-ink-600 hover:border-wing-500 hover:text-wing-600"
              >
                + {assetById.get(id)?.symbol ?? id}
              </button>
            ))}
          </div>
        )}

        <div className="relative">
          <input
            className="input"
            placeholder={tr("lens.searchAssets")}
            value={assetQuery}
            onChange={(e) => setAssetQuery(e.target.value)}
          />
          {searchResults.length > 0 && (
            <div className="card absolute z-10 mt-1 w-full overflow-hidden">
              {searchResults.map((a) => (
                <button
                  key={a.assetId}
                  onClick={() => addAsset(a.assetId)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-ink-50"
                >
                  <span>
                    <span className="font-medium">{a.symbol}</span>{" "}
                    <span className="text-ink-400">{a.name}</span>
                  </span>
                  {!a.hasPriceFeed && (
                    <span className="text-xs text-ink-400">{tr("lens.noPriceFeed")}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <button
        disabled={!canSubmit}
        onClick={() =>
          props.onSubmit({ name: name.trim(), topicIds, trackedAssetIds: assetIds })
        }
        className="btn-primary w-full"
      >
        {props.busy ? tr("lens.saving") : props.submitLabel}
      </button>
    </div>
  );
}
