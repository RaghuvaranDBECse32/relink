"""Verify: stale-answer / evidence-freshness engine (Global AI Hackathon: Tavily + Bifrost; Future Health: health profile).

Pipeline: extract claims -> Tavily evidence (general + news) -> LLM stance judgement (via Bifrost or Gemini) ->
DETERMINISTIC aggregation into CURRENT / STALE / CONFLICTING / UNVERIFIED.
A recent search hit never makes a claim CURRENT by itself: it needs a source judged to SUPPORT the claim AND dated inside the freshness window.
Without a configured judge, claims are returned as NEEDS_REVIEW with candidate evidence - never silently 'verified'.
"""
from __future__ import annotations
import json, os, re, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from . import llm

HEALTH_DOMAINS = ["who.int","nih.gov","cdc.gov","nhs.uk","ema.europa.eu","fda.gov","doh.gov.ae","mohap.gov.ae","mayoclinic.org","cochrane.org","medlineplus.gov"]
WINDOWS = {"volatile": 120, "stable": 1095}   # freshness windows in days
MONTHS = {m: i+1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
STANCES = {"supports","contradicts","supersedes","irrelevant"}

# ---------- dates ----------
def parse_date(s: str | None):
    if not s: return None
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%SZ","%Y-%m-%d","%a, %d %b %Y %H:%M:%S %Z","%a, %d %b %Y %H:%M:%S %z"):
        try:
            d = datetime.strptime(s.replace("Z","+0000") if fmt.endswith("%z") else s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError: continue
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", s)
    if m:
        try: return datetime(int(m[1]),int(m[2]),int(m[3]),tzinfo=timezone.utc)
        except ValueError: return None
    return None

def date_from_text(text: str, url: str = ""):
    m = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/", url or "")
    if m:
        try: return datetime(int(m[1]),int(m[2]),int(m[3]),tzinfo=timezone.utc)
        except ValueError: pass
    m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}),? (20\d{2})\b", text or "")
    if m:
        try: return datetime(int(m[3]),MONTHS[m[1].lower()],int(m[2]),tzinfo=timezone.utc)
        except ValueError: pass
    return parse_date(text)

# ---------- Tavily (real documented API: POST https://api.tavily.com/search, Bearer auth) ----------
def tavily_search(query, topic="general", include_domains=None, days=None, max_results=5):
    key = os.environ.get("TAVILY_API_KEY")
    if not key: return None
    body = {"query": query[:400], "search_depth": "advanced" if topic == "general" else "basic", "topic": topic,
            "max_results": max_results, "include_answer": False}
    if include_domains: body["include_domains"] = include_domains
    if topic == "news" and days: body["days"] = days
    req = urllib.request.Request(os.environ.get("TAVILY_API_URL", "https://api.tavily.com/search"), data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode()).get("results", [])
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise RuntimeError(f"Tavily request failed: {type(e).__name__}")

def gather_evidence(claim, profile):
    dom = HEALTH_DOMAINS if profile == "health" else None
    seen, ev = set(), []
    for topic in ("general", "news"):
        res = tavily_search(claim, topic, dom, days=365)
        if res is None: return None
        for x in res:
            u = x.get("url")
            if not u or u in seen: continue
            seen.add(u); text = (x.get("content") or "")[:900]
            d = parse_date(x.get("published_date")) or date_from_text(text, u)
            ev.append({"title": x.get("title") or u, "url": u, "domain": urlparse(u).netloc.removeprefix("www."),
                       "snippet": text, "published": d.date().isoformat() if d else None, "relevance": x.get("score")})
    return ev[:10]

# ---------- LLM judgement ----------
JUDGE_SYS = ("You are a strict fact-checking analyst. For ONE claim and a numbered list of evidence snippets, judge each snippet. "
 "Stances: 'supports' (snippet directly states the claim holds), 'contradicts' (snippet directly states the claim is false), "
 "'supersedes' (snippet shows the claim was once true but newer information replaces it), 'irrelevant'. "
 "Use ONLY the provided snippets; do not use outside knowledge. A snippet that merely mentions the topic is 'irrelevant'. "
 'Also classify claim_type: "volatile" (prices, office-holders, versions, rankings, laws, \"latest/current\" facts, medical guidance that changes) or "stable". '
 'Return JSON only: {"claim_type":"volatile|stable","stances":[{"i":0,"stance":"...","reason":"<=25 words"}]}')

def judge(claim, evidence):
    if not evidence or llm.provider() is None: return None
    listing = "\n".join(f"[{i}] ({e['published'] or 'undated'}) {e['domain']}: {e['snippet'][:500]}" for i, e in enumerate(evidence))
    out = llm.complete_json(JUDGE_SYS, f"CLAIM: {claim}\nTODAY: {datetime.now(timezone.utc).date()}\nEVIDENCE:\n{listing}")
    stances = {}
    for s in (out or {}).get("stances", []):
        if isinstance(s.get("i"), int) and 0 <= s["i"] < len(evidence) and s.get("stance") in STANCES:
            stances[s["i"]] = (s["stance"], str(s.get("reason", ""))[:200])
    ctype = out.get("claim_type") if (out or {}).get("claim_type") in WINDOWS else "volatile"
    return {"claim_type": ctype, "stances": stances}

# ---------- deterministic aggregation (unit-tested) ----------
def aggregate(claim, evidence, judgement, today=None):
    today = today or datetime.now(timezone.utc)
    if not evidence: return {"status": "UNVERIFIED", "reason": "No evidence was retrieved for this claim.", "confidence": "none"}
    if judgement is None:
        return {"status": "NEEDS_REVIEW", "confidence": "none",
                "reason": "Evidence was retrieved but no LLM judge is configured, so support/contradiction was not assessed. Review the sources yourself."}
    ctype = judgement["claim_type"]; window = timedelta(days=WINDOWS[ctype])
    rows = []
    for i, e in enumerate(evidence):
        st, why = judgement["stances"].get(i, ("irrelevant", "not judged"))
        e["stance"], e["stance_reason"] = st, why; rows.append((e, st, parse_date(e["published"])))
    sup = [(e, d) for e, s, d in rows if s == "supports"]
    con = [(e, d) for e, s, d in rows if s == "contradicts"]
    sup_by = [(e, d) for e, s, d in rows if s == "supersedes"]
    fresh_sup = [(e, d) for e, d in sup if d and today - d <= window]
    domains = {e["domain"] for e, _ in sup + con + sup_by}
    conf = "high" if len(domains) >= 3 else "medium" if len(domains) == 2 else "low"
    base = {"claim_type": ctype, "freshness_window_days": WINDOWS[ctype], "confidence": conf}
    if sup_by:
        return {**base, "status": "STALE", "reason": f"{len(sup_by)} source(s) indicate newer information supersedes this claim."}
    if sup and con:
        return {**base, "status": "CONFLICTING", "reason": f"{len(sup)} source(s) support and {len(con)} contradict the claim."}
    if con:
        return {**base, "status": "CONFLICTING", "reason": f"{len(con)} source(s) contradict the claim and none support it."}
    if fresh_sup:
        return {**base, "status": "CURRENT", "reason": f"Supported by {len(fresh_sup)} source(s) dated within {WINDOWS[ctype]} days; none contradict it."}
    if sup:
        dated = [d for _, d in sup if d]
        if dated:
            return {**base, "status": "STALE", "reason": f"Supporting evidence exists but the newest is {max(dated).date()}, older than the {WINDOWS[ctype]}-day window for a {ctype} claim; currency cannot be confirmed."}
        return {**base, "status": "UNVERIFIED", "reason": "Sources support the claim but none carries a publication date, so freshness cannot be established."}
    return {**base, "status": "UNVERIFIED", "reason": "No retrieved source directly supports or contradicts the claim."}

# ---------- claim extraction ----------
EXTRACT_SYS = ('Extract the distinct, checkable factual claims from the text as short standalone sentences (max 5). '
               'Ignore opinions. Return JSON only: {"claims":["..."]}')

def extract_claims(text, max_claims=5):
    text = text.strip()
    if len(text) <= 220 and "\n" not in text: return [text], "single-claim"
    try:
        out = llm.complete_json(EXTRACT_SYS, text[:4000])
        cl = [c.strip() for c in (out or {}).get("claims", []) if isinstance(c, str) and len(c.strip()) > 8][:max_claims]
        if cl: return cl, "llm"
    except RuntimeError: pass
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if len(p.strip()) > 20]
    return parts[:max_claims], "sentence-split"

def verify(text, profile="general"):
    if profile not in ("general", "health"): profile = "general"
    claims, how = extract_claims(text)
    results, notes = [], []
    for c in claims:
        ev = gather_evidence(c, profile)
        if ev is None:
            results.append({"claim": c, "status": "UNVERIFIED", "confidence": "none", "sources": [],
                            "reason": "TAVILY_API_KEY is not configured, so no live evidence was retrieved. Use demo mode to see the logic on synthetic cases."})
            continue
        try: j = judge(c, ev)
        except RuntimeError as e: j = None; notes.append(str(e))
        results.append({"claim": c, **aggregate(c, ev, j), "sources": ev})
    return {"profile": profile, "extraction": how, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "judge": llm.provider() or "none", "mode": "live" if os.environ.get("TAVILY_API_KEY") else "no-evidence-source",
            "results": results, "notes": notes,
            "disclaimer": "Automated triage, not a final fact-check. Health results are informational and not medical advice."}

# ---------- clearly-labelled synthetic demo (runs the SAME aggregator) ----------
def demo():
    t = datetime.now(timezone.utc)
    def d(days): return (t - timedelta(days=days)).date().isoformat()
    def ev(dom, pub, snip): return {"title": dom, "url": "https://" + dom + "/synthetic", "domain": dom, "snippet": snip, "published": pub, "relevance": None}
    cases = [
     ("The Acme Phone 5 is Acme's newest flagship.", "volatile",
      [ev("news.example", d(400), "Acme launched the Phone 5 as its flagship."), ev("tech.example", d(20), "Acme unveiled the Phone 6, replacing the Phone 5 as flagship.")],
      {0: "supports", 1: "supersedes"}),
     ("Acme's CEO is Jane Roe.", "volatile",
      [ev("press.example", d(15), "Acme names Jane Roe CEO."), ev("wire.example", d(30), "Jane Roe, Acme chief executive, said on Monday...")], {0: "supports", 1: "supports"}),
     ("Vitamin Z cures influenza.", "volatile",
      [ev("health.example", d(60), "Trial found Vitamin Z did not reduce influenza duration."), ev("blog.example", d(200), "Vitamin Z cured my flu!")], {0: "contradicts", 1: "supports"}),
     ("Acme will open a Lisbon office.", "volatile", [ev("blog.example", None, "Acme is rumoured to be opening in Lisbon.")], {0: "supports"}),
     ("Acme was founded in 1998.", "stable", [], {}),
    ]
    out = []
    for claim, ctype, evidence, stn in cases:
        j = {"claim_type": ctype, "stances": {i: (s, "synthetic fixture") for i, s in stn.items()}}
        out.append({"claim": claim, **aggregate(claim, evidence, j if evidence else j), "sources": evidence})
    return {"mode": "SYNTHETIC DEMO — fictional companies and fixtures, not real-world evidence", "checked_at": t.isoformat(timespec="seconds"),
            "profile": "demo", "results": out, "notes": [], "judge": "fixture",
            "disclaimer": "Demonstrates the deterministic classification logic only."}
