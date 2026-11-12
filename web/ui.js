"use strict";
// Primitivas compartilhadas, sem dependências de runtime ou acesso à API.
const uiPaths = {
  overview: ["M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"],
  transactions: ["M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"],
  wallet: ["M20 7V5a2 2 0 0 0-2-2H6a3 3 0 0 0 0 6h15v12H6a3 3 0 0 1-3-3V6", "M21 12h-5v5h5"],
  contactless: ["M7 9a5 5 0 0 1 0 6M11 6a9 9 0 0 1 0 12M15 3a13 13 0 0 1 0 18"],
  chart: ["M4 3v17h17M8 15v-4m5 4V7m5 8v-5"],
  target: ["M21 12a9 9 0 1 1-9-9 9 9 0 0 1 9 9Z", "M17 12a5 5 0 1 1-5-5 5 5 0 0 1 5 5ZM12 10v4m-2-2h4"],
  shield: ["M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4Z", "m8 12 3 3 5-6"],
  more: ["M4 12h1m6 0h1m6 0h1"],
  theme: ["M20 15a8 8 0 0 1-11-11 9 9 0 1 0 11 11Z"],
  plus: ["M12 4v16M4 12h16"],
  upload: ["M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"],
  download: ["M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"],
  income: ["M12 3v17m-6-6 6 6 6-6"],
  expense: ["M12 21V4m-6 6 6-6 6 6"],
  empty: ["M4 7h16v14H4zM8 7V3h8v4M9 13h6"],
  close: ["m6 6 12 12M18 6 6 18"],
};
function uiIcon(name) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  for (const [key, value] of Object.entries({ viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.75", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false", class: "ui-icon" })) svg.setAttribute(key, value);
  for (const d of uiPaths[name] || uiPaths.empty) {
    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}
function uiStatus(text, kind = "info") {
  const target = document.querySelector("#status");
  target.dataset.kind = kind;
  target.setAttribute("role", kind === "error" ? "alert" : "status");
  target.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
  target.textContent = text;
}
let uiSubmission = null, uiId = 0;
const uiReturnFocus = new WeakMap();
let uiPendingReturn = null;
function uiRestoreFocus() {
  if (uiPendingReturn && !uiPendingReturn.isConnected && document.activeElement === document.body) document.querySelector("#page-title").focus();
  uiPendingReturn = null;
}
async function requestCloseDialog(dialog) {
  if (dialog.querySelector('[aria-busy="true"]')) return;
  if (dialog.dataset.dirty === "true" && !await confirmAction("Descartar os valores ainda não salvos deste formulário?")) return;
  dialog.close();
}
function uiClearErrors(root) {
  root.querySelectorAll(".field-error,.dialog-error").forEach((node) => node.remove());
  root.querySelectorAll('[aria-invalid="true"]').forEach((field) => {
    field.removeAttribute("aria-invalid");
    const ids = (field.getAttribute("aria-describedby") || "").split(" ").filter((id) => document.getElementById(id));
    if (ids.length) field.setAttribute("aria-describedby", ids.join(" "));
    else field.removeAttribute("aria-describedby");
  });
}
function uiFieldError(field, text) {
  if (!field.hasAttribute("aria-label") && field.closest("label")) field.setAttribute("aria-label", field.closest("label").textContent.trim());
  if (!field.id) field.id = `field-${++uiId}`;
  const id = `${field.id}-error`;
  let error = document.getElementById(id);
  if (!error) {
    error = document.createElement("span");
    error.id = id;
    error.className = "field-error";
    field.after(error);
  }
  error.textContent = text;
  field.setAttribute("aria-invalid", "true");
  const ids = new Set((field.getAttribute("aria-describedby") || "").split(" ").filter(Boolean));
  ids.add(id);
  field.setAttribute("aria-describedby", [...ids].join(" "));
}
function uiFormError(root, error) {
  uiClearErrors(root);
  const summary = document.createElement("div");
  summary.className = "dialog-error";
  summary.setAttribute("role", "alert");
  summary.tabIndex = -1;
  const heading = document.createElement("strong");
  heading.textContent = "Confira antes de continuar";
  const description = document.createElement("p");
  description.textContent = error.message;
  summary.append(heading, description);
  const candidates = [];
  if (error.field) {
    const field = [...root.querySelectorAll("input,select")].find((node) => node.name === error.field && node.type !== "hidden");
    if (field) candidates.push([field, error.message]);
  }
  for (const detail of error.fields || []) {
    const key = detail.loc?.at(-1);
    const name = { amount_cents: "amount", target_cents: "target", saved_cents: "saved", buffer_cents: "buffer" }[key] || key;
    const field = [...root.querySelectorAll("input,select")].find((node) => node.name === name && node.type !== "hidden");
    if (field) candidates.push([field, "Confira o valor informado neste campo."]);
  }
  if (error.inputValue !== undefined) {
    const field = [...root.querySelectorAll('input[inputmode="decimal"],input[name="amount"]')].find((node) => node.value.trim().replace(/^-/, "") === error.inputValue);
    if (field) candidates.push([field, error.message]);
  }
  for (const [field, text] of candidates) {
    uiFieldError(field, text);
    const link = document.createElement("a");
    link.href = `#${field.id}`;
    link.textContent = field.getAttribute("aria-label") || field.closest("label")?.childNodes[0]?.textContent.trim() || "Corrigir campo";
    link.onclick = (event) => { event.preventDefault(); field.focus(); };
    summary.append(link);
  }
  const first = root.querySelector(".section-heading");
  if (first) first.after(summary); else root.prepend(summary);
  summary.focus();
}
function uiBusy(form) {
  if (!form) return () => {};
  form.dataset.uiBusy = "true";
  form.setAttribute("aria-busy", "true");
  const buttons = [...form.querySelectorAll('button[type="submit"],button:not([type])')];
  const releaseButtons = buttons.map((button) => uiButtonBusy(button));
  // O bloqueio de submit é central; os módulos mantêm seu próprio disabled/versionamento.
  return () => {
    delete form.dataset.uiBusy;
    form.removeAttribute("aria-busy");
    releaseButtons.forEach((release) => release());
  };
}
function uiButtonBusy(button) {
  const nodes = [...button.childNodes];
  const oldName = button.getAttribute("aria-label");
  const original = document.createElement("span"), current = document.createElement("span");
  original.className = "busy-original";
  original.setAttribute("aria-hidden", "true");
  original.append(...nodes);
  current.className = "busy-current";
  current.textContent = "Processando…";
  button.dataset.uiBusy = "true";
  button.setAttribute("aria-disabled", "true");
  button.setAttribute("aria-label", "Processando, aguarde");
  button.replaceChildren(original, current);
  return () => {
    button.replaceChildren(...nodes);
    delete button.dataset.uiBusy;
    button.removeAttribute("aria-disabled");
    if (oldName === null) button.removeAttribute("aria-label"); else button.setAttribute("aria-label", oldName);
  };
}
async function confirmAction(description) {
  const dialog = document.querySelector("#confirm-dialog");
  if (dialog.open) return false;
  const invoker = document.activeElement;
  document.querySelector("#confirm-description").textContent = description;
  const destructive = /excluir|remover|descartar/i.test(description);
  document.querySelector("#confirm-title").textContent = /descartar/i.test(description) ? "Descartar alterações?" : destructive ? "Confirmar exclusão" : "Confirmar alteração";
  dialog.querySelector('[value="confirm"]').textContent = /descartar/i.test(description) ? "Descartar alterações" : destructive ? "Confirmar exclusão" : "Confirmar alteração";
  dialog.returnValue = "cancel";
  return new Promise((resolve) => {
    const listeners = new AbortController();
    const finish = (value) => {
      listeners.abort();
      if (dialog.open) dialog.close(value);
      if (invoker?.isConnected) invoker.focus();
      resolve(value === "confirm");
    };
    dialog.querySelector("form").addEventListener("submit", (event) => {
      event.preventDefault();
      finish(event.submitter?.value || "cancel");
    }, { signal: listeners.signal });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); finish("cancel"); }, { signal: listeners.signal });
    // Um close antigo pode chegar depois de reabrir o mesmo diálogo no Chromium.
    dialog.addEventListener("close", () => { if (!dialog.open) finish(dialog.returnValue); }, { signal: listeners.signal });
    dialog.showModal();
    dialog.querySelector('[value="cancel"]').focus();
  });
}
function uiRoute() {
  const [name, query = ""] = location.hash.slice(1).split("?");
  const month = new URLSearchParams(query).get("month");
  return { view: ["overview", "transactions", "finance", "planning", "goals", "privacy"].includes(name) ? name : "overview", month: /^\d{4}-(0[1-9]|1[0-2])$/.test(month || "") ? month : null };
}
function uiWriteRoute(name) {
  const month = document.querySelector("#month").value;
  const hash = `#${name}${["goals", "privacy"].includes(name) ? "" : `?month=${month}`}`;
  if (location.hash !== hash) history.pushState(null, "", hash);
}
function uiOverviewBalance(data, state = "ready") {
  const value = document.querySelector("#overview-account-balance");
  const context = document.querySelector("#overview-balance-context");
  value.classList.toggle("balance-unavailable", state !== "ready" || data?.total_cents === null);
  if (state !== "ready") {
    value.textContent = { demo: "Saldo indisponível na demonstração", loading: "Consultando saldos…", error: "Não foi possível consultar o saldo", signedout: "Saldo indisponível" }[state];
    context.textContent = state === "demo" ? "Use uma conta conectada para definir saldos iniciais e consultar seus registros." : state === "loading" ? "Calculando a partir dos seus registros. Aguarde a atualização." : state === "error" ? "Tente atualizar a consulta. Valores anteriores não são exibidos como atuais." : "Conecte sua conta para consultar os saldos.";
    return;
  }
  const date = document.querySelector("#balance-date").value.split("-").reverse().join("/");
  if (!data.accounts.length) {
    value.textContent = "Cadastre sua primeira conta";
    value.classList.add("balance-unavailable");
    context.textContent = "Depois, informe o saldo inicial e a data de referência para começar o cálculo.";
    return;
  }
  value.textContent = data.total_cents === null ? "Saldo total indisponível" : money(data.total_cents);
  context.textContent = data.total_cents === null ? `Em ${date} · Subtotal conhecido: ${money(data.known_subtotal_cents)} · ${data.unknown_accounts} ${data.unknown_accounts === 1 ? "conta sem referência aplicável" : "contas sem referência aplicável"}. ${data.unassigned_transactions} ${data.unassigned_transactions === 1 ? "lançamento sem conta" : "lançamentos sem conta"}.` : `Saldo em ${date} · ${data.accounts.length} ${data.accounts.length === 1 ? "conta incluída" : "contas incluídas"}.`;
}
function uiEnhance(root = document) {
  root.querySelectorAll("[data-icon]:not([data-icon-ready])").forEach((node) => { node.dataset.iconReady = "true"; node.replaceChildren(uiIcon(node.dataset.icon)); });
  root.querySelectorAll(".icon-button.close:not([data-icon-ready])").forEach((node) => { node.dataset.iconReady = "true"; node.replaceChildren(uiIcon("close")); });
  root.querySelectorAll('input[inputmode="decimal"]:not([data-money-ready]),#opening-form input[name="amount"]:not([data-money-ready])').forEach((field) => {
    field.dataset.moneyReady = "true";
    field.pattern = (field.closest("#opening-form") ? "-?" : "") + "([0-9]{1,9}|[0-9]{1,3}(\\.[0-9]{3}){1,2})([,.][0-9]{1,2})?";
    const label = field.closest("label");
    if (!label) return;
    if (!field.id) field.id = `field-${++uiId}`;
    const help = document.createElement("span");
    help.id = `${field.id}-help`;
    help.className = "field-help";
    help.textContent = "Ex.: 1.234,56";
    if (!field.hasAttribute("aria-label")) field.setAttribute("aria-label", label.textContent.trim());
    field.setAttribute("aria-describedby", [field.getAttribute("aria-describedby"), help.id].filter(Boolean).join(" "));
    label.append(help);
  });
}
document.addEventListener("submit", (event) => {
  if (event.target.method === "dialog") return;
  if (event.target.dataset.uiBusy === "true") { event.preventDefault(); event.stopImmediatePropagation(); return; }
  uiSubmission = event.target;
  uiClearErrors(event.target);
}, true);
document.addEventListener("invalid", (event) => {
  const field = event.target;
  uiFieldError(field, field.validity.valueMissing ? "Preencha este campo para continuar." : field.inputMode === "decimal" ? "Informe um valor em reais. Ex.: 1.234,56." : "Confira o formato e os limites deste campo.");
}, true);
document.addEventListener("input", (event) => {
  const field = event.target;
  if (field.closest("form")) field.closest("form").dataset.dirty = "true";
  const dialog = field.closest("dialog");
  if (dialog && dialog.id !== "confirm-dialog") dialog.dataset.dirty = "true";
  if (field.matches('[aria-invalid="true"]')) {
    document.getElementById(`${field.id}-error`)?.remove();
    field.removeAttribute("aria-invalid");
  }
});
document.addEventListener("DOMContentLoaded", () => {
  uiEnhance();
  document.querySelector(".skip-link").addEventListener("click", (event) => {
    event.preventDefault();
    const title = document.querySelector("#page-title");
    title.focus();
    title.scrollIntoView({ block: "start" });
  });
  document.querySelectorAll("dialog:not(#confirm-dialog)").forEach((dialog) => {
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); requestCloseDialog(dialog); });
    dialog.addEventListener("close", () => {
      uiPendingReturn = uiReturnFocus.get(dialog);
      if (uiPendingReturn?.isConnected) uiPendingReturn.focus();
      requestAnimationFrame(() => { if (uiPendingReturn && !uiPendingReturn.isConnected) uiRestoreFocus(); });
    });
  });
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) for (const node of mutation.addedNodes) if (node.nodeType === Node.ELEMENT_NODE) uiEnhance(node.parentElement || document);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  const more = document.querySelector("#more-navigation");
  const button = document.querySelector("#more-navigation-button");
  const small = matchMedia("(max-width: 1023px)");
  const syncMenu = () => { more.hidden = small.matches && button.getAttribute("aria-expanded") !== "true"; };
  button.onclick = () => { button.setAttribute("aria-expanded", String(button.getAttribute("aria-expanded") !== "true")); syncMenu(); };
  small.addEventListener("change", syncMenu);
  syncMenu();
  document.querySelector("#theme-preference").onchange = (event) => walleturboTheme.apply(event.target.value, true);
  walleturboTheme.apply();
  window.addEventListener("hashchange", () => {
    const route = uiRoute();
    const changed = route.month && route.month !== document.querySelector("#month").value;
    if (changed) document.querySelector("#month").value = route.month;
    showView(route.view, false);
    if (changed) action(refresh);
  });
  document.querySelector("#overview-import").onclick = () => openImport();
  document.querySelector("#overview-new-card").onclick = () => openSetup("card");
  document.querySelector("#clear-search").onclick = () => { document.querySelector("#search").value = ""; renderTransactions(); document.querySelector("#search").focus(); };
});
