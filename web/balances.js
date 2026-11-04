"use strict";
let balanceGeneration = 0,
  transferOffset = 0;
$("#balance-date").value = today;
const balanceForms = ["opening", "transfer", "reverse-transfer"];
function clearBalances() {
  balanceGeneration++;
  transferOffset = 0;
  $("#balance-list").replaceChildren();
  $("#transfer-list").replaceChildren();
  $("#balance-notice").textContent = "";
  $("#new-transfer").disabled = true;
  $("#more-transfers").hidden = true;
  for (const name of balanceForms) {
    const form = $("#" + name + "-form");
    form.reset();
    form.querySelectorAll("select").forEach((n) => n.replaceChildren());
    form
      .querySelectorAll("input,select,button")
      .forEach((n) => (n.disabled = true));
    const dialog = $("#" + name + "-dialog");
    dialog.querySelector(".dialog-error")?.remove();
    if (dialog.open) dialog.close();
  }
  $("#opening-title").textContent = "Referência de saldo";
}
function balanceDialog(name) {
  if (!csrf || demo)
    throw Error("Conecte sua conta para registrar saldos e transferências.");
  const form = $("#" + name + "-form");
  form.reset();
  form
    .querySelectorAll("input,select,button")
    .forEach((n) => (n.disabled = false));
  openDialog("#" + name + "-dialog");
  return form;
}
async function loadBalances() {
  const generation = ++balanceGeneration;
  const target = $("#balance-list");
  target.replaceChildren();
  $("#transfer-list").replaceChildren();
  $("#more-transfers").hidden = true;
  $("#new-transfer").disabled = true;
  if (!csrf || demo) {
    clearBalances();
    $("#balance-notice").textContent =
      "Conecte sua conta para consultar saldos e registrar transferências. Esses recursos não usam dados da demonstração.";
    return;
  }
  $("#balance-notice").textContent = "Calculando saldos…";
  const day = $("#balance-date").value;
  if (!day) throw Error("Informe uma data de consulta.");
  const data = await api("/api/balances?as_of=" + encodeURIComponent(day));
  if (generation !== balanceGeneration || !csrf || demo) return;
  $("#balance-notice").textContent =
    (data.total_cents === null
      ? `Subtotal conhecido: ${money(data.known_subtotal_cents)}. ${data.unknown_accounts} conta(s) sem referência aplicável e ${data.unassigned_transactions} lançamento(s) sem conta. Total completo indisponível.`
      : `Saldo calculado das contas: ${money(data.total_cents)}.`) +
    " Calculado pelos registros até a data, sem consulta bancária.";
  $("#new-transfer").disabled = data.accounts.length < 2;
  if (!data.accounts.length)
    empty(target, "Cadastre uma conta para definir sua referência de saldo.");
  data.accounts.forEach((a) => {
    const panel = el("article", undefined, "panel account-balance");
    panel.dataset.accountId = a.id;
    panel.append(
      el("h3", a.name),
      el(
        "strong",
        a.balance_cents === null
          ? "Saldo desconhecido"
          : money(a.balance_cents),
        "account-balance-value",
      ),
    );
    panel.append(
      el(
        "p",
        a.opening_date
          ? `Referência: ${money(a.opening_cents)} no início de ${a.opening_date.split("-").reverse().join("/")} · revisão ${a.version}.`
          : "Informe o saldo inicial para começar o cálculo.",
      ),
    );
    if (a.status === "before_reference")
      panel.append(
        el(
          "p",
          "A consulta antecede sua referência. Não há saldo retroativo estimado.",
        ),
      );
    if (a.excluded_movements)
      panel.append(
        el(
          "p",
          `${a.excluded_movements} movimento(s) anteriores à referência, mantidos somente no histórico.`,
        ),
      );
    panel.append(
      button(
        a.version ? "Corrigir referência" : "Definir saldo inicial",
        () => {
          const f = balanceDialog("opening");
          $("#opening-title").textContent = "Referência de saldo · " + a.name;
          f.elements.account_id.value = a.id;
          f.elements.request_id.value = crypto.randomUUID();
          f.elements.expected_version.value = a.version;
          f.elements.date.value = a.opening_date || day;
          f.elements.amount.value =
            a.opening_cents === null
              ? ""
              : (a.opening_cents / 100).toFixed(2).replace(".", ",");
        },
      ),
    );
    target.append(panel);
  });
  transferOffset = 0;
  await loadTransfers(generation, true);
}
async function loadTransfers(generation, reset = false) {
  const page = await api(`/api/transfers?offset=${transferOffset}&limit=30`);
  if (generation !== balanceGeneration || !csrf || demo) return;
  const target = $("#transfer-list");
  if (reset) target.replaceChildren();
  if (reset && !page.items.length)
    empty(target, "Nenhuma transferência registrada.");
  const names = (id) =>
    financeAccounts.find((a) => a.id === id)?.name || "Conta";
  page.items.forEach((t) => {
    const row = el("div", undefined, "planning-row");
    row.append(
      el(
        "p",
        `${t.description} · ${names(t.source_account_id)} → ${names(t.destination_account_id)} · ${money(t.amount_cents)} · ${t.date.split("-").reverse().join("/")}`,
      ),
    );
    if (t.reversed_date)
      row.append(
        el(
          "span",
          "Revertida em " + t.reversed_date.split("-").reverse().join("/"),
          "badge",
        ),
      );
    else
      row.append(
        button("Reverter transferência", () => {
          const f = balanceDialog("reverse-transfer");
          f.elements.id.value = t.id;
          f.elements.date.min = t.date;
          f.elements.date.value = today < t.date ? t.date : today;
        }),
      );
    target.append(row);
  });
  transferOffset += page.items.length;
  $("#more-transfers").hidden = !page.has_more;
}
$("#balance-date").onchange = () => action(loadBalances);
$("#more-transfers").onclick = () =>
  action(async () => {
    const button = $("#more-transfers");
    button.disabled = true;
    try {
      await loadTransfers(balanceGeneration);
    } finally {
      button.disabled = false;
    }
  });
$("#new-transfer").onclick = () =>
  action(() => {
    const f = balanceDialog("transfer");
    f.elements.request_id.value = crypto.randomUUID();
    populateAccounts(f.elements.source_account_id);
    populateAccounts(f.elements.destination_account_id);
    f.elements.destination_account_id.selectedIndex = 1;
    f.elements.date.value = today;
  });
async function submitBalanceForm(form, work) {
  const submit = form.querySelector('button[type="submit"]');
  if (submit.disabled) return;
  submit.disabled = true;
  try {
    await work();
  } finally {
    submit.disabled = !csrf || demo;
  }
}
$("#opening-form").onsubmit = (e) => {
  e.preventDefault();
  action(() =>
    submitBalanceForm(e.target, async () => {
      const f = e.target,
        raw = f.elements.amount.value.trim();
      const amount = raw.startsWith("-") ? -cents(raw.slice(1)) : cents(raw);
      await api(`/api/accounts/${f.elements.account_id.value}/opening`, "PUT", {
        request_id: f.elements.request_id.value,
        expected_version: Number(f.elements.expected_version.value),
        date: f.elements.date.value,
        amount_cents: amount,
        reason: f.elements.reason.value.trim(),
      });
      $("#opening-dialog").close();
      await loadBalances();
      message(
        "Referência salva. Correções anteriores permanecem na exportação.",
      );
    }),
  );
};
$("#transfer-form").onsubmit = (e) => {
  e.preventDefault();
  action(() =>
    submitBalanceForm(e.target, async () => {
      const f = e.target;
      if (
        f.elements.source_account_id.value ===
        f.elements.destination_account_id.value
      )
        throw Error("Escolha contas diferentes.");
      const amount = cents(f.elements.amount.value);
      if (amount <= 0) throw Error("Informe um valor positivo.");
      await api("/api/transfers", "POST", {
        request_id: f.elements.request_id.value,
        source_account_id: f.elements.source_account_id.value,
        destination_account_id: f.elements.destination_account_id.value,
        date: f.elements.date.value,
        amount_cents: amount,
        description: f.elements.description.value.trim(),
      });
      $("#transfer-dialog").close();
      await loadBalances();
      message("Transferência registrada, sem duplicar receitas ou despesas.");
    }),
  );
};
$("#reverse-transfer-form").onsubmit = (e) => {
  e.preventDefault();
  action(() =>
    submitBalanceForm(e.target, async () => {
      const f = e.target;
      await api(`/api/transfers/${f.elements.id.value}/reverse`, "POST", {
        date: f.elements.date.value,
      });
      $("#reverse-transfer-dialog").close();
      await loadBalances();
      message("Reversão registrada na data informada.");
    }),
  );
};

document
  .querySelectorAll('[data-view="finance"]')
  .forEach((b) => b.addEventListener("click", () => action(loadBalances)));
action(loadBalances);
