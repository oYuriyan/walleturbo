"use strict";
let financeAccounts = [],
  financeCards = [],
  financeStatements = [];
function clearFinance() {
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
  const expectedCsrf = csrf;
  const data = await Promise.all([
    api("/api/accounts"),
    api("/api/cards"),
    api("/api/statements?month=" + $("#month").value),
  ]);
  if (csrf !== expectedCsrf || demo) return;
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
  b.onclick = () => action(fn);
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
function renderFinance() {
  const accounts = $("#account-list"),
    cards = $("#card-list"),
    statements = $("#statement-list");
  accounts.replaceChildren();
  cards.replaceChildren();
  statements.replaceChildren();
  accounts.append(el("span", "Contas cadastradas", "subtle"));
  financeAccounts.forEach((a) => {
    const row = el("div", undefined, "account-management");
    row.dataset.entityId = a.id;
    row.append(
      el("span", a.name + (a.archived ? " · Arquivada" : ""), "badge"),
    );
    if (csrf && !demo && typeof manageEntity === "function")
      row.append(button("Gerenciar conta", () => manageEntity(a, "accounts")));
    accounts.append(row);
  });
  if (!financeAccounts.length)
    accounts.append(
      el(
        "span",
        "Cadastre uma conta para vincular lançamentos e pagamentos.",
        "subtle",
      ),
    );
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
      label.append(
        el(
          "h2",
          financeCards.find((c) => c.id === s.card_id)?.name || "Cartão",
        ),
        el(
          "p",
          `Vence em ${s.due_date.split("-").reverse().join("/")} · ${s.status === "open" ? "Em revisão" : s.remaining_cents === 0 ? "Paga" : "Conferida"} · ${s.pending} pendência(s)`,
        ),
      );
      heading.append(label, el("strong", money(s.total_cents)));
      panel.append(heading);
      const actions = el("div", undefined, "actions");
      if (s.status === "open") {
        const archived = financeCards.find((c) => c.id === s.card_id)?.archived;
        if (!archived)
          actions.append(
            button("Importar CSV", () => openImport(s.id)),
            button("Ler PDF", () => openPdf(s.id)),
          );
        actions.append(
          button(
            "Conferir total",
            () => {
              const f = $("#reconcile-form");
              f.reset();
              f.elements.id.value = s.id;
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
            } else await api(`/api/statements/${s.id}/reopen`, "POST");
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
          `Pago: ${money(s.paid_cents)} · Restante: ${money(s.remaining_cents)}`,
        ),
      );
      s.charges.forEach((c) => {
        const row = transactionNode(
          {
            ...c,
            kind: c.kind === "refund" ? "income" : "expense",
            description: `${c.description}${c.kind === "refund" ? " · Estorno" : ""} · ${c.installment}/${c.installments}`,
          },
          false,
        );
        if (s.status === "open") {
          const tools = el("div", undefined, "row-actions");
          tools.append(
            button("Revisar categoria", () => {
              const f = $("#review-charge-form");
              f.elements.id.value = c.id;
              f.elements.category.value = c.category;
              openDialog("#review-charge-dialog");
            }),
            button("Excluir compra", async () => {
              if (
                !confirm(
                  "Excluir esta compra e todas as suas parcelas? Todas as faturas afetadas precisam estar abertas.",
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
                await api("/api/card-operations/" + c.operation_id, "DELETE");
              await refresh();
            }),
          );
          row.append(tools);
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
                !confirm(
                  "Remover apenas este registro de pagamento? Isso não desfaz uma operação bancária.",
                )
              )
                return;
              if (demo)
                raw.payments = raw.payments.filter((x) => x.id !== p.id);
              else await api("/api/statement-payments/" + p.id, "DELETE");
              await refresh();
            },
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
    await refresh();
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
    await refresh();
    message(
      "Compra ou estorno registrado. Confira as faturas nos meses de vencimento.",
    );
  });
};
$("#review-charge-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      body = { category: f.elements.category.value, reviewed: true };
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
    await refresh();
  });
};
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
      });
    $("#reconcile-dialog").close();
    await refresh();
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
    await refresh();
    message("Pagamento registrado, sem duplicar a despesa.");
  });
};
renderFinance();
