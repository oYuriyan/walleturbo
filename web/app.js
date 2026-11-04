"use strict";
const $ = (s) => document.querySelector(s);
const money = (n) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(
    n / 100,
  );
const categories = [
  "Moradia",
  "Alimentação",
  "Transporte",
  "Saúde",
  "Educação",
  "Lazer",
  "Assinaturas",
  "Compras",
  "Renda",
  "Outros",
];
const now = new Date(),
  today = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
let demo = false,
  csrf = "",
  all = [],
  goals = [],
  csvContent = "",
  view = "overview",
  importStatementId = null;
$("#month").value = today.slice(0, 7);
// Apenas preferência visual fica no navegador. Dados financeiros da demonstração ficam em memória.
try {
  document.body.classList.toggle(
    "dark",
    localStorage.getItem("walleturbo-theme") === "dark",
  );
} catch {}
function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function message(text) {
  $("#status").textContent = text;
}
function empty(target, text) {
  const box = el("div", undefined, "empty");
  box.append(el("span", "◎"), el("div", text));
  target.append(box);
}
async function api(path, method = "GET", body, headers = {}) {
  const response = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {}
    if (response.status === 401) {
      csrf = "";
      $("#login").hidden = false;
      $("#logout").hidden = true;
      $("#mode").textContent = "Sessão encerrada";
      all = [];
      goals = [];
      if (typeof clearFinance === "function") clearFinance();
      if (typeof clearPlanning === "function") clearPlanning();
      render(summary([]));
    }
    throw Error(
      typeof detail === "string"
        ? detail
        : "Confira os campos e tente novamente.",
    );
  }
  return response.status === 204 ? null : response.json();
}
async function action(fn) {
  try {
    await fn();
  } catch (e) {
    message(e.message);
    const dialog = document.querySelector("dialog[open]");
    if (dialog) {
      let error = dialog.querySelector(".dialog-error");
      if (!error) {
        error = el("p", undefined, "dialog-error");
        error.setAttribute("role", "alert");
        dialog.append(error);
      }
      error.textContent = e.message;
    }
  }
}
function allowed() {
  if (!demo && !csrf) {
    message(
      "Entre na sua conta ou explore a demonstração com dados fictícios.",
    );
    return false;
  }
  return true;
}
function summary(entries) {
  const sums = {
    income_cents: 0,
    expense_cents: 0,
    categories: {},
    insights: [],
  };
  entries.forEach((t) => {
    sums[t.kind === "income" ? "income_cents" : "expense_cents"] +=
      t.amount_cents;
    if (t.kind === "expense")
      sums.categories[t.category] =
        (sums.categories[t.category] || 0) + t.amount_cents;
  });
  sums.balance_cents = sums.income_cents - sums.expense_cents;
  if (sums.categories.Assinaturas)
    sums.insights.push({
      title: "Revise suas assinaturas",
      description:
        "Confira quais serviços ainda são úteis. Este valor não é uma economia garantida.",
      amount_cents: sums.categories.Assinaturas,
    });
  if (sums.balance_cents < 0)
    sums.insights.push({
      title: "Saídas acima das entradas",
      description: "Confira se todas as receitas foram registradas.",
      amount_cents: -sums.balance_cents,
    });
  return sums;
}
async function refresh() {
  let data;
  if (csrf && !demo) {
    data = await api("/api/dashboard?month=" + $("#month").value);
    all = data.transactions;
    goals = data.goals;
  } else {
    data = summary(all.filter((t) => t.date.startsWith($("#month").value)));
  }
  if (typeof loadFinance === "function") await loadFinance();
  if (demo && typeof applyDemoCards === "function") applyDemoCards(data);
  render(data);
  if (view === "planning" && typeof loadPlanning === "function")
    await loadPlanning();
}
function render(data) {
  $("#cash-result").textContent =
    "Movimentação líquida de caixa: " +
    money(data.cash_balance_cents ?? data.balance_cents);
  $("#card-result").textContent =
    "Pagamentos de fatura no mês: " + money(data.card_payment_cents || 0);
  $("#balance").textContent = money(data.balance_cents);
  $("#income").textContent = money(data.income_cents);
  $("#expense").textContent = money(data.expense_cents);
  const cat = $("#categories");
  cat.replaceChildren();
  const entries = Object.entries(data.categories).sort((a, b) => b[1] - a[1]);
  if (!entries.length)
    empty(cat, "Suas categorias aparecerão com os primeiros lançamentos.");
  entries.forEach(([name, value]) => {
    const row = el("div", undefined, "category-row"),
      label = el("div", undefined, "category-label");
    label.append(el("span", name), el("strong", money(value)));
    row.append(label, progress(value, data.expense_cents, name));
    cat.append(row);
  });
  const ins = $("#insights");
  ins.replaceChildren();
  if (!data.insights.length)
    empty(
      ins,
      "Ainda não há alertas para este período. Continue acompanhando.",
    );
  data.insights.forEach((i) => {
    const card = el("div", undefined, "insight");
    card.append(
      el("strong", i.title),
      el("p", i.description),
      el("b", money(i.amount_cents)),
    );
    ins.append(card);
  });
  renderTransactions();
  renderGoals();
  if (typeof renderFinance === "function") renderFinance();
}
function progress(value, max, label) {
  const wrap = el("div", undefined, "track"),
    bar = el("progress");
  bar.max = Math.max(1, max);
  bar.value = value;
  bar.setAttribute("aria-label", label);
  wrap.append(bar);
  return wrap;
}
function transactionNode(t, editable) {
  const row = el("div", undefined, "transaction"),
    info = el("div", undefined, "transaction-info");
  info.append(
    el("strong", t.description),
    el("small", `${t.category} · ${t.date.split("-").reverse().join("/")}`),
  );
  if (!t.reviewed) info.append(el("div", "Revisão pendente", "pending"));
  row.append(
    el("div", t.kind === "income" ? "↓" : "↑", "transaction-icon"),
    info,
    el(
      "strong",
      (t.kind === "income" ? "+ " : "− ") + money(t.amount_cents),
      "transaction-amount " + (t.kind === "income" ? "positive" : ""),
    ),
  );
  if (editable) {
    const actions = el("div", undefined, "row-actions"),
      edit = el("button", "Revisar"),
      del = el("button", "Excluir");
    edit.onclick = () => openEntry(t);
    del.onclick = () =>
      action(async () => {
        if (!confirm(`Excluir o lançamento “${t.description}”?`)) return;
        if (!demo) await api("/api/transactions/" + t.id, "DELETE");
        all = all.filter((x) => x.id !== t.id);
        await refresh();
        message("Lançamento excluído.");
      });
    actions.append(edit, del);
    row.append(actions);
  }
  return row;
}
function renderTransactions() {
  const entries = all
      .filter((t) => t.date.startsWith($("#month").value))
      .sort((a, b) => b.date.localeCompare(a.date)),
    recent = $("#recent"),
    list = $("#transaction-list");
  recent.replaceChildren();
  list.replaceChildren();
  entries.slice(0, 4).forEach((t) => recent.append(transactionNode(t, false)));
  const search = $("#search").value.toLocaleLowerCase("pt-BR");
  const filtered = entries.filter((t) =>
    (t.description + " " + t.category)
      .toLocaleLowerCase("pt-BR")
      .includes(search),
  );
  filtered.forEach((t) => list.append(transactionNode(t, true)));
  if (!entries.length)
    empty(
      recent,
      "Seu primeiro lançamento é o começo de uma visão mais clara.",
    );
  if (!filtered.length)
    empty(list, "Nenhum lançamento encontrado neste período.");
}
function goalNode(g, editable) {
  const box = el("div", undefined, editable ? "panel goal" : "goal"),
    head = el("div", undefined, "goal-head"),
    label = el("div");
  label.append(
    el("strong", g.name),
    el("small", "Até " + g.deadline.split("-").reverse().join("/")),
  );
  head.append(el("span", "◎", "goal-symbol"), label);
  const values = el("div", undefined, "goal-values");
  values.append(
    el("strong", money(g.saved_cents)),
    el("span", "de " + money(g.target_cents)),
  );
  box.append(head, values, progress(g.saved_cents, g.target_cents, g.name));
  const target = new Date(g.deadline + "T12:00:00"),
    months = Math.max(
      1,
      (target.getFullYear() - now.getFullYear()) * 12 +
        target.getMonth() -
        now.getMonth() +
        1,
    );
  box.append(
    el(
      "p",
      g.saved_cents >= g.target_cents
        ? "Meta alcançada. Celebre essa conquista!"
        : g.deadline < today
          ? "Prazo encerrado. Revise seu plano."
          : `${money(Math.ceil((g.target_cents - g.saved_cents) / months))}/mês para chegar lá, sem considerar rendimentos.`,
      "goal-plan",
    ),
  );
  if (editable) {
    const button = el("button", "Atualizar reserva", "text-button");
    button.onclick = () => openGoal(g);
    box.append(button);
  }
  return box;
}
function renderGoals() {
  const preview = $("#goal-preview"),
    list = $("#goal-list");
  preview.replaceChildren();
  list.replaceChildren();
  goals.slice(0, 2).forEach((g) => preview.append(goalNode(g, false)));
  goals.forEach((g) => list.append(goalNode(g, true)));
  if (!goals.length) {
    empty(preview, "Dê um nome ao seu próximo sonho.");
    empty(list, "Crie uma meta para começar a planejar.");
  }
}
function showView(name) {
  view = name;
  document.querySelectorAll(".view").forEach((n) => (n.hidden = n.id !== name));
  document.querySelectorAll(".nav[data-view]").forEach((n) => {
    n.classList.toggle("active", n.dataset.view === name);
    if (n.dataset.view === name) n.setAttribute("aria-current", "page");
    else n.removeAttribute("aria-current");
  });
}
function openDialog(id) {
  const d = $(id);
  d.querySelector(".dialog-error")?.remove();
  d.showModal();
}
function openEntry(t) {
  if (!allowed()) return;
  const f = $("#entry-form");
  f.reset();
  f.elements.id.value = t?.id || "";
  f.elements.description.value = t?.description || "";
  f.elements.amount.value = t
    ? (t.amount_cents / 100).toFixed(2).replace(".", ",")
    : "";
  f.elements.date.value = t?.date || today;
  f.elements.kind.value = t?.kind || "expense";
  f.elements.category.value = t?.category || "Outros";
  f.elements.reviewed.checked = true;
  if (typeof populateAccounts === "function")
    populateAccounts(f.elements.account_id, true);
  f.elements.account_id.value = t?.account_id || "";
  $("#entry-title").textContent = t ? "Revisar lançamento" : "Novo lançamento";
  openDialog("#entry-dialog");
}
function openGoal(g) {
  if (!allowed()) return;
  const f = $("#goal-form");
  f.reset();
  f.elements.id.value = g?.id || "";
  f.elements.name.value = g?.name || "";
  f.elements.target.value = g
    ? (g.target_cents / 100).toFixed(2).replace(".", ",")
    : "";
  f.elements.saved.value = g
    ? (g.saved_cents / 100).toFixed(2).replace(".", ",")
    : "0";
  f.elements.deadline.value = g?.deadline || "";
  openDialog("#goal-dialog");
}
function cents(value) {
  if (!/^\d{1,9}([,.]\d{1,2})?$/.test(value))
    throw Error("Informe um valor válido com até duas casas decimais.");
  const [whole, decimal = ""] = value.replace(",", ".").split(".");
  return Number(whole) * 100 + Number(decimal.padEnd(2, "0"));
}
categories.forEach((c) => $("#category-options").append(el("option", c)));
document
  .querySelectorAll("[data-view]")
  .forEach((b) => (b.onclick = () => showView(b.dataset.view)));
document
  .querySelectorAll('[data-action="new-entry"]')
  .forEach((b) => (b.onclick = () => openEntry()));
document
  .querySelectorAll('[data-action="new-goal"]')
  .forEach((b) => (b.onclick = () => openGoal()));
document
  .querySelectorAll(".close")
  .forEach((b) => (b.onclick = () => b.closest("dialog").close()));
$("#theme").onclick = () => {
  document.body.classList.toggle("dark");
  try {
    localStorage.setItem(
      "walleturbo-theme",
      document.body.classList.contains("dark") ? "dark" : "light",
    );
  } catch {}
};
// O seletor de tema permanece acessível também em telas pequenas.
const mobileTheme = el("button", "◐", "ghost");
mobileTheme.setAttribute("aria-label", "Alternar tema");
mobileTheme.onclick = () => $("#theme").click();
$(".topbar>div").append(mobileTheme);
$("#month").onchange = () =>
  action(async () => {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test($("#month").value))
      throw Error("Selecione um mês válido.");
    await refresh();
  });
$("#search").oninput = renderTransactions;
$("#demo").onclick = () => {
  message("");
  demo = true;
  csrf = "";
  const month = $("#month").value;
  all = [
    ["Salário", 650000, "income", "Renda", "01"],
    ["Aluguel", 180000, "expense", "Moradia", "02"],
    ["Mercado da semana", 28490, "expense", "Alimentação", "03"],
    ["Café com amigos", 6800, "expense", "Lazer", "03"],
    ["Spotify", 2190, "expense", "Assinaturas", "02"],
    ["Uber", 2490, "expense", "Transporte", "03"],
    ["Netflix", 5590, "expense", "Assinaturas", "01"],
  ].map(([description, amount_cents, kind, category, day], i) => ({
    id: "demo-" + i,
    date: month + "-" + day,
    description,
    amount_cents,
    kind,
    category,
    reviewed: i < 4,
  }));
  goals = [
    {
      id: "goal-demo",
      name: "Minha reserva de emergência",
      target_cents: 1500000,
      saved_cents: 450000,
      deadline: now.getFullYear() + 1 + "-12-01",
    },
    {
      id: "goal-demo-2",
      name: "Uma viagem para desacelerar",
      target_cents: 800000,
      saved_cents: 210000,
      deadline: now.getFullYear() + 1 + "-06-01",
    },
  ];
  $("#mode").textContent = "Demonstração";
  $("#notice").firstElementChild.textContent =
    "Dados fictícios, somente nesta aba. Alterações serão descartadas ao recarregar.";
  $("#demo").hidden = true;
  seedFinance();
  action(refresh);
};
$("#entry-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      id = f.elements.id.value,
      body = {
        description: f.elements.description.value.trim(),
        date: f.elements.date.value,
        amount_cents: cents(f.elements.amount.value),
        kind: f.elements.kind.value,
        category: f.elements.category.value,
        reviewed: f.elements.reviewed.checked,
        account_id: f.elements.account_id.value || null,
      };
    if (body.amount_cents <= 0 || !body.description)
      throw Error("Informe uma descrição e um valor maior que zero.");
    if (demo) {
      if (id) all = all.map((t) => (t.id === id ? { id, ...body } : t));
      else all.push({ id: crypto.randomUUID(), ...body });
    } else
      await api(
        "/api/transactions" + (id ? "/" + id : ""),
        id ? "PUT" : "POST",
        body,
      );
    $("#entry-dialog").close();
    await refresh();
    message(
      "Lançamento salvo. Se necessário, altere o período para visualizar a data informada.",
    );
  });
};
$("#goal-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      id = f.elements.id.value,
      body = {
        name: f.elements.name.value.trim(),
        target_cents: cents(f.elements.target.value),
        saved_cents: cents(f.elements.saved.value),
        deadline: f.elements.deadline.value,
      };
    if (
      !body.name ||
      body.target_cents <= 0 ||
      body.saved_cents > body.target_cents
    )
      throw Error(
        "Informe uma meta positiva e uma reserva que não ultrapasse o objetivo.",
      );
    if (demo) {
      if (id) goals = goals.map((g) => (g.id === id ? { id, ...body } : g));
      else goals.push({ id: crypto.randomUUID(), ...body });
    } else
      await api("/api/goals" + (id ? "/" + id : ""), id ? "PUT" : "POST", body);
    $("#goal-dialog").close();
    await refresh();
    message("Meta atualizada.");
  });
};
$("#import-button").onclick = () => openImport();
function openImport(statementId = null) {
  importStatementId = statementId;
  $("#import-account-label").hidden = !!statementId;
  populateAccounts($("#import-account"), true);
  importVersion++;
  if (!allowed()) return;
  if (demo) {
    message(
      "A importação CSV usa a API autenticada. Conecte sua conta; na demonstração, use lançamentos manuais.",
    );
    return;
  }
  csvContent = "";
  $("#csv-file").value = "";
  $("#import-preview").replaceChildren();
  $("#confirm-import").disabled = true;
  openDialog("#import-dialog");
}
let importVersion = 0;
$("#csv-file").onchange = () =>
  action(async () => {
    const version = ++importVersion;
    csvContent = "";
    $("#confirm-import").disabled = true;
    $("#import-preview").replaceChildren();
    const file = $("#csv-file").files[0];
    if (!file) return;
    if (file.size > 256000) throw Error("Arquivo excede 256 KB.");
    const content = await file.text(),
      result = await api(
        importStatementId
          ? `/api/statements/${importStatementId}/import/preview`
          : "/api/import/preview",
        "POST",
        {
          content,
          ...(!importStatementId
            ? { account_id: $("#import-account").value || null }
            : {}),
        },
      );
    if (version !== importVersion) return;
    csvContent = content;
    $("#import-preview").append(
      el(
        "p",
        `${result.entries.length} lançamentos encontrados. Categorias sugeridas por regras; revise após importar.`,
      ),
    );
    result.entries.forEach((t) =>
      $("#import-preview").append(transactionNode(t, false)),
    );
    $("#confirm-import").disabled = false;
  });
$("#confirm-import").onclick = () =>
  action(async () => {
    $("#confirm-import").disabled = true;
    try {
      const result = await api(
        importStatementId
          ? `/api/statements/${importStatementId}/import/confirm`
          : "/api/import/confirm",
        "POST",
        {
          content: csvContent,
          ...(!importStatementId
            ? { account_id: $("#import-account").value || null }
            : {}),
        },
      );
      $("#import-dialog").close();
      await refresh();
      message(
        `${result.created} lançamentos importados; ${result.duplicates} duplicados ignorados. Revise as categorias.`,
      );
    } finally {
      $("#confirm-import").disabled = false;
    }
  });
$("#logout").onclick = () =>
  action(async () => {
    await api("/api/logout", "POST");
    location.reload();
  });
$("#export").onclick = () =>
  action(async () => {
    if (!allowed()) return;
    const data = demo
        ? { transactions: all, goals, ...exportDemoFinance() }
        : await api("/api/privacy/export"),
      url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      ),
      link = el("a");
    link.href = url;
    link.download = "walleturbo-dados.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
$("#erase").onclick = () => {
  if (allowed()) openDialog("#delete-dialog");
};
$("#delete-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    if (e.target.elements.confirmation.value !== "EXCLUIR")
      throw Error("Digite EXCLUIR.");
    if (!demo)
      await api("/api/privacy/data", "DELETE", undefined, {
        "X-Confirm-Delete": "EXCLUIR",
      });
    all = [];
    goals = [];
    clearFinance();
    csrf = "";
    $("#delete-dialog").close();
    await refresh();
    if (!demo) {
      $("#login").hidden = false;
      $("#logout").hidden = true;
      $("#mode").textContent = "Não conectado";
    }
    message("Dados financeiros ativos excluídos.");
  });
};
(async () => {
  render(summary([]));
  try {
    const response = await fetch("/api/me");
    if (response.ok) {
      const me = await response.json();
      csrf = me.csrf;
      $("#mode").textContent = "Conta conectada";
      $("#login").hidden = true;
      $("#logout").hidden = false;
      $("#notice").hidden = true;
      await refresh();
    } else if (response.status !== 401)
      message("Conexão indisponível. A demonstração continua disponível.");
  } catch {
    message("Conexão indisponível. A demonstração continua disponível.");
  }
})();
