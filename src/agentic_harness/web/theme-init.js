// Runs before the first paint (not deferred): apply a saved theme so the page never
// flashes the wrong one. Kept tiny on purpose; the toggle itself lives in theme.js.
try {
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") {
    document.querySelector('meta[name="color-scheme"]').content = saved;
  }
} catch {
  // Storage blocked (private mode, site data off): follow the system theme.
}
