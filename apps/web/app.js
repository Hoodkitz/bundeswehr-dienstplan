// Bundeswehr Dienstplan – Web-App (ohne Build-Schritt). Zeiten sind Ortszeit der Einheit und werden als
// lokale ISO-Zeiten ohne Zeitzone ausgetauscht; deshalb nie über Date() umrechnen, sondern Strings formatieren.

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const store = {
  get: k => { try { return sessionStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { v == null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch {} },
};

// ------------------------------------------------------------------ Rollen -> Rechte (Spiegel von permissions.py)
const PERMS = {
  soldat: ["roster:my-shifts", "trade:request", "self:service"],
  planer: ["soldat:read", "soldat:write", "abwesenheit:read", "abwesenheit:write", "roster:create", "roster:read",
           "roster:cancel", "roster:replan", "trade:decide"],
  truppenarzt: ["soldat:read", "abwesenheit:read", "abwesenheit:write"],
  vorgesetzter: ["soldat:read", "roster:read", "roster:approve", "trade:decide"],
  admin: ["tenant:manage", "soldat:read", "soldat:write", "abwesenheit:read", "roster:create", "roster:cancel",
          "export:datev"],
  audit: ["roster:read", "audit:read", "export:datev"],
};
const STATUS = {
  DRAFT_INIT: "angelegt", DATA_FETCHING: "Daten laden", CONSTRAINT_VALIDATION: "Regeln prüfen",
  SOLVER_OPTIMIZING: "wird berechnet", HARDFEASIBILITY_CHECK: "Zulässigkeit prüfen", SIMULATION_REVIEW: "Belastung prüfen",
  COMMAND_APPROVAL_INTERRUPT: "wartet auf Freigabe", PUBLISHED: "veröffentlicht", REALTIME_REPLANNING: "wird umgeplant",
  MANUAL_REVIEW: "Nacharbeit nötig", CANCELLED: "abgebrochen", FAILED: "fehlgeschlagen",
};
const RUNNING = ["DRAFT_INIT", "DATA_FETCHING", "CONSTRAINT_VALIDATION", "SOLVER_OPTIMIZING", "HARDFEASIBILITY_CHECK",
                 "SIMULATION_REVIEW", "REALTIME_REPLANNING"];
const CANCELLABLE = ["DRAFT_INIT", "DATA_FETCHING", "CONSTRAINT_VALIDATION", "SOLVER_OPTIMIZING",
                     "HARDFEASIBILITY_CHECK", "SIMULATION_REVIEW", "COMMAND_APPROVAL_INTERRUPT", "MANUAL_REVIEW"];
const SCHICHTTYP = {GRUNDDIENST: "Grunddienst", WACHDIENST: "Wachdienst", BEREITSCHAFT: "Bereitschaft",
                    SANITAETSDIENST: "Sanitätsdienst", UEBUNG: "Übung", LEHRGANG: "Lehrgang"};
const ABW = {URLAUB: "Urlaub", KRANK: "Krank", LEHRGANG: "Lehrgang", FREIWUNSCH: "Freiwunsch"};
const DIENSTGRADE = ["Soldat", "Gefreiter", "Obergefreiter", "Hauptgefreiter", "Stabsgefreiter", "Unteroffizier",
  "Stabsunteroffizier", "Feldwebel", "Oberfeldwebel", "Hauptfeldwebel", "Leutnant", "Oberleutnant", "Hauptmann",
  "Major", "Oberstleutnant", "Oberst"];
const MODUS = {keine: "Grundbetrieb", uebung: "Übung (§ 30c Abs. 4 SG)", einsatz: "Einsatz (§ 30c Abs. 4 SG)",
               landesverteidigung: "Landesverteidigung (§ 30c Abs. 4 SG)"};

const S = {token: null, claims: null, perms: new Set(), tenant: null, soldaten: {}, tab: null, poll: null};
const can = p => S.perms.has(p);

// ------------------------------------------------------------------ Hilfen
function toast(msg, bad = false) {
  const t = $("#toast"); t.textContent = msg; t.className = "toast" + (bad ? " bad" : "");
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.add("hidden"), 3500);
}
const d2 = n => String(n).padStart(2, "0");
const fmtDate = s => s ? `${s.slice(8, 10)}.${s.slice(5, 7)}.${s.slice(0, 4)}` : "–";
const fmtTime = s => s ? s.slice(11, 16) : "";
const fmtDT = s => s ? `${fmtDate(s)} ${fmtTime(s)}` : "–";
const dayName = iso => ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"][new Date(iso.slice(0, 10) + "T12:00:00").getDay()];
const name = id => { const s = S.soldaten[id]; return s ? `${s.dienstgrad} ${s.nachname}` : (id ? "unbekannt" : "unbesetzt"); };
function addDays(iso, n) { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${d2(d.getMonth() + 1)}-${d2(d.getDate())}`; }

function decode(token) {
  try { return JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))); } catch { return null; }
}
function errText(data, fallback) {
  const d = data && data.detail;
  if (!d) return fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(x => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`).join("; ");
  if (d.detail) return d.detail + (d.violations ? ": " + d.violations.map(v => v.detail).join("; ") : "");
  return JSON.stringify(d);
}
async function api(path, opts = {}) {
  await ensureFreshToken();
  const headers = {...(opts.body && !(opts.body instanceof FormData) ? {"Content-Type": "application/json"} : {}),
                   ...(S.token ? {Authorization: "Bearer " + S.token} : {}), ...(opts.headers || {})};
  const r = await fetch(path, {...opts, headers});
  if (r.status === 401) { logout(); throw new Error("Sitzung abgelaufen – bitte neu anmelden"); }
  if (opts.raw) { if (!r.ok) throw new Error(`Fehler ${r.status}`); return r; }
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) throw new Error(errText(data, `Fehler ${r.status}`));
  return data;
}
const post = (p, body, headers) => api(p, {method: "POST", body: JSON.stringify(body ?? {}), headers});

// ------------------------------------------------------------------ Anmeldung (OIDC Authorization Code + PKCE)
let cfg = {oidc: null, dev_login: false};
const b64url = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const rand = n => b64url(crypto.getRandomValues(new Uint8Array(n)));
async function discovery() {
  const r = await fetch(cfg.oidc.issuer.replace(/\/$/, "") + "/.well-known/openid-configuration");
  if (!r.ok) throw new Error("Identity Provider nicht erreichbar");
  return r.json();
}
async function oidcStart() {
  const d = await discovery();
  const verifier = rand(48), state = rand(16);
  const challenge = b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
  store.set("pkce", JSON.stringify({verifier, state}));
  const u = new URL(d.authorization_endpoint);
  Object.entries({response_type: "code", client_id: cfg.oidc.client_id, redirect_uri: location.origin + "/app/",
                  scope: cfg.oidc.scope, state, code_challenge: challenge, code_challenge_method: "S256"})
    .forEach(([k, v]) => u.searchParams.set(k, v));
  location.assign(u.toString());
}
async function tokenRequest(params) {
  const d = await discovery();
  const r = await fetch(d.token_endpoint, {method: "POST", headers: {"Content-Type": "application/x-www-form-urlencoded"},
                                           body: new URLSearchParams({client_id: cfg.oidc.client_id, ...params})});
  if (!r.ok) throw new Error("Anmeldung beim Identity Provider fehlgeschlagen");
  const t = await r.json();
  setSession(t.access_token, t.refresh_token || null);
}
async function oidcCallback() {
  const q = new URLSearchParams(location.search);
  if (!q.get("code")) return false;
  const saved = JSON.parse(store.get("pkce") || "{}");
  history.replaceState(null, "", "/app/");
  store.set("pkce", null);
  if (!saved.state || saved.state !== q.get("state")) throw new Error("Ungültige Anmeldeantwort (state)");
  await tokenRequest({grant_type: "authorization_code", code: q.get("code"), redirect_uri: location.origin + "/app/",
                      code_verifier: saved.verifier});
  return true;
}
let refreshing = null;
async function ensureFreshToken() {
  if (!S.claims || !S.claims.exp || !cfg.oidc) return;
  if (S.claims.exp * 1000 - Date.now() > 60000) return;
  const rt = store.get("rt");
  if (!rt) return;
  refreshing = refreshing || tokenRequest({grant_type: "refresh_token", refresh_token: rt}).catch(() => logout())
    .finally(() => { refreshing = null; });
  await refreshing;
}
function setSession(access, refresh) {
  S.token = access; S.claims = decode(access);
  store.set("at", access); if (refresh !== undefined) store.set("rt", refresh);
}
function logout() {
  S.token = S.claims = null; S.perms = new Set(); store.set("at", null); store.set("rt", null);
  clearTimeout(S.poll);
  $("#app").classList.add("hidden"); $("#login").classList.remove("hidden");
  $("#logout").classList.add("hidden"); $("#who").textContent = "";
}

async function devLogin(e) {
  e.preventDefault();
  $("#loginErr").textContent = "";
  try {
    const roles = $$("#devLogin .roles input:checked").map(i => i.value);
    if (!roles.length) throw new Error("Mindestens eine Rolle wählen");
    let tenant = $("#devTenant").value.trim();
    if (!tenant) {  // Testmandant anlegen: Plattform-Admin-Token -> neuer Mandant
      const boot = await (await fetch("/dev/token", {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({sub: "plattform-admin", tenant_id: crypto.randomUUID(), roles: ["admin"]})})).json();
      const r = await fetch("/api/v1/tenants", {method: "POST", headers: {"Content-Type": "application/json", Authorization: "Bearer " + boot.access_token},
        body: JSON.stringify({name: "Testeinheit " + new Date().toLocaleDateString("de-DE"), datev_berater_nr: "12345", datev_mandant_nr: "1"})});
      if (!r.ok) throw new Error("Testmandant konnte nicht angelegt werden");
      tenant = (await r.json()).id;
    }
    const r = await fetch("/dev/token", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({sub: $("#devSub").value.trim(), tenant_id: tenant, roles})});
    if (!r.ok) throw new Error(errText(await r.json().catch(() => null), "Anmeldung fehlgeschlagen"));
    setSession((await r.json()).access_token, null);
    await start();
  } catch (err) { $("#loginErr").textContent = err.message; }
}

// ------------------------------------------------------------------ Start & Navigation
const TABS = [
  {id: "plaene", label: "Dienstpläne", perm: "roster:read", render: renderPlaene},
  {id: "soldaten", label: "Personal", perm: "soldat:read", render: renderSoldaten},
  {id: "abwesenheiten", label: "Abwesenheiten", perm: "abwesenheit:read", render: renderAbwesenheiten},
  {id: "meine", label: "Meine Dienste", perm: "roster:my-shifts", render: renderMeine},
  {id: "tausch", label: "Diensttausch", perm: ["trade:request", "trade:decide"], render: renderTausch},
  {id: "datev", label: "DATEV-Export", perm: "export:datev", render: renderDatev},
  {id: "audit", label: "Audit-Log", perm: "audit:read", render: renderAudit},
  {id: "daten", label: "Meine Daten", perm: "self:service", render: renderDaten},
];
async function start() {
  // Rollen aus demselben Claim wie der Server (z. B. Keycloak realm_access.roles)
  const roles = (cfg.roles_claim || "roles").split(".").reduce((o, k) => (o && typeof o === "object" ? o[k] : undefined), S.claims);
  S.roles = Array.isArray(roles) ? roles : [];
  S.perms = new Set(S.roles.flatMap(r => PERMS[r] || []));
  $("#login").classList.add("hidden"); $("#app").classList.remove("hidden"); $("#logout").classList.remove("hidden");
  try { S.tenant = await api("/api/v1/tenants/current"); } catch { S.tenant = null; }
  $("#who").innerHTML = `<b>${esc(S.tenant ? S.tenant.name : "Einheit")}</b> · ${esc(S.claims.sub)} · ${esc(S.roles.join(", "))}`;
  if (can("soldat:read")) await loadSoldaten();
  const tabs = TABS.filter(t => [].concat(t.perm).some(can));
  $("#tabs").innerHTML = tabs.map(t => `<button type="button" data-tab="${t.id}">${esc(t.label)}</button>`).join("");
  $$("#tabs button").forEach(b => b.onclick = () => show(b.dataset.tab));
  if (!tabs.length) { $("#view").innerHTML = `<div class="card">Ihre Rollen geben keinen Zugriff auf diese Anwendung.</div>`; return; }
  show(tabs[0].id);
}
function show(id) {
  clearTimeout(S.poll);
  S.tab = id;
  $$("#tabs button").forEach(b => b.setAttribute("aria-current", b.dataset.tab === id ? "page" : "false"));
  const t = TABS.find(x => x.id === id);
  $("#view").innerHTML = `<div class="card muted">Lade …</div>`;
  t.render().catch(err => { $("#view").innerHTML = `<div class="card error">${esc(err.message)}</div>`; });
}
async function loadSoldaten() {
  S.soldaten = {};
  (await api("/api/v1/soldaten")).forEach(s => S.soldaten[s.id] = s);
}

// ------------------------------------------------------------------ Dienstpläne
async function renderPlaene() {
  const jobs = await api("/api/v1/jobs/roster");
  const v = $("#view");
  v.innerHTML = `
    ${can("roster:create") ? `<div class="row end"><button class="primary" id="neuerPlan">Neuen Dienstplan erstellen</button></div><div id="planForm"></div>` : ""}
    <div class="card"><h2>Dienstpläne</h2>
    ${jobs.length ? `<div class="scroll"><table><thead><tr><th>Zeitraum</th><th>Status</th><th>Schichten</th><th>Unbesetzt</th><th>Bewertung</th><th>Erstellt von</th><th></th></tr></thead><tbody>
      ${jobs.map(j => `<tr><td>${fmtDate(j.zeitraum_start)} – ${fmtDate(j.zeitraum_ende)}${j.ausnahme_modus !== "keine" ? ` <span class="badge warn">${esc(MODUS[j.ausnahme_modus])}</span>` : ""}</td>
        <td><span class="badge s-${esc(j.status)}">${esc(STATUS[j.status] || j.status)}</span></td>
        <td>${j.schichten.length}</td><td>${j.schichten.filter(s => !s.soldat_id).length || "–"}</td>
        <td>${esc(j.score || "–")}</td><td>${esc(j.created_by)}</td>
        <td><button data-job="${esc(j.id)}">Öffnen</button></td></tr>`).join("")}
    </tbody></table></div>` : `<p class="muted">Noch keine Dienstpläne.${can("roster:create") ? " Legen Sie zuerst Personal an und erstellen Sie dann einen Plan." : ""}</p>`}</div>
    <div id="jobDetail"></div>`;
  $$("[data-job]").forEach(b => b.onclick = () => openJob(b.dataset.job));
  if (can("roster:create")) $("#neuerPlan").onclick = planForm;
  if (RUNNING.some(st => jobs.some(j => j.status === st))) S.poll = setTimeout(() => S.tab === "plaene" && !$("#jobDetail").innerHTML && renderPlaene(), 3000);
}

function planForm() {
  const today = new Date(); const mon = new Date(today); mon.setDate(today.getDate() + ((8 - today.getDay()) % 7 || 7));
  const start = `${mon.getFullYear()}-${d2(mon.getMonth() + 1)}-${d2(mon.getDate())}`;
  $("#planForm").innerHTML = `<form class="card" id="pf">
    <h2>Neuer Dienstplan</h2>
    <div class="grid3">
      <div><label for="pfVon">Von</label><input type="date" id="pfVon" value="${start}" required></div>
      <div><label for="pfBis">Bis</label><input type="date" id="pfBis" value="${addDays(start, 6)}" required></div>
      <div><label for="pfModus">Betriebsart</label><select id="pfModus">${Object.entries(MODUS).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
    </div>
    <h3>Dienstposten je Tag</h3>
    <p class="muted">Jede Zeile wird an den gewählten Wochentagen angelegt. Endet ein Dienst vor seinem Beginn, läuft er über Mitternacht.</p>
    <div id="pfRows"></div>
    <button type="button" id="pfAdd">+ Dienstposten</button>
    <div class="row end"><button type="button" id="pfCancel" class="ghost">Abbrechen</button><button class="primary" type="submit">Plan berechnen</button></div>
  </form>`;
  const addRow = (r = {typ: "GRUNDDIENST", von: "07:00", bis: "16:00", anzahl: 1, quali: "", ort: "", tage: [1, 2, 3, 4, 5]}) => {
    const el = document.createElement("fieldset"); el.className = "pfrow";
    el.innerHTML = `<div class="grid6">
      <div><label>Art</label><select class="typ">${Object.entries(SCHICHTTYP).map(([k, v]) => `<option value="${k}" ${k === r.typ ? "selected" : ""}>${v}</option>`).join("")}</select></div>
      <div><label>Beginn</label><input type="time" class="von" value="${r.von}" required></div>
      <div><label>Ende</label><input type="time" class="bis" value="${r.bis}" required></div>
      <div><label>Personal</label><input type="number" class="anzahl" min="1" max="50" value="${r.anzahl}" required></div>
      <div><label>Qualifikation (ATN)</label><input class="quali" value="${esc(r.quali)}" placeholder="optional"></div>
      <div><label>Ort</label><input class="ort" value="${esc(r.ort)}" placeholder="optional"></div></div>
      <div class="row days">${["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map((t, i) => `<label><input type="checkbox" value="${(i + 1) % 7}" ${r.tage.includes((i + 1) % 7) ? "checked" : ""}> ${t}</label>`).join("")}
      <button type="button" class="ghost del">entfernen</button></div>`;
    el.querySelector(".del").onclick = () => el.remove();
    $("#pfRows").appendChild(el);
  };
  addRow();
  addRow({typ: "WACHDIENST", von: "18:00", bis: "06:00", anzahl: 2, quali: "", ort: "Hauptwache", tage: [0, 1, 2, 3, 4, 5, 6]});
  $("#pfAdd").onclick = () => addRow();
  $("#pfCancel").onclick = () => $("#planForm").innerHTML = "";
  $("#pf").onsubmit = async e => {
    e.preventDefault();
    const von = $("#pfVon").value, bis = $("#pfBis").value;
    if (bis < von) return toast("Das Ende liegt vor dem Beginn", true);
    const schichten = [];
    for (let day = von; day <= bis; day = addDays(day, 1)) {
      const wd = new Date(day + "T12:00:00").getDay();
      for (const row of $$(".pfrow")) {
        const tage = $$(".days input:checked", row).map(i => +i.value);
        if (!tage.includes(wd)) continue;
        const a = $(".von", row).value, b = $(".bis", row).value;
        schichten.push({typ: $(".typ", row).value, start: `${day}T${a}:00`, ende: `${b <= a ? addDays(day, 1) : day}T${b}:00`,
                        anzahl: +$(".anzahl", row).value, erforderliche_qualifikation: $(".quali", row).value.trim() || null,
                        ort: $(".ort", row).value.trim() || null});
      }
    }
    if (!schichten.length) return toast("Keine Dienstposten im Zeitraum", true);
    try {
      const job = await post("/api/v1/jobs/roster", {zeitraum_start: von, zeitraum_ende: bis, ausnahme_modus: $("#pfModus").value, schichten},
                             {"Idempotency-Key": crypto.randomUUID()});
      toast("Plan wird berechnet …");
      $("#planForm").innerHTML = "";
      openJob(job.id);
    } catch (err) { toast(err.message, true); }
  };
}

async function openJob(id) {
  clearTimeout(S.poll);
  const j = await api(`/api/v1/jobs/roster/${id}`);
  const box = $("#jobDetail");
  if (!box) return;
  const days = {};
  j.schichten.forEach(s => (days[s.start.slice(0, 10)] ||= []).push(s));
  const bad = new Set(j.violations.filter(v => v.level === "hard").flatMap(v => v.shift_ids || []));
  const hard = j.violations.filter(v => v.level === "hard"), other = j.violations.filter(v => v.level !== "hard");
  const actions = [
    can("roster:approve") && j.status === "COMMAND_APPROVAL_INTERRUPT" ? `<button class="primary" data-act="approve">Freigeben (Befehl nach § 10 SG)</button>` : "",
    can("roster:replan") && j.status === "PUBLISHED" ? `<button data-act="replan">Umplanen (nach Ausfall)</button>` : "",
    can("roster:cancel") && CANCELLABLE.includes(j.status) ? `<button class="danger" data-act="cancel">Abbrechen</button>` : "",
  ].join("");
  const per = (j.stats && j.stats.pro_soldat) || {};
  box.innerHTML = `<div class="card">
    <div class="row between"><h2>Dienstplan ${fmtDate(j.zeitraum_start)} – ${fmtDate(j.zeitraum_ende)}</h2><button class="ghost" id="closeJob">Schließen</button></div>
    <p><span class="badge s-${esc(j.status)}">${esc(STATUS[j.status] || j.status)}</span> ${RUNNING.includes(j.status) ? '<span class="spinner" aria-label="läuft"></span>' : ""}
      · Bewertung ${esc(j.score || "–")} · Version ${j.version}${j.approved_by ? ` · freigegeben von ${esc(j.approved_by)} am ${fmtDT(j.approved_at)}` : ""}</p>
    ${j.status === "COMMAND_APPROVAL_INTERRUPT" && !can("roster:approve") ? `<p class="hint">Der Plan ist zulässig und wartet auf die Freigabe durch den Vorgesetzten.</p>` : ""}
    ${j.status === "MANUAL_REVIEW" ? `<p class="hint bad">Nicht freigabefähig: Personal, Qualifikationen oder Abwesenheiten anpassen und einen neuen Plan berechnen.</p>` : ""}
    ${hard.length ? `<h3>Verstöße (müssen behoben werden)</h3><ul class="viol">${hard.map(v => `<li><b>${esc(v.constraint)}</b>: ${esc(v.detail)}${v.soldat_id ? ` (${esc(name(v.soldat_id))})` : ""}</li>`).join("")}</ul>` : ""}
    ${j.warnings.length ? `<h3>Hinweise</h3><ul>${j.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
    ${other.length ? `<details><summary>${other.length} weiche Abweichungen (Fairness, Wünsche)</summary><ul>${other.map(v => `<li>${esc(v.constraint)}: ${esc(v.detail)}</li>`).join("")}</ul></details>` : ""}
    <div class="row">${actions}</div>
  </div>
  <div class="week">${Object.keys(days).sort().map(d => `<div class="day"><h4>${dayName(d)} ${fmtDate(d)}</h4>
    ${days[d].sort((a, b) => a.start.localeCompare(b.start)).map(s => `<div class="shift t-${esc(s.typ)} ${!s.soldat_id ? "open" : ""} ${bad.has(s.id) ? "violation" : ""}">
      <div class="when">${fmtTime(s.start)}–${fmtTime(s.ende)}${s.ende.slice(0, 10) !== s.start.slice(0, 10) ? " (+1)" : ""} ${s.pinned ? "📌" : ""}</div>
      <div><b>${esc(SCHICHTTYP[s.typ] || s.typ)}</b>${s.ort ? ` · ${esc(s.ort)}` : ""}</div>
      <div class="who">${esc(name(s.soldat_id))}</div>
      ${s.erforderliche_qualifikation ? `<div class="muted">ATN ${esc(s.erforderliche_qualifikation)}</div>` : ""}</div>`).join("")}</div>`).join("")}</div>
  ${Object.keys(per).length ? `<div class="card"><h3>Belastung</h3><div class="scroll"><table><thead><tr><th>Soldat</th><th>Stunden</th><th>Dienste</th><th>Nachtdienste</th></tr></thead><tbody>
    ${Object.entries(per).sort((a, b) => b[1].stunden - a[1].stunden).map(([sid, p]) => `<tr><td>${esc(name(sid))}</td><td>${p.stunden}</td><td>${p.schichten}</td><td>${p.nachtdienste}</td></tr>`).join("")}
    </tbody></table></div><p class="muted">Ø ${j.stats.stunden_schnitt} h · min ${j.stats.stunden_min} h · max ${j.stats.stunden_max} h</p></div>` : ""}`;
  $("#closeJob").onclick = () => { clearTimeout(S.poll); box.innerHTML = ""; renderPlaene(); };
  $$("[data-act]", box).forEach(b => b.onclick = async () => {
    const act = b.dataset.act;
    if (act === "cancel" && !confirm("Diesen Planungslauf wirklich abbrechen?")) return;
    if (act === "approve" && !confirm("Plan als Befehl freigeben und veröffentlichen?")) return;
    try { await post(`/api/v1/jobs/roster/${j.id}/${act}`, act === "replan" ? {} : undefined); toast("Erledigt"); openJob(j.id); }
    catch (err) { toast(err.message, true); }
  });
  box.scrollIntoView({behavior: "smooth", block: "start"});
  if (RUNNING.includes(j.status)) S.poll = setTimeout(() => openJob(j.id), 2000);
}

// ------------------------------------------------------------------ Personal
async function renderSoldaten() {
  await loadSoldaten();
  const list = Object.values(S.soldaten);
  $("#view").innerHTML = `
    ${can("soldat:write") ? `<details class="card" ${list.length ? "" : "open"}><summary>Soldat anlegen</summary><form id="sf" class="grid3">
      <div><label for="sfPn">Personalnummer</label><input id="sfPn" required minlength="5" pattern="[A-Za-z0-9\\-]+"></div>
      <div><label for="sfDg">Dienstgrad</label><select id="sfDg">${DIENSTGRADE.map(d => `<option>${d}</option>`).join("")}</select></div>
      <div><label for="sfVn">Vorname</label><input id="sfVn" required></div>
      <div><label for="sfNn">Nachname</label><input id="sfNn" required></div>
      <div><label for="sfQ">Qualifikationen (ATN, kommagetrennt)</label><input id="sfQ" placeholder="z. B. WACHE, SAN"></div>
      <div><label for="sfSub">Login-Kennung (für „Meine Dienste“)</label><input id="sfSub" placeholder="optional"></div>
      <div><label><input type="checkbox" id="sfSan"> Kein Sanitätsdienst (Opt-out)</label></div>
      <div class="row end"><button class="primary" type="submit">Anlegen</button></div></form></details>` : ""}
    <div class="card"><h2>Personal (${list.length})</h2>
    <input id="sFilter" placeholder="Suchen nach Name, Dienstgrad, ATN …" aria-label="Personal filtern">
    <div class="scroll"><table><thead><tr><th>Name</th><th>Dienstgrad</th><th>Personalnr.</th><th>Qualifikationen</th><th>Login</th>${can("soldat:write") ? "<th></th>" : ""}</tr></thead>
    <tbody id="sBody"></tbody></table></div></div>`;
  const draw = () => {
    const q = ($("#sFilter").value || "").toLowerCase();
    $("#sBody").innerHTML = list.filter(s => !q || `${s.vorname} ${s.nachname} ${s.dienstgrad} ${s.qualifikationen.join(" ")}`.toLowerCase().includes(q))
      .map(s => `<tr><td>${esc(s.nachname)}, ${esc(s.vorname)}</td><td>${esc(s.dienstgrad)}</td><td>${esc(s.personalnummer)}</td>
        <td>${s.qualifikationen.map(q => `<span class="badge">${esc(q)}</span>`).join(" ")}${s.sanitaet_opt_out ? ' <span class="badge warn">kein SanDst</span>' : ""}</td>
        <td>${s.user_sub ? esc(s.user_sub) : '<span class="muted">–</span>'}</td>
        ${can("soldat:write") ? `<td><button data-edit="${esc(s.id)}">Qualifikationen</button></td>` : ""}</tr>`).join("") || `<tr><td colspan="6" class="muted">Keine Treffer.</td></tr>`;
    $$("[data-edit]").forEach(b => b.onclick = async () => {
      const s = S.soldaten[b.dataset.edit];
      const v = prompt(`Qualifikationen von ${s.dienstgrad} ${s.nachname} (kommagetrennt):`, s.qualifikationen.join(", "));
      if (v === null) return;
      try { await api(`/api/v1/soldaten/${s.id}`, {method: "PATCH", body: JSON.stringify({qualifikationen: v.split(",").map(x => x.trim()).filter(Boolean)})}); toast("Gespeichert"); renderSoldaten(); }
      catch (err) { toast(err.message, true); }
    });
  };
  $("#sFilter").oninput = draw; draw();
  if (can("soldat:write")) $("#sf").onsubmit = async e => {
    e.preventDefault();
    try {
      await post("/api/v1/soldaten", {personalnummer: $("#sfPn").value.trim(), dienstgrad: $("#sfDg").value, vorname: $("#sfVn").value.trim(),
        nachname: $("#sfNn").value.trim(), qualifikationen: $("#sfQ").value.split(",").map(x => x.trim()).filter(Boolean),
        sanitaet_opt_out: $("#sfSan").checked, user_sub: $("#sfSub").value.trim() || null});
      toast("Soldat angelegt"); renderSoldaten();
    } catch (err) { toast(err.message, true); }
  };
}

// ------------------------------------------------------------------ Abwesenheiten
async function renderAbwesenheiten() {
  if (!Object.keys(S.soldaten).length) await loadSoldaten();
  const rows = await api("/api/v1/abwesenheiten");
  const opts = Object.values(S.soldaten).map(s => `<option value="${esc(s.id)}">${esc(s.nachname)}, ${esc(s.vorname)} (${esc(s.dienstgrad)})</option>`).join("");
  $("#view").innerHTML = `
    ${can("abwesenheit:write") ? `<form class="card grid3" id="af"><h2 class="full">Abwesenheit eintragen</h2>
      <div><label for="afS">Soldat</label><select id="afS" required>${opts}</select></div>
      <div><label for="afT">Art</label><select id="afT">${Object.entries(ABW).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div>
      <div></div>
      <div><label for="afV">Von</label><input type="date" id="afV" required></div>
      <div><label for="afB">Bis einschließlich</label><input type="date" id="afB" required></div>
      <div class="row end"><button class="primary" type="submit">Eintragen</button></div>
      <p class="muted full">Krankmeldungen enthalten keine Diagnose – nur den Zeitraum (Datensparsamkeit).</p></form>` : ""}
    <div class="card"><h2>Abwesenheiten</h2><div class="scroll"><table><thead><tr><th>Soldat</th><th>Art</th><th>Von</th><th>Bis</th></tr></thead><tbody>
      ${rows.map(a => `<tr><td>${esc(name(a.soldat_id))}</td><td>${esc(ABW[a.typ] || a.typ)}</td><td>${fmtDate(a.start)}</td><td>${fmtDate(a.ende.slice(11, 16) === "00:00" ? addDays(a.ende.slice(0, 10), -1) : a.ende)}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">Keine Abwesenheiten erfasst.</td></tr>`}
    </tbody></table></div></div>`;
  if (can("abwesenheit:write")) $("#af").onsubmit = async e => {
    e.preventDefault();
    const v = $("#afV").value, b = $("#afB").value;
    if (b < v) return toast("Das Ende liegt vor dem Beginn", true);
    try { await post("/api/v1/abwesenheiten", {soldat_id: $("#afS").value, typ: $("#afT").value, start: `${v}T00:00:00`, ende: `${addDays(b, 1)}T00:00:00`}); toast("Eingetragen"); renderAbwesenheiten(); }
    catch (err) { toast(err.message, true); }
  };
}

// ------------------------------------------------------------------ Meine Dienste
async function renderMeine() {
  let shifts;
  try { shifts = await api("/api/v1/roster/my-shifts"); }
  catch (err) { $("#view").innerHTML = `<div class="card">${esc(err.message)}<p class="muted">Ihr Login muss vom Planer Ihrem Personaleintrag zugeordnet werden.</p></div>`; return; }
  $("#view").innerHTML = `<div class="card"><h2>Meine Dienste</h2>
    ${shifts.length ? `<ul class="mylist">${shifts.map(s => `<li><div><b>${dayName(s.start)} ${fmtDate(s.start)}</b> ${fmtTime(s.start)}–${fmtTime(s.ende)}</div>
      <div>${esc(SCHICHTTYP[s.typ] || s.typ)}${s.ort ? ` · ${esc(s.ort)}` : ""}</div>
      ${s.ruhezeit_bis_naechste_h != null ? `<div class="muted ${s.ruhezeit_bis_naechste_h < 11 ? "bad" : ""}">Ruhezeit bis zum nächsten Dienst: ${s.ruhezeit_bis_naechste_h} h</div>` : ""}</li>`).join("")}</ul>`
      : `<p class="muted">Keine veröffentlichten Dienste.</p>`}</div>`;
}

// ------------------------------------------------------------------ Diensttausch
async function renderTausch() {
  const v = $("#view"); v.innerHTML = "";
  if (can("trade:request")) {
    const [mine, trades] = await Promise.all([api("/api/v1/roster/my-shifts").catch(() => []), api("/api/v1/roster/trades").catch(() => [])]);
    const card = document.createElement("div"); card.className = "card";
    card.innerHTML = `<h2>Tausch beantragen</h2>
      ${mine.length ? `<form id="tf" class="grid3"><div><label for="tfS">Mein Dienst</label><select id="tfS">${mine.map(s => `<option value="${esc(s.schicht_id)}">${fmtDate(s.start)} ${fmtTime(s.start)} ${esc(SCHICHTTYP[s.typ] || s.typ)}</option>`).join("")}</select></div>
        <div><label for="tfK">Personalnummer des Kameraden</label><input id="tfK" required></div>
        <div><label for="tfB">Begründung</label><input id="tfB" maxlength="500"></div>
        <div class="row end full"><button class="primary" type="submit">Beantragen</button></div></form>` : `<p class="muted">Keine tauschbaren Dienste.</p>`}
      <h3>Meine Anfragen</h3>${tradeTable(trades, true)}`;
    v.appendChild(card);
    if ($("#tf", card)) $("#tf", card).onsubmit = async e => {
      e.preventDefault();
      try { await post("/api/v1/roster/trades", {schicht_id: $("#tfS").value, an_personalnummer: $("#tfK").value.trim(), begruendung: $("#tfB").value || null}); toast("Beantragt"); renderTausch(); }
      catch (err) { toast(err.message, true); }
    };
  }
  if (can("trade:decide")) {
    const pending = await api("/api/v1/roster/trades/pending");
    const card = document.createElement("div"); card.className = "card";
    card.innerHTML = `<h2>Zu entscheiden</h2>${tradeTable(pending, false)}`;
    v.appendChild(card);
  }
  $$("[data-trade]").forEach(b => b.onclick = async () => {
    const [id, act] = b.dataset.trade.split(":");
    try {
      if (act === "accept") await post(`/api/v1/roster/trades/${id}/accept`);
      else await post(`/api/v1/roster/trades/${id}/decide`, {genehmigt: act === "ok"});
      toast("Erledigt"); renderTausch();
    } catch (err) { toast(err.message, true); }
  });
}
function tradeTable(rows, mine) {
  const st = {OFFEN: "offen", ANGENOMMEN: "vom Kameraden angenommen", GENEHMIGT: "genehmigt", ABGELEHNT: "abgelehnt"};
  if (!rows.length) return `<p class="muted">Keine Anfragen.</p>`;
  return `<div class="scroll"><table><thead><tr><th>Von</th><th>An</th><th>Status</th><th>Begründung</th><th></th></tr></thead><tbody>
    ${rows.map(t => `<tr><td>${esc(t.von_name || name(t.von_soldat_id))}</td><td>${esc(t.an_name || name(t.an_soldat_id))}</td><td>${esc(st[t.status] || t.status)}</td><td>${esc(t.begruendung || "")}</td><td>
      ${mine && t.an_mich && t.status === "OFFEN" ? `<button data-trade="${esc(t.id)}:accept">Annehmen</button>` : ""}
      ${!mine && t.status === "ANGENOMMEN" ? `<button class="primary" data-trade="${esc(t.id)}:ok">Genehmigen</button>` : ""}
      ${!mine && ["OFFEN", "ANGENOMMEN"].includes(t.status) ? `<button class="danger" data-trade="${esc(t.id)}:no">Ablehnen</button>` : ""}</td></tr>`).join("")}
  </tbody></table></div>`;
}

// ------------------------------------------------------------------ DATEV
async function renderDatev() {
  const [pub, exps] = await Promise.all([api("/api/v1/exports/datev/jobs"), api("/api/v1/exports/datev")]);
  $("#view").innerHTML = `<form class="card grid3" id="xf"><h2 class="full">Export an die Lohnabrechnung</h2>
      <div><label for="xfJ">Veröffentlichter Dienstplan</label><select id="xfJ">${pub.map(j => `<option value="${esc(j.id)}">${fmtDate(j.zeitraum_start)} – ${fmtDate(j.zeitraum_ende)} (v${j.version})</option>`).join("")}</select></div>
      <div><label for="xfF">Format</label><select id="xfF"><option value="lodas">DATEV LODAS</option><option value="lug">DATEV Lohn und Gehalt</option></select></div>
      <div class="row end"><button class="primary" type="submit" ${pub.length ? "" : "disabled"}>Export erstellen</button></div>
      ${pub.length ? "" : `<p class="muted full">Exportiert werden nur freigegebene, veröffentlichte Pläne.</p>`}</form>
    <div class="card"><h2>Exporte</h2><div class="scroll"><table><thead><tr><th>Erstellt</th><th>Format</th><th>Status</th><th></th></tr></thead><tbody>
      ${exps.map(x => `<tr><td>${fmtDT(x.created_at)}</td><td>${esc(x.format.toUpperCase())}</td><td>${esc(x.status)}${x.error ? ` – ${esc(x.error)}` : ""}</td>
        <td>${x.status === "DONE" ? `<button data-dl="${esc(x.id)}" data-fmt="${esc(x.format)}">Herunterladen</button>` : ""}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">Noch keine Exporte.</td></tr>`}
    </tbody></table></div></div>`;
  $("#xf").onsubmit = async e => {
    e.preventDefault();
    try { await post("/api/v1/exports/datev", {job_id: $("#xfJ").value, format: $("#xfF").value}); toast("Export wird erstellt"); setTimeout(renderDatev, 1200); }
    catch (err) { toast(err.message, true); }
  };
  $$("[data-dl]").forEach(b => b.onclick = async () => {
    try {
      const r = await api(`/api/v1/exports/datev/${b.dataset.dl}/download`, {raw: true});
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a"); a.href = url; a.download = `datev_${b.dataset.fmt}_${b.dataset.dl.slice(0, 8)}.txt`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (err) { toast(err.message, true); }
  });
}

// ------------------------------------------------------------------ Audit
async function renderAudit() {
  const [rows, ver] = await Promise.all([api("/api/v1/audit?limit=300"), api("/api/v1/audit/verify")]);
  $("#view").innerHTML = `<div class="card"><h2>Audit-Log</h2>
    <p class="${ver.intakt ? "ok" : "bad"}">${ver.intakt ? "✔ Hash-Kette intakt" : `✖ Hash-Kette beschädigt ab Eintrag ${esc(ver.erste_defekte_seq)}`} · ${ver.eintraege} Einträge</p>
    <div class="scroll"><table><thead><tr><th>#</th><th>Zeit</th><th>Aktion</th><th>Benutzer</th><th>Details</th></tr></thead><tbody>
    ${rows.slice().reverse().map(e => `<tr><td>${e.seq}</td><td>${fmtDT(e.ts)}</td><td>${esc(e.action)}</td><td>${esc(e.actor)}</td><td class="mono">${esc(JSON.stringify(e.payload))}</td></tr>`).join("")}
    </tbody></table></div></div>`;
}

// ------------------------------------------------------------------ Meine Daten (DSGVO)
async function renderDaten() {
  $("#view").innerHTML = `<div class="card"><h2>Meine Daten</h2>
    <p>Sie können alle zu Ihnen gespeicherten Daten herunterladen (Art. 15 DSGVO) oder die Löschung beantragen (Art. 17 DSGVO).
    Daten mit gesetzlicher Aufbewahrungspflicht (z. B. Lohnrelevantes) werden bis zum Fristablauf gesperrt statt gelöscht.</p>
    <div class="row"><button id="dExp">Daten herunterladen</button><button class="danger" id="dDel">Löschung beantragen</button></div></div>`;
  $("#dExp").onclick = async () => {
    try {
      const data = await api("/api/v1/users/me/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
      const a = document.createElement("a"); a.href = url; a.download = "meine-daten.json"; a.click();
    } catch (err) { toast(err.message, true); }
  };
  $("#dDel").onclick = async () => {
    if (!confirm("Löschung Ihrer personenbezogenen Daten beantragen? Dies kann nicht rückgängig gemacht werden.")) return;
    try { const r = await api("/api/v1/users/me", {method: "DELETE"}); toast(r && r.status ? `Beantragt: ${r.status}` : "Beantragt"); }
    catch (err) { toast(err.message, true); }
  };
}

// ------------------------------------------------------------------ Boot
(async () => {
  $("#logout").onclick = logout;
  try { cfg = await (await fetch("/api/v1/auth/config")).json(); } catch {}
  if (cfg.oidc) { $("#oidcLogin").classList.remove("hidden"); $("#oidcLogin").onclick = () => oidcStart().catch(e => $("#loginErr").textContent = e.message); }
  if (cfg.dev_login) { $("#devLogin").classList.remove("hidden"); $("#devLogin").onsubmit = devLogin; }
  if (!cfg.oidc && !cfg.dev_login) $("#loginErr").textContent = "Anmeldung ist nicht konfiguriert (OIDC_JWKS_URL / OIDC_CLIENT_ID).";
  try {
    if (cfg.oidc && await oidcCallback()) return start();
  } catch (e) { $("#loginErr").textContent = e.message; return; }
  const at = store.get("at");
  if (at) {
    setSession(at);
    if (S.claims && S.claims.exp * 1000 > Date.now()) start().catch(logout);
    else logout();
  }
})();
