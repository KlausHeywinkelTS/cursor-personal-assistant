"use strict";

const STATUS_LABEL = {
  REGISTERED: "Registriert", IN_PROGRESS: "In Arbeit", BLOCKED: "Blockiert", REVIEW_REQUIRED: "Review erforderlich",
  DONE: "Erledigt", FAILED: "Fehlgeschlagen", CANCELLED: "Abgebrochen",
};
const TABS = [
  ["all", "Alle", null], ["active", "In Arbeit", ["REGISTERED", "IN_PROGRESS"]], ["review", "Review erforderlich", ["REVIEW_REQUIRED"]],
  ["blocked", "Blockiert", ["BLOCKED"]], ["done", "Abgeschlossen", ["DONE"]], ["failed", "Fehlgeschlagen", ["FAILED", "CANCELLED"]],
];
const ACTIVE = ["REGISTERED", "IN_PROGRESS", "BLOCKED"];

let state = null, filter = "all", openTaskId = null, csrf = null, refreshTimer = null;

/* ---------- Hilfen ---------- */
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) if (c != null && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
  return el;
}
const $ = (id) => document.getElementById(id);
function ago(iso) {
  if (!iso) return "–";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "gerade eben";
  if (s < 3600) return `vor ${Math.round(s / 60)} Min.`;
  if (s < 86400) return `vor ${Math.round(s / 3600)} Std.`;
  return `vor ${Math.round(s / 86400)} Tg.`;
}
const abs = (iso) => (iso ? new Date(iso).toLocaleString("de-DE") : "");
const time = (iso) => h("span", { title: abs(iso) }, ago(iso));
const base = (p) => (p ? p.replace(/[\\/]+$/, "").split(/[\\/]/).pop() : "–");
const pill = (cls, text) => h("span", { class: `pill ${cls}` }, text);
function flags(t) {
  const out = [];
  if (t.completion_incomplete) out.push(h("div", { class: "flag" }, "Abschluss erkannt, Ergebnis unvollständig"));
  if (t.orphan_suspected && ACTIVE.includes(t.status)) out.push(h("div", { class: "flag" }, "Möglicherweise verwaist: keine Aktivität mehr"));
  return out;
}

/* ---------- Daten ---------- */
async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error ? body.error.message : `HTTP ${res.status}`);
  return body;
}
async function refresh() {
  try {
    state = await api("/api/state");
    setConn(true);
    render();
    if (openTaskId != null && $("detail").open) showDetail(openTaskId, true);
  } catch (e) { setConn(false); }
}
function scheduleRefresh() { clearTimeout(refreshTimer); refreshTimer = setTimeout(refresh, 150); }
function setConn(ok) {
  const el = $("conn");
  el.className = `conn ${ok ? "ok" : "bad"}`;
  el.textContent = ok ? "live" : "keine Verbindung";
}
async function act(taskId, action, button) {
  if (action === "cancel" && !window.confirm("Auftrag wirklich abbrechen? Der Agent wird dadurch wieder frei.")) return;
  if (action === "fail" && !window.confirm("Ergebnis als fehlgeschlagen markieren?")) return;
  button.disabled = true;
  $("d-error").hidden = true;
  try {
    csrf = csrf || (await api("/api/csrf")).csrf_token;
    await api(`/api/tasks/${taskId}/actions/${action}`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify({ note: "" }),
    });
    await refresh();
  } catch (e) {
    $("d-error").textContent = e.message; $("d-error").hidden = false;
  } finally { button.disabled = false; }
}
function actionButtons(t) {
  const btn = (cls, label, action) => h("button", { type: "button", class: cls, onclick: (ev) => { ev.stopPropagation(); act(t.id, action, ev.currentTarget); } }, label);
  if (t.status === "REVIEW_REQUIRED") return [btn("primary", "Als erledigt markieren", "done"), btn("danger", "Fehlgeschlagen", "fail")];
  if (t.status === "BLOCKED") return [t.agent_stopped_at ? null : btn("primary", "Blocker gelöst", "unblock"), btn("danger", "Abbrechen", "cancel")].filter(Boolean);
  if (ACTIVE.includes(t.status)) return [btn("danger", "Abbrechen", "cancel")];
  return [];
}

/* ---------- Rendering ---------- */
function render() {
  if (!state) return;
  const a = state.attention;
  $("attention").replaceChildren(...[
    a.review ? h("span", { class: "chip review" }, `${a.review} Review offen`) : null,
    a.blocked ? h("span", { class: "chip blocked" }, `${a.blocked} blockiert`) : null,
    a.orphans ? h("span", { class: "chip orphan" }, `${a.orphans} möglicherweise verwaist`) : null,
    !a.review && !a.blocked && !a.orphans ? h("span", { class: "chip calm" }, "Nichts offen") : null,
  ].filter(Boolean));
  document.title = (a.review + a.blocked ? `(${a.review + a.blocked}) ` : "") + "Team-Cockpit";

  $("agents").replaceChildren(...state.agents.map(agentCard));
  if (!state.agents.length) $("agents").replaceChildren(h("p", { class: "empty" }, "Keine Agenten konfiguriert (Profile mit team_member: true fehlen)."));

  const attn = state.tasks.filter((t) => t.status === "REVIEW_REQUIRED" || t.status === "BLOCKED").reverse();
  $("attention-section").hidden = attn.length === 0;
  $("attention-list").replaceChildren(...attn.map(attentionCard));

  $("tabs").replaceChildren(...TABS.map(([key, label, statuses]) => {
    const n = statuses ? state.tasks.filter((t) => statuses.includes(t.status)).length : state.tasks.length;
    return h("button", { type: "button", role: "tab", "aria-selected": String(key === filter), onclick: () => { filter = key; render(); } },
      label, h("span", { class: "count" }, `(${n})`));
  }));
  const statuses = TABS.find((x) => x[0] === filter)[2];
  const rows = state.tasks.filter((t) => !statuses || statuses.includes(t.status));
  $("tasks").replaceChildren(...rows.map(taskRow));
  $("tasks-empty").hidden = rows.length > 0;
}
function agentCard(a) {
  const t = a.current_task;
  const label = a.availability === "busy" ? "Beschäftigt" : "Frei";
  return h("div", { class: "card" },
    h("h3", null, a.display_name, pill(a.availability, label)),
    t ? [
      h("div", { class: "task-title" }, `#${t.id} ${t.title}`),
      h("div", { class: "meta" }, pill(t.status, STATUS_LABEL[t.status])),
      h("div", { class: "meta", title: t.project_path || "" }, `Projekt: ${base(t.project_path)}`),
      h("div", { class: "meta" }, "Begonnen: ", time(t.started_at || t.created_at)),
      h("div", { class: "meta" }, "Letzte Aktualisierung: ", time(t.updated_at)),
      flags(t),
    ] : h("div", { class: "meta" }, a.description || "Verfügbar für einen neuen Auftrag."),
    a.open_reviews ? h("div", { class: "meta" }, `${a.open_reviews} Review(s) offen`) : null,
  );
}
function attentionCard(t) {
  return h("div", { class: `card ${t.status === "BLOCKED" ? "attn-blocked" : "attn-review"}`, onclick: () => showDetail(t.id), tabindex: "0", role: "button", onkeydown: (e) => { if (e.key === "Enter") showDetail(t.id); } },
    h("h3", null, `${t.agent_display_name}`, pill(t.status, STATUS_LABEL[t.status])),
    h("div", { class: "task-title" }, `#${t.id} ${t.title}`),
    h("div", { class: "meta" }, t.status === "BLOCKED" ? "Blocker: " : "Ergebnis: ", (t.status === "BLOCKED" ? lastBlocker(t) : t.summary) || "–"),
    flags(t),
    h("div", { class: "actions" }, actionButtons(t)),
  );
}
const lastBlocker = (t) => t.blocker_reason || "siehe Details";
function taskRow(t) {
  return h("tr", { tabindex: "0", onclick: () => showDetail(t.id), onkeydown: (e) => { if (e.key === "Enter") showDetail(t.id); } },
    h("td", null, t.id), h("td", null, t.agent_display_name),
    h("td", { class: "title" }, t.title, t.parent_task_id ? h("span", { class: "meta" }, ` (Unterauftrag von #${t.parent_task_id})`) : null, flags(t)),
    h("td", { title: t.project_path || "" }, base(t.project_path)),
    h("td", null, pill(t.status, STATUS_LABEL[t.status])),
    h("td", null, time(t.updated_at)));
}

/* ---------- Detail ---------- */
const taskLink = (id, label) => h("a", { href: `#task-${id}`, onclick: (e) => { e.preventDefault(); showDetail(id); } }, `#${id} ${label}`);
async function showDetail(id, silent) {
  openTaskId = id;
  try {
    const t = await api(`/api/tasks/${id}`);
    $("d-title").textContent = `#${t.id} ${t.title}`;
    const ref = t.result_reference || "";
    const refEl = /^https?:\/\//.test(ref) ? h("a", { href: ref, target: "_blank", rel: "noopener noreferrer" }, ref) : ref || "–";
    const blocker = [...t.events].reverse().find((e) => e.event_type === "STATUS_BLOCKED" || e.event_type === "BLOCKER_UPDATED");
    $("d-body").replaceChildren(h("div", null,
      h("div", null, pill(t.status, STATUS_LABEL[t.status])),
      flags(t).map((f) => h("div", { class: "banner" }, f.textContent)),
      h("dl", null,
        h("dt", null, "Agent"), h("dd", null, t.agent_display_name),
        t.parent ? [h("dt", null, "Beauftragt von"), h("dd", null, taskLink(t.parent.id, `${t.parent.agent_display_name}: ${t.parent.title}`))] : null,
        t.children && t.children.length ? [h("dt", null, "Unteraufträge"), h("dd", null, h("ul", { class: "events" },
          t.children.map((c) => h("li", null, taskLink(c.id, `${c.agent_display_name}: ${c.title}`), " ", pill(c.status, STATUS_LABEL[c.status])))))] : null,
        h("dt", null, "Projekt"), h("dd", null, t.project_path || "–"),
        h("dt", null, "Beschreibung"), h("dd", null, t.description || "–"),
        t.status === "BLOCKED" && blocker ? [h("dt", null, "Blocker"), h("dd", null, blocker.message)] : null,
        h("dt", null, "Zusammenfassung"), h("dd", null, t.summary || "–"),
        h("dt", null, "Ergebnis"), h("dd", null, refEl),
        t.failure_reason ? [h("dt", null, "Grund"), h("dd", null, t.failure_reason)] : null,
        h("dt", null, "Begonnen"), h("dd", null, abs(t.started_at) || "–"),
        h("dt", null, "Aktualisiert"), h("dd", null, abs(t.updated_at))),
      h("h4", null, "Ereignisse"),
      h("ul", { class: "events" }, t.events.map((e) => h("li", null, h("span", { class: "t" }, new Date(e.timestamp).toLocaleTimeString("de-DE")), `${e.event_type}${e.message ? ": " + e.message : ""}`))),
    ));
    $("d-actions").replaceChildren(...actionButtons(t));
    if (!$("detail").open) { $("d-error").hidden = true; $("detail").showModal(); history.replaceState(null, "", `#task-${id}`); }
  } catch (e) { if (!silent) { $("d-error").textContent = e.message; $("d-error").hidden = false; } }
}

/* ---------- Start ---------- */
$("d-close").addEventListener("click", () => { $("detail").close(); });
$("detail").addEventListener("close", () => { openTaskId = null; history.replaceState(null, "", location.pathname); });
refresh().then(() => {  // Deep-Link: /#task-12 öffnet direkt die Detailansicht
  const m = /^#task-(\d+)$/.exec(location.hash);
  if (m) showDetail(Number(m[1]));
});
setInterval(refresh, 10000); // Polling-Fallback
setInterval(() => state && render(), 30000); // relative Zeiten aktualisieren
if (window.EventSource) {
  const es = new EventSource("/api/stream");
  es.addEventListener("changed", scheduleRefresh);
  es.addEventListener("hello", scheduleRefresh);
}
