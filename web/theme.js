"use strict";
// Executado no head: somente preferência visual, sem dados financeiros.
(() => {
  const system = matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  try {
    const saved = localStorage.getItem("walleturbo-theme");
    if (["system", "light", "dark"].includes(saved)) preference = saved;
  } catch {}
  function apply(value = preference, persist = false) {
    document.documentElement.classList.add("theme-changing");
    preference = value;
    const dark = value === "dark" || (value === "system" && system.matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.body?.classList.toggle("dark", dark);
    const select = document.querySelector("#theme-preference");
    if (select) select.value = value;
    const button = document.querySelector("#theme");
    if (button) button.setAttribute("aria-pressed", String(dark));
    if (persist) {
      try { localStorage.setItem("walleturbo-theme", value); } catch {}
    }
    requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.remove("theme-changing")));
  }
  window.walleturboTheme = { apply, get preference() { return preference; } };
  system.addEventListener("change", () => apply());
  apply();
})();
