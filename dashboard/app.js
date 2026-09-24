// HåkonBench dashboard — vanilla JS, no build step.
"use strict";

const S = {
  config: null,
  job: null,          // latest job snapshot (from SSE)
  es: null,           // EventSource for the active job
  skew: 0,            // client clock − server clock (seconds)
  form: null,         // new-run form state (kept while navigating)
  plan: null,
  planSeq: 0,
  runTab: "results",
  logOpen: false,
};
const PROVIDER_ORDER = ["anthropic", "openai", "google", "xai"];
const PROVIDER_NAME = { anthropic: "Anthropic", openai: "OpenAI", google: "Google", xai: "xAI" };
const DIMS = [["accuracy", "Accuracy"], ["strategy", "Strategy"], ["creativity", "Creativity"], ["structure", "Structure"], ["fidelity", "Fidelity"]];
// Short stencil codes shown in narrow leaderboards (full name stays in title + screen-reader text)
const DIM_SHORT = { accuracy: "ACC", strategy: "STR", creativity: "CRE", structure: "STU", fidelity: "FID" };

const $ = (sel, el = document) => el.querySelector(sel);
const view = $("#view");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = (t) => DOMPurify.sanitize(marked.parse(t || ""));
const enc = encodeURIComponent;
// Sound hook — safe no-op if sound.js failed to load.
const sfx = (name) => { try { if (window.SFX) window.SFX.play(name); } catch { /* ignore */ } };
const reduceMotion = () => !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
// Phase-locked animation delay for looping effects on elements that SSE re-renders every event:
// a fresh node joins the loop where the old one was instead of restarting it (no stutter).
// `key` adds a stable per-item offset (e.g. the model label) so sibling loops don't run in lockstep.
const hashMs = (k, ms) => { let h = 0; for (const c of String(k)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h % ms; };
const phase = (ms, key = "") => `-${((Date.now() + (key ? hashMs(key, ms) : 0)) % ms) / 1000}s`;

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await r.json().catch(() => null);
  if (!r.ok) throw new Error((data && data.error) || `${r.status} ${r.statusText}`);
  return data;
}

function toast(msg, bad = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (bad ? " bad" : "");   // drops .show/.out …
  clearTimeout(toast._h);
  t.hidden = false;
  void t.offsetWidth;                             // … so re-adding .show replays the slide-in and the LED blinks
  t.classList.add("show");
  if (bad) sfx("error");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    if (reduceMotion()) { t.hidden = true; return; }
    t.classList.add("out");                       // slide back down, then hide
    toast._h = setTimeout(() => { t.hidden = true; t.classList.remove("out"); }, 200);
  }, bad ? 7000 : 3500);
}

// ── Formatting ───────────────────────────────────────────────
const nf = new Intl.NumberFormat("nb-NO");
const fmtInt = (n) => (n == null || n === "" ? "—" : nf.format(Number(n)));
function fmtTok(n) {
  if (n == null || n === "") return "—";
  n = Number(n);
  return n >= 1000 ? (n / 1000).toFixed(n >= 100000 ? 0 : 1).replace(".", ",") + "k" : String(n);
}
function fmtDur(s) {
  if (s == null || isNaN(s)) return "—";
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h) return `${h}t ${m}m`;
  if (m) return `${m}m ${String(sec).padStart(2, "0")}s`;
  return `${sec}s`;
}
const fmtSecs = (s) => (s == null ? "—" : fmtDur(Number(s)));
const serverNow = () => Date.now() / 1000 - S.skew;
const shortModel = (spec) => (spec || "").split("/").pop();
const pdot = (p) => `<span class="pdot ${esc(p)}"></span>`;
const scoreClass = (v) => (v == null ? "" : v >= 8 ? "hi" : v >= 5 ? "mid" : "lo");

// ── Routing ──────────────────────────────────────────────────
function route() {
  const h = location.hash.slice(1) || "/";
  const [path, qs] = h.split("?");
  const parts = path.split("/").filter(Boolean);
  const params = new URLSearchParams(qs || "");
  const section = parts[0] || "runs";
  document.querySelectorAll("[data-nav]").forEach((a) =>
    a.classList.toggle("active", a.dataset.nav === (section === "run" ? "runs" : section)));
  closeDrawer();
  screenSwap();
  if (section === "run" && parts[1]) return renderRun(decodeURIComponent(parts[1]));
  if (section === "new") return renderNew(params);
  if (section === "live") return renderLive();
  return renderRuns();
}
window.addEventListener("hashchange", route);

function loading(msg = "Laster…") {
  view.innerHTML = `<div class="empty loading"><span class="spin" aria-hidden="true"></span><p>${esc(msg)}</p></div>`;
}
function failView(e) {
  view.innerHTML = `<div class="empty fail"><h3>Noe gikk galt</h3><p>${esc(e.message || e)}</p><a class="btn" href="#/">Til runs</a></div>`;
}

// ── Screen swap + boot screen (decorative; skipped under reduced motion) ──
// On a route change the #swap-veil blanks the old screen at once, then a scan beam sweeps down and
// reveals the new one as soon as it has rendered (or after 260 ms, revealing the loading screen).
// Only route() arms it — SSE re-renders and tab redraws never replay it.
const Swap = { pending: false, hold: 0, done: 0, first: true };
const isLoadingView = () => !!view.querySelector(":scope > .empty.loading");
function screenSwap() {
  if (Swap.first) { Swap.first = false; return; }   // first route: the boot screen does the reveal
  const v = $("#swap-veil");
  if (!v || reduceMotion()) return;
  clearTimeout(Swap.done);
  v.classList.remove("sweep");
  view.classList.remove("entering");
  v.classList.add("hold");
  Swap.pending = true;
  clearTimeout(Swap.hold);
  Swap.hold = setTimeout(sweep, 60);
}
function sweep() {
  const v = $("#swap-veil");
  clearTimeout(Swap.hold);
  Swap.pending = false;
  v.classList.remove("hold");
  void v.offsetWidth;
  v.classList.add("sweep");
  view.classList.add("entering");
  clearTimeout(Swap.done);
  Swap.done = setTimeout(() => { v.classList.remove("sweep"); view.classList.remove("entering"); }, 320);
}
const Boot = { el: $("#boot") };
function bootDone(now) {
  const b = Boot.el;
  if (!b) return;
  Boot.el = null;
  // Keep the decorative lines up for at least ~340 ms after navigation start, never longer:
  // total cost is ≤ ~560 ms even on an instant server, and 0 extra when /api/config is slow.
  const wait = now ? 0 : Math.max(0, 340 - performance.now());
  setTimeout(() => {
    b.classList.add("off");
    view.classList.add("entering");
    setTimeout(() => { b.remove(); view.classList.remove("entering"); }, 300);
  }, wait);
}
if (Boot.el) {
  if (reduceMotion()) { Boot.el.remove(); Boot.el = null; }
  else {
    // Skippable: any click / key dismisses it. The overlay is pointer-events:none and both listeners are
    // passive capture listeners, so the click or key still reaches its real target. Hard cap 1.5 s.
    const skip = () => bootDone(true);
    // A click outside the command bar lands on content the boot screen still hides: dismiss only, don't activate.
    // (preventDefault on pointerdown doesn't cancel the click, so the matching click is swallowed too.)
    window.addEventListener("pointerdown", (e) => {
      if (document.getElementById("boot") && e.target instanceof Element && !e.target.closest(".topbar")) {   // still on screen (incl. its exit)
        e.preventDefault();
        const eat = (ev) => { ev.preventDefault(); ev.stopPropagation(); };
        window.addEventListener("click", eat, { capture: true, once: true });
        setTimeout(() => window.removeEventListener("click", eat, { capture: true }), 600);
      }
      skip();
    }, { capture: true, once: true });
    window.addEventListener("keydown", skip, { capture: true, once: true });
    setTimeout(skip, 1500);
  }
}
new MutationObserver(() => {
  if (isLoadingView() || !view.firstElementChild) return;
  if (Swap.pending) sweep();
  if (Boot.el) bootDone(false);
}).observe(view, { childList: true });

// ── Runs list ────────────────────────────────────────────────
async function renderRuns() {
  loading();
  let runs;
  try { runs = await api("/api/runs"); } catch (e) { return failView(e); }
  const buckets = runs.filter((r) => !r.legacy);
  const legacy = runs.filter((r) => r.legacy);
  const answers = runs.reduce((a, r) => a + r.ok, 0);
  view.innerHTML = `
    <div class="page-head">
      <div><h1>Runs</h1><div class="sub">${runs.length} runs · ${fmtInt(answers)} lagrede svar</div></div>
      <div class="actions"><a class="btn primary" href="#/new">＋ Ny run</a></div>
    </div>
    ${buckets.length ? `<div class="runs-grid">${buckets.map(runCard).join("")}</div>` :
      `<div class="card empty"><h3>Ingen runs ennå</h3><p>Start din første run.</p><a class="btn primary" href="#/new">Ny run</a></div>`}
    ${legacy.length ? `<h2 class="section">Eldre runs · før config-buckets</h2><div class="runs-grid legacy">${legacy.map(runCard).join("")}</div>` : ""}`;
}

function configChips(m, r = {}) {
  if (!m || !m.effort) return `<span class="chip">legacy-mappe</span>`;
  return `
    <span class="chip mono ${r.current_prompt ? "gold" : ""}" title="${r.current_prompt ? "Samme prompt som nå" : "Eldre prompt"}">p${esc(m.prompt_sha)}</span>
    <span class="chip">effort: ${esc(m.effort)}</span>
    <span class="chip ${m.web_search ? "on" : ""}">${m.web_search ? "web-søk på" : "web-søk av"}</span>
    ${m.tag ? `<span class="chip">tag: ${esc(m.tag)}</span>` : ""}`;
}

function runCard(r) {
  const w = r.winner;
  return `
  <a class="card run-card" href="#/run/${enc(r.name)}">
    <div class="name">${esc(r.name)}</div>
    <div class="chips">${configChips(r.manifest, r)}</div>
    ${w ? `<div class="winner">
        <span class="trophy">🏆</span>
        <div class="who"><b>${esc(w.model)}</b><span>${esc(PROVIDER_NAME[w.provider] || w.provider)}</span></div>
        <div class="score">${w.total}<small>/50</small></div>
      </div>` : `<div class="winner"><div class="who"><span>${r.graded ? "Karakterer kunne ikke leses" : "Ikke gradet ennå"}</span></div></div>`}
    <div class="foot">
      <span>${r.ok} svar</span>
      ${r.failed ? `<span class="bad">${r.failed} feilet</span>` : ""}
      ${r.graded ? `<span>gradet ${esc(r.graded_at ? r.graded_at.slice(0, 10) : r.graded)}${r.grader ? " av " + esc(shortModel(r.grader)) : ""}</span>` : ""}
      ${r.ungraded.length ? `<span style="color:var(--warn)">${r.ungraded.length} ikke gradet</span>` : ""}
    </div>
  </a>`;
}

// ── Run detail ───────────────────────────────────────────────
async function renderRun(name) {
  loading();
  let d;
  try { d = await api(`/api/runs/${enc(name)}`); } catch (e) { return failView(e); }
  const canFill = !d.legacy && d.current_prompt;
  const tabs = [
    ["results", "Resultater"],
    ["verdict", "Dommerens vurdering"],
    ["answers", `Svar (${d.answers.length})`],
    ["prompt", "Prompt"],
    ["history", `Historikk (${d.history.length})`],
  ];
  if (!tabs.some(([k]) => k === S.runTab)) S.runTab = "results";
  const draw = () => {
    view.innerHTML = `
      <a class="back" href="#/">← Alle runs</a>
      <div class="page-head">
        <div>
          <h1 class="mono">${esc(d.name)}</h1>
          <div class="chips" style="margin-top:10px">${configChips(d.manifest, d)}
            ${d.grader ? `<span class="chip">dommer: ${esc(d.grader)}</span>` : ""}</div>
        </div>
        <div class="actions">
          ${canFill ? `<a class="btn" href="#/new?from=${enc(d.name)}">＋ Kjør flere modeller her</a>` : ""}
          <button class="btn primary" id="regrade-btn">⚖ Grade på nytt</button>
        </div>
      </div>
      ${!d.legacy && !d.current_prompt ? `<div class="note warn" style="margin:-8px 0 16px">Denne bucketen ble besvart med en <b>eldre prompt</b> (p${esc(d.manifest.prompt_sha)}). Dagens prompt er p${esc(S.config.prompt_sha)}, så nye runs havner i en annen bucket.</div>` : ""}
      ${d.ungraded.length ? `<div class="note warn" style="margin:-8px 0 16px"><b>${d.ungraded.length} svar er ikke med i siste grading:</b> ${d.ungraded.map((l) => `<code>${esc(l)}</code>`).join(", ")}. Grade på nytt for å få dem med i sammenligningen.</div>` : ""}
      <div class="tabs">${tabs.map(([k, t]) => `<button data-tab="${k}" class="${S.runTab === k ? "active" : ""}">${esc(t)}</button>`).join("")}</div>
      <div id="tab-body">${tabBody(d)}</div>`;
    view.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => {
      const hadFocus = document.activeElement === b;
      S.runTab = b.dataset.tab;
      draw();
      const tb = $("#tab-body");
      if (tb) tb.classList.add("tab-in");   // fresh node each click → the fade plays once per switch
      if (hadFocus) refocus({ key: focusKey(b) });
    }));
    $("#regrade-btn").onclick = () => openRegrade(d.name);
    wireAnswerClicks(view, d.name);
    view.querySelectorAll("[data-history]").forEach((el) => (el.onclick = () => openHistory(d.name, el.dataset.history, el.dataset.label)));
  };
  draw();
}

function tabBody(d) {
  switch (S.runTab) {
    case "verdict":
      return d.verdict ? `<div class="card pad md">${md(d.verdict)}</div>` : emptyCard("Ikke gradet ennå", "Trykk «Grade på nytt» for å få en dom.");
    case "answers":
      return d.answers.length ? `<div class="answers">${d.answers.map(answerItem).join("")}</div>` : emptyCard("Ingen svar", "");
    case "prompt":
      return `<div class="card pad prompt-box">${esc(d.prompt || "(ingen _prompt.md i denne mappen — legacy-run)")}</div>`;
    case "history":
      return d.history.length ? `<div class="answers">${d.history.map((h) => `
        <button class="card answer-item" data-history="${esc(h.file)}" data-label="${esc(h.grader + " · " + h.when)}">
          <span class="pdot ${esc(h.grader.split("/")[0])}"></span>
          <div class="body"><b>${esc(h.grader)}</b><div class="meta">${esc(h.when)}</div></div>
        </button>`).join("")}</div>` : emptyCard("Ingen arkiverte dommer", "Eldre runs har bare _grades.md.");
    default: {
      let html = d.board && d.board.rows.length ? `<div class="card board-wrap">${boardHTML(d.board)}</div>` :
        emptyCard(d.verdict ? "Kunne ikke lese karaktertabellen" : "Ikke gradet ennå", d.verdict ? "Se «Dommerens vurdering» for hele teksten." : "Grade bucketen for å få en leaderboard.");
      const bad = d.answers.filter((a) => a.status !== "ok");
      if (bad.length) {
        html += `<div class="note bad"><b>${bad.length} uten gyldig svar</b> (blir kalt på nytt neste gang denne configen kjøres): ${bad.map((a) => `<code>${esc(a.label)}</code>`).join(", ")}</div>`;
      }
      return html;
    }
  }
}

const emptyCard = (title, text) => `<div class="card empty"><h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;

function boardHTML(board) {
  const rows = board.rows;
  const showSearch = rows.some((r) => r.meta && r.meta.web_searches != null);
  return `<table class="board">
    <thead><tr>
      <th>#</th><th>Modell</th>${DIMS.map(([k, t]) => `<th class="dim" title="${t}" data-short="${DIM_SHORT[k]}"><span class="lbl">${t}</span></th>`).join("")}
      <th class="total">Total</th><th class="num">Tid</th><th class="num" title="Output / reasoning / total">Tokens</th>${showSearch ? "<th class=\"num\">Søk</th>" : ""}
    </tr></thead>
    <tbody>${rows.map((r, i) => `
      <tr ${r.label ? `data-answer="${esc(r.label)}"` : ""}>
        <td class="rank"><span class="rk">${i + 1}</span></td>
        <td><div class="model-cell">${pdot(r.provider)}<div><b>${esc(r.model)}</b> <span class="faint mono" style="font-size:11px">${esc(r.letter)}</span>
          ${r.verdict ? `<div class="verdict">${esc(r.verdict)}</div>` : ""}</div></div></td>
        ${DIMS.map(([k]) => `<td class="dim"><div class="v">${r[k] ?? "—"}</div><div class="bar ${scoreClass(r[k])}"><i style="width:${(r[k] || 0) * 10}%"></i></div></td>`).join("")}
        <td class="total"><div class="v">${r.total ?? "—"}<small>/50</small></div><div class="bar"><i style="width:${((r.total || 0) / 50) * 100}%"></i></div></td>
        <td class="num">${fmtSecs(r.meta.seconds)}</td>
        <td class="num">${fmtTok(r.meta.output_tokens)} / ${fmtTok(r.meta.reasoning_tokens)} / ${fmtTok(r.meta.total_tokens)}</td>
        ${showSearch ? `<td class="num">${r.meta.web_searches ?? "—"}</td>` : ""}
      </tr>`).join("")}
    </tbody></table>`;
}

function answerItem(a) {
  const m = a.meta || {};
  const bits = a.status === "ok"
    ? [fmtSecs(m.seconds), m.total_tokens ? fmtTok(m.total_tokens) + " tok" : null, m.date ? String(m.date).slice(0, 10) : null].filter(Boolean).join(" · ")
    : esc((a.error || "").split("\n")[0].slice(0, 90));
  return `<button class="card answer-item" data-answer="${esc(a.label)}">
    ${pdot(a.provider)}
    <div class="body"><b>${esc(a.model)}</b><div class="meta">${bits}</div></div>
    <span class="status ${esc(a.status)}">${{ ok: "OK", failed: "Feilet", empty: "Tomt", unknown: "?" }[a.status] || esc(a.status)}</span>
  </button>`;
}

function wireAnswerClicks(root, runName) {
  root.querySelectorAll("[data-answer]").forEach((el) => {
    el.onclick = () => openAnswer(runName, el.dataset.answer);
    if (el.tagName === "TR") {   // leaderboard rows: keyboard-operable (Enter/Space below)
      el.tabIndex = 0;
      const name = el.querySelector(".model-cell b");
      if (name) el.setAttribute("aria-label", `Åpne svar: ${name.textContent}`);
    }
  });
}

// Enter / Space on the non-button click targets (leaderboard rows, live model cards). Delegated on #view,
// so it survives every re-render.
view.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const t = e.target;
  if (!(t instanceof Element) || !t.matches("tr[data-answer][tabindex], .mcard[data-live-answer][tabindex]")) return;
  e.preventDefault();
  t.click();
});

// A stable selector for a focusable element, so focus can be put back on its re-rendered twin.
function focusKey(el) {
  if (!el || el === document.body || !(el instanceof Element)) return null;
  for (const a of ["data-live-answer", "data-answer", "data-history", "data-tab", "data-nav", "data-regrade",
    "data-spec", "data-effort", "data-toggle", "data-all", "data-remove"]) {
    if (el.hasAttribute(a)) return `${el.tagName.toLowerCase()}[${a}="${CSS.escape(el.getAttribute(a))}"]`;
  }
  if (el.id) return "#" + CSS.escape(el.id);
  if (el.matches(".log summary")) return ".log summary";
  return null;
}
function refocus(saved) {
  if (!saved) return false;
  let el = saved.el && saved.el.isConnected ? saved.el : null;
  if (!el && saved.key) el = document.querySelector(saved.key);
  if (el && typeof el.focus === "function" && !el.closest("[inert]")) { el.focus({ preventScroll: true }); return document.activeElement === el; }
  return false;
}

// ── Drawer ───────────────────────────────────────────────────
let drawerReturnFocus = null;   // { el, key } — key finds the re-rendered node if el was replaced
// While the drawer is open the page behind it is inert (no focus, no clicks, hidden from AT).
function setBackgroundInert(on) {
  for (const el of [$(".topbar"), view]) { if (el) el.inert = on; }
}
function openDrawer(titleHTML, bodyHTML) {
  const wasOpen = $("#drawer").classList.contains("open");
  if (!wasOpen) { const a = document.activeElement; drawerReturnFocus = { el: a, key: focusKey(a) }; }
  $("#drawer-title").innerHTML = titleHTML;
  $("#drawer-body").innerHTML = bodyHTML;
  $("#drawer-body").scrollTop = 0;
  $("#drawer").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
  $("#drawer").inert = false;
  if (!wasOpen) {
    setBackgroundInert(true);
    sfx("open");
    const x = $(".drawer-head .icon-btn");
    if (x) x.focus({ preventScroll: true });
  }
}
function closeDrawer() {
  const wasOpen = $("#drawer").classList.contains("open");
  if (!wasOpen) return;   // route() calls this on every navigation — do nothing (and steal no focus) when closed
  $("#drawer").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
  $("#drawer").inert = true;   // closed drawer: out of the Tab order and the accessibility tree
  setBackgroundInert(false);
  sfx("close");
  const back = drawerReturnFocus;
  drawerReturnFocus = null;
  if (!refocus(back) && document.activeElement && document.activeElement.closest("#drawer")) document.activeElement.blur();
}
document.addEventListener("click", (e) => { if (e.target.closest("[data-close-drawer]")) closeDrawer(); });
// Escape closes the top-most layer: the modal if one is open, otherwise the drawer.
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { if ($("#modal")) closeModal(); else closeDrawer(); } });

async function openAnswer(run, label) {
  openDrawer(`<h2><span class="ident">${esc(label)}</span></h2>`, `<span class="spin"></span>`);
  try {
    const a = await api(`/api/runs/${enc(run)}/answers/${enc(label)}`);
    const m = a.meta || {};
    const chips = [
      [PROVIDER_NAME[a.provider] || a.provider],
      m.seconds != null && [`tid ${fmtSecs(m.seconds)}`],
      m.output_tokens != null && [`output ${fmtInt(m.output_tokens)}`],
      m.reasoning_tokens != null && [`reasoning ${fmtInt(m.reasoning_tokens)}`],
      m.total_tokens != null && [`total ${fmtInt(m.total_tokens)}`],
      m.web_searches != null && [`${m.web_searches} web-søk`],
      m.effort && [`effort ${m.effort}`],
      m.date && [String(m.date).slice(0, 16).replace("T", " ")],
    ].filter(Boolean);
    openDrawer(
      `<h2>${pdot(a.provider)} <span class="ident">${esc(a.model)}</span></h2><div class="chips">${chips.map(([t]) => `<span class="chip">${esc(t)}</span>`).join("")}</div>`,
      a.status === "ok" ? `<div class="md">${md(a.body)}</div>`
        : `<div class="note bad"><b>${a.status === "empty" ? "Tom respons" : "Feilet"}</b></div><pre class="mono" style="white-space:pre-wrap">${esc(a.error || "")}</pre>`,
    );
  } catch (e) {
    openDrawer(`<h2><span class="ident">${esc(label)}</span></h2>`, `<div class="note bad">${esc(e.message)}</div>`);
  }
}

async function openHistory(run, file, label) {
  openDrawer(`<h2><span class="ident">${esc(label)}</span></h2>`, `<span class="spin"></span>`);
  try {
    const g = await api(`/api/runs/${enc(run)}/grades/${enc(file)}`);
    openDrawer(`<h2>⚖ <span class="ident">${esc(label)}</span></h2><div class="muted" style="font-size:12px">${esc(file)}</div>`,
      (g.board && g.board.rows.length ? `<div class="card board-wrap" style="margin-bottom:20px">${boardHTML(g.board)}</div>` : "") +
      `<div class="md">${md(g.verdict)}</div>`);
  } catch (e) {
    openDrawer(`<h2><span class="ident">${esc(label)}</span></h2>`, `<div class="note bad">${esc(e.message)}</div>`);
  }
}

// ── Modal ────────────────────────────────────────────────────
let modalReturnFocus = null;
function modal(html) {
  const old = $("#modal");
  if (old) { const cb = old.onModalClose; old.onModalClose = null; old.remove(); if (cb) cb(); }
  else modalReturnFocus = document.activeElement;
  document.querySelectorAll(".modal-bg.closing").forEach((n) => n.remove());   // a dialog still powering off
  const bg = document.createElement("div");
  bg.className = "modal-bg";
  bg.id = "modal";
  bg.innerHTML = `<div class="card modal" role="dialog" aria-modal="true">${html}</div>`;
  const title = bg.querySelector("h3");
  if (title) { title.id = "modal-title"; bg.firstElementChild.setAttribute("aria-labelledby", "modal-title"); }
  const desc = bg.querySelector(".modal > .muted");
  if (desc) { desc.id = "modal-desc"; bg.firstElementChild.setAttribute("aria-describedby", "modal-desc"); }
  bg.addEventListener("click", (e) => { if (e.target === bg) closeModal(); });
  document.body.appendChild(bg);
  sfx("open");
  return bg;
}
function closeModal() {
  const m = $("#modal");
  if (!m) return;
  // CRT power-off: the dying dialog loses its id (so it no longer counts as "the modal"),
  // goes inert, collapses to a line and is removed.
  m.removeAttribute("id");
  m.querySelectorAll("[id]").forEach((el) => el.removeAttribute("id"));   // #rg-grader etc. belong to the next dialog
  m.inert = true;
  m.classList.add("closing");
  if (reduceMotion()) m.remove(); else setTimeout(() => m.remove(), 170);
  sfx("close");
  const cb = m.onModalClose;   // e.g. confirmModal resolving false on Escape / backdrop
  m.onModalClose = null;
  if (cb) cb();
  const back = modalReturnFocus;
  modalReturnFocus = null;
  if (back && back.isConnected && typeof back.focus === "function") back.focus({ preventScroll: true });
}
function focusables(box) {
  return [...box.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")]
    .filter((el) => !el.disabled && !el.hidden && el.getClientRects().length);
}
// Keep Tab / Shift+Tab inside the top-most layer: an open modal wins over an open drawer.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Tab") return;
  const box = $("#modal .modal") || $(".drawer.open .drawer-panel");
  if (!box) return;
  const f = focusables(box);
  if (!f.length) { e.preventDefault(); return; }
  const first = f[0], last = f[f.length - 1];
  if (!box.contains(document.activeElement)) { e.preventDefault(); (e.shiftKey ? last : first).focus(); }
  else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
});

function confirmModal(title, bodyHTML, okText) {
  return new Promise((resolve) => {
    const m = modal(`<h3>${esc(title)}</h3><div class="muted">${bodyHTML}</div>
      <div class="btns"><button class="btn" data-no>Avbryt</button><button class="btn primary" data-yes>${esc(okText)}</button></div>`);
    m.onModalClose = () => resolve(false);            // Avbryt, Escape, backdrop click, or replaced by another modal
    m.querySelector("[data-no]").onclick = () => closeModal();
    m.querySelector("[data-yes]").onclick = () => { resolve(true); closeModal(); };
    m.querySelector("[data-yes]").focus();
  });
}

function graderSelect(id, value) {
  const opts = S.config.graders.map((g) => `<option value="${esc(g)}" ${g === value ? "selected" : ""}>${esc(g)}${g === S.config.default_grader ? "  (standard)" : ""}</option>`).join("");
  const custom = !S.config.graders.includes(value);
  return `<select class="input" id="${id}">${opts}<option value="__custom" ${custom ? "selected" : ""}>Annen modell…</option></select>
    <input class="input" id="${id}-custom" aria-label="Egendefinert dommermodell" placeholder="provider/modell, f.eks. anthropic/claude-opus-5" style="margin-top:8px" ${custom ? `value="${esc(value)}"` : "hidden"}>`;
}
function readGrader(id) {
  const v = $("#" + id).value;
  return v === "__custom" ? $("#" + id + "-custom").value.trim() : v;
}
function wireGraderSelect(id, onChange) {
  $("#" + id).onchange = () => {
    $("#" + id + "-custom").hidden = $("#" + id).value !== "__custom";
    onChange && onChange();
  };
  $("#" + id + "-custom").oninput = () => onChange && onChange();
}

function openRegrade(run) {
  if (S.job && S.job.active) return toast("En run pågår allerede — vent til den er ferdig.", true);
  const m = modal(`<h3>⚖ Grade på nytt</h3>
    <p class="muted" style="margin-top:0">Hele bucketen grades blindt i ett kall. Den forrige dommen blir liggende i historikken.</p>
    <div class="field"><label for="rg-grader">Dommer</label>${graderSelect("rg-grader", S.config.default_grader)}</div>
    <div class="btns"><button class="btn" data-no>Avbryt</button><button class="btn primary" data-yes>Start grading</button></div>`);
  wireGraderSelect("rg-grader");
  $("#rg-grader").focus();
  m.querySelector("[data-no]").onclick = closeModal;
  m.querySelector("[data-yes]").onclick = async () => {
    try {
      const { id } = await api("/api/jobs", { method: "POST", body: JSON.stringify({ kind: "regrade", run, grader: readGrader("rg-grader") }) });
      closeModal();
      attachJob(id);
      sfx("chirp");
      location.hash = "#/live";
    } catch (e) { toast(e.message, true); }
  };
}

// ── New run ──────────────────────────────────────────────────
function initForm() {
  const c = S.config;
  S.form = {
    selected: new Set(c.contestants.map((m) => `${m.provider}/${m.model}`)),
    custom: [],
    effort: c.default_effort,
    web_search: false,
    refresh: false,
    tag: "",
    timeout: "",
    grade: true,
    grader: c.default_grader,
  };
}

async function renderNew(params) {
  if (!S.form) initForm();
  const from = params.get("from");
  if (from) {
    try {
      const d = await api(`/api/runs/${enc(from)}`);
      if (d.manifest && d.manifest.effort) {
        Object.assign(S.form, { effort: d.manifest.effort, web_search: !!d.manifest.web_search, tag: d.manifest.tag || "" });
        toast(`Innstillinger hentet fra ${from}`);
      }
    } catch (e) { toast(e.message, true); }
    history.replaceState(null, "", "#/new");
  }
  view.innerHTML = `
    <div class="page-head"><div><h1>Ny run</h1>
      <div class="sub">Velg modeller, effort og dommer. Svar som allerede finnes for samme config gjenbrukes — du betaler bare for det som mangler.</div></div></div>
    <div class="new-grid">
      <div id="form"></div>
      <div class="plan card pad" id="plan"></div>
    </div>`;
  S.plan = null;
  drawForm();
  drawPlan();
  refreshPlan();
}

function allModels() {
  const f = S.form;
  const list = S.config.contestants.map((m) => ({ ...m, spec: `${m.provider}/${m.model}`, custom: false }));
  for (const spec of f.custom) {
    const [provider, ...rest] = spec.split("/");
    list.push({ provider, model: rest.join("/"), spec, custom: true, knobs: {} });
  }
  return list;
}

function drawForm() {
  const f = S.form, c = S.config;
  // The form is re-rendered on every change: put focus back on the twin of the control that had it.
  const act = document.activeElement, host = $("#form");
  const keep = act && host && host.contains(act) ? { el: null, key: focusKey(act) } : null;
  const models = allModels();
  const groups = PROVIDER_ORDER.map((p) => [p, models.filter((m) => m.provider === p)]).filter(([, l]) => l.length);
  $("#form").innerHTML = `
    <section class="card form-section">
      <h3>Modeller</h3>
      <p class="hint">${f.selected.size} valgt. Hentet fra <code>CONTESTANTS</code> i haakonbench.py. Egendefinerte modeller legges til under.</p>
      <div class="providers">${groups.map(([p, list]) => `
        <div class="prov">
          <div class="prov-head">${pdot(p)} ${esc(PROVIDER_NAME[p])}
            ${c.providers[p] && !c.providers[p].key ? `<span class="nokey">mangler API-nøkkel</span>` : ""}
            <button class="link-btn" data-all="${p}">${list.every((m) => f.selected.has(m.spec)) ? "ingen" : "alle"}</button></div>
          ${list.map((m) => {
            const toggle = `<button type="button" class="model-toggle ${f.selected.has(m.spec) ? "on" : ""}" data-spec="${esc(m.spec)}" aria-pressed="${f.selected.has(m.spec)}">
              <span class="box" aria-hidden="true">${f.selected.has(m.spec) ? "✓" : ""}</span>
              <span class="name" title="${esc(m.model)}">${esc(m.model)}</span>
              ${m.knobs[f.effort] ? `<span class="knob" title="Effort-nivå sendt til denne modellen">${esc(m.knobs[f.effort])}</span>` : ""}
            </button>`;
            // Custom rows: the remove control is a sibling button (a button can't hold another button)
            return m.custom ? `<div class="model-row">${toggle}<button type="button" class="x" data-remove="${esc(m.spec)}" aria-label="Fjern" title="Fjern">✕</button></div>` : toggle;
          }).join("")}
        </div>`).join("")}
      </div>
      <div class="add-row">
        <input class="input mono" id="custom-model" aria-label="Egendefinert modell" placeholder="provider/modell — f.eks. openai/gpt-6-astra">
        <button class="btn" id="add-model">Legg til</button>
      </div>
    </section>

    <section class="card form-section">
      <h3>Effort</h3>
      <p class="hint">Oversettes til hver leverandørs eget nivå (se tallet ved hver modell). Setter også token-budsjettet.</p>
      <div class="seg">${c.tiers.map((t) => `<button type="button" data-effort="${t.name}" class="${f.effort === t.name ? "on" : ""}" aria-pressed="${f.effort === t.name}"><b>${t.name}</b><span>${fmtTok(t.max_tokens)} tokens</span></button>`).join("")}</div>
      <div style="margin-top:14px">
        <button type="button" class="toggle-row" data-toggle="web_search" role="switch" aria-checked="${!!f.web_search}"><span class="txt"><b>Web-søk</b><span>Slå på hver leverandørs server-side søk. Av = kun egen kunnskap.</span></span><span class="switch ${f.web_search ? "on" : ""}" aria-hidden="true"></span></button>
        <button type="button" class="toggle-row" data-toggle="refresh" role="switch" aria-checked="${!!f.refresh}"><span class="txt"><b>Ignorer cache</b><span>Kall alle valgte modeller på nytt, selv om de allerede har svart på denne configen.</span></span><span class="switch ${f.refresh ? "on" : ""}" aria-hidden="true"></span></button>
      </div>
      <div class="fields">
        <div class="field"><label for="tag">Tag (valgfri)</label><input class="input" id="tag" value="${esc(f.tag)}" placeholder="f.eks. variance-2 → egen bucket"></div>
        <div class="field"><label for="timeout">Timeout per modell (sekunder)</label><input class="input" id="timeout" type="number" min="0" value="${esc(f.timeout)}" placeholder="ingen grense"></div>
      </div>
    </section>

    <section class="card form-section">
      <h3>Jury</h3>
      <p class="hint">Dommeren leser alle svarene i bucketen anonymt (A, B, C…) og faktasjekker mot <code>wow_reference.yaml</code>.</p>
      <button type="button" class="toggle-row" data-toggle="grade" role="switch" aria-checked="${!!f.grade}" style="border-top:0"><span class="txt"><b>Grade etter run</b><span>Av = bare samle inn svar (billig tilkoblingstest).</span></span><span class="switch ${f.grade ? "on" : ""}" aria-hidden="true"></span></button>
      <div class="field" ${f.grade ? "" : "hidden"}><label for="grader">Dommer</label>${graderSelect("grader", f.grader)}</div>
    </section>`;

  const F = $("#form");
  F.querySelectorAll("[data-spec]").forEach((b) => (b.onclick = () => {
    f.selected.has(b.dataset.spec) ? f.selected.delete(b.dataset.spec) : f.selected.add(b.dataset.spec);
    drawForm(); refreshPlan();
  }));
  F.querySelectorAll("[data-remove]").forEach((b) => (b.onclick = () => {
    const spec = b.dataset.remove, had = document.activeElement === b;
    f.custom = f.custom.filter((s) => s !== spec);
    f.selected.delete(spec);
    drawForm(); refreshPlan();
    if (had) $("#custom-model").focus({ preventScroll: true });   // its row is gone: land on the add field
  }));
  F.querySelectorAll("[data-all]").forEach((b) => (b.onclick = () => {
    const list = allModels().filter((m) => m.provider === b.dataset.all);
    const all = list.every((m) => f.selected.has(m.spec));
    list.forEach((m) => (all ? f.selected.delete(m.spec) : f.selected.add(m.spec)));
    drawForm(); refreshPlan();
  }));
  F.querySelectorAll("[data-effort]").forEach((b) => (b.onclick = () => { f.effort = b.dataset.effort; drawForm(); refreshPlan(); }));
  F.querySelectorAll("[data-toggle]").forEach((row) => (row.onclick = () => { f[row.dataset.toggle] = !f[row.dataset.toggle]; drawForm(); refreshPlan(); }));
  $("#tag").oninput = (e) => { f.tag = e.target.value; refreshPlan(); };
  $("#timeout").oninput = (e) => { f.timeout = e.target.value; };
  const add = () => {
    const v = $("#custom-model").value.trim();
    const [p, ...rest] = v.split("/");
    if (!PROVIDER_ORDER.includes(p) || !rest.join("/")) return toast(`Skriv provider/modell — provider må være en av: ${PROVIDER_ORDER.join(", ")}`, true);
    if (!allModels().some((m) => m.spec === v)) f.custom.push(v);
    f.selected.add(v);
    drawForm(); refreshPlan();
  };
  $("#add-model").onclick = add;
  $("#custom-model").onkeydown = (e) => { if (e.key === "Enter") add(); };
  if (f.grade) wireGraderSelect("grader", () => { f.grader = readGrader("grader"); drawPlan(); });
  if (keep) refocus(keep);
}

function formPayload() {
  const f = S.form;
  return {
    models: [...f.selected],
    effort: f.effort, web_search: f.web_search, refresh: f.refresh, tag: f.tag,
    timeout: f.timeout, grade: f.grade, grader: f.grader,
  };
}

let planTimer = null;
function refreshPlan() {
  clearTimeout(planTimer);
  planTimer = setTimeout(async () => {
    const seq = ++S.planSeq;
    if (!S.form.selected.size) { S.plan = null; return drawPlan(); }
    try {
      const plan = await api("/api/plan", { method: "POST", body: JSON.stringify(formPayload()) });
      if (seq === S.planSeq) { S.plan = plan; drawPlan(); }
    } catch (e) { if (seq === S.planSeq) { S.plan = { error: e.message }; drawPlan(); } }
  }, 200);
}

function drawPlan() {
  const el = $("#plan");
  if (!el) return;
  const f = S.form, p = S.plan;
  if (!f.selected.size) { el.innerHTML = `<h3 style="margin:0">Plan</h3><p class="muted">Velg minst én modell.</p>`; return; }
  if (!p) { el.innerHTML = `<span class="spin"></span>`; return; }
  if (p.error) { el.innerHTML = `<h3 style="margin:0">Plan</h3><div class="note bad">${esc(p.error)}</div>`; return; }
  const busy = S.job && S.job.active;
  const nothing = !p.to_call.length && !f.grade;
  el.innerHTML = `
    <div class="plan-head"><h3 style="margin:0">Plan</h3><span class="chip ${p.exists ? "" : "gold"}">${p.exists ? "eksisterende bucket" : "ny bucket"}</span></div>
    <div class="plan-bucket">${esc(p.bucket)}</div>
    ${p.conflicts.length ? `<div class="note bad">${p.conflicts.map(esc).join("<br>")}</div>` : ""}
    <div class="plan-stats">
      <div class="stat"><b style="color:var(--run)">${p.to_call.length}</b><span>API-kall</span></div>
      <div class="stat"><b>${p.reused.length}</b><span>gjenbrukes</span></div>
      <div class="stat"><b>${f.grade ? p.grade_count : "–"}</b><span>grades</span></div>
    </div>
    <div class="plan-list">
      ${p.to_call.length ? `<h4>Kalles nå</h4>${p.to_call.map((m) => `<div class="plan-item">${pdot(m.provider)}<span class="name">${esc(m.model)}</span><span class="side">${esc(m.knob ?? "default")} · ${fmtTok(m.max_tokens)}</span></div>`).join("")}` : ""}
      ${p.reused.length ? `<h4>Gjenbrukes (allerede besvart)</h4>${p.reused.map((m) => `<div class="plan-item">${pdot(m.provider)}<span class="name">${esc(m.model)}</span><span class="side">${esc(m.date || "")}</span></div>`).join("")}` : ""}
      ${f.grade && p.others.length ? `<h4>Også i bucketen (grades med)</h4>${p.others.map((l) => `<div class="plan-item">${pdot(l.split("__")[0])}<span class="name">${esc(l.split("__")[1] || l)}</span></div>`).join("")}` : ""}
    </div>
    ${f.grade ? `<p class="muted" style="font-size:12px;margin:0 0 12px">Dommer: <b style="color:var(--text)">${esc(f.grader)}</b> — ett kall over hele bucketen.</p>` : ""}
    <button class="btn primary big" id="start" ${busy || nothing || p.conflicts.length ? "disabled" : ""}>
      ${busy ? "En run pågår allerede" : p.to_call.length ? `▶ Start run · ${p.to_call.length} kall` : f.grade ? "⚖ Bare grade bucketen" : "Ingenting å gjøre"}
    </button>`;
  const btn = $("#start");
  if (btn) btn.onclick = startRun;
}

async function startRun() {
  const f = S.form, p = S.plan;
  if (f.grade) f.grader = readGrader("grader");
  const ok = await confirmModal(
    p.to_call.length ? "Start run?" : "Grade bucketen?",
    `${p.to_call.length ? `<b style="color:var(--text)">${p.to_call.length} betalte API-kall</b> (effort ${esc(f.effort)}, web-søk ${f.web_search ? "på" : "av"})` : "Ingen modeller trenger å kalles"}
     ${f.grade ? `, deretter grading av ${p.grade_count} svar med <b style="color:var(--text)">${esc(f.grader)}</b>.` : ", uten grading."}
     ${S.config.demo ? "<br><br>DEMO: ingenting blir faktisk kalt." : ""}`,
    p.to_call.length ? "Start" : "Grade",
  );
  if (!ok) return;
  try {
    const { id } = await api("/api/jobs", { method: "POST", body: JSON.stringify(formPayload()) });
    attachJob(id);
    sfx("chirp");
    location.hash = "#/live";
  } catch (e) { toast(e.message, true); }
}

// ── Live job ─────────────────────────────────────────────────
function attachJob(id) {
  if (S.es) S.es.close();
  const es = new EventSource(`/api/jobs/${id}/events`);
  S.es = es;
  es.onmessage = (ev) => {
    const prev = S.job && S.job.id === id ? S.job : null;
    const wasActive = !!(prev && prev.active);
    S.job = JSON.parse(ev.data);
    if (prev) jobSfx(prev, S.job);
    S.skew = Date.now() / 1000 - S.job.now;
    updateNav();
    if (currentSection() === "live") drawLive();
    if (!S.job.active) {
      es.close();
      if (S.es === es) S.es = null;
      if (wasActive) {
        const msg = { done: "Ferdig! 🎣", error: "Run feilet", cancelled: "Run avbrutt" }[S.job.status] || "Ferdig";
        toast(msg, S.job.status === "error");
      }
    }
  };
  es.onerror = () => { if (S.job && !S.job.active) es.close(); };
}

// Sounds on job state transitions only (never on every SSE tick).
function jobSfx(a, b) {
  if (a.active && !b.active) {
    if (b.status === "done") sfx("done");
    else if (b.status === "error") sfx("error");
    return;
  }
  const key = (m) => m.label || `${m.provider}/${m.model}`;
  const was = new Map((a.models || []).map((m) => [key(m), m.state]));
  const moved = (b.models || []).filter((m) => was.has(key(m)) && was.get(key(m)) !== m.state);
  if (moved.some((m) => m.state === "failed" || m.state === "empty")) sfx("blip");
  else if (moved.some((m) => m.state === "done")) sfx("tick");
}

const currentSection = () => ((location.hash.slice(2) || "").split(/[/?]/)[0] || "runs");

function jobProgress(j) {
  const called = j.models.filter((m) => m.state !== "cached");
  const finished = called.filter((m) => ["done", "failed", "empty", "cancelled"].includes(m.state));
  return { called, finished };
}

function updateNav() {
  const j = S.job;
  const active = !!(j && j.active);
  $("#live-dot").hidden = !active;
  let txt = "";
  if (active) {
    if (j.status === "grading") txt = "grader";
    else { const { called, finished } = jobProgress(j); txt = called.length ? `${finished.length}/${called.length}` : ""; }
  }
  $("#live-count").textContent = txt;
  if ($("#start")) drawPlan();
}

function renderLive() {
  if (!S.job) {
    view.innerHTML = `<div class="card empty"><h3>Ingen run pågår</h3><p>Start en ny run, så kan du følge den her mens svarene kommer inn.</p><a class="btn primary" href="#/new">Ny run</a></div>`;
    return;
  }
  drawLive();
}

const STATUS_TXT = { starting: "Starter…", running: "Kjører", grading: "Grader", done: "Ferdig", error: "Feilet", cancelled: "Avbrutt" };
const STATE_TXT = { queued: "I kø", running: "Kjører", done: "Ferdig", failed: "Feilet", empty: "Tom", cached: "Gjenbrukt", cancelled: "Avbrutt" };

function drawLive() {
  const j = S.job;
  if (!j) return renderLive();
  const { called, finished } = jobProgress(j);
  const pct = j.kind === "regrade" ? (j.status === "done" ? 100 : 50)
    : called.length ? (finished.length / called.length) * 100 * (j.params.grade ? 0.9 : 1) + (j.grading && j.grading.state === "done" ? 10 : 0) : (j.active ? 50 : 100);
  const order = { running: 0, queued: 1, done: 2, empty: 3, failed: 3, cancelled: 4, cached: 5 };
  const models = [...j.models].sort((a, b) => (order[a.state] ?? 9) - (order[b.state] ?? 9));
  const act = document.activeElement;
  const keepFocus = act && view.contains(act) ? { el: null, key: focusKey(act) } : null;
  const logNearBottom = (() => { const pre = $(".log pre"); return !pre || pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 20; })();

  view.innerHTML = `
    <div class="card live-head">
      <div>
        <div class="live-status ${j.status}"><span class="ind" style="--ph:${phase(1400)}"></span>${STATUS_TXT[j.status] || j.status}${j.kind === "regrade" ? " · regrade" : ""}</div>
        <div class="live-meta">${j.bucket ? `<a href="#/run/${enc(j.bucket)}" class="mono">${esc(j.bucket)}</a>` : "…"}
          ${j.kind === "run" ? ` · effort ${esc(j.params.effort)} · web-søk ${j.params.web_search ? "på" : "av"}${j.params.timeout ? ` · timeout ${j.params.timeout}s` : ""}` : ""}</div>
      </div>
      <div class="right">
        ${j.kind === "run" && called.length ? `<span class="muted">${finished.length} / ${called.length} ferdig</span>` : ""}
        <span class="elapsed tick" data-since="${j.started}" ${j.finished ? `data-until="${j.finished}"` : ""}>${fmtDur((j.finished || serverNow()) - j.started)}</span>
        ${j.active ? `<button class="btn danger" id="cancel" ${j.cancel_requested ? "disabled" : ""}>${j.cancel_requested ? "Avbryter…" : "■ Avbryt"}</button>` : ""}
      </div>
      <div class="progress ${j.active ? "active" : ""}" style="--ph:${phase(2000)}"><i style="width:${Math.min(100, pct)}%"></i></div>
    </div>

    ${j.error ? `<div class="note bad" style="margin:0 0 16px"><b>Feil:</b> ${esc(j.error)}</div>` : ""}

    ${models.length ? `<div class="live-grid">${models.map((m) => modelCard(m, j)).join("")}</div>` : ""}

    ${gradingCard(j)}

    <details class="log" ${S.logOpen ? "open" : ""}><summary>Logg (${j.logs.length})</summary>
      <pre>${esc(j.logs.map((l) => `${new Date(l.t * 1000).toLocaleTimeString("nb-NO")}  ${l.msg}`).join("\n")) || "—"}</pre></details>`;

  // Gauge: the bar is a fresh node every event, so glide it from where the last one stood.
  const bar = $(".progress > i"), target = Math.min(100, pct);
  if (bar && S.gauge && S.gauge.id === j.id && S.gauge.pct !== target && !reduceMotion()) {
    bar.style.width = S.gauge.pct + "%";
    void bar.offsetWidth;
    bar.style.width = target + "%";
  }
  S.gauge = { id: j.id, pct: target };
  const pre = $(".log pre");
  if (pre && logNearBottom) pre.scrollTop = pre.scrollHeight;
  $(".log").addEventListener("toggle", (e) => (S.logOpen = e.target.open));
  const c = $("#cancel");
  if (c) c.onclick = async () => {
    const ok = await confirmModal("Avbryte run?", "Modeller som allerede har svart er lagret. Resten avbrytes (og kalles på nytt neste gang). Grading hoppes over.", "Avbryt run");
    if (ok) api(`/api/jobs/${j.id}/cancel`, { method: "POST" }).catch((e) => toast(e.message, true));
  };
  view.querySelectorAll("[data-live-answer]").forEach((el) => (el.onclick = () => openAnswer(j.bucket, el.dataset.liveAnswer)));
  view.querySelectorAll("[data-regrade]").forEach((el) => (el.onclick = () => openRegrade(j.bucket)));
  wireAnswerClicks(view, j.bucket);
  if (keepFocus) refocus(keepFocus);
}

function modelCard(m, j) {
  const meta = m.meta || {};
  const clickable = ["done", "cached"].includes(m.state);
  let body = "";
  if (m.state === "running") {
    body = `<div class="big tick" data-since="${m.started}">${fmtDur(serverNow() - m.started)}</div><div class="small">effort: ${esc(m.knob ?? "default")}</div>`;
  } else if (m.state === "queued") {
    body = `<div class="big faint">—</div><div class="small">venter</div>`;
  } else if (m.state === "done") {
    body = `<div class="big">${fmtSecs(m.secs)}</div><div class="small">${fmtTok(meta.output_tokens)} ut · ${fmtTok(meta.total_tokens)} totalt${meta.web_searches != null ? ` · ${meta.web_searches} søk` : ""} · ${fmtInt(m.chars)} tegn</div>`;
  } else if (m.state === "failed") {
    body = `<div class="big">${fmtSecs(m.secs)}</div><div class="err" title="${esc(m.error)}">${esc(m.error)}</div>`;
  } else if (m.state === "empty") {
    body = `<div class="big">${fmtSecs(m.secs)}</div><div class="err">Tom respons — brukte trolig opp hele budsjettet på resonnering.</div>`;
  } else if (m.state === "cached") {
    body = `<div class="small">Svarte allerede på denne configen${meta.date ? ` (${esc(String(meta.date).slice(0, 10))})` : ""}. ${fmtSecs(meta.seconds)} · ${fmtTok(meta.total_tokens)} tok</div>`;
  } else if (m.state === "cancelled") {
    body = `<div class="small">Avbrutt — ingenting lagret.</div>`;
  }
  return `<div class="card mcard ${m.state} ${clickable ? "clickable" : ""}" ${clickable ? `data-live-answer="${esc(m.label)}" tabindex="0" role="button"` : ""}${m.state === "running" ? ` style="--ph:${phase(2400, m.label || m.model)}"` : ""}>
    <div class="top">${pdot(m.provider)}<b title="${esc(m.model)}">${esc(m.model)}</b>
      <span class="status ${m.state}">${m.state === "running" ? `<span class="spin" style="width:9px;height:9px;border-width:1.5px;vertical-align:-1px;--ph:${phase(1400)}"></span> ` : ""}${STATE_TXT[m.state] || m.state}</span></div>
    ${body}
  </div>`;
}

function gradingCard(j) {
  const g = j.grading;
  if (j.kind === "run" && !j.params.grade) {
    return `<div class="card grading-card"><div class="row"><h3>⚖ Grading</h3><span class="status skipped">Hoppet over</span></div></div>`;
  }
  const grader = (g && g.grader) || j.params.grader;
  let right = "", body = "";
  if (!g) {
    right = `<span class="status queued">Venter</span>`;
    body = j.active ? `<p class="muted" style="margin:10px 0 0">Starter når alle modellene har svart. Hele bucketen grades blindt i ett kall.</p>` : "";
  } else if (g.state === "running") {
    right = `<span class="status running"><span class="spin" style="width:9px;height:9px;border-width:1.5px;vertical-align:-1px;--ph:${phase(1400)}"></span> Grader ${g.count} svar</span>
      <span class="elapsed tick" style="font-size:15px" data-since="${g.started}">${fmtDur(serverNow() - g.started)}</span>`;
    body = `<p class="muted" style="margin:10px 0 0">Dommeren leser alle svarene og faktasjekker mot referansedataene. Dette tar gjerne 1–4 minutter.</p>`;
  } else if (g.state === "done") {
    right = `<span class="status done">Ferdig</span><span class="muted">${fmtDur(g.finished - g.started)}</span>
      <a class="btn" style="margin-left:auto" href="#/run/${enc(j.bucket)}">Åpne run →</a>`;
    body = j.board && j.board.rows.length ? `<div class="board-wrap" style="margin-top:14px">${boardHTML(j.board)}</div>` : "";
  } else if (g.state === "failed") {
    right = `<span class="status failed">Feilet</span><button class="btn" style="margin-left:auto" data-regrade>Grade på nytt</button>`;
    body = `<div class="err mono" style="margin-top:10px;color:var(--bad)">${esc(g.error)}</div>`;
  } else {
    right = `<span class="status ${esc(g.state)}">${g.state === "skipped" ? "Hoppet over" : "Avbrutt"}</span>`;
    body = g.reason ? `<p class="muted" style="margin:10px 0 0">${esc(g.reason)}</p>` : "";
  }
  return `<div class="card grading-card"><div class="row"><h3>⚖ Grading</h3><span class="muted mono" style="font-size:12px">${esc(grader)}</span>${right}</div>${body}</div>`;
}

// Tick every running timer once a second without re-rendering.
setInterval(() => {
  const now = serverNow();
  document.querySelectorAll(".tick").forEach((el) => {
    const until = el.dataset.until ? Number(el.dataset.until) : now;
    el.textContent = fmtDur(until - Number(el.dataset.since));
  });
}, 1000);

// ── Boot ─────────────────────────────────────────────────────
(async function boot() {
  loading();
  try {
    S.config = await api("/api/config");
  } catch (e) {
    view.innerHTML = `<div class="empty fail"><h3>Får ikke kontakt med serveren</h3><p>${esc(e.message)}</p><p>Kjør <code>python dashboard.py</code>.</p></div>`;
    return;
  }
  $("#demo-badge").hidden = !S.config.demo;
  $("#prompt-chip").textContent = "prompt p" + S.config.prompt_sha;
  try {
    const job = await api("/api/jobs/current");
    if (job) {
      S.job = job;
      S.skew = Date.now() / 1000 - job.now;
      if (job.active) attachJob(job.id);
      updateNav();
    }
  } catch { /* no job yet */ }
  route();
})();
