"use strict";
let historyGeneration = 0,
  historyCursor = null;
function clearHistory() {
  historyGeneration++;
  historyCursor = null;
  $("#history-list").replaceChildren();
  $("#history-notice").textContent = "";
  $("#more-history").hidden = true;
}
const historyEntities = {
  import_relocation: "Competência da importação",
  import_link: "Vínculo de importação",
  month_plan: "Cenário mensal",
  budget: "Limite mensal",
  account: "Conta",
  card: "Cartão",
  goal: "Meta",
  transaction: "Lançamento",
  card_charge: "Compra ou estorno",
  statement: "Fatura",
  statement_payment: "Pagamento de fatura",
  opening_balance: "Referência de saldo",
  transfer: "Transferência",
};
const historyFields = {
  buffer_cents: "Margem de segurança",
  income_reference_cents: "Renda de referência",
  records_complete: "Registros confirmados",
  version: "Versão",
  origin_version: "Versão da origem",
  name: "Nome",
  account_id: "Conta",
  source_account_id: "Conta de origem",
  destination_account_id: "Conta de destino",
  description: "Descrição",
  amount_cents: "Valor",
  target_cents: "Objetivo",
  saved_cents: "Reserva informada",
  date: "Data",
  deadline: "Prazo",
  category: "Categoria",
  kind: "Tipo",
  reviewed: "Revisado",
  status: "Situação",
  archived: "Arquivado",
  expected_cents: "Total conferido",
  due_date: "Vencimento",
  reversed_date: "Reversão",
  month: "Mês da fatura",
  installment: "Parcela",
  installments: "Total de parcelas",
  reason: "Motivo",
  correction_reason: "Motivo da correção",
};
function historyValue(key, value) {
  if (key.endsWith("account_id") && value)
    return (
      financeAccounts.find((a) => a.id === value)?.name ||
      "Conta sem cadastro atual (vínculo na exportação)"
    );
  if (value === null || value === undefined) return "Não informado";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (key.endsWith("_cents")) return money(value);
  return (
    {
      expense: "Despesa",
      income: "Receita",
      refund: "Estorno",
      open: "Aberta",
      closed: "Conferida",
    }[value] || String(value)
  );
}
async function loadHistory(reset) {
  if (!csrf || demo) {
    clearHistory();
    message("Entre na conta para consultar o histórico financeiro.");
    return;
  }
  const generation = reset ? ++historyGeneration : historyGeneration;
  $("#history-notice").textContent = "Consultando alterações…";
  const cursor = reset ? null : historyCursor;
  const data = await api(
    "/api/history?limit=30" +
      (cursor ? "&before_id=" + encodeURIComponent(cursor) : ""),
  );
  if (generation !== historyGeneration || !csrf || demo) return;
  const target = $("#history-list");
  if (reset) target.replaceChildren();
  for (const item of data.items) {
    const details = el("details", undefined, "history-item"),
      summary = el("summary");
    const state = item.after || item.before || {};
    summary.textContent = `${historyEntities[item.entity] || "Registro"} · ${{ created: "Criado", updated: "Alterado", deleted: "Excluído" }[item.action]} · ${new Date(item.occurred_at).toLocaleString("pt-BR")} · ${state.name || state.description || state.month || "Registro financeiro"}`;
    details.append(summary);
    const fields = el("dl");
    for (const [key, label] of Object.entries(historyFields)) {
      const before = item.before?.[key],
        after = item.after?.[key];
      if (before === undefined && after === undefined) continue;
      if (item.action === "updated" && before === after) continue;
      fields.append(
        el("dt", label),
        el(
          "dd",
          item.action === "updated"
            ? `${historyValue(key, before)} → ${historyValue(key, after)}`
            : historyValue(key, (item.after || item.before)[key]),
        ),
      );
    }
    // Vínculos também permanecem no JSON exportado, mesmo se o cadastro for excluído.
    details.append(fields);
    target.append(details);
  }
  if (reset && !data.items.length)
    empty(target, "Nenhuma alteração registrada a partir da versão 0.8.");
  historyCursor = data.next_cursor;
  $("#more-history").hidden = !historyCursor;
  $("#history-notice").textContent =
    "Consulta atualizada. Abra um registro para ver os valores.";
}
$("#refresh-history").onclick = () => action(() => loadHistory(true));
$("#more-history").onclick = () =>
  action(async () => {
    const b = $("#more-history");
    if (b.disabled || !historyCursor) return;
    b.disabled = true;
    try {
      await loadHistory(false);
    } finally {
      b.disabled = false;
    }
  });
