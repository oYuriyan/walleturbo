"use strict";
let planningGeneration = 0;
const budgetCategory = $("#budget-form").elements.category;
categories
  .filter((c) => c !== "Renda")
  .forEach((c) => budgetCategory.append(el("option", c)));
function clearPlanning() {
  planningGeneration++;
  $("#plan-form").reset();
  $("#budget-form").reset();
  for (const id of [
    "budget-list",
    "goal-plan-list",
    "recurrence-list",
    "planning-warnings",
  ])
    $("#" + id).replaceChildren();
  for (const id of ["capacity", "planning-disclaimer", "planning-notice"])
    $("#" + id).textContent = "";
  for (const form of [$("#plan-form"), $("#budget-form")])
    form
      .querySelectorAll("input,select,button")
      .forEach((n) => (n.disabled = true));
}
async function loadPlanning() {
  const generation = ++planningGeneration;
  const enabled = !!csrf && !demo;
  for (const form of [$("#plan-form"), $("#budget-form")])
    form
      .querySelectorAll("input,select,button")
      .forEach((n) => (n.disabled = !enabled));
  for (const id of [
    "budget-list",
    "goal-plan-list",
    "recurrence-list",
    "planning-warnings",
  ])
    $("#" + id).replaceChildren();
  $("#capacity").textContent = "";
  $("#planning-disclaimer").textContent = "";
  if (!enabled) {
    clearPlanning();
    $("#planning-notice").textContent =
      "Conecte sua conta para configurar e analisar seu planejamento. A demonstração mantém somente os fluxos de lançamentos, cartões e metas.";
    return;
  }
  $("#planning-notice").textContent = "Calculando com os registros do mês…";
  const data = await api("/api/planning/" + $("#month").value);
  if (generation !== planningGeneration) return;
  $("#planning-notice").textContent =
    `Resultado registrado: ${money(data.figures.result_cents)} · Variação de caixa: ${money(data.figures.cash_change_cents)}`;
  const form = $("#plan-form");
  form.elements.income.value =
    data.plan.income_reference_cents === null
      ? ""
      : (data.plan.income_reference_cents / 100).toFixed(2).replace(".", ",");
  form.elements.buffer.value = (data.plan.buffer_cents / 100)
    .toFixed(2)
    .replace(".", ",");
  form.elements.complete.checked = data.plan.records_complete;
  data.warnings.forEach((w) => $("#planning-warnings").append(el("p", w)));
  $("#capacity").textContent =
    data.capacity_cents === null
      ? "Sugestão de aporte indisponível até conferir os dados"
      : `Margem para a simulação de aportes: ${money(data.capacity_cents)}`;
  data.budgets.forEach((b) => {
    const row = el("div", undefined, "planning-row"),
      info = el("div");
    info.append(
      el("strong", b.category),
      el(
        "p",
        `Gasto líquido ${money(b.spent_cents)} de ${money(b.amount_cents)} · ${b.exceeded_cents > 0 ? "Excedido em " + money(b.exceeded_cents) : "Disponível " + money(b.remaining_cents)}`,
      ),
    );
    row.append(
      info,
      button(
        "Remover limite",
        async () => {
          if (
            !confirm(
              "Remover este limite mensal? Os lançamentos serão preservados.",
            )
          )
            return;
          await api(
            `/api/planning/${data.month}/budget/${encodeURIComponent(b.category)}`,
            "DELETE",
          );
          await loadPlanning();
        },
        "text-button",
      ),
    );
    $("#budget-list").append(row);
  });
  if (!data.budgets.length)
    empty($("#budget-list"), "Defina um limite para acompanhar uma categoria");
  data.goals.forEach((g) => {
    const row = el("div", undefined, "planning-row"),
      info = el("div");
    info.append(
      el("strong", g.name),
      el(
        "p",
        g.remaining_cents === 0
          ? "Meta alcançada"
          : g.expired
            ? "Prazo vencido: revise a data da meta"
            : `Necessário por mês: ${money(g.required_monthly_cents)} · Sugestão neste cenário: ${g.suggested_cents === null ? "indisponível" : money(g.suggested_cents)}`,
      ),
    );
    if (g.gap_cents > 0 && !g.expired)
      info.append(
        el(
          "p",
          `Faltam ${money(g.gap_cents)} em relação ao aporte necessário; revise prazo, objetivo ou gastos`,
        ),
      );
    row.append(info);
    $("#goal-plan-list").append(row);
  });
  if (!data.goals.length)
    empty($("#goal-plan-list"), "Cadastre uma meta para simular os aportes");
  data.recurrences.forEach((r) => {
    const details = el("details", undefined, "recurrence"),
      summary = el(
        "summary",
        `${r.merchant} · ${money(r.current_cents)} neste mês`,
      );
    details.append(summary, el("p", r.reason));
    r.evidence.forEach((e) =>
      details.append(
        el(
          "p",
          `${e.month} · ${money(e.amount_cents)} · ${e.source === "transaction" ? "Lançamento direto" : "Cartão"} · ${e.description}`,
        ),
      ),
    );
    $("#recurrence-list").append(details);
  });
  if (!data.recurrences.length)
    empty(
      $("#recurrence-list"),
      "Nenhuma recorrência elegível encontrada na janela de seis meses",
    );
  $("#planning-disclaimer").textContent =
    data.disclaimer +
    " Aportes são distribuídos pela data de prazo, usando as metas atuais. Método: " +
    data.method;
}
document
  .querySelector("[data-view=planning]")
  .addEventListener("click", () => action(loadPlanning));
$("#plan-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target;
    await api(`/api/planning/${$("#month").value}/plan`, "PUT", {
      income_reference_cents: f.elements.income.value
        ? cents(f.elements.income.value)
        : null,
      buffer_cents: cents(f.elements.buffer.value),
      records_complete: f.elements.complete.checked,
    });
    await loadPlanning();
    message("Cenário salvo. A simulação não movimenta nem reserva dinheiro.");
  });
};
$("#budget-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target;
    await api(`/api/planning/${$("#month").value}/budget`, "PUT", {
      category: f.elements.category.value,
      amount_cents: cents(f.elements.amount.value),
    });
    await loadPlanning();
    message("Limite mensal salvo.");
  });
};
