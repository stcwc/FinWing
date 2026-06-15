import { api } from "../api/client";
import { useAsync } from "../api/hooks";
import { EmptyState, Spinner, timeAgo } from "../components/ui";

interface Metrics {
  userCount: number;
  signinsToday: number;
  activeToday: number;
}
interface FeedbackItem {
  userId: string;
  submittedAt: string;
  text: string;
  context?: string;
}

export default function Admin() {
  const metrics = useAsync(() => api.get<Metrics>("/admin/metrics"), []);
  const feedback = useAsync(
    () => api.get<{ items: FeedbackItem[] }>("/admin/feedback"),
    []
  );

  if (metrics.loading) return <Spinner />;

  const stats = [
    { label: "Total users", value: metrics.data?.userCount ?? 0 },
    { label: "Sign-ins today", value: metrics.data?.signinsToday ?? 0 },
    { label: "Active today", value: metrics.data?.activeToday ?? 0 },
  ];

  return (
    <div className="space-y-8">
      <section>
        <h1 className="mb-4 text-xl font-semibold">Admin</h1>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {stats.map((s) => (
            <div key={s.label} className="card p-5">
              <div className="text-3xl font-semibold text-ink-900">{s.value}</div>
              <div className="mt-1 text-sm text-ink-400">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Feedback</h2>
        {feedback.loading ? (
          <Spinner />
        ) : feedback.data?.items.length === 0 ? (
          <EmptyState title="No feedback yet" />
        ) : (
          <div className="space-y-3">
            {feedback.data!.items.map((f, i) => (
              <div key={i} className="card p-4">
                <div className="mb-1 flex items-center gap-2 text-xs text-ink-400">
                  <span className="font-mono">{f.userId.slice(0, 8)}</span>
                  <span>·</span>
                  <span>{timeAgo(f.submittedAt)}</span>
                </div>
                <p className="text-sm text-ink-800">{f.text}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
