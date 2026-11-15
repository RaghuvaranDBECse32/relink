"""Security Teacher: explainable, rule-based screening + lessons. Only analyses text the user explicitly submits."""
from __future__ import annotations
import ipaddress, re
from urllib.parse import urlparse

SHORTENERS = {"bit.ly","tinyurl.com","t.co","goo.gl","is.gd","cutt.ly","rb.gy","ow.ly","shorturl.at"}
RISKY_TLDS = {"zip","mov","top","xyz","click","country","gq","tk","ml","cf","work","support","icu","rest"}
BRANDS = ["paypal","google","microsoft","apple","amazon","whatsapp","facebook","instagram","netflix","hdfc","sbi","icici","paytm","dhl","fedex"]
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.I)

RULES = [  # (id, category, regex, weight, why, safe action)
 ("urgency","pressure",r"\b(urgent(ly)?|immediately|act now|within \d+ (hours?|minutes?)|last warning|final notice|account (will be )?(suspended|blocked|closed))\b",2,
  "Scammers create time pressure so you act before thinking.","Pause. Real organisations rarely demand action within minutes; contact them through an official channel you already trust."),
 ("credential_request","credentials",r"\b(password|passcode|otp|one[- ]time (code|password)|verification code|recovery code|pin|cvv|card number|aadhaar)\b",4,
  "Legitimate services never ask you to send passwords, OTPs, PINs or recovery codes in a message.","Never share these. If you already did, change the password and sign out of all sessions now."),
 ("payment_request","payment",r"\b(gift ?cards?|crypto(currency)?|bitcoin|wire transfer|processing fee|advance fee|upi (id|request)|send money|pay (now|immediately))\b",3,
  "Unusual payment methods and advance fees are common in fraud because they are hard to reverse.","Confirm the request by calling the person or company on a number you looked up yourself."),
 ("impersonation","impersonation",r"\b(ceo|boss|bank officer|customer care|support team|administrator|tax (department|officer)|police|courier)\b",1,
  "Attackers pose as authority figures or support staff to borrow trust.","Verify identity through a known contact method, not through details inside the message."),
 ("prize_lure","lure",r"\b(you('ve| have)? won|lottery|prize|reward points|free (gift|iphone|recharge)|claim your)\b",3,
  "Unexpected rewards are bait to collect your data or fees.","Ignore it. You cannot win a contest you did not enter."),
 ("secrecy","pressure",r"\b(don'?t tell|keep (this )?(secret|confidential)|do not share with anyone)\b",2,
  "Secrecy requests isolate victims from people who could spot the scam.","Talk to someone you trust before acting."),
 ("health_miracle","health",r"\b(miracle cure|guaranteed cure|cures? (cancer|diabetes)|doctors? (hate|don'?t want you to know)|detox(ify)? your)\b",3,
  "Absolute cure claims and 'hidden truth' framing are hallmarks of health misinformation and scams.","Check the claim with a licensed clinician and an official health authority before acting or forwarding."),
 ("health_admin_lure","health",r"\b(insurance (claim|refund)|claim (your )?refund|medical (bill|report) (ready|pending)|appointment (confirm|cancel)\w* (here|link)|pharmacy (order|delivery) (failed|held))\b",3,
  "Fake insurance, appointment or pharmacy notices are used to harvest identity and payment details.","Open your insurer or clinic's own app/website directly instead of using the link."),
 ("fear_of_loss","pressure",r"\b(legal action|arrest|penalty|your (sim|number|account) will be)\b",2,
  "Threats of loss or punishment are used to override judgment.","Do not respond to threats in chat; verify with the real organisation."),
]

def _url_findings(raw: str):
    url = raw if raw.lower().startswith("http") else "http://" + raw
    host = (urlparse(url).hostname or "").lower(); netloc = urlparse(url).netloc
    flags = []
    def add(i, why, pts): flags.append({"indicator": i, "why": why, "points": pts})
    try: ipaddress.ip_address(host); add("ip_address_host","The link points to a raw IP address instead of a named website.",3)
    except ValueError: pass
    if host.startswith("xn--") or ".xn--" in host: add("punycode","The domain uses punycode, which can disguise look-alike characters.",3)
    if "@" in netloc: add("userinfo_in_url","Text before '@' in a link can hide the real destination.",3)
    if host in SHORTENERS: add("url_shortener","Shortened links hide where they lead.",2)
    parts = host.split(".")
    if len(parts) > 4: add("many_subdomains","Very long subdomain chains are used to bury the real domain.",2)
    if parts and parts[-1] in RISKY_TLDS: add("risky_tld","This top-level domain is frequently abused in scams (not proof by itself).",1)
    if raw.lower().startswith("http://"): add("no_https","The link is not encrypted (http).",1)
    base = ".".join(parts[-2:]) if len(parts) >= 2 else host
    for b in BRANDS:
        if b in host and not (base == b + ".com" or base.startswith(b + ".")):
            add("brand_lookalike",f"The domain mentions '{b}' but is not that brand's own domain ({base}).",3); break
    if any(ch.isdigit() for ch in base.split(".")[0]) and any(b in re.sub(r"[01345]", lambda m: {"0":"o","1":"l","3":"e","4":"a","5":"s"}[m.group()], base.split(".")[0]) for b in BRANDS):
        add("digit_substitution","Digits are replacing letters to imitate a known brand.",3)
    return {"url": raw[:200], "host": host, "findings": flags}

LESSON_FOR = {"credentials":"phishing","pressure":"social-engineering","payment":"payment-fraud","impersonation":"impersonation",
              "lure":"phishing","health":"health-scams","links":"links"}

def analyze(text: str) -> dict:
    text = text or ""
    hits, score = [], 0
    for rid, cat, rx, w, why, act in RULES:
        if re.search(rx, text, re.I):
            hits.append({"indicator": rid, "category": cat, "why": why, "safe_action": act, "points": w}); score += w
    urls = [_url_findings(u.rstrip(".,);")) for u in URL_RE.findall(text)][:5]
    for u in urls:
        for f in u["findings"]: score += f["points"]
    if urls and not any(u["findings"] for u in urls):
        hits.append({"indicator":"link_present","category":"links","why":"The message contains a link. No structural red flags were found, but a clean-looking link can still be malicious.",
                     "safe_action":"Prefer typing the known address yourself.","points":1}); score += 1
    elif urls:
        hits.append({"indicator":"suspicious_link","category":"links","why":"At least one link shows structural red flags (see link analysis).",
                     "safe_action":"Do not open it. Visit the organisation's site by typing its address.","points":0})
    level = "high" if score >= 6 else "caution" if score >= 2 else "low"
    cats = {h["category"] for h in hits}
    lessons = sorted({LESSON_FOR[c] for c in cats if c in LESSON_FOR})
    return {
      "risk_level": level, "score": score, "indicators": hits, "links": urls,
      "what_to_do": ("Do not click, reply, pay or share codes. Verify through an official channel you look up yourself; report and block if it is spam."
                     if level != "low" else "No listed warning sign triggered. That does not prove safety — stay cautious with unexpected requests."),
      "what_you_can_learn": [LESSONS_BY_ID[l]["title"] for l in lessons if l in LESSONS_BY_ID],
      "lesson_ids": lessons,
      "method": "Transparent rule-based screening (deterministic). Not a malware scanner or a verdict. Only the text you submitted was analysed and it was not stored.",
    }

LESSONS = [
 {"id":"phishing","title":"Phishing: how it works","body":"Phishing messages imitate a trusted sender to make you reveal credentials or install something. Look for mismatched sender and domain, urgency, and requests to 'verify' details. Go to the real site yourself instead of using the link.",
  "quiz":{"q":"A message says your account closes in 1 hour unless you tap a link. Best response?","options":["Tap quickly","Open the official app/site yourself and check","Forward to friends"],"answer":1}},
 {"id":"links","title":"Reading a link safely","body":"The registered domain is the part just before the final extension: in login.example.com.evil.xyz the real site is evil.xyz. Watch for IP addresses, '@', punycode (xn--), shorteners and look-alike spellings.",
  "quiz":{"q":"In 'paypal.secure-login.top/verify', who owns the site?","options":["PayPal","secure-login.top","Cannot be known"],"answer":1}},
 {"id":"account-takeover","title":"Account takeover & 2FA","body":"Attackers get in via reused passwords, stolen codes and SIM/OTP scams. Use a unique long passphrase per service, a password manager, and an authenticator app instead of SMS where possible. Never read a code out to anyone.",
  "quiz":{"q":"Someone 'from support' asks for the code just sent to you. What is it?","options":["Normal verification","An attempt to take over your account","A bank refund"],"answer":1}},
 {"id":"social-engineering","title":"Social engineering","body":"Manipulation exploits emotion: fear, urgency, authority, kindness. The defence is a habit: slow down, verify via a second channel, and be comfortable saying no.",
  "quiz":{"q":"Which is a classic pressure tactic?","options":["Take your time","Act within 10 minutes or lose access","Check our website"],"answer":1}},
 {"id":"impersonation","title":"Fake profiles & impersonation","body":"A new number claiming to be your relative or boss is a known scam. Call the person on their old number. Check profile age, mutual contacts and whether the story asks for money.",
  "quiz":{"q":"'Hi mum, this is my new number, send money.' First step?","options":["Send money","Call the old number","Ask for a selfie only"],"answer":1}},
 {"id":"payment-fraud","title":"Payment & advance-fee fraud","body":"Gift cards, crypto, wire transfers and 'processing fees' are favoured because they are hard to reverse. Real lotteries and refunds do not require you to pay first.",
  "quiz":{"q":"A prize requires a small fee first. This is…","options":["Normal","A red flag for fraud","Tax"],"answer":1}},
 {"id":"privacy","title":"Privacy & safe file sharing","body":"Share the minimum. Strip metadata from photos, avoid sending ID documents in chat, and prefer expiring links. Remember: transport encryption protects data in transit only; end-to-end encryption needs a reviewed protocol.",
  "quiz":{"q":"Does HTTPS alone make a chat end-to-end encrypted?","options":["Yes","No — the server can still read it","Only on mobile"],"answer":1}},
 {"id":"health-scams","title":"Health misinformation & medical scams","body":"Be wary of 'miracle cures', fake insurance refunds and pharmacy delivery failures. Confirm medical claims with a licensed clinician and an official health authority before acting or forwarding.",
  "quiz":{"q":"A forwarded post promises a guaranteed cure doctors hide. Best step?","options":["Forward it","Check an official health authority/clinician","Buy it"],"answer":1}},
]
LESSONS_BY_ID = {l["id"]: l for l in LESSONS}
