const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs");
const { randomUUID } = require("crypto");
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8")),
    base = process.env.APP_URL || "http://localhost:8000";
  const browser = await chromium.launch({
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 1000 },
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
  const page = await context.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let csrf;
  try {
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    csrf = (await (await context.request.get(base + "/api/me")).json()).csrf;
    const headers = { Origin: base, "X-CSRF-Token": csrf };
    const card = await (
      await context.request.post(base + "/api/cards", {
        headers,
        data: { name: "Fatura de teste PDF", due_day: 10 },
      })
    ).json();
    await context.request.post(
      `${base}/api/cards/${card.id}/statements?month=2026-11`,
      { headers },
    );
    await page.locator("#month").fill("2026-11");
    await page.locator("#month").dispatchEvent("change");
    await page.getByRole("button", { name: "Contas e cartões" }).click();
    await page.getByRole("button", { name: "Ler PDF", exact: true }).click();
    let originalPreview;
    // Capturar pelo transporte HTTP evita depender do cache de inspeção do Chromium.
    // O upload da interface e a resposta real do parser continuam sendo usados.
    await page.route("**/import/pdf/preview", async (route) => {
      const response = await route.fetch();
      if (response.status() !== 200) throw Error("Prévia real de PDF falhou");
      originalPreview = await response.json();
      await route.fulfill({ response });
    });
    await page
      .locator("#pdf-file")
      .setInputFiles("artifacts/fatura-sintetica.pdf");
    await page.locator(".pdf-row").first().waitFor({ timeout: 20000 });
    if ((await page.locator(".pdf-row").count()) !== 2)
      throw Error("Prévia incompleta");
    const before = await (
      await context.request.get(base + "/api/privacy/export")
    ).json();
    if (before.card_charges.length) throw Error("Prévia persistiu lançamentos");
    await page
      .locator(".pdf-row")
      .first()
      .locator("[name=description]")
      .fill("Mercado revisado");
    await page
      .locator(".pdf-row")
      .first()
      .locator("[name=amount]")
      .fill("120,00");
    await page.locator("#pdf-reviewed").check();
    await page.screenshot({
      path: "artifacts/pdf-desktop.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: "artifacts/pdf-mobile.png", fullPage: true });
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw Error("Overflow mobile");
    await page
      .getByRole("button", { name: "Importar seleção revisada" })
      .click();
    await page.locator("#pdf-dialog").waitFor({ state: "hidden" });
    await page.getByText("Mercado revisado · 1/1", { exact: true }).waitFor();
    const result = await (
      await context.request.get(base + "/api/statements?month=2026-11")
    ).json();
    if (result[0].total_cents !== 9655 || result[0].pending !== 0)
      throw Error("Correção ou estorno não preservados");
    const importedExpense = result[0].charges.find((c) => c.kind === "expense");
    await page
      .locator("#statement-list .transaction")
      .filter({ hasText: "Mercado revisado" })
      .locator(".row-menu > summary")
      .click();
    await page
      .locator("#statement-list .transaction")
      .filter({ hasText: "Mercado revisado" })
      .getByRole("button", { name: "Corrigir importado", exact: true })
      .click();
    const correction = page.locator("#correction-form"),
      dialog = page.locator("#correction-dialog");
    await dialog.waitFor({ state: "visible" });
    if (
      !(await correction
        .locator('[name="installments"]')
        .evaluate((n) => n.readOnly)) ||
      !(await correction
        .locator('[name="first_month"]')
        .evaluate((n) => n.readOnly))
    )
      throw Error("Contexto da origem não foi preservado");
    await correction.locator('[name="amount"]').fill("125,00");
    await correction
      .locator('[name="reason"]')
      .fill("Conferido após importação");
    await correction
      .getByRole("button", { name: "Conferir alterações", exact: true })
      .click();
    await page
      .getByText("2026-11: R$ 96,55 → R$ 101,55", { exact: true })
      .waitFor();
    await page.locator("#confirm-correction").scrollIntoViewIfNeeded();
    await dialog.screenshot({ path: "artifacts/import-correction-mobile.png" });
    const refreshed = page.waitForResponse(
      (r) => r.url().includes("/api/transfers?") && r.status() === 200,
    );
    await page.locator("#confirm-correction").click();
    await dialog.waitFor({ state: "hidden" });
    await refreshed;
    const deleteRevision = (
      await (
        await context.request.get(
          base + "/api/card-operations/" + importedExpense.operation_id,
        )
      ).json()
    ).revision;
    const erased = await context.request.delete(
      base +
        "/api/card-operations/" +
        importedExpense.operation_id +
        "?expected_revision=" +
        deleteRevision,
      { headers },
    );
    if (erased.status() !== 204) throw Error("Exclusão do importado falhou");
    const entries = originalPreview.entries.map(({ page, line, ...e }) => e);
    const repeated = await context.request.post(
      `${base}/api/statements/${result[0].id}/import/pdf/confirm`,
      {
        headers,
        data: {
          preview_token: originalPreview.preview_token,
          reviewed: true,
          entries,
        },
      },
    );
    const repeatedData = await repeated.json();
    if (
      repeated.status() !== 200 ||
      repeatedData.created !== 0 ||
      repeatedData.removed !== 1
    )
      throw Error("PDF recriou origem excluída");
    const repeatedCSV = await context.request.post(
      `${base}/api/statements/${result[0].id}/import/confirm`,
      {
        headers,
        data: {
          content:
            "data;descricao;valor;tipo\n2026-11-03;Mercado;123,45;despesa\n",
        },
      },
    );
    if ((await repeatedCSV.json()).removed !== 1)
      throw Error("CSV não compartilhou a origem do PDF excluído");
    // O ciclo adicional respeita as cotas de importação e de IP.
    await new Promise((resolve) => setTimeout(resolve, 61000));
    const manualResponse = await context.request.post(
      base + "/api/card-purchases",
      {
        headers,
        data: {
          request_id: randomUUID(),
          card_id: card.id,
          first_month: "2026-11",
          date: "2026-11-03",
          description: "Compra manual para conciliar",
          amount_cents: 12000,
          installments: 1,
          kind: "expense",
          category: "Outros",
          reviewed: true,
        },
      },
    );
    if (manualResponse.status() !== 201)
      throw Error("Compra manual sintética falhou");
    const manual = (await manualResponse.json())[0];
    await page.getByRole("button", { name: "Ler PDF", exact: true }).click();
    await page
      .locator("#pdf-file")
      .setInputFiles("artifacts/fatura-conciliacao-sintetica.pdf");
    const aliasRow = page.locator(".pdf-row").first();
    await aliasRow.locator("[name=amount]").fill("120,00");
    await page.locator("#pdf-review-links").click();
    await aliasRow.locator("select[data-pdf-link]").selectOption(manual.id);
    await aliasRow.locator("[name=amount]").fill("120,01");
    await aliasRow.locator("[name=include]").uncheck();
    await aliasRow.locator("[name=include]").check();
    if (
      !(await aliasRow.locator("select[data-pdf-link]").isDisabled()) ||
      (await aliasRow.locator("select[data-pdf-link]").inputValue()) !== ""
    )
      throw Error("Destino antigo continuou disponível após edição");
    await aliasRow.locator("[name=amount]").fill("120,00");
    await page.locator("#pdf-review-links").click();
    await aliasRow.locator("select[data-pdf-link]").selectOption(manual.id);
    await page.locator("#pdf-reviewed").check();
    const linkedResponse = page.waitForResponse(
      (r) => r.url().endsWith("/import/pdf/confirm") && r.status() === 200,
    );
    await page.locator("#pdf-confirm").click();
    if ((await (await linkedResponse).json()).linked !== 1)
      throw Error("PDF não vinculou o destino revisado");
    await page.locator("#pdf-dialog").waitFor({ state: "hidden" });
    await page.getByRole("button", { name: "Ler PDF", exact: true }).click();
    await page
      .locator("#pdf-file")
      .setInputFiles("artifacts/fatura-conciliacao-sintetica.pdf");
    const reason = page.locator('.pdf-row [name="release_reason"]');
    await reason.fill("Destino conferido novamente");
    await page
      .getByRole("button", { name: "Desfazer vínculo", exact: true })
      .scrollIntoViewIfNeeded();
    await page.locator("#pdf-dialog").screenshot({
      path: "artifacts/pdf-link-mobile.png",
    });
    page.once("dialog", (dialog) => dialog.accept());
    const releasedResponse = page.waitForResponse(
      (r) => r.url().endsWith("/import/pdf/unlink") && r.status() === 200,
    );
    await page
      .getByRole("button", { name: "Desfazer vínculo", exact: true })
      .click();
    if ((await (await releasedResponse).json()).released !== 1)
      throw Error("Desfazimento PDF falhou");
    await reason.waitFor({ state: "detached" });
    await page
      .locator(".pdf-row")
      .first()
      .locator("[name=amount]")
      .fill("120,00");
    await page.locator("#pdf-review-links").click();
    await page.locator("select[data-pdf-link]").selectOption(manual.id);
    await page.locator("#pdf-reviewed").check();
    const relinkedResponse = page.waitForResponse(
      (r) => r.url().endsWith("/import/pdf/confirm") && r.status() === 200,
    );
    await page.locator("#pdf-confirm").click();
    if ((await (await relinkedResponse).json()).linked !== 1)
      throw Error("Remapeamento PDF falhou");
    await page.locator("#pdf-dialog").waitFor({ state: "hidden" });
    const finalCharges = (
      await (await context.request.get(base + "/api/privacy/export")).json()
    ).card_charges;
    if (
      finalCharges.length !== 2 ||
      finalCharges.find((c) => c.id === manual.id).amount_cents !== 12000
    )
      throw Error(
        "Conciliação alterou os valores ou a quantidade de lançamentos",
      );
    if (errors.length) throw Error(errors.join("\n"));
    console.log(
      "PASS: PDF real no navegador: revisão, estorno, correção, proteção após exclusão, consulta de destinos revisados, vínculo/desfazimento/releitura e nova associação sem alterar os valores no mobile.",
    );
  } finally {
    if (csrf) {
      const clean = await context.request.delete(base + "/api/privacy/data", {
        headers: {
          Origin: base,
          "X-CSRF-Token": csrf,
          "X-Confirm-Delete": "EXCLUIR",
        },
      });
      if (clean.status() !== 200) throw Error("Limpeza sintética falhou");
    }
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
