import { FormEvent, useState } from "react";
import { api } from "../lib/api";
import type { User } from "../lib/types";

export default function Auth({ onAuth }: { onAuth: (token: string, u: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault(); setError(""); setBusy(true);
    try {
      const r = mode === "login" ? await api.login(email, password) : await api.register(email, name, password);
      onAuth(r.access_token, r.user);
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong"); }
    finally { setBusy(false); }
  }

  return (
    <div className="grid h-full place-items-center p-4">
      <div className="grid w-full max-w-4xl gap-10 md:grid-cols-2 md:items-center">
        <div>
          <h1 className="text-5xl font-extrabold leading-[1.05] tracking-tight">Ask your notes.<br /><span className="font-extralight">Get answers you can check.</span></h1>
          <p className="mt-5 max-w-sm text-mute">SafeStudy answers from the material you upload and shows exactly which passage backed each claim.</p>
        </div>
        <form onSubmit={submit} className="card space-y-3 p-6" aria-label={mode === "login" ? "Sign in" : "Create account"}>
          <h2 className="text-xl font-extrabold">{mode === "login" ? "Sign in" : "Create your account"}</h2>
          {mode === "register" && <input className="input" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} aria-label="Name" />}
          <input className="input" type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" aria-label="Email" />
          <input className="input" type="password" placeholder="Password (8+ characters)" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete={mode === "login" ? "current-password" : "new-password"} aria-label="Password" />
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
          <button type="button" className="w-full text-sm text-mute hover:text-ink" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
