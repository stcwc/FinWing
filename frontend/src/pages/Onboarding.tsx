import { useState } from "react";
import { api, loadStatic } from "../api/client";
import { useAsync } from "../api/hooks";
import { useAuth } from "../auth";
import { Asset, Lens, Topic } from "../api/types";
import { LensComposer } from "../components/LensComposer";
import { Spinner, Toast } from "../components/ui";

export default function Onboarding() {
  const { refresh } = useAuth();
  const topics = useAsync(() => loadStatic<Topic[]>("taxonomy.json"), []);
  const assets = useAsync(() => loadStatic<Asset[]>("assets.json"), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (topics.loading || assets.loading) return <Spinner label="Loading topics…" />;
  if (!topics.data || !assets.data)
    return <Toast message="Could not load topics." onClose={() => topics.reload()} />;

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
        <img src="/apple-touch-icon.png" alt="" className="mx-auto mb-2 h-12 w-12" />
        <h1 className="text-2xl font-semibold tracking-tight">Create your first lens</h1>
        <p className="mt-1 text-sm text-ink-400">
          A lens is a set of topics you want to follow. Describe what you care about and let
          AI pick the topics, or choose them yourself below.
        </p>
      </div>

      <div className="card p-6">
        <LensComposer
          showSuggest
          topics={topics.data}
          assets={assets.data}
          maxTopics={10}
          maxAssets={10}
          submitLabel="Create lens"
          onSubmit={create}
          busy={busy}
        />
      </div>
      {error && <Toast message={error} onClose={() => setError(null)} />}
    </div>
  );
}
