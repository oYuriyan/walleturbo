"use strict";
let pdfStatementId = null,
  pdfToken = null,
  pdfGeneration = 0;
function clearPdf() {
  pdfGeneration++;
  pdfToken = null;
  pdfStatementId = null;
  $("#pdf-form").reset();
  $("#pdf-file").value = "";
  for (const id of ["#pdf-state", "#pdf-warnings", "#pdf-rows", "#pdf-totals"])
    $(id).replaceChildren();
  $("#pdf-confirm").disabled = true;
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
  pdfStatementId = statementId;
  pdfToken = null;
  $("#pdf-form").reset();
  $("#pdf-state").textContent = "";
  $("#pdf-warnings").replaceChildren();
  $("#pdf-rows").replaceChildren();
  $("#pdf-totals").textContent = "";
  $("#pdf-confirm").disabled = true;
  openDialog("#pdf-dialog");
}
$("#pdf-dialog").addEventListener("close", () => {
  pdfGeneration++;
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
      .querySelectorAll("input:not([name=include]),select")
      .forEach((input) => (input.disabled = !checkbox.checked));
  };
  row.addEventListener("input", () => {
    $("#pdf-reviewed").checked = false;
    updatePdfTotal();
  });
  row.addEventListener("change", () => {
    $("#pdf-reviewed").checked = false;
    updatePdfTotal();
  });
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
    $("#pdf-confirm").disabled = !pdfToken || !rows.length;
  } catch {
    $("#pdf-totals").textContent = "Confira os valores antes de importar.";
    $("#pdf-confirm").disabled = true;
  }
}
$("#pdf-file").onchange = () =>
  action(async () => {
    const generation = ++pdfGeneration;
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
    if (!pdfToken || !$("#pdf-reviewed").checked)
      throw Error("Leia o PDF e confirme a revisão antes de importar.");
    const entries = selectedPdfEntries();
    if (
      !entries.length ||
      entries.some((e) => e.amount_cents <= 0 || !e.description)
    )
      throw Error("Confira os lançamentos selecionados.");
    $("#pdf-confirm").disabled = true;
    try {
      const result = await api(
        `/api/statements/${pdfStatementId}/import/pdf/confirm`,
        "POST",
        { preview_token: pdfToken, reviewed: true, entries },
      );
      $("#pdf-dialog").close();
      await refresh();
      message(
        `${result.created} lançamento(s) importado(s); ${result.duplicates} linha(s) já conhecida(s) ignorada(s).${result.removed ? ` ${result.removed} excluída(s) anteriormente não foram recriadas.` : ""} Confira agora o total da fatura.`,
      );
    } finally {
      if ($("#pdf-dialog").open) updatePdfTotal();
    }
  });
};
