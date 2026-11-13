// The page's behavior. Plain JS, no build step (spec/02-ui.md).
// Text from the server is always set with textContent, never as HTML.

const PAGE_HEADER = { "X-Harness-Page": "1" }; // the server refuses actions without it (D-20)
// Owner unlock (D-190): on a hosted copy, the owner's passphrase rides on every request from
// this tab, so its runs use the Claude key. Kept for this tab only; Lock forgets it.
const OWNER_STORE = "harness-owner";
const OWNER_PASS = (() => {
  try {
    return sessionStorage.getItem(OWNER_STORE) || "";
  } catch {
    return "";
  }
})();
if (OWNER_PASS) PAGE_HEADER["X-Harness-Owner"] = OWNER_PASS;
const ICONS = { waiting: "○", passed: "✓", failed: "✗", skipped: "–" };

const $ = (id) => document.getElementById(id);
// The guided tour (S13): /?tour replays recorded runs and sends nothing; /?tour=record also
// records your voice. tour.js plays it through this file's own onEvent() (D-171).
let TOUR = new URLSearchParams(location.search).get("tour") !== null; // the sidebar button turns it on
const TOUR_RECORD = new URLSearchParams(location.search).get("tour") === "record";
// Bring a new line into view. In the tour the player scrolls instead: it centres whatever
// the spotlight frames, so the page never jumps to its bottom edge (your review).
const reveal = (node, how) => TOUR || node.scrollIntoView(how);

// ── Health: smoke row + what the Agent view can offer ───────────────────────
let health = null;
// The Evals and Golden Dataset pages' state; declared up here because showView() may
// open either page before the rest of the file has run.
const evals = { index: null, result: null, live: null, running: false, suite: [] };
let goldenFilter = "all"; // Golden Dataset: all, single, multi or core

async function loadHealth() {
  const server = $("smoke-server");
  const key = $("smoke-key");
  try {
    health = await (await fetch("/api/health", { headers: OWNER_PASS ? { "X-Harness-Owner": OWNER_PASS } : {} })).json();
    server.textContent = "Server up ✓";
    server.className = "pill ok";
    // A missing key is fine: everything offline works without it (S00-AC12).
    key.textContent = health.key === "present" ? "Key present ✓" : "Key skipped";
    key.className = health.key === "present" ? "pill ok" : "pill skip";
    $("version").textContent = `v${health.version}`;
    if (health.mode === "public") showPublicMode();
    if (health.mode === "owner") showOwnerMode();
  } catch {
    server.textContent = "Server down";
    server.className = "pill bad";
  }
  setUpAgent();
  dispatchEvent(new Event("harness-ready")); // the tour starts once the page knows its workspace
}

// ── Views: Agent, Memory, Evals and Checks, chosen by the URL hash ─────────────────────────
// Public tour mode (S14, D-189): a hosted, keyless copy that only plays the tour. The server
// refuses every change; the page hides what would need one, and says how to run it for real.
function showPublicMode() {
  document.body.classList.add("public-mode");
  const note = $("public-note");
  note.append(el("span", "public-text", "A read-only replay of a real agent run. Clone the repository to run it live with your own model key."));
  if (health.repository) {
    const link = Object.assign(document.createElement("a"), { href: health.repository, className: "public-code", target: "_blank", rel: "noopener" });
    link.append(fromTemplate("tpl-github"), "View the Code");
    note.append(link);
  }
  note.hidden = false;
  // The tour sets whose view and which person; a visitor can see them but not change them.
  for (const id of ["profiles", "people", "work"]) $(id).inert = true;
  // The owner's way in: only at ?owner, or after a passphrase that didn't work.
  if (new URLSearchParams(location.search).has("owner") || health.owner_denied) note.append(ownerForm(health.owner_denied));
  showView();
}

// The passphrase box. Sent once to check it, then kept for this tab (D-190).
function ownerForm(denied) {
  if (denied) forgetOwner();
  const form = el("form", "owner-form");
  const input = Object.assign(document.createElement("input"), { type: "password", placeholder: "Owner passphrase", autocomplete: "off", required: true });
  input.setAttribute("aria-label", "Owner passphrase");
  const unlock = Object.assign(document.createElement("button"), { type: "submit", textContent: "Unlock" });
  form.append(input, unlock);
  if (denied) form.append(el("p", "owner-error", "That passphrase didn't work."));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      sessionStorage.setItem(OWNER_STORE, input.value);
    } catch {
      return;
    }
    location.replace(location.pathname); // reload without ?owner: health now answers as the owner
  });
  return form;
}

function forgetOwner() {
  try {
    sessionStorage.removeItem(OWNER_STORE);
  } catch {
    // Nothing kept.
  }
}

// An owner session on a hosted copy: the full agent view, runs on Claude, nothing else opened.
function showOwnerMode() {
  document.body.classList.add("public-mode", "owner-mode");
  const note = $("public-note");
  note.append("Owner session: live runs use your Claude key and cost real money. ");
  const lock = Object.assign(document.createElement("button"), { type: "button", className: "owner-lock", textContent: "Lock" });
  lock.addEventListener("click", () => {
    forgetOwner();
    location.replace(location.pathname);
  });
  note.append(lock);
  note.hidden = false;
  showView();
}

function showView() {
  const views = { "#checks": "checks", "#memory": "memory", "#online": "online", "#evals": "evals", "#golden": "golden" };
  const hosted = health?.mode === "public" || health?.mode === "owner";
  const view = hosted ? "agent" : views[location.hash] ?? "agent";
  for (const name of ["agent", "memory", "online", "evals", "golden", "checks"]) {
    $(`view-${name}`).hidden = name !== view;
  }
  if (view === "memory") loadFacts();
  if (view === "online") loadOnline();
  if (view === "evals") loadEvals();
  if (view === "golden") loadGolden();
  for (const link of document.querySelectorAll(".nav-item")) {
    if (link.dataset.view === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

// NDJSON: one JSON event per line, arriving while the work goes on.
async function* readLines(response) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) if (line.trim()) yield JSON.parse(line);
  }
}

// ── Checks panel (S00) ──────────────────────────────────────────────────────

// "tests/unit/test_cli.py::test_s00_ac2_version_flag" → { id: "S00-AC2", name: "Version flag" }
function describe(nodeid) {
  const [file, test = nodeid] = nodeid.split("::");
  const match = test.match(/^test_(s\d+)_(ac\d+)_(.+)$/i);
  const words = (match ? match[3] : test.replace(/^test_/, "")).replaceAll("_", " ");
  return {
    id: match ? `${match[1]}-${match[2]}`.toUpperCase() : "",
    name: words.charAt(0).toUpperCase() + words.slice(1),
    file,
  };
}

function makeRow(nodeid) {
  const { id, name, file } = describe(nodeid);
  const row = document.createElement("li");
  row.className = "row waiting";

  const icon = document.createElement("span");
  icon.className = "icon";
  icon.textContent = ICONS.waiting;

  const checkId = document.createElement("span");
  checkId.className = "check-id";
  checkId.textContent = id;

  const label = document.createElement("span");
  label.className = "name";
  label.textContent = name;
  const where = document.createElement("span");
  where.className = "file";
  where.textContent = file;
  label.append(where);

  const time = document.createElement("span");
  time.className = "time";

  row.append(icon, checkId, label, time);
  return row;
}

function markRow(row, outcome, seconds) {
  row.className = `row ${outcome} done`;
  row.querySelector(".icon").textContent = ICONS[outcome] ?? "?";
  row.querySelector(".time").textContent = `${seconds.toFixed(2)} s`;
}

async function runChecks() {
  const button = $("run-checks");
  const summary = $("summary");
  const progress = $("progress");
  const rows = $("rows");
  const byTest = new Map();
  const counts = { passed: 0, failed: 0, skipped: 0 };
  const started = performance.now();

  button.disabled = true;
  rows.replaceChildren();
  summary.className = "summary";
  summary.textContent = "Running checks…";
  progress.value = 0;

  try {
    const response = await fetch("/api/checks", { method: "POST", headers: PAGE_HEADER });
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);

    for await (const event of readLines(response)) {
      if (event.type === "collected") {
        progress.max = Math.max(event.tests.length, 1);
        for (const nodeid of event.tests) {
          const row = makeRow(nodeid);
          byTest.set(nodeid, row);
          rows.append(row);
        }
      } else if (event.type === "result") {
        counts[event.outcome] = (counts[event.outcome] ?? 0) + 1;
        const row = byTest.get(event.test);
        if (row) markRow(row, event.outcome, event.seconds);
        progress.value += 1;
      } else if (event.type === "error") {
        throw new Error(event.message);
      } else if (event.type === "exit") {
        const seconds = ((performance.now() - started) / 1000).toFixed(1);
        const parts = [`${counts.passed} passed`, `${counts.failed} failed`];
        if (counts.skipped) parts.push(`${counts.skipped} skipped`);
        const ok = event.code === 0;
        if (!ok && counts.failed === 0) parts.push(`test run exited with code ${event.code}`);
        summary.textContent = `${ok ? "✓" : "✗"} ${parts.join(" · ")} · ${seconds} s`;
        summary.className = `summary ${ok ? "pass" : "fail"}`;
      }
    }
  } catch (error) {
    summary.textContent = `✗ ${error.message}`;
    summary.className = "summary fail";
  } finally {
    button.disabled = false;
  }
}

// ── Agent view (S01): calm chat on top, every harness step one line you can open ──
const REASONS = {
  answered: "answered",
  step_limit: "hit the step limit",
  cost_limit: "hit the cost limit",
  time_limit: "hit the time limit",
  outside_scope: "outside this assistant's job",
  output_limit: "the answer was cut off at the output limit",
};
let agentName = "agent";

function setUpAgent() {
  const ws = health?.workspace;
  if (!ws) {
    $("send").disabled = true;
    return;
  }
  // Every name and example comes from the workspace: the page knows no agent (D-40).
  agentName = ws.title;
  setUpOrg(ws);
  $("empty-title").textContent = `What should the ${ws.title} do?`;
  $("empty-hint").textContent = "";
  setUpProfilePicker(ws);
  for (const tag of document.querySelectorAll(".synthetic-tag")) tag.hidden = !ws.synthetic_data;
  refreshWork();
  $("examples").replaceChildren(
    ...(ws.examples ?? []).map((text) => {
      const chip = el("button", "example", text);
      chip.type = "button";
      chip.addEventListener("click", () => {
        $("task").value = text;
        $("task").focus();
      });
      return chip;
    }),
  );
  setUpModelPicker();
  setUpEffortPicker();
  setUpPeople();
  setUpPane();
  // Every run calls a real model, so no key means nothing can run: say so only then.
  const hasKey = health.key === "present";
  $("send").disabled = !hasKey;
  $("model").disabled = !hasKey;
  $("effort").disabled = !hasKey;
  $("composer-alert").textContent = hasKey ? "" : "No Gemini key: add it to .env and restart.";
}

// The model menu offers only models with a price (the server checks again, D-31).
// Your last pick is remembered in this browser; if it's gone, the configured default wins.
const MODEL_KEY = "live-model";

// "gemini-3.5-flash-lite" → "Gemini 3.5 Flash-Lite"
function modelLabel(id) {
  // claude-sonnet-5-5 → "Claude Sonnet 5.5" (D-102)
  const claude = id.match(/^claude-([a-z]+)-(\d+)-(\d+)$/);
  if (claude) return `Claude ${claude[1].charAt(0).toUpperCase() + claude[1].slice(1)} ${claude[2]}.${claude[3]}`;
  const [version, ...words] = id.replace(/^gemini-/, "").split("-");
  const tier = words.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join("-");
  return `Gemini ${version} ${tier}`.trim();
}

// Profiles (D-39): whose view the agent works for. Same menu style as the model menu.
// Switching starts a fresh thread, because each profile gets different context.
const profileKey = (ws) => `profile:${ws.name}`;

// Top of the sidebar: the company (name and logo), then a menu of its agents. All from the
// workspace; one agent per workspace for now, so the menu has one entry (D-86).
function setUpOrg(ws) {
  $("org-name").textContent = ws.owner || ws.title;
  const logo = $("org-logo");
  logo.hidden = !ws.logo;
  if (ws.logo) logo.src = "/api/workspace/logo";
  const pick = $("agent-pick");
  for (const old of pick.querySelectorAll("option")) old.remove();
  for (const agent of ws.agents ?? []) {
    const option = el("option");
    option.value = agent.id;
    option.append(el("span", null, agent.name));
    pick.append(option);
  }
  pick.value = ws.name;
  const about = (ws.agents ?? []).find((a) => a.id === ws.name)?.description ?? "";
  $("agent-desc").textContent = about;
  $("agent-desc").hidden = !about;
}

function setUpProfilePicker(ws) {
  const pick = $("profile"); // stays as the one source of the value; the cards below drive it
  const box = $("profile-box");
  for (const old of pick.querySelectorAll("option")) old.remove();
  for (const old of box.querySelectorAll(".profile-switch")) old.remove();
  box.hidden = !ws.profiles?.length;
  $("profiles").hidden = box.hidden; // the heading goes with the cards
  if (box.hidden) return;
  for (const profile of ws.profiles) {
    const option = el("option", null, profile.label);
    option.value = profile.id;
    pick.append(option);
  }
  let saved = null;
  try {
    saved = localStorage.getItem(profileKey(ws));
  } catch {
    // Storage blocked: start with the first profile.
  }
  pick.value = ws.profiles.some((p) => p.id === saved) ? saved : ws.profiles[0].id;

  // Cards: real radio buttons (arrow keys and screen readers work), a thumb that glides.
  const group = el("div", "profile-switch");
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-label", "Whose view the agent works for");
  group.style.setProperty("--n", ws.profiles.length);
  ws.profiles.forEach((profile, i) => {
    const card = el("label", "pf-card");
    const input = el("input");
    input.type = "radio";
    input.name = "profile-card";
    input.value = profile.id;
    input.checked = profile.id === pick.value;
    input.addEventListener("change", () => {
      pick.value = profile.id;
      group.style.setProperty("--i", i);
      pick.dispatchEvent(new Event("change"));
    });
    const avatar = el("span", "pf-avatar", profile.label.charAt(0).toUpperCase());
    const text = el("span", "pf-text");
    text.append(el("span", "pf-name", profile.label), el("span", "pf-sub", "Working as"));
    card.append(input, avatar, text, el("span", "pf-live"));
    group.append(card);
    if (input.checked) group.style.setProperty("--i", i);
  });
  group.prepend(el("span", "pf-thumb"));
  box.append(group);
}

function currentProfile() {
  return $("profile-box").hidden ? null : $("profile").value;
}

// ── Acting As (S12 Part B, D-137): who is answering approvals. Role-played; the server checks. ──
const people = () => health?.workspace?.people ?? [];
const roleOf = (p) => (p ? `${p.name} (${p.role})` : "");
// The profile's person, unless a hand-off put someone else in (the CFO on a CFO card). In memory
// only: it ends with the approval and with a profile change.
let handoff = null;
function currentPerson() {
  const all = people();
  const mine = all.find((p) => p.role === labelFor(currentProfile()));
  return all.find((p) => p.id === handoff) ?? mine ?? all[0] ?? null;
}
const pendingCards = new Set(); // each waiting approval card's refresh, so a switch updates them all

function setPerson(id) {
  const p = people().find((x) => x.id === id);
  handoff = p && p.role !== labelFor(currentProfile()) ? id : null;
  renderPeople();
  for (const refresh of pendingCards) refresh();
}

function renderPeople() {
  const all = people();
  $("people").hidden = all.length === 0;
  if (!all.length) return;
  const me = currentPerson();
  // Follows the profile: only its role's people. A hand-off to someone else (the CFO) adds them while they act.
  const mine = all.filter((p) => p.role === labelFor(currentProfile()));
  const shown = me && !mine.includes(me) ? [...mine, me] : mine.length ? mine : all;
  $("people-list").replaceChildren(
    ...shown.map((p) => {
      const b = el("button", `person${p.id === me?.id ? " is-me" : ""}`);
      b.type = "button";
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", String(p.id === me?.id));
      b.append(el("span", "person-avatar", p.name.charAt(0)), el("span", "person-text"));
      b.lastChild.append(el("strong", null, p.name), el("span", null, p.role));
      b.addEventListener("click", () => setPerson(p.id));
      return b;
    }),
  );
}

function setUpPeople() {
  renderPeople();
  $("profile").addEventListener("change", () => setPerson(null)); // a new profile is a new person
}

const labelFor = (id) => health?.workspace?.profiles?.find((p) => p.id === id)?.label ?? id;

// ── Your work (S07): this profile's conversations, newest first, named by topic ──
let currentSession = null; // the conversation the next task continues; null: a new one
let workItems = [];

const ago = (seconds) => {
  const s = Math.max(0, Date.now() / 1000 - seconds);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
};
const withProfile = () => (currentProfile() ? `?profile=${encodeURIComponent(currentProfile())}` : "");

async function refreshWork() {
  if (TOUR) return renderWork(); // the tour's own chat only
  try {
    const response = await fetch(`/api/sessions${withProfile()}`);
    if (!response.ok) return;
    workItems = (await response.json()).sessions;
  } catch {
    return; // the list is a convenience; the page works without it
  }
  renderWork();
}

function renderWork() {
  $("work").hidden = false;
  $("work-empty").hidden = workItems.length > 0;
  const list = $("work-list");
  list.replaceChildren(
    ...workItems.map((item) => {
      const li = el("li", `work-item${item.id === currentSession ? " active" : ""}`);
      li.dataset.id = item.id;
      const open = el("button", "work-open");
      open.type = "button";
      open.setAttribute("aria-current", item.id === currentSession ? "true" : "false");
      open.append(el("span", "work-title", item.title), el("span", "work-meta", `${plural(item.turns, "task")} · ${ago(item.updated)}`));
      open.addEventListener("click", () => openSession(item.id));
      const del = el("button", "work-delete", "×");
      del.type = "button";
      del.setAttribute("aria-label", `Delete ${item.title}`);
      del.addEventListener("click", () => {
        // Two clicks, no pop-up: the first asks, the second deletes.
        if (!del.classList.contains("sure")) {
          del.classList.add("sure");
          del.textContent = "Delete?";
          setTimeout(() => {
            del.classList.remove("sure");
            del.textContent = "×";
          }, 3000);
          return;
        }
        deleteSession(item.id);
      });
      li.append(open, del);
      return li;
    }),
  );
}

function clearThread() {
  for (const turn of $("thread").querySelectorAll(".turn")) turn.remove();
}

// A conversation lives on the Agent page: starting or opening one goes there from any page.
function toAgent() {
  if (location.hash && location.hash !== "#agent") location.hash = "#agent";
}

function newConversation() {
  toAgent();
  currentSession = null;
  clearThread();
  $("empty-state").hidden = false;
  renderWork();
  $("task").focus();
}

async function openSession(id) {
  toAgent();
  const response = await fetch(`/api/sessions/${encodeURIComponent(id)}${withProfile()}`);
  if (!response.ok) return refreshWork();
  const session = await response.json();
  currentSession = id;
  clearThread();
  $("empty-state").hidden = true;
  for (const t of session.turns) $("thread").append(pastTurn(t));
  renderWork();
  $("thread").lastElementChild?.scrollIntoView({ block: "end" });
  $("task").focus();
}

// An earlier task, shown as it was asked and answered. Its steps are in the trace.
function pastTurn(t) {
  const turn = el("article", "turn");
  const you = el("div", "you");
  you.append(el("p", "bubble", t.task));
  const agent = el("div", "agent");
  const shown = el("ol", "activity past-cards");
  if (t.plan) {
    const row = el("li", "act part-plan todo-row");
    row.append(todoCard(t.plan));
    shown.append(row);
  }
  if (t.checks) {
    // The finished line of a live run, chips included; addActivity only needs a list to add to.
    const r = { ...t.checks, retrying: false, round: t.checks.rounds };
    const check = startCheck({ activity: shown }, r.round, r.results);
    finishCheck(check, r, { past: true });
  }
  if (shown.children.length) agent.append(shown);
  const reply = el("div", "reply");
  if (t.answer) renderProse(reply, t.answer);
  else reply.append(el("p", "run-foot", `Ended: ${t.outcome}`));
  const meta = el("div", "run-meta");
  meta.append(el("span", "past-meta", `${money(t.usd)} · ${t.seconds.toFixed(1)} s`));
  agent.append(reply);
  if (t.online) {
    const q = qualityCard(0);
    fillQuality(q, t.online);
    agent.append(q.card);
  }
  agent.append(meta);
  turn.append(you, agent);
  return turn;
}

async function deleteSession(id) {
  const response = await fetch(`/api/sessions/${encodeURIComponent(id)}${withProfile()}`, {
    method: "DELETE",
    headers: PAGE_HEADER,
  });
  if (!response.ok) return refreshWork();
  if (id === currentSession) newConversation();
  await refreshWork();
}

function switchProfile() {
  try {
    localStorage.setItem(profileKey(health.workspace), $("profile").value);
  } catch {
    // Storage blocked: the switch still applies to this page.
  }
  currentSession = null; // a conversation belongs to one profile
  clearThread();
  $("empty-state").hidden = false;
  loadPane(); // each profile has its own context, tools and switches
  refreshWork();
  if (!$("view-online").hidden) loadOnline();
  $("task").focus();
}

// Effort: how hard the model thinks. Gemini calls it thinking_level (D-85). "Auto" sends
// nothing, so the model uses its own default (medium on most, minimal on Flash-Lite).
const EFFORT_KEY = "effort";
const EFFORTS = [
  ["", "Auto", 0],
  ["low", "Low", 1],
  ["medium", "Medium", 2],
  ["high", "High", 3],
];
function setUpEffortPicker() {
  const pick = $("effort");
  for (const old of pick.querySelectorAll("option")) old.remove();
  const offered = new Set(health.efforts ?? []);
  for (const [value, label, level] of EFFORTS) {
    if (value && !offered.has(value)) continue;
    const option = el("option");
    option.value = value;
    const glyph = fromTemplate("tpl-bars");
    glyph.dataset.level = level;
    option.append(glyph, el("span", null, `Thinking: ${label}`));
    pick.append(option);
  }
  let saved = "";
  try {
    saved = localStorage.getItem(EFFORT_KEY) ?? "";
  } catch {
    // Storage blocked: start on Auto.
  }
  pick.value = [...pick.options].some((o) => o.value === saved) ? saved : "";
}

function setUpModelPicker() {
  const pick = $("model");
  // Keep the select's own trigger <button>; replace only the options.
  for (const old of pick.querySelectorAll("option")) old.remove();
  for (const id of health.models ?? []) {
    const option = el("option");
    option.value = id;
    // A neutral mark for Claude, so the menu shows at a glance which provider answers.
    option.append(fromTemplate(id.startsWith("claude-") ? "tpl-claude" : "tpl-spark"), el("span", null, modelLabel(id)));
    pick.append(option);
  }
  let saved = null;
  try {
    saved = localStorage.getItem(MODEL_KEY);
  } catch {
    // Storage blocked: fall back to the default model.
  }
  pick.value = health.models?.includes(saved) ? saved : health.model;
}

// Small helpers: every element is built here, and all text goes in as text.
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
const fromTemplate = (id) => $(id).content.firstElementChild.cloneNode(true);
const plural = (n, word, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;
const money = (usd) => `$${usd.toFixed(5)}`;
const argText = (args) =>
  Object.entries(args ?? {})
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
// A tool call as code: find(kind="order", id="A-7"). Long values cut short.
const callBrief = (name, args) =>
  `${name}(${Object.entries(args ?? {})
    .map(([k, v]) => {
      const text = (typeof v === "string" ? v : JSON.stringify(v)).replace(/\s+/g, " ");
      const cut = text.length > 32 ? `${text.slice(0, 32)}…` : text;
      return typeof v === "string" ? `${k}="${cut}"` : `${k}=${cut}`;
    })
    .join(", ")})`;
// What came back, in a few words: the error's first line, or the first fields of the result.
function resultBrief(output, isError) {
  const cut = (text, n = 60) => (text.length > n ? `${text.slice(0, n)}…` : text);
  if (isError) return `error: ${cut(output.split("\n")[0].replace(/^\w+Error:\s*/, ""))}`;
  let data;
  try {
    data = JSON.parse(output.startsWith("[Harness") ? output.slice(output.indexOf("\n") + 1) : output);
  } catch {
    return `returned "${cut(output.replace(/\s+/g, " "), 48)}"`;
  }
  if (Array.isArray(data)) return `returned ${plural(data.length, "item")}`;
  if (data && typeof data === "object") {
    const keys = Object.keys(data);
    return `returned ${keys.slice(0, 3).join(", ")}${keys.length > 3 ? "…" : ""}`;
  }
  return `returned ${cut(String(data), 48)}`;
}
// The tool's own description, first line: what it does, in its author's words.
const toolDoes = (name) => paneInfo?.tools.find((t) => t.name === name)?.description.split("\n")[0];
const shorten = (key, value) =>
  typeof value === "string" && value.length > 160 ? `${value.slice(0, 160)}… (${value.length} chars)` : value;

// One task and the agent's work on it, appended to the thread.
function newTurn(task) {
  const turn = el("article", "turn new");
  const you = el("div", "you");
  you.append(el("p", "bubble", task));

  const agent = el("div", "agent");
  const head = el("header", "agent-head");
  const stats = el("span", "agent-stats working", "Working…");
  head.append(el("span", "agent-name", agentName), el("span", "agent-label", "Activity"), stats);
  const activity = el("ol", "activity");
  activity.setAttribute("aria-label", "What the harness did");
  const reply = el("div", "reply");
  const files = el("div", "files"); // cards for files the tools saved (S03)
  const foot = el("p", "run-foot"); // only for a stop or a failure; empty (hidden) when all went well
  const meta = el("div", "run-meta"); // calls · tokens · cost · time, once the answer is in
  agent.append(head, activity, reply, files, foot, meta);

  turn.append(you, agent);
  $("thread").append(turn);
  reveal(turn, { block: "end" });
  return { activity, reply, files, foot, meta, stats, split: { input: 0, output: 0, thinking: 0 }, cached: 0, window: null, lastInput: 0, model: null, tools: new Map(), tokens: 0, lanes: new Map(), approvals: new Map() };
}

// One activity line. It opens to plain facts, then the raw event (the X-ray).
function addActivity(turn, { text, part = "loop", risk, state = "working", facts, raw }) {
  const li = el("li", `act part-${part} new`);
  const details = el("details");
  const summary = el("summary");
  const dot = el("span", "dot");
  dot.setAttribute("aria-hidden", "true");
  const label = el("span", "act-text", text);
  summary.append(dot, label, el("span", "act-tag", part.toUpperCase()));
  // How much power the tool has: read, write or action (S03). Guardrails will key off it.
  if (risk) summary.append(el("span", `act-risk risk-${risk}`, risk));
  summary.append(fromTemplate("tpl-chevron"));
  const factList = el("dl", "facts");
  const rawBox = el("details", "raw");
  const pre = el("pre");
  rawBox.append(el("summary", null, "Raw event"), pre);
  const body = el("div", "act-body");
  body.append(factList, rawBox);
  details.append(summary, body);
  li.append(details);
  turn.activity.append(li);
  const row = { li, dot, label, factList, pre };
  setActivity(row, { state, facts, raw });
  reveal(li, { block: "nearest" });
  return row;
}

function setActivity(row, { text, state, facts, raw }) {
  if (text !== undefined) row.label.textContent = text;
  if (state) {
    row.li.classList.remove("working", "done", "error");
    row.li.classList.add(state);
    row.dot.textContent = state === "done" ? "✓" : state === "error" ? "✗" : "";
  }
  if (facts) row.factList.replaceChildren(...facts.flatMap(([k, v]) => [el("dt", null, k), el("dd", null, v)]));
  if (raw !== undefined) row.pre.textContent = JSON.stringify(raw, shorten, 2);
}

// Models write a little markdown. Show headings, paragraphs, lists (nested by indent),
// **bold**, `code` and sources as badges, by building elements, never by parsing HTML, so
// model text can't inject anything. The page does the styling, the model only the words (D-131).
function renderProse(container, text) {
  let lists = []; // open lists, outermost first: { el, indent, kind }
  let para = [];
  const flush = () => {
    if (para.length) {
      const p = el("p");
      appendInline(p, para.join("\n"));
      container.append(p);
    }
    para = [];
  };
  let quote = null; // an open <blockquote>, for "> " lines (D-164)
  for (const line of text.split("\n")) {
    const quoted = line.match(/^\s*>\s?(.*)$/);
    if (quoted) {
      flush();
      lists = [];
      if (!quote) container.append((quote = el("blockquote", "prose-quote")));
      const p = el("p");
      appendInline(p, quoted[1]);
      if (quoted[1].trim()) quote.append(p);
      continue;
    }
    quote = null;
    const heading = line.match(/^\s*(#{1,4})\s+(.*)$/);
    const item = line.match(/^(\s*)(?:[-*•]|(\d+)[.)])\s+(.*)$/);
    if (heading) {
      flush();
      lists = [];
      const h = el(heading[1].length <= 2 ? "h3" : "h4", "prose-h");
      appendInline(h, heading[2]);
      container.append(h);
    } else if (item) {
      flush();
      const indent = item[1].replace(/\t/g, "  ").length;
      const kind = item[2] ? "ol" : "ul";
      while (lists.length && indent < lists.at(-1).indent) lists.pop();
      const top = lists.at(-1);
      if (!top || indent > top.indent || top.kind !== kind) {
        if (top && indent <= top.indent) lists.pop(); // same level, other kind: a sibling list
        const parent = lists.at(-1)?.el.lastElementChild ?? container; // nest under the last item
        const list = el(kind);
        parent.append(list);
        lists.push({ el: list, indent, kind });
      }
      const li = el("li");
      appendInline(li, item[3]);
      lists.at(-1).el.append(li);
    } else if (!line.trim()) {
      flush();
      lists = [];
    } else {
      lists = [];
      para.push(line);
    }
  }
  flush();
}

// A source in backticks: a section (§), an ID like CUS-0042, or a file path. Shown as a badge.
const SOURCE = /§|^[A-Z]{2,}-\d+|\.md$|\//;

function appendInline(parent, text) {
  // "(`standard-terms §2`)" → a badge alone: the badge already reads as a source.
  text = text.replace(/\((`[^`]+`(?:,\s*`[^`]+`)*)\)/g, (whole, inner) => (SOURCE.test(inner.replace(/`/g, "")) ? inner : whole));
  for (const part of text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)) {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) parent.append(el("strong", null, part.slice(2, -2)));
    else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      const inner = part.slice(1, -1);
      parent.append(el("code", SOURCE.test(inner) ? "cite" : null, inner));
    } else if (part) parent.append(part);
  }
}

// Screen readers hear the start and the end of a run, not every step.
const announce = (text) => {
  $("run-status").textContent = text;
};

// Turn one event from the harness into a change on the page.
function onEvent(ev, turn) {
  const d = ev.data;
  if (ev.type === "session_started") {
    currentSession = d.session_id;
    if (d.new) {
      workItems = [{ id: d.session_id, title: d.title, turns: 0, updated: Date.now() / 1000 }, ...workItems];
      renderWork();
    }
    return;
  }
  if (ev.type === "session_titled") {
    const item = workItems.find((i) => i.id === d.session_id);
    if (item) item.title = d.title;
    renderWork();
    document.querySelector(`.work-item[data-id="${d.session_id}"] .work-title`)?.classList.add("retitled");
    return;
  }
  // While a check round's ticks play (S11), later events wait their turn, in order.
  if (turn.holding) return void turn.queue.push(ev);
  // A helper's events carry agent_id (D-63): they go to its own lane, not the main list.
  if (d.agent_id) return onLaneEvent(ev, turn);
  if (ev.type === "run_started") {
    turn.planOn = (d.tools ?? []).includes("write_plan");
    const off = d.off ?? {};
    const switchedOff = [...(off.tools ?? []), ...(off.skills ?? []), ...(off.subagents ?? [])];
    addActivity(turn, {
      text: `Started a run · ${d.model}${switchedOff.length ? ` · ${switchedOff.length} off` : ""}`,
      state: "done",
      facts: [
        ["Model", d.model],
        ["Thinking", d.thinking ? `${d.thinking} (thinking_level)` : "the model's default"],
        ["Tools", d.tools.join(", ") || "none"],
        ...(switchedOff.length ? [["Switched off", switchedOff.join(", ")]] : []),
        ["Limits", `${d.limits.max_steps} calls · $${d.limits.max_usd} · ${d.limits.max_seconds} s`],
        ["Run", ev.run_id],
      ],
      raw: d,
    });
    const c = d.context ?? {};
    if (c.files?.length || c.skills?.length) {
      // What went into the prompt, before the first call (S02): the CONTEXT line.
      const who = c.profile ? `${labelFor(c.profile)} · ` : "";
      addActivity(turn, {
        text:
          `Loaded context · ${who}${plural(c.files.length, "file")} · ${plural(c.skills.length, "skill")}` +
          (c.warnings?.length ? " · ⚠ over budget" : ""),
        part: "context",
        state: "done",
        facts: [
          ...(c.profile ? [["Profile", labelFor(c.profile)]] : []),
          ...c.files.map((f) => ["File", `${f.path} · ~${f.tokens} tokens`]),
          ...c.skills.map((s) => ["Skill", `${s.name}: ${s.description}`]),
          ["Prompt", `~${c.prompt_tokens} tokens · id ${c.prompt_id} (same on every call)`],
          ...(c.warnings ?? []).map((w) => ["Warning", w]),
        ],
        raw: c,
      });
    }
    if (c.notes?.length) {
      // Long-term memory read into the prompt (S07), shown as its own step (S12-AC5).
      addActivity(turn, {
        text: `Read ${plural(c.notes.length, "fact")} from long-term memory${c.profile ? ` (${labelFor(c.profile)})` : ""}`,
        part: "memory",
        state: "done",
        facts: c.notes.map((n, i) => [`Fact ${i + 1}`, factText(n)]),
        raw: { notes: c.notes },
      });
    }
  } else if (ev.type === "context_trimmed") {
    const saved = Math.max(0, d.before - d.after);
    const pct = d.window ? Math.round(((d.fill ?? d.before) / d.window) * 100) : null;
    const what =
      d.technique === "summarize"
        ? `summarized ${plural(d.turns, "earlier task")}`
        : `cleared ${plural(d.cleared, "old tool result")}`;
    addActivity(turn, {
      text: `Trimmed context · ${what} · about ${saved.toLocaleString()} tokens freed`,
      part: "context",
      state: "done",
      facts: [
        ["Why", pct === null ? "The conversation was getting long." : `The context was at ${pct}% of the ${d.window.toLocaleString()}-token working window.`],
        ["What", d.technique === "summarize" ? "Older tasks were folded into a short summary by a small model." : "Old tool results became one-line stubs; the agent can ask again."],
        ["Size", `about ${d.before.toLocaleString()} → ${d.after.toLocaleString()} tokens (estimated)`],
        ["Kept", "The saved conversation still has everything. The model's own steps are never changed."],
      ],
      raw: d,
    });
  } else if (ev.type === "model_called") {
    if (d.window) turn.window = d.window;
    turn.model = addActivity(turn, {
      text: `Model is thinking · call ${d.step}`,
      facts: [["Sends", `the whole history: ${plural(d.history, "step")} (store=false)`]],
      raw: d,
    });
  } else if (ev.type === "model_replied" && turn.model) {
    const u = d.usage ?? {};
    const used = (u.total_input_tokens ?? 0) + (u.total_output_tokens ?? 0) + (u.total_thought_tokens ?? 0);
    turn.tokens += used;
    turn.cached += u.total_cached_tokens ?? 0;
    turn.lastInput = u.total_input_tokens ?? turn.lastInput;
    turn.split.input += u.total_input_tokens ?? 0;
    turn.split.output += u.total_output_tokens ?? 0;
    turn.split.thinking += u.total_thought_tokens ?? 0;
    let text = `Model replied: ${d.status}`;
    if (d.tool_calls.length) {
      // ["search", "search"] → "search ×2"
      const counts = new Map();
      for (const name of d.tool_calls) counts.set(name, (counts.get(name) ?? 0) + 1);
      const names = [...counts].map(([name, n]) => (n > 1 ? `${name} ×${n}` : name));
      text = `Model picked ${names.length > 1 ? `${names.length} tools` : "a tool"}: ${names.join(", ")}`;
    } else if (d.status === "completed") {
      text = turn.rounds?.at(-1)?.retrying ? "Model rewrote the answer" : "Model wrote the answer";
    }
    setActivity(turn.model, {
      text,
      state: "done",
      facts: [
        ["Status", d.status],
        ["Tokens", `in ${u.total_input_tokens ?? 0} · out ${u.total_output_tokens ?? 0} · thinking ${u.total_thought_tokens ?? 0}`],
        ["Cost", `${money(d.usd)} (paid-tier price)`],
        ["Steps", `${plural(d.steps.length, "step")} kept exactly as received`],
      ],
      raw: d,
    });
  } else if (ev.type === "plan_updated") {
    // One To-Do card per task, redrawn on every update (S11).
    turn.direct?.li.remove(); // it planned after all
    turn.direct = null;
    if (!turn.todo) {
      turn.todo = el("li", "act part-plan todo-row");
      turn.activity.append(turn.todo);
    }
    turn.todo.replaceChildren(todoCard(d.items));
  } else if (ev.type === "verify_started") {
    // A circle while it checks, and each check as a chip: ○ now, ✓ or ✗ when done (S11).
    turn.check = startCheck(turn, d.round, d.checks);
  } else if (ev.type === "verify_finished") {
    // One line per round, in run order: draft → checked → rewrote → checked. It opens to
    // each check's reason, what the agent was told, and the draft.
    if (d.retrying && turn.model) setActivity(turn.model, { text: "Model wrote a draft" });
    (turn.rounds ??= []).push(d);
    const check = turn.check ?? startCheck(turn, d.round, d.results); // an old trace: no start event
    turn.check = null;
    // The checks are code and take milliseconds: hold the circle a moment so it can be
    // seen, then tick them off one by one. Nothing here slows the run itself.
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const wait = reduce ? 0 : Math.max(0, 400 - (performance.now() - check.since));
    const step = reduce ? 0 : 110;
    const shown = d.results.filter((r) => r.status !== "skipped");
    turn.holding = true;
    turn.queue ??= [];
    shown.forEach((r, i) => setTimeout(() => settleRow(rowFor(check, r), r.status), wait + i * step));
    setTimeout(() => {
      finishCheck(check, d);
      turn.holding = false;
      for (const e of turn.queue.splice(0)) onEvent(e, turn);
    }, wait + shown.length * step);
  } else if (ev.type === "tool_started" && d.name === "write_plan") {
    turn.tools.set(d.call_id, { plan: true }); // the To-Do card shows it
  } else if (ev.type === "tool_finished" && turn.tools.get(d.call_id)?.plan) {
    if (d.is_error) addActivity(turn, { text: `Plan not saved · ${d.output}`, part: "plan", state: "error", raw: d });
  } else if (ev.type === "tool_started") {
    // Not in the tour: the line comes at the first tool call, and the recorded run writes its
    // To-Do plan a call later, so "no plan" would be wrong on screen (your review, D-194).
    if (turn.planOn && !turn.todo && !turn.direct && !TOUR) {
      // Direct or To-Do: the model decides (D-121). Say which, so a missing plan reads as its
      // choice, not as something skipped (your request, D-147).
      turn.direct = addActivity(turn, {
        text: "No To-Do plan · the model chose to work directly",
        part: "plan",
        state: "done",
        facts: [
          ["Who decides", "The model. It writes a To-Do plan for 3 or more parts, or 2 or more asks in one message; otherwise it works directly"],
          ["Checked", "Plan Complete applies only when a plan was made"],
        ],
      });
    }
    const args = argText(d.arguments);
    const part = d.name === "delegate_task" ? "sub-agent" : d.part === "context" ? "context" : "tool";
    // load_skill is the harness's own context tool: name it for what it does.
    let label = `Tool call · ${callBrief(d.name, d.arguments)}`;
    if (d.name === "load_skill") label = `Read skill ${d.arguments?.name ?? ""}`;
    if (d.name === "save_note") label = "Saved a fact to long-term memory";
    if (d.name === "delegate_task") label = `Handed the job to the ${d.arguments?.agent ?? "helper"} sub-agent`;
    const risk = part === "tool" ? d.risk : undefined;
    const row = addActivity(turn, { text: label, part, risk, raw: d });
    turn.tools.set(d.call_id, { row, args, label, name: d.name, arguments: d.arguments ?? {} });
    if (d.name === "delegate_task") turn.delegateRow = row; // its helper's lane goes under it
  } else if (ev.type === "tool_finished") {
    const started = turn.tools.get(d.call_id);
    if (started) {
      const blocked = d.blocked;
      setActivity(started.row, {
        text: blocked
          ? `⛔ Blocked · ${started.label} · ${blocked.label} (${blocked.because})`
          : ["load_skill", "delegate_task", "save_note"].includes(started.name)
            ? started.label
            : `${started.label} → ${resultBrief(d.output ?? "", d.is_error)}`,
        state: d.is_error ? "error" : "done",
        facts: [
          ...(toolDoes(started.name) ? [["What it does", toolDoes(started.name)]] : []),
          // One row per argument, so a long draft doesn't swallow the others.
          ...(started.args
            ? Object.entries(started.arguments).map(([k, v]) => [k, typeof v === "string" ? v : JSON.stringify(v)])
            : [["Arguments", "none"]]),
          ...(d.risk ? [["Risk", d.risk]] : []),
          ...(d.blocked ? [["Blocked by", `${d.blocked.rule}: ${d.blocked.label} (${d.blocked.because})`]] : []),
          ...(d.hidden ? [["Hidden", `${d.hidden.join(", ")} (not for this profile)`]] : []),
          ["Output", d.output],
          ["Call ID", d.call_id ?? "–"],
          ["Sent back as", d.is_error ? "an error the model can read" : "a result"],
        ],
        raw: d,
      });
      // ⚠ A result that tries to instruct the AI gets its own Guardrail line (D-78).
      if (d.flags?.length) {
        addActivity(turn, {
          text: `⚠ Flagged · ${d.name} returned text that tries to instruct the AI → fenced as data; any action it asks for still needs a person`,
          part: "guard",
          state: "done",
          facts: [
            ["Text", d.flags[0]],
            ["What the harness did", "Put a warning in front of the result: it is data from a document, not an instruction."],
            ["What still protects you", "Every action waits for its hard limits, its checks and a person. The harness can't promise the model ignored the text, so it doesn't claim to."],
          ],
          raw: { flags: d.flags },
        });
      }
    }
  } else if (ev.type === "scope_checked") {
    // The scope guard (D-81): one small check before the loop starts.
    const out = !d.in_scope;
    addActivity(turn, {
      text: out ? `⛔ Outside scope · ${d.reason || "not this assistant's job"}` : d.error ? "Scope check skipped (the check model was busy)" : "Checked the request is in scope",
      part: "guard",
      state: out ? "error" : "done",
      facts: [
        ["Verdict", out ? "outside scope: refused before the agent started" : "in scope"],
        ...(d.reason ? [["Why", d.reason]] : []),
        ...(d.error ? [["Check failed", `${d.error} (the run went ahead; the prompt still keeps it on topic)`]] : []),
        ["Cost", money(d.usd ?? 0)],
      ],
      raw: d,
    });
  } else if (ev.type === "limits_checked") {
    // Every hard limit on this action, passes included (S12-AC3, D-135).
    const crossed = d.limits.filter((l) => !l.held);
    const offered = d.limits.filter((l) => l.value !== null && l.value !== undefined && l.value !== false);
    const short = (l) => `${l.arg.replace(/_(pct|days|months)$/, "").replace(/_/g, " ")} ${l.value} ${l.line}`;
    addActivity(turn, {
      text: crossed.length
        ? `⛔ Hard limit crossed · ${crossed.map((l) => `${l.label} (${l.because})`).join(", ")}`
        : `Hard limits held · ${offered.length ? offered.map(short).join(" · ") : `${plural(d.limits.length, "rule")}, none touched`}`,
      part: "guard",
      state: crossed.length ? "error" : "done",
      facts: d.limits.map((l) => [`${l.held ? "✓" : "✗"} ${l.label}`, `${l.value === null || l.value === undefined ? "not offered" : l.value} · limit ${l.line} · ${l.because}`]),
      raw: d,
    });
  } else if (ev.type === "action_checked") {
    // The workspace's checks on this call, before anyone is asked (S12-AC1, D-134).
    const failed = d.results.filter((r) => r.status === "failed");
    const mark = { passed: "✓", failed: "✗", error: "!", skipped: "–" };
    addActivity(turn, {
      text: failed.length
        ? `Stopped before ${d.name} · ${failed.map((r) => r.label).join(", ")} failed → back to the agent, no one asked`
        : `Checked before ${d.name} · ${d.results.filter((r) => r.status === "passed").map((r) => r.label).join(", ") || "nothing to check"} ✓`,
      part: "verify",
      state: failed.length ? "error" : "done",
      facts: d.results.map((r) => [`${mark[r.status]} ${r.label}`, r.message]),
      raw: d,
    });
  } else if (ev.type === "approval_requested") {
    turn.approvals.set(d.call_id, approvalCard(turn, d));
  } else if (ev.type === "approval_decided") {
    turn.approvals.get(d.call_id)?.decided(d);
  } else if (ev.type === "file_saved") {
    // In the run's steps, where it happened: after its limits, checks and approvals (D-136).
    const row = el("li", "act file-row");
    const inline = fileCard(d);
    inline.open = false; // folded here; the email shows open under the answer
    row.append(inline);
    turn.activity.append(row);
    reveal(row, { block: "nearest" });
    // An email, sent or drafted, shows open with the answer that reports it (D-164).
    if (inline.classList.contains("email-card")) (turn.mail ??= []).push(d);
  } else if (ev.type === "online_evals_started") {
    // After the answer (D-148): its quality, scored while you read. Never sent back.
    turn.quality = qualityCard(d.metrics.length, d.judge);
    turn.meta.before(turn.quality.card);
  } else if (ev.type === "online_evals_finished") {
    if (!turn.quality) {
      turn.quality = qualityCard(0);
      turn.meta.before(turn.quality.card);
    }
    fillQuality(turn.quality, d);
    announce(`Online evals: ${turn.quality.count.textContent}`);
  } else if (ev.type === "run_finished") {
    // A model call that never got its reply (time limit, error) is marked, not left spinning.
    if (turn.model?.li.classList.contains("working")) setActivity(turn.model, { state: "error" });
    turn.stats.classList.remove("working");
    turn.stats.textContent = ""; // the header was "Working…"; the numbers now sit under the answer
    const numbers = [plural(d.model_calls, "call"), `${turn.tokens} tokens`, money(d.usd), `${d.seconds.toFixed(1)} s`];
    turn.meta.replaceChildren(receipt(turn, d));
    if (d.answer) renderProse(turn.reply, d.answer);
    // What went out or was drafted, with the answer that reports it (your request, 2026-11-12).
    for (const mail of turn.mail ?? []) turn.files.append(fileCard(mail));
    const reason = REASONS[d.reason] ?? d.reason;
    const unverified = d.checks?.passed === false ? d.checks.results.filter((r) => r.status === "failed").map((r) => r.label) : [];
    const note =
      { stopped: `■ Stopped: ${reason}`, failed: `✗ Failed: ${reason}` }[d.outcome] ??
      (unverified.length ? `⚠ Not verified: ${unverified.join(", ")} still failing. See the Checks card above for why.` : "");
    turn.foot.textContent = note;
    turn.foot.className = `run-foot ${d.outcome}${unverified.length ? " unverified" : ""}`;
    announce(`${note || "Run complete"}. ${numbers.join(", ")}`);
    reveal(turn.meta, { block: "nearest" });
  }
}

// The agent's to-do list for this task (S11): ✓ done, ▸ doing, – skipped with its reason.
const BOX = { open: "○", doing: "▸", done: "✓", skipped: "–" };
function todoCard(items) {
  const finished = items.filter((i) => i.status === "done" || i.status === "skipped").length;
  const card = el("div", "todo-card");
  const head = el("div", "card-head");
  head.append(el("span", "card-title", "To-Do"), el("span", "card-count", `${finished} of ${items.length} done`));
  const list = el("ul", "todo-list");
  for (const i of items) {
    const li = el("li", `todo-item is-${i.status}`);
    li.append(el("span", "todo-box", BOX[i.status] ?? "○"), el("span", "todo-text", i.text));
    if (i.note) li.append(el("span", "todo-note", i.note));
    list.append(li);
  }
  card.append(head, list);
  return card;
}

// A check round as a card, built like the To-Do card (S11, your request): a title, a count,
// then one row per check that applied, added as it ticks to ✓ or ✗; a failure's reason sits
// under its row. No names while checking: listing them all, then dropping the ones that didn't
// apply, read like a plan that vanished (your note, D-147). Returns what verify_finished fills.
function startCheck(turn, round, checks) {
  const li = el("li", "act part-verify todo-row");
  const card = el("div", "todo-card check-card is-checking");
  const head = el("div", "card-head");
  const title = el("span", "card-title", round > 1 ? "Checking the new answer…" : "Checking the answer…");
  const count = el("span", "card-count", `${checks.length} checks`);
  head.append(el("span", "check-spin", ""), title, count);
  head.title = "Before you see an answer, the harness checks it with the workspace's rules: plain code, not a model. A failure goes back to the agent once.";
  const list = el("ul", "todo-list");
  const rows = new Map();
  card.append(head, list);
  li.append(card);
  turn.activity.append(li);
  reveal(li, { block: "nearest" });
  return { card, title, count, list, rows, since: performance.now() };
}

// The row for one check's result, made when it is first shown.
function rowFor(check, x) {
  if (!check.rows.has(x.name)) {
    const row = el("li", "todo-item is-pending");
    row.append(el("span", "todo-box", "○"), el("span", "todo-text", x.label));
    check.list.append(row);
    check.rows.set(x.name, row);
  }
  return check.rows.get(x.name);
}

function settleRow(row, status) {
  if (!row) return;
  row.className = `todo-item is-${status}`;
  row.firstChild.textContent = { passed: "✓", failed: "✗", error: "!", skipped: "–" }[status] ?? "○";
}

// The round's verdict on the card: its title, count and colour; failures' reasons under their
// rows; checks that didn't apply folded into one quiet row; on a retry, what the agent was told.
function finishCheck(check, r, { past = false } = {}) {
  const applied = r.results.filter((x) => x.status === "passed" || x.status === "failed");
  const failed = applied.filter((x) => x.status === "failed");
  const n = `${applied.length - failed.length} of ${applied.length} passed`;
  let title, count, state;
  if (r.passed === null) [title, count, state] = ["Checked the answer", "nothing to check", "skipped"];
  else if (r.passed && r.round > 1) [title, count, state] = [past ? "Checked the answer" : "Checked the new answer", `${n} · fixed on retry`, "passed"];
  else if (r.passed) [title, count, state] = ["Checked the answer", n, "passed"];
  else if (r.retrying) [title, count, state] = ["Checked the draft", `${failed.length} failed · sent back to fix`, "retrying"];
  else [title, count, state] = ["Not verified", `${failed.length} still failing`, "failed"];
  check.title.textContent = title;
  check.count.textContent = count;
  check.card.className = `todo-card check-card is-${state}`;
  for (const x of r.results) {
    if (x.status === "skipped") continue;
    const row = rowFor(check, x);
    settleRow(row, x.status);
    if (x.status !== "passed") row.append(el("span", "todo-note", x.status === "error" ? `The check itself broke (not sent back): ${x.message}` : x.message));
    else row.title = x.message; // a pass says why on hover
  }
  const skipped = r.results.filter((x) => x.status === "skipped");
  if (skipped.length) {
    const row = el("li", "todo-item is-skipped");
    row.append(el("span", "todo-box", "–"), el("span", "todo-text", `${skipped.length} didn't apply`));
    row.title = skipped.map((x) => `${x.label}: ${x.message}`).join("\n");
    check.list.append(row);
  }
  if (r.note || r.draft) {
    const fold = el("details", "check-fold");
    fold.append(el("summary", null, "What the agent was told, and its draft"));
    const facts = el("dl", "facts");
    if (r.note) facts.append(el("dt", null, "Told the agent"), el("dd", null, r.note.replace(/^\[Harness check\]\s*/, "")));
    if (r.draft) facts.append(el("dt", null, "The draft"), el("dd", null, r.draft));
    fold.append(facts);
    check.card.append(fold);
  }
}

// ── Online Evals card (D-148): under the answer, filled when the scores arrive ──
const GRADED = { code: "Code", judge: "LLM as Judge" };
const gradeChip = (by) => el("span", `grade-chip grade-${by}`, GRADED[by] ?? by);
const scoreText = (r) => (r.score == null ? "–" : r.score.toFixed(2));

function qualityCard(n, judge) {
  // Folded by default (your request): the header's "3 of 6 passed" is the summary; open for why.
  const card = el("details", "todo-card check-card quality-card is-checking");
  const head = el("summary", "card-head");
  const title = el("span", "card-title", "Online Evals");
  const count = el("span", "card-count", n ? `scoring ${plural(n, "metric")}…` : "");
  head.append(el("span", "check-spin", ""), title, count, fromTemplate("tpl-chevron"));
  head.title = `After you see the answer, the harness scores its quality: code metrics, and one LLM as Judge call${judge ? ` (${modelLabel(judge)})` : ""}. Never blocking, never sent back to the agent.`;
  const list = el("ul", "todo-list");
  card.append(head, list);
  return { card, title, count, list };
}

function fillQuality(q, d) {
  const results = d.results ?? [];
  const scored = results.filter((r) => r.status === "passed" || r.status === "failed");
  const passed = scored.filter((r) => r.status === "passed").length;
  const state = !scored.length ? "skipped" : passed === scored.length ? "passed" : "mixed";
  q.card.className = `todo-card check-card quality-card is-${state}`;
  const off = d.judge_off ? " · judge off" : ""; // only the free code metrics ran (D-167)
  q.count.textContent = (scored.length ? `${passed} of ${scored.length} passed` : d.error ? "not scored" : "nothing to score") + off;
  const rows = [];
  for (const r of results) {
    if (r.status === "skipped") continue;
    const row = el("li", `todo-item quality-item is-${r.status}`);
    const box = { passed: "✓", failed: "✗", not_scored: "?" }[r.status] ?? "○";
    row.append(el("span", "todo-box", box), el("span", "todo-text", r.label), el("span", "q-score", scoreText(r)), gradeChip(r.graded_by));
    const why = r.status === "not_scored" ? `Not scored: ${r.reason}` : r.reason;
    const missing = r.unsupported?.length ? ` Not found: ${r.unsupported.join("; ")}` : "";
    if (r.status !== "passed") row.append(el("span", "todo-note", why + missing));
    else row.title = why;
    rows.push(row);
  }
  const skipped = results.filter((r) => r.status === "skipped");
  if (skipped.length) {
    const row = el("li", "todo-item is-skipped");
    row.append(el("span", "todo-box", "–"), el("span", "todo-text", `${skipped.length} didn't apply`));
    row.title = skipped.map((r) => `${r.label}: ${r.reason}`).join("\n");
    rows.push(row);
  }
  if (d.judge) {
    const row = el("li", "todo-item quality-foot");
    row.append(el("span", "todo-box", ""), el("span", "todo-note", `Judge: ${modelLabel(d.judge)} · ${money(d.usd ?? 0)} · never sent back to the agent`));
    rows.push(row);
  }
  q.list.replaceChildren(...rows);
}

// The run summary under the final answer: four numbers that count up, and where the
// tokens went (read from the prompt, written as the answer, or spent thinking).
function receipt(turn, d) {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Short labels keep the summary on one line; "$" and "s" say what they are.
  const cells = [
    [d.model_calls === 1 ? "Model Call" : "Model Calls", d.model_calls, (n) => String(Math.round(n)), "calls"],
    ["Tokens", turn.tokens, (n) => Math.round(n).toLocaleString(), "tokens"],
    ["", d.usd, (n) => `$${n.toFixed(5)}`, "cost"],
    ["", d.seconds, (n) => `${n.toFixed(1)} s`, "time"],
  ];
  const card = el("div", "receipt");
  const grid = el("div", "receipt-grid");
  for (const [label, value, format, key] of cells) {
    const cell = el("div", `receipt-cell rc-${key}`);
    const number = el("span", "receipt-num", format(reduce ? value : 0));
    cell.append(number, ...(label ? [el("span", "receipt-label", label)] : []));
    grid.append(cell);
    if (!reduce) {
      const start = performance.now();
      const tick = (now) => {
        const t = Math.min(1, (now - start) / 900);
        number.textContent = format(value * (1 - (1 - t) ** 3)); // ease out
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
  }
  card.append(grid);
  const { input, output, thinking } = turn.split;
  if (input + output + thinking) {
    const bar = el("div", "receipt-bar");
    const words = `Tokens: ${input.toLocaleString()} input · ${output.toLocaleString()} output · ${thinking.toLocaleString()} thinking`;
    bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", words);
    bar.title = words;
    const legend = el("div", "receipt-legend");
    for (const [name, n, cls] of [["Input", input, "in"], ["Output", output, "out"], ["Thinking", thinking, "think"]]) {
      if (!n) continue;
      const seg = el("span", `seg seg-${cls}`);
      seg.style.flexGrow = n;
      bar.append(seg);
      const item = el("span", `legend-item lg-${cls}`);
      item.append(el("i"), `${name} ${n.toLocaleString()}`);
      legend.append(item);
    }
    if (turn.cached) {
      const item = el("span", "legend-item lg-cached");
      item.append(el("i"), `Cached ${turn.cached.toLocaleString()}`);
      legend.append(item);
    }
    const tokens = el("div", "receipt-tokens"); // one column: the bar, its legend under it
    tokens.append(bar, legend);
    card.append(tokens);
  }
  if (turn.window && turn.lastInput) {
    // How full the working window was on the last call: green, amber past 50%, red past 70%.
    const share = Math.min(1, turn.lastInput / turn.window);
    const row = el("div", "receipt-fill");
    const track = el("div", "fill-track");
    const level = el("span", `fill-level ${share >= 0.7 ? "hot" : share >= 0.5 ? "warm" : "cool"}`);
    level.style.width = `${Math.max(2, Math.round(share * 100))}%`;
    track.append(level);
    row.append(el("span", "fill-label", `Context ${turn.lastInput.toLocaleString()} / ${turn.window.toLocaleString()} (${Math.round(share * 100)}%)`), track);
    row.title = "How full the agent's working window was on its last call. Past 50% old tool results are cleared; past 70% older tasks are summarized.";
    card.append(row);
  }
  return card;
}

// A helper's lane (S04): nested under the line that started it, with its own counters.
function newLane(turn, d) {
  const box = el("div", "lane");
  const head = el("div", "lane-head");
  const stats = el("span", "lane-stats working", "Working…");
  head.append(el("span", "lane-name", d.agent), el("span", "lane-meta", ""), stats);
  const activity = el("ol", "activity lane-activity");
  activity.setAttribute("aria-label", `What ${d.agent} did`);
  box.append(head, activity);
  (turn.delegateRow?.li ?? turn.activity).append(box);
  // The same counters as a main turn: onEvent fills them for the helper too (found live:
  // a missing split crashed the page on the helper's first reply).
  return { box, head, stats, activity, model: null, tools: new Map(), tokens: 0, lanes: new Map(), split: { input: 0, output: 0, thinking: 0 }, cached: 0, window: null, lastInput: 0 };
}

function onLaneEvent(ev, turn) {
  const { agent_id: id, parent_id: _parent, agent: _agent, ...data } = ev.data;
  let lane = turn.lanes.get(id);
  if (!lane) {
    lane = newLane(turn, ev.data);
    turn.lanes.set(id, lane);
  }
  if (ev.type === "run_started") {
    lane.head.querySelector(".lane-meta").textContent = `${data.model} · ${plural(data.tools.length, "tool")}`;
  } else if (ev.type === "run_finished") {
    if (lane.model?.li.classList.contains("working")) setActivity(lane.model, { state: "error" });
    lane.stats.classList.remove("working");
    const why = data.outcome === "completed" ? "" : ` · ${REASONS[data.reason] ?? data.reason}`;
    lane.stats.textContent = `${plural(data.model_calls, "call")} · ${lane.tokens} tokens · ${money(data.usd)} · ${data.seconds.toFixed(1)} s${why}`;
    lane.box.classList.add(data.outcome);
  } else {
    onEvent({ ...ev, data }, lane); // same lines as the main agent, in the lane
  }
}

// "rate_pct", 5 → "rate 5%"; "notice_days", 30 → "notice 30 days". Generic: it
// reads only the name's ending, never a workspace's terms.
function termText(arg, value) {
  const unit = { pct: "%", days: " days", months: " months" }[arg.match(/_(pct|days|months)$/)?.[1]] ?? "";
  const name = arg.replace(/_(pct|days|months)$/, "").replaceAll("_", " ");
  return value === true ? name : `${name} ${value}${unit}`;
}

// What one person in the chain decides: their terms, or the rule's name when it has none.
function decides(step) {
  const own = step.rules.filter((r) => r.arg);
  return own.length ? own.map((r) => termText(r.arg, r.value)).join(" · ") : step.rules.map((r) => r.label).join(" · ");
}

// ⏸ Human in the loop (D-79): the run waits here until you approve or reject.
function approvalCard(turn, d) {
  const asking = d.kind === "question";
  const role = d.approver || "you";
  const mine = (d.chain ?? []).find((c) => c.approver === d.approver);
  const what = mine ? decides(mine) : d.rule || d.name;
  const row = addActivity(turn, {
    text: asking ? "⏸ The agent has a question for you" : `⏸ Waiting for ${role}${d.of > 1 ? ` · step ${d.step} of ${d.of}` : ""} · ${what}`,
    part: "guard",
    facts: [["Why", d.because]],
    raw: d,
  });
  const card = el("div", asking ? "approval-card" : "approval-card approval-v2");
  const head = el("div", "approval-head");
  const countdown = el("span", "approval-clock");
  if (asking) {
    head.append(el("span", "approval-role", "Question"), countdown);
  } else {
    // Who, and which step: an avatar, the role, "Step 1 of 3".
    const who = el("div", "approval-who");
    who.append(el("strong", "approval-name", d.approver || "A person"), el("span", "approval-sub", d.of > 1 ? `Step ${d.step} of ${d.of} · approval needed` : "Approval needed"));
    head.append(el("span", "approval-avatar", (d.approver || "?").charAt(0).toUpperCase()), who, countdown);
  }
  const buttons = el("div", "approval-actions");
  const field = el(asking ? "textarea" : "input", "approval-field");
  field.setAttribute("aria-label", asking ? "Your answer" : "Reason, shown to the agent if you reject");
  field.placeholder = asking ? "Your answer…" : "Reason if you reject (the agent will read it)";
  if (asking) field.rows = 2;
  field.maxLength = 500;
  const approve = el("button", "approve", asking ? "Send Answer" : d.approver ? `Approve as ${d.approver}` : "Approve");
  const hand = el("div", "approval-handoff"); // "this needs the CFO" and who to switch to
  const reject = el("button", "reject", asking ? "Skip" : "Reject");
  for (const b of [approve, reject]) b.type = "button";
  buttons.append(approve, reject);

  if (asking) {
    card.append(head, el("p", "approval-question", d.arguments?.question ?? ""), field, buttons);
  } else {
    // What THIS person decides, as the headline; the rule behind it underneath.
    const focus = el("div", "approval-focus");
    const chips = el("div", "approval-terms");
    const own = (mine?.rules ?? []).filter((r) => r.arg);
    if (own.length) chips.append(...own.map((r) => el("span", "approval-term", termText(r.arg, r.value))));
    focus.append(el("span", "approval-kicker", "You're approving"), el("p", "approval-what", own.length ? (mine.rules.map((r) => r.label).join(" · ")) : d.rule || d.name), ...(own.length ? [chips] : []), el("p", "approval-rule", d.because));
    // The whole chain, so no one reads the others' terms as theirs.
    const chain = el("ol", "approval-chain");
    chain.setAttribute("aria-label", "Approval chain");
    (d.chain ?? []).forEach((c, i) => {
      const state = i + 1 < d.step ? "done" : i + 1 === d.step ? "now" : "next";
      const li = el("li", `chain-step is-${state}`);
      li.append(el("span", "chain-node", state === "done" ? "✓" : String(i + 1)), el("strong", "chain-name", c.approver || "A person"), el("span", "chain-what", decides(c)));
      chain.append(li);
    });
    // What the person approves, always in view (your request): the message as it will read,
    // then every term it offers and who decides each, this approver's rows marked.
    const args = d.arguments ?? {};
    const owner = new Map((d.chain ?? []).flatMap((c) => c.rules.filter((r) => r.arg).map((r) => [r.arg, c.approver])));
    const shown = (v) => v !== null && v !== undefined && v !== false && v !== "";
    // From the workspace (D-141): header facts ("To", "Customer"), and where each term started.
    const facts = (d.context ?? []).filter((r) => r.fact);
    const started = new Map((d.context ?? []).filter((r) => r.arg).map((r) => [r.arg, r]));
    // A term goes in the table: one someone decides, or one the workspace knows the start of.
    const isTerm = (k) => owner.has(k) || started.has(k);
    const all = el("section", "approval-message");
    if (typeof args.body === "string" || typeof args.subject === "string") {
      all.append(el("h5", "approval-section", "Message to approve"));
      const mail = el("div", "approval-mail");
      const meta = el("div", "approval-mail-meta");
      // The workspace's header facts when it gives them; else every argument that isn't the
      // subject, body or a term.
      const lines = facts.length
        ? facts.map((f) => [f.fact, f.value])
        : Object.entries(args)
            .filter(([k, v]) => !["subject", "body"].includes(k) && !isTerm(k) && shown(v))
            .map(([k, v]) => [k.replace(/_id$/, "").replaceAll("_", " "), String(v)]);
      for (const [key, value] of lines) {
        const line = el("div", "approval-mail-line");
        line.append(el("span", "approval-mail-key", key), el("span", null, value));
        meta.append(line);
      }
      if (args.subject) mail.append(el("p", "approval-mail-subject", args.subject));
      mail.append(meta);
      const body = el("div", "approval-mail-body");
      renderProse(body, String(args.body ?? ""));
      mail.append(body);
      all.append(mail);
    }
    const terms = Object.entries(args).filter(([k, v]) => isTerm(k) && shown(v));
    if (terms.length) {
      // Where each term started, when the workspace knows (D-141): today's agreement, the
      // other side's ask, and which way this offer moves from today.
      const withStart = started.size > 0;
      all.append(el("h5", "approval-section", "Terms in this message"));
      const table = el("table", "approval-table");
      const headRow = el("tr");
      headRow.append(
        el("th", null, "Term"),
        // Column titles in the workspace's own words; "Today" and "Asked" if it gives none.
        ...(withStart ? [el("th", null, d.context_labels?.current ?? "Today"), el("th", null, d.context_labels?.asked ?? "Asked")] : []),
        el("th", null, "We offer"),
        el("th", null, "Decided by"),
      );
      table.append(el("thead"), el("tbody"));
      table.tHead.append(headRow);
      const arrow = { up: ["↑", "Up from today"], down: ["↓", "Down from today"], same: ["=", "Same as today"] };
      for (const [k, v] of terms) {
        const s0 = started.get(k);
        const tr = el("tr", owner.get(k) === d.approver ? "is-mine" : "");
        const unit = { pct: "%", days: " days", months: " months" }[k.match(/_(pct|days|months)$/)?.[1]] ?? "";
        const termCell = el("td");
        termCell.append(el("span", "approval-term-name", k.replace(/_(pct|days|months)$/, "").replaceAll("_", " ")), ...(s0?.ref ? [el("span", "approval-ref", s0.ref)] : []));
        const offerCell = el("td", "approval-num");
        offerCell.append(s0?.offered ?? `${v}${unit}`);
        if (s0?.change && arrow[s0.change]) {
          const [mark, words] = arrow[s0.change];
          const tag = el("span", `approval-change is-${s0.change}`, mark);
          tag.title = words;
          tag.setAttribute("aria-label", words);
          offerCell.append(tag);
        }
        tr.append(
          termCell,
          ...(withStart ? [el("td", "approval-was", s0?.current ?? "—"), el("td", "approval-was", s0?.asked ?? "—")] : []),
          offerCell,
          // No rule on it: within what the sender may offer, so no one else decides.
          el("td", null, owner.get(k) === d.approver ? `${owner.get(k)} · this step` : owner.get(k) ?? "Within limits"),
        );
        table.tBodies[0].append(tr);
      }
      all.append(table);
    }
    if (!all.children.length) {
      // A tool that isn't a message: its arguments, plainly.
      all.append(facts(Object.entries(args).filter(([, v]) => shown(v)).map(([k, v]) => [k.replaceAll("_", " "), typeof v === "string" ? v : JSON.stringify(v)])));
    }
    card.append(head, focus, ...((d.chain ?? []).length > 1 ? [chain] : []), all, hand, field, buttons);
    if (d.approver) card.append(el("p", "approval-demo", "Role-played: the server checks your role. This project has no logins."));
    card.chainNode = chain.children[d.step - 1]?.querySelector(".chain-node");
  }
  row.li.append(card);
  // Show what you act on (your report): the next card is taller than the screen, and scrolling
  // to its top hid the buttons. Centre the buttons, or the "Switch to" box, after refresh().
  const showActions = () => {
    const target = asking || buttons.hidden === false ? buttons : hand;
    requestAnimationFrame(() => reveal(target, { block: "center", behavior: "smooth" }));
  };
  announce(asking ? "The agent has a question for you" : `${d.name} is waiting for ${role}`);

  // Who may answer (D-137): someone with the card's role. Anyone else is told who to switch to.
  function refresh() {
    if (asking || !d.approver || !people().length) return;
    const me = currentPerson();
    const mayAnswer = me?.role === d.approver;
    buttons.hidden = field.hidden = !mayAnswer;
    approve.textContent = `Approve as ${me?.name ?? d.approver}`;
    hand.replaceChildren();
    hand.hidden = mayAnswer;
    if (mayAnswer) return;
    hand.append(el("p", "handoff-text", `You are acting as ${roleOf(me)}. This one needs the ${d.approver}.`));
    for (const p of people().filter((x) => x.role === d.approver)) {
      const sw = el("button", "handoff-switch", `Switch to ${roleOf(p)}`);
      sw.type = "button";
      sw.addEventListener("click", () => {
        setPerson(p.id);
        showActions(); // after the switch, the Approve button is where you look
      });
      hand.append(sw);
    }
  }
  pendingCards.add(refresh);
  refresh();
  showActions();

  // A countdown to the time-out: no answer in time counts as no.
  const ends = Date.now() + (d.timeout_s ?? 0) * 1000;
  const tick = d.timeout_s
    ? setInterval(() => {
        const left = Math.max(0, Math.round((ends - Date.now()) / 1000));
        countdown.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} left`;
      }, 1000)
    : null;
  if (d.timeout_s) countdown.textContent = `${Math.floor(d.timeout_s / 60)}:${String(d.timeout_s % 60).padStart(2, "0")} left`;

  async function answer(approved) {
    if (TOUR) return; // the tour sends nothing: its decisions are in the recorded run
    approve.disabled = reject.disabled = field.disabled = true;
    const said = field.value.trim();
    if (asking && approved && !said) {
      approve.disabled = reject.disabled = field.disabled = false;
      field.focus();
      return;
    }
    try {
      const response = await fetch("/api/approval", {
        method: "POST",
        headers: { ...PAGE_HEADER, "Content-Type": "application/json" },
        body: JSON.stringify({
          call_id: d.call_id,
          approved,
          note: asking ? (approved ? said : "skipped") : approved ? "" : said || "rejected on the page",
          person: currentPerson()?.id ?? null,
        }),
      });
      if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    } catch (error) {
      approve.disabled = reject.disabled = field.disabled = false;
      card.append(el("p", "approval-error", `Couldn't send your answer: ${error.message}`));
    }
  }
  approve.addEventListener("click", () => answer(true));
  reject.addEventListener("click", () => answer(false));

  return {
    decided(result) {
      if (tick) clearInterval(tick);
      pendingCards.delete(refresh);
      if (handoff) setPerson(null); // the hand-off ends with the approval
      hand.remove();
      buttons.remove();
      field.remove();
      countdown.remove();
      card.querySelector(".approval-demo")?.remove();
      const noAnswer = result.note === "no answer in time";
      const label = asking
        ? result.approved
          ? "✓ You answered"
          : "✗ Skipped"
        : result.approved
          ? `✓ Approved by ${result.person || role}`
          : `✗ ${noAnswer ? `No answer from ${role}` : `Rejected by ${result.person || role}`}`;
      setActivity(row, { text: `${label} · ${d.name}`, state: result.approved ? "done" : "error" });
      card.classList.add(result.approved ? "approved" : "rejected");
      if (card.chainNode) {
        card.chainNode.textContent = result.approved ? "✓" : "✗";
        card.chainNode.parentElement.className = `chain-step is-${result.approved ? "done" : "stopped"}`;
      }
      if (asking && result.approved) card.append(el("p", "approval-result", result.note));
      if (!asking && !result.approved) {
        card.append(el("p", "approval-result", `${result.note || "Rejected"}`), el("p", "approval-nothing", "Nothing ran. The agent has been told why."));
      }
    },
  };
}

// A file a tool saved: name and place on the card, the text when opened (D-53).
// A saved file that starts with mail headers (From, To, Date, Subject) is shown as the email
// that went out. Generic: the page knows mail's shape, not any workspace (your request).
const MAIL_HEADER = /^(from|to|cc|date|subject):\s*(.*)$/i;

function parseEmail(text) {
  const lines = text.split("\n");
  const headers = {};
  let i = 0;
  for (; i < lines.length; i++) {
    const m = lines[i].match(MAIL_HEADER);
    if (!m) break;
    headers[m[1].toLowerCase()] = m[2].trim();
  }
  if (!headers.to || !headers.subject) return null;
  // Trailing blocks like "Offered terms:" + a list, or a "(note)", are the email's record, not
  // its body: they go in a footer.
  const blocks = lines.slice(i).join("\n").trim().split(/\n\s*\n/);
  const footer = [];
  while (blocks.length > 1) {
    const b = blocks.at(-1).trim().split("\n");
    const section = b.length > 1 && /:\s*$/.test(b[0]) && b.slice(1).every((l) => /^\s*[-*•]\s/.test(l));
    const note = b.length === 1 && /^\(.*\)$/.test(b[0]);
    if (!section && !note) break;
    footer.unshift(section ? { title: b[0].replace(/:\s*$/, ""), items: b.slice(1).map((l) => l.replace(/^\s*[-*•]\s+/, "")) } : { note: b[0].slice(1, -1) });
    blocks.pop();
  }
  return { headers, body: blocks.join("\n\n"), footer };
}

// "Acme <A-17>" → name "Acme", address "A-17".
function mailPerson(value) {
  const m = value.match(/^\s*(.*?)\s*<([^>]+)>\s*$/);
  return m ? { name: m[1] || m[2], address: m[2] } : { name: value, address: "" };
}

function emailCard(d, mail) {
  const sent = d.folder === "outbox"; // the outbox is what went; a task file is a draft (D-164)
  const card = el("details", `file-card email-card folder-${d.folder}`);
  card.open = true; // the email is the outcome: show it
  const to = mailPerson(mail.headers.to);
  const summary = el("summary");
  summary.append(el("span", `email-badge${sent ? "" : " is-draft"}`, sent ? "✉ Sent" : "✎ Draft"), el("span", "file-name", mail.headers.subject), el("span", "file-where", `to ${to.name}`), fromTemplate("tpl-chevron"));
  const head = el("div", "email-head");
  const from = mailPerson(mail.headers.from ?? "");
  const avatar = el("span", "email-avatar", (from.name || "?").trim().charAt(0).toUpperCase());
  const who = el("div", "email-who");
  const fromLine = el("div", "email-from");
  fromLine.append(el("strong", null, from.name || "Unknown sender"), ...(from.address ? [el("span", "email-addr", `<${from.address}>`)] : []));
  const toLine = el("div", "email-to");
  toLine.append(el("span", "email-key", "To"), el("span", null, to.name), ...(to.address ? [el("span", "email-addr", `<${to.address}>`)] : []));
  who.append(fromLine, toLine);
  head.append(avatar, who, el("time", "email-date", mail.headers.date ?? ""));
  const subject = el("h4", "email-subject", mail.headers.subject);
  const body = el("div", "email-body");
  renderProse(body, mail.body);
  const parts = [subject, head, body];
  if (mail.footer.length) {
    const foot = el("div", "email-foot");
    for (const f of mail.footer) {
      if (f.note) {
        foot.append(el("p", "email-note", f.note));
        continue;
      }
      const row = el("div", "email-record");
      const chips = el("div", "email-chips");
      chips.append(...f.items.map((x) => el("span", "email-chip", x)));
      row.append(el("span", "email-key", f.title), chips);
      foot.append(row);
    }
    parts.push(foot);
  }
  const sheet = el("div", "email-sheet");
  sheet.append(...parts);
  const where = el("p", "email-where", sent ? `Saved as ${d.path}` : `Draft, not sent · ${d.path}`);
  card.append(summary, sheet, where);
  return card;
}

function fileCard(d) {
  // Mail headers in the outbox or a task file: an email card, sent or draft (D-164).
  const mail = d.folder === "outbox" || d.folder === "tasks" ? parseEmail(d.text) : null;
  if (mail) return emailCard(d, mail);
  const card = el("details", `file-card folder-${d.folder}`);
  const summary = el("summary");
  const where = d.folder === "outbox" ? "Sent · outbox" : "Draft";
  const name = el("span", "file-name", d.path.split("/").pop());
  summary.append(fromTemplate("tpl-file"), name, el("span", "file-where", `${where} · ${d.path}`), fromTemplate("tpl-chevron"));
  const body = el("div", "file-body");
  renderProse(body, d.text);
  card.append(summary, body);
  return card;
}

async function runTask(event) {
  event.preventDefault();
  const input = $("task");
  const task = input.value.trim();
  const send = $("send");
  if (!task || send.disabled) return;
  send.disabled = true;
  $("empty-state").hidden = true;
  input.value = "";
  const turn = newTurn(task);
  announce("Working on it");
  let freed = false;
  const free = () => {
    if (freed) return;
    freed = true;
    send.disabled = false;
    input.focus();
    refreshWork(); // task counts and times
  };
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { ...PAGE_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify({ task, model: $("model").value, effort: $("effort").value || null, profile: currentProfile(), person: currentPerson()?.id ?? null, off: currentOff(), session: currentSession }),
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    for await (const ev of readLines(response)) {
      onEvent(ev, turn);
      // The answer is in: you may ask again while the online evals score it (D-148).
      if (ev.type === "run_finished" && !ev.data.agent_id) free();
    }
  } catch (error) {
    turn.stats.classList.remove("working");
    turn.stats.textContent = "";
    turn.foot.textContent = `✗ ${error.message}`;
    turn.foot.className = "run-foot failed";
    announce(`Failed: ${error.message}`);
  } finally {
    free();
    if (paneInfo) loadPane(); // a fact the agent just saved shows at once
  }
}

// ── Harness pane (S04): the harness parts, for this profile, with switches ──
// Built from GET /api/harness, the same code a run uses (D-68). A switch can only take
// something away, and the run request says what (D-70). Switch state is kept per
// workspace + profile in this browser (D-71).
let paneInfo = null;
const offKey = () => `off:${health.workspace.name}:${currentProfile() ?? ""}`;
const PANE_OPEN = "pane-open";

function readOff() {
  try {
    const saved = JSON.parse(localStorage.getItem(offKey()) ?? "{}");
    return { tools: saved.tools ?? [], skills: saved.skills ?? [], subagents: saved.subagents ?? [], checks: saved.checks ?? [] };
  } catch {
    return { tools: [], skills: [], subagents: [], checks: [] };
  }
}

function saveOff(off) {
  try {
    localStorage.setItem(offKey(), JSON.stringify(off));
  } catch {
    // Storage blocked: the switches still apply to this page.
  }
}

// Only names this profile actually has: an old saved name never reaches the server.
function currentOff() {
  if (!paneInfo) return { tools: [], skills: [], subagents: [], checks: [] };
  const off = readOff();
  const has = {
    tools: [...paneInfo.tools.map((t) => t.name), ...(paneInfo.harness_tools ?? []).map((t) => t.name)],
    checks: [...(paneInfo.verify?.checks ?? []), ...(paneInfo.verify?.action_checks ?? [])].map((c) => c.name),
    skills: paneInfo.skills.map((s) => s.name),
    subagents: paneInfo.subagents.map((a) => a.name),
  };
  return Object.fromEntries(Object.entries(off).map(([kind, names]) => [kind, names.filter((n) => has[kind].includes(n))]));
}

const offCount = (off) => off.tools.length + off.skills.length + off.subagents.length + off.checks.length;

function setPaneOpen(open, remember = true) {
  $("harness-pane").hidden = !open;
  $("lane-right").hidden = !open;
  $("pane-toggle").hidden = open || !health?.workspace;
  $("pane-toggle").setAttribute("aria-expanded", String(open));
  if (remember) {
    try {
      localStorage.setItem(PANE_OPEN, open ? "1" : "0");
    } catch {
      // Storage blocked: the pane just won't remember.
    }
  }
}

function setUpPane() {
  if (!health?.workspace) return;
  let saved = null;
  try {
    saved = localStorage.getItem(PANE_OPEN);
  } catch {
    // Storage blocked: decide by screen width.
  }
  setPaneOpen(saved === null ? matchMedia("(min-width: 1100px)").matches : saved === "1", false);
  loadPane();
}

async function loadPane() {
  const profile = currentProfile();
  const query = profile ? `?profile=${encodeURIComponent(profile)}` : "";
  try {
    const response = await fetch(`/api/harness${query}`);
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    paneInfo = await response.json();
  } catch (error) {
    $("pane-body").replaceChildren(el("p", "pane-error", `Couldn't load the harness: ${error.message}`));
    return;
  }
  renderPane();
}

// One switch. Checked = on. Native switch semantics, styled the same in every browser.
function switchFor(kind, name) {
  const label = el("label", "switch-wrap");
  const input = el("input", "switch");
  input.type = "checkbox";
  input.setAttribute("switch", "");
  input.setAttribute("role", "switch");
  input.checked = !readOff()[kind].includes(name);
  // A tour, or a visitor to the hosted copy, sees each switch but can't change it (your review).
  input.addEventListener("click", (event) => {
    if (document.body.matches(".tour-mode, .public-mode:not(.owner-mode)")) event.preventDefault();
  });
  input.addEventListener("change", () => {
    const off = readOff();
    off[kind] = input.checked ? off[kind].filter((n) => n !== name) : [...new Set([...off[kind], name])];
    saveOff(off);
    if (paneInfo) renderPane();
    if (!$("view-online").hidden) loadOnline(); // its switches live on the Online Evals page
  });
  label.append(input, el("span", "visually-hidden", `Use ${name}`));
  return label;
}

// A line you can open: name and tags on top, the details below.
function paneItem({ kind, name, id, tags = [], detail, off, locked = false }) {
  const li = el("li", `pane-item${locked ? " is-locked" : off ? " is-off" : ""}`);
  const details = el("details");
  const summary = el("summary");
  summary.append(el("span", "item-name", name), ...tags, fromTemplate("tpl-chevron"));
  details.append(summary, detail);
  // A locked item is a permission (S05), not a switch: nothing to turn on here.
  li.append(kind && !locked ? switchFor(kind, id ?? name) : el("span", "switch-spacer"));
  li.append(details);
  return li;
}

// A sub-heading inside a part: a plain title, and a quiet note on the right.
function subhead(title, note) {
  const head = el("div", "pane-sub");
  head.append(el("span", "sub-title", title), el("span", "sub-note", note));
  return head;
}

function facts(rows) {
  const dl = el("dl", "facts");
  dl.append(...rows.flatMap(([k, v]) => [el("dt", null, k), el("dd", null, v)]));
  return dl;
}

function paneSection(part, title, summaryText, body, open = false) {
  const section = el("details", `pane-part part-${part}`);
  section.open = open;
  const summary = el("summary");
  summary.append(el("span", "part-dot"), el("span", "part-title", title), el("span", "part-sum", summaryText), fromTemplate("tpl-chevron"));
  section.append(summary, ...body);
  return section;
}

function renderPane() {
  const info = paneInfo;
  const off = currentOff();
  const n = offCount(off);
  $("pane-reset").hidden = n === 0;
  $("off-chip").hidden = n === 0;
  $("off-chip").textContent = `${n} off`;

  // Context: what is in the prompt on every call, and the skills it can load.
  const files = el("ul", "pane-list");
  files.append(
    ...info.context.files.map((f) => {
      const li = el("li", "pane-file");
      li.append(el("span", "item-name", f.path), el("span", "sub-note", `~${f.tokens} tokens`));
      return li;
    }),
  );
  const fileTokens = info.context.files.reduce((sum, f) => sum + f.tokens, 0);
  const skills = el("ul", "pane-list");
  skills.append(
    ...info.skills.map((s) =>
      paneItem({
        kind: "skills",
        name: s.name,
        off: off.skills.includes(s.name),
        detail: facts([["Description", s.description], ["Source", s.source]]),
      }),
    ),
  );
  const context = paneSection("context", "Context", `${plural(info.context.files.length, "file")} · ${plural(info.skills.length, "skill")} · ~${info.context.prompt_tokens} tokens`, [
    subhead("System instructions", `always loaded · ~${fileTokens} tokens`),
    files,
    subhead("Skills", "progressive disclosure · loaded when relevant"),
    skills,
    // Keeping the context small inside one conversation: pruning and summarizing (S07).
    ...(info.memory.trimming
      ? [
          subhead("Context management", "keeps each call small"),
          facts([
            ["Window", `${info.memory.trimming.window.toLocaleString()} tokens per call`],
            ["Past " + Math.round(info.memory.trimming.prune_at * 100) + "%", `prune: old tool results become one-line stubs (the newest ${info.memory.trimming.keep_recent} stay whole)`],
            ["Past " + Math.round(info.memory.trimming.summarize_at * 100) + "%", "summarize: older tasks are folded into a short summary"],
          ]),
        ]
      : []),
  ]);

  // Tools: what the agent can do, with each tool's risk; helpers are tools too.
  const tools = el("ul", "pane-list");
  tools.append(
    ...info.tools.map((t) => {
      const tags = [el("span", `act-risk risk-${t.risk}`, t.risk)];
      if (t.source === "built-in") tags.push(el("span", "pane-tag", "built-in"));
      if (t.delegate_only) tags.push(el("span", "pane-tag", "helper only"));
      const locked = info.guardrails.not_allowed.includes(t.name);
      if (locked) tags.push(el("span", "pane-tag", `not for ${info.guardrails.profile}`));
      const params = Object.entries(t.parameters?.properties ?? {}).map(([k, v]) => `${k}: ${v.type}${v.enum ? ` (${v.enum.join(", ")})` : ""}`);
      return paneItem({
        kind: "tools",
        name: t.name,
        tags,
        locked,
        off: off.tools.includes(t.name),
        // Docstrings wrap at 100 characters; show them as one flowing paragraph.
        detail: facts([["Description", t.description.replace(/\s*\n\s*/g, " ")], ["Parameters", params.join("\n") || "none"]]),
      });
    }),
  );
  const helpers = el("ul", "pane-list");
  helpers.append(
    ...info.subagents.map((a) =>
      paneItem({
        kind: "subagents",
        name: a.name,
        // On a Claude run every helper uses the small Claude model (D-103).
        tags: [el("span", "pane-tag", ($("model").value || "").startsWith("claude-") && health.claude_small_model ? modelLabel(health.claude_small_model) : a.model ? modelLabel(a.model) : "same model")],
        off: off.subagents.includes(a.name),
        detail: facts([
          ["Does", a.description],
          ["Tools", a.tools.join(", ")],
          ["Returns", `at most ${a.max_words} words`],
          ["Instructions", a.source],
        ]),
      }),
    ),
  );
  // The harness's own tools (S11): the model sees them like any other, and each can be
  // switched off for a run (each line says what that means).
  const own = el("ul", "pane-list");
  own.append(
    ...(info.harness_tools ?? []).map((t) =>
      paneItem({
        kind: "tools",
        name: t.name,
        tags: [el("span", `act-risk risk-${t.risk}`, t.risk), el("span", "pane-tag", "built-in")],
        off: off.tools.includes(t.name),
        detail: facts([["Description", t.description.replace(/\s*\n\s*/g, " ")], ["When off", t.when_off]]),
      }),
    ),
  );
  // Local: functions running inside the harness. Remote: tools on other servers (MCP).
  const remote = info.remote_tools ?? [];
  const toolBody = [
    subhead("Local tools", "run inside the harness"),
    tools,
    ...(own.children.length ? [subhead("Harness tools", "added by the harness")] : []),
    ...(own.children.length ? [own] : []),
    subhead("Remote tools", "MCP"),
    remote.length ? el("p", "pane-note", remote.join(", ")) : el("p", "pane-note", "None connected"),
  ];
  if (info.subagents.length) toolBody.push(subhead("Sub-agents", "own context · read-only"), helpers);
  const toolsSection = paneSection("tools", "Tools", `${plural(info.tools.length, "tool")}${own.children.length ? ` + ${own.children.length} harness` : ""}${info.subagents.length ? ` · ${plural(info.subagents.length, "sub-agent")}` : ""}`, toolBody);

  // Memory (S07): short-term is the conversation; long-term is facts kept across them.
  const m = info.memory;
  const who = info.guardrails.profile;
  const factList = el("ul", "note-list");
  factList.append(...m.notes.slice(0, 3).map((n) => el("li", null, factText(n))));
  const seeAll = el("a", "pane-link", m.notes.length > 3 ? `See all ${m.notes.length} facts` : "Open Memory");
  seeAll.href = "#memory";
  const memory = paneSection("memory", "Memory", m.notes_on ? `${plural(m.notes.length, "fact")} kept` : "this conversation only", [
    subhead("Short-term", "this conversation"),
    el("p", "pane-note", "Each task resends the conversation so far, so the agent remembers it. Open one from Chats to carry on."),
    subhead("Long-term", "facts across conversations"),
    !m.notes_on
      ? el("p", "pane-note", "This agent doesn't keep facts between conversations.")
      : m.notes.length
        ? factList
        : el("p", "pane-note", `No facts saved for ${who} yet. The agent saves one when it learns something worth keeping.`),
    ...(m.notes_on ? [seeAll] : []),
  ]);

  // Guardrails (S05): three colour-coded cards, one short line per rule. Details on hover.
  const g = info.guardrails;
  const chips = (items, kind) => {
    const box = el("div", "chips");
    box.append(...items.map((item) => el("span", `chip chip-${kind}`, item)));
    return box;
  };
  const section = (because) => because.match(/§\d+/)?.[0] ?? because;
  // One rule: its words, an optional § badge on the right, and the full reason on hover.
  const line = (text, because, hover) => {
    const li = el("li");
    li.append(el("span", "limit-label", text));
    if (because) li.append(el("span", "limit-badge", section(because)));
    li.title = hover ?? because ?? "";
    return li;
  };
  const list = (items) => {
    const ul = el("ul", "guard-limits");
    ul.append(...items);
    return ul;
  };
  const card = (tone, icon, title, note, body) => {
    const box = el("section", `guard-card tone-${tone}`);
    const head = el("header", "guard-head");
    head.append(el("span", "guard-icon", icon), el("span", "guard-title", title), el("span", "guard-note", note));
    box.append(head, ...body);
    return box;
  };
  const allowedCard = card("ok", "✓", "Allowed", g.profile, [
    chips(g.allowed, "ok"),
    el("p", "guard-text", `Writes only to ${g.writes.map((w) => w.split("/")[0] + "/").join(" · ")}`),
  ]);
  const notAllowedCard = card("no", "✕", "Not allowed", "always blocked", [
    list([
      ...(g.scope ? [line("Off-topic questions", "", `Only: ${g.scope.covers}${g.scope.knows ? ` Also in scope: ${g.scope.knows}.` : ""}`)] : []),
      ...g.not_allowed.map((t) => line(`Using ${t}`, "", `${g.profile} can't use ${t}`)),
      ...(g.hidden_fields.length ? [line(`Seeing ${plural(g.hidden_fields.length, "field")}`, "", g.hidden_fields.join("\n"))] : []),
      ...g.never.map((r) => line(r.label, r.because)),
      line("Editing its own setup", "", g.protected.join("\n")),
    ]),
  ]);
  const pauseCard = card("pause", "⏸", "Human in the loop", "asks you first", [
    g.approvals.length
      ? list(g.approvals.map((a) => line(a.approver ? `${a.label} → ${a.approver}` : a.tool, a.because)))
      : el("p", "guard-text", `Not applicable for ${g.profile}`),
  ]);
  const guardBody = [allowedCard, notAllowedCard, pauseCard];
  if (people().length) {
    // Who may answer an approval (D-137): said plainly, with what is and isn't enforced.
    const me = currentPerson();
    guardBody.push(facts([["Identity", `Acting as ${roleOf(me)}. An approval is accepted only from a person with the card's role: the server checks it. People are role-played; there are no logins, so this shows who must decide, not who someone really is`]]));
  }
  // Say so plainly if an action this profile may use would run without a person.
  const asks = new Set(g.approvals.map((a) => a.tool));
  const unguarded = info.tools.filter((t) => t.risk === "action" && g.allowed.includes(t.name) && !asks.has(t.name));
  if (unguarded.length) guardBody.push(el("p", "pane-warn", `${plural(unguarded.length, "action")} run without asking anyone.`));
  const guard = paneSection("guard", "Guardrails", g.never.length || g.approvals.length ? `${plural(g.never.length, "hard limit")} · ${plural(g.approvals.length, "approval")}` : "read-only", guardBody);

  // Agentic loop: the brakes and the model, for the next run.
  const l = info.loop;
  // Plain words for anyone: what the loop does, when it stops. Raw values are in the trace.
  const time = l.max_seconds % 60 === 0 ? `${l.max_seconds / 60} minutes` : `${l.max_seconds} seconds`;
  const share = (x) => ({ 0.5: "half", 0.25: "a quarter" })[x] ?? `${x * 100}%`;
  const loopSection = paneSection("loop", "Agentic Loop", `${l.max_steps} steps · $${l.max_usd} · ${time}`, [
    facts([
      ["How it works", "Thinks, uses a tool, reads the result, and repeats until it has an answer"],
      // Picked per run in the chat box, so it follows the menu (with the Thinking level).
      ["Model", `${modelLabel($("model").value || health.model)} · Thinking: ${$("effort")?.selectedOptions[0]?.textContent.replace(/^Thinking:\s*/, "") || "Auto"}. You pick both in the chat box; each run can use a different one`],
      ["Small jobs", smallJobs(l.small_models ?? [])],
      ["Stops", `When it has an answer, or after ${l.max_steps} steps, $${l.max_usd} or ${time}, whichever comes first`],
      ["Helpers get", `Up to ${share(l.helper_slice.time)} the time left and ${share(l.helper_slice.money)} of the budget`],
      // Planning (S11): part of the loop, not a step before it.
      ...(info.verify?.plan_on
        ? [["Plans", off.tools.includes("write_plan") ? "Switched off: no to-do lists this run" : "For a task with 3 or more parts the agent keeps a to-do list (write_plan) and can't finish with items open; a simple question gets a direct answer"]]
        : []),
      // A fixed prompt keeps every request's start identical, which is what Gemini's
      // caching needs; cached input is billed at a lower price (pricing.toml).
      ["Prompt caching", "The prompt stays fixed for the whole run, so Gemini can cache it and charge less"],
    ]),
  ]);

  // Verification (S11): the checks an answer passes before you see it, run once the agent
  // has drafted its answer. Planning lives in the loop and its tool under Tools.
  const v = info.verify ?? { plan_on: false, checks: [], retries: 0 };
  const checkList = el("ul", "pane-list check-names");
  checkList.append(
    ...v.checks.map((c) =>
      paneItem({
        kind: "checks",
        name: c.label,
        id: c.name,
        tags: c.source === "built-in" ? [el("span", "pane-tag", "built-in")] : [],
        off: off.checks.includes(c.name),
        detail: facts([["Passes when", c.description], ["Kind", "Plain code: free, exact, the same every time"]]),
      }),
    ),
  );
  const actionList = el("ul", "pane-list check-names");
  actionList.append(
    ...(v.action_checks ?? []).map((c) =>
      paneItem({
        kind: "checks",
        name: c.label,
        id: c.name,
        tags: [el("span", "pane-tag", `before ${c.tool}`)],
        off: off.checks.includes(c.name),
        detail: facts([["Passes when", c.description], ["On a failure", "The call is stopped and goes back to the agent; no one is asked to approve it"]]),
      }),
    ),
  );
  const nAll = v.checks.length + (v.action_checks ?? []).length;
  const verifySection = paneSection("verify", "Verification", `${plural(nAll, "check")} · ${plural(v.retries, "retry", "retries")}`, [
    ...(actionList.children.length ? [subhead("Before an action", "after the hard limits, before anyone is asked"), actionList] : []),
    subhead("Checks", "after the draft, before you see it"),
    checkList,
    facts([["On a failure", `The failures go back to the agent ${v.retries === 1 ? "once" : `up to ${v.retries} times`}; if it still fails, the answer is marked Not Verified`]]),
  ]);

  // Keep which sections you had open across re-renders.
  const wasOpen = new Map([...$("pane-body").querySelectorAll(".pane-part")].map((d) => [d.className, d.open]));
  // The order of one run, and of the docs: the loop is the core; context and tools are
  // what it works with; guardrails gate the tools; memory is kept at the end (D-67).
  // Run order (D-67): the loop, what it works with, what gates the tools, the check on the
  // answer at the end (S11), then what is kept.
  const sections = [loopSection, context, toolsSection, guard, ...(v.checks.length ? [verifySection] : []), memory];
  for (const s of sections) if (wasOpen.has(s.className)) s.open = wasOpen.get(s.className);
  $("pane-body").replaceChildren(...sections);
}

// Who does the small jobs (helpers, the off-topic check, titles, summaries) for the model
// picked now: Claude Haiku on a Claude run (D-103), else the workspace's small model.
function smallJobs(gemini) {
  const claude = ($("model").value || "").startsWith("claude-") && health.claude_small_model;
  const names = claude ? [modelLabel(health.claude_small_model)] : gemini.map(modelLabel);
  return `${names.join(", ") || "the same model"}: the helper, the off-topic check, titles and summaries`;
}

function resetOff() {
  saveOff({ tools: [], skills: [], subagents: [], checks: [] });
  renderPane();
}

// ── Wiring ──────────────────────────────────────────────────────────────────
$("run-checks").addEventListener("click", runChecks);
$("composer").addEventListener("submit", runTask);
$("task").addEventListener("keydown", (event) => {
  // Enter sends; Shift+Enter adds a new line.
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    $("composer").requestSubmit();
  }
});
$("model").addEventListener("change", () => {
  try {
    localStorage.setItem(MODEL_KEY, $("model").value);
  } catch {
    // Storage blocked: the pick still applies to this page, it just isn't remembered.
  }
});
$("new-task").addEventListener("click", newConversation);
$("effort").addEventListener("change", () => {
  try {
    localStorage.setItem(EFFORT_KEY, $("effort").value);
  } catch {
    // Storage blocked: the pick still applies to this page.
  }
});
$("profile").addEventListener("change", switchProfile);
$("model").addEventListener("change", () => paneInfo && renderPane());
$("effort").addEventListener("change", () => paneInfo && renderPane());
$("pane-toggle").addEventListener("click", () => setPaneOpen(true));
$("pane-close").addEventListener("click", () => setPaneOpen(false));
$("off-chip").addEventListener("click", () => setPaneOpen(true));
$("pane-reset").addEventListener("click", resetOff);
addEventListener("hashchange", showView);
showView();
loadHealth();

// ── Lane widths: drag the sidebar's or the Harness pane's edge (keys work too) ──
// Saved per browser; double-click a handle to go back to the default width.
const LANES = {
  left: { handle: "lane-left", prop: "--left", min: 200, max: 440, start: 240 },
  right: { handle: "lane-right", prop: "--right", min: 280, max: 680, start: 340 },
};

function setLane(side, px, remember = true) {
  const lane = LANES[side];
  const width = Math.round(Math.min(lane.max, Math.max(lane.min, px)));
  document.body.style.setProperty(lane.prop, `${width}px`);
  const handle = $(lane.handle);
  handle.setAttribute("aria-valuemin", lane.min);
  handle.setAttribute("aria-valuemax", lane.max);
  handle.setAttribute("aria-valuenow", width);
  if (remember) {
    try {
      localStorage.setItem(`lane:${side}`, String(width));
    } catch {
      // Storage blocked: the width holds for this page only.
    }
  }
}

for (const [side, lane] of Object.entries(LANES)) {
  let saved = null;
  try {
    saved = Number(localStorage.getItem(`lane:${side}`)) || null;
  } catch {
    // Storage blocked: start from the default.
  }
  setLane(side, saved ?? lane.start, false);
  const handle = $(lane.handle);
  // The new width from the pointer: the left lane grows rightwards, the right lane leftwards.
  const widthAt = (x) => (side === "left" ? x : document.documentElement.clientWidth - x);
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    handle.classList.add("active");
    document.body.classList.add("resizing");
  });
  handle.addEventListener("pointermove", (event) => {
    if (handle.hasPointerCapture(event.pointerId)) setLane(side, widthAt(event.clientX), false);
  });
  const stop = (event) => {
    if (!handle.hasPointerCapture(event.pointerId)) return;
    handle.releasePointerCapture(event.pointerId);
    handle.classList.remove("active");
    document.body.classList.remove("resizing");
    setLane(side, widthAt(event.clientX));
  };
  handle.addEventListener("pointerup", stop);
  handle.addEventListener("pointercancel", stop);
  handle.addEventListener("dblclick", () => setLane(side, lane.start));
  handle.addEventListener("keydown", (event) => {
    const now = Number(handle.getAttribute("aria-valuenow"));
    const step = event.shiftKey ? 48 : 16;
    // Arrow keys move the edge the way it points: on the right lane, Left makes it wider.
    const grow = side === "left" ? 1 : -1;
    const moves = { ArrowLeft: -step * grow, ArrowRight: step * grow, Home: lane.min - now, End: lane.max - now };
    if (!(event.key in moves)) return;
    event.preventDefault();
    setLane(side, now + moves[event.key]);
  });
}

// ── Memory view (left lane): long-term facts, per profile, with Forget ─────────
// "- 2026-11-10 · text" → the text; the date shows apart.
const factText = (line) => line.replace(/^- \d{4}-\d{2}-\d{2} · /, "").replace(/^- /, "");
const factDate = (line) => line.match(/^- (\d{4}-\d{2}-\d{2})/)?.[1] ?? "";

// ── Online Evals page (D-148): every scored answer of this profile, newest first ──
// The judge's On/Off switch (D-167): the server keeps it; the page only shows and changes it.
function showJudge(on) {
  const input = $("online-judge");
  input.disabled = false;
  input.checked = on === true;
  $("online-judge-state").textContent = input.checked ? "On" : "Off";
}

$("online-judge").addEventListener("change", async (event) => {
  const input = event.target;
  input.disabled = true;
  try {
    const response = await fetch("/api/online-evals/judge", {
      method: "POST",
      headers: { ...PAGE_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify({ on: input.checked }),
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    showJudge((await response.json()).judge_on);
    announce(`LLM as Judge ${input.checked ? "on" : "off"}`);
  } catch (error) {
    input.checked = !input.checked; // not saved: show what the server still has
    input.disabled = false;
    announce(`Couldn't change the judge: ${error.message}`);
  }
});

async function loadOnline() {
  const summary = $("online-summary");
  const answers = $("online-answers");
  let body;
  try {
    const response = await fetch(`/api/online-evals${withProfile()}`);
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    body = await response.json();
  } catch (error) {
    summary.replaceChildren(el("p", "memory-empty", `Couldn't load the online evals: ${error.message}`));
    answers.replaceChildren();
    return;
  }
  const rows = body.answers;
  showJudge(body.judge_on);
  if (!paneInfo) await loadPane(); // the metrics list and their switches come from the harness info
  if (!rows.length && !paneInfo?.online_evals) {
    summary.replaceChildren(el("p", "memory-empty", "No scored answers yet for this profile. Ask the agent something: each answer is scored after you see it."));
    answers.replaceChildren();
    return;
  }
  // Per metric: the mean score and how often it passed, over the answers it applied to.
  const metrics = new Map();
  for (const m of paneInfo?.online_evals?.metrics ?? []) metrics.set(m.name, { label: m.label, graded_by: m.graded_by, sum: 0, n: 0, passed: 0, scored: 0 });
  for (const a of rows) {
    for (const r of a.results ?? []) {
      const m = metrics.get(r.name) ?? { label: r.label, graded_by: r.graded_by, sum: 0, n: 0, passed: 0, scored: 0 };
      if (r.status === "passed" || r.status === "failed") {
        m.scored += 1;
        m.passed += r.status === "passed" ? 1 : 0;
        if (r.score != null) [m.sum, m.n] = [m.sum + r.score, m.n + 1];
      }
      metrics.set(r.name, m);
    }
  }
  const table = el("table", "evals-metrics online-metrics");
  const head = el("tr");
  for (const name of ["On", "Metric", "Graded By", "Reference", "Threshold", "Average", "Passed"]) {
    const th = el("th", null, name);
    th.scope = "col";
    head.append(th);
  }
  const thead = el("thead");
  thead.append(head);
  const tbody = el("tbody");
  for (const [id, m] of metrics) {
    const tr = el("tr");
    const on = el("td", "metric-on");
    on.append(switchFor("checks", id)); // off: not scored on the next answers of this profile
    tr.append(on);
    const name = el("th", "metric-name", m.label);
    name.scope = "row";
    const by = el("td", "metric-by");
    by.append(gradeChip(m.graded_by));
    const ok = m.scored && m.passed === m.scored;
    tr.append(name, by, referenceCell(false), thresholdCell(m.graded_by === "code" ? 1 : (paneInfo?.online_evals?.pass_at ?? 0.7)), el("td", "q-score", m.n ? (m.sum / m.n).toFixed(2) : "–"), el("td", `q-rate ${m.scored ? (ok ? "pass" : "fail") : ""}`, m.scored ? `${m.passed} of ${m.scored}` : "didn't apply"));
    tbody.append(tr);
  }
  table.append(thead, tbody);
  summary.replaceChildren(table);
  if (!rows.length) {
    answers.replaceChildren(el("p", "memory-empty", "No scored answers yet for this profile. Ask the agent something: each answer is scored after you see it."));
    return;
  }

  // One row per answer: the question, then each metric's score, coloured by its verdict.
  const names = [...metrics.keys()];
  const wrap = el("div", "online-scroll");
  const list = el("table", "online-table");
  const top = el("tr");
  for (const name of ["Question", ...names.map((n) => metrics.get(n).label), "When"]) {
    const th = el("th", null, name);
    th.scope = "col";
    top.append(th);
  }
  const lhead = el("thead");
  lhead.append(top);
  const lbody = el("tbody");
  for (const a of rows) {
    const tr = el("tr");
    const ask = el("th", "online-ask");
    ask.scope = "row";
    const open = el("button", "online-open", a.task);
    open.type = "button";
    open.title = `Open the conversation "${a.title}"`;
    open.addEventListener("click", () => {
      location.hash = "#agent";
      openSession(a.session);
    });
    ask.append(open);
    tr.append(ask);
    for (const n of names) {
      const r = (a.results ?? []).find((x) => x.name === n);
      const td = el("td");
      if (r) {
        td.append(el("span", `q-pill is-${r.status}`, r.status === "skipped" ? "–" : scoreText(r)));
        td.title = `${r.label}: ${r.reason}`;
      }
      tr.append(td);
    }
    tr.append(el("td", "online-when", new Date(a.at * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })));
    lbody.append(tr);
  }
  list.append(lhead, lbody);
  wrap.append(list);
  answers.replaceChildren(wrap);
}

async function loadFacts() {
  const grid = $("memory-grid");
  let body;
  try {
    const response = await fetch("/api/facts");
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    body = await response.json();
  } catch (error) {
    grid.replaceChildren(el("p", "memory-empty", `Couldn't load memory: ${error.message}`));
    return;
  }
  if (!body.on) {
    grid.replaceChildren(el("p", "memory-empty", "This agent doesn't keep facts between conversations."));
    return;
  }
  grid.replaceChildren(
    ...body.profiles.map((p) => {
      const card = el("section", "memory-card");
      const head = el("header", "memory-card-head");
      head.append(el("span", "pf-avatar memory-avatar", p.label.charAt(0).toUpperCase()), el("h2", null, p.label), el("span", "memory-count", plural(p.facts.length, "fact")));
      card.append(head);
      if (!p.facts.length) {
        card.append(el("p", "memory-empty", "Nothing saved yet."));
        return card;
      }
      const list = el("ul", "fact-list");
      // Newest first: what the agent learned most recently.
      for (const line of [...p.facts].reverse()) {
        const li = el("li", "fact");
        const forget = el("button", "fact-forget", "Forget");
        forget.type = "button";
        forget.setAttribute("aria-label", `Forget: ${factText(line)}`);
        forget.addEventListener("click", async () => {
          // Two clicks, no pop-up: the first asks, the second forgets.
          if (!forget.classList.contains("sure")) {
            forget.classList.add("sure");
            forget.textContent = "Forget?";
            setTimeout(() => {
              forget.classList.remove("sure");
              forget.textContent = "Forget";
            }, 3000);
            return;
          }
          const response = await fetch("/api/facts/forget", {
            method: "POST",
            headers: { ...PAGE_HEADER, "Content-Type": "application/json" },
            body: JSON.stringify({ profile: p.id, line }),
          });
          if (response.ok) {
            loadFacts();
            if (paneInfo) loadPane();
          }
        });
        li.append(el("span", "fact-text", factText(line)), el("span", "fact-date", factDate(line)), forget);
        list.append(li);
      }
      card.append(list);
      return card;
    }),
  );
}

// ── Evals view (S10): summary, metrics, cases, past evals, Run ───────────────
// The server only reads result files and starts one fixed command (D-113, D-115).

const duration = (s) => (s >= 60 ? `${Math.floor(s / 60)} m ${Math.round(s % 60)} s` : `${Math.round(s)} s`);
const metricInfo = (id) => evals.index?.catalog?.metrics?.[id] ?? { name: id, kind: "judge", threshold: 0 };
const STATUS = { passed: "Passed", failed: "Failed", incomplete: "Not Finished", running: "Running", waiting: "Waiting", notrun: "Not Run" };

async function loadEvals(select) {
  try {
    const response = await fetch("/api/evals");
    // 404 on the list itself: the page is newer than the server process (it predates S10).
    if (response.status === 404) throw new Error("the server is older than this page. Restart it.");
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    evals.index = await response.json();
  } catch (error) {
    showEvalProblem(`Couldn't load evals: ${error.message}`);
    $("evals-run").disabled = true; // nothing to start until the server can run evals
    return;
  }
  if (evals.index.has_cases && !evals.suite.length) {
    const plan = await fetch("/api/evals/plan").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (plan?.type === "plan") {
      evals.suite = plan.cases;
      evals.defaultJudge = plan.judge;
    }
  }
  setUpEvalPickers(evals.defaultJudge);
  refreshCost();
  // An eval is running but this page didn't start it (a reload, another tab): follow it.
  if (evals.index.running && !evals.running) watchEval(() => fetch("/api/evals/follow"));
  const id = select === null ? null : (select ?? evals.result?.id); // nothing chosen: the ready state
  evals.result = null;
  if (id) {
    const response = await fetch(`/api/evals/${encodeURIComponent(id)}`);
    if (response.ok) evals.result = await response.json();
  }
  $("evals-run").disabled = !evals.index.has_cases || evals.running || evals.index.running;
  renderEvals();
}

function renderEvals() {
  renderEvalSummary();
  renderMetrics();
  renderCases();
  renderEvalHistory();
}

function showEvalProblem(text) {
  $("evals-summary").replaceChildren(el("p", "evals-stopped", text));
}

// ── Summary: a hero anyone can read: a ring, one sentence, three numbers ─────
const SVG = "http://www.w3.org/2000/svg";

// A ring split into passed (green), failed (red) and not finished (grey).
// A ring with an optional caption and legend. Segments are drawn in order around it.
//   ready: no segments, the test count in the middle;
//   live: one blue arc, the share of tests done (never pass/fail colours mid-run);
//   result: green passed then red failed, "Pass Rate" under the number, and a legend.
function ringBlock({ segments = [], total, center, caption, legend = [] }) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 120 120");
  svg.setAttribute("class", "hero-ring");
  svg.setAttribute("aria-hidden", "true");
  const r = 52;
  const round = 2 * Math.PI * r;
  let start = 0;
  const circle = (cls) => {
    const c = document.createElementNS(SVG, "circle");
    c.setAttribute("cx", "60");
    c.setAttribute("cy", "60");
    c.setAttribute("r", String(r));
    c.setAttribute("class", cls);
    svg.append(c);
    return c;
  };
  circle("ring-track");
  for (const { count, cls } of segments) {
    if (!count || !total) continue; // a zero arc would still draw a round dot
    const len = (count / total) * round;
    const c = circle(cls);
    c.style.strokeDasharray = `${len} ${round}`;
    c.style.strokeDashoffset = `${-start}`;
    start += len;
  }
  const middle = document.createElementNS(SVG, "text");
  middle.setAttribute("x", "60");
  middle.setAttribute("y", caption ? "55" : "60");
  middle.setAttribute("class", "ring-pct");
  middle.textContent = center;
  svg.append(middle);
  if (caption) {
    const under = document.createElementNS(SVG, "text");
    under.setAttribute("x", "60");
    under.setAttribute("y", "77");
    under.setAttribute("class", "ring-caption");
    under.textContent = caption;
    svg.append(under);
  }
  const block = el("div", "hero-ring-block");
  block.append(svg);
  if (legend.length) {
    const list = el("ul", "ring-legend");
    for (const [count, label, cls] of legend) list.append(el("li", cls, `${count} ${label}`));
    block.append(list);
  }
  return block;
}

// A metric result's status. Results saved before D-118 have none: a judge error with no
// score was Not Scored, "nothing to grade" was Not Applicable.
function statusOf(m) {
  if (m.status) return m.status;
  if (m.score == null && m.error) return "not_scored";
  if (/no question-answer pairs|nothing to evaluate/i.test(m.reason ?? "")) return "not_applicable";
  return "scored";
}
const inCatalog = (id) => Boolean(evals.index?.catalog?.metrics?.[id]); // dropped metrics stay hidden

const metricCount = () => Object.keys(evals.index?.catalog?.metrics ?? {}).length || 11;

function tile(value, label, tone = "") {
  const t = el("div", `hero-tile ${tone}`);
  t.append(el("strong", null, value), el("span", null, label));
  return t;
}

// A stop reason in a few words; older results kept the raw error.
function plainStop(reason) {
  if (/429|quota/i.test(reason)) {
    const when = reason.match(/retry in (\d[\dhms.]*)/i)?.[1] ?? reason.match(/resets in (\d[\dhms.]*)/)?.[1];
    return `Gemini's free daily quota ran out${when ? ` (it resets in ${when})` : ""}, so some tests didn't finish.`;
  }
  if (/503|busy/i.test(reason)) return "Gemini was busy, so some tests didn't finish.";
  return reason;
}

// Results saved before D-116 have no "paid": all-Gemini ones cost the person nothing.
const usedClaude = (r) => [r.model, r.agent?.now, r.judge?.first, r.judge?.now].some((m) => m?.startsWith("claude-"));
const usdText = (usd) => (usd === 0 ? "$0" : usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`);

// Safety: the share of runs where every rule held (both guardrail metrics).
function safety(metrics) {
  const parts = ["guardrails", "guardrails_turns"].map((id) => metrics?.[id]).filter((m) => m?.runs);
  const runs = parts.reduce((n, m) => n + m.runs, 0);
  return runs ? parts.reduce((n, m) => n + m.passed, 0) / runs : null;
}

// "Gemini 3.8 Flash → Claude Haiku 5.5" when a model ran out mid-eval.
const modelPath = (first, now) => (now && now !== first ? `${modelLabel(first)} → ${modelLabel(now)}` : modelLabel(first));

// Who pays: Claude is paid; Gemini here runs on the free tier. Read from the models used.
function costLabel(models, paid) {
  const claude = models.some((m) => m?.startsWith("claude-"));
  const gemini = models.some((m) => m?.startsWith("gemini-"));
  if (claude && gemini) return paid ? "Cost · Claude Paid, Gemini Free Tier" : "Cost · Gemini Free Tier";
  return claude ? "Cost · Claude, Paid" : "Cost · Gemini Free Tier";
}

// The card: ring, words, tiles, and at the bottom the next run's model menus (the same
// two <select>s every time, moved in, so a menu keeps its state across re-renders).
function hero({ ring, kicker, headline, sub, tiles }) {
  const box = el("div", "evals-hero");
  const words = el("div", "hero-words");
  if (kicker) words.append(el("p", "hero-kicker", kicker));
  words.append(el("h2", "hero-headline", headline), el("p", "hero-sub", sub));
  const row = el("div", "hero-tiles");
  row.append(...tiles);
  words.append(row);
  const next = $("evals-next");
  for (const pick of next.querySelectorAll("select")) pick.disabled = Boolean(evals.live);
  box.append(ringBlock(ring), words, next);
  return box;
}

// Fill the two menus once: Gemini by default, so nothing paid runs unless picked (D-104).
function setUpEvalPickers(defaultJudge) {
  const models = health?.models ?? [];
  if (!models.length || $("evals-model").options.length) return;
  const gemini = (m) => m && !m.startsWith("claude-");
  fillModelPick($("evals-model"), models);
  fillModelPick($("evals-judge"), models);
  $("evals-model").value = [$("model").value, health?.model].find(gemini) ?? models.find(gemini) ?? models[0];
  $("evals-judge").value = models.includes(defaultJudge) ? defaultJudge : models.find(gemini) ?? models[0];
}

function renderEvalSummary() {
  const box = $("evals-summary");
  const live = evals.live;
  if (live) {
    const total = live.cases.length;
    const passed = live.cases.filter((c) => c.status === "passed").length;
    const failed = live.cases.filter((c) => c.status === "failed").length;
    const runs = live.cases.reduce((n, c) => n + c.done, 0);
    const s = safety(metricTotals());
    const all = total * live.runs;
    return void box.replaceChildren(
      hero({
        ring: {
          segments: [{ count: runs, cls: "ring-progress" }],
          total: all,
          center: `${Math.round((runs / Math.max(all, 1)) * 100)}%`,
          caption: "Done",
          legend: [
            [passed, "Passed", "pass"],
            [failed, "Failed", "fail"],
            [total - passed - failed, "To Go", "todo"],
          ],
        },
        headline: `Testing the agent… ${passed + failed} of ${total} tests done`,
        sub: `${runs} of ${all} runs finished. Each test is a conversation with a known right answer.`,
        kicker: "Running Now",
        tiles: [
          tile(`${passed + failed} / ${total}`, "Tests Completed"),
          tile(s == null ? "–" : `${Math.round(s * 100)}%`, "Safety Rules Held", s === 1 ? "good" : s == null ? "" : "bad"),
          tile(usdText(live.paid ?? 0), `${costLabel([live.agent, live.judge], live.paid)} · So Far`),
        ],
      }),
    );
  }
  if (!evals.index?.has_cases) return void box.replaceChildren(el("p", "evals-note", "No eval cases for this agent."));
  const r = evals.result;
  if (!r) {
    // Nothing run or opened yet: no verdict, just what a run will do.
    const single = evals.suite.filter((c) => c.turns.length === 1).length;
    const multi = evals.suite.length - single;
    const core = evals.suite.filter((c) => c.core).length;
    return void box.replaceChildren(
      hero({
        ring: { total: 0, center: String(evals.suite.length || "–"), caption: "Tests" },
        headline: `${evals.suite.length} Tests Ready to Run`,
        sub: `${single} single-turn and ${multi} multi-turn conversations with known right answers, each scored on ${metricCount()} metrics.`,
        tiles: [
          tile(String(evals.suite.length), "Tests"),
          tile(String(metricCount()), "Metrics"),
          tile(String(core), "Core Tests"),
        ],
      }),
    );
  }
  const { passed, failed, incomplete, cases } = r.summary;
  const s = safety(r.metrics);
  const paid = r.usd.paid ?? (usedClaude(r) ? r.usd.total : 0);
  const older = evals.index.results[evals.index.results.findIndex((x) => x.id === r.id) + 1];
  const change = older?.summary ? passed - older.summary.passed : 0;
  const headline =
    r.status === "stopped" && incomplete
      ? `Stopped early: ${passed} of ${cases} tests passed`
      : passed === cases
        ? `The agent passed all ${cases} tests`
        : `The agent passed ${passed} of ${cases} tests`;
  const agentFirst = r.agent?.first ?? r.model;
  const agentNow = r.agent?.now ?? r.model;
  const sub = [
    `${cases} conversations with known right answers, ${r.runs > 1 ? `each run ${r.runs} times (all must pass)` : "each run once"}. `,
    `Agent ${modelPath(agentFirst, agentNow)}, judged by ${modelPath(r.judge.first, r.judge.now)}.`,
    change ? ` ${change > 0 ? "▲" : "▼"} ${Math.abs(change)} since the eval before.` : "",
  ].join("");
  const models = [agentFirst, agentNow, r.judge.first, r.judge.now];
  box.replaceChildren(
    hero({
      ring: {
        segments: [
          { count: passed, cls: "ring-pass" },
          { count: failed, cls: "ring-fail" },
        ],
        total: cases,
        center: `${Math.round((passed / Math.max(cases, 1)) * 100)}%`,
        caption: "Pass Rate",
        legend: [
          [passed, "Passed", "pass"],
          [failed, "Failed", "fail"],
          ...(incomplete ? [[incomplete, "Not Finished", "todo"]] : []),
        ],
      },
      headline,
      sub,
      tiles: [
        tile(`${passed + failed} / ${cases}`, "Tests Completed", incomplete ? "" : "good"),
        tile(s == null ? "–" : `${Math.round(s * 100)}%`, "Safety Rules Held", s === 1 ? "good" : s == null ? "" : "bad"),
        tile(usdText(paid), costLabel(models, paid)),
        tile(duration(r.seconds), "Run Time"),
      ],
      kicker: `Eval of ${r.started}`,
    }),
  );
  // No banner for a stop: the headline says it; the reason is one hover away.
  if (r.status === "stopped") box.querySelector(".hero-headline").title = plainStop(r.stop_reason);
}

// ── Metrics: the 12 we score, in DeepEval's groups ───────────────────────────
// Per metric: the mean score and runs passed, from the saved result or the live eval.
function metricTotals() {
  if (!evals.live) return resultTotals(evals.result);
  const totals = {};
  for (const c of evals.live.cases) {
    for (const [id, m] of Object.entries(c.metrics)) {
      const t = (totals[id] ??= { sum: 0, scored: 0, passed: 0, runs: 0 });
      t.sum += m.sum;
      t.scored += m.scored;
      t.passed += m.passed;
      t.runs += m.runs;
    }
  }
  for (const t of Object.values(totals)) t.score = t.scored ? t.sum / t.scored : null;
  return totals;
}

// A saved eval's totals, worked out from its runs so every result (old or new) counts the
// same way: only real scores; Not Scored and Not Applicable are left out (D-118).
function resultTotals(result) {
  const totals = {};
  for (const c of result?.cases ?? []) {
    for (const run of c.runs) {
      for (const [id, m] of Object.entries(run.metrics)) {
        if (statusOf(m) !== "scored") continue;
        const t = (totals[id] ??= { sum: 0, scored: 0, passed: 0, runs: 0 });
        if (m.score != null) {
          t.sum += m.score;
          t.scored += 1;
        }
        t.passed += m.passed ? 1 : 0;
        t.runs += 1;
      }
    }
  }
  for (const t of Object.values(totals)) t.score = t.scored ? t.sum / t.scored : null;
  return totals;
}

function scoreCell(info, total) {
  const cell = el("td", "metric-score");
  if (!total?.runs) return cell.append(el("span", "score-none", "–")), cell;
  const ok = total.passed === total.runs;
  const line = el("div", `score-line ${ok ? "pass" : "fail"}`);
  const bar = el("span", "score-bar");
  const fill = el("span", "score-fill");
  fill.style.width = `${Math.round((total.score ?? (ok ? 1 : 0)) * 100)}%`;
  const mark = el("span", "score-mark"); // where the metric starts to pass
  mark.style.left = `${Math.round(info.threshold * 100)}%`;
  bar.append(fill, mark);
  line.append(
    el("span", "score-num", total.score == null ? (ok ? "✓" : "✗") : total.score.toFixed(2)),
    bar,
    el("span", "score-runs", `${total.passed}/${total.runs} passed`),
  );
  cell.title = `Passes at ${info.threshold}`;
  cell.append(line);
  return cell;
}

// Where a metric starts to pass (catalog.json): "≥ 0.70"; 1.0 means every check must hold.
// Reference-based: compared with the golden case's known answer. Reference-free: judged by
// rules or criteria alone, so it also works live, where no right answer is known.
function referenceCell(based) {
  const cell = el("td", "metric-by");
  cell.append(el("span", `ref-chip ${based ? "ref-based" : "ref-free"}`, based ? "Reference-based" : "Reference-free"));
  // Reference-based vs reference-free (D-161; DeepEval also says "referenceless").
  cell.title = based ? "Reference-based: compared with the test's known right answer (expected tools, outcome, reference answer)" : "Reference-free: judged by rules or criteria alone, no known answer needed";
  return cell;
}

function thresholdCell(at) {
  const n = Number(at);
  const cell = el("td", "metric-at", n >= 1 ? "1.00 · all" : `≥ ${n.toFixed(2)}`);
  cell.title = n >= 1 ? "Passes only with a perfect score: every check holds" : `Passes at a score of ${n.toFixed(2)} or more`;
  return cell;
}

function renderMetrics() {
  const table = $("evals-metrics");
  const catalog = evals.index?.catalog;
  if (!catalog) return void table.replaceChildren();
  const totals = metricTotals();
  const head = el("thead");
  const names = el("tr");
  for (const name of ["Metric", "What It Checks", "Graded By", "Reference", "Threshold", "Score"]) {
    const th = el("th", null, name);
    th.scope = "col";
    names.append(th);
  }
  head.append(names);
  const bodies = catalog.tables.map((group) => {
    const body = el("tbody");
    const title = el("tr", "metric-group");
    const th = el("th", null, `${group.title} · ${group.subtitle}`);
    th.scope = "colgroup";
    th.colSpan = 6;
    title.append(th);
    body.append(title);
    for (const row of group.rows) {
      for (const id of row.metrics) {
        const info = metricInfo(id);
        const tr = el("tr");
        const name = el("th", "metric-name", info.name);
        name.scope = "row";
        name.append(el("span", "metric-cat", row.name));
        const by = el("td", "metric-by");
        by.append(gradeChip(info.kind));
        const at = thresholdCell(info.threshold);
        if (info.decides === false) {
          at.append(el("span", "metric-reported", "Reported"));
          at.title = info.note ?? "Shown, but never fails a test";
        }
        tr.append(name, el("td", "metric-does", info.measures ?? ""), by, referenceCell(info.reference), at, scoreCell(info, totals[id]));
        body.append(tr);
      }
    }
    return body;
  });
  table.replaceChildren(head, ...bodies);
}

// ── Cases: one line each; open one to see what the agent did and why it scored so ──
// Every case in the suite: its result from the eval on show, or "Not run".
function caseRows() {
  if (evals.live) return evals.live.cases;
  const ran = new Map((evals.result?.cases ?? []).map((c) => [c.id, c]));
  const listed = evals.suite.length ? evals.suite : [...ran.values()];
  return listed.map((s) => {
    const c = ran.get(s.id);
    // Not Scored / Not Applicable and dropped metrics never count as a miss (D-118)
    const missed = c ? c.runs.flatMap((r) => Object.entries(r.metrics).filter(([id, m]) => inCatalog(id) && metricInfo(id).decides !== false && statusOf(m) === "scored" && !m.passed).map(([id]) => id)) : [];
    return { ...s, ...c, status: c?.status ?? "notrun", ask: s.turns[0], turns: s.turns.length, missed: new Set(missed) };
  });
}

function caseLine(row) {
  const line = el("div", "case-line");
  line.append(el("span", `case-status status-${row.status}`, STATUS[row.status] ?? row.status));
  const main = el("div", "case-main");
  const ask = el("p", "case-ask", `“${row.ask ?? row.id}”`);
  if (row.turns > 1) ask.append(el("span", "case-more", ` + ${row.turns - 1} more turn${row.turns > 2 ? "s" : ""}`));
  const meta = el("p", "case-meta", `${row.id} · ${labelFor(row.profile)} · ${row.group}`);
  if (row.core) meta.append(el("span", "case-core", "Core"));
  main.append(ask, meta);
  line.append(main);
  const missed = [...(row.missed ?? [])].map((id) => metricInfo(id).name);
  // How many deciding metrics passed, over all runs (D-162): 17/18 reads very differently from 3/18.
  const tally = (row.runs ?? []).reduce((t, r) => (r.score ? [t[0] + r.score.passed, t[1] + r.score.of] : t), [0, 0]);
  if (tally[1]) line.append(el("span", "case-score", `${tally[0]}/${tally[1]} · ${Math.round((100 * tally[0]) / tally[1])}%`));
  line.append(el("span", "case-missed", missed.length ? `Missed: ${missed.join(", ")}` : ""));
  return line;
}

function runDetail(run) {
  const block = el("section", "case-run");
  const how = run.passed ? "passed" : run.complete === false ? "not finished" : "failed";
  block.append(el("h4", null, `Run ${run.run} · ${how} · ${modelLabel(run.model ?? evals.result.model)} · $${run.usd.toFixed(4)}`));
  for (const turn of run.turns) {
    const t = el("div", "case-turn");
    t.append(el("p", "turn-ask", turn.task));
    if (turn.tools.length || turn.scope === "out") {
      const tools = el("ul", "turn-tools");
      for (const tool of turn.tools) {
        const how = tool.blocked ? `blocked: ${tool.blocked}` : tool.approvals.length ? tool.approvals.map((a) => `${a.approver} ${a.approved === "yes" ? "approved" : "rejected"}`).join(", ") : tool.ok ? "ok" : "error";
        tools.append(el("li", tool.ok ? "ok" : "bad", `${tool.agent ? `${tool.agent} → ` : ""}${tool.name} · ${how}`));
      }
      if (turn.scope === "out") tools.append(el("li", "bad", "refused as off-topic"));
      t.append(tools);
    }
    t.append(el("p", "turn-answer", turn.answer || "(no answer)"));
    block.append(t);
  }
  // Misses first, then passes, then what wasn't scored (D-118).
  const rank = (m) => (statusOf(m) !== "scored" ? 2 : m.passed ? 1 : 0);
  const scores = Object.entries(run.metrics)
    .filter(([id]) => inCatalog(id))
    .sort(([, a], [, b]) => rank(a) - rank(b));
  if (!scores.length) block.append(el("p", "evals-note", "Not scored: the eval stopped during this run."));
  const list = el("ul", "run-scores");
  for (const [id, m] of scores) {
    const status = statusOf(m);
    const off = status !== "scored";
    const li = el("li", off ? "off" : m.passed ? "pass" : "fail");
    const label = off ? (status === "not_applicable" ? "Not Applicable" : "Not Scored") : m.score == null ? "" : m.score.toFixed(2);
    const why = off ? (status === "not_applicable" ? "Nothing to grade in this conversation." : `The judge failed, not the agent: ${m.error}`) : m.reason || m.error || "";
    li.append(
      el("span", "run-score-mark", off ? "–" : m.passed ? "✓" : "✗"),
      el("span", "run-score-name", `${metricInfo(id).name} ${label}`.trim()),
      el("span", "run-score-why", why),
    );
    list.append(li);
  }
  block.append(list);
  return block;
}

function renderCases() {
  const box = $("evals-cases");
  const rows = caseRows();
  if (!rows.length) return void box.replaceChildren(el("p", "evals-note", "Nothing yet."));
  const single = rows.filter((r) => r.turns === 1);
  const multi = rows.filter((r) => r.turns > 1);
  // Each group folds, closed by default (your request); the heading carries the tally, and
  // a group you opened stays open while a live eval re-draws the list.
  evals.openGroups ??= new Set();
  box.replaceChildren(
    ...[["Single Turn", single], ["Multi-Turn", multi]]
      .filter(([, group]) => group.length)
      .map(([title, group]) => {
        const fold = el("details", "case-fold");
        fold.open = evals.openGroups.has(title);
        fold.addEventListener("toggle", () => (fold.open ? evals.openGroups.add(title) : evals.openGroups.delete(title)));
        const head = el("summary", "case-kind");
        const count = (status) => group.filter((r) => r.status === status).length;
        const tally = [
          [count("passed"), "Passed", "pass"],
          [count("failed"), "Failed", "fail"],
          [count("running"), "Running", "run"],
          [count("waiting") + count("notrun") + count("incomplete"), "Not Run", ""],
        ].filter(([n]) => n);
        head.append(el("span", "case-kind-title", `${title} · ${group.length}`));
        const marks = el("span", "case-kind-tally");
        for (const [n, label, cls] of tally) marks.append(el("span", cls, `${n} ${label}`));
        head.append(marks);
        const list = el("div", "case-fold-list");
        list.append(...group.map(caseItem));
        fold.append(head, list);
        return fold;
      }),
  );
}

function caseItem(row) {
  if (!row.runs?.length) {
    const plain = el("div", "case-row");
    plain.append(caseLine(row));
    return plain;
  }
  const item = el("details", "case-row");
  const summary = el("summary");
  summary.append(caseLine(row));
  const body = el("div", "case-body");
  body.append(el("p", "case-expected", `Expected: ${row.expected_outcome}`), ...row.runs.map(runDetail));
  item.append(summary, body);
  return item;
}

function renderEvalHistory() {
  const list = $("evals-history");
  const results = evals.index?.results ?? [];
  if (!results.length) return void list.replaceChildren(el("li", "evals-note", "Nothing yet."));
  list.replaceChildren(
    ...results.map((r) => {
      const li = el("li");
      const pick = el("button", "history-item");
      pick.type = "button";
      if (r.id === evals.result?.id) pick.setAttribute("aria-current", "true");
      pick.append(
        el("span", "history-date", r.started ?? r.id),
        el("span", "history-score", r.summary ? `${r.summary.passed}/${r.summary.cases} passed` : "–"),
        el("span", "history-meta", `${modelLabel(r.model ?? "")} · ${r.runs} run${r.runs > 1 ? "s" : ""} · $${(r.usd?.total ?? 0).toFixed(4)}`),
        el("span", "history-tag", r.status === "stopped" ? "Stopped Early" : ""),
      );
      pick.addEventListener("click", () => loadEvals(r.id === evals.result?.id ? null : r.id));
      // × deletes this eval; the first click asks, the second deletes (like Chats).
      const drop = el("button", "history-delete", "×");
      drop.type = "button";
      drop.setAttribute("aria-label", `Delete the eval of ${r.started ?? r.id}`);
      drop.addEventListener("click", async () => {
        if (!drop.classList.contains("sure")) {
          drop.classList.add("sure");
          drop.textContent = "Delete?";
          setTimeout(() => {
            drop.classList.remove("sure");
            drop.textContent = "×";
          }, 3000);
          return;
        }
        const response = await fetch(`/api/evals/${encodeURIComponent(r.id)}`, { method: "DELETE", headers: PAGE_HEADER });
        if (!response.ok) return void showEvalProblem(`Couldn't delete: ${(await response.json()).detail ?? response.statusText}`);
        announce("Eval deleted.");
        loadEvals(r.id === evals.result?.id ? null : undefined);
      });
      li.className = "history-row";
      li.append(pick, drop);
      return li;
    }),
  );
}

// ── Golden Dataset: each case as written, what "right" means, nothing scored ─

async function loadGolden() {
  if (!evals.suite.length) {
    const plan = await fetch("/api/evals/plan").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (plan?.type === "plan") {
      evals.suite = plan.cases;
      evals.defaultJudge = plan.judge;
    }
  }
  renderGolden();
}

// A labelled row of chips ("Must Say: 2.1 3.2 …"); an empty list shows nothing.
function chipRow(label, items, tone = "") {
  if (!items?.length) return null;
  const row = el("div", "golden-row");
  row.append(el("span", "golden-label", label));
  const chips = el("div", "golden-chips");
  for (const item of items) chips.append(el("span", `golden-chip ${tone}`, item));
  row.append(chips);
  return row;
}

function goldenCard(c) {
  const card = el("article", "golden-card");
  const head = el("header", "golden-card-head");
  head.append(el("span", "golden-id", c.id));
  const tags = el("span", "golden-tags");
  tags.append(el("span", "golden-tag", labelFor(c.profile)));
  if (c.turns.length > 1) tags.append(el("span", "golden-tag", `${c.turns.length} Turns`));
  if (c.core) tags.append(el("span", "golden-tag core", "Core"));
  head.append(tags);
  const chat = el("div", "golden-chat");
  for (const turn of c.turns) chat.append(el("p", "golden-ask", turn));
  const expected = el("div", "golden-expected");
  expected.append(el("span", "golden-label", "Right Answer"), el("p", null, c.expected_outcome));
  // A tool with required arguments shows once, with them: tool(name="value")
  const withArgs = (tool) => c.key_args[tool] ? `${tool}(${Object.entries(c.key_args[tool]).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})` : tool;
  const tools = [...new Set([...c.expected_tools, ...Object.keys(c.key_args)])].map(withArgs);
  const asks = Object.entries(c.approvals).map(([role, answer]) => `${role} ${answer === "approve" ? "approves" : "rejects"}`);
  const rules = [
    chipRow("Must Use Tools", tools, "tool"),
    chipRow("Must Say", c.must_include, "good"),
    chipRow("Must Never Say", c.must_not_include, "bad"),
    chipRow("Must Never Go Through", c.never_call, "bad"),
    chipRow("Must Ask", c.expect_approval),
    chipRow("Scripted Answers", asks),
    chipRow("Rule Must Fire", c.expect_blocked, "bad"),
    chipRow("Must Flag", c.expect_flagged ? ["Instruction aimed at AI"] : [], "bad"),
    chipRow("Scope", c.scope === "out" ? ["Refused as off-topic"] : [], "bad"),
  ].filter(Boolean);
  card.append(head, chat, expected, ...rules);
  return card;
}

function renderGolden() {
  const cases = evals.suite;
  const single = cases.filter((c) => c.turns.length === 1).length;
  $("golden-sub").textContent = cases.length
    ? `${cases.length} conversations with known right answers: ${single} single-turn, ${cases.length - single} multi-turn, ${cases.filter((c) => c.core).length} in the core set.`
    : "No golden cases for this agent.";
  const keep = {
    all: () => true,
    single: (c) => c.turns.length === 1,
    multi: (c) => c.turns.length > 1,
    core: (c) => c.core,
  }[goldenFilter];
  const shown = cases.filter(keep);
  const groups = [...new Set(shown.map((c) => c.group))];
  $("golden-list").replaceChildren(
    ...groups.flatMap((g) => {
      const inGroup = shown.filter((c) => c.group === g);
      const grid = el("div", "golden-grid");
      grid.append(...inGroup.map(goldenCard));
      return [el("h2", "golden-group-title", `${g} · ${inGroup.length}`), grid];
    }),
  );
}

for (const button of document.querySelectorAll(".golden-filter button")) {
  button.addEventListener("click", () => {
    goldenFilter = button.dataset.filter;
    for (const b of document.querySelectorAll(".golden-filter button")) b.setAttribute("aria-pressed", String(b === button));
    renderGolden();
  });
}

// ── Run dialog: pick cases, runs and model; see the estimate; then start ────
let planTimer = 0;

function pickedCases() {
  return [...$("evals-case-list").querySelectorAll("input:checked")].map((box) => box.value);
}
const pickedRuns = () => Number($("evals-form").elements.runs.value);

async function fetchPlan(cases) {
  const query = new URLSearchParams({ cases: cases.join(","), runs: pickedRuns(), model: $("evals-model").value });
  if ($("evals-judge").value) query.set("judge", $("evals-judge").value);
  const response = await fetch(`/api/evals/plan?${query}`);
  if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
  return response.json();
}

// The same animated menu as the chat's model pill: provider mark + name, check on the pick.
function fillModelPick(pick, models) {
  for (const old of pick.querySelectorAll("option")) old.remove(); // keep the trigger <button>
  for (const id of models) {
    const option = el("option");
    option.value = id;
    option.append(fromTemplate(id.startsWith("claude-") ? "tpl-claude" : "tpl-spark"), el("span", null, modelLabel(id)));
    pick.append(option);
  }
}

async function openEvalDialog() {
  setUpEvalPickers(evals.defaultJudge);
  let plan;
  try {
    plan = await fetchPlan([]);
    if (plan.type !== "plan") throw new Error(plan.message ?? "No plan.");
  } catch (error) {
    showEvalProblem(`Can't start: ${error.message}`);
    return;
  }
  const list = $("evals-case-list");
  list.replaceChildren();
  let group = "";
  for (const c of plan.cases) {
    if (c.group !== group) list.append(el("p", "case-pick-group", (group = c.group)));
    const label = el("label", "case-pick");
    const box = Object.assign(document.createElement("input"), { type: "checkbox", value: c.id, checked: c.core || !plan.cases.some((x) => x.core) });
    box.dataset.core = c.core ? "1" : "";
    label.append(box, el("span", null, c.id), el("span", "case-pick-turns", c.turns.length > 1 ? `${c.turns.length} turns` : ""));
    list.append(label);
  }
  refreshEstimate();
  $("evals-dialog").returnValue = ""; // Esc or Cancel must never reuse an old "start"
  $("evals-dialog").showModal();
}

function showEstimate(plan) {
  const est = $("evals-estimate");
  const n = pickedCases().length;
  $("evals-start").disabled = n === 0;
  if (!n) return void (est.textContent = "Pick at least one case.");
  est.replaceChildren(
    el("span", null, `Agent ${modelLabel(plan.model)} · judge ${modelLabel(plan.judge)} · ≈ ${plan.estimate.agent_runs} agent runs · ≈ ${plan.estimate.judge_calls} judge calls · cap $${plan.cap_usd.toFixed(2)}`),
    el("strong", "evals-estimate-cost", costToYou(plan)),
  );
}

// "$0 on Gemini's free tier · up to ≈ $0.10 if Claude Haiku 5.5 does it all"
function costToYou(plan) {
  const { low, high } = plan.cost ?? { low: 0, high: 0 };
  const money = (usd) => (usd < 0.01 ? `$${usd.toFixed(3)}` : `$${usd.toFixed(2)}`);
  const helper = modelLabel(plan.fallback_agent ?? plan.fallback_judge ?? "");
  let text = low
    ? `Cost to you: ≈ ${money(low)}–${money(high)} (Claude is paid)`
    : high
      ? `Cost to you: $0 on Gemini's free tier · up to ≈ ${money(high)} if ${helper} does it all`
      : "Cost to you: $0 on Gemini's free tier · if it runs out, the eval stops (no Claude key)";
  if (high > plan.cap_usd) text += ` · the $${plan.cap_usd.toFixed(2)} cap stops it before that`;
  return text;
}

function refreshEstimate() {
  if (!$("evals-dialog").open) return refreshCost(); // a picker changed on the card
  clearTimeout(planTimer);
  const cases = pickedCases();
  if (cases.length) {
    evals.next = { cases, runs: pickedRuns() }; // the panel shows what Start will run
    refreshCost();
  }
  if (!cases.length) return showEstimate({});
  planTimer = setTimeout(async () => {
    try {
      showEstimate(await fetchPlan(cases));
    } catch (error) {
      $("evals-estimate").textContent = error.message;
    }
  }, 250);
}

// ── Next Run cost panel (D-117): what each role costs, and what you pay ─────
let costTimer = 0;
const part = (root, name) => root.querySelector(`[data-part="${name}"]`);
const usdShort = (usd) => (usd <= 0 ? "$0" : usd < 0.01 ? `$${usd.toFixed(3)}` : `$${usd.toFixed(2)}`);

// A dollar figure that counts to its new value (0.4 s, easing out); instant if reduced motion.
function countTo(node, value) {
  const from = Number(node.dataset.value ?? 0);
  node.dataset.value = String(value);
  if (from === value || matchMedia("(prefers-reduced-motion: reduce)").matches) return void (node.textContent = usdShort(value));
  const start = performance.now();
  const step = (now) => {
    if (node.dataset.value !== String(value)) return; // a newer value took over
    const t = Math.min((now - start) / 400, 1);
    node.textContent = usdShort(from + (value - from) * (1 - (1 - t) ** 3));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// What the next run covers: the dialog's last pick, else the core set.
function nextScope() {
  if (!evals.next) {
    const core = evals.suite.filter((c) => c.core).map((c) => c.id);
    evals.next = { cases: core.length ? core : evals.suite.map((c) => c.id), runs: 1 };
  }
  return evals.next;
}

function refreshCost() {
  clearTimeout(costTimer);
  costTimer = setTimeout(async () => {
    if (!evals.suite.length || !$("evals-model").value) return;
    const { cases, runs } = nextScope();
    const query = new URLSearchParams({ cases: cases.join(","), runs, model: $("evals-model").value });
    if ($("evals-judge").value) query.set("judge", $("evals-judge").value);
    try {
      const response = await fetch(`/api/evals/plan?${query}`);
      if (response.ok) renderCostPanel(await response.json());
    } catch {
      // the panel keeps its last numbers
    }
  }, 150);
}

// One role's card: Free Tier or Paid, the big number, the work, the free-limit meter.
function roleCard(card, role, work, helper) {
  card.classList.toggle("paid", role.paid);
  const pill = part(card, "pill");
  pill.textContent = role.paid ? "Paid" : "Free Tier";
  pill.className = `cost-pill ${role.paid ? "paid" : "free"}`;
  countTo(part(card, "num"), role.paid ? role.usd_list : 0);
  part(card, "list").textContent = role.paid ? "Billed to your Claude key" : `${usdShort(role.usd_list)} on a paid key`;
  part(card, "work").textContent = work;
  const meter = part(card, "meter");
  const text = part(card, "meter-text");
  const limit = role.free_per_day;
  meter.hidden = role.paid || !limit;
  card.classList.remove("over");
  if (role.paid) return void (text.textContent = "");
  if (!limit) return void (text.textContent = "Free limit unknown");
  const share = role.calls / limit;
  meter.firstElementChild.style.width = `${Math.min(share, 1) * 100}%`;
  card.classList.toggle("over", share > 1);
  text.textContent =
    share <= 1 ? `${role.calls} of ${limit} free calls a day` : helper ? `Over the free limit: ${helper} takes over` : "Over the free limit: the eval will stop";
}

function renderCostPanel(plan) {
  const cost = plan.cost;
  if (plan.type !== "plan" || !cost?.agent) return;
  const { cases, runs } = nextScope();
  const core = evals.suite.filter((c) => c.core).map((c) => c.id);
  const isCore = cases.length === core.length && cases.every((id) => core.includes(id));
  $("next-scope").textContent = `${cases.length} ${isCore ? "core " : ""}test${cases.length === 1 ? "" : "s"} × ${runs} run${runs > 1 ? "s" : ""}`;
  const basis = $("next-basis");
  // Only say where the numbers come from once they come from your own evals.
  basis.hidden = cost.basis !== "measured";
  basis.textContent = `From your last ${cost.from_evals} eval${cost.from_evals > 1 ? "s" : ""}`;
  basis.title = "Average tokens, calls and time per test, from your recent evals.";
  evals.lastPlan = plan;
  const helper = cost.fallback ? modelLabel(cost.fallback.model) : "";
  const turns = cost.agent.turns;
  roleCard($("cost-agent"), cost.agent, `${turns} answer${turns === 1 ? "" : "s"} · ≈ ${cost.agent.calls} model calls`, helper);
  roleCard($("cost-judge"), cost.judge, `${cost.judge.calls} grading calls`, helper);
  // A model grading its own answers is lenient: say so (your pick, D-118).
  part($("cost-judge"), "note").textContent =
    cost.agent.model === cost.judge.model ? "Grading its own answers: pick a different judge" : "";

  const total = $("cost-total");
  part(total, "time").textContent = cost.seconds ? `≈ ${aboutTime(cost.seconds)} to run` : "";
  if (evals.live) return showThisRun(); // while running, You Pay shows what's spent
  $("next-label").textContent = "Next Run";
  countTo(part(total, "num"), cost.low);
  part(total, "range").textContent =
    cost.high > cost.low
      ? `Up to ${usdShort(cost.high)} if Gemini runs out and ${helper} steps in`
      : cost.low > 0
        ? "Billed to your Claude key"
        : "Free tier only: the eval stops if Gemini runs out";
  if (cost.high > plan.cap_usd) part(total, "range").append(el("strong", "cost-cap", ` The $${plan.cap_usd.toFixed(2)} cap stops it first.`));
  // The split: what each role costs at most, in the two role colours.
  const most = (role, backup) => (role.paid ? role.usd_list : (backup ?? role.usd_list));
  const agentMost = most(cost.agent, cost.fallback?.agent_usd);
  const judgeMost = most(cost.judge, cost.fallback?.judge_usd);
  const sum = agentMost + judgeMost || 1;
  const split = part(total, "split");
  split.firstElementChild.style.width = `${(agentMost / sum) * 100}%`;
  split.lastElementChild.style.width = `${(judgeMost / sum) * 100}%`;
  // Say which price the split uses: the takeover model's when Gemini could run out.
  const takeover = cost.fallback && !(cost.agent.paid && cost.judge.paid);
  part(total, "legend").replaceChildren(
    el("span", "legend-note", takeover ? `If ${helper} does it all:` : "Split:"),
    el("span", "legend-agent", `Agent ${usdShort(agentMost)}`),
    el("span", "legend-judge", `Judge ${usdShort(judgeMost)}`),
  );
}

// "about 8 min", "under a minute"
function aboutTime(seconds) {
  if (seconds < 60) return "under a minute";
  const minutes = Math.round(seconds / 60);
  return minutes < 90 ? `${minutes} min` : `${Math.round(minutes / 6) / 10} h`;
}
const clock = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

// While a run is going, the cost panel is "This Run": spent so far against the estimate.
function showThisRun() {
  const live = evals.live;
  const cost = evals.lastPlan?.cost;
  if (!live) return;
  $("next-label").textContent = "This Run";
  const total = $("cost-total");
  countTo(part(total, "num"), live.paid ?? 0);
  const estimate = cost ? (cost.high > cost.low ? `${usdShort(cost.low)}–${usdShort(cost.high)}` : usdShort(cost.low)) : "";
  part(total, "range").textContent = estimate ? `Spent so far, of ≈ ${estimate} estimated` : "Spent so far";
}

// ── The activity panel: what is happening now, how long it has taken, what's left ──
const PHASES = ["agent", "judge", "done"];
const STALL_SECONDS = 60; // this long with no news, the panel says what it's waiting on

function setPhase(phase, detail = "") {
  if (evals.live) evals.live.phase = phase;
  $("live-detail").classList.remove("stalled");
  const at = PHASES.indexOf(phase);
  for (const li of $("live-phases").children) {
    const i = PHASES.indexOf(li.dataset.phase);
    li.className = i < at ? "past" : i === at ? "now" : "";
  }
  $("live-detail").textContent = detail;
}

function feed(text, tone = "") {
  const live = evals.live;
  const line = el("li", tone);
  line.append(el("span", "feed-time", live ? clock((Date.now() - live.started) / 1000) : ""), el("span", null, text));
  $("live-feed").prepend(line);
  while ($("live-feed").children.length > 8) $("live-feed").lastElementChild.remove();
}

// Elapsed and time left: the mean seconds of finished tests (or the plan's) × tests to go.
function tickLive() {
  const live = evals.live;
  if (!live) return;
  const elapsed = (Date.now() - live.started) / 1000;
  const all = live.cases.length * live.runs;
  const done = live.cases.reduce((n, c) => n + c.done, 0);
  const each = live.timed.length ? live.timed.reduce((a, b) => a + b, 0) / live.timed.length : live.perTest;
  const left = Math.max(each * (all - done) - (live.current ? (Date.now() - live.current) / 1000 : 0), 0);
  $("live-count").textContent = `${done} of ${all} tests`;
  const quiet = (Date.now() - live.lastEvent) / 1000;
  if (quiet > STALL_SECONDS) {
    const who = live.phase === "agent" ? live.agent : live.judge;
    const detail = $("live-detail");
    detail.textContent = `Waiting on ${modelLabel(who)} for ${clock(quiet)}… (it gives up after 2 min a call; Stop ends the run)`;
    detail.classList.add("stalled");
  }
  $("live-time").textContent = `${clock(elapsed)} elapsed · ${done === all ? "finishing" : `≈ ${aboutTime(left)} left`}`;
}

// ── A live eval: rows fill in as runs finish ──────────────────────────────────
function liveRow(caseId) {
  return evals.live?.cases.find((c) => c.id === caseId);
}

function startEval(cases, runs, model, judge) {
  return watchEval(() =>
    fetch("/api/evals/run", {
      method: "POST",
      headers: { ...PAGE_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify({ cases, runs, model, judge }),
    }),
  );
}

// Follow a run to its end: one this page started, or one already running when the page
// opened (after a reload). The server keeps every event, so either way the panel shows the
// whole run, with Stop (D-119).
async function watchEval(request) {
  evals.running = true;
  $("evals-run").disabled = true;
  $("evals-reset").disabled = true;
  $("evals-live").hidden = false;
  $("evals-stop").disabled = false;
  $("live-feed").replaceChildren();
  $("live-ask").textContent = "Starting…";
  setPhase("agent");
  const progress = $("evals-progress");
  progress.value = 0;
  let saved = null;
  let finished = null;
  let ticker = 0;
  try {
    const response = await request();
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    for await (const ev of readLines(response)) {
      if (evals.live) evals.live.lastEvent = Date.now(); // the stall warning starts from here
      if (ev.type === "eval_started") {
        progress.max = Math.max(ev.cases.length * ev.runs, 1);
        const planned = evals.lastPlan?.cost?.seconds;
        const testRuns = ev.cases.length * ev.runs;
        evals.live = {
          runs: ev.runs,
          agent: ev.model,
          firstAgent: ev.model,
          judge: ev.judge,
          firstJudge: ev.judge,
          spent: 0,
          paid: 0,
          started: Date.now(),
          lastEvent: Date.now(),
          phase: "agent",
          current: 0,
          timed: [],
          perTest: planned ? planned / testRuns : 60,
          cases: ev.cases.map((c) => ({ ...c, status: "waiting", done: 0, missed: new Set(), metrics: {} })),
        };
        // The cost cards show this run's models (a page that came back may have others picked).
        for (const [pick, model] of [["evals-model", ev.model], ["evals-judge", ev.judge]]) {
          if ([...$(pick).options].some((o) => o.value === model)) $(pick).value = model;
        }
        refreshCost();
        ticker = setInterval(tickLive, 1000);
        feed(`Started ${testRuns} test${testRuns > 1 ? "s" : ""} · agent ${modelLabel(ev.model)} · judge ${modelLabel(ev.judge)}`);
        renderEvals();
        tickLive();
      } else if (ev.type === "run_started") {
        const row = liveRow(ev.case);
        if (row) row.status = "running";
        evals.live.current = Date.now();
        $("live-ask").textContent = `“${row?.ask ?? ev.case}”`;
        $("live-ask").title = ev.case;
        setPhase("agent", `${modelLabel(evals.live.agent)} is answering${evals.live.runs > 1 ? ` · run ${ev.run} of ${evals.live.runs}` : ""}`);
        renderCases();
      } else if (ev.type === "agent_finished") {
        const tools = [...new Set(ev.tools)];
        feed(`${ev.case}: agent answered in ${Math.round(ev.seconds)} s${tools.length ? ` · used ${tools.join(", ")}` : " · no tools"}`);
        setPhase("judge", "Grading starts");
      } else if (ev.type === "metric_started") {
        setPhase("judge", `${modelLabel(evals.live.judge)} grading ${metricInfo(ev.metric).name} (${ev.index} of ${ev.of})`);
      } else if (ev.type === "agent_switched") {
        evals.live.agent = ev.to;
        feed(`${modelLabel(ev.from)} ran out of quota: ${modelLabel(ev.to)} takes over`, "warn");
        renderEvalSummary();
      } else if (ev.type === "run_finished") {
        const row = liveRow(ev.case);
        if (row) {
          for (const [id, m] of Object.entries(ev.metrics)) {
            if ((m.status ?? "scored") !== "scored") continue; // Not Scored never counts (D-118)
            const t = (row.metrics[id] ??= { sum: 0, scored: 0, passed: 0, runs: 0, score: null });
            if (m.score != null) {
              t.sum += m.score;
              t.scored += 1;
            }
            t.passed += m.passed ? 1 : 0;
            t.runs += 1;
            t.score = t.scored ? t.sum / t.scored : null;
            if (!m.passed) row.missed.add(id);
          }
          row.done += 1;
          row.status = !ev.passed ? "failed" : row.done >= evals.live.runs ? "passed" : "running";
        }
        evals.live.spent = ev.spent_usd;
        evals.live.paid = ev.paid_usd ?? null;
        if (ev.judge) evals.live.judge = ev.judge;
        if (ev.seconds != null) evals.live.timed.push(ev.seconds);
        evals.live.current = 0;
        progress.value += 1;
        const misses = row ? [...row.missed].map((id) => metricInfo(id).name) : [];
        feed(
          `${ev.passed ? "✓" : "✗"} ${ev.case} ${ev.passed ? "passed" : "failed"} · ${Math.round(ev.seconds ?? 0)} s · ${usdShort(ev.usd)}${!ev.passed && misses.length ? ` · missed ${misses.join(", ")}` : ""}`,
          ev.passed ? "pass" : "fail",
        );
        setPhase("done", ev.passed ? "Passed" : "Failed");
        renderEvalSummary();
        renderMetrics();
        renderCases();
        showThisRun();
        tickLive();
      } else if (ev.type === "eval_finished") {
        finished = ev;
      } else if (ev.type === "saved") {
        saved = ev.id;
      } else if (ev.type === "error") {
        throw new Error(ev.message);
      }
    }
  } catch (error) {
    showEvalProblem(`✗ ${error.message}`);
  } finally {
    clearInterval(ticker);
    evals.running = false;
    evals.live = null;
    $("evals-live").hidden = true;
    $("evals-reset").disabled = false;
    await loadEvals(saved ?? undefined); // also turns Run back on and the panel back to Next Run
    if (!finished) announce("Eval ended.");
    else if (finished.status === "stopped") announce(`Eval stopped: ${finished.stop_reason}`);
    else announce(`Eval finished: ${finished.summary.passed} of ${finished.summary.cases} cases passed.`);
  }
}

$("evals-run").addEventListener("click", openEvalDialog);
// Reset: back to the ready card, the core set and no eval open (your request).
$("evals-reset").addEventListener("click", () => {
  evals.next = null;
  loadEvals(null);
  announce("Evals reset.");
});
$("evals-case-list").addEventListener("change", refreshEstimate);
$("evals-model").addEventListener("change", refreshEstimate);
$("evals-judge").addEventListener("change", refreshEstimate);
for (const radio of document.querySelectorAll('#evals-form input[name="runs"]')) radio.addEventListener("change", refreshEstimate);
$("evals-core").addEventListener("click", () => {
  for (const box of $("evals-case-list").querySelectorAll("input")) box.checked = box.dataset.core === "1";
  refreshEstimate();
});
$("evals-all").addEventListener("click", () => {
  for (const box of $("evals-case-list").querySelectorAll("input")) box.checked = true;
  refreshEstimate();
});
$("evals-none").addEventListener("click", () => {
  for (const box of $("evals-case-list").querySelectorAll("input")) box.checked = false;
  refreshEstimate();
});
$("evals-dialog").addEventListener("close", () => {
  if ($("evals-dialog").returnValue === "start") startEval(pickedCases(), pickedRuns(), $("evals-model").value, $("evals-judge").value);
});
$("evals-stop").addEventListener("click", async () => {
  $("evals-stop").disabled = true;
  $("live-detail").textContent = "Stopping after this test…";
  await fetch("/api/evals/stop", { method: "POST", headers: PAGE_HEADER });
});

// ── Sidebar groups fold (Profiles, Chats, Workspace, Observability); each one's state is kept per browser ─
for (const group of document.querySelectorAll(".side-group")) {
  const toggle = group.querySelector(".side-toggle");
  if (!toggle) continue; // Acting As doesn't fold (found: it stopped every group after it folding)
  // New key name (2026-11-12): folds clicked before "all folded but Chats" don't override it.
  const key = `side-fold-${group.dataset.group}`;
  const set = (collapsed) => {
    group.classList.toggle("collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    group.querySelector(".side-body").inert = collapsed; // folded links can't take focus
  };
  const folded = group.dataset.collapsed === "1"; // all but Chats start folded (your request)
  try {
    const saved = localStorage.getItem(key);
    set(saved === null ? folded : saved === "1");
  } catch {
    set(folded); // storage blocked: its default
  }
  toggle.addEventListener("click", () => {
    const collapsed = !group.classList.contains("collapsed");
    set(collapsed);
    try {
      localStorage.setItem(key, collapsed ? "1" : "0");
    } catch {
      // not remembered; it still folds
    }
  });
}
