"use strict";
let lifecycleGeneration = 0;
function clearLifecycle() {
  lifecycleGeneration++;
  const f = $("#lifecycle-form");
  f.reset();
  f.querySelectorAll('input[type="hidden"]').forEach((n) => (n.value = ""));
  f.querySelectorAll("input,button").forEach((n) => (n.disabled = true));
  $("#lifecycle-title").textContent = "Gerenciar cadastro";
  $("#delete-empty-entity").hidden = true;
  $("#lifecycle-dialog").querySelector(".dialog-error")?.remove();
  if ($("#lifecycle-dialog").open) $("#lifecycle-dialog").close();
}
function manageEntity(row, kind) {
  if (!csrf || demo)
    throw Error("Entre na conta para gerenciar seus cadastros.");
  lifecycleGeneration++;
  const f = $("#lifecycle-form");
  f.reset();
  f.querySelectorAll("input,button").forEach((n) => (n.disabled = false));
  f.elements.id.value = row.id;
  f.elements.kind.value = kind;
  f.elements.version.value = row.version;
  f.elements.name.value = row.name;
  f.elements.archived.checked = row.archived;
  $("#lifecycle-title").textContent =
    kind === "accounts" ? "Gerenciar conta" : "Gerenciar cartão";
  $("#delete-empty-entity").hidden = !row.archived;
  openDialog("#lifecycle-dialog");
}
$("#lifecycle-form").onsubmit = (e) => {
  e.preventDefault();
  action(async () => {
    const f = e.target,
      submit = f.querySelector('button[type="submit"]');
    if (submit.disabled) return;
    const generation = lifecycleGeneration;
    submit.disabled = true;
    try {
      await api(`/api/${f.elements.kind.value}/${f.elements.id.value}`, "PUT", {
        name: f.elements.name.value.trim(),
        archived: f.elements.archived.checked,
        expected_version: Number(f.elements.version.value),
      });
      if (generation !== lifecycleGeneration) return;
      $("#lifecycle-dialog").close();
      await refresh();
      message("Cadastro atualizado. Histórico e vínculos preservados.");
    } finally {
      if (generation === lifecycleGeneration) submit.disabled = !csrf;
    }
  });
};
$("#reload-lifecycle").onclick = () =>
  action(async () => {
    const f = $("#lifecycle-form"),
      id = f.elements.id.value,
      kind = f.elements.kind.value;
    const generation = lifecycleGeneration;
    await refresh();
    if (generation !== lifecycleGeneration || !csrf) return;
    const row = (kind === "accounts" ? financeAccounts : financeCards).find(
      (row) => row.id === id,
    );
    if (!row) {
      clearLifecycle();
      throw Error("Cadastro não encontrado. A lista foi atualizada.");
    }
    manageEntity(row, kind);
  });
$("#delete-empty-entity").onclick = () =>
  action(async () => {
    const f = $("#lifecycle-form");
    if (
      !confirm(
        "Excluir este cadastro arquivado? A operação será recusada se houver registros vinculados.",
      )
    )
      return;
    const generation = lifecycleGeneration,
      button = $("#delete-empty-entity");
    button.disabled = true;
    try {
      await api(
        `/api/${f.elements.kind.value}/${f.elements.id.value}?expected_version=${f.elements.version.value}`,
        "DELETE",
      );
      if (generation !== lifecycleGeneration) return;
      $("#lifecycle-dialog").close();
      await refresh();
      message("Cadastro vazio excluído.");
    } finally {
      if (generation === lifecycleGeneration) button.disabled = !csrf;
    }
  });
