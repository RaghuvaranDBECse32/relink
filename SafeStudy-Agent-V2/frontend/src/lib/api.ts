import type { Conversation, Doc, Health, Msg, Source, Summary, User } from "./types";

const TOKEN_KEY = "safestudy.token";
export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } };
export const setToken = (t: string | null) => {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
};

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : "Request failed"; } catch { /* non-JSON */ }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  register: (email: string, display_name: string, password: string) =>
    req<{ access_token: string; user: User }>("/auth/register", { method: "POST", body: JSON.stringify({ email, display_name, password }) }),
  login: (email: string, password: string) =>
    req<{ access_token: string; user: User }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => req<User>("/auth/me"),
  health: () => req<Health>("/health"),
  conversations: (q = "") => req<Conversation[]>(`/conversations${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  conversation: (id: string) => req<Conversation & { messages: Msg[] }>(`/conversations/${id}`),
  deleteConversation: (id: string) => req<void>(`/conversations/${id}`, { method: "DELETE" }),
  exportConversation: (id: string) => req<string>(`/conversations/${id}/export`),
  feedback: (message_id: string, rating: 1 | -1) => req(`/feedback`, { method: "POST", body: JSON.stringify({ message_id, rating }) }),
  documents: (q = "") => req<Doc[]>(`/documents${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  upload: (file: File, topic: string) => {
    const f = new FormData(); f.append("file", file); f.append("topic", topic);
    return req<Doc>("/documents", { method: "POST", body: f });
  },
  deleteDocument: (id: string) => req<void>(`/documents/${id}`, { method: "DELETE" }),
  summary: () => req<Summary>("/analytics/summary"),
};

export interface StreamHandlers {
  onMeta: (conversationId: string) => void;
  onSources: (s: Source[]) => void;
  onToken: (t: string) => void;
  onReplace: (t: string) => void;
  onDone: (d: { message_id: string; is_safe: boolean; model?: string }) => void;
  onError: (m: string) => void;
}

/** POST + Server-Sent Events over fetch (EventSource can't send auth headers). */
export async function streamChat(message: string, conversationId: string | null, h: StreamHandlers, signal?: AbortSignal) {
  const res = await fetch("/api/chat/stream", {
    method: "POST", signal,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken() ?? ""}` },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok || !res.body) { h.onError(res.status === 401 ? "Session expired. Please sign in again." : "Could not reach the server."); return; }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i); buf = buf.slice(i + 2);
      const ev = /^event: (.+)$/m.exec(block)?.[1];
      const raw = /^data: (.+)$/m.exec(block)?.[1];
      if (!ev || !raw) continue;
      const d = JSON.parse(raw);
      if (ev === "meta") h.onMeta(d.conversation_id);
      else if (ev === "sources") h.onSources(d.sources);
      else if (ev === "token") h.onToken(d.text);
      else if (ev === "replace") h.onReplace(d.text);
      else if (ev === "done") h.onDone(d);
      else if (ev === "error") h.onError(d.message);
    }
  }
}
