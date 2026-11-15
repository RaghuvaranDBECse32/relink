#!/usr/bin/env python3
"""ReLink server: JSON API + static UI on one port. Run: python server.py  (PORT env, default 8080)."""
from __future__ import annotations
import json, mimetypes, os, re, threading, time
from collections import defaultdict, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from relink import store, teacher, verify, lunar, llm, __version__
from relink.store import ApiError

STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 64 * 1024
_hits: dict[str, deque] = defaultdict(deque); _lock = threading.Lock()

def rate_ok(key: str, limit: int, per: int = 60) -> bool:
    with _lock:
        q = _hits[key]; t = time.time()
        while q and q[0] < t - per: q.popleft()
        if len(q) >= limit: return False
        q.append(t); return True

def status_payload():
    return {"version": __version__, "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "integrations": {"tavily_configured": bool(os.environ.get("TAVILY_API_KEY")),
                             "llm_provider": llm.provider() or "none",
                             "bifrost_configured": bool(os.environ.get("BIFROST_BASE_URL")),
                             "gemini_configured": bool(os.environ.get("GEMINI_API_KEY"))},
            "messaging": {"transport": "HTTP polling (WebSocket planned)", "end_to_end_encryption": False,
                          "encryption_in_transit": "only when deployed behind HTTPS", "encryption_at_rest": False,
                          "retention_days": int(os.environ.get("RETENTION_DAYS", "0")) or "off"},
            "lunar_model": "analytic series (Meeus), flat horizon + mask; not SPICE/Horizons; not terrain-aware"}

# ---- handlers: (ctx) -> json. ctx has c (db), u (user|None), q (query), b (body), p (path params) ----
def h_register(x): return store.register(x.c, x.b.get("username"), x.b.get("password"), x.b.get("display_name"))
def h_login(x): return store.login(x.c, x.b.get("username"), x.b.get("password"))
def h_logout(x): store.logout(x.c, x.u); return {"ok": True}
def h_me(x): return {**store.public_user(x.u), "read_receipts": bool(x.u["read_receipts"])}
def h_patch_me(x): store.update_me(x.c, x.u, x.b.get("display_name"), x.b.get("read_receipts")); return {"ok": True}
def h_search(x): return {"users": store.search_users(x.c, x.u, x.q.get("q", ""))}
def h_contacts(x): return store.list_contacts(x.c, x.u)
def h_creq(x): return store.request_contact(x.c, x.u, x.b.get("username"))
def h_cresp(x): return store.respond_contact(x.c, x.u, x.b.get("username"), bool(x.b.get("accept")))
def h_block(x): return store.block(x.c, x.u, x.b.get("username"), True)
def h_unblock(x): return store.block(x.c, x.u, x.b.get("username"), False)
def h_report(x): return store.report(x.c, x.u, x.b.get("username"), x.b.get("message_id"), x.b.get("reason"))
def h_direct(x): return store.open_direct(x.c, x.u, x.b.get("username"))
def h_group(x): return store.create_group(x.c, x.u, x.b.get("title"), x.b.get("members"))
def h_convs(x): return {"conversations": store.list_conversations(x.c, x.u)}
def h_msgs(x): return {"messages": store.get_messages(x.c, x.u, int(x.p[0]), int(x.q.get("after", 0) or 0))}
def h_send(x): return store.send_message(x.c, x.u, int(x.p[0]), x.b.get("body"))
def h_read(x): return store.mark_read(x.c, x.u, int(x.p[0]))
def h_export(x): return store.export_account(x.c, x.u)
def h_delete(x): return store.delete_account(x.c, x.u, x.b.get("password"))
def h_status(x): return status_payload()

def h_lessons(x): return {"lessons": teacher.LESSONS}
def h_analyze(x):
    t = x.b.get("text", "")
    if not isinstance(t, str) or not t.strip(): raise ApiError(400, "Provide the text you want analysed.")
    return teacher.analyze(t[:8000])

def h_verify(x):
    t = x.b.get("text") or x.b.get("claim") or ""
    if not isinstance(t, str) or len(t.strip()) < 8: raise ApiError(400, "Provide a claim or answer to check (8+ characters).")
    if not rate_ok("verify:" + x.ip, 12): raise ApiError(429, "Verification rate limit reached. Try again in a minute.")
    try: res = verify.verify(t[:4000], x.b.get("profile", "general"))
    except RuntimeError as e: raise ApiError(502, str(e))
    if x.u: x.c.execute("INSERT INTO verifications(user_id,created_at,result) VALUES(?,?,?)", (x.u["id"], store.now(), json.dumps(res)))
    return res
def h_vdemo(x): return verify.demo()
def h_vhist(x):
    rows = x.c.execute("SELECT id,created_at,result FROM verifications WHERE user_id=? ORDER BY id DESC LIMIT 20", (x.u["id"],)).fetchall()
    return {"history": [{"id": r["id"], "at": r["created_at"], "result": json.loads(r["result"])} for r in rows]}

def h_sites(x): return {"sites": lunar.SITES, "limitations": lunar.LIMITATIONS}
def h_luna(x):
    b = x.b
    try:
        start = datetime.fromisoformat(str(b.get("start", "")).replace("Z", "+00:00"))
        if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
        sites = b.get("sites") or []
        if not 1 <= len(sites) <= 4: raise ValueError("choose 1-4 sites")
        res = [lunar.analyse_site(str(s.get("name", "Site"))[:60], float(s["latitude"]), float(s["longitude"]), start,
                                  float(b.get("hours", 720)), float(b.get("step_min", 60)), float(b.get("mask_deg", 0))) for s in sites]
    except (ValueError, KeyError, TypeError) as e: raise ApiError(400, f"Invalid input: {e}")
    return {"timezone": "UTC", "start": start.isoformat(), "results": res, "limitations": lunar.LIMITATIONS,
            "model": "Meeus analytic series + optical libration; flat horizon with mask angle"}

# (method, regex, handler, auth, rate-limit-per-minute for this route group or None)
ROUTES = [
 ("GET", r"/api/status", h_status, False), ("POST", r"/api/auth/register", h_register, False), ("POST", r"/api/auth/login", h_login, False),
 ("POST", r"/api/auth/logout", h_logout, True), ("GET", r"/api/me", h_me, True), ("PATCH", r"/api/me", h_patch_me, True),
 ("GET", r"/api/users/search", h_search, True), ("GET", r"/api/contacts", h_contacts, True),
 ("POST", r"/api/contacts/request", h_creq, True), ("POST", r"/api/contacts/respond", h_cresp, True),
 ("POST", r"/api/blocks", h_block, True), ("POST", r"/api/blocks/remove", h_unblock, True), ("POST", r"/api/reports", h_report, True),
 ("POST", r"/api/direct", h_direct, True), ("POST", r"/api/groups", h_group, True), ("GET", r"/api/conversations", h_convs, True),
 ("GET", r"/api/conversations/(\d+)/messages", h_msgs, True), ("POST", r"/api/conversations/(\d+)/messages", h_send, True),
 ("POST", r"/api/conversations/(\d+)/read", h_read, True), ("GET", r"/api/account/export", h_export, True), ("POST", r"/api/account/delete", h_delete, True),
 ("GET", r"/api/teacher/lessons", h_lessons, False), ("POST", r"/api/teacher/analyze", h_analyze, False),
 ("POST", r"/api/verify", h_verify, False), ("GET", r"/api/verify/demo", h_vdemo, False), ("GET", r"/api/verify/history", h_vhist, True),
 ("GET", r"/api/luna/sites", h_sites, False), ("POST", r"/api/luna/analyze", h_luna, False),
]
ROUTES = [(m, re.compile("^" + p + "$"), h, a) for m, p, h, a in ROUTES]

class Ctx:  # request context
    pass

class Handler(BaseHTTPRequestHandler):
    server_version = "ReLink/" + __version__; protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *a):
        if os.environ.get("RELINK_LOG"): super().log_message(fmt, *a)

    def _send(self, code, payload, ctype="application/json; charset=utf-8", extra=None):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("X-Frame-Options", "DENY"); self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-store" if ctype.startswith("application/json") else "no-cache")
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def _ip(self): return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        f = (STATIC / rel).resolve()
        if STATIC.resolve() not in f.parents or not f.is_file(): f = STATIC / "index.html"
        self._send(200, f.read_bytes(), mimetypes.guess_type(str(f))[0] or "application/octet-stream")

    def _dispatch(self, method):
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            if method == "GET": return self._static(url.path)
            return self._send(405, {"error": "Method not allowed"})
        ip = self._ip()
        if not rate_ok("g:" + ip, 240): return self._send(429, {"error": "Too many requests."})
        if url.path.startswith("/api/auth/") and not rate_ok("a:" + ip, int(os.environ.get("AUTH_RATE_LIMIT", "12"))): return self._send(429, {"error": "Too many attempts. Wait a minute."})
        for m, rx, fn, auth in ROUTES:
            mt = rx.match(url.path)
            if m == method and mt:
                c = store.connect()
                try:
                    x = Ctx(); x.c, x.ip, x.p, x.q = c, ip, mt.groups(), {k: v[0] for k, v in parse_qs(url.query).items()}
                    x.b = {}; x.u = None
                    if method in ("POST", "PATCH"):
                        n = int(self.headers.get("Content-Length") or 0)
                        if n > MAX_BODY: raise ApiError(413, "Request too large.")
                        if n:
                            try: x.b = json.loads(self.rfile.read(n).decode())
                            except ValueError: raise ApiError(400, "Body must be valid JSON.")
                            if not isinstance(x.b, dict): raise ApiError(400, "Body must be a JSON object.")
                    h = self.headers.get("Authorization", "")
                    if h.startswith("Bearer "): x.u = store.user_from_token(c, h[7:])
                    if auth and not x.u: raise ApiError(401, "Please sign in.")
                    out = fn(x); c.commit(); return self._send(200, out)
                except ApiError as e: c.rollback(); return self._send(e.status, {"error": e.message})
                except Exception:
                    c.rollback()
                    if os.environ.get("RELINK_LOG"): raise
                    return self._send(500, {"error": "Internal error."})
                finally: c.close()
        self._send(404, {"error": "Not found."})

    def do_GET(self): self._dispatch("GET")
    def do_POST(self): self._dispatch("POST")
    def do_PATCH(self): self._dispatch("PATCH")

def create_server(host="0.0.0.0", port=8080):
    store.init_db(); store.purge_old_messages(int(os.environ.get("RETENTION_DAYS", "0") or 0))
    return ThreadingHTTPServer((host, port), Handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080")); srv = create_server(port=port)
    print(f"ReLink {__version__} on http://localhost:{port}  (integrations: {status_payload()['integrations']})")
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
