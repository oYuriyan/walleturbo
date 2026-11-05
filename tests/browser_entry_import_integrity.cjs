const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs"),
  assert = require("assert/strict"),
  { randomUUID } = require("crypto");
const base = "http://localhost:8000";
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8"));
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
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
  let headers;
  try {
    headers = {
      Origin: base,
      "X-CSRF-Token": (
        await (await context.request.get(base + "/api/me")).json()
      ).csrf,
    };
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator('.nav[data-view="transactions"]').click();
    await page.locator('#transactions [data-action="new-entry"]').click();
    const form = page.locator("#entry-form"),
      dialog = page.locator("#entry-dialog");
    await form.locator('[name="description"]').fill("Gasto sintético");
    await form.locator('[name="amount"]').fill("12,34");
    await form.locator('[name="date"]').fill("2026-11-03");
    let refreshed = page.waitForResponse(
      (r) => r.url().includes("/api/transfers?") && r.status() === 200,
    );
    const createdResponse = page.waitForResponse(
      (r) => r.url().endsWith("/api/transactions") && r.status() === 201,
    );
    await form
      .getByRole("button", { name: "Salvar lançamento", exact: true })
      .click();
    const created = await createdResponse,
      original = created.request().postDataJSON(),
      row = await created.json();
    await dialog.waitFor({ state: "hidden" });
    await refreshed;
    const path = base + "/api/transactions/" + row.id;
    let transaction = page
      .locator("#transaction-list .transaction")
      .filter({ hasText: "Gasto sintético" });
    await transaction
      .getByRole("button", { name: "Revisar", exact: true })
      .click();
    await form.locator('[name="amount"]').fill("15,00");
    await form.locator('[name="reason"]').fill("Revisão local");
    assert.equal(
      (
        await context.request.put(path, {
          headers,
          data: {
            ...original,
            request_id: randomUUID(),
            expected_version: 1,
            reason: "Outra sessão",
            amount_cents: 2000,
          },
        })
      ).status(),
      200,
    );
    await form
      .getByRole("button", { name: "Salvar lançamento", exact: true })
      .click();
    await dialog
      .getByText(
        "Lançamento alterado em outra sessão. Recarregue antes de salvar.",
        { exact: true },
      )
      .waitFor();
    await page.locator("#reload-entry").click();
    await page.waitForFunction(
      () =>
        document.querySelector('#entry-form [name="amount"]').value === "20,00",
    );
    await form.locator('[name="amount"]').fill("15,00");
    await form.locator('[name="reason"]').fill("Conferido após recarga");
    refreshed = page.waitForResponse(
      (r) => r.url().includes("/api/transfers?") && r.status() === 200,
    );
    await form
      .getByRole("button", { name: "Salvar lançamento", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
    await refreshed;
    assert.equal(
      (
        await context.request.delete(path + "?expected_version=1", { headers })
      ).status(),
      409,
    );
    page.once("dialog", (d) => d.accept());
    await transaction
      .getByRole("button", { name: "Excluir", exact: true })
      .click();
    await page
      .locator("#transaction-list .transaction")
      .waitFor({ state: "detached" });
    assert.equal(
      (
        await context.request.post(base + "/api/transactions", {
          headers,
          data: original,
        })
      ).status(),
      409,
    );
    const csv =
      "data;descricao;valor;tipo\n2026-11-03;Origem CSV;10,00;despesa\n";
    assert.equal(
      (
        await context.request.post(base + "/api/import/confirm", {
          headers,
          data: { content: csv },
        })
      ).status(),
      200,
    );
    refreshed = page.waitForResponse(
      (r) => r.url().includes("/api/transfers?") && r.status() === 200,
    );
    await page.locator("#month").dispatchEvent("change");
    await refreshed;
    transaction = page
      .locator("#transaction-list .transaction")
      .filter({ hasText: "Origem CSV" });
    page.once("dialog", (d) => d.accept());
    await transaction
      .getByRole("button", { name: "Excluir", exact: true })
      .click();
    await page
      .locator("#transaction-list .transaction")
      .waitFor({ state: "detached" });
    await page.locator("#import-button").click();
    await page.locator("#csv-file").setInputFiles({
      name: "movimentos.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv),
    });
    await page.waitForFunction(
      () => !document.querySelector("#confirm-import").disabled,
    );
    await page.locator("#confirm-import").click();
    await page.locator("#import-dialog").waitFor({ state: "hidden" });
    await page
      .getByText(/excluídas anteriormente não foram recriadas/)
      .waitFor();
    assert.equal(
      await page.locator("#transaction-list .transaction").count(),
      0,
    );
    await page.screenshot({
      path: "artifacts/entry-import-mobile.png",
      fullPage: true,
    });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await page.locator('#transactions [data-action="new-entry"]').click();
    await form.locator('[name="description"]').fill("Não deve permanecer");
    await form.locator('[name="amount"]').fill("3,00");
    assert.equal(
      (
        await context.request.delete(base + "/api/privacy/data", {
          headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
        })
      ).status(),
      200,
    );
    headers = null;
    await form
      .getByRole("button", { name: "Salvar lançamento", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
    assert.equal(await form.locator('[name="description"]').inputValue(), "");
    assert.equal(await form.locator('[name="request_id"]').inputValue(), "");
    assert.equal(await page.locator("#csv-file").inputValue(), "");
    assert.equal(await page.locator("#import-preview").textContent(), "");
    console.log(
      "PASS: lançamento com UUID/versão, conflito/recarga, exclusão obsoleta, reimportação sem recriação e limpeza no mobile.",
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
