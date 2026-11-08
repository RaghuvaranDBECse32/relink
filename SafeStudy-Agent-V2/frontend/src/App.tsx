import { useCallback, useEffect, useState } from "react";
import { api, getToken, setToken } from "./lib/api";
import type { User } from "./lib/types";
import { useTheme } from "./lib/theme";
import Auth from "./components/Auth";
import Chat from "./components/Chat";
import Library from "./components/Library";
import Analytics from "./components/Analytics";
import Settings from "./components/Settings";
import MusicPlayer from "./components/MusicPlayer";

type View = "study" | "library" | "analytics" | "settings";
const NAV: { id: View; label: string; icon: string }[] = [
  { id: "study", label: "Study", icon: "M4 5h16v11H8l-4 4V5z" },
  { id: "library", label: "Library", icon: "M5 4h10a3 3 0 013 3v13H8a3 3 0 01-3-3V4z" },
  { id: "analytics", label: "Progress", icon: "M5 20V10m7 10V4m7 16v-7" },
  { id: "settings", label: "Settings", icon: "M12 15a3 3 0 100-6 3 3 0 000 6zm7-3l2-1-2-4-2 1-2-1V5h-4v2l-2 1-2-1-2 4 2 1v2l-2 1 2 4 2-1 2 1v2h4v-2l2-1 2 1 2-4-2-1v-2z" },
];

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(!!getToken());
  const [view, setView] = useState<View>("study");
  const [theme, setTheme] = useTheme();

  useEffect(() => {
    if (!getToken()) return;
    api.me().then(setUser).catch(() => setToken(null)).finally(() => setBooting(false));
  }, []);

  const signOut = useCallback(() => { setToken(null); setUser(null); }, []);

  if (booting) return <div className="grid h-full place-items-center text-mute">Loading…</div>;
  if (!user) return <Auth onAuth={(t, u) => { setToken(t); setUser(u); }} />;

  return (
    <div className="mx-auto flex h-full max-w-[1400px] flex-col lg:flex-row">
      <nav aria-label="Primary" className="order-last flex shrink-0 justify-around border-t border-line bg-surface p-2 lg:order-first lg:w-64 lg:flex-col lg:justify-start lg:gap-1 lg:border-r lg:border-t-0 lg:bg-transparent lg:p-4">
        <div className="mb-6 hidden items-center gap-3 px-3 lg:flex">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand text-lg font-extrabold text-white">S</span>
          <span className="text-xl font-extrabold tracking-tight">Safe<span className="font-extralight">Study</span></span>
        </div>
        {NAV.map((n) => (
          <button key={n.id} onClick={() => setView(n.id)} aria-current={view === n.id ? "page" : undefined}
            className={`flex items-center gap-4 rounded-full px-4 py-3 text-lg transition-colors hover:bg-brandsoft ${view === n.id ? "font-extrabold" : "font-light"}`}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={view === n.id ? 2.4 : 1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={n.icon} /></svg>
            <span className="hidden lg:inline">{n.label}</span>
            <span className="sr-only lg:hidden">{n.label}</span>
          </button>
        ))}
        <div className="mt-auto hidden items-center gap-3 rounded-full p-3 lg:flex">
          <span className="grid h-10 w-10 place-items-center rounded-full bg-brandsoft font-extrabold text-brand">{user.display_name[0]?.toUpperCase()}</span>
          <div className="min-w-0"><div className="truncate text-sm font-semibold">{user.display_name}</div><div className="truncate font-mono text-xs text-mute">{user.email}</div></div>
        </div>
      </nav>
      <main className="min-h-0 flex-1">
        {view === "study" && <Chat />}
        {view === "library" && <Library />}
        {view === "analytics" && <Analytics />}
        {view === "settings" && <Settings user={user} theme={theme} setTheme={setTheme} onSignOut={signOut} />}
      </main>
      <MusicPlayer />
    </div>
  );
}
