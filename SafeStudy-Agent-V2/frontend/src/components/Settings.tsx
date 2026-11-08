import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Health, User } from "../lib/types";
import type { ThemeMode } from "../lib/theme";

export default function Settings({ user, theme, setTheme, onSignOut }: {
  user: User; theme: ThemeMode; setTheme: (m: ThemeMode) => void; onSignOut: () => void;
}) {
  const [h, setH] = useState<Health | null>(null);
  useEffect(() => { api.health().then(setH).catch(() => setH(null)); }, []);
  const rows: [string, string][] = h ? [["AI model", h.llm], ["Vector store", h.vector_store], ["Embeddings", h.embeddings]] : [];
  return (
    <div className="mx-auto h-full max-w-xl overflow-y-auto p-5">
      <h1 className="text-2xl font-extrabold">Settings</h1>
      <section className="card mt-5 p-5">
        <h2 className="font-extrabold">Appearance</h2>
        <div className="mt-3 flex gap-2" role="radiogroup" aria-label="Theme">
          {(["system", "light", "dark"] as ThemeMode[]).map((m) => (
            <button key={m} role="radio" aria-checked={theme === m} onClick={() => setTheme(m)} className={`btn flex-1 border capitalize ${theme === m ? "border-brand bg-brandsoft text-brand" : "border-line"}`}>{m}</button>
          ))}
        </div>
      </section>
      <section className="card mt-4 p-5">
        <h2 className="font-extrabold">Account</h2>
        <p className="mt-2 text-sm">{user.display_name}</p>
        <p className="font-mono text-sm text-mute">{user.email}</p>
        <button className="btn-ghost mt-4" onClick={onSignOut}>Sign out</button>
      </section>
      <section className="card mt-4 p-5">
        <h2 className="font-extrabold">System status</h2>
        {!h ? <p className="mt-2 text-sm text-bad">Backend unreachable.</p> : (
          <dl className="mt-3 space-y-2 text-sm">
            {rows.map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-mute">{k}</dt><dd className="font-mono">{v}</dd></div>)}
          </dl>
        )}
        {h?.llm === "offline-fallback" && <p className="mt-3 text-sm text-warn">No Gemini key configured. Answers are extracted straight from your notes.</p>}
        {h?.embeddings === "hash" && <p className="mt-2 text-sm text-mute">Hashed embeddings match on wording. Set EMBEDDING_BACKEND=sentence-transformers for true semantic search.</p>}
      </section>
    </div>
  );
}
