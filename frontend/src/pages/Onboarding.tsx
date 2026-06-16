import { useState } from "react";
import { api, loadStatic } from "../api/client";
import { useAsync } from "../api/hooks";
import { useAuth } from "../auth";
import { Asset, Lens, Topic, TopicSuggestion } from "../api/types";
import { LensEditor } from "../components/LensEditor";
import { Spinner, Toast } from "../components/ui";

export default function Onboarding() {
  const { refresh } = useAuth();
  const topics = useAsync(() => loadStatic<Topic[]>("taxonomy.json"), []);
  const assets = useAsync(() => loadStatic<Asset[]>("assets.json"), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // AI interest -> topic suggestion
  const [interests, setInterests] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [seed, setSeed] = useState<{ topicIds: string[]; assetIds: string[]; key: number }>({
    topicIds: [],
    assetIds: [],
    key: 0,
  });

  if (topics.loading || assets.loading) return <Spinner label="Loading topics…" />;
  if (!topics.data || !assets.data)
    return <Toast message="Could not load topics." onClose={() => topics.reload()} />;

  async function suggestFromInterests() {
    const text = interests.trim();
    if (!text || suggesting) return;
    setSuggesting(true);
    try {
      const res = await api.post<TopicSuggestion>("/topics/suggest", { text });
      if (res.topicIds.length === 0 && res.assetIds.length === 0) {
        setError("Couldn't find matching topics — try describing your interests differently.");
        return;
      }
      // Remount the editor with the suggested selections (key bump).
      setSeed((s) => ({ topicIds: res.topicIds, assetIds: res.assetIds, key: s.key + 1 }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Suggestion failed");
    } finally {
      setSuggesting(false);
    }
  }

  async function create(data: {
    name: string;
    topicIds: string[];
    trackedAssetIds: string[];
  }) {
    setBusy(true);
    try {
      await api.post<Lens>("/lenses", data);
      await refresh(); // lensCount > 0 → App routes to the main shell
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create lens");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-6 text-center">
        <div className="mb-1 text-3xl text-wing-600">◆</div>
        <h1 className="text-2xl font-semibold tracking-tight">Create your first lens</h1>
        <p className="mt-1 text-sm text-ink-400">
          A lens is a set of topics you want to follow. Describe what you care about and let
          AI pick the topics, or choose them yourself below.
        </p>
      </div>

      {/* AI interest box */}
      <div className="card mb-5 p-5">
        <label className="mb-1 block text-sm font-medium">Tell us your interests</label>
        <p className="mb-3 text-xs text-ink-400">
          In plain words — e.g. “US national debt and the US dollar.” We’ll suggest the
          relevant topics (and related drivers), which you can then tweak.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <textarea
            className="input min-h-[44px] flex-1 resize-none"
            rows={1}
            placeholder="What are you interested in?"
            value={interests}
            maxLength={500}
            onChange={(e) => setInterests(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) suggestFromInterests();
            }}
          />
          <button
            className="btn-primary shrink-0"
            disabled={suggesting || !interests.trim()}
            onClick={suggestFromInterests}
          >
            {suggesting ? "Thinking…" : "✨ Suggest topics"}
          </button>
        </div>
        {seed.key > 0 && (
          <p className="mt-2 text-xs text-wing-600">
            Suggested {seed.topicIds.length} topic{seed.topicIds.length === 1 ? "" : "s"}
            {seed.assetIds.length > 0 && ` and ${seed.assetIds.length} asset${seed.assetIds.length === 1 ? "" : "s"}`}{" "}
            below — adjust anything you like.
          </p>
        )}
      </div>

      <div className="card p-6">
        <LensEditor
          key={seed.key}
          topics={topics.data}
          assets={assets.data}
          maxTopics={10}
          maxAssets={10}
          initialName={interests.trim() ? interests.trim().slice(0, 60) : ""}
          initialTopicIds={seed.topicIds}
          initialAssetIds={seed.assetIds}
          submitLabel="Create lens"
          onSubmit={create}
          busy={busy}
        />
      </div>
      {error && <Toast message={error} onClose={() => setError(null)} />}
    </div>
  );
}
