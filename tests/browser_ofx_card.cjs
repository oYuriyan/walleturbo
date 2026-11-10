const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("fs"),
  assert = require("assert/strict");
(async () => {
  const seed = JSON.parse(fs.readFileSync(0, "utf8")),
    base = process.env.APP_URL || "http://localhost:8000";
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
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
  const headers = {
    Origin: base,
    "X-CSRF-Token": (await (await context.request.get(base + "/api/me")).json())
      .csrf,
  };
  const page = await context.newPage(),
    errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const source = fs.readFileSync("tests/fixtures/ofx/card-102.ofx", "utf8");
  const file = (text) => ({
    name: "cartao-sintetico.ofx",
    mimeType: "application/x-ofx",
    buffer: Buffer.from(text),
  });
  try {
    const card = await (
      await context.request.post(base + "/api/cards", {
        headers,
        data: { name: "Cartão OFX", due_day: 10 },
      })
    ).json();
    const bills = [];
    for (const month of ["2026-11", "2026-12"])
      bills.push(
        await (
          await context.request.post(
            `${base}/api/cards/${card.id}/statements?month=${month}`,
            { headers },
          )
        ).json(),
      );
    const manual = (
      await (
        await context.request.post(base + "/api/card-purchases", {
          headers,
          data: {
            request_id: require("crypto").randomUUID(),
            card_id: card.id,
            first_month: "2026-11",
            date: "2026-11-03",
            description: "Compra manual OFX",
            amount_cents: 12345,
            installments: 1,
            kind: "expense",
            category: "Outros",
            reviewed: true,
          },
        })
      ).json()
    )[0];
    await page.goto(base);
    await page.getByText("Conta conectada", { exact: true }).waitFor();
    await page.locator("#month").fill("2026-11");
    await page.locator("#month").dispatchEvent("change");
    await page
      .getByRole("button", { name: "Contas e cartões", exact: true })
      .click();
    const open = async (text = source) => {
      await page
        .locator("#statement-list")
        .getByRole("button", { name: "Importar CSV / OFX", exact: true })
        .click();
      await page.locator("#import-format").selectOption("ofx");
      await page.locator("#csv-file").setInputFiles(file(text));
      await page
        .locator("#import-preview input[data-source-index]")
        .first()
        .waitFor();
    };
    await open();
    await page
      .locator('#import-preview select[data-link-index="0"]')
      .selectOption(manual.id);
    const checkboxBounds = await page
      .locator('input[data-source-index="0"]')
      .boundingBox();
    assert(checkboxBounds.width <= 24 && checkboxBounds.height <= 24);
    assert.equal(
      await page.locator("#import-preview [data-ofx-payment]").count(),
      1,
    );
    assert.equal(await page.locator("#import-preview .positive").count(), 1);
    const previewText = await page.locator("#import-preview").textContent();
    assert(
      !previewText.includes("4111111111111111") &&
        !previewText.includes("4111 1111 1111 1111"),
    );
    await page.locator("#import-acknowledgement").check();
    assert(await page.locator("#confirm-import").isDisabled());
    await page.locator("#import-credits-reviewed").check();
    await page.locator('input[data-source-index="2"]').uncheck();
    assert(!(await page.locator("#import-credits-reviewed").isChecked()));
    await page.locator('input[data-source-index="2"]').check();
    await page.locator("#import-credits-reviewed").check();
    await page.locator("#confirm-import").scrollIntoViewIfNeeded();
    await page
      .locator("#import-dialog")
      .screenshot({ path: "artifacts/ofx-card-mobile.png" });
    let response = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/api/statements/${bills[0].id}/import/ofx/confirm`) &&
        r.status() === 200,
    );
    await page.locator("#confirm-import").click();
    const result = await (await response).json();
    assert.equal(result.created, 2);
    assert.equal(result.linked, 1);
    await page.locator("#import-dialog").waitFor({ state: "hidden" });
    const exported = await (
      await context.request.get(base + "/api/privacy/export")
    ).json();
    assert.equal(exported.card_charges.length, 3);
    assert.equal(exported.statement_payments.length, 0);
    assert.equal(exported.transactions.length, 0);
    assert(
      exported.card_charges.every(
        (row) => row.installment === 1 && row.installments === 1,
      ),
    );
    const replay = await context.request.post(
      `${base}/api/statements/${bills[0].id}/import/ofx/confirm`,
      {
        headers,
        data: {
          content: fs.readFileSync("tests/fixtures/ofx/card-220.ofx", "utf8"),
          reviewed: true,
          credits_reviewed: true,
        },
      },
    );
    assert.equal(replay.status(), 200);
    assert.equal((await replay.json()).created, 0);
    await open();
    await page
      .locator('input[data-release-reason="0"]')
      .fill("Destino conferido novamente");
    page.once("dialog", (dialog) => dialog.accept());
    response = page.waitForResponse(
      (r) => r.url().endsWith("/import/ofx/unlink") && r.status() === 200,
    );
    await page.locator('button[data-release-index="0"]').click();
    assert.equal((await (await response).json()).released, 1);
    await page
      .locator('input[data-release-reason="0"]')
      .waitFor({ state: "detached" });
    await page
      .locator('#import-preview select[data-link-index="0"]')
      .selectOption(manual.id);
    await page.locator("#import-acknowledgement").check();
    await page.locator("#import-credits-reviewed").check();
    response = page.waitForResponse(
      (r) => r.url().endsWith("/import/ofx/confirm") && r.status() === 200,
    );
    await page.locator("#confirm-import").click();
    assert.equal((await (await response).json()).linked, 1);
    await page.locator("#import-dialog").waitFor({ state: "hidden" });
    const loaded = page.waitForResponse(
      (r) =>
        r.url().includes("/api/statements?month=2026-12") && r.status() === 200,
    );
    await page.locator("#month").fill("2026-12");
    await page.locator("#month").dispatchEvent("change");
    await loaded;
    await open();
    await page
      .locator("#import-preview")
      .getByText(/Origem já reservada em outra fatura/)
      .first()
      .waitFor();
    await page.locator("#import-acknowledgement").check();
    await page.locator("#import-credits-reviewed").check();
    assert(await page.locator("#confirm-import").isDisabled());
    await page.locator("#import-dialog .close").click();
    await page.waitForFunction(
      () => document.querySelector("#import-preview").textContent === "",
    );
    assert.deepEqual(errors, []);
    console.log(
      "PASS: OFX cartão mobile distingue pagamentos/estornos, exige revisão de créditos, preserva PAN oculto, vincula/desfaz/refaz sem duplicar e bloqueia outra fatura.",
    );
  } finally {
    assert.equal(
      (
        await context.request.delete(base + "/api/privacy/data", {
          headers: { ...headers, "X-Confirm-Delete": "EXCLUIR" },
        })
      ).status(),
      200,
    );
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
