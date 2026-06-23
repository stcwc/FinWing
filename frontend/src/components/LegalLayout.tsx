import { ReactNode } from "react";
import { Link } from "react-router-dom";

/** Standalone, auth-free layout for the public legal pages (privacy, terms).
 *  Deliberately self-contained: no API calls or auth state, so the pages render
 *  for signed-out visitors and crawlers alike. */
export function LegalLayout({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-ink-50 text-ink-800">
      <header className="border-b border-ink-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2">
            <img src="/finwing-logo.png" alt="FinWing" className="h-8 w-auto" />
          </Link>
          <nav className="flex gap-4 text-sm text-ink-600">
            <Link to="/privacy" className="hover:text-ink-900">Privacy</Link>
            <Link to="/terms" className="hover:text-ink-900">Terms</Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-2xl font-semibold text-ink-900">{title}</h1>
        <p className="mt-1 text-sm text-ink-400">Last updated: {updated}</p>
        <div className="mt-8 space-y-7 text-sm leading-relaxed text-ink-600">
          {children}
        </div>
      </main>

      <footer className="border-t border-ink-200 py-8 text-center text-xs text-ink-400">
        © {new Date().getFullYear()} FinWing ·{" "}
        <Link to="/privacy" className="hover:text-ink-600">Privacy</Link> ·{" "}
        <Link to="/terms" className="hover:text-ink-600">Terms</Link>
      </footer>
    </div>
  );
}

/** A titled section within a legal page. */
export function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-base font-semibold text-ink-900">{heading}</h2>
      {children}
    </section>
  );
}
