# Submission pack — ONE project (ReLink), tailored per competition

**Rule of thumb:** same codebase, different lead module and honest claims. Check each event's rules on duplicate/multi-event submissions and on work-during-event requirements before submitting. Tick "uses Google tools/models" **only** for what you actually ran.

## 1. Hack2skill Buildathon — Open Innovation (deadline 15 Nov 11:59 PM IST)
Use the **mandatory reference PPT** (I don't have it — upload it and I'll fill it). Lead with Chat + Security Teacher.
- One-sentence summary: *ReLink is an independent messenger with a built-in AI Security Teacher that explains scams and phishing as people chat.*
- Problem: Scams, phishing and impersonation spread through messaging, while most apps offer little contextual security education; people locked out of one service need a trustworthy alternative.
- User: students, families, small businesses, first-time smartphone users.
- Solution: messenger + opt-in Teacher (indicators, reasons, safe action, lesson) + Verify to check forwarded claims.
- Stage: **MVP** (working prototype; not production). 
- AI use: LLM explanations and claim judging via Gemini (directly or through Bifrost); deterministic rules for the core screening.
- Google models: select **Gemini API** only if you run it before submitting; development platforms: tick only tools you used.
- Deploy/scale: Cloud Run (container included), Secret Manager for keys, Cloud SQL (Postgres) replacing SQLite, HTTPS load balancer. *(Plan — not yet done.)*
- Business: freemium; B2B/education subscriptions for security-awareness. Competitors: WhatsApp, Signal, Telegram (differentiator: in-flow, consent-based security teaching + evidence checking).

## 2. Global AI Hackathon — Tavily *Stale-Answer Detector* (+ Bifrost) (deadline 15 Nov 11:59 PM IST)
Select **Stale-Answer Detector** as the theme; GitHub repo must be **public** with this README; PPT required; demo video optional. Lead with **Verify**. Requires real `TAVILY_API_KEY` and `BIFROST_BASE_URL` (run Bifrost gateway) — if you can't run Bifrost, don't claim it; use direct Gemini and say so. Pitch: problem (confident but outdated answers) → pipeline → four verdicts → why recency alone ≠ CURRENT → dashboard + exportable report → limits. Run at least one live check before recording.

## 3. NASA Space Apps (closes 15 Nov 11:59 PM local)
Challenge: **Lunar Landing Site Navigator**. Submit Link Planner as the project; cite Meeus algorithms, state it is analytic (not SPICE/Horizons), flat-horizon + mask, no terrain. Don't claim NASA endorsement. Confirm on the NASA portal that a project built partly beforehand meets the event's rules, and use the official submission form/team registration.

## 4. Future Health Digital Innovation Challenge (early feedback 15 Nov; final 20 Nov)
I don't know which problem statement you chose. Candidate framing: **Patient-Message Trust Agent** for Abu Dhabi — Security Teacher (health-scam rules: fake insurance/pharmacy/appointment lures) + Verify health profile (WHO/NIH/CDC/NHS/DoH Abu Dhabi/MOHAP only). Needs: desirability/feasibility/viability slide, <3-min narrative, Abu Dhabi relevance (DoH/MOHAP sources, Arabic UI is future work), no medical-advice claims. Not a diagnostic tool.

## 5. Jabali AI Game Jam — COMPLETED & INTEGRATED
- **Game Title**: *Lunar Link* / *Lunar Relay*
- **Studio URL**: `https://friendjam.jabali.ai`
- **Description**: *Match coloured lunar tiles to power relay towers and blast incoming waves of noise before they reach your base. Time your matches to the towers' opening link windows, survive five waves, and conquer the moon in charming pixel-art style!*
- **Integration**: Playable directly inside ReLink's web app under the **Lunar Relay** tab, complete with 7×7 match grid, 4-tower beam defense, link window cycling, and 3× surge shots.

## 6. Other Upcoming Tracks
- **Innodata (6 Dec)**: needs its official Coding Task Factory statement.
- **PromptWars × AIGeeks (18 Nov)**: send the problem statements; ReLink modules can be reused if they fit.
