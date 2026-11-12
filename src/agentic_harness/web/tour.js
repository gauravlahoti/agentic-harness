// The guided tour (S13, D-168–D-177). Plain JS, loaded after app.js and using its functions.
//
// /?tour plays the workspace's recorded runs, step by step: each step shows its caption,
// opens its Harness pane part, plays your clip, and feeds its events to app.js's own
// onEvent(), so the replay draws exactly what a live run draws (D-171). When the clip ends,
// the next step starts (D-170). /?tour=record adds a recorder for your voice (D-176).
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
  muted: false,
  gen: 0, // bumped on every jump, so an old step's timers stop
  show: null,
  audio: new Audio(),
};

const MIN_GAP = 150; // ms between two events: fast enough to follow, slow enough to see
const MAX_GAP = 1500;
const EVENTS_SHARE = 0.75; // events fill this share of a step, so the voice can finish on them

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
  // Whose view and which model the run was recorded with. Not remembered: the tour
  // mustn't change your own page's choices.
  if (data.profile && [...$("profile").options].some((o) => o.value === data.profile)) $("profile").value = data.profile;
  if (data.model && [...$("model").options].some((o) => o.value === data.model)) $("model").value = data.model;
  setPerson(data.person ?? null);
  if (roomForPane()) setPaneOpen(true, false);
  loadPane();
  $("tour-bar").hidden = false;
  $("tour-rec-box").hidden = !TOUR_RECORD;
  // The pane redraws itself (a new profile, a model change): keep the step's part open.
  new MutationObserver(() => markPart(tour.show)).observe($("pane-body"), { childList: true });
  showStep(0);
  $("tour-play").textContent = TOUR_RECORD ? "Play Step" : "Start Tour";
}

// ── Playing events ─────────────────────────────────────────────────────────
function feed(i) {
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
  for (let i = tour.pos; i < startOf(n); i += 1) feed(i);
  tour.step = n;
  const step = steps[n];
  $("tour-count").textContent = `${n + 1} of ${steps.length}`;
  $("tour-title").textContent = step.title;
  $("tour-say").textContent = step.say;
  $("tour-fill").style.width = `${((n + 1) / steps.length) * 100}%`;
  $("tour-back").disabled = n === 0;
  $("tour-next").disabled = n === steps.length - 1;
  showCard(step.card);
  markPart(step.show);
  noteClip(step);
}

// Play step n: events spread over the clip (or its reading time), then the next step.
async function playStep(n, { silent = false } = {}) {
  showStep(n);
  const gen = tour.gen;
  const step = tour.data.steps[n];
  tour.playing = true;
  setPlayLabel();
  const clip = step.audio && !silent ? await loadClip(step.audio) : null;
  if (gen !== tour.gen) return;
  const seconds = clip ? clip.duration : step.seconds;
  const count = step.upto - tour.pos;
  const gap = Math.min(MAX_GAP, Math.max(MIN_GAP, (seconds * 1000 * EVENTS_SHARE) / Math.max(count, 1)));
  const voice = clip ? playClip(gen) : wait(seconds * 1000, gen);
  for (let i = tour.pos; i < step.upto; i += 1) {
    if (!(await wait(gap, gen))) return;
    feed(i);
  }
  if (!(await voice) || gen !== tour.gen) return;
  // The voice leads (D-170): on to the next step, unless recording or at the end.
  if (n < tour.data.steps.length - 1 && !TOUR_RECORD && tour.playing) return playStep(n + 1);
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

function setPlayLabel(text) {
  $("tour-play").textContent = text ?? (TOUR_RECORD ? (tour.playing ? "Pause" : "Play Step") : tour.playing ? "Pause" : "Play");
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
  if (tour.pos === 0) $("empty-state").hidden = Boolean(markdown);
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
    $("tour-mute").textContent = tour.muted ? "Unmute" : "Mute";
    $("tour-mute").setAttribute("aria-pressed", String(tour.muted));
  });
  $("tour-rec").addEventListener("click", toggleRecord);
  if (health) setUpTour();
  else addEventListener("harness-ready", setUpTour, { once: true });
}
