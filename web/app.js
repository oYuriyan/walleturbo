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
      if (typeof clearBalances === "function") clearBalances();
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
  const expectedCsrf = csrf,
    expectedDemo = demo;
  let data;
  if (csrf && !demo) {
    data = await api("/api/dashboard?month=" + $("#month").value);
    if (csrf !== expectedCsrf || demo !== expectedDemo) return;
    all = data.transactions;
    goals = data.goals;
  } else {
    data = summary(all.filter((t) => t.date.startsWith($("#month").value)));
  }
  if (typeof loadFinance === "function") await loadFinance();
  if (csrf !== expectedCsrf || demo !== expectedDemo) return;
  if (demo && typeof applyDemoCards === "function") applyDemoCards(data);
  render(data);
  if (typeof loadBalances === "function") await loadBalances();
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
        if (!demo)
          await api(
            `/api/transactions/${t.id}?expected_version=${t.version}`,
            "DELETE",
          );
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
let goalGeneration = 0;
function clearGoalForm() {
  goalGeneration++;
  const form = $("#goal-form");
  form.reset();
  form.querySelectorAll('input[type="hidden"]').forEach((n) => (n.value = ""));
  form.querySelectorAll("input,button").forEach((n) => (n.disabled = true));
  $("#goal-dialog").querySelector(".dialog-error")?.remove();
  if ($("#goal-dialog").open) $("#goal-dialog").close();
}
function goalNode(g, editable) {
  const box = el("div", undefined, editable ? "panel goal" : "goal"),
    head = el("div", undefined, "goal-head"),
    label = el("div");
  box.dataset.goalId = g.id;
  if (g.archived)
    box.append(el("p", "Meta arquivada · fora da simulação", "badge"));
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
      g.archived
        ? "Valores preservados. Reative para incluir no planejamento."
        : g.saved_cents >= g.target_cents
          ? "Meta alcançada. Celebre essa conquista!"
          : g.deadline < today
            ? "Prazo encerrado. Revise seu plano."
            : `${money(Math.ceil((g.target_cents - g.saved_cents) / months))}/mês para chegar lá, sem considerar rendimentos.`,
      "goal-plan",
    ),
  );
  if (editable) {
    const button = el("button", "Gerenciar meta", "text-button");
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
  const active = goals.filter((g) => !g.archived);
  active.slice(0, 2).forEach((g) => preview.append(goalNode(g, false)));
  if (!active.length) empty(preview, "Crie ou reative uma meta para planejar.");
  goals.forEach((g) => list.append(goalNode(g, true)));
  if (!goals.length) {
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
let entryGeneration = 0;
function clearEntryForm() {
  entryGeneration++;
  const f = $("#entry-form");
  f.reset();
  f.querySelectorAll('input[type="hidden"]').forEach((n) => (n.value = ""));
  f.querySelectorAll("input,select,button").forEach((n) => (n.disabled = true));
  f.elements.account_id.replaceChildren();
  $("#entry-origin").textContent = "";
  if ($("#entry-dialog").open) $("#entry-dialog").close();
}
function clearImports() {
  importVersion++;
  csvContent = "";
  importStatementId = null;
  $("#csv-file").value = "";
  $("#import-preview").replaceChildren();
  $("#import-account").replaceChildren();
  $("#confirm-import").disabled = true;
  if ($("#import-dialog").open) $("#import-dialog").close();
}
function openEntry(t) {
  if (!allowed()) return;
  const f = $("#entry-form");
  entryGeneration++;
  f.reset();
  f.querySelectorAll("input,select,button").forEach(
    (n) => (n.disabled = false),
  );
  f.elements.version.value = t?.version || 1;
  f.elements.request_id.value = crypto.randomUUID();
  $("#entry-reason-label").hidden = !t;
  f.elements.reason.required = !!t;
  $("#reload-entry").hidden = !t;
  $("#entry-origin").textContent = t?.imported
    ? "Importado: a origem será preservada. Reimportações não substituem esta correção."
    : "";
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
    populateAccounts(f.elements.account_id, true, t?.account_id);
  f.elements.account_id.value = t?.account_id || "";
  $("#entry-title").textContent = t ? "Revisar lançamento" : "Novo lançamento";
  openDialog("#entry-dialog");
}
function openGoal(g) {
  if (!allowed()) return;
  goalGeneration++;
  const f = $("#goal-form");
  f.reset();
  f.querySelectorAll("input,button").forEach((n) => (n.disabled = false));
  f.elements.version.value = g?.version || 0;
  f.elements.archived.checked = !!g?.archived;
  $("#goal-archive-label").hidden = !g;
  $("#reload-goal").hidden = !g;
  $("#delete-goal").hidden = !g?.archived;
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
$("#reload-entry").onclick = () =>
  action(async () => {
    const id = $("#entry-form").elements.id.value,
      generation = entryGeneration,
      expectedCsrf = csrf;
    if (demo) {
      openEntry(all.find((t) => t.id === id));
      return;
    }
    const [row] = await Promise.all([
      api("/api/transactions/" + id),
      loadFinance(),
    ]);
    if (generation !== entryGeneration || csrf !== expectedCsrf) return;
    openEntry(row);
  });
$("#entry-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      submit = f.querySelector('button[type="submit"]');
    if (submit.disabled) return;
    const generation = entryGeneration,
      id = f.elements.id.value;
    const body = {
      description: f.elements.description.value.trim(),
      date: f.elements.date.value,
      amount_cents: cents(f.elements.amount.value),
      kind: f.elements.kind.value,
      category: f.elements.category.value,
      reviewed: f.elements.reviewed.checked,
      account_id: f.elements.account_id.value || null,
      request_id: f.elements.request_id.value,
    };
    if (id)
      Object.assign(body, {
        expected_version: Number(f.elements.version.value),
        reason: f.elements.reason.value.trim(),
      });
    if (!body.description || body.amount_cents <= 0)
      throw Error("Informe uma descrição e um valor maior que zero.");
    submit.disabled = true;
    try {
      if (demo) {
        const { expected_version, reason, request_id, ...values } = body;
        if (id)
          all = all.map((t) =>
            t.id === id ? { id, ...values, version: (t.version || 1) + 1 } : t,
          );
        else all.push({ id: crypto.randomUUID(), ...values, version: 1 });
      } else
        await api(
          "/api/transactions" + (id ? "/" + id : ""),
          id ? "PUT" : "POST",
          body,
        );
      if (generation !== entryGeneration) return;
      $("#entry-dialog").close();
      await refresh();
      message(
        "Lançamento salvo. Se necessário, altere o período para visualizar a data informada.",
      );
    } finally {
      if (generation === entryGeneration) submit.disabled = !csrf && !demo;
    }
  });
};
$("#goal-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      submit = f.querySelector('button[type="submit"]');
    if (submit.disabled) return;
    const generation = goalGeneration,
      id = f.elements.id.value;
    const body = {
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
    if (id)
      Object.assign(body, {
        archived: f.elements.archived.checked,
        expected_version: Number(f.elements.version.value),
      });
    submit.disabled = true;
    try {
      if (demo) {
        const { expected_version, ...values } = body;
        if (id)
          goals = goals.map((g) =>
            g.id === id ? { id, ...values, version: (g.version || 0) + 1 } : g,
          );
        else
          goals.push({
            id: crypto.randomUUID(),
            ...values,
            archived: false,
            version: 0,
          });
      } else
        await api(
          "/api/goals" + (id ? "/" + id : ""),
          id ? "PUT" : "POST",
          body,
        );
      if (generation !== goalGeneration) return;
      $("#goal-dialog").close();
      await refresh();
      message(
        "Meta salva. A reserva informada não movimenta dinheiro entre contas.",
      );
    } finally {
      if (generation === goalGeneration) submit.disabled = !csrf && !demo;
    }
  });
};
$("#reload-goal").onclick = () =>
  action(async () => {
    const id = $("#goal-form").elements.id.value,
      generation = goalGeneration;
    await refresh();
    if (generation !== goalGeneration || (!csrf && !demo)) return;
    const row = goals.find((g) => g.id === id);
    if (!row) {
      clearGoalForm();
      throw Error("Meta não encontrada. A lista foi atualizada.");
    }
    openGoal(row);
  });
$("#delete-goal").onclick = () =>
  action(async () => {
    const f = $("#goal-form"),
      id = f.elements.id.value,
      generation = goalGeneration;
    if (
      !confirm(
        "Excluir a meta arquivada? A exclusão exige reserva informada igual a zero.",
      )
    )
      return;
    const button = $("#delete-goal");
    if (button.disabled) return;
    button.disabled = true;
    try {
      if (demo) {
        const row = goals.find((g) => g.id === id);
        if (!row?.archived || row.saved_cents)
          throw Error("Arquive a meta e revise a reserva antes de excluir.");
        goals = goals.filter((g) => g.id !== id);
      } else
        await api(
          `/api/goals/${id}?expected_version=${f.elements.version.value}`,
          "DELETE",
        );
      if (generation !== goalGeneration) return;
      $("#goal-dialog").close();
      await refresh();
      message("Meta excluída.");
    } finally {
      if (generation === goalGeneration) button.disabled = !csrf && !demo;
    }
  });
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
$("#import-account").onchange = () => {
  importVersion++;
  csvContent = "";
  $("#import-preview").replaceChildren();
  $("#confirm-import").disabled = true;
  if ($("#csv-file").files[0]) $("#csv-file").onchange();
};
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
    const selectionStatus = el("p");
    selectionStatus.setAttribute("role", "status");
    let acknowledged = !result.possible_duplicates?.length;
    const updateSelection = () => {
      if (version !== importVersion) return;
      const count = $("#import-preview").querySelectorAll(
        "input[data-source-index]:checked",
      ).length;
      selectionStatus.textContent = `${count} de ${result.entries.length} lançamentos selecionados.`;
      $("#confirm-import").disabled =
        !count ||
        !acknowledged ||
        $("#confirm-import").dataset.busy === String(version);
    };
    result.entries.forEach((t, index) => {
      const label = el("label"),
        selected = el("input");
      selected.type = "checkbox";
      selected.checked = true;
      selected.dataset.sourceIndex = index;
      selected.onchange = updateSelection;
      label.append(
        selected,
        document.createTextNode(
          ` Importar lançamento ${index + 1}: ${t.description}`,
        ),
      );
      $("#import-preview").append(label, transactionNode(t, false));
    });
    $("#import-preview").append(selectionStatus);
    if (result.possible_duplicates?.length) {
      $("#confirm-import").disabled = true;
      $("#import-preview").append(
        el(
          "p",
          "Possíveis duplicatas: mesma data, valor e tipo. Descrições podem ser diferentes. Confira antes de importar; compras legítimas podem coincidir. Linhas já conhecidas continuam sujeitas à deduplicação existente.",
        ),
      );
      for (const candidate of result.possible_duplicates) {
        $("#import-preview").append(
          el(
            "p",
            `Linha ${candidate.source_index + 2} do CSV: registros existentes para conferir${candidate.more ? " (mostrando os primeiros 5)" : ""}.`,
          ),
        );
        for (const match of candidate.matches) {
          $("#import-preview").append(
            el(
              "p",
              `${match.date} · ${match.description} · ${money(match.amount_cents)}`,
            ),
          );
        }
        const destinationLabel = el("label"),
          destination = el("select");
        destination.dataset.linkIndex = candidate.source_index;
        const createOption = el(
          "option",
          "Criar ou reconhecer pela origem (sem novo vínculo)",
        );
        createOption.value = "";
        destination.append(createOption);
        for (const match of candidate.matches) {
          const option = el(
            "option",
            `Vincular a: ${match.description} · ${money(match.amount_cents)} · ${match.id.slice(0, 8)}`,
          );
          option.value = match.id;
          option.dataset.version = match.version;
          destination.append(option);
        }
        destinationLabel.append(
          document.createTextNode(
            `Destino do lançamento ${candidate.source_index + 1}`,
          ),
          destination,
        );
        $("#import-preview").append(destinationLabel);
      }
      const label = el("label"),
        acknowledgement = el("input");
      acknowledgement.type = "checkbox";
      acknowledgement.id = "import-acknowledgement";
      acknowledgement.onchange = () => {
        acknowledged = acknowledgement.checked;
        updateSelection();
      };
      label.append(
        acknowledgement,
        document.createTextNode(
          " Conferi os sinais e desejo importar os lançamentos selecionados.",
        ),
      );
      $("#import-preview").append(label);
    }
    updateSelection();
  });
$("#confirm-import").onclick = () =>
  action(async () => {
    if (!csvContent || $("#confirm-import").disabled) return;
    const version = importVersion;
    const excluded = [
      ...$("#import-preview").querySelectorAll(
        "input[data-source-index]:not(:checked)",
      ),
    ].map((input) => Number(input.dataset.sourceIndex));
    const links = [
      ...$("#import-preview").querySelectorAll("select[data-link-index]"),
    ]
      .filter(
        (select) =>
          select.value && !excluded.includes(Number(select.dataset.linkIndex)),
      )
      .map((select) => ({
        source_index: Number(select.dataset.linkIndex),
        resource_id: select.value,
        expected_version: Number(select.selectedOptions[0].dataset.version),
      }));
    $("#confirm-import").dataset.busy = String(version);
    $("#confirm-import").disabled = true;
    try {
      const result = await api(
        importStatementId
          ? `/api/statements/${importStatementId}/import/confirm`
          : "/api/import/confirm",
        "POST",
        {
          content: csvContent,
          excluded_indices: excluded,
          links,
          ...(!importStatementId
            ? { account_id: $("#import-account").value || null }
            : {}),
        },
      );
      if (version !== importVersion) return;
      $("#import-dialog").close();
      await refresh();
      message(
        `${result.created} lançamentos importados; ${result.duplicates} linhas já conhecidas ignoradas.${result.linked ? ` ${result.linked} origens vinculadas a registros existentes.` : ""}${result.skipped ? ` ${result.skipped} não selecionados nesta importação.` : ""}${result.removed ? ` ${result.removed} excluídas anteriormente não foram recriadas.` : ""} Revise as categorias.`,
      );
    } finally {
      if ($("#confirm-import").dataset.busy === String(version))
        delete $("#confirm-import").dataset.busy;
      if (version === importVersion) {
        $("#import-preview input[data-source-index]")?.dispatchEvent(
          new Event("change"),
        );
      }
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
