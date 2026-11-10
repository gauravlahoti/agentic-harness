// The page's behavior. Plain JS, no build step (spec/02-ui.md).
// Text from the server is always set with textContent, never as HTML.

const PAGE_HEADER = { "X-Harness-Page": "1" }; // the server refuses actions without it (D-20)
const ICONS = { waiting: "○", passed: "✓", failed: "✗", skipped: "–" };

const $ = (id) => document.getElementById(id);

// ── Health: smoke row + what the Agent view can offer ───────────────────────
let health = null;

async function loadHealth() {
  const server = $("smoke-server");
  const key = $("smoke-key");
  try {
    health = await (await fetch("/api/health")).json();
    server.textContent = "Server up ✓";
    server.className = "pill ok";
    // A missing key is fine: everything offline works without it (S00-AC12).
    key.textContent = health.key === "present" ? "Key present ✓" : "Key skipped";
    key.className = health.key === "present" ? "pill ok" : "pill skip";
    $("version").textContent = `v${health.version}`;
  } catch {
    server.textContent = "Server down";
    server.className = "pill bad";
  }
  setUpAgent();
}

// ── Views: Agent and Checks, chosen by the URL hash ─────────────────────────
function showView() {
  const view = location.hash === "#checks" ? "checks" : "agent";
  for (const name of ["agent", "checks"]) {
    $(`view-${name}`).hidden = name !== view;
  }
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
  $("workspace-name").textContent = ws.owner ? `${ws.title} · ${ws.owner}` : ws.title;
  $("empty-title").textContent = `What should the ${ws.title} do?`;
  $("empty-hint").textContent = "";
  setUpProfilePicker(ws);
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
  // Every run calls a real model, so no key means nothing can run: say so only then.
  const hasKey = health.key === "present";
  $("send").disabled = !hasKey;
  $("model").disabled = !hasKey;
  $("composer-alert").textContent = hasKey ? "" : "No Gemini key: add it to .env and restart.";
}

// The model menu offers only models with a price (the server checks again, D-31).
// Your last pick is remembered in this browser; if it's gone, the configured default wins.
const MODEL_KEY = "live-model";

// "gemini-3.5-flash-lite" → "Gemini 3.5 Flash-Lite"
function modelLabel(id) {
  const [version, ...words] = id.replace(/^gemini-/, "").split("-");
  const tier = words.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join("-");
  return `Gemini ${version} ${tier}`.trim();
}

// Profiles (D-39): whose view the agent works for. Same menu style as the model menu.
// Switching starts a fresh thread, because each profile gets different context.
const profileKey = (ws) => `profile:${ws.name}`;

function setUpProfilePicker(ws) {
  const pick = $("profile");
  const box = $("profile-box");
  for (const old of pick.querySelectorAll("option")) old.remove();
  box.hidden = !ws.profiles?.length;
  if (box.hidden) return;
  for (const profile of ws.profiles) {
    const option = el("option");
    option.value = profile.id;
    option.append(el("span", "profile-dot"), el("span", null, profile.label));
    pick.append(option);
  }
  let saved = null;
  try {
    saved = localStorage.getItem(profileKey(ws));
  } catch {
    // Storage blocked: start with the first profile.
  }
  pick.value = ws.profiles.some((p) => p.id === saved) ? saved : ws.profiles[0].id;
}

function currentProfile() {
  return $("profile-box").hidden ? null : $("profile").value;
}

const labelFor = (id) => health?.workspace?.profiles?.find((p) => p.id === id)?.label ?? id;

function switchProfile() {
  try {
    localStorage.setItem(profileKey(health.workspace), $("profile").value);
  } catch {
    // Storage blocked: the switch still applies to this page.
  }
  for (const turn of $("thread").querySelectorAll(".turn")) turn.remove();
  $("empty-state").hidden = false;
  $("task").focus();
}

function setUpModelPicker() {
  const pick = $("model");
  // Keep the select's own trigger <button>; replace only the options.
  for (const old of pick.querySelectorAll("option")) old.remove();
  for (const id of health.models ?? []) {
    const option = el("option");
    option.value = id;
    option.append(fromTemplate("tpl-spark"), el("span", null, modelLabel(id)));
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
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const money = (usd) => `$${usd.toFixed(5)}`;
const argText = (args) =>
  Object.entries(args ?? {})
    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
// The line shows each argument briefly; the full text is in the opened facts.
const argBrief = (args) =>
  Object.entries(args ?? {})
    .map(([k, v]) => {
      const text = (typeof v === "string" ? v : JSON.stringify(v)).replace(/\s+/g, " ");
      return `${k}: ${text.length > 48 ? `${text.slice(0, 48)}…` : text}`;
    })
    .join(", ");
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
  head.append(fromTemplate("tpl-mark"), el("span", "agent-name", agentName), el("span", "agent-label", "Activity"), stats);
  const activity = el("ol", "activity");
  activity.setAttribute("aria-label", "What the harness did");
  const reply = el("div", "reply");
  const files = el("div", "files"); // cards for files the tools saved (S03)
  const foot = el("p", "run-foot");
  agent.append(head, activity, reply, files, foot);

  turn.append(you, agent);
  $("thread").append(turn);
  turn.scrollIntoView({ block: "end" });
  return { activity, reply, files, foot, stats, model: null, tools: new Map(), tokens: 0 };
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
  li.scrollIntoView({ block: "nearest" });
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

// Models write a little markdown. Show paragraphs, lists, **bold** and `code`
// by building elements, never by parsing HTML, so model text can't inject anything.
function renderProse(container, text) {
  let list = null;
  let para = [];
  const flush = () => {
    if (para.length) {
      const p = el("p");
      appendInline(p, para.join("\n"));
      container.append(p);
    }
    para = [];
  };
  for (const line of text.split("\n")) {
    const item = line.match(/^\s*(?:[-*•]|(\d+)\.)\s+(.*)$/);
    if (item) {
      flush();
      const kind = item[1] ? "ol" : "ul";
      if (!list || list.tagName.toLowerCase() !== kind) {
        list = el(kind);
        container.append(list);
      }
      const li = el("li");
      appendInline(li, item[2]);
      list.append(li);
    } else if (!line.trim()) {
      flush();
      list = null;
    } else {
      list = null;
      para.push(line);
    }
  }
  flush();
}

function appendInline(parent, text) {
  for (const part of text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)) {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) parent.append(el("strong", null, part.slice(2, -2)));
    else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) parent.append(el("code", null, part.slice(1, -1)));
    else if (part) parent.append(part);
  }
}

// Screen readers hear the start and the end of a run, not every step.
const announce = (text) => {
  $("run-status").textContent = text;
};

// Turn one event from the harness into a change on the page.
function onEvent(ev, turn) {
  const d = ev.data;
  if (ev.type === "run_started") {
    addActivity(turn, {
      text: `Started a run · ${d.model}`,
      state: "done",
      facts: [
        ["Model", d.model],
        ["Tools", d.tools.join(", ") || "none"],
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
  } else if (ev.type === "model_called") {
    turn.model = addActivity(turn, {
      text: `Thinking · call ${d.step}`,
      facts: [["Sends", `the whole history: ${plural(d.history, "step")} (store=false)`]],
      raw: d,
    });
  } else if (ev.type === "model_replied" && turn.model) {
    const u = d.usage ?? {};
    const used = (u.total_input_tokens ?? 0) + (u.total_output_tokens ?? 0) + (u.total_thought_tokens ?? 0);
    turn.tokens += used;
    let text = `Model replied: ${d.status}`;
    if (d.tool_calls.length) {
      // ["lookup", "lookup"] → "lookup ×2"
      const counts = new Map();
      for (const name of d.tool_calls) counts.set(name, (counts.get(name) ?? 0) + 1);
      const names = [...counts].map(([name, n]) => (n > 1 ? `${name} ×${n}` : name));
      text = `Decided to use ${names.join(", ")}`;
    } else if (d.status === "completed") {
      text = "Wrote the answer";
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
  } else if (ev.type === "tool_started") {
    const args = argText(d.arguments);
    const brief = argBrief(d.arguments);
    const part = d.part === "context" ? "context" : "tool";
    // load_skill is the harness's own context tool: name it for what it does.
    const label =
      d.name === "load_skill" ? `Read skill ${d.arguments?.name ?? ""}` : `${d.name}${brief ? ` · ${brief}` : ""}`;
    const risk = part === "tool" ? d.risk : undefined;
    const row = addActivity(turn, { text: `Running ${label}`, part, risk, raw: d });
    turn.tools.set(d.call_id, { row, args, label, arguments: d.arguments ?? {} });
  } else if (ev.type === "tool_finished") {
    const started = turn.tools.get(d.call_id);
    if (started) {
      setActivity(started.row, {
        text: started.label,
        state: d.is_error ? "error" : "done",
        facts: [
          // One row per argument, so a long draft doesn't swallow the others.
          ...(started.args
            ? Object.entries(started.arguments).map(([k, v]) => [k, typeof v === "string" ? v : JSON.stringify(v)])
            : [["Arguments", "none"]]),
          ...(d.risk ? [["Risk", d.risk]] : []),
          ["Output", d.output],
          ["Call ID", d.call_id ?? "–"],
          ["Sent back as", d.is_error ? "an error the model can read" : "a result"],
        ],
        raw: d,
      });
    }
  } else if (ev.type === "file_saved") {
    turn.files.append(fileCard(d));
  } else if (ev.type === "run_finished") {
    // A model call that never got its reply (time limit, error) is marked, not left spinning.
    if (turn.model?.li.classList.contains("working")) setActivity(turn.model, { state: "error" });
    turn.stats.classList.remove("working");
    turn.stats.textContent = `${plural(d.model_calls, "call")} · ${turn.tokens} tokens · ${money(d.usd)} · ${d.seconds.toFixed(1)} s`;
    if (d.answer) renderProse(turn.reply, d.answer);
    const reason = REASONS[d.reason] ?? d.reason;
    const foot = {
      completed: "✓ Run complete",
      stopped: `■ Stopped: ${reason}`,
      failed: `✗ Failed: ${reason}`,
    }[d.outcome];
    turn.foot.textContent = foot ?? d.outcome;
    turn.foot.className = `run-foot ${d.outcome}`;
    announce(`${foot}. ${turn.stats.textContent}`);
    turn.foot.scrollIntoView({ block: "nearest" });
  }
}

// A file a tool saved: name and place on the card, the text when opened (D-53).
function fileCard(d) {
  const card = el("details", `file-card folder-${d.folder}`);
  const summary = el("summary");
  const where = d.folder === "outbox" ? "Outbox · not sent" : "Draft";
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
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { ...PAGE_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify({ task, model: $("model").value, profile: currentProfile() }),
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    for await (const ev of readLines(response)) onEvent(ev, turn);
  } catch (error) {
    turn.stats.classList.remove("working");
    turn.stats.textContent = "";
    turn.foot.textContent = `✗ ${error.message}`;
    turn.foot.className = "run-foot failed";
    announce(`Failed: ${error.message}`);
  } finally {
    send.disabled = false;
    input.focus();
  }
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
$("profile").addEventListener("change", switchProfile);
addEventListener("hashchange", showView);
showView();
loadHealth();
