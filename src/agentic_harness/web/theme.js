// The light/dark toggle. Two visible states: "follow the system" and "the opposite of it".
// Choosing the theme the system already has removes the saved choice, so the page never
// stays pinned by accident. The new theme spreads out in a circle from the toggle.

const STORAGE_KEY = "color-scheme";
const meta = document.querySelector('meta[name="color-scheme"]');
const systemDark = matchMedia("(prefers-color-scheme: dark)");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

function systemScheme() {
  return systemDark.matches ? "dark" : "light";
}

// What the user sees right now: the pinned theme, or the system's.
function shownScheme() {
  return meta.content === "light" || meta.content === "dark" ? meta.content : systemScheme();
}

function apply(saved) {
  meta.content = saved ?? "light dark";
}

function save(saved) {
  try {
    if (saved) localStorage.setItem(STORAGE_KEY, saved);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked: the theme still changes, it just isn't remembered.
  }
}

// Reveal the new theme in a growing circle centred on the toggle.
function revealFrom(button, change) {
  if (!document.startViewTransition || reduceMotion.matches) {
    change();
    return;
  }
  const box = button.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  const transition = document.startViewTransition(change);
  transition.ready.then(() => {
    document.documentElement.animate(
      { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
      {
        duration: 600,
        easing: "cubic-bezier(0.22, 1, 0.36, 1)",
        pseudoElement: "::view-transition-new(root)",
      },
    );
  });
}

const toggle = document.getElementById("theme-toggle");
toggle.addEventListener("click", () => {
  const target = shownScheme() === "dark" ? "light" : "dark";
  // Same as the system → back to "follow the system"; otherwise remember it.
  const saved = target === systemScheme() ? null : target;
  save(saved);
  revealFrom(toggle, () => apply(saved));
});

// Another tab changed the theme: follow it, without animation.
addEventListener("storage", (event) => {
  if (event.key === STORAGE_KEY || event.key === null) {
    apply(event.newValue === "light" || event.newValue === "dark" ? event.newValue : null);
  }
});
