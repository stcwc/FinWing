import { useState } from "react";
import { api, loadStatic } from "../api/client";
import { useAsync } from "../api/hooks";
import { useAuth } from "../auth";
import { Asset, Lens, Topic, UserProfile } from "../api/types";
import { LensComposer } from "../components/LensComposer";
import { EmptyState, Modal, Spinner, Toast } from "../components/ui";

export default function Settings() {
  const { refresh } = useAuth();
  const profile = useAsync(() => api.get<UserProfile>("/users/me"), []);
  const lenses = useAsync(() => api.get<Lens[]>("/lenses"), []);
  const topics = useAsync(() => loadStatic<Topic[]>("taxonomy.json"), []);
  const assets = useAsync(() => loadStatic<Asset[]>("assets.json"), []);
  const [editing, setEditing] = useState<Lens | "new" | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  if (profile.loading || lenses.loading || topics.loading || assets.loading)
    return <Spinner />;

  const atCap = (lenses.data?.length ?? 0) >= 5;

  async function saveLens(data: {
    name: string;
    topicIds: string[];
    trackedAssetIds: string[];
  }) {
    try {
      if (editing === "new") await api.post("/lenses", data);
      else if (editing) await api.patch(`/lenses/${editing.lensId}`, data);
      setEditing(null);
      lenses.reload();
      refresh();
    } catch (e) {
      setToast(e instanceof Error ? e.message : "Failed to save lens");
    }
  }

  async function removeLens(lens: Lens) {
    if (!confirm(`Delete lens "${lens.name}"? Past summaries are kept.`)) return;
    await api.del(`/lenses/${lens.lensId}`);
    lenses.reload();
    refresh();
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="mb-4 text-xl font-semibold">Settings</h1>
        <SummaryTimeCard profile={profile.data!} onSaved={() => setToast("Saved.")} />
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Lenses</h2>
          <button
            className="btn-primary"
            disabled={atCap}
            onClick={() => setEditing("new")}
            title={atCap ? "Maximum 5 lenses" : undefined}
          >
            + New lens
          </button>
        </div>

        {lenses.data?.length === 0 ? (
          <EmptyState title="No lenses yet" hint="Create your first lens above." />
        ) : (
          <div className="space-y-3">
            {lenses.data!.map((lens) => (
              <div key={lens.lensId} className="card flex items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{lens.name}</div>
                  <div className="mt-0.5 truncate text-xs text-ink-400">
                    {lens.topicIds.length} topics · {lens.trackedAssetIds.length} tracked
                    assets
                  </div>
                </div>
                <button className="btn-outline" onClick={() => setEditing(lens)}>
                  Edit
                </button>
                <button
                  className="btn-ghost text-red-600 hover:bg-red-50"
                  onClick={() => removeLens(lens)}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {editing && (
        <Modal
          title={editing === "new" ? "New lens" : `Edit ${editing.name}`}
          onClose={() => setEditing(null)}
        >
          <LensComposer
            showSuggest={editing === "new"}
            topics={topics.data!}
            assets={assets.data!}
            maxTopics={10}
            maxAssets={10}
            initialName={editing === "new" ? "" : editing.name}
            initialTopicIds={editing === "new" ? [] : editing.topicIds}
            initialAssetIds={editing === "new" ? [] : editing.trackedAssetIds}
            submitLabel={editing === "new" ? "Create lens" : "Save changes"}
            onSubmit={saveLens}
          />
        </Modal>
      )}
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}

function SummaryTimeCard({
  profile,
  onSaved,
}: {
  profile: UserProfile;
  onSaved: () => void;
}) {
  const [time, setTime] = useState(profile.summaryTimePref);
  const [tz, setTz] = useState(profile.timezone);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await api.patch("/users/me", { summaryTimePref: time, timezone: tz });
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card p-4">
      <div className="mb-3 text-sm font-medium">Daily summary delivery</div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-ink-400">Time (local)</span>
          <input
            type="time"
            className="input w-36"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </label>
        <label className="flex-1 text-sm">
          <span className="mb-1 block text-ink-400">Timezone (IANA)</span>
          <input
            className="input"
            value={tz}
            onChange={(e) => setTz(e.target.value)}
            placeholder="America/New_York"
          />
        </label>
        <button className="btn-primary" disabled={busy} onClick={save}>
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
