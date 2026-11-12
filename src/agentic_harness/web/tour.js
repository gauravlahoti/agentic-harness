// The guided tour (S13, D-168–D-179). Plain JS, loaded after app.js and using its functions.
//
// /?tour plays the workspace's recorded runs, step by step. A voice orb speaks each step in
// subtitles, one sentence at a time (D-178). A living diagram shows the model as a brain in
// a jar, then the harness around it; during the replay each event lights its part (D-179).
// The page dims and a spotlight follows the newest line, while the Harness pane opens the
// part being explained. Events go through app.js's own onEvent(), so the replay draws
// exactly what a live run draws (D-171). /?tour=record adds a recorder for your voice (D-176).
//
// Does not: call a model, send a run or an approval (app.js stops both in tour mode), or
// know any workspace: every word comes from GET /api/tour.

const tour = {
  data: null,
  flat: [], // every event, all turns in order: { ev, turn }
  turnStart: new Map(), // event index → the turn it starts
  turns: [], // the page's turn objects, made as each turn starts
  step: -1,
  pos: 0, // how many events have been played
  playing: false,
  started: false, // the spotlight dims the page only once the tour is under way
  speaking: false,
  muted: false,
  gen: 0, // bumped on every jump, so an old step's timers stop
  show: null,
  scene: "jar",
  spot: null, // the element in the spotlight
  audio: new Audio(),
  analyser: null,
};

const MIN_GAP = 150; // ms between two events: fast enough to follow, slow enough to see
const MAX_GAP = 1500;
const EVENTS_SHARE = 0.75; // events fill this share of a step, so the voice can finish on them
const lessMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// Which harness part each kind of event belongs to: the diagram lights it (D-179). The
// harness's own event names, so this knows no workspace.
const PART_OF = {
  run_started: "context",
  context_trimmed: "context",
  model_called: "loop",
  model_replied: "loop",
  plan_updated: "loop",
  verify_started: "loop",
  verify_finished: "loop",
  run_finished: "loop",
  tool_started: "tools",
  tool_finished: "tools",
  file_saved: "tools",
  agent_switched: "tools",
  agent_finished: "tools",
  scope_checked: "guard",
  limits_checked: "guard",
  action_checked: "guard",
  approval_requested: "guard",
  approval_decided: "guard",
};
const MEMORY_TOOLS = new Set(["load_skill", "save_note"]); // the harness's own context tools
const NODE_AT = { loop: [200, 65], tools: [335, 200], guard: [200, 335], context: [65, 200] };

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
// The pane opens beside the chat only where it fits (the page's own rule); on a phone it
// would cover the chat, so there the tour leaves it to you.
const roomForPane = () => matchMedia("(min-width: 1100px)").matches;

// Wait, but only while playing: Pause stops the clock. False if a jump made this step old.
async function wait(ms, gen) {
  for (let left = ms; left > 0; ) {
    await sleep(50);
    if (gen !== tour.gen) return false;
    if (tour.playing) left -= 50;
  }
  return gen === tour.gen;
}

async function setUpTour() {
  let data;
  try {
    const response = await fetch("/api/tour");
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    data = await response.json();
  } catch (error) {
    $("tour-bar").hidden = false;
    $("tour-title").textContent = "No tour";
    $("tour-say").textContent = `Couldn't load the tour: ${error.message}`;
    for (const id of ["tour-back", "tour-play", "tour-next", "tour-mute"]) $(id).disabled = true;
    return;
  }
  tour.data = data;
  tour.flat = [];
  data.turns.forEach((turn, k) => {
    tour.turnStart.set(tour.flat.length, k);
    for (const ev of turn.events) tour.flat.push({ ev, turn: k });
  });
  document.body.classList.add("tour-mode");
  document.body.classList.toggle("tour-recording", TOUR_RECORD);
  // The stage floats over everything: out of the chat's layout, into <body>.
  document.body.append($("tour-spot"), $("tour-chapter"), $("tour-stage"));
  $("tour-stage").hidden = false;
  // Whose view and which model the run was recorded with. Not remembered: the tour
  // mustn't change your own page's choices.
  if (data.profile && [...$("profile").options].some((o) => o.value === data.profile)) $("profile").value = data.profile;
  if (data.model && [...$("model").options].some((o) => o.value === data.model)) $("model").value = data.model;
  setPerson(data.person ?? null);
  if (roomForPane()) setPaneOpen(true, false);
  loadPane();
  $("tour-bar").hidden = false;
  $("tour-rec-box").hidden = !TOUR_RECORD;
  $("tour-dots").replaceChildren(...data.steps.map((s) => Object.assign(el("li", "tour-tick"), { title: s.title })));
  // The pane redraws itself (a new profile, a model change): keep the step's part open.
  new MutationObserver(() => markPart(tour.show)).observe($("pane-body"), { childList: true });
  showStep(0);
  $("tour-play").textContent = TOUR_RECORD ? "Play Step" : "Start Tour";
  requestAnimationFrame(frame);
}

// ── Playing events ─────────────────────────────────────────────────────────
function feed(i, { quiet = false } = {}) {
  const { ev, turn: k } = tour.flat[i];
  if (tour.turnStart.has(i)) {
    if (k === 0) onEvent({ type: "session_started", data: { session_id: "tour", title: tour.data.chat, new: true } }, null);
    $("empty-state").hidden = true;
    tour.turns[k] = newTurn(tour.data.turns[k].task);
  }
  onEvent(ev, tour.turns[k]);
  tour.pos = i + 1;
  // A card waiting for another role: switch to that person, as someone at the page would.
  if (ev.type === "approval_requested" && !ev.data.agent_id) handOff(ev.data.approver);
  if (quiet) return;
  fire(partOf(ev));
  const turn = tour.turns[k];
  tour.spot = ev.type === "run_finished" && !ev.data.agent_id && turn.reply.childElementCount ? turn.reply : turn.activity.lastElementChild;
}

function partOf(ev) {
  if (ev.type === "tool_started" || ev.type === "tool_finished") {
    if (MEMORY_TOOLS.has(ev.data.name ?? ev.data.tool)) return "context";
  }
  return PART_OF[ev.type] ?? null;
}

function handOff(role) {
  const person = people().find((p) => p.role === role);
  if (person && person.id !== currentPerson()?.id) setPerson(person.id);
}

// Back to an empty chat: the start of the tour.
function resetReplay() {
  clearThread();
  tour.turns = [];
  tour.pos = 0;
  currentSession = null;
  workItems = [];
  renderWork();
  setPerson(tour.data.person ?? null);
  $("empty-state").hidden = false;
}

const startOf = (n) => (n > 0 ? tour.data.steps[n - 1].upto : 0);

// Show step n, its events up to where it starts already played (instantly).
function showStep(n) {
  tour.gen += 1;
  tour.audio.pause();
  const steps = tour.data.steps;
  if (startOf(n) < tour.pos) resetReplay(); // going back: replay from the start, quickly
  for (let i = tour.pos; i < startOf(n); i += 1) feed(i, { quiet: true });
  tour.step = n;
  const step = steps[n];
  $("tour-count").textContent = `${String(n + 1).padStart(2, "0")} of ${String(steps.length).padStart(2, "0")}`;
  $("tour-title").textContent = step.title;
  // Recording: the whole paragraph is your script. Playing: the first sentence, then the
  // captions follow the voice.
  $("tour-say").textContent = TOUR_RECORD ? step.say : sentences(step.say)[0];
  [...$("tour-dots").children].forEach((tick, i) => {
    tick.className = `tour-tick${i < n ? " done" : i === n ? " now" : ""}`;
  });
  $("tour-countdown").textContent = "";
  tour.speaking = false;
  $("tour-back").disabled = n === 0;
  $("tour-next").disabled = n === steps.length - 1;
  setScene(step.scene);
  showCard(step.card);
  tour.spot = step.card ? $("tour-card") : step.scene === "hud" ? (tour.turns.at(-1)?.activity.lastElementChild ?? null) : null;
  markPart(step.show);
  noteClip(step);
}

// Play step n: events spread over the clip (or its reading time), a pause, then the next.
async function playStep(n, { silent = false } = {}) {
  showStep(n);
  const gen = tour.gen;
  const step = tour.data.steps[n];
  tour.playing = true;
  tour.started = true;
  hearVoice();
  setPlayLabel();
  chapter(n, step.title);
  const clip = step.audio && !silent ? await loadClip(step.audio) : null;
  if (gen !== tour.gen) return;
  const seconds = clip ? clip.duration : step.seconds;
  const count = step.upto - tour.pos;
  const gap = Math.min(MAX_GAP, Math.max(MIN_GAP, (seconds * 1000 * EVENTS_SHARE) / Math.max(count, 1)));
  tour.speaking = true;
  const voice = clip ? playClip(gen) : wait(seconds * 1000, gen);
  captions(step, seconds, gen, Boolean(clip));
  for (let i = tour.pos; i < step.upto; i += 1) {
    if (!(await wait(gap, gen))) return;
    feed(i);
  }
  if (!(await voice) || gen !== tour.gen) return;
  tour.speaking = false;
  // A pause to look, counted down by Next, then the guide moves on (D-178). Not when
  // recording, nor after the last step.
  if (n < tour.data.steps.length - 1 && !TOUR_RECORD) {
    for (let left = tour.data.pause; left > 0; left -= 1) {
      $("tour-countdown").textContent = `Next in ${left} s`;
      if (!(await wait(1000, gen))) return;
    }
    return playStep(n + 1);
  }
  tour.playing = false;
  setPlayLabel(n === tour.data.steps.length - 1 && !TOUR_RECORD ? "Start Again" : undefined);
}

// ── Voice ──────────────────────────────────────────────────────────────────
// A clip and its length. A browser's own recording (WebM) often says its length is
// "Infinity" until read to the end: seeking far ahead makes it work the length out.
function loadClip(url) {
  return new Promise((resolve) => {
    const audio = tour.audio;
    const done = () => resolve(Number.isFinite(audio.duration) ? { duration: audio.duration } : null);
    audio.onloadedmetadata = () => {
      if (Number.isFinite(audio.duration)) return done();
      audio.ontimeupdate = () => {
        audio.ontimeupdate = null;
        audio.currentTime = 0;
        done();
      };
      audio.currentTime = 1e9;
    };
    audio.onerror = () => resolve(null); // a missing clip: the reading time instead
    audio.muted = tour.muted;
    audio.src = url;
    audio.load();
  });
}

// Play the loaded clip; resolves when it ends. Pause pauses it; a jump stops it.
function playClip(gen) {
  const audio = tour.audio;
  audio.currentTime = 0;
  return new Promise((resolve) => {
    audio.onended = () => resolve(gen === tour.gen);
    audio.play().catch(() => resolve(gen === tour.gen)); // blocked: go on without sound
  });
}

// The orb listens to the real voice: its frequencies shape the ring. Made on the first
// click (browsers allow sound only after one); without it the orb still breathes.
function hearVoice() {
  if (tour.analyser) return tour.analyser.context.resume();
  try {
    const context = new AudioContext();
    const source = context.createMediaElementSource(tour.audio);
    tour.analyser = context.createAnalyser();
    tour.analyser.fftSize = 128;
    source.connect(tour.analyser);
    tour.analyser.connect(context.destination);
  } catch {
    tour.analyser = null;
  }
}

// The caption: one sentence at a time, each given its share of the voice by its word
// count. An estimate, not word-exact subtitles (D-178); Pause holds it with the voice.
function sentences(text) {
  return text.match(/[^.!?]+[.!?]+["')\]]*|[^.!?]+$/g)?.map((s) => s.trim()).filter(Boolean) ?? [text];
}

async function captions(step, seconds, gen, withClip) {
  if (TOUR_RECORD) return; // the whole script stays up while you read it
  const parts = sentences(step.say);
  const words = parts.map((p) => p.split(/\s+/).length);
  const total = words.reduce((a, b) => a + b, 0);
  let played = 0; // seconds of the step heard so far, when there's no clip to ask
  let shown = 0;
  for (;;) {
    const at = withClip ? tour.audio.currentTime : played;
    let end = 0;
    let i = 0;
    for (; i < parts.length - 1; i += 1) {
      end += (words[i] / total) * seconds;
      if (at < end) break;
    }
    if (i !== shown) {
      shown = i;
      const say = $("tour-say");
      say.textContent = parts[i];
      say.classList.remove("enter");
      void say.offsetWidth; // restart the fade for the new sentence
      say.classList.add("enter");
    }
    if (at >= seconds || (withClip && tour.audio.ended)) return;
    if (!(await wait(100, gen))) return;
    played += 0.1;
  }
}

function setPlayLabel(text) {
  $("tour-bar").classList.toggle("is-paused", !tour.playing);
  $("tour-play").textContent = text ?? (TOUR_RECORD ? (tour.playing ? "Pause" : "Play Step") : tour.playing ? "Pause" : "Play");
}

// ── The stage: chapter titles, the diagram, the spotlight, the orb ─────────
function chapter(n, title) {
  const card = $("tour-chapter");
  card.replaceChildren(el("span", "chapter-no", String(n + 1).padStart(2, "0")), el("span", "chapter-title", title));
  card.hidden = false;
  card.classList.remove("show");
  void card.offsetWidth;
  card.classList.add("show");
}

function setScene(scene) {
  tour.scene = scene;
  $("tour-stage").dataset.scene = scene;
}

// One part lights up and a pulse runs from it to the model.
function fire(part) {
  if (!part) return;
  const node = $("tour-stage").querySelector(`.node-${part}`);
  node.classList.remove("fire");
  void node.getBoundingClientRect();
  node.classList.add("fire");
  if (lessMotion()) return;
  const [x, y] = NODE_AT[part];
  const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  dot.setAttribute("r", "6");
  dot.setAttribute("class", `stage-pulse pulse-${part}`);
  $("stage-particles").append(dot);
  dot.animate([{ transform: `translate(${x}px, ${y}px)`, opacity: 1 }, { transform: "translate(200px, 200px)", opacity: 0.2 }], { duration: 700, easing: "cubic-bezier(0.5, 0, 0.2, 1)" }).finished.then(() => dot.remove());
}

// Every frame: the diagram's place, the spotlight's frame and the orb's voice.
function frame(time) {
  placeStage();
  placeSpot();
  drawOrb(time);
  requestAnimationFrame(frame);
}

function placeStage() {
  const stage = $("tour-stage");
  const chat = $("view-agent").getBoundingClientRect();
  let size;
  let left;
  let top;
  if (tour.scene !== "hud") {
    // A big scene: centred over the chat, above the subtitles.
    size = Math.min(620, chat.width * 0.96, innerHeight * 0.64);
    left = chat.left + chat.width / 2 - size / 2;
    top = Math.max(12, innerHeight * 0.4 - size * 0.55);
  } else {
    // The live diagram: in the gap beside the chat, if there is one.
    const pane = $("harness-pane");
    const edge = pane.hidden ? innerWidth : pane.getBoundingClientRect().left;
    const room = edge - chat.right;
    size = Math.min(210, room - 24);
    left = chat.right + (room - size) / 2;
    top = innerHeight - size * 1.1 - 40;
  }
  place(stage, { left, top, width: Math.max(size, 0) });
  stage.classList.toggle("is-away", size < 140);
}

// Move an element, only when it moved. Through element.style: the page's security policy
// blocks style attributes, not the style object.
function place(node, box) {
  for (const [key, value] of Object.entries(box)) {
    const px = `${Math.round(value)}px`;
    if (node.style[key] !== px) node.style[key] = px;
  }
}

function placeSpot() {
  const spot = $("tour-spot");
  spot.hidden = !tour.started;
  if (!tour.started) return;
  const target = tour.spot?.isConnected ? tour.spot : null;
  const pad = 8;
  let box;
  if (target) {
    const r = target.getBoundingClientRect();
    box = { left: r.left - pad, top: r.top - pad, width: r.width + pad * 2, height: Math.min(r.height + pad * 2, innerHeight * 0.7) };
  } else {
    // Nothing to frame: the whole page dims behind the scene.
    box = { left: innerWidth / 2, top: innerHeight * 0.4, width: 0, height: 0 };
  }
  spot.classList.toggle("is-empty", !target);
  place(spot, box);
}

const bins = new Uint8Array(64);
function drawOrb(time) {
  const canvas = $("guide-avatar");
  const g = canvas.getContext("2d");
  const size = canvas.width;
  const mid = size / 2;
  const color = getComputedStyle(canvas).color;
  g.clearRect(0, 0, size, size);
  // How loud the voice is right now: the real audio when there is a clip, else a gentle
  // made-up rhythm while the captions run, else a slow breath.
  let levels = null;
  if (tour.analyser && !tour.audio.paused) {
    tour.analyser.getByteFrequencyData(bins);
    if (bins.some((v) => v > 0)) levels = [...bins].map((v) => v / 255);
  }
  if (!levels) {
    const talking = tour.speaking && tour.playing;
    levels = [...bins].map((_, i) => (talking ? 0.35 + 0.3 * Math.abs(Math.sin(time / 180 + i * 0.7) * Math.sin(time / 310 + i)) : 0.08 + 0.05 * Math.sin(time / 900)));
  }
  const loud = levels.reduce((a, b) => a + b, 0) / levels.length;
  const core = size * 0.22 + loud * size * 0.07;
  // The ring: one bar per frequency, mirrored so it reads as a whole.
  g.lineCap = "round";
  g.strokeStyle = color;
  g.lineWidth = 2.4;
  g.shadowColor = color;
  g.shadowBlur = 12;
  const bars = 48;
  for (let i = 0; i < bars; i += 1) {
    const level = levels[(i < bars / 2 ? i : bars - i) % levels.length];
    const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
    const inner = core + 8;
    const outer = inner + 4 + level * size * 0.16;
    g.globalAlpha = 0.35 + level * 0.65;
    g.beginPath();
    g.moveTo(mid + Math.cos(angle) * inner, mid + Math.sin(angle) * inner);
    g.lineTo(mid + Math.cos(angle) * outer, mid + Math.sin(angle) * outer);
    g.stroke();
  }
  // The core: a glowing sphere.
  g.globalAlpha = 1;
  g.shadowBlur = 28;
  const fill = g.createRadialGradient(mid - core * 0.35, mid - core * 0.4, core * 0.1, mid, mid, core);
  fill.addColorStop(0, "#e9fffb");
  fill.addColorStop(0.45, color);
  fill.addColorStop(1, "rgba(0, 40, 36, 0.9)");
  g.fillStyle = fill;
  g.beginPath();
  g.arc(mid, mid, core, 0, Math.PI * 2);
  g.fill();
  g.shadowBlur = 0;
}

// ── The pane part and the card ─────────────────────────────────────────────
function markPart(part) {
  tour.show = part;
  for (const section of document.querySelectorAll("#pane-body .pane-part")) {
    section.classList.remove("tour-glow");
    if (section.dataset.tourOpened) {
      section.open = false;
      delete section.dataset.tourOpened;
    }
  }
  if (!part) return;
  if (roomForPane()) setPaneOpen(true, false);
  const sections = part === "pane" ? [...document.querySelectorAll("#pane-body .pane-part")] : [...document.querySelectorAll(`#pane-body .pane-part.part-${part}`)];
  for (const section of sections) {
    section.classList.add("tour-glow");
    if (part !== "pane" && !section.open) {
      section.open = true;
      section.dataset.tourOpened = "1";
    }
  }
  sections[0]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// The step's card, from Markdown: tables by hand, everything else by app.js's renderProse,
// which builds elements and never parses HTML.
function showCard(markdown) {
  const card = $("tour-card");
  card.hidden = !markdown;
  card.replaceChildren();
  // Before the run starts the chat is empty: a big scene or a card takes its place.
  if (tour.pos === 0) $("empty-state").hidden = Boolean(markdown) || tour.scene !== "hud";
  if (!markdown) return;
  // Runs of table lines become a table; the lines between them are prose.
  let run = [];
  const flush = () => {
    if (!run.length) return;
    if (run[0].trim().startsWith("|")) card.append(cardTable(run));
    else {
      const prose = el("div", "tour-card-text");
      renderProse(prose, run.join("\n").trim());
      card.append(prose);
    }
    run = [];
  };
  for (const line of markdown.split("\n")) {
    if (run.length && line.trim().startsWith("|") !== run[0].trim().startsWith("|")) flush();
    run.push(line);
  }
  flush();
}

function cardTable(lines) {
  const cells = (line) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  const rows = lines.filter((line) => !/^\|[\s:|-]+\|$/.test(line.trim()));
  const table = el("table", "tour-table");
  const head = el("tr");
  head.append(...cells(rows[0]).map((c) => el("th", null, c)));
  table.append(el("thead"), el("tbody"));
  table.tHead.append(head);
  for (const row of rows.slice(1)) {
    const tr = el("tr");
    tr.append(...cells(row).map((c) => el("td", null, c)));
    table.tBodies[0].append(tr);
  }
  return table;
}

// ── Recording your voice (D-176) ───────────────────────────────────────────
let recorder = null;
let micStream = null;
let recordTick = 0;

function noteClip(step) {
  if (!TOUR_RECORD) return;
  $("tour-rec").textContent = "Record";
  $("tour-rec").classList.remove("is-on");
  $("tour-rec-note").textContent = step.audio ? "Clip saved: Record again to replace it" : `No clip yet · about ${Math.round(step.seconds)} s to read`;
}

async function toggleRecord() {
  if (recorder?.state === "recording") return recorder.stop();
  try {
    micStream ??= await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: true, autoGainControl: true } });
  } catch (error) {
    $("tour-rec-note").textContent = `No microphone: ${error.message}`;
    return;
  }
  const type = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
  recorder = new MediaRecorder(micStream, { mimeType: type, audioBitsPerSecond: 64000 });
  const chunks = [];
  const step = tour.data.steps[tour.step];
  recorder.ondataavailable = (e) => chunks.push(e.data);
  recorder.onstop = () => saveTake(step, new Blob(chunks, { type: recorder.mimeType }));
  recorder.start();
  const started = Date.now();
  $("tour-rec").textContent = "Stop";
  $("tour-rec").classList.add("is-on");
  recordTick = setInterval(() => {
    const s = Math.round((Date.now() - started) / 1000);
    $("tour-rec-note").textContent = `● Recording · ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 250);
  playStep(tour.step, { silent: true }); // the step plays while you speak, without the old take
}

async function saveTake(step, blob) {
  clearInterval(recordTick);
  $("tour-rec").textContent = "Record";
  $("tour-rec").classList.remove("is-on");
  $("tour-rec-note").textContent = "Saving…";
  try {
    const response = await fetch(`/api/tour/audio/${encodeURIComponent(step.id)}`, {
      method: "PUT",
      headers: { ...PAGE_HEADER, "Content-Type": blob.type || "audio/webm" },
      body: blob,
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText);
    const fresh = await (await fetch("/api/tour")).json();
    step.audio = fresh.steps.find((s) => s.id === step.id)?.audio ?? null;
    $("tour-rec-note").textContent = `Saved · ${Math.round(blob.size / 1000)} KB. Play Step to hear it.`;
  } catch (error) {
    $("tour-rec-note").textContent = `Not saved: ${error.message}`;
  }
}

// ── Controls ───────────────────────────────────────────────────────────────
function go(n) {
  if (TOUR_RECORD) {
    tour.playing = false;
    showStep(n); // recording: arrive at the step and wait for you
    setPlayLabel();
  } else playStep(n);
}

if (TOUR) {
  $("tour-play").addEventListener("click", () => {
    const label = $("tour-play").textContent;
    if (label === "Start Tour" || label === "Start Again") return playStep(0);
    if (label === "Play Step") return playStep(tour.step);
    tour.playing = !tour.playing;
    if (tour.playing) tour.audio.src && tour.audio.paused && !tour.audio.ended && tour.audio.play().catch(() => {});
    else tour.audio.pause();
    setPlayLabel();
  });
  $("tour-back").addEventListener("click", () => go(Math.max(0, tour.step - 1)));
  $("tour-next").addEventListener("click", () => go(Math.min(tour.data.steps.length - 1, tour.step + 1)));
  $("tour-mute").addEventListener("click", () => {
    tour.muted = !tour.muted;
    tour.audio.muted = tour.muted; // muted, the clip still sets the pace; the caption carries on
    const mute = $("tour-mute");
    mute.setAttribute("aria-pressed", String(tour.muted));
    mute.title = tour.muted ? "Unmute" : "Mute";
    mute.querySelector(".visually-hidden").textContent = mute.title;
  });
  $("tour-rec").addEventListener("click", toggleRecord);
  if (health) setUpTour();
  else addEventListener("harness-ready", setUpTour, { once: true });
}
