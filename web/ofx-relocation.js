"use strict";
function ofxRelocationControls(
  base,
  content,
  index,
  origin,
  destinations,
  version,
  updateSelection,
) {
  const details = el("details"),
    summary = el("summary", `Corrigir competência do lançamento ${index + 1}`);
  details.dataset.relocationIndex = index;
  details.append(summary);
  if (!destinations.length) {
    details.append(
      el(
        "p",
        "Abra a fatura do mês correto em Contas e cartões e refaça esta prévia. O destino precisa ser outra fatura em revisão do mesmo cartão.",
      ),
    );
    return details;
  }
  const destination = el("select"),
    destinationLabel = el("label", "Fatura de destino"),
    reason = el("input"),
    reasonLabel = el("label", "Motivo da mudança de competência"),
    simulate = el("button", "Simular mudança", "button secondary"),
    effects = el("div"),
    acknowledgement = el("input"),
    ackLabel = el("label", undefined, "checkbox"),
    confirmMove = el("button", "Confirmar mudança de competência", "button");
  destination.dataset.relocationDestination = index;
  destination.setAttribute("aria-label", "Fatura de destino");
  for (const row of destinations) {
    const option = el("option", row.month);
    option.value = row.id;
    destination.append(option);
  }
  reason.type = "text";
  reason.minLength = 3;
  reason.maxLength = 160;
  reason.dataset.relocationReason = index;
  acknowledgement.type = "checkbox";
  acknowledgement.disabled = true;
  simulate.type = confirmMove.type = "button";
  confirmMove.disabled = true;
  destinationLabel.append(destination);
  reasonLabel.append(reason);
  ackLabel.append(
    acknowledgement,
    document.createTextNode(
      " Conferi o lançamento e o efeito nas duas faturas.",
    ),
  );
  details.append(
    el(
      "p",
      "Move o lançamento original e sua origem juntos. Valores, data, categoria e conferência são preservados. Vínculos adicionais precisam ser desfeitos antes da mudança.",
    ),
    destinationLabel,
    reasonLabel,
    simulate,
    effects,
    ackLabel,
    confirmMove,
  );
  let prepared = null,
    generation = 0;
  const current = () => version === importVersion;
  const busy = () => $("#confirm-import").dataset.busy === String(version);
  const invalidate = () => {
    generation++;
    prepared = null;
    acknowledgement.checked = false;
    acknowledgement.disabled = confirmMove.disabled = true;
    effects.replaceChildren();
  };
  destination.onchange = reason.oninput = invalidate;
  acknowledgement.onchange = () => {
    confirmMove.disabled = !prepared || !acknowledgement.checked || busy();
  };
  simulate.onclick = () =>
    action(async () => {
      if (!current() || busy()) return;
      invalidate();
      const explanation = reason.value.trim();
      if (explanation.length < 3)
        throw Error("Informe o motivo da mudança (mínimo 3 caracteres).");
      const inputVersion = generation,
        payload = {
          content,
          source_index: index,
          resource_id: origin.resource_id,
          destination_statement_id: destination.value,
          expected_version: origin.target.version,
          expected_origin_version: origin.version,
          reason: explanation,
        };
      $("#confirm-import").dataset.busy = String(version);
      simulate.disabled = true;
      updateSelection();
      try {
        const result = await api(`${base}/relocate/preview`, "POST", payload);
        if (!current() || inputVersion !== generation) return;
        prepared = {
          ...payload,
          expected_revision: result.revision,
          request_id: crypto.randomUUID(),
          reviewed: true,
        };
        effects.append(
          el(
            "p",
            `${result.description} · ${money(result.amount_cents)} · ${result.kind === "refund" ? "Estorno" : "Despesa"}`,
          ),
        );
        for (const row of [result.source, result.destination])
          effects.append(
            el(
              "p",
              `Fatura ${row.month}: total ${money(row.total_before_cents)} → ${money(row.total_after_cents)}; restante ${money(row.remaining_before_cents)} → ${money(row.remaining_after_cents)}.`,
            ),
          );
        effects.append(el("p", result.notice));
        acknowledgement.disabled = false;
      } finally {
        if (busy()) delete $("#confirm-import").dataset.busy;
        simulate.disabled = false;
        updateSelection();
      }
    });
  confirmMove.onclick = () =>
    action(async () => {
      if (!current() || busy() || !prepared || !acknowledgement.checked) return;
      $("#confirm-import").dataset.busy = String(version);
      confirmMove.disabled = simulate.disabled = true;
      updateSelection();
      try {
        await api(`${base}/relocate`, "POST", prepared);
        if (!current()) return;
        $("#import-dialog").close();
        await refresh();
        message(
          "Competência corrigida; lançamento, origem e histórico preservados. Reenvios devem usar a fatura de destino.",
        );
      } finally {
        if (busy()) delete $("#confirm-import").dataset.busy;
        if (current()) {
          invalidate();
          simulate.disabled = false;
          updateSelection();
        }
      }
    });
  return details;
}
