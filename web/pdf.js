"use strict";
let pdfStatementId = null,
  pdfToken = null,
  pdfGeneration = 0,
  pdfReviewVersion = 0,
  pdfBusy = false;
function clearPdf() {
  pdfGeneration++;
  pdfReviewVersion++;
  pdfBusy = false;
  pdfToken = null;
  pdfStatementId = null;
  $("#pdf-form").reset();
  $("#pdf-file").value = "";
  for (const id of ["#pdf-state", "#pdf-warnings", "#pdf-rows", "#pdf-totals"])
    $(id).replaceChildren();
  $("#pdf-confirm").disabled = true;
  $("#pdf-review-links").disabled = true;
  if ($("#pdf-dialog").open) $("#pdf-dialog").close();
}
function openPdf(statementId) {
  if (!allowed()) return;
  if (demo) {
    message(
      "A leitura de PDF exige conta conectada. Na demonstração, registre compras manualmente.",
    );
    return;
  }
  pdfGeneration++;
  pdfReviewVersion++;
  pdfBusy = false;
  pdfStatementId = statementId;
  pdfToken = null;
  $("#pdf-form").reset();
  $("#pdf-state").textContent = "";
  $("#pdf-warnings").replaceChildren();
  $("#pdf-rows").replaceChildren();
  $("#pdf-totals").textContent = "";
  $("#pdf-confirm").disabled = true;
  $("#pdf-review-links").disabled = true;
  openDialog("#pdf-dialog");
}
$("#pdf-dialog").addEventListener("close", () => {
  pdfGeneration++;
  pdfReviewVersion++;
  pdfToken = null;
  $("#pdf-file").value = "";
  $("#pdf-rows").replaceChildren();
});
function field(label, name, value, type = "text") {
  const wrap = el("label", label),
    input = el("input");
  input.name = name;
  input.type = type;
  input.value = value;
  input.required = true;
  wrap.append(input);
  return wrap;
}
function candidateRow(entry) {
  const row = el("fieldset", undefined, "pdf-row");
  row.dataset.index = entry.source_index;
  row.append(el("legend", `Página ${entry.page} · linha ${entry.line}`));
  const selection = el("label", "Incluir lançamento", "checkbox"),
    checkbox = el("input");
  checkbox.type = "checkbox";
  checkbox.name = "include";
  checkbox.checked = true;
  selection.prepend(checkbox);
  row.append(selection);
  const fields = el("div", undefined, "form-grid");
  const date = field("Data", "date", entry.date, "date"),
    amount = field(
      "Valor (R$)",
      "amount",
      (entry.amount_cents / 100).toFixed(2).replace(".", ","),
    );
  amount.querySelector("input").inputMode = "decimal";
  amount.querySelector("input").pattern = "[0-9]+([,.][0-9]{1,2})?";
  fields.append(date, amount);
  const description = field("Descrição", "description", entry.description);
  description.querySelector("input").maxLength = 160;
  const kindLabel = el("label", "Tipo"),
    kind = el("select");
  kind.name = "kind";
  for (const [value, text] of [
    ["expense", "Compra / encargo"],
    ["refund", "Estorno"],
  ]) {
    const option = el("option", text);
    option.value = value;
    kind.append(option);
  }
  kind.value = entry.kind;
  kindLabel.append(kind);
  const categoryLabel = el("label", "Categoria"),
    category = el("select");
  category.name = "category";
  categories
    .filter((c) => c !== "Renda")
    .forEach((c) => category.append(el("option", c)));
  category.value = entry.category;
  categoryLabel.append(category);
  fields.append(kindLabel, categoryLabel);
  row.append(description, fields);
  checkbox.onchange = () => {
    row
      .querySelectorAll("input:not([name=include]),select,button")
      .forEach(
        (input) =>
          (input.disabled =
            !checkbox.checked || input.dataset.stale === "true"),
      );
  };
  const changed = (event) => {
    pdfReviewVersion++;
    $("#pdf-reviewed").checked = false;
    if (["date", "amount", "kind"].includes(event.target.name)) {
      const destination = row.querySelector("select[data-pdf-link]");
      if (destination) {
        destination.value = "";
        destination.disabled = true;
        destination.dataset.stale = "true";
      }
    }
    updatePdfTotal();
  };
  row.addEventListener("input", changed);
  row.addEventListener("change", changed);
  return row;
}
function selectedPdfEntries() {
  return [...document.querySelectorAll(".pdf-row")]
    .filter((row) => row.querySelector("[name=include]").checked)
    .map((row) => ({
      source_index: Number(row.dataset.index),
      date: row.querySelector("[name=date]").value,
      description: row.querySelector("[name=description]").value.trim(),
      amount_cents: cents(row.querySelector("[name=amount]").value),
      kind: row.querySelector("[name=kind]").value,
      category: row.querySelector("[name=category]").value,
    }));
}
function updatePdfTotal() {
  try {
    const rows = selectedPdfEntries(),
      total = rows.reduce(
        (a, e) => a + e.amount_cents * (e.kind === "refund" ? -1 : 1),
        0,
      );
    $("#pdf-totals").textContent =
      `${rows.length} selecionado(s) · Total líquido: ${money(total)}`;
    $("#pdf-confirm").disabled = !pdfToken || !rows.length || pdfBusy;
    $("#pdf-review-links").disabled = !pdfToken || !rows.length || pdfBusy;
  } catch {
    $("#pdf-totals").textContent = "Confira os valores antes de importar.";
    $("#pdf-confirm").disabled = true;
    $("#pdf-review-links").disabled = true;
  }
}
function renderPdfLinks(data) {
  for (const row of document.querySelectorAll(".pdf-row")) {
    row.querySelector("[data-pdf-reconciliation]")?.remove();
    const index = Number(row.dataset.index),
      origin = data.known_origins?.find((item) => item.source_index === index),
      candidate = data.possible_duplicates?.find(
        (item) => item.source_index === index,
      ),
      area = el("div");
    area.dataset.pdfReconciliation = "";
    if (origin) {
      area.append(
        el(
          "p",
          origin.removed
            ? "Origem conhecida sem registro disponível: não será recriada."
            : `Origem já associada a: ${origin.target.description} · ${money(origin.target.amount_cents)}.`,
        ),
      );
      if (origin.releasable) {
        const label = field(
            "Motivo para desfazer o vínculo",
            "release_reason",
            "",
          ),
          reason = label.querySelector("input"),
          release = el("button", "Desfazer vínculo", "button");
        reason.required = false;
        reason.maxLength = 240;
        release.type = "button";
        release.onclick = () =>
          action(async () => {
            if (pdfBusy || !pdfToken) return;
            const explanation = reason.value.trim();
            if (explanation.length < 3)
              throw Error("Informe o motivo (mínimo 3 caracteres).");
            if (
              !confirm(
                "Desfazer somente o vínculo e reler o arquivo? O lançamento será preservado; edições ainda não importadas serão descartadas.",
              )
            )
              return;
            const generation = pdfGeneration;
            pdfBusy = true;
            updatePdfTotal();
            release.disabled = true;
            try {
              await api(
                `/api/statements/${pdfStatementId}/import/pdf/unlink`,
                "POST",
                {
                  preview_token: pdfToken,
                  release: {
                    source_index: index,
                    resource_id: origin.resource_id,
                    expected_version: origin.target.version,
                    expected_origin_version: origin.version,
                    reason: explanation,
                  },
                },
              );
              if (generation !== pdfGeneration) return;
              message(
                "Vínculo desfeito; lançamento preservado. Confira a nova prévia.",
              );
              $("#pdf-file").onchange();
            } finally {
              if (generation === pdfGeneration) {
                pdfToken = null;
                pdfBusy = false;
                $("#pdf-state").textContent =
                  "Releia o arquivo antes de continuar.";
                updatePdfTotal();
              }
            }
          });
        area.append(label, release);
      }
    }
    if (candidate) {
      area.append(
        el(
          "p",
          `Possíveis duplicatas por data, valor e tipo. Confira o destino; compras legítimas podem coincidir.${candidate.more ? " Mostrando os primeiros 5." : ""}`,
        ),
      );
      const label = el("label", "Destino do lançamento"),
        destination = el("select"),
        original = el("option", "Criar ou reconhecer pela origem");
      original.value = "";
      destination.dataset.pdfLink = index;
      destination.dataset.originVersion = data.origin_versions[index];
      destination.append(original);
      for (const match of candidate.matches) {
        const option = el(
          "option",
          `Vincular a: ${match.description} · ${money(match.amount_cents)} · ${match.id.slice(0, 8)}`,
        );
        option.value = match.id;
        option.dataset.version = match.version;
        destination.append(option);
      }
      label.append(destination);
      area.append(label);
    }
    row.append(area);
    if (!row.querySelector("[name=include]").checked)
      area
        .querySelectorAll("input,select,button")
        .forEach((input) => (input.disabled = true));
  }
}
$("#pdf-review-links").onclick = () =>
  action(async () => {
    if (!pdfToken || pdfBusy) return;
    const generation = pdfGeneration,
      revision = ++pdfReviewVersion;
    pdfBusy = true;
    $("#pdf-reviewed").checked = false;
    updatePdfTotal();
    try {
      const data = await api(
        `/api/statements/${pdfStatementId}/import/pdf/review`,
        "POST",
        {
          preview_token: pdfToken,
          entries: selectedPdfEntries(),
        },
      );
      if (generation !== pdfGeneration || revision !== pdfReviewVersion) return;
      renderPdfLinks(data);
    } finally {
      if (generation === pdfGeneration) {
        pdfBusy = false;
        updatePdfTotal();
      }
    }
  });
$("#pdf-file").onchange = () =>
  action(async () => {
    const generation = ++pdfGeneration;
    pdfReviewVersion++;
    pdfBusy = false;
    pdfToken = null;
    $("#pdf-confirm").disabled = true;
    $("#pdf-reviewed").checked = false;
    $("#pdf-rows").replaceChildren();
    $("#pdf-warnings").replaceChildren();
    $("#pdf-totals").textContent = "";
    const file = $("#pdf-file").files[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) throw Error("PDF excede 2 MB.");
    $("#pdf-state").textContent = "Lendo o documento…";
    try {
      const response = await fetch(
        `/api/statements/${pdfStatementId}/import/pdf/preview`,
        {
          method: "POST",
          headers: { "Content-Type": "application/pdf", "X-CSRF-Token": csrf },
          body: file,
        },
      );
      if (response.status === 401) {
        await api("/api/me");
        return;
      }
      const data = await response.json();
      if (generation !== pdfGeneration) return;
      if (!response.ok)
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : "Não foi possível ler o PDF.",
        );
      pdfToken = data.preview_token;
      $("#pdf-state").textContent =
        `${data.entries.length} candidato(s) em ${data.pages} página(s). Prévia válida por 10 minutos.`;
      data.warnings.forEach((text) => $("#pdf-warnings").append(el("p", text)));
      $("#pdf-warnings").append(
        el(
          "p",
          `${data.skipped_lines} linha(s) não reconhecida(s), incluindo possíveis cabeçalhos e resumos.`,
        ),
      );
      if (data.empty_pages.length)
        $("#pdf-warnings").append(
          el("p", "Páginas sem texto: " + data.empty_pages.join(", ")),
        );
      data.entries.forEach((entry) =>
        $("#pdf-rows").append(candidateRow(entry)),
      );
      renderPdfLinks(data);
      updatePdfTotal();
    } catch (error) {
      if (generation === pdfGeneration)
        $("#pdf-state").textContent = "Leitura não concluída";
      throw error;
    }
  });
$("#pdf-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    if (pdfBusy) return;
    if (!pdfToken || !$("#pdf-reviewed").checked)
      throw Error("Leia o PDF e confirme a revisão antes de importar.");
    const entries = selectedPdfEntries();
    if (
      !entries.length ||
      entries.some((e) => e.amount_cents <= 0 || !e.description)
    )
      throw Error("Confira os lançamentos selecionados.");
    $("#pdf-confirm").disabled = true;
    const generation = pdfGeneration;
    const indices = new Set(entries.map((entry) => entry.source_index));
    const links = [...document.querySelectorAll("select[data-pdf-link]")]
      .filter(
        (select) =>
          select.value &&
          !select.disabled &&
          indices.has(Number(select.dataset.pdfLink)),
      )
      .map((select) => ({
        source_index: Number(select.dataset.pdfLink),
        resource_id: select.value,
        expected_version: Number(select.selectedOptions[0].dataset.version),
        expected_origin_version: Number(select.dataset.originVersion),
      }));
    pdfBusy = true;
    updatePdfTotal();
    try {
      const result = await api(
        `/api/statements/${pdfStatementId}/import/pdf/confirm`,
        "POST",
        { preview_token: pdfToken, reviewed: true, entries, links },
      );
      if (generation !== pdfGeneration) return;
      $("#pdf-dialog").close();
      await refresh();
      message(
        `${result.created} lançamento(s) importado(s); ${result.duplicates} linha(s) já conhecida(s) ignorada(s).${result.linked ? ` ${result.linked} origem(ns) vinculada(s) a registros existentes.` : ""}${result.removed ? ` ${result.removed} excluída(s) anteriormente não foram recriadas.` : ""} Confira agora o total da fatura.`,
      );
    } finally {
      if (generation === pdfGeneration) {
        pdfBusy = false;
        if ($("#pdf-dialog").open) updatePdfTotal();
      }
    }
  });
};
