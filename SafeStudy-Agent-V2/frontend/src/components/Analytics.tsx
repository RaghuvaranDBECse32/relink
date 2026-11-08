import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Summary } from "../lib/types";

export default function Analytics() {
  const [s, setS] = useState<Summary | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { api.summary().then(setS).catch(() => setErr(true)); }, []);

  if (err) return <p className="p-6 text-bad" role="alert">Could not load your progress.</p>;
  if (!s) return <p className="p-6 text-mute">Loading…</p>;
  const max = Math.max(1, ...s.activity.map((a) => a.questions));
  const stats = [
    { v: s.questions, l: "Questions asked" },
    { v: s.conversations, l: "Conversations" },
    { v: s.grounded_rate === null ? "–" : `${Math.round(s.grounded_rate * 100)}%`, l: "Answers backed by notes" },
    { v: `${s.helpful}/${s.helpful + s.not_helpful}`, l: "Rated helpful" },
  ];
  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto p-5">
      <h1 className="text-2xl font-extrabold">Progress</h1>
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((x) => (
          <div key={x.l} className="card p-4"><div className="font-mono text-3xl font-semibold">{x.v}</div><div className="mt-1 text-sm text-mute">{x.l}</div></div>
        ))}
      </div>
      <section className="card mt-5 p-5" aria-label="Activity in the last 7 days">
        <h2 className="font-extrabold">Last 7 days</h2>
        <div className="mt-4 flex h-36 items-end gap-2">
          {s.activity.map((a) => (
            <div key={a.day} className="flex flex-1 flex-col items-center gap-1">
              <span className="font-mono text-xs text-mute">{a.questions || ""}</span>
              <div className="w-full rounded-t-md bg-brand" style={{ height: `${(a.questions / max) * 100}%`, minHeight: a.questions ? 4 : 2, opacity: a.questions ? 1 : 0.25 }} />
              <span className="font-mono text-xs text-mute">{new Date(a.day + "T00:00").toLocaleDateString(undefined, { weekday: "short" })}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="card mt-5 p-5">
        <h2 className="font-extrabold">Topics</h2>
        {s.topics.length === 0 ? <p className="mt-2 text-mute">Ask a question in Study and your topics will show up here.</p> : (
          <ul className="mt-3 space-y-3">
            {s.topics.map((t) => (
              <li key={t.topic}>
                <div className="flex justify-between text-sm"><span className="font-semibold">{t.topic}</span><span className="font-mono text-mute">{t.questions} asked</span></div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-brand" style={{ width: `${(t.grounded / Math.max(1, t.questions)) * 100}%` }} /></div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
