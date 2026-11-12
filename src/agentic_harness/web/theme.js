// The light/dark toggle. Dark is the default, like gauravlahoti.dev (D-179); light is the
// other state. Choosing dark again removes the saved choice, so the page never stays pinned
// by accident. The new theme spreads out in a circle from the toggle.

const STORAGE_KEY = "theme"; // new name (D-179): old "light" pins from the system-following days don't count
const meta = document.querySelector('meta[name="color-scheme"]');
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

const DEFAULT_SCHEME = "dark";

// What the user sees right now: the saved theme, or the default.
function shownScheme() {
  return meta.content === "light" ? "light" : DEFAULT_SCHEME;
}

function apply(saved) {
  meta.content = saved ?? DEFAULT_SCHEME;
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
  // The default needs no saving; only light is remembered.
  const saved = target === DEFAULT_SCHEME ? null : target;
  save(saved);
  revealFrom(toggle, () => apply(saved));
});

// Another tab changed the theme: follow it, without animation.
addEventListener("storage", (event) => {
  if (event.key === STORAGE_KEY || event.key === null) {
    apply(event.newValue === "light" || event.newValue === "dark" ? event.newValue : null);
  }
});
