import json, os, sys, tempfile, threading, unittest, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_tmp = tempfile.mkdtemp()
os.environ["RELINK_DB"] = os.path.join(_tmp, "t.db"); os.environ["RELINK_SECRET"] = "test-secret"
os.environ["AUTH_RATE_LIMIT"] = "1000"
for k in ("TAVILY_API_KEY", "BIFROST_BASE_URL", "GEMINI_API_KEY"): os.environ.pop(k, None)
from relink import lunar, verify, teacher, store, llm
import server
U = timezone.utc

class TestLunar(unittest.TestCase):
    def test_meeus_example_moon_position(self):  # Meeus AA ch.47 worked example, 1992-04-12 0h TD
        lon, lat, d = lunar.moon_ecliptic(2448724.5)
        self.assertAlmostEqual(float(lon[0]), 133.162655, delta=0.002)
        self.assertAlmostEqual(float(lat[0]), -3.229126, delta=0.002)
        self.assertAlmostEqual(float(d[0]), 368409.7, delta=30)
    def test_meeus_example_libration(self):  # ch.53: optical l'=-1.206, b'=+4.194
        l, b = lunar.sub_earth(2448724.5)
        self.assertAlmostEqual(float(l[0]), -1.206, delta=0.02); self.assertAlmostEqual(float(b[0]), 4.194, delta=0.02)
    def test_2026_new_moon_and_eclipse(self):
        ts = [datetime(2026, 11, 8, tzinfo=U) + timedelta(minutes=5 * i) for i in range(12 * 24 * 12)]
        j = [lunar.julian_day(t) for t in ts]; ml, _, _ = lunar.moon_ecliptic(j); sl, _ = lunar.sun_ecliptic(j)
        import numpy as np
        d = ((ml - sl + 180) % 360) - 180; i = int(np.where((d[:-1] < 0) & (d[1:] >= 0))[0][0])
        self.assertLess(abs((ts[i] - datetime(2026, 11, 9, 7, 2, tzinfo=U)).total_seconds()), 15 * 60)  # almanac new moon 2026-11-09 ~07:02 UTC
        e = lunar.elongation_deg(lunar.julian_day(datetime(2026, 8, 12, 17, 46, tzinfo=U)))  # total solar eclipse
        self.assertLess(float(e[0]), 1.5)
    def test_libration_bounds_over_year(self):
        l, b = lunar.sub_earth([lunar.julian_day(datetime(2026, 1, 1, tzinfo=U) + timedelta(hours=8 * i)) for i in range(1100)])
        self.assertLess(abs(l).max(), 8.6); self.assertLess(abs(b).max(), 7.0); self.assertGreater(abs(b).max(), 6.0)
    def test_pole_physics(self):
        r = lunar.analyse_site("pole", -90, 0, datetime(2026, 11, 14, tzinfo=U), 24 * 60, 120)
        se = r["series"]["sun_el"]; self.assertTrue(all(abs(x) < 2.0 for x in se))   # Sun stays within ~1.54 deg of horizon at the pole
        self.assertTrue(0.3 < r["earth"]["fraction"] < 0.7)                          # Earth visible roughly half of the libration cycle
    def test_equator_nearside_earth_high(self):
        g = lunar.site_geometry([lunar.julian_day(datetime(2026, 11, 14, tzinfo=U))], 0, 0)
        self.assertGreater(float(g["earth"][0][0]), 75)
    def test_validation(self):
        for kw in ({"lat": 95}, {"hours": 0}, {"step": 0}, {"mask": 45}):
            with self.assertRaises(ValueError):
                lunar.analyse_site("x", kw.get("lat", -88), 0, datetime(2026, 11, 14, tzinfo=U), kw.get("hours", 24), kw.get("step", 60), kw.get("mask", 0))

class TestAggregate(unittest.TestCase):
    now = datetime(2026, 11, 14, tzinfo=U)
    def ev(self, dom, days, stance=None):
        return {"domain": dom, "published": (self.now - timedelta(days=days)).date().isoformat() if days is not None else None, "snippet": "", "title": dom, "url": "https://" + dom}
    def J(self, t, **st): return {"claim_type": t, "stances": {i: (s, "") for i, s in st.items()}}
    def agg(self, evs, j): return verify.aggregate("c", evs, j, self.now)
    def test_current(self): self.assertEqual(self.agg([self.ev("a", 10)], {"claim_type": "volatile", "stances": {0: ("supports", "")}})["status"], "CURRENT")
    def test_recent_page_not_enough(self): self.assertEqual(self.agg([self.ev("a", 1)], {"claim_type": "volatile", "stances": {0: ("irrelevant", "")}})["status"], "UNVERIFIED")
    def test_old_support_is_stale(self): self.assertEqual(self.agg([self.ev("a", 500)], {"claim_type": "volatile", "stances": {0: ("supports", "")}})["status"], "STALE")
    def test_stable_claim_old_support_ok(self): self.assertEqual(self.agg([self.ev("a", 500)], {"claim_type": "stable", "stances": {0: ("supports", "")}})["status"], "CURRENT")
    def test_undated_support_unverified(self): self.assertEqual(self.agg([self.ev("a", None)], {"claim_type": "volatile", "stances": {0: ("supports", "")}})["status"], "UNVERIFIED")
    def test_superseded(self): self.assertEqual(self.agg([self.ev("a", 400), self.ev("b", 5)], {"claim_type": "volatile", "stances": {0: ("supports", ""), 1: ("supersedes", "")}})["status"], "STALE")
    def test_conflict(self): self.assertEqual(self.agg([self.ev("a", 5), self.ev("b", 5)], {"claim_type": "volatile", "stances": {0: ("supports", ""), 1: ("contradicts", "")}})["status"], "CONFLICTING")
    def test_no_evidence(self): self.assertEqual(self.agg([], None)["status"], "UNVERIFIED")
    def test_no_judge_needs_review(self): self.assertEqual(self.agg([self.ev("a", 1)], None)["status"], "NEEDS_REVIEW")
    def test_demo_covers_states(self): self.assertEqual({r["status"] for r in verify.demo()["results"]}, {"STALE", "CURRENT", "CONFLICTING", "UNVERIFIED"})
    def test_date_parse(self):
        self.assertEqual(verify.date_from_text("Published Mar 3, 2026 by X").date().isoformat(), "2026-03-03")
        self.assertEqual(verify.date_from_text("", "https://x.com/2025/07/09/story").date().isoformat(), "2025-07-09")

class _Mock(BaseHTTPRequestHandler):
    seen = []
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Mock.seen.append((self.path, self.headers.get("Authorization"), self.headers.get("x-goog-api-key"), body))
        recent = (datetime.now(U) - timedelta(days=7)).date().isoformat()
        if self.path == "/search":
            out = {"results": [{"title": "Official", "url": "https://gov.example/a", "content": "Jane Roe is CEO.", "score": 0.9, "published_date": recent}]}
        else:
            out = {"choices": [{"message": {"content": '```json\n{"claim_type":"volatile","stances":[{"i":0,"stance":"supports","reason":"states it"}]}\n```'}}]}
        b = json.dumps(out).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

class TestIntegrationsWithMock(unittest.TestCase):
    """Exercises our HTTP client code paths against a local stand-in; proves request shape, NOT that live APIs accept it."""
    def test_pipeline(self):
        srv = HTTPServer(("127.0.0.1", 0), _Mock); threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}"
        os.environ.update(TAVILY_API_KEY="tvly-test", TAVILY_API_URL=base + "/search", BIFROST_BASE_URL=base, BIFROST_API_KEY="bf-test", BIFROST_MODEL="gemini/gemini-2.5-flash")
        try:
            r = verify.verify("Jane Roe is the CEO of Acme.", "health")
            self.assertEqual(r["results"][0]["status"], "CURRENT"); self.assertEqual(r["judge"], "bifrost")
            tav = [s for s in _Mock.seen if s[0] == "/search"]; self.assertEqual(len(tav), 2)
            self.assertEqual(tav[0][1], "Bearer tvly-test"); self.assertIn("who.int", tav[0][3]["include_domains"]); self.assertEqual(tav[1][3]["topic"], "news")
            bf = [s for s in _Mock.seen if s[0] == "/v1/chat/completions"][0]
            self.assertEqual(bf[1], "Bearer bf-test"); self.assertEqual(bf[3]["model"], "gemini/gemini-2.5-flash")
        finally:
            for k in ("TAVILY_API_KEY", "TAVILY_API_URL", "BIFROST_BASE_URL", "BIFROST_API_KEY", "BIFROST_MODEL"): os.environ.pop(k, None)
            srv.shutdown()
    def test_no_key_is_honest(self):
        r = verify.verify("The latest lunar mission confirmed a new landing site.")
        self.assertEqual(r["results"][0]["status"], "UNVERIFIED"); self.assertEqual(r["results"][0]["sources"], [])

class TestTeacher(unittest.TestCase):
    def test_phish(self):
        r = teacher.analyze("URGENT account suspended, verify now http://paypa1-login.top/x and send your OTP")
        self.assertEqual(r["risk_level"], "high"); self.assertTrue(any(f["indicator"] == "digit_substitution" for f in r["links"][0]["findings"]))
    def test_benign(self): self.assertEqual(teacher.analyze("Lunch at 1pm tomorrow?")["risk_level"], "low")
    def test_url_tricks(self):
        f = {x["indicator"] for x in teacher.analyze("see http://192.168.1.5/login and http://bit.ly/abc and http://google.com@evil.xyz/")["links"][0]["findings"]}
        self.assertIn("ip_address_host", f)
    def test_health(self): self.assertTrue(any(i["category"] == "health" for i in teacher.analyze("Miracle cure that doctors hate!")["indicators"]))

class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = server.create_server("127.0.0.1", 0); cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
    def call(self, method, path, body=None, tok=None):
        req = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + tok} if tok else {})})
        try:
            with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
    def user(self, name):
        s, r = self.call("POST", "/api/auth/register", {"username": name, "password": "correct-horse-9"}); self.assertEqual(s, 200, r); return r["token"]

    def test_invalid_message_cursor(self):
        token = self.user("cursor_test")
        status, payload = self.call("GET", "/api/conversations/1/messages?after=abc", tok=token)
        self.assertEqual(status, 400)

    def test_password_max_length(self):
        status, payload = self.call("POST", "/api/auth/register", {
            "username": "long_password", "password": "a" * 129})
        self.assertEqual(status, 400)

    def test_static_and_status(self):
        self.assertEqual(self.call("GET", "/api/status")[1]["messaging"]["end_to_end_encryption"], False)
        with urllib.request.urlopen(self.base + "/") as r: self.assertIn("text/html", r.headers["Content-Type"]); self.assertIn("nosniff", r.headers["X-Content-Type-Options"])
        with urllib.request.urlopen(self.base + "/../server.py") as r: self.assertIn("html", r.read().decode().lower()[:200])  # traversal falls back to index
    def test_auth_rules(self):
        self.assertEqual(self.call("POST", "/api/auth/register", {"username": "ab", "password": "correct-horse-9"})[0], 400)
        self.assertEqual(self.call("POST", "/api/auth/register", {"username": "weakpw", "password": "short"})[0], 400)
        self.user("dupe_user"); self.assertEqual(self.call("POST", "/api/auth/register", {"username": "DUPE_user", "password": "correct-horse-9"})[0], 409)
        self.assertEqual(self.call("POST", "/api/auth/login", {"username": "dupe_user", "password": "wrong-pass-123"})[0], 401)
        self.assertEqual(self.call("GET", "/api/me")[0], 401); self.assertEqual(self.call("GET", "/api/me", tok="garbage.token")[0], 401)
        t = self.call("POST", "/api/auth/login", {"username": "dupe_user", "password": "correct-horse-9"})[1]["token"]
        self.assertEqual(self.call("GET", "/api/me", tok=t)[0], 200); self.call("POST", "/api/auth/logout", tok=t)
        self.assertEqual(self.call("GET", "/api/me", tok=t)[0], 401)   # logout revokes tokens
    def test_messaging_flow(self):
        a, b, c = self.user("alice_t"), self.user("bob_t"), self.user("carol_t")
        self.assertEqual(self.call("POST", "/api/direct", {"username": "bob_t"}, a)[0], 403)        # not contacts yet
        self.assertEqual(self.call("POST", "/api/contacts/request", {"username": "bob_t"}, a)[1]["status"], "pending")
        self.assertEqual(self.call("GET", "/api/contacts", tok=b)[1]["incoming"][0]["username"], "alice_t")
        self.call("POST", "/api/contacts/respond", {"username": "alice_t", "accept": True}, b)
        s, d = self.call("POST", "/api/direct", {"username": "bob_t"}, a); self.assertEqual(s, 200); cid = d["id"]
        self.call("POST", f"/api/conversations/{cid}/messages", {"body": "hello bob"}, a)
        convs = self.call("GET", "/api/conversations", tok=b)[1]["conversations"]; self.assertEqual(convs[0]["unread"], 1)
        self.assertEqual(self.call("GET", f"/api/conversations/{cid}/messages", tok=a)[1]["messages"][0]["state"], "sent")
        self.assertEqual(self.call("GET", f"/api/conversations/{cid}/messages", tok=c)[0], 404)       # outsider cannot read
        self.call("POST", f"/api/conversations/{cid}/read", {}, b)
        self.assertEqual(self.call("GET", f"/api/conversations/{cid}/messages", tok=a)[1]["messages"][0]["state"], "read")
        self.assertEqual(self.call("GET", "/api/conversations", tok=b)[1]["conversations"][0]["unread"], 0)
        self.call("PATCH", "/api/me", {"read_receipts": False}, b)
        self.call("POST", f"/api/conversations/{cid}/messages", {"body": "again"}, a); self.call("POST", f"/api/conversations/{cid}/read", {}, b)
        self.assertEqual(self.call("GET", f"/api/conversations/{cid}/messages?after=1", tok=a)[1]["messages"][-1]["state"], "sent")  # receipts off -> never 'read'
        self.assertEqual(self.call("POST", f"/api/conversations/{cid}/messages", {"body": " "}, a)[0], 400)
        self.assertEqual(self.call("POST", f"/api/conversations/{cid}/messages", {"body": "x" * 4001}, a)[0], 400)
        # groups need accepted contacts
        self.assertEqual(self.call("POST", "/api/groups", {"title": "g", "members": ["bob_t", "carol_t"]}, a)[0], 403)
        self.call("POST", "/api/contacts/request", {"username": "carol_t"}, a); self.call("POST", "/api/contacts/respond", {"username": "alice_t", "accept": True}, c)
        s, g = self.call("POST", "/api/groups", {"title": "trio", "members": ["bob_t", "carol_t"]}, a); self.assertEqual(s, 200)
        self.call("POST", f"/api/conversations/{g['id']}/messages", {"body": "group hi"}, a)
        self.assertEqual(self.call("GET", f"/api/conversations/{g['id']}/messages", tok=c)[1]["messages"][0]["body"], "group hi")
        # block + report
        self.assertEqual(self.call("POST", "/api/reports", {"username": "alice_t", "message_id": 1, "reason": "spam"}, b)[0], 200)
        self.call("POST", "/api/blocks", {"username": "alice_t"}, b)
        self.assertEqual(self.call("POST", f"/api/conversations/{cid}/messages", {"body": "blocked?"}, a)[0], 403)
        self.assertEqual(self.call("GET", "/api/users/search?q=alice", tok=b)[1]["users"], [])
    def test_export_delete(self):
        t = self.user("zed_user"); exp = self.call("GET", "/api/account/export", tok=t)[1]; self.assertEqual(exp["user"]["username"], "zed_user")
        self.assertEqual(self.call("POST", "/api/account/delete", {"password": "nope-nope-123"}, t)[0], 403)
        self.assertEqual(self.call("POST", "/api/account/delete", {"password": "correct-horse-9"}, t)[0], 200)
        self.assertEqual(self.call("GET", "/api/me", tok=t)[0], 401)
    def test_public_modules(self):
        self.assertEqual(self.call("POST", "/api/teacher/analyze", {"text": "send your OTP now"})[1]["risk_level"], "caution")
        self.assertGreaterEqual(len(self.call("GET", "/api/teacher/lessons")[1]["lessons"]), 6)
        self.assertEqual(self.call("GET", "/api/verify/demo")[1]["profile"], "demo")
        self.assertEqual(self.call("POST", "/api/verify", {"text": "short"})[0], 400)
        s, r = self.call("POST", "/api/luna/analyze", {"start": "2026-11-14T00:00:00Z", "hours": 48, "step_min": 60, "mask_deg": 0,
                         "sites": [{"name": "A", "latitude": -88, "longitude": 0}, {"name": "B", "latitude": -85, "longitude": 60}]})
        self.assertEqual(s, 200); self.assertEqual(len(r["results"]), 2); self.assertIn("limitations", r)
        self.assertEqual(self.call("POST", "/api/luna/analyze", {"start": "bad", "sites": []})[0], 400)
        self.assertEqual(self.call("POST", "/api/luna/analyze", {"start": "2026-11-14", "hours": 99999, "sites": [{"latitude": -88, "longitude": 0}]})[0], 400)

if __name__ == "__main__": unittest.main(verbosity=1)
