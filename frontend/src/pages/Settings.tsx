import { useState } from "react";
import { api, loadStatic } from "../api/client";
import { useAsync } from "../api/hooks";
import { useAuth } from "../auth";
import { Asset, Lens, Topic, UserProfile } from "../api/types";
import { LensComposer } from "../components/LensComposer";
import { LanguageToggle } from "../components/LanguageToggle";
import { useI18n } from "../i18n";
import { EmptyState, Modal, Spinner, Toast } from "../components/ui";

export default function Settings() {
  const { refresh } = useAuth();
  const { t } = useI18n();
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
    if (!confirm(t("settings.deleteConfirm", { name: lens.name }))) return;
    await api.del(`/lenses/${lens.lensId}`);
    lenses.reload();
    refresh();
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="mb-4 text-xl font-semibold">{t("settings.title")}</h1>
        <div className="card mb-4 flex items-center justify-between p-4">
          <span className="text-sm font-medium">{t("settings.language")}</span>
          <LanguageToggle />
        </div>
        <SummaryTimeCard profile={profile.data!} onSaved={() => setToast(t("settings.saved"))} />
        <EmailSummaryCard
          profile={profile.data!}
          onSaved={() => setToast(t("settings.saved"))}
        />
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t("settings.lenses")}</h2>
          <button
            className="btn-primary"
            disabled={atCap}
            onClick={() => setEditing("new")}
            title={atCap ? t("settings.maxLenses") : undefined}
          >
            {t("settings.newLens")}
          </button>
        </div>

        {lenses.data?.length === 0 ? (
          <EmptyState title={t("feed.noLenses")} hint={t("feed.createInSettings")} />
        ) : (
          <div className="space-y-3">
            {lenses.data!.map((lens) => (
              <div key={lens.lensId} className="card flex items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{lens.name}</div>
                  <div className="mt-0.5 truncate text-xs text-ink-400">
                    {t("settings.topicsAssets", {
                      t: lens.topicIds.length,
                      a: lens.trackedAssetIds.length,
                    })}
                  </div>
                </div>
                <button className="btn-outline" onClick={() => setEditing(lens)}>
                  {t("settings.edit")}
                </button>
                <button
                  className="btn-ghost text-red-600 hover:bg-red-50"
                  onClick={() => removeLens(lens)}
                >
                  {t("settings.delete")}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {editing && (
        <Modal
          title={
            editing === "new"
              ? t("settings.newLensTitle")
              : t("settings.editLens", { name: editing.name })
          }
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
            submitLabel={editing === "new" ? t("lens.create") : t("lens.save")}
            onSubmit={saveLens}
          />
        </Modal>
      )}
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
}

function EmailSummaryCard({
  profile,
  onSaved,
}: {
  profile: UserProfile;
  onSaved: () => void;
}) {
  const { t } = useI18n();
  const [on, setOn] = useState(profile.emailSummaries);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    const next = !on;
    setOn(next); // optimistic
    setBusy(true);
    try {
      await api.patch("/users/me", { emailSummaries: next });
      onSaved();
    } catch {
      setOn(!next); // revert on failure
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card mt-4 flex items-center justify-between gap-4 p-4">
      <div className="min-w-0">
        <div className="text-sm font-medium">{t("settings.emailSummaries")}</div>
        <div className="mt-0.5 text-xs text-ink-400">
          {t("settings.emailSummariesHint", { email: profile.email })}
        </div>
      </div>
      <button
        role="switch"
        aria-checked={on}
        aria-label={t("settings.emailSummaries")}
        disabled={busy}
        onClick={toggle}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
          on ? "bg-wing-500" : "bg-ink-200"
        }`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
            on ? "translate-x-5" : "translate-x-0.5"
          }`}
        />
      </button>
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
  const { t } = useI18n();
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
      <div className="mb-3 text-sm font-medium">{t("settings.delivery")}</div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-ink-400">{t("settings.time")}</span>
          <input
            type="time"
            className="input w-36"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </label>
        <label className="flex-1 text-sm">
          <span className="mb-1 block text-ink-400">{t("settings.timezone")}</span>
          <input
            className="input"
            value={tz}
            onChange={(e) => setTz(e.target.value)}
            placeholder="America/New_York"
          />
        </label>
        <button className="btn-primary" disabled={busy} onClick={save}>
          {busy ? t("settings.saving") : t("settings.save")}
        </button>
      </div>
    </div>
  );
}
