const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs"),
  assert = require("assert/strict");
const base = process.env.APP_URL || "http://localhost:8000";
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8"));
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  await context.addCookies([
    {
      name: "walleturbo_session",
      value: seed.sid,
      url: base,
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  const page = await context.newPage();
  await require("./ui_helpers.cjs").respectRateLimits(context, page);
  let headers;
  try {
    const csrf = (await (await context.request.get(base + "/api/me")).json())
      .csrf;
    headers = { Origin: base, "X-CSRF-Token": csrf };
    const account = await (
      await context.request.post(base + "/api/accounts", {
        headers,
        data: { name: "Conta sintética" },
      })
    ).json();
    const card = await (
      await context.request.post(base + "/api/cards", {
        headers,
        data: { name: "Cartão sintético", due_day: 10 },
      })
    ).json();
    // Uma fatura vazia já representa vínculo e impede exclusão do cartão.
    assert.equal(
      (
        await context.request.post(
          base + `/api/cards/${card.id}/statements?month=2026-11`,
          { headers },
        )
      ).status(),
      201,
    );
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await require("./ui_helpers.cjs").navigate(page, "finance");
    const form = page.locator("#lifecycle-form"),
      dialog = page.locator("#lifecycle-dialog");
    const manage = async (id, kind) => {
      await page
        .locator(`[data-entity-id="${id}"]`)
        .getByRole("button", {
          name: kind === "accounts" ? "Gerenciar conta" : "Gerenciar cartão",
          exact: true,
        })
        .click();
    };
    const save = async () => {
      const saved = await form.evaluate((f) => ({
        kind: f.elements.kind.value,
        id: f.elements.id.value,
        version: Number(f.elements.version.value),
      }));
      const completed = page.waitForResponse(
        (response) =>
          response.request().method() === "PUT" &&
          response.url().endsWith(`/api/${saved.kind}/${saved.id}`),
      );
      await form
        .getByRole("button", { name: "Salvar cadastro", exact: true })
        .click();
      assert.equal(
        (await completed).status(),
        200,
        "Salvar cadastro deve ser aceito antes de fechar o diálogo",
      );
      await dialog.waitFor({ state: "hidden" });
      await page.waitForFunction(
        ({ id, version }) =>
          Number(
            document.querySelector(`[data-entity-id="${id}"]`)?.dataset
              .entityVersion,
          ) > version,
        saved,
      );
    };
    await manage(account.id, "accounts");
    // Simular outra sessão antes de salvar; a interface deve exigir recarga explícita.
    assert.equal(
      (
        await context.request.put(base + `/api/accounts/${account.id}`, {
          headers,
          data: {
            name: "Alterada em outra sessão",
            archived: false,
            expected_version: 0,
          },
        })
      ).status(),
      200,
    );
    await form.locator('[name="name"]').fill("Edição obsoleta");
    await form
      .getByRole("button", { name: "Salvar cadastro", exact: true })
      .click();
    await dialog
      .getByText(
        "Cadastro alterado em outra sessão. Atualize antes de salvar.",
        { exact: true },
      )
      .waitFor();
    await page.locator("#reload-lifecycle").click();
    await page.waitForFunction(
      () =>
        document.querySelector('#lifecycle-form [name="name"]').value ===
        "Alterada em outra sessão",
    );
    await form.locator('[name="name"]').fill("Reserva arquivada");
    await form.locator('[name="archived"]').check();
    await save();
    await page
      .locator(`[data-entity-id="${account.id}"]`)
      .getByRole("heading", { name: "Reserva arquivada", exact: true })
      .waitFor();
    await manage(account.id, "accounts");
    await form.locator('[name="archived"]').uncheck();
    await save();
    await manage(account.id, "accounts");
    await form.locator('[name="archived"]').check();
    await save();
    await manage(card.id, "cards");
    await form.locator('[name="archived"]').check();
    await save();
    await manage(card.id, "cards");
    await require("./ui_helpers.cjs").confirmNext(page, async () => {
      await page.locator("#delete-empty-entity").click();
    });
    await dialog
      .getByText(
        "Cadastro possui registros vinculados. Mantenha arquivado para preservar o histórico.",
        { exact: true },
      )
      .waitFor();
    assert(await dialog.isVisible());
    await page.screenshot({
      path: "artifacts/lifecycle-mobile.png",
      fullPage: true,
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await dialog.getByRole("button", { name: "Fechar", exact: true }).click();
    await manage(account.id, "accounts");
    await require("./ui_helpers.cjs").confirmNext(page, async () => {
      await page.locator("#delete-empty-entity").click();
    });
    await dialog.waitFor({ state: "hidden" });
    assert.equal(
      (await (await context.request.get(base + "/api/accounts")).json()).length,
      0,
    );
    // Dados preenchidos devem sumir ao expirar a sessão.
    await manage(card.id, "cards");
    assert(await dialog.isVisible());
    assert.equal(
      (
        await context.request.delete(base + "/api/privacy/data", {
          headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
        })
      ).status(),
      200,
    );
    headers = null;
    // Uma atualização anterior pode receber 401 e fechar o diálogo antes de um
    // clique. Faça o cliente da página observar a expiração em ambos os casos.
    await page.evaluate(async () => {
      await api("/api/accounts").catch(() => {});
    });
    await dialog.waitFor({ state: "hidden" });
    assert.equal(await page.locator("#mode").textContent(), "Sessão encerrada");
    assert.equal(await form.locator('[name="name"]').inputValue(), "");
    assert.equal(await page.locator("#card-list [data-entity-id]").count(), 0);
    console.log(
      "PASS: conflito/recarregamento, renomeação, arquivamento/reativação, exclusão com/sem vínculos e limpeza de sessão no navegador mobile.",
    );
  } finally {
    if (headers)
      await context.request.delete(base + "/api/privacy/data", {
        headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
      });
    await context.close();
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
