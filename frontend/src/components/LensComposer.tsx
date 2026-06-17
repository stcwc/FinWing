import { useState } from "react";
import { api } from "../api/client";
import { Asset, Topic, TopicSuggestion } from "../api/types";
import { useI18n } from "../i18n";
import { LensEditor } from "./LensEditor";

interface Props {
  topics: Topic[];
  assets: Asset[];
  maxTopics: number;
  maxAssets: number;
  submitLabel: string;
  onSubmit: (data: { name: string; topicIds: string[]; trackedAssetIds: string[] }) => void;
  busy?: boolean;
  /** Show the free-form "Tell us your interests" AI helper (new-lens only). */
  showSuggest?: boolean;
  initialName?: string;
  initialTopicIds?: string[];
  initialAssetIds?: string[];
}

/**
 * Lens editor plus the optional AI interest helper. Typing free-form interests
 * calls /topics/suggest and pre-selects the returned topics/assets by remounting
 * the editor (key bump) with new initial values — the user can still edit them.
 */
export function LensComposer(props: Props) {
  const { t } = useI18n();
  const [interests, setInterests] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seed, setSeed] = useState({
    name: props.initialName ?? "",
    topicIds: props.initialTopicIds ?? [],
    assetIds: props.initialAssetIds ?? [],
    key: 0,
    suggested: false,
  });

  async function suggest() {
    const text = interests.trim();
    if (!text || suggesting) return;
    setSuggesting(true);
    setError(null);
    try {
      const res = await api.post<TopicSuggestion>("/topics/suggest", { text });
      if (res.topicIds.length === 0 && res.assetIds.length === 0) {
        setError(t("compose.suggestFailed"));
        return;
      }
      setSeed((s) => ({
        name: text.slice(0, 60),
        topicIds: res.topicIds,
        assetIds: res.assetIds,
        key: s.key + 1,
        suggested: true,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Suggestion failed");
    } finally {
      setSuggesting(false);
    }
  }

  return (
    <div>
      {props.showSuggest && (
        <div className="mb-5 rounded-lg border border-dashed border-ink-200 bg-ink-50 p-4">
          <label className="mb-1 block text-sm font-medium">{t("compose.interestsLabel")}</label>
          <p className="mb-3 text-xs text-ink-400">{t("compose.interestsHint")}</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <textarea
              className="input min-h-[44px] flex-1 resize-none"
              rows={1}
              placeholder={t("compose.interestsPlaceholder")}
              value={interests}
              maxLength={500}
              onChange={(e) => setInterests(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) suggest();
              }}
            />
            <button
              className="btn-primary shrink-0"
              disabled={suggesting || !interests.trim()}
              onClick={suggest}
            >
              {suggesting ? t("compose.thinking") : t("compose.suggest")}
            </button>
          </div>
          {seed.suggested && (
            <p className="mt-2 text-xs text-wing-600">
              {t("compose.suggestedPrefix")} {seed.topicIds.length}{" "}
              {seed.topicIds.length === 1 ? t("compose.topic") : t("compose.topics")}
              {seed.assetIds.length > 0 &&
                ` + ${seed.assetIds.length} ${
                  seed.assetIds.length === 1 ? t("compose.asset") : t("compose.assets")
                }`}{" "}
              {t("compose.suggestedSuffix")}
            </p>
          )}
          {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        </div>
      )}

      <LensEditor
        key={seed.key}
        topics={props.topics}
        assets={props.assets}
        maxTopics={props.maxTopics}
        maxAssets={props.maxAssets}
        initialName={seed.name}
        initialTopicIds={seed.topicIds}
        initialAssetIds={seed.assetIds}
        submitLabel={props.submitLabel}
        onSubmit={props.onSubmit}
        busy={props.busy}
      />
    </div>
  );
}
