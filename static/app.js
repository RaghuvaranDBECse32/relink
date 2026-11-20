"use strict";
// ---------- helpers (all dynamic text goes through textContent; no innerHTML with data) ----------
const $ = (s, r = document) => r.querySelector(s);
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
}
let token = sessionStorage.getItem("relink_token"), me = null, STATUS = null, timer = null, active = null, cleanupView = null;
async function api(path, method = "GET", body) {
  const r = await fetch("/api" + path, { method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) }, body: body ? JSON.stringify(body) : undefined });
  let d = {}; try { d = await r.json(); } catch {}
  if (!r.ok) { if (r.status === 401 && token) { setToken(null); } throw new Error(d.error || "Request failed (" + r.status + ")"); }
  return d;
}
function setToken(t) { token = t; t ? sessionStorage.setItem("relink_token", t) : sessionStorage.removeItem("relink_token"); if (!t) me = null; }
const busy = async (btn, fn, out) => { btn.disabled = true; try { await fn(); } catch (e) { out && out.replaceChildren(h("div", { class: "note", role: "alert" }, "⚠ " + e.message)); } finally { btn.disabled = false; } };
const when = iso => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
const put = (el, ...k) => el.replaceChildren(...k.flat().filter(x => x != null && x !== false));
const badge = (t, c = "") => h("span", { class: "badge " + c }, t);

// ---------- shell ----------
const main = $("#main");
document.querySelectorAll(".rail [data-tab]").forEach(b => b.addEventListener("click", () => show(b.dataset.tab)));
let labelSeq = 0;
function linkLabels(root = main) {
  root.querySelectorAll("label:not([for])").forEach(label => {
    const control = label.querySelector("input,textarea,select") || label.nextElementSibling;
    if (control && /^(INPUT|TEXTAREA|SELECT)$/.test(control.tagName)) {
      if (!control.id) control.id = "relink-field-" + (++labelSeq);
      label.htmlFor = control.id;
    }
  });
}
async function show(tab) {
  cleanupView?.(); cleanupView = null;
  clearInterval(timer); active = null;
  document.querySelectorAll(".rail [data-tab]").forEach(b => {
    const selected = b.dataset.tab === tab;
    b.classList.toggle("on", selected);
    if (selected) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  main.replaceChildren(); await views[tab](); linkLabels(); main.focus();
}
async function loadStatus() {
  try { STATUS = await api("/status"); } catch { STATUS = null; }
  const i = STATUS?.integrations;
  $("#railfoot").replaceChildren(h("div", {}, "v" + (STATUS?.version || "?")), h("div", {}, "LLM: " + (i?.llm_provider || "?")), h("div", {}, "Tavily: " + (i?.tavily_configured ? "on" : "off")));
}

// ---------- views ----------
const views = {};
views.home = async () => {
  const i = STATUS?.integrations || {}, m = STATUS?.messaging || {};
  main.append(
    h("div", { class: "eyebrow" }, "One platform · five trust problems"),
    h("h1", {}, "Reliable links. Verified signals."),
    h("p", { class: "lede" }, "ReLink is a single trust layer: talk to people on an independent messenger, learn to spot attacks as they happen, check whether an answer is still true, plan when a link to Earth is geometrically possible, and defend lunar relay transmissions."),
    h("div", { class: "grid g2" },
      card("Chat", "Accounts, contacts, groups, unread and read state, block/report, export and delete. Independent service — it does not touch or bypass any other platform.", "chat"),
      card("Security Teacher", "Paste a suspicious message or link you choose to share. Get indicators, reasons, safe actions and a lesson. Nothing is read automatically.", "teacher"),
      card("Verify", "Stale-answer detector: Tavily evidence + an LLM judge via Bifrost or Gemini, then a deterministic CURRENT / STALE / CONFLICTING / UNVERIFIED verdict. Health profile restricts to official health sources.", "verify"),
      card("Link Planner", "Sun and Earth elevation at lunar south-pole sites over time: solar windows, direct-to-Earth geometric windows, side-by-side comparison with stated assumptions.", "luna"),
      card("Lunar Relay (Game)", "Match lunar tiles to power relay towers and blast noise waves before they breach the base. Time your matches to active link windows for 3× surge shots!", "game")),
    h("div", { class: "card" }, h("h2", {}, "What is real in this build"),
      h("div", {}, badge("Tavily " + (i.tavily_configured ? "configured" : "not configured"), i.tavily_configured ? "ok" : "warn"),
        badge("LLM judge: " + (i.llm_provider || "none"), i.llm_provider && i.llm_provider !== "none" ? "ok" : "warn"),
        badge("End-to-end encryption: NO", "bad"), badge("Transport: HTTPS only when deployed behind TLS", "warn"), badge("Lunar model: analytic, flat horizon", "warn"),
        badge("Game: Jabali Game Jam edition", "ok")),
      h("p", { class: "small mute" }, "Without API keys, Verify says UNVERIFIED rather than guessing; a clearly-labelled synthetic demo shows the classifier. Chat uses HTTP polling today; WebSockets and a reviewed E2EE protocol are roadmap items, not claims.")));
};
const card = (t, d, tab) => h("div", { class: "card" }, h("h2", {}, t), h("p", { class: "mute" }, d), h("button", { class: "btn ghost sm", onclick: () => show(tab) }, "Open →"));

// ----- Chat -----
views.chat = async () => {
  main.append(h("div", { class: "eyebrow" }, "Independent messaging"), h("h1", {}, "Chat"));
  if (!token) return authForm();
  try { me = await api("/me"); } catch { return authForm(); }
  const left = h("div", { class: "card list" }), right = h("div", { class: "card" }, h("p", { class: "mute" }, "Select a conversation, or add a contact by username and open a chat.")), box = h("div", { class: "chat" }, left, right);
  main.append(h("div", { class: "note" }, "Prototype messenger: not end-to-end encrypted, and the server can read messages. Use HTTPS in deployment. Don't send secrets."), box);
  const renderList = async () => {
    const [cv, ct] = await Promise.all([api("/conversations"), api("/contacts")]);
    const search = h("input", { placeholder: "Find @username…", "aria-label": "Search users" }), res = h("div", {});
    search.addEventListener("input", async () => {
      if (search.value.trim().length < 2) return res.replaceChildren();
      const r = await api("/users/search?q=" + encodeURIComponent(search.value));
      res.replaceChildren(...r.users.map(u => h("div", { class: "row" }, h("span", {}, "@" + u.username),
        h("button", { class: "btn sm", onclick: async () => { try { await api("/contacts/request", "POST", { username: u.username }); search.value = ""; res.replaceChildren(); renderList(); } catch (e) { alert(e.message); } } }, "Add"))));
    });
    put(left, h("div", { class: "row" }, h("b", {}, "@" + me.username), h("button", { class: "btn ghost sm", onclick: () => { api("/auth/logout", "POST").catch(() => {}); setToken(null); show("chat"); } }, "Sign out")),
      search, res,
      ct.incoming.length ? h("div", {}, h("h3", {}, "Requests"), ...ct.incoming.map(u => h("div", { class: "row" }, "@" + u.username,
        h("button", { class: "btn sm", onclick: async () => { await api("/contacts/respond", "POST", { username: u.username, accept: true }); renderList(); } }, "Accept"),
        h("button", { class: "btn ghost sm", onclick: async () => { await api("/contacts/respond", "POST", { username: u.username, accept: false }); renderList(); } }, "Decline")))) : null,
      h("h3", {}, "Conversations"),
      ...cv.conversations.map(c => h("button", { class: c.id === active ? "on" : "", onclick: () => openConv(c) }, c.title, c.unread ? h("span", { class: "unread" }, c.unread) : null,
        h("div", { class: "small mute" }, c.last ? c.last.body : "No messages yet"))),
      h("h3", {}, "Contacts"),
      ...ct.contacts.map(u => h("div", { class: "row" }, "@" + u.username,
        h("button", { class: "btn ghost sm", onclick: async () => { const d = await api("/direct", "POST", { username: u.username }); await renderList(); openConv({ id: d.id, title: "@" + u.username }); } }, "Message"),
        h("button", { class: "btn ghost sm", onclick: async () => { if (confirm("Block @" + u.username + "?")) { await api("/blocks", "POST", { username: u.username }); renderList(); } } }, "Block"))),
      ct.contacts.length >= 2 ? h("button", { class: "btn ghost sm", onclick: newGroup(ct.contacts, renderList) }, "New group") : null,
      h("details", {}, h("summary", {}, "Account"),
        h("label", {}, h("input", { type: "checkbox", checked: me.read_receipts, onchange: e => api("/me", "PATCH", { read_receipts: e.target.checked }) }), " Send read receipts"),
        h("button", { class: "btn ghost sm", onclick: exportData }, "Export my data"), h("button", { class: "btn ghost sm", onclick: deleteAccount }, "Delete account")));
  };
    const openConv = async c => {
    active = c.id; const log = h("div", { class: "msgs", "aria-live": "polite" });
    const input = h("textarea", { placeholder: "Message…", "aria-label": "Chat message", style: "min-height:60px" }), out = h("div", {});
    const send = h("button", { class: "btn" }, "Send");
    send.onclick = () => busy(send, async () => { await api(`/conversations/${c.id}/messages`, "POST", { body: input.value }); input.value = ""; await pull(); }, out);
    right.replaceChildren(h("h2", {}, c.title), log, input, send, out,
      h("p", { class: "small mute" }, "Tick states: “sent” means stored by the server; “read” appears only after the other member opened it and has receipts enabled. There is no “delivered” state yet."));
    let sig = "";
    const pull = async () => {
      const all = (await api(`/conversations/${c.id}/messages?after=0`)).messages, s2 = JSON.stringify(all.map(m => [m.id, m.state]));
      if (s2 === sig) return; const stick = log.scrollTop + log.clientHeight >= log.scrollHeight - 30 || !sig; sig = s2;
      log.replaceChildren(...all.map(msgEl)); if (stick) log.scrollTop = log.scrollHeight; api(`/conversations/${c.id}/read`, "POST", {}).catch(() => {});
    };
    const msgEl = m => h("div", { class: "msg" + (m.mine ? " mine" : "") },
      !m.mine ? h("b", { class: "small" }, "@" + m.sender) : null, h("div", {}, m.body),
      h("small", {}, when(m.at) + (m.mine ? " · " + m.state : "") + " ",
        h("a", { href: "#", onclick: e => { e.preventDefault(); teachMsg(m.body); } }, "check with Teacher"), " ",
        !m.mine ? h("a", { href: "#", onclick: async e => { e.preventDefault(); const r = prompt("Why are you reporting this message?"); if (r) { await api("/reports", "POST", { username: m.sender, message_id: m.id, reason: r }); alert("Reported."); } } }, "report") : null));
    await pull(); renderList();
    pullActive = pull;
  };
  let pullActive = null;
  await renderList();
  clearInterval(timer);
  timer = setInterval(async () => { try { if (document.hidden) return; if (pullActive) await pullActive(); if (!left.contains(document.activeElement)) await renderList(); } catch {} }, 3000);
};
function newGroup(contacts, done) { return async () => {
  const title = prompt("Group name?"); if (!title) return;
  const names = prompt("Members (comma-separated usernames from your contacts):\n" + contacts.map(c => c.username).join(", ")); if (!names) return;
  try { await api("/groups", "POST", { title, members: names.split(",").map(s => s.trim().replace(/^@/, "")).filter(Boolean) }); done(); } catch (e) { alert(e.message); } }; }
async function exportData() { const d = await api("/account/export"); const a = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })), download: "relink-export.json" }); a.click(); }
async function deleteAccount() { const pw = prompt("Type your password to permanently delete your account and your messages:"); if (!pw) return; try { await api("/account/delete", "POST", { password: pw }); setToken(null); show("chat"); } catch (e) { alert(e.message); } }
function authForm() {
  const u = h("input", { autocomplete: "username", placeholder: "username (a-z, 0-9, _)" }), p = h("input", { type: "password", autocomplete: "current-password", placeholder: "password (10+ chars)" }), out = h("div", {});
  const go = (path) => (e) => busy(e.target, async () => { const r = await api(path, "POST", { username: u.value, password: p.value }); setToken(r.token); show("chat"); }, out);
  main.append(h("div", { class: "card", style: "max-width:420px" }, h("h2", {}, "Sign in or create an account"), h("label", {}, "Username"), u, h("label", {}, "Password"), p,
    h("button", { class: "btn", onclick: go("/auth/login") }, "Sign in"), h("button", { class: "btn ghost", onclick: go("/auth/register") }, "Create account"), out,
    h("p", { class: "small mute" }, "Passwords are hashed with scrypt. We collect only a username and display name.")));
}
function teachMsg(text) { show("teacher").then(() => { const t = $("#tx"); if (t) { t.value = text; $("#tgo").click(); } }); }

// ----- Teacher -----
views.teacher = async () => {
  main.append(h("div", { class: "eyebrow" }, "Opt-in analysis · explainable rules"), h("h1", {}, "Security Teacher"),
    h("p", { class: "lede" }, "Only text you paste here is analysed, and it is not stored. Results are screening guidance, never a verdict."));
  const t = h("textarea", { id: "tx", "aria-label": "Suspicious message or link", placeholder: "Paste a suspicious message or link…" }), out = h("div", {});
  const go = h("button", { class: "btn", id: "tgo" }, "Analyse");
  go.onclick = () => busy(go, async () => {
    const r = await api("/teacher/analyze", "POST", { text: t.value });
    out.replaceChildren(h("div", { class: "card" }, h("div", { class: "status s-" + r.risk_level }, r.risk_level.toUpperCase() + " RISK · score " + r.score),
      h("h3", {}, "What to do"), h("p", {}, r.what_to_do),
      r.indicators.length ? h("h3", {}, "Why it looks suspicious") : null,
      ...r.indicators.map(i => h("div", { class: "src" }, h("b", {}, i.indicator.replaceAll("_", " ")), h("div", {}, i.why), h("div", { class: "mute" }, "Safe action: " + i.safe_action))),
      ...r.links.map(l => h("div", { class: "src" }, h("b", { class: "mono" }, l.host || l.url), l.findings.length ? l.findings.map(f => h("div", {}, "⚑ " + f.why)) : h("div", { class: "mute" }, "No structural red flags."))),
      r.what_you_can_learn.length ? h("p", {}, "Lessons for this incident: " + r.what_you_can_learn.join(", ")) : null, h("p", { class: "small mute" }, r.method)));
  }, out);
  const lessons = await api("/teacher/lessons");
  main.append(h("div", { class: "card" }, t, go, h("button", { class: "btn ghost", onclick: () => { t.value = "URGENT: your account will be suspended in 1 hour. Verify now: http://paypa1-secure.top/login and reply with the OTP we sent."; } }, "Load example")), out,
    h("h2", {}, "Lessons"), h("div", { class: "grid g2" }, ...lessons.lessons.map(l => {
      const fb = h("div", { class: "small" });
      return h("div", { class: "card quiz" }, h("h3", {}, l.title), h("p", {}, l.body), h("b", { class: "small" }, l.quiz.q),
        ...l.quiz.options.map((o, i) => h("button", { onclick: e => { e.target.className = i === l.quiz.answer ? "right" : "wrong"; fb.textContent = i === l.quiz.answer ? "Correct." : "Not quite — try another."; } }, o)), fb);
    })));
};

// ----- Verify -----
views.verify = async () => {
  main.append(h("div", { class: "eyebrow" }, "Stale-answer detector · Tavily + Bifrost/Gemini"), h("h1", {}, "Verify"),
    h("p", { class: "lede" }, "Paste a claim or an AI-generated answer. ReLink retrieves live evidence, has a model judge each source against the claim, and applies fixed rules for freshness. A recent web page alone never makes a claim CURRENT."));
  const t = h("textarea", { "aria-label": "e.g. “Jane Roe is the CEO of Acme.”", placeholder: "e.g. “Jane Roe is the CEO of Acme.”" }), prof = h("select", {}, h("option", { value: "general" }, "General web"), h("option", { value: "health" }, "Health (official sources only: WHO, NIH, CDC, NHS, DoH Abu Dhabi, MOHAP…)")), out = h("div", {});
  const run = (path, body, method = "POST") => async e => busy(e.target, async () => renderVerify(out, await api(path, method, body && body()) ), out);
  main.append(h("div", { class: "card" }, h("label", {}, "Claim or answer"), t, h("label", {}, "Profile"), prof,
    h("button", { class: "btn", onclick: run("/verify", () => ({ text: t.value, profile: prof.value })) }, "Verify"),
    h("button", { class: "btn ghost", onclick: run("/verify/demo", null, "GET") }, "Run synthetic demo")), out);
};
function renderVerify(out, r) {
  const md = ["# ReLink Verify report", `Checked: ${r.checked_at} · Mode: ${r.mode || ""} · Judge: ${r.judge}`, ""];
  const cards = r.results.map(x => {
    md.push(`## ${x.status} — ${x.claim}`, x.reason, "", ...(x.sources || []).map(s => `- [${s.stance || "?"}] ${s.domain} (${s.published || "undated"}) ${s.url}`), "");
    return h("div", { class: "card" }, h("div", { class: "status s-" + x.status }, x.status + (x.confidence && x.confidence !== "none" ? " · confidence " + x.confidence : "")),
      h("h2", {}, x.claim), h("p", {}, x.reason), x.claim_type ? h("p", { class: "small mute" }, `Claim type: ${x.claim_type} · freshness window ${x.freshness_window_days} days`) : null,
      (x.sources || []).length ? h("details", { open: true }, h("summary", {}, "Evidence timeline (" + x.sources.length + ")"),
        ...[...x.sources].sort((a, b) => (b.published || "").localeCompare(a.published || "")).map(s => h("div", { class: "src" },
          h("span", { class: "badge" }, s.published || "undated"), s.stance ? badge(s.stance, s.stance === "supports" ? "ok" : s.stance === "irrelevant" ? "" : "bad") : null,
          h("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" }, s.title), h("div", { class: "mute" }, s.domain + (s.stance_reason ? " — " + s.stance_reason : ""))))) : null);
  });
  const dl = h("button", { class: "btn ghost", onclick: () => h("a", { href: URL.createObjectURL(new Blob([md.join("\n")], { type: "text/markdown" })), download: "relink-verify-report.md" }).click() }, "Export report (.md)");
  out.replaceChildren(h("div", { class: "note" }, (r.mode ? r.mode + " · " : "") + r.disclaimer), ...(r.notes || []).map(n => h("div", { class: "note" }, n)), ...cards, dl);
}

// ----- Link Planner -----
views.luna = async () => {
  const { sites, limitations } = await api("/luna/sites");
  main.append(h("div", { class: "eyebrow" }, "NASA Space Apps · Lunar Landing Site Navigator"), h("h1", {}, "Link Planner"),
    h("p", { class: "lede" }, "Compare Sun and Earth visibility from candidate lunar south-pole sites. All times UTC."),
    h("div", { class: "note" }, h("b", {}, "Read before using: "), limitations.join(" ")));
  const boxes = sites.map((s, i) => h("label", { style: "display:flex;gap:8px;align-items:center;margin:4px 0" }, h("input", { type: "checkbox", style: "width:auto", checked: i < 3, value: i }), s.name + `  (${s.latitude}°, ${s.longitude}°)`));
  const custom = [h("input", { "aria-label": "Custom site name", placeholder: "Custom name" }), h("input", { type: "number", step: "0.01", "aria-label": "Custom latitude", placeholder: "Latitude (-90…90)" }), h("input", { type: "number", step: "0.01", "aria-label": "Custom longitude", placeholder: "Longitude (-180…180)" })];
  const today = new Date().toISOString().slice(0, 10);
  const start = h("input", { type: "date", value: today }), hours = h("input", { type: "number", value: 720, min: 1, max: 1440 }), step = h("input", { type: "number", value: 60, min: 1, max: 720 }), mask = h("input", { type: "number", value: 0, min: 0, max: 30, step: "0.5" });
  const out = h("div", {}), go = h("button", { class: "btn" }, "Compute windows");
  go.onclick = () => busy(go, async () => {
    const picked = boxes.map((b, i) => b.querySelector("input").checked ? sites[i] : null).filter(Boolean);
    if (custom[1].value !== "" && custom[2].value !== "") picked.push({ name: custom[0].value || "Custom", latitude: +custom[1].value, longitude: +custom[2].value });
    const r = await api("/luna/analyze", "POST", { sites: picked, start: start.value + "T00:00:00Z", hours: +hours.value, step_min: +step.value, mask_deg: +mask.value });
    renderLuna(out, r, +mask.value);
  }, out);
  main.append(h("div", { class: "card" }, h("h3", {}, "Candidate sites (max 4)"), ...boxes, h("div", { class: "row" }, ...custom),
    h("div", { class: "row" }, h("div", {}, h("label", {}, "Start date (UTC)"), start), h("div", {}, h("label", {}, "Duration (hours)"), hours), h("div", {}, h("label", {}, "Step (minutes)"), step), h("div", {}, h("label", {}, "Horizon mask (°) — stand-in for terrain"), mask)), go), out);
};
function renderLuna(out, r, mask) {
  const rows = r.results;
  const tbl = h("table", {}, h("thead", {}, h("tr", {}, ...["Site", "Sun up (h)", "Sun up %", "Earth up (h)", "Earth up %", "Both (h)", "Rel. insolation*", "Longest Earth window (h)"].map(x => h("th", {}, x)))),
    h("tbody", {}, ...rows.map(s => h("tr", {}, h("td", {}, s.site.name), h("td", {}, s.sun.hours_visible), h("td", {}, (s.sun.fraction * 100).toFixed(0) + "%"),
      h("td", {}, s.earth.hours_visible), h("td", {}, (s.earth.fraction * 100).toFixed(0) + "%"), h("td", {}, s.both.hours_visible), h("td", {}, s.mean_relative_insolation_horizontal_panel.toFixed(3)),
      h("td", {}, Math.max(0, ...s.earth_windows.map(w => w.hours)))))));
  const charts = rows.map(s => { const c = h("canvas", { role: "img", "aria-label": "Elevation of Sun and Earth over time at " + s.site.name }); requestAnimationFrame(() => draw(c, s, mask)); return h("div", { class: "card" }, h("h3", {}, s.site.name),
    h("div", { class: "legend" }, h("span", { style: "color:var(--amber)" }, "━ Sun elevation"), h("span", { style: "color:var(--sig)" }, "━ Earth elevation"), h("span", { class: "mute" }, "shaded = above horizon mask")), c,
    h("details", {}, h("summary", {}, "Earth windows (" + s.earth_windows.length + ")"), ...s.earth_windows.map(w => h("div", { class: "small mono" }, w.start.slice(0, 16) + " → " + w.end.slice(0, 16) + " · " + w.hours + " h")), s.earth_windows.length ? null : h("div", { class: "small mute" }, "None in range.")),
    h("details", {}, h("summary", {}, "Sun windows (" + s.sun_windows.length + ")"), ...s.sun_windows.slice(0, 40).map(w => h("div", { class: "small mono" }, w.start.slice(0, 16) + " → " + w.end.slice(0, 16) + " · " + w.hours + " h"))));
  });
  out.replaceChildren(h("div", { class: "card", style: "overflow:auto" }, h("h2", {}, "Side-by-side"), tbl, h("p", { class: "small mute" }, "*Unit-less geometric proxy (mean sin elevation while Sun is up), not watts. " + r.model + ". Geometric Earth visibility ≠ working radio link.")), ...charts);
}
function draw(cv, s, mask) {
  const dpr = devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr; const g = cv.getContext("2d"); g.scale(dpr, dpr);
  const css = getComputedStyle(document.documentElement), col = n => css.getPropertyValue(n).trim();
  const S = s.series, n = S.t.length, all = S.sun_el.concat(S.earth_el), lo = Math.min(-2, ...all) - 1, hi = Math.max(2, ...all) + 1, pad = 34;
  const X = i => pad + (W - pad - 8) * i / Math.max(1, n - 1), Y = v => H - 22 - (H - 34) * (v - lo) / (hi - lo);
  g.font = "10px " + col("--mono"); g.fillStyle = col("--mute"); g.strokeStyle = col("--line");
  for (let v = Math.ceil(lo / 2) * 2; v <= hi; v += 2) { g.beginPath(); g.moveTo(pad, Y(v)); g.lineTo(W - 8, Y(v)); g.stroke(); g.fillText(v + "°", 2, Y(v) + 3); }
  const shade = (arr, color) => { g.fillStyle = color; let a = null; arr.forEach((v, i) => { if (v > mask && a === null) a = i; if ((v <= mask || i === n - 1) && a !== null) { g.fillRect(X(a), 6, X(i) - X(a), H - 28); a = null; } }); };
  g.globalAlpha = .12; shade(S.earth_el, col("--sig")); g.globalAlpha = 1;
  g.strokeStyle = col("--mute"); g.setLineDash([4, 3]); g.beginPath(); g.moveTo(pad, Y(mask)); g.lineTo(W - 8, Y(mask)); g.stroke(); g.setLineDash([]);
  const line = (arr, c) => { g.strokeStyle = c; g.lineWidth = 1.8; g.beginPath(); arr.forEach((v, i) => i ? g.lineTo(X(i), Y(v)) : g.moveTo(X(i), Y(v))); g.stroke(); };
  line(S.sun_el, col("--amber")); line(S.earth_el, col("--sig"));
  g.fillStyle = col("--mute"); [0, Math.floor(n / 2), n - 1].forEach(i => g.fillText(S.t[i].slice(5, 10), Math.min(X(i), W - 40), H - 6));
}

// ----- Lunar Relay (Jabali Game Jam Edition) -----
views.game = async () => {
  main.append(
    h("div", { class: "eyebrow" }, "Jabali AI Game Jam · Lunar Relay / Lunar Link"),
    h("h1", {}, "Lunar Relay: Defence Grid"),
    h("p", { class: "lede" }, "Match coloured lunar tiles to power relay towers and blast incoming waves of noise before they breach the base. Time your matches to the towers' opening link windows for 3× SURGE shots!"),
    h("div", { class: "note" },
      h("b", {}, "Jabali Game Jam Entry: "),
      "Built & published with Jabali Studio. ",
      h("a", { href: "https://friendjam.jabali.ai", target: "_blank", style: "color:var(--amber);font-weight:700" }, "Open in Jabali Editor ↗"))
  );

  const container = h("div", { class: "card", style: "max-width:680px;margin:0 auto" });
  main.append(container);

  // Game state
  let score = 0, wave = 1, maxWaves = 5, baseHealth = 5, maxBase = 5, isPaused = false, gameOver = false, won = false;
  let animId = null;

  // Towers: 4 colors: 0: Cyan, 1: Pink/Magenta, 2: Amber/Gold, 3: Lime-Green
  const towerColors = ["#38d9d6", "#f06292", "#ffb23e", "#a3e635"];
  const towerNames = ["Cyan Tower", "Pink Tower", "Amber Tower", "Lime Tower"];
  const towers = [
    { x: 200, y: 80, color: 0, range: 75, winOpen: false, winTimer: 0, winPeriod: 160, charge: 0 },
    { x: 340, y: 75, color: 1, range: 80, winOpen: false, winTimer: 40, winPeriod: 180, charge: 0 },
    { x: 450, y: 130, color: 2, range: 70, winOpen: false, winTimer: 80, winPeriod: 150, charge: 0 },
    { x: 230, y: 160, color: 3, range: 75, winOpen: false, winTimer: 120, winPeriod: 170, charge: 0 },
  ];

  // Track waypoints for creeps (S-curve towards base at x:110, y:180)
  const track = [
    { x: 500, y: 55 },
    { x: 200, y: 55 },
    { x: 190, y: 120 },
    { x: 460, y: 120 },
    { x: 460, y: 180 },
    { x: 110, y: 180 }
  ];

  let creeps = [];
  let lasers = [];
  let spawnTimer = 0;
  let creepsToSpawn = 6;
  let creepsSpawned = 0;

  function resetWave() {
    creeps = [];
    creepsToSpawn = 5 + wave * 3;
    creepsSpawned = 0;
    spawnTimer = 0;
  }

  // Canvas for Lunar Arena
  const canvas = h("canvas", { role: "img", "aria-label": "Lunar Relay game board. Use the relay grid buttons below to play.", style: "width:100%;height:240px;background:#0b0e14;border-radius:8px;display:block" });
  canvas.width = 600;
  canvas.height = 240;
  const ctx = canvas.getContext("2d");

  // HUD
  const hudScore = h("span", { class: "mono", style: "font-weight:700" }, "0");
  const hudWave = h("span", { class: "badge ok", role: "status" }, "WAVE 1/5");
  const hudBase = h("span", { class: "badge warn", role: "status" }, "BASE: 5/5");
  const pauseBtn = h("button", { class: "btn ghost sm" }, "Pause");
  pauseBtn.onclick = () => { isPaused = !isPaused; pauseBtn.textContent = isPaused ? "Resume" : "Pause"; };

  const hud = h("div", { style: "display:flex;justify-content:space-between;align-items:center;margin-bottom:10px" },
    h("div", { style: "display:flex;gap:12px;align-items:center" },
      h("span", { class: "mono small" }, "SCORE: ", hudScore), hudWave, hudBase
    ),
    pauseBtn
  );

  // 7x7 Match-3 Grid
  const GRID_SIZE = 7;
  let grid = [];
  function initGrid() {
    grid = [];
    for (let r = 0; r < GRID_SIZE; r++) {
      const row = [];
      for (let c = 0; c < GRID_SIZE; c++) {
        row.push(Math.floor(Math.random() * 4));
      }
      grid.push(row);
    }
    removeInitialMatches();
  }

  function removeInitialMatches() {
    for (let r = 0; r < GRID_SIZE; r++) {
      for (let c = 0; c < GRID_SIZE; c++) {
        while ((c >= 2 && grid[r][c] === grid[r][c-1] && grid[r][c] === grid[r][c-2]) ||
               (r >= 2 && grid[r][c] === grid[r-1][c] && grid[r][c] === grid[r-2][c])) {
          grid[r][c] = (grid[r][c] + 1) % 4;
        }
      }
    }
  }

  initGrid();
  resetWave();

  // Grid container
  const gridEl = h("div", {
    style: "display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin-top:12px;background:#151922;padding:8px;border-radius:8px;user-select:none"
  });

  let selectedTile = null;

  function renderGridUI() {
    gridEl.replaceChildren();
    for (let r = 0; r < GRID_SIZE; r++) {
      for (let c = 0; c < GRID_SIZE; c++) {
        const val = grid[r][c];
        const isSel = selectedTile && selectedTile.r === r && selectedTile.c === c;
        const color = towerColors[val];
        const glyphs = ["◆", "✚", "▲", "■"];
        const tile = h("div", {
          style: `height:44px;display:flex;align-items:center;justify-content:center;background:${color}22;border:2px solid ${isSel ? '#fff' : color};border-radius:6px;cursor:pointer;font-size:20px;color:${color};font-weight:900;box-shadow:${isSel ? '0 0 10px #fff' : 'none'};transition:all .1s`,
          onclick: () => onTileClick(r, c)
        }, glyphs[val]);
        gridEl.append(tile);
      }
    }
  }

  function onTileClick(r, c) {
    if (gameOver || isPaused) return;
    if (!selectedTile) {
      selectedTile = { r, c };
      renderGridUI();
      return;
    }
    const d = Math.abs(selectedTile.r - r) + Math.abs(selectedTile.c - c);
    if (d === 1) {
      // Swap
      const r1 = selectedTile.r, c1 = selectedTile.c;
      const t = grid[r1][c1]; grid[r1][c1] = grid[r][c]; grid[r][c] = t;
      selectedTile = null;
      const matched = checkMatches();
      if (!matched) {
        // Swap back
        const tb = grid[r1][c1]; grid[r1][c1] = grid[r][c]; grid[r][c] = tb;
      }
      renderGridUI();
    } else {
      selectedTile = { r, c };
      renderGridUI();
    }
  }

  function checkMatches() {
    let matched = false;
    const toClear = Array.from({ length: GRID_SIZE }, () => Array(GRID_SIZE).fill(false));

    // Horizontal
    for (let r = 0; r < GRID_SIZE; r++) {
      let run = 1;
      for (let c = 1; c < GRID_SIZE; c++) {
        if (grid[r][c] === grid[r][c-1]) {
          run++;
        } else {
          if (run >= 3) {
            for (let k = c - run; k < c; k++) toClear[r][k] = true;
          }
          run = 1;
        }
      }
      if (run >= 3) {
        for (let k = GRID_SIZE - run; k < GRID_SIZE; k++) toClear[r][k] = true;
      }
    }

    // Vertical
    for (let c = 0; c < GRID_SIZE; c++) {
      let run = 1;
      for (let r = 1; r < GRID_SIZE; r++) {
        if (grid[r][c] === grid[r-1][c]) {
          run++;
        } else {
          if (run >= 3) {
            for (let k = r - run; k < r; k++) toClear[k][c] = true;
          }
          run = 1;
        }
      }
      if (run >= 3) {
        for (let k = GRID_SIZE - run; k < GRID_SIZE; k++) toClear[k][c] = true;
      }
    }

    // Process matched
    const colorCounts = [0, 0, 0, 0];
    for (let r = 0; r < GRID_SIZE; r++) {
      for (let c = 0; c < GRID_SIZE; c++) {
        if (toClear[r][c]) {
          matched = true;
          colorCounts[grid[r][c]]++;
          grid[r][c] = Math.floor(Math.random() * 4); // drop new
        }
      }
    }

    if (matched) {
      // Fire towers for matched colors!
      for (let col = 0; col < 4; col++) {
        if (colorCounts[col] > 0) {
          triggerTowerFire(col, colorCounts[col]);
        }
      }
      score += 100;
      hudScore.textContent = score;
    }
    return matched;
  }

  function triggerTowerFire(colorIdx, matchSize) {
    const tower = towers[colorIdx];
    if (!tower) return;
    const isSurge = tower.winOpen;
    const dmg = isSurge ? 3 : 1;

    // Find nearest creep in range or closest to base
    let target = null;
    let minD = 9999;
    creeps.forEach(cr => {
      const d = Math.hypot(cr.x - tower.x, cr.y - tower.y);
      if (d < tower.range && d < minD) {
        minD = d;
        target = cr;
      }
    });

    if (!target && creeps.length > 0) {
      target = creeps[0]; // fire across map if no creep in range
    }

    if (target) {
      target.hp -= dmg;
      lasers.push({
        x1: tower.x, y1: tower.y,
        x2: target.x, y2: target.y,
        color: towerColors[colorIdx],
        surge: isSurge,
        life: 14
      });
      if (isSurge) {
        score += 50;
        hudScore.textContent = score;
      }
    }
  }

  // Game loop
  function loop() {
    if (!isPaused && !gameOver) {
      updateGame();
    }
    drawGame();
    animId = requestAnimationFrame(loop);
  }

  function updateGame() {
    // Update tower link windows
    towers.forEach(t => {
      t.winTimer++;
      if (t.winTimer >= t.winPeriod) {
        t.winTimer = 0;
        t.winOpen = !t.winOpen;
      }
    });

    // Spawn creeps
    spawnTimer++;
    if (spawnTimer > 70 && creepsSpawned < creepsToSpawn) {
      spawnTimer = 0;
      creepsSpawned++;
      creeps.push({
        wpIdx: 0,
        x: track[0].x,
        y: track[0].y,
        hp: 2 + Math.floor(wave / 2),
        maxHp: 2 + Math.floor(wave / 2),
        speed: 0.9 + wave * 0.12
      });
    }

    // Move creeps along track
    for (let i = creeps.length - 1; i >= 0; i--) {
      const cr = creeps[i];
      if (cr.hp <= 0) {
        score += 25 * wave;
        hudScore.textContent = score;
        creeps.splice(i, 1);
        continue;
      }
      const targetWp = track[cr.wpIdx + 1];
      if (!targetWp) {
        // Reached lunar base!
        baseHealth--;
        hudBase.textContent = `BASE: ${baseHealth}/${maxBase}`;
        creeps.splice(i, 1);
        if (baseHealth <= 0) {
          gameOver = true;
          won = false;
        }
        continue;
      }
      const dx = targetWp.x - cr.x;
      const dy = targetWp.y - cr.y;
      const dist = Math.hypot(dx, dy);
      if (dist < cr.speed) {
        cr.wpIdx++;
      } else {
        cr.x += (dx / dist) * cr.speed;
        cr.y += (dy / dist) * cr.speed;
      }
    }

    // Update laser beams
    for (let i = lasers.length - 1; i >= 0; i--) {
      lasers[i].life--;
      if (lasers[i].life <= 0) lasers.splice(i, 1);
    }

    // Wave progression
    if (creepsSpawned >= creepsToSpawn && creeps.length === 0) {
      if (wave < maxWaves) {
        wave++;
        hudWave.textContent = `WAVE ${wave}/5`;
        resetWave();
      } else {
        gameOver = true;
        won = true;
      }
    }
  }

  function drawGame() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Lunar terrain background with craters
    ctx.fillStyle = "#0c1017";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Lunar track (S-curve path)
    ctx.strokeStyle = "#1e2633";
    ctx.lineWidth = 26;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(track[0].x, track[0].y);
    for (let i = 1; i < track.length; i++) ctx.lineTo(track[i].x, track[i].y);
    ctx.stroke();

    ctx.strokeStyle = "#2f3c4e";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 6]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Lunar Base dome
    ctx.fillStyle = "#38d9d6";
    ctx.beginPath();
    ctx.arc(110, 180, 18, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#0c1017";
    ctx.beginPath();
    ctx.arc(110, 180, 13, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#38d9d6";
    ctx.fillText("BASE", 98, 184);

    // Towers & Link Windows
    towers.forEach((t, idx) => {
      // Range circle
      ctx.strokeStyle = t.winOpen ? towerColors[t.color] : "#222a36";
      ctx.lineWidth = t.winOpen ? 2 : 1;
      ctx.beginPath();
      ctx.arc(t.x, t.y, t.range, 0, Math.PI * 2);
      ctx.stroke();

      // Tower pylon
      ctx.fillStyle = towerColors[t.color];
      ctx.fillRect(t.x - 4, t.y - 12, 8, 24);
      ctx.beginPath();
      ctx.arc(t.x, t.y - 14, 6, 0, Math.PI * 2);
      ctx.fill();

      // Link window bar underneath
      ctx.fillStyle = "#151b24";
      ctx.fillRect(t.x - 16, t.y + 16, 32, 6);
      if (t.winOpen) {
        ctx.fillStyle = "#ffffff";
        ctx.shadowColor = towerColors[t.color];
        ctx.shadowBlur = 8;
        ctx.fillRect(t.x - 16, t.y + 16, 32, 6);
        ctx.shadowBlur = 0;
        ctx.fillStyle = "#ffffff";
        ctx.font = "9px monospace";
        ctx.fillText("3x SURGE", t.x - 20, t.y + 32);
      } else {
        const pct = t.winTimer / t.winPeriod;
        ctx.fillStyle = towerColors[t.color];
        ctx.fillRect(t.x - 16, t.y + 16, 32 * pct, 6);
      }
    });

    // Creeps (Noise bugs)
    creeps.forEach(cr => {
      ctx.fillStyle = "#c084fc";
      ctx.beginPath();
      ctx.arc(cr.x, cr.y, 8, 0, Math.PI * 2);
      ctx.fill();

      // Eyes
      ctx.fillStyle = "#fff";
      ctx.fillRect(cr.x - 4, cr.y - 2, 2, 2);
      ctx.fillRect(cr.x + 2, cr.y - 2, 2, 2);

      // HP bar
      ctx.fillStyle = "#ef4444";
      ctx.fillRect(cr.x - 10, cr.y - 14, 20, 3);
      ctx.fillStyle = "#22c55e";
      ctx.fillRect(cr.x - 10, cr.y - 14, 20 * (cr.hp / cr.maxHp), 3);
    });

    // Laser blasts
    lasers.forEach(l => {
      ctx.strokeStyle = l.color;
      ctx.lineWidth = l.surge ? 4 : 2;
      ctx.shadowColor = l.surge ? "#ffffff" : l.color;
      ctx.shadowBlur = l.surge ? 12 : 4;
      ctx.beginPath();
      ctx.moveTo(l.x1, l.y1);
      ctx.lineTo(l.x2, l.y2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    });

    // Game Over / Win overlay
    if (gameOver) {
      ctx.fillStyle = "rgba(10, 14, 20, 0.85)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = won ? "#6fe0b8" : "#ff7a6b";
      ctx.font = "bold 24px var(--serif)";
      ctx.textAlign = "center";
      ctx.fillText(won ? "MISSION ACCOMPLISHED! ALL WAVES CLEARED" : "BASE COMPROMISED - NOISE BREACH", canvas.width / 2, 110);
      ctx.font = "14px monospace";
      ctx.fillStyle = "#efe9dc";
      ctx.fillText(`Final Score: ${score}`, canvas.width / 2, 140);
      ctx.textAlign = "left";
    }
  }

  renderGridUI();
  loop();

  // Cleanup on tab switch
  cleanupView = () => { if (animId !== null) cancelAnimationFrame(animId); };
  // Add Restart button
  const restartBtn = h("button", {
    class: "btn sm",
    onclick: () => {
      score = 0; wave = 1; baseHealth = 5; gameOver = false; won = false; isPaused = false;
      hudScore.textContent = "0";
      hudWave.textContent = "WAVE 1/5";
      hudBase.textContent = "BASE: 5/5";
      initGrid();
      resetWave();
      renderGridUI();
    }
  }, "Restart Game");

  container.append(
    hud,
    canvas,
    h("div", { style: "display:flex;justify-content:space-between;align-items:center;margin-top:10px" },
      h("span", { class: "mono small mute" }, "RELAY GRID: Tap two neighbours to swap & match 3"),
      restartBtn
    ),
    gridEl
  );
};

(async () => { await loadStatus(); show("home"); })();
