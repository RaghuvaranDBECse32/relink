# ReLink — reliable links, verified signals

One platform, five trust problems, one codebase:

| Module | What it does | Competition fit |
|---|---|---|
| **Chat** | Independent messenger: accounts, contacts, groups, unread/read state, block/report, data export & delete | Hack2skill Buildathon (Open Innovation) |
| **Security Teacher** | Opt-in, explainable screening of a message/link you paste + 8 lessons with quizzes | Hack2skill Buildathon · Future Health (health-scam rules) |
| **Verify** | Stale-answer detector: Tavily evidence → LLM judge via **Bifrost** (or Gemini) → deterministic CURRENT / STALE / CONFLICTING / UNVERIFIED. Health profile = official sources only | Global AI Hackathon (Tavily *Stale-Answer Detector*, Bifrost) · Future Health |
| **Link Planner** | Sun/Earth elevation, visibility windows and site comparison at lunar south-pole sites (UTC) | NASA Space Apps (*Lunar Landing Site Navigator*) |
| **Lunar Relay** | Match-3 & tower-defence lunar link game: power relay towers to defeat noise waves during link windows | Jabali AI Game Jam · NASA Space Apps Companion |

ReLink is an **independent** service. It does not bypass, impersonate or interoperate with WhatsApp or any other platform.

## Run (no build step, Python 3.10+)
```bash
pip install -r requirements.txt     # numpy only (Link Planner)
python server.py                    # http://localhost:8080
python -m unittest discover -s tests   # 29 tests
```
Optional keys: copy `.env.example`, export the variables. Without keys Verify returns **UNVERIFIED** (it never fakes evidence) and a clearly-labelled **synthetic demo** shows the classifier.

Docker / Cloud Run: `docker build -t relink . && docker run -p 8080:8080 relink` (deploy behind HTTPS; keys in Secret Manager; mount a volume or use Cloud SQL for durable data).

## Architecture
`static/` (vanilla JS, no CDN, CSP-safe) → `server.py` (stdlib HTTP, routing, rate limits, security headers) → `relink/store.py` (SQLite, scrypt, signed expiring tokens), `teacher.py`, `verify.py` (Tavily client + aggregator), `llm.py` (Bifrost / Gemini REST), `lunar.py` (ephemeris + geometry).

## Honest status (read this)
- **Not end-to-end encrypted.** The server can read messages. HTTPS only when you deploy it behind TLS. Polling, not WebSockets. No delivered-state, no attachments, no groups admin roles.
- **Verify** needs `TAVILY_API_KEY` and a judge (`BIFROST_BASE_URL` or `GEMINI_API_KEY`). Our tests prove request shapes and logic against local stand-ins; **live Tavily/Bifrost/Gemini calls have not been exercised here** — run one real check before you demo. Confirm Bifrost's endpoint/model naming against its current docs.
- **Link Planner** is an analytic ephemeris (Meeus), flat horizon + mask angle, **not JPL SPICE/Horizons and not terrain-aware**. Crater-floor sites are really permanently shadowed; flat-horizon results overstate their sunlight. Earth "visibility" is geometry, not a radio link. See `docs/METHODS.md`.
- Security Teacher is rule-based screening, not a malware scanner.

## Layout
`server.py` · `relink/` · `static/` · `tests/test_all.py` · `docs/` (METHODS, SUBMISSIONS, DEMO_SCRIPT, screenshots)
