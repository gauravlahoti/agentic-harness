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
  spot: [], // the elements in the spotlight
  answer: null, // a finished run's turn, framed once its answer is drawn
  centred: { spot: null, height: 0 }, // what the page last scrolled to
  audio: new Audio(),
  analyser: null,
};

const SVG_NS = "http://www.w3.org/2000/svg";
const MIN_GAP = 320; // ms between two events: slow enough for the eye and the spotlight to follow
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
  document.body.append($("tour-spot"), $("tour-stage"));
  // Hidden by its own attributes until now, so a stale stylesheet can never show it (your report).
  for (const name of ["display", "width", "height"]) $("tour-stage").removeAttribute(name);
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
// A turn's question bubble, before any of its events: the voice introduces the ask first.
function openTurn(k) {
  if (tour.turns[k]) return;
  if (k === 0) onEvent({ type: "session_started", data: { session_id: "tour", title: tour.data.chat, new: true } }, null);
  $("empty-state").hidden = true;
  tour.turns[k] = newTurn(tour.data.turns[k].task);
}

const bubbleOf = (turn) => turn.activity.closest(".turn").querySelector(".you");

function feed(i, { quiet = false } = {}) {
  const { ev, turn: k } = tour.flat[i];
  if (tour.turnStart.has(i)) openTurn(k);
  const turn = tour.turns[k];
  // Where this event's lines go: the main list, or a helper's own lane (D-63).
  const helper = ev.data.agent_id;
  const listOf = () => (helper ? turn.lanes.get(helper)?.activity : turn.activity);
  const list = listOf();
  const before = list ? list.children.length : 0;
  onEvent(ev, turn);
  tour.pos = i + 1;
  // A card waiting for another role: switch to that person, as someone at the page would.
  if (ev.type === "approval_requested" && !helper) handOff(ev.data.approver);
  if (quiet) return;
  fire(partOf(ev));
  // The spotlight frames everything this event added (three lines at a run's start, say),
  // and inside a helper's lane its newest line, not the whole lane (your review).
  // A finished run: the answer and its cost line, framed together (your review). The page
  // may still be ticking the checks and draws the answer after them, so wait for it.
  if (ev.type === "run_finished" && !helper) return void (tour.answer = turn);
  const now = listOf();
  const added = now ? [...now.children].slice(now === list ? before : 0) : [];
  if (added.length) tour.spot = added;
  else if (helper && !list && turn.lanes.get(helper)) tour.spot = [turn.lanes.get(helper).box]; // the lane just opened
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
  tour.answer = null;
  tour.audio.pause();
  const steps = tour.data.steps;
  if (startOf(n) < tour.pos) resetReplay(); // going back: replay from the start, quickly
  for (let i = tour.pos; i < startOf(n); i += 1) feed(i, { quiet: true });
  tour.step = n;
  const step = steps[n];
  startStory(step); // a step with beats starts with the model alone (D-191)
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
  const last = tour.turns.at(-1)?.activity.lastElementChild;
  tour.spot = step.card ? [$("tour-card")] : step.scene === "hud" && last ? [last] : [];
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
  chapter();
  const clip = step.audio && !silent ? await loadClip(step.audio) : null;
  if (gen !== tour.gen) return;
  const seconds = clip ? clip.duration : step.seconds;
  // A step that starts a turn: the question appears first, in the spotlight.
  if (tour.turnStart.has(tour.pos) && step.upto > tour.pos) {
    openTurn(tour.turnStart.get(tour.pos));
    tour.spot = [bubbleOf(tour.turns.at(-1))];
  }
  tour.speaking = true;
  const voice = clip ? playClip(gen) : null;
  if (!(await follow(step, seconds, gen, Boolean(clip)))) return;
  if (voice && !(await voice)) return;
  // Whatever the cues left, the step still ends where its `until` says.
  for (let i = tour.pos; i < step.upto; i += 1) {
    if (!(await wait(MIN_GAP, gen))) return;
    feed(i);
  }
  tour.speaking = false;
  // An optional pause to look (`pause`, default none: D-182), then the guide moves on. Not when
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
    tour.voiceFailed = false;
    audio.onended = () => resolve(gen === tour.gen);
    audio.play().catch(() => {
      tour.voiceFailed = true; // blocked: the captions' clock takes over
      resolve(gen === tour.gen);
    });
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

// One clock for the subtitles and the run: where the voice is now (D-180). Each sentence
// and each cue mark sits at a word; a word's time is its share of the voice. With a clip
// the clock is the clip itself, so Pause holds everything.
async function follow(step, seconds, gen, withClip) {
  const parts = sentences(step.say);
  const total = Math.max(step.say.split(/\s+/).length, 1);
  const starts = []; // the word each sentence starts at
  parts.reduce((at, part) => (starts.push(at), at + part.split(/\s+/).length), 0);
  // No cue marks: spread the step's events over three quarters of the voice, as before.
  const span = step.upto - tour.pos;
  const cues = step.cues.length ? step.cues : Array.from({ length: span }, (_, k) => ({ word: Math.round(((k + 1) / span) * total * EVENTS_SHARE), upto: tour.pos + k + 1 }));
  let played = 0; // seconds heard, when there's no clip to ask
  let shown = 0;
  let next = 0; // the next cue to reach
  let popped = 0; // pop marks the voice has passed (D-184)
  let switched = 0; // scene marks the voice has passed (D-185)
  let beaten = 0; // beat marks the voice has passed (D-191)
  let chipped = 0; // chip marks the voice has passed (D-191)
  let due = tour.pos; // play the run up to here
  for (;;) {
    const clipClock = withClip && !tour.voiceFailed;
    const at = clipClock ? tour.audio.currentTime : played;
    const word = (at / seconds) * total;
    // The subtitle: the last sentence whose first word the voice has reached.
    let i = 0;
    while (i + 1 < parts.length && starts[i + 1] <= word) i += 1;
    if (!TOUR_RECORD && i !== shown) {
      shown = i;
      const say = $("tour-say");
      say.textContent = parts[i];
      say.classList.remove("enter");
      void say.offsetWidth; // restart the fade for the new sentence
      say.classList.add("enter");
    }
    // The run: every cue the voice has passed; one event per tick, so they cascade in.
    while (next < cues.length && cues[next].word <= word) due = Math.max(due, cues[next++].upto);
    // The diagram: each part pops as the voice names it.
    while (popped < step.pops.length && step.pops[popped].word <= word) pop(step.pops[popped++].part);
    while (switched < step.scenes.length && step.scenes[switched].word <= word) setScene(step.scenes[switched++].scene);
    while (beaten < step.beats.length && step.beats[beaten].word <= word) beat(step.beats[beaten++].beat);
    while (chipped < step.chip_marks.length && step.chip_marks[chipped].word <= word) chip(step.chip_marks[chipped++].chip);
    if (tour.pos < due) feed(tour.pos);
    const done = (clipClock && tour.audio.ended) || at >= seconds;
    if (done && tour.pos >= due) return true;
    if (!(await wait(MIN_GAP, gen))) return false;
    played += MIN_GAP / 1000;
  }
}

function setPlayLabel(text) {
  $("tour-bar").classList.toggle("is-paused", !tour.playing);
  $("tour-play").textContent = text ?? (TOUR_RECORD ? (tour.playing ? "Pause" : "Play Step") : tour.playing ? "Pause" : "Play");
}

// ── The stage: the step label, the diagram, the spotlight, the orb ─────────
// A new step: its name flashes in the label line, never over the content (your review).
function chapter() {
  const label = document.querySelector(".guide-step");
  label.classList.remove("flash");
  void label.offsetWidth;
  label.classList.add("flash");
}

function setScene(scene) {
  tour.scene = scene;
  $("tour-stage").dataset.scene = scene;
  // The build scene starts bare: each part appears only when the voice pops it (D-185).
  for (const node of $("tour-stage").querySelectorAll(".on")) node.classList.remove("on");
}

// The model-alone story (D-191). Beats add up: once sealed, the jar stays sealed while the
// voice says what the model can and can't do. A step with beats starts with the model alone.
const BEATS = ["think", "reach", "seal", "tell", "bounce"];

function startStory(step) {
  const stage = $("tour-stage");
  for (const name of BEATS) stage.classList.remove(`beat-${name}`);
  delete stage.dataset.beat;
  stage.classList.toggle("has-story", step.beats.length > 0);
  // The step's chips as a roadmap: numbered nodes on a rail, each lit as the voice names it.
  const row = $("stage-chips");
  row.replaceChildren();
  const gap = step.chips.length > 1 ? Math.min(100, 300 / (step.chips.length - 1)) : 0;
  const top = 200 - (gap * (step.chips.length - 1)) / 2; // centred on the stage
  const svg = (tag, attrs, text) => {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
    if (text !== undefined) node.textContent = text;
    return node;
  };
  step.chips.forEach((label, i) => {
    const y = top + i * gap;
    const group = svg("g", { class: "stage-chip" });
    group.dataset.chip = String(i + 1);
    if (i > 0) group.append(svg("line", { class: "chip-rail", x1: 96, y1: y - gap + 22, x2: 96, y2: y - 22, pathLength: 100 }));
    group.append(
      svg("circle", { class: "chip-ripple", cx: 96, cy: y, r: 20 }),
      svg("circle", { class: "chip-node", cx: 96, cy: y, r: 20 }),
      svg("text", { class: "chip-num", x: 96, y: y + 6 }, String(i + 1)),
      svg("text", { class: "chip-text", x: 134, y: y + 6 }, label),
    );
    row.append(group);
  });
}

function beat(name) {
  const stage = $("tour-stage");
  stage.classList.add(`beat-${name}`);
  stage.dataset.beat = name;
}

function chip(n) {
  for (const node of $("stage-chips").querySelectorAll(".now")) node.classList.remove("now");
  $("stage-chips").querySelector(`[data-chip="${n}"]`)?.classList.add("on", "now");
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

// A part named by the voice pops: it swells, glows and settles (D-184).
function pop(part) {
  const node = $("tour-stage").querySelector(`.node-${part}`);
  node.classList.remove("pop");
  void node.getBoundingClientRect(); // restart the animation if it pops twice
  node.classList.add("pop");
  if (tour.scene === "build") {
    node.classList.add("on");
    $("tour-stage").querySelector(`.spoke-${part}`).classList.add("on");
  }
  fire(part);
}

// Hide the guide strip to keep your eyes on the page (D-186): the subtitles and controls fold
// away, the orb stays; the voice and the replay carry on. Show Guide brings it back.
function tuckGuide(tucked) {
  $("tour-bar").classList.toggle("is-tucked", tucked);
  $("tour-show").hidden = !tucked;
  $(tucked ? "tour-show" : "tour-hide").focus();
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
  // A finished run's answer is drawn: frame it with its cost line.
  const done = tour.answer;
  if (done && !done.holding && done.reply.childElementCount) {
    tour.spot = [done.reply, done.meta];
    tour.answer = null;
  }
  // One frame round every element in the spotlight (an event can add several lines).
  const targets = (tour.spot ?? []).filter((node) => node?.isConnected);
  const target = targets.length > 0;
  const pad = 8;
  let box;
  if (target) {
    const rects = targets.map((node) => node.getBoundingClientRect());
    const left = Math.min(...rects.map((r) => r.left));
    const top = Math.min(...rects.map((r) => r.top));
    const right = Math.max(...rects.map((r) => r.right));
    const bottom = Math.max(...rects.map((r) => r.bottom));
    // Never under the guide: the frame stops above its floor.
    const floor = document.querySelector(".dock").getBoundingClientRect().top + 24;
    centre(top, bottom, floor - 24);
    box = { left: left - pad, top: top - pad, width: right - left + pad * 2, height: Math.max(0, Math.min(bottom + pad, floor) - (top - pad)) };
  } else {
    // Nothing to frame: the whole page dims behind the scene.
    box = { left: innerWidth / 2, top: innerHeight * 0.4, width: 0, height: 0 };
  }
  spot.classList.toggle("is-empty", !target);
  place(spot, box);
}

// Scroll the page so the framed lines sit in the middle of the space above the guide, with
// room below them (your review). Only when the frame moves on or grows, so you can still
// scroll freely in between. Too tall to fit: show its end, where the newest line is.
function centre(top, bottom, floor) {
  const height = bottom - top;
  const last = tour.centred;
  if (last.spot === tour.spot && Math.abs(height - last.height) < 40) return;
  tour.centred = { spot: tour.spot, height };
  const fits = height <= floor - 24;
  const delta = fits ? (top + bottom) / 2 - floor / 2 : bottom - (floor - 24);
  if (Math.abs(delta) > 24) scrollBy({ top: delta, behavior: lessMotion() ? "auto" : "smooth" });
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
  // Muted only silences the speaker: the guide is still talking, so the orb keeps moving.
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
    if (section.dataset.tourOpened) {
      section.open = false;
      delete section.dataset.tourOpened;
    }
  }
  // The whole harness: one cyan edge round the pane, not every part tinted (your review).
  $("harness-pane").classList.toggle("tour-whole", part === "pane");
  if (!part) return;
  if (roomForPane()) setPaneOpen(true, false);
  if (part === "pane") return;
  // The part the voice is talking about opens; no tint or edge, so the pane keeps its look (your review).
  const sections = [...document.querySelectorAll(`#pane-body .pane-part.part-${part}`)];
  for (const section of sections) {
    if (!section.open) {
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
// Leave the tour: the voice stops and the normal page opens, with your own chats and the
// composer back. Same page, without ?tour, so nothing from the replay stays behind.
function exitTour() {
  tour.gen += 1;
  tour.audio.pause();
  if (recorder?.state === "recording") recorder.stop();
  location.assign(location.pathname + location.hash);
}

function go(n) {
  if (TOUR_RECORD) {
    tour.playing = false;
    showStep(n); // recording: arrive at the step and wait for you
    setPlayLabel();
  } else playStep(n);
}

// The sidebar's "Want a Guided Tour?": start here, on this page. A reload would lose the
// click, and browsers play sound only after one; so the URL changes without one.
async function startTour() {
  history.pushState(null, "", `?tour${location.hash}`);
  TOUR = true;
  $("tour-invite").hidden = true;
  currentSession = null; // your own chat steps aside; Exit Tour brings it back
  clearThread();
  workItems = [];
  renderWork();
  await setUpTour();
  if (tour.data) playStep(0);
}

// Offer the tour only when the workspace has one.
async function offerTour() {
  try {
    const response = await fetch("/api/tour");
    $("tour-invite").hidden = !response.ok;
  } catch {
    // No tour to offer.
  }
}

$("tour-invite").addEventListener("click", startTour);
// The browser's Back from a tour started here: leave it, like Exit Tour.
addEventListener("popstate", () => {
  if (TOUR && new URLSearchParams(location.search).get("tour") === null) exitTour();
});
{
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
  $("tour-hide").addEventListener("click", () => tuckGuide(true));
  $("tour-show").addEventListener("click", () => tuckGuide(false));
  $("tour-rec").addEventListener("click", toggleRecord);
  $("tour-exit").addEventListener("click", exitTour);
  addEventListener("keydown", (event) => {
    // A hosted copy is the tour (D-189): Escape has nothing to go back to.
    if (TOUR && health?.mode !== "public" && event.key === "Escape" && !event.defaultPrevented) exitTour();
  });
  // A hosted copy opens on the tour, waiting on Start Tour: browsers play sound only after a click.
  const begin = () => {
    if (health?.mode === "public" && !TOUR) {
      history.replaceState(null, "", `?tour${location.hash}`);
      TOUR = true;
      currentSession = null;
      clearThread();
      workItems = [];
      renderWork();
    }
    return TOUR ? setUpTour() : offerTour();
  };
  if (health) begin();
  else addEventListener("harness-ready", begin, { once: true });
}
