"use strict";
let paymentCorrectionGeneration = 0,
  paymentInputVersion = 0,
  paymentCorrectionBody = null;
function invalidatePaymentPreview() {
  paymentInputVersion++;
  paymentCorrectionBody = null;
  $("#confirm-payment-correction").disabled = true;
  $("#payment-correction-effects").replaceChildren();
}
function clearPaymentCorrection() {
  paymentCorrectionGeneration++;
  invalidatePaymentPreview();
  const f = $("#payment-correction-form");
  f.reset();
  f.querySelectorAll('input[type="hidden"]').forEach((n) => (n.value = ""));
  f.querySelectorAll("input,select,button").forEach((n) => (n.disabled = true));
  f.elements.account_id.replaceChildren();
  $("#payment-correction-context").textContent = "";
  $("#payment-correction-dialog").querySelector(".dialog-error")?.remove();
  if ($("#payment-correction-dialog").open)
    $("#payment-correction-dialog").close();
}
async function openPaymentCorrection(id) {
  const generation = ++paymentCorrectionGeneration,
    expectedCsrf = csrf;
  if (!csrf || demo)
    throw Error("Entre na conta para corrigir um registro de pagamento.");
  invalidatePaymentPreview();
  const [data] = await Promise.all([
    api("/api/statement-payments/" + id),
    loadFinance(),
  ]);
  if (generation !== paymentCorrectionGeneration || csrf !== expectedCsrf)
    return;
  const f = $("#payment-correction-form"),
    p = data.payment;
  f.reset();
  f.querySelectorAll("input,select,button").forEach(
    (n) => (n.disabled = false),
  );
  f.elements.payment_id.value = p.id;
  f.elements.version.value = p.version;
  f.elements.request_id.value = crypto.randomUUID();
  populateAccounts(f.elements.account_id, false, p.account_id);
  f.elements.account_id.value = p.account_id;
  f.elements.date.value = p.date;
  f.elements.amount.value = (p.amount_cents / 100).toFixed(2).replace(".", ",");
  f.elements.as_of.value = $("#balance-date").value || today;
  $("#payment-correction-context").textContent =
    `Fatura ${data.statement.month} · ${financeCards.find((c) => c.id === data.statement.card_id)?.name || "Cartão"}`;
  invalidatePaymentPreview();
  openDialog("#payment-correction-dialog");
}
$("#payment-correction-form").oninput = invalidatePaymentPreview;
$("#payment-correction-form").onchange = invalidatePaymentPreview;
$("#reload-payment-correction").onclick = () =>
  action(() =>
    openPaymentCorrection(
      $("#payment-correction-form").elements.payment_id.value,
    ),
  );
$("#payment-correction-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      generation = paymentCorrectionGeneration;
    const body = {
      request_id: f.elements.request_id.value,
      expected_version: Number(f.elements.version.value),
      account_id: f.elements.account_id.value,
      date: f.elements.date.value,
      amount_cents: cents(f.elements.amount.value),
      as_of: f.elements.as_of.value,
      reason: f.elements.reason.value.trim(),
    };
    invalidatePaymentPreview();
    const inputVersion = paymentInputVersion;
    const data = await api(
      `/api/statement-payments/${f.elements.payment_id.value}/preview`,
      "POST",
      body,
    );
    if (
      generation !== paymentCorrectionGeneration ||
      inputVersion !== paymentInputVersion ||
      !csrf
    )
      return;
    const target = $("#payment-correction-effects");
    target.append(
      el("h3", "Prévia do registro corrigido"),
      el(
        "p",
        `Data da consulta: ${data.as_of.split("-").reverse().join("/")}.`,
      ),
    );
    for (const a of data.accounts)
      target.append(
        el(
          "p",
          a.before_cents === null
            ? `${a.name}: saldo desconhecido na data; confira a referência da conta.`
            : `${a.name}: ${money(a.before_cents)} → ${money(a.after_cents)}.`,
        ),
      );
    target.append(
      el(
        "p",
        `Pago na fatura: ${money(data.statement.paid_before_cents)} → ${money(data.statement.paid_after_cents)}. Restante: ${money(data.statement.remaining_before_cents)} → ${money(data.statement.remaining_after_cents)}.`,
      ),
    );
    for (const c of data.cash_changes)
      target.append(
        el("p", `Mudança no caixa de ${c.month}: ${money(c.delta_cents)}.`),
      );
    target.append(el("p", data.notice));
    paymentCorrectionBody = body;
    $("#confirm-payment-correction").disabled = false;
  });
};
$("#confirm-payment-correction").onclick = () =>
  action(async () => {
    if (!paymentCorrectionBody) return;
    const generation = paymentCorrectionGeneration,
      f = $("#payment-correction-form"),
      body = paymentCorrectionBody;
    paymentCorrectionBody = null;
    $("#confirm-payment-correction").disabled = true;
    await api(
      `/api/statement-payments/${f.elements.payment_id.value}`,
      "PUT",
      body,
    );
    if (generation !== paymentCorrectionGeneration || !csrf) return;
    $("#payment-correction-dialog").close();
    await refreshAfterSave();
    message("Registro de pagamento corrigido. Histórico e saldos atualizados.");
  });
