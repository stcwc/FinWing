import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { TKey } from "../i18n/dict";
import { ChatPanel } from "./ChatPanel";
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

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-1.5 font-medium transition-colors ${
      isActive ? "bg-ink-100 text-ink-900" : "text-ink-600 hover:bg-ink-50"
    }`;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-ink-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <img src="/finwing-logo.png" alt="FinWing" className="h-7 w-auto" />
          <nav className="flex items-center gap-1 text-sm">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={navClass}>
                {t(item.key)}
              </NavLink>
            ))}
            {isAdmin && (
              <NavLink to="/admin" className={navClass}>
                {t("nav.admin")}
              </NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <LanguageToggle />
            <button onClick={() => setChatOpen((v) => !v)} className="btn-outline">
              💬 {t("nav.chat")}
            </button>
            <span className="hidden text-ink-400 sm:inline">{user?.email}</span>
            <button onClick={logout} className="btn-ghost">
              {t("nav.signOut")}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-ink-200 py-4 text-center text-xs text-ink-400">
        {t("footer.disclaimer")}
      </footer>

      {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
    </div>
  );
}
