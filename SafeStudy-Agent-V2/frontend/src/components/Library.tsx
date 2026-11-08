import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Doc } from "../lib/types";

export default function Library() {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const load = (s = q) => api.documents(s).then(setDocs).catch(() => setDocs([]));
  useEffect(() => { const t = setTimeout(() => load(q), 200); return () => clearTimeout(t); }, [q]); // eslint-disable-line

  async function upload() {
    const f = file.current?.files?.[0];
    if (!f) { setMsg({ ok: false, text: "Choose a PDF, TXT or MD file first." }); return; }
    setBusy(true); setMsg(null);
    try {
      const d = await api.upload(f, topic || "General");
      setMsg({ ok: true, text: `Indexed “${d.title}” into ${d.chunk_count} passages.` });
      if (file.current) file.current.value = "";
      load();
    } catch (e) { setMsg({ ok: false, text: e instanceof Error ? e.message : "Upload failed" }); }
    finally { setBusy(false); }
  }

  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto p-5">
      <h1 className="text-2xl font-extrabold">Library</h1>
      <p className="mt-1 text-mute">Upload notes and they become citable sources in Study.</p>
      <div className="card mt-5 grid gap-3 p-4 sm:grid-cols-[1fr_180px_auto]">
        <input ref={file} type="file" accept=".pdf,.txt,.md" className="input" aria-label="Document file" />
        <input className="input" placeholder="Topic (e.g. DBMS)" value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={120} aria-label="Topic" />
        <button className="btn-primary" onClick={upload} disabled={busy}>{busy ? "Indexing…" : "Upload"}</button>
        {msg && <p role="status" className={`text-sm sm:col-span-3 ${msg.ok ? "text-ok" : "text-bad"}`}>{msg.text}</p>}
      </div>
      <input className="input mt-5" placeholder="Search documents" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search documents" />
      <ul className="mt-4 space-y-2">
        {docs === null && <li className="text-mute">Loading…</li>}
        {docs?.length === 0 && <li className="card p-6 text-center text-mute">Nothing matches. Upload a document to get started.</li>}
        {docs?.map((d) => (
          <li key={d.id} className="card flex items-center justify-between gap-3 p-4">
            <div className="min-w-0">
              <div className="truncate font-semibold">{d.title}</div>
              <div className="mt-0.5 text-sm text-mute">{d.topic} <span className="font-mono">· {d.chunk_count} passages</span>{d.builtin && " · built in"}</div>
            </div>
            {!d.builtin && <button className="btn-ghost" onClick={async () => { await api.deleteDocument(d.id); load(); }} aria-label={`Delete ${d.title}`}>Delete</button>}
          </li>
        ))}
      </ul>
    </div>
  );
}
