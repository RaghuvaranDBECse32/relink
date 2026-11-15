"""SQLite persistence + accounts + messaging. Standard library only."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, re, secrets, sqlite3, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = os.environ.get("RELINK_DB", str(Path(__file__).resolve().parent.parent / "data" / "relink.db"))
USERNAME_RE = re.compile(r"^[a-z0-9_]{3,24}$")
TOKEN_TTL = 12 * 3600

class ApiError(Exception):
    def __init__(self, status: int, message: str): self.status, self.message = status, message

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
  pw_hash TEXT NOT NULL, created_at TEXT NOT NULL, token_ver INTEGER NOT NULL DEFAULT 0,
  read_receipts INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS contact_requests(id INTEGER PRIMARY KEY, from_id INTEGER NOT NULL, to_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, UNIQUE(from_id,to_id));
CREATE TABLE IF NOT EXISTS blocks(blocker_id INTEGER NOT NULL, blocked_id INTEGER NOT NULL, PRIMARY KEY(blocker_id,blocked_id));
CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, reporter_id INTEGER NOT NULL, target_user_id INTEGER,
  message_id INTEGER, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT, dm_key TEXT UNIQUE,
  created_by INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members(conv_id INTEGER NOT NULL, user_id INTEGER NOT NULL, last_read_id INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(conv_id,user_id));
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, conv_id INTEGER NOT NULL, sender_id INTEGER NOT NULL,
  body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conv_id,id);
CREATE TABLE IF NOT EXISTS verifications(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, result TEXT NOT NULL);
"""

def now() -> str: return datetime.now(timezone.utc).isoformat(timespec="seconds")

def connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10); c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    with connect() as c: c.executescript(SCHEMA)

def purge_old_messages(days: int):
    if days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        with connect() as c: c.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))

# ---------- credentials (scrypt + HMAC-signed expiring tokens; no custom cryptography) ----------
def _secret() -> bytes:
    env = os.environ.get("RELINK_SECRET")
    if env: return env.encode()
    p = Path(DB_PATH).parent / ".secret"; p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists(): p.write_bytes(secrets.token_bytes(32)); os.chmod(p, 0o600)
    return p.read_bytes()

def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()

def verify_password(pw: str, stored: str) -> bool:
    try:
        _, s, d = stored.split("$"); salt, dk = base64.b64decode(s), base64.b64decode(d)
        return hmac.compare_digest(hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32), dk)
    except Exception: return False

def _b64(b: bytes) -> str: return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _unb64(s: str) -> bytes: return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def make_token(uid: int, ver: int) -> str:
    body = _b64(json.dumps({"u": uid, "v": ver, "e": int(time.time()) + TOKEN_TTL}).encode())
    return body + "." + _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())

def user_from_token(c, token: str):
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(_b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest()), sig): return None
        p = json.loads(_unb64(body))
        if p["e"] < time.time(): return None
        u = c.execute("SELECT * FROM users WHERE id=?", (p["u"],)).fetchone()
        return u if u and u["token_ver"] == p["v"] else None
    except Exception: return None

# ---------- accounts ----------
def public_user(u) -> dict: return {"id": u["id"], "username": u["username"], "display_name": u["display_name"]}

def register(c, username: str, password: str, display_name: str | None):
    username = (username or "").strip().lower()
    if not USERNAME_RE.match(username): raise ApiError(400, "Username must be 3-24 characters: a-z, 0-9, underscore.")
    if len(password or "") < 10: raise ApiError(400, "Password must be at least 10 characters.")
    if password.lower() == username or password.lower() in {"password123", "1234567890"}: raise ApiError(400, "Choose a less guessable password.")
    dn = (display_name or username).strip()[:40] or username
    try:
        cur = c.execute("INSERT INTO users(username,display_name,pw_hash,created_at) VALUES(?,?,?,?)",
                        (username, dn, hash_password(password), now()))
    except sqlite3.IntegrityError: raise ApiError(409, "That username is taken.")
    u = c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"token": make_token(u["id"], u["token_ver"]), "user": public_user(u)}

def login(c, username: str, password: str):
    u = c.execute("SELECT * FROM users WHERE username=?", ((username or "").strip().lower(),)).fetchone()
    ok = verify_password(password or "", u["pw_hash"]) if u else verify_password(password or "", hash_password("x"))
    if not u or not ok: raise ApiError(401, "Invalid username or password.")
    return {"token": make_token(u["id"], u["token_ver"]), "user": public_user(u)}

def logout(c, u): c.execute("UPDATE users SET token_ver=token_ver+1 WHERE id=?", (u["id"],))

def update_me(c, u, display_name, read_receipts):
    if display_name is not None:
        c.execute("UPDATE users SET display_name=? WHERE id=?", (str(display_name).strip()[:40] or u["username"], u["id"]))
    if read_receipts is not None:
        c.execute("UPDATE users SET read_receipts=? WHERE id=?", (1 if read_receipts else 0, u["id"]))

def _by_username(c, username: str):
    v = c.execute("SELECT * FROM users WHERE username=?", ((username or "").strip().lower(),)).fetchone()
    if not v: raise ApiError(404, "User not found.")
    return v

def is_blocked(c, a: int, b: int) -> bool:
    return c.execute("SELECT 1 FROM blocks WHERE (blocker_id=? AND blocked_id=?) OR (blocker_id=? AND blocked_id=?)", (a, b, b, a)).fetchone() is not None

def search_users(c, u, q: str):
    q = re.sub(r"[^a-z0-9_]", "", (q or "").lower())
    if len(q) < 2: return []
    rows = c.execute("SELECT * FROM users WHERE username LIKE ? AND id<>? ORDER BY username LIMIT 10", (q + "%", u["id"])).fetchall()
    return [public_user(r) for r in rows if not is_blocked(c, u["id"], r["id"])]

# ---------- contacts / blocking / reporting ----------
def request_contact(c, u, username):
    v = _by_username(c, username)
    if v["id"] == u["id"]: raise ApiError(400, "You cannot add yourself.")
    if is_blocked(c, u["id"], v["id"]): raise ApiError(403, "Cannot send a request to this user.")
    inc = c.execute("SELECT * FROM contact_requests WHERE from_id=? AND to_id=?", (v["id"], u["id"])).fetchone()
    if inc and inc["status"] == "pending":
        c.execute("UPDATE contact_requests SET status='accepted' WHERE id=?", (inc["id"],)); return {"status": "accepted"}
    try: c.execute("INSERT INTO contact_requests(from_id,to_id,created_at) VALUES(?,?,?)", (u["id"], v["id"], now()))
    except sqlite3.IntegrityError: pass
    return {"status": "pending"}

def respond_contact(c, u, username, accept: bool):
    v = _by_username(c, username)
    r = c.execute("SELECT * FROM contact_requests WHERE from_id=? AND to_id=? AND status='pending'", (v["id"], u["id"])).fetchone()
    if not r: raise ApiError(404, "No pending request from that user.")
    if accept: c.execute("UPDATE contact_requests SET status='accepted' WHERE id=?", (r["id"],))
    else: c.execute("DELETE FROM contact_requests WHERE id=?", (r["id"],))
    return {"status": "accepted" if accept else "declined"}

def are_contacts(c, a, b) -> bool:
    return c.execute("SELECT 1 FROM contact_requests WHERE status='accepted' AND ((from_id=? AND to_id=?) OR (from_id=? AND to_id=?))", (a, b, b, a)).fetchone() is not None

def list_contacts(c, u):
    acc = c.execute("""SELECT users.* FROM contact_requests r JOIN users ON users.id = CASE WHEN r.from_id=? THEN r.to_id ELSE r.from_id END
        WHERE r.status='accepted' AND (r.from_id=? OR r.to_id=?) ORDER BY users.username""", (u["id"],) * 3).fetchall()
    inc = c.execute("SELECT users.* FROM contact_requests r JOIN users ON users.id=r.from_id WHERE r.to_id=? AND r.status='pending'", (u["id"],)).fetchall()
    out = c.execute("SELECT users.* FROM contact_requests r JOIN users ON users.id=r.to_id WHERE r.from_id=? AND r.status='pending'", (u["id"],)).fetchall()
    return {"contacts": [public_user(x) for x in acc], "incoming": [public_user(x) for x in inc], "outgoing": [public_user(x) for x in out]}

def block(c, u, username, on=True):
    v = _by_username(c, username)
    if v["id"] == u["id"]: raise ApiError(400, "You cannot block yourself.")
    if on: c.execute("INSERT OR IGNORE INTO blocks VALUES(?,?)", (u["id"], v["id"]))
    else: c.execute("DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?", (u["id"], v["id"]))
    return {"blocked": on}

def report(c, u, username, message_id, reason):
    reason = (reason or "").strip()[:500]
    if not reason: raise ApiError(400, "Please give a reason.")
    target = _by_username(c, username)["id"] if username else None
    if message_id:
        m = c.execute("SELECT m.id FROM messages m JOIN members mb ON mb.conv_id=m.conv_id AND mb.user_id=? WHERE m.id=?", (u["id"], message_id)).fetchone()
        if not m: raise ApiError(404, "Message not found.")
    c.execute("INSERT INTO reports(reporter_id,target_user_id,message_id,reason,created_at) VALUES(?,?,?,?,?)",
              (u["id"], target, message_id, reason, now()))
    return {"reported": True}

# ---------- conversations / messages ----------
def _member(c, conv_id, uid):
    if not c.execute("SELECT 1 FROM members WHERE conv_id=? AND user_id=?", (conv_id, uid)).fetchone(): raise ApiError(404, "Conversation not found.")

def open_direct(c, u, username):
    v = _by_username(c, username)
    if v["id"] == u["id"]: raise ApiError(400, "Pick another user.")
    if is_blocked(c, u["id"], v["id"]): raise ApiError(403, "You cannot message this user.")
    if not are_contacts(c, u["id"], v["id"]): raise ApiError(403, "Add this user as a contact first (they must accept).")
    key = f"{min(u['id'], v['id'])}:{max(u['id'], v['id'])}"
    r = c.execute("SELECT id FROM conversations WHERE dm_key=?", (key,)).fetchone()
    if r: return {"id": r["id"]}
    cur = c.execute("INSERT INTO conversations(kind,dm_key,created_by,created_at) VALUES('direct',?,?,?)", (key, u["id"], now()))
    for uid in (u["id"], v["id"]): c.execute("INSERT INTO members(conv_id,user_id) VALUES(?,?)", (cur.lastrowid, uid))
    return {"id": cur.lastrowid}

def create_group(c, u, title, usernames):
    title = (title or "").strip()[:60]
    if not title: raise ApiError(400, "Group needs a title.")
    others = [_by_username(c, n) for n in sorted(set(usernames or []))]
    if not 1 <= len(others) <= 49: raise ApiError(400, "Groups need 1-49 other members.")
    for v in others:
        if v["id"] == u["id"] or is_blocked(c, u["id"], v["id"]) or not are_contacts(c, u["id"], v["id"]):
            raise ApiError(403, f"Cannot add @{v['username']} (must be an accepted, unblocked contact).")
    cur = c.execute("INSERT INTO conversations(kind,title,created_by,created_at) VALUES('group',?,?,?)", (title, u["id"], now()))
    for uid in [u["id"]] + [v["id"] for v in others]: c.execute("INSERT INTO members(conv_id,user_id) VALUES(?,?)", (cur.lastrowid, uid))
    return {"id": cur.lastrowid}

def list_conversations(c, u):
    rows = c.execute("""SELECT cv.*, mb.last_read_id FROM conversations cv JOIN members mb ON mb.conv_id=cv.id AND mb.user_id=?""", (u["id"],)).fetchall()
    out = []
    for r in rows:
        peers = c.execute("SELECT users.* FROM members m JOIN users ON users.id=m.user_id WHERE m.conv_id=? AND m.user_id<>?", (r["id"], u["id"])).fetchall()
        last = c.execute("SELECT m.*, us.username FROM messages m JOIN users us ON us.id=m.sender_id WHERE conv_id=? ORDER BY m.id DESC LIMIT 1", (r["id"],)).fetchone()
        unread = c.execute("SELECT COUNT(*) n FROM messages WHERE conv_id=? AND id>? AND sender_id<>?", (r["id"], r["last_read_id"], u["id"])).fetchone()["n"]
        title = r["title"] if r["kind"] == "group" else (("@" + peers[0]["username"]) if peers else "(deleted user)")
        out.append({"id": r["id"], "kind": r["kind"], "title": title, "members": [x["username"] for x in peers], "unread": unread,
                    "last": ({"body": last["body"][:80], "at": last["created_at"], "by": last["username"]} if last else None)})
    out.sort(key=lambda x: (x["last"] or {"at": ""})["at"], reverse=True)
    return out

def get_messages(c, u, conv_id, after=0):
    _member(c, conv_id, u["id"])
    rows = c.execute("""SELECT m.id, m.body, m.created_at, m.sender_id, us.username FROM messages m JOIN users us ON us.id=m.sender_id
        WHERE conv_id=? AND m.id>? ORDER BY m.id LIMIT 200""", (conv_id, int(after))).fetchall()
    others = c.execute("""SELECT m.last_read_id, us.read_receipts FROM members m JOIN users us ON us.id=m.user_id WHERE m.conv_id=? AND m.user_id<>?""", (conv_id, u["id"])).fetchall()
    out = []
    for r in rows:
        mine = r["sender_id"] == u["id"]
        # "read" only when every other member has receipts enabled and has actually opened past this message; otherwise just "sent".
        state = None
        if mine: state = "read" if others and all(o["read_receipts"] and o["last_read_id"] >= r["id"] for o in others) else "sent"
        out.append({"id": r["id"], "body": r["body"], "at": r["created_at"], "sender": r["username"], "mine": mine, "state": state})
    return out

def send_message(c, u, conv_id, body):
    _member(c, conv_id, u["id"]); body = (body or "").strip()
    if not body: raise ApiError(400, "Message is empty.")
    if len(body) > 4000: raise ApiError(400, "Message too long (4000 max).")
    conv = c.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
    if conv["kind"] == "direct":
        peer = c.execute("SELECT user_id FROM members WHERE conv_id=? AND user_id<>?", (conv_id, u["id"])).fetchone()
        if peer and is_blocked(c, u["id"], peer["user_id"]): raise ApiError(403, "You cannot message this user.")
    cur = c.execute("INSERT INTO messages(conv_id,sender_id,body,created_at) VALUES(?,?,?,?)", (conv_id, u["id"], body, now()))
    c.execute("UPDATE members SET last_read_id=? WHERE conv_id=? AND user_id=?", (cur.lastrowid, conv_id, u["id"]))
    return {"id": cur.lastrowid, "at": now()}

def mark_read(c, u, conv_id):
    _member(c, conv_id, u["id"])
    c.execute("UPDATE members SET last_read_id=COALESCE((SELECT MAX(id) FROM messages WHERE conv_id=?),0) WHERE conv_id=? AND user_id=?", (conv_id, conv_id, u["id"]))
    return {"ok": True}

# ---------- data rights ----------
def export_account(c, u):
    msgs = c.execute("SELECT conv_id, body, created_at FROM messages WHERE sender_id=? ORDER BY id", (u["id"],)).fetchall()
    return {"exported_at": now(), "user": {"username": u["username"], "display_name": u["display_name"], "created_at": u["created_at"]},
            "contacts": list_contacts(c, u), "conversations": list_conversations(c, u),
            "messages_sent_by_you": [dict(m) for m in msgs],
            "note": "Messages from other people are not included in your export."}

def delete_account(c, u, password):
    if not verify_password(password or "", u["pw_hash"]): raise ApiError(403, "Password incorrect.")
    uid = u["id"]
    c.execute("DELETE FROM messages WHERE sender_id=?", (uid,))
    c.execute("DELETE FROM members WHERE user_id=?", (uid,))
    c.execute("DELETE FROM contact_requests WHERE from_id=? OR to_id=?", (uid, uid))
    c.execute("DELETE FROM blocks WHERE blocker_id=? OR blocked_id=?", (uid, uid))
    c.execute("DELETE FROM verifications WHERE user_id=?", (uid,))
    c.execute("DELETE FROM users WHERE id=?", (uid,))
    return {"deleted": True}
