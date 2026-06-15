import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import { ChatPanel } from "./ChatPanel";

const navItems = [
  { to: "/lenses", label: "Lenses" },
  { to: "/summaries", label: "Daily Summaries" },
  { to: "/settings", label: "Settings" },
  { to: "/feedback", label: "Feedback" },
];

export function Shell() {
  const { user, isAdmin, logout } = useAuth();
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-ink-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <div className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="text-wing-600">◆</span> FinWing
          </div>
          <nav className="flex items-center gap-1 text-sm">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 font-medium transition-colors ${
                    isActive
                      ? "bg-ink-100 text-ink-900"
                      : "text-ink-600 hover:bg-ink-50"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            {isAdmin && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 font-medium transition-colors ${
                    isActive ? "bg-ink-100 text-ink-900" : "text-ink-600 hover:bg-ink-50"
                  }`
                }
              >
                Admin
              </NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <button onClick={() => setChatOpen((v) => !v)} className="btn-outline">
              💬 Chat
            </button>
            <span className="hidden text-ink-400 sm:inline">{user?.email}</span>
            <button onClick={logout} className="btn-ghost">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-ink-200 py-4 text-center text-xs text-ink-400">
        FinWing provides news synthesis for information only — not financial advice.
      </footer>

      {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
    </div>
  );
}
