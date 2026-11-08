import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { api, streamChat } from "../lib/api";
import type { Conversation, Msg, Source } from "../lib/types";

const SUGGESTIONS = ["Explain 2NF with an example", "What is deadlock?", "TCP vs UDP", "How does binary search work?"];

function Cited({ text, sources, onPick }: { text: string; sources: Source[]; onPick: (i: number) => void }) {
  return (
    <>
      {text.split(/(\[\d+\])/g).map((p, i) => {
        const m = /^\[(\d+)\]$/.exec(p);
        if (m && sources[+m[1] - 1])
          return <button key={i} onClick={() => onPick(+m[1] - 1)} className="mx-0.5 rounded-md bg-brandsoft px-1.5 font-mono text-xs font-semibold text-brand hover:opacity-80" aria-label={`Source ${m[1]}`}>{m[1]}</button>;
        return <span key={i}>{p}</span>;
      })}
    </>
  );
}

export default function Chat() {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [search, setSearch] = useState("");
  const [active, setActive] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const [focus, setFocus] = useState<number | null>(null);
  const [railOpen, setRailOpen] = useState(false);
  const [voted, setVoted] = useState<Record<string, 1 | -1>>({});
  const endRef = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  const loadList = useCallback((q = "") => api.conversations(q).then(setConvs).catch(() => {}), []);
  useEffect(() => { const t = setTimeout(() => loadList(search), 200); return () => clearTimeout(t); }, [search, loadList]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);
  useEffect(() => () => abort.current?.abort(), []);

  async function open(id: string) {
    setActive(id); setFocus(null); setRailOpen(false); setError("");
    try { setMsgs((await api.conversation(id)).messages); } catch { setError("Could not load this conversation."); }
  }
  function fresh() { abort.current?.abort(); setActive(null); setMsgs([]); setFocus(null); setError(""); setRailOpen(false); }

  async function send(text: string) {
    const q = text.trim();
    if (!q || streaming) return;
    setInput(""); setError(""); setStreaming(true); setFocus(null);
    setMsgs((m) => [...m, { id: `u${Date.now()}`, role: "user", content: q }, { id: "pending", role: "assistant", content: "", sources: [] }]);
    const patch = (fn: (m: Msg) => Msg) => setMsgs((all) => all.map((m) => (m.id === "pending" ? fn(m) : m)));
    abort.current = new AbortController();
    try {
      await streamChat(q, active, {
        onMeta: (id) => setActive(id),
        onSources: (s) => patch((m) => ({ ...m, sources: s })),
        onToken: (t) => patch((m) => ({ ...m, content: m.content + t })),
        onReplace: (t) => patch((m) => ({ ...m, content: t })),
        onDone: (d) => patch((m) => ({ ...m, id: d.message_id, is_safe: d.is_safe, model: d.model })),
        onError: (e) => { setError(e); patch((m) => ({ ...m, id: "failed" })); },
      }, abort.current.signal);
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError("Connection lost. Please try again.");
    } finally { setStreaming(false); loadList(search); }
  }

  const last = [...msgs].reverse().find((m) => m.role === "assistant" && m.sources?.length);
  const sources = last?.sources ?? [];

  async function exportMd() {
    if (!active) return;
    const md = await api.exportConversation(active);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
    a.download = "safestudy-conversation.md"; a.click(); URL.revokeObjectURL(a.href);
  }

  const rail = (
    <aside aria-label="History and sources" className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto p-4">
      <div className="flex gap-2">
        <input className="input" placeholder="Search history" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search history" />
        <button className="btn-primary shrink-0" onClick={fresh}>New</button>
      </div>
      <ul className="space-y-1">
        {convs.length === 0 && <li className="px-2 text-sm text-mute">No conversations yet.</li>}
        {convs.map((c) => (
          <li key={c.id} className="group flex items-center">
            <button onClick={() => open(c.id)} className={`min-w-0 flex-1 truncate rounded-xl px-3 py-2 text-left text-sm hover:bg-brandsoft ${c.id === active ? "bg-brandsoft font-semibold" : ""}`}>{c.title}</button>
            <button aria-label={`Delete ${c.title}`} onClick={async () => { await api.deleteConversation(c.id); if (c.id === active) fresh(); loadList(search); }} className="px-2 text-mute opacity-0 hover:text-bad focus:opacity-100 group-hover:opacity-100">✕</button>
          </li>
        ))}
      </ul>
      <div className="mt-2 border-t border-line pt-4">
        <h3 className="mb-2 text-sm font-extrabold">Sources for the latest answer</h3>
        {sources.length === 0 ? <p className="text-sm text-mute">Cited passages appear here.</p> : (
          <ol className="space-y-2">
            {sources.map((s, i) => (
              <li key={s.chunk_id} className={`card p-3 text-sm ${focus === i ? "border-brand" : ""}`}>
                <div className="flex items-center justify-between gap-2"><span className="font-mono text-xs font-semibold text-brand">[{i + 1}]</span><span className="font-mono text-xs text-mute">match {Math.round(s.score * 100)}%</span></div>
                <div className="mt-1 font-semibold">{s.title}</div>
                <p className="mt-1 text-mute">{s.text}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </aside>
  );

  return (
    <div className="flex h-full min-h-0">
      <section aria-label="Conversation" className="flex min-w-0 flex-1 flex-col border-line xl:border-r">
        <header className="flex items-center justify-between border-b border-line px-5 py-4">
          <h1 className="text-xl font-extrabold">Study</h1>
          <div className="flex gap-2">
            {active && <button className="btn-ghost" onClick={exportMd}>Export</button>}
            <button className="btn-ghost xl:hidden" onClick={() => setRailOpen(true)}>History</button>
          </div>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto" role="log" aria-live="polite">
          {msgs.length === 0 ? (
            <div className="mx-auto max-w-xl px-6 py-16">
              <h2 className="text-4xl font-extrabold tracking-tight">What are you studying?</h2>
              <p className="mt-3 text-mute">Answers come from the built-in CS notes and anything you add in Library.</p>
              <div className="mt-8 flex flex-wrap gap-2">{SUGGESTIONS.map((s) => <button key={s} className="btn-ghost" onClick={() => send(s)}>{s}</button>)}</div>
            </div>
          ) : msgs.map((m) => (
            <article key={m.id} className="flex gap-3 border-b border-line px-5 py-5">
              <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-full text-sm font-extrabold ${m.role === "user" ? "bg-brandsoft text-brand" : "bg-brand text-white"}`}>{m.role === "user" ? "You" : "S"}</span>
              <div className="min-w-0 flex-1">
                <p className={`whitespace-pre-wrap leading-relaxed ${m.id === "pending" && streaming ? "caret" : ""}`}>
                  {m.role === "assistant" ? <Cited text={m.content} sources={m.sources ?? []} onPick={setFocus} /> : m.content}
                </p>
                {m.role === "assistant" && m.is_safe === false && <p className="mt-2 text-sm text-warn">Safety engine intervened on this response.</p>}
                {m.role === "assistant" && m.model && m.id !== "pending" && m.id !== "failed" && (
                  <div className="mt-3 flex items-center gap-3 text-xs text-mute">
                    <span className="font-mono">{m.model}</span>
                    {([1, -1] as const).map((r) => (
                      <button key={r} aria-label={r === 1 ? "Helpful" : "Not helpful"} disabled={!!voted[m.id]} onClick={async () => { await api.feedback(m.id, r).catch(() => {}); setVoted((v) => ({ ...v, [m.id]: r })); }}
                        className={`hover:text-ink disabled:cursor-default ${voted[m.id] === r ? "font-extrabold text-brand" : ""}`}>{r === 1 ? "Helpful" : "Not helpful"}</button>
                    ))}
                  </div>
                )}
              </div>
            </article>
          ))}
          <div ref={endRef} />
        </div>
        {error && <p role="alert" className="border-t border-line px-5 py-2 text-sm text-bad">{error}</p>}
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); send(input); }} className="flex items-end gap-3 border-t border-line p-4">
          <textarea className="input max-h-40 min-h-[44px] resize-none" rows={1} maxLength={4000} value={input} placeholder="Ask about a topic in your notes" aria-label="Message"
            onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }} />
          <button className="btn-primary" disabled={streaming || !input.trim()}>{streaming ? "Answering…" : "Ask"}</button>
        </form>
      </section>
      <div className="hidden w-[360px] shrink-0 xl:block">{rail}</div>
      {railOpen && (
        <div className="fixed inset-0 z-20 flex justify-end bg-black/50 xl:hidden" onClick={() => setRailOpen(false)}>
          <div className="h-full w-[88%] max-w-sm bg-canvas" onClick={(e) => e.stopPropagation()}>{rail}</div>
        </div>
      )}
    </div>
  );
}
