"use strict";
let correctionGeneration = 0,
  correctionBody = null;
function clearCorrection() {
  correctionGeneration++;
  correctionBody = null;
  const f = $("#correction-form");
  f.reset();
  f.querySelectorAll('input[type="hidden"]').forEach((n) => (n.value = ""));
  f.querySelectorAll("input,select,button").forEach((n) => (n.disabled = true));
  $("#correction-effects").replaceChildren();
  $("#correction-card").textContent = "";
  if ($("#correction-dialog").open) $("#correction-dialog").close();
}
async function openCorrection(id) {
  const generation = ++correctionGeneration,
    expectedCsrf = csrf;
  if (!csrf || demo) throw Error("Entre na conta para corrigir uma compra.");
  invalidateCorrection();
  const data = await api("/api/card-operations/" + id);
  if (generation !== correctionGeneration || csrf !== expectedCsrf) return;
  if (!data.editable)
    throw Error("Operação importada inconsistente; revise seus vínculos.");
  const f = $("#correction-form");
  f.reset();
  f.querySelectorAll("input,select,button").forEach(
    (n) => (n.disabled = false),
  );
  f.elements.operation_id.value = id;
  f.elements.card_id.value = data.card_id;
  f.elements.request_id.value = crypto.randomUUID();
  f.elements.revision.value = data.revision;
  for (const key of [
    "description",
    "date",
    "first_month",
    "installments",
    "kind",
  ])
    f.elements[key].value = data[key];
  f.elements.amount.value = (data.amount_cents / 100)
    .toFixed(2)
    .replace(".", ",");
  f.elements.reviewed.checked = data.reviewed;
  f.elements.installments.readOnly = data.origin === "imported";
  f.elements.first_month.readOnly = data.origin === "imported";
  $("#correction-title").textContent =
    data.origin === "imported"
      ? "Corrigir lançamento importado"
      : "Corrigir compra completa";
  $("#correction-policy").textContent =
    data.origin === "imported"
      ? "A fatura original e uma única parcela serão mantidas. A origem permanece reservada para evitar reimportações."
      : "Todas as parcelas serão recalculadas. O cartão original será mantido. Faturas afetadas precisam estar abertas; confira a prévia antes de confirmar.";
  f.elements.category.replaceChildren();
  for (const option of $("#category-options").options)
    if (option.value !== "Renda")
      f.elements.category.append(option.cloneNode(true));
  f.elements.category.value = data.category;
  $("#correction-card").textContent =
    financeCards.find((c) => c.id === data.card_id)?.name || "Cartão original";
  invalidateCorrection();
  openDialog("#correction-dialog");
}
function invalidateCorrection() {
  correctionBody = null;
  $("#confirm-correction").disabled = true;
  $("#correction-effects").replaceChildren();
}
$("#correction-form").oninput = invalidateCorrection;
$("#correction-form").onchange = invalidateCorrection;
$("#reload-correction").onclick = () =>
  action(() =>
    openCorrection($("#correction-form").elements.operation_id.value),
  );
$("#correction-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      generation = correctionGeneration;
    const body = {
      request_id: f.elements.request_id.value,
      card_id: f.elements.card_id.value,
      expected_revision: f.elements.revision.value,
      description: f.elements.description.value.trim(),
      date: f.elements.date.value,
      first_month: f.elements.first_month.value,
      amount_cents: cents(f.elements.amount.value),
      installments: Number(f.elements.installments.value),
      kind: f.elements.kind.value,
      category: f.elements.category.value,
      reviewed: f.elements.reviewed.checked,
      reason: f.elements.reason.value.trim(),
    };
    const signature = JSON.stringify(body);
    invalidateCorrection();
    const data = await api(
      `/api/card-operations/${f.elements.operation_id.value}/preview`,
      "POST",
      body,
    );
    if (generation !== correctionGeneration || !csrf) return;
    // Qualquer edição durante a consulta invalida a prévia recebida.
    const current = {
      ...body,
      description: f.elements.description.value.trim(),
      date: f.elements.date.value,
      first_month: f.elements.first_month.value,
      amount_cents: cents(f.elements.amount.value),
      installments: Number(f.elements.installments.value),
      kind: f.elements.kind.value,
      category: f.elements.category.value,
      reviewed: f.elements.reviewed.checked,
      reason: f.elements.reason.value.trim(),
    };
    if (JSON.stringify(current) !== signature) return;
    correctionBody = body;
    const target = $("#correction-effects");
    target.append(el("h3", "Totais das faturas após a correção"));
    for (const effect of data.effects)
      target.append(
        el(
          "p",
          `${effect.month}: ${money(effect.before_cents)} → ${money(effect.after_cents)}`,
        ),
      );
    $("#confirm-correction").disabled = false;
  });
};
$("#confirm-correction").onclick = () =>
  action(async () => {
    if (!correctionBody) return;
    const generation = correctionGeneration,
      f = $("#correction-form"),
      body = correctionBody;
    correctionBody = null;
    $("#confirm-correction").disabled = true;
    await api(
      `/api/card-operations/${f.elements.operation_id.value}`,
      "PUT",
      body,
    );
    if (generation !== correctionGeneration || !csrf) return;
    $("#correction-dialog").close();
    await refresh();
    message(
      "Compra corrigida. Todas as parcelas e o histórico foram atualizados.",
    );
  });
