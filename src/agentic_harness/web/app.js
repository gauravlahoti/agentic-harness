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

// ── Agent view (S01): send a task, show each step as it happens ─────────────
const EXAMPLES = ["What time is it in Tokyo?", "What time is it in UTC and in New York?"];

function setUpAgent() {
  const ws = health?.workspace;
  const fake = document.querySelector('input[name="mode"][value="fake"]');
  const live = document.querySelector('input[name="mode"][value="live"]');
  if (!ws) {
    $("send").disabled = true;
    return;
  }
  const toolCount = `${ws.tools.length} tool${ws.tools.length === 1 ? "" : "s"}`;
  $("workspace-name").textContent = `${ws.name} workspace · ${toolCount}`;
  $("empty-hint").textContent = ws.tools.length
    ? `Tools: ${ws.tools.join(", ")}. Every step the harness takes appears below.`
    : "This workspace has no tools yet.";
  $("examples").replaceChildren(
    ...EXAMPLES.map((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "example";
      chip.textContent = text;
      chip.addEventListener("click", () => {
        $("task").value = text;
        $("task").focus();
      });
      return chip;
    }),
  );
  fake.disabled = !ws.fake;
  live.disabled = health.key !== "present";
  if (fake.disabled && !live.disabled) live.checked = true;
  updateModeHint();
}

function currentMode() {
  return document.querySelector('input[name="mode"]:checked')?.value ?? "fake";
}

function updateModeHint() {
  $("mode-hint").textContent =
    currentMode() === "fake"
      ? "Fake: replays a recorded Gemini run. Free; tools still run for real."
      : `Live: calls ${health?.model ?? "Gemini"} with your key.`;
}

// One timeline row per step. Rows are updated in place as later events arrive.
function addStep({ icon = "○", what, sub = "", tag = "loop", state = "working", raw }) {
  const row = document.createElement("li");
  row.className = `step new ${state}`;

  const iconEl = document.createElement("span");
  iconEl.className = "icon";
  iconEl.setAttribute("aria-hidden", "true");
  iconEl.textContent = icon;

  const text = document.createElement("span");
  text.className = "what";
  const title = document.createElement("span");
  title.textContent = what;
  const subEl = document.createElement("span");
  subEl.className = "sub";
  subEl.textContent = sub;
  text.append(title, subEl);

  const meta = document.createElement("span");
  meta.className = "meta";
  const cost = document.createElement("span");
  const tagEl = document.createElement("span");
  tagEl.className = `tag ${tag}`;
  tagEl.textContent = tag.toUpperCase();
  meta.append(cost, tagEl);

  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "details";
  const pre = document.createElement("pre");
  details.append(summary, pre);

  row.append(iconEl, text, meta, details);
  $("timeline").append(row);
  const step = { row, iconEl, title, subEl, cost, pre };
  setRaw(step, raw);
  row.scrollIntoView({ block: "nearest" });
  return step;
}

function updateStep(step, { icon, what, sub, state, cost, raw }) {
  if (icon !== undefined) step.iconEl.textContent = icon;
  if (what !== undefined) step.title.textContent = what;
  if (sub !== undefined) step.subEl.textContent = sub;
  if (state) step.row.className = `step ${state}`;
  if (cost !== undefined) step.cost.textContent = cost;
  if (raw !== undefined) setRaw(step, raw);
}

// Raw event data for the curious; long values (thought signatures) are shortened.
function setRaw(step, raw) {
  const shorten = (key, value) =>
    typeof value === "string" && value.length > 160
      ? `${value.slice(0, 160)}… (${value.length} chars)`
      : value;
  step.pre.textContent = JSON.stringify(raw, shorten, 2);
}

const money = (usd) => `$${usd.toFixed(5)}`;
const tokenCount = (u) =>
  (u?.total_input_tokens ?? 0) + (u?.total_output_tokens ?? 0) + (u?.total_thought_tokens ?? 0);
const callText = (name, args) =>
  `${name}(${Object.entries(args ?? {})
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ")})`;
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function setStatus(text, state = "") {
  const status = $("run-status");
  status.textContent = text;
  status.className = `status-line ${state}`;
}

// Models often write **bold**. Show it as bold by building elements, never by parsing HTML,
// so text from the model can't inject anything into the page.
function appendWithBold(parent, text) {
  text.split(/\*\*(.+?)\*\*/g).forEach((part, i) => {
    if (i % 2 === 1) {
      const strong = document.createElement("strong");
      strong.textContent = part;
      parent.append(strong);
    } else {
      parent.append(part);
    }
  });
}

function showAnswer(d) {
  const card = document.createElement("div");
  card.className = `answer ${d.outcome}`;
  const label = document.createElement("span");
  label.className = "answer-label";
  label.textContent =
    d.outcome === "completed" ? "Answer" : `${d.outcome === "stopped" ? "Stopped" : "Failed"}: ${d.reason}`;
  const body = document.createElement("span");
  appendWithBold(body, d.answer || (d.outcome === "completed" ? "(no text)" : "No answer."));
  card.append(label, body);
  $("answer-slot").replaceChildren(card);
  card.scrollIntoView({ block: "nearest" });
}

// Turn one event from the harness into a change on the page.
function onEvent(ev, live) {
  const d = ev.data;
  if (ev.type === "run_started") {
    const limits = `${d.limits.max_steps} calls, $${d.limits.max_usd}, ${d.limits.max_seconds} s`;
    addStep({
      icon: "▸",
      what: "Task received",
      sub: `${d.model} · tools: ${d.tools.join(", ") || "none"} · limits: ${limits}`,
      state: "done",
      raw: d,
    });
  } else if (ev.type === "model_called") {
    live.model = addStep({
      what: `Asking the model · call ${d.step}`,
      sub: `sending ${plural(d.history, "step")} of history`,
      raw: d,
    });
    setStatus(`Working on it… call ${d.step}`, "working");
  } else if (ev.type === "model_replied" && live.model) {
    let what = `Model replied: ${d.status}`;
    if (d.tool_calls.length) what = `Model wants ${d.tool_calls.join(", ")}`;
    else if (d.status === "completed") what = "Model answered";
    updateStep(live.model, {
      icon: "✓",
      what,
      sub: `${d.status} · ${tokenCount(d.usage)} tokens`,
      state: "done",
      cost: money(d.usd),
      raw: d,
    });
  } else if (ev.type === "tool_started") {
    const call = callText(d.name, d.arguments);
    const step = addStep({ what: `Running ${call}`, tag: "tool", raw: d });
    live.tools.set(d.call_id, { step, call });
  } else if (ev.type === "tool_finished") {
    const started = live.tools.get(d.call_id);
    if (started) {
      updateStep(started.step, {
        icon: d.is_error ? "✗" : "✓",
        what: `Ran ${started.call}`,
        sub: d.output,
        state: d.is_error ? "error" : "done",
        raw: d,
      });
    }
  } else if (ev.type === "run_finished") {
    const summary = `${plural(d.model_calls, "call")} · ${money(d.usd)} · ${d.seconds.toFixed(1)} s`;
    if (d.outcome === "completed") setStatus(`✓ Completed in ${summary}`, "completed");
    else if (d.outcome === "stopped") setStatus(`Stopped (${d.reason}) · ${summary}`, "stopped");
    else setStatus(`✗ Failed · ${summary}`, "failed");
    // A model call that never got its reply (time limit, error) is marked, not left spinning.
    if (live.model?.row.classList.contains("working")) updateStep(live.model, { icon: "✗", state: "error" });
    showAnswer(d);
  }
}

async function runTask(event) {
  event.preventDefault();
  const task = $("task").value.trim();
  const send = $("send");
  if (!task || send.disabled) return;
  send.disabled = true;
  $("empty-state").hidden = true;
  $("timeline").replaceChildren();
  $("answer-slot").replaceChildren();
  $("task-echo").textContent = task;
  setStatus("Working on it…", "working");

  const live = { model: null, tools: new Map() }; // rows still waiting for their result
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { ...PAGE_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify({ task, mode: currentMode() }),
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    for await (const ev of readLines(response)) onEvent(ev, live);
  } catch (error) {
    setStatus(`✗ ${error.message}`, "failed");
  } finally {
    send.disabled = false;
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
for (const input of document.querySelectorAll('input[name="mode"]')) {
  input.addEventListener("change", updateModeHint);
}
addEventListener("hashchange", showView);
showView();
loadHealth();
