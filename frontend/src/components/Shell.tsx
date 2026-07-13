import { useCallback, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { TKey } from "../i18n/dict";
import { ArticleAttachment } from "../api/types";
import { ChatPanel } from "./ChatPanel";
import { ChatProvider } from "./chatContext";
import { LanguageToggle } from "./LanguageToggle";

const navItems: { to: string; key: TKey }[] = [
  { to: "/lenses", key: "nav.lenses" },
  { to: "/summaries", key: "nav.summaries" },
  { to: "/settings", key: "nav.settings" },
  { to: "/feedback", key: "nav.feedback" },
];

export function Shell() {
  const { user, isAdmin, logout } = useAuth();
  const { t } = useI18n();
  const [chatOpen, setChatOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [attachments, setAttachments] = useState<ArticleAttachment[]>([]);

  const addAttachment = useCallback((a: ArticleAttachment) => {
    setAttachments((prev) =>
      prev.some((p) => p.articleId === a.articleId) ? prev : [...prev, a]
    );
  }, []);
  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.articleId !== id));
  }, []);
  const openChat = useCallback(() => setChatOpen(true), []);

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-1.5 font-medium transition-colors ${
      isActive ? "bg-ink-100 text-ink-900" : "text-ink-600 hover:bg-ink-50"
    }`;
  const mobileNavClass = ({ isActive }: { isActive: boolean }) =>
    `block rounded-lg px-3 py-2 font-medium transition-colors ${
      isActive ? "bg-ink-100 text-ink-900" : "text-ink-700 hover:bg-ink-50"
    }`;

  const allNav = isAdmin
    ? [...navItems, { to: "/admin", key: "nav.admin" as TKey }]
    : navItems;

  return (
    <ChatProvider value={{ attachments, addAttachment, removeAttachment, openChat }}>
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-30 border-b border-ink-200 bg-white/80 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
            <img src="/finwing-logo.png" alt="FinWing" className="h-7 w-auto" />

            {/* Desktop nav */}
            <nav className="hidden items-center gap-1 text-sm md:flex">
              {allNav.map((item) => (
                <NavLink key={item.to} to={item.to} className={navClass}>
                  {t(item.key)}
                </NavLink>
              ))}
            </nav>

            {/* Desktop actions */}
            <div className="ml-auto hidden items-center gap-3 text-sm md:flex">
              <LanguageToggle />
              <button onClick={() => setChatOpen((v) => !v)} className="btn-outline">
                💬 {t("nav.chat")}
              </button>
              <span className="text-ink-400">{user?.email}</span>
              <button onClick={logout} className="btn-ghost">
                {t("nav.signOut")}
              </button>
            </div>

            {/* Mobile actions: chat + burger */}
            <div className="ml-auto flex items-center gap-1 md:hidden">
              <button
                onClick={() => setChatOpen((v) => !v)}
                className="rounded-lg px-2 py-1.5 text-lg leading-none hover:bg-ink-100"
                aria-label={t("nav.chat")}
              >
                💬
              </button>
              <button
                onClick={() => setMenuOpen((v) => !v)}
                className="rounded-lg px-2 py-1.5 text-xl leading-none text-ink-700 hover:bg-ink-100"
                aria-label={t("nav.menu")}
                aria-expanded={menuOpen}
              >
                {menuOpen ? "✕" : "☰"}
              </button>
            </div>
          </div>

          {/* Mobile dropdown menu */}
          {menuOpen && (
            <div className="space-y-1 border-t border-ink-200 bg-white px-4 py-3 text-sm md:hidden">
              {allNav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={mobileNavClass}
                  onClick={() => setMenuOpen(false)}
                >
                  {t(item.key)}
                </NavLink>
              ))}
              <div className="my-2 border-t border-ink-200" />
              <div className="flex items-center justify-between px-1">
                <LanguageToggle />
                <span className="truncate text-ink-400">{user?.email}</span>
              </div>
              <button
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
                className="mt-2 w-full rounded-lg px-3 py-2 text-left font-medium text-ink-700 hover:bg-ink-50"
              >
                {t("nav.signOut")}
              </button>
            </div>
          )}
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          <Outlet />
        </main>

        <footer className="border-t border-ink-200 py-4 text-center text-xs text-ink-400">
          {t("footer.disclaimer")}
        </footer>

        {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
      </div>
    </ChatProvider>
  );
}
