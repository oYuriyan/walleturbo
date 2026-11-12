"use strict";
let financeAccounts = [],
  financeCards = [],
  financeStatements = [];
let financeGeneration = 0;
let overviewSelectedCardId = null;
function clearFinance() {
  overviewSelectedCardId = null;
  financeGeneration++;
  for (const name of [
    "setup",
    "purchase",
    "payment",
    "reconcile",
    "review-charge",
  ]) {
    const f = $("#" + name + "-form");
    f.reset();
    f.querySelectorAll('input[type="hidden"]').forEach((n) => (n.value = ""));
    for (const key of ["account_id", "card_id"])
      f.elements[key]?.replaceChildren();
    const dialog = $("#" + name + "-dialog");
    dialog.querySelector(".dialog-error")?.remove();
    if (dialog.open) dialog.close();
  }
  if (typeof clearEntryForm === "function") clearEntryForm();
  if (typeof clearImports === "function") clearImports();
  if (typeof clearPdf === "function") clearPdf();
  if (typeof clearPaymentCorrection === "function") clearPaymentCorrection();
  if (typeof clearCorrection === "function") clearCorrection();
  if (typeof clearHistory === "function") clearHistory();
  if (typeof clearGoalForm === "function") clearGoalForm();
  if (typeof clearLifecycle === "function") clearLifecycle();
  if (typeof clearBalances === "function") clearBalances();
  financeAccounts = [];
  financeCards = [];
  financeStatements = [];
}
function exportDemoFinance() {
  return {
    accounts: financeAccounts,
    cards: financeCards,
    statements: financeStatements,
  };
}
function seedFinance() {
  financeAccounts = [{ id: crypto.randomUUID(), name: "Conta principal" }];
  financeCards = [
    { id: crypto.randomUUID(), name: "Cartão do dia a dia", due_day: 10 },
  ];
  financeStatements = [];
}
async function loadFinance() {
  if (demo || !csrf) return;
  const expectedCsrf = csrf,
    generation = ++financeGeneration,
    month = $("#month").value;
  const data = await Promise.all([
    api("/api/accounts"),
    api("/api/cards"),
    api("/api/statements?month=" + month),
  ]);
  if (
    csrf !== expectedCsrf ||
    demo ||
    generation !== financeGeneration ||
    month !== $("#month").value
  )
    return;
  [financeAccounts, financeCards, financeStatements] = data;
}
function totals(statement) {
  if (!demo) return statement;
  const total = statement.charges.reduce(
      (a, c) => a + c.amount_cents * (c.kind === "refund" ? -1 : 1),
      0,
    ),
    paid = statement.payments.reduce((a, p) => a + p.amount_cents, 0);
  return {
    ...statement,
    total_cents: total,
    paid_cents: paid,
    remaining_cents: total - paid,
    pending: statement.charges.filter((c) => !c.reviewed).length,
  };
}
function applyDemoCards(data) {
  const selected = financeStatements.filter(
      (s) => s.month === $("#month").value,
    ),
    paid = financeStatements
      .flatMap((s) => s.payments)
      .filter((p) => p.date.startsWith($("#month").value))
      .reduce((a, p) => a + p.amount_cents, 0);
  data.cash_balance_cents = data.balance_cents - paid;
  data.card_payment_cents = paid;
  for (const s of selected)
    for (const c of s.charges) {
      const amount = c.amount_cents * (c.kind === "refund" ? -1 : 1);
      data.expense_cents += amount;
      data.balance_cents -= amount;
      data.categories[c.category] = (data.categories[c.category] || 0) + amount;
    }
  data.insights = data.insights.filter((insight) => insight.title !== "Saídas acima das entradas");
  if (data.balance_cents < 0) data.insights.push({ title: "Saídas acima das entradas", description: "Confira se todas as receitas foram registradas.", amount_cents: -data.balance_cents });
}
function populate(select, rows, emptyLabel) {
  select.replaceChildren();
  if (emptyLabel) {
    const o = el("option", emptyLabel);
    o.value = "";
    select.append(o);
  }
  rows.forEach((row) => {
    const o = el("option", row.name);
    o.value = row.id;
    select.append(o);
  });
}
function populateAccounts(select, optional = false, currentId = null) {
  const rows = financeAccounts
    .filter((a) => !a.archived || a.id === currentId)
    .map((a) => ({ ...a, name: a.name + (a.archived ? " · Arquivada" : "") }));
  populate(select, rows, optional ? "Sem conta vinculada" : null);
}
function button(label, fn, cls = "ghost") {
  const b = el("button", label, cls);
  b.type = "button";
  b.onclick = () => action(async () => {
    if (b.disabled) return;
    b.disabled = true;
    const release = uiButtonBusy(b);
    try { await fn(); }
    finally { release(); b.disabled = false; }
  });
  return b;
}
function localStatement(card, month) {
  let s = financeStatements.find(
    (s) => s.card_id === card.id && s.month === month,
  );
  if (!s) {
    const [year, m] = month.split("-").map(Number),
      day = Math.min(card.due_day, new Date(year, m, 0).getDate());
    s = {
      id: crypto.randomUUID(),
      card_id: card.id,
      month,
      due_date: month + "-" + String(day).padStart(2, "0"),
      status: "open",
      charges: [],
      payments: [],
      expected_cents: null,
    };
    financeStatements.push(s);
  }
  return s;
}
function renderOverviewCards() {
  const target = $("#overview-cards"), options = $("#overview-card-options");
  target.replaceChildren();
  options.replaceChildren();
  const month = $("#month").value;
  const available = financeCards.filter((card) => !card.archived || financeStatements.some((bill) => bill.card_id === card.id && bill.month === month));
  $("#overview-card-count").textContent = available.length > 2 ? `(2 de ${available.length})` : available.length ? `(${available.length})` : "";
  if (!available.length) {
    overviewSelectedCardId = null;
    empty(target, csrf || demo ? "Seus cartões e faturas ficam a um toque daqui." : "Conecte sua conta para acompanhar os cartões.", csrf || demo ? "Cadastrar cartão" : undefined, () => openSetup("card"));
    return;
  }
  const shown = available.slice(0, 2);
  const card = shown.find((item) => item.id === overviewSelectedCardId) || shown[0];
  overviewSelectedCardId = card.id;
  const raw = financeStatements.find((item) => item.card_id === card.id && item.month === month);
  const bill = raw ? totals(raw) : null;
  const open = () => {
    showView("finance");
    const destination = bill ? document.getElementById("statement-" + bill.id) : $("#card-list").querySelector(`[data-entity-id="${CSS.escape(String(card.id))}"]`);
    if (destination) { destination.tabIndex = -1; destination.focus({ preventScroll: true }); destination.scrollIntoView({ block: "start" }); }
  };
  const stage = el("div", undefined, "card-showcase"), stack = el("div", undefined, "card-stack");
  const access = el("button", undefined, "credit-access");
  access.type = "button";
  access.dataset.cardId = card.id;
  access.title = card.name;
  access.setAttribute("aria-label", `Ver ${bill ? "fatura de " : "cartão "}${card.name} no período selecionado`);
  const face = el("span", undefined, "card-front");
  face.setAttribute("aria-hidden", "true");
  const brand = el("span", "walleturbo.", "card-front-brand"), chip = el("span", undefined, "card-chip");
  const wireless = uiIcon("contactless");
  wireless.classList.add("card-contactless");
  const identity = el("span", undefined, "card-front-identity");
  identity.append(el("span", "Cartão de crédito", "card-front-label"), el("strong", card.name, "card-front-name"));
  face.append(brand, chip, wireless, identity);
  access.append(face);
  access.onclick = open;
  stack.append(access);
  const info = el("div", undefined, "card-information");
  if (card.name.length > 28) info.append(el("strong", card.name, "card-selected-name"));
  const facts = el("dl", undefined, "card-facts");
  const fact = (label, value, cls = "") => {
    const row = el("div");
    row.append(el("dt", label), el("dd", value, cls));
    facts.append(row);
  };
  const billValue = bill ? money(bill.total_cents).replace(/\u00a0/g, " ") : "Sem fatura";
  fact("Fatura do período", billValue, "card-bill-total" + (billValue.length > 14 ? " card-value-long" : ""));
  fact("Vencimento", bill ? bill.due_date.split("-").reverse().join("/") : `Dia ${card.due_day}`);
  fact("Situação", card.archived ? "Arquivado" : bill ? bill.status === "open" ? "Em revisão" : "Conferida" : "Não registrada");
  if (bill?.paid_cents > 0) fact("Restante", money(bill.remaining_cents), "credit-remaining");
  const details = el("button", bill ? "Ver fatura" : "Ver cartão", "text-button card-open");
  details.type = "button";
  details.setAttribute("aria-label", `Ver detalhes de ${card.name}`);
  details.onclick = open;
  info.append(facts, details);
  stage.append(stack, info);
  target.append(stage);
  if (shown.length > 1) shown.forEach((item) => {
    const choice = el("button", item.name, "card-choice");
    choice.type = "button";
    choice.dataset.cardId = item.id;
    choice.setAttribute("aria-pressed", String(item.id === card.id));
    choice.setAttribute("aria-label", `Selecionar cartão ${item.name}`);
    choice.title = item.name;
    choice.onclick = () => {
      overviewSelectedCardId = item.id;
      renderOverviewCards();
      options.querySelector(`[data-card-id="${CSS.escape(String(item.id))}"]`).focus({ preventScroll: true });
    };
    options.append(choice);
  });
}
function renderFinance() {
  renderOverviewCards();
  const accounts = $("#account-list"),
    cards = $("#card-list"),
    statements = $("#statement-list");
  accounts.replaceChildren();
  cards.replaceChildren();
  statements.replaceChildren();
  accounts.hidden = !demo;
  if (demo) {
    accounts.append(el("span", "Contas de demonstração", "subtle"));
    financeAccounts.forEach((a) =>
      accounts.append(el("span", a.name, "badge")),
    );
  }
  financeCards.forEach((c) => {
    const panel = el("article", undefined, "panel");
    panel.append(
      el("span", "CARTÃO DE CRÉDITO", "eyebrow"),
      el("h2", c.name),
      el(
        "p",
        `Vencimento: dia ${c.due_day}. Ajustado para o último dia em meses curtos.`,
      ),
    );
    panel.dataset.entityId = c.id;
    panel.dataset.entityVersion = c.version;
    if (c.archived)
      panel.append(
        el("p", "Cartão arquivado · faturas e pagamentos preservados", "badge"),
      );
    if (csrf && !demo && typeof manageEntity === "function")
      panel.append(button("Gerenciar cartão", () => manageEntity(c, "cards")));
    if (!c.archived)
      panel.append(
        button("Abrir fatura do período", async () => {
          if (demo) localStatement(c, $("#month").value);
          else
            await api(
              `/api/cards/${c.id}/statements?month=${$("#month").value}`,
              "POST",
            );
          await refresh();
        }),
      );
    cards.append(panel);
  });
  if (!financeCards.length)
    empty(cards, "Cadastre seu primeiro cartão usando apenas um apelido.");
  financeStatements
    .filter((s) => s.month === $("#month").value)
    .forEach((raw) => {
      const s = totals(raw),
        panel = el("article", undefined, "panel statement"),
        heading = el("div", undefined, "section-heading"),
        label = el("div");
      panel.id = "statement-" + s.id;
      label.append(
        el(
          "h2",
          financeCards.find((c) => c.id === s.card_id)?.name || "Cartão",
        ),
        el(
          "p",
          `Vence em ${s.due_date.split("-").reverse().join("/")} · ${s.status === "open" ? "Em revisão" : "Conferida"} · ${s.pending} ${s.pending === 1 ? "categoria pendente" : "categorias pendentes"}`,
        ),
      );
      heading.append(label, el("strong", money(s.total_cents)));
      panel.append(heading);
      const actions = el("div", undefined, "actions");
      if (s.status === "open") {
        const archived = financeCards.find((c) => c.id === s.card_id)?.archived;
        if (!archived)
          actions.append(
            button("Importar CSV / OFX", () => openImport(s.id)),
            button("Ler PDF", () => openPdf(s.id)),
          );
        actions.append(
          button(
            "Conferir total",
            () => {
              const f = $("#reconcile-form");
              f.reset();
              f.elements.id.value = s.id;
              f.elements.revision.value = s.revision || "";
              openDialog("#reconcile-dialog");
            },
            "button",
          ),
        );
      } else {
        actions.append(
          button("Reabrir fatura", async () => {
            if (demo) {
              if (raw.payments.length)
                throw Error(
                  "Estorne os registros de pagamento antes de reabrir.",
                );
              raw.status = "open";
              raw.expected_cents = null;
            } else
              await api(
                `/api/statements/${s.id}/reopen?expected_revision=${s.revision}`,
                "POST",
              );
            await refresh();
          }),
        );
        if (s.remaining_cents > 0)
          actions.append(
            button(
              "Registrar pagamento",
              () => {
                if (!financeAccounts.some((a) => !a.archived))
                  throw Error(
                    "Cadastre ou reative uma conta de origem primeiro.",
                  );
                const f = $("#payment-form");
                f.reset();
                f.elements.id.value = s.id;
                f.elements.request_id.value = crypto.randomUUID();
                populateAccounts(f.elements.account_id);
                f.elements.date.value = today;
                f.elements.amount.value = (s.remaining_cents / 100)
                  .toFixed(2)
                  .replace(".", ",");
                openDialog("#payment-dialog");
              },
              "button",
            ),
          );
      }
      panel.append(
        actions,
        el(
          "p",
          `${s.remaining_cents < 0 ? "Crédito na fatura" : s.status !== "open" && s.remaining_cents === 0 ? "Fatura paga" : s.paid_cents > 0 ? "Pagamento parcial" : "Sem pagamento registrado"} · Pago: ${money(s.paid_cents)} · Restante: ${money(s.remaining_cents)}`,
        ),
      );
      s.charges.forEach((c) => {
        const row = transactionNode(
          {
            ...c,
            kind: c.kind,
            description: `${c.description}${c.kind === "refund" ? " · Estorno" : ""} · ${c.installment}/${c.installments}`,
          },
          false,
        );
        if (s.status === "open") {
          const tools = el("div", undefined, "row-actions");
          if (!demo && csrf)
            tools.append(
              button(
                c.imported ? "Corrigir importado" : "Corrigir compra",
                () => openCorrection(c.operation_id),
              ),
            );
          tools.append(
            button("Revisar categoria", () => {
              const f = $("#review-charge-form");
              f.elements.id.value = c.id;
              f.elements.version.value = c.version || 1;
              f.elements.category.value = c.category;
              openDialog("#review-charge-dialog");
            }),
            button("Excluir compra", async () => {
              const current = !demo
                ? await api("/api/card-operations/" + c.operation_id)
                : null;
              if (
                !await confirmAction(
                  current
                    ? `Excluir “${current.description}” e suas ${current.installments} parcela(s), total ${money(current.amount_cents)}? Todas as faturas afetadas precisam estar abertas.`
                    : "Excluir esta compra e todas as suas parcelas?",
                )
              )
                return;
              if (demo) {
                const affected = financeStatements.filter((st) =>
                  st.charges.some((ch) => ch.operation_id === c.operation_id),
                );
                if (affected.some((st) => st.status !== "open"))
                  throw Error(
                    "Há parcelas em fatura conferida. Reabra antes de excluir.",
                  );
                affected.forEach(
                  (st) =>
                    (st.charges = st.charges.filter(
                      (ch) => ch.operation_id !== c.operation_id,
                    )),
                );
              } else
                await api(
                  `/api/card-operations/${c.operation_id}?expected_revision=${current.revision}`,
                  "DELETE",
                );
              await refresh();
            }),
          );
          const menu = el("details", undefined, "row-menu"),
            summary = el("summary", "Ações");
          summary.setAttribute("aria-label", `Ações de ${c.description}`);
          menu.append(summary, tools);
          row.append(menu);
        }
        panel.append(row);
      });
      if (!s.charges.length)
        empty(
          panel,
          "Nenhum lançamento nesta fatura. Registre uma compra ou importe o CSV.",
        );
      s.payments.forEach((p) => {
        const row = el("div", undefined, "payment-row");
        row.append(
          el(
            "span",
            `Pagamento de ${money(p.amount_cents)} em ${p.date.split("-").reverse().join("/")} · ${financeAccounts.find((a) => a.id === p.account_id)?.name || "Conta"}`,
          ),
          button(
            "Estornar registro",
            async () => {
              if (
                !await confirmAction(
                  "Remover apenas este registro de pagamento? Isso não desfaz uma operação bancária.",
                )
              )
                return;
              if (demo)
                raw.payments = raw.payments.filter((x) => x.id !== p.id);
              else
                await api(
                  `/api/statement-payments/${p.id}?expected_version=${p.version}`,
                  "DELETE",
                );
              await refresh();
            },
            "text-button",
          ),
        );
        if (!demo && csrf)
          row.append(
            button(
              "Corrigir pagamento",
              () => openPaymentCorrection(p.id),
              "text-button",
            ),
          );
        panel.append(row);
      });
      statements.append(panel);
    });
  if (!statements.childElementCount)
    empty(
      statements,
      "Nenhuma fatura neste mês. Abra uma fatura no cartão ou registre uma compra.",
    );
}
function openSetup(type) {
  if (!allowed()) return;
  const f = $("#setup-form");
  f.reset();
  f.elements.type.value = type;
  $("#setup-title").textContent =
    type === "account" ? "Cadastrar conta" : "Cadastrar cartão";
  $("#due-day-label").hidden = type === "account";
  f.elements.due_day.disabled = type === "account";
  openDialog("#setup-dialog");
}
$("#new-account").onclick = () => openSetup("account");
$("#new-card").onclick = () => openSetup("card");
$("#setup-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      type = f.elements.type.value,
      body = { name: f.elements.name.value.trim() };
    if (!body.name) throw Error("Informe um apelido.");
    if (type === "card") body.due_day = Number(f.elements.due_day.value);
    if (demo)
      (type === "card" ? financeCards : financeAccounts).push({
        id: crypto.randomUUID(),
        ...body,
      });
    else
      await api(type === "card" ? "/api/cards" : "/api/accounts", "POST", body);
    $("#setup-dialog").close();
    await refreshAfterSave();
    message("Cadastro salvo.");
  });
};
for (const select of [
  $("#purchase-form").elements.category,
  $("#review-charge-form").elements.category,
])
  categories
    .filter((c) => c !== "Renda")
    .forEach((c) => select.append(el("option", c)));
$("#new-purchase").onclick = () => {
  if (!allowed()) return;
  if (!financeCards.some((c) => !c.archived)) {
    message("Cadastre ou reative um cartão primeiro.");
    return;
  }
  const f = $("#purchase-form");
  f.reset();
  f.elements.request_id.value = crypto.randomUUID();
  f.elements.date.value = today;
  f.elements.first_month.value = $("#month").value;
  populate(
    f.elements.card_id,
    financeCards.filter((c) => !c.archived),
  );
  openDialog("#purchase-dialog");
};
$("#purchase-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      body = {
        request_id: f.elements.request_id.value,
        card_id: f.elements.card_id.value,
        first_month: f.elements.first_month.value,
        date: f.elements.date.value,
        description: f.elements.description.value.trim(),
        amount_cents: cents(f.elements.amount.value),
        installments: Number(f.elements.installments.value),
        kind: f.elements.kind.value,
        category: f.elements.category.value,
        reviewed: f.elements.reviewed.checked,
      };
    if (
      !body.description ||
      body.amount_cents < body.installments ||
      body.installments < 1 ||
      body.installments > 36
    )
      throw Error("Confira descrição, valor e quantidade de parcelas.");
    if (body.kind === "refund" && body.installments !== 1)
      throw Error("Estornos devem entrar em uma única fatura.");
    if (demo) {
      if (
        !financeStatements.some((s) =>
          s.charges.some((c) => c.operation_id === body.request_id),
        )
      ) {
        const card = financeCards.find((c) => c.id === body.card_id),
          [year, month] = body.first_month.split("-").map(Number),
          plan = [];
        for (let i = 0; i < body.installments; i++) {
          const d = new Date(year, month - 1 + i, 1),
            period =
              d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0"),
            existing = financeStatements.find(
              (s) => s.card_id === card.id && s.month === period,
            );
          if (existing && existing.status !== "open")
            throw Error("Uma das parcelas está em fatura conferida.");
          plan.push(period);
        }
        plan.forEach((period, i) => {
          localStatement(card, period).charges.push({
            ...body,
            id: crypto.randomUUID(),
            operation_id: body.request_id,
            installment: i + 1,
            amount_cents:
              Math.floor(body.amount_cents / body.installments) +
              (i < body.amount_cents % body.installments ? 1 : 0),
          });
        });
      }
    } else await api("/api/card-purchases", "POST", body);
    $("#purchase-dialog").close();
    await refreshAfterSave();
    message(
      "Compra ou estorno registrado. Confira as faturas nos meses de vencimento.",
    );
  });
};
$("#reload-charge-review").onclick = () =>
  action(async () => {
    const f = $("#review-charge-form"),
      id = f.elements.id.value,
      expectedCsrf = csrf;
    await refresh();
    if (!csrf || csrf !== expectedCsrf) return;
    const row = financeStatements
      .flatMap((s) => s.charges)
      .find((c) => c.id === id);
    if (!row)
      throw Error(
        "Lançamento não encontrado neste período. Atualize as faturas.",
      );
    f.elements.version.value = row.version;
    f.elements.category.value = row.category;
    $("#review-charge-dialog").querySelector(".dialog-error")?.remove();
  });
$("#review-charge-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      body = {
        category: f.elements.category.value,
        reviewed: true,
        expected_version: Number(f.elements.version.value),
      };
    if (demo) {
      const s = financeStatements.find((s) =>
        s.charges.some((c) => c.id === f.elements.id.value),
      );
      if (s.status !== "open") throw Error("Reabra a fatura antes de revisar.");
      Object.assign(
        s.charges.find((c) => c.id === f.elements.id.value),
        body,
      );
    } else
      await api(`/api/card-charges/${f.elements.id.value}/review`, "PUT", body);
    $("#review-charge-dialog").close();
    await refreshAfterSave();
  });
};
$("#reload-reconcile").onclick = () =>
  action(async () => {
    const f = $("#reconcile-form"),
      id = f.elements.id.value,
      expectedCsrf = csrf;
    const current = demo
      ? totals(financeStatements.find((s) => s.id === id))
      : await api("/api/statements/" + id);
    if (
      csrf !== expectedCsrf ||
      f.elements.id.value !== id ||
      !$("#reconcile-dialog").open
    )
      return;
    f.elements.revision.value = current.revision || "";
    f.elements.amount.value = "";
    $("#reconcile-dialog").querySelector(".dialog-error")?.remove();
    message("Fatura recarregada. Confira novamente o total do emissor.");
  });
$("#reconcile-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      expected = cents(f.elements.amount.value);
    if (demo) {
      const s = financeStatements.find((s) => s.id === f.elements.id.value),
        t = totals(s);
      if (t.pending)
        throw Error("Revise todas as categorias antes de conferir.");
      if (t.total_cents !== expected)
        throw Error("Total informado diverge dos lançamentos.");
      s.status = "closed";
      s.expected_cents = expected;
    } else
      await api(`/api/statements/${f.elements.id.value}/close`, "POST", {
        expected_cents: expected,
        expected_revision: f.elements.revision.value,
      });
    $("#reconcile-dialog").close();
    await refreshAfterSave();
    message(
      "Fatura conferida. Agora você pode registrar os pagamentos realizados.",
    );
  });
};
$("#payment-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      body = {
        request_id: f.elements.request_id.value,
        account_id: f.elements.account_id.value,
        date: f.elements.date.value,
        amount_cents: cents(f.elements.amount.value),
      };
    if (body.amount_cents <= 0) throw Error("Informe um valor positivo.");
    if (demo) {
      const s = financeStatements.find((s) => s.id === f.elements.id.value);
      if (
        s.status !== "closed" ||
        body.amount_cents > totals(s).remaining_cents
      )
        throw Error("Confira o estado e o valor restante da fatura.");
      if (!s.payments.some((p) => p.request_id === body.request_id))
        s.payments.push({ id: crypto.randomUUID(), ...body });
    } else
      await api(
        `/api/statements/${f.elements.id.value}/payments`,
        "POST",
        body,
      );
    $("#payment-dialog").close();
    await refreshAfterSave();
    message("Pagamento registrado, sem duplicar a despesa.");
  });
};
renderFinance();
